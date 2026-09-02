# M44 explicit-cache release-candidate packaging

## Outcome

M44 is a normal stop after the build subprocess started and before the frozen artifact
gate. Its only package attempt must not be retried.

The caller-created cache was seeded from the frozen local ignored subset: 14,049 files,
627,590,722 bytes, and tree SHA-256
`5f5101e6fe74e847d0bb9d0a3e9e06398e00a85917106ada647f3225072812fc`.
The source and target trees matched, the 13 frozen local/editable metadata files stayed
excluded, and the source cache was not mutated. This proves byte identity for the copied
subset only; its upstream provenance was not independently authenticated.

The Windows runner captured the build process as implicit CP950 text. A subprocess
reader encountered byte `0xc3` at position 18,831 and raised `UnicodeDecodeError`.
`process.stderr` consequently became `None`, and receipt assembly then raised
`AttributeError` at `process.stderr.strip()`. No runner receipt retained the build exit
code or elapsed time. M44 therefore cannot call the build successful even though a
partial artifact exists.

## Read-only artifact forensics

After the crash, read-only inspection found exactly one generated source archive and no
wheel:

- `whole_home_agent-0.1.0.tar.gz`: 209,221 bytes, SHA-256
  `44e16a69d1fcd72aa3492306db9ba4d9a4b1d4d3d423c62627b27faf3433dd91`;
- 116 members, 104 files, and 928,564 uncompressed file bytes;
- no unsafe member types or forbidden archive members under the inherited M41 checks;
- exactly one `src/whole_home_agent/presentation.py`, matching the frozen source hash
  `26e625e763575a2b873978f8d930128be624c23433eb2fb72cfa3b65ee596a55`;
- the inherited source-distribution contract fails because required `uv.lock` is absent.

Because the wheel did not exist, the fresh environment, wheel installation, installed
dependency check, M40 normal/fallback presentation checks, compact demo, and Python
socket guard never started. The offline/no-config/no-Python-download flags and sanitized
environment were selected, but no OS network instrument existed, so zero network
attempts are not claimed.

## Cleanup and evidence limits

The 628 MB disposable cache, detached source worktree, partial source archive, empty run
directory, and output directories were removed; no generated artifact or cache remains.
The source archive could be regenerated only by a separately authorized future attempt.

M44 does not establish a complete valid source distribution, a wheel, fresh installation,
installed demo behavior, teammate usability, public CI, provider compatibility, or
real-home performance. It changes no product behavior, schema, or dependency, makes no
provider request, reads no private/live/additional media, performs no push, and keeps
`OPERATE` disabled.

If work resumes, the next repository-only decision should preserve this stop while
hardening subprocess output capture against non-CP950 bytes and deciding how `uv.lock`
enters the source distribution. A new build would require a separately frozen attempt;
M44 itself authorizes neither a retry nor a push.
