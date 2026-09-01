# M30 answer-subject identity decision

## Decision

Select `A_CANONICAL_ANSWER_TRACE_SUBJECT` as the sole eligible candidate for one
separately frozen M31 implementation. M30 read only committed repository text; it did
not read media or a model, run the demo/checker, or change code, schema, or presentation.

The evidence chain is small:

1. `QueryRequest` requires `subject_id`.
2. `AnswerTrace` omits it.
3. `_trace` is the sole `AnswerTrace` constructor and already receives the request for
   every FOUND and non-FOUND branch.
4. Both B0 CLI and B1 public serializers project `AnswerTrace`, and both omit subject.
5. UNKNOWN, scope failure, frontier failure, and conflict can return an empty relation
   path, so neither path inspection nor fixed UI prose is a complete identity contract.

## Frozen matrix

| Candidate | G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 | Decision |
|---|---|---|---|---|---|---|---|---|---|
| A — canonical `AnswerTrace.subject_id` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | eligible |
| B — public DTO only | FAIL | PASS | FAIL | FAIL | FAIL | PASS | PASS | PASS | ineligible |
| C — current path/UI context | FAIL | FAIL | FAIL | FAIL | PASS | PASS | FAIL | PASS | ineligible |

The gates cover canonical query identity, authoritative source, B0/B1 parity,
non-FOUND completeness, one source of truth, additive compatibility, judge/debug
clarity, and bounded implementation.

## Bounded implementation authority

M31 may add one required immutable `subject_id` to `AnswerTrace`, copy it only from the
validated `QueryRequest` in `_trace`, and serialize it in both B0 CLI and B1 public
answers. It must test FOUND, UNKNOWN, CONFLICT, SCOPE_REQUIRED, OUT_OF_SCOPE, and
FRONTIER_MISMATCH; preserve claims, projection, query resolution, epistemic meaning,
and frozen session canonical hashes; and remove or rename no existing answer field.

This is an additive serialized change but may affect strict external JSON consumers or
manual/positional `AnswerTrace` construction. No stable answer-schema promise was found
in the pinned repository evidence, and the package is version `0.1.0`; that bounds but
does not erase compatibility risk. M31 must record it explicitly. M29 cannot be rerun.

The selection establishes no CV gain, household transfer, product correctness,
physical truth, governance adoption, or runtime authority. `OPERATE` remains disabled.

Python 3.12.13 passed all `324/324` tests, including `10/10` M30 contract and
result tests. The staged public-release audit scanned 267 files / 534
index-and-worktree snapshots with zero violations and `operate_enabled: false`.
