from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path

from resumeprobe.contracts import canonical
from resumeprobe.http_contract import HttpScenario


def send_request(port: int, request: dict, attempt: int, timeout: float = 3) -> dict:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid loopback port")
    headers = {"Content-Type": "application/json", "X-ResumeProbe-Attempt": str(attempt)}
    if request["key"] is not None:
        headers["Idempotency-Key"] = request["key"]
    encoded = canonical({"operation_id": request["operation_id"], "payload": request["payload"]})
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("POST", "/effects", encoded, headers)
        response = connection.getresponse()
        raw = response.read(8193)
        if len(raw) > 8192:
            raise ValueError("fixture response exceeds limit")
        return {"outcome": "response", "status": response.status, "body": json.loads(raw)}
    except (http.client.HTTPException, OSError) as exc:
        return {"outcome": "transport_error", "error_type": type(exc).__name__}
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Internal synthetic loopback client")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--attempt", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    scenario = HttpScenario(
        **json.loads((args.directory / "scenario.json").read_text(encoding="utf-8"))
    )
    result = send_request(args.port, scenario.request(args.attempt), args.attempt)
    result.update({"pid": os.getpid(), "attempt": args.attempt})
    (args.directory / f"client-{args.attempt}.json").write_text(canonical(result), encoding="utf-8")


if __name__ == "__main__":
    main()
