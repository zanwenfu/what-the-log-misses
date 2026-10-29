# Details

The files, definitions and scripts behind "What the Log Misses". The overview is in [README.md](README.md).

The published runs themselves are not copied here. They are public on the SWE-bench leaderboards (bash-only Verified
and Multilingual), with trajectories under `s3://swe-bench-submissions/...`, readable over anonymous HTTPS and linked
from `github.com/SWE-bench/experiments`. The replay code fetches them.

## Layout

| Path | What it holds |
|---|---|
| `data/verified/cells.csv` | One row per published Verified run (1,635 replayed; `main=True` marks the 1,557 kept): fidelity tier, exit-status agreement, exposure, breaks, end state, grades, fix-test counts |
| `data/verified/states.csv` | One row per tested snapshot: the command after which it was taken, and its status: `ok` (every previously passing test passes), `broken` (one fails, or a group cannot load) or `hang` (the test run did not finish) |
| `data/verified/intervals.csv` | One row per break (1,237 rows; the 1,192 breaks of kept runs have `main=True`): onset and repair command, kind (test/load), how it ended, the seen/unseen verdict and its parts (`ran_tests`, `saw_failure`, `named`), and the number of the break's own error lines (`evidence_lines`; the lines themselves are not in this release) |
| `data/verified/models.csv` | Per model: exposure, leaderboard resolve rate, run counts (Fig. 2) |
| `data/verified/summary.json` | The report's aggregate numbers and checks (replay fidelity, planted breaks, second replay) |
| `data/verified/extras_machine.json`, `recompute-final4.json` | Checks computed on the replay machine: file-print and search-output agreement with the originals (99.3%), and the second implementation's independent recount of every break. The code that computed them is not in this release |
| `data/verified/baseline_onset.json`, `baseline_rule.json` | The naive baseline (flag every edit not followed by a test run), on the onset footing used in RQ4 |
| `data/verified/judge_summary*.json` | Step-level judges: `judge_summary3.json` is Table III (four readers on 288 common commands); `judge_summary_full.json` is the whole-run judges |
| `data/verified/humancheck.json`, `audit.json` | The 40-card human check of the seen/unseen rule (two labellers) and the earlier LLM audit |
| `data/verified/fileclause_ver_nowarn.json` | Multilingual's extra seen condition applied to Verified as a robustness check (55% -> 52%) |
| `data/multilingual/` | The same tables for SWE-bench Multilingual (266 kept of 292 replayed runs, 150 breaks), the task draw (`task_draw.json`), the leaderboard's own test scripts per task (`scripts/`), the check of our parsers against every published test log (`official_check.json`), the loose-rule bound (`liberal.json`), the 20-break human check (`humancheck_ml.json`, `humancheck_ml2.json`), and the extra-condition correction: `fileclause_ml.json` lists every break it changed, `error_bound.json` gives looser bounds, and `before_file_clause_*` are the tables under the Verified rule alone |
| `judge/` | Step-level judge study: `judge2.py` (the exact prompt is the `SYSTEM` string; `--model sonnet|opus|deepseek`, `--examples` for the four labelled examples in `examples.json`), the sampled commands (`sample.json`, `sample2.json`), every judge's raw answers (`results*.jsonl`), `analyse3.py` (Table III), and `without_claude_agents.py` (the check that leaves out runs by Claude agents) |
| `judge/whole_run/` | Whole-run judge study: `sample_full.py` (150 random kept runs, seeded), `judge_full.py` (prompt and calls), both judges' raw answers (`full_sonnet.jsonl`, `full_opus.jsonl`), `analyse_full.py` (precision measured directly on every edit) |
| `humancheck/` | Verified: the 40 blind cards (`label-check.html`), the key (`key.json`), the two labellers' labels (`labels_author.txt`, `labels_second.txt`; the second labeller, not an author, labelled the 40 cards alone, without seeing the author's answers or the rule's labels, and the two answer lines are identical), `score.py`. Multilingual: the first 20 cards (`label-check-multilingual.html`, `key_multilingual.json`), the 10 rebuilt cards with fuller excerpts (`relabel-10-cards.html`, `key_relabel_10.json`, `labels_author_relabel_10.txt`), the 20-card sheet with the rule stated in plain words at the top (`label-check-multilingual-v2-20-cards.html`, `key_multilingual_v2_20.json`, the author's labels under that rule in `labels_author_v2_20.txt`, recorded for completeness; the paper reports the earlier round, and all rounds are in `data/multilingual/humancheck_ml.json`), the card builders (`make_cards*.py`) and `score_ml2.py`. `make_cards_end.py` builds a further 30 blind cards of breaks that runs end on (20 unseen, 10 seen), for a check after this version |
| `data/verified/planted/` | The 20 planted known-answer runs (`specs/`), what the replay found for each (`score.json`), and how the specs were built and checked (`README.md`) |
| `data/verified/reproducibility-366.txt` | The second replay: 366 runs replayed twice, compared state by state (`code/scripts/compare_runs.py`); the only differences are a submission-match flag fixed before the final run and one sympy test that flips on code already broken |
| `paper/` | The scripts that turn these tables into every number in the paper (`paper_numbers.py`, `ml_numbers.py`, `review_numbers.py`, `baseline_onset.py`, and `planted_numbers.py`, `review2_numbers.py`, `review3_numbers.py`, `review4_numbers.py`, and `extra_numbers.py`, which first checks that it recomputes 63 of the paper's numbers exactly) and their output (`numbers*.tex`); `paper/figures/` holds both figure scripts, the Fig. 1 data and the PDFs; `paper/corrections/` holds the Multilingual extra-condition scripts |
| `data/verified/leaderboard_meta.csv` | Each entry's own averages over all 500 tasks (model calls and dollars per task, reasoning setting), read from its `metadata.yaml` in `github.com/SWE-bench/experiments` |
| `data/verified/log_signs_runs.csv`, `log_signs_breaks.csv` | What the published logs show of scaffold 2.0.0's shell, which ran commands outside the project's Python environment: per run, whether any output shows the image's base Python, says "No module named", or whether any command runs `pip install`; per break, whether the base Python shows before it (made by `code/scripts/log_signs.py` from the published trajectories) |
| `data/multilingual/log_signs_runs.csv` | Per kept Multilingual run: the shell the scaffold used and whether any output says the language's toolchain was not found (made by `code/scripts/log_signs_ml.py` from the published trajectories) |
| `data/verified/edit_methods.csv` | Per entry and edit method (`sed -i`, a Python script, a heredoc or redirect, git, other): edits on clean code and the breaks they start (made by `code/scripts/log_signs.py`) |
| `data/verified/instructions_check.json` | What the scaffold's standard instructions say about testing, for one published run of each of the 41 Verified and 13 Multilingual entries (`instructions_pairs.txt`; made by `code/scripts/check_instructions.py`): every entry suggests reproducing the issue with the agent's own script and rerunning it to verify the fix, and none asks for the repository's existing tests |
| `code/` | The replay and labelling code (`code/replaykit/benchmarks/public_replay.py`, `swebench_multilingual.py`, `swebench_log_multilingual.py`, `public_trajectories.py`, `code/scripts/public_replay.py`, `code/scripts/public_replay_report.py`, plus the modules they import) with its tests |

## Definitions (as in the paper)

- *Previously passing test*: a SWE-bench PASS_TO_PASS test that also passes on the run's starting code in the replay.
- *Fix tests*: the tests a fix must make pass (FAIL_TO_PASS).
- A command *breaks* the code (a regression) if, after it, a previously passing test fails or a group of them can no
  longer load. A break lasts until every such test passes again; if the failing group changes kind, a new break begins.
  "Outlasts the next edit": not repaired by the agent's very next command that changes the code.
- *Seen*: in the log as the model saw it (first and last 5,000 characters of each output), between the break's onset
  and its end, a test run reported a failure, or an output named a broken test or printed the break's own error.
  Otherwise *unseen*. On Multilingual, an error line that points at a file the breaking command edited also counts as
  seen (see below).
- *Exposure*: the share of a run's commands after which its code is broken; an entry's exposure is the mean over its runs.

## Reproducing the numbers

`bash reproduce.sh` (Python 3.11 or newer, standard library only) rebuilds every numbers file into `out/` and compares
each with the copy the paper was built from, in about 15 seconds. It also rescores the human check.

The figures need matplotlib and are written to the current folder:

```
python3 paper/figures/fig_models.py data/verified/models.csv --cells=data/verified/cells.csv \
  20250802_mini-v1.0.0_qwen3-coder-480b-a35b-instruct 20250726_mini-v1.0.0_gemini-2.5-pro \
  20260217_mini-v2.0.0_deepseek-3-2-high 20260217_mini-v2.0.0_gpt-5-2-high
python3 paper/figures/fig_timeline.py paper/figures/timeline_data.json
```

Comments in the scripts and in `numbers*.tex` keep an earlier draft's label "Table II" for what the paper now
prints as Table III (the judges).

Not every number in `paper/numbers*.tex` appears in the paper: the files define 836 macros and the paper uses
242, listed in `paper/USED_MACROS.txt`. The others are kept for the record, and a few measure something close to
a number in the paper but not the same thing:
- `\Shipped` (12.5%) is the share of runs *that submitted a patch* whose patch is broken; the paper's 12.3%
  (`\EndBrokenRunsShare`) is the share of *all kept runs* whose final code is broken.
- `\RulePrecision` (30%) scores the log-only baseline against every edit after which the code is broken (3,763 of
  13,608 edits); the paper's 11% (`\RvBaselinePrecision`) scores it against the edits that *start* a break on clean code
  (992 of 10,037), the question the judges answer in RQ4.
- `\RvJSPrecCI` and `\RvJOPrecCI` vary only the judges' false-alarm rate; the paper's intervals (`\XtJSPrecCI`,
  `\XtJOPrecCI`, from `extra_numbers.py`) vary all three rates.

## Scripts that need more than this package

- Replaying runs needs Docker (`pip install ./code[replay]`), the SWE-bench images and the published trajectories:
`python3 code/scripts/public_replay.py pool --root <root> --cells <cells file>`, then
`python3 code/scripts/public_replay_report.py --root <root>`. A replay root for Multilingual holds `multilingual.jsonl`
  (the dataset) and `scripts/<task>.sh` (the leaderboard's test scripts). The root's submission list, task list and
  per-task details come from the leaderboard repository and the SWE-bench dataset and are not copied here.
- `code/scripts/log_signs.py` and `log_signs_ml.py` read the published runs from a folder of downloaded trajectories
  (`<submission>/<task>.traj.json`), and checks each run's command count against `cells.csv` first.
- The card builders (`humancheck/make_cards*.py`) and `paper/corrections/*.py` read the published runs from a local
  folder of downloaded trajectories; pass the scratch folder and `code/` as their arguments (each script's first lines
  say which).
- `judge/judge2.py` and `judge/whole_run/judge_full.py` call paid models on Amazon Bedrock (key in
  `AWS_BEARER_TOKEN_BEDROCK`); `--prompts-only` writes the prompts without any call. Their recorded answers are in
  `judge/`, so nothing here needs to call them again.
- The replay's wall time and compute cost in the paper (8.2 hours, about $15) are taken from the replay machine's log,
  which is not in this release.

## Multilingual: the extra seen condition

The Multilingual replay kept each test's pass or fail from the leaderboard's own log parsers but, for two thirds of
the breaks, not the error text, so the rule's "printed the break's own error" clause had nothing to match there. The
paper's Multilingual numbers therefore add one condition: an output line that reports an error and points at a source
file the breaking command edited (on that line or in the stack-trace lines around it) shows the break. It turns 18 of
116 unseen breaks into seen ones (77% -> 65%). `data/multilingual/` holds the corrected tables; `before_file_clause_*`
are the tables under the Verified rule alone; `fileclause_ml.json` lists every changed break with the line that changed
it; `error_bound.json` gives looser bounds (any error line at all: 47%). On Verified, where every break's error text
was recorded, the paper keeps the exact match; the same condition there would give 52% (`data/verified/fileclause_ver_nowarn.json`),
partly by counting errors the original bug itself prints. The scripts are in `paper/corrections/`.

## Whole-run judges

`judge/whole_run/`: Claude Sonnet 5.5 and Opus 5.5 read the complete log of each of 150 random kept Verified runs
(`sample_full.json`, seeded; two runs hosted outside the bucket were redrawn) and say, for every command that changed
the code, whether the repository was broken right after it. `analyse_full.py` scores them on all 848 edits made on
clean code (67 start a break): precision measured directly, with a bootstrap over runs. Results in
`data/verified/judge_summary_full.json`. Command 0 in the sample is the starting snapshot, not an edit, and is not
scored. Three runs with many edits were asked again with a larger output limit after the first answer ran out.

## Licence

Code: Apache-2.0 (`LICENSE`). Labels and tables: CC BY 4.0 (`LICENSE-DATA`). The SWE-bench log parsers, test
specifications and per-task test scripts included here are SWE-bench's, under the MIT licence
(`LICENSES/SWE-bench-MIT.txt`; see `NOTICE`). The published runs belong to their submitters and are not redistributed,
except for the short excerpts the human-check cards, the judge files and `extras_machine.json` need.
