# Putnam Archive Toolkit

This folder contains:

- Bulk downloader for Putnam problems and solutions TeX from `https://kskedlaya.org/putnam-archive/`
- Parser/indexer that builds a single JSON dataset
- Searchable web UI to browse by year/section/topic and open full TeX
- Gemini labeling script to classify each problem with rich metadata

## 1) Download all TeX files

```bash
bash putnam_archive/scripts/download_putnam_tex.sh
```

Defaults to years `1985..2025` and stores files in:

- `putnam_archive/data/raw/problems`
- `putnam_archive/data/raw/solutions`

## 2) Build dataset for web app

```bash
python3 putnam_archive/scripts/build_dataset.py
```

Outputs:

- `putnam_archive/data/processed/problems.json`
- `putnam_archive/site/problems.js`

By default, this uses `pandoc` (if installed) to also generate `problem_html`/`solution_html` for cleaner rendering.
Disable that with:

```bash
python3 putnam_archive/scripts/build_dataset.py --no-pandoc
```

## 3) Run the searchable site

```bash
cd putnam_archive/site
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## 4) Label problems with Gemini

Set API key:

```bash
export GEMINI_API_KEY='YOUR_KEY_HERE'
```

Run labeling:

```bash
python3 putnam_archive/scripts/label_topics_gemini.py \
  --input putnam_archive/data/processed/problems.json \
  --output putnam_archive/data/processed/problems.labeled.json \
  --model gemini-2.0-flash-lite
```

Metadata produced per problem includes:

- `topic`, `secondary_topics`, `difficulty`, `topic_confidence`
- `problem_type`, `answer_format`
- `techniques`, `concepts`, `prerequisites`, `theorems`, `keywords`
- `estimated_solve_time_minutes`
- `requires_casework`, `requires_construction`, `uses_symmetry`, `is_multi_part`
- `difficulty_reason`
- `hints` (progressive) plus `hint_1`, `hint_2`, `hint_3`

Publish labeled data to site:

```bash
python3 putnam_archive/scripts/publish_site_data.py \
  --input putnam_archive/data/processed/problems.labeled.json
```

## Notes

- Some early years do not have official solution TeX in the archive; those entries remain available as problem-only.
- You can rerun the downloader safely; existing files are overwritten.
- You can run the web server from either `putnam_archive/` or `putnam_archive/site/`; `putnam_archive/index.html` redirects to the app.
