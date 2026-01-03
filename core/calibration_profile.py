import time
import json
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Tuple

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from execution.backend_contract import BackendBase, Result


CALIBRATION_PATH = Path("calibration_profile.json")
EXPIRY_SECONDS = 60 * 60 * 24


@dataclass(frozen=True)
class CalibrationProfile:
    screen_width: int
    screen_height: int
    cursor_bounds: Tuple[int, int, int, int]
    created_at: float
    expires_at: float
    fingerprint_hash: str

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CalibrationManager:
    def __init__(self, backend: BackendBase, environment_hash: str):
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.CALIBRATE)

        if not isinstance(backend, BackendBase):
            Poison.trigger("invalid backend for calibration")

        self._backend = backend
        self._env_hash = environment_hash

    def _discover_bounds(self) -> Tuple[int, int, int, int]:
        Poison.assert_clean()

        res: Result = self._backend.screenshot(_executor_token=self._backend._executor_token)
        if not res.ok:
            Poison.trigger("screenshot failed during calibration")

        details = res.details
        if "width" not in details or "height" not in details:
            Poison.trigger("calibration screenshot missing resolution")

        w = details["width"]
        h = details["height"]

        if not isinstance(w, int) or not isinstance(h, int) or w <= 0 or h <= 0:
            Poison.trigger("invalid resolution during calibration")

        return 0, 0, w - 1, h - 1

    def run(self) -> CalibrationProfile:
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.CALIBRATE)

        bounds = self._discover_bounds()
        now = time.time()

        profile = CalibrationProfile(
            screen_width=bounds[2] + 1,
            screen_height=bounds[3] + 1,
            cursor_bounds=bounds,
            created_at=now,
            expires_at=now + EXPIRY_SECONDS,
            fingerprint_hash=self._env_hash,
        )

        self._persist(profile)
        return profile

    def _persist(self, profile: CalibrationProfile) -> None:
        Poison.assert_clean()

        raw = json.dumps(asdict(profile), sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()

        payload = {
            "profile": asdict(profile),
            "sha256": digest,
        }

        try:
            CALIBRATION_PATH.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True))
        except BaseException as e:
            Poison.trigger(f"calibration persist failed: {repr(e)}")


def load_calibration(environment_hash: str) -> CalibrationProfile:
    Poison.assert_clean()

    if not CALIBRATION_PATH.exists():
        Poison.trigger("calibration profile missing")

    try:
        payload = json.loads(CALIBRATION_PATH.read_text())
    except BaseException as e:
        Poison.trigger(f"calibration read failed: {repr(e)}")

    if not isinstance(payload, dict):
        Poison.trigger("malformed calibration payload")

    if "profile" not in payload or "sha256" not in payload:
        Poison.trigger("malformed calibration structure")

    profile_data = payload["profile"]
    expected_hash = payload["sha256"]

    raw = json.dumps(profile_data, sort_keys=True).encode()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        Poison.trigger("calibration profile tampered")

    try:
        profile = CalibrationProfile(**profile_data)
    except BaseException as e:
        Poison.trigger(f"invalid calibration fields: {repr(e)}")

    if profile.fingerprint_hash != environment_hash:
        Poison.trigger("calibration environment mismatch")

    if profile.is_expired():
        Poison.trigger("calibration expired")

    return profile
