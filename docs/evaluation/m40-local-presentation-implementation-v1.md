# M40 deterministic local presentation implementation

## Outcome

M40 passes its bounded local implementation gate. The closed replay now builds the
exact M38 context once, passes a fresh validated copy to
`DeterministicLocationPresenter`, and returns a sanitized presentation receipt. The
same structured answer remains the source of truth and survives presenter failure.

## Implemented path

```text
scoped AnswerTrace
  → exact M38 allowlist
  → present_location_context
      → deterministic-location/1
      → validated prose or fixed fallback
  → additive presentation receipt + unchanged structured answer
```

The port receives no ledger, model, credential, endpoint, evidence store, media, tool,
or action handle. `public_demo.py` is the only composition root and selects no other
presenter.

## Evidence-bound wording correction

The previous helper said the key was put in the bag and then the bag moved to the sofa.
The minimized presenter context contains only the active relation path:

```text
inside(key, bag)
at_zone(bag, sofa)
```

M40 therefore renders: “系統估計鑰匙在包包裡，且包包位於沙發；所以鑰匙可能在沙發上的包包裡。” This is a presentation correction; it does not rewrite source claims or
claim that the relations are physical truth.

## Failure and hostile cases

Tests cover all non-FOUND statuses, direct and containment-chain FOUND answers, exact
allowlisting, extra fields, hostile identifiers, contradictory location, throwing
presenters, invalid identity, empty/non-text/overlong/control-character output, and
exception-text redaction. An actual closed-demo run with a forced throwing presenter
keeps `answer.status=FOUND` and `location_id=sofa` while returning only
`PRESENTER_FAILURE` plus fixed fallback text.

## Verification and limits

Python 3.12.13 passes `35/35` focused presentation/context/demo tests. A clean LF Git
worktree passes `433/433` complete-regression tests with 38 existing optional-dependency
skips. The public audit scans 315 files / 630 index-and-worktree snapshots with zero
violations and `operate_enabled: false`.

These results establish local deterministic presentation and bounded fallback only.
They do not establish language-model quality, local-model or provider compatibility,
teammate usability, real-home correctness, consent, or egress authority. Public CI was
not run and nothing was pushed.
