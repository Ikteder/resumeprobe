# Crash receipts must not share the transaction under test

Accepted2026-10-09. A record written inside an uncommitted effect transaction disappears
on rollback. A second connection writing to that same database can block on its write
lock. Neither is a useful way to prove an in-transaction injection boundary.

Use a separate SQLite control database with FULL synchronization for worker starts and
crash receipts. The process exits only after the receipt's transaction commits. The
supervisor waits for termination, reads the effect/key state, then starts a fresh child.
The control store is instrumentation, not part of the tool's atomic business transaction.

The actual EffectSink has a disabled internal observation seam around insertion and
commit. The split ordering remains explicitly isolated inside the internal fixture worker.
Normal effect behavior stays atomic. Sink connections now close explicitly after commit
or rollback; Python connection context managers alone do not close connections.

These receipts establish consistency within a trusted local experiment. They are unsigned
and cannot prove origin or authentic execution to a hostile report submitter.
