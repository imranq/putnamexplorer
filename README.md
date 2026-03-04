# Putnam Explorer

A local-first Putnam problem explorer with:

- Full archive ingestion (`1985..2025`) from `https://kskedlaya.org/putnam-archive/`
- Searchable browser by year/section/topic/keyword
- Collapsed-by-default solutions
- Copy actions (problem, solution, both)
- Keyboard navigation (`j/k`, `/`, `s`)
- Recently viewed row (persistent in local storage)
- LLM metadata labeling pipeline (Gemini)

## Project Structure

- `putnam_archive/`: main app + data pipeline
- `putnam_archive/site/`: static web UI
- `putnam_archive/scripts/`: download, build, label, publish scripts
- `next.md`: product roadmap and feature backlog

## Quick Start

```bash
# from repo root
python3 putnam_archive/scripts/build_dataset.py
cd putnam_archive
python3 -m http.server 8080
```

Open `http://localhost:8080`.

## Rebuild Everything

```bash
bash putnam_archive/scripts/rebuild_all.sh
```

## Label Metadata with Gemini

```bash
export GEMINI_API_KEY='YOUR_KEY'
python3 putnam_archive/scripts/label_topics_gemini.py \
  --input putnam_archive/data/processed/problems.json \
  --output putnam_archive/data/processed/problems.labeled.json \
  --model gemini-2.0-flash-lite \
  --force

python3 putnam_archive/scripts/publish_site_data.py \
  --input putnam_archive/data/processed/problems.labeled.json
```

## Keyboard Shortcuts

- `j`: next problem
- `k`: previous problem
- `/`: focus search
- `s`: toggle solution panel

## Notes

- Pandoc rendering is enabled by default during dataset build (if `pandoc` is installed).
- Some early years do not include official TeX solutions in the source archive.
