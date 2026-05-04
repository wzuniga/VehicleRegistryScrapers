"""Scraper de Consulta Vehicular SUNARP — versión headless-first para servidor Linux.

Autónomo: no depende de b_consulta_vehicular_scraper.py.
"""

import argparse
import base64
import logging
import os
import platform
import random
import time
import warnings

import requests
import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
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

# Patch uc.Chrome.__del__ to silently ignore the WinError 6 on Windows
# that occurs when the destructor runs after cleanup() already closed the driver.
def _patched_del(self):
    try:
        self.quit()
    except Exception:
        pass

uc.Chrome.__del__ = _patched_del

# Script CDP para evadir detección de Cloudflare en Linux headless.
CLOUDFLARE_BYPASS_CDP_SCRIPT = '''
    // --- webdriver ---
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // --- Plataforma Windows ---
    Object.defineProperty(navigator, 'platform',    { get: () => 'Win32' });
    Object.defineProperty(navigator, 'vendor',      { get: () => 'Google Inc.' });
    Object.defineProperty(navigator, 'userAgent',   { get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' });
    Object.defineProperty(navigator, 'appVersion',  { get: () => '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' });

    // --- Hardware ---
    Object.defineProperty(navigator, 'languages',          { get: () => ['es-ES', 'es', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory',        { get: () => 8 });
    Object.defineProperty(navigator, 'maxTouchPoints',      { get: () => 0 });

    // --- Conexión de red realista ---
    Object.defineProperty(navigator, 'connection', {
        get: () => ({ effectiveType: '4g', rtt: 50, downlink: 10, saveData: false })
    });

    // --- Screen: crítico — headless reporta 0 o valores extraños ---
    Object.defineProperty(screen, 'width',       { get: () => 1366 });
    Object.defineProperty(screen, 'height',      { get: () => 768 });
    Object.defineProperty(screen, 'availWidth',  { get: () => 1366 });
    Object.defineProperty(screen, 'availHeight', { get: () => 728 });
    Object.defineProperty(screen, 'colorDepth',  { get: () => 24 });
    Object.defineProperty(screen, 'pixelDepth',  { get: () => 24 });

    // --- Window dimensions: outerWidth/Height = 0 en --headless=new ---
    Object.defineProperty(window, 'outerWidth',  { get: () => 1366 });
    Object.defineProperty(window, 'outerHeight', { get: () => 900 });
    Object.defineProperty(window, 'innerWidth',  { get: () => 1366 });
    Object.defineProperty(window, 'innerHeight', { get: () => 768 });
    Object.defineProperty(window, 'devicePixelRatio', { get: () => 1 });

    // --- document.hasFocus() = false en headless ---
    document.hasFocus = () => true;

    // --- Permissions API ---
    if (navigator.permissions && navigator.permissions.query) {
        const origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = (params) => {
            if (params.name === 'notifications') {
                return Promise.resolve({ state: 'prompt', onchange: null });
            }
            return origQuery(params);
        };
    }

    // --- Notification permission ---
    try {
        Object.defineProperty(Notification, 'permission', { get: () => 'default' });
    } catch(e) {}

    // --- Plugins realistas ---
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

    // --- WebGL: ocultar Mesa/llvmpipe ---
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

    // --- window.chrome completo ---
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


class ConsultaVehicularScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://consultavehicular.sunarp.gob.pe/'
        self.captcha_id = None

    def setup_driver(self, headless=False):
        logger.info('Configuring Chrome driver...')

        self._virtual_display = None

        # En Linux: usar Xvfb (virtual display) en vez de --headless=new.
        # Xvfb hace que Chrome crea que tiene un display real → propiedades
        # de screen/window correctas → Cloudflare Turnstile auto-verifica.
        if headless and platform.system() == 'Linux':
            try:
                from pyvirtualdisplay import Display
                self._virtual_display = Display(visible=False, size=(1366, 768))
                self._virtual_display.start()
                logger.info('Xvfb virtual display started (1366x768)')
                headless = False  # Chrome corre sin --headless=new
            except ImportError:
                logger.warning('pyvirtualdisplay not installed, falling back to --headless=new')
                logger.warning('Install with: pip install pyvirtualdisplay')
            except Exception as e:
                logger.warning(f'Could not start virtual display: {e}, falling back to --headless=new')

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
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/147.0.0.0 Safari/537.36'
        )

        if headless:
            options.add_argument('--headless=new')
            logger.info('Headless mode enabled (--headless=new)')
        else:
            logger.info('Headless mode disabled (real or virtual display)')

        options.page_load_strategy = 'eager'
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
        }
        options.add_experimental_option('prefs', prefs)

        try:
            self.driver = uc.Chrome(options=options, version_main=147)
            logger.info('Chrome driver ready')
            try:
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': CLOUDFLARE_BYPASS_CDP_SCRIPT
                })
                logger.info('Anti-detection CDP scripts injected')
            except Exception as cdp_error:
                logger.warning(f'Could not inject CDP scripts: {cdp_error}')
            return True
        except Exception as e:
            logger.error(f'Error configuring Chrome driver: {e}')
            return False

    def navigate_to_page(self):
        try:
            logger.info(f'Navigating to {self.url}...')
            self.driver.get(self.url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-root'))
            )
            logger.info('Page loaded')
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f'Error navigating to page: {e}')
            return False

    def fill_plate_number(self, plate):
        try:
            logger.info(f'Filling plate number: {plate}')
            plate_input_xpath = (
                '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content'
                '/div/nz-card/div/app-form-datos-consulta/div/form/fieldset/nz-form-item[1]'
                '/nz-form-control/div/div/nz-input-group/input'
            )
            plate_input = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, plate_input_xpath))
            )
            plate_input.clear()
            for char in plate:
                plate_input.send_keys(char)
            logger.info('Plate number entered')
            return True
        except Exception as e:
            logger.error(f'Error filling plate number: {e}')
            return False

    def click_search_button(self):
        try:
            logger.info('Clicking search button...')
            button_xpath = (
                '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content'
                '/div/nz-card/div/app-form-datos-consulta/div/form/fieldset/nz-form-item[3]'
                '/nz-form-control/div/div/div/button'
            )
            button = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, button_xpath))
            )
            button.click()
            logger.info('Search button clicked')
            return True
        except Exception as e:
            logger.error(f'Error clicking search button: {e}')
            return False

    def get_result_image_base64(self):
        try:
            logger.info('Getting result image as base64...')
            result_img_xpath = (
                '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content'
                '/div/nz-card/div/app-form-datos-consulta/div/img'
            )
            result_img = WebDriverWait(self.driver, 12).until(
                EC.presence_of_element_located((By.XPATH, result_img_xpath))
            )
            src_attribute = result_img.get_attribute('src')
            if not src_attribute or not src_attribute.startswith('data:image'):
                logger.error('src does not contain a base64 image')
                return None
            if ';base64,' in src_attribute:
                image_base64 = src_attribute.split(';base64,')[1]
                logger.info(f'Base64 extracted (len={len(image_base64)})')
                return image_base64
            logger.error('base64 marker not found in src')
            return None
        except Exception as e:
            logger.error(f'Error getting result image: {e}')
            return None

    def send_image_to_api(self, image_base64, plate_number, plate_id):
        try:
            logger.info('Sending image to API...')
            api_url = 'http://54.204.68.114:3000/vehicles'
            payload = {'plateNumber': plate_number, 'imageBase64': image_base64}
            headers = {'accept': '*/*', 'Content-Type': 'application/json'}
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            if response.status_code in [200, 201]:
                if plate_id is not None and str(plate_id).strip() != '':
                    logger.info(f'Marking plate {plate_id} as loaded...')
                    mark_url = f'http://54.204.68.114:3000/pending-car-plates/{plate_id}/mark-loaded/B'
                    requests.patch(mark_url, headers={'accept': '*/*'}, timeout=10).raise_for_status()
                    logger.info(f'Plate {plate_id} marked as loaded')
                else:
                    logger.info('Manual run without plate_id: skipping mark-loaded')
                return True
            else:
                logger.error(f'API error. Status: {response.status_code}, Response: {response.text}')
                return False
        except Exception as e:
            logger.error(f'Error sending image to API: {e}')
            return False

    def take_screenshot(self, filename='screenshot.png'):
        try:
            os.makedirs('consulta_vehicular', exist_ok=True)
            path = os.path.join('consulta_vehicular', filename)
            self.driver.save_screenshot(path)
            logger.info(f'Screenshot saved: {path}')
            return True
        except Exception as e:
            logger.error(f'Error taking screenshot: {e}')
            return False

    def cleanup(self):
        if self.driver:
            logger.info('Closing browser...')
            try:
                self.driver.quit()
                logger.info('Browser closed')
            except (OSError, Exception) as e:
                if isinstance(e, OSError) and hasattr(e, 'winerror') and e.winerror == 6:
                    logger.debug('Invalid handle during cleanup (expected on Windows)')
                else:
                    logger.error(f'Error closing browser: {e}')
            finally:
                self.driver = None
        if getattr(self, '_virtual_display', None):
            try:
                self._virtual_display.stop()
                logger.info('Virtual display stopped')
            except Exception:
                pass
            self._virtual_display = None

    def run(self, plate_number=None, plate_id=None, headless=False):
        try:
            if not plate_number:
                logger.error('Missing required parameter: plate_number')
                return False

            logger.info(f'Parameters received:')
            logger.info(f'   Plate: {plate_number}')
            logger.info(f'   Headless: {headless}')

            if not self.setup_driver(headless=headless):
                return False
            if not self.navigate_to_page():
                return False
            if not self.fill_plate_number(plate_number):
                return False

            time.sleep(7)

            if not self.click_search_button():
                return False

            image_base64 = self.get_result_image_base64()
            if not image_base64:
                logger.error('Could not get base64 image')
                return False

            if not self.send_image_to_api(image_base64, plate_number, plate_id):
                logger.warning('Could not send image to API')
                return False

            logger.info('Process completed successfully')
            return True
        except Exception as e:
            logger.error(f'Error in run: {e}')
            return False
        finally:
            self.cleanup()


class TestConsultaVehicularScraper(ConsultaVehicularScraper):
    """Optimized scraper: fast Turnstile handling, CapSolver fallback."""

    def __init__(self):
        super().__init__()

    # ------------------------------------------------------------------ #
    #  Cloudflare Turnstile                                                #
    # ------------------------------------------------------------------ #

    def _is_turnstile_verified(self):
        try:
            token = self.driver.execute_script(
                "const el = document.querySelector('[name=\"cf-turnstile-response\"]');"
                "return el ? el.value : null;"
            )
            return bool(token and token.strip())
        except Exception:
            return False

    def _get_turnstile_sitekey(self):
        try:
            return self.driver.execute_script("""
                const el = document.querySelector('[data-sitekey]');
                if (el) return el.getAttribute('data-sitekey');
                for (const f of document.querySelectorAll('iframe')) {
                    const m = (f.src || '').match(/[?&]k=([^&]+)/);
                    if (m) return m[1];
                }
                return null;
            """)
        except Exception:
            return None

    def _solve_turnstile_with_capsolver(self, sitekey):
        api_key = os.environ.get('CAPSOLVER_API_KEY', '').strip()
        if not api_key:
            logger.warning('CAPSOLVER_API_KEY not set — skipping captcha solver')
            return None
        logger.info(f'Solving Turnstile via CapSolver (sitekey={sitekey[:20]}...)')
        try:
            resp = requests.post(
                'https://api.capsolver.com/createTask',
                json={'clientKey': api_key, 'task': {
                    'type': 'AntiTurnstileTaskProxyLess',
                    'websiteURL': self.url,
                    'websiteKey': sitekey,
                }},
                timeout=30,
            ).json()
            if resp.get('errorId'):
                logger.error(f'CapSolver error: {resp.get("errorDescription")}')
                return None
            task_id = resp['taskId']
            for _ in range(30):
                time.sleep(3)
                result = requests.post(
                    'https://api.capsolver.com/getTaskResult',
                    json={'clientKey': api_key, 'taskId': task_id},
                    timeout=30,
                ).json()
                if result.get('status') == 'ready':
                    token = result['solution']['token']
                    logger.info(f'CapSolver token received (len={len(token)})')
                    return token
                if result.get('errorId'):
                    logger.error(f'CapSolver task failed: {result.get("errorDescription")}')
                    return None
            logger.error('CapSolver timed out')
            return None
        except Exception as e:
            logger.error(f'CapSolver error: {e}')
            return None

    def _inject_turnstile_token(self, token):
        try:
            self.driver.execute_script("""
                document.querySelectorAll('[name="cf-turnstile-response"]').forEach(el => {
                    el.value = arguments[0];
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('input',  { bubbles: true }));
                });
            """, token)
            logger.info('Turnstile token injected')
            return True
        except Exception as e:
            logger.warning(f'Token injection error: {e}')
            return False

    def _solve_turnstile(self):
        """Poll for auto-verification every 500 ms (fast on Windows/residential IPs).
        Falls back to CapSolver if CAPSOLVER_API_KEY is set."""
        logger.info('Waiting for Turnstile auto-verification...')
        for _ in range(20):          # 10 s max, 500 ms intervals
            if self._is_turnstile_verified():
                logger.info('Turnstile auto-verified')
                return True
            time.sleep(0.5)

        sitekey = self._get_turnstile_sitekey()
        if not sitekey:
            logger.warning('Turnstile sitekey not found — proceeding anyway')
            return False
        logger.info(f'Sitekey: {sitekey}')
        token = self._solve_turnstile_with_capsolver(sitekey)
        if not token:
            return False
        return self._inject_turnstile_token(token)

    # ------------------------------------------------------------------ #
    #  Cloudflare page challenge                                           #
    # ------------------------------------------------------------------ #

    def _is_challenge_present(self):
        try:
            src = (self.driver.page_source or '').lower()
            title = (self.driver.title or '').lower()
        except Exception:
            return False
        markers = ['checking your browser', 'just a moment', 'cf-chl',
                   'challenge-platform', 'cf-browser-verification', 'verifying you are human']
        return any(m in src or m in title for m in markers)

    def wait_for_challenge_clear(self, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            if not self._is_challenge_present():
                if self.driver.find_elements(By.TAG_NAME, 'app-root'):
                    return True
            time.sleep(0.5)
        return False

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def navigate_to_page(self):
        try:
            logger.info(f'Navigating to {self.url}...')
            self.driver.get(self.url)

            WebDriverWait(self.driver, 25).until(
                lambda d: d.execute_script('return document.readyState') in ('interactive', 'complete')
            )

            if self._is_challenge_present():
                logger.info('Cloudflare challenge detected — waiting...')
                if not self.wait_for_challenge_clear(timeout=20):
                    logger.warning('Challenge did not clear; continuing anyway')

            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-root'))
            )
            logger.info('Page ready')
            return True
        except Exception as e:
            logger.error(f'Error navigating: {e}')
            self.take_screenshot(f'nav_error_{int(time.time())}.png')
            return False

    # ------------------------------------------------------------------ #
    #  Search                                                              #
    # ------------------------------------------------------------------ #

    def click_search_button(self):
        button_xpath = (
            '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content'
            '/div/nz-card/div/app-form-datos-consulta/div/form/fieldset/nz-form-item[3]'
            '/nz-form-control/div/div/div/button'
        )
        for attempt in range(1, 4):
            try:
                logger.info(f'Clicking search button (attempt {attempt}/3)...')
                button = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, button_xpath))
                )
                button.click()
            except Exception as click_error:
                logger.warning(f'Normal click failed, trying JS fallback: {click_error}')
                try:
                    button = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, button_xpath))
                    )
                    self.driver.execute_script('arguments[0].click();', button)
                except Exception as js_error:
                    logger.error(f'JS click fallback failed: {js_error}')
                    return False

            time.sleep(1)
            if self._is_captcha_modal_present():
                logger.warning(f'Captcha modal on attempt {attempt}')
                self.take_screenshot(f'captcha_modal_{attempt}_{int(time.time())}.png')
                if not self._dismiss_captcha_modal():
                    return False
                if attempt < 3:
                    time.sleep(1)
                    continue
                return False

            return True
        return False

    def _is_captcha_modal_present(self):
        try:
            nodes = self.driver.find_elements(By.XPATH, '/html/body/div/div')
            if not nodes:
                return False
            text = (nodes[0].text or '').lower()
            return 'captcha no resuelto' in text or 'por favor resuelva el captcha' in text
        except Exception:
            return False

    def _dismiss_captcha_modal(self):
        for xpath in [
            "//div[@role='dialog']//button[normalize-space()='OK' or .//span[normalize-space()='OK']]",
            '/html/body/div/div//button',
        ]:
            try:
                btn = WebDriverWait(self.driver, 4).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                btn.click()
                time.sleep(0.5)
                return True
            except Exception:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    self.driver.execute_script('arguments[0].click();', btn)
                    time.sleep(0.5)
                    return True
                except Exception:
                    continue
        return False

    # ------------------------------------------------------------------ #
    #  Result image                                                        #
    # ------------------------------------------------------------------ #

    def _extract_base64_from_src(self, src):
        if not src:
            return None
        if src.startswith('data:image') and ';base64,' in src:
            return src.split(';base64,', 1)[1]
        if src.startswith('http://') or src.startswith('https://'):
            try:
                r = requests.get(src, timeout=20)
                r.raise_for_status()
                return base64.b64encode(r.content).decode('utf-8')
            except Exception as e:
                logger.warning(f'Could not fetch image: {e}')
        return None

    def get_result_image_base64(self):
        logger.info('Extracting result image...')
        xpath = (
            '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content'
            '/div/nz-card/div/app-form-datos-consulta/div/img'
        )
        for attempt in range(1, 7):
            try:
                img = WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                b64 = self._extract_base64_from_src(img.get_attribute('src'))
                if b64:
                    logger.info(f'Image extracted (len={len(b64)})')
                    return b64
                # JS fallback
                b64 = self._extract_base64_from_src(self.driver.execute_script(
                    "const i=document.querySelector('app-form-datos-consulta div img');"
                    "return i?i.getAttribute('src'):null;"
                ))
                if b64:
                    logger.info(f'Image extracted via JS (len={len(b64)})')
                    return b64
                logger.warning('Image present but src not ready; retrying...')
            except TimeoutException:
                logger.warning(f'Timeout on attempt {attempt}')
            except Exception as e:
                logger.warning(f'Error on attempt {attempt}: {e}')
            time.sleep(1)

        logger.error('Could not extract image after all retries')
        return None

    # ------------------------------------------------------------------ #
    #  Optimized run                                                       #
    # ------------------------------------------------------------------ #

    def run(self, plate_number=None, plate_id=None, headless=False):
        try:
            if not plate_number:
                logger.error('Missing plate_number')
                return False

            logger.info(f'Plate: {plate_number} | Headless: {headless}')

            if not self.setup_driver(headless=headless):
                return False
            if not self.navigate_to_page():
                return False
            if not self.fill_plate_number(plate_number):
                return False

            # Solve Turnstile while the page is idle (no extra sleep needed)
            self._solve_turnstile()

            if not self.click_search_button():
                return False

            image_base64 = self.get_result_image_base64()
            if not image_base64:
                return False

            if not self.send_image_to_api(image_base64, plate_number, plate_id):
                return False

            logger.info('Done')
            return True
        except Exception as e:
            logger.error(f'run() error: {e}')
            return False
        finally:
            self.cleanup()


def get_pending_plate():
    """Fetch the next unprocessed plate from the API."""
    try:
        resp = requests.get(
            'http://54.204.68.114:3000/pending-car-plates/unloaded/B/first',
            headers={'accept': '*/*'},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f'Pending plate: {data.get("plate")} (id={data.get("id")})')
        return data
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None  # no pending plates
        logger.error(f'Error fetching pending plate: {e}')
        return None
    except Exception as e:
        logger.error(f'Error fetching pending plate: {e}')
        return None


def process_plate(plate_number, plate_id, headless=True):
    """Process one plate, retrying once on failure."""
    for attempt in range(1, 3):
        scraper = TestConsultaVehicularScraper()
        try:
            success = scraper.run(
                plate_number=plate_number,
                plate_id=plate_id,
                headless=headless,
            )
            if success:
                return True
            logger.warning(f'Plate {plate_number} failed on attempt {attempt}/2')
        except Exception as e:
            logger.error(f'Unexpected error on attempt {attempt}: {e}')
        finally:
            scraper.cleanup()

        if attempt < 2:
            logger.info('Waiting 2s before retry...')
            time.sleep(2)

    logger.error(f'Plate {plate_number} failed after 2 attempts — skipping')
    return False


def run_test(plate_number, plate_id=None, headless=True):
    scraper = TestConsultaVehicularScraper()
    return scraper.run(plate_number=plate_number, plate_id=plate_id, headless=headless)


def main():
    """Main entry point.

    Default: production loop fetching plates from the API.
    Override with --plate for manual single-plate testing.
    """
    import sys

    # Manual single-plate mode: python script.py --plate BNP276 [--no-headless]
    if '--plate' in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument('--plate', required=True)
        parser.add_argument('--plate-id', default=None)
        parser.add_argument('--headless', dest='headless', action='store_true', default=True)
        parser.add_argument('--no-headless', dest='headless', action='store_false')
        args = parser.parse_args()
        plate = args.plate.strip().upper()
        logger.info('=' * 60)
        logger.info(f'Manual mode — plate={plate}, headless={args.headless}')
        logger.info('=' * 60)
        success = run_test(plate_number=plate, plate_id=args.plate_id, headless=args.headless)
        return 0 if success else 1

    # Production loop
    logger.info('=' * 60)
    logger.info('Consulta Vehicular SUNARP — production loop')
    logger.info('=' * 60)

    while True:
        try:
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
            process_plate(plate_number, plate_id, headless=True)

            time.sleep(1)

        except KeyboardInterrupt:
            logger.info('Stopped by user')
            break
        except Exception as e:
            logger.error(f'Unexpected loop error: {e}')
            time.sleep(5)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
