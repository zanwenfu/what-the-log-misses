"""The numbers the review round asked for, as LaTeX macros (prefix Rv), from the two replay reports.

    python3 review_numbers.py <Verified report dir> <Multilingual report dir> > numbers_review.tex

- Transient breaks: repaired, clean, by the very next command that changes the code. Lasting: every other break.
- Judge precision at the natural rate: break-starting edits over edits made on clean code, the judges' recall
  weighted by the natural mix of unseen and seen breaks, and their false-alarm rate on clean edits (Wilson interval).
- RQ3 on runs that end clean, and per-model intervals for the two models the text compares.
- Multilingual's unseen share under a deliberately loose rule (liberal.json, computed on the replay machine).
"""
import csv, json, random, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)
VER, ML = Path(sys.argv[1]), Path(sys.argv[2])
SEED, BOOT = 20261023, 2000


def pct(x, digits=0):
    return f"{100 * x:.{digits}f}"


def load(report):
    cells = {(r["submission"], r["task"]): r for r in csv.DictReader((report / "cells.csv").open()) if r["main"] == "True"}
    states = defaultdict(set)
    for r in csv.DictReader((report / "states.csv").open()):
        if (r["submission"], r["task"]) in cells and r["trigger"] != "final":
            states[(r["submission"], r["task"])].add(int(r["command"]))
    breaks = [b for b in csv.DictReader((report / "intervals.csv").open()) if b["main"] == "True"]
    return cells, {k: sorted(v) for k, v in states.items()}, breaks


def transient(b, states):
    if b["ended"] != "clean" or b["repair"] in ("", "None"):
        return False
    later = [c for c in states.get((b["submission"], b["task"]), []) if c > int(b["onset"])]
    return bool(later) and later[0] == int(b["repair"])


def split(report, tag, macros):
    cells, states, breaks = load(report)
    lasting = [b for b in breaks if not transient(b, states)]
    runs_l = {(b["submission"], b["task"]) for b in lasting}
    runs_lu = {(b["submission"], b["task"]) for b in lasting if b["unseen"] == "True"}
    judged = [b for b in lasting if b["unseen"] in ("True", "False")]
    macros[f"Rv{tag}Transient"] = pct(1 - len(lasting) / len(breaks))
    macros[f"Rv{tag}LastingRuns"] = pct(len(runs_l) / len(cells))
    macros[f"Rv{tag}LastingUnseenRuns"] = pct(len(runs_lu) / len(cells))
    macros[f"Rv{tag}LastingUnseen"] = pct(sum(b["unseen"] == "True" for b in judged) / len(judged))
    macros[f"Rv{tag}LastingOpen"] = pct(sum(b["ended"] in ("", "None") for b in lasting) / len(lasting))
    tasks = sorted({k[1] for k in cells}); rng = random.Random(SEED)
    runs_by_task = Counter(k[1] for k in cells); lu_by_task = Counter(k[1] for k in runs_lu)
    draws = []
    for _ in range(BOOT):
        smp = [rng.choice(tasks) for _ in tasks]
        draws.append(sum(lu_by_task[t] for t in smp) / sum(runs_by_task[t] for t in smp))
    draws.sort()
    macros[f"Rv{tag}LastingUnseenRunsCI"] = f"{pct(draws[int(.025 * BOOT)])}--{pct(draws[int(.975 * BOOT) - 1])}"
    # Among lasting breaks only (a transient break is repaired by definition): the share still open at the end, for
    # unseen and seen breaks, and a task-bootstrap interval for the difference.
    by_task = defaultdict(list)
    for b in judged:
        by_task[b["task"]].append((b["unseen"] == "True", b["ended"] in ("", "None")))
    def open_gap(smp):
        rows = [x for t in smp for x in by_task.get(t, [])]
        u = [o for s, o in rows if s]; v = [o for s, o in rows if not s]
        return (sum(u) / len(u), sum(v) / len(v)) if u and v else None
    u_open, s_open = open_gap(tasks)
    macros[f"Rv{tag}LastingUnseenOpen"], macros[f"Rv{tag}LastingSeenOpen"] = pct(u_open), pct(s_open)
    macros[f"Rv{tag}LastingOpenGap"] = pct(u_open - s_open)
    gaps = sorted(g[0] - g[1] for g in (open_gap([rng.choice(tasks) for _ in tasks]) for _ in range(BOOT)) if g)
    macros[f"Rv{tag}LastingOpenGapCI"] = f"{pct(gaps[int(.025 * len(gaps))])}--{pct(gaps[int(.975 * len(gaps)) - 1])}"
    # The same comparison only for breaks with at least 10 commands left in the run (late breaks are both less often
    # seen and less often repaired, which alone can produce a gap).
    ncmd = {k: int(r["commands"]) for k, r in cells.items()}
    late = defaultdict(list)
    for b in judged:
        if ncmd[(b["submission"], b["task"])] - int(b["onset"]) >= 10:
            late[b["task"]].append((b["unseen"] == "True", b["ended"] in ("", "None")))
    rows10 = [x for t in tasks for x in late.get(t, [])]
    macros[f"Rv{tag}LateUnseenOpen"] = pct(sum(o for s_, o in rows10 if s_) / max(1, sum(1 for s_, _ in rows10 if s_)))
    macros[f"Rv{tag}LateSeenOpen"] = pct(sum(o for s_, o in rows10 if not s_) / max(1, sum(1 for s_, _ in rows10 if not s_)))
    # Runs whose code ends on a break the log never showed, with a task-bootstrap interval.
    end_unseen = Counter(b["task"] for b in breaks if b["unseen"] == "True" and b["ended"] in ("", "None"))
    macros[f"Rv{tag}EndUnseenRuns"] = pct(sum(end_unseen.values()) / len(cells), 1)
    draws = []
    for _ in range(BOOT):
        smp = [rng.choice(tasks) for _ in tasks]
        draws.append(sum(end_unseen[t] for t in smp) / sum(runs_by_task[t] for t in smp))
    draws.sort()
    macros[f"Rv{tag}EndUnseenRunsCI"] = f"{pct(draws[int(.025 * BOOT)], 1)}--{pct(draws[int(.975 * BOOT) - 1], 1)}"
    eb_by = Counter(k[1] for k, r in cells.items() if (r["end_broken"] if r["recorded_submitted"] == "True" else r["stop_broken"]) == "True")
    draws = []
    for _ in range(BOOT):
        smp = [rng.choice(tasks) for _ in tasks]
        draws.append(sum(eb_by[t] for t in smp) / sum(runs_by_task[t] for t in smp))
    draws.sort()
    macros[f"Rv{tag}EndBrokenRunsCI"] = f"{pct(draws[int(.025 * BOOT)], 1)}--{pct(draws[int(.975 * BOOT) - 1], 1)}"
    return cells, breaks


macros = {}
vcells, vbreaks = split(VER, "", macros)
# Of the runs that fail on the leaderboard, the share that end with a previously passing test broken, and of those the
# share whose break the log never showed; task-bootstrap interval for the first.
def _end(r):
    return r["end_broken"] if r["recorded_submitted"] == "True" else r["stop_broken"]
_open_unseen = {(b["submission"], b["task"]) for b in vbreaks if b["unseen"] == "True" and b["ended"] in ("", "None")}
_failed = [k for k, r in vcells.items() if r["leaderboard_resolved"] == "False"]
_fb = [k for k in _failed if _end(vcells[k]) == "True"]
macros["RvFailedRuns"] = len(_failed)
_eb_by = Counter(k[1] for k, r in vcells.items() if _end(r) == "True"); _all_by = Counter(k[1] for k in vcells)
_t = sorted(_all_by); _r = random.Random(SEED); _dd = []
for _ in range(BOOT):
    _smp = [_r.choice(_t) for _ in _t]; _dd.append(sum(_eb_by[x] for x in _smp) / sum(_all_by[x] for x in _smp))
_dd.sort(); macros["RvEndBrokenCI"] = f"{pct(_dd[int(.025 * BOOT)], 1)}--{pct(_dd[int(.975 * BOOT) - 1], 1)}"
_graded = [k for k, r in vcells.items() if r["leaderboard_resolved"] in ("True", "False")]
_resolved = [k for k in _graded if vcells[k]["leaderboard_resolved"] == "True"]
macros["RvRunsWithGrade"] = f"{len(_graded):,}"
macros["RvResolvedRuns"] = len(_resolved)
macros["RvResolvedEndBroken"] = sum(_end(vcells[k]) == "True" for k in _resolved)
_both = [k for k in _graded if vcells[k]["replay_resolved"] in ("True", "False")]
_match = [k for k in _both if vcells[k]["replay_resolved"] == vcells[k]["leaderboard_resolved"]]
macros["RvGradeCompared"] = f"{len(_both):,}"
macros["RvGradeMatchRuns"] = f"{len(_match):,}"
_mset = set(_match)
macros["RvMatchBreakAny"] = pct(sum(vcells[k]["any_break"] == "True" for k in _match) / len(_match))
_mb = [b for b in vbreaks if (b["submission"], b["task"]) in _mset]
macros["RvMatchUnseen"] = pct(sum(b["unseen"] == "True" for b in _mb) / len(_mb))
macros["RvMatchExposure"] = pct(statistics.mean(float(vcells[k]["exposure"]) for k in _match if vcells[k]["exposure"] not in ("", "None")), 1)
# The two models the text compares, on the same tasks: paired difference in exposure with a task bootstrap.
_A, _B = "20250802_mini-v1.0.0_qwen3-coder-480b-a35b-instruct", "20250726_mini-v1.0.0_gemini-2.5-pro"
_ea = {k[1]: float(r["exposure"]) for k, r in vcells.items() if k[0] == _A and r["exposure"] not in ("", "None")}
_eb = {k[1]: float(r["exposure"]) for k, r in vcells.items() if k[0] == _B and r["exposure"] not in ("", "None")}
_common = sorted(set(_ea) & set(_eb)); _rng2 = random.Random(SEED)
_dd = sorted(statistics.mean(_ea[t] - _eb[t] for t in (_rng2.choice(_common) for _ in _common)) for _ in range(BOOT))
macros["RvPairDiff"] = pct(statistics.mean(_ea[t] - _eb[t] for t in _common))
macros["RvPairSharedTasks"] = len(_common)
macros["RvPairSharedResolvedA"] = sum(vcells[_A, t]["leaderboard_resolved"] == "True" for t in _common)
macros["RvPairSharedResolvedB"] = sum(vcells[_B, t]["leaderboard_resolved"] == "True" for t in _common)
macros["RvPairDiffCI"] = f"{pct(_dd[int(.025 * BOOT)])}--{pct(_dd[int(.975 * BOOT) - 1])}"
macros["RvFailedEndBroken"] = pct(len(_fb) / len(_failed))
macros["RvFailedEndBrokenUnseen"] = pct(sum(k in _open_unseen for k in _fb) / len(_fb))
_tasks = sorted({k[1] for k in vcells}); _rng = random.Random(SEED); _d = []
_f_by, _fb_by = Counter(k[1] for k in _failed), Counter(k[1] for k in _fb)
for _ in range(BOOT):
    _smp = [_rng.choice(_tasks) for _ in _tasks]
    _n = sum(_f_by[t] for t in _smp)
    if _n:
        _d.append(sum(_fb_by[t] for t in _smp) / _n)
_d.sort()
macros["RvFailedEndBrokenCI"] = f"{pct(_d[int(.025 * len(_d))])}--{pct(_d[int(.975 * len(_d)) - 1])}"
# Failed runs that end broken although every fix test passes: the regression alone cost the task.
_fixed = [k for k in _fb if vcells[k]["f2p_total"] not in ("", "None") and int(vcells[k]["f2p_total"]) > 0
          and int(vcells[k]["f2p_passing_end"]) == int(vcells[k]["f2p_total"])]
macros["RvFailedOnlyRegression"] = len(_fixed)
macros["RvFailedOnlyRegressionShare"] = pct(len(_fixed) / len(_failed))
macros["RvUngradedRuns"] = len(vcells) - len(_graded)
split(ML, "ML", macros)

# Judge precision at the natural rate: among edits made on clean code (the population the judges' two classes come
# from: an edit that starts a break, or one that leaves the code clean), the share that start a break.
numbers = {k: v for k, v in (line.split("}{", 1) for line in Path("numbers.tex").read_text().splitlines() if line.startswith("\\newcommand"))}
def num(name):
    return float(numbers["\\newcommand{\\" + name].rstrip("}").replace(",", ""))
seq = defaultdict(list)
for r in csv.DictReader((VER / "states.csv").open()):
    if (r["submission"], r["task"]) in vcells and r["trigger"] != "final":
        seq[(r["submission"], r["task"])].append((int(r["seq"]), r["status"]))
on_clean = onsets = 0
for v in seq.values():
    v.sort()
    for (_, before), (_, after) in zip(v, v[1:]):
        if before == "ok":
            on_clean += 1
            onsets += after != "ok"
prevalence = onsets / on_clean
macros["RvOnsetEdits"], macros["RvCleanEdits"] = onsets, f"{on_clean:,}"


def wilson(k, n, z=1.96):
    p_hat = k / n; d = 1 + z * z / n; c = p_hat + z * z / (2 * n)
    h = z * (p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) ** 0.5
    return (c - h) / d, (c + h) / d


unseen_share = num("Unseen") / 100
for judge in ("Sonnet", "Opus"):
    recall = unseen_share * num(f"J{judge}Unseen") / 100 + (1 - unseen_share) * num(f"J{judge}Seen") / 100
    k, n = num(f"J{judge}Clean"), num(f"J{judge}CleanN")
    def precision(false_alarm):
        return recall * prevalence / (recall * prevalence + false_alarm * (1 - prevalence))
    low, high = wilson(round(k * n / 100), int(n))
    macros[f"Rv{judge}Precision"] = pct(precision(k / 100))
    macros[f"Rv{judge}PrecisionCI"] = f"{pct(precision(high))}--{pct(precision(low))}"
macros["RvEditsPerBreak"] = f"{1 / prevalence:.0f}"
# After a free syntax check: only breaks that are not syntax errors remain to be caught by reading the log.
first = {}
for r in csv.DictReader((VER / "states.csv").open()):
    k = (r["submission"], r["task"])
    if k in vcells and r["trigger"] != "final":
        first.setdefault(k, []).append((int(r["seq"]), int(r["command"]), r["status"]))
before_cmd = {}
for k, v in first.items():
    v.sort()
    for (_, _, s0), (_, c1, _) in zip(v, v[1:]):
        before_cmd[(k, c1)] = s0
non_syntax_onsets = sum(1 for b in vbreaks if b["syntax_error"] == "False"
                        and before_cmd.get(((b["submission"], b["task"]), int(b["onset"]))) == "ok")
post = non_syntax_onsets / on_clean
macros["RvPostSyntaxEditsPerBreak"] = f"{1 / post:.0f}"
for judge in ("Sonnet", "Opus"):
    recall = num(f"J{judge}Test") / 100
    false_alarm = num(f"J{judge}Clean") / 100
    macros[f"Rv{judge}PostSyntaxPrecision"] = pct(recall * post / (recall * post + false_alarm * (1 - post)))
load_breaks = [b for b in vbreaks if b["kind"] == "load"]
macros["RvSyntaxOfLoad"] = pct(sum(b["syntax_error"] == "True" for b in load_breaks) / len(load_breaks))


# RQ3 among runs that end clean, within each scaffold version.
def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y); mx, my = statistics.mean(rx), statistics.mean(ry)
    num_ = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return num_ / (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5


def end_state(r):
    return r["end_broken"] if r["recorded_submitted"] == "True" else r["stop_broken"]


models = {r["submission"]: r for r in csv.DictReader((VER / "models.csv").open())}
for era, tag in (("_mini-v1.", "Old"), ("_mini-v2.", "New")):
    by = defaultdict(list)
    for r in vcells.values():
        if era in r["submission"] and end_state(r) == "False" and r["exposure"] not in ("", "None"):
            by[r["submission"]].append(float(r["exposure"]))
    pairs = [(float(models[s]["resolve_rate_leaderboard"]), statistics.mean(v)) for s, v in by.items()
             if models.get(s, {}).get("resolve_rate_leaderboard") not in (None, "", "None")]
    macros[f"RvRhoClean{tag}"] = f"{spearman([a for a, _ in pairs], [b for _, b in pairs]):.2f}"
rng = random.Random(SEED)
for tag, name in (("A", "20250802_mini-v1.0.0_qwen3-coder-480b-a35b-instruct"), ("B", "20250726_mini-v1.0.0_gemini-2.5-pro")):
    clean_v = [float(r["exposure"]) for (s, _), r in vcells.items() if s == name and end_state(r) == "False"
               and r["exposure"] not in ("", "None")]
    macros[f"RvPair{tag}Clean"] = pct(statistics.mean(clean_v), 1)
    v = [float(r["exposure"]) for (s, _), r in vcells.items() if s == name and r["exposure"] not in ("", "None")]
    draws = sorted(statistics.mean(rng.choice(v) for _ in v) for _ in range(BOOT))
    macros[f"RvPair{tag}CI"] = f"{pct(draws[int(.025 * BOOT)], 1)}--{pct(draws[int(.975 * BOOT) - 1], 1)}"

onset = json.loads((VER / "baseline_onset.json").read_text())  # baseline_onset.py, on the replay machine
macros["RvBaselineRecall"] = pct(onset["recall"])
macros["RvBaselinePrecision"] = pct(onset["precision"])
macros["RvBaselineFlagRate"] = pct(onset["flag_rate"])
# Four log readers on the same sampled commands (judge/analyse3.py): shares, precision at the natural rate and after a
# syntax check, and the labelled examples' effect on Sonnet.
j3 = json.loads((VER / "judge_summary3.json").read_text())
macros["RvJudgeCommon"] = j3["common_items"]
for name, tag in (("sonnet", "S"), ("opus", "O"), ("deepseek", "D"), ("sonnet_examples", "X")):
    for g, gt in (("unseen", "Unseen"), ("unseen_load", "Load"), ("unseen_test", "Test"), ("seen", "Seen"), ("clean", "Clean")):
        macros[f"RvJ{tag}{gt}"] = j3[name][g]["share"]
        macros[f"RvJ{tag}{gt}N"] = j3[name][g]["n"]
    macros[f"RvJ{tag}Prec"] = j3[name]["precision"]
    macros[f"RvJ{tag}PrecCI"] = f"{j3[name]['precision_ci'][0]}--{j3[name]['precision_ci'][1]}"
    macros[f"RvJ{tag}PostSyn"] = j3[name]["precision_after_syntax_check"]
ex = j3["examples_effect_on_sonnet"]["unseen"]
macros["RvExFlipUp"], macros["RvExFlipDown"], macros["RvExN"] = ex["to_broken"], ex["to_ok"], ex["n"]
# Whole-run judges (judge/judge_full.py, analyse_full.py): every edit of 150 random kept runs, precision as measured.
full = json.loads((VER / "judge_summary_full.json").read_text())
macros["RvFullRuns"], macros["RvFullOnsets"] = full["opus"]["runs"], full["opus"]["onsets"]
macros["RvFullCleanEdits"] = full["opus"]["edits_on_clean"]
for name, tag in (("sonnet", "S"), ("opus", "O")):
    macros[f"RvFull{tag}Recall"] = full[name]["recall"]
    macros[f"RvFull{tag}Prec"] = full[name]["precision"]
    macros[f"RvFull{tag}PrecCI"] = f"{full[name]['precision_ci'][0]}--{full[name]['precision_ci'][1]}"
    macros[f"RvFull{tag}PostSyn"] = full[name]["precision_after_syntax"]
human_ml = json.loads((ML / "humancheck_ml.json").read_text())
macros["RvMLHumanCards"], macros["RvMLHumanAnswered"] = human_ml["cards"], human_ml["answered"]
macros["RvMLHumanAgree"] = human_ml["agree"]
macros["RvMLHumanKappa"] = f"{human_ml['kappa']:.2f}"
macros["RvMLHumanRuleSeen"] = human_ml["disagree"]["human_unseen_rule_seen"]
# The edited-file error clause that stands in for missing error text on Multilingual, applied to Verified as a check.
macros["RvVerFileClauseUnseen"] = round(json.loads((VER / "fileclause_ver_nowarn.json").read_text())["summary"]["share_after"])
liberal = json.loads((ML / "liberal.json").read_text())
macros["RvMLUnseenLiberal"] = pct(liberal["unseen_liberal"] / liberal["breaks"])

for name, value in macros.items():
    print(f"\\newcommand{{\\{name}}}{{{value}}}")
