<div align="center">

![GitHub Workflow Status](https://img.shields.io/github/workflow/status/itu-helper/data/Refresh%20Lessons?label=Refreshing%20Lesson%20Data&style=flat-square)
![GitHub Workflow Status](https://img.shields.io/github/workflow/status/itu-helper/data/Refresh%20Courses%20&%20Course%20Plans?label=Refreshing%20Course%20Data&style=flat-square)
![GitHub repo size](https://img.shields.io/github/repo-size/itu-helper/data?style=flat-square)
![GitHub](https://img.shields.io/github/license/itu-helper/data?style=flat-square)
![GitHub issues](https://img.shields.io/github/issues-raw/itu-helper/data)

# **ITU Helper**

</div>
    
<div align="left">
    <img src="https://raw.githubusercontent.com/itu-helper/home/main/images/logo.png" align="right"
     alt="ITU Helper Logo" width="180" height="180">
</div>
<div align="center">

_İTÜ'lüler için İTÜ'lülerden_

_ITU Helper_ İstanbul Teknik Üniversitesi öğrencilerine yardım etmek amacıyla ön şart görselleştirme, ders planı oluşturma ve resmi İTÜ sitelerini birleştirme gibi hizmetler sağlayan bir açık kaynaklı websitesidir.

_ITU Helper_'a [_bu adresten_](https://itu-helper.github.io/home/) ulaşabilirsiniz.

</div>
<br>
<br>
<br>

# **itu-helper/data-updater**

## **Ne İşe Yarar?**

_Github Actions_ kullanarak **Veri Yenileme Aralıkları** kısmında belirtilen aralıklarda, İTÜ'nün çeşitli sitelerinden ders planlarını ve programlarını okur ve buraya _commit_'ler. Daha sonra, `assets/js` dosyasında bulunan javascript scriptleri ile veya manuel olarak bu datalara erişilebilirsiniz.

## **Veri Yenileme Aralıkları**

-   **(00:04 - 02:49) 15dk da bir**: _Lesson_'lar güncellenir.
-   **(03:00)**: _Course_'lar ve Ders Planları güncellenir.
-   **(04:04 - 23:49) 15dk da bir**: _Lesson_'lar güncellenir.

> 🛈 _Lesson_'ların daha sık güncellenmesinin nedeni kontenjan verilerinin güncel tutulmasının gerekmesidir. _Course_'ların ve Ders Planlarının güncellendiği sırada _Lesson_'ların güncellenememsi _Github Actions_'da kullandığımız _Git Auto Commit_'in repo'da değişiklik olması durumda commit atamamasındandır.

## **Verilerin İsimlendirilmesi**

-   **Dersler**
    -   _MAT 281E_ → Course
    -   _CRN: 22964, MAT 281E_ → Lesson
-   **Ders Planları**
    -   _Bilgisayar ve Bilişim Fakültesi_ → Faculty
    -   _Yapay Zeka ve Veri Mühedisliği_ → Program
    -   _2021-2022 / Güz Dönemi Öncesi_ → Iteration

## **Nasıl Kullanılır?**

### **Verileri data_manager.js ile Okumak (Javascript için)**

Öncelikle `<body>` _tag_'inin alt kısmına şu satırları yazarak scriptleri importlamanız lazım.

```html
<script src="https://cdn.jsdelivr.net/gh/itu-helper/data@master/assets/js/lesson.js"></script>
<script src="https://cdn.jsdelivr.net/gh/itu-helper/data@master/assets/js/course.js"></script>
<script src="https://cdn.jsdelivr.net/gh/itu-helper/data@master/assets/js/course_group.js"></script>
<script src="https://cdn.jsdelivr.net/gh/itu-helper/data@master/assets/js/data_manager.js"></script>
```

Daha sonra verilere erişmek için bir `DataManager` nesnesi oluşturmanız ve verileri okumanız lazım.

```javascript
// dataManager oluştur.
var dataManager = new DataManager();

// verileri oku.
dataManager.readAllTextFiles();
```

> :warning: `dataManager`'dan verilere erişmeye ilk çalıştığınızda, verilere erişildiğinde `dataManager.onFileLoad` fonksiyonu çalışıtırılacak, bu fonksiyonun varsayılan değeri `() => {}` şekildedir, sitenizde donma vs. gibi durumları önlemek için bu fonksiyonu kullanabilirsiniz.

Verileri okuduktan sonra aşağıdaki şekildeki gibi istediğiniz verilere erişebilirsiniz

```javascript
// courses içinde bütün Course'ları barındıran bir
var courses = dataManager.courses;

// semesters bir dictionary, ders planına erişmek istediğiniz dersi
// semesters["fakülte"]["program"]["iterasyon"] şekilde seçerek
// 8 elemanlı bir semester array'i alabilirsiniz. Semester array'inin
// her bir elemanı da bir Course arrayi.
var semesters = dataManager.semesters;
```

### **Verileri Manuel Okumak**

Aşağıdaki linkerden verilere erişebilir ve bu verileri kendiniz işleyebilirsiniz.

`lesson_rows.txt`: https://raw.githubusercontent.com/itu-helper/data/main/lesson_rows.txt

`course_rows.txt`: https://raw.githubusercontent.com/itu-helper/data/main/course_rows.txt

`course_plans.txt`: https://raw.githubusercontent.com/itu-helper/data/main/course_plans.txt

#### **Python Örneği**

Aşağıdaki kodda requests library'si ile CRN ile dersin [bu sayfadaki](https://www.sis.itu.edu.tr/TR/ogrenci/ders-programi/ders-programi.php?seviye=LS) satırına 6 satırda erişme gösterilmiştir.

```python
from requests import get

URL = "https://raw.githubusercontent.com/itu-helper/data/main/lesson_rows.txt"

page = get(URL)
# page.text bize her satırı, table elementleri "|" ile, table rowlaro "\n" ile ayrılmış şekilde returnler.
lines = page.text.split("\n")

# Her satırı "|" ile ayırarak tablodaki elemanlara erişiyoruz ve CRN'yi dictionary'nin key'i olacak şekilde dictionary compherension yapıyoruz.
crn_to_lesson_line = {lesson.split("|")[0] : lesson for lesson in lines}

print(crn_to_lesson_line["21516"])
# OUTPUT
# 21516|BLG 102E||Ayşe  Tosun, Ali  Çakmak|EEBEEB|Salı Perşembe |0830/1129 1530/1729 |5102 6307 |110|85|BLG, BLGE, CEN
```
