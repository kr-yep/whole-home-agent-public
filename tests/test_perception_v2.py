"""Independent scorer and scheduler regression checks for the v2 experiment."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

TOOLS = Path(__file__).resolve().parents[1]/"tools"
sys.path.insert(0,str(TOOLS))
try:
    from benchmark_perception_v2 import score_events, BurstScheduler
    from generate_ablation_v2 import SCENARIOS, scene
finally:
    sys.path.pop(0)


class V2ScorerTests(unittest.TestCase):
    def event(self, frame=10):
        return dict(frame_index=frame,operation="assert",subject_id="key",predicate="inside",object_id="bag")

    def test_missed_duplicate_early_and_late_events(self):
        expected = [self.event()]
        self.assertEqual(score_events(expected,[])["fn"],1)
        for frame in (9,19):
            score = score_events(expected,[self.event(frame)])
            self.assertEqual((score["tp"],score["fp"],score["fn"]),(0,1,1))
        score = score_events(expected,[self.event(12),self.event(13)])
        self.assertEqual((score["tp"],score["fp"],score["fn"]),(1,1,0))

    def test_empty_negative_does_not_get_artificial_perfect_f1(self):
        self.assertIsNone(score_events([],[])["f1"])
        self.assertEqual(score_events([],[self.event()])["fp"],1)

    def test_scripted_scenes_are_distinct_and_labels_do_not_use_predictions(self):
        for name in SCENARIOS:
            for variant in range(4):
                frames, events, queries = scene(name,variant)
                self.assertEqual(len(frames),80)
                self.assertEqual(len(queries),10)
                if name in ("stationary","occlusion","disappear"):
                    self.assertEqual(events,[])
                if name=="take_out":
                    self.assertEqual(events[-1]["operation"],"retract")
                    last_key = next(q for q in queries if q["frame"]==79 and q["subject"]=="key")
                    self.assertEqual(last_key["status"],"UNKNOWN")

    @unittest.skipUnless(importlib.util.find_spec("numpy"),"optional video dependencies")
    def test_idle_anchor_and_change_burst(self):
        import numpy as np
        def frame(i,changed=False):
            rgb = np.zeros((16,16,3),dtype=np.uint8)
            if changed:
                rgb[4,4,:]=255
            return SimpleNamespace(position=SimpleNamespace(frame_index=i,pts=i),rgb=rgb)
        scheduler = BurstScheduler()
        self.assertTrue(scheduler.evaluate(frame(0)).selected)
        self.assertFalse(scheduler.evaluate(frame(1)).selected)
        self.assertTrue(scheduler.evaluate(frame(2)).selected)
        self.assertTrue(scheduler.evaluate(frame(3,True)).selected)
        self.assertTrue(scheduler.evaluate(frame(4,True)).selected)
