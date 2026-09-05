# Perception ablation v1 results — 2026-09-05

Executed the [frozen plan](perception-ablation-v1-plan.md): five arms, three
repeats each, 15 complete replays, no harness restart or parameter retuning.
[Raw results](perception-ablation-v1-results.json) include individual runs,
resolved configurations and source/code hashes. All quality outputs repeated
exactly. These are local working-tree results, not a pushed release.

Verification: 563 tests passed, zero failures/errors/skips, in the locked demo
environment (57.223 seconds). Four new tests cover frame-local IDs, direct-query
semantics, rejecting fast-but-wrong candidates, and percentile calculation.

## Observations

| Arm | Matched / expected events | Final key answer | Detector calls | Median replay |
| --- | --- | --- | --- | --- |
| Baseline | 2 / 2 | FOUND sofa | 80 | 2250 ms |
| Motion + periodic | 0 / 2 | UNKNOWN | 8 | 524 ms |
| No tracking | 2 / 2 | FOUND sofa | 80 | 2137 ms |
| Single confirmation | 2 / 2 | FOUND sofa | 80 | 2117 ms |
| Direct relations only | 2 / 2 | UNKNOWN | 80 | 2106 ms |

No arm emitted unmatched events on this one positive clip. This is not an estimate
of false-alarm rate on negative household footage. All arms decoded 80 frames;
the scheduler saves detector calls, not video decoding. Replay timings exclude
setup, evaluator and query execution. Therefore direct-only timing differences
are runtime variation, **not** measured query-speed improvements. Other small
timing differences also have no statistical significance claim.

Baseline confirmation lags were 2 and 3 frames (0.2 and 0.3 seconds at 10 fps).
Single-confirmation lags were 0 and 1 frame. Single-confirmation retains lookback
and historical state; it is not purely single-frame understanding.

## Decisions

1. **Do not enable the default scheduler for this relation pipeline.** It reduced
   detector calls 90% and replay time about 77%, but lost both events. The existing
   scheduler can wait 10 frames between anchors while the relation engine permits
   gaps of only 2; `observe()` resets transient evidence beyond that gap. The run
   recorded 7 abstentions. Sparse sampling and temporal confirmation need to be
   designed together, not solved by deleting the evidence check after this result.
2. **Tracking removal is inconclusive for household use.** In this bounded path,
   the binder resolves one instance per label and the relation engine never reads
   track IDs. Equality identifies that architectural limitation; this clip cannot
   evaluate same-class identity preservation. There was no detector-call saving.
3. **Keep temporal confirmation as the default.** Its removal lowered confirmation
   lag on the clean positive sequence but has not been compared on transient
   occlusion/negative footage. Existing regression tests still protect baseline
   take-out, disappearance, motion, observation gaps and ambiguous bindings; those
   tests are not a replacement for paired negative-video ablation.
4. **Keep relation-chain queries.** Removing traversal preserved the two detected
   events but lost the key-to-sofa answer. A direct relation can still say the bag
   is at the sofa; it cannot derive the hidden key's zone without chaining.

No efficiency arm met the predefined quality-and-cost criterion. This means no
production default should change on these results, not that optimization is
impossible. No new runtime restriction was added by this experiment.

## Next bounded work

First add independently labelled positive and negative indoor sequences (or a
separately versioned synthetic stress suite while indoor labels are unavailable).
Cover transient occlusion, true disappearance, stationary holds, take-out,
same-class objects and lighting changes. Freeze those cases before a second run.
Then compare a scheduler designed for pending-event confirmation against full
sampling; do not simply raise the permitted observation gap to force this clip
to pass. Separately test how an instance-aware binder uses tracking identity.

Real-camera accuracy, YOLO resource use, long-duration operation, real LLM quality
and physical device execution remain outside this result. No bootstrap interval
is reported because there is only one independent source clip.
