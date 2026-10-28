"""Every number the paper states, as LaTeX macros, straight from the replay report.

    python3 paper_numbers.py <report dir> > numbers.tex

Reads summary.json (and models.csv for the model comparison). Nothing in the paper's text is typed by hand:
\\input{numbers} and use the macros, so a re-run of the report re-states the paper.
"""
import csv
import json
import sys
from pathlib import Path

report = Path(sys.argv[1] if len(sys.argv) > 1 else "report")
s = json.loads((report / "summary.json").read_text())
main, ci, cells, checks, cross = s["overall_main"], s["overall_main_ci"], s["cells"], s["checks"], s["cross_model"]


def pct(x, digits=0):
    return "n/a" if x is None else f"{100 * x:.{digits}f}"


def num(x):
    """A count or a median: no trailing .0 on a whole number."""
    return "n/a" if x is None else (str(int(x)) if float(x).is_integer() else f"{x:.1f}")


def ci_text(key, digits=0):
    low, high = ci.get(key, (None, None))
    return "n/a" if low is None else f"{pct(low, digits)}--{pct(high, digits)}"


macros = {
    "RunsTotal": f"{cells['total']:,}",
    "RunsDone": f"{cells['done']:,}",
    "RunsMain": f"{cells['main']:,}",
    "RunsExact": cells["tiers"].get("exact", 0),
    "RunsUnsubmitted": cells["tiers"].get("unsubmitted", 0),
    "RunsDiverged": cells["tiers"].get("diverged", 0),
    "MainShare": pct(cells["main"] / cells["done"]) if cells["done"] else "n/a",
    "BreakAny": pct(main["runs_with_break_any"]),
    "BreakAnyCI": ci_text("runs_with_break_any"),
    "BreakTest": pct(main["runs_with_break_test"]),
    "BreakLoad": pct(main["runs_with_break_load"]),
    "Breaks": f"{main['intervals']:,}",
    "BreaksTest": main["intervals_test"],
    "BreaksLoad": main["intervals_load"],
    "BreakMedianLen": num(main["median_interval_duration"]),
    "RepairedShare": pct(main["repaired_share"]),
    "Unseen": pct(main["unseen_interval_share"]),
    "UnseenCI": ci_text("unseen_interval_share"),
    "Silent": pct(main["silent_interval_share"]),
    "UnseenNoTests": pct(main["unseen_no_tests_share"]),
    "UnseenRepaired": pct(main["unseen_repaired_share"]),
    "Exposure": pct(main["exposure_mean"], 1),
    "ExposureCI": ci_text("exposure_mean", 1),
    "ExposureFirstEdit": pct(main["exposure_after_first_edit_mean"], 1),
    "Wasted": pct(main["wasted_share_mean"], 1),
    "EndBroken": pct(main["end_tree_broken_share"]),
    "Shipped": pct(main["shipped_share"], 1),
    "ShippedCI": ci_text("shipped_share", 1),
    "ShippedRuns": f"{main['shipped_runs']:,}",
    "StopRuns": main["stop_runs"],
    "StopBroken": pct(main["stop_broken_share"]),
    "LimitStopRuns": main["limit_stop_runs"],
    "LimitStopBroken": pct(main["limit_stop_broken_share"]),
    "BrokenEnds": main["broken_end_runs"],
    "GuardKeeps": pct(main["guard_keeps_work_share"]),
    "GuardSolved": pct(main["guard_solved_share"]),
    "EverSolved": pct(main["ever_solved_share"]),
    "Overshoot": pct(main["overshoot_share"]),
    "Models": cross["models"],
    "Rho": "n/a" if cross["spearman"] is None else f"{cross['spearman']:.2f}",
    "RhoP": "n/a" if cross["p_value"] is None else (f"= {cross['p_value']:.3f}" if cross["p_value"] >= 0.001 else "< 0.001"),
    "FlakyExcluded": checks["flaky_excluded_total"],
    "DuplicateDisagree": checks["final_duplicate"]["disagreed"],
    "DuplicateCompared": f"{checks['final_duplicate']['compared']:,}",
    "PlantedPass": sum(1 for v in checks["planted"].values() if v["pass"]),
    "PlantedTotal": len(checks["planted"]),
    "ExitAgree": pct(checks["exit_status_agreement"]["matched"] / checks["exit_status_agreement"]["compared"], 1)
    if checks["exit_status_agreement"]["compared"] else "n/a",
    "ExitCompared": f"{checks['exit_status_agreement']['compared']:,}",
}
pairs = checks["resolved_agreement_exact"]
both = {k: v for k, v in pairs.items() if "None" not in k}
agree = sum(v for k, v in both.items() if k.split(",")[0].split("=")[1] == k.split(",")[1].split("=")[1])
macros["VerdictAgree"] = pct(agree / sum(both.values()), 1) if both else "n/a"
macros["VerdictCompared"] = f"{sum(both.values()):,}"

exposures, resolves = [], []
models_csv = report / "models.csv"
if models_csv.exists():
    for row in csv.DictReader(models_csv.open()):
        if row.get("exposure_mean") not in ("", "None") and row.get("runs") not in ("", "0"):
            exposures.append(float(row["exposure_mean"]))
        if row.get("resolve_rate_leaderboard") not in ("", "None"):
            resolves.append(float(row["resolve_rate_leaderboard"]))
macros["ExposureMin"] = pct(min(exposures), 1) if exposures else "n/a"
macros["ExposureMax"] = pct(max(exposures), 1) if exposures else "n/a"
macros["ResolveMin"] = pct(min(resolves)) if resolves else "n/a"
macros["ResolveMax"] = pct(max(resolves)) if resolves else "n/a"

# Breakdowns from the per-run and per-break rows: by scaffold era and by repository.
csv.field_size_limit(sys.maxsize)
cells_rows = [r for r in csv.DictReader((report / "cells.csv").open()) if r["main"] == "True"]
break_rows = [r for r in csv.DictReader((report / "intervals.csv").open()) if r["main"] == "True"]


def share(rows, key, value="True"):
    rows = [r for r in rows if r.get(key) not in ("", "None")]
    return sum(r[key] == value for r in rows) / len(rows) if rows else None


def mean_of(rows, key):
    values = [float(r[key]) for r in rows if r.get(key) not in ("", "None")]
    return sum(values) / len(values) if values else None


for era, tag in (("_mini-v1.", "Old"), ("_mini-v2.", "New")):
    runs = [r for r in cells_rows if era in r["submission"]]
    macros[f"Era{tag}Runs"] = len(runs)
    macros[f"Era{tag}Break"] = pct(share(runs, "any_break"))
    macros[f"Era{tag}Exposure"] = pct(mean_of(runs, "exposure"), 1)
    macros[f"Era{tag}Unseen"] = pct(share([b for b in break_rows if era in b["submission"]], "unseen"))
repos = sorted({r["task"].split("__")[0] for r in cells_rows})
repo_break = [share([r for r in cells_rows if r["task"].startswith(repo + "__")], "any_break") for repo in repos]
repo_unseen = [share([b for b in break_rows if b["task"].startswith(repo + "__")], "unseen") for repo in repos]
macros["Repos"] = len(repos)
macros["RepoBreakMin"], macros["RepoBreakMax"] = pct(min(repo_break)), pct(max(repo_break))
macros["RepoUnseenMin"], macros["RepoUnseenMax"] = pct(min(repo_unseen)), pct(max(repo_unseen))
macros["UnseenTest"] = pct(main["unseen_test_share"])
macros["UnseenLoad"] = pct(main["unseen_load_share"])
macros["UnseenOpen"] = main["unseen_open_breaks"]
macros["UnseenOpenTest"] = main["unseen_open_test_breaks"]
grades = checks["grade_agreement_main_submitted"]
agreeing = grades.get("both_clean", 0) + grades.get("same_breaks", 0)
macros["GradeAgree"] = pct(agreeing / sum(grades.values()), 1) if grades else "n/a"

# ------------------------------------------------------------------ the reviewers' re-analyses
import math  # noqa: E402
import random  # noqa: E402
import statistics  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402

BOOT, SEED = 2000, 20261023
tasks = sorted({r["task"] for r in cells_rows})


def boot_ci(stat, seed=SEED):
    """Percentile 95% interval of stat(task multiset) over task resamples, as the report's own intervals."""
    rng, values = random.Random(seed), []
    for _ in range(BOOT):
        value = stat([rng.choice(tasks) for _ in tasks])
        if value is not None:
            values.append(value)
    values.sort()
    return values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]


def by_task(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["task"]].append(row)
    return grouped


def pooled(grouped, sample, fn):
    return fn([row for task in sample for row in grouped.get(task, [])])


def share_true(rows, key):
    rows = [r for r in rows if r.get(key) in ("True", "False")]
    return sum(r[key] == "True" for r in rows) / len(rows) if rows else None


def wilson(k, n, z=1.96):
    p, den = k / n, 1 + z * z / n
    centre, half = (p + z * z / (2 * n)) / den, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


def ci_pct(pair, digits=0):
    return f"{pct(pair[0], digits)}--{pct(pair[1], digits)}"


# How breaks end: repaired, turned into the other kind, or still open when the run ended.
endings = Counter(b["ended"] if b["ended"] not in ("", "None") else "open" for b in break_rows)
macros["EndClean"], macros["EndChanged"], macros["EndOpen"] = endings["clean"], endings["changed"], endings["open"]
seen_rows = [b for b in break_rows if b["unseen"] == "False"]
unseen_rows = [b for b in break_rows if b["unseen"] == "True"]
macros["UnseenBreaks"] = len(unseen_rows)
macros["UnseenChanged"] = sum(b["ended"] == "changed" for b in unseen_rows)
macros["SeenRepaired"] = pct(sum(b["ended"] == "clean" for b in seen_rows) / len(seen_rows))

# One episode per stretch of broken code of either kind: breaks that hand over to the other kind are merged.
episodes = []
runs_breaks = defaultdict(list)
for b in break_rows:
    runs_breaks[(b["submission"], b["task"])].append(b)
for parts in runs_breaks.values():
    parts.sort(key=lambda b: int(b["onset"]))
    current = []
    for b in parts:
        previous = current[-1] if current else None
        if previous and previous["ended"] == "changed" and previous["repair"] not in ("", "None") \
                and int(previous["repair"]) == int(b["onset"]):
            current.append(b)
        else:
            if current:
                episodes.append(current)
            current = [b]
    if current:
        episodes.append(current)
judged = [e for e in episodes if all(b["unseen"] in ("True", "False") for b in e)]
macros["Episodes"] = f"{len(episodes):,}"
macros["EpisodeUnseen"] = pct(sum(all(b["unseen"] == "True" for b in e) for e in judged) / len(judged))
macros["EpisodeMedianLen"] = num(statistics.median(sum(int(b["duration"]) for b in e) for e in episodes))

# Stops: runs that end clean, and step caps at quantiles of run length (the tree after the cap-th command).
def end_state(r):
    return r["end_broken"] if r["recorded_submitted"] == "True" else r["stop_broken"]


clean_end = [r for r in cells_rows if end_state(r) == "False"]
macros["CleanEndRuns"] = f"{len(clean_end):,}"
macros["CleanEndExposure"] = pct(mean_of(clean_end, "exposure"), 1)
macros["CleanEndBreak"] = pct(share_true(clean_end, "any_break"))
state_rows = list(csv.DictReader((report / "states.csv").open()))
main_keys = {(r["submission"], r["task"]): r for r in cells_rows}
timeline = defaultdict(list)
for row in state_rows:
    if (row["submission"], row["task"]) in main_keys:
        timeline[(row["submission"], row["task"])].append((int(row["command"]), row["status"]))
lengths = sorted(int(r["commands"]) for r in cells_rows)


def cut_at(cap, rows):
    """Of the runs longer than cap commands, the share whose tree after the cap-th command is broken."""
    broken = measured = 0
    for r in rows:
        key = (r["submission"], r["task"])
        if int(r["commands"]) <= cap or key not in timeline:
            continue
        before = [status for command, status in sorted(timeline[key]) if command <= cap]  # states count commands from 1
        if before and before[-1] != "hang":
            measured += 1
            broken += before[-1] == "broken"
    return (broken / measured, measured) if measured else (None, 0)


grouped_cells = by_task(cells_rows)
for tag, q in (("Median", 0.5), ("Ninety", 0.9)):
    cap = lengths[int(q * len(lengths))]
    value, measured = cut_at(cap, cells_rows)
    macros[f"Cap{tag}"] = cap
    macros[f"Cap{tag}Runs"] = measured
    macros[f"Cap{tag}Broken"] = pct(value)
    macros[f"Cap{tag}CI"] = ci_pct(boot_ci(lambda sample, cap=cap: pooled(grouped_cells, sample, lambda rows: cut_at(cap, rows)[0])))
limit = [r for r in cells_rows if r["recorded_submitted"] == "False" and r["recorded_exit_status"] == "LimitsExceeded"
         and r["stop_broken"] in ("True", "False")]
macros["LimitStopCI"] = ci_pct(wilson(sum(r["stop_broken"] == "True" for r in limit), len(limit)))
macros["LimitStopModels"] = len({r["submission"] for r in limit})

# What a repaired break costs: resolves (none, task-stratified) and commands (on the same task).
def group(r):
    if r["any_break"] != "True":
        return "none"
    return {"False": "repaired", "True": "open"}.get(end_state(r), "unknown")


graded = [r for r in cells_rows if r["leaderboard_resolved"] in ("True", "False")]
for tag, name in (("None", "none"), ("Repaired", "repaired")):
    rows = [r for r in graded if group(r) == name]
    macros[f"Resolve{tag}"] = pct(sum(r["leaderboard_resolved"] == "True" for r in rows) / len(rows))
num_, den_ = 0.0, 0.0
for rows in by_task(graded).values():
    a = [r["leaderboard_resolved"] == "True" for r in rows if group(r) == "repaired"]
    b = [r["leaderboard_resolved"] == "True" for r in rows if group(r) == "none"]
    if a and b:
        weight = len(a) * len(b) / (len(a) + len(b))
        num_, den_ = num_ + weight * (sum(a) / len(a) - sum(b) / len(b)), den_ + weight
macros["ResolveDiffTask"] = f"{100 * num_ / den_:+.1f}"
ratios = []
for rows in by_task(cells_rows).values():
    a = [int(r["commands"]) for r in rows if group(r) == "repaired"]
    b = [int(r["commands"]) for r in rows if group(r) == "none"]
    if a and b:
        ratios.append(statistics.median(a) / statistics.median(b))
macros["CommandsRatio"] = f"{statistics.median(ratios):.1f}"

# Robustness: runs whose every command exited as recorded; runs whose verdict matches the leaderboard.
full = [r for r in cells_rows if r["rc_agreement"] not in ("", "None") and float(r["rc_agreement"]) == 1.0]
full_keys = {(r["submission"], r["task"]) for r in full}
macros["FullExitRuns"] = f"{len(full):,}"
macros["FullExitBreak"] = pct(share_true(full, "any_break"))
macros["FullExitUnseen"] = pct(share_true([b for b in break_rows if (b["submission"], b["task"]) in full_keys], "unseen"))
agree_keys = {(r["submission"], r["task"]) for r in graded if r["replay_resolved"] in ("True", "False")
              and r["replay_resolved"] == r["leaderboard_resolved"]}
macros["AgreeUnseen"] = pct(share_true([b for b in break_rows if (b["submission"], b["task"]) in agree_keys], "unseen"))
compared = [r for r in graded if r["replay_resolved"] in ("True", "False")]
disagree = [r for r in compared if r["replay_resolved"] != r["leaderboard_resolved"]]
top3 = Counter(r["task"] for r in disagree).most_common(3)
macros["VerdictDisagree"] = len(disagree)
macros["VerdictTopThree"] = sum(n for _, n in top3)

# Eras: unseen share with its interval; rank correlation within each era (permutation test).
grouped_breaks = by_task(break_rows)
for era, tag in (("_mini-v1.", "Old"), ("_mini-v2.", "New")):
    rows = [b for b in break_rows if era in b["submission"]]
    grouped = by_task(rows)
    macros[f"Era{tag}Breaks"] = len(rows)
    macros[f"Era{tag}UnseenCI"] = ci_pct(boot_ci(lambda sample, g=grouped: pooled(g, sample, lambda rs: share_true(rs, "unseen"))))


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out, i = [0.0] * len(values), 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return cov / math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))


def permutation_p(x, y, n=20000, seed=SEED):
    rng, observed, shuffled, hits = random.Random(seed), abs(spearman(x, y)), list(y), 0
    for _ in range(n):
        rng.shuffle(shuffled)
        hits += abs(spearman(x, shuffled)) >= observed
    return (hits + 1) / (n + 1)


model_rows = [r for r in csv.DictReader(models_csv.open())
              if r.get("exposure_mean") not in ("", "None") and r.get("resolve_rate_leaderboard") not in ("", "None")]
for era, tag in (("_mini-v1.", "Old"), ("_mini-v2.", "New")):
    rows = [r for r in model_rows if era in r["submission"]]
    x = [float(r["resolve_rate_leaderboard"]) for r in rows]
    y = [float(r["exposure_mean"]) for r in rows]
    p_value = permutation_p(x, y)
    macros[f"Era{tag}Models"] = len(rows)
    macros[f"Rho{tag}"] = f"{spearman(x, y):.2f}"
    macros[f"Rho{tag}P"] = f"= {p_value:.2f}" if p_value >= 0.001 else "< 0.001"
    macros[f"Era{tag}ExposureMin"], macros[f"Era{tag}ExposureMax"] = pct(min(y), 1), pct(max(y), 1)

# The model pairs the text compares: same scaffold version and release, alike in resolve rate.
by_name = {r["submission"]: r for r in csv.DictReader(models_csv.open())}
PAIRS = (("PairA", "20250802_mini-v1.0.0_qwen3-coder-480b-a35b-instruct", "PairB", "20250726_mini-v1.0.0_gemini-2.5-pro"),
         ("PairC", "20260217_mini-v2.0.0_kimi-k2-5-high", "PairD", "20260217_mini-v2.0.0_gpt-5-2-high"))
for tag_a, name_a, tag_b, name_b in PAIRS:
    for tag, name in ((tag_a, name_a), (tag_b, name_b)):
        row = by_name[name]
        macros[f"{tag}Resolve"] = pct(float(row["resolve_rate_leaderboard"]))
        macros[f"{tag}Exposure"] = pct(float(row["exposure_mean"]), 1)
        macros[f"{tag}Runs"] = row["runs"]
    a = {r["task"]: float(r["exposure"]) for r in cells_rows if r["submission"] == name_a and r["exposure"] not in ("", "None")}
    b = {r["task"]: float(r["exposure"]) for r in cells_rows if r["submission"] == name_b and r["exposure"] not in ("", "None")}
    common = sorted(set(a) & set(b))

    def diff(sample, a=a, b=b, common=set(common)):
        kept = [t for t in sample if t in common]
        return statistics.mean(a[t] - b[t] for t in kept) if kept else None

    low, high = boot_ci(diff)
    macros[f"{tag_a}{tag_b}Diff"] = pct(statistics.mean(a[t] - b[t] for t in common), 1)
    macros[f"{tag_a}{tag_b}DiffCI"] = f"{pct(low, 1)}--{pct(high, 1)}"
    macros[f"{tag_a}{tag_b}Tasks"] = len(common)

# What cheaper checks would catch; what the grade ignores; how the grade and our label disagree.
macros["SyntaxShare"] = pct(main["syntax_error_share"])
macros["SyntaxLoadShare"] = pct(main["syntax_error_load_share"])
macros["SkipOnly"] = main["skip_only_breaks"]
macros["GradeOfficialOnly"] = grades.get("official_only", 0)
macros["GradeOursOnly"] = grades.get("ours_only", 0)
macros["GradeBothDifferent"] = grades.get("both_different", 0)
macros["GradeDisagree"] = sum(v for k, v in grades.items() if k not in ("both_clean", "same_breaks"))
macros["GradeCompared"] = f"{sum(grades.values()):,}"
official_only = Counter(r["task"] for r in cells_rows if r["grade_agreement"] == "official_only")
macros["GradeOneTask"] = official_only.most_common(1)[0][1] if official_only else 0
shipped_rows = [r for r in cells_rows if r["recorded_submitted"] == "True" and r["shipped_any"] in ("True", "False")]
failed_grading = official_only.most_common(1)[0][0] if official_only else None
kept = [r for r in shipped_rows if not (r["task"] == failed_grading and r["grade_agreement"] == "official_only")]
macros["ShippedNoGradeFail"] = pct(sum(r["shipped_any"] == "True" for r in kept) / len(kept), 1)

# Machine-side checks (machine_extras.py), when present beside the report.
extras_path = report / "extras_machine.json"
if extras_path.exists():
    extras = json.loads(extras_path.read_text())
    printed, searched = extras["printed"], extras["searched"]
    abbreviated = 0
    for sample in printed.get("samples", []):
        def norm(text):
            import re
            return re.sub(r"(?m)^index [0-9a-f]+\.\.[0-9a-f]+", "index", text)
        if norm(sample["recorded"]) != sample["recorded"] and norm(sample["recorded"])[:1500] == norm(sample["replayed"])[:1500]:
            abbreviated += 1
    macros["PrintCompared"] = f"{printed['compared']:,}"
    macros["PrintSame"] = pct(printed["same"] / printed["compared"], 1)
    macros["PrintSameNorm"] = pct((printed["same"] + abbreviated) / printed["compared"], 1)
    macros["SearchCompared"] = f"{searched['compared']:,}"
    macros["SearchSame"] = pct(searched["same"] / searched["compared"], 1)
    macros["ReplayMedianMin"] = f"{extras['seconds_median'] / 60:.1f}"
    macros["ReplayNinetyMin"] = f"{extras['seconds_p90'] / 60:.0f}"
    macros["CellHours"] = f"{extras['cell_hours']:.0f}"
    macros["StatesTested"] = f"{extras['states_tested']:,}"
    macros["SpendMain"] = f"{extras['model_cost_total']:.0f}"
    macros["SpendBroken"] = f"{extras['model_cost_on_broken']:.0f}"
    macros["SpendBrokenShare"] = pct(extras["model_cost_on_broken"] / extras["model_cost_total"], 1)
    macros["RunsInstalling"] = pct(extras["runs_installing"] / extras["runs"])
macros["RunsMissing"] = cells["total"] - cells["done"]
macros["GuardSolvedRuns"] = sum(r.get("guard_solved") == "True" for r in cells_rows)

# The skeptic's checks: breaks no compile check finds; the run population final-patch grading cannot see; stability.
non_syntax = [b for b in break_rows if b.get("syntax_error") == "False"]
macros["NonSyntaxRuns"] = pct(len({(b["submission"], b["task"]) for b in non_syntax}) / len(cells_rows))
macros["NonSyntaxUnseen"] = pct(share_true(non_syntax, "unseen"))
macros["NonSyntaxOpen"] = sum(b["ended"] in ("", "None") for b in non_syntax)
macros["OneCommandBreaks"] = sum(int(b["duration"]) == 1 for b in break_rows)
macros["HangStates"] = sum(int(r["states_hang"] or 0) for r in cells_rows)
macros["UnknownStates"] = sum(int(r["states_unknown"] or 0) for r in cells_rows)
macros["StatesObserved"] = f"{sum(int(r['observations'] or 0) for r in cells_rows):,}"
macros["BreakRepairClean"] = pct(sum(r["any_break"] == "True" and end_state(r) == "False" for r in cells_rows) / len(cells_rows))
macros["UnseenOpenShare"] = pct(sum(b["ended"] in ("", "None") for b in unseen_rows) / len(unseen_rows))
macros["SeenOpenShare"] = pct(sum(b["ended"] in ("", "None") for b in seen_rows) / len(seen_rows))
halves = defaultdict(lambda: ([], []))
order = {task: i % 2 for i, task in enumerate(tasks)}
for r in cells_rows:
    if r["exposure"] not in ("", "None"):
        halves[r["submission"]][order[r["task"]]].append(float(r["exposure"]))
both_halves = [v for v in halves.values() if v[0] and v[1]]
macros["SplitHalf"] = f"{spearman([statistics.mean(v[0]) for v in both_halves], [statistics.mean(v[1]) for v in both_halves]):.2f}"
if extras_path.exists():
    installing = {tuple(x) for x in extras["installing"]}
    plain = [r for r in cells_rows if (r["submission"], r["task"]) not in installing]
    plain_keys = {(r["submission"], r["task"]) for r in plain}
    macros["NoInstallRuns"] = f"{len(plain):,}"
    macros["NoInstallUnseen"] = pct(share_true([b for b in break_rows if (b["submission"], b["task"]) in plain_keys], "unseen"))
    macros["NoInstallBreak"] = pct(share_true(plain, "any_break"))

# R4 without hand-picking: every pair of models on the same scaffold version within 3 points of resolve rate.
import itertools  # noqa: E402

exp_by = defaultdict(dict)
for r in cells_rows:
    if r["exposure"] not in ("", "None"):
        exp_by[r["submission"]][r["task"]] = float(r["exposure"])
alike = []
for a, b in itertools.combinations(model_rows, 2):
    if a["submission"].split("_")[1] != b["submission"].split("_")[1]:
        continue
    if abs(float(a["resolve_rate_leaderboard"]) - float(b["resolve_rate_leaderboard"])) > 0.03:
        continue
    hi, lo = sorted((a, b), key=lambda m: -float(m["exposure_mean"]))
    common = set(exp_by[hi["submission"]]) & set(exp_by[lo["submission"]])

    def gap(sample, hi=hi["submission"], lo=lo["submission"], common=common):
        kept = [t for t in sample if t in common]
        return statistics.mean(exp_by[hi][t] - exp_by[lo][t] for t in kept) if kept else None

    ratio = float(hi["exposure_mean"]) / max(float(lo["exposure_mean"]), 1e-9)
    alike.append((ratio, boot_ci(gap)[0] > 0))
macros["PairsAlike"] = len(alike)
macros["PairsTwoFold"] = sum(ratio >= 2 for ratio, _ in alike)
macros["PairsReliable"] = sum(reliable for _, reliable in alike)
macros["SyntaxTest"] = sum(b["kind"] == "test" and b.get("syntax_error") == "True" for b in break_rows)
macros["SyntaxLoad"] = sum(b["kind"] == "load" and b.get("syntax_error") == "True" for b in break_rows)


# Intervals for the cost comparison (task bootstrap): resolve difference on the same task, and the commands ratio.
def repaired_vs_none(sample):
    num_, den_ = 0.0, 0.0
    for task in sample:
        rows = [r for r in graded if r["task"] == task]
        a = [r["leaderboard_resolved"] == "True" for r in rows if group(r) == "repaired"]
        b = [r["leaderboard_resolved"] == "True" for r in rows if group(r) == "none"]
        if a and b:
            weight = len(a) * len(b) / (len(a) + len(b))
            num_, den_ = num_ + weight * (sum(a) / len(a) - sum(b) / len(b)), den_ + weight
    return num_ / den_ if den_ else None


def commands_ratio(sample):
    values = []
    for task in sample:
        rows = [r for r in cells_rows if r["task"] == task]
        a = [int(r["commands"]) for r in rows if group(r) == "repaired"]
        b = [int(r["commands"]) for r in rows if group(r) == "none"]
        if a and b:
            values.append(statistics.median(a) / statistics.median(b))
    return statistics.median(values) if values else None


low, high = boot_ci(repaired_vs_none)
macros["ResolveDiffTaskCI"] = f"${100 * low:+.1f}$ to ${100 * high:+.1f}$"
low, high = boot_ci(commands_ratio)
macros["CommandsRatioCI"] = f"{low:.1f}--{high:.1f}"

# Without the three tasks the replay grades differently from the leaderboard.
three = {task for task, _ in top3}
rest = [r for r in cells_rows if r["task"] not in three]
rest_keys = {(r["submission"], r["task"]) for r in rest}
macros["RestRuns"] = f"{len(rest):,}"
macros["RestBreak"] = pct(share_true(rest, "any_break"))
macros["RestUnseen"] = pct(share_true([b for b in break_rows if (b["submission"], b["task"]) in rest_keys], "unseen"))
# The final replay pool's wall clock (pool.log: 09:01:32 to 17:15:26 UTC) at the machine's $1.8144 an hour.
macros["ReplayWallHours"] = "8.2"
macros["ReplayDollars"] = f"{8.23 * 1.8144:.0f}"

# Robustness columns (Table I): exposure over each subset.
macros["FullExitExposure"] = pct(mean_of(full, "exposure"), 1)
macros["RestExposure"] = pct(mean_of(rest, "exposure"), 1)
if extras_path.exists():
    macros["NoInstallExposure"] = pct(mean_of(plain, "exposure"), 1)
non_syntax_keys = {(b["submission"], b["task"]) for b in non_syntax}
# A log-only rule: flag every tree-changing command that no test run follows before the next one (baseline_rule.py).
rule_path = report / "baseline_rule.json"
if rule_path.exists():
    rule = json.loads(rule_path.read_text())
    macros["RuleEdits"] = f"{rule['edits']:,}"
    macros["RuleFlagRate"] = pct(rule["flag_rate"])
    macros["RulePrecision"] = pct(rule["precision"])
    macros["RuleRecall"] = pct(rule["recall"])
# Table I's last column: the range of each headline measure over the three robustness subsets.
def span(values, digits=0):
    values = [v for v in values if v is not None]
    return f"{pct(min(values), digits)}--{pct(max(values), digits)}"


if extras_path.exists():
    macros["RangeBreak"] = span([share_true(full, "any_break"), share_true(plain, "any_break"), share_true(rest, "any_break")])
    macros["RangeUnseen"] = span([share_true([b for b in break_rows if (b["submission"], b["task"]) in keys], "unseen")
                                  for keys in (full_keys, plain_keys, rest_keys)])
    macros["RangeExposure"] = span([mean_of(full, "exposure"), mean_of(plain, "exposure"), mean_of(rest, "exposure")], 1)

# The P2 pilot: a model judge (Claude Sonnet 5.5) reads the agent's log at sampled steps (judge/judge.py).
judge_path = report / "judge_summary.json"
if judge_path.exists():
    judged = json.loads(judge_path.read_text())

    def jshare(key):
        return judged[key]["share"], f"{judged[key]['ci'][0]}--{judged[key]['ci'][1]}", judged[key]["n"]

    for tag, key in (("Unseen", "BROKEN on unseen_break"), ("Seen", "BROKEN on seen_break"), ("Clean", "BROKEN on clean"),
                     ("UnseenSyntax", "  unseen_break syntax=True"), ("UnseenNoSyntax", "  unseen_break syntax=False"),
                     ("UnseenTest", "  unseen_break kind=test"), ("UnseenLoad", "  unseen_break kind=load")):
        value, ci, n = jshare(key)
        macros[f"Judge{tag}"], macros[f"Judge{tag}CI"], macros[f"Judge{tag}N"] = value, ci, n
    macros["JudgeCost"] = "6"  # all calls incl. both dry runs and the re-asked 16 (judge/run.log), Bedrock list prices
# The judge study with two judges (judge/analyse2.py): Sonnet 5.5 and Opus 5.5 on the same sampled commands.
judge2_path = report / "judge_summary2.json"
if judge2_path.exists():
    judged2 = json.loads(judge2_path.read_text())
    for tag, name in (("Sonnet", "sonnet"), ("Opus", "opus")):
        for row, key in (("Unseen", "unseen"), ("Load", "unseen_load"), ("Test", "unseen_test"), ("Seen", "seen"),
                         ("Clean", "clean")):
            cell = judged2[name][key]
            macros[f"J{tag}{row}"] = cell["share"]
            macros[f"J{tag}{row}CI"] = f"{cell['ci'][0]}--{cell['ci'][1]}"
            macros[f"J{tag}{row}N"] = cell["n"]
    macros["JudgeBothMissed"] = judged2["unseen_missed_by_both"]
    macros["JudgeBothN"] = judged2["opus"]["unseen"]["n"]
    macros["JudgeTotalCost"] = f"{judged2['sonnet']['cost'] + judged2['opus']['cost']:.0f}"
# Runs that end broken, and how many of them show nothing in the log.
broken_end = [r for r in cells_rows if end_state(r) == "True"]
macros["EndBrokenRuns"] = len(broken_end)
macros["EndBrokenRunsShare"] = pct(len(broken_end) / len(cells_rows), 1)
macros["EndBrokenUnseenShare"] = pct(main["unseen_open_breaks"] / len(broken_end))
macros["UnseenOpenShareRuns"] = pct(main["unseen_open_breaks"] / len(cells_rows), 1)
if rule_path.exists():
    macros["RuleBase"] = pct(rule["broken_edits"] / rule["edits"])
# R4 on runs that end clean, and stability within one scaffold version.
clean_by = defaultdict(list)
for r in clean_end:
    if r["exposure"] not in ("", "None"):
        clean_by[r["submission"]].append(float(r["exposure"]))
for tag, name in (("PairA", PAIRS[0][1]), ("PairB", PAIRS[0][3])):
    macros[f"{tag}CleanExposure"] = pct(statistics.mean(clean_by[name]), 1)
old_halves = [v for k, v in halves.items() if "_mini-v1." in k and v[0] and v[1]]
macros["SplitHalfOld"] = f"{spearman([statistics.mean(v[0]) for v in old_halves], [statistics.mean(v[1]) for v in old_halves]):.2f}"

# The final review's checks: is seeing a break tied to its ending; is exposure run length in disguise.
def open_gap(rows):
    unseen_ = [b["ended"] in ("", "None") for b in rows if b["unseen"] == "True"]
    seen_ = [b["ended"] in ("", "None") for b in rows if b["unseen"] == "False"]
    return sum(unseen_) / len(unseen_) - sum(seen_) / len(seen_) if unseen_ and seen_ else None


macros["OpenGap"] = f"{100 * open_gap(break_rows):.0f}"
low, high = boot_ci(lambda sample: pooled(grouped_breaks, sample, open_gap))
macros["OpenGapCI"] = f"{100 * low:.0f}--{100 * high:.0f}"
new_halves = [v for k, v in halves.items() if "_mini-v2." in k and v[0] and v[1]]
macros["SplitHalfNew"] = f"{spearman([statistics.mean(v[0]) for v in new_halves], [statistics.mean(v[1]) for v in new_halves]):.2f}"
for era, tag in (("_mini-v1.", "Old"), ("_mini-v2.", "New")):
    names = sorted({r["submission"] for r in cells_rows if era in r["submission"]})
    exposure_ = [mean_of([r for r in cells_rows if r["submission"] == n], "exposure") for n in names]
    length_ = [statistics.mean(int(r["commands"]) for r in cells_rows if r["submission"] == n) for n in names]
    macros[f"RhoLength{tag}"] = f"{spearman(exposure_, length_):.2f}"
edits_by = Counter((row["submission"], row["task"]) for row in state_rows if row["trigger"] == "tool")
for tag, name in (("PairA", PAIRS[0][1]), ("PairB", PAIRS[0][3])):
    runs_ = [r for r in cells_rows if r["submission"] == name]
    edits_ = sum(edits_by[(r["submission"], r["task"])] for r in runs_)
    macros[f"{tag}BreaksPerEdits"] = f"{100 * sum(b['submission'] == name for b in break_rows) / edits_:.0f}"
    macros[f"{tag}FirstEditExposure"] = pct(mean_of(runs_, "exposure_after_first_edit"))
macros["TotalCommands"] = f"{sum(int(r['commands']) for r in cells_rows):,}"
# Fisher's exact test on the example task: runs that saw the test fail vs not, by repaired vs submitted broken.
def fisher_p(a, b, c, d):
    n, row1, col1 = a + b + c + d, a + b, a + c

    def prob(x):
        return math.comb(row1, x) * math.comb(n - row1, col1 - x) / math.comb(n, col1)

    observed = prob(a)
    return sum(prob(x) for x in range(max(0, col1 - (n - row1)), min(row1, col1) + 1) if prob(x) <= observed + 1e-12)


# The lead example: one task, one previously passing test, broken by many runs.
EX_TASK, EX_TEST = "django__django-11490", "test_combining_multiple_models (queries.test_qs_combinators.QuerySetSetOperationTests)"
ex_runs = defaultdict(list)
for b in break_rows:
    if b["task"] == EX_TASK and EX_TEST in b["tests"].split(";"):
        ex_runs[(b["submission"], b["task"])].append(b)
ex_open = [k for k, bs in ex_runs.items() if any(b["ended"] in ("", "None") for b in bs)]
ex_fixed = [k for k in ex_runs if k not in ex_open]
macros["ExRuns"] = sum(r["task"] == EX_TASK for r in cells_rows)
macros["ExBroke"] = len(ex_runs)
macros["ExShipped"] = len(ex_open)
macros["ExShippedUnseen"] = sum(any(b["ended"] in ("", "None") and b["unseen"] == "True" for b in ex_runs[k]) for k in ex_open)
macros["ExFixed"] = len(ex_fixed)
macros["ExFixedSeen"] = sum(any(b["unseen"] == "False" for b in ex_runs[k]) for k in ex_fixed)  # saw it fail at least once
macros["ExFixedResolved"] = sum(main_keys[k]["leaderboard_resolved"] == "True" for k in ex_fixed)
shipped_seen = macros["ExShipped"] - macros["ExShippedUnseen"]
fixed_unseen = macros["ExFixed"] - macros["ExFixedSeen"]
p_ex = fisher_p(macros["ExFixedSeen"], shipped_seen, fixed_unseen, macros["ExShippedUnseen"])
macros["ExFisher"] = "10^{-6}" if p_ex < 1e-6 else f"{p_ex:.1g}"
macros["ExFisherBelow"] = "< 10^{-6}" if p_ex < 1e-6 else f"= {p_ex:.1g}"
# The audits (counts kept beside the report by hand from each round's verdicts: audit.json).
audit_path = report / "audit.json"
if audit_path.exists():
    audit = json.loads(audit_path.read_text())
    macros["AuditBreaks"] = audit["breaks"]
    macros["AuditRounds"] = audit["rounds"]
    macros["AuditLastAgree"] = audit["last_agree"]
    macros["AuditLastTotal"] = audit["last_total"]
    macros["AuditLastCI"] = ci_pct(wilson(audit["last_agree"], audit["last_total"]))
else:
    for name in ("AuditBreaks", "AuditRounds", "AuditLastAgree", "AuditLastTotal"):
        macros[name] = "\\XX{}"

# The human check (one author, blind to the rule's labels, judged 40 cards: humancheck.json).
human_path = report / "humancheck.json"
if human_path.exists():
    human = json.loads(human_path.read_text())
    macros["HumanCards"] = human["cards"]
    macros["HumanAnswered"] = human["answered"]
    macros["HumanAgree"] = human["agree"]
    macros["HumanAgreeShare"] = pct(human["agree"] / human["answered"])
    macros["HumanKappa"] = f"{human['kappa']:.2f}"
    macros["HumanDisagree"] = human["answered"] - human["agree"]
    macros["HumanCantTell"] = human["cant_tell"]
    macros["HumanSeenOnly"] = human["disagree"]["human_seen_rule_unseen"]
    macros["HumanUnseenOnly"] = human["disagree"]["human_unseen_rule_seen"]
    second = human.get("second_labeller")
    if second:
        macros["HumanSecondAgree"] = second["agree_with_first"]

for name, value in macros.items():
    print(f"\\newcommand{{\\{name}}}{{{value}}}")
