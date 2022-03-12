from math import ceil
from scraper import Scraper
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import threading
from driver_manager import DriverManager
from time import perf_counter
from rich import print as rprint
import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import NewConnectionError


class CoursePlanScraper(Scraper):
    MAX_FACULTY_THREADS = 4

    def generate_dropdown_options_faculty(self, driver):
        # Check if the dropdown is already expanded.
        dropdown = driver.find_elements(By.TAG_NAME, "button")[0]
        if dropdown.get_attribute("aria-expanded") == "true":
            return

        # Clicking this generates dropdown options.
        driver.find_elements(
            By.CLASS_NAME, "filter-option-inner-inner")[0].click()
        self.wait()

    def generate_dropdown_options_program(self, driver):
        # Check if the dropdown is already expanded.
        dropdown = driver.find_elements(By.TAG_NAME, "button")[1]
        if dropdown.get_attribute("aria-expanded") == "true":
            return

        # Clicking this generates dropdown options.
        driver.find_elements(
            By.CLASS_NAME, "filter-option-inner-inner")[1].click()
        self.wait()

    def get_submit_button(self):
        return self.find_elements_by_class("button")[0]

    def scrape_program(self, url):
        soup = self.get_soup_from_url(url)

        program_list = []
        tables = soup.find_all("table", {"class": "table-responsive"})
        for table in tables:
            semester_program = []

            # First row is just the header.
            rows = table.find_all("tr")[1:]
            for row in rows:
                cells = row.find_all("td")

                # If the course is selective.
                a = cells[1].find("a")
                if a is not None:
                    selective_courses_url = url.replace(
                        url.split("/")[-1], a["href"])

                    selective_courses_title = a.get_text()

                    selective_soup = self.get_soup_from_url(
                        selective_courses_url)

                    selective_courses = []
                    selective_course_table = selective_soup.find(
                        "table", {"class": "table-responsive"})

                    if selective_course_table is not None:
                        selective_course_rows = selective_course_table.find_all(
                            "tr")

                        # First row is just the header.
                        for selective_row in selective_course_rows[1:]:
                            selective_courses.append(
                                selective_row.find("a").get_text())

                        semester_program.append(
                            {selective_courses_title: selective_courses})
                    else:
                        # TODO: Add support for selective courses like this:
                        # https://www.sis.itu.edu.tr/TR/ogrenci/lisans/ders-planlari/plan/MAK/20031081.html
                        semester_program.append(
                            {selective_courses_title: []})
                else:
                    course_code = cells[0].find("a").get_text()
                    semester_program.append(course_code)

            program_list.append(semester_program)

        return program_list

    def get_soup_from_url(self, url):
        try:
            page = requests.get(url)
            soup = BeautifulSoup(page.content, "html.parser")
            return soup
        except NewConnectionError:
            rprint(f"[bold red]Failed to load the url {url}, trying again...")
            self.wait()
            return self.get_soup_from_url(url)

    def scrap_programs(self, program_name, url):
        program_iterations = dict()
        soup = self.get_soup_from_url(url)

        # Cache the urls for the program iterations.
        for a in soup.find_all("a"):
            iteration_url = a["href"]
            inner_part = a.get_text()
            if ".html" in iteration_url:
                program_iterations[inner_part] = url + iteration_url

        def scrap_program_and_save(key, url):
            try:
                program_iterations[key] = self.scrape_program(url)
            except Exception as e:
                rprint(
                    f"[bold red]The following error was thrown while scraping a program iteration of [cyan]\"{program_name}\"[bold red]:\n\n{e}")
                self.wait()
                scrap_program_and_save(key, url)

        for program_iteration, url in program_iterations.items():
            scrap_program_and_save(program_iteration, url)

        return program_iterations

    def scrap_course_plan(self, i, url):
        driver = DriverManager.create_driver()
        driver.get(url)

        def get_faculty_dropdown_options():
            self.generate_dropdown_options_faculty(driver)
            return driver.find_elements(By.TAG_NAME, "li")[69:]

        faculty_dropdown_option = get_faculty_dropdown_options()[i]
        faculty = self.get_dropdown_option_if_available(
            faculty_dropdown_option)
        if faculty is None:
            driver.quit()
            return

        faculty_name = faculty_dropdown_option.find_element(
            By.TAG_NAME, "span").get_attribute("innerHTML")

        ActionChains(driver).move_to_element(
            faculty).click(faculty).perform()

        def get_program_dropdown_options():
            self.generate_dropdown_options_program(driver)
            return driver.find_elements(By.TAG_NAME, "li")

        faculty_plans = dict()
        for j in range(len(get_program_dropdown_options())):
            program_dropdown_option = get_program_dropdown_options()[j]
            program = self.get_dropdown_option_if_available(
                program_dropdown_option)
            if program is None:
                continue

            program_name = program_dropdown_option.find_element(
                By.TAG_NAME, "span").get_attribute("innerHTML")

            ActionChains(driver).move_to_element(
                program).click(program).perform()

            driver.find_elements(By.CLASS_NAME, "button")[0].click()
            self.wait()

            faculty_plans[program_name] = self.scrap_programs(
                program_name, driver.current_url)

            rprint(
                f"[white]Finished Scraping The Program: [cyan]\"{program_name}\"[white] Under the Faculty: [bold red]\"{faculty_name}\"")
            driver.back()

        driver.quit()
        rprint(
            f"[white]Finished Scraping The Faculty: [bold red]\"{faculty_name}\"")
        self.faculties[faculty_name] = faculty_plans

    def scrap_course_plans(self):
        def get_faculty_dropdown_options():
            self.generate_dropdown_options_faculty(self.webdriver)
            return self.find_elements_by_tag("li")[69:85]

        faculty_order = [x.find_element(By.TAG_NAME, "span").get_attribute("innerHTML")
                         for x in get_faculty_dropdown_options()]

        t0 = perf_counter()
        self.faculties = dict()
        print("====== Scraping Course Programs ======")
        faculty_count = len(get_faculty_dropdown_options())
        for j in range(ceil(faculty_count / self.MAX_FACULTY_THREADS)):
            rprint(f"[bold green]Refreshed:[green] Faculty Threads")
            threads = []
            for i in range(self.MAX_FACULTY_THREADS):
                current_index = i + j * self.MAX_FACULTY_THREADS
                if current_index >= faculty_count:
                    break

                threads.append(threading.Thread(
                    target=self.scrap_course_plan, args=(current_index, self.webdriver.current_url)))

            for t in threads:
                t.start()

            for t in threads:
                t.join()
            rprint(
                f"[bold green]Threads Finished:[green] Thread {0 + j * self.MAX_FACULTY_THREADS} - {(j + 1) * self.MAX_FACULTY_THREADS}")

        t1 = perf_counter()
        rprint(
            f"Scraping Course Plans Completed in [green]{round(t1 - t0, 2)}[white] seconds.")
        return self.faculties, faculty_order
