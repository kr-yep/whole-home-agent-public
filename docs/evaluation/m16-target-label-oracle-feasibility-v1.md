# M16 target-label-oracle feasibility

## Verdict

`PASS_TO_NO_MEDIA_GENERATION_STRATEGY_GATE` within the synthetic semantic-fixture
envelope.

The project can now distinguish scored frames, true negative frames, unknown frames,
scorable instances, non-scorable visibility states, persistent identity, and protected
source groups before delegating metric calculation to the existing evaluator. Every
frozen exact case and rejection case passed on clean implementation revision
`7c2f50425590de39cdb2d62ebb37d0ed9c529b30`.

This is a measurement-contract result. It does not establish useful images, detector or
tracker quality, synthetic-to-real transfer, container/zone truth, fixed-camera transfer,
movement recognition, or household operation.

## Smallest implemented boundary

`whole_home_agent.target_oracle` adds one no-media layer around the existing canonical
`BoundingBox`, `Detection`, and `evaluate_detection_quality` contracts. It contains no
CV, ML, storage, network, UI, device, or action dependency.

The layer owns only the concerns the old quality calculator could not safely infer:

- immutable source-group, reference-instance, frame, sequence, and reference-transition
  values;
- zero-based complete frame accounting and composite sequence/frame identity;
- `SCORED` versus `UNKNOWN` frames;
- `VISIBLE`, `TRUNCATED`, `OCCLUDED`, `ABSENT`, and `UNKNOWN` instance states;
- a rule that `UNKNOWN` cannot silently become a detector negative;
- stable instance labels, reference transition bounds, and duplicate/conflict rejection;
- protected participant, house/room, session, sequence, camera/time, and synchronized-
  view split groups;
- FP@0.50 divided by all and only scored frames.

Reference transitions are synthetic evaluation annotations. They are not product
`MovementCandidate`, `ClaimCandidate`, `AcceptedClaim`, action intent, or physical truth.

## Exact metric cases

The fixture has a 1000x1000 coordinate space, one 50x50 key target (0.25% frame area),
two scored frames including one explicit negative frame, one unknown frame, and one
synthetic reference transition.

| Case | AP50 | mAP50:95 | recall@0.50 | 0.1–1% recall | FP@0.50 | FP/scored frame |
|---|---:|---:|---:|---:|---:|---:|
| Perfect | 1.0 | 1.0 | 1.0 | 1.0 | 0 | 0.0 |
| Empty | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 |
| Duplicate | 1.0 | 1.0 | 1.0 | 1.0 | 1 | 0.5 |
| Wrong class | 0.0 | 0.0 | 0.0 | 0.0 | 1 | 0.5 |
| Bad localization | 0.0 | 0.0 | 0.0 | 0.0 | 1 | 0.5 |
| False positive on explicit negative frame | 1.0 | 1.0 | 1.0 | 1.0 | 1 | 0.5 |

Reversing input prediction order produced the same complete report. Empty predictions
produced a valid zero-recall result, not a failed or missing evaluation.

## Exact rejection cases

| Condition | Stable failure code | Why it fails closed |
|---|---|---|
| Prediction on an unknown frame | `PREDICTION_ON_UNSCORED_FRAME` | It cannot be silently ignored or counted as a negative |
| Duplicate frame identity | `DUPLICATE_FRAME_IDENTITY` | The FP denominator and temporal order would be ambiguous |
| Persistent instance changes class | `INSTANCE_LABEL_CONFLICT` | One identity cannot silently become another class |
| Any protected group crosses splits | `PROTECTED_GROUP_SPLIT_LEAKAGE` | Related sources cannot supply both selection and held-out evidence |
| Unknown instance appears in a scored frame | `SCORED_FRAME_HAS_UNKNOWN_INSTANCE` | Incomplete annotation cannot masquerade as exhaustive background |

## Reproducibility evidence

- Fixture:
  `examples/fixtures/evaluation/d1_target_oracle_v1.json`, SHA-256
  `8d217461fc387dc8895b9e32ed76e677202732af85aba8888bb926fe22fc4023`.
- Focused suite: `12/12` passed.
- Clean implementation revision suite: `138/138` passed under Python 3.12.13.
- Clean revision public audit: 147 files / 294 index-and-worktree snapshots, zero
  violations, `operate_enabled: false`.
- No new dependency, media generation/download, model load, training, private source,
  reserved source, movement candidate, semantic claim, or operational capability.

## Claim ledger

| Claim | Evidence class | Permissible wording | Unsupported extension |
|---|---|---|---|
| M16-C1 | Exact synthetic conformance fixture | The D1 scope layer produces the frozen metric results for six hostile fake-prediction cases | The metrics are correct for every external dataset or annotation convention |
| M16-C2 | Exact rejection tests | Unknown frames/instances, duplicate identities, label conflicts, and protected split leakage fail closed | Future adapters cannot contain a translation bug or incomplete label |
| M16-C3 | Source inspection and imports | The new module reuses canonical types/evaluator and adds no CV/ML/runtime dependency | The full evaluation stack has no optional dependencies or architectural debt |
| M16-C4 | Bounded pass decision | It is now reasonable to compare no-media data-generation strategies against this oracle | It is reasonable to generate media, train, or record a household now |

## Next gate

Run M17 as a no-media generation-strategy reality gate. Compare exactly the existing 2D
renderer extension, a procedural 3D/Blender route, licensed asset compositing, and
`STOP`. Select at most one only if it can emit this D1 contract with deterministic
source-group separation, legally publishable provenance, target interaction coverage,
and a three-day/20 GiB bound. No media generation or dependency installation belongs in
that comparison gate.
