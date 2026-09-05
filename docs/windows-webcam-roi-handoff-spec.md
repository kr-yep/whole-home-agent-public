# Whole Home Agent Integrated Specification from Windows Webcam Input to ROI Handoff

- Document number: `WHA-WIN-CAPTURE-ROI-001`
- Version: `1.2-draft`
- Date created: `2026-09-04`
- Date revised: `2026-09-05`
- Document status: `PROPOSED / R1 CORE IMPLEMENTED`
- Operational status: `OPERATE DISABLED`
- Target environment: Windows 11 x64, one USB/UVC color webcam
- Scope: From image acquisition from the webcam through confirmation of acceptance at the ROI processing ingress

## 1. Purpose and Status of This Document

This document consolidates the specification for acquiring video on Windows and safely delivering normalized full frames to the ROI processing ingress in a verifiable manner, in preparation for future webcam use by Whole Home Agent. It is intended to provide, in a single document, the scope of responsibility, boundaries, data formats, processing order, failure behavior, development isolation, test methods, and completion criteria.

This document is a proposed implementation specification integrating ADR 0025, ADR 0026, ADR 0027, and a detailed protocol proposal; it is not an adopted operational policy. Creating this document, implementing it, or successfully testing it does not authorize camera use, household data acquisition, photographing people, storage, external transmission, or device operation. The current repository remains `OPERATE DISABLED`.

Items described as “required” in this document are conformity requirements for a future implementation of this proposal. Until `ACTION_POLICY.md`, `PROJECT_STATE.md`, stakeholder consent, roles, device and camera registration, and execution authorization are finalized, only offline testing with generated images is in scope.

- **1.1-draft** maintained the 1.0-draft ROI ingress boundary and wire v1 specification, while clarifying the configuration profile, missing source-end, cleanup code, camera lifetime, and synchronous timeout evidence limits identified during R0 review. Cross-AppContainer named pipe communication remained tentative pending R2A feasibility validation.
- **1.2-draft** reflects Windows `SharedReadOnly` limitations where the frame source format cannot be changed, modifying future live profiles to `ExclusiveControl`. Exclusive control is strictly limited to a single `SetFormatAsync` invocation applying the registered 1280×720 exact MediaFrameFormat. Camera controls such as focus, exposure, and zoom are strictly prohibited, as are fallback formats/devices and reader resizing. Wire v1, ROI ingress, raw retention, and R2A/R4 gates remain unchanged.

## 2. Objective

The objective of this work is to define a boundary capable of accepting future Windows webcam input, separately from the current demo that directly reads a fixed video, and to make the following result reproducible:

```text
One frame acquired from the webcam
  -> Normalize to the specified size and color format
  -> Convert to a message that explicitly represents order, time, and loss
  -> Send to SemanticHost over isolated local communication
  -> Validate strictly
  -> Pass read-only to the ROI processing ingress
  -> Confirm ROI-side acceptance and buffer release
```

The deliverable of this work is the delivery result: “the image correctly reached the ROI ingress.” Recognizing an object, selecting the correct ROI, tracking keys or a bag, or understanding facts about a household are not included.

## 3. Scope of Responsibility

### 3.1 Included

- Contract-test input using generated frames
- Webcam initialization, start, stop, and disposal if authorized in the future
- Color-frame acquisition
- Acquisition-position numbering at a fixed 10 Hz cadence
- Normalization to 1280×720 RGB24
- Unification of orientation, mirroring, row stride, and coordinate system
- A finite session protocol representing frames, gaps, start, and end
- A transmit queue of at most three frames
- One-way local delivery over a Windows named pipe
- Validation of the pipe peer, message format, length, ordering, timestamps, and hash
- Synchronous lending of read-only frames to the ROI ingress
- Confirmation of ROI acceptance, rejection, timeout, and buffer release
- Generation of a delivery receipt at session end
- Fail-closed processing on failure
- Reliable release of camera, pipe, and buffer resources
- Structured logs and aggregate metrics that contain no images

### 3.2 Excluded

- Selecting ROI rectangles or polygons
- Cropping, tiling, resizing, or letterboxing frames
- Selecting frames through motion detection
- Object detection, tracking, embedding, or relationship inference
- `ClaimCandidate` generation, claim commit, ledger, or projection
- Question answering, Streamlit display, LLM/VLM, or presenter
- SQLite or any other persistent memory
- Saving raw frames, video, thumbnails, or cropped images
- Cloud APIs, localhost HTTP, TCP, WebSocket, or RTSP
- Audio, microphones, face recognition, or person identification
- Multiple cameras, cross-camera ID transfer, or automatic reconnection
- Continuous monitoring, unattended execution, or 24-hour operation
- Use in real homes, with people, or in private spaces
- Device control or physical action

## 4. ROI Definition and Responsibility Boundary

In this document, ROI means the `Region of Interest` processing stage. However, the delivery boundary in this work is not the result of ROI computation; it is the ingress at which the ROI processing stage receives a normalized full frame. The scope ends when all of the following conditions hold:

1. SemanticHost has validated the structure, size, order, and time of one frame.
2. The ROI ingress has received a read-only lease for that same frame.
3. The ROI ingress has completed the required synchronous processing.
4. The ROI ingress has released the lease exactly once.
5. The ROI ingress has returned `ACCEPTED` for the same session and sequence.

If the ROI side later generates rectangles, polygons, or crops, those are governed by a separate contract. CaptureHost and CaptureStreamDecoder in this work must not determine the ROI in advance or interpret downstream detection results.

If stakeholders interpret “deliver to ROI” as “generate an ROI crop and pass it downstream,” implementation must stop and a different version of the specification must be agreed because that interpretation differs from this document’s responsibility boundary.

## 5. System Architecture

The future Windows architecture separates CaptureHost, which has camera permission, from SemanticHost, which performs ROI and semantic processing, into separate processes with separate AppContainer IDs.

```text
A person presses Start on screen
          |
          v
+------------------------------------------------------+
| Wha.CaptureHost                                     |
| C# / WinUI 3 / MSIX AppContainer                    |
| Permission: webcam only                             |
| MediaCapture + MediaFrameReader                     |
| numbering -> RGB24 conversion -> 3-slot queue       |
| -> pipe transmission                                |
+----------------------------+-------------------------+
                             |
                             | Windows named pipe
                             | one-way, one connection,
                             | length-limited, DACL-restricted
                             v
+------------------------------------------------------+
| Wha.SemanticHost                                    |
| Separate MSIX AppContainer / fixed Python runtime   |
| No webcam, microphone, network, or broad filesystem |
| permissions                                         |
| decoder -> validator -> ROI ingress                 |
+----------------------------+-------------------------+
                             |
                             | RoiAcceptResultV1
                             v
                    End of current responsibility
```

CaptureHost is a camera adapter, not a model, database, state manager, question-answering system, or external service. SemanticHost has neither camera APIs nor camera permission and passes only received transient frames to the ROI ingress.

The normal Python environment, current CLI, current Streamlit application, macOS/Linux tests, and existing demo must not build, install, start, import, or enumerate cameras through CaptureHost.

## 6. Execution Profiles

| Profile | Input | Purpose | Current treatment |
|---|---|---|---|
| `stream_sim_d0` | Python-generated RGB | Pure contract testing | May be implemented in the future |
| `windows_generated_ipc_v1` | RGB generated inside the Windows package | Inter-AppContainer communication testing | Permitted after a separate implementation request |
| `windows_webcam_d1_v1` | Registered webcam | Physical-device acceptance testing | Currently prohibited |

All profiles use the same message structure and ROI contract. A simplified format or separate ROI interface must not be created solely for generated tests.

`windows_webcam_d1_v1` must not be selected unless execution authorization, roles, consent, camera capability, field of view, execution deadline, signed package hash, and configuration hash all match. It must not be possible to enable it using only an environment variable, user question, LLM output, import side effect, or ordinary CLI option.

## 7. Fixed Parameters

| Item | Value |
|---|---|
| Capture schema | `whole-home-agent.capture-message.v1` |
| ROI session schema | `whole-home-agent.roi-ingress-session.v1` |
| ROI frame schema | `whole-home-agent.roi-ingress-frame.v1` |
| ROI gap schema | `whole-home-agent.roi-ingress-gap.v1` |
| ROI end schema | `whole-home-agent.roi-ingress-end.v1` |
| ROI result schema | `whole-home-agent.roi-accept-result.v1` |
| ROI receipt schema | `whole-home-agent.roi-delivery-receipt.v1` |
| ROI profile | `windows_webcam_roi_v1` |
| Image width | 1280 pixels |
| Image height | 720 pixels |
| Pixel format | `rgb24` |
| Channel order | R, G, B |
| Channel depth | unsigned 8-bit |
| Array layout | contiguous `height x width x 3` |
| Row stride | 3840 bytes |
| Payload per frame | 2,764,800 bytes |
| Origin | top left |
| x-axis | rightward |
| y-axis | downward |
| Rotation | normalized to 0 degrees |
| Mirroring | none |
| ROI-side color interpretation | sRGB |
| Acquisition cadence | 10/1 positions per second |
| One position | 100,000,000 ns |
| Normal acquisition duration | 30,000,000,000 ns |
| Normal position count | 300 |
| CaptureHost frame slots | 3 |
| Decoder frame slots | 1 |
| ROI lease slots | 1 |
| Application frame limit | 5 total |
| Normal temporal gap limit | 2 positions |
| Metadata limit | 8,192 bytes |
| Body limit | 2,764,800 bytes |
| Raw retention | `none` |
| Audio | `false` |
| Network egress | `false` |
| Camera sharing | `exclusive_control`, format configuration only |
| Camera control scope | `format_only` |
| Source format fallback | `false` |
| Reader resize | `false` |

Changing resolution, color format, cadence, queue, or retention method requires updating the configuration hash and test results. If wire compatibility changes, v2 must be proposed instead of overwriting v1.

## 8. Configuration and Hashes

In each execution profile, CaptureHost, the decoder, and ROI must use the same resolved configuration for that profile. R1 uses `configs/capture/stream-sim-d0-v1.toml` and explicitly maps `profile_id=stream_sim_d0` to `source_profile=generated_stream_d0` on the wire. The following example is reserved for future live profiles and must not be reused as the R1/R2 hash. The configuration is read exactly once before pipe creation or camera opening; unknown, missing, duplicate, incorrectly typed, or out-of-range keys are rejected. Values sent by the message sender must not expand local limits.

The initial configuration includes at least the following:

```toml
schema = "whole-home-agent.capture-config.v1"
profile_id = "windows_webcam_d1_v1"
width = 1280
height = 720
pixel_format = "rgb24"
target_fps_numerator = 10
target_fps_denominator = 1
sampling_interval_ns = 100000000
max_positions = 300
sampling_window_ns = 30000000000
camera_initialization_timeout_ns = 5000000000
camera_open_to_close_limit_ns = 37000000000
pipe_connect_timeout_ns = 5000000000
pipe_inactivity_timeout_ns = 1000000000
roi_accept_timeout_ns = 100000000
end_flush_timeout_ns = 2000000000
resource_release_timeout_ns = 2000000000
queue_capacity = 3
roi_capacity = 1
max_gap_frames = 2
raw_retention = "none"
audio_enabled = false
network_egress_enabled = false
camera_sharing_mode = "exclusive_control"
camera_control_scope = "format_only"
allow_source_format_fallback = false
allow_reader_resize = false

[transport]
wire_version = 1
max_metadata_bytes = 8192
max_body_bytes = 2764800
pipe_instances = 1

[roi]
profile_id = "windows_webcam_roi_v1"
layout = "HWC_CONTIGUOUS"
row_stride_bytes = 3840
origin = "top_left"
x_axis = "right"
y_axis = "down"
rotation_degrees = 0
mirrored = false
color_interpretation = "srgb"
```

In the live profile, the following `[camera_source]` object generated during device registration is also mandatory:

| Field | Condition |
|---|---|
| `binding_schema` | `whole-home-agent.camera-format-binding.v1` |
| `frame_source_ref` | Opaque registration reference containing no hardware ID |
| `stream_kind` | `color` |
| `width`, `height` | 1280, 720 |
| `source_subtype` | Exact case-normalized subtype at registration |
| `frame_rate_numerator`, `frame_rate_denominator` | Exact positive fraction at registration, at least 10 fps |
| `reader_output_subtype` | `BGRA8` |
| `format_fingerprint` | Canonical SHA-256 of the above binding fields |

This object is not an operational conjecture, but an output from human-reviewed registration. The total configuration including this object forms the basis for `capture_config_hash`; if missing, the live configuration is unresolved and the camera must not be opened.

After defaults are applied, the configuration hash is computed by converting all scalar values to canonical JSON in key order and applying SHA-256 to its UTF-8 byte sequence, producing 64 lowercase hexadecimal characters. `capture_config_hash` covers the entire Capture configuration; `roi_config_hash` covers the ROI configuration and ROI schema version.

A configuration hash identifies configuration bytes; it does not prove the camera, video, consent, authenticity, or real-world state.

## 9. Identifiers

`capture_session_id` is an opaque ID representing one producer lifetime. Future physical-device runs use a canonical lowercase UUIDv4 and issue a new ID for every reconnection, restart, or retry. Generated tests may use a fixed test ID in the manifest.

`source_id` is an opaque profile-scoped ID. It must not contain a person’s name, room name, address, account, camera product name, or user-entered text. It consists of 1–128 printable ASCII characters with no control characters or whitespace.

The camera hardware ID is retained only inside the trusted launch boundary and is not passed onto the wire, into ROI values or receipts, or into logs.

## 10. Windows Camera Acquisition Specification

This section applies only if R4 is separately authorized in the future.

CaptureHost uses `MediaCapture` and a color `MediaFrameReader`. Python `VideoCapture(0)`, camera indexes, OpenCV enumeration, and DirectShow fallback are not used.

Camera startup proceeds as follows:

1. SemanticHost creates the named-pipe server.
2. CaptureHost and SemanticHost verify each other’s package/AppContainer identity.
3. A person presses Start in the CaptureHost UI.
4. The trusted boundary rechecks execution authorization, expiry, package hash, device capability, and configuration hash.
5. CaptureHost opens only the single registered device as video-only, CPU memory, and `ExclusiveControl` mode.
6. It selects exactly 1 `MediaFrameFormat` matching the registered source ID, stream kind, 1280×720, subtype, frame rate fraction, and format fingerprint, and invokes `SetFormatAsync` exactly once. If 0 or multiple matches exist, it fails closed.
7. It re-verifies that `CurrentFormat` exactly matches the registered values.
8. It creates a reader with fixed `BGRA8` output subtype and no BitmapSize, strictly prohibiting resizing.
9. It starts the reader.
10. It sends `start` and begins generating positions for 30 seconds.
11. After 300 positions or user clicking Finish, it stops and disposes the reader and camera.
12. It sends a `SEALED end` only after confirming successful camera release.
13. SemanticHost validates, terminates ROI, generates the receipt, and releases the pipe.

Pipe connection and peer authentication complete within 5 seconds before camera open. Camera and reader initialization are limited to 5 seconds, and camera open-to-close is limited to 37 seconds. The on-screen capture indicator remains visible from before camera open until after camera disposal.

Startup does not occur if the registered camera is absent, the device ID has changed, permission is denied, 1280×720 is unavailable, exact format fails to match uniquely, exclusive control cannot be acquired, or the driver falls back to another format. The system does not automatically switch to shared mode, another camera, another resolution, or let the reader resize.

`ExclusiveControl` is used strictly for format configuration. CaptureHost must not access or invoke VideoDeviceController, focus, exposure, zoom, white balance, torch, pan/tilt, or vendor properties. The exact format including source subtype and frame rate fraction must be fixed during human-reviewed device registration, with normalized hashes included in the live configuration. At this stage with no registered camera, fabricated formats or live configuration hashes must not be invented.

Because `SharedReadOnly` cannot change the frame source format and only guarantees exact format if the driver happens to match, it is not used in this profile.

## 11. Image Normalization Specification

CaptureHost converts the selected source frame exactly once into the following canonical frame:

```text
shape:          720 x 1280 x 3
layout:         HWC_CONTIGUOUS
channel order:  RGB
dtype:          uint8
stride:         3840 bytes
origin:         top-left
x direction:    right
y direction:    down
rotation:       0 degrees
mirrored:       false
payload bytes:  2,764,800
```

For BGRA8 driver input, B, G, R is reordered to R, G, B and alpha is discarded. If another source subtype such as NV12 is permitted, the Windows conversion path is fixed in advance and tested with generated color bars. Capture does not crop, resize, letterbox, tile, sharpen, denoise, motion-filter, or classify objects.

Downstream box coordinates use `xyxy` on the original frame, including `x1,y1` and excluding `x2,y2` (max-exclusive). Valid ranges are `0 <= x1 < x2 <= 1280` and `0 <= y1 < y2 <= 720`. Although capture does not generate boxes, the coordinate system is fixed so downstream stages can map back to the original image.

## 12. Acquisition Timestamps and Position Numbering

Both Windows processes use QueryPerformanceCounter directly. A counter `c` with frequency `f` is converted to nanoseconds without floating-point arithmetic:

```text
q = c // f
r = c % f
monotonic_ns = q * 1_000_000_000 + (r * 1_000_000_000) // f
```

Operations include overflow checks. This is local monotonic time, not UTC, camera exposure time, or a capture date/time. `captured_monotonic_ns` is the QPC observation immediately after CaptureHost first places the selected source frame under application ownership.

With `start.started_monotonic_ns = t0`, the deadline for position `n` is:

```text
deadline(n) = t0 + (n + 1) * 100_000_000 ns
0 <= n < 300
```

At each deadline, exactly one position is recorded as either a frame or a gap. The same source frame is not used for multiple positions. A future frame is not assigned to a past position, and an old frame is not repeated to conceal a gap.

For each position, use the latest frame newer than the previously used frame and observed no later than the current deadline. If none is available, the reason is `source_unavailable`; if conversion cannot finish in time, `capture_overrun`; if a converted frame cannot enter the transmit queue, `queue_overflow`.

Only consecutive gaps with the same reason may be combined into one range. A pending gap is sent before a subsequent frame. If a gap cannot be sent, the session fails without sealing.

## 13. CaptureMessageV1 Wire Specification

Each named-pipe record consists, in order, of a fixed 16-byte prefix, canonical JSON metadata, and a raw-frame body only when required.

### 13.1 Fixed Prefix

| Offset | Size | Type | Value |
|---:|---:|---|---|
| 0 | 4 | byte | ASCII `WHA1`, hex `57 48 41 31` |
| 4 | 1 | u8 | wire major version `1` |
| 5 | 1 | u8 | `1=start`, `2=frame`, `3=gap`, `4=end` |
| 6 | 2 | u16be | flags, always `0` |
| 8 | 4 | u32be | metadata length |
| 12 | 4 | u32be | body length |

Metadata is 2–8192 bytes. The body is exactly 2,764,800 bytes for a frame and zero bytes otherwise. The decoder reads the complete prefix and validates version, kind, flags, and lengths before allocating a buffer. Because a pipe read may be split, it must not assume one read returns the entire record.

Compression, chunking, extra trailers, another pixel body, unknown flags, and version downgrade are prohibited.

### 13.2 Canonical JSON

Metadata is a top-level UTF-8 JSON object. Keys are sorted by Unicode code point; unnecessary whitespace is omitted; booleans and null are lowercase. Integers are decimal and may not use unnecessary leading zeros, `+`, decimals, exponent notation, NaN, or Infinity. BOMs, comments, duplicate keys, unknown or missing keys, arrays, and unknown nested objects are rejected.

After parsing, the decoder re-encodes under the same rules and rejects the metadata unless it exactly matches the original bytes. If Python and C# differ, the cross-language conformance vectors committed to the repository are authoritative.

### 13.3 Common Fields

| Field | Condition |
|---|---|
| `schema` | `whole-home-agent.capture-message.v1` |
| `kind` | one of `start`, `frame`, `gap`, `end` |
| `capture_session_id` | constant within the session |
| `source_id` | constant within the session |

The prefix kind and metadata kind must match.

### 13.4 start

`start` is sent exactly once and first. The body is zero bytes. Additional fields are:

| Field | Condition |
|---|---|
| `source_profile` | currently only `generated_stream_d0`; add `windows_webcam_d1_v1` after future authorization |
| `capture_config_hash` | lowercase SHA-256, 64 characters |
| `width`, `height` | `1280`, `720` |
| `pixel_format` | `rgb24` |
| `target_fps_numerator`, `target_fps_denominator` | `10`, `1` |
| `started_monotonic_ns` | unsigned 64-bit integer |
| `activation_decision_id` | `null` for generated input; opaque reference for authorized live input |
| `policy_version` | `null` for generated input; adopted-policy reference for authorized live input |
| `raw_retention` | `none` |
| `audio_enabled` | `false` |
| `network_egress_enabled` | `false` |

The activation ID and policy version are evidence references; the message itself does not create authority.

### 13.5 frame

Additional frame metadata fields are below. RGB bytes are placed in the record body, not base64-encoded into metadata.

| Field | Condition |
|---|---|
| `source_sequence` | matches the next position expected by the decoder |
| `captured_monotonic_ns` | at or after start and nondecreasing from the preceding message |
| `width`, `height` | `1280`, `720` |
| `pixel_format` | `rgb24` |

The body length is exactly 2,764,800 bytes. Raw bytes must not be emitted to logs, exceptions, JSON, SQLite, files, presenters, or model context.

### 13.6 gap

A gap explicitly represents positions that could not be sent. The body is zero bytes.

| Field | Condition |
|---|---|
| `first_missing_sequence` | next position expected by the decoder |
| `last_missing_sequence` | at least first and no greater than 299 |
| `detected_monotonic_ns` | at or after start and nondecreasing from the preceding message |
| `reason` | `capture_overrun`, `queue_overflow`, or `source_unavailable` |

The next position after a gap is `last_missing_sequence + 1`. A gap of three or more positions requires resetting ROI temporal state.

### 13.7 end

`end` is sent exactly once and last. The body is zero bytes.

| Field | Condition |
|---|---|
| `status` | `SEALED`, `ABORTED`, or `FAILED` |
| `last_source_sequence` | last accounted position, or `null` if empty |
| `frame_count` | number of frame messages |
| `dropped_frame_count` | number of gap positions |
| `ended_monotonic_ns` | at or after all message timestamps |
| `stream_sha256` | lowercase 64-character value only for `SEALED`; otherwise `null` |
| `failure_code` | `null` for `SEALED`; otherwise a fixed code |

For a nonempty stream, `frame_count + dropped_frame_count = last_source_sequence + 1`; for an empty stream, both counts are zero. For a normal 300-position session, `last_source_sequence=299`.

Only these capture failure codes are allowed:

- `CAPTURE_CANCELLED`
- `CAPTURE_PIPE_FAILED`
- `CAPTURE_DEVICE_LOST`
- `CAPTURE_FORMAT_CHANGED`
- `CAPTURE_TIMEOUT`
- `CAPTURE_RESOURCE_RELEASE_FAILED`
- `CAPTURE_INTERNAL_FAILED`

## 14. Stream Digest

CaptureHost and SemanticHost independently compute the stream SHA-256. The preimage is ordered as follows:

```text
UTF-8("whole-home-agent.capture-stream.v1\0")
raw 32 bytes of capture_config_hash
u64be(width) || u64be(height)
u64be(target_fps_numerator) || u64be(target_fps_denominator)
UTF-8("rgb24\0")
For each frame:
  0x46 || u64be(source_sequence)
       || u64be(captured_monotonic_ns - started_monotonic_ns)
       || u64be(len(rgb_bytes)) || rgb_bytes
For each gap:
  0x47 || u64be(first_missing_sequence) || u64be(last_missing_sequence)
       || u64be(detected_monotonic_ns - started_monotonic_ns)
       || reason_code
```

Reason codes are `capture_overrun=0x01`, `queue_overflow=0x02`, and `source_unavailable=0x03`. `u64be` means unsigned 64-bit big-endian.

The decoder compares `end.stream_sha256` in constant time. A mismatch fails the session and prevents a successful result from passing beyond ROI. The digest identifies only the received bytes; it does not prove camera authenticity, capture time, scene completeness, or real-world facts. Per-frame hashes are not retained in logs or receipts.

## 15. Named Pipe and Connection Authentication

The logical pipe name is:

```text
\\.\pipe\LOCAL\wha.capture.v1.<session_nonce>
```

`session_nonce` is 128 random bits generated per session and represented as 32 lowercase hexadecimal characters. It is for routing, not an authentication, consent, or authorization token, and is not retained after the session.

The pipe uses byte mode and asynchronous operation, with SemanticHost inbound-only, CaptureHost outbound-only, one server instance, and one client. SemanticHost does not use the default security descriptor; it grants only the minimum required rights to the exact CaptureHost and SemanticHost AppContainer SIDs and denies the Anonymous and Network SIDs.

SemanticHost verifies the connecting client process token and package/AppContainer SID. CaptureHost verifies the server process token and SemanticHost package identity. Impersonation is disabled. If identity cannot be verified, the process exits without opening the camera.

The activation mechanism that passes the nonce to CaptureHost is validated for feasibility on Windows packages and fixed in R2. It must not use a file, registry, environment variable, clipboard, TCP, user question, or model output.

## 16. ROI Ingress Contract

The invocation order uses this logical API:

```python
roi.open_session(RoiIngressSessionV1) -> None
roi.accept(RoiIngressFrameV1, RoiFrameLeaseV1) -> RoiAcceptResultV1
roi.accept_gap(RoiIngressGapV1) -> None
roi.close_session(RoiIngressEndV1) -> None
roi.abort_session(RoiIngressEndV1 | None) -> None
```

Calls are single-threaded, non-reentrant, and sequence-ordered. `close_session` is called exactly once only for a normal `SEALED` session. For `ABORTED`, `FAILED`, or decoder failure, idempotent `abort_session` is called once.

### 16.1 RoiIngressSessionV1

The session value contains schema, capture/session ID, source profile, capture configuration hash, ROI profile, ROI configuration hash, ROI implementation version, width, height, pixel format, layout, stride, origin, axes, rotation, mirroring, color interpretation, target FPS, start QPC, maximum positions, maximum gap, and raw retention.

Layout and related values come from hashed local configuration; unknown values specified by a frame message are not adopted.

### 16.2 RoiIngressFrameV1

| Field | Condition |
|---|---|
| `schema` | `whole-home-agent.roi-ingress-frame.v1` |
| `capture_session_id` | matches the open session |
| `source_sequence` | validated position |
| `source_offset_ns` | capture timestamp minus session start |
| `captured_monotonic_ns` | validated QPC time |
| `width`, `height`, `pixel_format` | match the session |
| `layout`, `row_stride_bytes` | `HWC_CONTIGUOUS`, `3840` |
| `origin`, `rotation_degrees`, `mirrored` | `top_left`, `0`, `false` |
| `payload_length` | `2764800` |

Pixel bytes are not included in the descriptor and are passed only through `RoiFrameLeaseV1`. Pixels must not appear in repr output, JSON, exceptions, or logs.

### 16.3 RoiFrameLeaseV1

The lease provides a contiguous read-only view of 2,764,800 bytes and a single-use `release()`.

- At most one lease is valid at a time.
- ROI calls `release()` exactly once before returning from `accept`.
- ROI does not retain the full-frame view or an alias.
- ROI does not modify the backing buffer.
- Double release, failure to release, and access after release are classified as `ROI_BUFFER_LEAK`.
- `accept` completes within 100,000,000 ns measured using SemanticHost QPC.
- If asynchronous full-frame retention is needed, design a new version instead of relaxing v1.

### 16.4 RoiIngressGapV1

The gap value contains schema, session/source IDs, inclusive missing range, detection QPC, offset from start, reason, and `reset_temporal_state`. Reset is true only for a gap length of at least three. `accept_gap` is called before any subsequent frame and completes within 100,000,000 ns.

### 16.5 RoiAcceptResultV1

| Field | Condition |
|---|---|
| `schema` | `whole-home-agent.roi-accept-result.v1` |
| `capture_session_id` | matches the submitted frame |
| `source_sequence` | matches the submitted frame |
| `status` | `ACCEPTED` or `REJECTED` |
| `reason_code` | `null` if accepted; fixed code if rejected |
| `accepted_monotonic_ns` | QPC if accepted; `null` if rejected |
| `roi_ingress_version` | matches the open session |
| `roi_config_hash` | matches the open session |

Rejection codes are limited to `ROI_REJECT_CAPACITY`, `ROI_REJECT_UNAVAILABLE`, and `ROI_REJECT_INTERNAL`. The first rejection, exception, or timeout ends the session. `ACCEPTED` means only delivery acceptance; it does not mean ROI discovery, object detection, a claim, or a real-world fact.

## 17. Buffer Ownership and Backpressure

The application limit is five full-frame buffers:

| Owner | Limit | Release point |
|---|---:|---|
| CaptureHost outbound queue | 3 | record write completion or pipe failure |
| SemanticHost decoder | 1 | ROI lease creation or validation failure |
| ROI ingress lease | 1 | ROI `release()` |
| Total | 5 | must not be exceeded |

Because one frame is 2,764,800 bytes, the application payload limit is 13,824,000 bytes. This excludes Windows driver buffers, internal pipe buffers, managed objects, fixed headers, and temporary conversion surfaces; these are measured separately.

CaptureHost retains at most one application-visible `MediaFrameReference` at a time and disposes it immediately after conversion or rejection. The camera callback does not wait for pipe I/O or ROI processing; it copies into a free slot or records a gap. It does not create an unbounded task, queue, list, or byte array for every callback.

When the queue is full, an old queued frame is not overwritten by a new frame. Instead, the new position is recorded as `queue_overflow`. Gap metadata does not consume a raw-frame slot.

## 18. State Transitions

CaptureHost transitions in this order:

```text
CREATED
  -> PIPE_CONNECTING
  -> PIPE_READY
  -> CAMERA_OPENING
  -> READER_READY
  -> STREAMING
  -> FINISHING
  -> SEALED
  -> CLOSING
  -> CLOSED
```

Cancel transitions `STREAMING -> ABORTING -> ABORTED -> CLOSING`. A failure transitions from any nonterminal state to `FAILED -> CLOSING`. Processing never resumes from a terminal state.

In `FINISHING`, the host stops generating positions, sends pending frames/gaps, stops and disposes the reader and camera, and sends `SEALED end` only after successful release. If camera release fails, it sends `FAILED/CAPTURE_RESOURCE_RELEASE_FAILED` when possible.

The SemanticHost decoder transitions as follows:

```text
LISTENING
  -> WAIT_START
  -> OPENING_ROI
  -> ACTIVE
  -> VERIFYING
  -> COMPLETE
  -> CLOSED
```

On a protocol, pipe, ROI, timeout, digest, or resource error, it immediately enters `FAILED`, sends no more frames to ROI, and performs only bounded cleanup. It rejects a second start, second client, post-end message, EOF before end, and unexplained sequence loss.

## 19. Timeouts and Operations

| Operation | Limit | Action |
|---|---:|---|
| Pipe connection and mutual identity verification | 5 s | fail before camera open |
| Camera/reader initialization | 5 s | close resources and fail |
| Camera open-to-close | 37 s | force close and fail |
| No pipe progress after start | 1 s | fail session |
| ROI frame accept | 100 ms | `ROI_CONSUMER_TIMEOUT` |
| ROI gap accept | 100 ms | fail session |
| Pending gap/end flush | 2 s | do not seal |
| CaptureHost reader/camera cleanup | 2 s | `CAPTURE_RESOURCE_RELEASE_FAILED` if end can be sent; otherwise controller failure evidence |
| SemanticHost pipe/ROI/buffer cleanup | 2 s | `ROI_RESOURCE_RELEASE_FAILED` |

Timeouts are measured with QPC.

Finish stops generation of new positions, flushes accounted messages, normally releases the camera, and attempts to seal. Cancel does not create a seal and sends `ABORTED` when possible. Closing the window during capture is treated as Cancel, not reinterpreted as Finish.

## 20. Delivery Failure Codes

The ROI delivery receipt allows only:

- `ROI_SCHEMA_INVALID`
- `ROI_SESSION_MISMATCH`
- `ROI_SEQUENCE_INVALID`
- `ROI_DIMENSION_MISMATCH`
- `ROI_PIXEL_FORMAT_INVALID`
- `ROI_LAYOUT_INVALID`
- `ROI_PAYLOAD_SIZE_INVALID`
- `ROI_QUEUE_FULL`
- `ROI_CONSUMER_TIMEOUT`
- `ROI_CONSUMER_REJECTED`
- `ROI_BUFFER_LEAK`
- `ROI_DIGEST_MISMATCH`
- `ROI_PIPE_CLOSED`
- `ROI_EARLY_END`
- `ROI_RESOURCE_RELEASE_FAILED`

The first terminal failure becomes the receipt’s `failure_code`. Additional cleanup failures do not overwrite the first cause; they are represented by `resource_release_ok=false`. Public receipts do not include exception types, stack traces, device names, pipe names, or frame contents.

If peer identity, DACL, camera permission, device enrollment, format, or initialization fails before start, no ROI session exists and an ROI receipt is not fabricated. The trusted controller records a separate sanitized launch failure.

Camera format launch failure codes are limited to:
- `LAUNCH_CAMERA_EXCLUSIVE_CONTROL_UNAVAILABLE`
- `LAUNCH_CAMERA_FORMAT_NOT_FOUND`
- `LAUNCH_CAMERA_FORMAT_AMBIGUOUS`
- `LAUNCH_CAMERA_FORMAT_SET_FAILED`
- `LAUNCH_CAMERA_FORMAT_VERIFY_FAILED`

Launch records must not contain device IDs, format enumeration lists, exception text, or frame data. If the format changes after start, the existing stream error code `CAPTURE_FORMAT_CHANGED` applies.

## 21. RoiDeliveryReceiptV1

The receipt is created exactly once after session termination and ROI cleanup.

| Field | Condition |
|---|---|
| `schema` | `whole-home-agent.roi-delivery-receipt.v1` |
| `capture_session_id`, `source_id` | session IDs |
| `capture_config_hash`, `roi_config_hash` | resolved configuration hashes |
| `roi_ingress_version` | fixed consumer version |
| `stream_sha256` | verified hash for SEALED; otherwise `null` |
| `source_end_status` | `SEALED`, `ABORTED`, or `FAILED` |
| `source_failure_code` | capture failure code or `null` |
| `status` | `COMPLETE`, `ABORTED`, or `FAILED` |
| `first_source_sequence`, `last_source_sequence` | `0` and final value if nonempty; both `null` if empty |
| `acquisition_positions` | total accounted positions |
| `frame_messages_received` | validated frame count |
| `roi_frames_accepted` | accepted and released frame count |
| `gap_positions` | total gap positions |
| `roi_frames_rejected` | valid rejection count |
| `capture_overrun_positions` | corresponding gap count |
| `queue_overflow_positions` | corresponding gap count |
| `source_unavailable_positions` | corresponding gap count |
| `delivery_latency_p50_ns` | nearest-rank p50 when available |
| `delivery_latency_p95_ns` | nearest-rank p95 when available |
| `delivery_latency_max_ns` | maximum when available |
| `peak_application_frame_slots` | 0–5 |
| `clock_basis_verified` | cross-process QPC verification result |
| `resource_release_ok` | bounded-release result for all resources |
| `failure_code` | `null` if complete; otherwise fixed code |
| `raw_retention` | `none` |

Counts satisfy:

```text
acquisition_positions = 0                         # if empty
acquisition_positions = last_source_sequence + 1  # if nonempty
gap_positions = Σ(last_missing - first_missing + 1)
acquisition_positions = frame_messages_received + gap_positions
gap_positions = capture_overrun_positions
              + queue_overflow_positions
              + source_unavailable_positions
```

Latency is `accepted_monotonic_ns - captured_monotonic_ns`; negative values are rejected. Values are sorted ascending and use the nearest-rank index `ceil(p * n) - 1`. If there are no accepted frames, latency fields are `null`.

`COMPLETE` is allowed only if all conditions below hold:

1. The start/frame/gap/end order and every field are correct.
2. Source end is `SEALED` and source failure is `null`.
3. The stream digest matches.
4. Every position is accounted for exactly once as a frame or gap.
5. Every received frame is accepted by ROI and there are zero rejections.
6. Every lease is released exactly once.
7. There is no timeout, pipe loss, second client, or unhandled exception.
8. `resource_release_ok=true`.
9. Raw bytes were not written to a file, log, exception, SQLite, presenter, or model.
10. The receipt itself passes exact-field validation.

Status priority is: `FAILED` for any local failure; then `FAILED` for source `FAILED`; `ABORTED` for source `ABORTED`; and `COMPLETE` only for source `SEALED` with all conditions satisfied.

## 22. Logging, Retention, and Privacy

Structured logs are limited to component/build version, sanitized profile/configuration hash, opaque session ID, state transitions, frame/gap/rejection counts, queue depth, aggregate timing, fixed failure codes, clock basis, resource release, and final status.

The following must not appear in logs, receipts, files, SQLite, or model context:

- Raw RGB bytes, base64, thumbnails, crops, or pixel samples
- Per-frame hashes
- Camera device IDs or names
- Package tokens, pipe nonce, or full pipe name
- Person names, room names, addresses, or full queries
- Credentials or the full text of consent or authority
- Provider/model payloads
- Exception text containing frame data

Raw frames are transient. Best-effort overwrite before returning a buffer to the pool is permitted, but the system must not claim guaranteed erasure of every internal copy held by Windows, drivers, or the managed runtime.

## 23. Development Isolation

| Surface | Permitted | Prohibited |
|---|---|---|
| Existing Python base/demo | B0/B1, fixed video, UI | camera dependency, device enumeration, live route |
| `stream_sim_d0` | pure contract, validator, generated frames | Windows camera APIs, private data, network |
| CaptureHost package | camera, RGB conversion, pipe writer, visible controls | ROI, detector, ledger, SQLite, LLM, network, audio |
| SemanticHost package | pipe reader, ROI ingress, fixed Python | webcam/mic/network capability, camera APIs, D1 storage |
| Hardware test lane | exact signed package, registered test camera | unattended CI, homes, people, cloud, reusable credentials |

The Windows project is restored and built only under an explicitly specified Windows build target. Ordinary `uv run`, help, import, editable install, macOS/Linux tests, and Streamlit startup must not invoke the Windows package or camera backend.

Black-box tests verify AppContainer, manifest, DACL, network denial, filesystem denial, unexpected child processes, and camera-capability placement. Manifest declarations alone are not proof of isolation.

## 24. Implementation Stages

### R0 Document Review

Review this document and confirm that ROI means the ingress, as well as the fixed values, wire format, lease, timeouts, receipt, and completion criteria. Add no code, dependencies, packages, or device permissions.

### R1 Pure Python Generated Contract

Implement immutable values, strict validators, canonical JSON, wire codec, digest, receipt calculator, generated producer, and fake ROI. Do not add Windows APIs or camera dependencies.

Happy-path cases include empty seal, one frame, 300 frames, one- or two-position gaps, temporal reset for a gap of at least three, early Finish, and round trip. Failure cases include missing/extra fields, wrong types, bad magic/version/flags/lengths, invalid UTF-8, duplicate JSON keys, frame before start, duplicate start/end, post-end data, missing/reversed/duplicate sequences, timestamp regression, overflow, size/layout mismatch, invalid gap, digest corruption, ROI rejection/exception/timeout, double/no release, partial pipe reads, a sixth slot, cancel, and cleanup failure.

The camera remains unusable after R1 completion.

### R2 Cross-Package Testing with Windows-Generated Frames

First execute **R2A**: using a minimal binary, verify whether two separate non-full-trust AppContainers can establish and use a named pipe. Because Microsoft general IPC documentation and `ConnectNamedPipe` documentation contain conflicting descriptions, merging into a single package or using `runFullTrust` to evade restrictions is strictly prohibited. If R2A fails, return to the `DECIDE` phase to re-select the local IPC mechanism.

Only after R2A passes, build CaptureHost and SemanticHost in separate AppContainers and send the same generated vectors as R1 instead of using camera APIs. Verify package identity, manifest, DACL, wrong SID, second client, partial I/O, backpressure, Python/C# byte equality, QPC consistency, process termination, and network/filesystem denial.

Confirm zero camera permission prompts and zero device enumeration.

### R3 Fault and Isolation Testing

Inject queue saturation, slow ROI, pipe break, malformed metadata, oversize values, digest corruption, wrong package, repeated launch, cancellation in every state, and process crash. Confirm every case fails closed and leaves no raw data, fallback source, full-trust route, or network route.

### R4 Separately Authorized Physical-Device Acceptance

R4 is not executed now. It requires adopted policy, role assignment, registration of the camera and a non-household field of view, required consent, fixed package/configuration hashes, and an activation decision with an execution deadline.

Before the positive run, verify permission denial, absent/wrong device, unsupported format, second client, Cancel, Finish, pipe break, and process crash. Then conduct one human-initiated run of at most 30 seconds against a generated calibration target containing neither people nor private spaces.

## 25. R4 Acceptance Criteria

A future positive physical-device run passes only if all of the following hold:

| Metric | Condition |
|---|---|
| Acquisition positions | 300 |
| Emitted frames accepted/released by ROI | all |
| ROI rejected | 0 |
| Capture-overrun gaps | 0 |
| Queue-overflow gaps | 0 |
| Source-unavailable gaps | 0 |
| p95 capture-to-accept | no more than 100,000,000 ns |
| Max capture-to-accept | no more than 300,000,000 ns |
| Peak application raw-frame slots | no more than 5 |
| Camera open-to-close | no more than 37,000,000,000 ns |
| Raw file/log/SQLite writes | 0 |
| Network connections/bytes sent | 0 |
| Clock basis verified | `true` |
| Resource release | `true` |
| Receipt status | `COMPLETE` |

Passing demonstrates only capture-to-ROI delivery for the specified Windows build, package, camera, driver, configuration, generated scene, and activation. It does not prove ROI accuracy, object recognition, household use, or 24-hour operation.

## 26. Test Vectors

R1 fixes a generated fixture package containing:

- A manifest with fixture ID, schema version, generator version, origin/license, content hash, and intended use
- Canonical metadata bytes for every message kind
- A deterministic non-photographic RGB pattern
- Expected 16-byte prefixes
- Complete wire records
- Digest preimages and SHA-256 values
- Canonical JSON for ROI session/frame/gap/result/receipt values
- Expected failures after a one-byte or one-field change

RGB patterns include black, white, red, green, blue, row/column ramps, asymmetric corner markers, and boundary coordinates to detect channel swaps, stride, rotation, mirroring, and off-by-one errors. Golden files are not regenerated automatically merely because they fail.

## 27. Handoff Items for the ROI Owner

The capture owner provides the ROI owner with:

1. This integrated specification
2. Immutable public types for ROI session/frame/gap/end/result
3. Strict validators
4. The synchronous ROI interface
5. Generated input and conformance vectors
6. Lease-misuse tests
7. Receipt schema and formulas
8. Coordinate, layout, and color tests
9. Timeout and slot limits, plus fault-injection hooks

Camera handles, pipe handles, device IDs, private frame sets, credentials, ledgers, databases, LLM/model interfaces, and action interfaces are not handed over.

## 28. Completion Criteria for This Work

Under current authority, work is complete when R0–R3 satisfy all of the following:

- This document’s interpretation of the ROI ingress is confirmed.
- All R1 happy-path and failure-path conformance tests pass.
- R2 passes Python/C# framing, package isolation, peer identity, QPC, lease, and cleanup tests without a camera.
- R3 confirms fail-closed behavior and resource limits.
- Existing B0/B1 results are unchanged.
- The normal Python path has no camera import, camera dependency, or device enumeration.
- Raw pixels do not enter disk, SQLite, logs, errors, presenters, or models.
- A live source cannot be enabled via environment variable, prompt, model, normal CLI, or import.
- Generated receipts are reproducible and pass exact-field validation.

R4 requires separate operational authorization and physical-device verification and is not part of the current completion criteria.

## 29. Stop Conditions

Stop implementation and return to design decisions if any of the following occurs:

- ROI means crop output rather than the ingress defined here.
- ROI must retain a full frame asynchronously.
- The fixed resolution and cadence cannot be obtained without resizing or driver fallback.
- Package or pipe peer identity cannot be verified.
- SemanticHost requires webcam or network capability.
- Named pipes cannot be used safely between the two AppContainers.
- Cross-process QPC cannot be verified.
- Five frame slots or the timeout limits are insufficient.
- Debugging/evaluation requires raw-media storage.
- A person or private space enters the field of view.
- An unpackaged/full-trust camera fallback is proposed.
- Live execution is required before policy adoption and activation.

Safe generated testing may continue, but restrictions must not be silently relaxed in code, configuration, tests, or documentation.

## 30. Final Deliverables

The final deliverables under this specification are not webcam footage or recognition results, but these four outcomes:

1. Generated input and future camera input are converted to the same contract.
2. Frames, gaps, start, and end can be delivered finitely and verifiably between isolated Windows processes.
3. Acceptance and release of each frame by the ROI ingress can be accounted for per session.
4. Success or failure can be explained through a sanitized receipt without retaining raw frames.

Only after these conditions are met may the webcam-to-ROI-ingress delivery component be described as complete. Subsequent ROI computation, object detection, tracking, claims, memory, and question answering are separate responsibilities with separate specifications and verification.

## 31. Relevant Primary Windows Documentation

- [MediaCapture initialization](https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.mediacapture.initializeasync)
- [MediaFrameReader](https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.frames.mediaframereader)
- [MediaCapture sharing mode](https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.mediacaptureinitializationsettings.sharingmode)
- [Camera privacy controls](https://support.microsoft.com/en-us/windows/manage-app-permissions-for-your-camera-in-windows-87ebc757-1f87-7bbf-84b5-0686afb6ca6b)
- [App capability declarations](https://learn.microsoft.com/en-us/windows/uwp/packaging/app-capability-declarations)
- [Windows application packaging and deployment](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/)
- [AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)
- [Named pipes](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipes)
- [Named-pipe security and access rights](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
- [QueryPerformanceCounter](https://learn.microsof

> Note: The final QueryPerformanceCounter URL is truncated in the supplied source text and has therefore been preserved as supplied.
