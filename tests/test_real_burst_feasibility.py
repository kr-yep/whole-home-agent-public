"""The preliminary real-data screen can reject, never certify end-to-end use."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
try:
    import check_real_burst_feasibility as screen
finally:
    sys.path.pop(0)


@unittest.skipUnless(importlib.util.find_spec("numpy"),"optional video dependencies")
class RealBurstScreenTests(unittest.TestCase):
    def run_fake(self, changing):
        import numpy as np
        def frames():
            for index in range(30):
                rgb=np.full((16,16,3),255*(index%2) if changing else 0,dtype=np.uint8)
                yield SimpleNamespace(rgb=rgb,position=SimpleNamespace(frame_index=index,pts=index))
        source=SimpleNamespace(iter_frames=frames,frame_count=30,mask_change_frames=frozenset({5,10}),
            coverage_window_frames=1,split="development",descriptor=SimpleNamespace(source_id="fake",content_hash="a"*64))
        manifest=SimpleNamespace(sequences=[SimpleNamespace(split="development",sequence_id="fake")])
        with patch.object(Path,"exists",return_value=False), patch.object(screen,"load_vost_motion_screen_manifest",return_value=manifest), patch.object(screen,"load_vost_motion_sequence",return_value=source), patch.object(screen,"digest",return_value="b"*64), patch.object(screen,"write_json") as write, contextlib.redirect_stdout(io.StringIO()):
            screen.main()
        return write.call_args.args[1]

    def test_constant_change_rejects_cost_and_does_not_authorize_push(self):
        report=self.run_fake(True)
        self.assertEqual(report["status"],"FAIL_EFFICIENCY_NECESSARY_CONDITION")
        self.assertTrue(all(r["selected"]==30 for r in report["rows"]))
        self.assertFalse(report["push_condition_met"])

    def test_static_source_is_not_an_end_to_end_pass(self):
        report=self.run_fake(False)
        self.assertEqual(report["status"],"NEEDS_FULL_VALIDATION")
        self.assertFalse(report["end_to_end_pass"])
        self.assertEqual(report["detector_calls_executed"],0)
