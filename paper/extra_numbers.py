"""Four extra analyses for "What the Log Misses", as LaTeX macros (prefix Xt), from the replication package's tables.

    python3 -I extra_numbers.py <package dir> > numbers_extra.tex

<package dir> is the replication package (README.md, data/, judge/, paper/). Nothing in it is written. Plain Python,
standard library only, one process; about a second.

First the script recomputes, by the paper's own definitions (paper/paper_numbers.py, paper/review_numbers.py,
judge/analyse3.py, judge/whole_run/analyse_full.py), every number it builds on and stops unless each one equals the
package's numbers*.tex (or judge_summary*.json). Then:
  1. Without syntax errors: the headline numbers counting only breaks with syntax_error == "False" (the column behind
     the paper's \\SyntaxShare and \\NonSyntaxRuns).
  2. Intervals: task bootstrap (2,000 draws, seed 20261023, percentile, as paper_numbers.boot_ci) for run shares;
     Wilson for simple counts; for the judges, Wilson per flag rate and a bootstrap for implied and measured precision.
  3. Leave one task out: min and max of each headline number over dropping each of the 40 tasks.
  4. Scaffold version: the headline numbers for mini-swe-agent 1.x and 2.x runs, and models run under both versions.
"""
import csv
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

PKG = Path(sys.argv[1])
VER = PKG / "data" / "verified"
SEED, BOOT = 20261023, 2000
csv.field_size_limit(sys.maxsize)

# ---------------------------------------------------------------- the package's own numbers, to check against
def read_macros(path):
    out = {}
    for line in path.read_text().splitlines():
        if line.startswith("\\newcommand{\\"):
            name, value = line[len("\\newcommand{\\"):].split("}{", 1)
            out[name] = value[:-1]
    return out


paper = {**read_macros(PKG / "paper" / "numbers.tex"), **read_macros(PKG / "paper" / "numbers_review.tex")}
checks = []


def check(name, value):
    """Stop unless our recomputation equals the paper's macro."""
    if str(value) != paper[name]:
        sys.exit(f"MISMATCH {name}: ours {value!r}, paper {paper[name]!r}")
    checks.append(name)


def pct(x, digits=0):
    return f"{100 * x:.{digits}f}"


def wilson(k, n, z=1.96):
    p, den = k / n, 1 + z * z / n
    centre, half = (p + z * z / (2 * n)) / den, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


def ci_text(pair, digits=0):
    return f"{pct(pair[0], digits)}--{pct(pair[1], digits)}"


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
models = {r["submission"]: r for r in csv.DictReader((VER / "models.csv").open())}
TASKS = sorted({k[1] for k in cells})
OLD, NEW = "_mini-v1.", "_mini-v2."


def end_state(r):
    return r["end_broken"] if r["recorded_submitted"] == "True" else r["stop_broken"]


def is_open(b):
    return b["ended"] in ("", "None")


def only_regression(r):
    """review_numbers.py: failed on the leaderboard, ends broken, and every fix test passes at the end."""
    return (r["leaderboard_resolved"] == "False" and end_state(r) == "True" and r["f2p_total"] not in ("", "None")
            and int(r["f2p_total"]) > 0 and int(r["f2p_passing_end"]) == int(r["f2p_total"]))


open_break = defaultdict(list)
for b in breaks:
    if is_open(b):
        open_break[(b["submission"], b["task"])].append(b)
assert all(len(v) == 1 for v in open_break.values()), "a run with two open breaks"


def aggregate(keys, syntax_free=False):
    """Per-task counts for the runs in keys (and their breaks), optionally counting only non-syntax breaks."""
    keys = set(keys)
    use = [b for b in breaks if (b["submission"], b["task"]) in keys and (not syntax_free or b["syntax_error"] == "False")]
    a = defaultdict(Counter)
    for k in keys:
        r, t = cells[k], k[1]
        a[t]["runs"] += 1
        a[t]["exp"] += float(r["exposure"])
        a[t]["failed"] += r["leaderboard_resolved"] == "False"
        ob = [b for b in open_break.get(k, []) if not syntax_free or b["syntax_error"] == "False"]
        a[t]["end_unseen"] += any(b["unseen"] == "True" for b in ob)
        # The only-regression run, and (syntax-free) only when the break the run ends on is not a syntax error.
        a[t]["only_reg"] += only_regression(r) and (not syntax_free or bool(ob))
        a[t]["only_reg_unseen"] += only_regression(r) and any(b["unseen"] == "True" for b in ob)
    broke = {(b["submission"], b["task"]) for b in use}
    for k in broke:
        a[k[1]]["break_runs"] += 1
    for b in use:
        if b["unseen"] in ("True", "False"):
            a[b["task"]]["breaks"] += 1
            a[b["task"]]["unseen"] += b["unseen"] == "True"
    return a


def ratio(a, sample, num, den):
    d = sum(a[t][den] for t in sample)
    return sum(a[t][num] for t in sample) / d if d else None


STATS = {  # name: (numerator, denominator) of a pooled ratio over a task multiset
    "BreakAny": ("break_runs", "runs"), "Unseen": ("unseen", "breaks"), "EndUnseen": ("end_unseen", "runs"),
    "OnlyReg": ("only_reg", "failed"), "Exposure": ("exp", "runs"),
}


def stat(a, name, sample=TASKS):
    return ratio(a, sample, *STATS[name])


def stat_ci(a, name):
    return boot(lambda smp: stat(a, name, smp), TASKS)


macros, notes = {}, []
ALL = aggregate(cells)

# ---------------------------------------------------------------- 0. the headline numbers, reproduced
check("RunsMain", f"{len(cells):,}")
check("Breaks", f"{len(breaks):,}")
check("BreakAny", pct(stat(ALL, "BreakAny")))
check("Unseen", pct(stat(ALL, "Unseen")))
check("RvEndUnseenRuns", pct(stat(ALL, "EndUnseen"), 1))
check("RvFailedRuns", sum(ALL[t]["failed"] for t in TASKS))
check("RvFailedOnlyRegression", sum(ALL[t]["only_reg"] for t in TASKS))
check("RvFailedOnlyRegressionShare", pct(stat(ALL, "OnlyReg")))
check("Exposure", pct(stat(ALL, "Exposure"), 1))
check("SyntaxShare", pct(sum(b["syntax_error"] == "True" for b in breaks) / len(breaks)))
NS = aggregate(cells, syntax_free=True)
check("NonSyntaxRuns", pct(stat(NS, "BreakAny")))
check("NonSyntaxUnseen", pct(stat(NS, "Unseen")))
# The 8.2% interval: review_numbers.py draws it from one generator after two earlier bootstraps of 2,000 x 40 draws.
rng = random.Random(SEED)
for _ in range(2 * BOOT * len(TASKS)):
    rng.choice(TASKS)
end_ci = percentile_ci(stat(ALL, "EndUnseen", [rng.choice(TASKS) for _ in TASKS]) for _ in range(BOOT))
check("RvEndUnseenRunsCI", ci_text(end_ci, 1))
# Model exposures and the Qwen3-Coder / Gemini 2.5 Pro pair.
QWEN, GEMINI = "20250802_mini-v1.0.0_qwen3-coder-480b-a35b-instruct", "20250726_mini-v1.0.0_gemini-2.5-pro"
exp_by = defaultdict(dict)
for (s, t), r in cells.items():
    exp_by[s][t] = float(r["exposure"])
check("PairAExposure", pct(statistics.mean(exp_by[QWEN].values()), 1))
check("PairBExposure", pct(statistics.mean(exp_by[GEMINI].values()), 1))
for s, m in models.items():
    assert abs(statistics.mean(exp_by[s].values()) - float(m["exposure_mean"])) < 1e-12, s
# Scaffold eras.
era_keys = {tag: [k for k in cells if era in k[0]] for era, tag in ((OLD, "Old"), (NEW, "New"))}
ERA = {tag: aggregate(keys) for tag, keys in era_keys.items()}
for tag in ("Old", "New"):
    check(f"Era{tag}Runs", len(era_keys[tag]))
    check(f"Era{tag}Models", len({k[0] for k in era_keys[tag]}))
    check(f"Era{tag}Break", pct(stat(ERA[tag], "BreakAny")))
    check(f"Era{tag}Unseen", pct(stat(ERA[tag], "Unseen")))
    check(f"Era{tag}Exposure", pct(stat(ERA[tag], "Exposure"), 1))
    check(f"Era{tag}Breaks", sum(ERA[tag][t]["breaks"] for t in TASKS))
new_models = sorted({k[0] for k in era_keys["New"]}, key=lambda s: -float(models[s]["exposure_mean"]))
check("EraNewExposureMax", pct(float(models[new_models[0]]["exposure_mean"]), 1))

# ---------------------------------------------------------------- judges (Table II and the whole-run study)
FILES = {"S": "results.jsonl", "O": "results_opus.jsonl", "D": "results_deepseek.jsonl", "X": "results_sonnet_examples.jsonl"}
PREVALENCE, UNSEEN_W = 0.0988, 0.55  # as analyse3.py is run in the README, and its fixed mix of unseen and seen


def jkey(r):
    return (r["kind"], r["submission"], r["task"], r["step"])


judges = {}
for tag, name in FILES.items():
    rows = [json.loads(line) for line in (PKG / "judge" / name).open()]
    judges[tag] = {jkey(r): r for r in rows if r.get("verdict") in ("BROKEN", "OK")}
common = sorted(set.intersection(*[set(v) for v in judges.values()]))
check("RvJudgeCommon", len(common))
CLASSES = {"Unseen": "unseen_break", "Seen": "seen_break", "Clean": "clean"}


def implied_precision(u, s, f, p=PREVALENCE):
    recall = UNSEEN_W * u + (1 - UNSEEN_W) * s
    return recall * p / (recall * p + f * (1 - p))


for tag, rows in judges.items():
    flags = {c: [rows[k]["verdict"] == "BROKEN" for k in common if k[0] == kind] for c, kind in CLASSES.items()}
    shares = {}
    for c, v in flags.items():
        check(f"RvJ{tag}{c}", round(100 * sum(v) / len(v)))
        check(f"RvJ{tag}{c}N", len(v))
        shares[c] = sum(v) / len(v)
        macros[f"XtJ{tag}{c}CI"] = (ci_text(wilson(sum(v), len(v))), f"Table II: \\RvJ{tag}{c}, Wilson 95% interval "
                                    f"over its {len(v)} sampled commands")
    rounded = {c: round(100 * x) / 100 for c, x in shares.items()}  # analyse3.py works from the rounded shares
    check(f"RvJ{tag}Prec", round(100 * implied_precision(rounded["Unseen"], rounded["Seen"], rounded["Clean"])))
    macros[f"XtJ{tag}PrecExact"] = (pct(implied_precision(shares["Unseen"], shares["Seen"], shares["Clean"])),
                                    "Table II: implied precision from the unrounded flag rates (paper's value uses rounded rates)")
    # All three flag rates vary: resample the commands within each sampled class (the sample was drawn by class).
    rng = random.Random(SEED)
    draws = []
    for _ in range(BOOT):
        r_ = {c: [rng.choice(v) for _ in v] for c, v in flags.items()}
        draws.append(implied_precision(*(sum(r_[c]) / len(r_[c]) for c in ("Unseen", "Seen", "Clean"))))
    macros[f"XtJ{tag}PrecCI"] = (ci_text(percentile_ci(draws)), "Table II: implied precision, 95% bootstrap over the "
                                 "sampled commands within each class (all three flag rates vary)")
    # Clustered by task instead (37 tasks): the more cautious interval.
    by_task = defaultdict(lambda: defaultdict(list))
    for k in common:
        for c, kind in CLASSES.items():
            if k[0] == kind:
                by_task[k[2]][c].append(rows[k]["verdict"] == "BROKEN")
    jt = sorted(by_task)

    def prec_tasks(smp, by_task=by_task):
        pooled = {c: [x for t in smp for x in by_task[t][c]] for c in CLASSES}
        if not all(pooled.values()):
            return None
        return implied_precision(*(sum(pooled[c]) / len(pooled[c]) for c in ("Unseen", "Seen", "Clean")))

    macros[f"XtJ{tag}PrecTaskCI"] = (ci_text(boot(prec_tasks, jt)), f"Table II: implied precision, 95% bootstrap over "
                                     f"the {len(jt)} tasks the sampled commands come from")
macros["XtJudgeTasks"] = (len({k[2] for k in common}), "Table II: tasks the 288 sampled commands come from")

# Whole-run judges (analyse_full.py): every edit on clean code in 150 random kept runs.
W = PKG / "judge" / "whole_run"
items = {(i["submission"], i["task"]): i for i in json.load((W / "sample_full.json").open())}
for i in items.values():
    i["edits"] = [e for e in i["edits"] if e["command"] > 0]
for tag, name in (("S", "sonnet"), ("O", "opus")):
    per_run = []
    for r in (json.loads(line) for line in (W / f"full_{name}.jsonl").open()):
        it = items[(r["submission"], r["task"])]
        calls = {int(k): v for k, v in r["calls"].items()}
        e = [(x, calls.get(x["command"])) for x in it["edits"] if x["before"] == "ok"]
        per_run.append({"task": r["task"], "tp": sum(x["onset"] and c == "BROKEN" for x, c in e),
                        "fp": sum(not x["onset"] and c == "BROKEN" for x, c in e),
                        "on": sum(x["onset"] for x, c in e), "clean": sum(not x["onset"] for x, c in e)})
    tp, fp = sum(p["tp"] for p in per_run), sum(p["fp"] for p in per_run)
    on, clean = sum(p["on"] for p in per_run), sum(p["clean"] for p in per_run)

    def prec(smp):
        a, b = sum(p["tp"] for p in smp), sum(p["fp"] for p in smp)
        return a / (a + b) if a + b else None

    check(f"RvFull{tag}Prec", round(100 * tp / (tp + fp)))
    check("RvFullOnsets", on)
    check("RvFullCleanEdits", on + clean)
    rng = random.Random(20261024)  # analyse_full.py: bootstrap over runs, draws[50] and draws[1949]
    draws = sorted(v for v in (prec([rng.choice(per_run) for _ in per_run]) for _ in range(2000)) if v is not None)
    check(f"RvFull{tag}PrecCI", f"{round(100 * draws[50])}--{round(100 * draws[1949])}")
    runs_by_task = defaultdict(list)
    for p in per_run:
        runs_by_task[p["task"]].append(p)
    wt = sorted(runs_by_task)
    label = {"S": "Sonnet", "O": "Opus"}[tag]
    macros[f"XtFull{tag}Flags"] = (tp + fp, f"Whole runs: edits on clean code that {label} flags as breaking")
    macros[f"XtFull{tag}Confirmed"] = (tp, f"Whole runs: {label} flags the tests confirm (the edit starts a break)")
    macros[f"XtFull{tag}Unconfirmed"] = (fp, f"Whole runs: {label} flags on edits that leave the code clean")
    macros[f"XtFull{tag}PrecExact"] = (pct(tp / (tp + fp), 1), f"Whole runs: {label} precision, one decimal")
    macros[f"XtFull{tag}PrecWilson"] = (ci_text(wilson(tp, tp + fp)), f"Whole runs: {label} precision, Wilson 95% "
                                        f"over its {tp + fp} flags (ignores clustering by run)")
    macros[f"XtFull{tag}PrecTaskCI"] = (ci_text(boot(lambda smp: prec([p for t in smp for p in runs_by_task[t]]), wt)),
                                        f"Whole runs: {label} precision, 95% bootstrap over the {len(wt)} tasks "
                                        f"(paper's interval is over runs: \\RvFull{tag}PrecCI)")
macros["XtFullCleanOnly"] = (clean, "Whole runs: edits on clean code that leave it clean (848 minus 67 onsets)")
macros["XtFullTasks"] = (len(wt), "Whole runs: tasks the 150 judged runs come from")

# ---------------------------------------------------------------- 1. without syntax errors
ns_breaks = [b for b in breaks if b["syntax_error"] == "False"]
macros["XtNoSynBreaks"] = (len(ns_breaks), "Breaks that are not syntax errors (of \\Breaks)")
macros["XtNoSynRunsCI"] = (ci_text(stat_ci(NS, "BreakAny")), "Runs with a non-syntax break (\\NonSyntaxRuns), task bootstrap")
macros["XtNoSynUnseenCI"] = (ci_text(stat_ci(NS, "Unseen")), "Non-syntax breaks unseen (\\NonSyntaxUnseen), task bootstrap")
macros["XtNoSynEndUnseenRunsN"] = (sum(NS[t]["end_unseen"] for t in TASKS), "Runs ending on an unseen non-syntax break")
macros["XtNoSynEndUnseenRuns"] = (pct(stat(NS, "EndUnseen"), 1), "Share of kept runs ending on an unseen non-syntax "
                                  "break (cf. \\RvEndUnseenRuns)")
macros["XtNoSynEndUnseenRunsCI"] = (ci_text(stat_ci(NS, "EndUnseen"), 1), "Same, task bootstrap")
macros["XtNoSynOnlyReg"] = (sum(NS[t]["only_reg"] for t in TASKS), "Failed runs whose only failure is a broken "
                            "previously passing test, the break being no syntax error (cf. \\RvFailedOnlyRegression)")
macros["XtNoSynOnlyRegShare"] = (pct(stat(NS, "OnlyReg"), 1), "Same, share of the \\RvFailedRuns{} failed runs "
                                 "(cf. \\RvFailedOnlyRegressionShare)")
macros["XtNoSynOnlyRegShareCI"] = (ci_text(stat_ci(NS, "OnlyReg"), 1), "Same, task bootstrap")
macros["XtNoSynOnlyRegUnseen"] = (sum(NS[t]["only_reg_unseen"] for t in TASKS), "Of \\XtNoSynOnlyReg, runs ending on an unseen break")

# ---------------------------------------------------------------- 2. intervals for the headline run shares
failed_n, onlyreg_n = sum(ALL[t]["failed"] for t in TASKS), sum(ALL[t]["only_reg"] for t in TASKS)
end_n = sum(ALL[t]["end_unseen"] for t in TASKS)
macros["XtOnlyRegShare"] = (pct(stat(ALL, "OnlyReg"), 1), "\\RvFailedOnlyRegressionShare to one decimal")
macros["XtOnlyRegShareCI"] = (ci_text(stat_ci(ALL, "OnlyReg"), 1), "\\RvFailedOnlyRegressionShare, 95% task bootstrap")
macros["XtOnlyRegShareWilson"] = (ci_text(wilson(onlyreg_n, failed_n), 1), "Same, Wilson over the failed runs (ignores tasks)")
macros["XtOnlyRegUnseen"] = (sum(ALL[t]["only_reg_unseen"] for t in TASKS), "Of \\RvFailedOnlyRegression, runs ending on an unseen break")
macros["XtEndUnseenRunsN"] = (end_n, "Runs ending on an unseen break (\\RvEndUnseenRuns of \\RunsMain)")
macros["XtEndUnseenRunsCI"] = (ci_text(end_ci, 1), "\\RvEndUnseenRuns, task bootstrap (reproduces \\RvEndUnseenRunsCI)")
macros["XtEndUnseenRunsWilson"] = (ci_text(wilson(end_n, len(cells)), 1), "Same, Wilson over runs (ignores tasks)")

# ---------------------------------------------------------------- 3. leave one task out
def drop_one(fn):
    values = [(fn([x for x in TASKS if x != t]), t) for t in TASKS]
    return min(values), max(values)


for name, tag, digits in (("BreakAny", "Break", 0), ("Unseen", "Unseen", 0), ("EndUnseen", "EndUnseen", 1),
                          ("OnlyReg", "OnlyReg", 1)):
    (lo, lo_t), (hi, hi_t) = drop_one(lambda smp, name=name: stat(ALL, name, smp))
    base = pct(stat(ALL, name), digits)
    macros[f"XtDrop{tag}Min"] = (pct(lo, digits), f"Drop one task: lowest {name} ({base} with all; lowest without {lo_t})")
    macros[f"XtDrop{tag}Max"] = (pct(hi, digits), f"Drop one task: highest {name} (highest without {hi_t})")


def pair_ratio(smp):
    a = [exp_by[QWEN][t] for t in smp if t in exp_by[QWEN]]
    b = [exp_by[GEMINI][t] for t in smp if t in exp_by[GEMINI]]
    return statistics.mean(a) / statistics.mean(b)


macros["XtPairRatio"] = (f"{pair_ratio(TASKS):.1f}", "Qwen3-Coder exposure over Gemini 2.5 Pro's (\\PairAExposure/\\PairBExposure)")
(lo, lo_t), (hi, hi_t) = drop_one(pair_ratio)
macros["XtDropPairRatioMin"] = (f"{lo:.1f}", f"Drop one task: lowest Qwen3-Coder/Gemini exposure ratio (without {lo_t})")
macros["XtDropPairRatioMax"] = (f"{hi:.1f}", f"Drop one task: highest ratio (without {hi_t})")
for name, tag, n in (("end_unseen", "EndUnseen", end_n), ("only_reg", "OnlyReg", onlyreg_n)):
    per = Counter({t: ALL[t][name] for t in TASKS if ALL[t][name]})
    top_t, top_n = per.most_common(1)[0]
    macros[f"Xt{tag}Tasks"] = (len(per), f"Distinct tasks among the {n} runs behind {tag}")
    macros[f"Xt{tag}TopTask"] = (top_n, f"Most of those runs from one task ({top_t})")

# ---------------------------------------------------------------- 4. scaffold version (and release year)
for tag in ("Old", "New"):
    a = ERA[tag]
    macros[f"XtEra{tag}BreakCI"] = (ci_text(stat_ci(a, "BreakAny")), f"Scaffold {tag}: \\Era{tag}Break, task bootstrap")
    macros[f"XtEra{tag}EndUnseenN"] = (sum(a[t]["end_unseen"] for t in TASKS), f"Scaffold {tag}: runs ending on an unseen break")
    macros[f"XtEra{tag}EndUnseen"] = (pct(stat(a, "EndUnseen"), 1), f"Scaffold {tag}: share of its \\Era{tag}Runs{{}} "
                                      "runs ending on an unseen break (cf. \\RvEndUnseenRuns)")
    macros[f"XtEra{tag}EndUnseenCI"] = (ci_text(stat_ci(a, "EndUnseen"), 1), "Same, task bootstrap")
    macros[f"XtEra{tag}ExposureCI"] = (ci_text(stat_ci(a, "Exposure"), 1), f"Scaffold {tag}: \\Era{tag}Exposure, task bootstrap")
    macros[f"XtEra{tag}OnlyRegN"] = (sum(a[t]["only_reg"] for t in TASKS), f"Scaffold {tag}: failed runs failed only "
                                     "by a broken previously passing test")
    macros[f"XtEra{tag}Failed"] = (sum(a[t]["failed"] for t in TASKS), f"Scaffold {tag}: runs the leaderboard marks failed")
    macros[f"XtEra{tag}OnlyReg"] = (pct(stat(a, "OnlyReg"), 1), f"Scaffold {tag}: share of its failed runs (cf. "
                                    "\\RvFailedOnlyRegressionShare)")
top = new_models[0]
macros["XtEraNewTopModel"] = (top.split("_", 2)[2], f"Scaffold 2.x model with the highest exposure (\\EraNewExposureMax\\%)")
years = {tag: sorted({k[0][:4] for k in keys}) for tag, keys in era_keys.items()}
notes.append(f"Release year: not in the tables. Submission years: 1.x runs {years['Old']}, 2.x runs {years['New']}, so a "
             "split by submission year is the scaffold split.")
assert years == {"Old": ["2025"], "New": ["2026"]}

# Models run under both scaffold versions (matched by name; the 2.x entries carry a reasoning setting, e.g. "high").
SAME = (("20250807_mini-v1.7.0_gpt-5-mini", "20260217_mini-v2.0.0_gpt-5-mini"),
        ("20251211_mini-v1.17.2_gpt-5.2-2025-12-11-high", "20260217_mini-v2.0.0_gpt-5-2-high"),
        ("20251201_mini-v1.17.1_deepseek-v3.2-reasoner", "20260217_mini-v2.0.0_deepseek-3-2-high"),
        ("20251124_mini-v1.16.0_claude-opus-4-5-20251101", "20260217_mini-v2.0.0_claude-4-5-opus-high"),
        ("20250929_mini-v1.13.3_sonnet-4-5-20250929", "20260217_mini-v2.0.0_claude-4-5-sonnet-high"),
        ("20251118_mini-v1.15.0_gemini-3-pro-preview-20251118", "20260226_mini-v2.0.0_gemini-3-pro-high"))
changes = []
for old, new in SAME:
    shared = sorted(set(exp_by[old]) & set(exp_by[new]))
    e_old = statistics.mean(exp_by[old][t] for t in shared)
    e_new = statistics.mean(exp_by[new][t] for t in shared)
    changes.append((e_new - e_old, old, new, e_old, e_new, len(shared)))
    notes.append(f"Same model, both scaffolds: {old} {pct(e_old, 1)} -> {new} {pct(e_new, 1)} on {len(shared)} shared tasks")
macros["XtSameModelPairs"] = (len(SAME), "Models run under both scaffold versions (matched by name)")
macros["XtSameModelLower"] = (sum(c[0] < 0 for c in changes), "Of those, exposure lower under 2.x (on shared tasks)")
macros["XtSameModelMedianChange"] = (f"{100 * statistics.median(c[0] for c in changes):+.1f}",
                                     "Median change in exposure, 2.x minus 1.x, points")
biggest = min(changes)
rest = [c[0] for c in changes if c is not biggest]
macros["XtSameModelBigOld"] = (pct(biggest[3], 1), f"Largest change: {biggest[1]} exposure under 1.x (shared tasks)")
macros["XtSameModelBigNew"] = (pct(biggest[4], 1), f"Largest change: {biggest[2]} exposure under 2.x (shared tasks)")
macros["XtSameModelRestMin"] = (f"{100 * min(rest):+.1f}", "The other pairs: smallest change, points")
macros["XtSameModelRestMax"] = (f"{100 * max(rest):+.1f}", "The other pairs: largest change, points")

# ---------------------------------------------------------------- output
print("% Extra analyses for 'What the Log Misses' (extra_numbers.py). Prefix Xt. Shares in percent.")
print(f"% Reproduced first, equal to the package's macros: {', '.join(dict.fromkeys(checks))}.")
print("% Already in numbers.tex, not repeated here: \\NonSyntaxRuns, \\NonSyntaxUnseen, \\EraOldModels, \\EraNewModels,")
print("% \\EraOldRuns, \\EraNewRuns, \\EraOldBreaks, \\EraNewBreaks, \\EraOldBreak, \\EraNewBreak, \\EraOldUnseen(CI),")
print("% \\EraNewUnseen(CI), \\EraOldExposure, \\EraNewExposure, \\EraNewExposureMax; the 8.2% interval is \\RvEndUnseenRunsCI.")
print("% Task bootstrap: 2,000 resamples of the 40 tasks, seed 20261023, percentile interval, as paper_numbers.py.")
for note in notes:
    print(f"% {note}")
for name, (value, comment) in macros.items():
    print(f"\\newcommand{{\\{name}}}{{{value}}} % {comment}")
