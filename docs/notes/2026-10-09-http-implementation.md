# HTTP implementation observations

Date 2026-10-09. Commercial primary references and impact gate are in the approved HTTP spec.

Initial matrix: fifteen expected matches, six safe, nine duplicate-effect contracts, zero
inconclusive. Completion-only classified all nine duplicates as successful. The unchanged
key after explicit prune still committed a second effect. Conflict retry returned 409 and
preserved the original effect. Actual provider cost USD 0.00.

The first full expanded test run found intermittent Windows socket resets when invalid
request semantics were rejected before consuming a framed body. Corrected the server to
consume only a bounded, unambiguously framed body before semantic validation. Framing
violations are tested header-first; no unbounded body drain is performed. Closing with
unread bytes can still surface as a transport reset for malformed clients, not a reliable
HTTP error response. The safety invariant is no effect, not a promised error body.

The auditor now validates ordered trace sequences, server identity, fresh client identity,
request keys, effect-to-event reconciliation, explicit prune evidence, response identity,
and complete declared suite membership. This protects consistency, not authenticity.

The saved Git credential lacks workflow scope. The configured GitHub connector successfully
published the reviewed 0.1 workflow without modifying or expanding that credential. Its
six-job CI passed. Do not report the earlier OAuth limitation as a current publication blocker.
