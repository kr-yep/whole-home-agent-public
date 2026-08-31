"""Conservative B1 binding, temporal inference, and query conformance."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from whole_home_agent.adapters.recorded_perception_source import (
    RecordedPerceptionCandidateSource,
)
from whole_home_agent.adapters.synthetic_color import (
    SyntheticColorDetector,
    load_synthetic_color_config,
)
from whole_home_agent.adapters.tracking import IoUTracker
from whole_home_agent.binding import BoundFrame, BoundObject, ManifestEntityBinder
from whole_home_agent.model import (
    ClaimOperation,
    EpistemicStatus,
    Predicate,
    ProducerRef,
    QueryRequest,
    QueryStatus,
    RunStatus,
    SourcePosition,
    TimestampBasis,
)
from whole_home_agent.orchestrator import run_source
from whole_home_agent.perception import BoundingBox, Detection, TrackObservation
from whole_home_agent.relation_inference import (
    RelationRuleConfig,
    TemporalRelationEngine,
    load_relation_rule_config,
)
from whole_home_agent.relation_evaluation import (
    evaluate_relations,
    load_relation_evaluation_config,
)
from whole_home_agent.video_manifest import load_video_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT / "examples" / "media" / "generated" / "key_bag_sofa_v1.manifest.json"
)
COLOR_CONFIG = ROOT / "configs" / "perception" / "synthetic-color-v1.toml"
RULE_CONFIG = ROOT / "configs" / "perception" / "relation-rules-v1.toml"
RELATION_EVAL_CONFIG = ROOT / "configs" / "perception" / "relation-eval-v1.toml"
HAS_VIDEO = importlib.util.find_spec("av") is not None and importlib.util.find_spec(
    "numpy"
) is not None
PRODUCER = ProducerRef("fake-detector", "1", "a" * 64, "b" * 64)


def _position(index: int) -> SourcePosition:
    return SourcePosition(
        source_sequence=index,
        source_offset=index,
        timestamp_basis=TimestampBasis.MEDIA_PTS,
        frame_index=index,
        pts=index,
        time_base_numerator=1,
        time_base_denominator=10,
    )


def _object(index: int, entity_id: str, box: tuple[float, float, float, float]):
    return BoundObject(
        entity_id=entity_id,
        label=entity_id,
        bbox=BoundingBox(*box),
        confidence=0.9,
        track_id=f"track-{entity_id}",
        position=_position(index),
    )


def _frame(
    index: int,
    *,
    key: tuple[float, float, float, float] | None,
    bag: tuple[float, float, float, float] | None,
    sofa: tuple[float, float, float, float] | None,
) -> BoundFrame:
    values = {"key": key, "bag": bag, "sofa": sofa}
    objects = tuple(
        _object(index, entity_id, box)
        for entity_id, box in sorted(values.items())
        if box is not None
    )
    return BoundFrame(
        position=_position(index),
        objects=objects,
        absent_entity_ids=tuple(
            entity_id for entity_id, box in sorted(values.items()) if box is None
        ),
        abstentions=(),
    )


class TemporalInferenceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_relation_rule_config(RULE_CONFIG, repository_root=ROOT)

    def engine(self) -> TemporalRelationEngine:
        return TemporalRelationEngine(
            self.config,
            source_id="synthetic-unit",
            detector_producer=PRODUCER,
            entity_map=(("bag", "bag"), ("key", "key"), ("sofa", "sofa")),
        )

    def test_take_out_requires_confirmed_reappearance_and_retracts_inside(self):
        engine = self.engine()
        bag = (10, 10, 30, 30)
        sofa = (60, 10, 100, 50)
        frames = (
            _frame(0, key=(15, 15, 20, 20), bag=bag, sofa=sofa),
            _frame(1, key=(16, 15, 21, 20), bag=bag, sofa=sofa),
            _frame(2, key=None, bag=bag, sofa=sofa),
            _frame(3, key=None, bag=bag, sofa=sofa),
            _frame(4, key=None, bag=bag, sofa=sofa),
            _frame(5, key=(35, 15, 40, 20), bag=bag, sofa=sofa),
            _frame(6, key=(36, 15, 41, 20), bag=bag, sofa=sofa),
        )
        candidates = tuple(
            candidate for frame in frames for candidate in engine.observe(frame)
        )
        self.assertEqual(
            [(item.operation, item.predicate) for item in candidates],
            [
                (ClaimOperation.ASSERT, Predicate.INSIDE),
                (ClaimOperation.RETRACT, Predicate.INSIDE),
            ],
        )
        self.assertTrue(
            all(item.epistemic_status is EpistemicStatus.ESTIMATED for item in candidates)
        )
        self.assertTrue(
            all(item.evidence_refs[0].quality == "perception_report" for item in candidates)
        )

    def test_disappearance_without_prior_containment_abstains(self):
        engine = self.engine()
        bag = (10, 10, 30, 30)
        sofa = (60, 10, 100, 50)
        for index in range(3):
            self.assertEqual(
                engine.observe(_frame(index, key=None, bag=bag, sofa=sofa)), ()
            )
        self.assertIn(
            "disappearance_without_containment_context",
            {item.reason for item in engine.abstentions},
        )

    def test_zone_requires_stationary_hold_not_overlap_alone(self):
        engine = self.engine()
        sofa = (50, 10, 100, 50)
        bag_boxes = (
            (50, 20, 60, 30),
            (55, 20, 65, 30),
            (60, 20, 70, 30),
            (60, 20, 70, 30),
            (60, 20, 70, 30),
            (60, 20, 70, 30),
        )
        emitted = [
            candidate
            for index, box in enumerate(bag_boxes)
            for candidate in engine.observe(
                _frame(index, key=(0, 0, 5, 5), bag=box, sofa=sofa)
            )
        ]
        zone_candidates = [
            item for item in emitted if item.predicate is Predicate.AT_ZONE
        ]
        self.assertEqual(len(zone_candidates), 1)
        self.assertEqual(zone_candidates[0].source_sequence, 5)

    def test_observation_gap_resets_confirmation_and_records_abstention(self):
        engine = self.engine()
        bag = (10, 10, 30, 30)
        sofa = (60, 10, 100, 50)
        engine.observe(_frame(0, key=(15, 15, 20, 20), bag=bag, sofa=sofa))
        engine.observe(_frame(1, key=(16, 15, 21, 20), bag=bag, sofa=sofa))
        self.assertEqual(engine.observe(_frame(10, key=None, bag=bag, sofa=sofa)), ())
        self.assertIn("observation_gap_exceeded", {x.reason for x in engine.abstentions})


@unittest.skipUnless(HAS_VIDEO, "video optional dependencies are not installed")
class RecordedPerceptionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_video_manifest(MANIFEST_PATH, repository_root=ROOT)
        width, height, targets = load_synthetic_color_config(
            COLOR_CONFIG, repository_root=ROOT
        )
        cls.detector = SyntheticColorDetector(
            width=width, height=height, targets=targets
        )
        cls.rules = load_relation_rule_config(RULE_CONFIG, repository_root=ROOT)

    def source(self, detector=None):
        return RecordedPerceptionCandidateSource(
            self.manifest,
            detector or self.detector,
            IoUTracker(),
            self.rules,
        )

    def test_rgb_replay_commits_two_estimates_and_resolves_key_to_sofa(self):
        source = self.source()
        result = run_source(source, replay_run_id="b1-relation-test")
        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertIsNotNone(result.session)
        session = result.session
        self.assertEqual(
            [
                (
                    item.source_sequence,
                    item.subject_id,
                    item.predicate,
                    item.object_id,
                    item.epistemic_status,
                )
                for item in session.accepted_claims
            ],
            [
                (37, "key", Predicate.INSIDE, "bag", EpistemicStatus.ESTIMATED),
                (68, "bag", Predicate.AT_ZONE, "sofa", EpistemicStatus.ESTIMATED),
            ],
        )
        answer = session.locate(
            QueryRequest(
                subject_id="key",
                world_scope=session.world_scope,
                replay_run_id=session.replay_run_id,
                as_of_source_sequence=session.projection_frontier,
            )
        )
        self.assertEqual(answer.status, QueryStatus.FOUND)
        self.assertEqual(answer.location_id, "sofa")
        self.assertEqual(answer.epistemic_status, "estimated")
        self.assertIn("estimated relations", answer.reason)
        self.assertEqual(len(answer.relation_path), 2)
        self.assertTrue(
            all(item.evidence_refs for item in session.accepted_claims)
        )
        self.assertTrue(source.diagnostics.completed)
        self.assertEqual(source.diagnostics.decoded_frames, 80)
        self.assertEqual(source.diagnostics.emitted_candidate_count, 2)
        self.assertIn(
            "disappearance_without_containment_context",
            {item.reason for item in source.diagnostics.abstentions},
        )
        evaluation = evaluate_relations(
            self.manifest,
            result,
            source.diagnostics.abstentions,
            source.diagnostics.completed,
            load_relation_evaluation_config(
                RELATION_EVAL_CONFIG, repository_root=ROOT
            ),
        )
        self.assertEqual(evaluation.quality.precision, 1.0)
        self.assertEqual(evaluation.quality.recall, 1.0)
        self.assertEqual(evaluation.quality.f1, 1.0)
        self.assertEqual(evaluation.quality.confirmation_lags_frames, (2, 3))
        self.assertTrue(evaluation.quality.answer_correct)

    def test_detector_failure_after_first_candidate_returns_no_partial_session(self):
        delegate = self.detector

        class FailingDetector:
            producer_ref = delegate.producer_ref
            device = delegate.device

            def detect(self, frame):
                if frame.position.frame_index >= 40:
                    raise RuntimeError("injected detector failure")
                return delegate.detect(frame)

            def peak_vram_bytes(self):
                return delegate.peak_vram_bytes()

            def runtime_metadata(self):
                return delegate.runtime_metadata()

        source = self.source(FailingDetector())
        result = run_source(source, replay_run_id="b1-failure-test")
        self.assertEqual(result.status, RunStatus.INCOMPLETE)
        self.assertIsNone(result.session)
        self.assertEqual(result.receipt.accepted_claim_count, 0)
        self.assertFalse(source.diagnostics.completed)

    def test_manifest_binder_abstains_on_two_instances_with_one_label(self):
        binder = ManifestEntityBinder(self.manifest)
        position = _position(0)
        detection = Detection(
            "key", 0.9, BoundingBox(0, 0, 5, 5), position, PRODUCER
        )
        bound = binder.bind(
            position,
            (
                TrackObservation("track-a", detection, 1),
                TrackObservation("track-b", detection, 1),
            ),
        )
        self.assertNotIn("key", bound.by_entity())
        self.assertEqual(bound.abstentions[0].reason, "ambiguous_instance")


if __name__ == "__main__":
    unittest.main()
