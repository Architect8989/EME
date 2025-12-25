import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOG_DIR = BASE / "logs"

EXPERIMENT_LOG = LOG_DIR / "experiments.jsonl"
CRASH_LOG = LOG_DIR / "crashes.log"
EVENT_LOG = LOG_DIR / "events.log"


def _ensure_dir(path: Path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


class Logger:
    def __init__(self, path: Path = EXPERIMENT_LOG):
        self.path = path
        _ensure_dir(self.path)

    def record(self, record: dict):
        try:
            line = json.dumps(record, ensure_ascii=False)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def log_event(message: str):
    try:
        _ensure_dir(EVENT_LOG)
        with open(EVENT_LOG, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass


def log_crash(message: str):
    try:
        _ensure_dir(CRASH_LOG)
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass
