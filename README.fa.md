# vrpbench

[English](README.md) · **فارسی**

چارچوب بنچمارک تکرارپذیر برای مسئلهٔ مسیریابی وسایل نقلیه. حل‌کننده‌های کامل را روی نمونه‌های یکسان و با بودجهٔ زمانی یکسان اجرا می‌کند و هر جواب را خودش امتیاز می‌دهد. معیار مقایسه، کیفیت جواب نهایی و زمان اجراست.

شش گونهٔ مسئله پوشش داده می‌شود:

| گونه | مسئله |
| --- | --- |
| **CVRP** | مسیریابی با ظرفیت. یک انبار، یک بازدید از هر مشتری، و بار هر مسیر حداکثر به‌اندازهٔ ظرفیت وسیله. |
| **VRPTW** | مسیریابی با پنجرهٔ زمانی. خدمت در هر مشتری باید داخل پنجرهٔ همان مشتری شروع و تمام شود. |
| **MDVRP** | مسیریابی چندانباره. هر مشتری می‌تواند از هر انبار سرویس بگیرد و انتخاب با حل‌کننده است. |
| **VRPMPD** | برداشت و تحویل ترکیبی. هر مشتری یا فقط تحویل است یا فقط برداشت، و بار بعد از هر توقف باید داخل ظرفیت بماند. |
| **PVRP** | مسیریابی دوره‌ای. هر مشتری در یک زیرمجموعهٔ مجاز از روزها بازدید می‌شود و هر روز جداگانه مسیریابی می‌گردد. |
| **SDVRP** | تحویل تفکیکی روی مجموعهٔ DIMACS R1. یک مشتری می‌تواند با بیش از یک مسیر سرویس بگیرد و مجموع مقادیر تحویلی باید برابر تقاضا باشد. |

رابط تعاملی ساخت و حل سناریو در [استودیوی مسیر](web/README.fa.md) است ([English](web/README.md)).

## فهرست

- [سیستم چگونه کار می‌کند](#سیستم-چگونه-کار-می‌کند)
- [پیش‌نیازها](#پیش‌نیازها)
- [نصب](#نصب)
- [اجرای بنچمارک](#اجرای-بنچمارک)
- [نتایج، ادامه، و اجرای موازی](#نتایج-ادامه-و-اجرای-موازی)
- [گزارش](#گزارش)
- [پیکربندی آزمایش](#پیکربندی-آزمایش)
- [حل‌کننده‌ها](#حل‌کننده‌ها)
- [داده‌ها و بهترین جواب‌های شناخته‌شده](#داده‌ها-و-بهترین-جواب‌های-شناخته‌شده)
- [بازبینی جواب‌ها](#بازبینی-جواب‌ها)
- [چیدمان مخزن](#چیدمان-مخزن)
- [آزمون‌ها](#آزمون‌ها)

## سیستم چگونه کار می‌کند

هر آزمایش یک فایل YAML است. حل‌کننده‌ها، بذرهای تصادفی، بودجهٔ زمانی، و فایل نمونه‌ها را نام می‌برد. اجراکننده این فایل را به شبکه‌ای از سلول‌ها گسترش می‌دهد. هر سلول یک نمونه، یک حل‌کننده، و یک بذر است.

```text
فایل YAML آزمایش
    -> اجراکننده (هر سلول = نمونه × حل‌کننده × بذر)
        -> بارگذار       از فایل یک Instance می‌سازد
        -> حل‌کننده      در محدودهٔ بودجه یک Solution برمی‌گرداند
        -> ارزیاب        مسافت را دوباره حساب می‌کند و شدنی بودن را بررسی می‌کند
        -> ذخیرهٔ نتیجه  یک سطر به results/results.csv اضافه می‌کند
```

پنج بسته این کار را انجام می‌دهند:

| بسته | نقش |
| --- | --- |
| `vrpbench/core` | نوع‌های مشترک `Instance` و `Solution`، و ارزیاب مستقل. |
| `vrpbench/datasets` | تجزیه‌کنندهٔ هر قالب نمونه، و جدول بهترین جواب شناخته‌شده. |
| `vrpbench/solvers` | یک آداپتور برای هر حل‌کننده، به‌علاوهٔ رجیستری‌ای که حل‌کنندهٔ تازه به آن وصل می‌شود. |
| `vrpbench/runner` | خواندن YAML، شبکهٔ سلول‌ها، ادامهٔ کار ناتمام، و کارگرهای موازی. |
| `vrpbench/results` | خروجی CSV افزایشی، و در صورت درخواست، فایل JSON مسیرها. |

ارزیاب مرجع مقدار هدف ثبت‌شده است. هر آداپتور می‌تواند هزینهٔ خودش را هم گزارش کند. ستون `obj_mismatch` اختلاف این گزارش با مسافت محاسبه‌شدهٔ دوباره است. آداپتور درست این اختلاف را نزدیک صفر نگه می‌دارد.

حل‌کنندهٔ تازه یعنی یک آداپتور که پروتکل `Solver` را رعایت کند، به‌علاوهٔ یک ورودی در `vrpbench/solvers/__init__.py`. اجراکننده، طرح CSV، و ارزیاب همان می‌مانند.

فهرست وابستگی‌ها در `pyproject.toml` است. فایل `requirements.txt` فقط یک خط دارد: `-e .[dev]`. این خط مخزن را به‌صورت قابل‌ویرایش، همراه با وابستگی توسعه (pytest)، نصب می‌کند.

## پیش‌نیازها

| پیش‌نیاز | نسخه | کاربرد |
| --- | --- | --- |
| Python | ۳.۱۱ یا جدیدتر | خود چارچوب، همهٔ حل‌کننده‌های همراه، و API وب. |
| pip | نسخهٔ جاری (نصب‌کننده آن را به‌روز می‌کند) | نصب بسته‌ها. |
| Git | هر نسخهٔ جاری | دریافت مخزن. |
| Node.js | ۲۰ یا جدیدتر | فقط استودیوی وب. راهنما: [web/README.fa.md](web/README.fa.md). |

بسته‌های `pyvrp` و `ortools` و `pyvroom` و `VRPSolverEasy` روی PyPI برای ویندوز، لینوکس، و مک چرخ (wheel) دارند. برای نصب پیش‌فرض به کامپایلر C++ نیاز نیست.

دو حل‌کننده چیزی می‌خواهند که داخل این چرخ‌ها نیست:

- **VRPSolverEasy** به کتابخانهٔ مشترک BaPCod نیاز دارد. اجرای CVRP و VRPTW که `vrpsolvereasy` در آن‌ها باشد، تا [کپی شدن این کتابخانه](#اختیاری-vrpsolvereasy-و-bapcod) شکست می‌خورد.
- **Alkaid-SDVRP** یک برنامهٔ خارجی است. اجرای SDVRP که `alkaid_sdvrp` در آن باشد، به این برنامه روی همان ماشین و به متغیر `ALKAID_SDVRP_EXECUTABLE` در همان پوسته نیاز دارد. جزئیات در [ALKAID_SETUP.md](ALKAID_SETUP.md) است.

PyVRP و OR-Tools و VROOM فایل دودویی اضافه نمی‌خواهند.

## نصب

همهٔ فرمان‌ها را از ریشهٔ مخزن اجرا کنید؛ همان پوشه‌ای که `pyproject.toml` در آن است.

اول مفسر را بررسی کنید:

```bash
python3 --version
```

در ویندوز، اگر `python3` روی `PATH` نبود:

```powershell
py -3 --version
```

نسخه باید ۳.۱۱ یا جدیدتر باشد. اگر پایتون سیستم قدیمی‌تر است، یک نسخهٔ جاری نصب کنید و محیط مجازی را با همان مفسر بسازید. بخش‌های زیر برای هر سیستم‌عامل یک راه مشخص می‌دهند.

### ویندوز

1. پایتون ۳.۱۱ یا جدیدتر را از [python.org](https://www.python.org/downloads/windows/) نصب کنید و در نصب‌کننده گزینهٔ **Add python.exe to PATH** را روشن کنید. نصب با `winget install Python.Python.3.12` همان پیش‌نیاز را برآورده می‌کند.
2. **PowerShell** را در ریشهٔ مخزن باز کنید.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

فراخوانی `.venv\Scripts\python.exe` به فعال‌سازی محیط نیاز ندارد و پیام سیاست اجرای اسکریپت در PowerShell را دور می‌زند. اگر بخواهید در همان پنجره فرمان‌های `python` و `vrpbench` در دسترس باشند:

```powershell
.\.venv\Scripts\Activate.ps1
```

اگر ویندوز از اجرای این اسکریپت خودداری کرد، برای کاربر جاری اجازهٔ اسکریپت محلی بدهید و دوباره تلاش کنید:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

در Command Prompt به‌جای `Activate.ps1` از `.venv\Scripts\activate.bat` استفاده کنید.

`run_all_benchmarks.sh` اسکریپت Bash است. آن را در [Git Bash](https://git-scm.com/download/win) یا WSL اجرا کنید، یا پنج پیکربندی کامل را خودتان در PowerShell اجرا کنید (فهرست در [اجرای بنچمارک](#اجرای-بنچمارک)).

### لینوکس

در دبیان، اوبونتو، و توزیع‌های هم‌خانواده، ماژول venv بستهٔ جداست:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

فدورا، RHEL، و توزیع‌های نزدیک:

```bash
sudo dnf install -y python3 python3-pip git
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`source .venv/bin/activate` فقط برای همان پایانه معتبر است. پایانهٔ تازه به فعال‌سازی دوباره نیاز دارد. بدون فعال‌سازی، مفسر را با `.venv/bin/python` صدا بزنید.

### مک

یک بار ابزارهای خط فرمان Xcode را نصب کنید (Git، و در صورت نیاز کامپایلر برای ساخت محلی یک چرخ):

```bash
xcode-select --install
```

پایتون ۳.۱۱ یا جدیدتر را با [Homebrew](https://brew.sh/) نصب کنید:

```bash
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

نصب‌کنندهٔ macOS در python.org هم مناسب است. محیط مجازی را با همان `python3` بسازید، نه با `/usr/bin/python3` قدیمی‌ای که بعضی نسخه‌های مک همراه دارند.

چرخ‌های Apple Silicon و اینتل جدا هستند. محیط مجازی را روی همان ماشینی بسازید که بنچمارک را اجرا می‌کند تا pip ساخت متناسب را انتخاب کند. همین قاعده برای دودویی‌های BaPCod در بخش بعد هم هست: آرشیو مک باید با معماری همان ماشین جور باشد.

`run_all_benchmarks.sh` اگر `nproc` موجود باشد از آن استفاده می‌کند. مک `nproc` ندارد، پس اسکریپت مگر با دادن تعداد کارگر، با یک کارگر ادامه می‌دهد:

```bash
chmod +x run_all_benchmarks.sh
./run_all_benchmarks.sh --threads "$(sysctl -n hw.ncpu)"
```

### تأیید نصب

با محیط مجازی فعال، یا با صدا زدن مستقیم مفسر آن:

```bash
python -c "import vrpbench, pyvrp, ortools, pyvroom; print('vrpbench', vrpbench.__version__)"
python -m pytest -q
```

چاپ `vrpbench 0.1.0` و تمام شدن pytest یعنی چارچوب و سه حل‌کنندهٔ ابتکاری وارد می‌شوند. بستهٔ `vrpsolvereasy` همراه بقیه نصب می‌شود و فقط هنگام حل، اگر کتابخانهٔ BaPCod نباشد، خطا می‌دهد.

نصب قابل‌ویرایش فرمان `vrpbench` را هم اضافه می‌کند:

```bash
vrpbench --config experiments/smoke.yaml
```

`python -m vrpbench.cli --config experiments/smoke.yaml` همان نقطهٔ ورود است.

### اختیاری: VRPSolverEasy و BaPCod

`VRPSolverEasy` روی PyPI فقط پوشش پایتون است. کتابخانهٔ بومی (`bapcod-shared.dll` در ویندوز، `.so` در لینوکس، `.dylib` در مک) را پروژهٔ BaPCod جداگانه منتشر می‌کند.

1. ساخت رایگان مخصوص سیستم‌عامل خود را از [bapcod.math.u-bordeaux.fr](https://bapcod.math.u-bordeaux.fr/) بگیرید. این ساخت از COIN-OR CLP استفاده می‌کند و برای CVRP و VRPTW در این چارچوب کافی است.
2. پوشهٔ خالی مخصوص سکو را داخل محیط مجازی پیدا کنید:

```bash
python -c "import VRPSolverEasy, pathlib; print(pathlib.Path(VRPSolverEasy.__file__).resolve().parent / 'lib')"
```

3. پوشهٔ متناظر آرشیو را در آن مسیر `lib` کپی کنید:

| سیستم‌عامل | پوشه داخل آرشیو BaPCod | مقصد زیر `lib/` |
| --- | --- | --- |
| ویندوز | `Windows` | `lib/Windows` |
| لینوکس | `Linux` | `lib/Linux` |
| مک | `Darwin` | `lib/Darwin` |

در ویندوز مقصد معمولاً `.venv\Lib\site-packages\VRPSolverEasy\lib\Windows` است. در لینوکس و مک معمولاً `.venv/lib/python3.x/site-packages/VRPSolverEasy/lib/<platform>` است. اگر این حدس‌ها فرق داشت، به خروجی فرمان بالا اعتماد کنید.

4. بار شدن کتابخانه را بررسی کنید:

```bash
python -c "from VRPSolverEasy.src import solver; solver.Model(); print('BaPCod loaded')"
```

دودویی ویندوز را فقط روی ویندوز، دودویی لینوکس را فقط روی لینوکس، و ساخت Darwin را فقط روی مک کپی کنید. کتابخانهٔ سیستم‌عامل دیگر، یا معماری پردازندهٔ دیگر، بار نمی‌شود. جزئیات، ساخت دانشگاهی CPLEX، و متن خطاها در [BAPCOD_SETUP.md](BAPCOD_SETUP.md) است.

### اختیاری: Alkaid-SDVRP

`alkaid_sdvrp` برنامهٔ رسمی Alkaid-SDVRP نسخهٔ ۱.۱ را اجرا می‌کند. این مخزن کد یا دودویی آن را همراه ندارد.

هدف `standalone` را از [HUST-Smart/Alkaid-SDVRP](https://github.com/HUST-Smart/Alkaid-SDVRP) با CMake و یک کامپایلر C++17 بسازید، سپس **در همان پایانه‌ای** که بنچمارک را شروع می‌کند مسیر برنامه را بدهید.

ویندوز (PowerShell)، بعد از ساخت با Rtools 4.4 که در [ALKAID_SETUP.md](ALKAID_SETUP.md) آمده است:

```powershell
$env:ALKAID_SDVRP_EXECUTABLE = "C:\path\to\AlkaidSD.exe"
```

لینوکس و مک:

```bash
export ALKAID_SDVRP_EXECUTABLE=/path/to/AlkaidSD
```

مقداری که در پنجرهٔ دیگری تنظیم شده باشد برای بنچمارک دیده نمی‌شود. مک همان ساخت Release با CMake را دارد که لینوکس دارد؛ کامپایلر همان است که ابزارهای خط فرمان Xcode نصب کرده‌اند.

### اختیاری: استودیوی وب

استودیو و نقشهٔ سوخت‌رسانی به extra با نام `web` و Node.js نسخهٔ ۲۰ یا جدیدتر نیاز دارند. نصب هر سیستم‌عامل در [web/README.fa.md](web/README.fa.md) است.

```bash
python -m pip install -e ".[web]"
```

در PowerShell ویندوز گیومه لازم است تا کروشه‌ها به‌عنوان wildcard تفسیر نشوند.

## اجرای بنچمارک

فرمان‌های زیر فرض می‌کنند محیط مجازی فعال است. در ویندوز `python` یعنی `.venv\Scripts\python.exe`. در لینوکس و مک یعنی `.venv/bin/python`.

```bash
# CVRP و VRPTW، هر کدام یک نمونهٔ کوچک، با PyVRP و OR-Tools
python -m vrpbench.cli --config experiments/smoke.yaml

# چندانباره، PyVRP + OR-Tools + VROOM
python -m vrpbench.cli --config experiments/mdvrp_smoke.yaml

# برداشت و تحویل ترکیبی
python -m vrpbench.cli --config experiments/vrpmpd_smoke.yaml

# مسیریابی دوره‌ای
python -m vrpbench.cli --config experiments/pvrp_smoke.yaml

# تحویل تفکیکی روی نمونه‌های نمایندهٔ DIMACS R1
python -m vrpbench.cli --config experiments/sdvrp_smoke.yaml
```

پیکربندی‌های کامل، با ده بذر و بودجهٔ ۱۰ ثانیه برای هر سلول، کنار فایل‌های smoke هستند:

| پیکربندی | محتوا |
| --- | --- |
| `experiments/benchmark.yaml` | مجموعهٔ X برای CVRP و Solomon برای VRPTW. PyVRP، OR-Tools، VROOM، VRPSolverEasy. |
| `experiments/mdvrp_benchmark.yaml` | MDVRP کورداو. PyVRP، OR-Tools، VROOM. |
| `experiments/vrpmpd_benchmark.yaml` | برداشت و تحویل ترکیبی سالحی–ناگی. |
| `experiments/pvrp_benchmark.yaml` | نمونه‌های دوره‌ای کورداو. |
| `experiments/sdvrp_benchmark.yaml` | هر ۹۵ نمونهٔ DIMACS R1. AASA-PyVRP، AASA-VROOM، Alkaid. |

هر پیکربندی کامل به همان `results/results.csv` سطر اضافه می‌کند، پس آن‌ها را پشت سر هم اجرا کنید. در لینوکس و مک، `run_all_benchmarks.sh` همین ترتیب را انجام می‌دهد.

```bash
chmod +x run_all_benchmarks.sh          # یک بار، بعد از clone
./run_all_benchmarks.sh                 # لینوکس: یک کارگر به‌ازای هر هسته
./run_all_benchmarks.sh --threads 8
./run_all_benchmarks.sh --threads 8 --force
```

در مک `--threads` را بدهید (بخش [نصب](#مک)). اسکریپت به ترتیب `.venv/bin/python`، سپس `python3`، سپس `python` را پیدا می‌کند، برای هر پیکربندی یک سربرگ زمان‌دار چاپ می‌کند، و اگر یکی شکست بخورد با کد غیرصفر خارج می‌شود.

در PowerShell ویندوز همان دنباله این است:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m vrpbench.cli --config experiments/benchmark.yaml --threads 8
& $py -m vrpbench.cli --config experiments/vrpmpd_benchmark.yaml --threads 8
& $py -m vrpbench.cli --config experiments/sdvrp_benchmark.yaml --threads 8
& $py -m vrpbench.cli --config experiments/pvrp_benchmark.yaml --threads 8
& $py -m vrpbench.cli --config experiments/mdvrp_benchmark.yaml --threads 8
```

## نتایج، ادامه، و اجرای موازی

هر سلول تمام‌شده یک سطر به `results/results.csv` اضافه می‌کند. اگر فرایند قطع شود، سطرهایی که نوشته شده‌اند می‌مانند. ستون‌های مهم برای مقایسه:

| ستون | معنی |
| --- | --- |
| `status` | `ok`، `infeasible`، یا `error`. |
| `objective` | مسافتی که خود چارچوب دوباره حساب کرده است. |
| `gap_pct` | شکاف نسبت به بهترین جواب شناخته‌شده، وقتی چنین مقداری در پرونده باشد. |
| `feasible` | آیا بررسی‌های مستقل قبول شده‌اند. |
| `runtime_s` | زمان دیوارساعتی همان حل. |
| `num_vehicles` | تعداد مسیرهای استفاده‌شده. |
| `obj_mismatch` | هزینهٔ گزارش‌شدهٔ حل‌کننده منهای هزینهٔ محاسبه‌شدهٔ دوباره. |
| `error` | متن استثنا وقتی `status` برابر `error` است. |

با `store_detail: true` در YAML، برای هر اجرا یک JSON شامل مسیرها هم در پوشهٔ نتایج نوشته می‌شود.

### ادامه

اجرای دوبارهٔ همان پیکربندی، CSV را می‌خواند و سلول‌هایی را که سطر دارند رد می‌کند.

```bash
python -m vrpbench.cli --config experiments/benchmark.yaml --threads 8
```

خط شروع، تعداد ردشده را می‌گوید؛ مثلاً: `Resume: 1430/1600 cells already in results/results.csv; running 170 remaining.`

هویت یک سلول چندتایی `(run_id, instance_name, variant, solver, seed)` است. نسخهٔ حل‌کننده و بودجهٔ زمانی جزء کلید نیستند، و سطر یک `run_id` دیگر سلول آزمایش جاری را مسدود نمی‌کند. هر وضعیتی، از جمله `error`، یعنی آن سلول انجام شده است. برای حل دوباره، `--force` (نام مستعار `--no-resume`) بدهید یا سطر را پاک کنید. `--force` سطر تازه اضافه می‌کند و فایل را خالی نمی‌کند. برای شروع از جدول خالی، `results_dir` را به پوشهٔ تازه ببرید یا CSV را حذف کنید.

### سلول‌های موازی

`--threads N` (نام مستعار `-j N`) تا `N` سلول را هم‌زمان، هر کدام در فرایند خودش، اجرا می‌کند. پیش‌فرض `1` است.

```bash
python -m vrpbench.cli --config experiments/benchmark.yaml --threads 8
```

هر کارگر همچنان تمام `time_budget_s` را دارد. `N` را حداکثر به‌اندازهٔ هسته‌های فیزیکی بگذارید. اگر `N` از `os.cpu_count()` بیشتر شود، CLI هشدار می‌دهد. با بیش از یک نخ، سطرها به ترتیب اتمام می‌رسند. مجموعهٔ سطرها با اجرای ترتیبی یکی است. استثنای یک سلول با `status=error` ذخیره می‌شود و بقیهٔ شبکه ادامه پیدا می‌کند.

## گزارش

`python-docx` همراه چارچوب نصب می‌شود. دو اسکریپت CSV را به یک گزارش Word در صفحهٔ افقی A4 تبدیل می‌کنند؛ هر گونه یک جدول:

```bash
python scripts/aggregate.py
python scripts/generate_report.py
```

`scripts/aggregate.py` فایل `results/results.csv` را می‌خواند و `results/table_data.json` را می‌نویسد. برای هر نمونه و هر حل‌کننده، میانگین هدف، شکاف، زمان، و تعداد وسیله را روی بذرهایی که `status` آن‌ها `ok` است حساب می‌کند و تعداد بذرهای موفق را ثبت می‌کند. نام نمونه‌ها نرمال می‌شوند تا یک فایل، چه با مسیر و چه با نام خالی، یک سطر بماند.

`scripts/generate_report.py` آن JSON را می‌خواند و `results/vrp_benchmark_report.docx` را می‌نویسد. گروه‌های حل‌کننده با خط ضخیم و یک رنگ ثابت جدا می‌شوند (PyVRP آبی، OR-Tools نارنجی، VROOM سبز، VRPSolverEasy بنفش، Alkaid قرمز). در هر سطر، بهترین مقدار هر معیار مقایسه‌پذیر درشت و روی ته‌رنگ همان حل‌کننده است. خط تیره یعنی آن حل‌کننده اجرای موفق نداشته است.

بعد از تغییر CSV هر دو اسکریپت را دوباره اجرا کنید. هر دو خروجی در `results/` می‌مانند.

## پیکربندی آزمایش

```yaml
run_id: baseline          # اختیاری؛ پیش‌فرض یک برچسب زمانی است
seeds: [0, 1, 2]          # یک سلول به‌ازای هر بذر
time_budget:
  base_s: 10              # ثانیه برای هر سلول
  per_node_ms: 0          # میلی‌ثانیهٔ اضافه به‌ازای هر گره؛ صفر بودجه را تخت نگه می‌دارد
solvers: [pyvrp, ortools, vroom, vrpsolvereasy]
store_detail: false       # true فایل JSON هر اجرا را هم می‌نویسد
results_dir: results
datasets:
  - variant: CVRP
    instances:
      - data/instances/X/X-n101-k25.vrp
  - variant: VRPTW
    instances:
      - data/instances/Solomon/C101.txt
  - variant: MDVRP         # لازم است: این فایل‌ها پسوند .txt را با Solomon شریک‌اند
    instances:
      - data/instances/MDVRP/old/p01.txt
  - variant: VRPMPD        # از پسوند .vrpmpd هم استنباط می‌شود
    instances:
      - data/instances/S/CMT01H.vrpmpd
  - variant: PVRP          # لازم است، به همان دلیل MDVRP
    instances:
      - data/instances/PVRP/old/p01.txt
  - variant: SDVRP
    instances:
      - data/instances/SDVRP_R1_instances/SET-1/SD1.txt
```

برای هر گروه `.txt` از نوع MDVRP یا PVRP، `variant` را صریح بنویسید. پسوند با VRPTW سالومون مشترک است و پسوند به‌تنهایی کافی نیست. SDVRP R1 از پسوندهای `.sd` و `.cri` و از فایل‌های `.txt` با شکل R1 شناخته می‌شود؛ نوشتن `variant: SDVRP` هم معتبر است.

اگر `vrpsolvereasy` در گروه MDVRP، VRPMPD، PVRP، یا SDVRP بیاید، پیکربندی رد می‌شود. نمونه‌های دوره‌ای نام‌های `pvrp_pyvrp` و `pvrp_ortools` و `pvrp_vroom` را می‌گیرند. نمونه‌های تحویل تفکیکی نام‌های `aasa_pyvrp` و `aasa_vroom` و `alkaid_sdvrp` را می‌گیرند. نام‌های سادهٔ `pyvrp` و `ortools` و `vroom` حل‌کننده‌های تک‌دوره‌ای هستند.

## حل‌کننده‌ها

| نام | روش | CVRP | VRPTW | MDVRP | VRPMPD | PVRP | SDVRP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pyvrp` | ابتکاری، جست‌وجوی همسایگی بزرگ | بله | بله | بله | بله |  |  |
| `ortools` | ابتکاری، مسیریابی OR-Tools | بله | بله | بله | بله |  |  |
| `vroom` | ابتکاری، جست‌وجوی همسایگی بزرگ | بله | بله | بله | بله |  |  |
| `vrpsolvereasy` | دقیق، شاخه و برش و قیمت (BaPCod) | بله | بله |  |  |  |  |
| `pvrp_pyvrp` | ALNS روی الگوی روزها، PyVRP برای هر روز |  |  |  |  | بله |  |
| `pvrp_ortools` | ALNS روی الگوی روزها، OR-Tools برای هر روز |  |  |  |  | بله |  |
| `pvrp_vroom` | ALNS روی الگوی روزها، VROOM برای هر روز |  |  |  |  | بله |  |
| `aasa_pyvrp` | تبدیل AASA به CVRP، سپس PyVRP |  |  |  |  |  | بله |
| `aasa_vroom` | تبدیل AASA به CVRP، سپس VROOM |  |  |  |  |  | بله |
| `alkaid_sdvrp` | ILS/RVND بومی Alkaid-SDVRP |  |  |  |  |  | بله |

OR-Tools بذر را نادیده می‌گیرد. پوشش AASA برای VROOM هم در حال حاضر بذر را نادیده می‌گیرد. `vrpsolvereasy` به کتابخانهٔ BaPCod نیاز دارد، نمونه‌های حداکثر ۱۰۲۲ گره را می‌پذیرد، و وقتی بودجهٔ زمانی برای یک روش دقیق کافی باشد اطلاع‌بخش است.

**MDVRP.** PyVRP و OR-Tools و VROOM چند انبار را مستقیم مدل می‌کنند: PyVRP با یک نوع وسیله به‌ازای هر انبار، OR-Tools با اندیس شروع و پایان برای هر وسیله، و VROOM با اندیس شروع و پایان برای هر وسیله. تخصیص باز است. فیلد حداکثر مدت مسیر در فایل‌های کورداو نادیده گرفته می‌شود تا هر سه حل‌کننده همان مسئلهٔ فقط-ظرفیت را حل کنند. به هر انبار به‌تعداد مشتریان وسیله داده می‌شود؛ جواب خوب خیلی کمتر از این تعداد را به کار می‌گیرد.

**VRPMPD.** PyVRP و VROOM روی هر توقف هم مقدار تحویل دارند و هم مقدار برداشت. OR-Tools با دو بُعد مسیریابی همان پیمایش بار را اعمال می‌کند. هر سه یک هزینهٔ ثابت بزرگ به‌ازای هر وسیله اضافه می‌کنند تا جست‌وجو اول تعداد وسیله را کم کند و بعد مسافت را. آداپتور پیش از گزارش هدف این هزینهٔ ثابت را برمی‌دارد تا `obj_mismatch` نزدیک صفر بماند.

**PVRP.** سه حل‌کنندهٔ `pvrp_*` یک پوشش ALNS مشترک دارند. جست‌وجوی بیرونی به هر مشتری یک ترکیب مجاز از روزها می‌دهد. حل‌کنندهٔ درونی بعد هر روز را جدا مسیریابی می‌کند: اگر نمونه حد مدت نداشته باشد به‌صورت CVRP، و اگر داشته باشد به‌صورت VRPTW، با حداکثر `m` وسیله در آن روز. هدف ثبت‌شده مجموع مسافت همهٔ روزهاست.

**SDVRP.** هدف، DIMACS R1 است: یک ظرفیت، تقاضای صحیح، مقدار تفکیکی صریح، ناوگان وابسته به سایت ندارد، حد مدت مسیر ندارد، و سقف سخت برای تعداد وسیله ندارد. `aasa_pyvrp` و `aasa_vroom` یک CVRP از قطعه‌های هم‌مکان با پارامتر تفکیک `p = 2` و دو سطح تقاضا می‌سازند و بعد آداپتور موجود را صدا می‌زنند. مقادیر تحویلی به همین قطعه‌ها محدود است، پس این یک تقریب از فضای کامل تفکیک است. `alkaid_sdvrp` فایل اصلی R1 را به Alkaid می‌دهد و از این کاهش استفاده نمی‌کند. هر جواب پذیرفته‌شده `route_deliveries` دارد.

## داده‌ها و بهترین جواب‌های شناخته‌شده

فایل نمونه‌ها زیر `data/instances/` هستند.

- **CVRP.** مجموعهٔ X از CVRPLIB در `data/instances/X/` (پسوند `.vrp`، مسافت اقلیدسی گردشده به نزدیک‌ترین عدد صحیح). بهترین جواب‌های شناخته‌شده از اوچوآ و همکاران، ۲۰۱۷، همراه است.
- **VRPTW.** مجموعهٔ ۱۰۰مشتری سالومون در `data/instances/Solomon/` (پسوند `.txt`، کلاس‌های C1، C2، R1، R2، RC1، RC2). مسافت، اقلیدسی خام است.
- **MDVRP.** نمونه‌های کورداو در `data/instances/MDVRP/` ([منبع](http://neumann.hec.ca/chairedistributique/data/)): `old/` مختصات صحیح دارد و `new/` مختصات اعشاری. مسافت به نزدیک‌ترین عدد صحیح گرد می‌شود. فیلدهای بسامد بازدید که مخصوص گونهٔ دوره‌ای است کنار گذاشته می‌شوند.
- **VRPMPD.** نمونه‌های S سالحی–ناگی در `data/instances/S/` (پسوند `.vrpmpd`، [منبع](http://webhotel4.ruc.dk/~keld/research/LKH-3/)). هر مشتری یا فقط تحویل است یا فقط برداشت. وسیله انبار را با همهٔ تحویل‌های مسیر ترک می‌کند؛ بار در تحویل کم و در برداشت زیاد می‌شود و بعد از هر توقف باید داخل ظرفیت بماند. پنجره‌های زمانی فایل نادیده گرفته می‌شوند. هدف واژه‌نامه‌ای است: اول وسیلهٔ کمتر، بعد مسافت کوتاه‌تر. بهترین جواب شناخته‌شده همراه نیست، پس `gap_pct` خالی می‌ماند.
- **PVRP.** نمونه‌های کورداو در `data/instances/PVRP/` ([منبع](http://neumann.hec.ca/chairedistributique/data/)): `old/p01` تا `p32` حد مدت مسیر ندارند و `new/pr01` تا `pr10` دارند. هر مشتری یک بسامد بازدید و فهرستی از ترکیب‌های مجاز روز دارد. در هر روز حداکثر `m` مسیر اجرا می‌شود. مسافت به نزدیک‌ترین عدد صحیح گرد می‌شود. هدف مجموع مسافت روزهاست و جملهٔ تعداد وسیله ندارد. بهترین جواب شناخته‌شده همراه نیست.
- **SDVRP.** DIMACS R1 در `data/instances/SDVRP_R1_instances/` (پسوندهای `.txt` و `.sd` و `.cri`؛ [منبع](http://dimacs.rutgers.edu/programs/challenge/vrp/vrpsd)): ۹۵ نمونه در چهار مجموعه. فایل عبارت است از `n Q`، یک خط با `n` تقاضا، سپس `n + 1` سطر مختصات که انبار اول است. مسافت برابر `floor(sqrt(dx² + dy²) + 0.5)` است. بهترین جواب‌های رسمی همراه است، پس `gap_pct` پر می‌شود.

`data/bks.csv` ستون‌های `instance_name` و `variant` و `bks_value` و `rounding` و `source` را نگه می‌دارد. ستون `rounding` قرارداد مقدار منتشرشده را ثبت می‌کند (`int` برای CVRP و اعشاری برای VRPTW) و بارگذار همان قرارداد را دنبال می‌کند. نبودن بهترین جواب شناخته‌شده، `gap_pct` را خالی می‌گذارد. برای MDVRP و VRPMPD و PVRP این نتیجهٔ عادی است.

## بازبینی جواب‌ها

هر جواب دوباره از ماتریس مسافت نمونه امتیاز می‌گیرد و بعد بررسی می‌شود:

- **CVRP و MDVRP.** هر مشتری یک بار بازدید می‌شود، انبار داخل مسیر نمی‌آید، و بار مسیر حداکثر به‌اندازهٔ ظرفیت است. MDVRP علاوه بر این می‌خواهد `route_depots` برای هر مسیر یک انبار واقعی نام ببرد، و مسیر از همان انبار امتیاز بگیرد.
- **VRPTW.** بررسی‌های CVRP، به‌علاوهٔ رعایت پنجرهٔ زمانی در هر توقف.
- **VRPMPD.** هر مشتری یک بار بازدید می‌شود. پیمایش بار از مجموع تحویل‌های مسیر شروع می‌شود، در تحویل کم و در برداشت زیاد می‌گردد، و بعد از هر توقف باید در بازهٔ `[0, capacity]` بماند.
- **PVRP.** هر مسیر یک روز دارد. روزهای بازدید یک مشتری باید دقیقاً با یک ترکیب مجاز برابر باشد. در هر روز حداکثر `m` مسیر اجرا می‌شود. بار مسیر حداکثر ظرفیت است. در مجموعهٔ جدید، سفر به‌علاوهٔ خدمت روی یک مسیر در محدودهٔ `max_route_duration` می‌ماند. مسافت روزها از ماتریس چارچوب جمع می‌شود.
- **SDVRP.** `route_deliveries` لازم است. کلیدهایش با مشتریان همان مسیر یکی است، هر مقدار مثبت است، بار مسیر حداکثر همان ظرفیت واحد است، و مقادیر تحویل‌شده به یک مشتری با تقاضای او برابر است.

## چیدمان مخزن

```text
vrpbench/           بسته‌های چارچوب (core, datasets, solvers, runner, results)
web/                سرویس FastAPI و استودیوی Vite
experiments/        پیکربندی‌های smoke و کامل
data/instances/     فایل‌های بنچمارک
data/bks.csv        بهترین جواب‌های شناخته‌شده
scripts/            aggregate.py و generate_report.py
tests/              مجموعهٔ pytest
results/            هنگام اجرای بنچمارک ساخته می‌شود
```

## آزمون‌ها

```bash
python -m pytest -q
```

آزمون‌هایی که به کتابخانهٔ BaPCod یا به اجرای زندهٔ Alkaid نیاز دارند، وقتی آن دودویی نباشد رد می‌شوند و مجموعهٔ پیش‌فرض سبز می‌ماند. پیکربندی‌های `experiments/*_smoke.yaml`، بعد از نصب بالا، بررسی سرتاسری سریع هستند.
