# Local component ablation — corrected protocol

Date: 2026-09-05. Status: previous v2 claims withdrawn; local rerun completed.

Measured results on this Windows checkout: template 15/15, persona 15/15,
policy-on 5/5, policy-off mock negative control 3/5. The latter accepted both
out-of-range values (16 and 35). Template median latency in this run was 3.62 ms.
Timing describes local query processing only, not video, network or voice latency.

The previous report called scripted responses a real unconstrained LLM, assumed
1250 ms latency, and assigned some rates directly. Those results do not support
claims of 100% LLM hallucinations, guaranteed zero hallucinations, physical safety,
or improved human preference. The original report remains in Git history.

## Reproduction

Install the repository package and run:

    python tools/benchmark_local_components.py --repeats 3

The legacy benchmark_ablation.py command forwards to the measured runner.
By default it prints JSON without overwriting a report. --output-json PATH saves
results explicitly. Each run constructs temporary memory from the versioned synthetic
semantic fixture; no existing household or demo database is read.

## Comparisons

- Template versus persona: same fixture, five declared queries, three repetitions,
  actual status/location checks and measured latency. FOUND answers need evidence paths.
- Policy on versus off: five typed temperature requests, a fresh mock device per case.
  Allowed values: 18, 26, 30; denied: 16, 35. These are demo limits, not universal
  medical or physical safety thresholds.
- Policy-off is a deliberately failing negative control. Exit status requires
  policy-on and both presentation treatments to pass.

## Limits

No model endpoint, camera, real device or human-rating study is used. Repetitions
measure timing and are not independent accuracy samples. No population rate or
confidence interval is inferred. Structured answer correctness does not guarantee
that arbitrary LLM prose is correct. Perception errors remain outside this experiment.
