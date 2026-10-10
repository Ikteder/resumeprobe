# Contributing

Reproduce a recovery problem with a synthetic tool and a precise crash boundary. Describe
which result was durably persisted and which effect committed. Do not use real credentials,
payments, email, or private prompts in fixtures.

Install `.[langgraph,dev]`, run pytest and Ruff, then run the bounded matrix. A new adapter
must use its real framework and persistent checkpoint store, prove the requested crash
was reached, resume in another process, and preserve independent effect evidence.

Keep production claims tied to observed versions and artifacts. Include dated decisions,
dataset notes, and acceptance criteria for meaningful behavioral changes. Contributions
are accepted under MIT; do not copy incompatible upstream code.
