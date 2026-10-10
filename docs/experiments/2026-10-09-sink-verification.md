# ResumeProbe 0.3 sink verification

2026-10-09, seed 20261009, Windows Python 3.14.7, SQLite 3.50.4, ResumeProbe 0.3.0.
LangGraph and SQLite saver remain pinned 1.2.14/3.1.1 for the original workflow suite.
No model/provider called. Actual paid cost USD 0.00.

```
python -m pytest -q
python -m ruff check src tests scripts
python -m compileall -q src tests
python -m pip check
python -m resumeprobe sink-run --seed 20261009 --repetitions 3 --output artifacts/sink-final
python scripts/export_evidence.py --sink artifacts/sink-final/report.json --json docs/experiments/sink-atomicity-v1.json --svg docs/assets/sink-atomicity-v1.svg
```

Full suite 113 passed in 46.64 seconds; focused sink plus existing sink 23 passed in 4.53 seconds.
Ruff, compilation, dependency consistency passed. Final 12-case matrix ran in 10095.461 ms;
initial matrix 3191.446 ms. These include process startup, instrumentation and filesystem
work; no throughput or performance advantage is claimed from this small variation.

| Boundary | Pre-resume effects / keys | Final effects per repetition | Status |
|---|---|---|---|
| before-key | 0 / 0 | 1,1,1 | safe |
| after-key | 0 / 0 | 1,1,1 | safe |
| after-commit | 1 / 1 | 1,1,1 | safe |
| split-commit, intentionally broken | 1 / 0 | 2,2,2 | unsafe |

12/12 expected matches, 9 safe, 3 duplicate, 0 inconclusive, 3 completion-only false safe.
First workers exited 86 and fresh workers 0. Independent control receipts, before/after
snapshots, operation/payload/key binding, and final result identities reconciled. Missing
cases, corrupt results, pre-resume key/count edits, boundary/PID/sequence edits, boolean exit
codes, malformed reports, timeouts and existing-output tests passed. Connections explicitly
closed after commit and conflict rollback with no ResourceWarning in the lifecycle test.

Desktop HTML: document client/scroll 1265 px and 12 expandable traces. Narrow requested 390x844
on selected tab: client/scroll 375 px. No overflow. SVG screenshot showed actual counts and
the explicit baseline warning. A reused browser tab retained an earlier host animation
error from before this report; the report has no scripts. No zero-error claim is made
for that reused tab. SVG XML and deterministic regeneration are checked during publication.

An attempted no-isolation build found no setuptools in the new Python virtual environment.
This is a build-environment setup issue, not a test pass or runtime failure. Install the
declared build tools in that isolated project environment before the final build and
clean-wheel checks. Installing setuptools 84.0.0 and wheel 0.48.0 resolved it. Source and
wheel then built successfully. Clean no-dependency wheel install matched all four sink
cases (three safe, one deliberately unsafe) and all five HTTP cases (two safe, three
deliberately unsafe), with zero inconclusive outcomes. Pip consistency, SVG XML, exact
regeneration, README style, and Git whitespace passed. Public CI recorded after publication.

No sudden power loss, damaged journal, VFS faults, server cluster, remote transactional
resource, independently authored dataset, or distributed exactly-once guarantee tested.
