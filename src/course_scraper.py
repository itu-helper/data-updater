from os import path
import re
from selenium.webdriver.support import expected_conditions as EC
import requests
from bs4 import BeautifulSoup
from logger import Logger
from constants import *
from time import sleep
import threading

from scraper import Scraper


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

    def scrap_table_html(self, source: str, course_code: str, timeout_dur: float=3.0, max_retries: int=5, log_prefix: str="") -> str|None:
        """
        Parse course HTML and return cleaned pipe-delimited course info.

        source can be either a Selenium WebDriver (old behaviour) or an HTML string (preferred).
        """
        html = source
        attempt = 0
        while attempt < max_retries:
            if attempt > 0:
                Logger.log_warning(f"{log_prefix} Retrying scrap_current_table for {course_code}, attempt {attempt+1}/{max_retries}")
            try:
                soup = BeautifulSoup(html, 'html.parser')

                # Helper to find a table by inspecting each <table>'s header
                # Match is performed against the table's first <th> inside <thead> (fallbacks applied).
                # Returns tbody <td> values as a 2D list of strings (each row is a list of td contents).
                def get_table(first_header: str) -> list[list[str]]:
                    try:
                        # All the tables in the page are also wrapped in a table and it's the first table so skipt it.
                        tables = soup.find_all('table')[1:]
                        for table in tables:
                            try:
                                # Try to get header text from thead > tr > th
                                header_text = ""
                                thead = table.find('thead')
                                if thead:
                                    first_th = thead.find('tr')
                                    if first_th:
                                        first_th = first_th.find('th')
                                        if first_th:
                                            header_text = first_th.get_text(strip=True)

                                # Fallback: if no thead or th, try first row's first cell (could be th or td)
                                if not header_text:
                                    first_row = table.find('tr')
                                    if first_row:
                                        first_cell = first_row.find(['th', 'td'])
                                        if first_cell:
                                            header_text = first_cell.get_text(strip=True)

                                if first_header in header_text:
                                    # Collect tbody rows' td values
                                    tbody = table.find('tbody') or table
                                    table_rows = []
                                    for tr in tbody.find_all('tr'):
                                        tds = tr.find_all('td')
                                        row_vals = [td.decode_contents().replace('\n', '').strip() for td in tds]
                                        table_rows.append(row_vals)
                                    return table_rows
                            except Exception as e:
                                Logger.log_error(f"get_table inner error: {e}")
                                continue
                    except Exception as e:
                        Logger.log_error(f"get_table outer error: {e}")
                        pass
                    return []

                course_details_table = get_table("Ders Kodu")
                if not course_details_table:
                    raise Exception("No course details table found")
        
                course_code_text = course_details_table[0][0]
                course_name_text = course_details_table[0][1]
                course_lang_text = course_details_table[0][2]

                # Remove tags but keep inner text later when cleaning
                # This means there are 2 course
                if "-" in course_code_text and len(course_code_text) > 1:
                    course_codes = [c.strip() for c in re.sub('<.*?>', '', course_code_text).split("-")]
                    course_index = -1
                    for idx, code in enumerate(course_codes):
                        if course_code in code:
                            course_index = idx
                            break

                    if course_index >= 0:
                        course_code_text = course_codes[course_index]
                        
                        splitted_course_name_text = re.sub('<.*?>', '', course_name_text).split('/')
                        course_name_text = splitted_course_name_text[min(course_index, len(splitted_course_name_text) - 1)].strip()
                        
                        splitted_course_lang_text = re.sub('<.*?>', '', course_lang_text).split('/')
                        course_lang_text = splitted_course_lang_text[min(course_index, len(splitted_course_lang_text) - 1)].strip()

                # Sometimes, there is a single name yet name in multiple languages.
                if "/" in course_name_text:
                    course_lang_text = course_lang_text.split("/")[0].strip()

                    course_names = course_name_text.split("/")
                    course_name_text = course_names[min(0 if "Türkçe" in course_lang_text else 1, len(course_names) - 1)].strip()

                # Convert "MAT103E" to "MAT 103E"
                course_code_text_plain = re.sub('<.*?>', '', course_code_text)
                if " " not in course_code_text_plain and len(course_code_text_plain) > 3:
                    if "TB001" in course_code_text_plain:
                        course_code_text_plain = course_code_text_plain[:2] + " " + course_code_text_plain[2:]
                    else:
                        course_code_text_plain = course_code_text_plain[:3] + " " + course_code_text_plain[3:]

                output = ""
                output += course_code_text_plain + "|"  # Course Code
                output += re.sub('<.*?>', '', course_name_text) + "|"  # Course Name
                output += re.sub('<.*?>', '', course_lang_text) + "|"  # Course Language

                credits_table = get_table("Kredi")
                if credits_table and len(credits_table) > 1 and len(credits_table[1]) > 1:
                    output += re.sub('<.*?>', '', credits_table[1][0].replace(",", ".")) + "|"  # Course Credits
                    output += re.sub('<.*?>', '', credits_table[1][1].replace(",", ".")) + "|"  # Course ECTS
                else:
                    output += "||"

                # Use get_table to find tables by their first <td> header inside a <tbody>
                desc_text = ""
                course_prereqs = ""
                major_prereqs = ""

                # Description table: look for a tbody whose first cell contains 'Ders Tanımı'
                desc_table = get_table("Ders Tanımı")
                if desc_table and len(desc_table) > 0 and len(desc_table[0]) > 0:
                    try:
                        desc_text = desc_table[0][0]
                    except Exception:
                        desc_text = ""

                # Prerequisites table: look for a tbody whose first cell contains 'Önşartlar'
                prereq_table = get_table("Önşartlar")
                if prereq_table and len(prereq_table) > 0 and len(prereq_table[0]) > 1:
                    # course_prereqs is expected at row index 1, td index 1
                    try:
                        course_prereqs = prereq_table[0][1] if len(prereq_table[0]) > 1 else ""
                    except Exception:
                        course_prereqs = ""
                if prereq_table and len(prereq_table) > 1:
                    try:
                        major_prereqs = prereq_table[1][1] if len(prereq_table[1]) > 1 else ""
                    except Exception:
                        major_prereqs = ""

                output += course_prereqs.replace("\n", "").replace("Veya", "veya").replace("ve", "ve") + "|"  # Course Prerequisites
                output += major_prereqs.replace("\n", "") + "|"  # Major Prerequisites
                output += desc_text.replace("\n", "")  # Description

                # Clean output - Thx Claude
                text = re.sub(r"[ \t]+", " ", re.sub(r"<.*?>", "", output)).replace("\n", " ").strip()
                text = re.sub(r"[\r\n\u2028\u2029]+", " ", text)  # Line breaks
                text = re.sub(r"[\t\xa0\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]+", " ", text)  # Various whitespace
                text = re.sub(r"\s+", " ", text)  # Normalize any remaining whitespace
                return text
            except Exception as e:
                Logger.log_error(f"{log_prefix} scrap_current_table failed for {course_code}:\n{e}")

            attempt += 1
        Logger.log_error(f"{log_prefix} scrap_current_table failed after retries.")
        return None

    # def scrap_current_table(self, driver, course_code: str, timeout_dur: float=3.0, max_retries: int=5, log_prefix: str="") -> str|None:
    #     """Original selenium-based implementation extracted to keep compatibility."""
    #     output = ""
    #     attempt = 0
    #     while attempt < max_retries:
    #         if attempt > 0:
    #             Logger.log_warning(f"{log_prefix} Retrying scrap_current_table for {course_code}, attempt {attempt+1}/{max_retries}")
    #         try:
    #             all_rows = WebDriverWait(driver, timeout_dur).until(
    #                 EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tbody tr"))
    #             )

    #             def get_cell(row_idx, col_idx):
    #                 tds = self.find_elements_by_css_selector("td", all_rows[row_idx])
    #                 return tds[col_idx].get_attribute("innerHTML").replace("\n", " ")

    #             course_code_text = get_cell(2, 0)
    #             course_name_text = get_cell(2, 1)
    #             course_lang_text = get_cell(2, 2)

    #             # This means there are 2 course
    #             if "-" in course_code_text and len(course_code_text) > 1:
    #                 course_codes = [c.strip() for c in course_code_text.split("-")]
    #                 course_index = -1
    #                 for idx, code in enumerate(course_codes):
    #                     if course_code in code:
    #                         course_index = idx
    #                         break

    #                 course_code_text = course_codes[course_index]

    #                 # For some fucking reason these are split with / when there are 2 courses instead of - like the course code.
    #                 course_name_text = course_name_text.split("/")[course_index].strip()
    #                 course_lang_text = course_lang_text.split("/")[course_index].strip()

    #             # Sometimes, there is a single name yet name in multiple languages.
    #             if "/" in course_name_text:
    #                 course_lang_text = course_lang_text.split("/")[0].strip()  # In this case, there must be a single language but just in case.
    #                 course_name_text = course_name_text.split("/")[0 if "Türkçe" in course_lang_text else 1].strip()


    #             # Convert "MAT103E" to "MAT 103E"
    #             if " " not in course_code_text and len(course_code_text) > 3:
    #                 course_code_text = course_code_text[:3] + " " + course_code_text[3:]

    #             output += course_code_text + "|"  # Course Code
    #             output += course_name_text + "|"  # Course Name
    #             output += course_lang_text + "|"  # Course Language

    #             output += get_cell(4, 0) + "|"  # Course Credits
    #             output += get_cell(4, 1) + "|"  # Course ECTS

    #             # These fields are dynamic so hardcoded indexes dont work. FAAAK
    #             tables = WebDriverWait(driver, timeout_dur).until(
    #                 EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table"))
    #             )[1:] # First one is used as a parent to all the other tables.

    #             desc_text = ""
    #             course_prereqs = ""
    #             major_prereqs = ""
    #             for table in tables:
    #                 try:
    #                     first_row = table.find_elements(By.CSS_SELECTOR, "tr")[0]
    #                     first_cell = first_row.find_elements(By.CSS_SELECTOR, "td")[0].text.strip()
    #                 except Exception:
    #                     continue

    #                 if "Ders Tanımı" in first_cell:
    #                     # Description table: get all text from 2nd row, 1st cell
    #                     desc_text = table.find_elements(By.CSS_SELECTOR, "tr")[1].find_elements(By.CSS_SELECTOR, "td")[0].get_attribute("innerHTML").replace("\n", "")
    #                 elif "Önşartlar" in first_cell:
    #                     course_prereqs = table.find_elements(By.CSS_SELECTOR, "tr")[1].find_elements(By.CSS_SELECTOR, "td")[1].get_attribute("innerHTML")
    #                     major_prereqs = table.find_elements(By.CSS_SELECTOR, "tr")[2].find_elements(By.CSS_SELECTOR, "td")[1].get_attribute("innerHTML")

    #             output += course_prereqs.replace("\n", "").replace("Veya", "veya").replace("ve", "ve") + "|"  # Course Prerequisites
    #             output += major_prereqs.replace("\n", "") + "|"  # Major Prerequisites
    #             output += desc_text.replace("\n", "")  # Description

    #             # Clean output - Thx Claude
    #             text = re.sub(r"[ \t]+", " ", re.sub(r"<.*?>", "", output)).replace("\n", " ").strip()
    #             text = re.sub(r"[\r\n\u2028\u2029]+", " ", text)  # Line breaks
    #             text = re.sub(r"[\t\xa0\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]+", " ", text)  # Various whitespace
    #             text = re.sub(r"\s+", " ", text)  # Normalize any remaining whitespace
    #             return text
    #         except UnexpectedAlertPresentException as e:
    #             Logger.log_error(f"{log_prefix} (attempt {attempt+1}/{max_retries}) | Unexpected alert present, dismissing it.")
    #             self.dismiss_alert(driver)
    #         except Exception as e:
    #             pass
                        
    #         sleep(0.5)
    #         attempt += 1
    #     Logger.log_error(f"{log_prefix} scrap_current_table failed after retries.")
    #     return None

    def scrap_courses_thread_routine(self, course_codes: list[str], thread_prefix: str, log_interval_modulo: int=100) -> None:
        # Use requests to call the public API endpoint for each course and parse the returned HTML
        session = requests.Session()
        # A small timeout and retry logic per course
        for name, number in [c.split(" ") for c in course_codes]:
            course_id = f"{name}{number}"

            # Some course number suffixes are not accepted by the API
            api_friendly_number = number
            if api_friendly_number.endswith("T"):
                api_friendly_number = api_friendly_number[:-1]
            if api_friendly_number.endswith("CO"):
                api_friendly_number = api_friendly_number[:-2]
            if api_friendly_number.endswith("ES"):
                api_friendly_number = api_friendly_number[:-2]
            if api_friendly_number.endswith("SC"):
                api_friendly_number = api_friendly_number[:-2]

            api_url = COURSES_API_URL.format(name, api_friendly_number)

            html = None
            attempts = 0
            while attempts < 3:
                try:
                    resp = session.get(api_url, timeout=10)
                    if resp.status_code == 200 and resp.text:
                        html = resp.text
                        break
                    else:
                        Logger.log_warning(f"{thread_prefix} Non-200 response {resp.status_code} for {course_id}")
                except Exception as e:
                    Logger.log_warning(f"{thread_prefix} Error fetching {course_id}: {e}")
                attempts += 1
                sleep(0.5)

            if not html:
                Logger.log_error(f"{thread_prefix} [red]Could not fetch HTML for \"{name} {number}\"[/red]")
                continue

            Logger.log_info(f"{thread_prefix} Scrapping \"{name} {number}\"")
            table_content = self.scrap_table_html(html, course_id, log_prefix=thread_prefix)
            if table_content is not None:
                Logger.log_info(f"{thread_prefix} [bright_green]Scraped \"{name} {number}\"[/bright_green]")
                self.courses.append(table_content)

                if len(self.courses) % log_interval_modulo == 0:
                    Logger.log_info(f"Scraped {len(self.courses)} courses in total.")
            else:
                Logger.log_error(f"{thread_prefix} [red]Could not scrape \"{name} {number}\"[/red]")

        Logger.log(f"{thread_prefix} [bright_green]Operation completed.[/bright_green]")

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
