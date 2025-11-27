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
    
    def fill_plate_number(self, plate):
        """Llena el campo de número de placa"""
        try:
            logger.info(f'🚙 Llenando número de placa: {plate}')
            
            plate_input_xpath = '/html/body/div[2]/div[2]/div[2]/div/input'
            
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
            captcha = client.decode(image_path)
            
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
    
    def fill_captcha_input(self, captcha_text):
        """Llena el input del captcha con el texto parseado"""
        try:
            logger.info(f'📝 Llenando captcha: {captcha_text}')
            
            captcha_input_xpath = '/html/body/div[2]/div[2]/div[4]/div/div/input'
            
            captcha_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, captcha_input_xpath))
            )
            
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            
            logger.info('✅ Captcha llenado correctamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error llenando captcha: {e}')
            return False
    
    def click_search_button(self):
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
    
    def run(self, plate_number=None, plate_id=None, headless=False):
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
            
            # Navegar a la página
            if not self.navigate_to_page():
                return False
            
            # Llenar número de placa
            if not self.fill_plate_number(plate_number):
                return False
            
            # Obtener imagen del captcha
            if not self.get_captcha_image():
                return False
            
            # Parsear captcha con DeathByCaptcha
            captcha_text = self.parse_captcha_with_dbc('inspeccion_tecnica/captcha.png')
            if not captcha_text:
                logger.error('❌ No se pudo parsear el captcha')
                return False
            
            # Llenar el input del captcha
            if not self.fill_captcha_input(captcha_text):
                return False
            
            # Hacer click en el botón de búsqueda
            if not self.click_search_button():
                return False
            
            # Tomar captura de pantalla final
            self.take_screenshot('inspeccion_tecnica_result.png')
            
            logger.info('✅ Proceso completado exitosamente')
            logger.info('🎉 Proceso completado exitosamente')
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
        headless=False               # Modo headless (opcional, default: False)
    )
    
    if success:
        logger.info('✅ Scraper ejecutado exitosamente')
    else:
        logger.error('❌ El scraper falló')


if __name__ == '__main__':
    main()
