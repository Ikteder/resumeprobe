# HTTP replay v1 fixture card

Created and accessed 2026-10-09. Independently authored synthetic contracts, MIT.
No third-party data, financial information, real user record, or model output.

Five scenarios, three repetitions each: absent key, retained stable key, per-attempt key,
explicitly pruned stable key, and changed payload under a retained key. Seed 20261009
determines operation identities. Every first response is lost after an atomic effect
commit; the second client runs in a different Python process. Server runs separately.

Original payload: publish_synthetic_receipt, seed, revision 1. Conflict uses revision 2.
JSON schema 1, suite http-replay-v1, includes server metadata, two client observations,
supervisor return codes, independent effects, durable ordered events, findings, and metrics.
Pruning deletes only the synthetic key record, never the effect. No timed expiration.

No train/test split: this is implementation-aligned regression evidence. Repetition
checks execution stability, not statistical independence or population generalization.
No held-out task corpus, true provider behavior, SDK, distributed store, or service SLA.
Raw checked evidence: docs/experiments/http-replay-v1.json. SQLite files stay ignored locally.
