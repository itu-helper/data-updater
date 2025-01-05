from scraper import Scraper
from logger import Logger
from selenium.webdriver.common.by import By
import threading
import re
from time import perf_counter
from selenium.webdriver.support import expected_conditions as EC
from constants import *

class CoursePlanScraper(Scraper):
    DEFAULT_ITERATION_NAME = "Tüm Öğrenciler İçin"

    def __init__(self, driver) -> None:
        super().__init__(driver)
        self.faculty_course_plans = {}

    def scrape_iteration_course_plan(self, url:str, log_prefix:str):
        soup = self.get_soup_from_url(url)  # Read the page.

        if soup is None:
            Logger.log_error(f"{log_prefix} Failed to load the url {url}.")
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

    def scrap_iterations(self, program_name: str, iteration_url: str, log_prefix: str) -> dict:
        program_iterations = dict()
        soup = self.get_soup_from_url(iteration_url)  # Read the page

        if soup is None:
            return dict()

        # If the URL is not valid
        if soup.find('h1', class_='text-danger'): 
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
                program_iterations[key] = self.scrape_iteration_course_plan(url, log_prefix)
            except Exception as e:
                Logger.log_warning(f"{log_prefix} The following error was thrown while scraping a program iteration ([blue]{key}[/blue]) of [cyan]\"{program_name}\"[/cyan]:\n\n{e}")
                self.wait()
                scrap_iteration_and_save(key, url, retry_count + 1)

        # Scrap all program iterations
        for iteration_name, iteration_url in iterations:
            Logger.log_info(f"{log_prefix} Scraping the iteration: [link={iteration_url}][dark_magenta]{iteration_name}[/dark_magenta][/link].")
            
            # Trim the iteration name, up to the first 4 digid number.
            # This way we get "Fizik Mühendisliği Lisans Programı (%100 İngilizce) 2010-2011 / Güz Dönemi Sonrası" -> "2010-2011 / Güz Dönemi Sonrası"
            iteration_match = re.search(r'\d{4}', iteration_name)
            if iteration_match:
                iteration_name = iteration_name[iteration_match.start():].strip()
            
            scrap_iteration_and_save(iteration_name, iteration_url)

        return program_iterations

    def scrap_faculty_course_plans_routine(self, programme_codes: str, thread_no: int):
        thread_prefix = f"[royal_blue1][Thread {str(thread_no).zfill(2)}][/royal_blue1]"
        for programme_code, programme_name, faculty, faculty_code in programme_codes:
            if "Yandal" in programme_name:
                Logger.log_info(f"{thread_prefix} Skipping the course plan for [blue]{programme_name}[/blue] in [blue]{faculty}[/blue] as it is a \"Yandal\" program.")
                continue
            
            if faculty not in self.faculty_course_plans:
                self.faculty_course_plans[faculty] = {}

            for url in COURSE_PLAN_URLS:
                Logger.log_info(f"{thread_prefix} Scraping the course plan for [blue]{programme_name}[/blue] in [blue]{faculty}[/blue].")
                iters = self.scrap_iterations(programme_name, url.format(programme_code), thread_prefix)
                if len(iters) != 0:
                    self.faculty_course_plans[faculty][programme_name] = iters
                    break

    # While splitting, make sure to have the plans of the same faculty be in the same chunk.
    def split_programme_codes_into_chunks(self, programme_codes, num_chunks):
        # Calculate the average chunk size and remainder
        target_chunk_size = len(programme_codes) // num_chunks
        
        chunks = []
        current_chunk = []

        for programme_code, programme_name, faculty, faculty_code in programme_codes:
            is_chunk_full = len(current_chunk) >= target_chunk_size
            belongs_to_same_faculty_with_last = len(current_chunk) > 0 and current_chunk[-1][2] == faculty

            if is_chunk_full and not belongs_to_same_faculty_with_last:
                chunks.append(current_chunk)
                current_chunk = []

            current_chunk.append((programme_code, programme_name, faculty, faculty_code))

        # If there are remaining items not added to chunks, add them.
        if len(current_chunk) > 0 and len(chunks) > 0:
            if len(chunks) < num_chunks:
                chunks.append(current_chunk)
            else:
                chunks[-1].extend(current_chunk)
        
        return chunks

    def scrap_course_plans(self):
        Logger.log_info("Scraping Course Programs")
        t0 = perf_counter()  # Start the timer for logging.

        with open(PROGRAMME_CODES_FILE_PATH, "r", encoding="utf-8") as ordered_faculty_names:
            programme_codes = [line.strip().split("|") for line in ordered_faculty_names.readlines()]

        thread_count = min(MAX_THREAD_COUNT, len(programme_codes))
        programme_code_chunks = self.split_programme_codes_into_chunks(programme_codes, thread_count)
        thread_count = len(programme_code_chunks)

        # Create the threads
        threads = []
        for i in range(thread_count):
            t = threading.Thread(target=self.scrap_faculty_course_plans_routine, args=(programme_code_chunks[i], i + 1))
            threads.append(t)
        
        # Start and wait for the threads to finish.
        for t in threads: t.start()
        for t in threads: t.join()

        # Faculties
        ordered_faculty_names = []
        for _, __, faculty, ___ in programme_codes:
            if faculty not in ordered_faculty_names:
                ordered_faculty_names.append(faculty)

        # Log how long the process took.
        t1 = perf_counter()
        Logger.log_info(f"Scraping Course Plans Completed in [green]{round(t1 - t0, 2)}[/green] seconds.")
        return {faculty:  self.faculty_course_plans[faculty] for faculty in ordered_faculty_names if faculty in self.faculty_course_plans}
