"""Private loopback-only synthetic tool server, never a production deployment."""

from __future__ import annotations

import argparse
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from resumeprobe.contracts import canonical
from resumeprobe.sink import EffectSink

BODY_LIMIT = 8192


class FixtureHTTPServer(ThreadingHTTPServer):
    # Set before listen(), not after construction. This local fixture accepts bursts
    # larger than older Python versions' default five-entry pending socket queue.
    request_queue_size = 64


def reject_constant(value: str):
    raise ValueError(f"non-finite JSON value: {value}")


def make_server(sink: EffectSink, *, drop_first: bool = True) -> ThreadingHTTPServer:
    lock = threading.Lock()
    dropped = False

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(2)

        def log_message(self, format, *args):
            pass

        def respond(self, status: int, body: dict) -> None:
            encoded = canonical(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(encoded)
            self.close_connection = True

        def do_POST(self):
            nonlocal dropped
            if self.path != "/effects":
                self.respond(404, {"error": "unknown fixture path"})
                return
            try:
                lengths = self.headers.get_all("Content-Length", [])
                if self.headers.get("Transfer-Encoding") or len(lengths) != 1:
                    raise ValueError("one Content-Length and no Transfer-Encoding required")
                length = int(lengths[0])
                if not 1 <= length <= BODY_LIMIT:
                    self.respond(413, {"error": "fixture body limit"})
                    return
                # Consume a bounded, unambiguously framed body before rejecting semantics.
                # Closing with unread bytes can reset the socket on Windows.
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError("incomplete body")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("application/json required")
                attempts = self.headers.get_all("X-ResumeProbe-Attempt", [])
                if len(attempts) != 1:
                    raise ValueError("one fixture attempt required")
                attempt = int(attempts[0])
                if not 1 <= attempt <= 100:
                    raise ValueError("attempt out of range")
                keys = self.headers.get_all("Idempotency-Key", [])
                if len(keys) > 1 or (keys and not 1 <= len(keys[0]) <= 255):
                    raise ValueError("invalid idempotency key")
                key = keys[0] if keys else None
                body = json.loads(raw, parse_constant=reject_constant)
                if not isinstance(body, dict) or set(body) != {"operation_id", "payload"}:
                    raise ValueError("expected operation_id and payload")
                operation = body["operation_id"]
                if not isinstance(operation, str) or not 1 <= len(operation) <= 128:
                    raise ValueError("invalid operation identity")
                if not isinstance(body["payload"], dict):
                    raise ValueError("payload must be an object")
            except (ValueError, TypeError, UnicodeError, TimeoutError):
                self.respond(400, {"error": "invalid fixture request"})
                return
            # Serializes response-loss injection with commit order, not all HTTP processing.
            with lock:
                sink.event("http_request", attempt, {"pid": os.getpid(), "key": key})
                try:
                    result = sink.apply_keyed(operation, body["payload"], key, attempt)
                except ValueError:
                    sink.event("http_conflict", attempt, {"operation_id": operation})
                    self.respond(409, {"error": "idempotency conflict"})
                    return
                if drop_first and not dropped:
                    dropped = True
                    sink.event("http_response_dropped", attempt, result)
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                sink.event("http_response_sent", attempt, result)
                self.respond(200, result)

    server = FixtureHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Internal synthetic loopback HTTP server")
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    sink = EffectSink(args.directory / "sink.sqlite")
    with make_server(sink) as server:
        ready = {"pid": os.getpid(), "port": server.server_port, "host": "127.0.0.1"}
        sink.event("http_server_started", 0, ready)
        (args.directory / "server-ready.json").write_text(canonical(ready), encoding="utf-8")
        server.serve_forever(poll_interval=0.05)


if __name__ == "__main__":
    main()
