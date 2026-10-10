# Loopback burst reliability correction

Approved 2026-10-09 before implementation under sustained project-work authorization.

CI run 38014892588 passed five jobs but Ubuntu Python 3.12 failed the concurrent-key
test: one returned a transport-error object rather than an HTTP status. The stack also
showed a peer closing before the server wrote its response. The original log did not
retain the transport error type, so an exact socket-level cause is not proven.

The fixture uses Python's default ThreadingHTTPServer accept backlog, which can be
smaller than its eight simultaneous test clients. Give this private loopback fixture
an explicit queue size of 64 before bind/listen. Keep timeouts and lost-response
injection unchanged; do not add retries or mask transport errors. Improve the assertion
to retain all failed results. Add a burst regression with 16 workers and 32 requests,
requiring every response to match and exactly one committed effect. Verify the configured
backlog directly. Treat the fix as a supported diagnosis only after six-job CI passes.

No production-server claim, external endpoint, model, provider, paid call, or upstream
copy. Existing matrix expectations and all tests remain gates. Record the failed run
and subsequent verification, rather than describing all original CI jobs as successful.
