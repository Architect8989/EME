import json
import time
import uuid
from pathlib import Path
from typing import Optional

from core.poison import Poison


LOG_DIR = Path("logs")
CRASH_DIR = LOG_DIR / "crash"


class LoggerError(Exception):
    pass


class Logger:
    _initialized: bool = False
    _run_id: Optional[str] = None

    @classmethod
    def init(cls):
        Poison.assert_clean()

        if cls._initialized:
            raise LoggerError("Logger already initialized")

        try:
            LOG_DIR.mkdir(exist_ok=True)
            CRASH_DIR.mkdir(exist_ok=True)
        except Exception as e:
            Poison.trigger(f"Logger init failed: {e}")

        cls._run_id = uuid.uuid4().hex
        cls._initialized = True

    @classmethod
    def assert_initialized(cls):
        if not cls._initialized:
            Poison.trigger("Logger used before initialization")

    @classmethod
    def _write(cls, path: Path, record: dict):
        Poison.assert_clean()
        cls.assert_initialized()

        record["monotonic_ts"] = time.monotonic()
        record["wall_ts"] = time.time()
        record["run_id"] = cls._run_id

        line = json.dumps(record, separators=(",", ":"), sort_keys=True)

        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            Poison.trigger(f"Logger write failed: {e}")

    @classmethod
    def record(cls, record: dict):
        cls._write(LOG_DIR / "events.jsonl", record)

    @classmethod
    def crash(cls, message: str, extra: dict | None = None):
        payload = {"type": "crash", "msg": message}
        if extra:
            payload["extra"] = extra
        cls._write(CRASH_DIR / "crash.jsonl", payload)


# ---- Public API ----

def log(name: str, meta: dict | None = None):
    Poison.assert_clean()
    payload = {"type": "event", "name": name}
    if meta:
        payload["meta"] = meta
    Logger.record(payload)


def log_crash(message: str, extra: dict | None = None):
    Poison.assert_clean()
    Logger.crash(message, extra)
