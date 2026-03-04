# Putnam Explorer Toolkit

This folder contains:

- Bulk downloader for Putnam problems and solutions TeX from `https://kskedlaya.org/putnam-archive/`
- Parser/indexer that builds a single JSON dataset
- Searchable web UI to browse by year/section/topic and open full TeX
- Gemini labeling script to classify each problem with rich metadata

## 1) Download all TeX files

```bash
bash scripts/download_putnam_tex.sh
```

Defaults to years `1985..2025` and stores files in:

- `data/raw/problems`
- `data/raw/solutions`

## 2) Build dataset for web app

```bash
python3 scripts/build_dataset.py
```

Outputs:

- `data/processed/problems.json`
- `site/problems.js`

By default, this uses `pandoc` (if installed) to also generate `problem_html`/`solution_html` for cleaner rendering.
Disable that with:

```bash
python3 scripts/build_dataset.py --no-pandoc
```

## 3) Run the searchable site

```bash
cd site
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
python3 scripts/label_topics_gemini.py \
  --input data/processed/problems.json \
  --output data/processed/problems.labeled.json \
  --model gemini-3.1-flash-lite-preview \
  --mode batch
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
python3 scripts/publish_site_data.py \
  --input data/processed/problems.labeled.json \
  --site-data site/problems.js
```

## Notes

- Some early years do not have official solution TeX in the archive; those entries remain available as problem-only.
- You can rerun the downloader safely; existing files are overwritten.
- Labeling logs are saved per run under `logs/label_runs/<RUN_ID>/`.
