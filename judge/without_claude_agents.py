"""Both judges' shares (Table II rows) with runs by Claude agents left out. Usage: python3 without_claude_agents.py judge/"""
import json, sys
d = sys.argv[1] if len(sys.argv) > 1 else "."
for judge, path in (("sonnet", "results.jsonl"), ("opus", "results_opus.jsonl")):
    rows = [json.loads(l) for l in open(f"{d}/{path}")]
    ok = [r for r in rows if r["verdict"] in ("BROKEN", "OK") and not any(w in r["submission"].lower() for w in ("claude", "sonnet", "opus", "haiku"))]
    for name, sel in (("unseen", lambda r: r["kind"] == "unseen_break"), ("unseen test", lambda r: r["kind"] == "unseen_break" and r["break_kind"] == "test"),
                      ("seen", lambda r: r["kind"] == "seen_break"), ("clean (false alarm)", lambda r: r["kind"] == "clean")):
        g = [r for r in ok if sel(r)]
        print(judge, name, f"{sum(r['verdict'] == 'BROKEN' for r in g)}/{len(g)}")
