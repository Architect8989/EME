from core.os_detection import detect_os


def bootstrap():
    """
    Prepare environment.
    Right now: detection only.
    Later: install tools with provenance.
    """
    facts = detect_os()
    return facts


if __name__ == "__main__":
    print(bootstrap())
