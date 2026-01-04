from dataclasses import dataclass

from core.poison import Poison


@dataclass(frozen=True)
class EnvironmentFingerprint:
    """
    Deterministic, constant environment fingerprint.
    """
    fingerprint_hash: str


class EnvironmentContract:
    """
    Frozen-environment contract.

    Mechanical guarantees:
    - No OS inspection
    - No platform probing
    - No subprocess usage
    - No conditional behavior
    - Deterministic, non-failing verification
    """

    _FROZEN_FINGERPRINT = EnvironmentFingerprint(
        fingerprint_hash="FROZEN_ENVIRONMENT"
    )

    @classmethod
    def verify(cls) -> EnvironmentFingerprint:
        Poison.assert_clean()
        return cls._FROZEN_FINGERPRINT

    @staticmethod
    def fingerprint_hash(fp: EnvironmentFingerprint) -> str:
        Poison.assert_clean()
        return fp.fingerprint_hash
