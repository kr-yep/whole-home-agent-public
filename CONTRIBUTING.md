# Contributing

Thanks for helping build Whole Home Agent. The current repository is an offline, synthetic-data B0 baseline. Contributions must preserve that boundary unless an explicit project decision and ADR expand it.

## Development workflow

1. Read `AGENTS.md`, `PROJECT_STATE.md`, and `ACTION_POLICY.md`.
2. Branch from `main` and keep the change focused.
3. Install the project with `python -m pip install -e .` on Python 3.11+.
4. Add deterministic tests and a frozen synthetic fixture when behavior changes.
5. Run `python -m unittest discover -s tests -v`.
6. Open a pull request that explains the change, evidence, limitations, and any boundary or data impact.

## Pull request checklist

- [ ] The patch stays within the authorized B0 scope, or cites the explicit decision and ADR that expands it.
- [ ] Tests cover success, unknown/conflict behavior, and relevant hostile input.
- [ ] Claims remain scoped and traceable; inference is not presented as physical truth.
- [ ] No private media, personal data, datasets without redistribution review, weights, databases, logs, secrets, or credentials are included.
- [ ] New dependencies have a clear need, pinned compatibility, and license review.
- [ ] Documentation and `PROJECT_STATE.md` are updated when current evidence or gates change.

## Design expectations

- Keep domain and application logic independent of concrete CV, model, storage, UI, and cloud libraries.
- Put integrations behind narrow ports/adapters.
- Prefer deterministic validation around probabilistic model output.
- Keep source reports, derived state, authority decisions, commands, acknowledgements, and observed outcomes distinct.
- Do not introduce graph storage, multi-agent infrastructure, or operational capabilities without evidence that the simpler baseline is insufficient.

For a possible security or privacy issue, avoid posting private household data or credentials in a public issue. Use GitHub's private vulnerability reporting for this repository when available.
