# M14 detector scientific-priority reality gate

## Verdict

`STOP_MODEL_SWAPPING` with normal completion.

Neither `dfine-medium-coco` nor `rt-detrv2-small-coco` establishes a materially
stronger, same-protocol and target-relevant prior than the detector path already
rejected on the frozen VOST development sequence. No model, VOST/VISOR media,
development source, reserved source, or test source was downloaded or loaded.

This is a bounded decision to stop the current off-the-shelf tournament. It is not a
claim that either architecture is poor, that no detector can work, or that target-domain
training will succeed.

## Frozen rule and discovered coverage gap

The pre-result contract named exactly D-FINE Medium, RT-DETRv2 Small, and
`STOP_MODEL_SWAPPING`. It froze a `+3.0` gain on either AP75 or AP-small with at most a
`1.0` decline on the other, a `2.5×` simultaneous cost ceiling, author-issued immutable
artifacts, explicit license disposition, a safe offline loader, and no cross-paper
metric filling.

The contract encoded D-FINE Small as its numeric reference, but the already recorded
Goal and `PROJECT_STATE.md` also required comparison with the failed RF-DETR Small
target screen. That comparator was accidentally omitted from the TOML. Thresholds were
not changed after research. Instead, the omission is recorded as
`FAIL_CLOSED_SCOPE_GAP`: passing only the D-FINE-S subcomparison cannot establish the
scientific priority that the Goal required.

## Primary evidence

The [D-FINE ICLR paper](https://proceedings.iclr.cc/paper_files/paper/2025/file/6cf58a87e3097e7d1f9be3e8693a93de-Paper-Conference.pdf)
reports the following COCO-only, 640-pixel same-family comparison:

| Profile | AP | AP50 | AP75 | AP-small | Params | GFLOPs | Published latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| D-FINE-S | 48.5 | 65.6 | 52.6 | 29.1 | 10.2M | 25.2 | 3.49 ms |
| D-FINE-M | 52.3 | 69.8 | 56.4 | 33.2 | 19.2M | 56.6 | 5.55 ms |

D-FINE-M therefore passes the narrow D-FINE-S numeric subgate: AP75 is `+3.8`,
AP-small is `+4.1`, and the parameter/FLOP/latency ratios are about
`1.88×/2.25×/1.59×`. The official repository currently lists `5.62 ms`; both latency
figures are T4, batch-one, TensorRT FP16 measurements and neither is this laptop's
PyTorch p95.

An author-owned immutable [D-FINE-M checkpoint revision](https://huggingface.co/Peterande/D-FINE/blob/a5f35932343b83c470bfe8659b439108080e6206/dfine_m_coco.pth)
identifies `dfine_m_coco.pth`, SHA-256
`b44a7586bf490858c7b8bce9e44bd025cb88724df9a07a8deb3ae1c12e608195`, with an
Apache-2.0 model-card declaration. It remains a pickle-container `.pth`; a strict local
`weights_only=true` load of these exact bytes was not attempted in M14. Artifact
identity therefore exists, while safe-loader compatibility remains unverified.

The [RT-DETRv2 paper](https://arxiv.org/abs/2407.17140) reports only AP `47.9` and AP50
`64.9` for its original S result. The later official repository/result is `48.1/65.1`,
and its author release log reports AP75 `52.1` and AP-small `30.2`. Relative to
D-FINE-S, those last two values are `-0.5/+1.1`, so RT-DETRv2-S fails the frozen
material-gain rule. Its author GitHub release is mutable and publishes no digest; the
official loader also exposes ordinary `torch.load`/URL-loading behavior. A community
Safetensors conversion cannot inherit author-artifact status or benchmark parity.

The [RF-DETR paper](https://arxiv.org/html/2511.09554v2) reports RF-DETR Small at AP
`52.9`, AP50 `71.9`, AP75 `57.0`, and AP-small `32.0`. Those figures come from a
different paper/artifact protocol and are context, not a paired numeric benchmark.
Even as directional context, D-FINE-M is `-0.6` on AP and AP75 and only `+1.2` on
AP-small; RT-DETRv2-S is weaker still. More importantly, the exact RF-DETR Small path
already failed the local development recall gate and recovered `0/11` of the prior
localization-miss frames. No same-protocol evidence shows either new candidate is
materially more likely to reverse that outcome.

COCO AP-small is not the local 0.1–1% mask-box bucket, COCO AP75 is not a causal proxy
for the 11 RetinaNet-conditional misses, and none of the sources tests fixed-camera
indoor transfer. Reusing the same 51 development frames for another adaptively selected
model would further weaken the evidence. The independent mask-box oracle tracker also
recorded 16 ID switches, so detector replacement alone cannot clear the observation
path.

## Candidate decisions

| Candidate | Narrow published gate | Trust / loader | Goal-level relevance | Decision |
|---|---|---|---|---|
| D-FINE-M COCO-only | Pass versus D-FINE-S | Immutable author bytes found; safe load unverified | No material same-protocol advantage over the failed target-screened path | `REJECT_DFINE_M_PRIORITY` |
| RT-DETRv2-S COCO-only | Fail (`-0.5/+1.1`) | Mutable undigested author release; safe load unverified | No stronger target-relevant prior | `REJECT_RTDETRV2_S_PRIORITY` |

The D-FINE-M artifact is therefore not downloaded merely to prove that another larger
DETR can load. Cost compatibility was not the active blocker in M12 or M13.

## Claim ledger

| Claim | Evidence class | Permissible wording | Unsupported extension |
|---|---|---|---|
| M14-C1 | Same-paper generic benchmark | D-FINE-M materially improves over D-FINE-S on COCO AP75/AP-small within the cited table | It will improve VOST, indoor, fixed-camera, or household detection |
| M14-C2 | Author artifact metadata | One immutable D-FINE-M `.pth` and hash are identifiable | The checkpoint was safely loaded, locally benchmarked, or cleared for every downstream use |
| M14-C3 | Author result log | RT-DETRv2-S does not meet the frozen AP75/AP-small gain rule | RT-DETRv2-S is generally inferior or cannot be useful after target training |
| M14-C4 | Cross-paper plus local context | Neither candidate supplies a material same-protocol prior over the failed RF-DETR path | COCO differences predict the reused 51 frames or intended household domain |
| M14-C5 | Bounded decision | Stop the current off-the-shelf model tournament and design a target-domain gate | No off-the-shelf detector can work, or target-domain training will work |

## Next gate

Proceed only to a no-media `TARGET_DOMAIN_DATA_TRAINING_REALITY_GATE`. First determine
whether a lawful, source-separated substrate can measure the intended fixed-camera
small-object/container problem. Training remains unavailable until that gate freezes
its estimand, split integrity, recipe, stopping rule, and one-time validation/test
policy. Tracker replacement remains a separate co-gate.
