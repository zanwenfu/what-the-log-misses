"""Version 2 of the Multilingual label cards: the same 20 breaks, each card now listing every test command the agent ran
while the code was broken and every error or failure line in what it saw (or saying there were none), instead of a
recorded error text the replay often lacks. Labels hidden; keys kept apart.

    python make_cards_ml2.py <scratchpad> <repo> <out.html> <key.json> <seed> [card numbers from version 1 ...]
"""
import html, importlib.util, json, random, re, sys
from pathlib import Path
SP, REPO, OUT, KEYOUT, SEED = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), int(sys.argv[5])
only = [int(x) for x in sys.argv[6:]]
sys.path.insert(0, str(REPO))
spec = importlib.util.spec_from_file_location("rep", REPO / "scripts/public_replay_report.py")
rep = importlib.util.module_from_spec(spec); sys.modules["rep"] = rep; spec.loader.exec_module(rep)
from taste.benchmarks.public_trajectories import parse_trajectory
subs = {s["name"]: s for s in json.load(open(SP / "ml/m1copy/submissions.json"))["submissions"]}
pick = json.load(open(SP / "ml/cards_pick.json"))
random.Random(2610233).shuffle(pick)          # version 1's order: card n of version 1 is pick[n - 1]
v1 = list(enumerate(pick, 1))
if only:
    v1 = [x for x in v1 if x[0] in only]
random.Random(SEED).shuffle(v1)
KEY = re.compile(r"(FAIL|ERROR|Error|error:|Traceback|failed|failing|failures?|Failure|Exception|SyntaxError|ParseError|Parse error|"
                 r"Fatal error|syntax error|Warning:|undefined method|uninitialized constant|not ok|✕|✘|×)")
ml = {"multilingual": True}
cards, key = [], {}
for n, (old, b) in enumerate(v1, 1):
    s, t = b["submission"], b["task"]
    traj = parse_trajectory(json.load(open(SP / f"ml/cards_trajs/{s}/{t}.traj.json")), mini_version=str(subs[s].get("version") or ""))
    cmds = list(traj.commands)
    last = int(b["repair"]) if b["repair"] not in ("", "None") else len(cmds)
    window = [(k, cmds[k - 1]) for k in range(int(b["onset"]), last + 1) if 1 <= k <= len(cmds)]
    tests = [x for x in b["tests"].split(";") if x][:6]
    what = (f"{len(b['tests'].split(';'))} previously passing test(s) fail, e.g. " + "; ".join(tests)) if b["kind"] == "test" \
        else f"the tests cannot run at all ({b['load_members']} previously passing tests stop loading: a file no longer parses, or a class or module no longer loads)"
    test_runs, err_lines, rows = [], [], []
    for k, c in window:
        submit = traj.submit_index is not None and k - 1 == traj.submit_index
        out = "(this is the final submit command; its output is the submitted patch, which the agent does not see)" if submit else rep.seen_output(c)
        if not submit and (rep.is_test_command(c.command, **ml) or (rep.tests_ran(out, **ml) and not rep.is_listing(c.command))):
            test_runs.append(f"command {k} (exit {c.returncode})")
        if not submit and not rep.is_listing(c.command):
            err_lines += [f"command {k}: {l.strip()}" for l in out.splitlines() if KEY.search(l)]
        rows.append(f"<div class='cmd'><b>command {k}</b> (exit {c.returncode}): <code>{html.escape(c.command[:400])}</code>"
                    f"<div class='out'><i>first part of what it printed:</i><pre>{html.escape(out[:700])}</pre></div></div>")
    tr = ("None. No command in this stretch ran the project's tests." if not test_runs
          else "These commands ran tests: " + ", ".join(test_runs) + ".")
    el = ("<p><b>Error or failure lines anywhere in what the agent saw in this stretch:</b> none. No output contains an error, "
          "a failure or a warning.</p>" if not err_lines else
          f"<p><b>Error or failure lines anywhere in what the agent saw in this stretch</b> ({len(err_lines)}; first 15):</p>"
          f"<pre>{html.escape(chr(10).join(x[:220] for x in err_lines[:15]))}</pre>")
    own = " | ".join(x for x in [b.get("evidence", ""), b.get("evidence_places", "")] if x)
    ownp = (f"<p><b>The error the tests printed for this break:</b> <code>{html.escape(own)}</code></p>" if own else
            "<p><b>The error the tests printed for this break:</b> not recorded by the replay. Judge from the test runs and "
            "the error lines: an error that points at the file the agent just edited counts as showing the break.</p>")
    key[n] = {"v1_card": old, "submission": s, "task": t, "onset": b["onset"], "kind": b["kind"]}
    cards.append(f"<section><h3>Card {n}: {html.escape(t)}</h3><p><b>What broke at command {b['onset']}:</b> {html.escape(what)}. "
                 f"The break lasts until command {last}.</p>{ownp}<p><b>Test runs while it was broken:</b> {tr}</p>{el}"
                 f"<details><summary>Every command in this stretch</summary>{''.join(rows)}</details>"
                 f"<p class='q'><b>Question:</b> while it was broken, did the agent's log SHOW the break, meaning a test run that "
                 f"reported a failure, a broken test named as failing, or an error this break causes?<br>"
                 f"<label><input type='radio' name='c{n}' value='S'> yes, shown</label> &nbsp; "
                 f"<label><input type='radio' name='c{n}' value='U'> no, not shown</label> &nbsp; "
                 f"<label><input type='radio' name='c{n}' value='?'> can't tell</label></p></section>")
page = f"""<!doctype html><html><head><meta charset='utf-8'><title>Label check v2</title><style>
body{{font:15px/1.45 -apple-system,Segoe UI,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#fafafa;color:#222}}
section{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:18px 0}}
pre{{white-space:pre-wrap;background:#f3f3f3;padding:6px;font-size:12.5px;max-height:260px;overflow:auto}}
.cmd{{border-left:3px solid #bbb;padding-left:10px;margin:8px 0}} .q{{background:#eef5ff;padding:8px;border-radius:6px}}
button{{font-size:16px;padding:8px 16px}}</style></head><body>
<h2>Label check, SWE-bench Multilingual ({len(cards)} cards: JavaScript, PHP, Ruby)</h2>
<p>Each card is one moment when an AI coding agent's edit broke tests that used to pass. Judge only from what the agent's
log showed while the code was broken. "Shown" means: a test run that reported a failure, any output naming one of the
broken tests as failing, or an error this break causes (for example a SyntaxError, PHP's Parse error, or Ruby's
NoMethodError, usually pointing at the file the agent just edited). Reading the code does not count. Each card lists the
test runs and every error line; open "Every command in this stretch" for the full log. Choose "can't tell" only if the
card truly does not let you decide. When done, click the button and send us the copied line.</p>
{''.join(cards)}
<p><button onclick="let a=[];for(let i=1;i<={len(cards)};i++){{let e=document.querySelector('input[name=c'+i+']:checked');a.push(i+(e?e.value:'-'))}};navigator.clipboard.writeText(a.join(' '));document.getElementById('done').textContent='Copied: '+a.join(' ')">Copy my answers</button></p>
<p id='done'></p></body></html>"""
OUT.write_text(page)
json.dump(key, open(KEYOUT, "w"), indent=1)
print(len(cards), "cards ->", OUT)
