import json
import time
import uuid
from pathlib import Path
from typing import Optional

from core.poison import Poison


LOG_DIR = Path("logs")
CRASH_DIR = LOG_DIR / "crash"


class LoggerError(RuntimeError):
    pass


class Logger:
    """
    Fail-closed, side-effect–bounded logger.

    Enforced invariants:
    - Single initialization
    - No logging after poison
    - No buffering, retries, or recovery
    - Any logging failure is terminal
    """

    _initialized: bool = False
    _run_id: Optional[str] = None

    @classmethod
    def init(cls) -> None:
        Poison.assert_clean()

        if cls._initialized:
            Poison.trigger("logger reinitialization attempted")

        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            CRASH_DIR.mkdir(parents=True, exist_ok=True)
        except BaseException as e:
            Poison.trigger(f"logger init failed: {repr(e)}")

        cls._run_id = uuid.uuid4().hex
        cls._initialized = True

    @classmethod
    def _assert_initialized(cls) -> None:
        if not cls._initialized:
            Poison.trigger("logger used before initialization")

    @classmethod
    def _write(cls, path: Path, record: dict) -> None:
        # logger must never operate after poison
        Poison.assert_clean()
        cls._assert_initialized()

        if not isinstance(record, dict):
            Poison.trigger("logger record is not a dict")

        payload = dict(record)
        payload["monotonic_ts"] = time.monotonic()
        payload["wall_ts"] = time.time()
        payload["run_id"] = cls._run_id

        try:
            line = json.dumps(
                payload,
                separators=(",", ":"),
                sort_keys=True,
            )
        except BaseException as e:
            Poison.trigger(f"logger serialization failed: {repr(e)}")

        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
        except BaseException as e:
            Poison.trigger(f"logger write failed: {repr(e)}")

    @classmethod
    def record(cls, record: dict) -> None:
        cls._write(LOG_DIR / "events.jsonl", record)

    @classmethod
    def crash(cls, message: str, extra: Optional[dict] = None) -> None:
        payload = {"type": "crash", "msg": message}
        if extra is not None:
            if not isinstance(extra, dict):
                Poison.trigger("logger crash extra is not a dict")
            payload["extra"] = extra
        cls._write(CRASH_DIR / "crash.jsonl", payload)


def log_event(name: str, meta: Optional[dict] = None) -> None:
    Poison.assert_clean()

    if not isinstance(name, str) or not name:
        Poison.trigger("invalid log event name")

    payload = {"type": "event", "name": name}
    if meta is not None:
        if not isinstance(meta, dict):
            Poison.trigger("log event meta is not a dict")
        payload["meta"] = meta

    Logger.record(payload)


def log_crash(message: str, extra: Optional[dict] = None) -> None:
    Poison.assert_clean()

    if not isinstance(message, str) or not message:
        Poison.trigger("invalid crash message")

    Logger.crash(message, extra)
