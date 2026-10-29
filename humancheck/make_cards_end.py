"""30 blind cards for a human check of the breaks that runs END on: 20 the rule calls unseen and 10 it calls seen,
drawn at random (seed 2610282) from the kept Verified runs whose final code is broken, shuffled; labels hidden.

Usage: python3 -I humancheck/make_cards_end.py <package dir> <trajectory dir> <cards.html> <key.json>
Keep the key file away from the second reader. The trajectory dir holds <submission>/<task>.traj.json as published.
"""
import csv, html, json, random, re, sys
from pathlib import Path
csv.field_size_limit(sys.maxsize)
PKG, TR, CARDS, KEY = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, str(PKG / "code"))
from replaykit.benchmarks.public_trajectories import parse_trajectory  # noqa: E402
COLOUR = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
def seen(c):
    out = c.output or ""
    if c.output_truncated and len(out) > 10000:
        out = out[:5000] + "\n" + out[-5000:]
    return COLOUR.sub("", out)
breaks = [b for b in csv.DictReader((PKG / "data/verified/intervals.csv").open())
          if b["main"] == "True" and b["unseen"] in ("True", "False") and b["ended"] in ("", "None")]
rng = random.Random(2610282)
pick = []
for flag, n in (("True", 20), ("False", 10)):
    pool = sorted((b for b in breaks if b["unseen"] == flag), key=lambda b: (b["submission"], b["task"]))
    pick += rng.sample(pool, n)
rng.shuffle(pick)
KEYLINE = re.compile(r"(FAIL|ERROR|Error|error:|Traceback|failed|Exception|SyntaxError|IndentationError|ImportError|"
                     r"passed|ran \d+ test|Ran \d+ test|OK\b|No module named)")
cards, key = [], {}
for n, b in enumerate(pick, 1):
    s, t = b["submission"], b["task"]
    traj = parse_trajectory(json.loads((TR / s / f"{t}.traj.json").read_text()), mini_version=re.search(r"mini-v([\d.]+)", s).group(1))
    cmds = list(traj.commands)
    window = [(k, cmds[k - 1]) for k in range(int(b["onset"]), len(cmds) + 1)]
    tests = [x for x in b["tests"].split(";") if x]
    what = (f"{len(tests)} previously passing test(s) fail, e.g. " + "; ".join(tests[:6])) if b["kind"] == "test" else \
        f"the tests cannot run at all ({b['load_members']} previously passing tests stop loading: a module no longer imports or a test class's set-up fails)"
    rows = []
    for k, c in window:
        out = seen(c)
        if traj.submit_index is not None and k - 1 == traj.submit_index:
            out = "(this is the final submit command; its output is the submitted patch, which the agent does not see)"
        names = [x.split("::")[-1].split(" ")[0] for x in tests if len(x) > 6]
        keylines = [l for l in out.splitlines() if KEYLINE.search(l) or any(nm and nm in l for nm in names)][:12]
        first = "the command that started the break" if k == int(b["onset"]) else f"command {k}"
        rows.append(f"<div class='cmd'><b>{first}</b> (command {k}, exit {c.returncode}): <code>{html.escape(c.command[:600])}</code>"
                    f"<div class='out'><i>first part of what it printed:</i><pre>{html.escape(out[:700])}</pre>"
                    + (f"<i>key lines anywhere in what it printed:</i><pre>{html.escape(chr(10).join(keylines)[:1500])}</pre>" if keylines else "")
                    + "</div></div>")
    key[n] = {"submission": s, "task": t, "onset": b["onset"], "kind": b["kind"], "syntax_error": b["syntax_error"],
              "rule_says": "unseen" if b["unseen"] == "True" else "seen"}
    cards.append(f"<section><h3>Card {n}: {html.escape(t)}</h3><p><b>What broke at command {b['onset']}:</b> {html.escape(what)}. "
                 f"The code stays broken until the run ends (command {len(cmds)}).</p>{''.join(rows)}"
                 f"<p class='q'><b>Question:</b> while it was broken, did the agent's log SHOW the break, meaning a test run that "
                 f"reported a failure, a broken test named as failing, or an error that the broken code itself causes?<br>"
                 f"<label><input type='radio' name='c{n}' value='S'> yes, shown</label> &nbsp; "
                 f"<label><input type='radio' name='c{n}' value='U'> no, not shown</label> &nbsp; "
                 f"<label><input type='radio' name='c{n}' value='?'> can't tell</label></p></section>")
page = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Label check, final breaks</title><style>
body{{font:15px/1.45 -apple-system,Segoe UI,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#fafafa;color:#222}}
section{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:18px 0}}
pre{{white-space:pre-wrap;background:#f3f3f3;padding:6px;font-size:12.5px;max-height:220px;overflow:auto}}
.cmd{{border-left:3px solid #bbb;padding-left:10px;margin:8px 0}} .q{{background:#eef5ff;padding:8px;border-radius:6px}}
button{{font-size:16px;padding:8px 16px}}</style></head><body>
<h2>Human check of the seen/unseen labels: breaks that runs end on ({len(cards)} cards)</h2>
<p>Each card shows a run from the command that broke the code to the end of the run; the code never recovers. Judge only
from what the agent's log showed after the break began. "Shown" means: a test run that reported any failure, any output
naming one of the broken tests as failing, or an error that the broken code itself causes (for example a SyntaxError or
ImportError pointing at the file the breaking command edited). Reading the code, or a listing of it with cat, grep or
sed -n, does not count. An error caused by something else, such as a missing package, does not count either. When
done, click the button and paste the line into the chat.</p>
{''.join(cards)}
<p><button onclick="let a=[];for(let i=1;i<={len(cards)};i++){{let e=document.querySelector('input[name=c'+i+']:checked');a.push(i+(e?e.value:'-'))}};navigator.clipboard.writeText(a.join(' '));document.getElementById('done').textContent='Copied: '+a.join(' ')">Copy my answers</button></p>
<p id='done'></p></body></html>"""
CARDS.write_text(page)
KEY.write_text(json.dumps(key, indent=1))
print(len(cards), "cards;", sum(v["rule_says"] == "unseen" for v in key.values()), "unseen in key;", CARDS.stat().st_size // 1024, "KB")
