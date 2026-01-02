import json
import time
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any


LEDGER_PATH = Path("outcome_ledger.jsonl")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class LedgerEntry:
    index: int
    timestamp_ns: int
    environment_hash: str
    calibration_hash: str
    state_before_hash: str
    action: Dict[str, Any]
    result: Dict[str, Any]
    state_after_hash: Optional[str]
    refusal: Optional[Dict[str, Any]]
    prev_hash: str
    entry_hash: str


class OutcomeLedgerError(Exception):
    pass


class OutcomeLedger:
    def __init__(self, path: Path = LEDGER_PATH):
        self._path = path
        self._last_hash = "GENESIS"
        self._index = 0
        if self._path.exists():
            self._rehydrate()

    def _rehydrate(self):
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                self._last_hash = obj["entry_hash"]
                self._index = obj["index"] + 1

    def append(
        self,
        *,
        environment_hash: str,
        calibration_hash: str,
        state_before_hash: str,
        action: Dict[str, Any],
        result: Dict[str, Any],
        state_after_hash: Optional[str] = None,
        refusal: Optional[Dict[str, Any]] = None,
    ) -> LedgerEntry:
        payload = {
            "index": self._index,
            "timestamp_ns": time.time_ns(),
            "environment_hash": environment_hash,
            "calibration_hash": calibration_hash,
            "state_before_hash": state_before_hash,
            "action": action,
            "result": result,
            "state_after_hash": state_after_hash,
            "refusal": refusal,
            "prev_hash": self._last_hash,
        }

        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        entry_hash = _sha256(raw)
        payload["entry_hash"] = entry_hash

        entry = LedgerEntry(**payload)

        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), separators=(",", ":")) + "\n")

        self._last_hash = entry_hash
        self._index += 1
        return entry

    @staticmethod
    def verify(path: Path = LEDGER_PATH) -> bool:
        last_hash = "GENESIS"
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                expected_prev = obj["prev_hash"]
                if expected_prev != last_hash:
                    raise OutcomeLedgerError("Hash chain broken")

                payload = obj.copy()
                entry_hash = payload.pop("entry_hash")
                raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                if _sha256(raw) != entry_hash:
                    raise OutcomeLedgerError("Entry hash mismatch")

                last_hash = entry_hash
        return True
