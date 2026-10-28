"""Fig. 1 of the replay paper: two runs of the same task, the same edit, two endings.

Each row is one run of django-11490 on scaffold version 1.0.0, command by command: the bar is the execution label
(the tree after each command, clean or failing a previously passing test, from the replay's states.csv); the marks
are what the agent's own log shows (from its published trajectory).

    python3 fig_timeline.py timeline_data.json
"""
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Times", "Nimbus Roman"],
                     "font.size": 7, "pdf.fonttype": 42})
CLEAN, BROKEN = "#cfd8dc", "#c62828"

data = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "timeline_data.json"))
RUNS = (
    ("20250802_mini-v1.0.0_claude-4-opus-20250514", "Claude Opus 4", "ends clean, task solved"),
    ("20250726_mini-v1.0.0_claude-sonnet-4-20250514", "Claude Sonnet 4", "ends broken, task failed"),
)
# The paper's two terms, written under each run's red span: Opus's log shows its break, Sonnet's never does.
SPAN = {"Claude Opus 4": "seen break", "Claude Sonnet 4": "unseen break"}
# What each run's log shows at the commands that matter (checked against the published trajectories). Every other
# command that changed the code gets a small grey edit mark, from the replay's saved states.
NOTES = {  # (command, kind, label, alignment, label place: 1 just above the mark, 2 higher with a leader)
    "Claude Opus 4": [(13, "edit", "one-line edit", "center", 1), (21, "nothing", "", "center", 1),
                      (22, "nothing", "", "center", 1), (23, "nothing", "", "center", 1),
                      (25, "failure", "sees the failure", "center", 2), (29, "edit", "undoes it", "left", 1)],
    "Claude Sonnet 4": [(15, "edit", "same edit", "center", 1), (23, "nothing", "", "center", 1),
                        (24, "nothing", "", "center", 1), (30, "own", "own script passes", "left", 1)],
}

fig, ax = plt.subplots(figsize=(3.45, 1.6))
for row, (name, label, ending) in enumerate(RUNS):
    y = 1.4 * (1 - row)
    run = data[name]
    states = sorted(run["states"])
    for i, (start, status) in enumerate(states):
        end = states[i + 1][0] if i + 1 < len(states) else run["n"]
        ax.barh(y, max(end - start, 0.6), left=start, height=0.32, color=BROKEN if status == "broken" else CLEAN,
                edgecolor="none")
    broken = [(s, states[i + 1][0] if i + 1 < len(states) else run["n"]) for i, (s, st) in enumerate(states)
              if st == "broken"]
    if broken:
        ax.text((broken[0][0] + broken[-1][1]) / 2, y - 0.2, SPAN[label], ha="center", va="top", fontsize=6.8,
                style="italic", color="0.1")
    labelled = {k for k, kind, *_ in NOTES[label] if kind == "edit"}
    for start, _ in states[1:]:
        if start not in labelled and start < run["n"]:
            ax.scatter([start], [y + 0.3], zorder=3, marker="v", color="0.6", s=11, linewidths=0)
    for k, kind, text, align, level in NOTES[label]:
        style = {"edit": dict(marker="v", color="black", s=26), "failure": dict(marker="o", color=BROKEN, s=32),
                 "nothing": dict(marker="o", facecolors="white", edgecolors="0.35", s=24),
                 "own": dict(marker="s", facecolors="white", edgecolors="0.35", s=22)}[kind]
        ax.scatter([k], [y + 0.3], zorder=3, linewidths=0.7, **style)
        if text:
            nudge = {"center": 0, "left": -2}[align]
            leader = dict(arrowstyle="-", lw=0.35, color="0.45", shrinkA=0, shrinkB=3) if level == 2 else None
            ax.annotate(text, (k, y + 0.3), textcoords="offset points", xytext=(nudge, 4.5 if level == 1 else 13),
                        ha=align, fontsize=6.8, arrowprops=leader)
    ax.annotate(ending, (run["n"], y), textcoords="offset points", xytext=(4, -2), fontsize=6.8, ha="left")
    ax.text(-1, y, label, ha="right", va="center", fontsize=7.2)
ax.set_xlim(0, max(data[name]["n"] for name, *_ in RUNS) + 1)
ax.set_ylim(-0.5, 2.15)
ax.set_yticks([])
ax.set_xlabel("command number", labelpad=1)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
bars = [plt.Rectangle((0, 0), 1, 1, color=CLEAN), plt.Rectangle((0, 0), 1, 1, color=BROKEN)]
marks = [plt.Line2D([], [], marker="v", color="black", ls="", ms=4.2),
         plt.Line2D([], [], marker="v", color="0.6", ls="", ms=3.2),
         plt.Line2D([], [], marker="o", color=BROKEN, ls="", ms=4.2),
         plt.Line2D([], [], marker="o", mfc="white", mec="0.35", ls="", ms=4.2),
         plt.Line2D([], [], marker="s", mfc="white", mec="0.35", ls="", ms=3.9)]
first = ax.legend(bars, ["bar: all previously passing tests pass", "bar: at least one of them fails"],
                  frameon=False, fontsize=6.8, loc="upper left", bbox_to_anchor=(-0.06, -0.3), handlelength=1.1,
                  labelspacing=0.25)
ax.add_artist(first)
ax.legend(marks, ["log: the one-line edit, or its undo", "log: other edits", "log: a test run shows the failure",
                  "log: a test command that runs no test", "log: the agent’s own check script"], frameon=False,
          fontsize=6.8, loc="upper left", bbox_to_anchor=(0.63, -0.3), handlelength=1.1, labelspacing=0.25)
fig.savefig("fig_timeline.pdf", bbox_inches="tight")
print("wrote fig_timeline.pdf")
