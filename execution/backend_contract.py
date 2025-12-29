from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol
from enum import Enum
import abc
import time
import threading


class ErrorCode(str, Enum):
    OK = "OK"
    TIMEOUT = "TIMEOUT"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    OS_REJECTED = "OS_REJECTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PRECONDITION_VIOLATION = "PRECONDITION_VIOLATION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Result:
    ok: bool
    error_code: ErrorCode
    details: dict
    started_at_ns: int
    finished_at_ns: int

    @staticmethod
    def success(started_at_ns: int, finished_at_ns: int, **details: Any) -> "Result":
        return Result(True, ErrorCode.OK, details, started_at_ns, finished_at_ns)

    @staticmethod
    def failure(
        error_code: ErrorCode,
        started_at_ns: int,
        finished_at_ns: int,
        **details: Any,
    ) -> "Result":
        return Result(False, error_code, details, started_at_ns, finished_at_ns)


class BackendContract(Protocol):
    def screenshot(
        self,
        *,
        timeout_seconds: float,
        latest_screenshot_timestamp_ns: int,
    ) -> Result:
        ...

    def move_mouse(
        self,
        x: int,
        y: int,
        *,
        timeout_seconds: float,
        latest_screenshot_timestamp_ns: int,
    ) -> Result:
        ...

    def click(
        self,
        button: str,
        count: int,
        *,
        timeout_seconds: float,
        latest_screenshot_timestamp_ns: int,
    ) -> Result:
        ...

    def type_text(
        self,
        text: str,
        *,
        timeout_seconds: float,
        latest_screenshot_timestamp_ns: int,
    ) -> Result:
        ...


class BackendBase(BackendContract, abc.ABC):
    def _guard_preconditions(self, timeout_seconds: float, ts: int) -> str | None:
        if timeout_seconds is None or timeout_seconds <= 0:
            return "invalid_timeout"
        if ts is None or ts <= 0:
            return "invalid_timestamp"
        return None

    def _run_with_timeout(self, timeout_seconds: float, fn, *args, **kwargs):
        result_holder = {"res": None, "exc": None}

        def target():
            try:
                result_holder["res"] = fn(*args, **kwargs)
            except Exception as e:
                result_holder["exc"] = e

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout_seconds)

        if t.is_alive():
            return "timeout", None, None

        if result_holder["exc"] is not None:
            return "exception", None, result_holder["exc"]

        return "ok", result_holder["res"], None

    def screenshot(
        self,
        *,
        timeout_seconds: float,
        latest_screenshot_timestamp_ns: int,
    ) -> Result:
        started = time.time_ns()
        pre = self._guard_preconditions(timeout_seconds, latest_screenshot_timestamp_ns)
        if pre:
            finished = time.time_ns()
            return Result.failure(
                ErrorCode.PRECONDITION_VIOLATION,
                started,
                finished,
                reason=pre,
            )

        status, payload, exc = self._run_with_timeout(
            timeout_seconds, self._impl_screenshot
        )
        finished = time.time_ns()

        if status == "timeout":
            return Result.failure(ErrorCode.TIMEOUT, started, finished)
        if exc:
            return Result.failure(ErrorCode.UNKNOWN, started, finished, error=str(exc))

        ok = isinstance(payload, dict) and all(
            k in payload for k in ("width", "height", "format", "sha256", "storage_key")
        )
        if not ok:
            return Result.failure(ErrorCode.UNKNOWN, started, finished, reason="bad_payload")

        return Result.success(started, finished, **payload)

    def move_mouse(
        self,
        x: int,
        y: int,
        *,
        timeout_seconds: float,
        latest_screenshot_timestamp_ns: int,
    ) -> Result:
        started = time.time_ns()
        pre = self._guard_preconditions(timeout_seconds, latest_screenshot_timestamp_ns)
        if pre:
            finished = time.time_ns()
            return Result.failure(
                ErrorCode.PRECONDITION_VIOLATION,
                started,
                finished,
                reason=pre,
            )

        if not isinstance(x, int) or not isinstance(y, int):
            finished = time.time_ns()
            return Result.failure(
                ErrorCode.INVALID_ARGUMENT, started, finished, reason="coords_not_int"
            )

        status, payload, exc = self._run_with_timeout(
            timeout_seconds, self._impl_move_mouse, x, y
        )
        finished = time.time_ns()

        if status == "timeout":
            return Result.failure(ErrorCode.TIMEOUT, started, finished)
        if exc:
            return Result.failure(ErrorCode.UNKNOWN, started, finished, error=str(exc))

        if not isinstance(payload, dict) or "final" not in payload:
            return Result.failure(ErrorCode.UNKNOWN, started, finished, reason="bad_payload")

        return Result.success(started, finished, requested=(x, y), **payload)

    def click(
        self,
        button: str,
        count: int,
        *,
        timeout_seconds: float,
        latest_screenshot_timestamp_ns: int,
    ) -> Result:
        started = time.time_ns()
        pre = self._guard_preconditions(timeout_seconds, latest_screenshot_timestamp_ns)
        if pre:
            finished = time.time_ns()
            return Result.failure(
                ErrorCode.PRECONDITION_VIOLATION,
                started,
                finished,
                reason=pre,
            )

        if button not in ("left", "right", "middle") or not (1 <= count <= 3):
            finished = time.time_ns()
            return Result.failure(
                ErrorCode.INVALID_ARGUMENT,
                started,
                finished,
                reason="button_or_count_invalid",
            )

        status, payload, exc = self._run_with_timeout(
            timeout_seconds, self._impl_click, button, count
        )
        finished = time.time_ns()

        if status == "timeout":
            return Result.failure(ErrorCode.TIMEOUT, started, finished)
        if exc:
            return Result.failure(ErrorCode.UNKNOWN, started, finished, error=str(exc))

        return Result.success(started, finished, button=button, count=count, **(payload or {}))

    def type_text(
        self,
        text: str,
        *,
        timeout_seconds: float,
        latest_screenshot_timestamp_ns: int,
    ) -> Result:
        started = time.time_ns()
        pre = self._guard_preconditions(timeout_seconds, latest_screenshot_timestamp_ns)
        if pre:
            finished = time.time_ns()
            return Result.failure(
                ErrorCode.PRECONDITION_VIOLATION,
                started,
                finished,
                reason=pre,
            )

        if not isinstance(text, str) or len(text) == 0 or len(text) > 4096:
            finished = time.time_ns()
            return Result.failure(
                ErrorCode.INVALID_ARGUMENT,
                started,
                finished,
                reason="text_invalid",
            )

        status, payload, exc = self._run_with_timeout(
            timeout_seconds, self._impl_type_text, text
        )
        finished = time.time_ns()

        if status == "timeout":
            return Result.failure(ErrorCode.TIMEOUT, started, finished)
        if exc:
            return Result.failure(ErrorCode.UNKNOWN, started, finished, error=str(exc))

        return Result.success(started, finished, length=len(text), **(payload or {}))

    @abc.abstractmethod
    def _impl_screenshot(self) -> dict:
        ...

    @abc.abstractmethod
    def _impl_move_mouse(self, x: int, y: int) -> dict:
        ...

    @abc.abstractmethod
    def _impl_click(self, button: str, count: int) -> dict:
        ...

    @abc.abstractmethod
    def _impl_type_text(self, text: str) -> dict:
        ...
