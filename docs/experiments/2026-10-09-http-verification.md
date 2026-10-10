# ResumeProbe 0.2 verification

Date 2026-10-09. Seed 20261009, Windows, Python 3.14.7, ResumeProbe 0.2.0.
No provider/model calls. Actual paid cost USD 0.00.

## Commands and outcomes

```
python -m pytest -q
python -m ruff check src tests scripts
python -m compileall -q src tests
python -m pip check
python -m build
python -m resumeprobe http-run --seed 20261009 --repetitions 3 --output artifacts/http-v1
python scripts/export_evidence.py --http artifacts/http-v1/report.json --json docs/experiments/http-replay-v1.json --svg docs/assets/http-replay-v1.svg
```

Full corrected suite: 94 passed in 42.83 seconds. Focused HTTP and adversarial evidence
suite: 39 passed in 6.24 seconds. Ruff, compilation, pip consistency passed. Final matrix
ran in 7688.631 ms, including subprocess startup and local HTTP, not production latency.

| Measure | Outcome |
|---|---:|
| Declared cases | 15 |
| Expected matches | 15 |
| Safe effect contracts | 6 |
| Duplicate-effect contracts | 9 |
| Inconclusive | 0 |
| Completion-only false safe | 9 |

No-key, per-attempt-key, and explicitly pruned-key cells observed effects `2,2,2` each.
Stable retained keys observed `1,1,1`. Changed payload observed `1,1,1` with HTTP `409`
each. A safe conflict is not successful workflow completion. First clients recorded real
transport errors, server and both client PIDs differed, and commit preceded dropped response.

Auditors independently recomputed both saved reports, validated complete declared suite
membership, verified request-key and result identity, and rejected altered evidence.
SVG XML and exact regeneration equality passed. README contains no em dash.

## Browser QA

HTTP HTML: five matrix rows and fifteen expandable traces. Desktop document client and
scroll widths 1265 px each; narrow requested 390x844 produced 375 px document client and
scroll widths, with an internally scrolling 335 px table container. No page overflow.
Fresh QA tab warning/error logs were empty. A reused tab retained one older host/runtime
error from before HTTP navigation; it was not attributed to this script-free report.
Pruned-key trace showed committed effect 1, dropped response, explicit key deletion,
retry, committed effect 2, and successful response. SVG screenshot verified all actual
count labels and bars. No decorative or external image data used.

## Known limits

Synthetic pruning, sequential supervisor, serialized local server effects, unsigned
evidence, no SDK retry rules, no provider calls, no server death or distributed transaction.
Malformed framing may produce a socket reset instead of an HTTP error because unconsumed
bytes are not drained without bounds. No effect is the required safety invariant.

Source and wheel built successfully. A clean wheel installation with no dependencies
matched all five HTTP cases (two safe, three deliberately unsafe) and all fifteen reference
cases (thirteen safe, two deliberately unsafe), with no inconclusive outcomes. Dependency
consistency passed. Final commit and 0.2 public CI are recorded after publication;
the earlier six-job CI passed the published 0.1 code. Version 0.2 source `e41777c`, workflow
`fda494e`, and merge `6e5fd64d9dd6ad46d9dc5f40904fb58c13b6f3c6` are public.
Run https://github.com/Ikteder/resumeprobe/actions/runs/38014252072 passed all six
Ubuntu/Windows Python 3.11/3.12/3.14 jobs, including the new HTTP matrix. A workflow-only
run started before the source push was canceled and is not passing evidence. No history
was force-pushed or rewritten. Vulnerability audit found no known dependency issues;
the unpublished local package itself was skipped by the PyPI audit.
