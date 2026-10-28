# Planted known-answer runs

Twenty hand-written command lists, one per SWE-bench Verified task, replayed exactly like a published run. Each
plants breaks in the code, repairs some of them, and states in `expected.intervals` the breaks the labeller must find
(the command that starts each one, the command that ends it, and its kind). Two of them (django__django-13569 and
sphinx-doc__sphinx-8548) were written before the main run; the other eighteen after it, to cover every repository
and every way a break can start and end.

Files: `specs/` (the twenty command lists with their expected answers) and `score.json` (for each run, the intervals
expected and the intervals the replay found, scored with the report code behind the paper's numbers).

## Result

19 of the 20 runs are labelled exactly: every planted interval is found with the right start, end and kind, and no
interval is found where none was planted. That is 38 of the 40 planted intervals.

The two misses are both in django__django-14373. Each planted break makes `test_twelve_hour_format` fail, but that
test checks its cases as Django *subtests*. A failing subtest prints no `... FAIL` on the test's own line, so the
next test's line runs on into it:

    test_twelve_hour_format (utils_tests.test_dateformat.DateFormatTests) ... test_y_format_year_before_1000 (utils_tests.test_dateformat.DateFormatTests) ... ok
    FAIL: test_twelve_hour_format (utils_tests.test_dateformat.DateFormatTests) (hour=0)

SWE-bench's own Django log parser, which the replay uses unchanged, records neither test from such a line. The
replay counts a previously passing test that the parser does not report as *unmeasured*, never as broken, so these
two breaks are missed. In the main data such parser misses occur in 15 of the 1,557 kept runs, and 14 of those
runs already contain a counted break, so they can raise the share of runs that break a previously passing test
from 36.3% to at most 36.4% (`paper/planted_numbers.py`).

## How the specs were checked before they were run

* Task data (base commit, PASS_TO_PASS, FAIL_TO_PASS, test patch, version) comes from SWE-bench Verified. All five fields were compared with the Hugging Face rows API for
  `princeton-nlp/SWE-bench_Verified` and match for all 18 tasks.
* Every edited source file and every graded test file was read at the base commit from
  `raw.githubusercontent.com`. Each named test was read in the test file *after* the official test patch, to
  confirm it reaches the edited line and is not replaced by the patch. None of the named tests is a
  FAIL_TO_PASS test.
* **sed uniqueness.** Every forward `sed s///` pattern was run against the raw base file and matches exactly
  **1 line**. Every reverse (repair) pattern matches **0 lines** at the base and exactly 1 line in the edited
  file. Line deletes (`$ d`, `1d`, `36d`) were checked to remove exactly the planted line.
* **Simulation.** The commands were replayed on a git copy of the fetched base files. The resulting tree after each command was labelled from the markers each break
  leaves in the file. The intervals were then derived with the instrument's own rule (`break_intervals`):
  a new interval at each change of kind, the final command skipped, and a break never repaired giving
  `repair_cmd: null`. **All 18 derived results equal the `expected` blocks.** Every repair returns the tree to
  the exact base tree. The only final diffs that are not empty are the five runs with a break never repaired,
  and django__django-16819, which leaves its harmless comment in place.


## Notes on what the labeller sees

* **pytest repos** (astropy, matplotlib, xarray, pylint, pytest, scikit-learn, sphinx): if a module that a test
  file imports fails to import, pytest stops the whole run at collection. Nothing is reported, so the state is
  marked "no results for any graded test", and every PASS_TO_PASS test becomes a load break. If pytest itself
  or a conftest cannot import, the result is the same.
* **django**: if the failing module is one Django itself imports at startup (`django/db/models/aggregates.py`),
  `runtests.py` dies and nothing is reported. If only the test module fails to import (possibly the case for
  `django/core/management/utils.py`), it shows up as a `_FailedTest` and no listed test is reported. Either way
  the kind is load.
* **Every load break was traced to a module-level import on the collection path**: the test file imports the
  module directly, or the package `__init__` does at module level, or pytest loads it as a default plugin
  (`_pytest.mark`). This check caught one mistake in the first draft. A missing import in
  `xarray/core/rolling.py` would only have produced test failures, because xarray imports `rolling` lazily. That
  break now sits in `xarray/core/dataarray.py`.
* **sympy**: a test id names no group (`container_of` returns None), so a load break can only be seen when the
  run reports nothing at all. All three sympy load breaks therefore sit in a module that `import sympy` loads
  (`sympy/sets/sets.py`, `sympy/sets/contains.py`). With them, `bin/test` fails before running any test. Sympy
  test breaks are ordinary failures (`test_x F` / `E`).
* No edit touches a test file, creates a loop or a sleep, or uses the network. None of the test breaks can hang,
  and a hang would be dropped from the intervals rather than counted.


## The table

Commands are numbered from 1. "cmd k" means the command after which the state is first broken or first clean.
P2P = PASS_TO_PASS.

| Task | # | Planted break (command) | File and edit | P2P tests it breaks, and why | Expected interval | Confidence |
|---|---|---|---|---|---|---|
| astropy__astropy-12907 | 1 | behaviour, cmd 2 | `astropy/modeling/separable.py` l.167 `_arith_oper`: `result = np.ones((left_outputs, left_inputs))` -> `np.zeros(...)` | `test_arith_oper` asserts `_arith_oper(sh1, scl1) == [[1]]` and `(rot, rot) == ones`; it now gets zeros. No compound model in `test_separable` uses an arithmetic operator. | test, onset 2, repair 4 (changed to load) | high |
| | 2 | syntax error on top, cmd 4 | `printf 'def broken(:\n' >>` same file | The test file imports `astropy.modeling.separable`, so collection fails. | load, onset 4, repair 6 | high |
| | | cmd 6 `sed -i '$ d'` removes only the broken line | (break 1 still present) | `test_arith_oper` fails again | test, onset 6, repair 7 (reverse sed) | high |
| | | | | **exposure 5/9** | | |
| astropy__astropy-14182 | 1 | behaviour, cmd 2 | `astropy/io/ascii/rst.py` l.65 `RST.write`: `lines = [lines[1]] + lines + [lines[1]]` -> `lines = lines + [lines[1]]` | `test_write_normal` expects the `====` rule first; it now gets the column-name line first. The module-level `ascii.read` in `test_rst.py` only reads, so collection is unaffected. | test, onset 2, repair 4 (git checkout) | high |
| | 2 | missing import, cmd 5 | `import planted_missing_module` inserted before l.7 `from .core import DefaultSplitter` | `astropy/io/ascii/__init__.py` imports `.rst`, so `from astropy.io import ascii` fails at collection for all 9 tests. | load, onset 5, **never repaired** | high |
| | | | | **exposure 5/7** | | |
| astropy__astropy-14508 | 1 | behaviour, cmd 2 | `astropy/io/fits/card.py` l.1282 `_format_value`: `f"{repr(value)[0]:>20}"  # T or F` -> `:<20` (booleans left-aligned) | `TestHeaderFunctions::test_boolean_value_card` asserts `str(Card("abc", True)) == _pad("ABC     =                    T")`. Other header tests with boolean cards may fail too, still as test failures. The test module has no module-level cards. | test, onset 2, repair 3 (reverse sed) | high |
| | 2 | same break planted again, cmd 5 | same edit | same | test, onset 5, **never repaired** | high |
| | | | | **exposure 3/6** | | |
| django__django-11292 | – | harmless, cmd 2 | `printf '\n# planted: harmless comment\n' >> django/core/management/utils.py` | none, so **no interval** | – | high |
| | 1 | behaviour, cmd 3 | same file l.83 `get_random_secret_key`: `get_random_string(50, chars)` -> `(40, chars)` | `test_get_random_secret_key (user_commands.tests.UtilsTests)` asserts `len(key) == 50`. | test, onset 3, repair 5 (changed to load) | high |
| | 2 | syntax error on top, cmd 5 | `printf 'def broken(:\n' >>` same file | `user_commands/tests.py` imports `django.core.management.utils`. The module (or Django itself) cannot import, so none of the 31 tests is reported. | load, onset 5, repair 6 (git checkout restores everything, including the comment) | high |
| | | | | **exposure 3/7** | | |
| django__django-14373 | 1 | behaviour, cmd 2 | `django/utils/dateformat.py` l.104 `TimeFormat.g`: `return self.data.hour % 12 or 12` -> `or 0` | `test_twelve_hour_format (utils_tests.test_dateformat.DateFormatTests)` expects hours 0 and 12 to print `'12'`; they now print `'0'`. | test, onset 2, repair 3 (reverse sed) | high |
| | 2 | same break planted again, cmd 5 | same edit | same | test, onset 5, repair 7 (git checkout) | high |
| | | | | **exposure 3/8** | | |
| django__django-15375 | 1 | missing import, cmd 2 | `import planted_missing_module` inserted before l.4 of `django/db/models/aggregates.py` | `django.db.models` imports `aggregates`, so Django cannot start and none of the 95 tests runs. | load, onset 2, repair 4 (git checkout) | high |
| | 2 | behaviour, cmd 5 | same file l.131 `class Max`: `function = 'MAX'` -> `'MIN'` (the pattern exists only in `Max`) | `test_aggregate_multi_join (aggregation.tests.AggregateTestCase)` asserts `Max("books__authors__age") == 57`; MIN returns the youngest author's age (25 or 29 in the fixtures). Other Max tests fail too. | test, onset 5, **never repaired** | high |
| | | | | **exposure 5/7** | | |
| django__django-16819 | 1 | function raises at its top, cmd 2 | `django/db/migrations/optimizer.py` l.30: `if app_label is None:` -> `if app_label is not None:` (so `optimize()` raises `TypeError` on every real call) | Every `assertOptimizesTo` test errors, e.g. `test_alter_alter_field`, `test_single` ("The optimizer does nothing on a single operation,") and `test_create_delete_model` ("CreateModel and DeleteModel should collapse into nothing."). `test_none_app_label` fails because nothing is raised. `OptimizerTests` is a SimpleTestCase, so no database or migrate step reaches the optimizer. | test, onset 2, repair 4 (reverse sed) | high |
| | – | harmless, cmd 5 | `printf '\n# planted: harmless comment\n' >> django/db/migrations/operations/models.py` (left in place) | none, so **no interval** | – | high |
| | | | | **exposure 2/7** | | |
| matplotlib__matplotlib-23412 | 1 | behaviour, cmd 2 | `lib/matplotlib/patches.py` l.1178 `Wedge.__str__`: `fmt = "Wedge(center=` -> `"Wedgy(center=` | `test_patch_str` asserts `str(Wedge(...)) == 'Wedge(center=(1, 2), r=3, ...)'`. | test, onset 2, repair 3 (reverse sed) | high |
| | 2 | syntax error, cmd 5 | `printf 'def broken(:\n' >>` same file | `test_patches.py` imports `matplotlib.patches` and `pyplot`, so collection fails. | load, onset 5, **never repaired** | high |
| | | | | **exposure 4/7** | | |
| pydata__xarray-6744 | 1 | behaviour, cmd 2 | `xarray/core/rolling.py` l.125 `Rolling.__repr__`: `c="(center)"` -> `c="(centre)"` | `TestDataArrayRolling::test_rolling_repr[numpy-1]` and `[dask-1]` assert `"DataArrayRolling [time->7(center)]"`. | test, onset 2, repair 3 (changed to load) | high |
| | 2 | missing import on top, cmd 3 | `xarray/core/dataarray.py`: `import planted_missing_module` inserted before l.20 `import numpy as np` (after the `__future__` import) | `xarray/__init__.py` imports `DataArray` at module level, so `import xarray` fails and collection and the conftest fail. (The import is deliberately not in `rolling.py`: xarray imports `rolling` only inside `DataArray.rolling()`, so an import error there would show as test failures, not a load break.) | load, onset 3, repair 5 (one git checkout of both files) | high |
| | | | | **exposure 3/6** | | |
| pylint-dev__pylint-7080 | 1 | behaviour, cmd 2 | `pylint/lint/run.py` l.122: `print(full_version)` -> `print("planted")` | `TestRunTC::test_version` asserts that the first line of `--version` starts with `"pylint "`. | test, onset 2, repair 3 (git checkout) | high |
| | 2 | syntax error, cmd 4 | `printf 'def broken(:\n' >>` same file | `tests/conftest.py` and `test_self.py` import `pylint.lint` (`Run`), so nothing runs. | load, onset 4, repair 5 (git checkout) | high |
| | 3 | behaviour, cmd 6 | same file l.218: `if linter.config.exit_zero:` -> `if not linter.config.exit_zero:` | `TestRunTC::test_exit_zero` (expects 0, now gets the error status) and `TestRunTC::test_no_out_encoding` (expects 28, now gets 0). Many other exit-code tests fail too. | test, onset 6, **never repaired** | high |
| | | | | **exposure 5/8** | | |
| pytest-dev__pytest-7324 | 1 | syntax error, cmd 2 | `printf 'def broken(:\n' >> src/_pytest/mark/expression.py` | `_pytest.mark` imports `expression`, so pytest itself cannot start and nothing is reported. | load, onset 2, repair 3 (`sed -i '$ d'`, which removes exactly that line) | high |
| | 2 | behaviour, cmd 5 | same file l.132: `ret = ast.NameConstant(False)` -> `(True)` (an empty expression now evaluates True) | `test_empty_is_false` asserts `not evaluate("", ...)`. The outer pytest run passes no `-k`/`-m`, so it never compiles an expression. | test, onset 5, repair 6 (git checkout) | high |
| | | | | **exposure 2/7** | | |
| scikit-learn__scikit-learn-14629 | 1 | function raises at its top, cmd 2 | `sklearn/multioutput.py` l.35: `    raise RuntimeError("planted")` inserted as the first line of `_fit_estimator` | Every `MultiOutput*.fit` raises, so `test_multi_target_regression`, `test_multi_output_classification`, `test_multi_output_exceptions` and others fail. Module-level code in the test only loads iris. | test, onset 2, repair 4 (`sed -i '36d'` deletes exactly the inserted line) | high |
| | | | | **exposure 2/6** | | |
| scikit-learn__scikit-learn-25931 | 1 | behaviour, cmd 2 | `sklearn/ensemble/_iforest.py` l.551: `average_path_length[mask_2] = 1.0` -> `2.0` | `test_iforest_average_path_length` asserts `_average_path_length([2]) == [1.0]`. | test, onset 2, repair 3 (reverse sed) | high |
| | 2 | missing import, cmd 4 | `import planted_missing_module` inserted after l.9 `from numbers import Integral, Real` | `from sklearn.ensemble import IsolationForest` fails at collection. | load, onset 4, repair 6 (git checkout) | high |
| | | | | **exposure 3/7** | | |
| sphinx-doc__sphinx-7440 | 1 | behaviour, cmd 2 | `sphinx/domains/std.py` l.429 `Glossary.run`: `if 'sorted' in self.options:` -> `if 'sorted' not in self.options:` | `test_glossary_sorted` expects the `:sorted:` glossary in the order term2/term1, then term3; it now stays in document order. | test, onset 2, repair 3 (git checkout) | high |
| | – | harmless, cmd 4 (reverted at cmd 5) | `printf '\n# planted: harmless comment\n' >>` same file | none, so **no interval** | – | high |
| | 2 | same break planted again, cmd 6 | same edit | same | test, onset 6, repair 7 (changed to load) | high |
| | 3 | syntax error on top, cmd 7 | `printf 'def broken(:\n' >>` same file | `test_domain_std.py` imports `StandardDomain`, so collection fails. | load, onset 7, repair 8 (git checkout restores both) | high |
| | | | | **exposure 3/9** | | |
| sphinx-doc__sphinx-9698 | 1 | behaviour, cmd 2 | `sphinx/domains/python.py` l.1428 `get_full_qualified_name`: `[modname, clsname, target]` -> `[clsname, modname, target]` | `test_get_full_qualified_name` asserts `'module1.Class.func'`; it now gets `'Class.module1.func'`. | test, onset 2, repair 3 (reverse sed) | high |
| | – | harmless blank line, cmd 4 (reverted at cmd 5) | `printf '\n' >>` same file | none, so **no interval** | – | high |
| | 2 | missing import, cmd 6 | `import planted_missing_module` inserted before l.11 `import builtins` | `test_domain_py.py` imports `sphinx.domains.python`, so collection fails. | load, onset 6, repair 8 (git checkout) | high |
| | | | | **exposure 3/9** | | |
| sympy__sympy-12489 | 1 | behaviour, cmd 2 | `sympy/combinatorics/permutations.py` l.2705 `josephus`: `while len(Q) > max(s, 1):` -> `max(s, 2)` | `test_josephus`: `josephus(4, 6, 1)` now gives `[3,1,0,2,4,5]`, not `[3,1,0,2,5,4]`. The call in `test_Permutation` uses s=2, so it is unchanged. | test, onset 2 ... | high |
| | 2 | second behaviour break that overlaps the first, cmd 4 | same file l.1502 `from_sequence`: `return ~Permutation(` -> `return Permutation(` | `test_from_sequence`: `'SymPy'` now gives the cycle (0 3 1), not (0 1 3). | ... stays broken; break 1 is reverse-sed repaired at cmd 5 while break 2 remains, so this is **one** interval: test, onset 2, repair 6 (git checkout) | high |
| | | | | **exposure 4/7** | | |
| sympy__sympy-20438 | 1 | syntax error, cmd 2 | `printf 'def broken(:\n' >> sympy/sets/sets.py` | `import sympy` fails (sympy imports `sympy.sets`), so `bin/test` reports nothing. | load, onset 2, repair 4 (changed to test) | high |
| | 2 | behaviour, cmd 3, under the syntax error | same file l.1099 `Interval._measure`: `return self.end - self.start` -> `return self.start - self.end` | `test_measure` asserts `Interval(1, 3).measure == 2`. It stays hidden by the load break until cmd 4. | (state stays load) | high |
| | | cmd 4 `sed -i '$ d'` removes the syntax error | | `test_measure` fails | test, onset 4, repair 6 (git checkout) | high |
| | | | | **exposure 4/7** | | |
| sympy__sympy-23950 | 1 | behaviour, cmd 2 | `sympy/sets/contains.py` l.33 `Contains.eval`: `raise TypeError('expecting Set` -> `raise ValueError('expecting Set` | `test_contains_basic`: `raises(TypeError, lambda: Contains(S.Integers, 1))`; the ValueError escapes sympy's `raises`, so the test errors. | test, onset 2, repair 3 (changed to load) | high |
| | 2 | missing import on top, cmd 3 | `import planted_missing_module` inserted before l.1 `from sympy.core import S` | `sympy/sets/__init__.py` imports `.contains`, so `import sympy` fails and nothing is reported. | load, onset 3, repair 5 (`sed -i '1d'` deletes the import line) | high |
| | | cmd 5: back to break 1 alone | | `test_contains_basic` fails | test, onset 5, repair 6 (git checkout) | high |
| | | | | **exposure 4/7** | | |


## Coverage

| Requirement | Required | Planted | Where |
|---|---|---|---|
| Test breaks from a behaviour change in code that named P2P tests call | >= 6 | 20 distinct (23 plantings) | every run; named tests in the table |
| Load breaks from a syntax error | >= 4 | 7 | 12907, 11292, 23412, 7080, 7324, 7440, 20438 |
| Load breaks from importing a module that does not exist | >= 2 | 6 | 14182, 15375, 6744, 25931, 9698, 23950 |
| Kind changes | >= 2 | 6 runs | test -> syntax load -> repair: 12907 (and back to test), 11292, 7440; test -> import load: 6744, 23950 (and back to test); load -> test: 20438 |
| Breaks never repaired (`repair_cmd: null`) | >= 2 | 5 | 14182 (load), 14508 (test), 15375 (test), 23412 (load), 7080 (test) |
| Repairs by a second sed, not git checkout | >= 2 | 10 | reverse `s///`: 12907, 14373, 14508, 16819, 23412, 25931, 9698, 12489 (partial); line delete: 7324 (`$ d`), 14629 (`36d`); and the partial repairs 12907 (`$ d`), 20438 (`$ d`), 23950 (`1d`) |
| Runs with a harmless edit that must give no interval | >= 2 | 4 | 11292, 16819 (comment), 7440 (comment), 9698 (blank line) |
| A break repaired, then the same break planted again | >= 1 | 3 | 14373, 7440, 14508 (the second time never repaired) |
| Read-only commands between edits | yes | every run | `ls`, `grep -n`, `head`, `tail`, `sed -n`, `cat \| head`, `git status`, `git diff --stat` |

Totals: 36 break plantings, giving 37 expected intervals over 18 runs and 131 commands (the final commands
included). The 36 plantings are 23 behaviour breaks (20 distinct edits, 3 of them planted a second time),
7 syntax errors and 6 missing imports.
