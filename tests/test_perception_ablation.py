"""Guard ablation switches and scoring independently of video dependencies."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

from whole_home_agent.model import Predicate

_path = Path(__file__).resolve().parents[1] / "tools/benchmark_perception_ablation.py"
_spec = importlib.util.spec_from_file_location("perception_ablation", _path)
benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(benchmark)


class PerceptionAblationTests(unittest.TestCase):
    def test_frame_local_ids_never_associate_across_frames(self):
        tracker = benchmark.FrameLocalTracker()
        first = SimpleNamespace(frame_index=1)
        second = SimpleNamespace(frame_index=2)
        a = tracker.update(first, (SimpleNamespace(position=first),))
        b = tracker.update(second, (SimpleNamespace(position=second),))
        self.assertNotEqual(a[0].track_id, b[0].track_id)
        self.assertEqual((a[0].track_age, b[0].track_age), (1, 1))
        with self.assertRaises(ValueError):
            tracker.update(second, (SimpleNamespace(position=first),))

    def test_direct_query_does_not_follow_containment(self):
        def relation(subject, predicate, target):
            return SimpleNamespace(subject_id=subject, predicate=predicate, object_id=target)
        session = SimpleNamespace(projection=SimpleNamespace(active_relations=(
            relation("key", Predicate.INSIDE, "bag"),
            relation("bag", Predicate.AT_ZONE, "sofa"),
        )))
        self.assertEqual(benchmark.direct_location(session, "key"), ("UNKNOWN", None))
        self.assertEqual(benchmark.direct_location(session, "bag"), ("FOUND", "sofa"))
        session.projection.active_relations += (relation("bag", Predicate.AT_ZONE, "table"),)
        self.assertEqual(benchmark.direct_location(session, "bag"), ("CONFLICT", None))
        session.projection.active_relations = ()
        self.assertEqual(benchmark.direct_location(session, "bag"), ("UNKNOWN", None))

    def test_fast_but_wrong_is_not_an_efficiency_candidate(self):
        rows = []
        for arm in benchmark.ARMS:
            for repeat in range(3):
                rows.append({"arm": arm, "repeat": repeat,
                             "replay_ms": 100 if arm == "baseline" else 50,
                             "detector_calls": 80 if arm == "baseline" else 8,
                             "quality": {"matched_events": 2, "false_events": 0,
                                         "missed_events": 0, "answer_correct": True}})
        self.assertTrue(benchmark.summarize(rows)["motion_periodic"]["efficiency_candidate"])
        next(r for r in rows if r["arm"] == "motion_periodic")["quality"]["answer_correct"] = False
        result = benchmark.summarize(rows)["motion_periodic"]
        self.assertFalse(result["quality_repeatable"])
        self.assertFalse(result["efficiency_candidate"])

    def test_nearest_rank_percentiles(self):
        self.assertIsNone(benchmark.percentile([], .95))
        self.assertEqual(benchmark.percentile([3, 1, 2], .5), 2)
        self.assertEqual(benchmark.percentile([3, 1, 2], .95), 3)


if __name__ == "__main__":
    unittest.main()
