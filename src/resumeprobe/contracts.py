from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

ADAPTERS = ("reference", "langgraph")
MODES = ("naive", "stable-key", "attempt-key")
BOUNDARIES = ("none", "before-effect", "after-effect", "after-task", "after-checkpoint")
CRASH_EXIT = 86


def canonical(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Scenario:
    adapter: str
    mode: str
    boundary: str
    seed: int
    repetition: int

    def __post_init__(self) -> None:
        if (
            self.adapter not in ADAPTERS
            or self.mode not in MODES
            or self.boundary not in BOUNDARIES
        ):
            raise ValueError("unknown adapter, mode, or boundary")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("seed must be an integer in [0, 2^32-1]")
        if type(self.repetition) is not int or not 0 <= self.repetition < 50:
            raise ValueError("repetition must be an integer in [0, 49]")

    @property
    def case_id(self) -> str:
        return f"{self.adapter}-{self.mode}-{self.boundary}-{self.repetition}"

    @property
    def operation_id(self) -> str:
        return digest(asdict(self))[:24]

    @property
    def payload(self) -> dict[str, object]:
        return {
            "action": "publish_synthetic_receipt",
            "seed": self.seed,
            "record": self.operation_id,
        }

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def matrix(seed: int, repetitions: int, adapters: tuple[str, ...]) -> list[Scenario]:
    if type(repetitions) is not int or not 1 <= repetitions <= 50:
        raise ValueError("repetitions must be in [1, 50]")
    if not adapters or len(set(adapters)) != len(adapters):
        raise ValueError("at least one distinct adapter is required")
    return [
        Scenario(adapter, mode, boundary, seed, repetition)
        for adapter in adapters
        for mode in MODES
        for boundary in BOUNDARIES
        for repetition in range(repetitions)
    ]
