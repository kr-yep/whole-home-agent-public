"""Run exactly one generated-input D-FINE Small engineering preflight."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import random
import socket
import subprocess
import sys
import time
import tomllib
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from whole_home_agent.adapters.dfine import DFineConfig, DFineDetector
from whole_home_agent.model import SourcePosition, TimestampBasis
from whole_home_agent.perception import VideoFrame


CONTRACT_PATH = ROOT / "configs" / "evaluation" / "m13-dfine-small-synthetic-v1.toml"
EXPECTED_SECTIONS = {
    "schema_version",
    "status",
    "screen_id",
    "intended_use",
    "candidate_count",
    "implementation",
    "artifact",
    "license",
    "semantics",
    "runtime",
    "fixture",
    "gate",
    "boundaries",
    "attempt",
    "decision",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside_repo(value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field} must be a POSIX repository-relative path")
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"{field} escaped the repository")
    resolved = (ROOT / relative).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"{field} escaped the repository") from error
    return resolved


def _exact_keys(value: object, expected: set[str], *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{field} schema is invalid")
    return value


@dataclass(frozen=True, slots=True)
class M13Contract:
    document: dict[str, Any]
    config_hash: str
    adapter_path: Path
    model_dir: Path
    marker_path: Path
    receipt_path: Path
    detector_config: DFineConfig


def load_contract(path: Path = CONTRACT_PATH) -> M13Contract:
    raw = path.read_bytes()
    document = tomllib.loads(raw.decode("utf-8"))
    if set(document) != EXPECTED_SECTIONS or document.get("schema_version") != 1:
        raise ValueError("M13 contract schema is invalid")
    if (
        document["status"] != "FROZEN_BEFORE_SYNTHETIC_PREFLIGHT"
        or document["screen_id"] != "m13-dfine-small-synthetic-v1"
        or document["intended_use"] != "SYNTHETIC_ONLY_ENGINEERING_QUALIFICATION"
        or document["candidate_count"] != 1
    ):
        raise ValueError("M13 candidate scope was loosened")

    implementation = _exact_keys(
        document["implementation"],
        {"library", "version", "tag", "tag_commit", "wheel_sha256", "adapter_path", "adapter_sha256"},
        field="implementation",
    )
    if (
        implementation["library"] != "transformers"
        or implementation["version"] != "5.16.1"
        or implementation["tag"] != "v5.16.1"
        or implementation["tag_commit"] != "fb405cdf1bb6fa7b85ac8871b5d8a8b1376f5a3c"
        or implementation["wheel_sha256"] != "2f2d5b98a5ad3718713653734298fa620754ed683702a635ebb587df3ed29c7e"
    ):
        raise ValueError("M13 implementation identity changed")
    adapter_path = _inside_repo(implementation["adapter_path"], field="adapter_path")
    if _sha256(adapter_path) != implementation["adapter_sha256"]:
        raise ValueError("M13 adapter changed after freeze")

    artifact = _exact_keys(
        document["artifact"],
        {
            "repository", "revision", "provenance", "original_equivalence_verified",
            "model_dir", "weights_filename", "weights_url", "weights_bytes",
            "weights_sha256", "config_filename", "config_bytes", "config_sha256",
            "preprocessor_filename", "preprocessor_bytes", "preprocessor_sha256",
        },
        field="artifact",
    )
    if (
        artifact["repository"] != "ustc-community/dfine-small-coco"
        or artifact["revision"] != "f79e65b5fbb33ceb9d3ebba042955d7410c608f8"
        or artifact["provenance"] != "COMMUNITY_CONVERTED_NOT_DFINE_AUTHOR_RELEASE"
        or artifact["original_equivalence_verified"] is not False
        or artifact["weights_filename"] != "model.safetensors"
        or artifact["config_filename"] != "config.json"
        or artifact["preprocessor_filename"] != "preprocessor_config.json"
    ):
        raise ValueError("M13 artifact identity or provenance changed")
    model_dir = _inside_repo(artifact["model_dir"], field="model_dir")

    license_record = _exact_keys(
        document["license"],
        {"declared_id", "metadata_url", "local_evaluation_allowed", "redistribution_allowed_by_project", "commercial_clearance_claimed"},
        field="license",
    )
    if license_record != {
        "declared_id": "Apache-2.0",
        "metadata_url": "https://huggingface.co/ustc-community/dfine-small-coco/tree/f79e65b5fbb33ceb9d3ebba042955d7410c608f8",
        "local_evaluation_allowed": True,
        "redistribution_allowed_by_project": False,
        "commercial_clearance_claimed": False,
    }:
        raise ValueError("M13 license boundary changed")

    semantics = document["semantics"]
    expected_ids = [39, 41, 43, 44, 45, 70, 72]
    expected_labels = ["bottle", "cup", "knife", "spoon", "bowl", "toaster", "refrigerator"]
    if (
        semantics["architecture"] != "DFineForObjectDetection"
        or semantics["model_type"] != "d_fine"
        or semantics["input_width"] != 640
        or semantics["input_height"] != 640
        or semantics["resize_preserves_aspect_ratio"] is not False
        or semantics["normalize"] is not False
        or semantics["pad"] is not False
        or semantics["num_queries"] != 300
        or semantics["dense_class_count"] != 80
        or semantics["confidence_threshold"] != 0.25
        or semantics["confidence_operator"] != ">="
        or semantics["postprocessor_threshold"] != 0.0
        or semantics["output_coordinates"] != "ORIGINAL_FRAME_ABSOLUTE_XYXY"
        or semantics["scored_class_ids"] != expected_ids
        or semantics["scored_labels"] != expected_labels
    ):
        raise ValueError("M13 inference semantics changed")

    runtime = document["runtime"]
    if (
        runtime["device"] != "cuda"
        or runtime["inference_dtype"] != "float16"
        or runtime["batch_size"] != 1
        or runtime["compile"] is not False
        or runtime["warmup_calls"] != 1
        or runtime["measured_calls"] != 51
        or runtime["deterministic_algorithms_required"] is not True
        or runtime["network_connections_allowed"] is not False
        or runtime["local_files_only"] is not True
        or runtime["trust_remote_code"] is not False
        or runtime["use_safetensors"] is not True
        or runtime["uv_lock_reproduces_gpu_environment"] is not False
    ):
        raise ValueError("M13 runtime profile changed")
    if _sha256(ROOT / "uv.lock") != runtime["uv_lock_sha256"]:
        raise ValueError("M13 dependency lock changed")

    fixture = document["fixture"]
    if fixture != {
        "kind": "GENERATED_IN_MEMORY_RGB",
        "width": 960,
        "height": 540,
        "generator_version": "m13-gradient-rectangles-v1",
        "rgb_sha256": "c0ef097cb129dbaaac0963d6a1e81341280584480308621de26636c7b49c0b98",
        "public_or_private_media_bytes_allowed": False,
    }:
        raise ValueError("M13 generated fixture changed")
    boundaries = document["boundaries"]
    if any(value is not False for value in boundaries.values()):
        raise ValueError("M13 forbidden capability was enabled")
    attempt = document["attempt"]
    if attempt["maximum_real_load_attempts"] != 1 or attempt["dirty_worktree_allowed"] is not False:
        raise ValueError("M13 attempt boundary changed")
    marker_path = _inside_repo(attempt["marker_path"], field="attempt.marker_path")
    receipt_path = _inside_repo(attempt["receipt_path"], field="attempt.receipt_path")

    model_config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    class_id_map = tuple(
        sorted((int(key), value) for key, value in model_config["id2label"].items())
    )
    detector_config = DFineConfig(
        model_dir=model_dir,
        weights_sha256=artifact["weights_sha256"],
        weights_bytes=artifact["weights_bytes"],
        config_sha256=artifact["config_sha256"],
        config_bytes=artifact["config_bytes"],
        preprocessor_sha256=artifact["preprocessor_sha256"],
        preprocessor_bytes=artifact["preprocessor_bytes"],
        class_id_map=class_id_map,
        scored_labels=tuple(expected_labels),
        model_revision=artifact["revision"],
        transformers_version=implementation["version"],
        confidence_threshold=semantics["confidence_threshold"],
        device=runtime["device"],
        inference_dtype=runtime["inference_dtype"],
    )
    return M13Contract(
        document=document,
        config_hash=hashlib.sha256(raw).hexdigest(),
        adapter_path=adapter_path,
        model_dir=model_dir,
        marker_path=marker_path,
        receipt_path=receipt_path,
        detector_config=detector_config,
    )


class OfflineNetworkGuard(AbstractContextManager["OfflineNetworkGuard"]):
    def __init__(self) -> None:
        self.attempts: list[str] = []

    def __enter__(self) -> "OfflineNetworkGuard":
        self._create_connection = socket.create_connection
        self._connect = socket.socket.connect
        self._connect_ex = socket.socket.connect_ex

        def deny(*args: object, **kwargs: object) -> None:
            self.attempts.append("python_socket_connection")
            raise RuntimeError("NETWORK_CONNECTION_DENIED")

        socket.create_connection = deny  # type: ignore[assignment]
        socket.socket.connect = deny  # type: ignore[assignment]
        socket.socket.connect_ex = deny  # type: ignore[assignment]
        return self

    def __exit__(self, *args: object) -> None:
        socket.create_connection = self._create_connection
        socket.socket.connect = self._connect
        socket.socket.connect_ex = self._connect_ex


def _write_json(path: Path, payload: object, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _git_state() -> tuple[str, bool]:
    safe_directory = f"safe.directory={ROOT.resolve()}"
    revision = subprocess.run(
        ["git", "-c", safe_directory, "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            [
                "git",
                "-c",
                safe_directory,
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return revision, dirty


def _generated_fixture(contract: M13Contract):
    import numpy as np

    width = contract.document["fixture"]["width"]
    height = contract.document["fixture"]["height"]
    x = np.arange(width, dtype=np.uint32)
    y = np.arange(height, dtype=np.uint32)
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:, :, 0] = ((x * 255) // (width - 1))[None, :]
    image[:, :, 1] = ((y * 255) // (height - 1))[:, None]
    image[:, :, 2] = ((((x[None, :] // 32) + (y[:, None] // 24)) % 2) * 48).astype(np.uint8)
    image[180:360, 360:600] = np.asarray([180, 120, 40], dtype=np.uint8)
    image[250:310, 440:500] = np.asarray([32, 80, 190], dtype=np.uint8)
    digest = hashlib.sha256(image.tobytes()).hexdigest()
    if digest != contract.document["fixture"]["rgb_sha256"]:
        raise RuntimeError("generated M13 fixture hash disagrees with the frozen contract")
    return image


def _canonical_digest(detections: object) -> str:
    payload = [
        {
            "bbox": list(item.bbox.as_xyxy()),
            "confidence": item.confidence,
            "label": item.label,
            "producer_identity": list(item.producer_ref.identity_payload()),
        }
        for item in detections
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _nearest_rank_p95(values: list[float]) -> float:
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("latencies must be finite non-negative values")
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _validate_environment(contract: M13Contract) -> tuple[object, object]:
    runtime = contract.document["runtime"]
    if os.environ.get("PYTHONHASHSEED") != runtime["pythonhashseed"]:
        raise RuntimeError("PYTHONHASHSEED must be set before launching M13")
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != runtime["cublas_workspace_config"]:
        raise RuntimeError("CUBLAS_WORKSPACE_CONFIG must be set before launching M13")
    if sys.version.split()[0] != runtime["installed_python"]:
        raise RuntimeError("Python version disagrees with the frozen M13 environment")
    import numpy as np
    import torch
    from transformers import DFineForObjectDetection, RTDetrImageProcessor

    if (
        DFineForObjectDetection.__name__ != "DFineForObjectDetection"
        or RTDetrImageProcessor.__name__ != "RTDetrImageProcessor"
    ):
        raise RuntimeError("reviewed D-FINE Transformers symbols are unavailable")

    versions = {
        "torch": torch.__version__,
        "torchvision": importlib.metadata.version("torchvision"),
        "transformers": importlib.metadata.version("transformers"),
        "safetensors": importlib.metadata.version("safetensors"),
    }
    expected = {
        "torch": runtime["installed_torch"],
        "torchvision": runtime["installed_torchvision"],
        "transformers": runtime["installed_transformers"],
        "safetensors": runtime["installed_safetensors"],
    }
    if versions != expected or not torch.cuda.is_available():
        raise RuntimeError("installed M13 GPU environment disagrees with the frozen contract")
    random.seed(runtime["random_seed"])
    np.random.seed(runtime["numpy_seed"])
    torch.manual_seed(runtime["torch_seed"])
    torch.cuda.manual_seed_all(runtime["torch_seed"])
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    return np, torch


def run(contract: M13Contract) -> dict[str, Any]:
    os.environ.update(
        {
            "HF_DATASETS_OFFLINE": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TORCH_FORCE_WEIGHTS_ONLY_LOAD": "1",
        }
    )
    _, torch = _validate_environment(contract)
    revision, dirty = _git_state()
    if dirty:
        raise RuntimeError("M13 formal preflight requires a clean worktree")
    image = _generated_fixture(contract)
    position = SourcePosition(
        source_sequence=0,
        source_offset=0,
        timestamp_basis=TimestampBasis.SYNTHETIC,
        frame_index=0,
    )
    frame = VideoFrame(position=position, rgb=image)
    started = datetime.now(UTC).isoformat()
    marker = {
        "attempt": 1,
        "code_revision": revision,
        "config_hash": contract.config_hash,
        "started_at": started,
        "status": "STARTED",
    }
    _write_json(contract.marker_path, marker, exclusive=True)
    guard = OfflineNetworkGuard()
    try:
        with guard:
            detector = DFineDetector(contract.detector_config)
            detector.detect(frame)
            latencies_ms: list[float] = []
            digests: list[str] = []
            detection_counts: list[int] = []
            for _ in range(contract.document["runtime"]["measured_calls"]):
                started_ns = time.perf_counter_ns()
                detections = detector.detect(frame)
                elapsed_ns = time.perf_counter_ns() - started_ns
                latencies_ms.append(elapsed_ns / 1_000_000)
                digests.append(_canonical_digest(detections))
                detection_counts.append(len(detections))
        ordered = sorted(latencies_ms)
        p95_ms = _nearest_rank_p95(latencies_ms)
        peak_vram = detector.peak_vram_bytes()
        deterministic = len(set(digests)) == 1
        gate = contract.document["gate"]
        engineering_pass = (
            not guard.attempts
            and deterministic
            and len(latencies_ms) == 51
            and p95_ms < gate["detector_p95_ms_strictly_less_than"]
            and peak_vram is not None
            and peak_vram < gate["peak_vram_bytes_strictly_less_than"]
        )
        decision = contract.document["decision"]
        receipt = {
            **marker,
            "completed_at": datetime.now(UTC).isoformat(),
            "status": (
                decision["engineering_pass_status"]
                if engineering_pass
                else decision["engineering_fail_status"]
            ),
            "development_screen_decision": decision["development_screen_status"],
            "development_screen_reason": decision["reason"],
            "artifact_provenance": contract.document["artifact"]["provenance"],
            "original_equivalence_verified": False,
            "fixture_kind": contract.document["fixture"]["kind"],
            "fixture_rgb_sha256": contract.document["fixture"]["rgb_sha256"],
            "public_or_private_media_bytes_read": 0,
            "measured_calls": len(latencies_ms),
            "latency_ms": {
                "p50": ordered[len(ordered) // 2],
                "p95_nearest_rank": p95_ms,
                "maximum": ordered[-1],
            },
            "peak_vram_bytes": peak_vram,
            "canonical_output_digest": digests[0],
            "canonical_output_constant": deterministic,
            "detection_count_min": min(detection_counts),
            "detection_count_max": max(detection_counts),
            "network_attempts": guard.attempts,
            "runtime": detector.runtime_metadata(),
            "gate_passed": engineering_pass,
            "evidence_limit": (
                "Generated-input compatibility and one local cost profile only; no target-source "
                "accuracy, converted-weight parity, indoor transfer, sustained runtime, tracking, "
                "movement, or product suitability was measured."
            ),
        }
        _write_json(contract.receipt_path, receipt)
        _write_json(contract.marker_path, receipt)
        return receipt
    except BaseException as error:
        invalid = {
            **marker,
            "completed_at": datetime.now(UTC).isoformat(),
            "status": "INVALID_NO_RETRY_IN_M13",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "network_attempts": guard.attempts,
        }
        _write_json(contract.receipt_path, invalid)
        _write_json(contract.marker_path, invalid)
        raise
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def main() -> int:
    contract = load_contract()
    receipt = run(contract)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
