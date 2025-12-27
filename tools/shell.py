# tools/shell.py

import subprocess
import shlex
import uuid
import time
from pathlib import Path

from core.logger import log
from core.delta import Delta


SAFE_WHITELIST = {
    "whoami",
    "uname -a",
    "ls",
    "pwd",
    "date",
}


def _now():
    return int(time.time() * 1000)


def _validate_command(cmd: str):
    if cmd not in SAFE_WHITELIST:
        raise ValueError(f"disallowed_command: {cmd}")


def run_shell(cmd: str) -> Delta:
    """
    PRIME RULE:
    Never return raw stdout. Never return Python objects.
    Always return a Delta describing *observable change or observation*.
    """

    _validate_command(cmd)

    start_ts = _now()
    cmd_id = str(uuid.uuid4())

    try:
        proc = subprocess.run(
            shlex.split(cmd),
            capture_output=True,
            text=True,
            timeout=10,
        )

        delta = Delta(
            kind="shell_observation",
            source="tools.shell",
            id=cmd_id,
            timestamp=_now(),
            data={
                "command": cmd,
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "duration_ms": _now() - start_ts,
            },
        )

        assert isinstance(delta, Delta), "non_delta_leak(shell)"
        log("shell_exec", delta.data)
        return delta

    except Exception as e:
        delta = Delta(
            kind="shell_error",
            source="tools.shell",
            id=cmd_id,
            timestamp=_now(),
            data={
                "command": cmd,
                "error": repr(e),
                "duration_ms": _now() - start_ts,
            },
        )

        assert isinstance(delta, Delta), "non_delta_leak(shell_error)"
        log("shell_error", delta.data)
        return delta
