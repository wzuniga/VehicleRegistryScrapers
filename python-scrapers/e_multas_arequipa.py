import logging
import requests
import time
from datetime import datetime
import json

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultasArequipaScraper:
    def __init__(self):
        self.url = 'https://www.muniarequipa.gob.pe/oficina-virtual/c0nInfrPermisos/faltas/buscar.php'
        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.8',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://www.muniarequipa.gob.pe',
            'priority': 'u=1, i',
            'referer': 'https://www.muniarequipa.gob.pe/oficina-virtual/c0nInfrPermisos/faltas/papeletas.php',
            'sec-ch-ua': '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-gpc': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }
        self.cookies = {
            # 'PHPSESSID': 'ge0f2ca62iml0tuceu4nf3p08h',
            # 'cf_clearance': '6LqJMD_XOB8S2bASyBvtCOddIPvVj3VwSFClCccUA6Q-1765253719-1.2.1.1-Qou871sNh8Ze06q94zHJ72jdMpOfmQMO4Gs_nJ.Iq_XTwWgaHckS4GlT3ti25WKgRLcGFzJJP2APoo3417QjSHVrdxYLD3pKngOHGzUVve7K.Qx_cVfJqMnV6Y81jdICINrHWSgIr0bvZb.cDP_DG0dYQHee7EW0DaD6EBmJBcXrLa6MC.PlR5cXjWj5tlkd2H4MISrSC1sFbvMfrXjpMG0bJzBwTEcZbuKIXEicDbY'
        }
    
    def query_multas(self, plate_number):
        """Consulta las multas de una placa específica"""
        try:
            logger.info(f'🔍 Consultando multas para placa: {plate_number}')
            
            # Preparar el payload con la placa
            data = f'placa={plate_number.lower()}'
            
            logger.info(f'📊 URL: {self.url}')
            logger.info(f'📋 Payload: {data}')
            
            # Hacer la petición POST
            response = requests.post(
                self.url,
                headers=self.headers,
                cookies=self.cookies,
                data=data,
                timeout=30
            )
            
            # Verificar respuesta
            if response.status_code == 200:
                logger.info(f'✅ Respuesta recibida ({response.status_code})')
                response_text = response.text.strip()
                
                logger.info(f'📄 Respuesta: {response_text}')
                
                # Verificar si no se encontraron resultados
                if "No se encontraron resultados" in response_text:
                    logger.info('ℹ️ No se encontraron multas para esta placa')
                    return {
                        'success': True,
                        'has_results': False,
                        'message': 'No se encontraron resultados'
                    }
                
                # Si hay resultados, la respuesta contendrá datos
                return {
                    'success': True,
                    'has_results': True,
                    'raw_response': response_text
                }
            else:
                logger.error(f'❌ Error en la petición. Status: {response.status_code}')
                logger.error(f'📄 Respuesta: {response.text}')
                return None
                
        except Exception as e:
            logger.error(f'❌ Error consultando multas: {e}')
            return None
    
    def send_to_api(self, plate_number, multas_data, plate_id):
        """Envía los datos de multas al endpoint correspondiente"""
        try:
            logger.info('📤 Enviando datos a la API...')
            
            # URL del endpoint (ajustar según el endpoint real)
            api_url = 'http://143.110.206.161:3000/multas-arequipa'
            
            # Payload
            payload = {
                'plateNumber': plate_number,
                'data': multas_data
            }
            
            # Headers
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json'
            }
            
            logger.info(f'📊 Enviando datos para placa: {plate_number}')
            
            # Enviar request POST
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            
            # Verificar respuesta
            if response.status_code in [200, 201]:
                logger.info(f'✅ Datos enviados exitosamente')
                
                # Marcar placa como cargada en la API
                logger.info(f'📝 Marcando placa {plate_id} como cargada...')
                mark_loaded_url = f'http://143.110.206.161:3000/pending-car-plates/{plate_id}/mark-loaded/E'
                mark_response = requests.patch(mark_loaded_url, headers={'accept': '*/*'}, timeout=10)
                mark_response.raise_for_status()
                logger.info(f'✅ Placa {plate_id} marcada como cargada')
                
                return True
            else:
                logger.error(f'❌ Error al enviar datos. Status: {response.status_code}, Respuesta: {response.text}')
                return False
                
        except Exception as e:
            logger.error(f'❌ Error enviando datos a la API: {e}')
            return False
    
    def process_plate(self, plate_number, plate_id):
        """Procesa una placa individual"""
        try:
            logger.info(f'📋 Procesando placa: {plate_number}')
            
            # Consultar multas
            multas_data = self.query_multas(plate_number)
            if not multas_data:
                logger.error('❌ No se pudieron obtener los datos de multas')
                return False
            
            # Enviar datos a la API
            if not self.send_to_api(plate_number, multas_data, plate_id):
                logger.warning('⚠️ No se pudieron enviar los datos a la API')
                return False
            
            logger.info('✅ Placa procesada exitosamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error procesando placa: {e}')
            return False


def get_pending_plate():
    """
    Obtiene la primera placa pendiente de la API
    
    Returns:
        dict: Diccionario con la información de la placa o None si hay error
    """
    try:
        logger.info('🌐 Obteniendo placa pendiente de la API...')
        
        url = 'http://143.110.206.161:3000/pending-car-plates/unloaded/E/first'
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


def main():
    """Función principal"""
    logger.info('=' * 60)
    logger.info('🚗 Multas Arequipa Scraper - Python')
    logger.info('=' * 60)
    
    scraper = MultasArequipaScraper()
    
    try:
        while True:
            try:
                # Obtener placa pendiente de la API
                plate_data = get_pending_plate()
                
                if not plate_data:
                    logger.info('⏳ No hay placas pendientes, esperando 2 segundos...')
                    time.sleep(2)
                    continue
                
                plate_number = plate_data.get('plate')
                plate_id = plate_data.get('id')
                
                if not plate_number:
                    logger.error('❌ La respuesta de la API no contiene una placa válida')
                    time.sleep(2)
                    continue
                
                logger.info(f'\n📋 Procesando:')
                logger.info(f'   🆔 ID: {plate_id}')
                logger.info(f'   🚙 Placa: {plate_number}')
                
                # Procesar placa
                success = scraper.process_plate(plate_number, plate_id)
                
                if success:
                    logger.info('✅ Placa procesada exitosamente')
                else:
                    logger.warning('⚠️ Fallo al procesar placa')
                
                # Pequeña pausa entre procesamiento de placas
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                logger.info('\n🛑 Proceso interrumpido por el usuario')
                break
            except Exception as e:
                logger.error(f'❌ Error inesperado en el ciclo: {e}')
                time.sleep(2)
                
    finally:
        logger.info('👋 Scraper finalizado')


if __name__ == '__main__':
    main()
