"""P2 pilot: does a model judge, reading the agent's own log, flag the steps that break previously passing tests?

    .venv/bin/python judge.py <scratchpad> <repo> [--limit N] [--jobs 6] [--out results.jsonl]

Each sampled step (judge/sample.json: unseen breaking steps, seen breaking steps, matched clean edits) becomes one
prompt: the task the agent was given, every earlier command (outputs of the last 15 as the model saw them), and the
step in question. The judge is asked directly whether the code is broken right after that step: an upper bound on
what a log reader can see, since a process reward model is not asked about each step this pointedly.
Bedrock Converse, Claude Sonnet 5.5 (global profile; it takes no temperature), max 2,000 output tokens (it reasons before answering); the shared system prompt
carries a cache point.
"""
import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("scratch")
ap.add_argument("repo")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--jobs", type=int, default=6)
ap.add_argument("--out", default="judge/results.jsonl")
ap.add_argument("--model", default="sonnet", choices=["sonnet", "opus", "deepseek"])
ap.add_argument("--examples", default="", help="judge/examples.json: labelled examples from tasks no sampled step comes from")
ap.add_argument("--sample", default="judge/sample.json")
ap.add_argument("--prompts-only", action="store_true", help="build every prompt, call nothing")
args = ap.parse_args()
sys.path.insert(0, args.repo)
import importlib.util  # noqa: E402

from taste.benchmarks.public_trajectories import parse_trajectory  # noqa: E402

spec = importlib.util.spec_from_file_location("rep", f"{args.repo}/scripts/public_replay_report.py")
rep = importlib.util.module_from_spec(spec)
sys.modules["rep"] = rep
spec.loader.exec_module(rep)

MODEL = {"sonnet": "global.anthropic.claude-sonnet-5-5", "opus": "global.anthropic.claude-opus-5-5",
         "deepseek": "deepseek.v3.2"}[args.model]
URL = f"https://bedrock-runtime.us-east-1.amazonaws.com/model/{MODEL}/converse"
KEY = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
PRICE = {"sonnet": {"in": 2.00, "out": 10.00, "cache_read": 0.10, "cache_write": 2.50},  # $ per M tokens (Bedrock list, Oct 16)
         "opus": {"in": 4.00, "out": 20.00, "cache_read": 0.20, "cache_write": 5.00},
         "deepseek": {"in": 0.62, "out": 1.85, "cache_read": 0.62, "cache_write": 0.62}}[args.model]  # deepseek: estimate
SYSTEM = (
    "You are reviewing the log of an AI coding agent that is fixing an issue in a Python repository. The log lists "
    "the shell commands the agent ran and what each printed, exactly as the agent saw them (long outputs were cut "
    "to their first and last part). Your job is to judge the state of the repository right after the LAST command "
    "shown.\n\nQuestion: right after the last command, is the repository broken, meaning at least one test that "
    "passed before the agent started would now fail, or could no longer run (for example because of a syntax error, "
    "an indentation error, or a broken import)? Consider every edit the agent has made so far, not only the last one. "
    "Judge only from the log.\n\nAnswer in exactly this form, with nothing else:\n"
    "VERDICT: BROKEN or OK\nCONFIDENCE: a whole number from 0 to 100 (how sure you are of the verdict)\n"
    "REASON: one sentence"
)
subs = {s["name"]: s for s in json.load(open(f"{args.scratch}/pubtraj/submissions.json"))["submissions"]}


def task_text(raw: dict) -> str:
    for message in raw.get("messages", []):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        text = content if isinstance(content, str) else " ".join(
            block.get("text", "") for block in content if isinstance(block, dict)) if isinstance(content, list) else ""
        found = re.search(r"<pr_description>(.*?)</pr_description>", text, re.S)
        return (found.group(1) if found else text)[:4000].strip()
    return ""


def clip(text: str, head: int, tail: int) -> str:
    text = text or ""
    return text if len(text) <= head + tail + 40 else text[:head] + f"\n[... {len(text) - head - tail} characters cut ...]\n" + text[-tail:]


def prompt(item: dict, trajs: str = "judge_trajs") -> str:
    s, t, k = item["submission"], item["task"], item["step"]
    raw = json.load(open(f"{args.scratch}/{trajs}/{s}/{t}.traj.json"))
    traj = parse_trajectory(raw, mini_version=str(subs[s].get("version") or ""))
    commands = list(traj.commands)[:k]
    lines = [f"TASK GIVEN TO THE AGENT:\n{task_text(raw)}\n", "THE AGENT'S LOG SO FAR:"]
    for n, c in enumerate(commands, 1):
        last = n == len(commands)
        tag = " <<< LAST COMMAND" if last else ""
        if n > len(commands) - 15:
            lines.append(f"\n[{n}]{tag} $ {clip(c.command, 1200, 300)}\n(exit status: {c.returncode})\n"
                         f"{clip(rep.seen_output(c), 900, 600)}")
        else:
            lines.append(f"\n[{n}] $ {clip(c.command, 250, 50)}\n(output omitted)")
    return "\n".join(lines)


def with_examples(system: str) -> str:
    """The same instructions, then labelled examples from tasks no sampled step comes from (the execution label as answer)."""
    if not args.examples:
        return system
    parts = [system, "\n\nBelow are four worked examples from OTHER tasks. For each, we re-ran the tests right after the "
             "last command shown; the EXECUTION LABEL is the true answer. Use them to calibrate, then judge the new log.\n"]
    for n, ex in enumerate(json.load(open(f"{args.scratch}/{args.examples}")), 1):
        label = ("EXECUTION LABEL: BROKEN. These previously passing tests now fail: " + "; ".join(ex["tests"])
                 if ex["kind"] == "example_broken" else "EXECUTION LABEL: OK. Every previously passing test still passes.")
        parts.append(f"\n===== EXAMPLE {n} =====\n{prompt(ex, trajs='judge/examples_trajs')}\n{label}\n")
    parts.append("\n===== END OF EXAMPLES =====")
    return "".join(parts)


SYSTEM_USED = with_examples(SYSTEM)


def call(text: str) -> dict:
    system = [{"text": SYSTEM_USED}] + ([{"cachePoint": {"type": "default"}}] if "anthropic" in MODEL else [])
    body = {"system": system,
            "messages": [{"role": "user", "content": [{"text": text}]}],
            "inferenceConfig": {"maxTokens": 6000}}
    request = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
        "authorization": f"Bearer {KEY}", "content-type": "application/json", "accept": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt * 3)
                continue
            raise RuntimeError(f"HTTP {exc.code}: {exc.read()[:300]!r}") from None
    raise RuntimeError("retries exhausted")


def judge(item: dict) -> dict:
    text = prompt(item)
    answer = call(text)
    reply = " ".join(block.get("text", "") for block in answer["output"]["message"]["content"])
    usage = answer.get("usage", {})
    verdict = re.search(r"VERDICT:\s*(BROKEN|OK)", reply)
    confidence = re.search(r"CONFIDENCE:\s*(\d+)", reply)
    return {**item, "judge": args.model + ("+examples" if args.examples else ""), "verdict": verdict.group(1) if verdict else None,
            "confidence": int(confidence.group(1)) if confidence else None, "reply": reply.strip()[:500],
            "prompt_chars": len(text), "usage": usage}


items = json.load(open(f"{args.scratch}/{args.sample}"))
if args.prompts_only:
    print(f"system prompt: {len(SYSTEM_USED)} chars")
    print(SYSTEM_USED[-1400:])
    sizes = sorted(len(prompt(i)) for i in items)
    print(f"{len(sizes)} prompts; chars median {sizes[len(sizes) // 2]}, p90 {sizes[int(0.9 * len(sizes))]}, max {sizes[-1]}; "
          f"about {sum(sizes) / 4 / 1e6:.2f}M input tokens")
    print(prompt(items[0])[:1500])
    print("...")
    print(prompt(items[0])[-1500:])
    raise SystemExit(0)
done = set()
if os.path.exists(args.out):
    done = {(r["kind"], r["submission"], r["task"], r["step"]) for r in map(json.loads, open(args.out))}
todo = [i for i in items if (i["kind"], i["submission"], i["task"], i["step"]) not in done]
if args.limit:
    order = {"unseen_break": 0, "clean": 1, "seen_break": 2}
    picked, seen_kinds = [], {}
    for item in todo:  # a mix of kinds for the dry run
        if seen_kinds.get(item["kind"], 0) < max(1, args.limit * (2 if item["kind"] != "seen_break" else 1) // 5):
            picked.append(item)
            seen_kinds[item["kind"]] = seen_kinds.get(item["kind"], 0) + 1
        if len(picked) == args.limit:
            break
    todo = sorted(picked, key=lambda i: order[i["kind"]])
cost, n = 0.0, 0
with open(args.out, "a") as log, concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
    for result in pool.map(judge, todo):
        u = result["usage"]
        cost += (u.get("inputTokens", 0) * PRICE["in"] + u.get("outputTokens", 0) * PRICE["out"]
                 + u.get("cacheReadInputTokens", 0) * PRICE["cache_read"]
                 + u.get("cacheWriteInputTokens", 0) * PRICE["cache_write"]) / 1e6
        n += 1
        log.write(json.dumps(result) + "\n")
        log.flush()
        print(f"{n}/{len(todo)} {result['kind']:12s} {result['verdict']} {result['confidence']} "
              f"in={u.get('inputTokens')} out={u.get('outputTokens')} cache={u.get('cacheReadInputTokens', 0)} "
              f"spent=${cost:.3f}", flush=True)
print(f"done: {n} calls, ${cost:.2f}")
