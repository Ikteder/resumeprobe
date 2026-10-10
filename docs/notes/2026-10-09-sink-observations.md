# Sink crash observations

Date2026-10-09. Actual initial matrix:12/12 expectations,9safe,3unsafe,0inconclusive.
Before-key and after-key deaths left no durable effect or key. After-commit death left
one of each, and retry reused the original result. The deliberately split baseline left
an effect but no key before retry and produced a second effect afterwards.

Separate control receipts avoided the lock and rollback problem of storing instrumentation
inside the effect transaction. All first workers exited86; new workers finished0. PIDs
differed. Connection-lifecycle tests check that commit and conflict rollback release SQLite
connections without ResourceWarnings. No capability claim exceeds the measured process
boundaries. Actual paid costUSD0.00. Primary SQLite and Python evidence is in the spec.

Focused sink tests:23passed in4.53seconds, including existing sink tests. The full suite,
packaging, visual checks, and public CI are recorded after completion, not inferred.
