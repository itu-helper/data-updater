from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from selenium.common.exceptions import TimeoutException

from time import sleep


class Scraper:
    SLEEP_DUR = .05

    def __init__(self, driver: webdriver.Chrome) -> None:
        self.webdriver = driver
        self.webdriver_wait = WebDriverWait(self.webdriver, 10)

    def find_elements_by_class(self, class_name: str) -> list:
        return self.webdriver.find_elements(By.CLASS_NAME, class_name)

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

    def get_dropdown_option_if_available(self, option):
        if len(option.find_elements(By.TAG_NAME, "a")) <= 0:
            return None
        if option.find_elements(By.TAG_NAME, "a")[0].get_attribute("role") != "option":
            return None
        if "Seçiniz" in option.find_elements(By.TAG_NAME, "a")[0].get_attribute("innerHTML"):
            return None
        return option.find_elements(By.TAG_NAME, "a")[0]
