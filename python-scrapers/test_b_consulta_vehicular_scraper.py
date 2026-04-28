"""Test runner for scraper B with headless-first stability improvements.

Focus:
- Keep behavior equivalent to b_consulta_vehicular_scraper.py
- Improve reliability with headless=True
- Add wait/retry logic for Cloudflare-like intermediate challenges
"""

import argparse
import base64
import time

import requests
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from b_consulta_vehicular_scraper import ConsultaVehicularScraper, logger


class TestConsultaVehicularScraper(ConsultaVehicularScraper):
    """Headless-oriented test variant for scraper B."""

    def __init__(self, pre_click_delay_seconds=5.0):
        super().__init__()
        self.pre_click_delay_seconds = max(0.0, float(pre_click_delay_seconds))

    def setup_driver(self, headless=False):
        """Configure Chrome with safer defaults for headless and anti-bot pages."""
        logger.info('Configuring Chrome driver for test scraper...')

        options = uc.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--lang=es-ES')
        options.add_argument('--window-size=1366,900')
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

        # Keep full resource loading to avoid breaking anti-bot/challenge flows.
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
                        window.chrome = { runtime: {} };
                    '''
                })
            except Exception as cdp_error:
                logger.warning(f'Could not inject extra CDP anti-detection script: {cdp_error}')

            return True
        except Exception as e:
            logger.error(f'Error configuring Chrome driver: {e}')
            return False

    def _is_challenge_present(self):
        """Detect common Cloudflare-like challenge states."""
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
        """Wait until challenge disappears and app root is available."""
        end_time = time.time() + timeout

        while time.time() < end_time:
            if not self._is_challenge_present():
                if self.driver.find_elements(By.TAG_NAME, 'app-root'):
                    return True
            time.sleep(1)

        return False

    def navigate_to_page(self):
        """Navigate and wait for app/challenge stabilization."""
        try:
            logger.info(f'Navigating to {self.url}...')
            self.driver.get(self.url)

            # Wait for at least an interactive document state.
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
        """Click search button with JS fallback (headless-safe)."""
        button_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content/div/nz-card/div/app-form-datos-consulta/div/form/fieldset/nz-form-item[3]/nz-form-control/div/div/div/button'

        if self.pre_click_delay_seconds > 0:
            logger.info(
                f'Waiting {self.pre_click_delay_seconds:.1f}s before clicking search to allow captcha/session stabilization...'
            )
            time.sleep(self.pre_click_delay_seconds)

        for attempt in range(1, 4):
            try:
                if self._is_challenge_present():
                    logger.info('Challenge detected before click; waiting a bit more for clearance...')
                    self.wait_for_challenge_clear(timeout=2)

                logger.info(f'Clicking search button (attempt {attempt}/3)...')
                button = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, button_xpath))
                )
                button.click()
            except Exception as click_error:
                logger.warning(f'Normal click failed, trying JS click fallback: {click_error}')
                try:
                    button = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, button_xpath))
                    )
                    self.driver.execute_script('arguments[0].click();', button)
                except Exception as js_error:
                    logger.error(f'Error clicking search button with fallback: {js_error}')
                    return False

            # Esperar un poco para detectar modal de captcha no resuelto.
            time.sleep(1.2)
            if self._is_captcha_modal_present():
                logger.warning('Captcha unresolved modal detected after click.')
                self.take_screenshot(f'captcha_modal_attempt_{attempt}_{int(time.time())}.png')

                if not self._dismiss_captcha_modal():
                    logger.error('Could not dismiss captcha modal.')
                    return False

                if attempt < 3:
                    logger.info('Retrying search click without page reload...')
                    time.sleep(2)
                    continue

                logger.error('Captcha modal persisted after retries.')
                return False

            return True

        return False

    def _is_captcha_modal_present(self):
        """Detect captcha unresolved modal using provided absolute path and fallback text."""
        try:
            modal_nodes = self.driver.find_elements(By.XPATH, '/html/body/div/div')
            if not modal_nodes:
                return False

            modal_text = (modal_nodes[0].text or '').lower()
            markers = [
                'captcha no resuelto',
                'por favor resuelva el captcha',
            ]
            return any(marker in modal_text for marker in markers)
        except Exception:
            return False

    def _dismiss_captcha_modal(self):
        """Dismiss captcha modal by clicking OK button."""
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
                logger.warning(f'Could not fetch image url and convert to base64: {e}')

        return None

    def _save_test_image(self, image_base64, filename='resultado_test.png'):
        """Decode and save the extracted image to disk for visual verification."""
        try:
            normalized_base64 = image_base64.strip()
            missing_padding = len(normalized_base64) % 4
            if missing_padding:
                normalized_base64 += '=' * (4 - missing_padding)

            image_bytes = base64.b64decode(normalized_base64)
            with open(filename, 'wb') as output_file:
                output_file.write(image_bytes)

            logger.info(f'Test image saved: {filename}')
            return True
        except Exception as e:
            logger.warning(f'Could not save test image {filename}: {e}')
            return False

    def get_result_image_base64(self):
        """Get result image base64 with retries for headless/challenge scenarios."""
        logger.info('Extracting result image as base64...')

        result_img_xpath = '/html/body/app-root/nz-content/div/app-inicio/app-vehicular/nz-layout/nz-content/div/nz-card/div/app-form-datos-consulta/div/img'

        for attempt in range(1, 7):
            try:
                logger.info(f'Attempt {attempt}/6 to read result image')

                # If challenge appears after click, wait a bit and retry.
                if self._is_challenge_present():
                    logger.info('Challenge detected while waiting result; waiting for clearance...')
                    self.wait_for_challenge_clear(timeout=25)

                result_img = WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.XPATH, result_img_xpath))
                )

                src_attribute = result_img.get_attribute('src')
                image_base64 = self._extract_base64_from_src(src_attribute)

                if image_base64:
                    self._save_test_image(image_base64, 'resultado_test.png')
                    logger.info(f'Base64 extracted successfully (len={len(image_base64)})')
                    return image_base64

                # Fallback to JS read in case WebElement reference is stale in headless mode.
                src_attribute_js = self.driver.execute_script(
                    """
                    const img = document.querySelector('app-form-datos-consulta div img');
                    return img ? img.getAttribute('src') : null;
                    """
                )
                image_base64 = self._extract_base64_from_src(src_attribute_js)
                if image_base64:
                    self._save_test_image(image_base64, 'resultado_test.png')
                    logger.info(f'Base64 extracted with JS fallback (len={len(image_base64)})')
                    return image_base64

                logger.warning('Image found but src is not usable yet; retrying...')

            except TimeoutException:
                logger.warning('Timed out waiting for result image; retrying...')
            except Exception as e:
                logger.warning(f'Unexpected error getting image base64 (attempt {attempt}): {e}')

            self.take_screenshot(f'headless_debug_attempt_{attempt}_{int(time.time())}.png')
            time.sleep(2)

        logger.error('Could not extract image base64 after all retries')
        return None


def run_test(plate_number, plate_id=None, headless=True, pre_click_delay=5.0):
    """Run test scraper with manual plate."""
    scraper = TestConsultaVehicularScraper(pre_click_delay_seconds=pre_click_delay)
    return scraper.run(
        plate_number=plate_number,
        plate_id=plate_id,
        headless=headless,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description='Headless-first test runner for b_consulta_vehicular_scraper.py'
    )
    parser.add_argument('--plate', required=True, help='Plate number to test, e.g. BNP276')
    parser.add_argument('--plate-id', help='Optional plate id for mark-loaded')

    # Headless defaults to True for this test script.
    parser.add_argument('--headless', dest='headless', action='store_true', default=True)
    parser.add_argument('--no-headless', dest='headless', action='store_false')
    parser.add_argument(
        '--pre-click-delay',
        type=float,
        default=5.0,
        help='Seconds to wait before clicking Realizar busqueda (default: 5.0)'
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
