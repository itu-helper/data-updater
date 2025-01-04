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
from constants import *

COURSE_PLANS_URL = "https://obs.itu.edu.tr/public/DersPlan/"
ALLOWED_PLAN_TYPE_VALS = [
    "lisans",  # <option value="lisans">Undergraduate</option>
    "uolp",    # <option value="uolp">UOLP</option>
]
ALLOWED_PROGRAM_TYPES = [
    r"UOLP",  # Same for both Turkish and English

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
    DEFAULT_ITERATION_NAME = "Tüm Öğrenciler İçin"

    def __init__(self, driver) -> None:
        super().__init__(driver)
        self.faculty_course_plans = dict()
        self.faculties = []
        self.completed_faculty_count = 0

        self.load_page(COURSE_PLANS_URL)

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
                            selective_courses.append(selective_row.find("a").get_text().replace("\n", "").strip())

                        semester_program.append({selective_courses_title.replace("\n", "").strip(): selective_courses})
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
            Logger.log_info(f"{log_prefix} Scraping the iteration: [link={iteration_url}][dark_magenta]{iteration_name}[/dark_magenta][/link].")
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

    def scrap_faculty_course_plans(self, faculty_name: str, driver, log_prefix: str="") -> None:
        # Open the course plans page.
        Logger.log_info(f"{log_prefix} Starting fetching the faculty: [blue]\"{faculty_name}\"[/blue]")
        driver.get(COURSE_PLANS_URL)
        self.wait()
        self.switch_to_turkish(driver, log_prefix)
        
        # Find the dropdown option for the faculty.
        filtered_faculties = [f for f in self.get_faculty_dropdown_options(driver) if f.get_attribute("innerHTML") == faculty_name]
        if len(filtered_faculties) == 0:
            Logger.log_error(f"{log_prefix} Failed to find the faculty: [cyan]\"{faculty_name}\"[/cyan]")
            driver.quit()
            return
        faculty = filtered_faculties[0]

        # Read the program types, if it's empty, stop fetching.
        program_types = self.create_dropdown_and_get_elements(self.get_program_type_dropdown_options, faculty, driver=driver)
        if program_types is None:
            return
        program_type_names = [p.get_attribute("innerHTML") for p in program_types]

        if faculty_name not in self.faculty_course_plans.keys():
            self.faculty_course_plans[faculty_name] = dict()

        Logger.log(f"{log_prefix} Found the following program types for the faculty: [blue]{faculty_name}[/blue]: {', '.join([p.get_attribute('innerHTML') for p in program_types])}")
        for program_type_name in program_type_names:
            # Make sure the program type is allowed.
            if program_type_name not in ALLOWED_PROGRAM_TYPES:
                # Logger.log_info(f"{log_prefix} Skipping the program type: [blue]{faculty_name}[/blue] [cyan]\"{program_type_name}\"[/cyan]. Not allowed")
                continue
            
            # Read the programs, if it's empty, skip the program type.
            program_type = [p for p in self.get_program_type_dropdown_options(driver) if p.get_attribute("innerHTML") == program_type_name][0]
            programs = self.create_dropdown_and_get_elements(self.get_program_dropdown_options, program_type, driver=driver)
            if programs is None:
                Logger.log_info(f"{log_prefix} Skipping the program type: [blue]{faculty_name}[/blue]/[cyan]{program_type_name}[/cyan]. Programs empty")
                continue
            program_names = [p.get_attribute("innerHTML") for p in programs]

            for program_name in program_names:
                # Read the plan types, if it's empty, skip the program.
                program = [p for p in self.get_program_dropdown_options(driver) if p.get_attribute("innerHTML") == program_name][0]
                plan_types = self.create_dropdown_and_get_elements(self.get_plan_type_dropdown_options, program, driver=driver)
                if plan_types is None:
                    Logger.log_info(f"{log_prefix} Skipping the program: [blue]{faculty_name}[/blue]/[cyan]{program_type_name}[/cyan]/[magenta]{program_name}\"[/magenta]. Plan Types empty")
                    continue

                for plan_type, plan_type_value in self.get_attribute_element_pairs(plan_types, "value"):
                    # Make sure the plan type is allowed.
                    if plan_type_value not in ALLOWED_PLAN_TYPE_VALS: continue

                    # Click the submit/göster button, and wait for the iterations list page to load.
                    plan_type.click()
                    driver.find_element(By.CSS_SELECTOR, 'input[type="submit"]').click()
                    self.wait()

                    program_data = self.scrap_iterations(f"{program_name} ({program_type_name})", driver.current_url, log_prefix + f" [{plan_type_value}]")
                    if program_type_name not in self.faculty_course_plans[faculty_name]:
                        self.faculty_course_plans[faculty_name][program_type_name] = program_data
                    else:
                        self.faculty_course_plans[faculty_name][program_type_name].update(program_data)
                    
                    driver.back()
                    self.wait()

                    # After going back, sometimes the dropdown values are not the same. It stays the same consistently when running locally
                    # however, when running on GitHub actions, it sometimes changes. So we need to re-read the dropdown values.
                    # So, if the dropdowns are cleared, rerun this method, but skip the values that are already fetched.
                    # That's why we use enumerate. Make sure to increment k by 1 but not the others.
                    place_holders = self.find_elements_by_css_selector("span.select2-selection__placeholder", driver)
                    if len(place_holders) > 0:
                        Logger.log_info(f"{log_prefix} Dropdown values are cleared, reapplying them.")

                        # Find the dropdown option for the faculty.
                        filtered_faculties = [f for f in self.get_faculty_dropdown_options(driver) if f.get_attribute("innerHTML") == faculty_name]
                        if len(filtered_faculties) == 0:
                            Logger.log_error(f"{log_prefix} Failed to find the faculty: [cyan]\"{faculty_name}\"[/cyan]")
                            driver.quit()
                            return
                        faculty = filtered_faculties[0]

                        # Read the program types, if it's empty, stop fetching.
                        program_types = self.create_dropdown_and_get_elements(self.get_program_type_dropdown_options, faculty, driver=driver)
                        for pt in program_types:
                            if pt.get_attribute("innerHTML") == program_type_name:
                                program_type = pt
                                break

                        # Reselect the program type
                        programs = self.create_dropdown_and_get_elements(self.get_program_dropdown_options, program_type, driver=driver)
                        print([self.is_element_stale(p) for p in programs])
                        for p in programs:
                            if p.get_attribute("innerHTML") == program_name:
                                program = p
                                break

                        # Reselect the plan types
                        plan_types = self.create_dropdown_and_get_elements(self.get_plan_type_dropdown_options, program, driver=driver)
                        for pt in plan_types:
                            if pt.get_attribute("value") == plan_type_value:
                                plan_type = pt
                                break
        
        Logger.log_info(f"{log_prefix} Finished Scraping The Faculty: [blue]\"{faculty_name}\"[/blue]")

    def create_dropdown_and_get_elements(self, dropdown_read_func, dropdown_generation_element, max_retries: int=20, driver=None):
        for _ in range(max_retries):
            dropdown_generation_element.click()
            self.wait(2)
            dropdown_vals = dropdown_read_func(driver)

            # If the dropdown values exist and there are no stale elements in the dropdown values, return the values
            if dropdown_vals is not None and True not in [self.is_element_stale(e) for e in dropdown_vals]:
                return dropdown_vals
            dropdown_vals = None

        return dropdown_vals

    def remove_empty_course_plans(self):
        Logger.log_info("Removing empty/non-undergrad faculties/programs from the dictionary.")
        for faculty_name in self.faculty_course_plans.keys():
            program_types_to_pop = []  # We cache the values to pop and pop them after the iteration to avoid runtime errors.
            for program_type_name in self.faculty_course_plans[faculty_name].keys():
                if len(self.faculty_course_plans[faculty_name][program_type_name]) <= 0:
                    program_types_to_pop.append(program_type_name)
            
            for p in program_types_to_pop:
                Logger.log_info(f"Removing: [red]\"{faculty_name}[/red]/[blue]{p}\"[/blue].")
                self.faculty_course_plans[faculty_name].pop(p)

        # After removing the empty program types, we might have caused some faculties to be empty, so we remove those as well.
        faculties_to_pop = []  # We cache the values to pop and pop them after the iteration to avoid runtime errors.
        for faculty_name in self.faculty_course_plans.keys():
            if len(self.faculty_course_plans[faculty_name].keys()) <= 0:
                faculties_to_pop.append(faculty_name)
        
        for p in faculties_to_pop:
            Logger.log_info(f"Removing: [red]\"{p}\"[/red].")
            self.faculty_course_plans.pop(p)

    # Here, we need to convert the faculty_course_plans, which is stored with the new format, to the old format for compatibility.
    # The input format is like [Faculty][Program Type][Program Name Iteration], ex: ['Fen - Edebiyat Fakültesi']['100% İngilizce Program']['Fizik Mühendisliği Lisans Programı (%100 İngilizce) 2010-2011 / Güz Dönemi Sonrası']
    # We need to convert this to ['Fen - Edebiyat Fakültesi']['Fizik Mühendisliği Lisans Programı (%100 İngilizce)']['2010-2011 / Güz Dönemi Sonrası']
    def get_formatted_faculty_course_plans(self, faculty_course_plans):
        def get_iteration_from_program_name(s: str) -> tuple[str, str]:
            program_name, iteration = None, None
            
            # Trim the iteration name, up to the first 4 digid number.
            # This way we get "Fizik Mühendisliği Lisans Programı (%100 İngilizce) 2010-2011 / Güz Dönemi Sonrası" -> "2010-2011 / Güz Dönemi Sonrası"
            iteration_match = re.search(r'\d{4}', s)
            if iteration_match:
                iteration = s[iteration_match.start():].strip()

            # We only want the name of the program, without the language part and the iteration, If the iteration is found.
            # start from the part before the iteration, then get the part before where %100  starts. Make sure both 30% and 100% are supported.
            # Also, support both Turkish and English, where the possition of the % changes.
            before_iteration = s[:iteration_match.start()].strip() if iteration is not None else None
            program_name_match = re.search(r'\%\d{2,3}|\\d{2,3}%', before_iteration if before_iteration is not None else s)
            if program_name_match:
                program_name = s[:program_name_match.start()].strip()
            elif before_iteration is not None:
                program_name = before_iteration

            return program_name, iteration
        
        formatted_dict = dict()
        for faculty in faculty_course_plans.keys():
            formatted_dict[faculty] = dict()

            for program_type_name, program in faculty_course_plans[faculty].items():
                for program_name, program_content in program.items():
                    trimmed_program_name, iteration = get_iteration_from_program_name(program_name)
                    
                    # If both the program name and iteration are None, the program name might not contain an iteration
                    # For example, "Peyzaj Mimarlığı Lisans Programı" has no iteration names, as it has a single iteration.
                    # https://obs.itu.edu.tr/public/DersPlan/DersPlanDetay/194
                    if trimmed_program_name is None and iteration is None:
                        trimmed_program_name = program_name
                        iteration = self.DEFAULT_ITERATION_NAME
                    elif trimmed_program_name is None:
                        Logger.log_warning(f"Failed to parse the program name from: {program_name}, skipping it.")
                        continue
                    elif iteration is None:
                        Logger.log_warning(f"Failed to parse the iteration from: {program_name}, iteration will be set to {self.DEFAULT_ITERATION_NAME}")
                        iteration = self.DEFAULT_ITERATION_NAME

                    program_name_with_type = f"{trimmed_program_name} ({program_type_name})"
                    # Because the language part can have both paranthesis or not (thank you itu), we need to find the match with out a paranthesis
                    # and if there is a paranthesis, remove it afterwards. Solving this inside `get_iteration_from_program_name` is probably much better
                    # but this works for now. Here, we just replace "( (" with "(". '... Programı ( (100% İngilizce Program)' -> '... Programı (100% İngilizce Program)'"
                    program_name_with_type = program_name_with_type.replace("( (", "(")
                    
                    if program_name_with_type not in formatted_dict[faculty].keys():
                        formatted_dict[faculty][program_name_with_type] = dict()
                    
                    formatted_dict[faculty][program_name_with_type][iteration] = program_content

        return formatted_dict

    def scrap_course_plan_thread_routine(self, thread_no: int):
        thread_prefix = f"[royal_blue1][Thread {str(thread_no).zfill(2)}][/royal_blue1]"
        Logger.log(f"{thread_prefix} Starting thread.")

        thread_driver = DriverManager.create_driver()
        while self.completed_faculty_count < len(self.faculties):  # While there are still faculties to fetch
            # # DEBUG | Uncomment this to stop fetching at faculty, useful for debugging.
            # if self.completed_faculty_count > 0:
            #     break

            self.completed_faculty_count += 1  # Increment the completed faculty count before completion so that other threads don't try to fetch the same faculty.
            thread_prefix = f"[royal_blue1][Thread {thread_no} (F: {self.completed_faculty_count}/{len(self.faculties)})][/royal_blue1]"
            faculty = self.faculties[self.completed_faculty_count - 1]
            
            self.scrap_faculty_course_plans(faculty, thread_driver, thread_prefix)
            Logger.log_info(f"{thread_prefix} [bright_green]Finished Scraping [blue]{faculty}[/blue].[/bright_green]")    

        DriverManager.kill_driver(thread_driver)
        Logger.log(f"{thread_prefix} [bright_green]Operation completed.[/bright_green]")

    def scrap_course_plans(self):
        Logger.log_info("Scraping Course Programs")
        self.wait()
        self.switch_to_turkish()

        t0 = perf_counter()  # Start the timer for logging.

        # Create a list of the names of the faculties, in ITU's order.
        faculties = self.get_faculty_dropdown_options()
        self.faculties = [f.get_attribute("innerHTML") for f in faculties]

        self.webdriver.minimize_window()  # Not really necessary but makes testing a lot easier.

        # Create the threads
        threads = []
        for i in range(min(MAX_THREAD_COUNT, len(self.faculties))):
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
        return self.get_formatted_faculty_course_plans(self.faculty_course_plans)

    @staticmethod
    def get_dropdown_option_if_available(option):
        if len(option.find_elements(By.TAG_NAME, "a")) <= 0:
            return None
        if option.find_elements(By.TAG_NAME, "a")[0].get_attribute("role") != "option":
            return None
        if "Seçiniz" in option.find_elements(By.TAG_NAME, "a")[0].get_attribute("innerHTML"):
            return None
        return option.find_elements(By.TAG_NAME, "a")[0]
