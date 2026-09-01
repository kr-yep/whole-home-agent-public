# M13 D-FINE Small synthetic engineering qualification

## Verdict

`ENGINEERING_COMPATIBLE_SYNTHETIC_ONLY` and
`STOP_DFINE_SMALL_NO_DEVELOPMENT_SCREEN`.

The single valid checkpoint-load attempt passed the two declared engineering cost
checks on one generated RGB input: detector p95 was `58.8077 ms` and peak allocated
VRAM was `104,530,432` bytes. All 51 measured calls produced the same canonical digest,
and the Python socket guard recorded no connection attempt.

This does **not** earn a VOST development screen. The artifact is a community
Safetensors conversion, not a D-FINE-author release, and no parity receipt binds these
converted bytes to the original checkpoint. The available published small-object and
localization prior is also too weak to justify another adaptive model screen by itself.

## Candidate and trust boundary

M13 froze exactly one candidate:

- repository: [`ustc-community/dfine-small-coco`](https://huggingface.co/ustc-community/dfine-small-coco/tree/f79e65b5fbb33ceb9d3ebba042955d7410c608f8);
- revision: `f79e65b5fbb33ceb9d3ebba042955d7410c608f8`;
- `model.safetensors`: `41,497,620` bytes, SHA-256
  `a144baff3a27bfd538fe37b11fa8d4fca5744b8c054b5301e7c699a1379cd18f`;
- Transformers `5.16.1`, official tag commit
  `fb405cdf1bb6fa7b85ac8871b5d8a8b1376f5a3c`, pinned wheel SHA-256
  `2f2d5b98a5ad3718713653734298fa620754ed683702a635ebb587df3ed29c7e`;
- declared model-card license: Apache-2.0, used locally for evaluation only; weights
  remain ignored and the project makes no redistribution or commercial-clearance
  claim.

The normal loader accepts only the verified local snapshot with
`local_files_only=true`, `trust_remote_code=false`, and `use_safetensors=true`. No
pickle fallback, mutable alias, remote code, automatic device map, or downloader is
available. The [Transformers D-FINE documentation](https://huggingface.co/docs/transformers/model_doc/d_fine)
documents this library implementation; it does not turn the community conversion into
an author-issued checkpoint.

The author-owned `.pth` was rejected for this bounded integration because it would add
pickle parsing and an un-packaged upstream source tree whose package initializer pulls
in training and COCO-evaluation dependencies. Although `weights_only=true` loaded its
tensor state in a separate qualification check, that route had more total integration
and maintenance complexity. No claim is made that the selected conversion is
numerically equivalent to it.

## Frozen adapter semantics

- Input is RGB `uint8` HWC, resized to exactly `640×640`, rescaled by `1/255`, with no
  normalization, padding, or aspect-ratio preservation.
- The output contract is dense COCO `0..79`: `39 -> bottle`, `41 -> cup`, `43 -> knife`,
  `44 -> spoon`, `45 -> bowl`, `70 -> toaster`, and `72 -> refrigerator`.
- The upstream postprocessor is called with threshold `0.0`; the adapter applies the
  canonical inclusive `confidence >= 0.25` rule itself.
- Boxes are original-frame absolute `xyxy`, checked for finite values, clipped, and
  dropped if degenerate. Results are canonically sorted before leaving the adapter.
- Transformers, Torch, model outputs, credentials, and generic tools do not cross the
  detector port. Importing the adapter performs no model, GPU, filesystem, or network
  operation.

Contract tests cover artifact-before-runtime validation, dense-versus-sparse class
semantics, the exact threshold boundary, output shape and finite-value rejection,
clipping, deterministic ordering, import-time isolation, one-attempt marking, generated
fixture identity, and the nearest-rank p95 rule.

## Attempt integrity

The first launch failed at the read-only Git revision precheck because the elevated
process did not trust the checkout as a safe directory. It occurred before the attempt
marker and before any checkpoint load. Commit
`a01799b52ce4ffeeb239bbe6eb397afa2ff64bcf` made that Git query explicitly local and
read-only; the worktree was then clean and the sole real-load attempt began.

- clean code revision: `a01799b52ce4ffeeb239bbe6eb397afa2ff64bcf`;
- frozen config SHA-256:
  `840b5e38dffbce19982957822f7552d3159e42c20513c6df9c4c97eccbc60982`;
- ignored local receipt SHA-256:
  `0b146474c8269df7e7ef87dd41be99c179f4d015df5be6fdc9816633000539f8`;
- generated input: in-memory `960×540` RGB, SHA-256
  `c0ef097cb129dbaaac0963d6a1e81341280584480308621de26636c7b49c0b98`;
- one excluded warm-up and exactly 51 measured complete adapter calls;
- CUDA 0, FP16, batch 1, deterministic algorithms, no compile;
- no VOST, VISOR, household, private, live, camera, training, movement, claim, cloud,
  action, or `OPERATE` capability.

The local environment was Python `3.12.13`, torch `2.11.0+cu128`, torchvision
`0.26.0+cu128`, Transformers `5.16.1`, Safetensors `0.8.0`, CUDA `12.8`, cuDNN `91900`,
and an NVIDIA GeForce RTX 4070 Laptop GPU. The repository lock resolves a different
cross-platform Torch stack and is explicitly recorded as not reproducing this GPU
environment.

## Results

| Check | Observation | Gate | Result |
|---|---:|---:|---|
| Complete measured calls | 51 | exactly 51 | Pass |
| Canonical output digests | 1 unique | exactly 1 | Pass |
| Detector p50 | 34.4482 ms | descriptive | — |
| Detector p95, nearest rank | 58.8077 ms | `< 100 ms` | Pass |
| Maximum measured latency | 62.4707 ms | descriptive | — |
| Peak allocated VRAM | 104,530,432 B | `< 1,073,741,824 B` | Pass |
| Python socket attempts | 0 | 0 | Pass |
| Public/private media bytes read | 0 | 0 | Pass |

The generated image happened to yield one retained detection on every measured call.
That count is used only to exercise deterministic output translation. It has no ground
truth and therefore supplies no accuracy, recall, localization, or semantic evidence.

## Why engineering passage is not scientific priority

The [official D-FINE paper](https://proceedings.iclr.cc/paper_files/paper/2025/file/6cf58a87e3097e7d1f9be3e8693a93de-Paper-Conference.pdf)
reports D-FINE-S at COCO AP `48.5`, AP50 `65.6`, AP75 `52.6`, and AP-small `29.1` at
640-pixel input. An earlier revision of this report incorrectly said RT-DETRv2-S was
higher on both AP75 and AP-small. The RT-DETR authors' release log reports AP75 `52.1`
and AP-small `30.2`: lower by `0.5` on AP75 and higher by only `1.1` on AP-small. That
correction further weakens, rather than creates, a localization-oriented priority
claim. None of these generic COCO figures show that D-FINE-S will recover M11's misses
or beat the already rejected RF-DETR Small path.

M11's categories were conditional diagnostics from the incumbent RetinaNet path: 30
confidence-filtered frames and 11 localization-miss frames. They are not intrinsic
causal labels. Repeatedly choosing models after observing the same 51 frames also risks
adaptively fitting candidate selection to that sequence even when thresholds remain
frozen.

## Claim ledger

| Claim | Evidence class | Permissible wording | Unsupported extension |
|---|---|---|---|
| M13-C1 | Integrity | One immutable Safetensors snapshot loaded locally with the declared closed options | It is an official D-FINE-author checkpoint or parity with the original is verified |
| M13-C2 | Behavioral / synthetic | The full adapter was deterministic over 51 repeated generated-input calls | It is accurate, stable over time, or correct on any real object |
| M13-C3 | Cost / one environment | This run's p95 and allocated VRAM passed the absolute engineering bounds | The detector is real-time, lightweight, 24/7-ready, or faster on another input/environment |
| M13-C4 | Recorded boundary | No public/private media bytes or recorded socket attempts occurred in this run | All possible process/OS network routes were independently isolated |
| M13-C5 | Decision | Engineering compatibility is established; scientific priority is not | Compatibility authorizes a VOST screen, product integration, tracking, or claims |

## Decision and next question

Do not load VOST for D-FINE Small. Record
`STOP_DFINE_SMALL_NO_DEVELOPMENT_SCREEN` while retaining the adapter as a closed,
replaceable engineering seam.

The next bounded Goal should stop model roulette by deciding between two paths using
only already published facts and existing aggregate receipts:

1. identify a candidate with materially stronger, independently relevant small-object
   prior than the failed RF-DETR Small path; or
2. conclude that off-the-shelf replacement evidence is exhausted and open a separate
   target-domain data/training reality gate capped by the existing 20-epoch/patience-5
   rule.

That decision must not read VOST/VISOR media, tune on reserved/test data, train, or
create movement or household claims.
