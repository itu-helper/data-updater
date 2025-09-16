from os import path
import re
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
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
        if path.exists(LESSONS_FILE_PATH):
            with open(LESSONS_FILE_PATH, "r") as file:
                course_codes += [l.split("|")[1] for l in file.readlines() if "|" in l]

        # Read the course plans file
        if path.exists(COURSE_PLANS_FILE_PATH):
            with open(COURSE_PLANS_FILE_PATH, "r") as file:
                course_rows = [l.replace("\n", "") for l in file.readlines() if l[0] != "#"]
                for cells in [row.split("=") for row in course_rows]:
                    for cell in cells:
                        # If elective course
                        if "[" in cell:
                            course_codes += cell.split("*")[-1].replace("(", "").replace(")", "").replace("]", "").split("|")
                        else:
                            course_codes.append(cell)

        # Read the old courses files
        if path.exists(COURSES_FILE_PATH):
            with open(COURSES_FILE_PATH, "r", encoding="utf-8") as file:
                course_codes += [l.split("|")[0] for l in file.readlines() if "|" in l]

        return list(set([c.strip() for c in course_codes if len(c.strip()) > 0]))  # Remove duplicates and empty strings.

    def scrap_current_table(self, driver, course_code: str, timeout_dur: float=3.0, max_retries: int=5, log_prefix: str="") -> str|None:
        output = ""
        attempt = 0
        while attempt < max_retries:
            if attempt > 0:
                Logger.log_warning(f"{log_prefix} Retrying scrap_current_table for {course_code}, attempt {attempt+1}/{max_retries}")
            try:
                all_rows = WebDriverWait(driver, timeout_dur).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tbody tr"))
                )

                def get_cell(row_idx, col_idx):
                    tds = self.find_elements_by_css_selector("td", all_rows[row_idx])
                    return tds[col_idx].get_attribute("innerHTML").replace("\n", " ")

                course_code_text = get_cell(2, 0)
                course_name_text = get_cell(2, 1)
                course_lang_text = get_cell(2, 2)

                # This means there are 2 course
                if "-" in course_code_text and len(course_code_text) > 1:
                    course_codes = [c.strip() for c in course_code_text.split("-")]
                    course_index = -1
                    for idx, code in enumerate(course_codes):
                        if course_code in code:
                            course_index = idx
                            break

                    course_code_text = course_codes[course_index]

                    # For some fucking reason these are split with / when there are 2 courses instead of - like the course code.
                    course_name_text = course_name_text.split("/")[course_index].strip()
                    course_lang_text = course_lang_text.split("/")[course_index].strip()

                # Sometimes, there is a single name yet name in multiple languages.
                if "/" in course_name_text:
                    course_lang_text = course_lang_text.split("/")[0].strip()  # In this case, there must be a single language but just in case.
                    course_name_text = course_name_text.split("/")[0 if "Türkçe" in course_lang_text else 1].strip()


                output += course_code_text + "|"  # Course Code
                output += course_name_text + "|"  # Course Name
                output += course_lang_text + "|"  # Course Language

                output += get_cell(4, 0) + "|"  # Course Credits
                output += get_cell(4, 1) + "|"  # Course ECTS

                # These fields are dynamic so hardcoded indexes dont work. FAAAK
                tables = WebDriverWait(driver, timeout_dur).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table"))
                )[1:] # First one is used as a parent to all the other tables.

                desc_text = ""
                course_prereqs = ""
                major_prereqs = ""
                for table in tables:
                    try:
                        first_row = table.find_elements(By.CSS_SELECTOR, "tr")[0]
                        first_cell = first_row.find_elements(By.CSS_SELECTOR, "td")[0].text.strip()
                    except Exception:
                        continue

                    if "Ders Tanımı" in first_cell:
                        # Description table: get all text from 2nd row, 1st cell
                        desc_text = table.find_elements(By.CSS_SELECTOR, "tr")[1].find_elements(By.CSS_SELECTOR, "td")[0].get_attribute("innerHTML").replace("\n", "")
                    elif "Önşartlar" in first_cell:
                        course_prereqs = table.find_elements(By.CSS_SELECTOR, "tr")[1].find_elements(By.CSS_SELECTOR, "td")[1].get_attribute("innerHTML")
                        major_prereqs = table.find_elements(By.CSS_SELECTOR, "tr")[2].find_elements(By.CSS_SELECTOR, "td")[1].get_attribute("innerHTML")

                output += course_prereqs.replace("\n", "") + "|"  # Course Prerequisites
                output += major_prereqs.replace("\n", "") + "|"  # Major Prerequisites
                output += desc_text.replace("\n", "")  # Description

                # Clean output - Thx Claude
                text = re.sub(r"[ \t]+", " ", re.sub(r"<.*?>", "", output)).replace("\n", " ").strip()
                text = re.sub(r"[\r\n\u2028\u2029]+", " ", text)  # Line breaks
                text = re.sub(r"[\t\xa0\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]+", " ", text)  # Various whitespace
                text = re.sub(r"\s+", " ", text)  # Normalize any remaining whitespace
                return text
            except UnexpectedAlertPresentException as e:
                Logger.log_error(f"{log_prefix} (attempt {attempt+1}/{max_retries}) | Unexpected alert present, dismissing it.")
                self.dismiss_alert(driver)
            except Exception as e:
                pass
                        
            sleep(0.5)
            attempt += 1
        Logger.log_error(f"{log_prefix} scrap_current_table failed after retries.")
        return None

    def scrap_courses_thread_routine(self, course_codes: list[str], thread_prefix: str, log_interval_modulo: int=100) -> None:
        driver = DriverManager.create_driver()
        driver.get(COURSES_URL)
        sleep(3)

        self.switch_to_turkish(driver, thread_prefix)

        for name, number in [c.split(" ") for c in course_codes]:
            course_code_name = self.find_elements_by_css_selector("input[name='bransKodu']", driver)[0]
            course_code_number = self.find_elements_by_css_selector("input[name='dersNo']", driver)[0]
            submit_button = self.find_elements_by_css_selector("input[type='submit']", driver)[0]
            
            course_code_name.clear()
            course_code_name.send_keys(name)

            course_code_number.clear()
            course_code_number.send_keys(number)

            submit_button.click()
            self.wait()

            Logger.log_info(f"{thread_prefix} Scrapping \"{name} {number}\"")
            table_content = self.scrap_current_table(driver, f"{name}{number}", log_prefix=thread_prefix)
            if table_content is not None:
                Logger.log_info(f"{thread_prefix} [bright_green]Scraped \"{name} {number}\"[/bright_green]")
                self.courses.append(table_content)

                if len(self.courses) % log_interval_modulo == 0:
                    Logger.log_info(f"Scraped {len(self.courses)} courses in total.")
            else:
                Logger.log_error(f"{thread_prefix} [red]Could not scrape \"{name} {number}\"[/red]")

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

        # Add missing courses from COURSES_FILE_PATH
        try:
            if path.exists(COURSES_FILE_PATH):
                with open(COURSES_FILE_PATH, "r", encoding="utf-8") as file:
                    for line in file:
                        line = line.strip()
                        if not line or "|" not in line:
                            continue
                        course_code = line.split("|")[0].strip()
                        # Check if course_code is already in self.courses
                        found = False
                        for c in self.courses:
                            if c.startswith(course_code + "|"):
                                found = True
                                break
                        if not found:
                            Logger.log_info(f"Adding missing course from old courses file: [i]\"{course_code}\"[/i]")
                            self.courses.append(line)
        except Exception as e:
            Logger.log_error(f"Error while adding missing courses from old courses file: {e}")

        return self.courses
