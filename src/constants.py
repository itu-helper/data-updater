# === URLS ===
LESSONS_URL = "https://obs.itu.edu.tr/public/DersProgram"
COURSES_URL = "https://www.sis.itu.edu.tr/TR/ogrenci/lisans/ders-bilgileri/ders-bilgileri.php"
COURSES_API_URL = "https://obs.itu.edu.tr/public/DersBilgi/DersBilgiSearch?bransKodu={0}&dersNo={1}"
COURSE_PLAN_URLS = [
    "https://obs.itu.edu.tr/public/DersPlan/DersPlanlariList?programKodu={0}_LS&planTipiKodu=lisans",       # Undergraduate
    "https://obs.itu.edu.tr/public/DersPlan/DersPlanlariList?programKodu={0}_LS&planTipiKodu=uolp",         # UOLP
    "https://obs.itu.edu.tr/public/DersPlan/DersPlanlariList?programKodu={0}_OL&planTipiKodu=on-lisans",    # Graduate
]
BUILDING_CODES_URL = "https://www.sis.itu.edu.tr/TR/obs-hakkinda/bina-kodlari.php"
BUILDING_CODES_URL2 = "https://obs.itu.edu.tr/public/GenelTanimlamalar/BinaKodlariList"
PROGRAMME_CODES_URL = "https://www.sis.itu.edu.tr/TR/obs-hakkinda/lisans-program-kodlari.php"

# === FILE NAMES ===
LESSONS_FILE_PATH = "data/lessons.psv"
COURSES_FILE_PATH = "data/courses.psv"
COURSE_PLANS_FILE_PATH = "data/course_plans.txt"
BUILDING_CODES_FILE_PATH = "data/building_codes.psv"
PROGRAMME_CODES_FILE_PATH = "data/programme_codes.psv"

# === OTHER ===
MAX_THREAD_COUNT = 4
