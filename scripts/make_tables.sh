#!/usr/bin/env bash
# make_tables.sh : rebuilds every table the figure reads, from the raw histograms in data/opens (seconds, no download)
set -euo pipefail
cd "$(dirname "$0")/.."
O=data/opens
BEFORE=$(ls $O/a.*.hist.tsv.gz | awk -F. '{d=$2} d<=20261105')
python3 scripts/tab3.py $O > data/tab44.txt
{ python3 scripts/loadcurve.py before $BEFORE
  python3 scripts/loadcurve.py nov06 $O/a.20261106.hist.tsv.gz
  python3 scripts/loadcurve.py nov11 $O/a.20261111.hist.tsv.gz
  python3 scripts/loadcurve.py nov12 $O/a.20261112.hist.tsv.gz; } > data/lc.tsv
python3 scripts/loadcurve5.py before $BEFORE > data/lc5_before.tsv
python3 scripts/loadcurve5.py nov12 $O/a.20261112.hist.tsv.gz > data/lc5_nov12.tsv
echo "tables rebuilt in data/"
