import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import os
import json
import requests

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SBSScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://servicios.sbs.gob.pe/reportesoat/BusquedaPlaca'
        
    def setup_driver(self, headless=False):
        """Configura el driver de Chrome con opciones anti-detección"""
        logger.info('🚀 Configurando Chrome driver...')
        
        options = uc.ChromeOptions()
        
        # Opciones básicas para evitar detección
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        
        # Modo headless configurable
        if headless:
            options.add_argument('--headless=new')
            logger.info('🔇 Modo headless activado')
        else:
            logger.info('👁️ Modo headless desactivado (navegador visible)')
        
        # Configurar viewport
        options.add_argument('--window-size=1250,750')
        
        # Preferencias adicionales
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
        }
        options.add_experimental_option('prefs', prefs)
        
        try:
            # undetected_chromedriver maneja automáticamente la mayoría de opciones anti-detección
            # version_main debe coincidir con la versión mayor de Chrome instalada
            self.driver = uc.Chrome(options=options, version_main=141)
            logger.info('✅ Chrome driver configurado exitosamente')
            
            # Ejecutar scripts anti-detección adicionales
            try:
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': '''
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['es-ES', 'es', 'en-US', 'en']
                        });
                        
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });
                        
                        window.chrome = {
                            runtime: {}
                        };
                    '''
                })
                logger.info('✅ Scripts anti-detección inyectados')
            except Exception as cdp_error:
                logger.warning(f'⚠️ No se pudieron inyectar scripts CDP: {cdp_error}')
                logger.info('ℹ️ Continuando sin scripts CDP adicionales')
            
            return True
        except Exception as e:
            logger.error(f'❌ Error configurando driver: {e}')
            return False
    
    def navigate_to_page(self):
        """Navega a la página de reporte SOAT de SBS"""
        try:
            logger.info(f'🌐 Navegando a {self.url}...')
            self.driver.get(self.url)
            
            # Esperar a que la página cargue
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            
            logger.info('✅ Página cargada exitosamente')
            
            # Esperar un poco más para asegurar carga completa
            time.sleep(3)
            
            return True
        except Exception as e:
            logger.error(f'❌ Error navegando a la página: {e}')
            return False
    
    def fill_plate_number(self, plate):
        """Llena el campo de número de placa"""
        try:
            logger.info(f'🚙 Llenando número de placa: {plate}')
            
            plate_input_xpath = '/html/body/div[4]/div/div/div/form/div[3]/div/div[2]/div/div[1]/div[1]/span/input'
            
            # Esperar a que el input esté presente
            plate_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, plate_input_xpath))
            )
            
            # Limpiar el campo primero
            plate_input.clear()
            
            # Escribir la placa con pequeñas pausas para simular escritura humana
            for char in plate:
                plate_input.send_keys(char)
                time.sleep(0.1)
            
            logger.info('✅ Número de placa ingresado correctamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error llenando número de placa: {e}')
            return False
    
    def select_radio_button(self, index=1):
        """Selecciona el radio button según el índice (1, 2 o 3)"""
        try:
            logger.info(f'🔘 Seleccionando radio button {index}...')
            
            radio_button_xpath = f'/html/body/div[4]/div/div/div/form/div[3]/div/div[2]/div/div[2]/div/table/tbody/tr/td[{index}]/input'
            
            # Esperar a que el radio button esté presente y clickeable
            radio_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, radio_button_xpath))
            )
            
            logger.info(f'✅ Radio button {index} encontrado, haciendo click...')
            radio_button.click()
            
            # Esperar un momento después del click
            time.sleep(1)
            
            logger.info(f'✅ Radio button {index} seleccionado')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error seleccionando radio button {index}: {e}')
            return False
    
    def click_submit_button(self):
        """Hace click en el botón de submit"""
        try:
            logger.info('🔘 Haciendo click en botón de submit...')
            
            submit_button_xpath = '/html/body/div[4]/div/div/div/form/div[3]/div/div[3]/input'
            
            # Esperar a que el botón esté presente y clickeable
            submit_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
            )
            
            logger.info('✅ Botón de submit encontrado, haciendo click...')
            submit_button.click()
            
            # Esperar a que procese la búsqueda
            logger.info('⏳ Esperando resultados...')
            time.sleep(3)
            
            logger.info('✅ Submit realizado')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error haciendo click en botón de submit: {e}')
            return False
    
    def extract_table_data(self):
        """Extrae el valor de la tabla de resultados"""
        try:
            logger.info('📊 Extrayendo datos de la tabla...')
            
            table_header_xpath = '/html/body/div[4]/div/div/div/form/div[3]/div/div[3]/div/div/div/div/table[1]/thead/tr/th/span'

            # Esperar a que el elemento esté presente
            table_header = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, table_header_xpath))
            )
            
            # Obtener el texto del elemento
            value = table_header.text.strip()
            
            logger.info(f'✅ Valor extraído: {value}')
            return value
            
        except Exception as e:
            logger.warning(f'⚠️ No se encontró la tabla de resultados: {e}')
            logger.info('📌 Usando valor por defecto: 0')
            return '0'
    
    def extract_table_html(self):
        """Extrae el HTML completo de la segunda tabla"""
        try:
            logger.info('📊 Extrayendo HTML de la tabla 2...')
            
            table_xpath = '/html/body/div[4]/div/div/div/form/div[3]/div/div[3]/div/div/div/div/table[2]'
            
            # Esperar a que la tabla esté presente
            table = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, table_xpath))
            )
            
            # Obtener el HTML completo de la tabla
            table_html = table.get_attribute('outerHTML')
            
            logger.info(f'✅ HTML de tabla extraído ({len(table_html)} caracteres)')
            return table_html
            
        except Exception as e:
            logger.warning(f'⚠️ No se encontró la tabla HTML: {e}')
            logger.info('📌 Usando valor por defecto: vacío')
            return ''
    
    def reset_form(self):
        """Resetea el formulario para una nueva búsqueda"""
        try:
            logger.info('🔄 Reseteando formulario...')
            
            # Navegar de vuelta a la página inicial
            self.driver.get(self.url)
            
            # Esperar a que la página cargue
            time.sleep(2)
            
            logger.info('✅ Formulario reseteado')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error reseteando formulario: {e}')
            return False
    
    def take_screenshot(self, filename='screenshot.png'):
        """Toma una captura de pantalla"""
        try:
            os.makedirs('sbs_scraper', exist_ok=True)
            screenshot_path = os.path.join('sbs_scraper', filename)
            self.driver.save_screenshot(screenshot_path)
            logger.info(f'📸 Captura guardada: {screenshot_path}')
            return True
        except Exception as e:
            logger.error(f'❌ Error tomando captura: {e}')
            return False
    
    def send_results_to_api(self, results, plate_id):
        """Envía los resultados a la API de SBS Insurance"""
        try:
            logger.info('📤 Enviando resultados a la API...')
            
            # URL del endpoint
            api_url = 'http://143.110.206.161:3000/sbs-insurance'
            
            # Mapear results al formato esperado por la API
            payload = {
                "plateNumber": results['plate_number'],
                "soatAccidents": int(results['SOAT']['count']) if results['SOAT']['count'].isdigit() else 0,
                "soatTableDetails": results['SOAT']['table_html'],
                "insuranceAccidents": int(results['SEGURO']['count']) if results['SEGURO']['count'].isdigit() else 0,
                "insuranceTableDetails": results['SEGURO']['table_html'],
                "catAccidents": int(results['CAT']['count']) if results['CAT']['count'].isdigit() else 0,
                "catTableDetails": results['CAT']['table_html']
            }
            
            # Headers
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json'
            }
            
            logger.info(f'📊 Payload: {json.dumps({k: v if k != "soatTableDetails" and k != "insuranceTableDetails" and k != "catTableDetails" else f"{len(v)} caracteres" for k, v in payload.items()}, indent=2)}')
            
            # Enviar request POST
            response = requests.post(api_url, json=payload, headers=headers)
            
            # Verificar respuesta
            if response.status_code in [200, 201]:
                logger.info(f'✅ Datos enviados exitosamente. Respuesta: {response.text}')
                
                # Marcar placa como cargada en la API
                logger.info(f'📝 Marcando placa {plate_id} como cargada...')
                mark_loaded_url = f'http://143.110.206.161:3000/pending-car-plates/{plate_id}/mark-loaded/C'
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
    
    def run(self, plate_number=None, plate_id=None, wait_time=5, headless=False):
        """Ejecuta el scraper completo"""
        try:
            # Validar parámetros requeridos
            if not plate_number:
                logger.error('❌ Error: Falta el parámetro obligatorio "plate_number" (número de placa)')
                logger.error('   Ejemplo: scraper.run(plate_number="BNP276")')
                return False
            
            logger.info(f'📋 Parámetros recibidos:')
            logger.info(f'   🚙 Placa: {plate_number}')
            logger.info(f'   👁️ Headless: {headless}')
            
            # Configurar driver
            if not self.setup_driver(headless=headless):
                return False
            
            # Diccionario para almacenar los resultados
            results = {
                'plate_number': plate_number,
                'SOAT': {
                    'count': '0',
                    'table_html': ''
                },
                'SEGURO': {
                    'count': '0',
                    'table_html': ''
                },
                'CAT': {
                    'count': '0',
                    'table_html': ''
                }
            }
            
            # Mapeo de índices a nombres de campos
            field_mapping = {
                1: 'SOAT',
                2: 'SEGURO',
                3: 'CAT'
            }
            
            # Ejecutar 3 veces con diferentes radio buttons
            for radio_index in [1, 2, 3]:
                logger.info('\n' + '=' * 60)
                logger.info(f'🔄 Iteración {radio_index}/3 - {field_mapping[radio_index]}')
                logger.info('=' * 60 + '\n')
                
                # Navegar a la página (primera vez o reset)
                if radio_index == 1:
                    if not self.navigate_to_page():
                        return False
                else:
                    if not self.reset_form():
                        return False
                
                # Llenar número de placa
                if not self.fill_plate_number(plate_number):
                    logger.warning(f'⚠️ No se pudo llenar la placa en iteración {radio_index}')
                    continue
                
                # Seleccionar radio button según el índice
                if not self.select_radio_button(radio_index):
                    logger.warning(f'⚠️ No se pudo seleccionar radio button {radio_index}')
                    continue
                
                # Click en botón de submit
                if not self.click_submit_button():
                    logger.warning(f'⚠️ No se pudo hacer submit en iteración {radio_index}')
                    continue
                
                # Extraer datos de la tabla
                table_value = self.extract_table_data()
                table_html = self.extract_table_html()
                
                field_name = field_mapping[radio_index]
                results[field_name]['count'] = table_value
                results[field_name]['table_html'] = table_html
                
                logger.info(f'✅ {field_name} - Count: {table_value}, HTML: {len(table_html)} caracteres')
                
                # Tomar captura de pantalla
                screenshot_name = f'sbs_{field_mapping[radio_index].lower()}.png'
                self.take_screenshot(screenshot_name)
                
                # Esperar un momento antes de la siguiente iteración
                time.sleep(2)
            
            # Guardar resultados en JSON
            logger.info('\n💾 Guardando resultados en JSON...')
            os.makedirs('sbs_scraper', exist_ok=True)
            json_path = os.path.join('sbs_scraper', 'sbs_results.json')
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f'✅ Resultados guardados en {json_path}')
            logger.info(f'📊 Resultados: {json.dumps(results, ensure_ascii=False, indent=2)}')
            
            # Enviar resultados a la API
            if plate_id:
                if not self.send_results_to_api(results, plate_id):
                    logger.warning('⚠️ No se pudieron enviar los datos a la API, pero el proceso continúa')
            else:
                logger.warning('⚠️ No se proporcionó plate_id, no se enviarán datos a la API')
            
            # Esperar el tiempo especificado
            logger.info(f'\n⏳ Esperando {wait_time} segundos...')
            time.sleep(wait_time)
            
            logger.info('\n🎉 Proceso completado exitosamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error en el proceso: {e}')
            return False
    
    def cleanup(self):
        """Limpia recursos y cierra el navegador"""
        if self.driver:
            logger.info('🧹 Cerrando navegador...')
            try:
                self.driver.quit()
                logger.info('✅ Navegador cerrado')
            except Exception as e:
                logger.error(f'❌ Error cerrando navegador: {e}')


def get_pending_plate():
    """
    Obtiene la primera placa pendiente de la API
    
    Returns:
        dict: Diccionario con la información de la placa o None si hay error
    """
    try:
        logger.info('🌐 Obteniendo placa pendiente de la API...')
        
        url = 'http://143.110.206.161:3000/pending-car-plates/unloaded/C/first'
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
    logger.info('🚗 SBS SOAT Scraper - Python')
    logger.info('=' * 60)
    
    scraper = SBSScraper()
    
    # Obtener placa pendiente de la API
    plate_data = get_pending_plate()
    
    if not plate_data:
        logger.error('❌ No se pudo obtener la placa de la API')
        return
    
    plate_number = plate_data.get('plate')
    plate_id = plate_data.get('id')
    
    if not plate_number:
        logger.error('❌ La respuesta de la API no contiene una placa válida')
        return
    
    logger.info(f'📋 Procesando:')
    logger.info(f'   🆔 ID: {plate_id}')
    logger.info(f'   🚙 Placa: {plate_number}')
    
    # Ejecutar scraper
    success = scraper.run(
        plate_number=plate_number,  # Placa obtenida de la API
        plate_id=plate_id,          # ID de la placa para marcar como cargada
        wait_time=5,                # Tiempo de espera al final (opcional, default: 100)
        headless=True               # Modo headless (opcional, default: False)
    )
    
    if success:
        logger.info('✅ Scraper ejecutado exitosamente')
    else:
        logger.error('❌ El scraper falló')


if __name__ == '__main__':
    main()

