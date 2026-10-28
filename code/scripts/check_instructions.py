"""What the scaffold told each agent about testing: one published run per entry, its first two messages, classified.

    python3 -I code/scripts/check_instructions.py fetch <pairs file> <download dir>
    python3 -I code/scripts/check_instructions.py classify <download dir> > data/verified/instructions_check.json

<pairs file> has one line per entry: "<board> <submission> <task>", board being verified or multilingual (the paper
used the first kept run of each entry in data/*/cells.csv). fetch reads each entry's metadata.yaml in
github.com/SWE-bench/experiments for its trajectory folder and downloads that run over anonymous HTTPS; the files are
published data, so classify only reads them as JSON. classify removes the issue text (between <pr_description> tags)
and records, per entry, whether the instructions hold the recommended workflow (a script of the agent's own to
reproduce the issue, rerun to verify the fix) and whether they ask for the repository's existing tests (any mention of
running existing, the repository's, relevant or unit tests, a test suite, pytest or runtests).
"""
import glob
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BUCKET = "https://swe-bench-submissions.s3.amazonaws.com/"
WORKFLOW = ("Create a script to reproduce the issue", "Verify your fix works by running your script again")
SUITE = re.compile(r"(run|running)\s+(the\s+)?(existing|repository'?s?|project'?s?|relevant|unit)\s+tests|test suite|"
                   r"pytest|runtests", re.I)


def get(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def fetch_one(line, out):
    board, sub, task = line.split()
    meta = get(f"https://raw.githubusercontent.com/SWE-bench/experiments/main/evaluation/{board}/{sub}/metadata.yaml")
    m = re.search(r"^\s*trajs:\s*['\"]?([^'\"\s]+)", meta.decode(), re.M)
    prefix = m.group(1) if m else ""
    bases = []
    if prefix.startswith("s3://swe-bench-submissions/"):
        bases.append(BUCKET + prefix[len("s3://swe-bench-submissions/"):])
    elif prefix.startswith("https://github.com/"):
        owner, repo, _tree, branch, *path = prefix[len("https://github.com/"):].split("/")
        bases.append(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{'/'.join(path)}")
    bases.append(f"{BUCKET}bash-only/{sub}/trajs")  # some metadata spell the folder in another case
    for base in bases:
        for url in (f"{base.rstrip('/')}/{task}/{task}.traj.json", f"{base.rstrip('/')}/{task}.traj.json"):
            try:
                data = get(url)
            except Exception:
                continue
            open(f"{out}/{board}.{sub}.json", "wb").write(data)
            return f"{board} {sub} ok"
    return f"{board} {sub} MISSING"


def instructions(path):
    d = json.load(open(path))
    msgs = d.get("messages") or d.get("trajectory") or d.get("history") or []
    text = ""
    for m in msgs[:2]:
        c = m.get("content") if isinstance(m, dict) else ""
        if isinstance(c, list):
            c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
        text += str(c) + "\n"
    i, j = text.find("<pr_description>"), text.find("</pr_description>")
    return text[:i] + text[j:] if i >= 0 and j > i else text


if sys.argv[1] == "fetch":
    lines = [l for l in open(sys.argv[2]).read().splitlines() if l.strip()]
    with ThreadPoolExecutor(8) as pool:
        for result in pool.map(lambda l: fetch_one(l, sys.argv[3]), lines):
            print(result)
else:
    rows = []
    for path in sorted(glob.glob(sys.argv[2] + "/*.json")):
        board, sub = path.rsplit("/", 1)[1][:-5].split(".", 1)
        text = instructions(path)
        rows.append({"board": board, "submission": sub, "workflow": all(w in text for w in WORKFLOW),
                     "asks_existing_tests": bool(SUITE.search(text))})
    summary = {b: {"entries": sum(r["board"] == b for r in rows),
                   "workflow": sum(r["board"] == b and r["workflow"] for r in rows),
                   "asks_existing_tests": sum(r["board"] == b and r["asks_existing_tests"] for r in rows)}
               for b in ("verified", "multilingual")}
    print(json.dumps({"summary": summary, "entries": rows}, indent=1))
