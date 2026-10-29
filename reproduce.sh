#!/usr/bin/env bash
# Rebuild every numbers file of the paper into out/ and compare each with the copy the paper was built from.
# Python 3.11 or newer, standard library only; about 15 seconds. Writes only inside out/, except that
# paper/review2_numbers.py rewrites paper/table_*.tex in place with identical content.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out out/wr/judge
python3 judge/analyse3.py judge 0.0988 0.0486 > out/judge_summary3.json   # Table III; 0.0988 = 992/10,037 (baseline_onset.json)
cp -R judge/whole_run/. out/wr/judge/
python3 judge/whole_run/analyse_full.py out/wr > out/judge_summary_full.json
python3 paper/paper_numbers.py data/verified > out/numbers.tex
python3 paper/ml_numbers.py data/multilingual > out/numbers_ml.tex
(cd paper && python3 review_numbers.py ../data/verified ../data/multilingual) > out/numbers_review.tex
python3 paper/extra_numbers.py . > out/numbers_extra.tex
python3 paper/planted_numbers.py . > out/numbers_planted.tex
python3 paper/review2_numbers.py . > out/numbers_review2.tex
python3 paper/review3_numbers.py . > out/numbers_review3.tex
python3 paper/review4_numbers.py . > out/numbers_review4.tex
status=0
for f in out/numbers*.tex; do
  cmp -s "$f" "paper/$(basename "$f")" || { echo "differs from the paper's copy: $f"; status=1; }
done
python3 humancheck/score.py "$(cat humancheck/labels_author.txt)"
if [ "$status" -eq 0 ]; then echo "Every numbers file matches the copy the paper was built from."; fi
exit "$status"
