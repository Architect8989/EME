from dataclasses import dataclass, field
from typing import List

from perception_env.region import Region


@dataclass
class VisualObject:
    """
    Ephemeral visual object.

    Represents a stable identity across frames, built from Regions.
    Identity is valid only for a single run (single life).

    Invariants:
    - No OS access
    - No backend / executor access
    - No persistence across runs
    - Identity is heuristic and may become unstable
    """

    object_id: int
    regions: List[Region] = field(default_factory=list)
    age: int = 0              # number of frames observed
    stability: float = 0.0    # 0.0 – 1.0 confidence of identity stability
    alive: bool = True

    def update(self, region: Region, stability_delta: float) -> None:
        """
        Update object with a new observed region.

        This mutates only in-run memory.
        """
        self.regions.append(region)
        self.age += 1

        # Clamp stability to [0.0, 1.0]
        self.stability = max(0.0, min(1.0, self.stability + stability_delta))

    @property
    def latest_region(self) -> Region:
        if not self.regions:
            raise RuntimeError("visual object has no regions")
        return self.regions[-1]

    def mark_dead(self) -> None:
        """
        Mark object as no longer observed.
        """
        self.alive = False
