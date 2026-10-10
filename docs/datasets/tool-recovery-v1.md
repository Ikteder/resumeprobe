# Tool Recovery v1 Dataset Card

Created and accessed: 2026-10-09. License: MIT, repository-authored fixtures.

The dataset is an executable Cartesian matrix: two adapters, three tool identity modes,
five crash boundaries, and three repetitions. Ninety cases run in actual worker processes.
Seed 20261009 binds deterministic operation IDs and synthetic payloads. Process IDs,
elapsed times, and platform metadata are measured and nondeterministic.

One action publishes a synthetic receipt into a local SQLite sink. It contains the seed
and a hashed operation ID, no user data, model output, third-party text, or real transaction.
Expected safe: every stable-key case and every other-mode case outside after-effect.
Expected unsafe: naive/per-attempt-key after-effect cells. Expected counts are declared
before execution; audit verdicts are computed independently from observed effects.

Raw machine evidence is `artifacts/matrix-v1/report.json` locally; ignored SQLite files
remain under case directories. A compact portable summary is committed under experiments.
There is no training, split, or learned model. The corpus is authored against known effect
invariants, not independent production evaluation. Three repetitions establish repeatability
on this host, not a rare-failure probability or statistical reliability bound.

Leakage boundary: all cases are public and implementation-aligned. Do not use them as an
unseen benchmark or claim superiority over the reference orchestration systems. Their own
documented idempotency boundaries motivate the experiment rather than serving as competitors.
