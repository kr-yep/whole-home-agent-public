# M32 verification-fixture boundary decision

## Outcome

Candidate A, explicit verification profiles, is the sole 8/8 selection. Future work
must name one of three profiles instead of combining incompatible requirements:

- `STATIC_CONTRACT`: text, source, configuration, manifest, and recorded metadata only;
  no media bytes and no application/demo execution.
- `COMPLETE_REGRESSION`: may read only the exact repository-committed, hash-pinned,
  project-owned `D0_SYNTHETIC` fixture named in the result. This is regression and
  conformance evidence only.
- `AD_HOC_ACCEPTANCE_OR_EXPERIMENT`: not authorized by M32; it requires a separately
  frozen gate even if it proposes the same fixture.

Candidate B collapses static and complete verification into a zero-media rule, which
cannot receipt the current decoder/demo conformance path. Candidate C permits media by
broad label instead of exact identity and fails six fatal gates.

## Repository evidence

The pinned CI workflow has separate B0, prerecorded-video, and closed-demo jobs.
`tests/test_public_demo.py` explicitly loads the public demo bytes and checks their
SHA-256 against the manifest. The manifest records an exact path and digest,
`project_generated_synthetic` provenance, `CC0-1.0`, and `D0_SYNTHETIC`. The public
audit accepts generated media only through a narrow manifest-backed exception.

Scoring used those text files and recorded metadata only. It executed no tests, demo,
checker, or audit and read no media or model. M32 changes no production code, schema,
presentation, dependency, storage, or runtime boundary.

After selection, the committed complete-regression workflow ran as a separate receipt.
All six jobs, including the prerecorded D0, closed-demo, and release-audit jobs,
succeeded in [public CI run 33521751091](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33521751091)
for revision `5ea23d81f762d060a2cc8f9b7e22ae686d595a0f`. This receipt does not
change the decision's evidence limits.

## Limits

This decision does not make M31 retroactively pass. It does not authorize M29 retry,
new fixtures, third-party/private/live media, model work, product/CV gain claims, or
operation. Existing separately governed M18 D1 material is neither changed nor
reauthorized by this D0-specific decision. A hash proves byte identity, not consent,
capture truth, scene completeness, or real-home transfer. `OPERATE` remains disabled.

## Next bounded gate

M33 may separately freeze one teammate clean-install and closed-demo drill using the
exact committed D0 fixture. It must define a disposable environment, commands, time
limit, expected structured output, receipts, failure classes, cleanup, and an explicit
statement of what is usable and what is still missing.
