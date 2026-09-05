# ADR 0028: Resolve webcam sharing mode contradiction and mandate R2A IPC validation gate

- Status: `PROPOSED / ADOPTED IN SPEC v1.2-DRAFT`
- Date: 2026-09-05
- Scope: Windows webcam capture initialization mode and cross-AppContainer IPC boundary

## Context

The initial architectural proposals (ADR 0025, WHA-WIN-CAPTURE-ROI-001 v1.0-draft) aimed to establish a least-privilege, verifiable pipeline from Windows webcam input to ROI ingress. However, detailed technical analysis of Microsoft WinRT specifications and Win32 IPC revealed two critical architectural issues:

1. **The `SharedReadOnly` vs `SetFormatAsync` Contradiction**:
   - The initial design required `MediaCaptureInitializationSettings.SharingMode = SharedReadOnly` while simultaneously requiring the camera to be strictly configured to `1280×720 RGB24 at 10 Hz`.
   - According to official Microsoft WinRT documentation (`MediaCaptureInitializationSettings.SharingMode`, `MediaFrameSource.SetFormatAsync`), an application operating in `SharedReadOnly` mode is explicitly prohibited from mutating the frame source format. Calling `SetFormatAsync` in shared read-only mode fails.
   - Consequently, in `SharedReadOnly`, an application can only receive whatever resolution and frame rate the underlying Windows camera driver happens to provide by default. Relying on accidental driver defaults is non-deterministic and unacceptable for reproducible verification.

2. **Cross-AppContainer Named Pipe Feasibility**:
   - Microsoft general Windows App IPC documentation indicates that named pipes can be shared between distinct MSIX packages by constructing appropriate AppContainer Package SIDs in the pipe's DACL.
   - Conversely, specific API documentation (e.g., `ConnectNamedPipe`, `GetNamedPipeClientProcessId`) notes historical restrictions regarding cross-AppContainer connections.
   - Before committing to full packaging and deployment, an empirical physical validation gate is required.

## Decision

To resolve these architectural issues while preserving repository safety invariants:

### 1. Adopt `ExclusiveControl` with Strict `format_only` Boundary
- Transition `MediaCaptureInitializationSettings.SharingMode` from `SharedReadOnly` to `ExclusiveControl`.
- **Strictly Bounded Scope (`format_only`)**:
  - Exclusive control is authorized solely for the purpose of invoking `MediaFrameSource.SetFormatAsync` exactly once during initialization to apply the registered `1280×720` format from `SupportedFormats`.
  - Calling or accessing `VideoDeviceController` is strictly prohibited. `CaptureHost` must not modify focus, exposure, zoom, white balance, torch/flash, pan/tilt, or vendor-specific camera properties.
  - Driver format fallback is strictly prohibited (`allow_source_format_fallback = false`). If the exact registered format is not available or cannot be uniquely resolved, initialization must fail closed (`LAUNCH_CAMERA_FORMAT_NOT_FOUND` or `LAUNCH_CAMERA_FORMAT_AMBIGUOUS`).
  - Reader resizing is strictly prohibited (`allow_reader_resize = false`).

### 2. Mandate Stage R2A Empirical Feasibility Gate
- Before deploying full MSIX packages for `Wha.CaptureHost` and `Wha.SemanticHost`, conduct an isolated minimal binary test (Stage R2A) on a physical Windows 11 machine.
- Verify whether two separate non-full-trust AppContainer processes can connect and exchange frames over a Win32 Named Pipe using explicit Package SID DACLs.
- Merging into a single package or using `runFullTrust` capability to bypass AppContainer isolation is strictly prohibited. If R2A fails, execution must halt and return to the `DECIDE` phase to select an alternative local IPC mechanism (e.g. `AppServiceConnection`).

### 3. Formalize Stage R4 Acceptance Criteria
Physical device acceptance (Stage R4) is separately authorized and requires passing on Windows 11 x64 under all 7 criteria:
1. `source_profile = windows_webcam_d1_v1`
2. Physical acquisition from the registered UVC webcam
3. Exactly 300 acquisition positions accounted for
4. 100% of frames received at ROI ingress are `ACCEPTED` and released
5. Every frame lease is released exactly once without leaks
6. Final `stream_sha256` digest matches byte-for-byte
7. Camera, pipe, and memory buffers are cleanly disposed within bounded timeouts

## Alternatives

- **Retain `SharedReadOnly` and accept whatever format the driver defaults to**:
  Rejected. Different cameras default to 640×480, 1080p, or 4K with variable frame rates. This breaks the downstream ROI contract, requires arbitrary software resampling, and prevents deterministic evaluation.
- **Allow reader-side resizing (`BitmapSize`)**:
  Rejected. Reader resizing consumes substantial CPU in the capture process, introduces interpolation artifacts, and hides driver configuration errors.
- **Bypass AppContainer sandboxing using `runFullTrust`**:
  Rejected. Running capture with full desktop trust eliminates least-privilege guarantees and violates repository governance.

## Consequences

- The architectural contradiction between format selection and sharing mode is formally resolved.
- Camera access remains minimally privileged: exclusive access is used exclusively to lock in the 1280×720 format.
- Implementation progression is strictly gated: R1 (pure Python contract) -> R2A (AppContainer pipe feasibility) -> R2 (cross-package generated vectors) -> R3 (fault injection) -> R4 (physical device acceptance).
- The repository remains `OPERATE DISABLED` until separate physical authorization is granted for Stage R4.
