import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import requests
from plate_offices import get_office_by_plate
from datetime import datetime
import os
import warnings

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suprimir el error de handle inválido en Windows al cerrar Chrome
warnings.filterwarnings('ignore', category=ResourceWarning)

# Patch para evitar el error de WinError 6 en el destructor de Chrome
original_chrome_del = uc.Chrome.__del__

def patched_chrome_del(self):
    """Versión parcheada del destructor que maneja el error de Windows"""
    try:
        original_chrome_del(self)
    except (OSError, Exception):
        # Ignorar silenciosamente errores de handle inválido en Windows
        pass

uc.Chrome.__del__ = patched_chrome_del


class SunarpScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://sprl.sunarp.gob.pe/sprl/ingreso'
        
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
        # options.add_argument('--disable-gpu')
        
        # Configurar viewport
        options.add_argument('--window-size=1250,750')
        
        # User agent realista (comentado - undetected_chromedriver lo maneja automáticamente)
        # options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Preferencias adicionales
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
        }
        options.add_experimental_option('prefs', prefs)
        
        # Excluir opciones de automatización (COMENTADO - causa error con algunas versiones de Chrome)
        # options.add_experimental_option('excludeSwitches', ['enable-automation'])
        # options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # undetected_chromedriver maneja automáticamente la mayoría de opciones anti-detección
            # version_main debe coincidir con la versión mayor de Chrome instalada
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
        """Navega a la página de inicio de SUNARP"""
        try:
            logger.info(f'🌐 Navegando a {self.url}...')
            self.driver.get(self.url)
            
            # Esperar a que la aplicación Angular cargue
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-root'))
            )
            
            logger.info('✅ Página cargada exitosamente')
            
            # Esperar un poco más para asegurar carga completa
            time.sleep(3)
            
            return True
        except Exception as e:
            logger.error(f'❌ Error navegando a la página: {e}')
            return False
    
    def fill_username(self, username='WZUNIGAH'):
        """Llena el campo de usuario"""
        try:
            logger.info(f'👤 Llenando campo de usuario con: {username}')
            
            username_xpath = '/html/body/div/form/div[1]/div/input'
            
            # Esperar a que el input esté presente
            username_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, username_xpath))
            )
            
            # Limpiar el campo primero
            username_input.clear()
            
            # Escribir el usuario con pequeñas pausas para simular escritura humana
            for char in username:
                username_input.send_keys(char)
                time.sleep(0.1)  # Pausa entre cada tecla
            
            logger.info('✅ Usuario ingresado correctamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error llenando campo de usuario: {e}')
            return False
    
    def fill_password(self, password='RMCC231112'):
        """Llena el campo de contraseña"""
        try:
            logger.info(f'🔑 Llenando campo de contraseña')
            
            password_xpath = '/html/body/div/form/div[2]/div/input'
            
            # Esperar a que el input esté presente
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, password_xpath))
            )
            
            # Limpiar el campo primero
            password_input.clear()
            
            # Escribir la contraseña con pequeñas pausas para simular escritura humana
            for char in password:
                password_input.send_keys(char)
                time.sleep(0.1)  # Pausa entre cada tecla
            
            logger.info('✅ Contraseña ingresada correctamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error llenando campo de contraseña: {e}')
            return False
    
    def submit_login_form(self):
        """Hace click en el botón de submit del formulario de login"""
        try:
            logger.info('🔘 Haciendo click en botón de submit...')
            
            submit_button_xpath = '/html/body/div/form/div[4]/button'
            
            # Esperar a que el botón esté presente y clickeable
            submit_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
            )
            
            logger.info('✅ Botón de submit encontrado, haciendo click...')
            submit_button.click()
            
            # Esperar a que la página navegue después del submit
            logger.info('⏳ Esperando navegación después del login...')
            time.sleep(3)
            
            logger.info('✅ Formulario enviado')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error haciendo submit del formulario: {e}')
            return False
    
    def click_login_button(self):
        """Hace click en el botón de inicio de sesión y espera a que cargue"""
        try:
            logger.info('🔘 Buscando botón de inicio de sesión...')
            
            # Esperar a que el botón esté presente
            login_button_xpath = '/html/body/app-root/app-iniciar-sesion/nz-layout/div[2]/div/div[1]/div/div/app-campo-login/nz-layout/div/div/nz-form-item/div[2]/div/div/div/app-card-glass/div/nz-content[2]/form/nz-form-item/nz-form-control/div/div/div/button'
            
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, login_button_xpath))
            )
            
            logger.info('✅ Botón encontrado, haciendo click...')
            login_button.click()
            
            # Esperar a que la página navegue/cargue después del click
            logger.info('⏳ Esperando a que cargue la siguiente página...')
            time.sleep(3)
            
            # Esperar a que desaparezca el botón o aparezca nuevo contenido
            WebDriverWait(self.driver, 10).until(
                EC.staleness_of(login_button)
            )
            
            logger.info('✅ Página cargada después del click')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error haciendo click en botón de login: {e}')
            return False
    
    def select_office(self, office_name):
        """Selecciona la oficina registral"""
        try:
            logger.info(f'🏢 Seleccionando oficina registral: {office_name}...')
            
            # Click en el input del selector de oficina
            office_input_xpath = '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div/div[1]/span/nz-card[1]/div/div/div/app-select-oficina-registral/div/div/nz-form-item/nz-form-control/div/div/nz-select/nz-select-top-control/nz-select-search/input'
            
            office_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, office_input_xpath))
            )
            
            logger.info('✅ Input de oficina encontrado, haciendo click...')
            office_input.click()
            
            # Esperar a que aparezcan las opciones
            time.sleep(1)
            
            # Buscar y hacer click en la oficina especificada
            logger.info(f'🔍 Buscando opción {office_name}...')
            options_container_xpath = '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport'
            
            # Esperar a que el contenedor de opciones esté presente
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, options_container_xpath))
            )
            
            # Hacer scroll hasta encontrar la oficina
            logger.info(f'📜 Haciendo scroll hasta encontrar {office_name}...')
            office_found = self.driver.execute_script(f"""
                const container = document.evaluate(
                    '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport',
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                ).singleNodeValue;
                
                if (!container) return false;
                
                const itemsContainer = document.evaluate(
                    '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport/div[1]',
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                ).singleNodeValue;
                
                const targetOffice = '{office_name}';
                
                // Función para buscar la oficina en los items actualmente visibles
                function findOffice() {{
                    const items = itemsContainer.querySelectorAll('nz-option-item');
                    for (let item of items) {{
                        if (item.getAttribute('title') === targetOffice) {{
                            return item;
                        }}
                    }}
                    return null;
                }}
                
                // Intentar encontrar la oficina haciendo scroll gradual
                return new Promise((resolve) => {{
                    let scrollAttempts = 0;
                    const maxAttempts = 50;
                    
                    const interval = setInterval(() => {{
                        // Buscar la oficina en cada iteración
                        const officeItem = findOffice();
                        if (officeItem) {{
                            clearInterval(interval);
                            officeItem.scrollIntoView({{ block: 'center' }});
                            setTimeout(() => {{
                                officeItem.click();
                                resolve(true);
                            }}, 300);
                            return;
                        }}
                        
                        // Hacer scroll
                        container.scrollTop += 100;
                        scrollAttempts++;
                        
                        // Si llegamos al final o al máximo de intentos sin encontrar
                        if (container.scrollTop + container.clientHeight >= container.scrollHeight || 
                            scrollAttempts >= maxAttempts) {{
                            clearInterval(interval);
                            resolve(false);
                        }}
                    }}, 100);
                }});
            """)
            
            if office_found:
                logger.info(f'✅ {office_name} seleccionado correctamente')
                # time.sleep(1)
                return True
            else:
                logger.error(f'❌ No se encontró la opción {office_name}')
                return False
            
        except Exception as e:
            logger.error(f'❌ Error seleccionando oficina: {e}')
            return False
            return False
    
    def click_registry_type_selector(self):
        """Hace click en el selector de tipo de registro"""
        try:
            logger.info('📋 Haciendo click en selector de tipo de registro...')
            
            registry_selector_xpath = '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div/div[1]/span/nz-card[2]/div/div/div[1]/div/div/app-select/div/nz-form-item/nz-form-control/div/div/nz-select/nz-select-top-control/nz-select-item'
            
            registry_selector = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, registry_selector_xpath))
            )
            
            logger.info('✅ Selector encontrado, haciendo click...')
            registry_selector.click()
            
            time.sleep(1)
            logger.info('✅ Click en selector de tipo de registro completado')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error haciendo click en selector de tipo de registro: {e}')
            return False
    
    def select_vehicular_property(self):
        """Selecciona la opción 'Propiedad Vehicular' del select"""
        try:
            logger.info('🚗 Seleccionando Propiedad Vehicular...')
            
            # Esperar a que aparezcan las opciones
            options_container_xpath = '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport'
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, options_container_xpath))
            )
            
            # Buscar y hacer click en "Propiedad Vehicular" usando JavaScript
            vehicular_found = self.driver.execute_script("""
                const container = document.evaluate(
                    '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport',
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                ).singleNodeValue;
                
                if (!container) return false;
                
                const items = container.querySelectorAll('nz-option-item');
                for (let item of items) {
                    if (item.getAttribute('title') === 'Propiedad Vehicular') {
                        item.click();
                        return true;
                    }
                }
                return false;
            """)
            
            if vehicular_found:
                logger.info('✅ Propiedad Vehicular seleccionado correctamente')
                time.sleep(1)
                return True
            else:
                logger.error('❌ No se encontró la opción Propiedad Vehicular')
                return False
            
        except Exception as e:
            logger.error(f'❌ Error seleccionando Propiedad Vehicular: {e}')
            return False
    
    def fill_plate_number(self, plate):
        """Llena el campo de número de placa"""
        try:
            logger.info(f'🚙 Llenando número de placa: {plate}')
            
            plate_input_xpath = '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div/div[1]/span/nz-card[3]/div/form/div/div[2]/nz-form-item/nz-form-control/div/div/input'
            
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
    
    def click_search_button(self):
        """Hace click en el botón de búsqueda"""
        try:
            logger.info('🔍 Haciendo click en botón de búsqueda...')
            
            search_button_xpath = '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div/div[1]/span/nz-card[3]/div/form/div/div[5]/button'
            
            # Esperar a que el botón esté presente y clickeable
            search_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, search_button_xpath))
            )
            
            logger.info('✅ Botón de búsqueda encontrado, haciendo click...')
            search_button.click()
            
            # Esperar a que procese la búsqueda
            logger.info('⏳ Esperando resultados de búsqueda...')
            time.sleep(3)
            
            logger.info('✅ Búsqueda realizada')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error haciendo click en botón de búsqueda: {e}')
            return False
    
    def click_table_button(self):
        """Hace click en el botón de la tabla de resultados después de 5 segundos"""
        try:
            logger.info('⏳ Esperando 5 segundos antes de hacer click en la tabla...')
            # time.sleep(5)
            
            logger.info('📊 Haciendo click en botón de la tabla...')
            
            table_button_xpath = '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div/div[1]/span[2]/nz-card/div/div[5]/div/nz-table/nz-spin/div/div/nz-table-inner-scroll/div[2]/table/tbody/tr[2]/td[7]/app-button/div/div/button'
            
            # Esperar a que el botón esté presente y clickeable
            table_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, table_button_xpath))
            )
            
            logger.info('✅ Botón de tabla encontrado, haciendo click...')
            table_button.click()
            
            # Esperar después del click
            logger.info('⏳ Esperando después del click...')
            time.sleep(3)
            
            logger.info('✅ Click en tabla completado')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error haciendo click en botón de tabla: {e}')
            return False
    
    def iterate_modal_table(self, plate_id, plate_number):
        """Itera sobre cada fila de la tabla del modal, captura información y cierra el modal"""
        try:
            logger.info('📋 Iniciando iteración sobre tabla del modal...')
            
            # XPath de la tabla principal
            tbody_xpath = '/html/body/div/div[3]/div[2]/div/div[2]/div/div/div[2]/div/nz-table/nz-spin/div/div/nz-table-inner-default/div/table/tbody'
            
            # Esperar a que la tabla esté presente
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, tbody_xpath))
            )
            
            # Obtener todas las filas (tr) de la tabla
            rows = self.driver.find_elements(By.XPATH, f'{tbody_xpath}/tr')
            total_rows = len(rows)
            
            logger.info(f'📊 Total de filas encontradas: {total_rows}')
            
            # Lista para almacenar todos los datos extraídos
            all_data = []
            
            # Iterar sobre cada fila
            for index in range(total_rows):
                try:
                    logger.info(f'🔄 Procesando fila {index + 1} de {total_rows}...')
                    
                    # Re-obtener las filas en cada iteración para evitar elementos obsoletos
                    rows = self.driver.find_elements(By.XPATH, f'{tbody_xpath}/tr')
                    row = rows[index]
                    
                    # Obtener el elemento clickeable dentro de la fila
                    clickable_element_xpath = f'{tbody_xpath}/tr[{index + 1}]/td/div[1]/span'
                    
                    try:
                        clickable_element = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, clickable_element_xpath))
                        )
                        
                        # Obtener el texto antes de hacer click
                        row_text = clickable_element.text
                        logger.info(f'   📝 Texto de la fila: {row_text}')
                        
                        # Hacer click en el elemento
                        clickable_element.click()
                        logger.info(f'   ✅ Click realizado en fila {index + 1}')
                        
                        # Esperar a que aparezca el modal
                        time.sleep(1)
                        
                        # Capturar datos de la tabla dentro del modal
                        modal_table_xpath = '/html/body/div/div[5]/div/nz-modal-confirm-container/div/div/div/div/div[1]/div/div/table'
                        
                        try:
                            modal_table = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, modal_table_xpath))
                            )
                            
                            # Obtener el contenido completo de la tabla del modal
                            modal_table_html = modal_table.get_attribute('outerHTML')
                            
                            # Extraer todas las filas de la tabla del modal
                            modal_rows = modal_table.find_elements(By.TAG_NAME, 'tr')
                            
                            logger.info(f'   📋 Datos de la tabla del modal (fila {index + 1}):')
                            
                            modal_data = {}
                            for modal_row in modal_rows:
                                cells = modal_row.find_elements(By.TAG_NAME, 'td')
                                if len(cells) >= 2:
                                    # Usar primera celda como clave y segunda como valor
                                    key = cells[0].text.strip()
                                    value = cells[1].text.strip()
                                    modal_data[key] = value
                                    logger.info(f'      {key}: {value}')
                                elif len(cells) == 1:
                                    # Si solo hay una celda, usar el contenido como clave con valor vacío
                                    key = cells[0].text.strip()
                                    modal_data[key] = ''
                                    logger.info(f'      {key}: (vacío)')
                            
                            # Guardar los datos de esta iteración
                            all_data.append({
                                'row_index': index + 1,
                                'row_text': row_text,
                                'modal_data': modal_data
                            })
                            
                        except Exception as modal_error:
                            logger.warning(f'   ⚠️ No se pudo capturar la tabla del modal: {modal_error}')
                        
                        # Hacer click en el botón para cerrar el modal
                        close_button_xpath = '/html/body/div/div[5]/div/nz-modal-confirm-container/div/div/div/div/div[2]/button'
                        
                        try:
                            close_button = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, close_button_xpath))
                            )
                            close_button.click()
                            logger.info(f'   ✅ Modal cerrado para fila {index + 1}')
                            
                            # Esperar a que el modal se cierre
                            # time.sleep(1)
                            
                        except Exception as close_error:
                            logger.warning(f'   ⚠️ No se pudo cerrar el modal: {close_error}')
                        
                    except Exception as row_error:
                        logger.warning(f'   ⚠️ Error procesando fila {index + 1}: {row_error}')
                        continue
                    
                except Exception as iteration_error:
                    logger.error(f'❌ Error en iteración {index + 1}: {iteration_error}')
                    continue
            
            logger.info(f'✅ Iteración completada. Total de filas procesadas: {len(all_data)}')
            
            # Guardar todos los datos en un archivo JSON
            import json
            os.makedirs('sunarp_scraper', exist_ok=True)
            json_path = os.path.join('sunarp_scraper', 'modal_data.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            logger.info(f'💾 Datos guardados en {json_path}')
            
            # Enviar datos a la API
            if not self.send_data_to_api(plate_id, plate_number, all_data):
                logger.warning('⚠️ No se pudieron enviar los datos a la API')
            
            return True
            
        except Exception as e:
            logger.error(f'❌ Error iterando sobre tabla del modal: {e}')
            return False
    
    def simulate_human_behavior(self):
        """Simula comportamiento humano con movimientos y pausas"""
        try:
            logger.info('🤖 Simulando comportamiento humano...')
            
            # Scroll aleatorio
            scroll_amount = 200
            self.driver.execute_script(f'window.scrollTo(0, {scroll_amount});')
            time.sleep(1)
            
            # Scroll de vuelta
            self.driver.execute_script('window.scrollTo(0, 0);')
            time.sleep(0.5)
            
            logger.info('✅ Simulación completada')
            return True
        except Exception as e:
            logger.error(f'❌ Error simulando comportamiento: {e}')
            return False
    
    def take_screenshot(self, filename='screenshot.png'):
        """Toma una captura de pantalla"""
        try:
            os.makedirs('sunarp_scraper', exist_ok=True)
            screenshot_path = os.path.join('sunarp_scraper', filename)
            self.driver.save_screenshot(screenshot_path)
            logger.info(f'📸 Captura guardada: {screenshot_path}')
            return True
        except Exception as e:
            logger.error(f'❌ Error tomando captura: {e}')
            return False
    
    def format_date_to_iso(self, date_str):
        """
        Convierte fecha en formato '06/05/2024 21:55' a ISO 8601 '2024-05-06T21:55:00Z'
        
        Args:
            date_str (str): Fecha en formato DD/MM/YYYY HH:MM
            
        Returns:
            str: Fecha en formato ISO 8601 o None si hay error
        """
        if not date_str or date_str.strip() == '':
            return None
        
        try:
            # Parsear fecha en formato DD/MM/YYYY HH:MM
            dt = datetime.strptime(date_str.strip(), '%d/%m/%Y %H:%M')
            # Convertir a formato ISO 8601 con Z (UTC)
            return dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        except ValueError as e:
            logger.warning(f'⚠️ No se pudo parsear la fecha "{date_str}": {e}')
            return None
    
    def get_max_version(self, plate_number):
        """
        Obtiene la versión máxima actual de una placa y retorna maxVersion + 1
        
        Args:
            plate_number (str): Número de placa
            
        Returns:
            int: maxVersion + 1, o 1 si no existe versión previa
        """
        try:
            logger.info(f'🔢 Obteniendo versión máxima para placa {plate_number}...')
            
            url = f'http://54.204.68.114:3000/sprl-sunarp/plate/{plate_number}/max-version'
            headers = {'accept': '*/*'}
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            max_version = data.get('maxVersion', 0)
            next_version = max_version + 1
            
            logger.info(f'✅ Versión actual: {max_version}, próxima versión: {next_version}')
            return next_version
            
        except requests.exceptions.RequestException as e:
            logger.warning(f'⚠️ Error obteniendo versión máxima: {e}. Usando versión 1')
            return 1
        except Exception as e:
            logger.warning(f'⚠️ Error inesperado obteniendo versión: {e}. Usando versión 1')
            return 1
    
    def send_data_to_api(self, plate_id, plate_number, all_data):
        """Envía los datos extraídos a la API"""
        try:
            logger.info('📤 Enviando datos a la API...')
            
            # 1. Obtener la versión inicial para esta placa
            current_version = self.get_max_version(plate_number)
            
            # 2. Crear/actualizar registro de placa maestra
            logger.info(f'📝 Creando registro de placa maestra para {plate_number}...')
            master_plate_url = 'http://54.204.68.114:3000/license-plate-master'
            master_plate_data = {
                'plateNumber': plate_number
            }
            response = requests.post(
                master_plate_url, 
                json=master_plate_data,
                headers={'accept': '*/*', 'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()
            logger.info(f'✅ Registro de placa maestra creado')
            
            # 3. Enviar cada registro de all_data a la API
            sunarp_url = 'http://54.204.68.114:3000/sprl-sunarp'
            success_count = 0
            error_count = 0
            
            for data_entry in all_data:
                print("data_entry")
                print(data_entry)
                try:
                    # Extraer información de modal_data
                    modal_data = data_entry.get('modal_data', {})
                    
                    # Construir el payload para cada registro
                    sunarp_payload = {
                        'version': current_version,
                        'registrationDate': None,
                        'presentationDate': None,
                        'category': None,
                        'actType': None,
                        'naturalParticipants': None,
                        'legalParticipants': None,
                        'notes': data_entry.get('row_text', ''),
                        'createdBy': 1,
                        'plateNumber': plate_number
                    }
                    
                    # Intentar extraer datos de modal_data (ahora es un dict)
                    for key, value in modal_data.items():
                        key_lower = key.lower()
                        
                        # Mapear los campos según la estructura de SUNARP
                        if 'inscripción' in key_lower:
                            # Convertir fecha a formato ISO 8601
                            sunarp_payload['registrationDate'] = self.format_date_to_iso(value)
                        elif 'presentación' in key_lower:
                            # Convertir fecha a formato ISO 8601
                            sunarp_payload['presentationDate'] = self.format_date_to_iso(value)
                        elif 'rubro' in key_lower:
                            sunarp_payload['category'] = value
                        elif 'acto' in key_lower:
                            sunarp_payload['actType'] = value
                        elif 'participantes naturales' in key_lower:
                            sunarp_payload['naturalParticipants'] = value
                        elif 'participantes juridicos' in key_lower:
                            sunarp_payload['legalParticipants'] = value
                    
                    logger.info(f'📝 Enviando registro {data_entry.get("row_index")}...')
                    response = requests.post(
                        sunarp_url,
                        json=sunarp_payload,
                        headers={'accept': '*/*', 'Content-Type': 'application/json'},
                        timeout=10
                    )
                    response.raise_for_status()
                    success_count += 1
                    logger.info(f'✅ Registro {data_entry.get("row_index")} enviado exitosamente')
                    
                except Exception as entry_error:
                    error_count += 1
                    logger.error(f'❌ Error enviando registro {data_entry.get("row_index")}: {entry_error}')
                    continue

            # 1. Marcar placa como cargada
            logger.info(f'📝 Marcando placa {plate_id} como cargada...')
            mark_loaded_url = f'http://54.204.68.114:3000/pending-car-plates/{plate_id}/mark-loaded/A'
            response = requests.patch(mark_loaded_url, headers={'accept': '*/*'}, timeout=10)
            response.raise_for_status()
            logger.info(f'✅ Placa {plate_id} marcada como cargada')
            
            logger.info(f'📊 Resumen: {success_count} registros enviados, {error_count} errores')
            return success_count > 0
            
        except Exception as e:
            logger.error(f'❌ Error enviando datos a la API: {e}')
            return False
    
    def login(self, headless=False):
        """Realiza el proceso de login en SUNARP"""
        try:
            logger.info('🔐 Iniciando proceso de login...')
            
            # Configurar driver
            if not self.setup_driver(headless=headless):
                return False
            
            # Navegar a la página
            if not self.navigate_to_page():
                return False
            
            # Simular comportamiento humano
            self.simulate_human_behavior()
            
            # Hacer click en el botón de login
            if not self.click_login_button():
                return False
            
            # Llenar el campo de usuario
            if not self.fill_username('WZUNIGAH'):
                return False
            
            # Llenar el campo de contraseña
            if not self.fill_password('RMCC231112'):
                return False
            
            # Hacer submit del formulario
            if not self.submit_login_form():
                return False
            
            # Esperar a que cargue la página principal
            logger.info('⏳ Esperando a que cargue la página principal...')
            time.sleep(5)
            
            logger.info('✅ Login completado exitosamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error en el login: {e}')
            return False
    
    def close_previous_modals(self):
        """Cierra modales anteriores antes de procesar una nueva placa"""
        try:
            logger.info('🔄 Recargando página...')
            
            # Por ahora solo recarga la página
            self.driver.refresh()
            
            # Esperar a que la página cargue completamente
            time.sleep(3)
            
            logger.info('✅ Página recargada correctamente')
            return True
            
            # # Botón 1: Cerrar modal principal
            # try:
            #     button1_xpath = '/html/body/div/div[3]/div[2]/div/div[2]/div/div/div[1]/button'
            #     button1 = WebDriverWait(self.driver, 3).until(
            #         EC.element_to_be_clickable((By.XPATH, button1_xpath))
            #     )
            #     button1.click()
            #     logger.info('✅ Modal principal cerrado')
            #     time.sleep(0.5)
            # except:
            #     logger.debug('ℹ️ Primer botón no encontrado (puede estar ya cerrado)')
            
            # # Botón 2: Cerrar modal secundario
            # try:
            #     button2_xpath = '/html/body/div/div[2]/div/nz-modal-container/div/div/button'
            #     button2 = WebDriverWait(self.driver, 3).until(
            #         EC.element_to_be_clickable((By.XPATH, button2_xpath))
            #     )
            #     button2.click()
            #     logger.info('✅ Modal secundario cerrado')
            #     time.sleep(0.5)
            # except:
            #     logger.debug('ℹ️ Segundo botón no encontrado (puede estar ya cerrado)')
            
            # # Botón 3: Limpiar búsqueda
            # try:
            #     button3_xpath = '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div/div[1]/span[2]/nz-card/div/div[8]/div[2]/app-button/div/div/button'
            #     button3 = WebDriverWait(self.driver, 3).until(
            #         EC.element_to_be_clickable((By.XPATH, button3_xpath))
            #     )
            #     button3.click()
            #     logger.info('✅ Búsqueda limpiada')
            #     time.sleep(1)
            # except:
            #     logger.debug('ℹ️ Tercer botón no encontrado (puede estar ya limpio)')
            
            # logger.info('✅ Modales cerrados correctamente')
            # return True
            
        except Exception as e:
            logger.warning(f'⚠️ Error recargando página: {e}')
            return False
    
    def process_plate(self, office_name, plate_number, plate_id):
        """Procesa una placa específica"""
        try:
            logger.info(f'📋 Procesando placa:')
            logger.info(f'   🏢 Oficina: {office_name}')
            logger.info(f'   🚙 Placa: {plate_number}')
            
            # Seleccionar oficina (parámetro dinámico)
            if not self.select_office(office_name):
                return False
            
            # Click en selector de tipo de registro
            if not self.click_registry_type_selector():
                return False
            
            # Seleccionar Propiedad Vehicular
            if not self.select_vehicular_property():
                return False
            
            # Llenar número de placa (parámetro dinámico)
            if not self.fill_plate_number(plate_number):
                return False
            
            # Click en botón de búsqueda
            if not self.click_search_button():
                return False
            
            # Click en botón de la tabla (después de 5 segundos)
            if not self.click_table_button():
                return False
            
            # Iterar sobre la tabla del modal
            if not self.iterate_modal_table(plate_id, plate_number):
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
                # Cerrar todas las ventanas primero
                try:
                    self.driver.close()
                except:
                    pass
                
                # Esperar un momento antes de quit
                time.sleep(0.5)
                
                # Terminar el driver
                self.driver.quit()
                
                # Limpiar la referencia
                self.driver = None
                
                logger.info('✅ Navegador cerrado')
            except Exception as e:
                logger.error(f'❌ Error cerrando navegador: {e}')
                # Forzar limpieza de referencia incluso si falla
                self.driver = None


def get_pending_plate():
    """
    Obtiene la primera placa pendiente de la API
    
    Returns:
        dict: Diccionario con la información de la placa o None si hay error
    """
    try:
        logger.info('🌐 Obteniendo placa pendiente de la API...')
        
        url = 'http://54.204.68.114:3000/pending-car-plates/unloaded/A/first'
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
    logger.info('🚗 SUNARP Scraper - Python')
    logger.info('=' * 60)
    
    scraper = SunarpScraper()
    needs_login = True
    
    try:
        while True:
            try:
                # Hacer login si es necesario
                if needs_login:
                    logger.info('🔄 Iniciando sesión en SUNARP...')
                    success = scraper.login(headless=False)
                    
                    if not success:
                        logger.error('❌ Fallo en el login, reintentando en 5 segundos...')
                        scraper.cleanup()
                        scraper = SunarpScraper()
                        time.sleep(5)
                        continue
                    
                    needs_login = False
                    logger.info('✅ Sesión iniciada correctamente')
                else:
                    # Si no necesita login, cerrar modales previos
                    scraper.close_previous_modals()
                
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
                
                # Obtener la oficina registral basándose en la primera letra de la placa
                office_name = get_office_by_plate(plate_number)
                
                if office_name == False:
                    logger.warning(f'⚠️ No se encontró oficina para la placa {plate_number}, marcando como cargada y pidiendo otra...')
                    continue
                
                logger.info(f'\n📋 Procesando:')
                logger.info(f'   🆔 ID: {plate_id}')
                logger.info(f'   🚙 Placa: {plate_number}')
                logger.info(f'   🏢 Oficina detectada: {office_name}')
                
                # Procesar placa usando sesión existente
                success = scraper.process_plate(office_name, plate_number, plate_id)
                
                if success:
                    logger.info('✅ Placa procesada exitosamente')
                else:
                    logger.warning('⚠️ Fallo al procesar placa, reiniciando sesión...')
                    needs_login = True
                    scraper.cleanup()
                    scraper = SunarpScraper()
                
                # Pequeña pausa entre procesamiento de placas
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                logger.info('\n🛑 Proceso interrumpido por el usuario')
                break
            except Exception as e:
                logger.error(f'❌ Error inesperado en el ciclo: {e}')
                needs_login = True
                scraper.cleanup()
                scraper = SunarpScraper()
                time.sleep(2)
                
    finally:
        # Limpieza final
        scraper.cleanup()
        logger.info('👋 Scraper finalizado')


if __name__ == '__main__':
    main()
