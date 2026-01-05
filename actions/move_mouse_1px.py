from dataclasses import dataclass

from core.mode_gate import Mode
from core.poison import Poison
from core.state_snapshot import StateSnapshot
from execution.action_contract import ActionContract
from execution.backend_contract import Result


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
    """
    Declarative action.

    Enforced invariants:
    - No OS effects
    - No backend method invocation
    - No executor token access
    - Pure intent derivation only
    """

    contract = MOVE_MOUSE_1PX_CONTRACT

    def _execute(self, backend) -> Result:
        # backend must never be used directly by actions
        Poison.trigger("action attempted direct backend access")
