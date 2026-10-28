"""The edit-flag baseline on the judges' footing: among edits made on clean code, flag every edit that no test run
follows before the next edit; score the flags against break onsets (the edit leaves the code broken)."""
import csv, json, sys, importlib.util, collections, pathlib
code, root, report = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, code)
spec = importlib.util.spec_from_file_location("rep", f"{code}/scripts/public_replay_report.py")
rep = importlib.util.module_from_spec(spec); sys.modules["rep"] = rep; spec.loader.exec_module(rep)
csv.field_size_limit(sys.maxsize)
cells = [r for r in csv.DictReader(open(f"{report}/cells.csv")) if r["main"] == "True"]
states = collections.defaultdict(list)
for s in csv.DictReader(open(f"{report}/states.csv")):
    if s["trigger"] != "final":
        states[(s["submission"], s["task"])].append((int(s["seq"]), int(s["command"]), s["status"]))
subs = json.load(open(root / "submissions.json"))
subs = subs.get("submissions", subs) if isinstance(subs, dict) else subs
subs = {s["name"]: s for s in subs} if isinstance(subs, list) else subs
tab = collections.Counter()
for r in cells:
    key = (r["submission"], r["task"])
    meta = subs.get(r["submission"], {})
    v = str(meta.get("version") or meta.get("mini_version") or meta.get("mini-swe-agent_version") or "")
    recorded = rep.load_recorded_commands(root, r["submission"], r["task"], v)
    def is_run(k):
        c = recorded[k - 1]
        return rep.is_test_command(c.command) or (rep.tests_ran(rep.seen_output(c)) and not rep.is_listing(c.command))
    seq = sorted(states[key])
    for i in range(1, len(seq)):
        if seq[i - 1][2] != "ok":
            continue
        k = seq[i][1]
        nxt = seq[i + 1][1] if i + 1 < len(seq) else len(recorded) + 1
        tested = any(is_run(j) for j in range(k, nxt) if 1 <= j <= len(recorded))
        tab[("onset" if seq[i][2] != "ok" else "clean", "tested" if tested else "flagged")] += 1
onsets = tab[("onset", "flagged")] + tab[("onset", "tested")]
flagged = tab[("onset", "flagged")] + tab[("clean", "flagged")]
total = sum(tab.values())
print(json.dumps({"edits_on_clean_code": total, "onsets": onsets, "flagged": flagged, "flag_rate": flagged / total,
                  "precision": tab[("onset", "flagged")] / flagged, "recall": tab[("onset", "flagged")] / onsets,
                  "base_rate": onsets / total, "table": {f"{a}/{b}": n for (a, b), n in tab.items()}}, indent=1))
