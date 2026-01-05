import threading


class SystemStateError(RuntimeError):
    pass


class _BootstrapToken:
    __slots__ = ()

    def __init__(self):
        # prevent subclassing or external construction tricks
        if type(self) is not _BootstrapToken:
            raise SystemStateError("invalid bootstrap token type")


class SystemState:
    """
    Terminal, monotonic global system state.

    Mechanical invariants (enforced, not documented):
    - Exactly one bootstrap token can ever exist
    - Token identity, not value, authorizes initialization
    - Initialization is single-shot and irreversible
    - Poison is terminal and dominates all states
    - No reset, no re-bootstrap, no recovery
    """

    _lock = threading.Lock()

    _initialized: bool = False
    _poisoned: bool = False
    _token: _BootstrapToken | None = None

    # ─────────────────────────────────────────────
    # Bootstrap (single issuance, single use)
    # ─────────────────────────────────────────────

    @classmethod
    def _issue_bootstrap_token(cls) -> _BootstrapToken:
        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("system poisoned")

            if cls._initialized:
                raise SystemStateError("system already initialized")

            if cls._token is not None:
                raise SystemStateError("bootstrap token already issued")

            token = _BootstrapToken()
            cls._token = token
            return token

    @classmethod
    def mark_initialized(cls, token: _BootstrapToken) -> None:
        # identity check must happen before lock release
        if token is None or token is not cls._token:
            cls._poison_now()
            raise SystemStateError("bootstrap token mismatch")

        with cls._lock:
            if cls._poisoned:
                raise SystemStateError("system poisoned")

            if cls._initialized:
                raise SystemStateError("system already initialized")

            if token is not cls._token:
                cls._poison_now()
                raise SystemStateError("bootstrap token mismatch")

            cls._initialized = True
            cls._token = None

    # ─────────────────────────────────────────────
    # Poisoning (terminal latch)
    # ─────────────────────────────────────────────

    @classmethod
    def poison(cls) -> None:
        with cls._lock:
            cls._poison_now()

    @classmethod
    def _poison_now(cls) -> None:
        cls._poisoned = True
        cls._token = None

    # ─────────────────────────────────────────────
    # Guards (fail-closed)
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
