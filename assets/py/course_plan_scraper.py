from scraper import Scraper
from logger import Logger
from selenium.webdriver.common.by import By
import threading
from driver_manager import DriverManager
from time import perf_counter
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


class CoursePlanScraper(Scraper):
    MAX_FACULTY_THREADS = 4

    def __init__(self, driver) -> None:
        super().__init__(driver)
        self.faculty_course_plans = dict()
        self.faculties = []

    def click_program_dropdown(self, driver):
        # Check if the dropdown is already expanded.
        dropdown = driver.find_elements(By.TAG_NAME, "button")[1]
        if 'aria-expanded="true"' in dropdown.get_attribute("outerHTML"):
            return

        # Clicking this generates dropdown options.
        dropdown.find_element(By.CLASS_NAME, "filter-option-inner-inner").click()
        self.wait()

    def get_submit_button(self):
        return self.find_elements_by_class("button")[0]

    def scrape_iteration_course_plan(self, url):
        soup = self.get_soup_from_url(url)  # Read the page.

        if soup is None:
            Logger.log_error(f"Failed to load the url {url}.")
            return [[dict()]]

        program_list = []
        tables = soup.find_all("table", {"class": "table-responsive"})  # Read all tables.
        
        for table in tables:
            semester_program = []

            # First row is just the header, skip it.
            rows = table.find_all("tr")[1:]
            for row in rows:
                cells = row.find_all("td")

                # If the course is selective.
                a = cells[1].find("a")
                if a is not None:
                    selective_courses_url = url.replace(url.split("/")[-1], a["href"])

                    selective_courses_title = a.get_text()

                    selective_soup = self.get_soup_from_url(
                        selective_courses_url)

                    selective_courses = []
                    selective_course_table = selective_soup.find("table", {"class": "table-responsive"})

                    if selective_course_table is not None:
                        selective_course_rows = selective_course_table.find_all("tr")

                        # First row is just the header.
                        for selective_row in selective_course_rows[1:]:
                            selective_courses.append(
                                selective_row.find("a").get_text())

                        semester_program.append({selective_courses_title: selective_courses})
                    else:
                        # TODO: Add support for selective courses like this:
                        # https://www.sis.itu.edu.tr/TR/ogrenci/lisans/ders-planlari/plan/MAK/20031081.html
                        semester_program.append({selective_courses_title: []})
                else:
                    course_code = cells[0].find("a").get_text()
                    semester_program.append(course_code)

            program_list.append(semester_program)

        return program_list

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

    def scrap_programs(self, program_name, url):
        program_iterations = dict()
        soup = self.get_soup_from_url(url)  # Read the page

        if soup is None:
            Logger.log_error(f"Failed to load the url {url} for the program {program_name}")
            return dict()

        # Cache the urls for the program iterations (they are usually date ranges like 2001-2002, 2021-2022 ve Sonrası, etc.).
        for a in soup.find_all("a"):
            iteration_url = a["href"]
            inner_part = a.get_text()
            if ".html" in iteration_url:  # Make sure they are links to other pages.
                program_iterations[inner_part] = url + iteration_url  # URLS are formatted like "/something.html"

        def scrap_iteration_and_save(key, url):
            try:
                program_iterations[key] = self.scrape_iteration_course_plan(url)
            except Exception as e:
                Logger.log_warning(f"The following error was thrown while scraping a program iteration ([blue]{key}[/blue]) of [cyan]\"{program_name}\"[/cyan]:\n\n{e}")
                self.wait()
                scrap_iteration_and_save(key, url)

        # Scrap all program iterations
        for program_iteration, url in program_iterations.items():
            scrap_iteration_and_save(program_iteration, url)

        return program_iterations

    def get_faculty_dropdown_options(self, driver=None):
        return self.get_dropdown_options("fakulte", driver)  # Skip the first option which is the default placeholder value.

    def get_program_dropdown_options(self, driver=None):
        return self.get_dropdown_options("program", driver)  # Skip the first option which is the default placeholder value.

    def get_dropdown_options(self, name: str, driver=None):
        if driver is None: driver = self.webdriver
    
        # Read all options under the 'name' dropdown, if there isn't more than 1 option, which is the default option, quit.
        tags = driver.find_elements(By.CSS_SELECTOR, f'select[name~="{name}"] option')
        if len(tags) <= 1: return None
    
        return tags[1:]  # Skip the first option which is the default placeholder value.

    def scrap_course_plan(self, i, url):
        # Open the course plan page from a new driver.
        driver = DriverManager.create_driver()
        driver.get(url)
        self.wait()

        # Read the faculty dropdown
        faculty = self.get_faculty_dropdown_options(driver)[i]
        
        # Make sure the faculty is valid, if not, quit.
        if faculty is None:
            DriverManager.kill_driver(driver)
            return

        # Store faculty related data.
        faculty_name = faculty.get_attribute("innerHTML")
        faculty_code = faculty.get_attribute("value")
        
        driver.get(f"{driver.current_url}{faculty_code}")  # Chose the current faculty from the dropdown.

        faculty_plans = dict()
        for j in range(len(self.get_program_dropdown_options(driver))):
            program = self.get_program_dropdown_options(driver)[j]  # Read the program corresponding to current index (j)
            if program is None: continue  # Make sure the program is valid, if not, skip it.

            program_name = program.get_attribute("innerHTML")  # Read the program name.

            # Choose the program.
            program.click()

            # Press the submit button.
            driver.find_elements(By.CLASS_NAME, "button")[0].click()
            self.wait()

            faculty_plans[program_name] = self.scrap_programs(program_name, driver.current_url)  # Scrap the program.

            Logger.log_info(f"Finished Scraping The Program: [cyan]\"{program_name}\"[/cyan] Under the Faculty: [blue]\"{faculty_name}\"[/blue]")
            driver.back()  # Go back to program selection.

        DriverManager.kill_driver(driver)  # Quit the newly created driver.
        Logger.log_info(f"Finished Scraping The Faculty: [blue]\"{faculty_name}\"[/blue]")
        self.faculty_course_plans[faculty_name] = faculty_plans  # Save the scrapped data to the faculties dict.

    def scrap_course_plans_thread(self, remaining_indexes: list[int], url: str):
        while len(remaining_indexes) > 0:
            current_index = remaining_indexes.pop(0)
            self.scrap_course_plan(current_index, url)
            Logger.log_info(f"Remaining faculty count: [green]{len(remaining_indexes)}[/green]")

    def scrap_course_plans(self):
        Logger.log_info("Scraping Course Programs")

        # Create a list of the names of the faculties, in ITU's order.
        self.faculties = [
            option.get_attribute("innerHTML")
            for option in self.get_faculty_dropdown_options()
        ]
        
        faculty_count = len(self.faculties)
        t0 = perf_counter()  # Start the timer for logging.
        
        self.webdriver.minimize_window()  # Not really necessary but makes testing a lot easier.

        threads = []
        remaining_indexes = list(range(0, faculty_count))
        for thread in range(self.MAX_FACULTY_THREADS):
            # Create a thread and add it to the threads list.
            thread = threading.Thread(target=self.scrap_course_plans_thread, args=(remaining_indexes, self.webdriver.current_url))
            threads.append(thread)

        # Start the threads.
        for t in threads: t.start()

        # Wait for all the threads to end.
        for t in threads: t.join()

        # Log how long the process took.
        t1 = perf_counter()
        Logger.log_info(f"Scraping Course Plans Completed in [green]{round(t1 - t0, 2)}[/green] seconds.")
        
        return self.faculty_course_plans, self.faculties  # return the results.

    @staticmethod
    def get_dropdown_option_if_available(option):
        if len(option.find_elements(By.TAG_NAME, "a")) <= 0:
            return None
        if option.find_elements(By.TAG_NAME, "a")[0].get_attribute("role") != "option":
            return None
        if "Seçiniz" in option.find_elements(By.TAG_NAME, "a")[0].get_attribute("innerHTML"):
            return None
        return option.find_elements(By.TAG_NAME, "a")[0]
