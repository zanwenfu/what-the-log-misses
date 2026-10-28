"""Both judges: share of sampled commands called broken, by execution label, with Wilson intervals."""
import json, math, sys
scratch = sys.argv[1]
def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h)), round(100 * (c + h))
out = {}
for judge, path in (("sonnet", "judge/results.jsonl"), ("opus", "judge/results_opus.jsonl")):
    rows = [json.loads(l) for l in open(f"{scratch}/{path}")]
    ok = [r for r in rows if r["verdict"] in ("BROKEN", "OK")]
    groups = {
        "unseen": [r for r in ok if r["kind"] == "unseen_break"],
        "unseen_load": [r for r in ok if r["kind"] == "unseen_break" and r["break_kind"] == "load"],
        "unseen_test": [r for r in ok if r["kind"] == "unseen_break" and r["break_kind"] == "test"],
        "seen": [r for r in ok if r["kind"] == "seen_break"],
        "clean": [r for r in ok if r["kind"] == "clean"],
    }
    res = {}
    for name, g in groups.items():
        k, n = sum(r["verdict"] == "BROKEN" for r in g), len(g)
        res[name] = {"called": k, "n": n, "share": round(100 * k / n) if n else None, "ci": list(wilson(k, n))}
    res["unparsed"] = len(rows) - len(ok)
    res["calls"] = len(rows)
    price = {"sonnet": (2, 10), "opus": (4, 20)}[judge]
    res["cost"] = round(sum((r["usage"].get("inputTokens", 0) * price[0] + r["usage"].get("outputTokens", 0) * price[1]) / 1e6 for r in rows), 2)
    out[judge] = res
    print(judge, {k: (v if not isinstance(v, dict) else f"{v['called']}/{v['n']}={v['share']}% {v['ci']}") for k, v in res.items()})
# agreement between judges on the commands both judged
a = {(r["kind"], r["submission"], r["task"], r["step"]): r["verdict"] for r in map(json.loads, open(f"{scratch}/judge/results.jsonl"))}
b = {(r["kind"], r["submission"], r["task"], r["step"]): r["verdict"] for r in map(json.loads, open(f"{scratch}/judge/results_opus.jsonl"))}
both = [k for k in a if k in b and a[k] in ("BROKEN", "OK") and b[k] in ("BROKEN", "OK")]
out["agreement"] = {"n": len(both), "same": sum(a[k] == b[k] for k in both)}
tb = [k for k in both if k[0] == "unseen_break"]
out["unseen_missed_by_both"] = sum(a[k] == "OK" and b[k] == "OK" for k in tb)
print("agreement", out["agreement"], "unseen breaks missed by both", out["unseen_missed_by_both"], "of", len(tb))
json.dump(out, open(f"{scratch}/judge/summary2.json", "w"), indent=1)
