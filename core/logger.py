"""
Audit-grade logger.
Append-only. JSONL. No silence. No guessing.
"""

import os
import json
import time
import uuid
from pathlib import Path


LOG_DIR = Path("logs")
CRASH_DIR = LOG_DIR / "crash"


def _ensure_dirs():
    LOG_DIR.mkdir(exist_ok=True)
    CRASH_DIR.mkdir(exist_ok=True)


_ensure_dirs()


class Logger:
    def __init__(self):
        self.run_id = uuid.uuid4().hex

    def _write(self, path: Path, record: dict):
        record["monotonic_ts"] = time.monotonic()
        record["wall_ts"] = time.time()
        record["run_id"] = self.run_id

        line = json.dumps(record, separators=(",", ":"), sort_keys=True)

        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def record(self, record: dict):
        path = LOG_DIR / "events.jsonl"
        self._write(path, record)

    def crash(self, message: str, extra: dict | None = None):
        payload = {"type": "crash", "msg": message}
        if extra:
            payload["extra"] = extra
        path = CRASH_DIR / "crash.jsonl"
        self._write(path, payload)


def log_event(name: str, meta: dict | None = None):
    logger = Logger()
    payload = {"type": "event", "name": name}
    if meta:
        payload["meta"] = meta
    logger.record(payload)


def log_crash(message: str, extra: dict | None = None):
    Logger().crash(message, extra)
