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


class ConoceAquiSunapScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://conoce-aqui.sunarp.gob.pe/conoce-aqui/inicio'
        
        # Cargar datos del .env
        self.dni = os.getenv('SUNARP_DNI', '71412097')
        self.digito_verificador = os.getenv('SUNARP_DIGITO_VERIFICADOR', '8')
        self.fecha_emision = os.getenv('SUNARP_FECHA_EMISION', '13/11/2024')
        
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
        
        # Optimizaciones de rendimiento
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        
        # Estrategia de carga de página: 'eager' no espera recursos externos
        options.page_load_strategy = 'eager'
        
        # Preferencias adicionales
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
        }
        options.add_experimental_option('prefs', prefs)
        
        try:
            self.driver = uc.Chrome(options=options, version_main=147)
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
        """Navega a la página de Conoce Aquí SUNARP"""
        try:
            logger.info(f'🌐 Navegando a {self.url}...')
            self.driver.get(self.url)
            
            # Esperar a que la aplicación Angular cargue
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-root'))
            )
            
            logger.info('✅ Página cargada exitosamente')
            
            # Esperar solo lo mínimo necesario para la carga inicial
            time.sleep(2)
            
            return True
        except Exception as e:
            logger.error(f'❌ Error navegando a la página: {e}')
            return False
    
    def close_modal(self):
        """Cierra el modal que aparece al cargar la página"""
        try:
            logger.info('🔔 Cerrando modal inicial...')
            
            modal_button_xpath = '/html/body/div/div[2]/div/nz-modal-container/div/div/div[3]/button[2]'
            
            # Esperar a que el botón del modal esté presente y sea clickeable
            modal_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, modal_button_xpath))
            )
            
            modal_button.click()
            logger.info('✅ Modal cerrado correctamente')
            
            # Pequeña pausa después de cerrar el modal
            time.sleep(1)
            return True
            
        except Exception as e:
            logger.error(f'❌ Error cerrando modal: {e}')
            return False
    
    def fill_dni(self):
        """Llena el campo de DNI"""
        try:
            logger.info(f'🆔 Llenando DNI: {self.dni}')
            
            dni_input_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-login/nz-layout/nz-content/div[2]/form/nz-form-item[2]/nz-form-control/div/div/nz-input-group/input'
            
            # Esperar a que el input esté presente y sea interactivo
            dni_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, dni_input_xpath))
            )
            
            # Limpiar el campo primero
            dni_input.clear()
            
            # Escribir el DNI
            dni_input.send_keys(self.dni)
            
            logger.info('✅ DNI ingresado correctamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error llenando DNI: {e}')
            return False
    
    def fill_digito_verificador(self):
        """Llena el campo de dígito verificador"""
        try:
            logger.info(f'🔢 Llenando dígito verificador: {self.digito_verificador}')
            
            digito_input_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-login/nz-layout/nz-content/div[2]/form/nz-form-item[3]/nz-form-control/div/div/nz-input-group/input'
            
            # Esperar a que el input esté presente y sea interactivo
            digito_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, digito_input_xpath))
            )
            
            # Limpiar el campo primero
            digito_input.clear()
            
            # Escribir el dígito verificador
            digito_input.send_keys(self.digito_verificador)
            
            logger.info('✅ Dígito verificador ingresado correctamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error llenando dígito verificador: {e}')
            return False
    
    def fill_fecha_emision(self):
        """Llena el campo de fecha de emisión"""
        try:
            logger.info(f'📅 Llenando fecha de emisión: {self.fecha_emision}')
            
            fecha_input_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-login/nz-layout/nz-content/div[2]/form/nz-form-item[4]/nz-form-control/div/div/nz-input-group/input'
            
            # Esperar a que el input esté presente y sea interactivo
            fecha_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, fecha_input_xpath))
            )
            
            # Limpiar el campo primero
            fecha_input.clear()
            
            # Escribir la fecha de emisión
            fecha_input.send_keys(self.fecha_emision)
            
            logger.info('✅ Fecha de emisión ingresada correctamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error llenando fecha de emisión: {e}')
            return False
    
    def click_submit_button(self):
        """Hace click en el botón de envío"""
        try:
            logger.info('🔍 Haciendo click en botón de envío...')
            
            button_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-login/nz-layout/nz-content/div[2]/form/nz-form-item[6]/nz-form-control/div/div/div/button'
            
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, button_xpath))
            )
            
            button.click()
            logger.info('✅ Click realizado')
            
            # Esperar a que cargue la siguiente página
            time.sleep(3)
            return True
            
        except Exception as e:
            logger.error(f'❌ Error haciendo click: {e}')
            return False
    
    def take_screenshot(self, filename=None):
        """Toma una captura de pantalla"""
        try:
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'sunarp_conoce_aqui_{timestamp}.png'
            
            os.makedirs('sunarp_conoce_aqui', exist_ok=True)
            screenshot_path = os.path.join('sunarp_conoce_aqui', filename)
            self.driver.save_screenshot(screenshot_path)
            logger.info(f'📸 Captura guardada: {screenshot_path}')
            return screenshot_path
        except Exception as e:
            logger.error(f'❌ Error tomando captura: {e}')
            return None
    
    def run(self, headless=False):
        """Ejecuta el scraper completo"""
        try:
            logger.info(f'📋 Parámetros cargados desde .env:')
            logger.info(f'   🆔 DNI: {self.dni}')
            logger.info(f'   🔢 Dígito Verificador: {self.digito_verificador}')
            logger.info(f'   📅 Fecha de Emisión: {self.fecha_emision}')
            logger.info(f'   👁️ Headless: {headless}')
            
            # Configurar driver
            if not self.setup_driver(headless=headless):
                return False
            
            # Navegar a la página
            if not self.navigate_to_page():
                return False
            
            # Cerrar modal inicial
            if not self.close_modal():
                return False
            
            # Llenar DNI
            if not self.fill_dni():
                return False
            
            time.sleep(1)
            
            # Llenar dígito verificador
            if not self.fill_digito_verificador():
                return False
            
            time.sleep(1)
            
            # Llenar fecha de emisión
            if not self.fill_fecha_emision():
                return False
            
            time.sleep(1)
            
            # Hacer click en el botón de envío
            if not self.click_submit_button():
                return False
            
            # Tomar captura de pantalla del resultado
            screenshot_path = self.take_screenshot()
            if screenshot_path:
                logger.info(f'✅ Resultado capturado en: {screenshot_path}')
            
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


def main():
    """Función principal"""
    logger.info('=' * 60)
    logger.info('🏢 Conoce Aquí SUNARP Scraper - Python')
    logger.info('=' * 60)
    
    try:
        # Crear instancia del scraper
        scraper = ConoceAquiSunapScraper()
        
        # Ejecutar scraper
        success = scraper.run(
            headless=False  # Modo headless (opcional, default: False)
        )
        
        if success:
            logger.info('✅ Scraper ejecutado exitosamente')
        else:
            logger.error('❌ El scraper falló')
            
    except KeyboardInterrupt:
        logger.info('\n🛑 Proceso interrumpido por el usuario')
    except Exception as e:
        logger.error(f'❌ Error inesperado: {e}')


if __name__ == '__main__':
    main()
