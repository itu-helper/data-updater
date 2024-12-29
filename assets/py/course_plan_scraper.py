from scraper import Scraper
from logger import Logger
from selenium.webdriver.common.by import By
import threading
import re
from driver_manager import DriverManager
from time import perf_counter
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

COURSE_PLANS_URL = "https://obs.itu.edu.tr/public/DersPlan/"
ALLOWED_PROGRAM_TYPE_VALS = [
    "lisans"  # <option value="lisans">Undergraduate</option>
]
ALLOWED_PROGRAM_TYPES = [
    # === English ===
    r"100% English Program",
    r"30% English Program",
    r"100% Turkish Program",
    # === Turkish ===
    # Note: (% signs are not missplaced to the right side, that's how they are in the website.)
    r"100% İngilizce Program",
    r"30% İngilizce Program",
    r"100% Türkçe Program",
]

class CoursePlanScraper(Scraper):
    MAX_FACULTY_THREADS = 4

    def __init__(self, driver) -> None:
        super().__init__(driver)
        self.faculty_course_plans = dict()
        self.ordered_faculty_names = []
        self.completed_faculty_count = 0

    def scrape_iteration_course_plan(self, url):
        soup = self.get_soup_from_url(url)  # Read the page.

        if soup is None:
            Logger.log_error(f"Failed to load the url {url}.")
            return [[dict()]]

        program_list = []
        tables = soup.find_all("table")  # Read all tables.
        
        for table in tables:
            semester_program = []
            rows = table.find("tbody").find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                cell0_a = cells[0].find("a")
                course_code = cell0_a.get_text().strip()

                # When a course is selective, the first cell becomes a button with text ("Dersler" or "Courses")
                if ("Dersler" or "Courses") in course_code:
                    selective_courses_title = cells[1].get_text()
                    selective_soup = self.get_soup_from_url(f"https://obs.itu.edu.tr{cell0_a['href']}")

                    selective_courses = []
                    selective_course_table = selective_soup.find("table")

                    if selective_course_table is not None:
                        selective_course_rows = selective_course_table.find_all("tr")

                        # First row is just the header.
                        for selective_row in selective_course_rows[1:]:
                            selective_courses.append(selective_row.find("a").get_text().strip())

                        semester_program.append({selective_courses_title: selective_courses})
                    else:
                        # Because ITU changed their website, I have no fucking clue what the "selective courses like below" is
                        # but the new UI might have fixed that issue. I'm leaving this here just in case
                        # ---------------------------------------------------------------------------------------------------
                        # TODO: Add support for selective courses like this:
                        # https://www.sis.itu.edu.tr/TR/ogrenci/lisans/ders-planlari/plan/MAK/20031081.html
                        semester_program.append({selective_courses_title: []})
                else:
                    semester_program.append(course_code)

            program_list.append(semester_program)

        return program_list

    def switch_to_turkish(self, driver=None):
        if driver is None:
            driver = self.webdriver

        lang_button = driver.find_element(By.CSS_SELECTOR, 'a.menu-lang')
        if "TÜRKÇE" in lang_button.get_attribute("innerHTML"):
            Logger.log_info("Switching to Turkish")
            lang_button.click()
            self.wait()

    def scrap_iterations(self, program_name: str, iteration_url: str, log_prefix: str="") -> dict:
        program_iterations = dict()
        soup = self.get_soup_from_url(iteration_url)  # Read the page

        if soup is None:
            return dict()

        # Cache the urls for the program iterations (they are usually date ranges like 2001-2002, 2021-2022 ve Sonrası, etc.).
        iterations = []
        for row in soup.select('tbody tr'):
            cells = row.select("td")
            iteration_url = cells[0].select("a")[0]["href"]
            iteration_name = cells[1].get_text().strip()
            iterations.append((iteration_name, f"https://obs.itu.edu.tr{iteration_url}"))

        def scrap_iteration_and_save(key, url, retry_count=0):
            if retry_count >= 5: 
                program_iterations[key] = None
                return
            try:
                program_iterations[key] = self.scrape_iteration_course_plan(url)
            except Exception as e:
                Logger.log_warning(f"{log_prefix} The following error was thrown while scraping a program iteration ([blue]{key}[/blue]) of [cyan]\"{program_name}\"[/cyan]:\n\n{e}")
                self.wait()
                scrap_iteration_and_save(key, url, retry_count + 1)

        # Scrap all program iterations
        for iteration_name, iteration_url in iterations:
            Logger.log_info(f"{log_prefix} Scraping the iteration: [blue]{iteration_name}[/blue] from [green]\"{iteration_url}\"[/green]")
            scrap_iteration_and_save(iteration_name, iteration_url)

        return program_iterations

    def get_faculty_dropdown_options(self, driver=None):
        return self.get_dropdown_options("FakulteId", driver)

    def get_program_dropdown_options(self, driver=None):
        return self.get_dropdown_options("programKodu", driver, remove_first=False)
    
    def get_program_type_dropdown_options(self, driver=None):
        return self.get_dropdown_options("ProgramTipiId", driver)
    
    def get_plan_type_dropdown_options(self, driver=None):
        return self.get_dropdown_options("planTipiKodu", driver, remove_first=False)

    # For some fucking reason, while some of the dropdown have a placeholder value at the top, some don't. Use `remove_first` to remove the first option if it is a placeholder.
    def get_dropdown_options(self, name: str, driver=None, remove_first: bool=True, timeout: float=1.0):
        if driver is None: 
            driver = self.webdriver
        
        css_selector = f'select[name~="{name}"] option'

        # Wait for the dropdown options to be present in the DOM
        try:
            WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, css_selector)))
        except Exception:
            return None

        # Retrieve all options under the dropdown
        options = driver.find_elements(By.CSS_SELECTOR, css_selector)
        
        if remove_first:
            return options[1:] if len(options) > 1 else None
        return options if len(options) > 0 else None

    def OLD_scrap_course_plan(self, i, url):
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

            faculty_plans[program_name] = self.scrap_iterations(program_name, driver.current_url)  # Scrap the program.

            Logger.log_info(f"Finished Scraping The Program: [cyan]\"{program_name}\"[/cyan] Under the Faculty: [blue]\"{faculty_name}\"[/blue]")
            driver.back()  # Go back to program selection.

        DriverManager.kill_driver(driver)  # Quit the newly created driver.
        Logger.log_info(f"Finished Scraping The Faculty: [blue]\"{faculty_name}\"[/blue]")
        self.faculty_course_plans[faculty_name] = faculty_plans  # Save the scrapped data to the faculties dict.

    def scrap_faculty_course_plans(self, faculty_name: str, log_prefix: str="") -> None:
        # Open the course plans page.
        Logger.log_info(f"{log_prefix} Starting fetching the faculty: [blue]\"{faculty_name}\"[/blue]")
        driver = DriverManager.create_driver()
        driver.get(COURSE_PLANS_URL)
        self.wait()
        self.switch_to_turkish(driver)
        
        # Find the dropdown option for the faculty.
        filtered_faculties = [f for f in self.get_faculty_dropdown_options(driver) if f.get_attribute("innerHTML") == faculty_name]
        if len(filtered_faculties) == 0:
            Logger.log_error(f"{log_prefix} Failed to find the faculty: [blue]\"{faculty_name}\"[/blue]")
            driver.quit()
            return
        faculty = filtered_faculties[0]

        # Read the program types, if it's empty, stop fetching.
        program_types = self.create_dropdown_and_get_elements(self.get_program_type_dropdown_options, faculty, driver=driver)
        if program_types is None:
            driver.quit()
            return

        self.faculty_course_plans[faculty_name] = dict()
        for program_type, program_type_name in self.get_attribute_element_pairs(program_types, "innerHTML"):
            # Make sure the program type is allowed.
            if program_type_name not in ALLOWED_PROGRAM_TYPES:
                continue
            
            # Read the programs, if it's empty, skip the program type.
            programs = self.create_dropdown_and_get_elements(self.get_program_dropdown_options, program_type, driver=driver)
            if programs is None:
                continue

            for program, program_name in self.get_attribute_element_pairs(programs, "innerHTML"):
                # Read the plan types, if it's empty, skip the program.
                plan_types = self.create_dropdown_and_get_elements(self.get_plan_type_dropdown_options, program, driver=driver)
                if plan_types is None:
                    continue

                for program_type, program_type_value in self.get_attribute_element_pairs(plan_types, "value"):
                    # Make sure the plan type is allowed.
                    if program_type_value not in ALLOWED_PROGRAM_TYPE_VALS: continue

                    # Click the submit/göster button, and wait for the iterations list page to load.
                    program_type.click()
                    driver.find_element(By.CSS_SELECTOR, 'input[type="submit"]').click()
                    self.wait()

                    program_data = self.scrap_iterations(f"{program_name} ({program_type_name})", driver.current_url, log_prefix)
                    self.faculty_course_plans[faculty_name][program_type_name] = program_data
                    driver.back()
        
        driver.quit()
        Logger.log_info(f"{log_prefix} Finished Scraping The Faculty: [blue]\"{faculty_name}\"[/blue]")

    def create_dropdown_and_get_elements(self, dropdown_read_func, dropdown_generation_element, max_retries: int=3, driver=None):
        for _ in range(max_retries):
            dropdown_generation_element.click()
            dropdown_vals = dropdown_read_func(driver)
            if dropdown_vals is None:
                return None

            # If there are no stale elements in the dropdown values, break the loop.
            if True not in [self.is_element_stale(e) for e in dropdown_vals]:
                break

            self.wait()

        return dropdown_vals

    def remove_empty_course_plans(self):
        Logger.log_info("Removing empty faculties/programs from the dictionary.")
        for faculty_name in self.course_plans.keys():
            program_types_to_pop = []  # We cache the values to pop and pop them after the iteration to avoid runtime errors.
            for program_type_name in self.course_plans[faculty_name].keys():
                if len(self.course_plans[faculty_name][program_type_name]) <= 0:
                    program_types_to_pop.append(program_type_name)
            
            for p in program_types_to_pop:
                Logger.log_info(f"Removing: [red]\"{faculty_name}[/red]/[blue]{p}\"[/blue].")
                self.course_plans[faculty_name].pop(p)

        # After removing the empty program types, we might have caused some faculties to be empty, so we remove those as well.
        faculties_to_pop = []  # We cache the values to pop and pop them after the iteration to avoid runtime errors.
        for faculty_name in self.course_plans.keys():
            if len(self.course_plans[faculty_name].keys()) <= 0:
                faculties_to_pop.append(faculty_name)
        
        for p in faculties_to_pop:
            Logger.log_info(f"Removing: [red]\"{p}\"[/red].")
            self.course_plans.pop(p)

    # Here, we need to convert the faculty_course_plans, which is stored with the new format, to the old format for compatibility.
    # The input format is like [Faculty][Program Type][Program Name Iteration], ex: ['Fen - Edebiyat Fakültesi']['100% İngilizce Program']['Fizik Mühendisliği Lisans Programı (%100 İngilizce) 2010-2011 / Güz Dönemi Sonrası']
    # We need to convert this to ['Fen - Edebiyat Fakültesi']['Fizik Mühendisliği Lisans Programı (%100 İngilizce)']['2010-2011 / Güz Dönemi Sonrası']
    def get_formatted_faculty_course_plans(self, faculty_course_plans):
        def get_iteration_from_program_name(s: str) -> tuple[str, str]:
            # Trim the iteration name, up to the first 4 digid number.
            # This way we get "Fizik Mühendisliği Lisans Programı (%100 İngilizce) 2010-2011 / Güz Dönemi Sonrası" -> "2010-2011 / Güz Dönemi Sonrası"
            match = re.search(r'\d{4}', s)
            if not match:
                return (None, None)

            program_name = s[:match.start()].strip()
            iteration = s[match.start():].strip()
            return program_name, iteration
        
        formatted_dict = dict()
        for faculty in faculty_course_plans.keys():
            formatted_dict[faculty] = dict()

            for program in faculty_course_plans[faculty].values():
                for program_name, program_content in program.items():
                    Logger.log_info(f"BEFORE: Program Name: {program_name}")
                    program_name, iteration = get_iteration_from_program_name(program_name)
                    Logger.log_info(f" AFTER: Program Name: {program_name}, Iteration: {iteration}")
                    if program_name is None or iteration is None:
                        Logger.log_warning(f"Failed to parse the program name and iteration from: {program_name}")
                        continue
                    if program_name not in formatted_dict[faculty]:
                        formatted_dict[faculty][program_name] = dict()
                    
                    formatted_dict[faculty][program_name][iteration] = program_content

        return formatted_dict

    def scrap_course_plan_thread_routine(self, thread_no: int):
        thread_prefix = f"[Thread {thread_no}]"
        Logger.log(f"{thread_prefix} Starting thread.")
        while self.completed_faculty_count < len(self.ordered_faculty_names):  # While there are still faculties to fetch
            # # DEBUG | Uncomment this to stop fetching at faculty, useful for debugging.
            # if self.completed_faculty_count > 0:
            #     break

            self.completed_faculty_count += 1  # Increment the completed faculty count before completion so that other threads don't try to fetch the same faculty.
            faculty = self.ordered_faculty_names[self.completed_faculty_count - 1]
            Logger.log(f"{thread_prefix} Scraping {faculty}, {self.completed_faculty_count}/{len(self.ordered_faculty_names)}")    
            self.scrap_faculty_course_plans(faculty, thread_prefix)

        Logger.log(f"{thread_prefix} Operation completed.")

    def scrap_course_plans(self):
        Logger.log_info("Scraping Course Programs")
        self.wait()
        self.switch_to_turkish()

        t0 = perf_counter()  # Start the timer for logging.

        # Create a list of the names of the faculties, in ITU's order.
        faculties = self.get_faculty_dropdown_options()
        self.ordered_faculty_names = [f.get_attribute("innerHTML") for f in faculties]
        self.course_plans = {f: dict() for f in self.ordered_faculty_names}

        self.webdriver.minimize_window()  # Not really necessary but makes testing a lot easier.

        # Create the threads
        threads = []
        for i in range(min(self.MAX_FACULTY_THREADS, len(self.ordered_faculty_names))):
            t = threading.Thread(target=self.scrap_course_plan_thread_routine, args=(i,))
            threads.append(t)
        
        # Start and wait for the threads to finish.
        for t in threads: t.start()
        for t in threads: t.join()

        # Remove the empty faculties and programs from the dictionary.
        self.remove_empty_course_plans()

        # Log how long the process took.
        t1 = perf_counter()
        Logger.log_info(f"Scraping Course Plans Completed in [green]{round(t1 - t0, 2)}[/green] seconds.")
        return self.get_formatted_faculty_course_plans(self.faculty_course_plans), self.ordered_faculty_names  # return the results.

    @staticmethod
    def get_dropdown_option_if_available(option):
        if len(option.find_elements(By.TAG_NAME, "a")) <= 0:
            return None
        if option.find_elements(By.TAG_NAME, "a")[0].get_attribute("role") != "option":
            return None
        if "Seçiniz" in option.find_elements(By.TAG_NAME, "a")[0].get_attribute("innerHTML"):
            return None
        return option.find_elements(By.TAG_NAME, "a")[0]
