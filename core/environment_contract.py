# core/environment_contract.py
"""
Authoritative environment verifier.
This file decides whether the system is allowed to exist.

If the environment deviates from the expected contract,
the system is killed before any actuator or backend loads.
"""

import hashlib
import locale
import platform
import subprocess
from dataclasses import dataclass, asdict

from core.mode_gate import ModeGate


class EnvironmentMismatch(Exception):
    pass


@dataclass(frozen=True)
class EnvironmentFingerprint:
    os_name: str
    os_version: str
    kernel: str
    architecture: str

    resolution: tuple[int, int]
    monitor_count: int
    wm_name: str

    locale: str
    keyboard_layout: str

    animations_disabled: bool


class EnvironmentContract:
    """
    Hard allowlist.
    Nothing outside this fingerprint is permitted.
    """

    # ⚠️ Populate this explicitly after first successful probe
    ALLOWED_HASHES: set[str] = set()

    @staticmethod
    def _run(cmd: str) -> str:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()

    @classmethod
    def collect(cls) -> EnvironmentFingerprint:
        try:
            # OS basics
            os_name = platform.system()
            os_version = platform.version()
            kernel = platform.release()
            architecture = platform.machine()

            # Display (Linux/X11 assumption — deliberate)
            resolution = tuple(
                map(
                    int,
                    cls._run("xdpyinfo | grep dimensions | awk '{print $2}'").split("x"),
                )
            )

            monitor_count = int(
                cls._run("xrandr --listmonitors | grep Monitors | awk '{print $2}'")
            )

            wm_name = cls._run("wmctrl -m | grep Name | cut -d':' -f2").strip()

            # Locale & keyboard
            loc = locale.getdefaultlocale()[0] or "UNKNOWN"
            keyboard_layout = cls._run("setxkbmap -query | grep layout | awk '{print $2}'")

            # Animations (GNOME-specific, strict)
            animations_disabled = (
                cls._run(
                    "gsettings get org.gnome.desktop.interface enable-animations"
                )
                == "false"
            )

            return EnvironmentFingerprint(
                os_name=os_name,
                os_version=os_version,
                kernel=kernel,
                architecture=architecture,
                resolution=resolution,
                monitor_count=monitor_count,
                wm_name=wm_name,
                locale=loc,
                keyboard_layout=keyboard_layout,
                animations_disabled=animations_disabled,
            )

        except Exception as e:
            ModeGate.kill(f"Environment collection failed: {e}")
            raise

    @staticmethod
    def fingerprint_hash(fp: EnvironmentFingerprint) -> str:
        raw = repr(sorted(asdict(fp).items())).encode()
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def verify(cls) -> EnvironmentFingerprint:
        """
        Verify environment against allowlist.
        This must be called before any backend initialization.
        """
        fp = cls.collect()
        h = cls.fingerprint_hash(fp)

        if h not in cls.ALLOWED_HASHES:
            ModeGate.kill(
                "Environment mismatch.\n"
                f"Fingerprint hash: {h}\n"
                f"Details: {fp}"
            )

        return fp
