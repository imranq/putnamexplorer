#!/usr/bin/env bash
set -euo pipefail

bash putnam_archive/scripts/download_putnam_tex.sh
python3 putnam_archive/scripts/build_dataset.py

echo "Done. Serve with: cd putnam_archive/site && python3 -m http.server 8080"
