import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import requests
from datetime import datetime
import json
from llama_cloud_services import LlamaParse
from dotenv import load_dotenv
import os
import cv2
import numpy as np
from PIL import Image
import deathbycaptcha
import re
from bs4 import BeautifulSoup

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
        self.url = 'https://consultavehicular.sunarp.gob.pe/consulta-vehicular/inicio'
        self.captcha_id = None  # Para almacenar el ID del captcha resuelto
        
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
        
        # Optimizaciones de rendimiento - sin bloquear imágenes (necesarias para captcha)
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        
        # Estrategia de carga de página: 'eager' no espera recursos externos
        options.page_load_strategy = 'eager'
        
        # Preferencias adicionales - bloquear solo recursos no críticos
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
            'profile.managed_default_content_settings.stylesheets': 2,  # Bloquear CSS
            'profile.managed_default_content_settings.fonts': 2,  # Bloquear fuentes
            'profile.managed_default_content_settings.media_stream': 2,  # Bloquear media
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
    
    def get_captcha_image(self):
        """Obtiene la imagen del captcha y la guarda"""
        try:
            logger.info('🖼️ Obteniendo imagen del captcha...')
            
            captcha_img_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content/div/nz-card/div/app-form-datos-consulta/div/form/fieldset/nz-form-item[2]/table/tr/td[1]/img'
            
            # Esperar a que la imagen esté presente
            captcha_img = WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.XPATH, captcha_img_xpath))
            )
            
            logger.info('✅ Imagen del captcha encontrada')
            
            # Obtener la imagen y guardarla
            os.makedirs('consulta_vehicular', exist_ok=True)
            captcha_path = os.path.join('consulta_vehicular', 'captcha.png')
            captcha_img.screenshot(captcha_path)
            
            logger.info(f'💾 Imagen del captcha guardada como {captcha_path}')
            
            # Aplicar filtros de imagen para mejorar OCR
            # self.preprocess_captcha_image('captcha.png')
            
            return True
            
        except Exception as e:
            logger.error(f'❌ Error obteniendo imagen del captcha: {e}')
            return False
    
    def preprocess_captcha_image(self, image_path='consulta_vehicular/captcha.png'):
        """Aplica filtros de procesamiento de imagen para mejorar el OCR"""
        try:
            logger.info('🔧 Aplicando filtros de mejora de imagen...')
            
            # Leer la imagen
            img = cv2.imread(image_path)
            
            # Convertir a escala de grises
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Aplicar umbralización adaptativa para mejorar contraste
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            
            # Reducir ruido con filtro de mediana
            denoised = cv2.medianBlur(thresh, 3)
            
            # Aumentar el contraste
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            # Aplicar dilatación y erosión para mejorar caracteres
            kernel = np.ones((2,2), np.uint8)
            morph = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)
            
            # Aumentar la nitidez
            sharpening_kernel = np.array([[-1,-1,-1],
                                          [-1, 9,-1],
                                          [-1,-1,-1]])
            sharpened = cv2.filter2D(morph, -1, sharpening_kernel)
            
            # Redimensionar imagen para mejor OCR (aumentar tamaño)
            height, width = sharpened.shape
            resized = cv2.resize(sharpened, (width * 3, height * 3), interpolation=cv2.INTER_CUBIC)
            
            # Guardar imagen procesada
            cv2.imwrite(image_path, resized)
            
            logger.info('✅ Filtros aplicados exitosamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error aplicando filtros: {e}')
            return False
    
    def parse_captcha_with_llama(self, image_path='consulta_vehicular/captcha.png'):
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
                self.captcha_id = captcha.get('captcha')  # Guardar ID para posible reporte
                logger.info(f'✅ Captcha resuelto: {result} (ID: {self.captcha_id})')
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
            
            captcha_input_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content/div/nz-card/div/app-form-datos-consulta/div/form/fieldset/nz-form-item[2]/table/tr/td[3]/nz-form-item/nz-form-control/div/div/nz-input-group/input'
            
            captcha_input = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, captcha_input_xpath))
            )
            
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            
            logger.info('✅ Captcha llenado correctamente')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error llenando captcha: {e}')
            return False
    
    def report_incorrect_captcha(self):
        """Reporta un captcha incorrectamente resuelto a DeathByCaptcha para obtener reembolso"""
        if not self.captcha_id:
            logger.warning('⚠️ No hay captcha_id para reportar')
            return False
        
        try:
            logger.info(f'📢 Reportando captcha incorrecto (ID: {self.captcha_id}) a DeathByCaptcha...')
            
            # Obtener credenciales
            dbc_username = os.getenv('DBC_USERNAME')
            dbc_password = os.getenv('DBC_PASSWORD')
            
            if not dbc_username or not dbc_password:
                logger.error('❌ No se encontraron credenciales de DBC')
                return False
            
            # Configurar cliente y reportar
            client = deathbycaptcha.SocketClient(dbc_username, dbc_password)
            result = client.report(self.captcha_id)
            
            if result:
                logger.info(f'✅ Captcha reportado exitosamente. Se obtendrá reembolso.')
                return True
            else:
                logger.warning('⚠️ No se pudo reportar el captcha')
                return False
                
        except Exception as e:
            logger.error(f'❌ Error reportando captcha: {e}')
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
    
    # COMENTADO: Versión anterior que guardaba screenshot
    # def get_result_image(self):
    #     """Obtiene la imagen del resultado y la guarda"""
    #     try:
    #         logger.info('🖼️ Obteniendo imagen del resultado...')
    #         
    #         result_img_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content/div/nz-card/div/app-form-datos-consulta/div/img'
    #         
    #         # Esperar a que la imagen esté presente
    #         result_img = WebDriverWait(self.driver, 15).until(
    #             EC.presence_of_element_located((By.XPATH, result_img_xpath))
    #         )
    #         
    #         logger.info('✅ Imagen del resultado encontrada')
    #         
    #         # Obtener la imagen y guardarla
    #         os.makedirs('consulta_vehicular', exist_ok=True)
    #         result_path = os.path.join('consulta_vehicular', 'result.png')
    #         result_img.screenshot(result_path)
    #         
    #         logger.info(f'💾 Imagen del resultado guardada como {result_path}')
    #         return True
    #         
    #     except Exception as e:
    #         logger.error(f'❌ Error obteniendo imagen del resultado: {e}')
    #         return False
    
    def get_result_image_base64(self):
        """Obtiene el base64 de la imagen del resultado directamente del atributo src"""
        try:
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
    
    # COMENTADO: Ya no se usa LlamaParse localmente
    # def parse_result_with_llama(self, image_path='consulta_vehicular/result.png', output_file='consulta_vehicular/result.json'):
    #     """Parsea la imagen del resultado usando LlamaParse y guarda en JSON"""
    #     try:
    #         logger.info('🤖 Parseando resultado con Llama...')')
    #         
    #         # Obtener API key desde variables de entorno
    #         api_key = os.getenv('LLAMA_CLOUD_API_KEY')
    #         if not api_key:
    #             logger.error('❌ LLAMA_CLOUD_API_KEY no encontrada en .env')
    #             return None
    #         
    #         parser = LlamaParse(
    #             api_key=api_key,
    #             result_type="markdown",
    #             parse_mode="parse_page_with_agent",
    #             model="openai-gpt-4-1-mini",
    #             high_res_ocr=True,
    #             adaptive_long_table=True,
    #             outlined_table_extraction=True,
    #             output_tables_as_HTML=True,
    #             precise_bounding_box=True,
    #         )
    #         documents = parser.load_data(image_path)
    #
    #         print(documents)
    #         
    #         # Extraer el texto markdown del documento
    #         result_text = documents[0].text if documents else ""
    #         
    #         # Extraer datos de la tabla HTML
    #         vehicle_data = self.extract_vehicle_data_from_markdown(result_text)
    #         
    #         # Guardar resultado en JSON
    #         result_data = {
    #             "markdown": result_text,
    #             "vehicle_data": vehicle_data,
    #             "timestamp": datetime.now().isoformat(),
    #             "image_path": image_path
    #         }
    #         
    #         os.makedirs('consulta_vehicular', exist_ok=True)
    #         with open(output_file, 'w', encoding='utf-8') as f:
    #             json.dump(result_data, f, ensure_ascii=False, indent=2)
    #         
    #         logger.info(f'✅ Resultado parseado y guardado en {output_file}')
    #         logger.info(f'📊 Datos extraídos: {vehicle_data}')
    #         return result_data
    #         
    #     except Exception as e:
    #         logger.error(f'❌ Error parseando resultado: {e}')
    #         return None
    
    def extract_vehicle_data_from_markdown(self, markdown_text):
        """Extrae los datos del vehículo desde el markdown y los convierte a diccionario"""
        try:
            logger.info('🔍 Extrayendo datos del vehículo desde markdown...')
            
            vehicle_data = {}
            
            # Buscar la tabla HTML en el markdown
            table_match = re.search(r'<table>(.*?)</table>', markdown_text, re.DOTALL)
            
            if table_match:
                table_html = table_match.group(0)
                
                # Parsear HTML con BeautifulSoup
                soup = BeautifulSoup(table_html, 'html.parser')
                
                # Extraer todas las filas
                rows = soup.find_all('tr')

                for row in rows:
                    cells = row.find_all('td')
                    
                    # Si no hay td, buscar th (para casos donde el key está en th)
                    if len(cells) == 0:
                        cells = row.find_all('th')
                    
                    # También manejar casos mixtos (th + td)
                    if len(cells) < 2:
                        th_cells = row.find_all('th')
                        td_cells = row.find_all('td')
                        if len(th_cells) > 0 and len(td_cells) > 0:
                            cells = th_cells + td_cells
                    
                    if len(cells) >= 2:
                        # Obtener clave y valor
                        key_cell = cells[0].get_text(strip=True)
                        value_cell = cells[1].get_text(strip=True)
                        
                        # Limpiar la clave (remover ** y :)
                        key = key_cell.replace('**', '').replace(':', '').strip()
                        
                        # Normalizar nombres de claves
                        key_mapping = {
                            'Nº PLACA': 'placa',
                            'Nº SERIE': 'serie',
                            'Nº VIN': 'vin',
                            'Nº MOTOR': 'motor',
                            'COLOR': 'color',
                            'MARCA': 'marca',
                            'MODELO': 'modelo',
                            'PLACA VIGENTE': 'placa_vigente',
                            'PLACA ANTERIOR': 'placa_anterior',
                            'ESTADO': 'estado',
                            'ANOTACIONES': 'anotaciones',
                            'SEDE': 'sede',
                            'AÑO DE MODELO': 'anio_modelo'
                        }
                        
                        normalized_key = key_mapping.get(key, key.lower().replace(' ', '_'))
                        vehicle_data[normalized_key] = value_cell
                
                # Extraer propietario(s) si existe
                propietario_match = re.search(r'PROPIETARIO\(S\):\s*\n\n(.+?)(?:\n|$)', markdown_text)
                if propietario_match:
                    vehicle_data['propietario'] = propietario_match.group(1).strip()
                
                logger.info(f'✅ Datos extraídos: {len(vehicle_data)} campos')
                return vehicle_data
            else:
                logger.warning('⚠️ No se encontró tabla en el markdown')
                return {}
                
        except Exception as e:
            logger.error(f'❌ Error extrayendo datos: {e}')
            return {}
    
    # COMENTADO: Ya no se usa este endpoint
    # def send_vehicle_data_to_api(self, vehicle_data, plate_id):
    #     """Envía los datos del vehículo al endpoint de la API"""
    #     try:
    #         logger.info('📤 Enviando datos del vehículo a la API...')')
    #         
    #         # URL del endpoint
    #         api_url = 'http://143.110.206.161:3000/vehicles'
    #         
    #         # Mapear vehicle_data al formato esperado por la API
    #         payload = {
    #             "plateNumber": vehicle_data.get('placa', ''),
    #             "serialNumber": vehicle_data.get('serie', ''),
    #             "vinNumber": vehicle_data.get('vin', ''),
    #             "engineNumber": vehicle_data.get('motor', ''),
    #             "color": vehicle_data.get('color', ''),
    #             "brand": vehicle_data.get('marca', ''),
    #             "model": vehicle_data.get('modelo', ''),
    #             "currentPlate": vehicle_data.get('placa_vigente', ''),
    #             "previousPlate": vehicle_data.get('placa_anterior', ''),
    #             "state": vehicle_data.get('estado', ''),
    #             "notes": vehicle_data.get('anotaciones', ''),
    #             "branchOffice": vehicle_data.get('sede', ''),
    #             "modelYear": int(vehicle_data.get('anio_modelo', 0)) if vehicle_data.get('anio_modelo', '').isdigit() else 0,
    #             "owners": vehicle_data.get('propietario', '')
    #         }
    #         
    #         # Headers
    #         headers = {
    #             'accept': '*/*',
    #             'Content-Type': 'application/json'
    #         }
    #         
    #         logger.info(f'📊 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}')
    #         
    #         # Enviar request POST
    #         response = requests.post(api_url, json=payload, headers=headers)
    #         
    #         # Verificar respuesta
    #         if response.status_code in [200, 201]:
    #             logger.info(f'✅ Datos enviados exitosamente. Respuesta: {response.text}')
    #             
    #             # Marcar placa como cargada en la API
    #             logger.info(f'📝 Marcando placa {plate_id} como cargada...')
    #             mark_loaded_url = f'http://143.110.206.161:3000/pending-car-plates/{plate_id}/mark-loaded/B'
    #             mark_response = requests.patch(mark_loaded_url, headers={'accept': '*/*'}, timeout=10)
    #             mark_response.raise_for_status()
    #             logger.info(f'✅ Placa {plate_id} marcada como cargada')
    #             
    #             return True
    #         else:
    #             logger.error(f'❌ Error al enviar datos. Status: {response.status_code}, Respuesta: {response.text}')
    #             return False
    #             
    #     except Exception as e:
    #         logger.error(f'❌ Error enviando datos a la API: {e}')
    #         return False
    
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
            
            # Parsear captcha con Llama
            captcha_text = self.parse_captcha_with_llama('consulta_vehicular/captcha.png')
            if not captcha_text:
                logger.error('❌ No se pudo parsear el captcha')
                return False
            
            # Llenar el input del captcha
            if not self.fill_captcha_input(captcha_text):
                return False
            
            # Hacer click en el botón de búsqueda
            if not self.click_search_button():
                return False
            
            # Obtener imagen del resultado en base64
            image_base64 = self.get_result_image_base64()
            if not image_base64:
                logger.error('❌ No se pudo obtener la imagen base64')
                return False
            
            # COMENTADO: Ya no se parsea localmente ni se envía vehicle_data
            # # Parsear resultado con Llama y guardar en JSON
            # result_data = self.parse_result_with_llama('consulta_vehicular/result.png', 'consulta_vehicular/result.json')
            #
            # if not result_data:
            #     logger.error('❌ No se pudo parsear el resultado')
            #     return False
            # 
            # # Enviar datos del vehículo a la API
            # vehicle_data = result_data.get('vehicle_data', {})
            # if vehicle_data:
            #     if not self.send_vehicle_data_to_api(vehicle_data, plate_id):
            #         logger.warning('⚠️ No se pudieron enviar los datos a la API, pero el proceso continúa')
            # else:
            #     logger.warning('⚠️ No hay datos del vehículo para enviar a la API')
            
            # Enviar imagen en base64 a la API
            if not self.send_image_to_api(image_base64, plate_number, plate_id):
                logger.warning('⚠️ No se pudo enviar la imagen a la API')
                return False
            
            logger.info('✅ Proceso completado exitosamente')
            
            # Tomar captura de pantalla final
            # self.take_screenshot('consulta_vehicular.png')
            
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
                    headless=True              # Modo headless (opcional, default: False)
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
