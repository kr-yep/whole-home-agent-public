# M18 tiny vector D1 slice proposal

## Purpose

Implement the smallest image-backed substrate that exercises the M16 D1 oracle without
changing the existing golden replay or loading a detector. M18 is an implementation and
reproducibility gate, not a training or transfer experiment.

## Contract to freeze before implementation

- exactly three project-owned source groups: development, validation, and test;
- exactly six 640×360 PNG/annotation pairs per group, 18 pairs total;
- at least one visible target in the 0.1–1% area bucket per split;
- explicit scored negative and unknown frames;
- `VISIBLE`, `OCCLUDED`, `TRUNCATED`, and `ABSENT` reference states;
- stable instance IDs and both containment and location reference transitions;
- asset, background, layout-seed family, scene/room, camera/time, and synchronized-view
  factors assigned before rendering and never crossing splits;
- one canonical manifest containing generator/config/license hashes, seed/group records,
  every output relative path/size/SHA-256, and total byte count;
- two clean generations produce byte-identical artifacts and exact M16 validation passes;
- generated substrate stays below 5 MiB and introduces no dependency.

## Stop conditions

Pass only if every exact schema, split, case-coverage, output pairing, size, and repeated-
byte gate passes while the existing B1 golden artifacts remain hash-identical. Otherwise
record the failure and stop; do not loosen M16 or modify a golden result.

## Boundaries

Only project-owned generated artwork is in scope. No external asset/media download,
recording, Blender/Kubric installation, detector/tracker load, training, VOST/VISOR or
reserved-source read, movement candidate, accepted claim, live/private/cloud/action
connection, or `OPERATE` enablement is authorized.

