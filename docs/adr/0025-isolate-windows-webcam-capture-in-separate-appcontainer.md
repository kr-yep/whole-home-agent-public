# ADR 0025: Isolate Windows webcam capture in a separate AppContainer

- Status: `PROPOSED`
- Date: 2026-09-04
- Scope: Windows webcam capture architecture and process isolation boundary

## Context

Introducing live webcam video acquisition introduces native driver execution risks, media capture crashes, and serious privacy/data-leakage hazards. Under the principle of least privilege, capturing frames from a physical camera must not be co-located within the same process that handles downstream semantic reasoning, SQLite query answering, language presentation, or network communication. Furthermore, the repository operates under `OPERATE DISABLED`, requiring that capture capability cannot be accidentally activated by standard Python imports or environment variables.

## Decision

To support future Windows webcam input while preserving repository invariants:

- Split the capture pipeline into two physically isolated Windows processes running under distinct MSIX AppContainers:
  1. `Wha.CaptureHost`: Written in C#/WinUI 3 (.NET 8) or C++/WinRT. Requests only the `webcam` device capability. Explicitly denies `internetClient` (no outbound/inbound networking), `microphone` (no audio), and general filesystem access. Owns `MediaCapture` and `MediaFrameReader`.
  2. `Wha.SemanticHost`: Contains the Python runtime and downstream processing. Denied all camera and microphone capabilities. Receives normalized frames exclusively over a local IPC channel.
- Connect `Wha.CaptureHost` and `Wha.SemanticHost` via a single-instance, one-way Windows Named Pipe (`\\.\pipe\LOCAL\wha.capture.v1.<session_nonce>`).
- Enforce strict DACLs (Discretionary Access Control Lists) granting read/write access solely to the current user token and the exact AppContainer Package SIDs of the two communicating processes. Deny `ANONYMOUS LOGON` and `NETWORK` SIDs.
- Require mutual peer verification of process tokens and package identity prior to camera initialization.
- Keep `CaptureHost` completely decoupled from domain logic, question answering, models, and databases.
- Retain `OPERATE DISABLED` across stages R0–R3, ensuring physical camera APIs remain uncalled until separate operational authorization (Stage R4).

## Alternatives

- Single-process Python capture with OpenCV `VideoCapture(0)`: Rejected because OpenCV requires full trust, bypasses AppContainer least-privilege sandboxing, and co-locates raw driver handles with language and semantic components.
- Background Windows Service or Named RPC: Rejected because Windows services run with elevated system privileges, violating least privilege, whereas AppContainers enforce explicit capability restrictions.
- Localhost HTTP/WebSocket server: Rejected because it requires network capabilities, exposes a network attack surface, and risks local port scanning/interception.

## Consequences

- Hardware capture is structurally isolated from semantic memory and query processing.
- A driver crash or buffer overrun in `CaptureHost` cannot compromise `SemanticHost` or access SQLite storage.
- Neither process possesses both camera access and network egress capabilities, eliminating the possibility of exfiltration.
- Cross-process AppContainer testing requires Windows 11 packaging and manifest verification in Stage R2.
