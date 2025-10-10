from time import perf_counter
from tqdm import tqdm
import argparse
import os
import re

from course_scraper import CourseScraper
from driver_manager import DriverManager
from lesson_scraper import LessonScraper
from misc_scraper import MiscScraper
from course_plan_scraper import CoursePlanScraper
from logger import Logger
from constants import *

def extract_from_a(a):
    if ">" not in a:
        return a
    return a.split(">")[1].split("<")[0].strip()


def split_lesson_row(row):
    return row.replace("<tr>", "").replace(
        "</tr>", "").replace("</td>", "").replace("<br>", " ").replace("</br>", "").split("<td>")[1:]


def process_lesson_row(row):
    data = split_lesson_row(row)

    processed_row = data[0] + "|"  # CRN
    processed_row += extract_from_a(data[1]) + "|"  # Course Code
    processed_row += data[3] + "|"  # Teaching Method
    processed_row += data[4] + "|"  # Instructor
    processed_row += extract_from_a(data[5]) + "|"  # Building
    processed_row += data[6] + "|"  # Day
    processed_row += data[7] + "|"  # Time
    processed_row += data[8] + "|"  # Room
    processed_row += data[9] + "|"  # Capacity
    processed_row += data[10] + "|"  # Enrolled
    processed_row += extract_from_a(data[12])  # Major Rest.

    # Remove multiple spaces and tabs.
    return re.sub(r'\s*\|\s*', '|', processed_row.replace("\n", "").replace("\t", "")).strip()


def save_lesson_rows(rows):
    Logger.log_info("Saving Lesson Rows...")

    # Save each row to a different line.
    lines = [process_lesson_row(row) + "\n" for row in rows]
    lines.sort()
    with open(LESSONS_FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def save_course_rows(rows):
    Logger.log_info("Saving Course Rows...")

    def fix_row_compability(row: str):
        # Convert the new style to the old style for compatibility.
        return row.replace(" veya", "veya ").replace("veya  ", "veya ") \
            .replace(" ve", "ve") \
            .replace("( ", "(") \
            .replace(" )", ")") \
            .replace("MIN.", "MIN").replace("MAX.", "MAX")

    # Save each row to a different line.
    lines = [f"{fix_row_compability(row)}\n" for row in sorted(rows)]

    with open(COURSES_FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def save_course_plans(faculty_course_plans):
    # faculty_course_plans dictionary is structure example:

    # faculties['İTÜ Kuzey Kıbrıs']['Deniz Ulaştırma İşletme Mühendisliği']['2014-2015 Güz ile 2015-2016 Güz Dönemleri Arası'] = [
    #        ['COM 101', 'PHE 101', ...],
    #        ['MST 102', 'NTH 102', ...],
    #        ['MST 221', 'MST 201', ..., {'Selective': ['HSS 201', 'MST 261', ...]}, ... ]
    #   ]

    # Read existing course plans
    try:
        existing_data = {}
        if os.path.exists(COURSE_PLANS_FILE_PATH):
            Logger.log_info("Reading existing course plans...")
            current_faculty = None
            current_plan = None
            current_iter = None
            
            with open(COURSE_PLANS_FILE_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
                for line in lines:
                    if line.startswith("# "):  # Faculty
                        current_faculty = line[2:].strip()
                        existing_data[current_faculty] = {}
                    elif line.startswith("## "):  # Plan
                        current_plan = line[3:].strip()
                        existing_data[current_faculty][current_plan] = {}
                    elif line.startswith("### "):  # Iteration
                        current_iter = line[4:].strip()
                        existing_data[current_faculty][current_plan][current_iter] = []
                    elif not line.strip():  # Empty line
                        continue
                    else:  # Semester data
                        if current_faculty and current_plan and current_iter:
                            if not line.strip():  # Skip completely empty lines
                                continue
                            current_semester = existing_data[current_faculty][current_plan][current_iter]
                            if len(current_semester) < 8:  # Only add if we haven't reached 8 semesters
                                courses = line.strip().split("=")
                                current_semester.append(courses)
        
        # Merge new data with existing data
        for existing_faculty in existing_data:
            if existing_faculty not in faculty_course_plans:
                Logger.log_info(f"Merging faculty from local data: \"{existing_faculty}\"")
                faculty_course_plans[existing_faculty] = {}
            
            for existing_faculty_plan in existing_data[existing_faculty]:
                if existing_faculty_plan not in faculty_course_plans[existing_faculty]:
                    Logger.log_info(f"Merging faculty plan from local data: \"{existing_faculty}/{existing_faculty_plan}\"")
                    faculty_course_plans[existing_faculty][existing_faculty_plan] = existing_data[existing_faculty][existing_faculty_plan]
    except Exception as e:
        Logger.log_error(f"Error while reading existing course plans: {e}")
    
    # Generate Lines
    lines = []
    faculties_tqdm = tqdm(faculty_course_plans.keys())
    for faculty in faculties_tqdm:
        faculties_tqdm.set_description(f"Saving Course Plans of \"{faculty}\"")
        lines.append(f"# {faculty}\n")
        for faculty_plan in faculty_course_plans[faculty].keys():
            lines.append(f"## {faculty_plan}\n")
            for faculty_plan_iter in faculty_course_plans[faculty][faculty_plan]:
                lines.append(f"### {faculty_plan_iter}\n")

                semesters = faculty_course_plans[faculty][faculty_plan][faculty_plan_iter]
                for i, semester in enumerate(semesters):
                    line = ""
                    for j, course in enumerate(semester):
                        if type(course) is dict:
                            selective_course_title = list(course.keys())[0]
                            selective_course_codes = course[selective_course_title]
                            selective_course_title = selective_course_title.replace("\n", "")

                            if len(selective_course_codes) <= 0:
                                Logger.log_info(f"Empty selective course list found in {faculty} - {faculty_plan} - {faculty_plan_iter} - {i + 1}. semester.")
                                line += f"[{selective_course_title}*()]"
                            else:
                                line += f"[{selective_course_title}*("
                                for k, course in enumerate(selective_course_codes):
                                    line += course.replace("\n", "")

                                    if k != len(selective_course_codes) - 1:
                                        line += "|"
                                    else:
                                        line += ")]"
                        else:
                            line += course

                        if j != len(semester) - 1:
                            line += "="

                    lines.append(line + "\n")
                if len(semesters) < 8:
                    lines.append("\n" * (8 - len(semesters)))

    # Save lines.
    with open(COURSE_PLANS_FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def save_misc_data(data):
    # BUILDING DATA
    with open(BUILDING_CODES_FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(data[0])

    # PROGRAMME DATA
    with open(PROGRAMME_CODES_FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(data[1])


parser = argparse.ArgumentParser(description="Scraps data from ITU's website.")
parser.add_argument('-scrap_target', type=str,
                    help="options: [lesson, course, course_plan, misc]")

if __name__ == "__main__":
    args = parser.parse_args()
    t0 = perf_counter()

    # Even though some scrappers don't use the given driver, not creating this sometimes throws issues, especially on GitHub Actions.
    # When creating a driver, we install the Chrome WebDriver. When we create multiple drivers on different threads, the downloads
    # may conflict and cause issues. So, we create the driver here. This way, even if we don't use it, the WebDriver is installed.
    driver = DriverManager.create_driver()

    if args.scrap_target == "course":
        course_rows = CourseScraper(None).scrap_courses()
        save_course_rows(course_rows)
    elif args.scrap_target == "course_plan":
        faculty_course_plans = CoursePlanScraper(driver).scrap_course_plans()
        save_course_plans(faculty_course_plans)
    elif args.scrap_target == "misc":  # Scrap Building Codes and Programme Codes
        data = MiscScraper().scrap_data()
        save_misc_data(data)
    elif args.scrap_target == "lesson":
        lesson_rows = LessonScraper(driver).scrap_tables()
        save_lesson_rows(lesson_rows)

    DriverManager.kill_driver(driver)

    t1 = perf_counter()
    Logger.log_info(f"Scraping & Saving Completed in [green]{round(t1 - t0, 2)}[/green] seconds")
