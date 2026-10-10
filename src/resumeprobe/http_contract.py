from __future__ import annotations

from dataclasses import asdict, dataclass

from resumeprobe.contracts import digest

HTTP_CASES = ("no-key", "stable-key", "attempt-key", "pruned-key", "payload-conflict")


@dataclass(frozen=True)
class HttpScenario:
    name: str
    seed: int
    repetition: int

    def __post_init__(self) -> None:
        if self.name not in HTTP_CASES:
            raise ValueError("unknown HTTP scenario")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("seed must be an integer in [0, 2^32-1]")
        if type(self.repetition) is not int or not 0 <= self.repetition < 50:
            raise ValueError("repetition must be in [0, 49]")

    @property
    def case_id(self) -> str:
        return f"http-{self.name}-{self.repetition}"

    @property
    def operation_id(self) -> str:
        return digest(asdict(self))[:24]

    def request(self, attempt: int) -> dict:
        payload = {"action": "publish_synthetic_receipt", "seed": self.seed, "revision": 1}
        if self.name == "payload-conflict" and attempt == 2:
            payload["revision"] = 2
        key = None if self.name == "no-key" else self.operation_id
        if self.name == "attempt-key":
            key = f"{key}:{attempt}"
        return {"operation_id": self.operation_id, "payload": payload, "key": key}

    @property
    def expected_status(self) -> str:
        return "safe" if self.name in ("stable-key", "payload-conflict") else "unsafe"

    def to_dict(self) -> dict:
        return asdict(self)
