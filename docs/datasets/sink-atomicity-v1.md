# Sink atomicity v1 fixture card

Created/accessed 2026-10-09; independent synthetic fixtures, MIT; seed20261009.
Four boundaries, three repetitions each, twelve cases. No model output, third-party
dataset, personal data, or actual downstream payment/mail operation.

Real EffectSink: crash after effect insertion, after key insertion, and after atomic
commit. A separately labeled split-commit comparison intentionally persists the effect
before its deduplication record and crashes between them. This is not production code.

Each case contains the first and second worker exit codes, ordered receipts from a
separate control SQLite store, a pre-resume ledger snapshot, a post-resume snapshot,
operation/payload/key identity, result, findings, and suite expectations. Schema1,
suite sink-atomicity-v1. Raw JSON at docs/experiments/sink-atomicity-v1.json.

No train/test split. Implementation-aligned regression evidence; repetitions check
process behavior rather than population generalization. Process IDs and elapsed time
are measured and not seed-stable. No VFS fault injection, filesystem damage, power loss,
distributed store, live provider, independent corpus, or external atomic resource.
