import subprocess


def probe_system_identity():
    result = subprocess.run(
        ["uname", "-a"],
        capture_output=True,
        text=True,
        timeout=3,
    )
    return result.stdout.strip()
