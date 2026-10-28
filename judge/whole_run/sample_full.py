"""Draw 150 kept Verified runs at random (seeded) for the whole-run judge, and list each run's code-changing commands
with their execution labels (state after the command; whether it starts a break on clean code; seen or unseen)."""
import csv, json, random, sys
from collections import defaultdict
from pathlib import Path
S = Path(sys.argv[1]); R = S / "pubtraj/report-final4"
csv.field_size_limit(sys.maxsize)
cells = sorted((r["submission"], r["task"]) for r in csv.DictReader(open(R / "cells.csv")) if r["main"] == "True")
rng = random.Random(20261024)
runs = rng.sample(cells, 150)
# Two drawn runs are hosted on GitHub, not the bucket; redraw them from the other runs.
GH = "20260901_mini-v2.4.2_gemini-3-5-flash"
missing = [r for r in runs if r[0] == GH and not (S / "judge/full_trajs" / r[0] / f"{r[1]}.traj.json").exists()]
pool = [c for c in cells if c not in runs and c[0] != GH]
runs = [r for r in runs if r not in missing] + rng.sample(pool, len(missing))
states = defaultdict(list)
for r in csv.DictReader(open(R / "states.csv")):
    if r["trigger"] != "final":
        states[r["submission"], r["task"]].append((int(r["seq"]), int(r["command"]), r["status"]))
onsets = {(b["submission"], b["task"], int(b["onset"])): b for b in csv.DictReader(open(R / "intervals.csv")) if b["main"] == "True"}
items = []
for s, t in runs:
    v = sorted(states[s, t]); prev = "ok"; edits = []
    for _, cmd, status in v:
        edits.append({"command": cmd, "before": prev, "after": status, "onset": prev == "ok" and status != "ok",
                      "unseen": (onsets.get((s, t, cmd)) or {}).get("unseen"),
                      "syntax": (onsets.get((s, t, cmd)) or {}).get("syntax_error"), "kind": (onsets.get((s, t, cmd)) or {}).get("kind")})
        prev = status
    items.append({"submission": s, "task": t, "edits": edits})
json.dump(items, open(S / "judge/sample_full.json", "w"), indent=1)
e = [x for i in items for x in i["edits"]]
print(len(items), "runs;", len(e), "edits;", sum(x["before"] == "ok" for x in e), "on clean code;", sum(x["onset"] for x in e), "start a break;",
      sum(x["onset"] and x["unseen"] == "True" for x in e), "unseen;", sum(x["after"] != "ok" for x in e), "broken states")
