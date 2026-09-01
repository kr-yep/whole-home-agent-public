# M15 target-domain data/training reality-gate proposal

## Purpose

Decide whether one bounded target-domain training experiment deserves investment. M15
is a data and evaluation design gate first; it does not authorize acquisition, media
loading, labeling, training, or operation.

## Required estimand

The substrate must support the intended observation question: can one local detector
recover small movable household objects and container/zone context from fixed-camera
indoor video at useful cost? Generic scene understanding, sparse active-object labels,
or egocentric motion alone is insufficient.

Before any media bytes are acquired, freeze:

- target-object recall at IoU `0.50`, AP50:95, and recall for objects occupying 0.1–1%
  of the frame;
- false positives per evaluated frame, detector p50/p95, VRAM, and complete-frame
  accounting;
- a separately reported target-event coverage measure for movement-relevant changes;
- tracker ID switches and fragmentations as an independent co-gate;
- abstention and failure reporting rather than treating unloaded validation as zero.

## Data eligibility

A candidate substrate must have traceable origin, immutable version or manifestable
bytes, explicit license/terms for the intended evaluation or training use, and labels
that can be translated without inventing physical truth. It must allow grouping by
source video plus the relevant scene, camera, person, household, and time boundaries.
Adjacent frames may not be randomly split.

`3518_unscrew_bottle` is adaptive development material because it informed M10–M14.
It cannot provide an unbiased validation or test result. `3510_unscrew_bottle` remains
reserved and unread; it does not become validation authority merely because it exists.
A final test would require another independent source/scene after a recipe is locked.

If no lawful fixed-camera indoor substrate with usable target labels exists, M15 ends
normally with `PIVOT_TO_DATA_ACQUISITION_DESIGN`. It must not fall back to another
COCO-model tournament or quietly treat egocentric evidence as fixed-camera transfer.

## Training gate, if data eligibility later passes

- Select one baseline and one recipe before validation; no backbone tournament inside
  the training gate.
- Freeze source-separated train/development/validation/test manifests and hashes.
- Use at most 20 epochs with patience 5; no improvement is a normal stop.
- Keep test tuning and automatic Kaggle submission prohibited.
- Compare paired quality and cost on the same hardware, input, warm-up, and measurement
  method; report all runs, not only the best.
- Freeze the minimum worthwhile gain and any bootstrap interval only after sample-size
  feasibility is known, before training results.
- A validation pass authorizes at most one frozen test read; it does not authorize B1
  claim creation, live sensing, or operation.

## First bounded M15 task

Using only official dataset cards, papers, terms, and metadata, compare at most three
pre-named public substrate candidates plus `STOP/PIVOT`. Do not download media. Select
exactly one only if its domain, labels, license, immutable manifest path, source-level
split support, and bounded acquisition cost all pass. Otherwise stop with a concrete
gap statement.
