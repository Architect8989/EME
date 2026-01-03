raise RuntimeError("Invalid entrypoint. Use main.py only.")
from core.system_state import SystemState
from core.mode_gate import ModeGate, Mode
from core.poison import Poison
from core.environment_contract import EnvironmentContract
from core.calibration_profile import load_calibration
from execution.action_executor import ActionExecutor
from body.linux_backend import LinuxBackend
from actions.move_mouse_1px import MoveMouse1px
from bootstrap.bootstrap import bootstrap


def main():
    # 1. Bootstrap (single entrypoint)
    info = bootstrap()
    env_hash = info["environment_hash"]

    # 2. Assert clean system
    SystemState.assert_initialized()
    Poison.assert_clean()

    # 3. Load calibration (hard gate)
    load_calibration(env_hash)

    # 4. Instantiate backend (no OS call yet)
    backend = LinuxBackend()

    # 5. Instantiate executor (binds backend + token)
    executor = ActionExecutor(
        backend=backend,
        environment_hash=env_hash,
    )

    # 6. Arm EXECUTE (explicit, one-way)
    ModeGate.arm_execute()
    ModeGate.arm(Mode.EXECUTE)

    # 7. Execute exactly one real action
    executor.execute(MoveMouse1px())

    # 8. Exit immediately (no loops, no retries)
    return


if __name__ == "__main__":
    main()
