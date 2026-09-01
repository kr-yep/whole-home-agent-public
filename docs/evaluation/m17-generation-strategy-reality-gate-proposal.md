# M17 no-media generation-strategy reality-gate proposal

## Purpose

Select at most one way to produce a small D1-conformant target-domain training/evaluation
substrate. M17 compares designs and official capability/license evidence only. It does
not install tools, download assets, render images, generate media, or train a model.

## Frozen candidate set for the next Goal

1. Extend the existing project-owned 2D replay renderer.
2. Add a procedural 3D scene route based on Blender's documented headless capabilities.
3. Compose scenes from explicitly licensed reusable object/background assets.
4. `STOP_NO_FEASIBLE_GENERATION_STRATEGY`.

No diffusion/image-generation route is included initially: it does not natively provide
deterministic exhaustive boxes, persistent identities, negative-frame truth, or exact
container/zone transitions, and adding a separate annotation oracle would defeat this
gate's purpose unless primary evidence shows otherwise.

## Required gates

Before reviewing candidate findings, freeze:

- exact emission of the M16 D1 schema and all hostile conformance cases;
- visible small objects spanning the 0.1–1% area bucket, explicit negative/unknown frames,
  occlusion/truncation, persistent IDs, and location/containment reference transitions;
- independent source groups created before results, with assets/backgrounds/layout seeds
  prevented from crossing splits;
- deterministic seed/config/artifact manifests and reproducible bytes where the toolchain
  permits them;
- original-code and third-party asset/tool license compatibility with a public repository
  and the intended non-commercial hackathon evaluation/training use;
- one bounded development slice deliverable within one working day, the complete frozen
  substrate within three days, no more than 20 GiB, and no paid/cloud/private dependency;
- replacement cost, installation cost, rendering time, and likely realism gap.

Select exactly one only if every fatal gate passes and it uniquely dominates by reuse,
oracle fidelity, provenance, time/storage cost, then realism. If none passes, stop and
redesign the target scope. If several pass without a unique Pareto result, stop rather
than implementing multiple generators.

## Boundaries

No image/video generation, media/asset download, tool/dependency installation, household
recording, VOST/VISOR or reserved-source read, detector/tracker load, training, movement
candidate, accepted claim, live/private/cloud/action connection, or `OPERATE` enablement
is authorized.
