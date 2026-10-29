"""Read the published trajectories of the kept Verified runs and write three small tables to data/verified/:

  log_signs_runs.csv    per run: commands, and whether any output shows the image's base Python
                        (/opt/miniconda3/lib/python3.x/ or /opt/miniconda3/bin/python, i.e. outside the testbed
                        environment), whether any output says "No module named", whether any command runs pip install
  log_signs_breaks.csv  per break: whether an output before the break's onset shows the base Python
  edit_methods.csv      per entry and edit method: edits on clean code (a snapshot after a code-changing command whose
                        previous state passed every counted test) and how many of them start a break

Usage: python3 -I code/scripts/log_signs.py <package dir> <trajectory dir>
<trajectory dir> holds <submission>/<task>.traj.json as published (github.com/SWE-bench/experiments, each entry's
metadata.yaml, assets.trajs). Every run's command count is checked against cells.csv first.
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PKG, TR = Path(sys.argv[1]), Path(sys.argv[2])
VER = PKG / "data" / "verified"
sys.path.insert(0, str(PKG / "code"))
from replaykit.benchmarks.public_trajectories import parse_trajectory  # noqa: E402

csv.field_size_limit(sys.maxsize)
BASE = re.compile(r"/opt/miniconda3/lib/python3\.\d+/|/opt/miniconda3/bin/python")
NO_MODULE = re.compile(r"No module named")
PIP = re.compile(r"\bpip3? install\b|python3? -m pip install")
# How a command edits, first match wins: sed in place; a Python script that writes files; a heredoc or redirect into
# a file; git apply, patch or a checkout/restore/stash; perl, awk or ed in place; anything else.
METHODS = [("sed", re.compile(r"\bsed\b[^|;&]*\s-i")),
           ("python", re.compile(r"\bpython3?\b.*(<<|-c\b)|\.write\(|open\([^)]*['\"]w")),
           ("heredoc", re.compile(r"\bcat\b[^|;&]*<<|(?<![<>])>(?!&)\s*[\w./-]+\.(py|cfg|toml|txt|rst|ini)\b")),
           ("git", re.compile(r"\bgit\s+apply\b|\bpatch\s+-p|\bgit\s+(checkout|restore|stash)\b")),
           ("perl_awk_ed", re.compile(r"\bperl\b.*-i|\bawk\b.*-i\s+inplace|\bed\s"))]


def method(command):
    for name, rx in METHODS:
        if rx.search(command):
            return name
    return "other"


cells = {(r["submission"], r["task"]): r for r in csv.DictReader((VER / "cells.csv").open()) if r["main"] == "True"}
breaks = [b for b in csv.DictReader((VER / "intervals.csv").open()) if b["main"] == "True"]
states = defaultdict(list)
for r in csv.DictReader((VER / "states.csv").open()):
    if (r["submission"], r["task"]) in cells and r["trigger"] in ("run", "tool"):
        states[(r["submission"], r["task"])].append((int(r["seq"]), r["trigger"], int(r["command"]), r["status"]))

commands = {}
for (s, t), r in sorted(cells.items()):
    raw = json.loads((TR / s / f"{t}.traj.json").read_text())
    cmds = list(parse_trajectory(raw, mini_version=re.search(r"mini-v([\d.]+)", s).group(1)).commands)
    assert len(cmds) == int(r["commands"]), f"{s} {t}: {len(cmds)} commands, cells.csv has {r['commands']}"
    commands[(s, t)] = cmds

with (VER / "log_signs_runs.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["submission", "task", "commands", "base_python", "no_module", "pip_install"])
    for (s, t), cmds in sorted(commands.items()):
        w.writerow([s, t, len(cmds), any(BASE.search(c.output or "") for c in cmds),
                    any(NO_MODULE.search(c.output or "") for c in cmds), any(PIP.search(c.command) for c in cmds)])

with (VER / "log_signs_breaks.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["submission", "task", "onset", "base_python_before"])
    for b in breaks:
        cmds = commands[(b["submission"], b["task"])]
        w.writerow([b["submission"], b["task"], b["onset"], any(BASE.search(c.output or "") for c in cmds[: int(b["onset"])])])

tally = defaultdict(Counter)
for key, rows in states.items():
    cmds, prev = commands[key], "ok"
    for _, trigger, k, status in sorted(rows):
        if trigger == "tool" and prev == "ok" and 1 <= k <= len(cmds):
            m = method(cmds[k - 1].command)
            tally[(key[0], m)]["edits"] += 1
            tally[(key[0], m)]["breaks"] += status == "broken"
        if status in ("ok", "broken"):
            prev = status
with (VER / "edit_methods.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["submission", "method", "edits_on_clean", "breaks_started"])
    for (s, m), c in sorted(tally.items()):
        w.writerow([s, m, c["edits"], c["breaks"]])
print(f"{len(commands)} runs read; {sum(c['edits'] for c in tally.values())} edits on clean code")
