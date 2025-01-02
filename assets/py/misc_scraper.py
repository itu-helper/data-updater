from bs4 import BeautifulSoup
from requests import get
from constants import *


class MiscScraper:
    def scrap_data(self):
        return (
            self.scrap_building_codes(BUILDING_CODES_URL),
            self.scrap_programme_codes(PROGRAMME_CODES_URL),
        )

    def scrap_building_codes(self, url):
        r = get(url)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser", from_encoding="utf-8")

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
        r = get(url)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser", from_encoding="utf-8")

        output = ""
        for row in soup.find_all("tr"):
            cells = [d.get_text().strip() for d in row.find_all("td")]
            if len(cells) != 2:
                continue

            output += f"{cells[0].strip()}|{cells[1].strip()}\n"

        return output
