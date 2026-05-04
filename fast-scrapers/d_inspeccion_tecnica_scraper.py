"""Inspección Técnica Vehicular Scraper — standalone with full anti-bot measures.

Flow: initialize browser once → get captcha image → solve with DeathByCaptcha →
      grab session cookie → query CITV API for each plate (reusing captcha+cookie) →
      reinitialize when captcha/cookie expire.
"""

import logging
import os
import platform
import time
import warnings

import deathbycaptcha
import requests
import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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


class InspeccionTecnicaScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://rec.mtc.gob.pe/Citv/ArConsultaCitv'
        self._virtual_display = None

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

    def navigate_to_page(self):
        try:
            self.driver.get(self.url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f'Error navigating: {e}')
            return False

    def get_captcha_image(self):
        try:
            captcha_img = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/img'))
            )
            os.makedirs('inspeccion_tecnica', exist_ok=True)
            captcha_path = os.path.join('inspeccion_tecnica', 'captcha.png')
            captcha_img.screenshot(captcha_path)
            return True
        except Exception as e:
            logger.error(f'Error getting captcha image: {e}')
            return False

    def parse_captcha_with_dbc(self, image_path='inspeccion_tecnica/captcha.png'):
        dbc_username = os.getenv('DBC_USERNAME')
        dbc_password = os.getenv('DBC_PASSWORD')
        if not dbc_username or not dbc_password:
            logger.error('DBC_USERNAME or DBC_PASSWORD not set in .env')
            return None
        try:
            client = deathbycaptcha.SocketClient(dbc_username, dbc_password)
            captcha = client.decode(image_path, type=0, verbose=0)
            if captcha:
                result = captcha.get('text', '').strip().upper()
                logger.info(f'Captcha solved: {result}')
                return result
            logger.error('Could not solve captcha')
            return None
        except Exception as e:
            logger.error(f'DBC error: {e}')
            return None

    def get_session_cookie(self):
        try:
            for cookie in self.driver.get_cookies():
                if cookie['name'] == 'ASP.NET_SessionId':
                    return cookie['value']
            logger.error('ASP.NET_SessionId cookie not found')
            return None
        except Exception as e:
            logger.error(f'Error getting session cookie: {e}')
            return None

    def query_citv_data(self, plate_number, captcha_text, session_cookie):
        try:
            url = (
                f'https://rec.mtc.gob.pe/CITV/JrCITVConsultarFiltro'
                f'?pArrParametros=1%7C{plate_number}%7C%7C{captcha_text}'
            )
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.6',
                'content-type': 'application/json',
                'referer': 'https://rec.mtc.gob.pe/Citv/ArConsultaCitv',
                'user-agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
                ),
                'Cookie': f'ASP.NET_SessionId={session_cookie}',
            }
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('orCodigo') == '-2':
                        logger.warning('Invalid captcha (orCodigo=-2) — reinitialize required')
                        return None
                    return data
                except Exception:
                    return {'raw_response': response.text}
            else:
                logger.warning(f'CITV query failed ({response.status_code}) — reinitialize required')
                return None
        except Exception as e:
            logger.error(f'Error querying CITV: {e}')
            return None

    def send_to_api(self, plate_number, citv_data, plate_id):
        try:
            response = requests.post(
                'http://54.204.68.114:3000/inspeccion-vehicular',
                json={'plateNumber': plate_number, 'data': citv_data},
                headers={'accept': '*/*', 'Content-Type': 'application/json'},
                timeout=60,
            )
            if response.status_code in [200, 201]:
                mark_url = f'http://54.204.68.114:3000/pending-car-plates/{plate_id}/mark-loaded/D'
                requests.patch(mark_url, headers={'accept': '*/*'}, timeout=10).raise_for_status()
                logger.info(f'Plate {plate_id} marked as loaded')
                return True
            else:
                logger.error(f'API error: {response.status_code} — {response.text}')
                return False
        except Exception as e:
            logger.error(f'Error sending to API: {e}')
            return False

    def initialize(self, headless=False):
        """Set up browser, solve captcha, grab session cookie. Returns (ok, captcha_text, session_cookie)."""
        try:
            if not self.setup_driver(headless=headless):
                return False, None, None
            if not self.navigate_to_page():
                return False, None, None
            if not self.get_captcha_image():
                return False, None, None
            captcha_text = self.parse_captcha_with_dbc()
            if not captcha_text:
                return False, None, None
            session_cookie = self.get_session_cookie()
            if not session_cookie:
                return False, None, None
            logger.info('Initialized — captcha and session cookie ready')
            return True, captcha_text, session_cookie
        except Exception as e:
            logger.error(f'Initialization error: {e}')
            return False, None, None

    def process_plate(self, plate_number, plate_id, captcha_text, session_cookie):
        """Query CITV and send result to API using existing captcha+cookie."""
        try:
            citv_data = self.query_citv_data(plate_number, captcha_text, session_cookie)
            if not citv_data:
                return False
            return self.send_to_api(plate_number, citv_data, plate_id)
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


def get_pending_plate():
    try:
        resp = requests.get(
            'http://54.204.68.114:3000/pending-car-plates/unloaded/D/first',
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
    logger.info('Inspeccion Tecnica Vehicular — production loop')
    logger.info('=' * 60)

    MAX_REINITS = 10
    scraper = InspeccionTecnicaScraper()
    captcha_text = None
    session_cookie = None
    needs_init = True
    reinit_count = 0

    try:
        while True:
            try:
                if needs_init:
                    if reinit_count >= MAX_REINITS:
                        logger.error(f'Reached max reinitializations ({MAX_REINITS}) — stopping')
                        break
                    reinit_count += 1
                    logger.info(f'Initializing ({reinit_count}/{MAX_REINITS})...')
                    ok, captcha_text, session_cookie = scraper.initialize(headless=True)
                    if not ok:
                        logger.error('Initialization failed — retrying in 5s...')
                        time.sleep(5)
                        continue
                    needs_init = False

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

                logger.info(f'Processing plate={plate_number} id={plate_id}')
                success = scraper.process_plate(plate_number, plate_id, captcha_text, session_cookie)

                if success:
                    reinit_count = 0
                else:
                    logger.warning('Plate failed — reinitializing...')
                    needs_init = True
                    scraper.cleanup()
                    scraper = InspeccionTecnicaScraper()

                time.sleep(0.5)

            except KeyboardInterrupt:
                logger.info('Stopped by user')
                break
            except Exception as e:
                logger.error(f'Unexpected loop error: {e}')
                needs_init = True
                scraper.cleanup()
                scraper = InspeccionTecnicaScraper()
                time.sleep(2)
    finally:
        scraper.cleanup()


if __name__ == '__main__':
    main()
