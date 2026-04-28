"""Scraper de Consulta Vehicular SUNARP — versión headless-first para servidor Linux.

Autónomo: no depende de b_consulta_vehicular_scraper.py.
"""

import argparse
import base64
import logging
import os
import time
import warnings

import requests
import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException
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

# Script CDP para evadir detección de Cloudflare en Linux headless.
# Falsifica navigator.platform, WebGL renderer, plugins y window.chrome
# para que el browser parezca un Chrome real en Windows.
CLOUDFLARE_BYPASS_CDP_SCRIPT = '''
    // Ocultar webdriver
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // Fingir plataforma Windows (crítico en Linux headless)
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
    Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
    Object.defineProperty(navigator, 'userAgent', {
        get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
    });
    Object.defineProperty(navigator, 'appVersion', {
        get: () => '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
    });

    // Idiomas y hardware
    Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // Plugins realistas (objetos, no números)
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
    const plugins = [
        makePlugin('PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format', [pdfMime]),
        makePlugin('Chrome PDF Viewer', 'internal-pdf-viewer', '', [pdfMime]),
        makePlugin('Chromium PDF Viewer', 'internal-pdf-viewer', '', [pdfMime]),
        makePlugin('Microsoft Edge PDF Viewer', 'internal-pdf-viewer', '', [pdfMime]),
        makePlugin('WebKit built-in PDF', 'internal-pdf-viewer', '', [pdfMime]),
    ];
    Object.defineProperty(navigator, 'plugins', {
        get: () => Object.assign(Object.create(PluginArray.prototype),
            plugins.reduce((a, p, i) => { a[i] = p; return a; }, { length: plugins.length }))
    });

    // Falsificar WebGL renderer (ocultar Mesa/llvmpipe del servidor Linux)
    const getParamHandler = {
        apply(target, ctx, args) {
            if (args[0] === 37445) return 'Google Inc. (NVIDIA)';
            if (args[0] === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)';
            return Reflect.apply(target, ctx, args);
        }
    };
    if (WebGLRenderingContext.prototype.getParameter)
        WebGLRenderingContext.prototype.getParameter = new Proxy(WebGLRenderingContext.prototype.getParameter, getParamHandler);
    if (typeof WebGL2RenderingContext !== 'undefined' && WebGL2RenderingContext.prototype.getParameter)
        WebGL2RenderingContext.prototype.getParameter = new Proxy(WebGL2RenderingContext.prototype.getParameter, getParamHandler);

    // Objeto window.chrome completo
    window.chrome = {
        app: {
            isInstalled: false,
            InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
            getDetails: function() { return null; },
            getIsInstalled: function() { return false; },
            runningState: function() { return 'cannot_run'; }
        },
        csi: function() {},
        loadTimes: function() { return {}; },
        runtime: {
            connect: function() {},
            sendMessage: function() {},
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
            logger.info('Headless mode enabled')
        else:
            logger.info('Headless mode disabled')

        options.page_load_strategy = 'normal'
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
            api_url = 'http://143.110.206.161:3000/vehicles'
            payload = {'plateNumber': plate_number, 'imageBase64': image_base64}
            headers = {'accept': '*/*', 'Content-Type': 'application/json'}
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            if response.status_code in [200, 201]:
                if plate_id is not None and str(plate_id).strip() != '':
                    logger.info(f'Marking plate {plate_id} as loaded...')
                    mark_url = f'http://143.110.206.161:3000/pending-car-plates/{plate_id}/mark-loaded/B'
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
    """Headless-oriented scraper with Cloudflare challenge handling."""

    def __init__(self, pre_click_delay_seconds=5.0):
        super().__init__()
        self.pre_click_delay_seconds = max(0.0, float(pre_click_delay_seconds))

    def _is_challenge_present(self):
        try:
            page_source = (self.driver.page_source or '').lower()
            title = (self.driver.title or '').lower()
        except Exception:
            return False

        markers = [
            'checking your browser',
            'just a moment',
            'cf-chl',
            'challenge-platform',
            'cf-browser-verification',
            'verifying you are human',
        ]
        return any(marker in page_source or marker in title for marker in markers)

    def wait_for_challenge_clear(self, timeout=45):
        end_time = time.time() + timeout
        while time.time() < end_time:
            if not self._is_challenge_present():
                if self.driver.find_elements(By.TAG_NAME, 'app-root'):
                    return True
            time.sleep(1)
        return False

    def navigate_to_page(self):
        try:
            logger.info(f'Navigating to {self.url}...')
            self.driver.get(self.url)

            WebDriverWait(self.driver, 25).until(
                lambda d: d.execute_script('return document.readyState') in ('interactive', 'complete')
            )

            if self._is_challenge_present():
                logger.info('Challenge detected. Waiting for page clearance...')
                if not self.wait_for_challenge_clear(timeout=60):
                    logger.warning('Challenge did not clear in expected time; continuing with best effort')

            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-root'))
            )

            logger.info('Page loaded and stabilized')
            return True
        except Exception as e:
            logger.error(f'Error navigating to page: {e}')
            self.take_screenshot(f'nav_error_{int(time.time())}.png')
            return False

    def click_search_button(self):
        button_xpath = (
            '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content'
            '/div/nz-card/div/app-form-datos-consulta/div/form/fieldset/nz-form-item[3]'
            '/nz-form-control/div/div/div/button'
        )

        if self.pre_click_delay_seconds > 0:
            logger.info(f'Waiting {self.pre_click_delay_seconds:.1f}s before clicking search...')
            time.sleep(self.pre_click_delay_seconds)

        for attempt in range(1, 4):
            try:
                if self._is_challenge_present():
                    logger.info('Challenge detected before click; waiting for clearance...')
                    self.wait_for_challenge_clear(timeout=2)

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
                    logger.error(f'JS click fallback also failed: {js_error}')
                    return False

            time.sleep(1.2)
            if self._is_captcha_modal_present():
                logger.warning('Captcha unresolved modal detected after click.')
                self.take_screenshot(f'captcha_modal_attempt_{attempt}_{int(time.time())}.png')

                if not self._dismiss_captcha_modal():
                    logger.error('Could not dismiss captcha modal.')
                    return False

                if attempt < 3:
                    logger.info('Retrying search click...')
                    time.sleep(2)
                    continue

                logger.error('Captcha modal persisted after retries.')
                return False

            return True

        return False

    def _is_captcha_modal_present(self):
        try:
            modal_nodes = self.driver.find_elements(By.XPATH, '/html/body/div/div')
            if not modal_nodes:
                return False
            modal_text = (modal_nodes[0].text or '').lower()
            markers = ['captcha no resuelto', 'por favor resuelva el captcha']
            return any(marker in modal_text for marker in markers)
        except Exception:
            return False

    def _dismiss_captcha_modal(self):
        ok_button_xpaths = [
            "//div[@role='dialog']//button[normalize-space()='OK' or .//span[normalize-space()='OK']]",
            '/html/body/div/div//button',
        ]
        for button_xpath in ok_button_xpaths:
            try:
                ok_button = WebDriverWait(self.driver, 4).until(
                    EC.element_to_be_clickable((By.XPATH, button_xpath))
                )
                ok_button.click()
                time.sleep(0.8)
                return True
            except Exception:
                try:
                    ok_button = self.driver.find_element(By.XPATH, button_xpath)
                    self.driver.execute_script('arguments[0].click();', ok_button)
                    time.sleep(0.8)
                    return True
                except Exception:
                    continue
        return False

    def _extract_base64_from_src(self, src_attribute):
        if not src_attribute:
            return None
        if src_attribute.startswith('data:image') and ';base64,' in src_attribute:
            return src_attribute.split(';base64,', 1)[1]
        if src_attribute.startswith('http://') or src_attribute.startswith('https://'):
            try:
                response = requests.get(src_attribute, timeout=20)
                response.raise_for_status()
                return base64.b64encode(response.content).decode('utf-8')
            except Exception as e:
                logger.warning(f'Could not fetch image url: {e}')
        return None

    def _save_test_image(self, image_base64, filename='resultado_test.png'):
        try:
            normalized = image_base64.strip()
            missing_padding = len(normalized) % 4
            if missing_padding:
                normalized += '=' * (4 - missing_padding)
            with open(filename, 'wb') as f:
                f.write(base64.b64decode(normalized))
            logger.info(f'Test image saved: {filename}')
            return True
        except Exception as e:
            logger.warning(f'Could not save test image {filename}: {e}')
            return False

    def get_result_image_base64(self):
        logger.info('Extracting result image as base64...')
        result_img_xpath = (
            '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content'
            '/div/nz-card/div/app-form-datos-consulta/div/img'
        )

        for attempt in range(1, 7):
            try:
                logger.info(f'Attempt {attempt}/6 to read result image')

                if self._is_challenge_present():
                    logger.info('Challenge detected while waiting for result; waiting for clearance...')
                    self.wait_for_challenge_clear(timeout=25)

                result_img = WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.XPATH, result_img_xpath))
                )

                src_attribute = result_img.get_attribute('src')
                image_base64 = self._extract_base64_from_src(src_attribute)
                if image_base64:
                    self._save_test_image(image_base64, 'resultado_test.png')
                    logger.info(f'Base64 extracted (len={len(image_base64)})')
                    return image_base64

                # JS fallback for stale element references in headless mode
                src_js = self.driver.execute_script(
                    "const img = document.querySelector('app-form-datos-consulta div img');"
                    "return img ? img.getAttribute('src') : null;"
                )
                image_base64 = self._extract_base64_from_src(src_js)
                if image_base64:
                    self._save_test_image(image_base64, 'resultado_test.png')
                    logger.info(f'Base64 extracted via JS fallback (len={len(image_base64)})')
                    return image_base64

                logger.warning('Image found but src not usable yet; retrying...')

            except TimeoutException:
                logger.warning('Timed out waiting for result image; retrying...')
            except Exception as e:
                logger.warning(f'Unexpected error on attempt {attempt}: {e}')

            self.take_screenshot(f'headless_debug_attempt_{attempt}_{int(time.time())}.png')
            time.sleep(2)

        logger.error('Could not extract image base64 after all retries')
        return None


def run_test(plate_number, plate_id=None, headless=True, pre_click_delay=5.0):
    scraper = TestConsultaVehicularScraper(pre_click_delay_seconds=pre_click_delay)
    return scraper.run(
        plate_number=plate_number,
        plate_id=plate_id,
        headless=headless,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description='Headless-first Consulta Vehicular SUNARP scraper'
    )
    parser.add_argument('--plate', required=True, help='Plate number, e.g. BNP276')
    parser.add_argument('--plate-id', help='Optional plate id for mark-loaded')
    parser.add_argument('--headless', dest='headless', action='store_true', default=True)
    parser.add_argument('--no-headless', dest='headless', action='store_false')
    parser.add_argument(
        '--pre-click-delay',
        type=float,
        default=5.0,
        help='Seconds to wait before clicking search button (default: 5.0)',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    plate = args.plate.strip().upper()

    logger.info('=' * 60)
    logger.info('Running TEST B scraper (headless-first)')
    logger.info(
        f'plate={plate}, plate_id={args.plate_id}, '
        f'headless={args.headless}, pre_click_delay={args.pre_click_delay}'
    )
    logger.info('=' * 60)

    success = run_test(
        plate_number=plate,
        plate_id=args.plate_id,
        headless=args.headless,
        pre_click_delay=args.pre_click_delay,
    )

    if success:
        logger.info('Test run completed successfully')
        return 0

    logger.error('Test run failed')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
