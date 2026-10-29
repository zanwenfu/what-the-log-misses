"""The second review round's analyses for "What the Log Misses", as LaTeX macros (prefix Rx), plus two tables.

    python3 -I paper/review2_numbers.py <package dir> > paper/numbers_review2.tex

<package dir> is the replication package (README.md, data/, judge/, paper/). Plain Python, standard library only, one
process; a few seconds. Besides the macros on standard output it writes two LaTeX table bodies (booktabs only, no
float wrapper): paper/table_syntax_era.tex (uses the Rx macros) and paper/table_models.tex (generated literals).

First the script recomputes, by the paper's own definitions (paper_numbers.py, review_numbers.py, extra_numbers.py,
judge/analyse3.py), every number it builds on and stops unless each equals the package's numbers*.tex. Then:
  1. Syntax errors x scaffold version (1.x = "_mini-v1.", 2.x = "_mini-v2." in the submission name): for breaks that are
     syntax errors and those that are not, the share of runs with such a break, the share of such breaks unseen, and
     the share of runs ending on such an unseen break.
  2. Exposure from each run's first edit (cells.csv exposure_after_first_edit, mean over the runs that edit): overall
     interval; the Qwen3-Coder / Gemini 2.5 Pro pair (paper_numbers.PAIRS[0]); the close pairs behind \\PairsAlike.
  3. Runs stopped by the step or cost limit (exit status LimitsExceeded, nothing submitted) and the code they left.
  4. Intervals for \\RvTransient, \\RvLastingRuns and \\RvLastingUnseen (review_numbers.py's definitions).
  5. The per-model table (paper/table_models.tex).
  6. A taxonomy of the non-syntax breaks by error: not computed. The Verified break table keeps no error text, and no
     older local report holds it for the same breaks (the reason is printed as a comment in the output).
  7. "Syntax check first, then a judge" on Table II's 288 sampled commands, joined exactly to the break table.
Every interval is the paper's task bootstrap: 2,000 resamples of the tasks, seed 20261023, a fresh generator per
statistic, percentile interval (paper_numbers.boot_ci).
"""
import csv
import itertools
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

PKG = Path(sys.argv[1])
VER = PKG / "data" / "verified"
SEED, BOOT = 20261023, 2000
OLD, NEW = "_mini-v1.", "_mini-v2."
csv.field_size_limit(sys.maxsize)


# ---------------------------------------------------------------- the package's own numbers, to check against
def read_macros(path):
    """\\newcommand{\\Name}{value}, with or without a trailing ' % comment' (numbers_extra.tex has one)."""
    out = {}
    for line in path.read_text().splitlines():
        if line.startswith("\\newcommand{\\"):
            name, rest = line[len("\\newcommand{\\"):].split("}{", 1)
            out[name] = rest.split("} % ", 1)[0] if "} % " in rest else rest[:-1]
    return out


paper = {}
for name in ("numbers.tex", "numbers_review.tex", "numbers_extra.tex"):
    for key, value in read_macros(PKG / "paper" / name).items():
        assert key not in paper, f"macro {key} defined twice"
        paper[key] = value
checks = []


def check(name, value):
    """Stop unless our recomputation equals the paper's macro."""
    if str(value) != paper[name]:
        sys.exit(f"MISMATCH {name}: ours {value!r}, paper {paper[name]!r}")
    checks.append(name)


def pct(x, digits=0):
    return f"{100 * x:.{digits}f}"


def ci_text(pair, digits=0):
    return f"{pct(pair[0], digits)}--{pct(pair[1], digits)}"


def wilson(k, n, z=1.96):
    p, den = k / n, 1 + z * z / n
    centre, half = (p + z * z / (2 * n)) / den, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


def percentile_ci(values):
    values = sorted(v for v in values if v is not None)
    return values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]


def boot(stat, units, seed=SEED, draws=BOOT):
    """Percentile 95% interval of stat(resampled units), a fresh generator per statistic (paper_numbers.boot_ci)."""
    rng = random.Random(seed)
    return percentile_ci(stat([rng.choice(units) for _ in units]) for _ in range(draws))


# ---------------------------------------------------------------- tables, read as the paper's scripts read them
cells = {(r["submission"], r["task"]): r for r in csv.DictReader((VER / "cells.csv").open()) if r["main"] == "True"}
breaks = [b for b in csv.DictReader((VER / "intervals.csv").open()) if b["main"] == "True"]
model_list = list(csv.DictReader((VER / "models.csv").open()))
models = {r["submission"]: r for r in model_list}
summary = json.loads((VER / "summary.json").read_text())["overall_main"]
TASKS = sorted({k[1] for k in cells})
states = defaultdict(list)  # (submission, task) -> [(seq, command, status)], the final snapshot left out
for r in csv.DictReader((VER / "states.csv").open()):
    if (r["submission"], r["task"]) in cells and r["trigger"] != "final":
        states[(r["submission"], r["task"])].append((int(r["seq"]), int(r["command"]), r["status"]))
for v in states.values():
    v.sort()


def end_state(r):
    return r["end_broken"] if r["recorded_submitted"] == "True" else r["stop_broken"]


def is_open(b):
    return b["ended"] in ("", "None")


def has(value):
    return value not in ("", "None")


def only_regression(r):
    """review_numbers.py: failed on the leaderboard, ends broken, and every fix test passes at the end."""
    return (r["leaderboard_resolved"] == "False" and end_state(r) == "True" and has(r["f2p_total"])
            and int(r["f2p_total"]) > 0 and int(r["f2p_passing_end"]) == int(r["f2p_total"]))


open_break = defaultdict(list)
for b in breaks:
    if is_open(b):
        open_break[(b["submission"], b["task"])].append(b)
assert all(len(v) == 1 for v in open_break.values()), "a run with two open breaks"


def aggregate(keys, keep=lambda b: True, only_reg_needs_break=False):
    """Per-task counts for the runs in keys and those of their breaks that keep() admits (extra_numbers.aggregate)."""
    keys = set(keys)
    a = defaultdict(Counter)
    for k in sorted(keys):
        r, t = cells[k], k[1]
        a[t]["runs"] += 1
        a[t]["exp"] += float(r["exposure"])
        if has(r["exposure_after_first_edit"]):
            a[t]["efe"] += float(r["exposure_after_first_edit"])
            a[t]["edited"] += 1
        a[t]["failed"] += r["leaderboard_resolved"] == "False"
        ob = [b for b in open_break.get(k, []) if keep(b)]
        a[t]["end_unseen"] += any(b["unseen"] == "True" for b in ob)
        a[t]["only_reg"] += only_regression(r) and (not only_reg_needs_break or bool(ob))
    use = [b for b in breaks if (b["submission"], b["task"]) in keys and keep(b)]
    for k in sorted({(b["submission"], b["task"]) for b in use}):
        a[k[1]]["break_runs"] += 1
    for b in use:
        if b["unseen"] in ("True", "False"):
            a[b["task"]]["breaks"] += 1
            a[b["task"]]["unseen"] += b["unseen"] == "True"
    return a


STATS = {  # name: (numerator, denominator) of a pooled ratio over a task multiset
    "BreakAny": ("break_runs", "runs"), "Unseen": ("unseen", "breaks"), "EndUnseen": ("end_unseen", "runs"),
    "OnlyReg": ("only_reg", "failed"), "Exposure": ("exp", "runs"), "FirstEdit": ("efe", "edited"),
}


def stat(a, name, sample=TASKS):
    num, den = STATS[name]
    d = sum(a[t][den] for t in sample)
    return sum(a[t][num] for t in sample) / d if d else None


def stat_ci(a, name):
    return boot(lambda smp: stat(a, name, smp), TASKS)


def total(a, key):
    return sum(a[t][key] for t in TASKS)


macros, notes = {}, []
ALL = aggregate(cells)
SYN = lambda b: b["syntax_error"] == "True"  # noqa: E731
NOSYN = lambda b: b["syntax_error"] == "False"  # noqa: E731
era_keys = {tag: [k for k in cells if era in k[0]] for era, tag in ((OLD, "Old"), (NEW, "New"))}
assert len(era_keys["Old"]) + len(era_keys["New"]) == len(cells)

# ---------------------------------------------------------------- 0. the numbers this builds on, reproduced
check("RunsMain", f"{len(cells):,}")
check("Breaks", f"{len(breaks):,}")
check("Exposure", pct(stat(ALL, "Exposure"), 1))
check("ExposureFirstEdit", pct(stat(ALL, "FirstEdit"), 1))
assert abs(stat(ALL, "FirstEdit") - summary["exposure_after_first_edit_mean"]) < 1e-12
report_ci = json.loads((VER / "summary.json").read_text())["overall_main_ci"]
notes.append(f"\\ExposureCI ({paper['ExposureCI']}) is the replay report's own interval (summary.json), not this "
             f"script's task bootstrap, which gives {ci_text(stat_ci(ALL, 'Exposure'), 1)} for exposure; the report's own "
             f"interval for first-edit exposure is {ci_text(report_ci['exposure_after_first_edit_mean'], 1)}.")
check("SyntaxShare", pct(sum(SYN(b) for b in breaks) / len(breaks)))
assert all(b["syntax_error"] in ("True", "False") for b in breaks)
NS = aggregate(cells, NOSYN, only_reg_needs_break=True)
check("NonSyntaxRuns", pct(stat(NS, "BreakAny")))
check("NonSyntaxUnseen", pct(stat(NS, "Unseen")))
check("XtNoSynEndUnseenRunsN", total(NS, "end_unseen"))
check("XtNoSynOnlyReg", total(NS, "only_reg"))
check("XtEndUnseenRunsN", total(ALL, "end_unseen"))
ERA = {tag: aggregate(keys) for tag, keys in era_keys.items()}
for tag in ("Old", "New"):
    check(f"Era{tag}Break", pct(stat(ERA[tag], "BreakAny")))
    check(f"Era{tag}Unseen", pct(stat(ERA[tag], "Unseen")))
    check(f"XtEra{tag}EndUnseen", pct(stat(ERA[tag], "EndUnseen"), 1))
# The pair the text compares (paper_numbers.PAIRS[0]: same scaffold release 1.0.0, alike in resolve rate).
QWEN, GEMINI = "20250802_mini-v1.0.0_qwen3-coder-480b-a35b-instruct", "20250726_mini-v1.0.0_gemini-2.5-pro"
exp_by, efe_by = defaultdict(dict), defaultdict(dict)
for (s, t), r in sorted(cells.items()):
    exp_by[s][t] = float(r["exposure"])
    if has(r["exposure_after_first_edit"]):
        efe_by[s][t] = float(r["exposure_after_first_edit"])


def pair_ratio(table, smp):
    a = [table[QWEN][t] for t in smp if t in table[QWEN]]
    b = [table[GEMINI][t] for t in smp if t in table[GEMINI]]
    return statistics.mean(a) / statistics.mean(b) if a and b and statistics.mean(b) else None


check("XtPairRatio", f"{pair_ratio(exp_by, TASKS):.1f}")
check("PairAFirstEditExposure", pct(statistics.mean(efe_by[QWEN].values())))
check("PairBFirstEditExposure", pct(statistics.mean(efe_by[GEMINI].values())))
for s, m in models.items():
    assert abs(statistics.mean(exp_by[s].values()) - float(m["exposure_mean"])) < 1e-12, s
    assert abs(statistics.mean(efe_by[s].values()) - float(m["exposure_after_first_edit_mean"])) < 1e-12, s
# The close pairs (paper_numbers.py, "R4 without hand-picking"): same release string, resolve rates within 0.03.
model_rows = [r for r in model_list if has(r.get("exposure_mean", "")) and has(r.get("resolve_rate_leaderboard", ""))]
alike = []
for a, b in itertools.combinations(model_rows, 2):
    if a["submission"].split("_")[1] != b["submission"].split("_")[1]:
        continue
    if abs(float(a["resolve_rate_leaderboard"]) - float(b["resolve_rate_leaderboard"])) > 0.03:
        continue
    alike.append((a["submission"], b["submission"]))
check("PairsAlike", len(alike))


def fold(pair, key):
    hi, lo = sorted((float(models[s][key]) for s in pair), reverse=True)
    return hi / max(lo, 1e-9)


check("PairsTwoFold", sum(fold(p, "exposure_mean") >= 2 for p in alike))


# Transient and lasting breaks (review_numbers.py).
def transient(b):
    if b["ended"] != "clean" or not has(b["repair"]):
        return False
    later = sorted({c for _, c, _ in states.get((b["submission"], b["task"]), []) if c > int(b["onset"])})
    return bool(later) and later[0] == int(b["repair"])


lasting = [b for b in breaks if not transient(b)]
lasting_judged = [b for b in lasting if b["unseen"] in ("True", "False")]
check("RvTransient", pct(1 - len(lasting) / len(breaks)))
check("RvLastingRuns", pct(len({(b["submission"], b["task"]) for b in lasting}) / len(cells)))
check("RvLastingUnseen", pct(sum(b["unseen"] == "True" for b in lasting_judged) / len(lasting_judged)))
# The step or cost limit (paper_numbers.py) and the report's own count of it.
limit = sorted(k for k, r in cells.items() if r["recorded_submitted"] == "False"
               and r["recorded_exit_status"] == "LimitsExceeded" and r["stop_broken"] in ("True", "False"))
limit_broken = [k for k in limit if cells[k]["stop_broken"] == "True"]
check("LimitStopRuns", len(limit))
check("LimitStopBroken", pct(len(limit_broken) / len(limit)))
check("LimitStopCI", ci_text(wilson(len(limit_broken), len(limit))))
check("LimitStopModels", len({k[0] for k in limit}))
assert len(limit) == summary["limit_stop_runs"] and len(limit_broken) / len(limit) == summary["limit_stop_broken_share"]

# ---------------------------------------------------------------- 1. syntax errors x scaffold version
ERA_NAME = {"Old": "1.x", "New": "2.x"}
SPLIT = {}
for tag in ("Old", "New"):
    for kind, keep, label in (("Syn", SYN, "syntax-error"), ("NoSyn", NOSYN, "non-syntax")):
        a = aggregate(era_keys[tag], keep)
        SPLIT[tag, kind] = a
        era = ERA_NAME[tag]
        m = f"Rx{tag}{kind}"
        macros[f"{m}Breaks"] = (total(a, "breaks"), f"Scaffold {era}: {label} breaks")
        macros[f"{m}Runs"] = (pct(stat(a, "BreakAny")), f"Scaffold {era}: share of its {total(a, 'runs')} runs with a "
                              f"{label} break")
        macros[f"{m}RunsCI"] = (ci_text(stat_ci(a, "BreakAny")), "Same, task bootstrap")
        macros[f"{m}Unseen"] = (pct(stat(a, "Unseen")), f"Scaffold {era}: share of its {label} breaks unseen")
        macros[f"{m}UnseenCI"] = (ci_text(stat_ci(a, "Unseen")), "Same, task bootstrap")
        macros[f"{m}EndUnseenN"] = (total(a, "end_unseen"), f"Scaffold {era}: runs ending on an unseen {label} break")
        macros[f"{m}EndUnseen"] = (pct(stat(a, "EndUnseen"), 1), f"Scaffold {era}: share of its runs ending on an "
                                   f"unseen {label} break")
        macros[f"{m}EndUnseenCI"] = (ci_text(stat_ci(a, "EndUnseen"), 1), "Same, task bootstrap")
    # The two kinds add up to the era's own counts (a run ends on at most one break).
    assert all(SPLIT[tag, "Syn"][t]["end_unseen"] + SPLIT[tag, "NoSyn"][t]["end_unseen"] == ERA[tag][t]["end_unseen"]
               for t in TASKS)
    assert total(SPLIT[tag, "Syn"], "breaks") + total(SPLIT[tag, "NoSyn"], "breaks") == total(ERA[tag], "breaks")
assert sum(total(SPLIT[t, "NoSyn"], "end_unseen") for t in ("Old", "New")) == total(NS, "end_unseen")

ROWS = (("Runs with such a break", "", "Runs"), ("Of those breaks, unseen", "", "Unseen"),
        ("Runs ending on such", "an unseen break", "EndUnseen"))  # the long label runs on into its interval row
COLS = (("Old", "Syn"), ("Old", "NoSyn"), ("New", "Syn"), ("New", "NoSyn"))
lines = ["% Generated by paper/review2_numbers.py; needs \\input{numbers_review2} (and booktabs). Syntax: breaks that",
         "% are syntax errors; Other: all other breaks. Shares in percent of the scaffold version's runs (first and",
         "% third share) or of its breaks of that kind (second); 95% task-bootstrap intervals below each share.",
         "{\\small",
         "\\begin{tabular}{@{}lrrrr@{}}",
         "\\toprule",
         " & \\multicolumn{2}{c}{2025, \\EraOldRuns{} runs} & \\multicolumn{2}{c}{2026, \\EraNewRuns{} runs} \\\\",
         "\\cmidrule(lr){2-3}\\cmidrule(l){4-5}",
         " & Syntax & Other & Syntax & Other \\\\",
         "\\midrule",
         "Breaks of that kind & " + " & ".join(f"\\Rx{e}{k}Breaks" for e, k in COLS) + " \\\\"]
for label, label2, key in ROWS:
    lines.append(f"{label} & " + " & ".join(f"\\Rx{e}{k}{key}\\%" for e, k in COLS) + " \\\\")
    lines.append(f"{label2} & " + " & ".join(f"{{\\scriptsize \\Rx{e}{k}{key}CI}}" for e, k in COLS) + " \\\\")
lines += ["\\bottomrule", "\\end{tabular}", "}"]
(PKG / "paper" / "table_syntax_era.tex").write_text("\n".join(lines) + "\n")

# ---------------------------------------------------------------- 2. exposure from each run's first edit
macros["RxFirstEditRuns"] = (f"{total(ALL, 'edited'):,}", "Kept runs with at least one edit (the first-edit "
                             "exposure is undefined for the rest)")
macros["RxExposureFirstEditCI"] = (ci_text(stat_ci(ALL, "FirstEdit"), 1), "\\ExposureFirstEdit, task bootstrap")
for tag, name in (("A", QWEN), ("B", GEMINI)):
    v = efe_by[name]
    macros[f"RxPair{tag}FirstEdit"] = (pct(statistics.mean(v.values()), 1), f"First-edit exposure of {name} "
                                       f"({len(v)} runs; cf. \\Pair{tag}FirstEditExposure)")
    macros[f"RxPair{tag}FirstEditCI"] = (ci_text(boot(lambda smp, v=v: statistics.mean(v[t] for t in smp if t in v)
                                                     if any(t in v for t in smp) else None, TASKS), 1), "Same, task bootstrap")
macros["RxPairFirstEditRatio"] = (f"{pair_ratio(efe_by, TASKS):.1f}", "Qwen3-Coder first-edit exposure over Gemini "
                                  "2.5 Pro's (cf. \\XtPairRatio for exposure)")
lo, hi = boot(lambda smp: pair_ratio(efe_by, smp), TASKS)
macros["RxPairFirstEditRatioCI"] = (f"{lo:.1f}--{hi:.1f}", "Same, task bootstrap")
lo, hi = boot(lambda smp: pair_ratio(exp_by, smp), TASKS)
macros["RxPairRatioCI"] = (f"{lo:.1f}--{hi:.1f}", "\\XtPairRatio (exposure), task bootstrap, for comparison")
folds = sorted(((fold(p, "exposure_after_first_edit_mean"), p) for p in alike), reverse=True)
macros["RxPairsFirstEditTwoFold"] = (sum(f >= 2 for f, _ in folds), "Of the \\PairsAlike close pairs, those whose "
                                     "first-edit exposures differ at least two-fold (cf. \\PairsTwoFold)")
macros["RxPairsFirstEditThreeFold"] = (sum(f >= 3 for f, _ in folds), "Same, at least three-fold")
macros["RxPairsFirstEditMaxRatio"] = (f"{folds[0][0]:.1f}", f"Largest first-edit ratio among them ({folds[0][1][0]} "
                                      f"vs {folds[0][1][1]})")
efolds = sorted(((fold(p, "exposure_mean"), p) for p in alike), reverse=True)
macros["RxPairsThreeFold"] = (sum(f >= 3 for f, _ in efolds), "For comparison: close pairs whose exposures differ "
                              "at least three-fold")
macros["RxPairsMaxRatio"] = (f"{efolds[0][0]:.1f}", f"For comparison: largest exposure ratio ({efolds[0][1][0]} vs "
                             f"{efolds[0][1][1]})")
same_order = sum((float(models[a]["exposure_mean"]) > float(models[b]["exposure_mean"]))
                 == (float(models[a]["exposure_after_first_edit_mean"]) > float(models[b]["exposure_after_first_edit_mean"]))
                 for a, b in alike)
macros["RxPairsFirstEditSameOrder"] = (same_order, "Close pairs in which the model with the higher exposure also has "
                                       "the higher first-edit exposure")

# ---------------------------------------------------------------- 3. runs stopped by the step or cost limit
limit_set = set(limit)
lim = defaultdict(Counter)
for k in limit:
    lim[k[1]]["runs"] += 1
    lim[k[1]]["broken"] += cells[k]["stop_broken"] == "True"
macros["RxLimitStopRuns"] = (len(limit), "Kept runs stopped by the step or cost limit (exit status LimitsExceeded, "
                             "nothing submitted; = summary.json limit_stop_runs)")
macros["RxLimitStopBrokenRuns"] = (len(limit_broken), "Of those, runs whose code at the stop is broken")
macros["RxLimitStopBroken"] = (pct(len(limit_broken) / len(limit)), "Same, share (= \\LimitStopBroken)")
lo, hi = boot(lambda smp: (sum(lim[t]["broken"] for t in smp) / sum(lim[t]["runs"] for t in smp))
              if sum(lim[t]["runs"] for t in smp) else None, TASKS)
macros["RxLimitStopBrokenCI"] = (ci_text((lo, hi)), "Same, task bootstrap (\\LimitStopCI is Wilson)")
macros["RxLimitStopUnseenRuns"] = (sum(any(b["unseen"] == "True" for b in open_break.get(k, [])) for k in limit_broken),
                                   "Of the limit-stopped runs left broken, those whose open break is unseen")
macros["RxLimitStopTasks"] = (len({k[1] for k in limit}), "Distinct tasks among the limit-stopped runs")
stopped = Counter(cells[k]["recorded_exit_status"] for k in cells if cells[k]["recorded_submitted"] == "False")
notes.append("Runs that submitted nothing, by exit status: " + ", ".join(f"{s} {n}" for s, n in sorted(stopped.items())))

# ---------------------------------------------------------------- 4. intervals for the transient / lasting split
tr = defaultdict(Counter)
for b in breaks:
    tr[b["task"]]["breaks"] += 1
    tr[b["task"]]["lasting"] += not transient(b)
for b in lasting_judged:
    tr[b["task"]]["lj"] += 1
    tr[b["task"]]["lju"] += b["unseen"] == "True"
for k in {(b["submission"], b["task"]) for b in lasting}:
    tr[k[1]]["lasting_runs"] += 1
for k in cells:
    tr[k[1]]["runs"] += 1


def tr_ratio(smp, num, den, complement=False):
    d = sum(tr[t][den] for t in smp)
    if not d:
        return None
    x = sum(tr[t][num] for t in smp) / d
    return 1 - x if complement else x


macros["RxTransientCI"] = (ci_text(boot(lambda smp: tr_ratio(smp, "lasting", "breaks", True), TASKS)),
                           "\\RvTransient (breaks repaired by the very next command that changes the code), task bootstrap")
macros["RxLastingRunsCI"] = (ci_text(boot(lambda smp: tr_ratio(smp, "lasting_runs", "runs"), TASKS)),
                             "\\RvLastingRuns, task bootstrap")
macros["RxLastingUnseenCI"] = (ci_text(boot(lambda smp: tr_ratio(smp, "lju", "lj"), TASKS)),
                               "\\RvLastingUnseen, task bootstrap")
macros["RxLastingBreaks"] = (len(lasting), "Breaks that outlast the next edit (1 - \\RvTransient of \\Breaks)")


# ---------------------------------------------------------------- 5. the per-model table
def tex(text):
    for a, b in (("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("$", "\\$"), ("#", "\\#"), ("_", "\\_"),
                 ("{", "\\{"), ("}", "\\}"), ("~", "\\textasciitilde{}"), ("^", "\\textasciicircum{}")):
        text = text.replace(a, b)
    return text


def model_name(submission):
    date, release, name = submission.split("_", 2)
    assert date.isdigit() and release.startswith("mini-v"), submission
    return name, release[len("mini-v"):]


per_model = []
for s in sorted({k[0] for k in cells}):
    runs = [cells[k] for k in sorted(cells) if k[0] == s]
    bs = [b for b in breaks if b["submission"] == s and b["unseen"] in ("True", "False")]
    m = models[s]
    name, release = model_name(s)
    row = {"submission": s, "name": name, "release": release, "major": int(release.split(".")[0]), "runs": len(runs),
           "resolve": float(m["resolve_rate_leaderboard"]),
           "break": sum(r["any_break"] == "True" for r in runs) / len(runs),
           "unseen": sum(b["unseen"] == "True" for b in bs) / len(bs) if bs else None, "breaks": len(bs),
           "exposure": statistics.mean(float(r["exposure"]) for r in runs),
           "first_edit": statistics.mean(efe_by[s].values()),
           "end_broken": sum(end_state(r) == "True" for r in runs) / len(runs)}
    # The same numbers as the report's per-model table, where it has them.
    assert row["runs"] == int(m["runs"]), s
    assert abs(row["break"] - float(m["runs_with_break_any"])) < 1e-12, s
    assert row["breaks"] == int(m["intervals"]), s
    assert row["unseen"] is None or abs(row["unseen"] - float(m["unseen_interval_share"])) < 1e-12, s
    per_model.append(row)
check("Models", len(per_model))
assert sum(r["runs"] for r in per_model) == len(cells)
per_model.sort(key=lambda r: (r["major"], -r["resolve"], r["name"]))
lines = ["% Generated by paper/review2_numbers.py (literals; booktabs only). Sized for a table* (full text width).",
         "% One row per kept model, by scaffold version, then leaderboard resolve rate (highest first). Model: the",
         "% submission's name without its date and scaffold release. Shares in percent: Resolved, the leaderboard's",
         "% resolve rate; Break, runs with a break; Unseen, breaks the log never showed; Exposure, share of a run's",
         "% commands after which its code is broken (mean over runs); From 1st edit, the same counted from the run's",
         "% first edit (mean over runs that edit); Ends broken, runs whose final code is broken.",
         "{\\footnotesize",
         "\\begin{tabular}{@{}llrrrrrrr@{}}",
         "\\toprule",
         "Model & Scaffold & Runs & Resolved & Break & Unseen & Exposure & From 1st edit & Ends broken \\\\",
         "\\midrule"]
for i, r in enumerate(per_model):
    if i and r["major"] != per_model[i - 1]["major"]:
        lines.append("\\midrule")
    unseen = "--" if r["unseen"] is None else pct(r["unseen"])
    lines.append(f"{tex(r['name'])} & {r['release']} & {r['runs']} & {pct(r['resolve'], 1)} & {pct(r['break'])} & "
                 f"{unseen} & {pct(r['exposure'], 1)} & {pct(r['first_edit'], 1)} & {pct(r['end_broken'])} \\\\")
lines += ["\\bottomrule", "\\end{tabular}", "}"]
(PKG / "paper" / "table_models.tex").write_text("\n".join(lines) + "\n")


# The same rows as a one-column table (paper/table_models_column.tex): model names without dates or "-instruct".
def short_name(name):
    name = re.sub(r"-?20\d\d-?\d\d-?\d\d", "", name)
    return re.sub(r"-(a35b-)?instruct$", "", name).replace("-a35b", "")


FEW_BREAKS = 10
col = ["% Generated by paper/review2_numbers.py: table_models.tex's rows, sized for one column.",
       "{\\scriptsize\\setlength{\\tabcolsep}{2pt}",
       "\\begin{tabular}{@{}lrrrrrrrrr@{}}",
       "\\toprule",
       "Model & Ver. & Runs & Res. & Brk. & $n$ & Uns. & Exp. & 1st & End \\\\",
       "\\midrule"]
for i, r in enumerate(per_model):
    if i and r["major"] != per_model[i - 1]["major"]:
        col.append("\\midrule")
    unseen = "--" if r["unseen"] is None else pct(r["unseen"])
    if r["breaks"] < FEW_BREAKS:  # an unseen share resting on fewer than 10 breaks is greyed
        unseen = f"\\textcolor{{gray}}{{{unseen}}}"
    col.append(f"{tex(short_name(r['name']))} & {r['release']} & {r['runs']} & {pct(r['resolve'], 1)} & {pct(r['break'])} & "
               f"{r['breaks']} & {unseen} & {pct(r['exposure'], 1)} & {pct(r['first_edit'], 1)} & {pct(r['end_broken'])} \\\\")
col += ["\\bottomrule", "\\end{tabular}", "}"]
assert len({short_name(r["name"]) + str(r["major"]) for r in per_model}) == len(per_model), "short names collide"
(PKG / "paper" / "table_models_column.tex").write_text("\n".join(col) + "\n")
macros["RxTableModels"] = (len(per_model), "Rows of the per-model table (table_models.tex)")
macros["RxTableModelsOld"] = (sum(r["major"] == 1 for r in per_model), "Of them, scaffold 1.x")
macros["RxTableModelsNew"] = (sum(r["major"] == 2 for r in per_model), "Of them, scaffold 2.x")
macros["RxTableFewBreaks"] = (sum(r["breaks"] < FEW_BREAKS for r in per_model), "Rows whose unseen share rests on fewer than 10 breaks (greyed)")

# ---------------------------------------------------------------- 6. non-syntax breaks by error: not computed
notes.append("Item 6 (non-syntax breaks by error) not computed: data/verified/intervals.csv keeps no error text "
             "(evidence_lines is a count). Of the older local reports, report-final2's intervals.csv has no error "
             "text either and differs from this package's break table on two breaks' seen/unseen verdict; "
             "report-final3 and report-final4 hold no break table with error text.")
# A coarse split the break table does support: how the non-syntax breaks show and how they end.
nosyn = [b for b in breaks if b["syntax_error"] == "False"]
macros["RxNoSynN"] = (len(nosyn), "Breaks that are not syntax errors (main runs)")
macros["RxNoSynLoad"] = (sum(b["kind"] == "load" for b in nosyn), "Of them, load breaks: a test file can no longer run (failing import, module-level error)")
macros["RxNoSynTest"] = (sum(b["kind"] == "test" for b in nosyn), "Of them, test breaks: a previously passing test fails")
macros["RxNoSynSkipOnly"] = (sum(b["skip_only"] == "True" for b in nosyn), "Of them, breaks whose only symptom is a skipped test")
macros["RxNoSynOpen"] = (sum(is_open(b) for b in nosyn), "Of them, breaks still open when the run ends")
macros["RxNoSynTestShare"] = (pct(sum(b["kind"] == "test" for b in nosyn) / len(nosyn)), "Share of non-syntax breaks that are test breaks")

# ---------------------------------------------------------------- 7. a syntax check first, then a judge (Table II)
FILES = {"S": "results.jsonl", "O": "results_opus.jsonl", "D": "results_deepseek.jsonl", "X": "results_sonnet_examples.jsonl"}
PREVALENCE, UNSEEN_W = 0.0988, 0.55  # analyse3.py as the README runs it, and its fixed unseen/seen mix
CLASSES = {"Unseen": "unseen_break", "Seen": "seen_break", "Clean": "clean"}


def jkey(r):
    return (r["kind"], r["submission"], r["task"], r["step"])


judges = {}
for tag, name in FILES.items():
    rows = [json.loads(line) for line in (PKG / "judge" / name).open()]
    judges[tag] = {jkey(r): r for r in rows if r.get("verdict") in ("BROKEN", "OK")}
common = sorted(set.intersection(*[set(v) for v in judges.values()]))
check("RvJudgeCommon", len(common))
sampled = {jkey(i): i for f in ("sample.json", "sample2.json") for i in json.load((PKG / "judge" / f).open())}
by_onset = {(b["submission"], b["task"], int(b["onset"])): b for b in breaks}
assert len(by_onset) == len(breaks), "two breaks with one onset"
before = {}
for k, v in states.items():
    for (_, _, s0), (_, c1, _) in zip(v, v[1:]):
        before[(k[0], k[1], c1)] = s0
after = {(k[0], k[1], c): s for k, v in states.items() for _, c, s in v}
problems = []
for key in common:
    kind, s, t, step = key
    b, item = by_onset.get((s, t, step)), sampled.get(key)
    if item is None:
        problems.append(f"{key}: not in sample.json or sample2.json")
    elif kind == "clean":
        if b is not None or after.get((s, t, step)) != "ok":
            problems.append(f"{key}: a clean command that starts a break or leaves the code broken")
    elif b is None:
        problems.append(f"{key}: no break starts at this command")
    elif b["unseen"] != {"unseen_break": "True", "seen_break": "False"}[kind] or b["kind"] != item["break_kind"]:
        problems.append(f"{key}: the break's verdict or kind differs from the sample's")
if problems:
    notes.append(f"Item 7 skipped: the join of the {len(common)} sampled commands to the break table is not exact "
                 f"({len(problems)} problems, first: {problems[0]}).")
else:
    syntax_flag = {k: k[0] != "clean" and by_onset[(k[1], k[2], k[3])]["syntax_error"] == "True" for k in common}
    notes.append(f"Item 7: all {len(common)} sampled commands join exactly: every sampled break command is the onset "
                 "of one kept break with the same seen/unseen verdict and kind; no clean command starts a break.")

    def wilson3(k, n):  # analyse3.py: Wilson bounds rounded to whole percents
        lo_, hi_ = wilson(k, n)
        return round(100 * lo_), round(100 * hi_)

    def prec(f, p, r):
        return r * p / (r * p + f * (1 - p)) if (r * p + f * (1 - p)) else None

    def analyse3(flag):
        """judge/analyse3.py's numbers for a reader whose verdict on item k is flag(k): shares rounded to percents."""
        res = {}
        for c, kind in CLASSES.items():
            v = [flag(k) for k in common if k[0] == kind]
            res[c] = (sum(v), len(v), round(100 * sum(v) / len(v)))
        recall = UNSEEN_W * res["Unseen"][2] / 100 + (1 - UNSEEN_W) * res["Seen"][2] / 100
        lo_, hi_ = wilson3(res["Clean"][0], res["Clean"][1])
        return {"shares": res, "recall": recall, "precision": round(100 * prec(res["Clean"][2] / 100, PREVALENCE, recall)),
                "precision_ci": (round(100 * prec(hi_ / 100, PREVALENCE, recall)),
                                 round(100 * prec(lo_ / 100, PREVALENCE, recall)))}

    def unrounded(flag, smp_keys):
        shares = {}
        for c, kind in CLASSES.items():
            v = [flag(k) for k in smp_keys if k[0] == kind]
            if not v:
                return None
            shares[c] = sum(v) / len(v)
        recall = UNSEEN_W * shares["Unseen"] + (1 - UNSEEN_W) * shares["Seen"]
        return recall, prec(shares["Clean"], PREVALENCE, recall)

    keys_by_task = defaultdict(list)
    for k in common:
        keys_by_task[k[2]].append(k)
    jt = sorted(keys_by_task)

    def task_ci(flag, which):
        def f(smp):
            got = unrounded(flag, [k for t in smp for k in keys_by_task[t]])
            return None if got is None else got[which]
        return boot(f, jt)

    readers = {"SynCheck": lambda k: syntax_flag[k]}
    for tag, label in (("S", "Sonnet"), ("O", "Opus")):
        judged = judges[tag]
        base = analyse3(lambda k, j=judged: j[k]["verdict"] == "BROKEN")
        check(f"RvJ{tag}Prec", base["precision"])
        check(f"RvJ{tag}PrecCI", f"{base['precision_ci'][0]}--{base['precision_ci'][1]}")
        check(f"XtJ{tag}PrecTaskCI", ci_text(task_ci(lambda k, j=judged: j[k]["verdict"] == "BROKEN", 1)))
        macros[f"RxJ{tag}Recall"] = (pct(base["recall"]), f"Table II: {label} recall at the natural unseen/seen mix "
                                     "(analyse3.py's 0.55/0.45 of the rounded shares), for comparison")
        readers[f"SynOrJ{tag}"] = lambda k, j=judged: syntax_flag[k] or j[k]["verdict"] == "BROKEN"
    for name, flag in readers.items():
        a3 = analyse3(flag)
        sh = a3["shares"]
        who = {"SynCheck": "a perfect syntax check alone", "SynOrJS": "syntax check, then Sonnet on the rest",
               "SynOrJO": "syntax check, then Opus on the rest"}[name]
        for c in ("Unseen", "Seen", "Clean"):
            macros[f"Rx{name}{c}"] = (sh[c][2], f"Table II sample: {who}, share of its {sh[c][1]} {c.lower()} "
                                      f"commands flagged ({sh[c][0]})")
        macros[f"Rx{name}Recall"] = (pct(a3["recall"]), f"{who}: recall at the natural unseen/seen mix (analyse3.py)")
        macros[f"Rx{name}RecallCI"] = (ci_text(task_ci(flag, 0)), f"Same, task bootstrap over the {len(jt)} sampled tasks")
        macros[f"Rx{name}Prec"] = (a3["precision"], f"{who}: implied precision at the natural break rate "
                                   f"({PREVALENCE}; analyse3.py)")
        if name != "SynCheck":
            macros[f"Rx{name}PrecCI"] = (f"{a3['precision_ci'][0]}--{a3['precision_ci'][1]}", "Same, analyse3.py's "
                                         "interval (Wilson on the false-alarm rate only)")
            macros[f"Rx{name}PrecTaskCI"] = (ci_text(task_ci(flag, 1)), f"Same, task bootstrap over the {len(jt)} "
                                             "sampled tasks (all three flag rates vary)")
    macros["RxSynCheckBreaksFlagged"] = (sum(syntax_flag.values()), f"Sampled break commands that start a syntax-error "
                                         f"break (of {sum(k[0] != 'clean' for k in common)})")
    # The sample's unseen class over-weights test breaks (sample2.json adds 50 of them), so its syntax mix is not the
    # natural one. Exact on all break-starting edits made on clean code, and the combined rules re-weighted to that mix.
    strata = Counter()
    for b in breaks:
        if before.get((b["submission"], b["task"], int(b["onset"]))) == "ok":
            strata[(b["unseen"] == "True", b["syntax_error"] == "True")] += 1
    check("RvOnsetEdits", sum(strata.values()))
    on_syntax = strata[(True, True)] + strata[(False, True)]
    macros["RxSynCheckRecallAll"] = (pct(on_syntax / sum(strata.values()), 1), f"A perfect syntax check's recall on all "
                                     f"\\RvOnsetEdits{{}} break-starting edits on clean code ({on_syntax} are syntax errors)")
    sample_syn = {kind: sum(syntax_flag[k] for k in common if k[0] == kind) / sum(k[0] == kind for k in common)
                  for kind in ("unseen_break", "seen_break")}
    pop_syn = {kind: strata[(u, True)] / (strata[(u, True)] + strata[(u, False)])
               for kind, u in (("unseen_break", True), ("seen_break", False))}
    macros["RxSampleUnseenSyn"] = (pct(sample_syn["unseen_break"]), "Table II sample: share of its unseen break "
                                   "commands that are syntax errors")
    macros["RxPopUnseenSyn"] = (pct(pop_syn["unseen_break"]), "All unseen breaks that start on clean code: share that "
                                "are syntax errors")
    for tag, label in (("S", "Sonnet"), ("O", "Opus")):
        judged = judges[tag]
        recall = 0.0
        for (u, syn), n in strata.items():
            if syn:
                recall += n  # the syntax check flags every one
                continue
            kind = "unseen_break" if u else "seen_break"
            v = [judged[k]["verdict"] == "BROKEN" for k in common if k[0] == kind and not syntax_flag[k]]
            recall += n * sum(v) / len(v)
        recall /= sum(strata.values())
        fa = sum(judged[k]["verdict"] == "BROKEN" for k in common if k[0] == "clean") / sum(k[0] == "clean" for k in common)
        macros[f"RxSynOrJ{tag}RecallStrat"] = (pct(recall), f"Syntax check, then {label}: recall re-weighted to the "
                                               "natural mix of seen/unseen x syntax/other among break-starting edits")
        macros[f"RxSynOrJ{tag}PrecStrat"] = (pct(prec(fa, PREVALENCE, recall)), "Same, implied precision at the "
                                             "natural break rate (unrounded rates)")

# ---------------------------------------------------------------- 8. claim audit (Oct 28): two definitions made explicit
# (a) The failed runs whose final code passes every fix test: how many of them submitted that code.
only_reg = [r for r in cells.values() if only_regression(r)]
macros["RxOnlyRegRuns"] = (len(only_reg), "Failed runs whose final code passes every fix test and fails a previously passing test")
macros["RxOnlyRegUnsubmitted"] = (sum(r["recorded_submitted"] != "True" for r in only_reg), "Of them, runs that submitted nothing (stopped)")
# (b) Table II's judges with every run by an Anthropic agent left out (names with claude, sonnet, opus or haiku).
JFILES = {"Sonnet": "results.jsonl", "Opus": "results_opus.jsonl", "DeepSeek": "results_deepseek.jsonl", "+ex.": "results_sonnet_examples.jsonl"}
def jk(r):
    return (r["kind"], r["submission"], r["task"], r["step"])
judged = {n: {jk(r): r for r in map(json.loads, (PKG / "judge" / f).open()) if r.get("verdict") in ("BROKEN", "OK")} for n, f in JFILES.items()}
shared = set.intersection(*(set(v) for v in judged.values()))
anthropic = lambda s: any(w in s.lower() for w in ("claude", "sonnet", "opus", "haiku"))
def flag_rate(rows, kind, keep):
    ks = [k for k in shared if k[0] == kind and keep(k[1])]
    return 100 * sum(rows[k]["verdict"] == "BROKEN" for k in ks) / len(ks), len(ks)
shift = {}
for n, rows in judged.items():
    for kind in ("unseen_break", "seen_break", "clean"):
        full, _ = flag_rate(rows, kind, lambda s: True)
        kept, nk = flag_rate(rows, kind, lambda s: not anthropic(s))
        shift[(n, kind)] = (kept - full, nk)
uc = [abs(v[0]) for (n, kind), v in shift.items() if kind in ("unseen_break", "clean")]
macros["RxNoAnthUnseenCleanMax"] = (f"{max(uc):.1f}", "Largest change in a judge's flag rate on unseen breaks or clean edits, runs by Anthropic agents left out (points)")
macros["RxNoAnthSeenMax"] = (f"{max(abs(v[0]) for (n, kind), v in shift.items() if kind == 'seen_break'):.1f}", "Largest change on seen breaks (points)")
macros["RxNoAnthSeenN"] = (shift[("Sonnet", "seen_break")][1], "Seen-break commands left after leaving those runs out")

# ---------------------------------------------------------------- output
print("% Second review round for 'What the Log Misses' (review2_numbers.py). Prefix Rx. Shares in percent.")
print(f"% Reproduced first, equal to the package's macros: {', '.join(dict.fromkeys(checks))}.")
print("% Task bootstrap: 2,000 resamples of the tasks, seed 20261023, a fresh generator per statistic, percentile.")
print("% Also written: paper/table_syntax_era.tex (uses these macros) and paper/table_models.tex (literals).")
for note in notes:
    print(f"% {note}")
for name, (value, comment) in macros.items():
    assert name.startswith("Rx") and name.isalpha(), name
    print(f"\\newcommand{{\\{name}}}{{{value}}} % {comment}")
