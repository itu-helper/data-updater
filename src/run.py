from time import perf_counter
from tqdm import tqdm
import argparse

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

    return processed_row


def save_lesson_rows(rows):
    Logger.log_info("Saving Lesson Rows...")

    # Save each row to a different line.
    lines = [process_lesson_row(row) + "\n" for row in rows]
    lines.sort()
    with open(LESSONS_FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def save_course_rows(rows):
    Logger.log_info("Saving Course Rows...")

    # Save each row to a different line.
    lines = [f"{row}\n" for row in sorted(rows)]

    with open(COURSES_FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def save_course_plans(faculty_course_plans):
    # faculty_course_plans dictionary is structure example:

    # faculties['İTÜ Kuzey Kıbrıs']['Deniz Ulaştırma İşletme Mühendisliği']['2014-2015 Güz ile 2015-2016 Güz Dönemleri Arası'] = [
    #        ['COM 101', 'PHE 101', ...],
    #        ['MST 102', 'NTH 102', ...],
    #        ['MST 221', 'MST 201', ..., {'Selective': ['HSS 201', 'MST 261', ...]}, ... ]
    #   ]

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
    driver = None

    # Scrap Courses
    if args.scrap_target == "course":
        course_rows = CourseScraper(None).scrap_courses()
        save_course_rows(course_rows)
    # Scrap Course Plans
    elif args.scrap_target == "course_plan":
        driver = DriverManager.create_driver()
        faculty_course_plans = CoursePlanScraper(driver).scrap_course_plans()
        save_course_plans(faculty_course_plans)
    # Scrap Building Codes and Programme Codes
    elif args.scrap_target == "misc":
        data = MiscScraper().scrap_data()
        save_misc_data(data)
    # Scrap Lessons
    elif args.scrap_target == "lesson":
        driver = DriverManager.create_driver()
        lesson_rows = LessonScraper(driver).scrap_tables()
        save_lesson_rows(lesson_rows)

    if driver is not None:
        DriverManager.kill_driver(driver)

    t1 = perf_counter()
    Logger.log_info(f"Scraping & Saving Completed in [green]{round(t1 - t0, 2)}[/green] seconds")
