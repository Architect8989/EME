import time
import json
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Tuple

import numpy as np

from core.mode_gate import ModeGate, Mode
from execution.backend_contract import BackendBase, Result, ErrorCode


CALIBRATION_PATH = Path("calibration_profile.json")
MAX_PROBE_MOVE_PX = 1
LATENCY_SAMPLES = 5
EXPIRY_SECONDS = 60 * 60 * 24


class CalibrationError(Exception):
    pass


@dataclass(frozen=True)
class CalibrationProfile:
    screen_width: int
    screen_height: int
    cursor_bounds: Tuple[int, int, int, int]
    latency_p50_ms: float
    latency_p95_ms: float
    created_at: float
    expires_at: float
    fingerprint_hash: str

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CalibrationManager:
    def __init__(self, backend: BackendBase, environment_hash: str):
        ModeGate.assert_allowed(require=Mode.CALIBRATE)
        self._backend = backend
        self._env_hash = environment_hash

    def _measure_latency(self) -> Tuple[float, float]:
        samples = []

        for _ in range(LATENCY_SAMPLES):
            start = time.time()
            res = self._backend.move_mouse_relative(0, 0)
            if not res.ok:
                raise CalibrationError("Latency probe failed")
            samples.append((time.time() - start) * 1000.0)
            time.sleep(0.05)

        arr = np.array(samples)
        return float(np.percentile(arr, 50)), float(np.percentile(arr, 95))

    def _discover_bounds(self) -> Tuple[int, int, int, int]:
        res = self._backend.screenshot()
        if not res.ok:
            raise CalibrationError("Screenshot failed during bounds discovery")

        w = res.data["width"]
        h = res.data["height"]
        return 0, 0, w - 1, h - 1

    def run(self) -> CalibrationProfile:
        ModeGate.assert_allowed(require=Mode.CALIBRATE)

        bounds = self._discover_bounds()
        p50, p95 = self._measure_latency()

        now = time.time()
        profile = CalibrationProfile(
            screen_width=bounds[2] + 1,
            screen_height=bounds[3] + 1,
            cursor_bounds=bounds,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            created_at=now,
            expires_at=now + EXPIRY_SECONDS,
            fingerprint_hash=self._env_hash,
        )

        self._persist(profile)
        return profile

    def _persist(self, profile: CalibrationProfile):
        raw = json.dumps(asdict(profile), sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()

        payload = {
            "profile": asdict(profile),
            "sha256": digest,
        }

        CALIBRATION_PATH.write_text(json.dumps(payload, indent=2))


def load_calibration(environment_hash: str) -> CalibrationProfile:
    if not CALIBRATION_PATH.exists():
        raise CalibrationError("Calibration profile missing")

    payload = json.loads(CALIBRATION_PATH.read_text())
    profile = CalibrationProfile(**payload["profile"])

    raw = json.dumps(payload["profile"], sort_keys=True).encode()
    if hashlib.sha256(raw).hexdigest() != payload["sha256"]:
        raise CalibrationError("Calibration profile tampered")

    if profile.fingerprint_hash != environment_hash:
        raise CalibrationError("Calibration does not match environment")

    if profile.is_expired():
        raise CalibrationError("Calibration expired")

    return profile
