"""The fourth review round's analyses for "What the Log Misses", as LaTeX macros (prefix Rz).

    python3 -I paper/review4_numbers.py <package dir> > paper/numbers_review4.tex

<package dir> is the replication package (README.md, data/, judge/, paper/). Plain Python, standard library only, one
process; a few seconds. Nothing is written except the macros on standard output.

First the script recomputes the numbers it builds on and stops unless each equals the package's numbers*.tex. Then:
  1. How breaks become seen: whether a test ran during the break, and how often such a test run showed it; by year.
  2. The six models run under both scaffold versions, on shared tasks: unseen shares of syntax errors and of other
     breaks, the share of breaks during which tests ran, and commands per run.
  3. Exposure and run length: in the close pairs (same scaffold version, resolve rates within 3 points), commands per
     run and commands on broken code, on shared tasks; Spearman's rho between an entry's exposure and its commands
     per run within each scaffold version.
  4. Runs that end on an unseen break: how many of these breaks last at most 12 commands (the human check's range).
  5. The judges with every run by a DeepSeek agent left out (DeepSeek V3.2 is both a judge and, twice, an agent).
  6. The leaderboard's own per-task averages over all 500 tasks (data/verified/leaderboard_meta.csv, read from each
     entry's metadata.yaml in github.com/SWE-bench/experiments): model calls and dollars per task against exposure,
     and the reasoning settings of the six models run under both scaffold versions.
  7. What the logs show of scaffold 2.0.0's shell (data/verified/log_signs_*.csv, from code/scripts/log_signs.py).
  8. How entries edit (data/verified/edit_methods.csv): the break rate of each edit method on clean code, and the
     share of an entry's edits made with sed against its exposure.
  9. For the rewritten text: how often the log showed breaks during which no test ran; the whole-run judges as counts
     (alarms per edit, chance level); the runs that submitted code failing only a previously passing test, with one
     task left out at a time.
"""
import csv
import itertools
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

PKG = Path(sys.argv[1])
VER = PKG / "data" / "verified"
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
for name in ("numbers.tex", "numbers_ml.tex", "numbers_review.tex", "numbers_extra.tex", "numbers_review2.tex",
             "numbers_review3.tex"):
    paper.update(read_macros(PKG / "paper" / name))


def pct(x, digits=0):
    return f"{100 * x:.{digits}f}"


def check(name, value):
    assert str(value) == paper[name], f"{name}: recomputed {value!r}, paper has {paper[name]!r}"


cells = {(r["submission"], r["task"]): r for r in csv.DictReader((VER / "cells.csv").open()) if r["main"] == "True"}
breaks = [b for b in csv.DictReader((VER / "intervals.csv").open()) if b["main"] == "True"]
models = {r["submission"]: r for r in csv.DictReader((VER / "models.csv").open())}
judged = [b for b in breaks if b["unseen"] in ("True", "False")]
yes = "True".__eq__


def is_open(b):
    return b["ended"] in ("", "None")


def has(value):
    return value not in ("", "None", None)


# ---------------------------------------------------------------- the numbers this script builds on
check("RunsMain", f"{len(cells):,}")
check("Breaks", f"{len(breaks):,}")
check("Unseen", pct(sum(yes(b["unseen"]) for b in judged) / len(judged)))
check("RyRanTestsBreaks", sum(yes(b["ran_tests"]) for b in judged))
check("RyNamedOnlySeen", sum(not yes(b["unseen"]) and not yes(b["saw_failure"]) for b in judged))
end_unseen = [b for b in judged if is_open(b) and yes(b["unseen"])]
check("XtEndUnseenRunsN", len(end_unseen))
check("XtNoSynEndUnseenRunsN", sum(not yes(b["syntax_error"]) for b in end_unseen))

M = {}

# 1. How breaks become seen.
seen = [b for b in judged if not yes(b["unseen"])]
tested = [b for b in judged if yes(b["ran_tests"])]
M["RzSeenNamedOnlyShare"] = (pct(sum(not yes(b["saw_failure"]) for b in seen) / len(seen)),
                             "% of seen breaks shown only by other output naming a broken test or printing its error")
M["RzTestedSeen"] = (sum(not yes(b["unseen"]) for b in tested), "breaks during which tests ran that the log showed")
M["RzTestedSeenShare"] = (pct(sum(not yes(b["unseen"]) for b in tested) / len(tested)), "the same, % of those breaks")
for tag, part in (("Old", OLD), ("New", NEW)):
    bs = [b for b in judged if part in b["submission"]]
    sb = [b for b in bs if not yes(b["unseen"])]
    M[f"RzEra{tag}RanTests"] = (pct(sum(yes(b["ran_tests"]) for b in bs) / len(bs)),
                                f"{part[6:]}x entries: % of breaks during which tests ran")
    M[f"RzEra{tag}NamedOnly"] = (pct(sum(not yes(b["saw_failure"]) for b in sb) / len(sb)),
                                 f"{part[6:]}x entries: % of seen breaks shown only by other output")
    M[f"RzEra{tag}SeenByTests"] = (pct(sum(yes(b["saw_failure"]) for b in bs) / len(bs)),
                                   f"{part[6:]}x entries: % of breaks a test run showed")
    M[f"RzEra{tag}SeenByOther"] = (pct(len(sb) / len(bs) - sum(yes(b["saw_failure"]) for b in bs) / len(bs)),
                                   f"{part[6:]}x entries: % of breaks only other output showed")
    M[f"RzEra{tag}SyntaxSeenByOther"] = (pct(sum(not yes(b["unseen"]) and not yes(b["saw_failure"]) for b in bs if yes(b["syntax_error"]))
                                             / sum(yes(b["syntax_error"]) for b in bs)),
                                         f"{part[6:]}x entries: % of syntax-error breaks only other output showed")

# 2. The six models run under both scaffold versions (review3_numbers.py, item 7), on shared tasks.
SAME = (("20250807_mini-v1.7.0_gpt-5-mini", "20260217_mini-v2.0.0_gpt-5-mini"),
        ("20251211_mini-v1.17.2_gpt-5.2-2025-12-11-high", "20260217_mini-v2.0.0_gpt-5-2-high"),
        ("20251201_mini-v1.17.1_deepseek-v3.2-reasoner", "20260217_mini-v2.0.0_deepseek-3-2-high"),
        ("20251124_mini-v1.16.0_claude-opus-4-5-20251101", "20260217_mini-v2.0.0_claude-4-5-opus-high"),
        ("20250929_mini-v1.13.3_sonnet-4-5-20250929", "20260217_mini-v2.0.0_claude-4-5-sonnet-high"),
        ("20251118_mini-v1.15.0_gemini-3-pro-preview-20251118", "20260226_mini-v2.0.0_gemini-3-pro-high"))
by_cell = defaultdict(list)
for b in judged:
    by_cell[(b["submission"], b["task"])].append(b)
tally = {"Old": Counter(), "New": Counter()}
for old, new in SAME:
    shared = {t for (e, t) in cells if e == old} & {t for (e, t) in cells if e == new}
    for tag, entry in (("Old", old), ("New", new)):
        c = tally[tag]
        for t in shared:
            c["runs"] += 1
            c["cmds"] += int(cells[(entry, t)]["commands"])
            for b in by_cell.get((entry, t), []):
                kind = "syn" if yes(b["syntax_error"]) else "oth"
                c["n"] += 1
                c["u"] += yes(b["unseen"])
                c[kind] += 1
                c[kind + "_u"] += yes(b["unseen"])
                c["tested"] += yes(b["ran_tests"])
for tag in ("Old", "New"):
    c, label = tally[tag], "1.x" if tag == "Old" else "2.x"
    check(f"RySame{tag}Unseen", pct(c["u"] / c["n"]))
    M[f"RzSame{tag}SyntaxShare"] = (pct(c["syn"] / c["n"]), f"same six models under {label}: % of breaks that are syntax errors")
    M[f"RzSame{tag}SyntaxUnseen"] = (pct(c["syn_u"] / c["syn"]), f"same, % of syntax errors unseen")
    M[f"RzSame{tag}OtherUnseen"] = (pct(c["oth_u"] / c["oth"]), f"same, % of other breaks unseen")
    M[f"RzSame{tag}RanTests"] = (pct(c["tested"] / c["n"]), f"same, % of breaks during which tests ran")
    M[f"RzSame{tag}Cmds"] = (f"{c['cmds'] / c['runs']:.0f}", f"same, commands per run")

# 3. Exposure and run length.
rows = [m for m in models.values() if has(m.get("exposure_mean")) and has(m.get("resolve_rate_leaderboard"))]
pairs = []
for a, b in itertools.combinations(rows, 2):
    if a["submission"].split("_")[1] != b["submission"].split("_")[1]:
        continue
    if abs(float(a["resolve_rate_leaderboard"]) - float(b["resolve_rate_leaderboard"])) > 0.03:
        continue
    hi, lo = sorted((a["submission"], b["submission"]), key=lambda s: -float(models[s]["exposure_mean"]))
    shared = sorted({t for (e, t) in cells if e == hi} & {t for (e, t) in cells if e == lo})

    def per_run(entry, fn, shared=shared):
        return statistics.mean(fn(cells[(entry, t)]) for t in shared)

    cmds = lambda r: int(r["commands"])
    broken = lambda r: float(r["exposure"]) * int(r["commands"])  # exposure = broken commands / commands
    pairs.append({"hi": hi, "lo": lo, "fold": float(models[hi]["exposure_mean"]) / max(float(models[lo]["exposure_mean"]), 1e-9),
                  "cmds": (per_run(hi, cmds), per_run(lo, cmds)), "broken": (per_run(hi, broken), per_run(lo, broken))})
check("PairsAlike", len(pairs))
check("PairsTwoFold", sum(p["fold"] >= 2 for p in pairs))
M["RzPairsMoreCmds"] = (sum(p["cmds"][0] > p["cmds"][1] for p in pairs),
                        "close pairs whose more exposed entry takes more commands per run (shared tasks)")
M["RzPairsTwoFoldMoreCmds"] = (sum(p["cmds"][0] > p["cmds"][1] for p in pairs if p["fold"] >= 2),
                               "of the two-fold pairs, those whose more exposed entry takes more commands per run")
M["RzPairsExtraCmds"] = (f"{statistics.median(p['cmds'][0] - p['cmds'][1] for p in pairs):.0f}",
                         "median over close pairs: extra commands per run of the more exposed entry")
M["RzPairsExtraBroken"] = (f"{statistics.median(p['broken'][0] - p['broken'][1] for p in pairs):.0f}",
                           "median over close pairs: extra commands per run on broken code")
fig = [p for p in pairs if "qwen3-coder" in p["hi"] and "gemini-2.5-pro" in p["lo"]]
assert len(fig) == 1
M["RzPairACmds"] = (f"{fig[0]['cmds'][0]:.0f}", "Qwen3-Coder: commands per run, tasks shared with Gemini 2.5 Pro")
M["RzPairBCmds"] = (f"{fig[0]['cmds'][1]:.0f}", "Gemini 2.5 Pro: commands per run, shared tasks")
M["RzPairABroken"] = (f"{fig[0]['broken'][0]:.0f}", "Qwen3-Coder: commands per run on broken code, shared tasks")
M["RzPairBBroken"] = (f"{fig[0]['broken'][1]:.0f}", "Gemini 2.5 Pro: commands per run on broken code, shared tasks")


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):  # average ranks for ties
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def spearman(xs, ys):
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return num / (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5


for tag, part in (("Old", OLD), ("New", NEW)):
    es = sorted({e for (e, t) in cells if part in e})
    exposure = [statistics.mean(float(cells[k]["exposure"]) for k in cells if k[0] == e) for e in es]
    cmds = [statistics.mean(int(cells[k]["commands"]) for k in cells if k[0] == e) for e in es]
    resolve = [float(models[e]["resolve_rate_leaderboard"]) for e in es]
    M[f"RzRhoCmds{tag}"] = (f"{spearman(exposure, cmds):.2f}", f"{part[6:]}x entries: Spearman rho, exposure vs commands per run")
    M[f"RzRhoResCmds{tag}"] = (f"{spearman(resolve, cmds):.2f}", f"{part[6:]}x entries: Spearman rho, resolve rate vs commands per run")

# 4. Runs that end on an unseen break: the break's length against the human check's range (at most 12 commands).
M["RzEndUnseenShort"] = (sum(int(b["duration"]) <= 12 for b in end_unseen),
                         "runs ending on an unseen break whose break lasts at most 12 commands")
M["RzEndUnseenLong"] = (sum(int(b["duration"]) > 12 for b in end_unseen), "the same, longer than 12 commands")

# 5. The judges with every run by a DeepSeek agent left out (cf. review2_numbers.py, item 8, for Anthropic agents).
JFILES = {"Sonnet": "results.jsonl", "Opus": "results_opus.jsonl", "DeepSeek": "results_deepseek.jsonl",
          "+ex.": "results_sonnet_examples.jsonl"}


def jk(r):
    return (r["kind"], r["submission"], r["task"], r["step"])


answers = {n: {jk(r): r for r in map(json.loads, (PKG / "judge" / f).open()) if r.get("verdict") in ("BROKEN", "OK")}
           for n, f in JFILES.items()}
common = set.intersection(*(set(v) for v in answers.values()))
check("RvJudgeCommon", len(common))
deepseek = lambda s: "deepseek" in s.lower()
shift = {}
for n, rows_ in answers.items():
    for kind in ("unseen_break", "seen_break", "clean"):
        ks = [k for k in common if k[0] == kind]
        kept = [k for k in ks if not deepseek(k[1])]
        rate = lambda keys: 100 * sum(rows_[k]["verdict"] == "BROKEN" for k in keys) / len(keys)
        shift[(n, kind)] = rate(kept) - rate(ks)
M["RzNoDeepSeekItems"] = (sum(deepseek(k[1]) for k in common), "sampled commands from runs by DeepSeek agents")
M["RzNoDeepSeekOwnMax"] = (f"{max(abs(shift[('DeepSeek', k)]) for k in ('unseen_break', 'seen_break', 'clean')):.1f}",
                           "largest change in the DeepSeek judge's flag rates with those runs left out (points)")
M["RzNoDeepSeekAllMax"] = (f"{max(abs(v) for v in shift.values()):.1f}", "the same, over every judge and row")

# 6. The leaderboard's own averages over all 500 tasks.
meta = {r["submission"]: r for r in csv.DictReader((VER / "leaderboard_meta.csv").open())}
assert set(meta) == set(models), "leaderboard_meta.csv covers every entry"
for tag, part in (("Old", OLD), ("New", NEW)):
    es = sorted(s for s in models if part in s)
    exposure = [float(models[s]["exposure_mean"]) for s in es]
    M[f"RzRhoCalls{tag}"] = (f"{spearman(exposure, [float(meta[s]['instance_calls']) for s in es]):.2f}",
                             f"{part[6:]}x entries: Spearman rho, exposure vs the leaderboard's model calls per task (500 tasks)")
    priced = [s for s in es if has(meta[s]["instance_cost"])]
    M[f"RzRhoDollars{tag}"] = (f"{spearman([float(models[s]['exposure_mean']) for s in priced], [float(meta[s]['instance_cost']) for s in priced]):.2f}",
                               f"{part[6:]}x entries: Spearman rho, exposure vs the leaderboard's dollars per task ({len(priced)} priced)")
calls = lambda s: float(meta[s]["instance_calls"])
M["RzPairsMoreCalls"] = (sum(calls(p["hi"]) > calls(p["lo"]) for p in pairs),
                         "close pairs whose more exposed entry makes more model calls per task on all 500 tasks")
M["RzPairACalls"] = (f"{calls(fig[0]['hi']):.0f}", "Qwen3-Coder: the leaderboard's model calls per task")
M["RzPairBCalls"] = (f"{calls(fig[0]['lo']):.0f}", "Gemini 2.5 Pro: the leaderboard's model calls per task")
M["RzPairADollars"] = (f"{float(meta[fig[0]['hi']]['instance_cost']):.2f}", "Qwen3-Coder: the leaderboard's dollars per task")
M["RzPairBDollars"] = (f"{float(meta[fig[0]['lo']]['instance_cost']):.2f}", "Gemini 2.5 Pro: the leaderboard's dollars per task")
high = lambda s: meta[s]["reasoning_effort"] == "high"
M["RzSameHighOld"] = (sum(high(o) for o, n in SAME), "of the six models run under both versions: entries listed as high reasoning under 1.x")
M["RzSameHighNew"] = (sum(high(n) for o, n in SAME), "the same under 2.x")
# Scaffold 2.0.0 ran each command with `bash -c` and no BASH_ENV, outside the image's testbed environment
# (code/replaykit/benchmarks/public_replay.py, needs_plain_shell); later releases (2.4.2 here) source .bashrc again.
new_runs = [k for k in cells if NEW in k[0]]
new_end_unseen = sum(NEW in b["submission"] for b in end_unseen)
M["RzEraNewEndUnseenOneIn"] = (f"{len(new_runs) / new_end_unseen:.0f}", "2026 entries: one run in this many ends on an unseen break")
M["RzEntriesPlainShell"] = (sum("_mini-v2.0.0_" in s for s in {e for (e, t) in cells}), "kept 2026 entries run with scaffold 2.0.0 (plain shell)")

# 7. What the logs show of scaffold 2.0.0's shell.
signs = {(r["submission"], r["task"]): r for r in csv.DictReader((VER / "log_signs_runs.csv").open())}
assert set(signs) == set(cells), "log_signs_runs.csv covers every kept run"
assert all(int(signs[k]["commands"]) == int(cells[k]["commands"]) for k in cells)
plain = lambda s: "_mini-v2.0.0_" in s
for tag, keep in (("Plain", lambda s: plain(s)), ("Login", lambda s: not plain(s))):
    ks = [k for k in signs if keep(k[0])]
    for col, name in (("base_python", "BasePy"), ("pip_install", "Pip"), ("no_module", "NoModule")):
        M[f"Rz{name}{tag}"] = (pct(sum(signs[k][col] == "True" for k in ks) / len(ks)),
                               f"% of {'2.0.0' if tag == 'Plain' else 'all other'} runs whose log shows {col}")
before = {(r["submission"], r["task"], r["onset"]): r["base_python_before"] == "True"
          for r in csv.DictReader((VER / "log_signs_breaks.csv").open())}
b20 = [b for b in judged if plain(b["submission"])]
for tag, flag in (("Shown", True), ("NotShown", False)):
    bs = [b for b in b20 if before[(b["submission"], b["task"], b["onset"])] == flag]
    M[f"RzBasePy{tag}Breaks"] = (len(bs), f"2.0.0 breaks whose log {'shows' if flag else 'does not show'} the base Python before the break")
    M[f"RzBasePy{tag}Unseen"] = (pct(sum(yes(b["unseen"]) for b in bs) / len(bs)), "the same, % unseen")

# 8. How entries edit.
em = defaultdict(Counter)
for r in csv.DictReader((VER / "edit_methods.csv").open()):
    em[r["submission"]][r["method"] + ":e"] += int(r["edits_on_clean"])
    em[r["submission"]][r["method"] + ":b"] += int(r["breaks_started"])
    em[r["submission"]]["e"] += int(r["edits_on_clean"])
    em[r["submission"]]["b"] += int(r["breaks_started"])
check("RvCleanEdits", f"{sum(c['e'] for c in em.values()):,}")
check("RvOnsetEdits", sum(c["b"] for c in em.values()))
for m, name in (("sed", "Sed"), ("python", "Python"), ("heredoc", "Heredoc")):
    e, b = sum(c[m + ":e"] for c in em.values()), sum(c[m + ":b"] for c in em.values())
    M[f"Rz{name}Edits"] = (f"{e:,}", f"edits on clean code made with {m}")
    M[f"Rz{name}BreakRate"] = (pct(b / e), f"% of them that start a break")
es = sorted(em)
sed_share = [em[e]["sed:e"] / em[e]["e"] for e in es]
M["RzRhoSedExposure"] = (f"{spearman(sed_share, [float(models[e]['exposure_mean']) for e in es]):.2f}",
                         f"all {len(es)} entries: Spearman rho, share of edits on clean code made with sed vs exposure")
both = [e for e in es if em[e]["sed:e"] >= 10 and em[e]["python:e"] >= 10]
M["RzSedVsPythonEntries"] = (len(both), "entries with at least 10 sed and 10 Python edits on clean code")
M["RzSedWorseEntries"] = (sum(em[e]["sed:b"] / em[e]["sed:e"] > em[e]["python:b"] / em[e]["python:e"] for e in both),
                          "of them, entries whose sed edits start breaks more often than their Python edits")
qa, gb = fig[0]["hi"], fig[0]["lo"]
M["RzPairASedEdits"] = (em[qa]["sed:e"], "Qwen3-Coder: sed edits on clean code (all its runs)")
M["RzPairBSedEdits"] = (em[gb]["sed:e"], "Gemini 2.5 Pro: sed edits on clean code (all its runs)")
M["RzPairASedBreak"] = (pct(em[qa]["sed:b"] / em[qa]["sed:e"]), "Qwen3-Coder: % of its sed edits that start a break")
M["RzPairBSedBreak"] = (pct(em[gb]["sed:b"] / em[gb]["sed:e"]), "Gemini 2.5 Pro: % of its sed edits that start a break")

# 9. Numbers for the rewritten text.
untested = [b for b in judged if not yes(b["ran_tests"])]
M["RzUntestedSeenShare"] = (pct(sum(not yes(b["unseen"]) for b in untested) / len(untested)),
                            "% of breaks during which no test ran that the log still showed (other output)")
W = json.loads((VER / "judge_summary_full.json").read_text())
check("RvFullCleanEdits", W["opus"]["edits_on_clean"])
check("RvFullOnsets", W["opus"]["onsets"])
for tag, name in (("S", "sonnet"), ("O", "opus")):
    M[f"RzFull{tag}Gate"] = (pct(W[name]["flags"] / W[name]["edits_on_clean"]), f"whole runs: % of edits on clean code {name} flags")
M["RzFullBase"] = (pct(W["opus"]["onsets"] / W["opus"]["edits_on_clean"]), "whole runs: % of edits on clean code that start a break (chance precision)")
def only_reg_sub(r):
    return (r["leaderboard_resolved"] == "False" and r["recorded_submitted"] == "True" and r["end_broken"] == "True"
            and has(r["f2p_total"]) and int(r["f2p_total"]) > 0 and int(r["f2p_passing_end"]) == int(r["f2p_total"]))
check("RyOnlyRegSubRuns", sum(only_reg_sub(r) for r in cells.values()))
tasks = sorted({t for (_, t) in cells})
drops = []
for t in tasks:
    rest = [r for k, r in cells.items() if k[1] != t]
    drops.append(sum(only_reg_sub(r) for r in rest) / len(rest))
M["RzOnlyRegSubDropMin"] = (pct(min(drops), 1), "% of kept runs that submitted code failing only a previously passing test, lowest with one task left out")
M["RzOnlyRegSubDropMax"] = (pct(max(drops), 1), "the same, highest")
top = Counter(t for (e, t), r in cells.items() if only_reg_sub(r)).most_common(1)[0]
M["RzOnlyRegSubTopTask"] = (top[1], f"most of those runs from one task ({top[0]})")

# 10. Multilingual: breaks during which tests ran (for Table II).
ml = [b for b in csv.DictReader((PKG / "data" / "multilingual" / "intervals.csv").open())
      if b["main"] == "True" and b["unseen"] in ("True", "False")]
check("MLUnseen", pct(sum(yes(b["unseen"]) for b in ml) / len(ml)))
M["RzMLRanTestsShare"] = (pct(sum(yes(b["ran_tests"]) for b in ml) / len(ml)), "Multilingual: % of breaks during which tests ran")
mlt = [b for b in ml if yes(b["ran_tests"])]
M["RzMLTestedSeenShare"] = (pct(sum(not yes(b["unseen"]) for b in mlt) / len(mlt)), "Multilingual: % of those the log showed")

# 11. Claims audit of the rewritten text (Oct 28, evening).
# (a) Breaks during which tests ran: how often the log named the broken test or printed its error (not just any failure).
M["RzTestedNamedShare"] = (pct(sum(yes(b["named"]) for b in tested) / len(tested)),
                           "% of breaks during which tests ran whose log named the broken test or printed its error")
# (b) Step-level judges as a gate: share of edits on clean code flagged at the natural mix, from Table III's flag rates.
check("RxJSRecall", paper["RxJSRecall"])
base = int(paper["RvOnsetEdits"].replace(",", "")) / int(paper["RvCleanEdits"].replace(",", ""))
for tag in ("S", "O"):
    recall, clean = int(paper[f"RxJ{tag}Recall"]) / 100, int(paper[f"RvJ{tag}Clean"]) / 100
    M[f"RzStepGate{tag}"] = (pct(base * recall + (1 - base) * clean), f"step-level judge {tag}: % of edits on clean code flagged at the natural break rate")
# (c) Edit methods within each scaffold version.
for tag, part in (("Old", OLD), ("New", NEW)):
    es_v = [e for e in es if part in e]
    M[f"RzRhoSedExposure{tag}"] = (f"{spearman([em[e]['sed:e'] / em[e]['e'] for e in es_v], [float(models[e]['exposure_mean']) for e in es_v]):.2f}",
                                   f"{part[6:]}x entries: Spearman rho, share of clean-code edits made with sed vs exposure")
    se, sb = sum(em[e]["sed:e"] for e in es_v), sum(em[e]["sed:b"] for e in es_v)
    pe, pb = sum(em[e]["python:e"] for e in es_v), sum(em[e]["python:b"] for e in es_v)
    M[f"RzSedBreakRate{tag}"] = (pct(sb / se), f"{part[6:]}x entries: % of sed edits on clean code that start a break")
    M[f"RzPythonBreakRate{tag}"] = (pct(pb / pe), f"{part[6:]}x entries: % of Python-script edits on clean code that start a break")
sed_share = lambda e: em[e]["sed:e"] / em[e]["e"]
M["RzPairsMoreSed"] = (sum(sed_share(p["hi"]) > sed_share(p["lo"]) for p in pairs),
                       "close pairs whose more exposed entry makes a larger share of its clean-code edits with sed")
# (d) The six models run under both versions: runs with a break on shared tasks.
for tag in ("Old", "New"):
    runs_b, runs_n = 0, 0
    for old, new in SAME:
        shared = {t for (e, t) in cells if e == old} & {t for (e, t) in cells if e == new}
        entry = old if tag == "Old" else new
        runs_n += len(shared)
        runs_b += sum(yes(cells[(entry, t)]["any_break"]) for t in shared)
    M[f"RzSame{tag}BreakRuns"] = (pct(runs_b / runs_n), f"same six models under {'1.x' if tag == 'Old' else '2.x'}: % of runs with a break, shared tasks")

# 12. Multilingual: does the scaffold's shell leave the language's toolchain out? (data/multilingual/log_signs_runs.csv)
mls = list(csv.DictReader((PKG / "data" / "multilingual" / "log_signs_runs.csv").open()))
M["RzMLToolMissingRuns"] = (sum(yes(r["toolchain_not_found"]) for r in mls), "Multilingual runs whose log says the language's toolchain was not found")
M["RzMLLogRuns"] = (len(mls), "Multilingual kept runs read for that check")

# ---------------------------------------------------------------- output
print("% Fourth review round (paper/review4_numbers.py): every value recomputed from the package's tables.")
for name, (value, comment) in M.items():
    assert name.startswith("Rz") and name.isalpha(), name
    print(f"\\newcommand{{\\{name}}}{{{value}}} % {comment}")
