from execution.backend_contract import BackendBase
from core.poison import Poison


class WindowsBackend(BackendBase):
    def __init__(self, *args, **kwargs):
        Poison.trigger("Windows backend is not supported in this build")
