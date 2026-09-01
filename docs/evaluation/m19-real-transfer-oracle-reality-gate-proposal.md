# M19 real transfer-oracle reality-gate proposal

## Purpose

Decide whether one small lawful real-image substrate can falsify synthetic-to-real
detector gain before the project generates more artwork or trains a model. M19 is an
official-source, no-download decision gate.

## Candidate set to freeze before findings

1. GMU Kitchens;
2. HomebrewedDB;
3. YCB-Video;
4. `STOP_NO_REAL_TRANSFER_ORACLE`.

These candidates are object-localized real indoor sequences rather than action-only
datasets. Candidate names are not eligibility claims.

## Fatal gates

- an official author or institution capability source;
- current official terms covering the intended non-commercial evaluation/training use;
- a stable official acquisition route requiring no manual approval beyond one day;
- real RGB indoor frames with dimensions and per-frame instance masks or boxes;
- movable household-object labels and stable instance identity;
- explicit annotation completeness or a scoring rule that never turns unlabelled objects
  into negatives;
- source scene/video/object/camera groups that can be frozen before results and kept
  within one split;
- evidence that a minimal evaluation subset can test at least one 0.1–1% target, explicit
  negatives or unknowns, and stay below 5 GiB;
- a translator to M16 D1 that does not invent relation truth;
- first bounded acquisition/translation slice within eight working hours.

Select at most one only if all fatal gates pass. `UNKNOWN` remains selection-ineligible,
not factual failure. If none passes, stop and redesign the transfer oracle; do not train
against the M18 development/validation/test artwork and report it as real transfer.

## Boundaries

No archive/media/annotation download, account/login, model load, detector/tracker run,
training, test tuning, movement candidate, claim commit, live/private/cloud/action
connection, or `OPERATE` enablement belongs in M19.
