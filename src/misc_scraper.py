from bs4 import BeautifulSoup
from requests import get
from constants import *
from logger import Logger


class MiscScraper:
    def scrap_data(self):
        return (
            self.scrap_building_codes(BUILDING_CODES_URL),
            self.scrap_programme_codes(PROGRAMME_CODES_URL),
        )

    def scrap_building_codes(self, url):
        Logger.log_info("Scraping building codes...")

        r = get(url)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        output = ""
        for row in soup.find_all("tr"):
            cells = [d.get_text().strip() for d in row.find_all("td")]

            if "(" not in cells[1]:
                cells[1] += u" (Ayazağa)"

            code = cells[0].strip()

            splitted_name = cells[1].split("(")
            campus_name = splitted_name[len(
                splitted_name) - 1].strip().replace(")", "")
            building_name = cells[1].replace(f"({campus_name})", "").strip()

            output += f"{code}|{building_name}|{campus_name}\n"

        return output

    def scrap_programme_codes(self, url):
        Logger.log_info("Scraping programme codes...")

        r = get(url)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        tbody = soup.find("tbody")
        if not tbody:
            return ""

        output = ""
        current_faculty_code, current_faculty = "", ""
        last_item_is_broken_row, broken_row_cells = False, []
        for element in tbody.children:
            # Skip text nodes and non-tag elements
            if not hasattr(element, "name") or element.name is None:
                continue
            
            # Handle proper rows
            if element.name == "tr":
                cells = [d.get_text().strip() for d in element.find_all("td")]
                
                # There are some empty rows in the table, skip them.
                if not cells:
                    continue

                # Found a faculty row.
                if len(cells) == 1:
                    faculty = cells[0].strip()
                    current_faculty_code = faculty.split("-")[0]
                    current_faculty = faculty.replace(f"{current_faculty_code}-", "").strip()
                    continue

                output += f"{cells[0].strip()}|{cells[1].strip()}|{current_faculty}|{current_faculty_code}\n"
            
            # Handle broken rows (https://github.com/itu-helper/data-updater/issues/4)
            if element.name == "td":
                if not last_item_is_broken_row:
                    broken_row_cells = []

                broken_row_cells.append(element.get_text().strip())
                last_item_is_broken_row = True
                
                # Only process if we have exactly 2 cells (course code and name)
                if len(broken_row_cells) == 2:
                    output += f"{broken_row_cells[0].strip()}|{broken_row_cells[1].strip()}|{current_faculty}|{current_faculty_code}\n"
                    broken_row_cells = []
            else:
                last_item_is_broken_row = False

        return output
