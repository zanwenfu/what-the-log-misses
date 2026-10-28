"""40 cards for a human check of the seen/unseen rule (20 seen, 20 unseen), labels hidden; key file kept apart."""
import csv, html, importlib.util, json, random, re, sys
from pathlib import Path
SP, REPO = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(REPO))
spec = importlib.util.spec_from_file_location("rep", REPO / "scripts/public_replay_report.py")
rep = importlib.util.module_from_spec(spec); sys.modules["rep"] = rep; spec.loader.exec_module(rep)
from replaykit.benchmarks.public_trajectories import parse_trajectory
csv.field_size_limit(sys.maxsize)
subs = {s["name"]: s for s in json.load(open(SP / "ml/m1copy/submissions.json"))["submissions"]}
pick = json.load(open(SP / "ml/cards_pick.json"))
rng = random.Random(2610233)
rng.shuffle(pick)
KEY = re.compile(r"(FAIL|ERROR|Error|error:|Traceback|failed|failing|failures?|Failure|Exception|SyntaxError|ParseError|Parse error|Fatal error|syntax error|passing|examples?,|Tests: |OK \(|not ok|\u2715|\u2718|\u00d7|Executed \d+)")
cards, key = [], {}
for n, b in enumerate(pick, 1):
    s, t = b["submission"], b["task"]
    traj = parse_trajectory(json.load(open(SP / f"ml/cards_trajs/{s}/{t}.traj.json")), mini_version=str(subs[s].get("version") or ""))
    cmds = list(traj.commands)
    last = int(b["repair"]) if b["repair"] not in ("", "None") else len(cmds)
    window = [(k, cmds[k - 1]) for k in range(int(b["onset"]), last + 1) if 1 <= k <= len(cmds)]
    tests = [x for x in b["tests"].split(";") if x][:6]
    what = (f"{len(b['tests'].split(';'))} previously passing test(s) fail, e.g. " + "; ".join(tests)) if b["kind"] == "test" \
        else f"the tests cannot run at all ({b['load_members']} previously passing tests stop loading: a module no longer imports or a test class's set-up dies)"
    rows = []
    for k, c in window:
        out = rep.seen_output(c)
        if traj.submit_index is not None and k - 1 == traj.submit_index:
            out = "(this is the final submit command; its output is the submitted patch, which the agent does not see)"
        keylines = [l for l in out.splitlines() if KEY.search(l) or any(x.split("::")[-1].split(" ")[0] in l for x in tests if len(x) > 6)][:12]
        rows.append(f"<div class='cmd'><b>command {k}</b> (exit {c.returncode}): <code>{html.escape(c.command[:400])}</code>"
                    f"<div class='out'><i>first part of what it printed:</i><pre>{html.escape(out[:700])}</pre>"
                    + (f"<i>key lines anywhere in what it printed:</i><pre>{html.escape(chr(10).join(keylines)[:1500])}</pre>" if keylines else "")
                    + "</div></div>")
    key[n] = {"submission": s, "task": t, "onset": b["onset"], "kind": b["kind"], "rule_says": "unseen" if b["unseen"] == "True" else "seen"}
    own = " | ".join(x for x in [b.get("evidence", ""), b.get("evidence_places", "")] if x) or "(no error line recorded for this break)"
    cards.append(f"<section><h3>Card {n}: {html.escape(t)}</h3><p><b>What broke at command {b['onset']}:</b> {html.escape(what)}. "
                 f"The break lasts until command {last}.</p>"
                 f"<p><b>This break's own error</b> (what the tests printed; counts as shown only if the agent's log shows the same error, "
                 f"or the same file and line for a syntax error): <code>{html.escape(own)}</code></p>{''.join(rows)}"
                 f"<p class='q'><b>Question:</b> while it was broken, did the agent's log SHOW the break, meaning a test run that "
                 f"reported a failure, a broken test named as failing, or this break's own error shown above?<br>"
                 f"<label><input type='radio' name='c{n}' value='S'> yes, shown</label> &nbsp; "
                 f"<label><input type='radio' name='c{n}' value='U'> no, not shown</label> &nbsp; "
                 f"<label><input type='radio' name='c{n}' value='?'> can't tell</label></p></section>")
page = f"""<!doctype html><html><head><meta charset='utf-8'><title>Label check</title><style>
body{{font:15px/1.45 -apple-system,Segoe UI,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#fafafa;color:#222}}
section{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:18px 0}}
pre{{white-space:pre-wrap;background:#f3f3f3;padding:6px;font-size:12.5px;max-height:220px;overflow:auto}}
.cmd{{border-left:3px solid #bbb;padding-left:10px;margin:8px 0}} .q{{background:#eef5ff;padding:8px;border-radius:6px}}
button{{font-size:16px;padding:8px 16px}}</style></head><body>
<h2>Human check of the seen/unseen labels, SWE-bench Multilingual (20 cards: JavaScript, PHP, Ruby)</h2>
<p>For each card, judge only from what the agent's log showed while the code was broken. "Shown" means: a test run that
reported any failure, any output naming one of the broken tests as failing, or the error this break causes (for example a SyntaxError, PHP's Parse error, or Ruby's NameError). Reading the code itself does not count. When done, click the button and paste the line into the chat.</p>
{''.join(cards)}
<p><button onclick="let a=[];for(let i=1;i<={len(cards)};i++){{let e=document.querySelector('input[name=c'+i+']:checked');a.push(i+(e?e.value:'-'))}};navigator.clipboard.writeText(a.join(' '));document.getElementById('done').textContent='Copied: '+a.join(' ')">Copy my answers</button></p>
<p id='done'></p></body></html>"""
(SP / "humancheck/label-check-multilingual.html").write_text(page)
(SP / "keys").mkdir(exist_ok=True)
json.dump(key, open(SP / "keys/humancheck-ml-key.json", "w"), indent=1)
print(len(cards), "cards;", sum(v["rule_says"] == "unseen" for v in key.values()), "unseen in key;", (SP / "humancheck/label-check.html").stat().st_size // 1024, "KB")
