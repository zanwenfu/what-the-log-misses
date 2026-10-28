"""Score the whole-run judges on every edit of the 150 sampled runs: among edits made on clean code, how many that start
a break are flagged (recall; unseen and seen apart), how many clean edits are flagged (false alarms), and precision as
it falls, with a bootstrap over runs; then precision after a free syntax check (syntax-error onsets removed)."""
import json, math, random, sys
S = sys.argv[1]
items = {(i["submission"], i["task"]): i for i in json.load(open(f"{S}/judge/sample_full.json"))}
for i in items.values():  # command 0 is the starting snapshot, not an edit
    i["edits"] = [e for e in i["edits"] if e["command"] > 0]


def wilson(k, n, z=1.96):
    if not n: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h)), round(100 * (c + h))]


out = {}
for model in ("sonnet", "opus"):
    try:
        rows = [json.loads(l) for l in open(f"{S}/judge/full_{model}.jsonl")]
    except FileNotFoundError:
        continue
    per_run = []
    for r in rows:
        it = items[(r["submission"], r["task"])]; calls = {int(k): v for k, v in r["calls"].items()}
        e = [(x, calls.get(x["command"])) for x in it["edits"] if x["before"] == "ok"]
        per_run.append({"tp": sum(x["onset"] and c == "BROKEN" for x, c in e), "fp": sum(not x["onset"] and c == "BROKEN" for x, c in e),
                        "on": sum(x["onset"] for x, c in e), "clean": sum(not x["onset"] for x, c in e),
                        "on_u": sum(x["onset"] and x["unseen"] == "True" for x, c in e),
                        "tp_u": sum(x["onset"] and x["unseen"] == "True" and c == "BROKEN" for x, c in e),
                        "on_s": sum(x["onset"] and x["unseen"] == "False" for x, c in e),
                        "tp_s": sum(x["onset"] and x["unseen"] == "False" and c == "BROKEN" for x, c in e),
                        "tp_ns": sum(x["onset"] and x["syntax"] == "False" and c == "BROKEN" for x, c in e),
                        "on_ns": sum(x["onset"] and x["syntax"] == "False" for x, c in e),
                        "unanswered": sum(c is None for x, c in e),
                        "states": len(it["edits"]), "state_right": sum((calls.get(x["command"]) == "BROKEN") == (x["after"] != "ok") for x in it["edits"])})
    T = {k: sum(p[k] for p in per_run) for k in per_run[0]}
    prec = lambda a, b: a / (a + b) if a + b else None
    rng = random.Random(20261024); draws = []
    for _ in range(2000):
        smp = [rng.choice(per_run) for _ in per_run]
        v = prec(sum(p["tp"] for p in smp), sum(p["fp"] for p in smp))
        if v is not None: draws.append(v)
    draws.sort()
    out[model] = {"runs": len(per_run), "edits_on_clean": T["on"] + T["clean"], "onsets": T["on"], "unanswered": T["unanswered"],
                  "recall": round(100 * T["tp"] / T["on"]), "recall_ci": wilson(T["tp"], T["on"]),
                  "recall_unseen": round(100 * T["tp_u"] / T["on_u"]), "n_unseen": T["on_u"], "recall_unseen_ci": wilson(T["tp_u"], T["on_u"]),
                  "recall_seen": round(100 * T["tp_s"] / T["on_s"]) if T["on_s"] else None, "n_seen": T["on_s"],
                  "false_alarm": round(100 * T["fp"] / T["clean"]), "false_alarm_ci": wilson(T["fp"], T["clean"]),
                  "flags": T["tp"] + T["fp"], "precision": round(100 * prec(T["tp"], T["fp"])),
                  "precision_ci": [round(100 * draws[50]), round(100 * draws[1949])],
                  "precision_after_syntax": round(100 * prec(T["tp_ns"], T["fp"])) if T["tp_ns"] + T["fp"] else None,
                  "base_rate": round(100 * T["on"] / (T["on"] + T["clean"]), 1),
                  "precision_at_overall_rate": round(100 * (lambda r, f, p: r * p / (r * p + f * (1 - p)))(T["tp"] / T["on"], T["fp"] / T["clean"], 992 / 10037)),
                  "state_accuracy": round(100 * T["state_right"] / T["states"]),
                  "cost": round(sum(r["cost"] for r in rows), 2)}
print(json.dumps(out, indent=1))
json.dump(out, open(f"{S}/judge/summary_full.json", "w"), indent=1)
