import logging
import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = 'https://webapp.apeseg.org.pe/consulta-soat/api'
API_URL = 'http://54.204.68.114:3000'

_BASE_HEADERS = {
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive',
    'Referer': 'https://webapp.apeseg.org.pe/consulta-soat/resultados',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-GPC': '1',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
    ),
    'sec-ch-ua': '"Chromium";v="147", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}


class ApesegSoatScraper:
    def __init__(self):
        self.access_token = None
        self.credentials = {
            'email': 'notificaciones@apeseg.org.pe',
            'password': 'G3sepa13579!',
        }

    def login(self):
        try:
            headers = {**_BASE_HEADERS, 'Content-Type': 'application/json', 'Origin': 'https://webapp.apeseg.org.pe'}
            resp = requests.post(
                f'{BASE_URL}/login',
                headers=headers,
                json=self.credentials,
                timeout=30,
                verify=False,
            )
            if resp.status_code == 200:
                self.access_token = resp.json().get('access_token')
                if self.access_token:
                    logger.info('Login successful')
                    return True
                logger.error('Login response missing access_token')
                return False
            logger.error(f'Login failed: {resp.status_code}')
            return False
        except Exception as e:
            logger.error(f'Login error: {e}')
            return False

    def consult_plate(self, plate_number):
        if not self.access_token:
            logger.error('No access_token — call login() first')
            return None
        try:
            headers = {
                **_BASE_HEADERS,
                'Authorization': f'Bearer {self.access_token}',
                'X-Referrer': 'https://www.apeseg.org.pe/',
                'X-Source': 'unknown',
            }
            resp = requests.get(
                f'{BASE_URL}/certificados/placa/{plate_number}',
                headers=headers,
                timeout=30,
                verify=False,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                logger.warning('Token expired or invalid')
                return None
            logger.error(f'Consult failed: {resp.status_code}')
            return None
        except Exception as e:
            logger.error(f'Error consulting plate {plate_number}: {e}')
            return None

    def get_max_version(self, plate):
        try:
            resp = requests.get(
                f'{API_URL}/soat-apeseg/plate/{plate}/max-version',
                headers={'accept': '*/*'},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get('maxVersion', 0) if isinstance(data, dict) else int(data)
            return 0
        except Exception as e:
            logger.error(f'Error getting max version: {e}')
            return 0

    def send_to_api(self, payload):
        try:
            resp = requests.post(
                f'{API_URL}/soat-apeseg',
                headers={'accept': '*/*', 'Content-Type': 'application/json'},
                json=payload,
                timeout=10,
            )
            if resp.status_code in [200, 201]:
                return True
            logger.error(f'API error ({resp.status_code}): {resp.text}')
            return False
        except Exception as e:
            logger.error(f'Error sending to API: {e}')
            return False

    def run(self, plate_number):
        try:
            certificates = self.consult_plate(plate_number)
            if certificates is None:
                return False

            if isinstance(certificates, dict) and 'certificados' in certificates:
                cert_list = certificates['certificados']
            elif isinstance(certificates, list):
                cert_list = certificates
            else:
                cert_list = [certificates] if certificates else []

            if not cert_list:
                logger.info(f'No certificates found for {plate_number}')
                return True

            next_version = self.get_max_version(plate_number) + 1
            success_count = 0
            for cert in cert_list:
                payload = {
                    'version': next_version,
                    'plate': plate_number,
                    'nombreCompania': cert.get('NombreCompania'),
                    'fechaInicio': cert.get('FechaInicio'),
                    'fechaFin': cert.get('FechaFin'),
                    'numeroPoliza': cert.get('NumeroPoliza'),
                    'nombreUsoVehiculo': cert.get('NombreUsoVehiculo'),
                    'nombreClaseVehiculo': cert.get('NombreClaseVehiculo'),
                    'estado': cert.get('Estado'),
                    'codigoUnicoPoliza': cert.get('CodigoUnicoPoliza'),
                    'codigoSBSAseguradora': cert.get('CodigoSBSAseguradora'),
                    'fechaControlPolicial': cert.get('FechaControlPolicial'),
                    'nombreContratante': cert.get('NombreContratante'),
                    'nombreUbigeo': cert.get('NombreUbigeo'),
                    'numeroSerieMotor': cert.get('NumeroSerieMotor'),
                    'numeroSerieChasis': cert.get('NumeroSerieChasis'),
                    'numeroAseguradora': cert.get('NumeroAseguradora'),
                    'tipoCertificado': cert.get('TipoCertificado'),
                    'fechaCreacion': cert.get('FechaCreacion'),
                    'numeroAsientos': str(cert.get('NumeroAsientos')) if cert.get('NumeroAsientos') is not None else None,
                    'modeloVehiculo': cert.get('ModeloVehiculo'),
                    'marca': cert.get('Marca'),
                    'createdBy': 1,
                }
                if self.send_to_api(payload):
                    success_count += 1

            return success_count > 0
        except Exception as e:
            logger.error(f'run() error: {e}')
            return False


def get_pending_plate():
    try:
        resp = requests.get(
            f'{API_URL}/pending-car-plates/unloaded/F/first',
            headers={'accept': '*/*'},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f'Pending plate: {data.get("plate")} (id={data.get("id")})')
        return data
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        logger.error(f'Error fetching pending plate: {e}')
        return None
    except Exception as e:
        logger.error(f'Error fetching pending plate: {e}')
        return None


def mark_plate_as_loaded(plate_id):
    try:
        requests.patch(
            f'{API_URL}/pending-car-plates/{plate_id}/mark-loaded/F',
            headers={'accept': '*/*'},
            timeout=10,
        ).raise_for_status()
        logger.info(f'Plate {plate_id} marked as loaded')
        return True
    except Exception as e:
        logger.error(f'Error marking plate as loaded: {e}')
        return False


def main():
    logger.info('=' * 60)
    logger.info('APESEG SOAT Scraper — production loop')
    logger.info('=' * 60)

    scraper = ApesegSoatScraper()
    if not scraper.login():
        logger.error('Initial login failed — aborting')
        return

    while True:
        try:
            plate_data = get_pending_plate()

            if not plate_data:
                logger.info('No pending plates — waiting 2s...')
                time.sleep(2)
                continue

            plate_number = plate_data.get('plate')
            plate_id = plate_data.get('id')

            if not plate_number:
                logger.error('API response missing plate field')
                time.sleep(2)
                continue

            logger.info(f'Processing plate={plate_number} id={plate_id}')
            result = scraper.run(plate_number=plate_number)

            if result:
                mark_plate_as_loaded(plate_id)
            else:
                logger.warning(f'Plate {plate_number} failed — attempting re-login...')
                if scraper.login():
                    result = scraper.run(plate_number=plate_number)
                    if result:
                        mark_plate_as_loaded(plate_id)
                    else:
                        logger.error(f'Plate {plate_number} failed after re-login — skipping')
                        time.sleep(2)
                else:
                    logger.error('Re-login failed — waiting 5s...')
                    time.sleep(5)

            time.sleep(1)

        except KeyboardInterrupt:
            logger.info('Stopped by user')
            break
        except Exception as e:
            logger.error(f'Unexpected loop error: {e}')
            time.sleep(5)


if __name__ == '__main__':
    main()
