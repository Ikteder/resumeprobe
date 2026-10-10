# ResumeProbe 0.1 Verification

Date: 2026-10-09. Manual user-authorized continuation. Seed 20261009.

## Environment and commands

Windows, Python 3.14.7, ResumeProbe 0.1.0, LangGraph 1.2.14, SQLite saver 3.1.1.

```
python -m pytest -q
python -m ruff check src tests
python -m compileall -q src tests
python -m pip check
python -m pip_audit
python -m build
python -m resumeprobe run --adapters reference langgraph --seed 20261009 --repetitions 3 --output artifacts/matrix-final
```

55 tests passed in 45.27 seconds after narrowing the task-result trace hook to the pinned
Functional API's `__return__` channel. Prior 55-test verification passed in 38.86 seconds.
Ruff passed after formatting and splitting one long SVG label. Compilation
and dependency consistency passed. Vulnerability audit found no known dependency
vulnerabilities; the unpublished local package was skipped. CacheControl emitted cache
deserialization warnings and refreshed affected cache entries. Source and wheel built.

## Actual experiment results

Ninety cases = two adapters x three tool modes x five boundaries x three repetitions.
Final matrix duration 106,922.924 ms, including fresh Python process and framework import costs.
This is experiment wall time, not model or tool latency.

| Measure | Result |
|---|---:|
| Expected outcomes matched | 90/90 |
| Safe effect contracts | 78 |
| Duplicate-effect contracts | 12 |
| Inconclusive | 0 |
| Completion-only false-safe outcomes | 12 |

At after-effect, naive and per-attempt-key modes committed `2,2,2` effects for both
adapters. Stable keys committed `1,1,1`. All other tested cells committed one effect.
No worker stderr was captured in the successful matrix. Tests also verified concurrent
stable-key transactions, conflicting payload rejection, missing effects, corrupted
result identity, unreached crashes, non-crash exits, timeouts, and output preservation.

## Visual checks

HTML rendered six metrics, thirty matrix rows, and ninety expandable traces. Desktop
document clientWidth and scrollWidth both 1265 px. Requested 390x844 viewport produced
375 px clientWidth and scrollWidth; the table scrolled inside its 342 px container while
its content measured 860 px. Captured browser warnings/errors: zero. SVG verification
confirmed the comparison's counts and labels. The exported JSON passes a fresh independent
verdict recomputation. A clean no-dependency wheel install ran all fifteen reference cases:
thirteen safe, two deliberately unsafe, zero inconclusive, fifteen expected matches.

## Interpretation

Completion-only missed all twelve observed duplicate contracts. This is measured
evidence about these authored cases, not a general classifier comparison or framework
ranking. A stable key only worked because the local sink atomically bound it to an
immutable payload and effect. No paid provider was called; actual cost USD 0.00.

## Boundaries

No remote service, distributed store, machine power loss, live model, independently
authored corpus, or LangGraph 8039 scheduler-race reproduction is claimed. The saved Git
credential lacks workflow scope; the configured GitHub connector subsequently published
the reviewed workflow without changing that credential. Source commit
`def3d9e4f369f8361bcc0c6251f07d81d2c75eaa` and CI commit
`3784f9e12ab30f2965ae313e335e281aa8643358` are public at
https://github.com/Ikteder/resumeprobe. Run 38013469173 passed all six Ubuntu/Windows
Python 3.11/3.12/3.14 jobs, including lint, tests, a 30-case matrix, and packaging.
