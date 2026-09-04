# ADR 0027: Use synchronous read-only lease and bounded memory for ROI ingress

- Status: `PROPOSED`
- Date: 2026-09-04
- Scope: Ingress memory management and downstream ROI delivery interface (`whole-home-agent.roi-ingress-frame.v1`)

## Context

Streaming uncompressed 1280×720 RGB24 video generates approximately $27.65\text{ MB/s}$ of continuous memory throughput at 10 Hz. If downstream ROI processing retains references, queues raw frames, or creates defensive buffer copies, application memory will quickly balloon, triggering severe garbage collection pauses and pipeline latency spikes. Furthermore, the boundary between image delivery and downstream ROI computation must be clearly defined so that capture responsibilities are strictly separated from semantic reasoning and object recognition.

## Decision

To manage memory predictably and establish a strict handoff boundary:

- Define the delivery boundary as the synchronous ingress call:
  ```python
  roi.accept(frame: RoiIngressFrameV1, lease: RoiFrameLeaseV1) -> RoiAcceptResultV1
  ```
- Enforce a strict 5-frame application memory ceiling ($\approx 13.18\text{ MiB}$):
  - At most 3 frames in `CaptureHost` outbound queue
  - At most 1 frame in `SemanticHost` decoder read buffer
  - At most 1 active lease at ROI ingress
- Implement zero-copy access via `RoiFrameLeaseV1`:
  - Exposes a contiguous, read-only `memoryview` of the 2,764,800-byte RGB24 buffer.
  - Requires the ROI ingress to invoke `lease.release()` exactly once before returning from `accept()`.
  - Forbids retaining persistent references to the backing memory, caching slices, or asynchronous escaping.
  - Treats double-release, access after release, or failure to release as a fatal `ROI_BUFFER_LEAK` failure.
- Bound ROI ingress execution time to at most 100 ms ($100,000,000\text{ ns}$); exceeding this deadline triggers `ROI_CONSUMER_TIMEOUT`.
- Output a comprehensive `RoiDeliveryReceiptV1` at session end accounting for all positions ($0..299$), delivered frames, recorded gaps, latency percentiles (p50, p95, max), and verifying zero raw data retention.

## Alternatives

- Immutable copying per frame: Rejected because allocating and copying $2.76\text{ MB}$ 10 times per second causes massive GC overhead and memory churn.
- Asynchronous unbounded queue to ROI: Rejected because backpressure cannot be guaranteed, violating the 5-frame memory ceiling and masking downstream consumer overload.
- Ingress returning cropped bounding boxes directly: Rejected because ROI selection and feature extraction belong to downstream perception modules, not to the capture adapter.

## Consequences

- Peak application memory for raw video is structurally capped at $13.18\text{ MiB}$.
- Downstream ROI processing must sample necessary features synchronously within the 100 ms window.
- The delivery receipt provides an auditable, cryptographic proof of correct delivery without persisting any raw frames to disk or SQLite.
