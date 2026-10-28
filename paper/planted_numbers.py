"""The planted known-answer runs, the parser-miss bound and the second replay, as LaTeX macros.

    python3 -I paper/planted_numbers.py . > numbers_planted.tex

Reads data/verified/planted/ (specs and score.json), data/verified/cells.csv and
data/verified/reproducibility-366.txt. Plain Python, standard library only.
"""
import csv
import json
import re
import sys
from pathlib import Path

PKG = Path(sys.argv[1])
VER = PKG / "data" / "verified"
specs = {p.stem: json.loads(p.read_text()) for p in sorted((VER / "planted" / "specs").glob("*.json"))}
score = json.loads((VER / "planted" / "score.json").read_text())
assert set(specs) == set(score), "every spec has a score"
for task, s in score.items():  # the score file's expectations are the specs' own
    assert [list(x) for x in s["expected"]] == [[i["onset_cmd"], i["repair_cmd"], i["kind"]] for i in specs[task]["expected"]["intervals"]], task
intervals = sum(len(s["expected"]) for s in score.values())
found = sum(sum(list(e) in [list(f) for f in s["found"]] for e in s["expected"]) for s in score.values())
extra = sum(sum(list(f) not in [list(e) for e in s["expected"]] for f in s["found"]) for s in score.values())
repos = {t.split("__")[0] for t in score}

cells = [r for r in csv.DictReader(open(VER / "cells.csv")) if r["main"] == "True"]
miss = [r for r in cells if r["states_with_unmeasured"] not in ("", "0", "None")]
miss_clean = [r for r in miss if r["any_break"] != "True"]
broke = sum(r["any_break"] == "True" for r in cells)

repro = (VER / "reproducibility-366.txt").read_text()
compared = [int(x) for x in re.findall(r"compared (\d+) cells", repro)]

m = {
    "PlRuns": len(score), "PlRunsExact": sum(s["pass"] for s in score.values()),
    "PlIntervals": intervals, "PlIntervalsFound": found, "PlIntervalsExtra": extra, "PlRepos": len(repos),
    "ParserMissRuns": len(miss), "ParserMissNoBreak": len(miss_clean),
    "BreakAnyExact": f"{100 * broke / len(cells):.1f}", "BreakAnyParserMax": f"{100 * (broke + len(miss_clean)) / len(cells):.1f}",
    "ReproPilot": compared[0], "ReproPartial": compared[1], "ReproRuns": sum(compared),
}
print("% Planted runs, parser-miss bound and second replay (planted_numbers.py). Shares in percent.")
for k, v in m.items():
    print(f"\\newcommand{{\\{k}}}{{{v}}}")
