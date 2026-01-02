import time

from core.mode_gate import ModeGate, Mode
from core.calibration_profile import load_calibration, CalibrationError


class ExecutionGuardError(Exception):
    pass


class ExecutionGuard:
    _armed_at: float | None = None
    _env_hash: str | None = None
    _calibration = None

    @classmethod
    def arm_execute(cls, *, environment_hash: str):
        if ModeGate.current_mode() not in (Mode.PROBE, Mode.CALIBRATE):
            raise ExecutionGuardError("Invalid mode transition to EXECUTE")

        try:
            calibration = load_calibration(environment_hash)
        except CalibrationError as e:
            ModeGate.kill(f"Calibration invalid: {e}")
            raise

        cls._env_hash = environment_hash
        cls._calibration = calibration
        cls._armed_at = time.time()

        ModeGate.arm_execute()
        ModeGate.arm(Mode.EXECUTE)

    @classmethod
    def assert_ready(cls, *, environment_hash: str):
        if ModeGate.current_mode() != Mode.EXECUTE:
            raise ExecutionGuardError("Not in EXECUTE mode")

        if cls._env_hash != environment_hash:
            ModeGate.kill("Environment hash mismatch during EXECUTE")

        if cls._calibration is None or cls._calibration.is_expired():
            ModeGate.kill("Calibration missing or expired during EXECUTE")

    @classmethod
    def disarm(cls):
        cls._armed_at = None
        cls._env_hash = None
        cls._calibration = None
        ModeGate.disarm()
