"""Four log readers on the same sampled commands: Sonnet 5.5, Opus 5.5, DeepSeek V3.2, and Sonnet 5.5 shown four
execution-labelled examples. Shares by execution label (Wilson 95%), precision at the natural rate of breaks among
edits made on clean code (and after a syntax check), and a paired exact test for the examples' effect on Sonnet.

    python3 analyse3.py <judge dir> <prevalence> <post-syntax prevalence> > summary3.json
"""
import json, math, sys

d, prevalence, post = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
FILES = {"sonnet": "results.jsonl", "opus": "results_opus.jsonl", "deepseek": "results_deepseek.jsonl",
         "sonnet_examples": "results_sonnet_examples.jsonl"}


def wilson(k, n, z=1.96):
    if not n:
        return [None, None]
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(100 * (c - h)), round(100 * (c + h))]


def key(r):
    return (r["kind"], r["submission"], r["task"], r["step"])


def load(name):
    try:
        rows = [json.loads(l) for l in open(f"{d}/{FILES[name]}")]
    except FileNotFoundError:
        return {}
    return {key(r): r for r in rows if r.get("verdict") in ("BROKEN", "OK")}


judges = {name: load(name) for name in FILES}
common = set.intersection(*[set(v) for v in judges.values() if v])
groups = {
    "unseen": lambda k, r: k[0] == "unseen_break",
    "unseen_load": lambda k, r: k[0] == "unseen_break" and r["break_kind"] == "load",
    "unseen_test": lambda k, r: k[0] == "unseen_break" and r["break_kind"] == "test",
    "seen": lambda k, r: k[0] == "seen_break",
    "clean": lambda k, r: k[0] == "clean",
}
out = {"common_items": len(common)}
for name, rows in judges.items():
    if not rows:
        continue
    res = {}
    for g, sel in groups.items():
        sub = [rows[k] for k in common if sel(k, rows[k])]
        k = sum(r["verdict"] == "BROKEN" for r in sub)
        res[g] = {"called": k, "n": len(sub), "share": round(100 * k / len(sub)) if sub else None, "ci": wilson(k, len(sub))}
    recall = 0.55 * res["unseen"]["share"] / 100 + 0.45 * res["seen"]["share"] / 100
    fa = res["clean"]["share"] / 100
    lo, hi = wilson(res["clean"]["called"], res["clean"]["n"])
    prec = lambda f, p, r: r * p / (r * p + f * (1 - p)) if (r * p + f * (1 - p)) else None
    res["precision"] = round(100 * prec(fa, prevalence, recall))
    res["precision_ci"] = [round(100 * prec(hi / 100, prevalence, recall)), round(100 * prec(lo / 100, prevalence, recall))]
    res["precision_after_syntax_check"] = round(100 * prec(fa, post, res["unseen_test"]["share"] / 100))
    out[name] = res


def paired(a, b, sel):
    """Exact two-sided McNemar on items where the two readers disagree."""
    ks = [k for k in common if sel(k, judges[a][k])]
    up = sum(judges[a][k]["verdict"] == "OK" and judges[b][k]["verdict"] == "BROKEN" for k in ks)
    down = sum(judges[a][k]["verdict"] == "BROKEN" and judges[b][k]["verdict"] == "OK" for k in ks)
    n = up + down
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(0, min(up, down) + 1)) / 2 ** n) if n else 1.0
    return {"to_broken": up, "to_ok": down, "p": round(p, 4), "n": len(ks)}


if judges.get("sonnet_examples"):
    out["examples_effect_on_sonnet"] = {g: paired("sonnet", "sonnet_examples", sel) for g, sel in groups.items()}
print(json.dumps(out, indent=1))
