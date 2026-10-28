"""Score the human check: agreement with the seen/unseen rule and Cohen's kappa. Usage: score.py "<1S 2U 3? ...>" """
import json, sys
key = json.load(open(__import__("pathlib").Path(__file__).with_name("key.json")))
answers = {}
for token in sys.argv[1].split():
    n, a = int(token[:-1]), token[-1]
    answers[n] = a
pairs = [(answers.get(int(n)), v["rule_says"]) for n, v in key.items()]
judged = [(h, r) for h, r in pairs if h in ("S", "U")]
agree = sum((h == "S") == (r == "seen") for h, r in judged)
n = len(judged)
p_o = agree / n if n else 0
hs = sum(h == "S" for h, _ in judged) / n if n else 0
rs = sum(r == "seen" for _, r in judged) / n if n else 0
p_e = hs * rs + (1 - hs) * (1 - rs)
kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else 1.0
print(f"answered {n} of {len(key)} (can't tell: {sum(h == '?' for h, _ in pairs)}, blank: {sum(h in (None, '-') for h, _ in pairs)})")
print(f"agreement {agree}/{n} = {100 * p_o:.0f}%, Cohen's kappa {kappa:.2f}")
for k, v in key.items():
    h = answers.get(int(k))
    if h in ("S", "U") and (h == "S") != (v["rule_says"] == "seen"):
        print(f"  disagree card {k}: you {h}, rule {v['rule_says']}: {v['submission']} {v['task']} onset {v['onset']} ({v['kind']})")
