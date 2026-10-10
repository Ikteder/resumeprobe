# Decision: Reconcile Against an Independent Effect Ledger

Date: 2026-10-09

Workflow completion is a weak recovery oracle. A crashed worker can repeat an effect and
still return successfully. Keep the synthetic downstream effect sink separate from each
adapter's checkpoint database. The sink is authoritative for effect count and payload identity.

Compare naive, stable-key, and per-attempt-key modes. The protected sink must commit key,
payload digest, effect, and result atomically. Reserving a key before performing the effect
or recording it after the effect would leave a loss or duplication window of its own.

Use actual `os._exit(86)` rather than an exception caught by the framework. The supervisor
resumes in a fresh interpreter. Checkpointer hooks observe `put_writes` only after the
public SQLite saver call commits. This deliberately avoids claiming that the harness is
a reproduction of LangGraph issue 8039's scheduler-dependent race.

Reference adapter supplies a standard-library reproducible path; optional LangGraph
supplies real integration evidence. Temporal and Restate need servers and are deferred.

Consequence: good replay is proven only for the tested local sink, boundaries, versions,
and host. Remote services, key expiry, authentication, power loss, and arbitrary application
tools remain separate integration questions. Tool payloads are synthetic; no user prompts
or provider keys belong in published evidence.
