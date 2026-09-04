# ADR 0026: Use fixed-prefix and canonical JSON wire protocol for capture IPC

- Status: `PROPOSED`
- Date: 2026-09-04
- Scope: IPC wire format, serialization, and stream verification (`whole-home-agent.capture-message.v1`)

## Context

Streaming high-resolution video frames (1280×720 RGB24 at 10 Hz) across an IPC boundary between C# and Python requires a robust, unambiguous wire protocol. Complex binary serialization frameworks (Protocol Buffers, gRPC, MessagePack) introduce large runtime dependencies, potential schema drift, and variable-length parsing vulnerabilities. Conversely, ad-hoc binary layouts make cross-language conformance testing difficult and fail to explicitly represent temporal gaps or verify stream completeness.

## Decision

To standardize inter-process frame transport:

- Adopt `whole-home-agent.capture-message.v1` using a fixed 16-byte binary prefix followed by canonical JSON metadata and an optional raw binary payload:
  - Offset `0..3`: 4 ASCII bytes `WHA1` (`0x57, 0x48, 0x41, 0x31`)
  - Offset `4`: `uint8` wire version (`1`)
  - Offset `5`: `uint8` message kind (`1=start`, `2=frame`, `3=gap`, `4=end`)
  - Offset `6..7`: `uint16be` reserved flags (must be `0`)
  - Offset `8..11`: `uint32be` metadata length ($2 \le L \le 8192$)
  - Offset `12..15`: `uint32be` body length ($2,764,800$ bytes for frames, $0$ otherwise)
- Format metadata strictly as canonical UTF-8 JSON: keys sorted by Unicode code point, minimal whitespace, lowercase booleans/null, decimal integers without exponents or leading zeros. The receiver parses and immediately re-encodes under identical rules, rejecting records whose bytes do not match byte-for-byte.
- Require explicit representation of missed positions via `gap` messages (`first_missing_sequence`, `last_missing_sequence`, `detected_monotonic_ns`, `reason`), ensuring that every temporal position $0 \le n < 300$ in a session is strictly accounted for.
- Compute an incremental, cross-process SHA-256 stream digest over ordered frame and gap records. `end` messages must present this hash in `stream_sha256`; the receiver verifies it in constant time before certifying a `SEALED` session.
- Reject compression, chunking, multiplexing, protocol downgrades, and unaligned reads. Fail closed on any framing, CRC, JSON, or digest error.

## Alternatives

- gRPC / Protocol Buffers: Rejected due to significant runtime dependencies, IPC socket overhead on Windows, and difficulty enforcing zero-copy payload boundaries.
- Shared Memory (Memory-Mapped Files): Rejected for initial stages because Named Pipes offer built-in asynchronous stream flow control, exact DACL security integration across AppContainers, and sequential read/write semantics without manual synchronization primitives. Shared memory may be considered in future revisions if pipe throughput proves inadequate.
- Base64-encoded JSON payloads: Rejected because encoding a $2.76\text{ MB}$ raw frame into Base64 expands the payload by 33% and creates massive GC memory pressure.

## Consequences

- Serialization is completely deterministic, transparent, and verifiable by both C# and Python.
- Pipe reads can be performed in exact two-stage chunks (16-byte prefix first, then exact metadata and body lengths).
- Gaps and dropped frames are explicit domain events, preventing silent frame skips from distorting temporal relations.
- Every completed session is cryptographically verifiable via its SHA-256 stream digest.
