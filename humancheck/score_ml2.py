"""Score the Multilingual human check against the corrected rule (report-ml-v2): the author's firm answers from version 1
plus their answers on the 10 rebuilt cards, and optionally a second labeller's answers on the 20-card version 2.

    python score_ml2.py <scratchpad> "<relabel answers, e.g. 1S 2U ...>" ["<second labeller answers on 20 cards>"]
"""
import csv, json, re, sys
from pathlib import Path
S = Path(sys.argv[1]); csv.field_size_limit(sys.maxsize)
parse = lambda txt: {int(re.match(r"\d+", a).group()): a[-1] for a in txt.split()}
rule = {(b["submission"], b["task"], b["onset"]): ("unseen" if b["unseen"] == "True" else "seen")
        for b in csv.DictReader(open(S / "ml/report-ml-v2/intervals.csv")) if b["main"] == "True"}
v1key = json.load(open(S / "keys/humancheck-ml-key.json"))
v1ans = parse("1? 2U 3? 4? 5S 6? 7? 8? 9? 10U 11? 12S 13S 14U 15U 16? 17S 18? 19S 20S")
rkey = json.load(open(S / "keys/relabel-10-key.json")); rans = parse(sys.argv[2])
author = {}
for n, a in v1ans.items():
    k = v1key[str(n)]
    if a != "?":
        author[(k["submission"], k["task"], k["onset"])] = a
for n, a in rans.items():
    k = rkey[str(n)]
    author[(k["submission"], k["task"], k["onset"])] = a


def score(labels):
    called = {k: a for k, a in labels.items() if a in "SU"}
    pairs = [("unseen" if a == "U" else "seen", rule[k]) for k, a in called.items()]
    agree = sum(h == r for h, r in pairs); n = len(pairs)
    po = agree / n if n else 0
    ph = sum(h == "unseen" for h, _ in pairs) / n if n else 0; pr = sum(r == "unseen" for _, r in pairs) / n if n else 0
    pe = ph * pr + (1 - ph) * (1 - pr)
    return {"cards": len(labels), "called": n, "agree": agree, "kappa": round((po - pe) / (1 - pe), 2) if n and pe < 1 else None,
            "rule_unseen_called": sum(r == "unseen" for _, r in pairs),
            "human_unseen_rule_seen": sum(h == "unseen" and r == "seen" for h, r in pairs),
            "human_seen_rule_unseen": sum(h == "seen" and r == "unseen" for h, r in pairs)}


out = {"author": score(author)}
if len(sys.argv) > 3:
    k2 = json.load(open(S / "keys/ml2-20-key.json")); a2 = parse(sys.argv[3])
    second = {(k2[str(n)]["submission"], k2[str(n)]["task"], k2[str(n)]["onset"]): a for n, a in a2.items()}
    out["second"] = score(second)
    both = [k for k in second if second[k] in "SU" and author.get(k, "?") in "SU"]
    out["labellers_agree"] = {"both_called": len(both), "agree": sum(second[k] == author[k] for k in both)}
print(json.dumps(out, indent=1))
json.dump(out, open(S / "ml/report-ml-v2/humancheck_ml2.json", "w"), indent=1)
