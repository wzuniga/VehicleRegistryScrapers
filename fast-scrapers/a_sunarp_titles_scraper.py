"""SUNARP Sigueloplus Titles Scraper — downloads title documents from sigueloplus.sunarp.gob.pe."""

import logging
import os
import platform
import sys
import time
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'python-scrapers'))

import requests
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from plate_offices import get_office_by_plate

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

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads_titles')


class SunarpTitlesScraper:
    def __init__(self):
        self.driver = None
        self.url = 'https://sigueloplus.sunarp.gob.pe/siguelo/'
        self._virtual_display = None

    # ------------------------------------------------------------------ #
    #  Driver setup                                                        #
    # ------------------------------------------------------------------ #

    def setup_driver(self, headless=False):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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
            'download.default_directory': DOWNLOAD_DIR,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'plugins.always_open_pdf_externally': True,
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
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def navigate_to_page(self):
        try:
            logger.info(f'Navigating to {self.url}...')
            self.driver.get(self.url)
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-root'))
            )
            time.sleep(3)
            self.accept_terms_modal()
            logger.info('Page loaded')
            return True
        except Exception as e:
            logger.error(f'Error navigating: {e}')
            return False

    def accept_terms_modal(self):
        try:
            btn_xpath = (
                '/html/body/div[1]/div[2]/div/mat-dialog-container/mat-dialog-actions/button[2]'
            )
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, btn_xpath))
            )
            btn.click()
            logger.info('Terms and conditions accepted')
            time.sleep(1)
        except TimeoutException:
            logger.info('No terms modal detected — continuing')
        except Exception as e:
            logger.warning(f'Could not accept terms modal: {e}')

    # ------------------------------------------------------------------ #
    #  Form filling                                                        #
    # ------------------------------------------------------------------ #

    def select_office(self, office_name):
        """Select oficina registral from the native <select> dropdown."""
        try:
            select_xpath = (
                '/html/body/app-root/app-ingreso/body/div/div[1]/div/div/div/form/div[3]/div/select'
            )
            select_el = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, select_xpath))
            )
            selected = self.driver.execute_script(
                """
                const sel = arguments[0];
                const target = arguments[1].trim().toUpperCase();
                for (let opt of sel.options) {
                    if (opt.text.trim().toUpperCase() === target) {
                        sel.value = opt.value;
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                        sel.dispatchEvent(new Event('input',  { bubbles: true }));
                        return opt.value;
                    }
                }
                return null;
                """,
                select_el,
                office_name,
            )
            if selected:
                logger.info(f'Office selected: {office_name} (value={selected})')
                time.sleep(1)
                return True
            logger.error(f'Office not found in dropdown: {office_name}')
            return False
        except Exception as e:
            logger.error(f'Error selecting office: {e}')
            return False

    def select_year(self, year='2018'):
        """Select año del título from the native <select> dropdown."""
        try:
            select_xpath = (
                '/html/body/app-root/app-ingreso/body/div/div[1]/div/div/div/form/div[4]/div/div/div/select'
            )
            select_el = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, select_xpath))
            )
            self.driver.execute_script(
                """
                const sel = arguments[0];
                sel.value = arguments[1];
                sel.dispatchEvent(new Event('change', { bubbles: true }));
                sel.dispatchEvent(new Event('input',  { bubbles: true }));
                """,
                select_el,
                str(year),
            )
            logger.info(f'Year selected: {year}')
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f'Error selecting year: {e}')
            return False

    def fill_titulo_number(self, titulo_number):
        """Type the título number into the input field."""
        try:
            input_xpath = (
                '/html/body/app-root/app-ingreso/body/div/div[1]/div/div/div/form/div[5]/div/div/input'
            )
            input_el = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, input_xpath))
            )
            input_el.click()
            input_el.clear()
            for char in titulo_number:
                input_el.send_keys(char)
                time.sleep(0.05)
            logger.info(f'Titulo number filled: {titulo_number}')
            return True
        except Exception as e:
            logger.error(f'Error filling titulo number: {e}')
            return False

    def click_search_button(self):
        """Wait for Cloudflare check then submit the form."""
        try:
            btn_xpath = (
                '/html/body/app-root/app-ingreso/body/div/div[1]/div/div/div/form/div[7]/div/div/button'
            )
            time.sleep(2)
            btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, btn_xpath))
            )
            btn.click()
            logger.info('Search button clicked — waiting for results page...')
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-titulo'))
            )
            time.sleep(2)
            logger.info('Results page loaded')
            return True
        except Exception as e:
            logger.error(f'Error clicking search button: {e}')
            return False

    # ------------------------------------------------------------------ #
    #  Results interaction                                                 #
    # ------------------------------------------------------------------ #

    def click_result_link(self):
        """Click the link in row 4 of the results table."""
        try:
            link_xpath = (
                '/html/body/app-root/app-titulo/body/div[13]/div[3]/table/tr[4]/td/a'
            )
            link = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, link_xpath))
            )
            link.click()
            logger.info('Result link clicked — waiting for modal...')
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f'Error clicking result link: {e}')
            return False

    def click_modal_download_button(self):
        """Click the download button, wait for Chrome to save the file, return base64."""
        try:
            btn_xpath = (
                '/html/body/div[1]/div[2]/div/mat-dialog-container'
                '/app-partidas/mat-card-content/div/div/table/tbody/tr/td[3]/button'
            )
            btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, btn_xpath))
            )

            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            existing_files = set(os.listdir(DOWNLOAD_DIR))
            main_handle = self.driver.window_handles[0]
            handles_before = set(self.driver.window_handles)

            btn.click()
            logger.info('Modal download button clicked — waiting for download...')

            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: len(d.window_handles) > len(handles_before)
                )
                for h in set(self.driver.window_handles) - handles_before:
                    try:
                        self.driver.switch_to.window(h)
                        self.driver.close()
                    except Exception:
                        pass
                self.driver.switch_to.window(main_handle)
            except TimeoutException:
                pass

            return self._wait_for_download(existing_files)
        except Exception as e:
            logger.error(f'Error clicking modal download button: {e}')
            return None

    # ------------------------------------------------------------------ #
    #  Document saving                                                     #
    # ------------------------------------------------------------------ #

    def _wait_for_download(self, existing_files, timeout=30):
        """Poll DOWNLOAD_DIR until a new completed file appears, read it as base64, then delete it."""
        import base64
        deadline = time.time() + timeout
        while time.time() < deadline:
            current_files = set(os.listdir(DOWNLOAD_DIR))
            new_files = current_files - existing_files
            completed = [f for f in new_files if not f.endswith('.crdownload') and not f.endswith('.tmp')]
            if completed:
                filepath = os.path.join(DOWNLOAD_DIR, completed[0])
                with open(filepath, 'rb') as f:
                    pdf_base64 = base64.b64encode(f.read()).decode('utf-8')
                os.remove(filepath)
                logger.info(f'File read and encoded ({len(pdf_base64):,} chars), temp file deleted')
                return pdf_base64
            time.sleep(0.5)
        logger.error('Download timed out — file never appeared in downloads folder')
        return None

    # ------------------------------------------------------------------ #
    #  Main flow                                                           #
    # ------------------------------------------------------------------ #

    def close_modal_and_return_to_form(self):
        """Close the partidas modal then navigate back to the search form."""
        try:
            # Switch back to main tab if we're still on the document tab
            main_handle = self.driver.window_handles[0]
            if self.driver.current_window_handle != main_handle:
                self.driver.close()
                self.driver.switch_to.window(main_handle)

            close_xpath = (
                '/html/body/div[1]/div[2]/div/mat-dialog-container'
                '/app-partidas/mat-card-header/mat-toolbar/mat-icon'
            )
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, close_xpath))
            )
            btn.click()
            logger.info('Modal closed')
            time.sleep(1)
        except TimeoutException:
            logger.info('Modal already closed')
        except Exception as e:
            logger.warning(f'Could not close modal: {e}')

        try:
            back_xpath = (
                '/html/body/app-root/app-titulo/body/app-navigation/nav/div[1]/ul/li[3]/a'
            )
            link = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, back_xpath))
            )
            link.click()
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, 'app-ingreso'))
            )
            time.sleep(1)
            logger.info('Returned to search form')
            return True
        except Exception as e:
            logger.error(f'Could not return to form: {e}')
            return False

    def process(self, office_name, titulo_year, titulo_number):
        try:
            logger.info(f'Processing: office={office_name} year={titulo_year} titulo={titulo_number}')
            if not self.select_office(office_name):
                return False
            if not self.select_year(titulo_year):
                return False
            if not self.fill_titulo_number(titulo_number):
                return False
            if not self.click_search_button():
                return False
            if not self.click_result_link():
                return False

            pdf_base64 = self.click_modal_download_button()
            if not pdf_base64:
                return False

            send_pdf_to_api(titulo_year, titulo_number, pdf_base64)
            return True
        except Exception as e:
            logger.error(f'Error in process: {e}')
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
#  API helpers                                                         #
# ------------------------------------------------------------------ #

API_BASE = 'http://54.204.68.114:3000'


def get_pending_titles():
    try:
        resp = requests.get(
            f'{API_BASE}/sprl-sunarp-titles/pending',
            headers={'accept': '*/*'},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f'Error fetching pending titles: {e}')
        return []


def send_pdf_to_api(titulo_year, titulo_number, pdf_base64):
    try:
        resp = requests.patch(
            f'{API_BASE}/sprl-sunarp-titles/{titulo_year}/{titulo_number}/pdf',
            json={'pdfBase64': pdf_base64},
            headers={'accept': '*/*', 'Content-Type': 'application/json'},
            timeout=30,
        )
        resp.raise_for_status()
        logger.info(f'PDF sent to API: {titulo_year}/{titulo_number}')
        return True
    except Exception as e:
        logger.error(f'Error sending PDF to API: {e}')
        return False


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

def main():
    logger.info('=' * 60)
    logger.info('SUNARP Sigueloplus Titles Scraper')
    logger.info('=' * 60)

    scraper = SunarpTitlesScraper()
    needs_restart = True

    try:
        while True:
            pending = get_pending_titles()
            if not pending:
                logger.info('No pending titles — waiting 10s...')
                time.sleep(10)
                continue

            for job in pending:
                titulo_year = job.get('tituloYear')
                titulo_number = job.get('tituloNumber')
                plate_number = job.get('plate')

                if not titulo_year or not titulo_number:
                    logger.warning(f'Invalid job data: {job}')
                    continue

                office_name = get_office_by_plate(plate_number) if plate_number else False
                if not office_name:
                    logger.warning(f'No office for plate {plate_number} (titulo {titulo_year}/{titulo_number}) — skipping')
                    continue

                while True:
                    if needs_restart:
                        scraper.cleanup()
                        scraper = SunarpTitlesScraper()
                        if not scraper.setup_driver(headless=False):
                            logger.error('Driver setup failed — retrying in 5s')
                            time.sleep(5)
                            continue
                        if not scraper.navigate_to_page():
                            logger.error('Navigation failed — retrying in 5s')
                            time.sleep(5)
                            continue
                        needs_restart = False

                    success = scraper.process(office_name, titulo_year, titulo_number)
                    if success:
                        logger.info(f'Done: {titulo_year}/{titulo_number} — restarting browser')
                        needs_restart = True
                        break
                    else:
                        logger.warning('Processing failed — restarting browser')
                        needs_restart = True

    except KeyboardInterrupt:
        logger.info('Stopped by user')
    finally:
        scraper.cleanup()


if __name__ == '__main__':
    main()
