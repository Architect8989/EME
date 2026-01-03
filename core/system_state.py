import threading


class SystemStateError(Exception):
    pass


class _BootstrapToken:
    __slots__ = ()


class SystemState:
    _lock = threading.Lock()
    _initialized: bool = False
    _token: _BootstrapToken | None = None

    @classmethod
    def _issue_bootstrap_token(cls) -> _BootstrapToken:
        with cls._lock:
            if cls._initialized:
                raise SystemStateError("System already initialized")
            if cls._token is not None:
                raise SystemStateError("Bootstrap token already issued")
            cls._token = _BootstrapToken()
            return cls._token

    @classmethod
    def mark_initialized(cls, token: _BootstrapToken):
        if not isinstance(token, _BootstrapToken):
            raise SystemStateError("Invalid bootstrap token")

        with cls._lock:
            if cls._initialized:
                raise SystemStateError("System already initialized")
            if token is not cls._token:
                raise SystemStateError("Bootstrap token mismatch")

            cls._initialized = True
            cls._token = None  # irreversibly consumed

    @classmethod
    def assert_initialized(cls):
        if not cls._initialized:
            raise SystemStateError("System not initialized via bootstrap")
