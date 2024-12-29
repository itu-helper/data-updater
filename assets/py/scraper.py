from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from requests.adapters import HTTPAdapter
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

import requests
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from time import sleep

from logger import Logger


class Scraper:
    SLEEP_DUR = .05

    def __init__(self, driver: webdriver.Chrome) -> None:
        self.webdriver = driver
        self.webdriver_wait = WebDriverWait(self.webdriver, 10)

    def is_element_stale(self, element) -> bool:
        try:
            # Attempt to access a property of the element
            return element.is_displayed() and element.is_enabled()
        except StaleElementReferenceException:
            return True  # Element is stale

    def get_attribute_element_pairs(self, elements: list, attribute: str) -> list[tuple]:
        return zip(elements, [e.get_attribute(attribute) for e in elements])

    def get_soup_from_url(self, url):
        try:
            # Retry strategy
            retry_strategy = Retry(
                total=5,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
                backoff_factor=1
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            http = requests.Session()
            http.mount("https://", adapter)
            http.mount("http://", adapter)
    
            page = http.get(url, timeout=25)  # Adding a timeout for good measure, ITU's network is usually shit.
            soup = BeautifulSoup(page.content, "html.parser")
            return soup
    
        except requests.exceptions.RequestException as e:
            Logger.log_warning(f"Failed to load the url {url}, trying again. Error raised: {e}")
            self.wait()
            return self.get_soup_from_url(url)
        except Exception as e:
            Logger.log_error(f"Failed to load the url {url}, error: {e}")
            return None

    def find_elements_by_class(self, class_name: str) -> list:
        return self.webdriver.find_elements(By.CLASS_NAME, class_name)
    
    def find_elements_by_css_selector(self, css_selector: str) -> list:
        return self.webdriver.find_elements(By.CSS_SELECTOR, css_selector)

    def find_elements_by_tag(self, tag_name: str) -> list:
        return self.webdriver.find_elements(By.TAG_NAME, tag_name)

    def wait(self, multiplier: int = 1):
        sleep(self.SLEEP_DUR * multiplier)

    def wait_until_loaded(self, element):
        self.webdriver_wait.until(EC.visibility_of(element))

    def wait_for_and_dismiss_alert(self, multiplier: int = 1) -> bool:
        try:
            WebDriverWait(self.webdriver, self.SLEEP_DUR * multiplier).until(EC.alert_is_present())
            return self.dismiss_alert()
        except TimeoutException:
            return False

    def dismiss_alert(self) -> bool:
        # Dismiss the alert. Note that sometimes we get an error saying the alert was already dismissed.
        # so just wrapped the dismiss line inside a try-except block.
        try:
            self.webdriver.switch_to.alert.accept()
            return True
        except Exception:
            return False
