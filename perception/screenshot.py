import time
from pathlib import Path
from PIL import ImageGrab


BASE = Path(__file__).resolve().parent.parent
SNAP_DIR = BASE / "snapshots"


def _ensure_dir(path: Path):
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


class Snapshot:
    def __init__(self, path: Path, width: int, height: int, timestamp: float):
        self.path = path
        self.width = width
        self.height = height
        self.timestamp = timestamp


def capture_screen(experiment_id: str) -> Snapshot:
    _ensure_dir(SNAP_DIR)

    ts = time.time()
    filename = f"{experiment_id}_{int(ts * 1000)}.png"
    out_path = SNAP_DIR / filename

    img = ImageGrab.grab()
    img.save(out_path)

    w, h = img.size
    return Snapshot(out_path, w, h, ts)
