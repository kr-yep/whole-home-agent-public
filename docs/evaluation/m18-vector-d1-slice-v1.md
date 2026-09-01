# M18 tiny vector D1 slice

## Verdict

`PASS_TO_REALISM_TRANSFER_GATE_DESIGN` within the project-generated vector-artwork
envelope.

The repository now contains one deterministic, image-backed D1 substrate with exact
M16 oracle semantics. This proves the generator → image/annotation pairing → provenance
manifest → protected split → oracle seam. It does not prove that the images are realistic
or that training on them improves a detector on a real home.

## Frozen substrate

| Property | Result |
|---|---:|
| Resolution | 640×360 |
| Protected source groups | 3: development, validation, test |
| Frames per group | 6 |
| PNG/annotation pairs | 18 |
| M16 oracle fixture | 1 |
| Non-manifest outputs | 37 |
| Total non-manifest bytes | 103,957 |
| Frozen maximum | 5,242,880 |

Every split contains the same six semantic roles but distinct asset, background, layout-
seed, room, camera/time, and synchronized-view identities:

1. visible key at the source;
2. truncated visible key near the bag;
3. known occluded key with an `inside` reference relation;
4. visible key at the sofa with an `at_zone` reference relation;
5. explicit scored negative with the key `ABSENT`;
6. an unscored `UNKNOWN` frame.

The full fixture contains six visible, three truncated, three occluded, three absent, and
three unknown key records. It has three containment and three location reference
transitions. The full visible key is 28×12 = 336 pixels, or 0.1458% of a 640×360 frame,
so every split has a target inside the frozen 0.1–1% bucket.

Reference annotations and relations are synthetic test truth. They are not physical
observations, `MovementCandidate`, `ClaimCandidate`, or `AcceptedClaim` values.

## Reproducibility and provenance

The canonical manifest records the project-owned CC0-1.0 use class, Pillow version,
contract and generator hashes, source-group seeds, and path/size/SHA-256 for every image,
frame annotation, and M16 fixture. The manifest deliberately does not self-hash.

Two independent clean generations produced identical bytes for every non-manifest
output and the manifest, and those bytes matched the committed substrate. The old B1
generator, MP4, annotation, and manifest retained their four frozen SHA-256 values.

Key identities:

- contract SHA-256: `2675f4f99aceb2064ab68ea4e656200f10cf07e76e39ced1620d87fd26adec9a`;
- generator SHA-256: `27aa7fe14fa4fb4654fc7ad601470420b92a81e3198cb8e40d8d36367b6c2472`;
- manifest SHA-256: `68a6e873c210626736a9e6c71e6d2829e205b35d1d27cbbf8d0dc1f6ad8193a9`;
- M16 fixture SHA-256: `20ea1209acc64aad987d85482ce3e17f625c78c068c3d0063c1950ff1a78bea2`.

## Verification

- Contract commits: `0f41a75`, then the pre-generation scene-parameter freeze
  `709f37e8e7cb06ba4f4686b2043f498c4224a2d3`.
- Clean implementation revision:
  `a7ea0b8582558c293307e727c703bcb059c6613a`.
- Focused suite: `12/12` passed before result recording.
- Clean implementation-revision suite: `161/161` passed under Python 3.12.13.
- Clean implementation-revision public audit: 198 files / 396 snapshots, zero
  violations, `operate_enabled: false`.
- Final result suite: `164/164` passed; final public audit: 201 files / 402
  snapshots, zero violations, `operate_enabled: false`.
- Four frames were visually inspected across visible, truncated, occluded, and
  destination roles.

## Hostile review

- Exact labels are expected because the renderer owns the pixels; they do not measure
  annotation noise or real perception.
- Split isolation prevents byte/source leakage but does not create meaningful visual
  diversity from three palettes and layouts.
- The text, simple shapes, and clean backgrounds may become shortcuts for a detector.
- Eighteen images are a schema/conformance slice, not a training dataset.
- Byte identity is currently verified with Pillow 12.3.0 and in CI; it is not a promise
  across arbitrary encoder versions.
- No detector was loaded and no AP, recall, latency, transfer, or tracking claim follows.

## Claim ledger

| Claim | Evidence | Permissible wording | Unsupported extension |
|---|---|---|---|
| M18-C1 | Manifest and pairing tests | The repo contains 18 hash-pinned project-generated PNG/annotation pairs | It contains sufficient training diversity |
| M18-C2 | M16 loader and split tests | All three groups load under M16 and protected groups do not cross splits | Real-world ground truth has the same completeness |
| M18-C3 | Two clean generations | The frozen local toolchain reproduced the committed bytes | Every Pillow/platform version will reproduce them |
| M18-C4 | Bounded pass | It is justified to design a real transfer gate | Training or real-home operation is authorized |

## Next gate

M19 must find, without acquisition, at most one real indoor small-household-object
evaluation substrate that can serve as a transfer oracle. It must use official sources,
keep unknown/unlabelled objects out of negative evidence, preserve source groups, and
prove a bounded lawful acquisition route before any data download or training.
