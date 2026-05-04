"""SUNARP SPRL Scraper — standalone with full anti-bot measures.

Logs in once and reuses the session across plates.
Refreshes the page between plates to reset state.
"""

import logging
import platform
import time
import warnings
from datetime import datetime

import requests
import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from plate_offices import get_office_by_plate

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

warnings.filterwarnings('ignore', category=ResourceWarning)
warnings.filterwarnings('ignore', message='.*invalid.*handle.*')


def _patched_del(self):
    try:
        self.quit()
    except Exception:
        pass


uc.Chrome.__del__ = _patched_del

CLOUDFLARE_BYPASS_CDP_SCRIPT = '''
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'platform',    { get: () => 'Win32' });
    Object.defineProperty(navigator, 'vendor',      { get: () => 'Google Inc.' });
    Object.defineProperty(navigator, 'userAgent',   { get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' });
    Object.defineProperty(navigator, 'appVersion',  { get: () => '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' });
    Object.defineProperty(navigator, 'languages',          { get: () => ['es-ES', 'es', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory',        { get: () => 8 });
    Object.defineProperty(navigator, 'maxTouchPoints',      { get: () => 0 });
    Object.defineProperty(navigator, 'connection', {
        get: () => ({ effectiveType: '4g', rtt: 50, downlink: 10, saveData: false })
    });
    Object.defineProperty(screen, 'width',       { get: () => 1366 });
    Object.defineProperty(screen, 'height',      { get: () => 768 });
    Object.defineProperty(screen, 'availWidth',  { get: () => 1366 });
    Object.defineProperty(screen, 'availHeight', { get: () => 728 });
    Object.defineProperty(screen, 'colorDepth',  { get: () => 24 });
    Object.defineProperty(screen, 'pixelDepth',  { get: () => 24 });
    Object.defineProperty(window, 'outerWidth',  { get: () => 1366 });
    Object.defineProperty(window, 'outerHeight', { get: () => 900 });
    Object.defineProperty(window, 'innerWidth',  { get: () => 1366 });
    Object.defineProperty(window, 'innerHeight', { get: () => 768 });
    Object.defineProperty(window, 'devicePixelRatio', { get: () => 1 });
    document.hasFocus = () => true;
    if (navigator.permissions && navigator.permissions.query) {
        const origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = (params) => {
            if (params.name === 'notifications') return Promise.resolve({ state: 'prompt', onchange: null });
            return origQuery(params);
        };
    }
    try { Object.defineProperty(Notification, 'permission', { get: () => 'default' }); } catch(e) {}
    const makePlugin = (name, filename, description, mimeTypes) => {
        const plugin = Object.create(Plugin.prototype);
        Object.defineProperties(plugin, {
            name: { value: name }, filename: { value: filename },
            description: { value: description }, length: { value: mimeTypes.length }
        });
        mimeTypes.forEach((mt, i) => { plugin[i] = mt; });
        return plugin;
    };
    const pdfMime = Object.create(MimeType.prototype);
    Object.defineProperties(pdfMime, {
        type: { value: 'application/pdf' }, suffixes: { value: 'pdf' },
        description: { value: 'Portable Document Format' }
    });
    const pluginList = [
        makePlugin('PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format', [pdfMime]),
        makePlugin('Chrome PDF Viewer', 'internal-pdf-viewer', '', [pdfMime]),
        makePlugin('Chromium PDF Viewer', 'internal-pdf-viewer', '', [pdfMime]),
        makePlugin('Microsoft Edge PDF Viewer', 'internal-pdf-viewer', '', [pdfMime]),
        makePlugin('WebKit built-in PDF', 'internal-pdf-viewer', '', [pdfMime]),
    ];
    Object.defineProperty(navigator, 'plugins', {
        get: () => Object.assign(Object.create(PluginArray.prototype),
            pluginList.reduce((a, p, i) => { a[i] = p; return a; }, { length: pluginList.length }))
    });
    const glHandler = {
        apply(target, ctx, args) {
            if (args[0] === 37445) return 'Google Inc. (NVIDIA)';
            if (args[0] === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)';
            return Reflect.apply(target, ctx, args);
        }
    };
    if (WebGLRenderingContext.prototype.getParameter)
        WebGLRenderingContext.prototype.getParameter = new Proxy(WebGLRenderingContext.prototype.getParameter, glHandler);
    if (typeof WebGL2RenderingContext !== 'undefined' && WebGL2RenderingContext.prototype.getParameter)
        WebGL2RenderingContext.prototype.getParameter = new Proxy(WebGL2RenderingContext.prototype.getParameter, glHandler);
    window.chrome = {
        app: {
            isInstalled: false,
            InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
            getDetails: () => null, getIsInstalled: () => false, runningState: () => 'cannot_run'
        },
        csi: () => {}, loadTimes: () => ({}),
        runtime: {
            connect: () => {}, sendMessage: () => {},
            OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', UPDATE: 'update' },
            PlatformOs: { WIN: 'win', MAC: 'mac', LINUX: 'linux', ANDROID: 'android' }
        }
    };
'''


class SunarpScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://sprl.sunarp.gob.pe/sprl/ingreso'
        self._virtual_display = None
        self._startup_modal_close_xpath = '/html/body/div/div[2]/div/nz-modal-container/div/div/button'

    # ------------------------------------------------------------------ #
    #  Driver setup                                                        #
    # ------------------------------------------------------------------ #

    def setup_driver(self, headless=False):
        if headless and platform.system() == 'Linux':
            try:
                from pyvirtualdisplay import Display
                self._virtual_display = Display(visible=False, size=(1366, 768))
                self._virtual_display.start()
                logger.info('Xvfb virtual display started')
                headless = False
            except ImportError:
                logger.warning('pyvirtualdisplay not installed, falling back to --headless=new')
            except Exception as e:
                logger.warning(f'Could not start virtual display: {e}')

        options = uc.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--lang=es-ES')
        options.add_argument('--window-size=1366,900')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
        )
        if headless:
            options.add_argument('--headless=new')

        options.page_load_strategy = 'eager'
        options.add_experimental_option('prefs', {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
        })

        try:
            self.driver = uc.Chrome(options=options, version_main=147)
            try:
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': CLOUDFLARE_BYPASS_CDP_SCRIPT
                })
            except Exception as e:
                logger.warning(f'Could not inject CDP scripts: {e}')
            return True
        except Exception as e:
            logger.error(f'Error configuring driver: {e}')
            return False

    # ------------------------------------------------------------------ #
    #  Utility                                                             #
    # ------------------------------------------------------------------ #

    def format_date_to_iso(self, date_str):
        if not date_str or not date_str.strip():
            return None
        try:
            dt = datetime.strptime(date_str.strip(), '%d/%m/%Y %H:%M')
            return dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        except ValueError:
            return None

    # ------------------------------------------------------------------ #
    #  Login                                                               #
    # ------------------------------------------------------------------ #

    def navigate_to_page(self):
        try:
            logger.info(f'Navigating to {self.url}...')
            self.driver.get(self.url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-root'))
            )
            self.close_startup_modal_if_present()
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f'Error navigating: {e}')
            return False

    def close_startup_modal_if_present(self, wait_timeout=2):
        try:
            close_button = WebDriverWait(self.driver, wait_timeout).until(
                EC.presence_of_element_located((By.XPATH, self._startup_modal_close_xpath))
            )
            try:
                close_button.click()
            except Exception:
                self.driver.execute_script('arguments[0].click();', close_button)

            WebDriverWait(self.driver, 5).until(
                EC.invisibility_of_element_located((By.XPATH, '//nz-modal-container'))
            )
            logger.info('Startup modal detected and closed')
            time.sleep(1)
            return True
        except TimeoutException:
            return True
        except Exception as e:
            logger.warning(f'Startup modal detected but could not be closed: {e}')
            return True

    def click_login_button(self):
        try:
            login_button_xpath = (
                '/html/body/app-root/app-iniciar-sesion/nz-layout/div[2]/div/div[1]/div/div'
                '/app-campo-login/nz-layout/div/div/nz-form-item/div[2]/div/div/div'
                '/app-card-glass/div/nz-content[2]/form/nz-form-item/nz-form-control'
                '/div/div/div/button'
            )
            for attempt in range(2):
                self.close_startup_modal_if_present(wait_timeout=2)
                login_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, login_button_xpath))
                )

                try:
                    login_button.click()
                    break
                except ElementClickInterceptedException:
                    logger.warning(f'Login click intercepted (attempt {attempt + 1}/2), retrying...')
                    self.close_startup_modal_if_present(wait_timeout=2)

                    if attempt == 1:
                        self.driver.execute_script('arguments[0].click();', login_button)
            # Wait for the login form to appear (Angular route change)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '/html/body/div/form'))
            )
            return True
        except Exception as e:
            logger.error(f'Error clicking login button: {e}')
            return False

    def _fill_input_reliably(self, input_xpath, value, field_name, max_attempts=4):
        for attempt in range(1, max_attempts + 1):
            input_el = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, input_xpath))
            )

            input_el.click()
            input_el.send_keys(Keys.CONTROL, 'a')
            input_el.send_keys(Keys.DELETE)
            time.sleep(0.1)

            for char in value:
                input_el.send_keys(char)
                time.sleep(0.07)

            typed_value = (input_el.get_attribute('value') or '').strip()
            if typed_value == value:
                return True

            logger.warning(
                f'{field_name} mismatch on attempt {attempt}/{max_attempts}: '
                f'"{typed_value}" != "{value}"'
            )
            time.sleep(0.2)

        # Fallback: set value via JS and trigger input/change so Angular sees the update.
        input_el = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, input_xpath))
        )
        self.driver.execute_script(
            """
            const input = arguments[0];
            const targetValue = arguments[1];
            input.focus();
            input.value = targetValue;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            input_el,
            value,
        )

        typed_value = (input_el.get_attribute('value') or '').strip()
        if typed_value == value:
            logger.info(f'{field_name} filled correctly using JS fallback')
            return True

        logger.error(f'Could not fill {field_name} correctly after retries')
        return False

    def fill_username(self, username='WZUNIGAH'):
        try:
            return self._fill_input_reliably(
                '/html/body/div/form/div[1]/div/input',
                username,
                'username',
            )
        except Exception as e:
            logger.error(f'Error filling username: {e}')
            return False

    def fill_password(self, password='RMCC231112'):
        try:
            return self._fill_input_reliably(
                '/html/body/div/form/div[2]/div/input',
                password,
                'password',
            )
        except Exception as e:
            logger.error(f'Error filling password: {e}')
            return False

    def submit_login_form(self):
        try:
            submit_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '/html/body/div/form/div[4]/button'))
            )
            submit_button.click()
            # Wait for Angular main app to load after login
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-main'))
            )
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f'Error submitting login form: {e}')
            return False

    def login(self, headless=False):
        try:
            logger.info('Starting login...')
            if not self.setup_driver(headless=headless):
                return False
            if not self.navigate_to_page():
                return False
            if not self.click_login_button():
                return False
            if not self.fill_username():
                return False
            if not self.fill_password():
                return False
            if not self.submit_login_form():
                return False
            logger.info('Login completed')
            return True
        except Exception as e:
            logger.error(f'Login error: {e}')
            return False

    # ------------------------------------------------------------------ #
    #  Plate processing                                                    #
    # ------------------------------------------------------------------ #

    def reset_page(self):
        try:
            self.driver.refresh()
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-main'))
            )
            time.sleep(3)
            return True
        except Exception as e:
            logger.warning(f'Error resetting page: {e}')
            return False

    def select_office(self, office_name):
        try:
            office_input_xpath = (
                '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content'
                '/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div'
                '/div[1]/span/nz-card[1]/div/div/div/app-select-oficina-registral/div/div'
                '/nz-form-item/nz-form-control/div/div/nz-select/nz-select-top-control'
                '/nz-select-search/input'
            )
            office_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, office_input_xpath))
            )
            office_input.click()
            time.sleep(1)

            options_xpath = '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport'
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, options_xpath))
            )

            office_found = self.driver.execute_script(f"""
                const container = document.evaluate(
                    '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport',
                    document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                ).singleNodeValue;
                if (!container) return false;

                const itemsContainer = document.evaluate(
                    '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport/div[1]',
                    document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                ).singleNodeValue;

                const targetOffice = '{office_name}';
                function findOffice() {{
                    const items = itemsContainer.querySelectorAll('nz-option-item');
                    for (let item of items) {{
                        if (item.getAttribute('title') === targetOffice) return item;
                    }}
                    return null;
                }}

                return new Promise((resolve) => {{
                    let attempts = 0;
                    const interval = setInterval(() => {{
                        const item = findOffice();
                        if (item) {{
                            clearInterval(interval);
                            item.scrollIntoView({{ block: 'center' }});
                            setTimeout(() => {{ item.click(); resolve(true); }}, 300);
                            return;
                        }}
                        container.scrollTop += 100;
                        if (container.scrollTop + container.clientHeight >= container.scrollHeight || attempts++ >= 50) {{
                            clearInterval(interval);
                            resolve(false);
                        }}
                    }}, 100);
                }});
            """)

            if office_found:
                return True
            logger.error(f'Office not found: {office_name}')
            return False
        except Exception as e:
            logger.error(f'Error selecting office: {e}')
            return False

    def click_registry_type_selector(self):
        try:
            selector_xpath = (
                '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content'
                '/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div'
                '/div[1]/span/nz-card[2]/div/div/div[1]/div/div/app-select/div'
                '/nz-form-item/nz-form-control/div/div/nz-select/nz-select-top-control/nz-select-item'
            )
            selector = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, selector_xpath))
            )
            selector.click()
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f'Error clicking registry type selector: {e}')
            return False

    def select_vehicular_property(self):
        try:
            options_xpath = '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport'
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, options_xpath))
            )
            found = self.driver.execute_script("""
                const container = document.evaluate(
                    '/html/body/div/div/div/nz-option-container/div/cdk-virtual-scroll-viewport',
                    document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
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
            if found:
                time.sleep(1)
                return True
            logger.error('Propiedad Vehicular option not found')
            return False
        except Exception as e:
            logger.error(f'Error selecting vehicular property: {e}')
            return False

    def fill_plate_number(self, plate):
        try:
            plate_input_xpath = (
                '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content'
                '/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div'
                '/div[1]/span/nz-card[3]/div/form/div/div[2]/nz-form-item'
                '/nz-form-control/div/div/input'
            )
            plate_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, plate_input_xpath))
            )
            plate_input.clear()
            for char in plate:
                plate_input.send_keys(char)
                time.sleep(0.05)
            return True
        except Exception as e:
            logger.error(f'Error filling plate: {e}')
            return False

    def click_search_button(self):
        try:
            search_xpath = (
                '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content'
                '/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div'
                '/div[1]/span/nz-card[3]/div/form/div/div[5]/button'
            )
            search_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, search_xpath))
            )
            search_button.click()
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f'Error clicking search button: {e}')
            return False

    def click_table_button(self):
        try:
            table_button_xpath = (
                '/html/body/app-root/app-main/nz-layout/nz-layout/nz-content'
                '/app-partidas-base-grafica-registral/div/div[2]/div/div/nz-spin/div'
                '/div[1]/span[2]/nz-card/div/div[5]/div/nz-table/nz-spin/div/div'
                '/nz-table-inner-scroll/div[2]/table/tbody/tr[2]/td[7]/app-button/div/div/button'
            )
            table_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, table_button_xpath))
            )
            table_button.click()
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f'Error clicking table button: {e}')
            return False

    def iterate_modal_table(self, plate_id, plate_number):
        try:
            tbody_xpath = (
                '/html/body/div/div[3]/div[2]/div/div[2]/div/div/div[2]/div/nz-table'
                '/nz-spin/div/div/nz-table-inner-default/div/table/tbody'
            )
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, tbody_xpath))
            )

            rows = self.driver.find_elements(By.XPATH, f'{tbody_xpath}/tr')
            total_rows = len(rows)
            logger.info(f'Modal table rows: {total_rows}')

            all_data = []
            for index in range(total_rows):
                try:
                    rows = self.driver.find_elements(By.XPATH, f'{tbody_xpath}/tr')
                    clickable_xpath = f'{tbody_xpath}/tr[{index + 1}]/td/div[1]/span'

                    clickable = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, clickable_xpath))
                    )
                    row_text = clickable.text
                    clickable.click()
                    time.sleep(1)

                    modal_table_xpath = (
                        '/html/body/div/div[5]/div/nz-modal-confirm-container'
                        '/div/div/div/div/div[1]/div/div/table'
                    )
                    modal_data = {}
                    try:
                        modal_table = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, modal_table_xpath))
                        )
                        for modal_row in modal_table.find_elements(By.TAG_NAME, 'tr'):
                            cells = modal_row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) >= 2:
                                modal_data[cells[0].text.strip()] = cells[1].text.strip()
                            elif len(cells) == 1:
                                modal_data[cells[0].text.strip()] = ''
                    except Exception as e:
                        logger.warning(f'Could not read modal table for row {index + 1}: {e}')

                    all_data.append({
                        'row_index': index + 1,
                        'row_text': row_text,
                        'modal_data': modal_data,
                    })

                    close_xpath = (
                        '/html/body/div/div[5]/div/nz-modal-confirm-container'
                        '/div/div/div/div/div[2]/button'
                    )
                    try:
                        close_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, close_xpath))
                        )
                        close_btn.click()
                    except Exception as e:
                        logger.warning(f'Could not close modal for row {index + 1}: {e}')

                except Exception as e:
                    logger.warning(f'Error on row {index + 1}: {e}')
                    continue

            logger.info(f'Rows processed: {len(all_data)}/{total_rows}')


            return self.send_data_to_api(plate_id, plate_number, all_data)

        except Exception as e:
            logger.error(f'Error iterating modal table: {e}')
            return False

    # ------------------------------------------------------------------ #
    #  API                                                                 #
    # ------------------------------------------------------------------ #

    def get_max_version(self, plate_number):
        try:
            resp = requests.get(
                f'http://54.204.68.114:3000/sprl-sunarp/plate/{plate_number}/max-version',
                headers={'accept': '*/*'},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get('maxVersion', 0) + 1
        except Exception:
            return 1

    def send_data_to_api(self, plate_id, plate_number, all_data):
        try:
            current_version = self.get_max_version(plate_number)

            # Create/update master plate record
            requests.post(
                'http://54.204.68.114:3000/license-plate-master',
                json={'plateNumber': plate_number},
                headers={'accept': '*/*', 'Content-Type': 'application/json'},
                timeout=10,
            ).raise_for_status()

            success_count = 0
            for entry in all_data:
                modal_data = entry.get('modal_data', {})
                payload = {
                    'version': current_version,
                    'registrationDate': None,
                    'presentationDate': None,
                    'category': None,
                    'actType': None,
                    'naturalParticipants': None,
                    'legalParticipants': None,
                    'notes': entry.get('row_text', ''),
                    'createdBy': 1,
                    'plateNumber': plate_number,
                }
                for key, value in modal_data.items():
                    k = key.lower()
                    if 'inscripción' in k:
                        payload['registrationDate'] = self.format_date_to_iso(value)
                    elif 'presentación' in k:
                        payload['presentationDate'] = self.format_date_to_iso(value)
                    elif 'rubro' in k:
                        payload['category'] = value
                    elif 'acto' in k:
                        payload['actType'] = value
                    elif 'participantes naturales' in k:
                        payload['naturalParticipants'] = value
                    elif 'participantes juridicos' in k:
                        payload['legalParticipants'] = value

                try:
                    requests.post(
                        'http://54.204.68.114:3000/sprl-sunarp',
                        json=payload,
                        headers={'accept': '*/*', 'Content-Type': 'application/json'},
                        timeout=10,
                    ).raise_for_status()
                    success_count += 1
                except Exception as e:
                    logger.error(f'Error sending row {entry.get("row_index")}: {e}')

            # Mark plate as loaded
            requests.patch(
                f'http://54.204.68.114:3000/pending-car-plates/{plate_id}/mark-loaded/A',
                headers={'accept': '*/*'},
                timeout=10,
            ).raise_for_status()
            logger.info(f'Plate {plate_id} marked as loaded — {success_count}/{len(all_data)} rows sent')
            return success_count > 0

        except Exception as e:
            logger.error(f'Error sending data to API: {e}')
            return False

    def process_plate(self, office_name, plate_number, plate_id):
        try:
            logger.info(f'Processing plate={plate_number} office={office_name}')
            if not self.select_office(office_name):
                return False
            if not self.click_registry_type_selector():
                return False
            if not self.select_vehicular_property():
                return False
            if not self.fill_plate_number(plate_number):
                return False
            if not self.click_search_button():
                return False
            if not self.click_table_button():
                return False
            if not self.iterate_modal_table(plate_id, plate_number):
                return False
            return True
        except Exception as e:
            logger.error(f'Error processing plate {plate_number}: {e}')
            return False

    def cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
            except (OSError, Exception) as e:
                if not (isinstance(e, OSError) and hasattr(e, 'winerror') and e.winerror == 6):
                    logger.error(f'Error closing browser: {e}')
            finally:
                self.driver = None
        if self._virtual_display:
            try:
                self._virtual_display.stop()
            except Exception:
                pass
            self._virtual_display = None


# ------------------------------------------------------------------ #
#  API helper                                                          #
# ------------------------------------------------------------------ #

def get_pending_plate():
    try:
        resp = requests.get(
            'http://54.204.68.114:3000/pending-car-plates/unloaded/A/first',
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


def main():
    logger.info('=' * 60)
    logger.info('SUNARP SPRL Scraper — production loop')
    logger.info('=' * 60)

    scraper = SunarpScraper()
    needs_login = True

    try:
        while True:
            try:
                if needs_login:
                    logger.info('Logging in to SUNARP...')
                    if not scraper.login(headless=True):
                        logger.error('Login failed — retrying in 5s...')
                        scraper.cleanup()
                        scraper = SunarpScraper()
                        time.sleep(5)
                        continue
                    needs_login = False
                else:
                    scraper.reset_page()

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

                office_name = get_office_by_plate(plate_number)
                if office_name is False:
                    logger.warning(f'No office found for plate {plate_number} — skipping')
                    continue

                success = scraper.process_plate(office_name, plate_number, plate_id)
                if not success:
                    logger.warning('Plate processing failed — re-logging in...')
                    needs_login = True
                    scraper.cleanup()
                    scraper = SunarpScraper()

                time.sleep(0.5)

            except KeyboardInterrupt:
                logger.info('Stopped by user')
                break
            except Exception as e:
                logger.error(f'Unexpected loop error: {e}')
                needs_login = True
                scraper.cleanup()
                scraper = SunarpScraper()
                time.sleep(2)
    finally:
        scraper.cleanup()


if __name__ == '__main__':
    main()
