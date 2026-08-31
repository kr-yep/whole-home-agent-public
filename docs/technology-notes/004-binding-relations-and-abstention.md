# Binding, temporal relations, and abstention

**Status:** implemented and tested for one hash-pinned generated replay only

## Boundary

The prerecorded adapter now composes one finite local pipeline:

```text
manifest → PTS frames → detector estimates → clip-local tracks
         → one-instance binding → temporal rules → ClaimCandidate
         → existing ClaimCommitter → pure projection → scoped query
```

Only the existing deterministic committer creates accepted claims. Detector boxes, track IDs, binding results, rule state, and abstentions remain reports or derived estimates; none is household authority or physical truth.

## Entity binding

`ManifestEntityBinder` accepts this baseline only when the manifest declares exactly one instance for each unique label. One matching track can bind to the declared entity. Zero detections means unobserved, not absent from the world. More than one matching detection is `ambiguous_instance`, and the entity is deliberately left unbound for that frame. Unknown labels are ignored with an abstention record.

This is enough for the fixed `key`, `bag`, and `sofa` story. It is not multi-object re-identification and does not create a persistent household identity.

## Temporal relation rules

All thresholds are validated from `configs/perception/relation-rules-v1.toml` and enter the relation producer config hash.

### `inside(key, bag)`

An assertion requires at least two recent observations where the key center is inside the bag box, followed by three unobserved-key frames while the bag remains observed and moves no more than the configured bound. This distinguishes a supported containment transition from generic disappearance. The assertion evidence spans the earlier contained observations through the confirmation frame.

If the key later reappears outside an observed bag for two consecutive frames, the engine emits an estimated retraction. A missing bag or ambiguous detection cannot prove take-out, so it abstains.

### `at_zone(bag, sofa)`

Box overlap alone is insufficient. The bag must overlap the sofa by the configured fraction and remain stationary for three observations. Moving inside the sofa region does not assert a settled location. A later low-overlap hold emits a retraction.

### Gaps and ambiguity

Frame order must increase. A gap larger than the configured window resets all in-progress confirmation streaks and records `observation_gap_exceeded`. Active accepted relations are not silently rewritten by a missing frame; only a separately confirmed retraction can end them.

The current color detector briefly misses the moving key before it reaches the bag. The rule records `disappearance_without_containment_context` at frame 28 and emits no claim there. This is the intended abstention behavior.

## End-to-end result

On `key_bag_sofa_v1.mp4`, the RGB pipeline emits exactly:

- frame 37: estimated `assert inside(key, bag)`, two frames after the annotated transition;
- frame 68: estimated `assert at_zone(bag, sofa)`, three frames after the annotated transition.

The frozen relation evaluator allows only non-negative confirmation lag up to five frames. On this single generated clip, event precision/recall/F1 and final `key → bag → sofa` answer accuracy are all `1.0`, with confirmation lags `(2, 3)` and one recorded abstention. These are fixture results, not evidence of indoor generalization.

The query returns `FOUND sofa`, epistemic status `estimated`, the two claim IDs, their source sequences, and a relation path. Each accepted claim retains its media PTS range, confidence, perception-evidence quality, relation rule artifact/config hash, and source hash. The answer says it was resolved from estimated relations rather than reported facts.

## Failure behavior

An injected detector failure after the first inferred candidate returns an `INCOMPLETE` receipt with no session and zero accepted claims. A caller cannot query partial state. Duplicate candidates remain idempotent, conflicting identities and cycles still fail at the unchanged B0 committer, and B0's frozen semantic hash remains its separate compatibility oracle.

## Calibration disclosure

While connecting M4, the synthetic sofa color tolerance was reduced from 20 to 10 because compressed pixels from another region widened the sofa box and caused a false early relation. This was a transparent adjustment on the manifest's `demo` split, not a frozen test result. With the revised demo-only config, AP50 remains `0.9604`, key recall `0.8857`, zero false positives, and mAP50:95 is approximately `0.5931` on the same clip. No real-home claim is attached to that tuning.

## Evidence boundary

This implementation supports one offline generated story and hostile synthetic unit cases for disappearance, ambiguity, gaps, motion, take-out, and failure. It does not support arbitrary objects, multiple same-class instances, occlusion truth, long-term identity, real homes, live sensing, or actions. `OPERATE` remains disabled.
