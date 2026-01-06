"""
Stage-0 Reflex Proof
====================

This file exists ONLY to prove embodiment.

Invariants:
- Single entrypoint
- Single OS action
- Single causality check
- Immediate exit
- No loops
- No recovery
- No persistence

This file must NEVER be imported.
"""

import sys
import time


# ─────────────────────────────────────────────
# HARD ENTRYPOINT SEAL
# ─────────────────────────────────────────────

if __name__ != "__main__":
    raise RuntimeError("stage0_reflex.py is not importable")


# ─────────────────────────────────────────────
# ABSOLUTE FAIL-CLOSED GUARD
# ─────────────────────────────────────────────

def poison(reason: str) -> None:
    sys.stderr.write(f"[STAGE-0 POISON] {reason}\n")
    sys.stderr.flush()
    sys.exit(1)


# ─────────────────────────────────────────────
# MAIN REFLEX
# ─────────────────────────────────────────────

def main() -> None:
    # Import NOTHING except the minimum needed for reflex
    try:
        from execution.backend_linux_x11 import LinuxBackend
        from execution.action_executor import ExecutorToken
        from actions.move_mouse_1px import MoveMouse1px
        from perception.delta import compute_delta
    except Exception as e:
        poison(f"import failure: {repr(e)}")

    # ── Instantiate backend directly (no framework)
    token = ExecutorToken()

    try:
        backend = LinuxBackend(token)
    except Exception as e:
        poison(f"backend init failed: {repr(e)}")

    # ── PRE-OBSERVATION
    try:
        pre = backend.screenshot()
        if not pre.ok:
            poison("pre screenshot failed")
    except Exception as e:
        poison(f"pre screenshot exception: {repr(e)}")

    # ── SINGLE ACTION (REFLEX)
    try:
        action = MoveMouse1px()
        action._execute(backend)
    except Exception as e:
        poison(f"action failed: {repr(e)}")

    # ── POST-OBSERVATION
    try:
        post = backend.screenshot()
        if not post.ok:
            poison("post screenshot failed")
    except Exception as e:
        poison(f"post screenshot exception: {repr(e)}")

    # ── CAUSALITY CHECK (BINARY)
    try:
        delta = compute_delta(
            pre_buffer=pre.details["buffer"],
            post_buffer=post.details["buffer"],
            width=pre.details["width"],
            height=pre.details["height"],
        )
    except Exception as e:
        poison(f"delta computation failed: {repr(e)}")

    pixels_changed = delta.get("pixels_changed", 0)
    if pixels_changed <= 0:
        poison("no causal pixel change detected")

    # ── SUCCESS → DIE
    sys.stdout.write("[STAGE-0 OK] Embodiment verified\n")
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
