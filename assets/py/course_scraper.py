from os import path
import re
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from logger import Logger
from constants import *
from time import sleep
import threading

from scraper import Scraper
from driver_manager import DriverManager


class CourseScraper(Scraper):
    def __init__(self, webdriver):
        super().__init__(webdriver)
        self.courses = []

    def get_course_codes(self):
        course_codes = []

        # Read the lessons file
        if path.exists(f"../../{LESSONS_FILE_NAME}"):
            with open(f"../../{LESSONS_FILE_NAME}", "r") as file:
                course_codes += [l.split("|")[1] for l in file.readlines() if "|" in l]

        # Read the course plans file
        if path.exists(f"../../{COURSE_PLANS_FILE_NAME}"):
            with open(f"../../{COURSE_PLANS_FILE_NAME}", "r") as file:
                course_rows = [l.replace("\n", "") for l in file.readlines() if l[0] != "#"]
                for cells in [row.split("=") for row in course_rows]:
                    for cell in cells:
                        # If elective course
                        if "[" in cell:
                            course_codes += cell.split("*")[-1].replace("(", "").replace(")", "").replace("]", "").split("|")
                        else:
                            course_codes.append(cell)

        # Read the old courses files
        if path.exists(f"../../{COURSES_FILE_NAME}"):
            with open(f"../../{COURSES_FILE_NAME}", "r", encoding="utf-8") as file:
                course_codes += [l.split("|")[0] for l in file.readlines() if "|" in l]

        return list(set([c for c in course_codes if len(c) > 0]))  # Remove duplicates and empty strings.

    def scrap_current_table(self, driver, timeout_dur: float=3.0):
        output = ""
        
        try:
            all_rows = WebDriverWait(driver, timeout_dur).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tbody tr"))
            )
        except TimeoutException:
            return None

        output += self.find_elements_by_css_selector("td", all_rows[2])[0].get_attribute("innerHTML") + "|"  # Course Code
        output += self.find_elements_by_css_selector("td", all_rows[2])[1].get_attribute("innerHTML") + "|"  # Course Name
        output += self.find_elements_by_css_selector("td", all_rows[2])[2].get_attribute("innerHTML") + "|"  # Course Language

        output += self.find_elements_by_css_selector("td", all_rows[4])[0].get_attribute("innerHTML") + "|"  # Course Credits
        output += self.find_elements_by_css_selector("td", all_rows[4])[1].get_attribute("innerHTML") + "|"  # Course ECTS

        output += self.find_elements_by_css_selector("td", all_rows[6])[1].get_attribute("innerHTML") + "|"  # Course Prerequisites
        output += self.find_elements_by_css_selector("td", all_rows[7])[1].get_attribute("innerHTML") + "|"  # Major Prerequisites

        output += self.find_elements_by_css_selector("td", all_rows[9])[0].get_attribute("innerHTML").replace("\n", "") # Description

        return re.sub(r'[ \t]+', ' ', re.sub(r'<.*?>', '', output)).strip()  # Remove HTML tags and extra spaces.

    def scrap_courses_thread_routine(self, course_codes: list[str], thread_prefix: str, log_interval_modulo: int=100) -> None:
        driver = DriverManager.create_driver()
        driver.get(COURSES_URL)
        sleep(3)

        self.switch_to_turkish(driver, thread_prefix)

        for name, number in [c.split(" ") for c in course_codes]:
            course_code_name = self.find_elements_by_css_selector("input[name='subj']", driver)[0]
            course_code_number = self.find_elements_by_css_selector("input[name='numb']", driver)[0]
            submit_button = self.find_elements_by_css_selector("input[type='submit']", driver)[0]
            
            course_code_name.clear()
            course_code_name.send_keys(name)

            course_code_number.clear()
            course_code_number.send_keys(number)

            submit_button.click()
            self.wait()

            table_content = self.scrap_current_table(driver)
            if table_content is not None:
                self.courses.append(table_content)

                if len(self.courses) % log_interval_modulo == 0:
                    Logger.log_info(f"{thread_prefix} Scraped {len(self.courses)} courses.")
            else:
                Logger.log_error(f"{thread_prefix} Could not scrap {name} {number}, timed out while waiting for the table to load.")

        Logger.log(f"{thread_prefix} [bright_green]Operation completed.[/bright_green]")
        DriverManager.kill_driver(driver)

    def split_list_into_chunks(self, lst, num_chunks):
        # Calculate the average chunk size and remainder
        chunk_size = len(lst) // num_chunks
        remainder = len(lst) % num_chunks
        
        # Initialize the chunks
        chunks = []
        start = 0
        
        for i in range(num_chunks):
            # If there's remainder, increase the chunk size for this chunk
            end = start + chunk_size + (1 if i < remainder else 0)
            chunks.append(lst[start:end])
            start = end
        
        return chunks

    def scrap_courses(self):
        Logger.log_info("====== Scraping All Courses ======")
        self.webdriver.minimize_window()  # Not really necessary but makes testing a lot easier.

        self.courses = []
        Logger.log_info("Finding course codes to scrap.")
        courses_to_scrap = sorted(self.get_course_codes())
        Logger.log_info(f"Found {len(courses_to_scrap)} courses to scrap.")
        
        chunks = self.split_list_into_chunks(courses_to_scrap, MAX_THREAD_COUNT)
        threads = []
        for i in range(MAX_THREAD_COUNT):
            prefix = f"[royal_blue1][Thread {str(i).zfill(2)}][/royal_blue1]"
            t = threading.Thread(target=self.scrap_courses_thread_routine, args=(chunks[i], prefix))
            threads.append(t)
        
        # Start and wait for the threads to finish.
        for t in threads: t.start()
        for t in threads: t.join()

        Logger.log_info("[bold green]Scraping all courses is completed.[/bold green]")
        return self.courses        
