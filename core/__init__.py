import sys

# NOTE:
# core must NEVER be imported before bootstrap completes.
# This file is the global import gate for the entire project.

try:
    from core.system_state import SystemState
except Exception:
    # If SystemState itself cannot be imported, this is fatal.
    sys.stderr.write("[FATAL] core imported before system_state available\n")
    sys.exit(1)


# Bootstrap is the ONLY allowed way to reach initialized state.
# Any import of core.* before initialization is a hard failure.
try:
    SystemState.assert_initialized()
except Exception:
    sys.stderr.write(
        "[FATAL] core imported before bootstrap initialization\n"
        "Use main.py as the sole entrypoint.\n"
    )
    sys.exit(1)
