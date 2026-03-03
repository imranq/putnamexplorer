#!/usr/bin/env bash
set -euo pipefail

BASE_URL="https://kskedlaya.org/putnam-archive"
OUT_DIR="${1:-putnam_archive/data/raw}"
START_YEAR="${2:-1985}"
END_YEAR="${3:-2025}"

mkdir -p "$OUT_DIR/problems" "$OUT_DIR/solutions"

for year in $(seq "$START_YEAR" "$END_YEAR"); do
  p_url="$BASE_URL/${year}.tex"
  s_url="$BASE_URL/${year}s.tex"

  if curl -fsSL "$p_url" -o "$OUT_DIR/problems/${year}.tex"; then
    echo "Downloaded problems: $year"
  else
    echo "Missing problems: $year"
  fi

  if curl -fsSL "$s_url" -o "$OUT_DIR/solutions/${year}s.tex"; then
    echo "Downloaded solutions: $year"
  else
    echo "No solutions tex: $year"
  fi
done
