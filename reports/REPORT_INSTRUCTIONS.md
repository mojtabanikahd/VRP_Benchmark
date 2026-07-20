# Persian Benchmark Report Instructions

## Objective

Create a formal Persian DOCX report describing:

1. What benchmarking system was implemented.
2. Which components, solvers, datasets and configurations were used.
3. How the benchmark was conducted.
4. Which evaluation metrics were used.
5. What results were obtained.
6. What conclusions can and cannot be drawn from the results.
7. What limitations remain.

## Sources

Inspect the following sources when available:

- README and documentation files
- Source code related to benchmark execution and solver integration
- Configuration files
- CSV, JSON and Excel result files
- Execution logs
- Generated tables and figures
- Existing reports or notes

Ignore:

- Virtual environments
- Dependency directories
- Cache files
- Temporary outputs
- Obsolete experiments, unless clearly marked as relevant
- Files unrelated to benchmark implementation or results

## Evidence rules

- Do not invent implementation details or numerical results.
- Derive numerical statements from result files rather than estimating them.
- Distinguish observed results from possible explanations.
- If a detail cannot be verified, write `نیازمند تأیید کاربر` in REPORT_NOTES.md.
- Do not claim that one method is generally superior based only on a limited experiment.
- Do not rerun expensive benchmarks unless explicitly requested.
- Report failed, missing or incomplete runs when they affect interpretation.
- Mention the source file supporting each important result in REPORT_NOTES.md.
- The final DOCX should not contain internal evidence markers or file paths unless useful to the reader.

## Persian writing rules

- Use formal, natural and readable Persian.
- Avoid word-for-word translation of English expressions.
- Use Persian `ی` and `ک`.
- Use نیم‌فاصله correctly in expressions such as `می‌شود` and `حل‌کننده‌ها`.
- Define specialized English terms at their first occurrence.
- Preserve software, solver, dataset and metric names in English when translation would create ambiguity.
- Keep sentences reasonably short.
- Avoid promotional or exaggerated language.
- Use Persian digits in normal prose, but preserve technical identifiers and software versions.

## Default terminology

- Benchmarking system: سامانه ارزیابی مقایسه‌ای
- Benchmark: ارزیابی مقایسه‌ای
- Solver: حل‌کننده
- Instance: نمونه مسئله
- Runtime: زمان اجرا
- Objective value: مقدار تابع هدف
- Solution quality: کیفیت جواب
- Optimality gap: شکاف بهینگی
- Configuration: پیکربندی
- Dataset: مجموعه‌داده
- Baseline: روش مبنا
- Reproducibility: تکرارپذیری
- Vehicle Routing Problem: مسئله مسیریابی وسایل نقلیه
- CVRP: مسئله مسیریابی وسایل نقلیه با ظرفیت
- VRPTW: مسئله مسیریابی وسایل نقلیه با پنجره زمانی

## Default report structure

1. صفحه عنوان
2. خلاصه اجرایی
3. مقدمه و هدف
4. دامنه سامانه پیاده‌سازی‌شده
5. معماری و اجزای اصلی
6. حل‌کننده‌ها و نحوه یکپارچه‌سازی
7. مجموعه‌داده‌ها و نمونه‌های آزمایشی
8. معیارها و روش اجرای ارزیابی
9. نتایج
10. تحلیل نتایج
11. محدودیت‌ها
12. جمع‌بندی و پیشنهادها

Sections without sufficient evidence may be shortened or omitted.

## DOCX requirements

- The document must be right-to-left.
- Use a professional Persian font available in the environment.
- Use actual Word heading styles.
- Use restrained, professional formatting.
- Insert only informative tables and figures.
- Provide Persian captions for tables and figures.
- Repeat table headings across pages when possible.
- Include page numbers.
- Use the supplied `report/template.docx` if it exists.
- Otherwise, create a clean professional design.
- Render the DOCX to page images and visually inspect all pages.
- Correct misplaced RTL text, broken tables, clipping and poor page breaks before delivery.