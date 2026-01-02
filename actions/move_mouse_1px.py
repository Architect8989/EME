from dataclasses import dataclass

from core.mode_gate import Mode
from core.state_snapshot import StateSnapshot
from execution.action_contract import ActionContract
from execution.backend_contract import BackendBase, Result, ErrorCode


def _precondition(snapshot: StateSnapshot) -> bool:
    return True


def _postcondition(before: StateSnapshot, after: StateSnapshot) -> bool:
    bx, by = before.cursor
    ax, ay = after.cursor
    return (ax == bx + 1 and ay == by) or (ax == bx - 1 and ay == by)


def _forbidden(snapshot: StateSnapshot) -> bool:
    return False


MOVE_MOUSE_1PX_CONTRACT = ActionContract(
    name="move_mouse_1px",
    allowed_mode=Mode.EXECUTE,
    precondition=_precondition,
    postcondition=_postcondition,
    forbidden=[_forbidden],
    max_impact=1.0,
)


@dataclass(frozen=True)
class MoveMouse1px:
    contract = MOVE_MOUSE_1PX_CONTRACT

    def _execute(self, backend: BackendBase) -> Result:
        snap = StateSnapshot.from_backend(backend)
        x, y = snap.cursor
        return backend.move_mouse(x + 1, y)
