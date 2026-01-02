from execution.backend_contract import BackendBase
from core.poison import Poison


class MacOSBackend(BackendBase):
    def __init__(self, *args, **kwargs):
        Poison.trigger("macOS backend is not supported in this build")
