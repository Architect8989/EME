import json
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict

from core.outcome_ledger import OutcomeLedger, OutcomeLedgerError


REGISTRY_PATH = Path("frozen_skills.json")


class SkillFreezeError(Exception):
    pass


@dataclass(frozen=True)
class FrozenSkillRecord:
    name: str
    environment_hash: str
    calibration_hash: str
    ledger_tail_hash: str
    sha256: str


class SkillFreezer:
    def __init__(self, ledger: OutcomeLedger):
        self._ledger = ledger

    def freeze(self, skill_name: str) -> FrozenSkillRecord:
        if not REGISTRY_PATH.exists():
            REGISTRY_PATH.write_text("{}")

        data: Dict[str, dict] = json.loads(REGISTRY_PATH.read_text())

        tail_hash = self._ledger._last_hash
        payload = {
            "name": skill_name,
            "ledger_tail_hash": tail_hash,
        }

        raw = json.dumps(payload, sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()

        record = FrozenSkillRecord(
            name=skill_name,
            environment_hash="BOUND_AT_EXECUTION",
            calibration_hash="BOUND_AT_EXECUTION",
            ledger_tail_hash=tail_hash,
            sha256=digest,
        )

        data[skill_name] = asdict(record)
        REGISTRY_PATH.write_text(json.dumps(data, indent=2))

        return record

    @staticmethod
    def verify(skill_name: str, ledger: OutcomeLedger) -> bool:
        if not REGISTRY_PATH.exists():
            raise SkillFreezeError("No frozen skills registry")

        data = json.loads(REGISTRY_PATH.read_text())
        if skill_name not in data:
            raise SkillFreezeError("Skill not frozen")

        record = data[skill_name]
        if ledger._last_hash != record["ledger_tail_hash"]:
            raise SkillFreezeError("Ledger drift detected")

        raw = json.dumps(
            {
                "name": record["name"],
                "ledger_tail_hash": record["ledger_tail_hash"],
            },
            sort_keys=True,
        ).encode()

        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise SkillFreezeError("Frozen skill tampered")

        return True
