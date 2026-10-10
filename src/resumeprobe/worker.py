from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

from resumeprobe.contracts import CRASH_EXIT, Scenario, canonical
from resumeprobe.sink import EffectSink


class CrashController:
    def __init__(self, scenario: Scenario, sink: EffectSink, attempt: int):
        self.scenario = scenario
        self.sink = sink
        self.attempt = attempt

    def hit(self, boundary: str) -> None:
        if self.attempt == 1 and self.scenario.boundary == boundary:
            self.sink.event("crash_injected", self.attempt, {"boundary": boundary})
            os._exit(CRASH_EXIT)

    def effect(self) -> dict[str, object]:
        self.sink.event("tool_invoked", self.attempt)
        self.hit("before-effect")
        result = self.sink.apply(
            self.scenario.operation_id, self.scenario.payload, self.scenario.mode, self.attempt
        )
        self.hit("after-effect")
        return result


def reference_worker(directory: Path, control: CrashController) -> dict[str, object]:
    with sqlite3.connect(directory / "checkpoint.sqlite") as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        previous = db.execute("SELECT value FROM state WHERE name='complete'").fetchone()
        if previous:
            control.sink.event("checkpoint_reused", control.attempt)
            return json.loads(previous[0])
        task_result = db.execute("SELECT value FROM state WHERE name='task'").fetchone()
        if task_result:
            result = json.loads(task_result[0])
            control.sink.event("task_result_reused", control.attempt)
        else:
            result = control.effect()
            db.execute("INSERT INTO state VALUES('task',?)", (canonical(result),))
            db.commit()
            control.sink.event("task_result_persisted", control.attempt)
            control.hit("after-task")
        db.execute("INSERT INTO state VALUES('complete',?)", (canonical(result),))
        db.commit()
    control.sink.event("checkpoint_persisted", control.attempt)
    control.hit("after-checkpoint")
    return result


def langgraph_worker(directory: Path, control: CrashController) -> dict[str, object]:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.func import entrypoint, task

    class ObservedSaver(SqliteSaver):
        def put_writes(self, config, writes, task_id, task_path=""):
            super().put_writes(config, writes, task_id, task_path)
            # The public saver method has committed the task result when it returns.
            # The pinned Functional API uses __return__ for task results, not __end__.
            if any(
                channel == "__return__" and isinstance(value, dict) and "effect_id" in value
                for channel, value in writes
            ):
                control.sink.event("task_result_persisted", control.attempt)
                control.hit("after-task")

    with sqlite3.connect(directory / "checkpoint.sqlite", check_same_thread=False) as connection:
        saver = ObservedSaver(connection)

        @task
        def publish_receipt(_: dict) -> dict:
            return control.effect()

        @entrypoint(checkpointer=saver)
        def workflow(payload: dict) -> dict:
            return publish_receipt(payload).result()

        config = {"configurable": {"thread_id": control.scenario.operation_id}}
        previous = workflow.get_state(config)
        if previous.created_at is not None and not previous.next:
            control.sink.event("checkpoint_reused", control.attempt)
            return previous.values
        value = None if previous.created_at is not None else control.scenario.payload
        result = workflow.invoke(value, config, durability="sync")
    control.sink.event("checkpoint_persisted", control.attempt)
    control.hit("after-checkpoint")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Internal ResumeProbe worker")
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--attempt", required=True, type=int, choices=(1, 2))
    args = parser.parse_args()
    scenario = Scenario(
        **json.loads((args.directory / "scenario.json").read_text(encoding="utf-8"))
    )
    sink = EffectSink(args.directory / "sink.sqlite")
    sink.event("worker_started", args.attempt, {"pid": os.getpid()})
    control = CrashController(scenario, sink, args.attempt)
    adapter = reference_worker if scenario.adapter == "reference" else langgraph_worker
    result = adapter(args.directory, control)
    sink.event("response_acknowledged", args.attempt, result)
    (args.directory / f"result-{args.attempt}.json").write_text(canonical(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
