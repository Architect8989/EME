import threading


class SystemStateError(RuntimeError):
    pass


class _BootstrapToken:
    __slots__ = ()


class SystemState:
    """
    Terminal, monotonic global system state.

    Mechanical invariants:
    - Exactly one bootstrap path
    - Bootstrap token is single-use and unforgeable
    - Initialization is irreversible
    - Poison is terminal and dominates all states
    - No reset, no re-bootstrap, no recovery
    """

    _lock = threading.Lock()

    _initialized: bool = False
    _poisoned: bool = False
    _token: _BootstrapToken | None = None

    # ─────────────────────────────────────────────
    # Bootstrap (single-use, irreversible)
    # ─────────────────────────────────────────────

    @classmethod
    def begin_bootstrap(cls) -> _BootstrapToken:
        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("system poisoned")

            if cls._initialized:
                raise SystemStateError("system already initialized")

            if cls._token is not None:
                raise SystemStateError("bootstrap already in progress")

            cls._token = _BootstrapToken()
            return cls._token

    @classmethod
    def mark_initialized(cls, token: _BootstrapToken) -> None:
        if not isinstance(token, _BootstrapToken):
            cls._poison_locked()
            raise SystemStateError("invalid bootstrap token")

        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("system poisoned")

            if cls._initialized:
                raise SystemStateError("system already initialized")

            if token is not cls._token:
                cls._poison_locked()
                raise SystemStateError("bootstrap token mismatch")

            cls._initialized = True
            cls._token = None

    # ─────────────────────────────────────────────
    # Poisoning (terminal, irreversible)
    # ─────────────────────────────────────────────

    @classmethod
    def poison(cls) -> None:
        with cls._lock:
            cls._poison_locked()

    @classmethod
    def _poison_locked(cls) -> None:
        cls._poisoned = True
        cls._token = None

    # ─────────────────────────────────────────────
    # Guards
    # ─────────────────────────────────────────────

    @classmethod
    def assert_initialized(cls) -> None:
        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("system poisoned")

            if not cls._initialized:
                raise SystemStateError("system not initialized")

    @classmethod
    def assert_alive(cls) -> None:
        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("system poisoned")
