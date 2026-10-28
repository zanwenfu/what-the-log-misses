"""Judge pilot results: how often the judge says BROKEN, by kind of step, with Wilson intervals."""
import csv, json, math, sys, collections
csv.field_size_limit(sys.maxsize)
scratch = sys.argv[1]
rows = [json.loads(l) for l in open(f"{scratch}/judge/results.jsonl")]
breaks = {(b["submission"], b["task"], int(b["onset"])): b for b in csv.DictReader(open(f"{scratch}/pubtraj/report-final4/intervals.csv")) if b["main"] == "True"}
def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h)), round(100 * (c + h))
out = {}
def report(name, sel, threshold=None):
    sel = [r for r in sel if r["verdict"] in ("BROKEN", "OK")]
    k = sum(r["verdict"] == "BROKEN" and (threshold is None or (r["confidence"] or 0) >= threshold) for r in sel)
    n = len(sel); lo, hi = wilson(k, n)
    out[name] = {"flagged": k, "n": n, "share": round(100 * k / n) if n else None, "ci": [lo, hi]}
    print(f"{name:42s} {k:3d}/{n:3d} = {100 * k / max(n, 1):5.1f}%  [{lo}-{hi}]")
print("unparsed:", sum(r["verdict"] not in ("BROKEN", "OK") for r in rows), "of", len(rows))
for kind in ("unseen_break", "seen_break", "clean"):
    report(f"BROKEN on {kind}", [r for r in rows if r["kind"] == kind])
for kind in ("unseen_break", "seen_break"):
    for syn in ("True", "False"):
        report(f"  {kind} syntax={syn}", [r for r in rows if r["kind"] == kind and breaks.get((r["submission"], r["task"], r["step"]), {}).get("syntax_error") == syn])
    for bk in ("test", "load"):
        report(f"  {kind} kind={bk}", [r for r in rows if r["kind"] == kind and r["break_kind"] == bk])
print("at confidence >= 80:")
for kind in ("unseen_break", "seen_break", "clean"):
    report(f"BROKEN>=80 on {kind}", [r for r in rows if r["kind"] == kind], threshold=80)
cost = sum((r["usage"].get("inputTokens", 0) * 2 + r["usage"].get("outputTokens", 0) * 10) / 1e6 for r in rows)
print(f"cost of the {len(rows)} kept calls: ${cost:.2f}")
json.dump(out, open(f"{scratch}/judge/summary.json", "w"), indent=1)
