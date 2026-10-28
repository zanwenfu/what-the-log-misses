"""Fig. 1 of the replay paper: per model, leaderboard resolve rate against exposure.

Reads models.csv as written by scripts/public_replay_report.py (main tiers: exact + unsubmitted runs) and writes
fig_models.pdf. Exposure is the share of a run's commands after which the code fails a previously passing test,
averaged over the model's runs: the chance that a stop after a uniformly random command leaves broken code.
Labels the models named on the command line (the pairs the text compares), else the two most exposed.

    python3 fig_models.py report/models.csv [--cells=report/cells.csv] [submission ...]

With --cells, each model gets a 95% interval for its exposure from a bootstrap over its runs (2,000 resamples).
"""
import csv
import random
import re
import sys
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Times", "Nimbus Roman"],
                     "font.size": 7.5, "pdf.fonttype": 42})


def short(name: str) -> str:
    """20250802_mini-v1.0.0_qwen3-coder-480b-a35b-instruct -> qwen3-coder-480b."""
    tail = name.split("_mini-v", 1)[-1]
    model = tail.split("_", 1)[-1] if "_" in tail else tail.split("-", 1)[-1]
    model = re.sub(r"-20\d\d-?\d\d-?\d\d$", "", model)
    model = re.sub(r"-(instruct|a35b-instruct|a35b)$", "", model, flags=re.I)
    return model.replace("-a35b", "")


path = sys.argv[1] if len(sys.argv) > 1 else "report/models.csv"
cells_path = next((a.split("=", 1)[1] for a in sys.argv[2:] if a.startswith("--cells=")), None)
named = {a for a in sys.argv[2:] if not a.startswith("--")}
rows = [r for r in csv.DictReader(open(path))
        if r.get("exposure_mean") not in ("", "None") and r.get("resolve_rate_leaderboard") not in ("", "None")]
xs = [100 * float(r["resolve_rate_leaderboard"]) for r in rows]
ys = [100 * float(r["exposure_mean"]) for r in rows]
v2 = ["_mini-v2." in r["submission"] for r in rows]

fig, ax = plt.subplots(figsize=(3.45, 1.7))
if cells_path:
    csv.field_size_limit(sys.maxsize)
    per_model = defaultdict(list)
    for c in csv.DictReader(open(cells_path)):
        if c["main"] == "True" and c["exposure"] not in ("", "None"):
            per_model[c["submission"]].append(float(c["exposure"]))
    rng = random.Random(20261023)
    for r, x, y, b in zip(rows, xs, ys, v2):
        v = per_model.get(r["submission"], [])
        if len(v) < 2:
            continue
        means = sorted(sum(rng.choice(v) for _ in v) / len(v) for _ in range(2000))
        lo, hi = 100 * means[50], 100 * means[1949]
        ax.plot([x, x], [lo, hi], color="#b2333a" if b else "#4a6fa5", alpha=0.35, lw=0.7, zorder=2)
ax.scatter([x for x, b in zip(xs, v2) if not b], [y for y, b in zip(ys, v2) if not b], s=13, color="#4a6fa5",
           marker="s", label="scaffold 1.x (2025)", zorder=3)
ax.scatter([x for x, b in zip(xs, v2) if b], [y for y, b in zip(ys, v2) if b], s=15, color="#b2333a",
           label="scaffold 2.x (2026)", zorder=3)
order = sorted(range(len(rows)), key=lambda i: -ys[i])
label = {i for i, r in enumerate(rows) if r["submission"] in named} or set(order[:2])
# Display names and label offsets (points) for the models the text names; others get the short name, to the right.
NAMES = {"qwen3-coder-480b": ("Qwen3-Coder", (4, 1.5), "left"), "gemini-2.5-pro": ("Gemini 2.5 Pro", (-14, 8), "right"),
         "kimi-k2-5-high": ("Kimi K2.5", (8, 34), "left"), "gpt-5-2-high": ("GPT-5.2", (16, -3), "left")}
for i in sorted(label):
    name, offset, align = NAMES.get(short(rows[i]["submission"]), (short(rows[i]["submission"]), (4, 1.5), "left"))
    ax.scatter([xs[i]], [ys[i]], s=46, facecolors="none", edgecolors="black", linewidths=0.6, zorder=4)
    ax.annotate(name, (xs[i], ys[i]), textcoords="offset points", xytext=offset, fontsize=6, ha=align,
                arrowprops=dict(arrowstyle="-", lw=0.6, color="0.2", shrinkA=0, shrinkB=3.5))
ax.set_xlabel("resolve rate on the leaderboard (%)")
ax.set_ylabel("exposure (%)")
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
ax.legend(frameon=False, fontsize=6, loc="lower left")
fig.savefig("fig_models.pdf", bbox_inches="tight")
print(f"wrote fig_models.pdf ({len(rows)} models)")
