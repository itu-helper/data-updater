from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from tqdm import tqdm
from requests import get

from scraper import Scraper


class CourseScraper(Scraper):

    def __init__(self, driver, snt_courses_url):
        self.snt_courses_url = snt_courses_url
        super().__init__(driver)

    def scrap_current_table(self):
        rows = self.find_elements_by_tag("tr")

        # Filter out the header rows.
        return [row.get_attribute("outerHTML") for row in rows if row.get_attribute("class") != "table-baslik"]

    def scrap_tables(self):
        def get_submit_button():
            return self.find_elements_by_class("project__filter")[0].find_elements(By.TAG_NAME, "input")[1]

        def get_dropdown_options():
            # Expand the dropdown.
            expand_button = self.find_elements_by_tag("button")[0]
            if expand_button.get_attribute("aria-expanded") == "false":
                ActionChains(self.webdriver).move_to_element(
                    expand_button).click(expand_button).perform()

            # First index is the "Select something" option
            return self.find_elements_by_tag("ul")[14].find_elements(By.TAG_NAME, "li")[1:]

        print("====== Scraping All Courses ======")
        courses = []
        option_parent_tqdms = tqdm(range(len(get_dropdown_options())))
        for i in option_parent_tqdms:
            dropdown_option = get_dropdown_options()[i]

            course_name = dropdown_option.find_elements(By.TAG_NAME, "span")[
                0].get_attribute("innerHTML").strip()

            option_parent_tqdms.set_description(
                f"Scraping \"{course_name}\" courses")

            self.wait_until_loaded(dropdown_option)

            dropdown_option = dropdown_option.find_element(By.TAG_NAME, "a")
            ActionChains(self.webdriver).move_to_element(
                dropdown_option).click(dropdown_option).perform()

            get_submit_button().click()
            self.wait()

            courses += self.scrap_current_table()

        print("====== Scraping Additional Courses from SNT ======")

        data = get(self.snt_courses_url).text
        soup = BeautifulSoup(data, "html.parser")
        snt_course_lines = [
            a.get_text().replace("\xa0", "")
            for a in soup.find_all("a") if "SNT 1" in a.get_text() or "SNT 2" in a.get_text()
        ]

        snt_course_rows = []
        for snt in tqdm(snt_course_lines):
            splitted_snt = snt.split(" ")
            course_code = f"{splitted_snt[0]} {splitted_snt[1]}"

            course_title = ""
            for word in splitted_snt[2:]:
                course_title += word + " "

            # We use <td> to split the data in the run.py, thats why we seperate with it.
            snt_course_rows.append(
                "<td>" + course_code + "<td>" + course_title.strip() + "<td> <td> ")

        # Remove Dupes.
        snt_course_rows = list(dict.fromkeys(snt_course_rows).keys())

        return courses + snt_course_rows
