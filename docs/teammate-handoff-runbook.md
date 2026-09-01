# Teammate clean-install and demo handoff

This is the exact handoff procedure for one real teammate. It tests a disposable clean
clone, locked install, and the closed project-generated replay. It does not test a live
camera, private household data, general object recognition, or device action.

`OPERATE` must remain `DISABLED`. Do not add credentials, private registries, camera
URLs, uploads, household media, or cloud inference.

## Pinned handoff

- Repository: `https://github.com/kr-yep/whole-home-agent-public.git`
- Approved revision: `f16a0a4f99ac97dce16430b70568a3f47613cc0d`
- Python: `3.12.x`
- uv: semantic version `0.11.24`
- Checker: `tools/check_teammate_drill.py`
- Checker SHA-256: `4c2f3a5252bfa6711bffb20e1e3d708efa43e0f27ef6a9ac246202669f328d1e`

Use the full 40-character revision. Do not replace it with `main`, a branch name, or a
newer commit. A future approved handoff must publish another exact revision instead of
silently moving this one.

## Prerequisites

Use a machine that has:

- Git with public GitHub access for the clone;
- Python 3.12 available to uv;
- uv 0.11.24;
- enough space for one disposable clone, `.venv`, and the locked demo dependencies.

Network is allowed only for the public clone and public package installation. The
checker denies Python socket connections while it runs the demo.

Verify versions before starting:

```text
git --version
uv --version
uv python find 3.12
```

The second token of `uv --version` must be `0.11.24`; Windows build metadata after that
token is allowed. If uv is absent, install the pinned release before starting, for
example with `python -m pip install --user uv==0.11.24` on Windows or
`python3 -m pip install --user uv==0.11.24` on macOS/Linux, then open a new shell if the
user scripts directory was newly added to `PATH`.

## Windows PowerShell procedure

Run this in a new PowerShell window. It creates a uniquely named directory under the
system temporary directory; it does not reuse your development checkout or virtual
environment.

```powershell
$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/kr-yep/whole-home-agent-public.git"
$ApprovedRevision = "f16a0a4f99ac97dce16430b70568a3f47613cc0d"
$DrillRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("whole-home-agent-m37-" + [guid]::NewGuid().ToString("N"))
$ReceiptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("whole-home-agent-m37-receipt-" + [guid]::NewGuid().ToString("N") + ".json")

$CloneTimer = [System.Diagnostics.Stopwatch]::StartNew()
git clone --no-checkout $RepoUrl $DrillRoot
git -C $DrillRoot checkout --detach $ApprovedRevision
$CloneTimer.Stop()
$CloneMs = $CloneTimer.Elapsed.TotalMilliseconds

$ActualRevision = (git -C $DrillRoot rev-parse HEAD).Trim()
$Dirty = git -C $DrillRoot status --porcelain
if ($ActualRevision -ne $ApprovedRevision) { throw "REVISION: expected $ApprovedRevision, got $ActualRevision" }
if ($Dirty) { throw "REVISION: clean checkout required" }

$Python312 = (uv python find 3.12).Trim()
$InstallTimer = [System.Diagnostics.Stopwatch]::StartNew()
Push-Location $DrillRoot
uv sync --frozen --extra demo --python $Python312
$InstallTimer.Stop()
$InstallMs = $InstallTimer.Elapsed.TotalMilliseconds

$ReceiptLines = & ".\.venv\Scripts\python.exe" "tools\check_teammate_drill.py" `
  --expected-revision $ApprovedRevision `
  --clone-elapsed-ms $CloneMs `
  --install-elapsed-ms $InstallMs `
  --run-id "m37-real-teammate"
$CheckerExit = $LASTEXITCODE
[System.IO.File]::WriteAllLines($ReceiptPath, [string[]]$ReceiptLines, [System.Text.UTF8Encoding]::new($false))
$ReceiptLines
"checker_exit_code=$CheckerExit"
"receipt_path=$ReceiptPath"
Pop-Location
```

Do not continue to presentation if the checker exit code is not `0` or the receipt
status is not `PASS`.

## macOS/Linux Bash or Zsh procedure

Run this in a new Bash or Zsh shell. It uses the same pinned revision and records clone
and install time in milliseconds.

```bash
set -eu
REPO_URL='https://github.com/kr-yep/whole-home-agent-public.git'
APPROVED_REVISION='f16a0a4f99ac97dce16430b70568a3f47613cc0d'
TEMP_ROOT="${TMPDIR:-/tmp}"
TEMP_ROOT="${TEMP_ROOT%/}"
DRILL_ROOT="$(mktemp -d "${TEMP_ROOT}/whole-home-agent-m37.XXXXXX")"
RECEIPT_PATH="$(mktemp "${TEMP_ROOT}/whole-home-agent-m37-receipt.XXXXXX")"
PYTHON312="$(uv python find 3.12)"

clone_start_ns="$("$PYTHON312" -c 'import time; print(time.perf_counter_ns())')"
git clone --no-checkout "$REPO_URL" "$DRILL_ROOT"
git -C "$DRILL_ROOT" checkout --detach "$APPROVED_REVISION"
clone_end_ns="$("$PYTHON312" -c 'import time; print(time.perf_counter_ns())')"
clone_ms="$(CLONE_START_NS="$clone_start_ns" CLONE_END_NS="$clone_end_ns" "$PYTHON312" -c 'import os; print(round((int(os.environ["CLONE_END_NS"]) - int(os.environ["CLONE_START_NS"])) / 1_000_000, 3))')"

actual_revision="$(git -C "$DRILL_ROOT" rev-parse HEAD)"
test "$actual_revision" = "$APPROVED_REVISION"
test -z "$(git -C "$DRILL_ROOT" status --porcelain)"

cd "$DRILL_ROOT"
install_start_ns="$("$PYTHON312" -c 'import time; print(time.perf_counter_ns())')"
uv sync --frozen --extra demo --python "$PYTHON312"
install_end_ns="$("$PYTHON312" -c 'import time; print(time.perf_counter_ns())')"
install_ms="$(INSTALL_START_NS="$install_start_ns" INSTALL_END_NS="$install_end_ns" "$PYTHON312" -c 'import os; print(round((int(os.environ["INSTALL_END_NS"]) - int(os.environ["INSTALL_START_NS"])) / 1_000_000, 3))')"

set +e
".venv/bin/python" tools/check_teammate_drill.py \
  --expected-revision "$APPROVED_REVISION" \
  --clone-elapsed-ms "$clone_ms" \
  --install-elapsed-ms "$install_ms" \
  --run-id 'm37-real-teammate' >"$RECEIPT_PATH"
checker_exit=$?
set -e
cat "$RECEIPT_PATH"
printf 'checker_exit_code=%s\nreceipt_path=%s\n' "$checker_exit" "$RECEIPT_PATH"
```

Do not continue to presentation if `checker_exit` is not `0` or the receipt status is
not `PASS`.

## How to read the receipt

A valid pass has all of the following:

- `status: "PASS"`, `failure_classes: []`, the exact approved `revision`, and
  `worktree_clean: true`;
- `python`, `platform`, and every pinned package under `resolved_versions` describe the
  actual teammate environment;
- `uv_lock_git_blob_sha256` equal to
  `f2d3639c4b34b9c8a05381baec95cd178d39e056d81bbb7bc028eaeba1c94c3e`;
- `manifest_sha256` and `source_content_sha256` identify the allowlisted project-owned
  source while `semantic_sha256` identifies the normalized answer document;
- `network_attempt_count: 0` during the offline checker;
- `output_summary.answer.subject_id: "key"`, `location_id: "sofa"`, status `FOUND`,
  epistemic status `estimated`, and a two-edge `key → bag → sofa` relation path;
- two accepted estimated claims, `run_receipt_status: "COMPLETE"`, and governance with
  `operate: "DISABLED"`;
- `semantic_sha256` equal to
  `23d57ee4bb7c612c752f61369d5b18450532d24283bacc59b7683b0a2d35d322`;
- clone at most 120,000 ms, install at most 600,000 ms, demo at most 120,000 ms, and
  total at most 840,000 ms, as reported by `clone_elapsed_ms`, `install_elapsed_ms`,
  `demo_elapsed_ms`, and `total_elapsed_ms`;
- `cleanup_required: true` and the bounded `evidence_limit` remain visible; cleanup is
  verified separately after the checker.

The three lock fields have different meanings:

- `uv_lock_git_blob_sha256` is the fatal committed-version identity;
- `uv_lock_worktree_sha256` describes the local checkout bytes;
- `uv_lock_worktree_representation_matches_git_blob` may be `false` on a clean CRLF
  checkout and is diagnostic, not by itself a failure.

Checker exit `0` means `PASS`. Exit `2` means a bounded `STOP` with one or more named
failure classes. Any other exit or no JSON receipt is an infrastructure error or crash;
do not reinterpret it as either product success or product failure.

## Failure classes and next action

| Failure | Meaning | Teammate action |
| --- | --- | --- |
| `REVISION` | Wrong commit or dirty checkout | Preserve the message, discard the disposable clone, and retry only with the approved SHA. |
| `INSTALL` | Locked environment could not be created | Record Python, uv, OS, and the exact error. Do not remove `--frozen` or edit the lock. |
| `LOCK_OR_MANIFEST` | Committed lock identity or source manifest differs | Stop and discard the clone. Do not normalize, rehash, or replace the expected values. |
| `NETWORK` | The offline demo attempted a socket connection | Stop and retain the receipt; do not add network permission. |
| `TIME_BUDGET` | One frozen elapsed-time ceiling was exceeded | Report the measured field. Do not silently widen the budget. |
| `CLI`, `OUTPUT_PARSE`, `RUN_RECEIPT` | Demo process or JSON receipt is invalid | Retain stdout/stderr and stop. |
| `SOURCE`, `GOVERNANCE`, `SCOPED_ANSWER`, `RELATION_TRACE`, `CLAIMS` | Expected bounded semantics changed | Retain the receipt and revision. Do not change thresholds or expected semantics. |
| `UNEXPECTED` or no JSON | Checker or environment failed outside a classified path | Record the command, exit code, and error; treat it as unresolved infrastructure. |

## Git, uv, and Windows ACL troubleshooting

- If Git reports dubious ownership in a managed environment, do not add `*` as a safe
  directory. Set an exact per-process safe directory for the disposable path, or ask
  the machine owner to fix ownership. A normal teammate-created clone should not need
  this.
- If `uv --version` prints platform/build text after `0.11.24`, compare only the second
  whitespace-delimited token. A different semantic version is a preflight stop.
- If `uv python find 3.12` fails, install Python 3.12 or let the teammate's approved uv
  setup provision it before restarting the drill. Do not substitute another version.
- If `uv sync --frozen` wants to change `uv.lock`, stop. Do not run an unlocked sync.
- On Windows, close Streamlit, Python, terminals whose current directory is inside the
  clone, and Explorer handles before cleanup. If the exact guarded temporary path still
  has an ACL error, record `CLEANUP` and ask the machine owner to remove only that path;
  never broaden permissions or delete a parent directory.

## 90-second presentation and CLI fallback

Only after a checker pass, start the local presentation from the retained clone:

```powershell
& "$DrillRoot\.venv\Scripts\streamlit.exe" run "$DrillRoot\src\whole_home_agent\streamlit_app.py"
```

```bash
"$DRILL_ROOT/.venv/bin/streamlit" run "$DRILL_ROOT/src/whole_home_agent/streamlit_app.py"
```

In 90 seconds: point out `OPERATE DISABLED`; play the eight-second generated clip;
ask where the key is; show the estimated `key → bag → sofa` trace and evidence frames;
finish by stating that this is one synthetic prerecorded replay, not real-home or live
camera evidence.

If the browser or Streamlit fails, use the compact CLI fallback without changing data or
semantics:

```powershell
& "$DrillRoot\.venv\Scripts\whole-home-agent.exe" demo-recorded --compact --run-id "teammate-presentation"
```

```bash
"$DRILL_ROOT/.venv/bin/whole-home-agent" demo-recorded --compact --run-id 'teammate-presentation'
```

Presentation success is not a substitute for the checker receipt.

## Safe cleanup

Keep the JSON receipt, stop Streamlit, leave the clone directory, then remove only the
validated disposable clone.

PowerShell:

```powershell
$TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
$ResolvedDrillRoot = [System.IO.Path]::GetFullPath($DrillRoot)
$Leaf = Split-Path -Leaf $ResolvedDrillRoot
if (-not $ResolvedDrillRoot.StartsWith($TempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe cleanup path" }
if (-not $Leaf.StartsWith("whole-home-agent-m37-")) { throw "Unsafe cleanup name" }
Remove-Item -LiteralPath $ResolvedDrillRoot -Recurse -Force
```

Bash/Zsh:

```bash
cd "$TEMP_ROOT"
case "$DRILL_ROOT" in
  "$TEMP_ROOT"/whole-home-agent-m37.*) rm -rf -- "$DRILL_ROOT" ;;
  *) printf 'Unsafe cleanup path: %s\n' "$DRILL_ROOT" >&2; exit 1 ;;
esac
```

Confirm the clone no longer exists. Report cleanup separately from the checker because a
valid demo result does not prove cleanup.

## Teammate result template

Copy this into the team channel and attach the JSON receipt. An alias is enough; do not
publish personal email, home paths, credentials, or private media.

```text
M37 real-teammate handoff result
teammate alias:
platform and version:
CPU / RAM (GPU optional; not required):
approved revision: f16a0a4f99ac97dce16430b70568a3f47613cc0d
Python:
uv semantic version:
checker exit code:
receipt status:
failure classes:
clone / install / demo / total ms:
uv_lock_git_blob_sha256:
uv_lock_worktree_sha256:
worktree representation matches blob:
semantic_sha256:
Streamlit presentation: PASS / STOP / NOT RUN
CLI fallback: PASS / STOP / NOT RUN
cleanup: PASS / STOP
receipt attached: YES / NO
sanitized notes:
```

## Claim limits

A pass proves only that one teammate reproduced the pinned clean-install and synthetic
offline demo on the reported machine. It does not establish another unreported platform,
real indoor small-object accuracy, live sensing, 24/7 operation, privacy readiness,
physical truth, or device authority. A stop is useful bounded evidence and must not be
hidden by changing the revision, dependency lock, thresholds, expected answer, or time
budgets.
