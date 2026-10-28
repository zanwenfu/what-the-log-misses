"""On the corrected Multilingual report (report-ml-v2): the loose-rule bound (liberal.py's rule, run here) and the human
check's agreement against the corrected rule."""
import csv, json, os, re, sys
from pathlib import Path
S, REPO = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(REPO))
from replaykit.benchmarks.public_trajectories import parse_trajectory
csv.field_size_limit(sys.maxsize)
V2 = S / "ml/report-ml-v2"
subs = {s["name"]: s for s in json.load(open(S / "ml/m1copy/submissions.json"))["submissions"]}
breaks = [b for b in csv.DictReader(open(V2 / "intervals.csv")) if b["main"] == "True"]
WORD = re.compile(r"(?i)\b(test|tests|spec|specs|jest|mocha|vitest|karma|phpunit|rspec|rake|pest|minitest)\b|_test\.|\.test\.|_spec\.|Test\.php")
still, cache = 0, {}
for b in breaks:
    if b["unseen"] != "True":
        continue
    k = (b["submission"], b["task"])
    if k not in cache:
        t = parse_trajectory(json.load(open(S / f"ml/bound_trajs/{k[0]}/{k[1]}.traj.json")), mini_version=str(subs[k[0]].get("version") or ""))
        cache[k] = [c.command for c in t.commands]
    cmds = cache[k]; on = int(b["onset"]); end = int(b["repair"]) if b["repair"] not in ("", "None") else len(cmds)
    still += not any(WORD.search(c) for c in cmds[on - 1:end])
liberal = json.load(open(S / "ml/report-ml/liberal.json"))
liberal.update({"unseen_liberal": still, "breaks": len(breaks), "note": "rule plus the edited-file error clause, then any command mentioning a test counts as seen"})
json.dump(liberal, open(V2 / "liberal.json", "w"), indent=1)
key = json.load(open(S / "keys/humancheck-ml-key.json"))
ans = {int(re.match(r"\d+", a).group()): a[-1] for a in "1? 2U 3? 4? 5S 6? 7? 8? 9? 10U 11? 12S 13S 14U 15U 16? 17S 18? 19S 20S".split()}
rule = {(b["submission"], b["task"], b["onset"]): ("unseen" if b["unseen"] == "True" else "seen") for b in breaks}
agree = answered = hu_rs = hs_ru = changed = 0
for n, k in key.items():
    r = rule[(k["submission"], k["task"], k["onset"])]; changed += r != k["rule_says"]
    a = ans[int(n)]
    if a == "?":
        continue
    answered += 1; h = "unseen" if a == "U" else "seen"
    agree += h == r; hu_rs += (h == "unseen" and r == "seen"); hs_ru += (h == "seen" and r == "unseen")
hc = json.load(open(S / "ml/report-ml/humancheck_ml.json"))
hc.update({"answered": answered, "agree": agree, "disagree": {"human_unseen_rule_seen": hu_rs, "human_seen_rule_unseen": hs_ru},
           "cards_whose_rule_label_changed": changed})
json.dump(hc, open(V2 / "humancheck_ml.json", "w"), indent=1)
print("liberal still unseen", still, "of", len(breaks), f"= {100 * still / len(breaks):.0f}%"); print(json.dumps(hc))
