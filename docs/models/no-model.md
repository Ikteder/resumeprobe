# Model and Provider Record

Date: 2026-10-09

No model, embedding, paid API, or hosted inference provider was called. Exact runtime
packages: LangGraph 1.2.14 and langgraph-checkpoint-sqlite 3.1.1; standard-library reference
adapter; local Python 3.14.7. The tool payload and crash policy are deterministic.

LangGraph is orchestration infrastructure here, not a language model. There is no token
count or model accuracy measurement. Actual paid-provider cost: USD 0.00. LangChain and
LangSmith tracing flags are disabled in workers to avoid inheriting optional hosted tracing.

Intended use: agent tool recovery integration experiments. Non-goals: semantic answer
quality, prompt injection evaluation, provider reliability rankings, or financial guarantees.
