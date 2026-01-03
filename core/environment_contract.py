import hashlib
from dataclasses import dataclass, asdict

from core.poison import Poison


class EnvironmentMismatch(RuntimeError):
    pass


@dataclass(frozen=True)
class EnvironmentFingerprint:
    fingerprint_hash: str


class EnvironmentContract:
    """
    Deterministic environment gate.

    Mechanical guarantees:
    - No OS inspection
    - No platform probing
    - No subprocess usage
    - No conditional platform support
    - Single immutable fingerprint input
    """

    @classmethod
    def verify(cls) -> EnvironmentFingerprint:
        """
        Environment verification is forbidden in a frozen artifact.
        """
        Poison.trigger("environment verification is not permitted in this build")

    @staticmethod
    def fingerprint_hash(_: EnvironmentFingerprint) -> str:
        Poison.trigger("environment fingerprinting is not permitted in this build")
