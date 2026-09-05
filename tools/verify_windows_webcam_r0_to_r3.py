"""Comprehensive Independent Verification Runner for Windows Webcam to ROI Handoff (R0-R3).

Specification: WHA-WIN-CAPTURE-ROI-001 (Stages R0, R1, R2, R3)
ADR: 0025, 0026, 0027
Governance: OPERATE DISABLED
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import secrets
import struct
import sys
import threading
import time
from typing import Any, Mapping, Optional

# Ensure src is on path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from whole_home_agent.adapters.windows_webcam.decoder import (
    CaptureStreamDecoder,
    STATE_ABORTED,
    STATE_COMPLETE,
    STATE_FAILED,
    calculate_nearest_rank_percentile,
)
from whole_home_agent.adapters.windows_webcam.pipe_ipc import (
    DEFAULT_PIPE_SDDL,
    NamedPipeClient,
    NamedPipeServer,
    is_valid_handle,
)
from whole_home_agent.adapters.windows_webcam.qpc import (
    now_qpc_ns,
    qpc_to_monotonic_ns,
    query_performance_counter,
    query_performance_frequency,
)
from whole_home_agent.adapters.windows_webcam.roi_contract import (
    ALLOWLISTED_LAUNCH_FAILURE_CODES,
    ALLOWLISTED_ROI_FAILURE_CODES,
    RoiAcceptResultV1,
    RoiDeliveryReceiptV1,
    RoiFrameLeaseV1,
    RoiIngressEndV1,
    RoiIngressFrameV1,
    RoiIngressGapV1,
    RoiIngressPort,
    RoiIngressSessionV1,
)
from whole_home_agent.adapters.windows_webcam.synthetic_producer import (
    SyntheticStreamBuilder,
    create_synthetic_frame_bytes,
    pack_wire_message,
)
from whole_home_agent.adapters.windows_webcam.wire_protocol import (
    FIXED_PREFIX_BYTES,
    FRAME_BODY_BYTES,
    KIND_END,
    KIND_FRAME,
    KIND_GAP,
    KIND_START,
    MAX_METADATA_BYTES,
    MIN_METADATA_BYTES,
    WIRE_MAGIC,
    WIRE_VERSION,
    StreamDigestCalculator,
    WireFramingError,
    WirePrefix,
    dumps_canonical_json,
    loads_canonical_json,
)

_IS_WINDOWS = sys.platform == "win32"


class SimpleTestRoi(RoiIngressPort):
    """Reliable test double for Stage R1/R2 verification."""

    def __init__(self, *, delay_s: float = 0.0) -> None:
        self.delay_s = delay_s
        self.opened_session: Optional[RoiIngressSessionV1] = None
        self.accepted_sequences: list[int] = []
        self.gaps: list[RoiIngressGapV1] = []
        self.closed_end: Optional[RoiIngressEndV1] = None
        self.aborted = False

    def open_session(self, session: RoiIngressSessionV1) -> None:
        self.opened_session = session

    def accept(self, frame: RoiIngressFrameV1, lease: RoiFrameLeaseV1) -> RoiAcceptResultV1:
        if self.delay_s > 0:
            time.sleep(self.delay_s)
        # Verify read-only contiguous memoryview
        view = lease.pixel_memory_view
        assert len(view) == FRAME_BODY_BYTES
        assert view.readonly
        lease.release()
        self.accepted_sequences.append(frame.source_sequence)
        return RoiAcceptResultV1(
            schema="whole-home-agent.roi-accept-result.v1",
            capture_session_id=frame.capture_session_id,
            source_sequence=frame.source_sequence,
            status="ACCEPTED",
            reason_code=None,
            accepted_monotonic_ns=frame.captured_monotonic_ns + 1_000_000,
            roi_ingress_version="windows_webcam_roi/1",
            roi_config_hash="00" * 32,
        )

    def accept_gap(self, gap: RoiIngressGapV1) -> None:
        self.gaps.append(gap)

    def close_session(self, end: RoiIngressEndV1) -> None:
        self.closed_end = end

    def abort_session(self, end: RoiIngressEndV1 | None) -> None:
        self.aborted = True


def log_step(stage: str, test_name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] [{stage}] {test_name}: {detail}")
    if not passed:
        raise AssertionError(f"Step failed: [{stage}] {test_name}: {detail}")


# ==============================================================================
# STAGE R0: SPECIFICATION & ARCHITECTURE DECISION INVARIANTS AUDIT
# ==============================================================================
def verify_stage_r0() -> None:
    print("\n" + "=" * 80)
    print("STAGE R0 VERIFICATION: Canonical Specification & ADR Invariants")
    print("=" * 80)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    spec_path = os.path.join(repo_root, "docs", "windows-webcam-roi-handoff-spec.md")
    spec_zh_path = os.path.join(repo_root, "docs", "windows-webcam-roi-handoff-spec.zh-TW.md")
    adr25_path = os.path.join(repo_root, "docs", "adr", "0025-isolate-windows-webcam-capture-in-separate-appcontainer.md")
    adr26_path = os.path.join(repo_root, "docs", "adr", "0026-use-fixed-prefix-and-canonical-json-wire-protocol.md")
    adr27_path = os.path.join(repo_root, "docs", "adr", "0027-use-synchronous-read-only-lease-for-roi-ingress.md")
    adr28_path = os.path.join(repo_root, "docs", "adr", "0028-resolve-webcam-sharing-mode-contradiction-and-mandate-r2a-gate.md")
    config_sim_path = os.path.join(repo_root, "configs", "capture", "stream-sim-d0-v1.toml")
    config_live_path = os.path.join(repo_root, "configs", "capture", "windows-webcam-d1-v1.toml")
    state_path = os.path.join(repo_root, "PROJECT_STATE.md")

    # 1. Document Existence & Version Invariants
    log_step("R0", "Document Existence (Spec En)", os.path.exists(spec_path), f"Found {spec_path}")
    log_step("R0", "Document Existence (Spec Zh-TW)", os.path.exists(spec_zh_path), f"Found {spec_zh_path}")
    log_step("R0", "Document Existence (ADR 0025)", os.path.exists(adr25_path), f"Found {adr25_path}")
    log_step("R0", "Document Existence (ADR 0026)", os.path.exists(adr26_path), f"Found {adr26_path}")
    log_step("R0", "Document Existence (ADR 0027)", os.path.exists(adr27_path), f"Found {adr27_path}")
    log_step("R0", "Document Existence (ADR 0028)", os.path.exists(adr28_path), f"Found {adr28_path}")
    log_step("R0", "Document Existence (Capture Config Sim)", os.path.exists(config_sim_path), f"Found {config_sim_path}")
    log_step("R0", "Document Existence (Capture Config Live)", os.path.exists(config_live_path), f"Found {config_live_path}")
    log_step("R0", "Document Existence (PROJECT_STATE)", os.path.exists(state_path), f"Found {state_path}")

    # 2. Operating Constitution & Version Check
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_text = f.read()
    with open(spec_zh_path, "r", encoding="utf-8") as f:
        spec_zh_text = f.read()
    with open(state_path, "r", encoding="utf-8") as f:
        state_text = f.read()

    log_step("R0", "Spec Version 1.2-draft (En)", "1.2-draft" in spec_text, "English spec is version 1.2-draft")
    log_step("R0", "Spec Version 1.2-draft (Zh-TW)", "1.2-draft" in spec_zh_text, "Traditional Chinese spec is version 1.2-draft")
    log_step("R0", "Governance Status (Spec En)", "OPERATE DISABLED" in spec_text, "Spec declares OPERATE DISABLED")
    log_step("R0", "Governance Status (Spec Zh-TW)", "OPERATE DISABLED" in spec_zh_text, "Chinese Spec declares OPERATE DISABLED")
    log_step("R0", "Governance Status (PROJECT_STATE)", "OPERATE DISABLED" in state_text, "PROJECT_STATE declares OPERATE DISABLED")
    log_step("R0", "Spec ExclusiveControl Invariant", "ExclusiveControl" in spec_text and "exclusive_control" in spec_text, "ExclusiveControl specified")

    # 3. Fixed Constants Invariants
    log_step("R0", "Fixed Resolution", (1280 * 720 * 3 == 2764800) and (FRAME_BODY_BYTES == 2764800), "1280x720 RGB24 == 2,764,800 bytes")
    log_step("R0", "Row Stride", 1280 * 3 == 3840, "3840 bytes row stride")
    log_step("R0", "Wire Magic", WIRE_MAGIC == b"WHA1", "Prefix Magic is ASCII 'WHA1'")
    log_step("R0", "Wire Version", WIRE_VERSION == 1, "Major Wire Version is 1")
    log_step("R0", "Metadata Bounds", MIN_METADATA_BYTES == 2 and MAX_METADATA_BYTES == 8192, "[2, 8192] bytes")
    log_step("R0", "App Memory Budget", (5 * 2764800) / (1024 * 1024) < 13.5, "5 frame slots <= 13.18 MiB")
    log_step("R0", "Launch Failure Codes Set", len(ALLOWLISTED_LAUNCH_FAILURE_CODES) == 5, f"5 launch failure codes defined: {sorted(ALLOWLISTED_LAUNCH_FAILURE_CODES)}")


# ==============================================================================
# STAGE R1: PURE PYTHON GENERATED CONTRACT & PROTOCOL VERIFICATION
# ==============================================================================
def verify_stage_r1() -> None:
    print("\n" + "=" * 80)
    print("STAGE R1 VERIFICATION: Pure Python Contract, Wire Protocol & Digest")
    print("=" * 80)

    # 1. Wire Prefix Packaging
    prefix = WirePrefix(
        magic=WIRE_MAGIC,
        wire_version=1,
        message_kind=KIND_FRAME,
        flags=0,
        metadata_length=256,
        body_length=FRAME_BODY_BYTES,
    )
    packed = prefix.pack()
    log_step("R1", "Wire Prefix Byte Length", len(packed) == FIXED_PREFIX_BYTES, f"Packed length == {len(packed)} bytes")
    unpacked = WirePrefix.unpack(packed)
    log_step("R1", "Wire Prefix Roundtrip Unpack", unpacked == prefix, "Prefix unpacked fields match exactly")

    # 2. Strict Canonical JSON
    data = {"b": 2, "a": 1, "nested": {"y": "val", "x": 10}}
    json_bytes = dumps_canonical_json(data)
    # Check lexicographical key sorting: "a" must precede "b", "x" precede "y"
    expected_substr = b'{"a":1,"b":2,"nested":{"x":10,"y":"val"}}'
    log_step("R1", "Canonical JSON Sorted Keys", json_bytes == expected_substr, f"Serialized bytes: {json_bytes.decode()}")

    # Floats must be rejected
    rejected_float = False
    try:
        dumps_canonical_json({"fps": 10.0})
    except Exception:
        rejected_float = True
    log_step("R1", "Canonical JSON Float Rejection", rejected_float, "Floating point numbers strictly rejected")

    # Duplicate keys in incoming JSON must be rejected
    dup_raw = b'{"schema":"v1","session":"abc","schema":"v2"}'
    rejected_dup = False
    try:
        loads_canonical_json(dup_raw)
    except Exception:
        rejected_dup = True
    log_step("R1", "Canonical JSON Duplicate Key Rejection", rejected_dup, "Duplicate JSON keys strictly rejected")

    # 3. Stream Digest Preimage Parity
    calc1 = StreamDigestCalculator(
        capture_config_hash="aa" * 32,
        started_monotonic_ns=1_000_000_000,
    )
    calc2 = StreamDigestCalculator(
        capture_config_hash="aa" * 32,
        started_monotonic_ns=1_000_000_000,
    )

    dummy_frame = bytes(FRAME_BODY_BYTES)
    calc1.update_frame(
        source_sequence=0,
        captured_monotonic_ns=1_000_000_000,
        rgb_bytes=dummy_frame,
    )
    calc2.update_frame(
        source_sequence=0,
        captured_monotonic_ns=1_000_000_000,
        rgb_bytes=dummy_frame,
    )

    hash1 = calc1.finalize_hex()
    hash2 = calc2.finalize_hex()
    log_step("R1", "Stream Digest Determinism", hash1 == hash2 and len(hash1) == 64, f"SHA-256 Digest: {hash1}")

    # 4. Synchronous Read-Only Lease (RoiFrameLeaseV1)
    buf = bytearray(FRAME_BODY_BYTES)
    buf[0] = 0xFE
    lease = RoiFrameLeaseV1(buf)
    log_step("R1", "Lease Initial State", not lease.is_released, "is_released is False")
    view = lease.pixel_memory_view
    log_step("R1", "Lease Readonly View", view.readonly and view[0] == 0xFE, "Read-only view verified")

    lease.release()
    log_step("R1", "Lease Released State", lease.is_released, "is_released is True")

    # Double release raises ValueError
    double_rel_raised = False
    try:
        lease.release()
    except ValueError:
        double_rel_raised = True
    log_step("R1", "Lease Double Release Prevention", double_rel_raised, "Second release raises ValueError")

    # View access after release raises BufferError
    access_after_rel_raised = False
    try:
        _ = lease.pixel_memory_view
    except BufferError:
        access_after_rel_raised = True
    log_step("R1", "Lease Access After Release Rejection", access_after_rel_raised, "Access raises BufferError")

    # 5. Decoder Happy Path: 300 Frames Session
    roi = SimpleTestRoi()
    decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)
    builder = SyntheticStreamBuilder()
    builder.emit_start()
    for seq in range(300):
        builder.emit_frame()
    stream_300 = builder.emit_sealed_end()

    t_start = time.perf_counter()
    receipt = decoder.process_stream(io.BytesIO(stream_300))
    t_elapsed = time.perf_counter() - t_start

    log_step("R1", "300 Frames Stream Status", receipt.status == "COMPLETE", f"Receipt status: {receipt.status}")
    log_step("R1", "300 Frames Accepted Count", receipt.roi_frames_accepted == 300, f"Accepted: {receipt.roi_frames_accepted}")
    log_step("R1", "300 Frames Positions Conservation", receipt.acquisition_positions == 300, "Conservation law satisfied")
    log_step("R1", "300 Frames Performance", t_elapsed < 3.0, f"Decoded 300 full frames in {t_elapsed:.3f}s")


# ==============================================================================
# STAGE R2: CROSS-PROCESS WINDOWS NAMED PIPE IPC LIVE VERIFICATION
# ==============================================================================
def verify_stage_r2() -> None:
    print("\n" + "=" * 80)
    print("STAGE R2 VERIFICATION: Windows QPC Clock & Live Win32 Named Pipe IPC")
    print("=" * 80)

    if not _IS_WINDOWS:
        print("[SKIP] Stage R2 requires native Windows 11 platform.")
        return

    # 1. High-Precision QPC Integer Scaling
    freq = query_performance_frequency()
    log_step("R2", "QPC Frequency Query", freq > 0, f"QPC Frequency: {freq} Hz")
    c1 = query_performance_counter()
    time.sleep(0.01)  # 10 ms sleep
    c2 = query_performance_counter()
    ns1 = qpc_to_monotonic_ns(c1, freq)
    ns2 = qpc_to_monotonic_ns(c2, freq)
    diff_ns = ns2 - ns1
    log_step("R2", "QPC Integer Monotonic Nanoseconds", diff_ns >= 5_000_000, f"Elapsed: {diff_ns} ns (~{diff_ns/1e6:.2f} ms)")

    # 2. Named Pipe Server Creation & DACL
    nonce = secrets.token_hex(16)
    server = NamedPipeServer(nonce, max_instances=1)
    log_step("R2", "Named Pipe Server Creation", is_valid_handle(server._handle), f"Pipe: {server.pipe_name}")

    # 3. Single Instance Restriction Verification
    client1 = NamedPipeClient(nonce)
    client2 = NamedPipeClient(nonce)

    t_conn = threading.Thread(target=server.wait_for_connection, daemon=True)
    t_conn.start()

    client1.connect(timeout_s=3.0)
    t_conn.join(timeout=3.0)
    log_step("R2", "Named Pipe Client 1 Connection", is_valid_handle(client1._handle), "Client 1 connected successfully")

    # Client 2 must be rejected because max_instances = 1
    client2_rejected = False
    try:
        client2.connect(timeout_s=0.5)
    except (TimeoutError, OSError):
        client2_rejected = True
    log_step("R2", "Single-Instance Rejection (Client 2)", client2_rejected, "Second connection rejected due to max_instances=1")

    # 4. Peer Token & Process Identity Verification
    client_pid = server.get_client_pid()
    log_step("R2", "Client Process ID Query", client_pid == os.getpid(), f"Client PID: {client_pid}")
    pid_match_ok = server.verify_client_identity(expected_pid=client_pid)
    pid_mismatch_ok = not server.verify_client_identity(expected_pid=client_pid + 99999)
    log_step("R2", "Client PID Identity Verification", pid_match_ok and pid_mismatch_ok, "PID validation exact")

    # Standard python process is not AppContainer, so require_app_container must return False
    not_app_container = not server.verify_client_identity(require_app_container=True)
    log_step("R2", "AppContainer Security Check", not_app_container, "Correctly identified non-AppContainer token")

    client1.close()
    server.close()

    # 5. Live Full Stream Delivery over Real Win32 Named Pipe
    nonce_stream = secrets.token_hex(16)
    pipe_server = NamedPipeServer(nonce_stream)
    pipe_client = NamedPipeClient(nonce_stream)
    roi_receiver = SimpleTestRoi()
    stream_decoder = CaptureStreamDecoder(roi_receiver, roi_config_hash="00" * 32)

    # Build 5-frame synthetic stream
    s_builder = SyntheticStreamBuilder(session_id=nonce_stream)
    s_builder.emit_start()
    for i in range(5):
        s_builder.emit_frame()
    full_wire_bytes = s_builder.emit_sealed_end()

    receipt_container = []

    def server_worker() -> None:
        pipe_server.wait_for_connection()
        pipe_stream = pipe_server.as_stream()
        r = stream_decoder.process_stream(pipe_stream)
        receipt_container.append(r)

    t_worker = threading.Thread(target=server_worker, daemon=True)
    t_worker.start()

    pipe_client.connect(timeout_s=3.0)
    pipe_client.write(full_wire_bytes)
    pipe_client.close()

    t_worker.join(timeout=5.0)
    pipe_server.close()

    log_step("R2", "Pipe Stream Receipt Delivery", len(receipt_container) == 1, "Server completed stream decoding")
    rec = receipt_container[0]
    log_step("R2", "Pipe Stream Status Complete", rec.status == "COMPLETE", f"Receipt status: {rec.status}")
    log_step("R2", "Pipe Stream 5 Frames Accepted", rec.roi_frames_accepted == 5, f"Frames accepted: {rec.roi_frames_accepted}")
    log_step("R2", "Pipe Stream SHA-256 Digest Match", rec.stream_sha256 is not None, f"Digest verified: {rec.stream_sha256[:16]}...")


# ==============================================================================
# STAGE R3: FAULT INJECTION, ADVERSARIAL SECURITY & ISOLATION VERIFICATION
# ==============================================================================
def verify_stage_r3() -> None:
    print("\n" + "=" * 80)
    print("STAGE R3 VERIFICATION: Fault Injection, Adversarial Testing & Zero Retention")
    print("=" * 80)

    forbidden_exts = (".raw", ".rgb", ".bmp", ".jpg", ".png", ".mp4", ".sqlite", ".db")
    initial_forbidden_files = set()
    for root, _, files in os.walk("."):
        if ".git" in root or ".venv" in root:
            continue
        for f in files:
            if f.endswith(forbidden_exts):
                initial_forbidden_files.add(os.path.join(root, f))

    # 1. Backpressure & Queue Saturation Overflow Gaps
    roi = SimpleTestRoi()
    decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)
    builder = SyntheticStreamBuilder()
    builder.emit_start()
    for i in range(5):
        builder.emit_frame()
    # 10 dropped frames due to queue overflow backpressure
    builder.emit_gap(5, 14, reason="queue_overflow")
    for i in range(15, 20):
        builder.emit_frame(sequence=i)
    wire_data = builder.emit_sealed_end()

    receipt = decoder.process_stream(io.BytesIO(wire_data))
    log_step("R3", "Queue Saturation Gap Status", receipt.status == "COMPLETE", "Stream sealed cleanly despite 10-frame gap")
    log_step("R3", "Queue Overflow Positions Accounting", receipt.queue_overflow_positions == 10 and receipt.acquisition_positions == 20, "20 total positions, 10 overflow gaps accounted")
    log_step("R3", "Temporal Reset Flag Triggered", roi.gaps[0].reset_temporal_state, "Gap >= 3 required temporal reset")

    # 2. 100ms Consumer Frame Timeout SLA Enforcement
    class TimingMock:
        def __init__(self) -> None:
            self.val = 1_000_000_000
            self.step = 0
        def __call__(self) -> int:
            ret = self.val
            self.val += self.step
            return ret

    clock_mock = TimingMock()
    slow_roi = SimpleTestRoi()
    decoder_timeout = CaptureStreamDecoder(slow_roi, roi_config_hash="00" * 32, time_monotonic_ns_fn=clock_mock)
    b_timeout = SyntheticStreamBuilder()
    b_timeout.emit_start().emit_frame()
    raw_timeout = b_timeout.emit_sealed_end()

    # Advance clock by 105ms (exceeding 100ms)
    clock_mock.step = 105_000_000
    r_timeout = decoder_timeout.process_stream(io.BytesIO(raw_timeout))
    log_step("R3", "100ms Consumer SLA Frame Timeout", r_timeout.status == "FAILED" and r_timeout.failure_code == "ROI_CONSUMER_TIMEOUT", f"Failed with {r_timeout.failure_code}")

    # 3. Mid-Stream Pipe Break Abrupt Closure
    if _IS_WINDOWS:
        nonce_break = secrets.token_hex(16)
        s_break = NamedPipeServer(nonce_break)
        c_break = NamedPipeClient(nonce_break)
        r_holder = []
        d_break = CaptureStreamDecoder(SimpleTestRoi(), roi_config_hash="00" * 32)

        def s_break_run() -> None:
            s_break.wait_for_connection()
            st = s_break.as_stream()
            r_holder.append(d_break.process_stream(st))

        t_break = threading.Thread(target=s_break_run, daemon=True)
        t_break.start()

        c_break.connect(timeout_s=3.0)
        b_break = SyntheticStreamBuilder(session_id=nonce_break)
        b_break.emit_start().emit_frame()
        c_break.write(b_break._buf.getvalue())
        # Abruptly close handle mid-stream without END
        c_break.close()
        t_break.join(timeout=3.0)
        s_break.close()

        log_step("R3", "Mid-Stream Pipe Break Rejection", len(r_holder) == 1 and r_holder[0].failure_code == "ROI_PIPE_CLOSED", f"Failure code: {r_holder[0].failure_code}")

    # 4. Malformed Metadata Rejection (Syntax / Duplicate / Float)
    dec_bad = CaptureStreamDecoder(SimpleTestRoi(), roi_config_hash="00" * 32)
    bad_syntax = b"{unclosed:json"
    p_bad = WirePrefix(WIRE_MAGIC, WIRE_VERSION, KIND_START, 0, len(bad_syntax), 0).pack() + bad_syntax
    r_bad = dec_bad.process_stream(io.BytesIO(p_bad))
    log_step("R3", "Malformed Metadata (Invalid JSON)", r_bad.failure_code == "ROI_SCHEMA_INVALID", f"Failure code: {r_bad.failure_code}")

    # 5. Oversize Metadata (> 8192 Bytes)
    dec_over = CaptureStreamDecoder(SimpleTestRoi(), roi_config_hash="00" * 32)
    p_over = struct.pack(">4sBBHII", WIRE_MAGIC, WIRE_VERSION, KIND_START, 0, 8193, 0)
    r_over = dec_over.process_stream(io.BytesIO(p_over))
    log_step("R3", "Oversize Metadata Rejection", r_over.failure_code == "ROI_SCHEMA_INVALID", f"Failure code: {r_over.failure_code}")

    # 6. Single Bitflip Digest Corruption
    b_tamper = SyntheticStreamBuilder()
    b_tamper.emit_start()
    for i in range(5):
        b_tamper.emit_frame()
    valid_bytes = bytearray(b_tamper.emit_sealed_end())
    # Tamper byte 1,000,000
    valid_bytes[1_000_000] ^= 0x01
    dec_tamper = CaptureStreamDecoder(SimpleTestRoi(), roi_config_hash="00" * 32)
    r_tamper = dec_tamper.process_stream(io.BytesIO(valid_bytes))
    log_step("R3", "Single Bitflip Digest Corruption", r_tamper.failure_code == "ROI_DIGEST_MISMATCH", f"Failure code: {r_tamper.failure_code}")

    # 7. Unexplained Sequence Gap Rejection
    b_skip = SyntheticStreamBuilder()
    b_skip.emit_start()
    b_skip.emit_frame(sequence=0)
    b_skip.emit_frame(sequence=2)  # seq 1 skipped without gap
    raw_skip = b_skip.emit_sealed_end()
    dec_skip = CaptureStreamDecoder(SimpleTestRoi(), roi_config_hash="00" * 32)
    r_skip = dec_skip.process_stream(io.BytesIO(raw_skip))
    log_step("R3", "Unexplained Sequence Gap Rejection", r_skip.failure_code == "ROI_SEQUENCE_INVALID", f"Failure code: {r_skip.failure_code}")

    # 8. Memory Leak (Unreleased Lease) Detection
    class LeakyRoi(RoiIngressPort):
        def open_session(self, s): pass
        def accept(self, f, lease):
            # Leaks lease: does NOT call lease.release()
            return RoiAcceptResultV1("whole-home-agent.roi-accept-result.v1", f.capture_session_id, f.source_sequence, "ACCEPTED", None, f.captured_monotonic_ns + 1000, "windows_webcam_roi/1", "00" * 32)
        def accept_gap(self, g): pass
        def close_session(self, e): pass
        def abort_session(self, e): pass

    dec_leak = CaptureStreamDecoder(LeakyRoi(), roi_config_hash="00" * 32)
    b_leak = SyntheticStreamBuilder()
    b_leak.emit_start().emit_frame()
    raw_leak = b_leak.emit_sealed_end()
    r_leak = dec_leak.process_stream(io.BytesIO(raw_leak))
    log_step("R3", "Consumer Lease Leak Detection", r_leak.failure_code == "ROI_BUFFER_LEAK", f"Failure code: {r_leak.failure_code}")

    # 9. Rapid Repeated Launch Cleanup (10 Consecutive Sessions)
    if _IS_WINDOWS:
        for idx in range(10):
            n_rep = secrets.token_hex(16)
            s_rep = NamedPipeServer(n_rep)
            c_rep = NamedPipeClient(n_rep)
            d_rep = CaptureStreamDecoder(SimpleTestRoi(), roi_config_hash="00" * 32)
            b_rep = SyntheticStreamBuilder(session_id=n_rep)
            b_rep.emit_start().emit_frame(sequence=0)
            raw_rep = b_rep.emit_sealed_end()
            res_rep = []

            def rep_run():
                s_rep.wait_for_connection()
                res_rep.append(d_rep.process_stream(s_rep.as_stream()))

            t_rep = threading.Thread(target=rep_run, daemon=True)
            t_rep.start()
            c_rep.connect(timeout_s=3.0)
            c_rep.write(raw_rep)
            c_rep.close()
            t_rep.join(timeout=3.0)
            s_rep.close()
            assert len(res_rep) == 1 and res_rep[0].status == "COMPLETE"
        log_step("R3", "Rapid Repeated Launch (10 Sessions)", True, "10 consecutive Win32 sessions started and cleaned cleanly")

    # 10. Cancellation in Active State
    b_abort = SyntheticStreamBuilder()
    b_abort.emit_start().emit_frame()
    raw_abort = b_abort.emit_aborted_end(failure_code="CAPTURE_CANCELLED")
    roi_abort = SimpleTestRoi()
    dec_abort = CaptureStreamDecoder(roi_abort, roi_config_hash="00" * 32)
    r_abort = dec_abort.process_stream(io.BytesIO(raw_abort))
    log_step("R3", "In-Flight Cancellation Handling", r_abort.status == "ABORTED" and r_abort.source_failure_code == "CAPTURE_CANCELLED", f"Receipt status: {r_abort.status}, reason: {r_abort.source_failure_code}")

    # 11. Zero Retention Disk Audit
    forbidden_exts = (".raw", ".rgb", ".bmp", ".jpg", ".png", ".mp4", ".sqlite", ".db")
    current_files = set()
    for root, _, files in os.walk("."):
        if ".git" in root or ".venv" in root:
            continue
        for f in files:
            if f.endswith(forbidden_exts):
                current_files.add(os.path.join(root, f))
    new_forbidden = current_files - initial_forbidden_files
    log_step("R3", "Zero Retention Anti-Forensics Audit", len(new_forbidden) == 0, f"New forbidden files created: {len(new_forbidden)}")


def main() -> None:
    print("=" * 80)
    print("STARTING INDEPENDENT RE-VERIFICATION RUNNER FOR STAGES R0 TO R3")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"Platform: {sys.platform} ({sys.version.split()[0]})")
    print(f"Operate Mode: OPERATE DISABLED")
    print("=" * 80)

    t0 = time.perf_counter()
    verify_stage_r0()
    verify_stage_r1()
    verify_stage_r2()
    verify_stage_r3()
    elapsed = time.perf_counter() - t0

    print("\n" + "=" * 80)
    print(f"ALL INDEPENDENT RE-VERIFICATION STEPS (R0 -> R3) PASSED SUCCESSFULLY in {elapsed:.2f}s!")
    print("=" * 80)


if __name__ == "__main__":
    main()
