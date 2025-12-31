import threading
from core.logger import log_event, log_crash


class SafetyGuard:
    def __init__(self):
        self._lock = threading.Lock()
        self._frozen = False
        self._reason = None
        self._observe_only = False

    # ---------- STATE QUERIES ----------

    def is_frozen(self) -> bool:
        with self._lock:
            return self._frozen

    def freeze_reason(self):
        with self._lock:
            return self._reason

    def is_observe_only(self) -> bool:
        with self._lock:
            return self._observe_only

    # ---------- HARD CONTROLS ----------

    def lock_observe_only(self):
        with self._lock:
            self._observe_only = True
            log_event("guard.lock.observe_only")

    def unlock_observe_only(self):
        with self._lock:
            if self._frozen:
                return False
            self._observe_only = False
            log_event("guard.unlock.observe_only")
            return True

    def emergency_stop(self, reason: str):
        with self._lock:
            if self._frozen:
                return
            self._frozen = True
            self._reason = reason
            log_crash("guard.emergency_stop", {"reason": reason})

    # ---------- ENFORCEMENT ----------

    def assert_can_execute(self):
        with self._lock:
            if self._frozen:
                raise RuntimeError(f"system frozen: {self._reason}")
            if self._observe_only:
                raise RuntimeError("observe-only mode enforced")

    # ---------- MANUAL RECOVERY ----------

    def manual_reset(self) -> bool:
        with self._lock:
            if not self._frozen:
                return False
            self._frozen = False
            self._reason = None
            log_event("guard.manual_reset")
            return True
