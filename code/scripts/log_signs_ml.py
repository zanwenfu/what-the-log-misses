"""Read the published trajectories of the kept Multilingual runs and write data/multilingual/log_signs_runs.csv: per run,
its command count, the shell the scaffold used, and whether any output says that the language's toolchain (node, npm,
npx, yarn, jest, mocha, tsc, php, composer, phpunit, ruby, bundle, rspec, rake, gem) was not found.

Usage: python3 -I code/scripts/log_signs_ml.py <package dir> <trajectory dir>
<trajectory dir> holds <submission>/<task>.traj.json as published (each entry's metadata.yaml in
github.com/SWE-bench/experiments, evaluation/multilingual, assets.trajs). Command counts are checked against cells.csv.
"""
import csv
import json
import re
import sys
from pathlib import Path

PKG, TR = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(PKG / "code"))
from replaykit.benchmarks.public_trajectories import parse_trajectory  # noqa: E402

csv.field_size_limit(sys.maxsize)
NOT_FOUND = re.compile(r"(node|npm|npx|yarn|jest|mocha|tsc|php|composer|phpunit|ruby|bundle|bundler|rspec|rake|gem): (command )?not found")
ML = PKG / "data" / "multilingual"
cells = {(r["submission"], r["task"]): r for r in csv.DictReader((ML / "cells.csv").open()) if r["main"] == "True"}
with (ML / "log_signs_runs.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["submission", "task", "commands", "shell", "toolchain_not_found"])
    for (s, t), r in sorted(cells.items()):
        traj = parse_trajectory(json.loads((TR / s / f"{t}.traj.json").read_text()), mini_version=re.search(r"mini-v([\w.]+)", s).group(1))
        cmds = list(traj.commands)
        assert len(cmds) == int(r["commands"]), f"{s} {t}: {len(cmds)} commands, cells.csv has {r['commands']}"
        w.writerow([s, t, len(cmds), " ".join(traj.interpreter), any(NOT_FOUND.search(c.output or "") for c in cmds)])
print(len(cells), "runs read")
