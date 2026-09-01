# M17 generation-strategy reality gate

## Verdict

`SELECT_ONE_TINY_D1_VECTOR_2D_SLICE`.

Exactly one candidate passed every frozen feasibility gate: extend the existing
project-owned 2D renderer. This authorizes only a small M18 implementation slice. It
does not establish image realism, detector gain, synthetic-to-real transfer, movement
recognition, or household operation.

Blender and Kubric remain technically credible later options. They were not selected
because important integration, delivery, or dependency requirements were not established
under this gate—not because the tools were proven incapable.

## Frozen result matrix

`PASS` supports only the named feasibility requirement. `UNKNOWN` means the requirement
was not established by the repository or accessible official sources checked; it is
selection-ineligible but not a factual failure.

| Fatal feasibility gate | Existing vector 2D | Blender headless 3D | Kubric + licensed assets |
|---|---|---|---|
| Exact M16 D1 emission | PASS | UNKNOWN | UNKNOWN |
| Target/transition coverage | PASS | PASS | PASS |
| Protected split construction | PASS | PASS | PASS |
| Deterministic manifest/provenance | PASS | PASS | PASS |
| Public-repo and intended-use rights | PASS | UNKNOWN | PASS |
| Pinnable tool version | PASS | PASS | PASS |
| First slice within 8 working hours | PASS¹ | UNKNOWN | UNKNOWN |
| Complete substrate within 3 days | PASS¹ | UNKNOWN | UNKNOWN |
| Complete substrate no more than 20 GiB | PASS¹ | PASS | UNKNOWN |
| No paid, cloud, or private dependency | PASS | PASS | FAIL |

¹ Bounded engineering feasibility inferred from the existing small generator, oracle,
and lockfile. M18 must measure the actual output size and repeated-generation behavior;
these are not historical delivery-time measurements.

## Why the existing renderer passes

Repository inspection found an already working 640×360 project-owned renderer with
stable `key`, `bag`, and `sofa` identities. The key is 28×12 pixels: 336 of 230,400
pixels, or about 0.1458% of the frame, inside the frozen 0.1–1% target bucket. The
existing sequence also represents `key inside bag` and later `bag at sofa`, records a
seed and generator/config/output hashes, and previously produced byte-identical outputs
in two consecutive runs.

The remaining work is a coherent extension, not a new rendering stack: emit exact M16
D1 records, add explicit negative/unknown/occluded/truncated cases, assign protected
groups before rendering, and freeze a tiny output manifest. The project owns its source
artwork; repository code is MIT and the existing generated output is CC0-1.0.

## Why Blender is not selected now

Blender's official command-line documentation supports background execution and Python
automation. Its official license page says rendered artwork belongs to the user, while
scripts using Blender's Python API have GPL-compatibility implications when distributed.
The review did not install Blender, freeze an asset set, resolve how a `bpy` integration
would be packaged beside this MIT repository, implement an exact D1 translator, or prove
the eight-hour/three-day delivery bounds. Those are `UNKNOWN`, not evidence that Blender
cannot provide a better realism prior later.

Official sources checked:

- [Blender command-line documentation](https://docs.blender.org/manual/en/4.5/advanced/command_line/index.html)
- [Blender licensing](https://www.blender.org/about/license/)

## Why Kubric is not selected now

Kubric documents instance segmentation, depth, optical flow, object coordinates,
randomized multi-object scenes, and split control. That is the strongest documented
oracle-fidelity prior of the three. Its Apache-2.0 code and asset-manifest license fields
also provide a useful provenance basis; Google Scanned Objects documents 1,030 household
models under CC BY 4.0.

The canonical setup nevertheless pulls a container, its published dependency set
includes Google Cloud packages, and its asset workflow uses cloud storage. A pinned,
minimal, fully local route was not established, nor were the exact D1 adapter,
eight-hour/three-day bound, and total substrate size. This directly misses the frozen
no-cloud gate and leaves other fatal requirements unknown. A later gate may revisit
Kubric only after primary evidence identifies a small local runtime and local licensed
asset subset.

Official sources checked:

- [Kubric repository and getting started](https://github.com/google-research/kubric)
- [Kubric license](https://github.com/google-research/kubric/blob/main/LICENSE)
- [Kubric dependencies](https://github.com/google-research/kubric/blob/main/requirements.txt)
- [Kubric asset manifests](https://github.com/google-research/kubric/blob/main/docs/source/X_assets.rst)
- [Kubric Blender renderer](https://github.com/google-research/kubric/blob/main/kubric/renderer/blender.py)
- [Google Scanned Objects publication](https://research.google/pubs/google-scanned-objects-a-high-quality-dataset-of-3d-scanned-household-items/)
- [Google Scanned Objects release note](https://research.google/blog/scanned-objects-by-google-research-a-dataset-of-3d-scanned-common-household-items/)

## Hostile review

- Vector artwork can make the oracle perfect while teaching a detector little about real
  homes. M18 therefore proves substrate mechanics only; a later frozen realism/transfer
  gate must decide whether any training is worth running.
- Exact generated boxes are not physical truth, and reference transitions are not
  `MovementCandidate`, `ClaimCandidate`, or `AcceptedClaim` values.
- A deterministic byte manifest does not establish realism, source authenticity, or
  deployment suitability.
- The selected strategy must not modify the existing B1 golden replay or its hashes.
- Blender/Kubric richness is not a reason to carry their integration cost before the
  smallest project-owned route has been falsified.

## Claim ledger

| Claim | Evidence | Permissible wording | Unsupported extension |
|---|---|---|---|
| M17-C1 | Existing generator source and manifest | The current renderer already has stable entities, a 0.1458% key, two reference transitions, and hash provenance | It already emits the full M16 D1 dataset contract |
| M17-C2 | Frozen matrix and official documentation | Exactly one candidate passed every M17 feasibility gate | It is the most realistic or highest-accuracy generator |
| M17-C3 | Official Blender/Kubric sources | Both alternatives document richer rendering/annotation capabilities | Either will improve the whole-home detector |
| M17-C4 | Bounded selection | One tiny vector D1 implementation slice is justified | Training, detector replacement, live capture, or household use is authorized |

## Next gate

M18 freezes and implements exactly one tiny project-owned vector dataset: three protected
source groups with 18 image/annotation pairs, exact M16 D1 semantics, required visibility
and transition cases, and deterministic byte manifests. It must preserve the old golden
replay unchanged and stop before any detector load or training.

