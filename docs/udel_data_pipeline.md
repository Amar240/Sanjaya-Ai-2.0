# UD Catalog Data Pipeline

This project includes scripts to scrape and normalize University of Delaware catalog courses for Sanjaya AI.

## What was generated

- `data/raw/courses_raw.json` (UG scrape)
- `data/raw/courses_raw_grad.json` (GR scrape)
- `data/raw/courses_raw_combined.json` (merged)
- `data/processed/courses.json` (normalized + validated)

## Install dependencies

```powershell
python -m pip install -r scripts/requirements-scraper.txt
```

## 1) Scrape undergraduate catalog (catoid=94)

```powershell
python scripts/scrape_udel_catalog.py \
  --base-url https://catalog.udel.edu/ \
  --departments CISC BINF ACCT SCEN MATH STAT MISY FINC BUAD ECON CHEM BISC \
  --max-index-pages 60 \
  --max-courses-per-dept 35 \
  --min-delay 0.0 --max-delay 0.0 \
  --timeout 10 --retries 1 --backoff-seconds 0.1 \
  --out data/raw/courses_raw.json
```

## 2) Scrape graduate catalog (catoid=93)

```powershell
python scripts/scrape_udel_catalog.py \
  --base-url https://catalog.udel.edu/index.php?catoid=93 \
  --departments CISC BINF ACCT SCEN MATH STAT MISY FINC BUAD ECON CHEM BISC \
  --max-index-pages 60 \
  --max-courses-per-dept 35 \
  --min-delay 0.0 --max-delay 0.0 \
  --timeout 10 --retries 1 --backoff-seconds 0.1 \
  --out data/raw/courses_raw_grad.json
```

## 3) Merge raw files

```powershell
python -c "import json; from pathlib import Path; d1=json.loads(Path('data/raw/courses_raw.json').read_text(encoding='utf-8')); d2=json.loads(Path('data/raw/courses_raw_grad.json').read_text(encoding='utf-8')); out=[]; seen=set(); [out.append(c) or seen.add((c.get('source_url',''),c.get('raw_header',''))) for src in (d1,d2) for c in src.get('courses',[]) if (c.get('source_url',''),c.get('raw_header','')) not in seen]; Path('data/raw/courses_raw_combined.json').write_text(json.dumps({'meta':{'sources':['courses_raw.json','courses_raw_grad.json'],'total_unique_courses':len(out)},'courses':out}, indent=2), encoding='utf-8'); print('combined', len(out))"
```

## 4) Normalize

```powershell
python scripts/normalize_courses.py --input data/raw/courses_raw_combined.json --output data/processed/courses.json
```

## 5) Validate

```powershell
python scripts/validate_courses.py --input data/processed/courses.json
```

## 6) Generate explicit course-skill mappings

```powershell
python scripts/generate_course_skills.py `
  --courses data/processed/courses.json `
  --skills data/processed/skills_market.json `
  --roles data/processed/roles_market.json `
  --out data/processed/course_skills.json
```

## 7) Validate course-skill mappings

```powershell
python scripts/validate_course_skills.py `
  --input data/processed/course_skills.json `
  --courses data/processed/courses.json `
  --skills data/processed/skills_market.json
```

## Notes

- `DATA` did not appear as a catalog subject code in this pass. `SCEN` appears in the catalog and can be used for data-science-adjacent coverage.
- Normalizer sets `level` as:
  - `UG` when source URL has `catoid=94`
  - `GR` when source URL has `catoid=93`
- Keep `prerequisites_text` from the source for explainability, even if parsed prerequisites are incomplete.
- `course_skills.json` is now used by backend planner for explicit skill mapping.
- Normalization now extracts `prerequisites`, `corequisites`, `antirequisites`, and `offered_terms`.

## 8) Report missing prerequisites

```powershell
python scripts/report_missing_prereqs.py `
  --courses data/processed/courses.json `
  --out data/processed/missing_prereqs_report.json
```

## 9) Fetch missing prerequisite course targets

```powershell
python scripts/fetch_missing_courses.py `
  --missing-report data/processed/missing_prereqs_report.json `
  --out data/raw/courses_raw_missing_targets.json `
  --max-pages 95
```
