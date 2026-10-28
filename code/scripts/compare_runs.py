"""Compare two replays of the same cells (the pilot and the full run): does the replay reproduce itself?

    python3 compare_runs.py /data/pubreplay/cells-pilot /data/pubreplay/cells

For every (submission, task) finished in both: the same commands changed the tree (the step ids of the
observations), each observed state tested with the same failing / unreported / skipped tests, and the same
submission verdict. Prints totals and every difference.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load(directory: Path):
    status = json.loads((directory / "status.json").read_text())
    if status.get("state") != "done":
        return None
    manifest = json.loads((directory / "manifest.json").read_text())
    session = manifest["session"]
    shadow = [json.loads(x) for x in (directory / "shadow.jsonl").read_text().splitlines() if x.strip()]
    shadow = sorted((s for s in shadow if s.get("session") == session), key=lambda s: s["seq"])
    states = {}
    for line in (directory / "states.jsonl").read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            states.setdefault(record["sha"], record)
    sequence = []
    for s in shadow:
        record = states.get(s["sha"], {})
        sequence.append((s["step_id"], record.get("ran"), record.get("infra_error"),
                         tuple(sorted(record.get("failed", []))), tuple(sorted(record.get("unreported", []))),
                         tuple(sorted(record.get("skipped", [])))))
    fidelity = json.loads((directory / "fidelity.json").read_text())
    return {"sequence": sequence, "same": fidelity.get("same_submission"), "resolved": fidelity.get("replay_resolved"),
            "commands": manifest.get("commands_replayed")}


def main() -> int:
    a_root, b_root = Path(sys.argv[1]), Path(sys.argv[2])
    compared = identical = 0
    differences = []
    for status in sorted(a_root.glob("*/*/status.json")):
        cell = status.parent
        submission, task = cell.parent.name, cell.name
        if submission == "planted":
            continue
        other = b_root / submission / task
        if not (other / "status.json").exists():
            continue
        a, b = load(cell), load(other)
        if a is None or b is None:
            continue
        compared += 1
        if a == b:
            identical += 1
            continue
        why = []
        if a["commands"] != b["commands"]:
            why.append(f"commands {a['commands']} vs {b['commands']}")
        if [s[0] for s in a["sequence"]] != [s[0] for s in b["sequence"]]:
            why.append(f"observed steps differ: {[s[0] for s in a['sequence']][:12]} vs {[s[0] for s in b['sequence']][:12]}")
        else:
            for x, y in zip(a["sequence"], b["sequence"]):
                if x != y:
                    why.append(f"state {x[0]}: failed {len(x[3])}->{len(y[3])} unreported {len(x[4])}->{len(y[4])} "
                               f"skipped {len(x[5])}->{len(y[5])} infra {x[2]}->{y[2]}")
        if a["same"] != b["same"]:
            why.append(f"same_submission {a['same']} vs {b['same']}")
        if a["resolved"] != b["resolved"]:
            why.append(f"resolved {a['resolved']} vs {b['resolved']}")
        differences.append((submission, task, why))
    print(f"compared {compared} cells finished in both; identical {identical}; different {len(differences)}")
    for submission, task, why in differences:
        print(f"  {submission} {task}")
        for line in why[:6]:
            print(f"      {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
