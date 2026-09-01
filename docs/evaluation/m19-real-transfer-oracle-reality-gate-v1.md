# M19 real transfer-oracle reality gate

## Verdict

`SELECT_YCB_VIDEO_BOP19_ACQUISITION_SLICE`.

HomebrewedDB and YCB-Video both passed every frozen feasibility gate through the
current BOP institutional distribution. The ordered tie-break reached its third and
final criterion: the annotated YCB-V BOP'19 route is 660 MB, versus 2.35 GB for the
smallest public annotated HB route. YCB-Video is therefore the unique bounded
selection.

This selection authorizes only one hash-pinned acquisition and M16 D1 translation
slice. It does not establish that the archive contains a 0.1–1% target, that generated
artwork improves a detector, that either pose dataset represents household movement,
or that any live/private/operational use is permitted.

## Frozen result matrix

`PASS` supports only the named feasibility requirement. `UNKNOWN` means accessible
official evidence did not establish the requirement; it remains selection-ineligible
without becoming a factual failure.

| Fatal gate | GMU Kitchens | HomebrewedDB | YCB-Video |
|---|---:|---:|---:|
| Official author/institution source | PASS | PASS | PASS |
| Terms cover non-commercial evaluation/training | UNKNOWN | PASS | PASS |
| Stable official acquisition | FAIL | PASS | PASS |
| No manual approval over one day | UNKNOWN | PASS | PASS |
| Real RGB indoor frames | PASS | PASS | PASS |
| Frame dimensions | UNKNOWN | PASS | PASS |
| Per-frame boxes or masks | PASS | PASS | PASS |
| Movable household labels | PASS | PASS | PASS |
| Stable instance identity | PASS | PASS | PASS |
| Complete annotations or safe scoring | UNKNOWN | PASS | PASS |
| Protected source groups | PASS | PASS | PASS |
| 0.1–1% verification path | UNKNOWN | PASS | PASS |
| Negative/unknown translation | UNKNOWN | PASS | PASS |
| Minimal annotated route <=5 GiB | UNKNOWN | PASS | PASS |
| Exact M16 D1 translation | UNKNOWN | PASS | PASS |
| First slice within 8 working hours | UNKNOWN | PASS¹ | PASS¹ |

¹ Bounded engineering feasibility, not a measured delivery-time result. The next gate
must stop if the actual acquisition or translation exceeds its limit.

## Why GMU Kitchens stops

The author/institution paper documents nine real RGB-D kitchen videos, eleven named
BigBird object instances, 2D boxes, and a three-fold scene split. That is useful
historical capability evidence.

The paper's official dataset URL now redirects to the general GMU Computer Science
home page. No current official download, dataset terms, archive size, dimension
contract, or exhaustive-label/negative policy was established. A mirror could not cure
those provenance and rights gaps under the frozen gate. Only the acquisition route is
recorded as a factual `FAIL`; the missing terms and semantics remain `UNKNOWN`.

Primary sources checked:

- [GMU Kitchens author paper](https://arxiv.org/abs/1609.07826)
- [author-cited dataset URL](https://cs.gmu.edu/~robot/gmu-kitchens.html)

## Why both BOP candidates pass

The current BOP dataset page is an institutional source for both candidates. It lists
HB under CC0-1.0 and YCB-V under MIT, provides public Hugging Face archives without an
application, and defines BOP-Classic data as real test images with labeled instances,
6D poses, amodal boxes, and modal masks.

The BOP format gives each annotation an `obj_id`, per-frame boxes, modal masks,
`px_count_all`, `px_count_visib`, and `visib_fract`. Its toolkit fixes the PrimeSense HB
and YCB-V dimensions at 640×480 and exposes scene and sensor identities. The detection
task assumes an arbitrary number of modeled instances without giving their presence to
the detector, and filters correctly detected instances below 10% visibility rather than
counting them as false positives. Together, these support a conservative class-scoped
translation:

- score only the modeled-object vocabulary in a fully parsed BOP frame;
- treat an absent selected modeled class as negative only inside that complete scope;
- mark unparseable frames and instances below the visibility threshold `UNKNOWN` or
  unscored;
- ignore unmodeled background objects instead of turning them into negatives;
- preserve BOP scene/image/object IDs in provenance and emit no relation or transition.

The 0.1–1% gate is a verification path, not a pre-observed positive: compute
`px_count_visib / (640 * 480)` after the next authorized acquisition and stop if no
eligible target falls in `[0.001, 0.01]`.

Official sources checked:

- [BOP datasets and current downloads](https://bop.felk.cvut.cz/datasets/)
- [BOP detection tasks](https://bop.felk.cvut.cz/tasks/)
- [BOP dataset format](https://github.com/thodan/bop_toolkit/blob/master/docs/bop_datasets_format.md)
- [BOP dataset parameters](https://github.com/thodan/bop_toolkit/blob/master/bop_toolkit_lib/dataset_params.py)
- [HB archive listing](https://huggingface.co/datasets/bop-benchmark/hb/tree/main)
- [HomebrewedDB paper](https://openaccess.thecvf.com/content_ICCVW_2019/papers/R6D/Kaskman_HomebrewedDB_RGB-D_Dataset_for_6D_Pose_Estimation_of_3D_Objects_ICCVW_2019_paper.pdf)
- [YCB-Video project](https://rse-lab.cs.washington.edu/projects/posecnn/)
- [YCB-Video paper](https://rse-lab.cs.washington.edu/papers/posecnn_rss18.pdf)
- [author toolbox, annotation format, and dataset license](https://github.com/yuxng/YCB_Video_toolbox)
- [author class list](https://github.com/yuxng/YCB_Video_toolbox/blob/master/classes.txt)
- [YCB-V archive listing](https://huggingface.co/datasets/bop-benchmark/ycbv/tree/main)

## Ordered tie-break

1. Annotation completeness and safe negatives: tie. Both selected routes use the same
   BOP object-localization and evaluation conventions.
2. Fixed or explicit camera relevance: tie. Both expose scene/camera grouping, but
   neither proves passive fixed-camera object movement.
3. Acquisition, translation, and storage cost: YCB-Video wins. Its `ycbv_base.zip`
   (15.8 kB displayed) plus `ycbv_test_bop19.zip` (660 MB displayed) is smaller than
   HB's base plus the 2.35 GB public annotated PrimeSense validation archive.

The original YCB-Video project links a roughly 265 GB corpus. M19 did not select that
corpus; it selected only BOP's smaller test subset.

## Hostile review

- Pose benchmarks mostly show a moving camera around arranged objects. They can falsify
  detector transfer but cannot validate household movement, containment, or zone logic.
- BOP object IDs are stable modeled-object identities, not person, ownership, or
  household identities.
- Selecting a small-target class from annotations is allowed only by a deterministic
  pre-model rule. It cannot inspect predictions or tune the frozen test slice.
- A public license and direct URL do not establish archive integrity. The acquisition
  goal must compute hashes, validate ZIP paths, record byte sizes, and stop on drift.
- The BOP visibility convention is not identical to M16. The translator must preserve
  the source values and apply the declared conservative mapping rather than silently
  rewriting occlusion into absence.
- No real YCB-V annotation or media byte was downloaded in M19.

## Claim ledger

| Claim | Evidence | Permissible wording | Unsupported extension |
|---|---|---|---|
| M19-C1 | GMU paper and current redirect | GMU documents useful historical kitchen localization data, but its current official acquisition route is unavailable | GMU has no usable copy or no license anywhere |
| M19-C2 | BOP dataset, task, and format docs | HB and YCB-V have current public licensed object-localization routes with executable safe-scoring translations | Every visible household object is annotated |
| M19-C3 | HF file listings | HB's public annotated validation route is 2.35 GB and YCB-V's BOP'19 route is 660 MB as displayed | The bytes or hashes were verified locally |
| M19-C4 | Frozen AND matrix and tie-breaks | YCB-Video is the unique bounded acquisition choice | It is the best real-home dataset or will improve a detector |
| M19-C5 | No-download boundary | One acquisition/translation slice is justified next | Training, test tuning, claims, live sensing, or operation is authorized |

## Verification

- Frozen contract commit: `443184f`.
- Recorded-result revision: `380ebf18fbb463af28ba975ddcceaff3cbfeccef`.
- Focused M19 tests: `9/9` passed.
- Clean result-revision suite: `173/173` passed under Python 3.12.13.
- Final staged public audit: 207 files / 414 index-and-worktree
  snapshots, zero violations, `operate_enabled: false`.
- Archive/media/annotation downloads, account use, model/tracker loads, training runs,
  VOST/VISOR reads, movement candidates, claims, and operational connections: zero.

## Next gate

M20 may acquire only `ycbv_base.zip` and `ycbv_test_bop19.zip` from the selected BOP
repository into an ignored local directory. It must hash and safely inspect the
archives, implement a BOP-to-D1 translator against synthetic contract fixtures, and use
a deterministic annotation-only rule to produce one local real D1 slice with at least
one 0.1–1% positive and one class-scoped negative. It must stop on license/source drift,
unsafe archive paths, missing public ground truth, missing small targets, incomplete
negative semantics, or the eight-hour bound. No model, prediction, training, relation,
claim, private/live source, cloud inference, or action belongs in M20.
