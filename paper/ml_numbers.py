"""The SWE-bench Multilingual replay's numbers, as LaTeX macros prefixed ML, by paper_numbers.py's definitions.

    python3 ml_numbers.py <multilingual report dir> > numbers_ml.tex

Reads summary.json, cells.csv, intervals.csv, models.csv, and official_check.json (our reading of the
published test logs against the official reports).
"""
import csv
import json
import sys
from pathlib import Path

report = Path(sys.argv[1])
s = json.loads((report / "summary.json").read_text())
main, ci, cells, checks = s["overall_main"], s["overall_main_ci"], s["cells"], s["checks"]
csv.field_size_limit(sys.maxsize)
cells_rows = [r for r in csv.DictReader((report / "cells.csv").open()) if r["main"] == "True"]
break_rows = [r for r in csv.DictReader((report / "intervals.csv").open()) if r["main"] == "True"]
LANGUAGE = {"preactjs": "JS", "babel": "JS", "vuejs": "JS", "facebook": "JS", "briannesbitt": "PHP", "phpoffice": "PHP",
            "laravel": "PHP", "php-cs-fixer": "PHP", "rubocop": "Ruby", "fastlane": "Ruby", "jekyll": "Ruby",
            "fluent": "Ruby"}


def pct(x, digits=0):
    return "n/a" if x is None else f"{100 * x:.{digits}f}"


def ci_text(key, digits=0):
    low, high = ci.get(key, (None, None))
    return "n/a" if low is None else f"{pct(low, digits)}--{pct(high, digits)}"


def share(rows, key, value="True"):
    rows = [r for r in rows if r.get(key) not in ("", "None")]
    return sum(r[key] == value for r in rows) / len(rows) if rows else None


def mean_of(rows, key):
    values = [float(r[key]) for r in rows if r.get(key) not in ("", "None")]
    return sum(values) / len(values) if values else None


def end_state(r):
    return r["end_broken"] if r["recorded_submitted"] == "True" else r["stop_broken"]


clean_end = [r for r in cells_rows if end_state(r) == "False"]
broken_end = [r for r in cells_rows if end_state(r) == "True"]
seen_rows = [b for b in break_rows if b["unseen"] == "False"]
unseen_rows = [b for b in break_rows if b["unseen"] == "True"]
non_syntax = [b for b in break_rows if b.get("syntax_error") == "False"]
macros = {
    "RunsTotal": cells["total"],
    "RunsDone": cells["done"],
    "RunsMain": cells["main"],
    "MainShare": pct(cells["main"] / cells["done"]) if cells["done"] else "n/a",
    "Models": len({r["submission"] for r in cells_rows}),
    "Tasks": len({r["task"] for r in cells_rows}),
    "BreakAny": pct(main["runs_with_break_any"]),
    "BreakAnyCI": ci_text("runs_with_break_any"),
    "BreakRepairClean": pct(sum(r["any_break"] == "True" and end_state(r) == "False" for r in cells_rows) / len(cells_rows)),
    "NonSyntaxRuns": pct(len({(b["submission"], b["task"]) for b in non_syntax}) / len(cells_rows)),
    "Breaks": len(break_rows),
    "SyntaxShare": pct(1 - len(non_syntax) / len(break_rows)) if break_rows else "n/a",
    "RepairedShare": pct(main["repaired_share"]),
    "Unseen": pct(main["unseen_interval_share"]),
    "UnseenCI": ci_text("unseen_interval_share"),
    "UnseenNoTests": pct(main["unseen_no_tests_share"]),
    "UnseenOpenShare": pct(sum(b["ended"] in ("", "None") for b in unseen_rows) / len(unseen_rows)) if unseen_rows else "n/a",
    "SeenOpenShare": pct(sum(b["ended"] in ("", "None") for b in seen_rows) / len(seen_rows)) if seen_rows else "n/a",
    "EndBrokenRuns": len(broken_end),
    "EndBrokenRunsShare": pct(len(broken_end) / len(cells_rows), 1),
    "EndBrokenUnseenShare": pct(main["unseen_open_breaks"] / len(broken_end)) if broken_end else "n/a",
    "UnseenOpenShareRuns": pct(main["unseen_open_breaks"] / len(cells_rows), 1),
    "Exposure": pct(main["exposure_mean"], 1),
    "ExposureCI": ci_text("exposure_mean", 1),
    "CleanEndExposure": pct(mean_of(clean_end, "exposure"), 1),
    "ExitAgree": pct(checks["exit_status_agreement"]["matched"] / checks["exit_status_agreement"]["compared"], 1),
}
pairs = checks["resolved_agreement_exact"]
both = {k: v for k, v in pairs.items() if "None" not in k}
agree = sum(v for k, v in both.items() if k.split(",")[0].split("=")[1] == k.split(",")[1].split("=")[1])
macros["VerdictAgree"] = pct(agree / sum(both.values()), 1) if both else "n/a"
exposures = [float(r["exposure_mean"]) for r in csv.DictReader((report / "models.csv").open())
             if r.get("exposure_mean") not in ("", "None") and r.get("runs") not in ("", "0")]
macros["ExposureMin"], macros["ExposureMax"] = pct(min(exposures), 1), pct(max(exposures), 1)
for tag in ("JS", "PHP", "Ruby"):
    runs = [r for r in cells_rows if LANGUAGE[r["task"].split("__")[0]] == tag]
    breaks = [b for b in break_rows if LANGUAGE[b["task"].split("__")[0]] == tag]
    macros[f"Break{tag}"] = pct(share(runs, "any_break"))
    macros[f"Unseen{tag}"] = pct(share(breaks, "unseen"))
official = report / "official_check.json"
if official.exists():
    o = json.loads(official.read_text())
    macros["OfficialChecked"] = o["checked"]
    macros["OfficialSame"] = o["same_tests"]

for name, value in macros.items():
    print(f"\\newcommand{{\\ML{name}}}{{{value}}}")
