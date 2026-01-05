import time
import hashlib

from core.poison import Poison
from core.logger import log_event, log_crash
from perception.screen_adapter import ScreenAdapter, Frame
from execution.backend_contract import Result
from evaluation.causality import evaluate_causality
from perception.delta import compute_delta

from perception_env.region_extractor import RegionExtractor
from perception_env.object_tracker import ObjectTracker
from perception_env.env_state_builder import EnvironmentStateBuilder
from perception_env.affordance_detector import AffordanceDetector
from perception_env.ephemeral_memory import EphemeralMemory


class Unverified(RuntimeError):
    pass


def _hash_record(prev_hash: str, record: dict) -> str:
    h = hashlib.sha256()
    if prev_hash:
        h.update(prev_hash.encode("utf-8"))
    h.update(repr(record).encode("utf-8"))
    return h.hexdigest()


class LifeLoop:
    """
    Single-pass execution verifier with environment modeling.

    Enforced invariants:
    - Exactly one execution attempt
    - Exactly two observations (pre/post)
    - Environment modeling is read-only
    - No retries, no loops
    - Any ambiguity poisons immediately
    """

    __slots__ = (
        "_executor",
        "_screen",
        "_last_hash",
        "_region_extractor",
        "_object_tracker",
        "_env_builder",
        "_affordance_detector",
        "_memory",
    )

    def __init__(self, executor) -> None:
        Poison.assert_clean()

        if executor is None:
            Poison.trigger("life_loop instantiated without executor")

        self._executor = executor
        self._screen = ScreenAdapter()
        self._last_hash = ""

        # ── environment modeling components (inert, deterministic)
        self._region_extractor = RegionExtractor()
        self._object_tracker = ObjectTracker()
        self._env_builder = EnvironmentStateBuilder()
        self._affordance_detector = AffordanceDetector()
        self._memory = EphemeralMemory()

    def run_experiment(self, action) -> dict:
        Poison.assert_clean()

        start_ts = time.monotonic()
        verdict = "UNVERIFIED"
        error = None

        try:
            log_event("experiment.begin")

            # ──────────────────
            # OBSERVE (PRE)
            # ──────────────────
            pre_res: Result = self._executor.backend.screenshot(
                _executor_token=self._executor.token
            )

            if not pre_res.ok:
                Poison.trigger("pre-screenshot failed")

            pre: Frame = self._screen.ingest(
                buffer=pre_res.details["buffer"],
                width=pre_res.details["width"],
                height=pre_res.details["height"],
                pixel_format=pre_res.details["pixel_format"],
            )

            # ──────────────────
            # ENVIRONMENT MODELING (READ-ONLY)
            # ──────────────────
            regions = self._region_extractor.extract(pre)
            objects = self._object_tracker.update(regions)

            cursor = pre_res.details.get("cursor")
            env_state = self._env_builder.build(
                objects=objects,
                cursor=cursor,
            )

            affordances = self._affordance_detector.detect(env_state)
            # NOTE: affordances are hypotheses only
            # No execution decision is made here unless an action is explicitly provided

            # ──────────────────
            # EXECUTE (SOLE AUTHORITY)
            # ──────────────────
            if action is not None:
                self._executor.execute(action)

            # ──────────────────
            # OBSERVE (POST)
            # ──────────────────
            post_res: Result = self._executor.backend.screenshot(
                _executor_token=self._executor.token
            )

            if not post_res.ok:
                Poison.trigger("post-screenshot failed")

            post: Frame = self._screen.ingest(
                buffer=post_res.details["buffer"],
                width=post_res.details["width"],
                height=post_res.details["height"],
                pixel_format=post_res.details["pixel_format"],
            )

            # ──────────────────
            # DELTA (BUFFER-LEVEL)
            # ──────────────────
            delta = compute_delta(
                pre_buffer=pre.buffer,
                post_buffer=post.buffer,
                width=pre.width,
                height=pre.height,
            )

            # ──────────────────
            # CAUSALITY (FAIL-CLOSED)
            # ──────────────────
            causality = evaluate_causality(
                delta=delta,
                time_window=(start_ts, time.monotonic()),
                pre_ts=pre.timestamp_monotonic,
                post_ts=post.timestamp_monotonic,
            )

            if causality.get("attributed") is not True:
                raise Unverified(causality.get("reason", "causality_failed"))

            verdict = "VERIFIED"

        except BaseException as e:
            error = repr(e)
            Poison.trigger(f"life_loop failure: {error}")

        record = {
            "type": "experiment",
            "verdict": verdict,
            "error": error,
            "duration": time.monotonic() - start_ts,
        }

        record_hash = _hash_record(self._last_hash, record)
        record["record_hash"] = record_hash
        record["prev_hash"] = self._last_hash
        self._last_hash = record_hash

        try:
            log_event(f"experiment.{verdict.lower()}")
        except BaseException as e:
            log_crash("logging failure", {"error": repr(e)})
            Poison.trigger(f"logging failure: {repr(e)}")

        if verdict != "VERIFIED":
            Poison.trigger("non-verified execution reached return")

        return record
