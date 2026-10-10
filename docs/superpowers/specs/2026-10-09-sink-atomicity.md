# Downstream transaction crash conformance

Approved 2026-10-09 before implementation under the user's sustained project-work request.
Same project, seed 20261009, focus 2 reliability. No new repository or scheduled draw.

## Problem and references

The 0.1/0.2 stable-key result depends on the server atomically persisting the effect and
deduplication record. Those slices only killed the caller or dropped its response. They
did not kill the sink while its transaction was open. Agent tool developers need concrete
evidence for the downstream assumption, not an assertion that an idempotency header helps.

Existing LangGraph/Temporal/Restate primary reviews still establish the orchestrator
replay boundary. The reviewed AWS idempotency article explicitly requires atomic token
and effect recording. [SQLite atomic commit](https://www.sqlite.org/atomiccommit.html),
accessed 2026-10-09, explains rollback journal recovery and assumptions about filesystem
and hardware. [Python SQLite context manager](https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager)
documents commit/rollback behavior and that a connection context does not close the
connection. No upstream code copied. Do not claim hardware/power-loss verification.

## Scope and approval

Add `resumeprobe sink-run` and `sink-audit`. A separate child process runs the real
EffectSink with a narrow internal observation hook around effect insertion, key insertion,
and successful commit. For the first attempt it writes an independent crash receipt to
a separate SQLite control database, then exits abruptly with code 86. Recording control
in the effect transaction would roll back the evidence, so keep the stores separate.

Three atomic cases: die after effect insertion before key; after key insertion before
commit; after commit before caller acknowledgment. After the first worker exits, take
a durable ledger snapshot before restarting. Resume in a fresh child. Expect one final
effect and valid original identity in all three cases. Expect zero effects before resume
for pre-commit crashes and one for post-commit crash.

One deliberately broken comparison: commit the effect in a standalone transaction, then
die before key insertion. Its retry executes the same broken ordering and creates a
second effect. Clearly label this a synthetic split-transaction baseline, never production
code or the real EffectSink behavior.

Reconcile first exit, fresh PID, independent crash receipt, pre-resume counts and key count,
post-resume effect count, payload/operation identity, and returned effect ID. Preserve JSON,
static HTML, and SVG evidence for three repetitions per case. Follow existing exclusive
output semantics, trusted unsigned evidence limits, no paid APIs, no third-party data.
Keep the observation hook internal and disabled normally. Explicitly close each sink
connection, preserving commit/rollback semantics. Expose no production remote endpoint.

## Acceptance

Twelve repeated cases match: nine safe real-sink cases, three duplicate split-transaction
cases. Completion-only misses all three split duplicates. Unit tests kill actual workers,
validate before/after snapshots, prove conflict behavior still holds, reject tampered
receipts/counts/results/missing cases, and preserve existing output. All 94 prior tests,
Ruff, packaging, no-dependency wheel, report/visual QA, and six-job public CI remain gates.

## Limits and publication

No real external transactional resource or two-phase commit. SQLite process death is
not sudden power loss, storage failure, filesystem reorder, or distributed exactly-once.
Results are authored regression evidence, not an independent provider benchmark. Publish
a reviewable MIT improvement only after acceptance passes. Actual paid cost USD 0.00.
