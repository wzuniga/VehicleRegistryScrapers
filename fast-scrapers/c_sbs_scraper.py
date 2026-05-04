"""SBS SOAT Scraper — standalone test version with anti-bot measures and reCAPTCHA v3 solving.

No imports from c_sbs_scraper.py.
"""

import argparse
import logging
import os
import platform
import time
import warnings

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


class SBSScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://servicios.sbs.gob.pe/reportesoat/BusquedaPlaca'
        self._virtual_display = None

    def setup_driver(self, headless=False):
        logger.info('Configuring Chrome driver...')

        # On Linux: use Xvfb instead of --headless=new so reCAPTCHA scores higher
        if headless and platform.system() == 'Linux':
            try:
                from pyvirtualdisplay import Display
                self._virtual_display = Display(visible=False, size=(1366, 768))
                self._virtual_display.start()
                logger.info('Xvfb virtual display started (1366x768)')
                headless = False
            except ImportError:
                logger.warning('pyvirtualdisplay not installed, falling back to --headless=new')
                logger.warning('Install with: pip install pyvirtualdisplay && sudo apt install xvfb')
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
            logger.info('Headless mode enabled')
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
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            logger.info('Page loaded')
            return True
        except Exception as e:
            logger.error(f'Error navigating: {e}')
            return False

    def fill_plate_number(self, plate):
        try:
            logger.info(f'Filling plate: {plate}')
            plate_input_xpath = (
                '/html/body/div[4]/div/div/div/form/div[3]/div/div[2]/div/div[1]/div[1]/span/input'
            )
            plate_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, plate_input_xpath))
            )
            plate_input.clear()
            for char in plate:
                plate_input.send_keys(char)
            logger.info('Plate entered')
            return True
        except Exception as e:
            logger.error(f'Error filling plate: {e}')
            return False

    def select_radio_button(self, index=1):
        try:
            logger.info(f'Selecting radio button {index}...')
            radio_xpath = (
                f'/html/body/div[4]/div/div/div/form/div[3]/div/div[2]/div/div[2]'
                f'/div/table/tbody/tr/td[{index}]/input'
            )
            radio = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, radio_xpath))
            )
            radio.click()
            logger.info(f'Radio button {index} selected')
            return True
        except Exception as e:
            logger.error(f'Error selecting radio button {index}: {e}')
            return False

    def click_submit_button(self):
        try:
            logger.info('Clicking submit...')
            submit_xpath = '/html/body/div[4]/div/div/div/form/div[3]/div/div[3]/input'
            submit = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, submit_xpath))
            )
            submit.click()
            logger.info('Submit clicked')
            return True
        except Exception as e:
            logger.error(f'Error clicking submit: {e}')
            return False

    def extract_table_data_optimized(self):
        try:
            logger.info('Extracting table data...')
            container_xpath = (
                '/html/body/div[4]/div/div/div/form/div[3]/div/div[3]/div/div/div/div'
            )
            container = WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.XPATH, container_xpath))
            )
            table_header = container.find_element(By.XPATH, './/table[1]/thead/tr/th/span')
            value = table_header.text.strip()
            table = container.find_element(By.XPATH, './/table[2]')
            table_html = table.get_attribute('outerHTML')
            logger.info(f'Data extracted — value: {value}, HTML: {len(table_html)} chars')
            return value, table_html
        except Exception as e:
            logger.warning(f'No table found: {e}')
            return '0', ''

    def reset_form(self):
        try:
            logger.info('Resetting form...')
            self.driver.get(self.url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            logger.info('Form reset')
            return True
        except Exception as e:
            logger.error(f'Error resetting form: {e}')
            return False

    def send_results_to_api(self, results, plate_id):
        try:
            logger.info('Sending results to API...')
            api_url = 'http://54.204.68.114:3000/sbs-insurance'
            payload = {
                'plateNumber': results['plate_number'],
                'soatAccidents': int(results['SOAT']['count']) if results['SOAT']['count'].isdigit() else 0,
                'soatTableDetails': results['SOAT']['table_html'],
                'insuranceAccidents': int(results['SEGURO']['count']) if results['SEGURO']['count'].isdigit() else 0,
                'insuranceTableDetails': results['SEGURO']['table_html'],
                'catAccidents': int(results['CAT']['count']) if results['CAT']['count'].isdigit() else 0,
                'catTableDetails': results['CAT']['table_html'],
            }
            headers = {'accept': '*/*', 'Content-Type': 'application/json'}
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            if response.status_code in [200, 201]:
                mark_url = f'http://54.204.68.114:3000/pending-car-plates/{plate_id}/mark-loaded/C'
                requests.patch(mark_url, headers={'accept': '*/*'}, timeout=10).raise_for_status()
                logger.info(f'Plate {plate_id} marked as loaded')
                return True
            else:
                logger.error(f'API error: {response.status_code} — {response.text}')
                return False
        except Exception as e:
            logger.error(f'Error sending to API: {e}')
            return False

    def take_screenshot(self, filename='screenshot.png'):
        try:
            os.makedirs('sbs_scraper', exist_ok=True)
            path = os.path.join('sbs_scraper', filename)
            self.driver.save_screenshot(path)
            logger.info(f'Screenshot saved: {path}')
        except Exception as e:
            logger.error(f'Error taking screenshot: {e}')

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
        if self._virtual_display:
            try:
                self._virtual_display.stop()
                logger.info('Virtual display stopped')
            except Exception:
                pass
            self._virtual_display = None


class TestSBSScraper(SBSScraper):
    """SBS scraper — lets the browser handle reCAPTCHA v3 naturally.

    Waits for grecaptcha to be ready before submitting so the page's own
    grecaptcha.execute() call fires with a real browser-generated token.
    """

    def _wait_for_grecaptcha(self, timeout=10):
        """Wait until the grecaptcha object and execute() are available."""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script(
                    'return typeof grecaptcha !== "undefined" '
                    '&& typeof grecaptcha.execute === "function";'
                )
            )
            logger.info('grecaptcha ready')
        except Exception:
            logger.warning('grecaptcha not detected — proceeding anyway')

    def run(self, plate_number=None, plate_id=None, headless=False):
        try:
            if not plate_number:
                logger.error('Missing plate_number')
                return False

            logger.info(f'Plate: {plate_number} | Headless: {headless}')

            if not self.setup_driver(headless=headless):
                return False

            results = {
                'plate_number': plate_number,
                'SOAT':   {'count': '0', 'table_html': ''},
                'SEGURO': {'count': '0', 'table_html': ''},
                'CAT':    {'count': '0', 'table_html': ''},
            }
            field_mapping = {1: 'SOAT', 2: 'SEGURO', 3: 'CAT'}

            for radio_index in [1, 2, 3]:
                logger.info(f'\n{"=" * 60}')
                logger.info(f'Iteration {radio_index}/3 — {field_mapping[radio_index]}')
                logger.info('=' * 60)

                if radio_index == 1:
                    if not self.navigate_to_page():
                        return False
                else:
                    if not self.reset_form():
                        return False

                if not self.fill_plate_number(plate_number):
                    logger.warning(f'Could not fill plate on iteration {radio_index}')
                    continue

                if not self.select_radio_button(radio_index):
                    logger.warning(f'Could not select radio button {radio_index}')
                    continue

                # Wait for reCAPTCHA v3 to initialize, then pause 1s to appear human
                self._wait_for_grecaptcha()
                time.sleep(1)

                if not self.click_submit_button():
                    logger.warning(f'Could not click submit on iteration {radio_index}')
                    continue

                value, table_html = self.extract_table_data_optimized()
                field_name = field_mapping[radio_index]
                results[field_name]['count'] = value
                results[field_name]['table_html'] = table_html
                logger.info(f'{field_name} — count: {value}, HTML: {len(table_html)} chars')

            if plate_id:
                self.send_results_to_api(results, plate_id)
            else:
                logger.warning('No plate_id — skipping API send')

            logger.info('Process completed')
            return True

        except Exception as e:
            logger.error(f'run() error: {e}')
            return False
        finally:
            self.cleanup()


# ------------------------------------------------------------------ #
#  API helpers                                                         #
# ------------------------------------------------------------------ #

def get_pending_plate():
    """Fetch the next unprocessed plate from the API."""
    try:
        resp = requests.get(
            'http://54.204.68.114:3000/pending-car-plates/unloaded/C/first',
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
        scraper = TestSBSScraper()
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


def run_test(plate_number, plate_id=None, headless=False):
    scraper = TestSBSScraper()
    return scraper.run(plate_number=plate_number, plate_id=plate_id, headless=headless)


def main():
    """Main entry point.

    Default: production loop fetching plates from the API.
    Override with --plate for manual single-plate testing.
    """
    import sys

    # Manual single-plate mode: python test_c_sbs_scraper.py --plate BNP276 [--no-headless]
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
    logger.info('SBS SOAT Scraper — production loop')
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
            time.sleep(2)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
