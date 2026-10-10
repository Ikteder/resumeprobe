from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from resumeprobe.contracts import canonical, digest


class EffectSink:
    """Synthetic downstream service with an independent, authoritative effect ledger."""

    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS effects (
                    effect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
                    attempt INTEGER NOT NULL, request_key TEXT
                );
                CREATE TABLE IF NOT EXISTS keys (
                    request_key TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL,
                    effect_id INTEGER NOT NULL REFERENCES effects(effect_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL, attempt INTEGER NOT NULL, detail TEXT NOT NULL
                );
                """
            )

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _event(db: sqlite3.Connection, kind: str, attempt: int, detail: object) -> None:
        db.execute(
            "INSERT INTO events(kind,attempt,detail) VALUES(?,?,?)",
            (kind, attempt, canonical(detail)),
        )

    def event(self, kind: str, attempt: int, detail: object = None) -> None:
        with self.connect() as db:
            self._event(db, kind, attempt, detail)

    def apply(
        self, operation_id: str, payload: object, mode: str, attempt: int
    ) -> dict[str, object]:
        if mode not in ("naive", "stable-key", "attempt-key"):
            raise ValueError("unknown effect mode")
        request_key = None
        if mode == "stable-key":
            request_key = operation_id
        elif mode == "attempt-key":
            request_key = f"{operation_id}:{attempt}"
        return self.apply_keyed(operation_id, payload, request_key, attempt)

    def apply_keyed(
        self, operation_id: str, payload: object, request_key: str | None, attempt: int
    ) -> dict[str, object]:
        payload_sha256 = digest(payload)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = None
            if request_key is not None:
                existing = db.execute(
                    "SELECT keys.payload_sha256,keys.effect_id,effects.operation_id FROM keys "
                    "JOIN effects USING(effect_id) WHERE keys.request_key=?",
                    (request_key,),
                ).fetchone()
            if existing:
                if existing[0] != payload_sha256 or existing[2] != operation_id:
                    raise ValueError("idempotency key reused with different payload or operation")
                effect_id = existing[1]
                self._event(db, "effect_reused", attempt, {"effect_id": effect_id})
            else:
                effect_id = db.execute(
                    "INSERT INTO effects(operation_id,payload_sha256,attempt,request_key) "
                    "VALUES(?,?,?,?)",
                    (operation_id, payload_sha256, attempt, request_key),
                ).lastrowid
                if request_key is not None:
                    db.execute(
                        "INSERT INTO keys VALUES(?,?,?)", (request_key, payload_sha256, effect_id)
                    )
                self._event(db, "effect_committed", attempt, {"effect_id": effect_id})
        return {
            "effect_id": effect_id,
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
        }

    def prune_fixture_key(self, request_key: str) -> None:
        """Explicit synthetic retention transition; effects are never deleted."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            deleted = db.execute("DELETE FROM keys WHERE request_key=?", (request_key,)).rowcount
            self._event(db, "key_pruned", 0, {"request_key": request_key, "deleted": deleted})

    def snapshot(self) -> dict[str, object]:
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            effects = [dict(row) for row in db.execute("SELECT * FROM effects ORDER BY effect_id")]
            events = []
            for row in db.execute("SELECT * FROM events ORDER BY seq"):
                event = dict(row)
                event["detail"] = json.loads(event["detail"])
                events.append(event)
        return {"effects": effects, "events": events}
