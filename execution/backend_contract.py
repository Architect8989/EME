from __future__ import annotations

import abc
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, Optional

from core.system_state import SystemState
from core.poison import Poison


class ErrorCode(str, Enum):
    OK = "OK"
    TIMEOUT = "TIMEOUT"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    PRECONDITION_VIOLATION = "PRECONDITION_VIOLATION"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Result:
    ok: bool
    error_code: ErrorCode
    details: dict
    started_at_ns: int
    finished_at_ns: int

    @staticmethod
    def ok_result(started_at_ns: int, finished_at_ns: int, **details: Any) -> "Result":
        return Result(True, ErrorCode.OK, details, started_at_ns, finished_at_ns)

    @staticmethod
    def err_result(
        error_code: ErrorCode,
        started_at_ns: int,
        finished_at_ns: int,
        **details: Any,
    ) -> "Result":
        return Result(False, error_code, details, started_at_ns, finished_at_ns)


class BackendContract(Protocol):
    def screenshot(self, *, _executor_token: Any) -> Result: ...
    def move_mouse(self, x: int, y: int, *, _executor_token: Any) -> Result: ...
    def click(self, button: str, count: int, *, _executor_token: Any) -> Result: ...
    def type_text(self, text: str, *, _executor_token: Any) -> Result: ...


class BackendBase(BackendContract, abc.ABC):
    """
    Executor-monopoly backend base.

    Mechanical guarantees:
    - Cannot be used before bootstrap
    - Cannot be used after poison
    - Cannot be used without executor token
    - Cannot be rebound to another executor
    - Direct calls poison the system
    """

    def __init__(self):
        SystemState.assert_initialized()
        Poison.assert_clean()
        self._executor_token: Optional[Any] = None

    def _bind_executor(self, token: Any) -> None:
        SystemState.assert_initialized()
        Poison.assert_clean()

        if self._executor_token is not None:
            Poison.trigger("backend executor rebind attempted")

        self._executor_token = token

    def _assert_executor(self, token: Any) -> None:
        SystemState.assert_initialized()
        Poison.assert_clean()

        if self._executor_token is None:
            Poison.trigger("backend used before executor binding")

        if token is not self._executor_token:
            Poison.trigger("invalid executor token used for backend call")

    def _guard(self, token: Any) -> None:
        SystemState.assert_initialized()
        Poison.assert_clean()
        self._assert_executor(token)

    def screenshot(self, *, _executor_token: Any) -> Result:
        self._guard(_executor_token)
        started = time.time_ns()
        try:
            payload = self._impl_screenshot()
        except Exception as e:
            finished = time.time_ns()
            return Result.err_result(ErrorCode.UNKNOWN, started, finished, error=str(e))
        finished = time.time_ns()
        if not isinstance(payload, dict):
            return Result.err_result(ErrorCode.UNKNOWN, started, finished, reason="bad_payload")
        return Result.ok_result(started, finished, **payload)

    def move_mouse(self, x: int, y: int, *, _executor_token: Any) -> Result:
        self._guard(_executor_token)
        started = time.time_ns()
        if not isinstance(x, int) or not isinstance(y, int):
            finished = time.time_ns()
            return Result.err_result(ErrorCode.INVALID_ARGUMENT, started, finished)
        try:
            payload = self._impl_move_mouse(x, y)
        except Exception as e:
            finished = time.time_ns()
            return Result.err_result(ErrorCode.UNKNOWN, started, finished, error=str(e))
        finished = time.time_ns()
        if not isinstance(payload, dict):
            return Result.err_result(ErrorCode.UNKNOWN, started, finished, reason="bad_payload")
        return Result.ok_result(started, finished, **payload)

    def click(self, button: str, count: int, *, _executor_token: Any) -> Result:
        self._guard(_executor_token)
        started = time.time_ns()
        if button not in ("left", "right", "middle") or count <= 0:
            finished = time.time_ns()
            return Result.err_result(ErrorCode.INVALID_ARGUMENT, started, finished)
        try:
            payload = self._impl_click(button, count)
        except Exception as e:
            finished = time.time_ns()
            return Result.err_result(ErrorCode.UNKNOWN, started, finished, error=str(e))
        finished = time.time_ns()
        if payload is not None and not isinstance(payload, dict):
            return Result.err_result(ErrorCode.UNKNOWN, started, finished, reason="bad_payload")
        return Result.ok_result(started, finished, **(payload or {}))

    def type_text(self, text: str, *, _executor_token: Any) -> Result:
        self._guard(_executor_token)
        started = time.time_ns()
        if not isinstance(text, str) or not text:
            finished = time.time_ns()
            return Result.err_result(ErrorCode.INVALID_ARGUMENT, started, finished)
        try:
            payload = self._impl_type_text(text)
        except Exception as e:
            finished = time.time_ns()
            return Result.err_result(ErrorCode.UNKNOWN, started, finished, error=str(e))
        finished = time.time_ns()
        if payload is not None and not isinstance(payload, dict):
            return Result.err_result(ErrorCode.UNKNOWN, started, finished, reason="bad_payload")
        return Result.ok_result(started, finished, **(payload or {}))

    @abc.abstractmethod
    def _impl_screenshot(self) -> dict:
        raise NotImplementedError

    @abc.abstractmethod
    def _impl_move_mouse(self, x: int, y: int) -> dict:
        raise NotImplementedError

    @abc.abstractmethod
    def _impl_click(self, button: str, count: int) -> dict:
        raise NotImplementedError

    @abc.abstractmethod
    def _impl_type_text(self, text: str) -> dict:
        raise NotImplementedError
