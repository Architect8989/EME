import time
from pathlib import Path
from PIL import Image, ImageDraw

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

    # Headless fallback: generate synthetic frame
    img = Image.new("RGB", (640, 400), color=(18, 18, 18))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), f"experiment={experiment_id}", fill=(200, 200, 200))
    draw.text((10, 30), f"timestamp={ts}", fill=(150, 150, 150))
    img.save(out_path)

    return Snapshot(out_path, 640, 400, ts)
