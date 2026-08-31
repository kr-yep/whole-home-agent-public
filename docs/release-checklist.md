# Public release checklist

This checklist applies to the bounded offline B0/B1 demo. Passing it does not enable `OPERATE`, authorize household data, or establish indoor accuracy.

## Required gates

- [ ] `PROJECT_STATE.md` still records `OPERATE DISABLED` and the intended source revision.
- [ ] The frozen B0 semantic fixture hash is unchanged: `226d30a5b826720d607d0b9a29bf3dfb9f5429eeedbbd70ffd1ff23c21233c8f`.
- [ ] `uv lock --check` succeeds and no dependency uses an unpinned mutable model alias.
- [ ] The complete local suite passes with bytecode writes disabled.
- [ ] The public-release audit reports zero findings before commit and against the staged index.
- [ ] The wheel and source archive build successfully.
- [ ] A fresh environment installed from the wheel can run `demo-recorded` outside the repository checkout.
- [ ] Browser QA confirms the fixed H.264 clip loads, the answer is replay-scoped and estimated, evidence limits are visible, and the console has no errors.
- [ ] `git diff --check` succeeds and the working tree is clean after the release commit.
- [ ] GitHub Actions passes on the public `main` branch.

## Reproducible commands

```powershell
uv sync --frozen --extra demo
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
uv lock --check
.\.venv\Scripts\python.exe tools\audit_public_release.py
uv build
git diff --check
```

For a Windows wheel smoke test, create a clean environment, install the built wheel with its `demo` extra, change to a directory outside the checkout, and run:

```powershell
whole-home-agent demo-recorded --compact --run-id wheel-install-smoke
```

The receipt must be `COMPLETE`, contain exactly two accepted estimated claims, resolve `key` to `sofa` through the two-step relation path, and expose no live, cloud, account, device, or action capability.

## Publication boundary

Do not publish real household media, coursework or competition datasets without confirmed rights, model weights, credentials, environment files, private run outputs, databases, embeddings, or local machine paths. Do not describe synthetic-fixture scores as real-home performance, “real-time,” “24/7,” or production readiness.
