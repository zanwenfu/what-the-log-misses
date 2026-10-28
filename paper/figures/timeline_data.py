import csv, json, sys, importlib.util, pathlib
code, root, report = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, code)
spec = importlib.util.spec_from_file_location("rep", f"{code}/scripts/public_replay_report.py")
rep = importlib.util.module_from_spec(spec); sys.modules["rep"] = rep; spec.loader.exec_module(rep)
csv.field_size_limit(sys.maxsize)
subs = json.load(open(f"{root}/submissions.json"))
out = {}
for s in sys.argv[4:]:
    t = "django__django-11490"
    meta = subs.get(s, {}); v = str(meta.get("version") or meta.get("mini_version") or meta.get("mini-swe-agent_version") or "")
    recorded = rep.load_recorded_commands(pathlib.Path(root), s, t, v)
    states = [(int(r["command"]), r["status"]) for r in csv.DictReader(open(f"{report}/states.csv")) if r["submission"] == s and r["task"] == t]
    cmds = []
    for k, c in enumerate(recorded, 1):
        run = rep.is_test_command(c.command) or (rep.tests_ran(rep.seen_output(c)) and not rep.is_listing(c.command))
        cmds.append({"k": k, "test_run": bool(run), "failure": bool(run and rep.shows_failure(c.returncode, rep.seen_output(c))),
                     "cmd": c.command[:90]})
    out[s] = {"commands": cmds, "states": states}
print(json.dumps(out))
