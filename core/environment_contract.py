from dataclasses import dataclass

from core.poison import Poison


@dataclass(frozen=True)
class EnvironmentFingerprint:
    """
    Immutable environment fingerprint.

    Enforced invariants:
    - Pure data container
    - No computation
    - No derivation
    - No mutation
    """

    fingerprint_hash: str


class EnvironmentContract:
    """
    Frozen-environment contract.

    Enforced invariants:
    - No OS inspection
    - No platform probing
    - No subprocess usage
    - No conditional behavior
    - No entropy sources
    - Deterministic, total verification
    """

    _FROZEN_FINGERPRINT = EnvironmentFingerprint(
        fingerprint_hash="FROZEN_ENVIRONMENT"
    )

    @classmethod
    def verify(cls) -> EnvironmentFingerprint:
        Poison.assert_clean()

        fp = cls._FROZEN_FINGERPRINT
        if not isinstance(fp, EnvironmentFingerprint):
            Poison.trigger("environment fingerprint corrupted")

        if not isinstance(fp.fingerprint_hash, str) or not fp.fingerprint_hash:
            Poison.trigger("invalid environment fingerprint")

        return fp

    @staticmethod
    def fingerprint_hash(fp: EnvironmentFingerprint) -> str:
        Poison.assert_clean()

        if not isinstance(fp, EnvironmentFingerprint):
            Poison.trigger("invalid fingerprint object")

        h = fp.fingerprint_hash
        if not isinstance(h, str) or not h:
            Poison.trigger("invalid fingerprint hash")

        return h
