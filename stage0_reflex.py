import sys

if __name__ != "__main__":
    raise RuntimeError("stage0_reflex.py is not importable")


def poison(reason: str) -> None:
    sys.stderr.write(f"[STAGE-0 POISON] {reason}\n")
    sys.stderr.flush()
    sys.exit(1)


def main() -> None:
    try:
        from body.linux_backend import LinuxBackend
        from execution.action_executor import ExecutorToken
        from actions.move_mouse_1px import MoveMouse1px
        from perception.delta import compute_delta
        from core.mode_gate import ModeGate, Mode
    except Exception as e:
        poison(f"import failure: {repr(e)}")

    token = ExecutorToken()
    try:
        backend = LinuxBackend(token)
    except Exception as e:
        poison(f"backend init failed: {repr(e)}")

    try:
        ModeGate.force(Mode.PROBE)
        pre = backend.screenshot()
        if not pre.ok:
            poison("pre screenshot failed")
    except Exception as e:
        poison(f"pre screenshot exception: {repr(e)}")

    try:
        ModeGate.force(Mode.EXECUTE)
        action = MoveMouse1px()
        action._execute(backend)
    except Exception as e:
        poison(f"action failed: {repr(e)}")

    try:
        ModeGate.force(Mode.PROBE)
        post = backend.screenshot()
        if not post.ok:
            poison("post screenshot failed")
    except Exception as e:
        poison(f"post screenshot exception: {repr(e)}")

    try:
        delta = compute_delta(
            pre_buffer=pre.details["buffer"],
            post_buffer=post.details["buffer"],
            width=pre.details["width"],
            height=pre.details["height"],
        )
    except Exception as e:
        poison(f"delta computation failed: {repr(e)}")

    if delta.get("pixels_changed", 0) <= 0:
        poison("no causal pixel change detected")

    sys.stdout.write("[STAGE-0 OK] Embodiment verified\n")
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
