def clamp_pointer(x: int, y: int, width: int, height: int):
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    return x, y


FORBIDDEN_KEYS = {
    "alt+f4",
    "ctrl+alt+del",
    "shutdown",
    "reboot"
}
