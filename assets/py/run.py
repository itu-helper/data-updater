from time import sleep, perf_counter
from rich import print as rprint
from tqdm import tqdm
import argparse

from course_scraper import CourseScraper
from driver_manager import DriverManager
from lesson_scraper import LessonScraper
from misc_scraper import MiscScraper
from course_plan_scraper import CoursePlanScraper

LESSONS_URL = "https://www.sis.itu.edu.tr/TR/ogrenci/ders-programi/ders-programi.php?seviye=LS"
COURSES_URL = "https://www.sis.itu.edu.tr/TR/ogrenci/lisans/onsartlar/onsartlar.php"
SNT_COURSES_URL = "https://sanat.itu.edu.tr/dersler/snt-kodlu-dersler"
COURSE_PLANS_URL = "https://www.sis.itu.edu.tr/TR/ogrenci/lisans/ders-planlari/ders-planlari.php?fakulte="
BUILDING_CODES_URL = "https://www.sis.itu.edu.tr/TR/obs-hakkinda/bina-kodlari.php"
PROGRAMME_CODES_URL = "https://www.sis.itu.edu.tr/TR/obs-hakkinda/lisans-program-kodlari.php"

LESSONS_FILE_NAME = "data/lesson_rows"
COURSE_FILE_NAME = "data/course_rows"
COURSE_PLANS_FILE_NAME = "data/course_plans"
BUILDING_CODES_FILE_NAME = "data/building_codes"
PROGRAMME_CODES_FILE_NAME = "data/programme_codes"

COURSE_ROWS_WARNING_LINE = "# FOLLOWING LINES WHERE ADDED FOR THE MISSING LESSONS. \n"


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
    print("Saving Lesson Rows...")

    # Save each row to a different line.
    lines = [process_lesson_row(row) + "\n" for row in rows]
    lines.sort()
    with open(f"../../{LESSONS_FILE_NAME}.txt", "w", encoding="utf-8") as f:
        f.writelines(lines)

    # If some a lesson has no coresponding course in the course_rows.txt file.
    # append them to that file.

    # Get the current course lines.
    with open(f"../../{COURSE_FILE_NAME}.txt", "r", encoding="utf-8") as f:
        current_course_lines_list = f.readlines()
        current_course_lines = f.read()

    lines_to_add = []
    course_codes_added = ""
    for row in rows:
        data = split_lesson_row(row)
        course_code = extract_from_a(data[1])
        if course_code not in current_course_lines + course_codes_added:
            line = course_code + "|"  # Course Code
            line += data[2] + "|"  # Course Name
            line += data[13] + "|"  # Course Rest.
            line += extract_from_a(data[12])  # Major Rest.

            lines_to_add.append(line + "\n")
            course_codes_added += course_code + " "

    if COURSE_ROWS_WARNING_LINE not in current_course_lines:
        lines_to_add.insert(0, COURSE_ROWS_WARNING_LINE)

    with open(f"../../{COURSE_FILE_NAME}.txt", "w", encoding="utf-8") as f:
        desired_lines = current_course_lines_list + lines_to_add
        lines_to_save = []
        course_codes = []
        for line in desired_lines:
            if "#" in line:
                course_code = lines_to_save
            else:
                course_code = line.split("|")[0]

            if course_code not in course_codes:
                lines_to_save.append(line)
                course_codes.append(course_code)

        f.writelines(lines_to_save)


def process_course_row(row):
    data = row.replace("<tr>", "").replace(
        "</tr>", "").replace("</td>", "").replace(
            "<br>", "").replace("</br>", "").replace(
                '<font color="#FF0000">', "").replace("</font>", "").split("<td>")[1:]

    processed_row = extract_from_a(data[0]) + "|"  # Course Code
    processed_row += data[1] + "|"  # Course Title
    processed_row += data[2] + "|"  # Requirements
    processed_row += data[3]  # Class Restrictions

    return processed_row


def save_course_rows(rows):
    print("Saving Course Rows...")

    # Save each row to a different line.
    lines = [process_course_row(row) + "\n" for row in rows]
    lines.sort()

    lines_to_secure = []
    try:
        with open(f"../../{COURSE_FILE_NAME}.txt", "r", encoding="utf-8") as f:
            already_saved_lines = f.readlines()
            for i, line in enumerate(already_saved_lines):
                if line == COURSE_ROWS_WARNING_LINE:
                    lines_to_secure = already_saved_lines[i:]
                    break
    except Exception:
        pass

    lines_to_secure_to_remove = []
    for line_to_secure in lines_to_secure:
        for line in lines:
            if line.split("|")[0] == line_to_secure.split("|")[0]:
                lines_to_secure_to_remove.append(line_to_secure)

    for r in lines_to_secure_to_remove:
        lines_to_secure.remove(r)

    with open(f"../../{COURSE_FILE_NAME}.txt", "w", encoding="utf-8") as f:
        f.writelines(lines + lines_to_secure)


def save_course_plans(faculties, faculty_order):
    # faculties dictionary is structure example:

    # faculties['İTÜ Kuzey Kıbrıs']['Deniz Ulaştırma İşletme Mühendisliği']
    # ['2014-2015 Güz ile 2015-2016 Güz Dönemleri Arası'] = [
    #     ['COM 101', 'PHE 101', ...],
    #     ['MST 102', 'NTH 102', ...],
    #     ['MST 221', 'MST 201', ..., {'Selective': ['HSS 201', 'MST 261', ...]},
    #     ....

    # Generate Lines
    lines = []
    faculties_tqdm = tqdm(faculty_order)
    for faculty in faculties_tqdm:
        faculties_tqdm.set_description(f"Saving Course Plans of \"{faculty}\"")
        lines.append(f"# {faculty}\n")
        for faculty_plan in faculties[faculty].keys():
            lines.append(f"## {faculty_plan}\n")
            for faculty_plan_iter in faculties[faculty][faculty_plan]:
                lines.append(f"### {faculty_plan_iter}\n")
                for i, semester in enumerate(faculties[faculty][faculty_plan][faculty_plan_iter]):
                    line = ""
                    for j, course in enumerate(semester):
                        if type(course) is dict:
                            for selective_course_title in course.keys():
                                line += f"[{selective_course_title}*("
                                for k, selective_course in enumerate(course[selective_course_title]):
                                    line += f"{selective_course}"

                                    if k != len(course[selective_course_title]) - 1:
                                        line += "|"
                                    else:
                                        line += ")]"
                        else:
                            line += course

                        if j != len(semester) - 1:
                            line += "="

                    lines.append(line + "\n")

    # Save lines.
    with open(f"../../{COURSE_PLANS_FILE_NAME}.txt", "w", encoding="utf-8") as f:
        f.writelines(lines)


def save_misc_data(data):
    # BUILDING DATA
    with open(f"../../{BUILDING_CODES_FILE_NAME}.txt", "w", encoding="utf-8") as f:
        f.writelines(data[0])

    # PROGRAMME DATA
    with open(f"../../{PROGRAMME_CODES_FILE_NAME}.txt", "w", encoding="utf-8") as f:
        f.writelines(data[1])


parser = argparse.ArgumentParser(description="Scraps data from ITU's website.")
parser.add_argument('-scrap_target', type=str,
                    help="options: [lesson, course]")

if __name__ == "__main__":
    args = parser.parse_args()
    t0 = perf_counter()

    # Create the driver.
    driver = DriverManager.create_driver()

    if args.scrap_target == "course":
        # Open the site, then wait for it to be loaded.
        driver.get(COURSES_URL)
        sleep(3)

        # Scrap and save the courses.
        course_scraper = CourseScraper(driver, SNT_COURSES_URL)
        course_rows = course_scraper.scrap_tables()
        save_course_rows(course_rows)

        print("")

        # Open the site, then wait for it to be loaded.
        driver.get(COURSE_PLANS_URL)
        sleep(3)

        # Scrap and save the courses.
        course_plan_scraper = CoursePlanScraper(driver)
        faculties, faculty_order = course_plan_scraper.scrap_course_plans()
        save_course_plans(faculties, faculty_order)

    elif args.scrap_target == "misc":
        misc_scraper = MiscScraper(
            BUILDING_CODES_URL, PROGRAMME_CODES_URL
        )

        data = misc_scraper.scrap_data()

        save_misc_data(data)

    elif args.scrap_target == "lesson":
        # Open the site, then wait for it to be loaded.
        driver.get(LESSONS_URL)
        sleep(3)

        # Scrap and save the courses.
        lesson_scraper = LessonScraper(driver)
        lesson_rows = lesson_scraper.scrap_tables()
        save_lesson_rows(lesson_rows)

    driver.quit()

    t1 = perf_counter()
    rprint(
        f"Scraping & Saving Completed in [green]{round(t1 - t0, 2)}[white] seconds")
