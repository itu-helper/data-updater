from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
import atexit
from tqdm import tqdm
from logger import Logger


class DriverManager:
    active_drivers = []

    @staticmethod
    def create_driver():
        Logger.log_info("Creating a new web driver.")
        chrome_options = Options()

        chrome_options.add_argument("--disable-extensions")
        # chrome_options.add_argument("--disable-gpu")
        # chrome_options.add_argument("--no-sandbox") # linux only
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("log-level=2")
        chrome_options.add_argument("--no-proxy-server")
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        DriverManager.active_drivers.append(driver)
        return driver

    @staticmethod
    def kill_driver(driver):
        driver.quit()
        if driver in DriverManager.active_drivers:
            DriverManager.active_drivers.remove(driver)

    @staticmethod
    def clear_drivers():
        if len(DriverManager.active_drivers) == 0:
            return

        Logger.log_info("Clearing all existing web drivers")
        for driver in tqdm(DriverManager.active_drivers, desc="Clearing Web Drivers"):
            driver.quit()


# It's recommended to uncomment the following code when testing locally.

# This is a safety measure, if the program crashes while running, this line here makes sure that all drivers are terminated.
# Really useful when the driver is headless and there are a lot of drivers active. No need to have this active when
# running on GitHub actions as the container is destroyed when the action is completed.
atexit.register(DriverManager.clear_drivers)
