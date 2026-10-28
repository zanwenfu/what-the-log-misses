"""Multilingual: how far the unseen share could fall if the rule missed errors it had no text for.

For every kept Multilingual break, rebuild the log the model saw between onset and repair (as the cards do), check the
rule's own test-run verdict, then count unseen breaks whose log shows any error-like line (A) or any error-or-failure
line (B) outside listings and the final submit command.
"""
import csv, importlib.util, json, re, sys
from collections import Counter
from pathlib import Path
S, REPO = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(REPO))
spec = importlib.util.spec_from_file_location("rep", REPO / "scripts/public_replay_report.py")
rep = importlib.util.module_from_spec(spec); sys.modules["rep"] = rep; spec.loader.exec_module(rep)
from replaykit.benchmarks.public_trajectories import parse_trajectory
csv.field_size_limit(sys.maxsize)
subs = {s["name"]: s for s in json.load(open(S / "ml/m1copy/submissions.json"))["submissions"]}
ERR = re.compile(r"(\w*Error\b|\w*Exception\b|Fatal error|Parse error|Traceback|Cannot find module|uninitialized constant|"
                 r"undefined method|undefined local variable|Uncaught|Warning: )")
FAIL = re.compile(r"(\bFAIL|\bfailed\b|\bfailing\b|\bfailures?\b|\bnot ok\b|✕|✘)", re.I)
rows = [r for r in csv.DictReader(open(S / "ml/report-ml/intervals.csv")) if r["main"] == "True"]
ml = {"multilingual": True}
out = Counter(); examples = []
for b in rows:
    s, t = b["submission"], b["task"]
    traj = parse_trajectory(json.load(open(S / f"ml/bound_trajs/{s}/{t}.traj.json")), mini_version=str(subs[s].get("version") or ""))
    cmds = list(traj.commands)
    last = int(b["repair"]) if b["repair"] not in ("", "None") else len(cmds)
    window = [(k, cmds[k - 1]) for k in range(int(b["onset"]), last + 1) if 1 <= k <= len(cmds)]
    tested = [c for _, c in window if rep.is_test_command(c.command, **ml) or (rep.tests_ran(rep.seen_output(c), **ml) and not rep.is_listing(c.command))]
    saw_failure = any(rep.shows_failure(c.returncode, rep.seen_output(c), **ml) for c in tested)
    shown = [(k, rep.seen_output(c)) for k, c in window
             if not rep.is_listing(c.command) and not (traj.submit_index is not None and k - 1 == traj.submit_index)]
    err = any(ERR.search(o) for _, o in shown)
    errfail = err or any(FAIL.search(o) for _, o in shown)
    unseen = b["unseen"] == "True"
    out["breaks"] += 1; out["unseen"] += unseen
    out["rule_failure_matches"] += (saw_failure == (b["saw_failure"] == "True"))
    if unseen:
        out[f"unseen_{b['kind']}"] += 1
        out[f"unseen_{b['kind']}_err"] += err
        out[f"unseen_{b['kind']}_errfail"] += errfail
        out[f"unseen_{b['kind']}_noevidence"] += not b["evidence"]
        out[f"unseen_{b['kind']}_noevidence_err"] += (not b["evidence"]) and err
        if err and len(examples) < 12:
            line = next(l for _, o in shown for l in o.splitlines() if ERR.search(l))
            examples.append((b["kind"], t, line.strip()[:150]))
res = dict(out)
res["unseen_share"] = round(100 * out["unseen"] / out["breaks"])
res["bound_err"] = round(100 * (out["unseen"] - out["unseen_load_err"] - out["unseen_test_err"]) / out["breaks"])
res["bound_err_load_only"] = round(100 * (out["unseen"] - out["unseen_load_noevidence_err"]) / out["breaks"])
res["bound_errfail"] = round(100 * (out["unseen"] - out["unseen_load_errfail"] - out["unseen_test_errfail"]) / out["breaks"])
print(json.dumps(res, indent=1)); [print(e) for e in examples]
json.dump(res, open(S / "ml/report-ml/error_bound.json", "w"), indent=1)

# C: a fairer correction. An error-like line counts as showing the break only if it, or the five lines after it (a
# stack trace), names a source file the breaking command touched.
SRC = re.compile(r"[\w./-]+\.(?:php|rb|js|jsx|ts|tsx|mjs|cjs|vue)\b")
c = Counter(); picks = []
for b in rows:
    if b["unseen"] != "True":
        continue
    s, t = b["submission"], b["task"]
    traj = parse_trajectory(json.load(open(S / f"ml/bound_trajs/{s}/{t}.traj.json")), mini_version=str(subs[s].get("version") or ""))
    cmds = list(traj.commands)
    files = {m.rsplit("/", 1)[-1] for m in SRC.findall(cmds[int(b["onset"]) - 1].command)}
    last = int(b["repair"]) if b["repair"] not in ("", "None") else len(cmds)
    hit = None
    for k in range(int(b["onset"]), last + 1):
        if not 1 <= k <= len(cmds) or rep.is_listing(cmds[k - 1].command) or (traj.submit_index is not None and k - 1 == traj.submit_index):
            continue
        lines = rep.seen_output(cmds[k - 1]).splitlines()
        for i, line in enumerate(lines):
            if ERR.search(line) and any(f in " ".join(lines[i:i + 6]) for f in files):
                hit = (k, line.strip()[:140]); break
        if hit:
            break
    c[b["kind"]] += 1; c[b["kind"] + "_hit"] += bool(hit); c["nofiles"] += not files
    if hit:
        picks.append((b["kind"], t, int(b["onset"]), hit[0], sorted(files), hit[1]))
res["unseen_c_hits"] = c["load_hit"] + c["test_hit"]
res["bound_file_matched"] = round(100 * (out["unseen"] - res["unseen_c_hits"]) / out["breaks"])
res["c_detail"] = dict(c)
print(json.dumps({k: res[k] for k in ("unseen_c_hits", "bound_file_matched", "c_detail")}, indent=1))
for p in picks: print(p)
json.dump(res, open(S / "ml/report-ml/error_bound.json", "w"), indent=1)
