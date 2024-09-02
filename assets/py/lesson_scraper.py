from selenium.webdriver.common.by import By
from tqdm import tqdm

from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.common.exceptions import StaleElementReferenceException

from scraper import Scraper


class LessonScraper(Scraper):
    def scrap_current_table(self) -> list[str]:
        try:
            rows = self.find_elements_by_tag("tr")
    
            return [
                row.get_attribute("outerHTML") for row in rows
                if row.get_attribute("class") != "table-baslik"  # Filter out the header rows.
            ]
        
        # If a course has no lessons, an alert dialogue will be displayed. If that happens, return an empty row.
        except UnexpectedAlertPresentException:
            self.dismiss_alert()
            self.wait()

            return []
        except StaleElementReferenceException:
            self.wait(3)
            return self.scrap_current_table()

    def generate_dropdown_options(self):
        # Select undergraduate from the dropdown.
        for option in self.find_elements_by_tag("option"):
            if option.get_attribute("value") == "LS":
                option.click()
                self.wait()
                break

    def scrap_tables(self) -> list[str]:
        def update_dropdown_references():
            self.generate_dropdown_options()
            dropdown_options = self.webdriver.find_elements(By.TAG_NAME, "option")

            # The options we want are course codes, they start after the initial value of
            # the dropdown which is "Ders Kodu Seçiniz"
            start_index = 0
            for _ in range(20):
                for i, o in enumerate(dropdown_options):
                    if "Ders Kodu Seçiniz" in o.get_attribute("innerHTML"):
                        start_index = i + 1
                        break
                else:
                    print("Course Dropdown is not loaded yet, waiting.")
                    self.wait(5)
                    dropdown_options = self.webdriver.find_elements(By.TAG_NAME, "option")
                    continue
                break

            submit_button = self.find_elements_by_tag("button")[0]
            return dropdown_options[start_index:], submit_button

        dropdown_options, submit_button = update_dropdown_references()
        lessons, option_parent_tqdm = [], tqdm(range(0, len(dropdown_options)))

        for i in option_parent_tqdm:
            for _ in range(20):
                rows = []
                try:
                    # Check if the dropdown option is valid.
                    dropdown_option = dropdown_options[i]
                    if dropdown_option is None: return []
        
                    # Update the tqdm.
                    course_name = dropdown_option.get_attribute("innerHTML").strip()
                    option_parent_tqdm.set_description(f"Scraping \"{course_name}\" lessons - current total: {len(lessons):04}")
        
                    self.wait_until_loaded(dropdown_option)  # Wait for the dropdown option to load.
                    dropdown_option.click()  # Choose the current course from the dropdown.
        
                    submit_button.click()  # Click Submit.
        
                    # Wait for the "Kayıt bulunamadı." alert, if it occurs, skip this course.
                    alert_dismissed = self.wait_for_and_dismiss_alert(20)
                    if alert_dismissed:
                        break
        
                    # Scrap the lessons. Because the script is fast, sometimes the lessons don't load,
                    # take that into account and wait a bit if lesson count is 0.
                    for _ in range(20):
                        rows = self.scrap_current_table()
                        if len(rows) != 0:
                            break
                        self.wait()
                except UnexpectedAlertPresentException:
                    break
                
                lessons += rows
                break
        
        """def scrap_course(index: int) -> list[str]:
            # Check if the dropdown option is valid.
            dropdown_option = dropdown_options[index]
            if dropdown_option is None: return []

            # Expand the course dropdown, if it isn't already expanded.
            if not self.is_course_dropdown_expanded(course_code_dropdown):
                course_code_dropdown.click()

            # Update the tqdm.
            course_name = dropdown_option.get_attribute("innerHTML").strip()
            option_parent_tqdm.set_description(f"Scraping \"{course_name}\" lessons")

            self.wait_until_loaded(dropdown_option)

            dropdown_option.click()  # Choose the current course from the dropdown.
            self.wait()

            # Minimize the course dropdown, if it isn't already minimized.
            if self.is_course_dropdown_expanded(course_code_dropdown):
                course_code_dropdown.click()
            
            submit_button.click()  # Click Submit.

            rows = self.scrap_current_table()   # Scrap the courses.
            if len(rows) == 0:
                print(f"no rows found for {course_name}, trying again.")
                self.wait(5)
                rows = self.scrap_current_table()   # Scrap the courses.
                print(f"{len(rows)} rows found for {course_name}")
            
            self.wait()  # Wait a bit, just in case an alert appears.
            
            return rows

        print("====== Scraping All Available Lessons ======")
        for i in option_parent_tqdm:
            for _ in range(10):  # This is basically just a while True loop with some safety measures.
                try:
                    courses += scrap_course(i)   # scrap the courses.
                    break
                except UnexpectedAlertPresentException:
                    self.dismiss_alert()"""

        return lessons
