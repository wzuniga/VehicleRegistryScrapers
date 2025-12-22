import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suprimir warnings de undetected_chromedriver sobre handle inválido
import warnings
warnings.filterwarnings('ignore', category=ResourceWarning)
warnings.filterwarnings('ignore', message='.*invalid.*handle.*')


class ConsultaVehicularScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://consultavehicular.sunarp.gob.pe/'
        self.captcha_id = None  # Para almacenar el ID del captcha resuelto
        
    def setup_driver(self, headless=False):
        """Configura el driver de Chrome con opciones anti-detección"""
        logger.info('🚀 Configurando Chrome driver...')
        
        options = uc.ChromeOptions()
        
        # Opciones básicas para evitar detección
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        
        # User agent realista
        # options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        
        # Modo headless configurable con opciones anti-detección adicionales
        if headless:
            options.add_argument("--headless=new")
            # Opciones adicionales para evitar detección de headless
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            logger.info('🔇 Modo headless activado con anti-detección')
        else:
            logger.info('👁️ Modo headless desactivado (navegador visible)')
        
        # Configurar viewport realista
        options.add_argument('--window-size=1920,1080')
        
        # Optimizaciones de rendimiento - mantener GPU para WebGL
        options.add_argument('--disable-extensions')
        # NO deshabilitar GPU - necesario para WebGL
        # options.add_argument('--disable-gpu')
        
        # Estrategia de carga de página: 'eager' no espera recursos externos
        options.page_load_strategy = 'eager'
        
        # Preferencias adicionales - mínimo bloqueo para evitar detección
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
        }
        options.add_experimental_option('prefs', prefs)
        
        try:
            # undetected_chromedriver maneja automáticamente la mayoría de opciones anti-detección
            # Intentar primero con version_main específica
            try:
                self.driver = uc.Chrome(options=options, version_main=143, use_subprocess=True)
                logger.info('✅ Chrome driver configurado exitosamente (versión 143)')
            except Exception as version_error:
                logger.warning(f'⚠️ No se pudo usar version_main=143: {version_error}')
                logger.info('🔄 Intentando sin especificar versión...')
                # Recrear opciones porque ChromeOptions no se puede reutilizar
                options_retry = uc.ChromeOptions()
                options_retry.add_argument('--disable-blink-features=AutomationControlled')
                options_retry.add_argument('--disable-dev-shm-usage')
                options_retry.add_argument('--no-sandbox')
                if headless:
                    options_retry.add_argument("--headless=new")
                    options_retry.add_argument('--disable-background-timer-throttling')
                    options_retry.add_argument('--disable-backgrounding-occluded-windows')
                    options_retry.add_argument('--disable-renderer-backgrounding')
                options_retry.add_argument('--window-size=1920,1080')
                options_retry.add_argument('--disable-extensions')
                options_retry.page_load_strategy = 'eager'
                prefs_retry = {
                    'profile.default_content_setting_values.notifications': 2,
                    'profile.default_content_settings.popups': 0,
                }
                options_retry.add_experimental_option('prefs', prefs_retry)
                # Intentar sin version_main - autodetección
                self.driver = uc.Chrome(options=options_retry, use_subprocess=True)
                logger.info('✅ Chrome driver configurado exitosamente (versión autodetectada)')
            
            # Ejecutar scripts anti-detección adicionales
            try:
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': '''
                        // Eliminar completamente webdriver
                        delete Object.getPrototypeOf(navigator).webdriver;
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined,
                            configurable: true
                        });
                        
                        // Languages
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['es-ES', 'es', 'en-US', 'en']
                        });
                        
                        // Fix plugins - crear PluginArray real
                        const originalPlugins = navigator.plugins;
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => {
                                const pluginArray = Object.create(PluginArray.prototype);
                                pluginArray.length = 5;
                                return pluginArray;
                            }
                        });
                        
                        // Ocultar propiedades de headless
                        Object.defineProperty(navigator, 'maxTouchPoints', {
                            get: () => 1
                        });
                        
                        Object.defineProperty(navigator, 'platform', {
                            get: () => 'Win32'
                        });
                        
                        // Simular Chrome real
                        window.chrome = {
                            runtime: {},
                            loadTimes: function() {},
                            csi: function() {},
                            app: {}
                        };
                        
                        // Fix permissions - simular granted
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
                        
                        // Fix Image dimensions
                        const originalCreateElement = document.createElement;
                        document.createElement = function(tag) {
                            const element = originalCreateElement.call(document, tag);
                            if (tag === 'img') {
                                Object.defineProperty(element, 'width', {
                                    get: function() { return this.naturalWidth || 0; },
                                    configurable: true
                                });
                                Object.defineProperty(element, 'height', {
                                    get: function() { return this.naturalHeight || 0; },
                                    configurable: true
                                });
                            }
                            return element;
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
        """Navega a la página de consulta vehicular de SUNARP"""
        try:
            logger.info(f'🌐 Navegando a {self.url}...')
            self.driver.get(self.url)
            
            # Esperar a que la aplicación Angular cargue
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-root'))
            )
            
            logger.info('✅ Página cargada exitosamente')
            
            # Esperar solo lo mínimo necesario para la carga inicial
            time.sleep(1)
            
            return True
        except Exception as e:
            logger.error(f'❌ Error navegando a la página: {e}')
            return False
    
    def fill_plate_number(self, plate):
        """Llena el campo de número de placa"""
        try:
            logger.info(f'🚙 Llenando número de placa: {plate}')
            
            plate_input_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content/div/nz-card/div/app-form-datos-consulta/div/form/fieldset/nz-form-item[1]/nz-form-control/div/div/nz-input-group/input'
            
            # Esperar a que el input esté presente y sea interactivo
            plate_input = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, plate_input_xpath))
            )
            
            # Limpiar el campo primero
            plate_input.clear()
            
            # Escribir la placa con pequeñas pausas para simular escritura humana
            for char in plate:
                plate_input.send_keys(char)
                # time.sleep(0.1)
            
            logger.info('✅ Número de placa ingresado correctamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error llenando número de placa: {e}')
            return False

    def click_search_button(self):
        """Hace click en el botón de búsqueda"""
        try:
            logger.info('🔍 Haciendo click en botón de búsqueda...')
            
            button_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content/div/nz-card/div/app-form-datos-consulta/div/form/fieldset/nz-form-item[3]/nz-form-control/div/div/div/button'
            
            button = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, button_xpath))
            )
            
            button.click()
            logger.info('✅ Click realizado')
            
            # Esperar a que cargue la página
            # time.sleep(3)
            return True
            
        except Exception as e:
            logger.error(f'❌ Error haciendo click: {e}')
            # Reportar captcha como incorrecto cuando falla el click
            logger.warning('⚠️ Posiblemente el captcha fue descifrado incorrectamente')
            self.report_incorrect_captcha()
            return False
    
    def get_result_image_base64(self):
        """Obtiene el base64 de la imagen del resultado directamente del atributo src"""
        try:
            # Tomar screenshot antes de obtener la imagen
            self.take_screenshot('before_result_extraction.png')
            
            logger.info('🖼️ Obteniendo imagen del resultado en base64...')
            
            result_img_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content/div/nz-card/div/app-form-datos-consulta/div/img'
            
            # Esperar a que la imagen esté presente con su atributo src
            result_img = WebDriverWait(self.driver, 12).until(
                EC.presence_of_element_located((By.XPATH, result_img_xpath))
            )
            
            logger.info('✅ Imagen del resultado encontrada')
            
            # Obtener el atributo src que contiene el base64
            src_attribute = result_img.get_attribute('src')
            
            if not src_attribute or not src_attribute.startswith('data:image'):
                logger.error('❌ El atributo src no contiene una imagen base64')
                return None
            
            # Extraer solo el base64 (remover el prefijo "data:image/png;base64,")
            if ';base64,' in src_attribute:
                image_base64 = src_attribute.split(';base64,')[1]
                logger.info(f'✅ Base64 extraído exitosamente (longitud: {len(image_base64)} caracteres)')
                return image_base64
            else:
                logger.error('❌ No se encontró el marcador base64 en src')
                return None
            
        except Exception as e:
            logger.error(f'❌ Error obteniendo imagen base64: {e}')
            return None

    def send_image_to_api(self, image_base64, plate_number, plate_id):
        """Envía la imagen en base64 al endpoint de la API"""
        try:
            logger.info('📤 Enviando imagen en base64 a la API...')
            
            # URL del endpoint
            api_url = 'http://143.110.206.161:3000/vehicles'
            
            # Payload con imagen base64
            payload = {
                "plateNumber": plate_number,
                "imageBase64": image_base64
            }
            
            # Headers
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json'
            }
            
            logger.info(f'📊 Enviando imagen para plate_id: {plate_id}')
            
            # Enviar request POST
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            
            # Verificar respuesta
            if response.status_code in [200, 201]:               
                # Marcar placa como cargada en la API
                logger.info(f'📝 Marcando placa {plate_id} como cargada...')
                mark_loaded_url = f'http://143.110.206.161:3000/pending-car-plates/{plate_id}/mark-loaded/B'
                mark_response = requests.patch(mark_loaded_url, headers={'accept': '*/*'}, timeout=10)
                mark_response.raise_for_status()
                logger.info(f'✅ Placa {plate_id} marcada como cargada')
                
                return True
            else:
                logger.error(f'❌ Error al enviar imagen. Status: {response.status_code}, Respuesta: {response.text}')
                return False
                
        except Exception as e:
            logger.error(f'❌ Error enviando imagen a la API: {e}')
            return False
    
    def take_screenshot(self, filename='screenshot.png'):
        """Toma una captura de pantalla"""
        try:
            os.makedirs('consulta_vehicular', exist_ok=True)
            screenshot_path = os.path.join('consulta_vehicular', filename)
            self.driver.save_screenshot(screenshot_path)
            logger.info(f'📸 Captura guardada: {screenshot_path}')
            return True
        except Exception as e:
            logger.error(f'❌ Error tomando captura: {e}')
            return False
    
    def run(self, plate_number=None, plate_id=None, headless=False, test=False):
        """Ejecuta el scraper completo"""
        try:
            # Modo test: probar detección de bots
            if test:
                logger.info('🧪 Modo TEST activado - Probando detección de bots')
                
                # Configurar driver
                if not self.setup_driver(headless=headless):
                    return False
                
                # Navegar a página de prueba
                logger.info('🌐 Navegando a https://bot.sannysoft.com/...')
                self.driver.get('https://bot.sannysoft.com/')
                
                # Esperar a que cargue completamente
                logger.info('⏳ Esperando 10 segundos para análisis completo...')
                time.sleep(10)
                
                # Tomar screenshot
                if headless:
                    self.take_screenshot('bot_detection_test.png')

                logger.info('✅ Test completado. Revisa la captura bot_detection_test.png')
                logger.info('📊 Resultados: Verifica en la imagen si aparece como bot detectado')
                
                return True
            
            # Flujo normal del scraper
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
            
            # Navegar a la página
            if not self.navigate_to_page():
                return False
            
            # Llenar número de placa
            if not self.fill_plate_number(plate_number):
                return False
            
            # Esperar 3 segundos después de llenar la placa
            time.sleep(7)
            
            # Hacer click en el botón de búsqueda
            if not self.click_search_button():
                return False
            
            # Obtener imagen del resultado en base64
            image_base64 = self.get_result_image_base64()
            if not image_base64:
                logger.error('❌ No se pudo obtener la imagen base64')
                return False
                       
            # Enviar imagen en base64 a la API
            if not self.send_image_to_api(image_base64, plate_number, plate_id):
                logger.warning('⚠️ No se pudo enviar la imagen a la API')
                return False
            
            logger.info('🎉 Proceso completado exitosamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error en el proceso: {e}')
            return False
        finally:
            # Asegurar que el navegador se cierre siempre
            self.cleanup()
    
    def cleanup(self):
        """Limpia recursos y cierra el navegador"""
        if self.driver:
            logger.info('🧹 Cerrando navegador...')
            try:
                self.driver.quit()
                logger.info('✅ Navegador cerrado')
            except (OSError, Exception) as e:
                # Ignorar errores de handle inválido en Windows durante cleanup
                if isinstance(e, OSError) and hasattr(e, 'winerror') and e.winerror == 6:
                    logger.debug('ℹ️ Handle inválido durante cleanup (esperado en Windows)')
                else:
                    logger.error(f'❌ Error cerrando navegador: {e}')
            finally:
                self.driver = None


def get_pending_plate():
    """
    Obtiene la primera placa pendiente de la API
    
    Returns:
        dict: Diccionario con la información de la placa o None si hay error
    """
    try:
        logger.info('🌐 Obteniendo placa pendiente de la API...')
        
        url = 'http://143.110.206.161:3000/pending-car-plates/unloaded/B/first'
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
    logger.info('🚗 Consulta Vehicular SUNARP Scraper - Python')
    logger.info('=' * 60)
    
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
            
            logger.info(f'📋 Procesando:')
            logger.info(f'   🆔 ID: {plate_id}')
            logger.info(f'   🚙 Placa: {plate_number}')
            
            # Crear nueva instancia del scraper para cada placa
            scraper = ConsultaVehicularScraper()
            
            try:
                # Ejecutar scraper
                success = scraper.run(
                    plate_number=plate_number,  # Placa obtenida de la API
                    plate_id=plate_id,          # ID de la placa para marcar como cargada
                    headless=True,              # Modo headless (opcional, default: False)
                    test=False
                )
                
                if success:
                    logger.info('✅ Scraper ejecutado exitosamente')
                else:
                    logger.error('❌ El scraper falló')
            finally:
                # Garantizar cleanup siempre
                if scraper.driver:
                    scraper.cleanup()
            
            # Pequeña pausa entre procesamiento de placas
            time.sleep(1)
            
        except KeyboardInterrupt:
            logger.info('\n🛑 Proceso interrumpido por el usuario')
            break
        except Exception as e:
            logger.error(f'❌ Error inesperado en el ciclo principal: {e}')
            time.sleep(2)
            continue


if __name__ == '__main__':
    main()
