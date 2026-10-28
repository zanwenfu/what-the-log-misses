"""Whole-run judge: a model reads an agent's complete log, as a post-hoc auditor would, and says for every command that
changed the code whether the repository was broken right after it. Scored against the execution labels on every edit
of 150 random kept Verified runs, so precision is measured at the natural rate of breaks, with no reweighting.

    .venv/bin/python judge_full.py <scratchpad> <repo> --model sonnet|opus [--limit N] [--jobs 8] [--prompts-only]

Bedrock Converse (bearer token in AWS_BEARER_TOKEN_BEDROCK); the shared system prompt carries a cache point; no
temperature (the models reject it); maxTokens set explicitly. Spend is tracked per call and the run stops at --cap.
"""
import argparse, concurrent.futures, json, os, re, sys, threading, time, urllib.error, urllib.request
ap = argparse.ArgumentParser()
ap.add_argument("scratch"); ap.add_argument("repo")
ap.add_argument("--model", default="sonnet", choices=["sonnet", "opus"])
ap.add_argument("--limit", type=int, default=0); ap.add_argument("--jobs", type=int, default=8)
ap.add_argument("--cap", type=float, default=20.0, help="stop starting new calls once this many dollars are spent")
ap.add_argument("--out", default=""); ap.add_argument("--prompts-only", action="store_true")
ap.add_argument("--max-tokens", type=int, default=12000)
ap.add_argument("--redo-unanswered", action="store_true", help="re-ask runs whose reply answered fewer edits than asked")
args = ap.parse_args()
sys.path.insert(0, args.repo)
import importlib.util  # noqa: E402
from taste.benchmarks.public_trajectories import parse_trajectory  # noqa: E402
spec = importlib.util.spec_from_file_location("rep", f"{args.repo}/scripts/public_replay_report.py")
rep = importlib.util.module_from_spec(spec); sys.modules["rep"] = rep; spec.loader.exec_module(rep)
MODEL = {"sonnet": "global.anthropic.claude-sonnet-5-5", "opus": "global.anthropic.claude-opus-5-5"}[args.model]
URL = f"https://bedrock-runtime.us-east-1.amazonaws.com/model/{MODEL}/converse"
KEY = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
PRICE = {"sonnet": {"in": 2.00, "out": 10.00, "cache_read": 0.10, "cache_write": 2.50},
         "opus": {"in": 4.00, "out": 20.00, "cache_read": 0.20, "cache_write": 5.00}}[args.model]
OUT = args.out or f"{args.scratch}/judge/full_{args.model}.jsonl"
SYSTEM = (
    "You are reviewing the complete log of an AI coding agent that worked on an issue in a Python repository. The log "
    "lists every shell command the agent ran and what each printed, exactly as the agent saw them (long outputs were "
    "cut to their first and last part). Commands that changed the repository's code are marked [EDIT].\n\n"
    "For EACH command marked [EDIT], judge the state of the repository right after it: BROKEN means at least one test "
    "that passed before the agent started would now fail, or could no longer run (for example because of a syntax "
    "error, an indentation error, or a broken import); OK means every such test would still pass. Consider every edit "
    "up to that point, not only that one. You may use the whole log, including what happened later. Judge only from "
    "the log.\n\nAnswer with exactly one line per [EDIT] command, in order, in this form and nothing else:\n"
    "STEP <number>: BROKEN\nor\nSTEP <number>: OK"
)
subs = {s["name"]: s for s in json.load(open(f"{args.scratch}/pubtraj/submissions.json"))["submissions"]}


def task_text(raw):
    for m in raw.get("messages", []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        text = c if isinstance(c, str) else " ".join(b.get("text", "") for b in c if isinstance(b, dict)) if isinstance(c, list) else ""
        found = re.search(r"<pr_description>(.*?)</pr_description>", text, re.S)
        return (found.group(1) if found else text)[:4000].strip()
    return ""


def clip(text, head, tail):
    text = text or ""
    return text if len(text) <= head + tail + 40 else text[:head] + f"\n[... {len(text) - head - tail} characters cut ...]\n" + text[-tail:]


def prompt(item):
    s, t = item["submission"], item["task"]
    raw = json.load(open(f"{args.scratch}/judge/full_trajs/{s}/{t}.traj.json"))
    traj = parse_trajectory(raw, mini_version=str(subs[s].get("version") or ""))
    edits = {e["command"] for e in item["edits"]}
    lines = [f"TASK GIVEN TO THE AGENT:\n{task_text(raw)}\n", "THE AGENT'S COMPLETE LOG:"]
    for n, c in enumerate(traj.commands, 1):
        tag = " [EDIT]" if n in edits else ""
        out = "(final submit; output not shown to the agent)" if traj.submit_index is not None and n - 1 == traj.submit_index else clip(rep.seen_output(c), 900, 600)
        lines.append(f"\n[{n}]{tag} $ {clip(c.command, 1200, 300)}\n(exit status: {c.returncode})\n{out}")
    lines.append("\n[EDIT] commands to judge, in order: " + ", ".join(str(e["command"]) for e in item["edits"]))
    return "\n".join(lines)


items = json.load(open(f"{args.scratch}/judge/sample_full.json"))
if args.prompts_only:
    sizes = sorted(len(prompt(i)) for i in items)
    tok = [x / 2.3 for x in sizes]  # the earlier judge prompts ran at about 2.3 characters per token
    print(f"{len(sizes)} prompts; chars median {sizes[len(sizes)//2]:,}, p90 {sizes[int(.9*len(sizes))]:,}, max {sizes[-1]:,}; "
          f"about {sum(tok)/1e6:.2f}M input tokens, max {max(tok)/1e3:.0f}k")
    for m, p in (("sonnet", (2, 10)), ("opus", (4, 20))):
        print(m, f"input ${sum(tok) * p[0] / 1e6:.2f} + output (~1.5k tokens a run) ${150 * 1500 * p[1] / 1e6:.2f}")
    raise SystemExit(0)
rows_done = [json.loads(l) for l in open(OUT)] if os.path.exists(OUT) else []
if args.redo_unanswered:  # keep complete answers only; the rest are asked again
    real = {(i["submission"], i["task"]): sum(e["command"] > 0 for e in i["edits"]) for i in items}
    keep = [r for r in rows_done if sum(int(k) > 0 for k in r["calls"]) >= real[(r["submission"], r["task"])]]
    with open(OUT, "w") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in keep)
    rows_done = keep
done = {(r["submission"], r["task"]) for r in rows_done}
todo = [i for i in items if (i["submission"], i["task"]) not in done]
if args.limit:
    todo = todo[:args.limit]
lock, spent = threading.Lock(), [0.0]


def call(text):
    body = {"system": [{"text": SYSTEM}, {"cachePoint": {"type": "default"}}],
            "messages": [{"role": "user", "content": [{"text": text}]}], "inferenceConfig": {"maxTokens": args.max_tokens}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
        "authorization": f"Bearer {KEY}", "content-type": "application/json", "accept": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt * 3); continue
            raise RuntimeError(f"HTTP {exc.code}: {exc.read()[:300]!r}") from None
    raise RuntimeError("retries exhausted")


def judge(item):
    with lock:
        if spent[0] >= args.cap:
            return None
    ans = call(prompt(item))
    reply = " ".join(b.get("text", "") for b in ans["output"]["message"]["content"])
    u = ans.get("usage", {})
    cost = (u.get("inputTokens", 0) * PRICE["in"] + u.get("outputTokens", 0) * PRICE["out"]
            + u.get("cacheReadInputTokens", 0) * PRICE["cache_read"] + u.get("cacheWriteInputTokens", 0) * PRICE["cache_write"]) / 1e6
    with lock:
        spent[0] += cost
    calls = {int(n): v for n, v in re.findall(r"STEP\s+(\d+)\s*:\s*(BROKEN|OK)", reply)}
    return {"submission": item["submission"], "task": item["task"], "judge": args.model, "calls": calls,
            "answered": sum(e["command"] in calls for e in item["edits"]), "edits": len(item["edits"]),
            "usage": u, "cost": cost, "reply_tail": reply.strip()[-300:]}


n = 0
with open(OUT, "a") as log, concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
    for res in pool.map(judge, todo):
        if res is None:
            continue
        n += 1; log.write(json.dumps(res) + "\n"); log.flush()
        u = res["usage"]
        print(f"{n}/{len(todo)} answered {res['answered']}/{res['edits']} in={u.get('inputTokens')} out={u.get('outputTokens')} "
              f"cache={u.get('cacheReadInputTokens', 0)} spent=${spent[0]:.2f}", flush=True)
print(f"done: {n} calls, ${spent[0]:.2f}")
