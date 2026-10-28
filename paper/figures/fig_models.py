"""Fig. 2 of the replay paper: per model, leaderboard resolve rate against exposure, one panel per scaffold version.

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


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return cov / (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5


intervals = {}
if cells_path:
    csv.field_size_limit(sys.maxsize)
    per_model = defaultdict(list)
    for c in csv.DictReader(open(cells_path)):
        if c["main"] == "True" and c["exposure"] not in ("", "None"):
            per_model[c["submission"]].append(float(c["exposure"]))
    rng = random.Random(20261023)
    for r in rows:
        v = per_model.get(r["submission"], [])
        if len(v) < 2:
            continue
        means = sorted(sum(rng.choice(v) for _ in v) / len(v) for _ in range(2000))
        intervals[r["submission"]] = (100 * means[50], 100 * means[1949])

# Display names and label offsets (points) for the models the text names.
NAMES = {"qwen3-coder-480b": ("Qwen3-Coder", (-8, 3), "right"), "gemini-2.5-pro": ("Gemini 2.5 Pro", (-10, 12), "right"),
         "deepseek-3-2-high": ("DeepSeek V3.2", (-6, 16), "right"), "gpt-5-2-high": ("GPT-5.2", (6, 34), "left")}
fig, axes = plt.subplots(1, 2, figsize=(3.45, 1.85), sharey=True, gridspec_kw={"wspace": 0.08})
for ax, newer, colour, marker, title in ((axes[0], False, "#4a6fa5", "s", "scaffold 1.x (2025)"),
                                         (axes[1], True, "#b2333a", "o", "scaffold 2.x (2026)")):
    idx = [i for i, b in enumerate(v2) if b == newer]
    for i in idx:
        lo_hi = intervals.get(rows[i]["submission"])
        if lo_hi:
            ax.plot([xs[i], xs[i]], list(lo_hi), color=colour, alpha=0.35, lw=0.7, zorder=2)
    ax.scatter([xs[i] for i in idx], [ys[i] for i in idx], s=12, color=colour, marker=marker, zorder=3)
    for i in idx:
        if rows[i]["submission"] in named:
            name, offset, align = NAMES.get(short(rows[i]["submission"]), (short(rows[i]["submission"]), (4, 2), "left"))
            ax.scatter([xs[i]], [ys[i]], s=44, facecolors="none", edgecolors="black", linewidths=0.6, zorder=4)
            ax.annotate(name, (xs[i], ys[i]), textcoords="offset points", xytext=offset, fontsize=7, ha=align,
                        arrowprops=dict(arrowstyle="-", lw=0.6, color="0.2", shrinkA=0, shrinkB=3.5))
    rho = spearman([xs[i] for i in idx], [ys[i] for i in idx])
    print(f"{title}: {len(idx)} models, Spearman rho = {rho:.2f}")
    ax.set_title(f"{title}, $\\rho$ = {rho:.2f}".replace("-", "\u2212"), fontsize=7.5, pad=3)
    ax.set_xlabel("resolve rate (%)")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
axes[0].set_ylabel("exposure (%)")
axes[1].set_xlim(54, 80)
fig.savefig("fig_models.pdf", bbox_inches="tight")
print(f"wrote fig_models.pdf ({len(rows)} models)")
