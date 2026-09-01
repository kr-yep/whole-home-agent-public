# M21 YCB-V per-archive root repair proposal

## Purpose

Repair the single packaging assumption falsified by M20, then retry the same bounded
materialization without changing its scientific or safety requirements.

## Sole allowed contract change

- `ycbv_base.zip` source root: `ycbv/`, destination unchanged;
- `ycbv_test_bop19.zip` source root: `test/`, destination prefixed with `ycbv/`;
- validate the mapped destination namespace across both archives before extracting any
  member.

The mapper must reject destination traversal, absolute/drive paths, symlinks,
case-folded duplicates, base/test destination collisions, encrypted or unsupported
members, and every existing size/ratio bound. A committed synthetic two-archive fixture
must prove these cases before the verified local archives are reused.

## Unchanged requirements

Source revision, archive names, URLs, exact sizes and SHA-256 values, MIT expectation,
5 GiB and eight-hour limits, annotation-only object/scene/frame order, 0.1–1% visible
target, true selected-class absence, incomplete/under-10%-visible unknown handling,
maximum 18 frames, project test-only scope, zero relation/transition output, and all
model/training/test-tuning/claim/live/private/cloud/action prohibitions remain frozen.

## Pass and stop

Pass only if the corrected mapping safely materializes the selected members, actual
metadata confirms the M20 source contract, and two real translations produce the same
complete D1 slice with at least one frozen-bucket positive and one class-scoped absent
frame. Stop normally on any other mismatch; do not add another infrastructure retry in
M21.

