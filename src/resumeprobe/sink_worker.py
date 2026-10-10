"""Internal crash worker. Split ordering is intentionally incorrect fixture code."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from resumeprobe.contracts import CRASH_EXIT, canonical, digest
from resumeprobe.sink import EffectSink


def control_event(directory: Path, kind: str, attempt: int, detail: object) -> None:
    with closing(sqlite3.connect(directory / "control.sqlite")) as db, db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute(
            "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, kind TEXT, "
            "attempt INTEGER, pid INTEGER, detail TEXT)"
        )
        db.execute(
            "INSERT INTO events(kind,attempt,pid,detail) VALUES(?,?,?,?)",
            (kind, attempt, os.getpid(), canonical(detail)),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Internal sink atomicity worker")
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--attempt", required=True, type=int, choices=(1, 2))
    args = parser.parse_args()
    scenario = json.loads((args.directory / "scenario.json").read_text(encoding="utf-8"))
    from resumeprobe.sink_recovery import SinkScenario

    selected = SinkScenario(**scenario)
    control_event(args.directory, "worker_started", args.attempt, None)

    def crash(boundary: str):
        if args.attempt == 1 and boundary == selected.boundary:
            control_event(args.directory, "crash_injected", args.attempt, {"boundary": boundary})
            os._exit(CRASH_EXIT)

    class ObservedSink(EffectSink):
        def _observe(self, boundary: str) -> None:
            crash(boundary)

    sink = ObservedSink(args.directory / "sink.sqlite")
    if selected.boundary == "split-commit":
        # Deliberately unsafe baseline: committing an effect before its key is NOT atomic.
        payload_hash = digest(selected.payload)
        with sink.connect() as db:
            existing = db.execute(
                "SELECT effect_id FROM keys WHERE request_key=?", (selected.operation_id,)
            ).fetchone()
            if existing:
                effect_id = existing[0]
            else:
                effect_id = db.execute(
                    "INSERT INTO effects(operation_id,payload_sha256,attempt,request_key) "
                    "VALUES(?,?,?,?)",
                    (selected.operation_id, payload_hash, args.attempt, selected.operation_id),
                ).lastrowid
        crash("split-commit")
        if not existing:
            with sink.connect() as db:
                db.execute(
                    "INSERT INTO keys VALUES(?,?,?)",
                    (selected.operation_id, payload_hash, effect_id),
                )
        result = {
            "effect_id": effect_id,
            "operation_id": selected.operation_id,
            "payload_sha256": payload_hash,
        }
    else:
        result = sink.apply_keyed(
            selected.operation_id, selected.payload, selected.operation_id, args.attempt
        )
    (args.directory / "result.json").write_text(canonical(result), encoding="utf-8")


if __name__ == "__main__":
    main()
