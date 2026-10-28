"""The seen/unseen rule plus one clause: an output line that reports an error and points at a source file the breaking
command edited (on that line or in the stack-trace lines around it) shows the break.

    python fileclause.py <scratchpad> <repo> ml|ver

Multilingual's replay recorded no error text for two thirds of its breaks, so the rule's "printed the break's own
error" clause had nothing to match there; this clause stands in for it. On Verified, where every break's error text was
recorded, it is a robustness check. Writes the flips, the corrected share with a task-bootstrap interval, and for
Multilingual a corrected copy of the report (report-ml-v2) for ml_numbers.py and review_numbers.py.
"""
import csv, importlib.util, json, random, re, shutil, sys
from collections import Counter, defaultdict
from pathlib import Path
S, REPO, BENCH = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(REPO))
spec = importlib.util.spec_from_file_location("rep", REPO / "scripts/public_replay_report.py")
rep = importlib.util.module_from_spec(spec); sys.modules["rep"] = rep; spec.loader.exec_module(rep)
from replaykit.benchmarks.public_trajectories import parse_trajectory
csv.field_size_limit(sys.maxsize)
ML = BENCH == "ml"
REPORT = S / ("ml/report-ml" if ML else "pubtraj/report-final4")
TRAJS = S / ("ml/bound_trajs" if ML else "pubtraj/bound_trajs")
SUBS = S / ("ml/m1copy/submissions.json" if ML else "pubtraj/submissions.json")
subs = {s["name"]: s for s in json.load(open(SUBS))["submissions"]}
ERR = re.compile(r"(\b[A-Z]\w*(?:Error|Exception)\b|Fatal error|Parse error|Traceback|Cannot find module|uninitialized constant|"
                 r"undefined method|undefined local variable|Uncaught|Warning: )")
if len(sys.argv) > 4 and sys.argv[4] == "nowarn":  # Python's DeprecationWarning lines are noise, not errors
    ERR = re.compile(ERR.pattern.replace("|Warning: ", ""))
SRC = re.compile(r"[\w./-]+\.(?:py|php|rb|js|jsx|ts|tsx|mjs|cjs|vue)\b")


def points_at_edit(output, files):
    lines = output.splitlines()
    for i, line in enumerate(lines):
        if not ERR.search(line) or line.lstrip().startswith("bash:"):
            continue
        for near in lines[max(0, i - 8): i + 6]:
            if "/tmp/" not in near and any(re.search(rf"(?<![\w.-]){re.escape(f)}\b", near) for f in files):
                return line.strip()[:160]
    return None


rows = list(csv.DictReader(open(REPORT / "intervals.csv")))
fields = list(rows[0].keys())
cache, flips = {}, []
for b in rows:
    if b["main"] != "True" or b["unseen"] != "True":
        continue
    s, t = b["submission"], b["task"]
    path = TRAJS / s / f"{t}.traj.json"
    if not path.exists():
        b["clause"] = "no-log"; continue
    if (s, t) not in cache:
        cache[s, t] = parse_trajectory(json.load(open(path)), mini_version=str(subs[s].get("version") or ""))
    traj = cache[s, t]; cmds = list(traj.commands)
    onset = int(b["onset"])
    files = {m.rsplit("/", 1)[-1] for m in SRC.findall(cmds[onset - 1].command)} if 1 <= onset <= len(cmds) else set()
    last = int(b["repair"]) if b["repair"] not in ("", "None") else len(cmds)
    for k in range(onset, last + 1):
        if not 1 <= k <= len(cmds) or rep.is_listing(cmds[k - 1].command) or (traj.submit_index is not None and k - 1 == traj.submit_index):
            continue
        hit = points_at_edit(rep.seen_output(cmds[k - 1]), files) if files else None
        if hit:
            flips.append({"submission": s, "task": t, "onset": onset, "kind": b["kind"], "at": k, "files": sorted(files), "line": hit})
            b["unseen"] = "False"; b["named"] = "True"; b["clause"] = "file"
            break
main = [b for b in rows if b["main"] == "True"]
tasks = sorted({b["task"] for b in main}); by = defaultdict(list)
for b in main:
    by[b["task"]].append(b["unseen"] == "True")
rng = random.Random(20261023); draws = []
for _ in range(2000):
    smp = [x for t in (rng.choice(tasks) for _ in tasks) for x in by[t]]
    draws.append(sum(smp) / len(smp))
draws.sort()
unseen = [b for b in main if b["unseen"] == "True"]
res = {"bench": BENCH, "breaks": len(main), "flips": len(flips), "no_log": sum(b.get("clause") == "no-log" for b in rows),
       "unseen_before": sum(1 for _ in flips) + len(unseen), "unseen_after": len(unseen),
       "share_after": round(100 * len(unseen) / len(main), 1), "ci_after": [round(100 * draws[50], 1), round(100 * draws[1949], 1)],
       "unseen_no_tests_after": round(100 * sum(b["ran_tests"] != "True" for b in unseen) / len(unseen), 1),
       "unseen_open_after": sum(b["ended"] in ("", "None") for b in unseen),
       "by_kind": dict(Counter(f["kind"] for f in flips))}
print(json.dumps(res, indent=1))
for f in flips[:40]:
    print(f["kind"], f["task"], f["onset"], "->", f["at"], f["files"], "|", f["line"][:110])
out = S / ("ml/fileclause_ml.json" if ML else "pubtraj/fileclause_ver" + ("_nowarn" if len(sys.argv) > 4 else "") + ".json")
json.dump({"summary": res, "flips": flips}, open(out, "w"), indent=1)
if ML:
    v2 = S / "ml/report-ml-v2"
    if v2.exists(): shutil.rmtree(v2)
    shutil.copytree(REPORT, v2)
    with open(v2 / "intervals.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    summary = json.loads((v2 / "summary.json").read_text())
    summary["overall_main"]["unseen_interval_share"] = len(unseen) / len(main)
    summary["overall_main_ci"]["unseen_interval_share"] = [draws[50], draws[1949]]
    summary["overall_main"]["unseen_no_tests_share"] = sum(b["ran_tests"] != "True" for b in unseen) / len(unseen)
    summary["overall_main"]["unseen_open_breaks"] = res["unseen_open_after"]
    summary["file_clause"] = res
    (v2 / "summary.json").write_text(json.dumps(summary, indent=1))
