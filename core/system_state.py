import threading


class SystemStateError(Exception):
    pass


class _BootstrapToken:
    __slots__ = ()


class SystemState:
    _lock = threading.Lock()

    _initialized: bool = False
    _poisoned: bool = False
    _token: _BootstrapToken | None = None

    # ─────────────────────────────────────────────
    # Bootstrap (single-use, monotonic)
    # ─────────────────────────────────────────────

    @classmethod
    def begin_bootstrap(cls) -> _BootstrapToken:
        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("System is poisoned")
            if cls._initialized:
                raise SystemStateError("System already initialized")
            if cls._token is not None:
                raise SystemStateError("Bootstrap already in progress")

            cls._token = _BootstrapToken()
            return cls._token

    @classmethod
    def mark_initialized(cls, token: _BootstrapToken):
        if not isinstance(token, _BootstrapToken):
            cls._poison_locked("Invalid bootstrap token type")
            raise SystemStateError("Invalid bootstrap token")

        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("System is poisoned")
            if cls._initialized:
                raise SystemStateError("System already initialized")
            if token is not cls._token:
                cls._poison_locked("Bootstrap token mismatch")
                raise SystemStateError("Bootstrap token mismatch")

            cls._initialized = True
            cls._token = None  # irreversibly consumed

    # ─────────────────────────────────────────────
    # Poisoning (terminal, irreversible)
    # ─────────────────────────────────────────────

    @classmethod
    def poison(cls, reason: str | None = None):
        with cls._lock:
            cls._poison_locked(reason)

    @classmethod
    def _poison_locked(cls, reason: str | None):
        cls._poisoned = True
        cls._token = None
        # NOTE: _initialized is intentionally NOT reset
        # Poisoned ≠ uninitialized; poisoned = terminal

    # ─────────────────────────────────────────────
    # Guards
    # ─────────────────────────────────────────────

    @classmethod
    def assert_initialized(cls):
        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("System is poisoned")
            if not cls._initialized:
                raise SystemStateError("System not initialized via bootstrap")

    @classmethod
    def assert_alive(cls):
        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("System is poisoned")
