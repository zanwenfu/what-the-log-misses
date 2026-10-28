"""The third review round's analyses for "What the Log Misses", as LaTeX macros (prefix Ry).

    python3 -I paper/review3_numbers.py <package dir> > paper/numbers_review3.tex

<package dir> is the replication package (README.md, data/, paper/). Plain Python, standard library only, one
process; a few seconds. Nothing is written except the macros on standard output.

First the script recomputes, by the paper's own definitions (paper_numbers.py, extra_numbers.py), the numbers it
builds on and stops unless each equals the package's numbers*.tex. Then:
  1. How the log showed the seen breaks: a test run reported a failure, or only some other output named the break.
  2. Unseen breaks the agent later repaired (the break ended clean), and the unseen share per entry.
  3. Runs ending broken whose log did show the break.
  4. Runs whose final code fails only a previously passing test and that submitted it, as a share of all kept runs.
  5. What the human check of the rule covers: breaks lasting at most 12 commands.
  6. Intervals that resample entries as well as tasks (a two-way bootstrap).
  7. The models run under both scaffold versions: the unseen share of their breaks on shared tasks.
  8. Replay's tests of the final code against SWE-bench's grader run on the replayed final patch (both today).
  9. Tests excluded as flaky: a test counts only if it passes on the starting code of every run of its task.
 10. The 12 models in both the Verified and the Multilingual sample: their break shares.
 11. A close pair among the 2.x entries, and the Fig. 2 pair's runs that end broken on shared tasks.
Every interval is the paper's bootstrap: 2,000 resamples, seed 20261023, a fresh generator per statistic, percentile.
"""
import csv
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

PKG = Path(sys.argv[1])
VER, ML = PKG / "data" / "verified", PKG / "data" / "multilingual"
SEED, BOOT = 20261023, 2000
OLD, NEW = "_mini-v1.", "_mini-v2."
csv.field_size_limit(sys.maxsize)


def read_macros(path):
    out = {}
    for line in path.read_text().splitlines():
        if line.startswith("\\newcommand{\\"):
            name, rest = line[len("\\newcommand{\\"):].split("}{", 1)
            out[name] = rest.split("} % ", 1)[0] if "} % " in rest else rest[:-1]
    return out


paper = {}
for name in ("numbers.tex", "numbers_ml.tex", "numbers_review.tex", "numbers_extra.tex", "numbers_review2.tex"):
    paper.update(read_macros(PKG / "paper" / name))


def pct(x, digits=0):
    return f"{100 * x:.{digits}f}"


def check(name, value):
    assert str(value) == paper[name], f"{name}: recomputed {value!r}, paper has {paper[name]!r}"


def percentile_ci(values):
    values = sorted(v for v in values if v is not None)
    return values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]


def boot(stat, units, seed=SEED):
    rng = random.Random(seed)
    return percentile_ci(stat([rng.choice(units) for _ in units]) for _ in range(BOOT))


def ci_text(pair, digits=0):
    return f"{pct(pair[0], digits)}--{pct(pair[1], digits)}"


def load(folder):
    cells = {(r["submission"], r["task"]): r for r in csv.DictReader((folder / "cells.csv").open()) if r["main"] == "True"}
    breaks = [b for b in csv.DictReader((folder / "intervals.csv").open()) if b["main"] == "True"]
    return cells, breaks


cells, breaks = load(VER)
TASKS = sorted({k[1] for k in cells})
ENTRIES = sorted({k[0] for k in cells})
judged = [b for b in breaks if b["unseen"] in ("True", "False")]


def end_state(r):
    return r["end_broken"] if r["recorded_submitted"] == "True" else r["stop_broken"]


def is_open(b):
    return b["ended"] in ("", "None")


open_break = {(b["submission"], b["task"]): b for b in breaks if is_open(b)}


def only_regression(r):
    return (r["leaderboard_resolved"] == "False" and end_state(r) == "True" and r["f2p_total"] not in ("", "None")
            and int(r["f2p_total"]) > 0 and int(r["f2p_passing_end"]) == int(r["f2p_total"]))


# ---------------------------------------------------------------- the numbers this script builds on
check("RunsMain", f"{len(cells):,}")
check("Breaks", f"{len(breaks):,}")
check("Unseen", pct(sum(b["unseen"] == "True" for b in judged) / len(judged)))
check("UnseenBreaks", sum(b["unseen"] == "True" for b in judged))
check("EndOpen", sum(is_open(b) for b in breaks))
check("RvFailedOnlyRegression", sum(only_regression(r) for r in cells.values()))
check("RxOnlyRegUnsubmitted", sum(only_regression(r) and r["recorded_submitted"] != "True" for r in cells.values()))
check("Models", len(ENTRIES))
broken_end = [k for k, r in cells.items() if end_state(r) == "True"]
check("EndBrokenUnseenShare", pct(sum(k in open_break and open_break[k]["unseen"] == "True" for k in broken_end)
                                  / len(broken_end)))

M = {}

# 1. How the log showed the seen breaks.
seen = [b for b in judged if b["unseen"] == "False"]
M["RyRanTestsBreaks"] = (sum(b["ran_tests"] == "True" for b in judged), "breaks during which a test runner ran tests")
M["RyRanTestsShare"] = (pct(sum(b["ran_tests"] == "True" for b in judged) / len(judged)), "the same, % of breaks")
M["RySawFailureBreaks"] = (sum(b["saw_failure"] == "True" for b in judged), "of all breaks, a test run reported a failure")
M["RyNamedOnlySeen"] = (sum(b["saw_failure"] == "False" for b in seen),
                        "seen breaks shown only by other output naming the broken test or printing its error")
assert M["RySawFailureBreaks"][0] + M["RyNamedOnlySeen"][0] == len(seen)

# 2. Unseen breaks repaired; the unseen share per entry.
unseen = [b for b in judged if b["unseen"] == "True"]
M["RyUnseenRepaired"] = (sum(b["ended"] == "clean" for b in unseen), "unseen breaks that ended with every test passing")
per_entry = defaultdict(Counter)
for b in judged:
    per_entry[b["submission"]]["n"] += 1
    per_entry[b["submission"]]["u"] += b["unseen"] == "True"
shares = [c["u"] / c["n"] for c in per_entry.values() if c["n"]]
M["RyEntryUnseenMedian"] = (pct(statistics.median(shares)), "median over entries of the share of breaks unseen")
M["RyEntriesHalfUnseen"] = (sum(s >= 0.5 for s in shares), "entries with at least half their breaks unseen")
M["RyEntriesWithBreaks"] = (len(shares), "entries with at least one break")

# 2b. Breaks still open when the run ends, unseen and seen.
M["RyUnseenOpenShare"] = (pct(sum(is_open(b) for b in unseen) / len(unseen)), "% of unseen breaks still open at the end")
M["RySeenOpenShare"] = (pct(sum(is_open(b) for b in seen) / len(seen)), "% of seen breaks still open at the end")

# 3. Runs ending broken on a break the log did show.
M["RyEndBrokenRuns"] = (len(broken_end), "kept runs that end on broken code")
M["RyEndSeenRuns"] = (sum(k in open_break and open_break[k]["unseen"] == "False" for k in broken_end),
                      "of those, runs whose log showed the break they end on")

# 4. Runs whose final code fails only a previously passing test and that submitted it, share of all kept runs.
def only_reg_sub(r):
    return only_regression(r) and r["recorded_submitted"] == "True"


def share_of_runs(keys, fn):
    by_task = defaultdict(list)
    for k in keys:
        by_task[k[1]].append(fn(cells[k]))
    point = sum(v for t in TASKS for v in by_task[t]) / len(keys)
    ci = boot(lambda s: (lambda xs: sum(xs) / len(xs) if xs else None)([v for t in s for v in by_task[t]]), TASKS)
    return point, ci


p, ci = share_of_runs(list(cells), only_reg_sub)
M["RyOnlyRegSubRuns"] = (sum(only_reg_sub(r) for r in cells.values()), "kept runs that submitted final code failing only a previously passing test")
M["RyOnlyRegSubShare"] = (pct(p, 1), "the same, % of all kept runs")
M["RyOnlyRegSubShareCI"] = (ci_text(ci, 1), "task bootstrap")
new_keys = [k for k in cells if NEW in k[0]]
p, ci = share_of_runs(new_keys, only_reg_sub)
M["RyOnlyRegSubShareNew"] = (pct(p, 1), "the same among 2.x runs")
M["RyOnlyRegSubShareNewCI"] = (ci_text(ci, 1), "task bootstrap")

# 5. The human check covers breaks lasting at most 12 commands.
short = [b for b in breaks if int(b["duration"]) <= 12]
M["RyShortBreakShare"] = (pct(len(short) / len(breaks)), "% of breaks lasting at most 12 commands")
M["RyShortOpen"] = (sum(is_open(b) for b in short), "breaks still open at the end that last at most 12 commands")

# 6. Two-way bootstrap: resample tasks and entries together.
by_cell_breaks = defaultdict(list)
for b in judged:
    by_cell_breaks[(b["submission"], b["task"])].append(b)
broke_cells = {(b["submission"], b["task"]) for b in breaks}


def two_way(stat):
    rng, values = random.Random(SEED), []
    for _ in range(BOOT):
        ts = [rng.choice(TASKS) for _ in TASKS]
        es = [rng.choice(ENTRIES) for _ in ENTRIES]
        keys = [(e, t) for e in es for t in ts if (e, t) in cells]
        values.append(stat(keys))
    return percentile_ci(values)


def s_break(keys):
    return sum(k in broke_cells for k in keys) / len(keys)


def s_unseen(keys):
    bs = [b for k in keys for b in by_cell_breaks.get(k, [])]
    return sum(b["unseen"] == "True" for b in bs) / len(bs) if bs else None


def s_end_unseen(keys):
    return sum(k in open_break and open_break[k]["unseen"] == "True" for k in keys) / len(keys)


check("BreakAny", pct(s_break(list(cells))))
M["RyBreakAnyCITwo"] = (ci_text(two_way(s_break)), "runs that break, tasks and entries resampled")
M["RyUnseenCITwo"] = (ci_text(two_way(s_unseen)), "breaks unseen, tasks and entries resampled")
M["RyEndUnseenCITwo"] = (ci_text(two_way(s_end_unseen), 1), "runs ending on an unseen break, tasks and entries resampled")

# 7. Models run under both scaffold versions: unseen share of their breaks on shared tasks.
SAME = (("20250807_mini-v1.7.0_gpt-5-mini", "20260217_mini-v2.0.0_gpt-5-mini"),
        ("20251211_mini-v1.17.2_gpt-5.2-2025-12-11-high", "20260217_mini-v2.0.0_gpt-5-2-high"),
        ("20251201_mini-v1.17.1_deepseek-v3.2-reasoner", "20260217_mini-v2.0.0_deepseek-3-2-high"),
        ("20251124_mini-v1.16.0_claude-opus-4-5-20251101", "20260217_mini-v2.0.0_claude-4-5-opus-high"),
        ("20250929_mini-v1.13.3_sonnet-4-5-20250929", "20260217_mini-v2.0.0_claude-4-5-sonnet-high"),
        ("20251118_mini-v1.15.0_gemini-3-pro-preview-20251118", "20260226_mini-v2.0.0_gemini-3-pro-high"))
check("XtSameModelPairs", len(SAME))
tally = {"old": Counter(), "new": Counter()}
for old, new in SAME:
    shared = {t for (e, t) in cells if e == old} & {t for (e, t) in cells if e == new}
    for side, entry in (("old", old), ("new", new)):
        for t in shared:
            for b in by_cell_breaks.get((entry, t), []):
                tally[side]["n"] += 1
                tally[side]["u"] += b["unseen"] == "True"
for side, label in (("old", "1.x"), ("new", "2.x")):
    tag = "Old" if side == "old" else "New"
    M[f"RySame{tag}Unseen"] = (pct(tally[side]["u"] / tally[side]["n"]), f"same six models under {label}: % of breaks unseen, shared tasks")
    M[f"RySame{tag}UnseenK"] = (tally[side]["u"], f"same, unseen breaks under {label}")
    M[f"RySame{tag}UnseenN"] = (tally[side]["n"], f"same, breaks under {label}")

# 8. Replay's tests of the final code against our own run of SWE-bench's grader on the replayed final patch.
grades = Counter(r["grade_agreement"] for r in cells.values() if r["grade_agreement"])
M["RyGraded"] = (f"{sum(grades.values()):,}", "kept runs whose replayed final patch we graded with SWE-bench's grader")
M["RyGradeSame"] = (f"{grades['both_clean'] + grades['same_breaks']:,}", "replay's tests find exactly the grader's failing previously passing tests")
M["RyGradeOursOnly"] = (grades["ours_only"], "replay's tests find a failure the grader does not")
M["RyGradeOfficialOnly"] = (grades["official_only"], "the grader finds a failure replay's tests miss (16 of 21 on matplotlib-23412)")
M["RyGradeDifferent"] = (grades["both_different"], "both find failures, but different ones")
assert set(grades) <= {"both_clean", "same_breaks", "ours_only", "official_only", "both_different"}

# 9. Flaky tests: a test counts only if it passes on the starting code of every replayed run of its task.
all_cells = list(csv.DictReader((VER / "cells.csv").open()))
runs_per_task = Counter(r["task"] for r in all_cells if r["usable"] == "True")
M["RyBaseRunsMin"] = (min(runs_per_task.values()), "fewest replayed runs per task (each tests the starting code once)")
flaky = {r["task"]: int(r["flaky_excluded"]) for r in all_cells}
M["RyFlakyTests"] = (sum(flaky.values()), "tests excluded because they failed on some run's starting code")
M["RyFlakyTasks"] = (sum(v > 0 for v in flaky.values()), "tasks with such a test")

# 10. The models in both samples: their break shares on Verified and on Multilingual.
ml_cells, ml_breaks = load(ML)
BOTH = {"claude-4-5-haiku": "20260217_mini-v2.0.0_claude-4-5-haiku-high", "claude-4-5-opus": "20260217_mini-v2.0.0_claude-4-5-opus-high",
        "claude-4-5-sonnet": "20260217_mini-v2.0.0_claude-4-5-sonnet-high", "claude-4-6-opus": "20260217_mini-v2.0.0_claude-4-6-opus",
        "deepseek-3-2": "20260217_mini-v2.0.0_deepseek-3-2-high", "gemini-3-flash": "20260217_mini-v2.0.0_gemini-3-flash-high",
        "gemini-3-pro": "20260226_mini-v2.0.0_gemini-3-pro-high", "glm-5": "20260217_mini-v2.0.0_glm-5-high",
        "gpt-5-2-high": "20260217_mini-v2.0.0_gpt-5-2-high", "gpt-5-mini": "20260217_mini-v2.0.0_gpt-5-mini",
        "kimi-k2-5": "20260217_mini-v2.0.0_kimi-k2-5-high", "minimax-2-5": "20260217_mini-v2.0.0_minimax-2-5-high"}
ml_entry = {}
for e in {k[0] for k in ml_cells}:
    model = e.split("_", 2)[2]
    if model in BOTH:
        ml_entry[model] = e
assert set(ml_entry) == set(BOTH), sorted(set(BOTH) - set(ml_entry))
ml_broke = {(b["submission"], b["task"]) for b in ml_breaks}
v_runs = [k for k in cells if k[0] in BOTH.values()]
m_runs = [k for k in ml_cells if k[0] in ml_entry.values()]
M["RyBothModels"] = (len(BOTH), "models in both samples (2.x on Verified; reasoning settings may differ)")
M["RyBothVerBreak"] = (pct(sum(k in broke_cells for k in v_runs) / len(v_runs)), "their Verified runs that break, %")
M["RyBothMLBreak"] = (pct(sum(k in ml_broke for k in m_runs) / len(m_runs)), "their Multilingual runs that break, %")
higher = 0
for model, ve in BOTH.items():
    vr = [k for k in v_runs if k[0] == ve]
    mr = [k for k in m_runs if k[0] == ml_entry[model]]
    higher += (sum(k in ml_broke for k in mr) / len(mr)) > (sum(k in broke_cells for k in vr) / len(vr))
M["RyBothMLHigher"] = (higher, "of those models, break more often on Multilingual")

# 11. A close pair among the 2.x entries; the Fig. 2 pair's broken endings on shared tasks.
models = {r["submission"]: r for r in csv.DictReader((VER / "models.csv").open())}
A, B = "20260217_mini-v2.0.0_deepseek-3-2-high", "20260217_mini-v2.0.0_gpt-5-2-high"
for tag, e in (("NewPairA", A), ("NewPairB", B)):
    M[f"Ry{tag}Resolve"] = (pct(float(models[e]["resolve_rate_leaderboard"]), 1), f"{e}: leaderboard resolve rate, %")
    M[f"Ry{tag}Exposure"] = (pct(float(models[e]["exposure_mean"]), 1), f"{e}: exposure, %")
assert abs(float(models[A]["resolve_rate_leaderboard"]) - float(models[B]["resolve_rate_leaderboard"])) <= 0.03
QA, QB = "20250802_mini-v1.0.0_qwen3-coder-480b-a35b-instruct", "20250726_mini-v1.0.0_gemini-2.5-pro"
shared = sorted({t for (e, t) in cells if e == QA} & {t for (e, t) in cells if e == QB})
check("RvPairSharedTasks", len(shared))
M["RyPairEndBrokenA"] = (sum(end_state(cells[(QA, t)]) == "True" for t in shared), "Qwen3-Coder runs ending broken, shared tasks")
M["RyPairEndBrokenB"] = (sum(end_state(cells[(QB, t)]) == "True" for t in shared), "Gemini 2.5 Pro runs ending broken, shared tasks")

# 12. The Multilingual rule check: the third pass, over all 20 cards with the rule written out (humancheck_ml.json).
import json
ml_check = json.load((ML / "humancheck_ml.json").open())
check("RvMLHumanAgree", ml_check["agree"])
third = [r for r in ml_check["rounds"] if r["round"] == 3][0]
assert third["answered"] == ml_check["cards"]
M["RyMLThirdAgree"] = (third["agree"], "third pass over all Multilingual cards, rule written out: agreements")
M["RyMLThirdKappa"] = (f"{third['kappa']:.2f}", "its Cohen's kappa")
M["RyMLThirdUnseenRuleSeen"] = (third["disagree"]["human_unseen_rule_seen"], "its cards called unseen that the rule calls seen")

print("% Third review round (paper/review3_numbers.py): every value recomputed from the package's tables.")
for name, (value, comment) in M.items():
    print(f"\\newcommand{{\\{name}}}{{{value}}} % {comment}")
