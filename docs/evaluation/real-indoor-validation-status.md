# Real indoor validation — not completed, 2026-09-05

User condition: push only after real indoor validation passes. This condition
has NOT been met. No commit or push was performed.

The public checkout initially had VOST/VISOR configurations and historical
reports but no local datasets or detector weights. The sibling original project's
indoor_recorded_d0 directory contains a generated contract clip, not real footage.

The official VOST data page offers train/validation images and masks under
CC BY-NC-SA 4.0: https://www.vostdataset.org/data.html . Its footage is egocentric
and is not a fixed-camera household location/containment acceptance set.

Attempted the existing hash-pinned 52 MB / 404-file motion-screen download with
8 workers, then retried with 4 workers. Both attempts ended in DNS resolution
failure (`getaddrinfo failed`). Partial data is retained under Git-ignored
datasets/vost/vost-motion-screen-v1. The required subset-manifest.json was not
created. Files must not be presented as an admitted complete dataset.

Prepared tools/check_real_burst_feasibility.py for a development-only, unchanged
parameter necessary-condition screen. Pixel-triggered selection is a lower bound
on selection with detector feedback (which can only extend dense windows). If
even that path cannot avoid 20% of calls, it rejects the efficiency goal on that
sequence. Passing this preliminary screen would still NOT certify end-to-end
object detection, containment, memory answers, or authorize the conditional push.

No real-data inference result or new quality score is claimed. Next: resume the
same verified subset download when DNS works, run the necessary-condition screen,
then obtain sufficient labelled indoor evidence and a real detector for the full
comparison. No threshold tuning on reserved data or substitution of synthetic
test results for real-world acceptance.
