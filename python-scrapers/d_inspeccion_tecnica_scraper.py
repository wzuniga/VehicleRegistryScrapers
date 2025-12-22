import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import requests
from datetime import datetime
import json
from dotenv import load_dotenv
import os
import deathbycaptcha

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InspeccionTecnicaScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://rec.mtc.gob.pe/Citv/ArConsultaCitv'
        
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
            self.driver = uc.Chrome(options=options, version_main=143)
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
        """Navega a la página de consulta de inspección técnica vehicular"""
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

    
    def get_captcha_image(self):
        """Obtiene la imagen del captcha y la guarda"""
        try:
            logger.info('🖼️ Obteniendo imagen del captcha...')
            
            captcha_img_xpath = '/html/body/div[2]/div[2]/div[3]/div/div/img'
            
            # Esperar a que la imagen esté presente
            captcha_img = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, captcha_img_xpath))
            )
            
            logger.info('✅ Imagen del captcha encontrada')
            
            # Obtener la imagen y guardarla
            os.makedirs('inspeccion_tecnica', exist_ok=True)
            captcha_path = os.path.join('inspeccion_tecnica', 'captcha.png')
            captcha_img.screenshot(captcha_path)
            
            logger.info(f'💾 Imagen del captcha guardada como {captcha_path}')
            
            return True
            
        except Exception as e:
            logger.error(f'❌ Error obteniendo imagen del captcha: {e}')
            return False
    
    def parse_captcha_with_dbc(self, image_path='inspeccion_tecnica/captcha.png'):
        """Parsea la imagen del captcha usando DeathByCaptcha"""
        try:
            logger.info('🤖 Parseando captcha con DeathByCaptcha...')
            
            # Obtener credenciales desde variables de entorno
            dbc_username = os.getenv('DBC_USERNAME')
            dbc_password = os.getenv('DBC_PASSWORD')
            
            if not dbc_username or not dbc_password:
                logger.error('❌ DBC_USERNAME o DBC_PASSWORD no encontradas en .env')
                return None
            
            # Configurar cliente DeathByCaptcha
            client = deathbycaptcha.SocketClient(dbc_username, dbc_password)
            
            logger.info('📤 Enviando captcha a DeathByCaptcha...')
            
            # Enviar captcha para resolución (deathbycaptcha espera la ruta del archivo)
            # verbose=0 para suprimir logs de deathbycaptcha
            captcha = client.decode(image_path, type=0, verbose=0)
            
            if captcha:
                result = captcha.get('text', '')
                logger.info(f'✅ Captcha resuelto: {result}')
                return result.strip().upper()
            else:
                logger.error('❌ No se pudo resolver el captcha')
                return None
            
        except Exception as e:
            logger.error(f'❌ Error parseando captcha: {e}')
            return None
    
    def get_session_cookie(self):
        """Extrae la cookie ASP.NET_SessionId del navegador"""
        try:
            logger.info('🍪 Obteniendo cookie ASP.NET_SessionId...')
            
            # Obtener todas las cookies
            cookies = self.driver.get_cookies()
            
            # Buscar la cookie ASP.NET_SessionId
            for cookie in cookies:
                if cookie['name'] == 'ASP.NET_SessionId':
                    session_id = cookie['value']
                    logger.info(f'✅ Cookie obtenida: {session_id}')
                    return session_id
            
            logger.error('❌ No se encontró la cookie ASP.NET_SessionId')
            return None
            
        except Exception as e:
            logger.error(f'❌ Error obteniendo cookie: {e}')
            return None
    
    def query_citv_data(self, plate_number, captcha_text, session_cookie):
        """Consulta los datos de CITV usando el endpoint con la cookie de sesión"""
        try:
            logger.info('🔍 Consultando datos de CITV...')
            
            # Construir la URL con los parámetros
            url = f'https://rec.mtc.gob.pe/CITV/JrCITVConsultarFiltro?pArrParametros=1%7C{plate_number}%7C%7C{captcha_text}'
            
            # Headers para la petición
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.6',
                'content-type': 'application/json',
                'priority': 'u=1, i',
                'referer': 'https://rec.mtc.gob.pe/Citv/ArConsultaCitv',
                'sec-ch-ua': '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'sec-gpc': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
                'Cookie': f'ASP.NET_SessionId={session_cookie}'
            }
            
            logger.info(f'📊 URL: {url}')
            logger.info(f'🍪 Cookie: ASP.NET_SessionId={session_cookie}')
            
            # Hacer la petición GET
            response = requests.get(url, headers=headers, timeout=30)
            
            # Verificar respuesta
            if response.status_code == 200:
                logger.info(f'✅ Respuesta recibida ({response.status_code})')
                
                try:
                    data = response.json()
                    logger.info(f'📄 Datos obtenidos: {json.dumps(data, ensure_ascii=False, indent=2)}')
                    
                    # Verificar si el código de error es -2 (captcha inválido)
                    if data.get('orCodigo') == "-2":
                        logger.warning('⚠️ Código de error -2: Captcha inválido, se requiere reinicialización')
                        return None
                    
                    return data
                except json.JSONDecodeError:
                    logger.warning('⚠️ La respuesta no es JSON válido')
                    logger.info(f'📄 Respuesta raw: {response.text}')
                    return {'raw_response': response.text}
            else:
                logger.error(f'❌ Error en la petición. Status: {response.status_code}')
                logger.error(f'📄 Respuesta: {response.text}')
                logger.warning('⚠️ El captcha/cookie probablemente expiraron, se requiere reinicialización')
                return None
                
        except Exception as e:
            logger.error(f'❌ Error consultando CITV: {e}')
            return None
    
    def send_to_api(self, plate_number, citv_data, plate_id):
        """Envía los datos de CITV al endpoint de inspección vehicular"""
        try:
            logger.info('📤 Enviando datos a la API...')
            
            # URL del endpoint
            api_url = 'http://143.110.206.161:3000/inspeccion-vehicular'
            
            # Payload
            payload = {
                'plateNumber': plate_number,
                'data': citv_data
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
                mark_loaded_url = f'http://143.110.206.161:3000/pending-car-plates/{plate_id}/mark-loaded/D'
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
    
        """Hace click en el botón de búsqueda"""
        try:
            logger.info('🔍 Haciendo click en botón de búsqueda...')
            
            button_xpath = '/html/body/div[2]/div[2]/div[5]/div/button[1]'
            
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, button_xpath))
            )
            
            button.click()
            logger.info('✅ Click realizado')
            
            # Esperar a que cargue la página
            time.sleep(3)
            return True
            
        except Exception as e:
            logger.error(f'❌ Error haciendo click: {e}')
            return False
    
    def take_screenshot(self, filename='screenshot.png'):
        """Toma una captura de pantalla"""
        try:
            os.makedirs('inspeccion_tecnica', exist_ok=True)
            screenshot_path = os.path.join('inspeccion_tecnica', filename)
            self.driver.save_screenshot(screenshot_path)
            logger.info(f'📸 Captura guardada: {screenshot_path}')
            return True
        except Exception as e:
            logger.error(f'❌ Error tomando captura: {e}')
            return False
    
    def initialize(self, headless=False):
        """Inicializa el navegador y obtiene captcha/cookie (solo una vez)"""
        try:
            # Configurar driver
            if not self.setup_driver(headless=headless):
                return False, None, None
            
            # Navegar a la página
            if not self.navigate_to_page():
                return False, None, None
            
            # Obtener imagen del captcha
            if not self.get_captcha_image():
                return False, None, None
            
            # Parsear captcha con DeathByCaptcha
            captcha_text = self.parse_captcha_with_dbc('inspeccion_tecnica/captcha.png')
            if not captcha_text:
                logger.error('❌ No se pudo parsear el captcha')
                return False, None, None
            
            # Obtener cookie de sesión
            session_cookie = self.get_session_cookie()
            if not session_cookie:
                logger.error('❌ No se pudo obtener la cookie de sesión')
                return False, None, None
            
            logger.info('✅ Inicialización completada exitosamente')
            return True, captcha_text, session_cookie
            
        except Exception as e:
            logger.error(f'❌ Error en la inicialización: {e}')
            return False, None, None
    
    def process_plate(self, plate_number, plate_id, captcha_text, session_cookie):
        """Procesa una placa individual usando captcha y cookie existentes"""
        try:
            logger.info(f'📋 Procesando placa: {plate_number}')
            
            # Consultar datos de CITV
            citv_data = self.query_citv_data(plate_number, captcha_text, session_cookie)
            if not citv_data:
                logger.error('❌ No se pudieron obtener los datos de CITV')
                return False
            
            # Enviar datos a la API
            if not self.send_to_api(plate_number, citv_data, plate_id):
                logger.warning('⚠️ No se pudieron enviar los datos a la API')
                return False
            
            logger.info('✅ Placa procesada exitosamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error procesando placa: {e}')
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
        
        url = 'http://143.110.206.161:3000/pending-car-plates/unloaded/D/first'
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
    logger.info('🚗 Inspección Técnica Vehicular Scraper - Python')
    logger.info('=' * 60)
    
    scraper = InspeccionTecnicaScraper()
    captcha_text = None
    session_cookie = None
    needs_initialization = True
    reinitialization_count = 0
    MAX_REINITIALIZATIONS = 10
    
    try:
        while True:
            try:
                # Inicializar o reinicializar si es necesario
                if needs_initialization:
                    # Verificar límite de reinicializaciones
                    if reinitialization_count >= MAX_REINITIALIZATIONS:
                        logger.error(f'❌ Se alcanzó el máximo de {MAX_REINITIALIZATIONS} reinicializaciones. Terminando script.')
                        break
                    
                    reinitialization_count += 1
                    logger.info(f'🔄 Inicializando navegador y obteniendo captcha/cookie... (Intento {reinitialization_count}/{MAX_REINITIALIZATIONS})')
                    success, captcha_text, session_cookie = scraper.initialize(headless=True)
                    
                    if not success:
                        logger.error('❌ Fallo en la inicialización, reintentando en 5 segundos...')
                        time.sleep(5)
                        continue
                    
                    needs_initialization = False
                    logger.info('✅ Listo para procesar placas')
                
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
                
                # Procesar placa usando captcha y cookie existentes
                success = scraper.process_plate(plate_number, plate_id, captcha_text, session_cookie)
                
                if success:
                    logger.info('✅ Placa procesada exitosamente')
                    # Resetear contador de reinicializaciones en caso de éxito
                    reinitialization_count = 0
                else:
                    logger.warning('⚠️ Fallo al procesar placa, reinicializando...')
                    needs_initialization = True
                    scraper.cleanup()
                    scraper = InspeccionTecnicaScraper()
                
                # Pequeña pausa entre procesamiento de placas
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                logger.info('\n🛑 Proceso interrumpido por el usuario')
                break
            except Exception as e:
                logger.error(f'❌ Error inesperado en el ciclo: {e}')
                needs_initialization = True
                scraper.cleanup()
                scraper = InspeccionTecnicaScraper()
                time.sleep(2)
                
    finally:
        # Limpieza final
        scraper.cleanup()
        logger.info('👋 Scraper finalizado')


if __name__ == '__main__':
    main()
