from bs4 import BeautifulSoup
from requests import get
from constants import *
from logger import Logger


class MiscScraper:
    def scrap_data(self):
        # There are 2 diff URLS for buildings for some fking reason, scrap them both the second one has no campus info
        building_codes = self.scrap_building_codes(BUILDING_CODES_URL) + self.scrap_building_codes(BUILDING_CODES_URL2, default_campus="")
        
        # Remove duplicates
        lines = []
        for line in building_codes.split("\n"):
            b = line.split("|")[0]  # Building code
            for existing_line in lines:
                # If building code already exists, keep the longer name (longer usually means campus is included)
                if existing_line.startswith(b + "|"):
                    if len(line) > len(existing_line):
                        lines.remove(existing_line)
                        lines.append(line)
                    break
            else:
                lines.append(line)

        return (
            "\n".join(lines).strip() + "\n",
             self.scrap_programme_codes(),
        )

    def scrap_building_codes(self, url, default_campus="Ayazağa"):
        Logger.log_info("Scraping building codes...")

        r = get(url)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        output = ""
        for row in soup.find_all("tr"):
            cells = [d.get_text().strip() for d in row.find_all("td")]

            if "(" not in cells[1] and len(default_campus) > 0:
                cells[1] += u" (${default_faculty})"

            code = cells[0].strip()

            splitted_name = cells[1].split("(")
            campus_name = splitted_name[len(splitted_name) - 1].strip().replace(")", "")
            building_name = cells[1].replace(f"({campus_name})", "").strip()

            if (campus_name == building_name):
                campus_name = default_campus

            output += f"{code}|{building_name}|{campus_name}\n"

        return output

    def scrap_programme_codes(self):
        Logger.log_info("Scraping programme codes...")

        output = ""
        for programme_type, url in PROGRAMME_CODES_URLS.items():
            r = get(url)
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, "html.parser")

            tbody = soup.find("tbody")
            if not tbody:
                return ""

            current_faculty = ""
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
                        current_faculty = cells[0].strip()
                        continue

                    programme_name = cells[0].strip().replace(f"_{programme_type}", "")
                    output += f"{programme_name}|{cells[1].strip()}|{current_faculty}|{programme_type}\n"

        return output
