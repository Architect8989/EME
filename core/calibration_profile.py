import time
import json
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Tuple

import numpy as np

from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from execution.backend_contract import BackendBase


CALIBRATION_PATH = Path("calibration_profile.json")
LATENCY_SAMPLES = 5
EXPIRY_SECONDS = 60 * 60 * 24


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
        Poison.assert_clean()
        ModeGate.assert_allowed(require=Mode.CALIBRATE)
        self._backend = backend
        self._env_hash = environment_hash

    def _discover_bounds(self) -> Tuple[int, int, int, int]:
        Poison.assert_clean()
        res = self._backend.screenshot()
        if not res.ok:
            Poison.trigger("Screenshot failed during calibration")

        if "width" not in res.data or "height" not in res.data:
            Poison.trigger("Calibration screenshot missing resolution")

        w = res.data["width"]
        h = res.data["height"]

        if w <= 0 or h <= 0:
            Poison.trigger("Invalid resolution during calibration")

        return 0, 0, w - 1, h - 1

    def _measure_latency(self) -> Tuple[float, float]:
        Poison.assert_clean()
        samples = []

        for _ in range(LATENCY_SAMPLES):
            start = time.time()
            res = self._backend.move_mouse_relative(0, 0)
            if not res.ok:
                Poison.trigger("Latency probe failed")
            samples.append((time.time() - start) * 1000.0)

        arr = np.array(samples)
        if arr.size == 0:
            Poison.trigger("No latency samples collected")

        p50 = float(np.percentile(arr, 50))
        p95 = float(np.percentile(arr, 95))

        if p50 <= 0 or p95 <= 0 or p95 < p50:
            Poison.trigger("Invalid latency distribution")

        return p50, p95

    def run(self) -> CalibrationProfile:
        Poison.assert_clean()
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
        Poison.assert_clean()
        raw = json.dumps(asdict(profile), sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()

        payload = {
            "profile": asdict(profile),
            "sha256": digest,
        }

        CALIBRATION_PATH.write_text(json.dumps(payload, indent=2))


def load_calibration(environment_hash: str) -> CalibrationProfile:
    Poison.assert_clean()

    if not CALIBRATION_PATH.exists():
        Poison.trigger("Calibration profile missing")

    payload = json.loads(CALIBRATION_PATH.read_text())

    if "profile" not in payload or "sha256" not in payload:
        Poison.trigger("Malformed calibration profile")

    profile = CalibrationProfile(**payload["profile"])

    raw = json.dumps(payload["profile"], sort_keys=True).encode()
    if hashlib.sha256(raw).hexdigest() != payload["sha256"]:
        Poison.trigger("Calibration profile tampered")

    if profile.fingerprint_hash != environment_hash:
        Poison.trigger("Calibration environment mismatch")

    if profile.is_expired():
        Poison.trigger("Calibration expired")

    return profile
