# M15 target-domain substrate reality gate

## Verdict

`ZERO_ELIGIBLE` and
`PIVOT_TO_SYNTHETIC_OR_PROJECT_GENERATED_TARGET_DATA_DESIGN`, with normal
completion.

The frozen gate required every eligibility dimension to pass. `FAIL` means accessible
official evidence contradicted or could not satisfy the named requirement. `UNKNOWN`
means the requirement was not established in the accessible official sources checked.
Both are selection-ineligible, but they are not the same factual claim. No tie-break was
used because no candidate passed every required gate.

This decision does not say that these datasets have no research value. It says none is
currently a lawful, obtainable, source-separable, detector-ready substrate for the
specific fixed-camera small-object and temporal estimand under the three-day cost gate.
No media, annotation archive, model, VOST/VISOR source, reserved source, or test source
was downloaded or loaded.

## Candidate evidence

| Candidate | Useful official evidence | Fatal frozen-gate evidence | Decision |
|---|---|---|---|
| Home Action Genome (HOMAGE) | Indoor synchronized ego plus third-person sequences; action, object, relationship, and sequence-split semantics; explicit non-commercial academic/competition terms | Scene graphs sample only 3 or 5 frames per atomic-action interval and cover the actor plus interacted objects, not every evaluated frame or all scored instances. The official download page says video/audio are available while other modalities will be released; eligible annotation access, one-day turnaround, manifestability, and a <=20 GiB subset are not established | Ineligible |
| CAD-120 | Mounted exocentric RGB-D, activity-involved object tracks, subactivities, affordances, and leave-one-subject-out evaluation | Only every 50th frame was manually boxed; intermediate boxes were produced by SIFT/depth tracking. Accessible official use terms were not established, and the author-cited acquisition endpoint is unavailable | Ineligible |
| Watch-n-Patch | Exocentric Kinect-v2 video, explicit dimensions, temporal actions, interacting-object types, subjects, offices, and kitchens | The paper's object regions are algorithm-derived interaction features, not released per-frame reference boxes for all evaluated instances. Accessible official use terms, a current official acquisition path, and a source-independent split manifest are not established | Ineligible |

HOMAGE is the closest product-story match, and CAD-120 is the closest compact
activity/affordance detector substrate. Those similarities are not permission to relax
the frozen localization, terms, acquisition, or split requirements.

## Primary sources reviewed

- HOMAGE [dataset page](https://homeactiongenome.org/),
  [download page and terms](https://homeactiongenome.org/download.html), and
  [author paper](https://arxiv.org/pdf/2105.05226).
- CAD-120 [author/institution paper](https://www.cs.cornell.edu/~hema/papers/activities_IJRR2013.pdf)
  and the author-cited `http://pr.cs.cornell.edu/humanactivities/data.php` endpoint.
- Watch-n-Patch [author/institution paper](https://www.cs.cornell.edu/~chenxiawu/papers/wpatch_wu_cvpr2015.pdf),
  [author page](https://www.cs.cornell.edu/~chenxiawu/), and the author-cited
  `http://watchnpatch.cs.cornell.edu` endpoint.

Third-party mirrors and summaries were not used to cure missing official provenance,
rights, or acquisition evidence.

## Important interpretation limits

- HOMAGE's terms permit competition or non-commercial academic use and prohibit
  unauthorized access and redistribution. They do not make the data open or authorize
  publishing its bytes with this repository.
- CAD-120 and Watch-n-Patch are not described as having no license. The bounded claim
  is that suitable use terms were not established from the accessible official material
  checked in this gate.
- CAD-120 has boxes across frames, but most are tracker-derived rather than independent
  manual reference boxes. That can be useful for activity research while still being a
  weak detector/tracker oracle.
- Interaction-only annotations are not exhaustive household inventories. Unlabeled
  visible objects cannot automatically be scored as detector false positives.
- Published action recognition, affordance, or scene-graph results do not establish the
  frozen recall, AP50:95, small-area recall, or false-positive-per-frame measures.
- No candidate establishes passive household transfer, 24/7 operation, containment or
  zone truth, or intended-product performance.

## Claim ledger

| Claim | Evidence class | Permissible wording | Unsupported extension |
|---|---|---|---|
| M15-C1 | Official paper and dataset metadata | All three candidates include exocentric indoor activity video and interaction semantics to different degrees | All three are detector-ready or fixed-home representative |
| M15-C2 | Official paper annotation protocols | HOMAGE is sparse 3/5-frame interaction localization; CAD-120 manually boxes every 50th frame and derives intermediate tracks; Watch-n-Patch does not establish per-frame reference object boxes | Any is a dense, exhaustive, independent detector oracle |
| M15-C3 | Official terms/acquisition pages checked at gate time | HOMAGE has restrictive non-commercial academic/competition terms; suitable CAD-120 and Watch-n-Patch terms were not established | The latter two have no license, or HOMAGE is open for redistribution |
| M15-C4 | Deterministic frozen-gate application | No candidate passes every required eligibility gate | No public dataset can ever support the project |
| M15-C5 | Bounded decision | Pivot to a no-media synthetic/project-generated target-data design gate | Recording household data, generating media, training, or operation is authorized |

## Discovered specification gap

The M15 contract named per-frame instance localization and the target metrics, but did
not make every oracle property executable. Before generating or acquiring anything,
the next gate must freeze:

- `frame x persistent object instance` as the detection unit and source sequence or
  movement episode as the temporal unit;
- dense/exhaustive reference boxes for every scored instance on every evaluated frame;
- stable IDs, negative frames, duplicate predictions, occluded/absent/truncated/unknown
  semantics, and complete-frame accounting;
- grouping of participant, house/room, session, camera, time, and synchronized views;
- perfect, empty, duplicate, and wrong-class synthetic prediction oracles.

This is a fail-closed clarification for the next gate, not a post-result change to the
M15 candidate thresholds.

## Next gate

Run M16 as a no-media `D1_TARGET_LABEL_ORACLE_FEASIBILITY` gate. It may define a small
synthetic-only annotation schema, fake predictions, and deterministic metric/split
contract tests. It may not render or download media, record a scene, load a detector,
train, inspect reserved sources, create movement candidates or accepted claims, connect
live/private/cloud/action capability, or enable `OPERATE`.
