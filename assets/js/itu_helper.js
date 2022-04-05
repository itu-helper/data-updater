class ITUHelper {
    LESSON_PATH = "https://raw.githubusercontent.com/itu-helper/data/main/lesson_rows.txt";
    COURSE_PATH = "https://raw.githubusercontent.com/itu-helper/data/main/course_rows.txt";
    COURSE_PLAN_PATH = "https://raw.githubusercontent.com/itu-helper/data/main/course_plans.txt";

    constructor() {
        this.#courses = [];
        this.#semesters = {};
        this.coursesDict = {};

        this.fileFetchStatus = 0;
        this.onFetchComplete = () => { };
    }

    /**
     * a list of `Course` objects.
     * 
     * ⚠️NOTE: `fetchData` must be called before accessing this property.
     */
    get courses() {
        if (this.#courses.length <= 0) {
            this.#createCourses();
            this.#courses.forEach(course => {
                this.coursesDict[course.courseCode] = course;
            });
            this.#createLessons();
            this.#connectAllCourses();
        }

        return this.#courses;
    }

    /**
    * a dictionary of dictionaries of dictionaries of arrays of `Course` & `CourseGroup` arrays.
    * Where each array represents a semester.
    * 
    * Structure:
    * 
    * `semesters["faculty name"]["programme name"]["iteration name"]` 
    * 
    * Example:
    * 
    * `semesters["Bilgisayar ve Bilişim Fakültesi"]["Yapay Zeka ve Veri Mühendisliği (% 100 İngilizce)"]["2021-2022 Güz Dönemi Sonrası"]`
    * 
    * ⚠️NOTE: `fetchData` must be called before accessing this property.
    */
    get semesters() {
        if (Object.keys(this.#semesters).length <= 0) {
            this.courses;
            this.#createSemesters();
        }

        return this.#semesters;
    }

    /**
     * fetches the data from itu-helper/data repo, calls `onFetchComplete`
     * when all files are fetches.
     */
    fetchData() {
        this.#fetchTextFile(this.LESSON_PATH, (txt) => {
            this.lesson_lines = txt.split("\n");
            this.#onTextFetchSuccess();
        });
        this.#fetchTextFile(this.COURSE_PATH, (txt) => {
            this.course_lines = txt.split("\n");
            this.#onTextFetchSuccess();
        });
        this.#fetchTextFile(this.COURSE_PLAN_PATH, (txt) => {
            this.course_plan_lines = txt.split("\n");
            this.#onTextFetchSuccess();
        });
    }

    #onTextFetchSuccess() {
        this.fileFetchStatus++;
        if (this.fileFetchStatus >= 3)
            this.onFetchComplete();
    }

    /**
     * processes `course_lines` to create the `courses` array.
     */
    #createCourses() {
        let lines = this.course_lines;
        this.#courses = [];
        this.coursesDict = {};

        for (let i = 0; i < lines.length; i++) {
            let line = lines[i].replace("\r", "");
            if (line.length == 0) continue;
            if (line[0] === "#") continue;

            let data = line.split("|");
            let course = new Course(data[0], data[1], data[2], data[3]);

            this.#courses.push(course);
        }
    }

    /**
     * processes `lesson_lines` to create lessons and add them to
     * corresponding courses of the `courses` array.
     */
    #createLessons() {
        let lines = this.lesson_lines;
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i].replace("\r", "");

            let data = line.split("|");
            let courseCode = data[1];
            let majorRest = data[9];
            let currentLesson = new Lesson(data[0], data[2], data[3], data[4],
                data[5], data[6], data[7], data[8]);

            let course = this.findCourseByCode(courseCode);
            if (!course) continue;

            course.lessons.push(currentLesson);
            course.majorRest = majorRest;
        }
    }

    /**
     * calls the `course.connectCourses` method for all courses in the `courses` array.
     */
    #connectAllCourses() {
        this.#courses.forEach(course => {
            course.connectCourses(this);
        });
    }

    /**
     * 
     * @param {string} courseCode the code of the course, Ex: "MAT 281E"
     * @returns the corresponding course in the `courses` array,
     * if the `courseCode` argument is empty returns null. If it is not empty
     * but a match cannot be found, creates a new course with the given title 
     * and the name `"Auto Generated Course"` and returns it.
     */
    findCourseByCode(courseCode) {
        let course = this.coursesDict[courseCode];
        if (course == undefined) {
            if (courseCode === "") return null;
            course = new Course(courseCode, "Auto Generated Course", "", "");
            course.requirements = [];
            this.#courses.push(course);
            this.coursesDict[courseCode] = course;

            // console.warn("[Course Generation] " + courseCode + " got auto-generated.");
        }

        return course;
    }

    /**
     * processes `course_plan_lines` to create the course plans
     * and fills it with the courses in the `courses` array.
     */
    #createSemesters() {
        let currentFaculty = "";
        let currentProgram = "";
        let currentIteration = "";
        let currentSemesters = [];
        this.#semesters = [];

        let lines = this.course_plan_lines;
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].replace("\r", "").trim();
            if (line.includes('# ')) {
                currentSemesters = [];
                let hashtagCount = line.split(' ')[0].length;
                let title = line.slice(hashtagCount + 1).trim();
                if (hashtagCount == 1) {
                    currentFaculty = title;
                    this.#semesters[currentFaculty] = {};
                }
                if (hashtagCount == 2) {
                    // Check if the last program had any iterations
                    // If not delete it.
                    if (this.#semesters[currentFaculty][currentProgram] != undefined) {
                        if (!Object.keys(this.#semesters[currentFaculty][currentProgram]).length)
                            delete this.#semesters[currentFaculty][currentProgram];
                    }

                    currentProgram = title;
                    this.#semesters[currentFaculty][currentProgram] = {};
                }
                if (hashtagCount == 3)
                    currentIteration = title;
            }
            else {
                let semester = [];
                let courses = line.split('=');
                for (let j = 0; j < courses.length; j++) {
                    let course = courses[j];
                    // Course Group
                    if (course[0] === "[") {
                        course = course.replace("[", "").replace("]", "");
                        let courseGroupData = course.split("*");
                        courseGroupData[1] = courseGroupData[1].replace("(", "").replace(")", "");
                        let selectiveCourseNames = courseGroupData[1].split('|');
                        let selectiveCourses = [];
                        selectiveCourseNames.forEach(selectiveCourseName => {
                            selectiveCourses.push(this.findCourseByCode(selectiveCourseName));
                        });
                        semester.push(new CourseGroup(selectiveCourses, courseGroupData[0]));
                    }
                    // Course
                    else {
                        let courseObject = this.findCourseByCode(course);
                        if (courseObject == null) continue;

                        semester.push(courseObject);
                    }
                }

                currentSemesters.push(semester);

                if (currentSemesters.length == 8)
                    this.#semesters[currentFaculty][currentProgram][currentIteration] = currentSemesters;
            }
        }
    }

    /**
     * @param {string} path path of the text file to fetch.
     * @param {*} onSuccess the method to call on success.
     */
    #fetchTextFile(path, onSuccess) {
        $.ajax({
            url: path,
            type: 'get',
            success: onSuccess,
        });
    }
}
