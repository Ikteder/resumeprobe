# Separate HTTP fixture, explicit retention transition

Accepted 2026-10-09. Extend ResumeProbe rather than building another proxy or SDK.

The first slice put sink and worker in the same process. A separate HTTP server and fresh
clients let the tool commit independently before the caller loses its response. Dropping
the server socket before any status line makes the ambiguous outcome visible as a real
transport error, not a mocked exception.

Retained keys are not permanent guarantees. Use a supervisor-controlled explicit key prune
after the first client exits, not elapsed-time sleep or a public admin endpoint. This is
a synthetic retention-state transition and avoids inventing provider timings. Preserve
effects for independent reconciliation.

The keyed sink binds operation identity as well as payload digest. Two distinct logical
operations with identical payloads are not equivalent intent. Reject collision rather than
returning the wrong operation's receipt. Keep task-key mode behavior compatible with 0.1.

All server traffic is loopback-only, bounded, and fixture-owned. A small global lock
serializes commit/drop ordering. The concurrency test measures safe key binding under
concurrent callers, not production server throughput. No performance advantage claimed.
