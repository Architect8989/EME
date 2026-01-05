import sys

from core.mode_gate import ModeGate, Mode
from core.environment_contract import EnvironmentContract
from core.poison import Poison
from core.system_state import SystemState


class BootstrapError(RuntimeError):
    pass


def _abort(reason: str) -> None:
    sys.stderr.write(f"[BOOTSTRAP ABORT] {reason}\n")
    sys.stderr.flush()
    Poison.trigger(f"bootstrap abort: {reason}")


def bootstrap(bootstrap_token) -> dict:
    """
    Deterministic, single-shot bootstrap.

    Enforced invariants:
    - Must be called exactly once
    - Requires valid bootstrap token
    - No OS interaction
    - No branching recovery
    - Any ambiguity is terminal
    """

    # global terminal guards
    Poison.assert_clean()

    # bootstrap token must be valid and current
    try:
        if bootstrap_token is not SystemState._token:
            _abort("invalid or stale bootstrap token")
    except BaseException:
        _abort("bootstrap token verification failed")

    # environment contract must verify or halt
    try:
        env_fp = EnvironmentContract.verify()
    except BaseException as e:
        _abort(f"environment verification failed: {repr(e)}")

    # deterministic initial mode
    try:
        ModeGate.transition(Mode.PROBE)
    except BaseException as e:
        _abort(f"mode initialization failed: {repr(e)}")

    # bootstrap returns only inert data
    try:
        env_hash = EnvironmentContract.fingerprint_hash(env_fp)
    except BaseException as e:
        _abort(f"environment hash failed: {repr(e)}")

    return {
        "environment_hash": env_hash,
        "status": "BOOTSTRAP_OK",
    }
