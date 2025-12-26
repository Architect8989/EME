from typing import Tuple, Any


class OSBackend:
    """
    Canonical body contract.
    No AI. No retries. No heuristics.
    """

    def move_pointer(self, x: int, y: int) -> None:
        raise NotImplementedError

    def mouse_button_down(self, button: str) -> None:
        raise NotImplementedError

    def mouse_button_up(self, button: str) -> None:
        raise NotImplementedError

    def key_down(self, key: str) -> None:
        raise NotImplementedError

    def key_up(self, key: str) -> None:
        raise NotImplementedError

    def capture_screen(self) -> Tuple[Any, float, dict]:
        """
        Returns frame, timestamp, metadata
        """
        raise NotImplementedError
