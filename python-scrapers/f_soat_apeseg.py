import time
import logging
import json
import requests
import urllib3

# Suprimir warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ApesegSoatScraper:
    def __init__(self):
        self.access_token = None
        self.base_url = 'https://webapp.apeseg.org.pe/consulta-soat/api'
        self.login_url = f'{self.base_url}/login'
        self.credentials = {
            'email': 'notificaciones@apeseg.org.pe',
            'password': 'G3sepa13579!'
        }
    
    def get_base_headers(self):
        """Retorna los headers base para las peticiones"""
        return {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.8',
            'Connection': 'keep-alive',
            'Referer': 'https://webapp.apeseg.org.pe/consulta-soat/resultados',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-GPC': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Brave";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
    
    def login(self):
        """
        Realiza el login y obtiene el access_token.
        Este método solo se ejecuta una vez, y se re-ejecuta si un paso siguiente falla.
        """
        try:
            logger.info('🔐 Iniciando sesión en APESEG...')
            
            headers = self.get_base_headers()
            headers['Content-Type'] = 'application/json'
            headers['Origin'] = 'https://webapp.apeseg.org.pe'
            
            response = requests.post(
                self.login_url,
                headers=headers,
                json=self.credentials,
                timeout=30,
                verify=False  # Desactivar verificación SSL
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                
                if self.access_token:
                    logger.info('✅ Login exitoso, access_token obtenido')
                    logger.info(f'🔑 Token: {self.access_token[:20]}...')
                    return True
                else:
                    logger.error('❌ Respuesta sin access_token')
                    # logger.error(f'📄 Respuesta: {data}')
                    return False
            else:
                logger.error(f'❌ Error en login. Status: {response.status_code}')
                logger.error(f'📄 Respuesta: {response.text}')
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f'❌ Error de conexión en login: {e}')
            return False
        except Exception as e:
            logger.error(f'❌ Error inesperado en login: {e}')
            return False
    
    def consult_plate(self, plate_number):
        """
        Consulta la información SOAT de una placa.
        
        Args:
            plate_number: Número de placa a consultar
            
        Returns:
            dict: Información del SOAT o None si hay error
        """
        if not self.access_token:
            logger.error('❌ No hay access_token. Ejecute login() primero.')
            return None
        
        try:
            logger.info(f'🚗 Consultando placa: {plate_number}')
            
            # Headers para la consulta de certificados
            auth_headers = self.get_base_headers()
            auth_headers['Authorization'] = f'Bearer {self.access_token}'
            auth_headers['X-Referrer'] = 'https://www.apeseg.org.pe/'
            auth_headers['X-Source'] = 'unknown'
            
            # Endpoint de consulta de certificados por placa
            consult_url = f'{self.base_url}/certificados/placa/{plate_number}'
            
            response = requests.get(
                consult_url,
                headers=auth_headers,
                timeout=30,
                verify=False  # Desactivar verificación SSL
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f'✅ Consulta completada para placa: {plate_number}')
                logger.info(f'📄 Respuesta: {json.dumps(data, indent=2, ensure_ascii=False)}')
                return data
            elif response.status_code == 401:
                logger.error('❌ Token expirado o inválido')
                return None
            else:
                logger.error(f'❌ Error en consulta. Status: {response.status_code}')
                logger.error(f'� Respuesta: {response.text}')
                return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f'❌ Error de conexión consultando placa: {e}')
            return None
        except Exception as e:
            logger.error(f'❌ Error inesperado consultando placa: {e}')
            return None

    def get_max_version(self, plate):
        """
        Obtiene la versión máxima registrada para una placa en la API.
        """
        try:
            url = f'http://54.204.68.114:3000/soat-apeseg/plate/{plate}/max-version'
            response = requests.get(url, headers={'accept': '*/*'}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Si data es un diccionario como {"maxVersion": 1}, extraer el valor
                if isinstance(data, dict):
                    return data.get('maxVersion', 0)
                # Si data es directamente el número
                return int(data)
            return 0
        except Exception as e:
            logger.error(f'❌ Error obteniendo versión máxima: {e}')
            return 0

    def send_to_api(self, payload):
        """
        Envía los datos de un certificado a la API de soat-apeseg.
        """
        try:
            url = 'http://54.204.68.114:3000/soat-apeseg'
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json'
            }
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code in [200, 201]:
                logger.info(f'✅ Datos guardados satisfactoriamente para poliza {payload.get("numeroPoliza")}')
                return True
            else:
                logger.error(f'❌ Error guardando en API ({response.status_code}): {response.text}')
                return False
        except Exception as e:
            logger.error(f'❌ Error en request a API: {e}')
            return False

    def run(self, plate_number=None):
        """
        Ejecuta la consulta completa para una placa y guarda los resultados.
        """
        try:
            if not plate_number:
                logger.error('❌ Error: Falta el parámetro obligatorio "plate_number"')
                return False
            
            logger.info(f'📋 Procesando placa: {plate_number}')
            
            # Consultar placa en APESEG
            certificates = self.consult_plate(plate_number)
            
            if certificates is not None:
                # Obtener versión actual + 1
                current_version = self.get_max_version(plate_number)
                next_version = current_version + 1
                logger.info(f'🔢 Versión para esta carga: {next_version}')

                # APESEG suele devolver una lista de certificados o un objeto con una lista
                if isinstance(certificates, dict) and 'certificados' in certificates:
                    cert_list = certificates['certificados']
                elif isinstance(certificates, list):
                    cert_list = certificates
                else:
                    cert_list = [certificates] if certificates else []

                if not cert_list:
                    logger.info(f'ℹ️ No se encontraron certificados para {plate_number}')
                    return True

                success_count = 0
                for cert in cert_list:
                    # Mapear datos de APESEG al payload de la API (Usando PascalCase según log)
                    payload = {
                        "version": next_version,
                        "plate": plate_number,
                        "nombreCompania": cert.get('NombreCompania'),
                        "fechaInicio": cert.get('FechaInicio'),
                        "fechaFin": cert.get('FechaFin'),
                        "numeroPoliza": cert.get('NumeroPoliza'),
                        "nombreUsoVehiculo": cert.get('NombreUsoVehiculo'),
                        "nombreClaseVehiculo": cert.get('NombreClaseVehiculo'),
                        "estado": cert.get('Estado'),
                        "codigoUnicoPoliza": cert.get('CodigoUnicoPoliza'),
                        "codigoSBSAseguradora": cert.get('CodigoSBSAseguradora'),
                        "fechaControlPolicial": cert.get('FechaControlPolicial'),
                        "nombreContratante": cert.get('NombreContratante'),
                        "nombreUbigeo": cert.get('NombreUbigeo'),
                        "numeroSerieMotor": cert.get('NumeroSerieMotor'),
                        "numeroSerieChasis": cert.get('NumeroSerieChasis'),
                        "numeroAseguradora": cert.get('NumeroAseguradora'),
                        "tipoCertificado": cert.get('TipoCertificado'),
                        "fechaCreacion": cert.get('FechaCreacion'),
                        "numeroAsientos": str(cert.get('NumeroAsientos')) if cert.get('NumeroAsientos') is not None else None,
                        "modeloVehiculo": cert.get('ModeloVehiculo'),
                        "marca": cert.get('Marca'),
                        "createdBy": 1
                    }
                    
                    if self.send_to_api(payload):
                        success_count += 1
                
                return success_count > 0
            else:
                logger.error(f'❌ No se pudo obtener información para {plate_number}')
                return False

                
        except Exception as e:
            logger.error(f'❌ Error en run: {e}')
            return None


def get_pending_plate():
    """
    Obtiene la primera placa pendiente de la API para la categoría F
    
    Returns:
        dict: Diccionario con la información de la placa o None si hay error
    """
    try:
        logger.info('🌐 Obteniendo placa pendiente de la API (Categoría F)...')
        
        url = 'http://54.204.68.114:3000/pending-car-plates/unloaded/F/first'
        headers = {'accept': '*/*'}
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        logger.info(f'✅ Placa obtenida: {data.get("plate")} (ID: {data.get("id")})')
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f'❌ Error obteniendo placa de la API: {e}')
        return None
    except Exception as e:
        logger.error(f'❌ Error inesperado: {e}')
        return None


def mark_plate_as_loaded(plate_id):
    """
    Marca una placa como cargada en la API para evitar procesarla nuevamente.
    """
    try:
        logger.info(f'📝 Marcando placa {plate_id} como cargada...')
        mark_loaded_url = f'http://54.204.68.114:3000/pending-car-plates/{plate_id}/mark-loaded/F'
        response = requests.patch(mark_loaded_url, headers={'accept': '*/*'}, timeout=10)
        response.raise_for_status()
        logger.info(f'✅ Placa {plate_id} marcada como cargada')
        return True
    except Exception as e:
        logger.error(f'❌ Error marcando placa como cargada: {e}')
        return False


def main():
    """Función principal - Modo automático procesando placas de la API"""
    logger.info('=' * 60)
    logger.info('🚗 APESEG SOAT Scraper - Python')
    logger.info('=' * 60)
    
    # Crear instancia del scraper
    scraper = ApesegSoatScraper()
    
    # Login inicial (solo se ejecuta una vez)
    if not scraper.login():
        logger.error('❌ No se pudo iniciar sesión. Abortando.')
        return
    
    logger.info('✅ Sesión iniciada. Procesando placas de la API...')
    
    while True:
        try:
            # Obtener placa pendiente de la API
            plate_data = get_pending_plate()
            
            if not plate_data:
                logger.info('⏳ No hay placas pendientes, esperando 5 segundos...')
                time.sleep(5)
                continue
            
            plate_number = plate_data.get('plate')
            plate_id = plate_data.get('id')
            
            if not plate_number:
                logger.error('❌ La respuesta de la API no contiene una placa válida')
                time.sleep(2)
                continue
            
            logger.info(f'📋 Procesando:')
            logger.info(f'   🆔 ID: {plate_id}')
            logger.info(f'   🚙 Placa: {plate_number}')
            
            # Ejecutar consulta
            result = scraper.run(plate_number=plate_number)
            
            if result:
                logger.info(f'✅ Consulta exitosa para {plate_number}')
                # Marcar como cargada para pasar a la siguiente
                mark_plate_as_loaded(plate_id)
            else:
                logger.error(f'❌ La consulta falló para {plate_number}')
                # Si falla, intentar re-login por si el token expiró
                logger.info('🔄 Intentando re-login...')
                if scraper.login():
                    # Reintentar consulta
                    result = scraper.run(plate_number=plate_number)
                    if result:
                        logger.info(f'✅ Consulta exitosa para {plate_number} después de re-login')
                        mark_plate_as_loaded(plate_id)
                    else:
                        logger.error(f'❌ Consulta falló nuevamente para {plate_number}')
                        time.sleep(2)
                else:
                    logger.error('❌ Re-login fallido. Esperando antes de continuar...')
                    time.sleep(5)
            
            # Pequeña pausa entre procesamiento de placas
            time.sleep(1)
            
        except KeyboardInterrupt:
            logger.info('\n👋 Proceso interrumpido por el usuario')
            break
        except Exception as e:
            logger.error(f'❌ Error inesperado en el ciclo principal: {e}')
            time.sleep(5)
            continue


if __name__ == '__main__':
    main()


