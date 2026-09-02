"""Run the single frozen M12 RF-DETR Small development screen."""

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
import tomllib
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
for path in (SRC, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from evaluation_cli_support import git_state, release_detector_runtime
from whole_home_agent.adapters.rfdetr import RFDetrConfig, RFDetrDetector
from whole_home_agent.adapters.vost import (
    load_vost_motion_screen_manifest,
    load_vost_motion_sequence,
)
from whole_home_agent.evaluation import evaluate_frame_set
from whole_home_agent.perception import Detection, VideoFrame


CONTRACT_PATH = ROOT / "configs" / "evaluation" / "vost-m12-rfdetr-small-v1.toml"
DEVELOPMENT_SEQUENCE_ID = "3518_unscrew_bottle"
RESERVED_SEQUENCE_ID = "3510_unscrew_bottle"
WEIGHTS_PATH = "models/weights/rfdetr/rf-detr-small.pth"
ADAPTER_PATH = "src/whole_home_agent/adapters/rfdetr.py"
EXPECTED_SCORED_LABELS = (
    "bottle",
    "bowl",
    "cup",
    "knife",
    "refrigerator",
    "spoon",
    "toaster",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_blob_sha256(relative_path: str) -> str:
    process = subprocess.run(
        ["git", "show", f"HEAD:{relative_path}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        shell=False,
    )
    if process.returncode != 0:
        raise ValueError(f"cannot read committed {relative_path}")
    return hashlib.sha256(process.stdout).hexdigest()


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


def _hash_string(value: object, length: int, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be lowercase hexadecimal")
    return value


@dataclass(frozen=True, slots=True)
class M12Contract:
    screen_id: str
    config_hash: str
    source_config: Path
    weights_path: Path
    adapter_path: Path
    class_id_map: tuple[tuple[int, str], ...]
    scored_labels: tuple[str, ...]
    document: dict[str, Any]


def load_contract(path: Path = CONTRACT_PATH) -> M12Contract:
    raw = path.read_bytes()
    document = tomllib.loads(raw.decode("utf-8"))
    top_keys = {
        "schema_version", "status", "screen_id", "intended_use", "candidate_count",
        "model_id", "model_variant", "package_version", "package_source_commit",
        "package_wheel_sha256", "license_id", "license_url", "weights_url",
        "weights_generation", "weights_generation_url", "weights_path", "weights_bytes",
        "weights_md5", "weights_sha256", "adapter_path", "adapter_sha256",
        "input_resolution", "confidence_threshold", "confidence_operator",
        "match_iou_threshold", "scored_labels", "class_ids", "class_names", "source",
        "runtime", "environment", "gate", "attempt", "m10_comparator", "m11_pairing",
        "stop",
    }
    if set(document) != top_keys or document.get("schema_version") != 1:
        raise ValueError("M12 contract schema is invalid")
    if (
        document["status"] != "FROZEN_BEFORE_DEVELOPMENT_RUN"
        or document["intended_use"] != "DEVELOPMENT_ONLY_DETECTOR_REPLACEMENT_REALITY_GATE"
        or document["candidate_count"] != 1
        or document["model_id"] != "rfdetr-small-coco-1.9.4"
        or document["model_variant"] != "small"
        or document["package_version"] != "1.9.4"
        or document["package_source_commit"] != "9b009fa928d6218320439803d1da01869a85c072"
        or document["license_id"] != "Apache-2.0"
        or document["input_resolution"] != 512
        or document["confidence_threshold"] != 0.25
        or document["confidence_operator"] != ">="
        or document["match_iou_threshold"] != 0.5
    ):
        raise ValueError("M12 candidate identity or threshold was loosened")
    _hash_string(document["package_wheel_sha256"], 64, field="package_wheel_sha256")
    _hash_string(document["weights_sha256"], 64, field="weights_sha256")
    _hash_string(document["weights_md5"], 32, field="weights_md5")
    if (
        document["weights_url"]
        != "https://storage.googleapis.com/rfdetr/small_coco/checkpoint_best_regular.pth"
        or document["weights_generation"] != "1753220474114031"
        or document["weights_generation_url"]
        != document["weights_url"] + "?generation=" + document["weights_generation"]
        or type(document["weights_bytes"]) is not int
        or document["weights_bytes"] <= 0
    ):
        raise ValueError("M12 artifact origin is invalid")
    weights_path = _inside_repo(document["weights_path"], field="weights_path")
    adapter_path = _inside_repo(document["adapter_path"], field="adapter_path")
    if document["weights_path"] != WEIGHTS_PATH or document["adapter_path"] != ADAPTER_PATH:
        raise ValueError("M12 local artifact allowlist changed")
    if _sha256(adapter_path) != document["adapter_sha256"]:
        raise ValueError("M12 adapter changed after freeze")
    ids = document["class_ids"]
    names = document["class_names"]
    if (
        not isinstance(ids, list)
        or not isinstance(names, list)
        or len(ids) != 80
        or len(names) != 80
        or any(type(item) is not int for item in ids)
        or any(not isinstance(item, str) or not item for item in names)
        or len(set(ids)) != 80
        or len(set(names)) != 80
        or tuple(sorted(ids)) != tuple(ids)
        or dict(zip(ids, names)).get(44) != "bottle"
        or tuple(document["scored_labels"]) != EXPECTED_SCORED_LABELS
    ):
        raise ValueError("M12 sparse COCO map or scored-label allowlist is invalid")

    source = _exact_keys(
        document["source"],
        {
            "config_path", "config_sha256", "sequence_id", "split", "frame_count",
            "content_hash", "annotation_hash", "target_label", "reserved_sequence_id",
            "reserved_bytes_allowed", "visor_sequence_allowed",
        },
        field="source",
    )
    source_config = _inside_repo(source["config_path"], field="source.config_path")
    if (
        _sha256(source_config) != source["config_sha256"]
        or source["sequence_id"] != DEVELOPMENT_SEQUENCE_ID
        or source["split"] != "development"
        or source["frame_count"] != 51
        or source["content_hash"] != "8297ad56f4697ef1040dbcd76c5042ba625a4a109ecfc5c1131442dcdef0f61e"
        or source["annotation_hash"] != "fdc1d4c24664edeb49bc63bad66fdaf968be4483f03efd4f0f0e7e1ab9061db1"
        or source["target_label"] != "bottle"
        or source["reserved_sequence_id"] != RESERVED_SEQUENCE_ID
        or source["reserved_bytes_allowed"] is not False
        or source["visor_sequence_allowed"] is not False
    ):
        raise ValueError("M12 development-only source boundary was loosened")

    runtime = _exact_keys(
        document["runtime"],
        {
            "device", "cuda_visible_devices", "inference_dtype", "inference_compile",
            "inference_inplace", "include_source_image", "batch_size", "warmup_frames",
            "pythonhashseed", "cublas_workspace_config", "random_seed", "numpy_seed",
            "torch_seed", "deterministic_algorithms_required", "network_connections_allowed",
        },
        field="runtime",
    )
    if runtime != {
        "device": "cuda", "cuda_visible_devices": "0", "inference_dtype": "float16",
        "inference_compile": False, "inference_inplace": True,
        "include_source_image": False, "batch_size": 1, "warmup_frames": 1,
        "pythonhashseed": "12", "cublas_workspace_config": ":4096:8",
        "random_seed": 12, "numpy_seed": 12, "torch_seed": 12,
        "deterministic_algorithms_required": True, "network_connections_allowed": False,
    }:
        raise ValueError("M12 runtime profile was loosened")

    environment = _exact_keys(
        document["environment"],
        {
            "python_version", "rfdetr_version", "pydantic_version", "pydeprecate_version",
            "supervision_version", "tqdm_version", "transformers_version", "torch_version",
            "torchvision_version", "numpy_version", "pillow_version", "av_version",
            "cuda_version", "cudnn_version", "gpu_name", "driver_version",
            "uv_lock_sha256", "uv_lock_reproduces_gpu_environment",
        },
        field="environment",
    )
    if environment["uv_lock_reproduces_gpu_environment"] is not False:
        raise ValueError("M12 must disclose the CUDA lock divergence")
    if _git_blob_sha256("uv.lock") != environment["uv_lock_sha256"]:
        raise ValueError("M12 dependency lock changed after freeze")

    gate = _exact_keys(
        document["gate"],
        {
            "minimum_recall50", "recall50_operator", "maximum_detector_p95_ms",
            "detector_p95_operator", "maximum_peak_vram_bytes", "peak_vram_operator",
            "all_checks_required",
        },
        field="gate",
    )
    if gate != {
        "minimum_recall50": 0.6, "recall50_operator": ">=",
        "maximum_detector_p95_ms": 100.0, "detector_p95_operator": "<",
        "maximum_peak_vram_bytes": 1073741824, "peak_vram_operator": "<",
        "all_checks_required": True,
    }:
        raise ValueError("M12 gates changed after freeze")
    attempt = _exact_keys(
        document["attempt"],
        {
            "maximum_development_attempts", "dirty_worktree_allowed",
            "incomplete_run_is_invalid", "nonfinite_metric_is_invalid",
            "missing_vram_is_invalid", "network_attempt_is_invalid", "exception_is_invalid",
            "training_allowed", "threshold_tuning_allowed", "reserved_validation_allowed",
            "movement_candidate_allowed", "claim_commit_allowed",
        },
        field="attempt",
    )
    if attempt["maximum_development_attempts"] != 1 or any(
        attempt[key] is not expected
        for key, expected in {
            "dirty_worktree_allowed": False,
            "incomplete_run_is_invalid": True,
            "nonfinite_metric_is_invalid": True,
            "missing_vram_is_invalid": True,
            "network_attempt_is_invalid": True,
            "exception_is_invalid": True,
            "training_allowed": False,
            "threshold_tuning_allowed": False,
            "reserved_validation_allowed": False,
            "movement_candidate_allowed": False,
            "claim_commit_allowed": False,
        }.items()
    ):
        raise ValueError("M12 attempt or safety policy was loosened")
    comparator = _exact_keys(
        document["m10_comparator"],
        {
            "receipt_sha256", "model_id", "matched_frames", "recall50",
            "detector_p95_ms", "peak_vram_bytes", "comparison_path",
        },
        field="m10_comparator",
    )
    if (
        comparator["receipt_sha256"] != "2f1a413073f565f2a9fff4fbbdb539bc66c3febe897e18eca50cf25cac2747d7"
        or comparator["model_id"] != "retinanet-resnet50-fpn-v2-coco-v1"
        or comparator["matched_frames"] != 10
        or comparator["recall50"] != 10 / 51
        or comparator["detector_p95_ms"] != 75.75940000242554
        or comparator["peak_vram_bytes"] != 412383744
        or comparator["comparison_path"] != "full_frame_perception"
    ):
        raise ValueError("M12 full-frame M10 comparator changed")
    pairing = _exact_keys(
        document["m11_pairing"],
        {
            "receipt_sha256", "confidence_filtered_frames", "localization_miss_frames",
            "matched_frames", "pairing_is_descriptive_only",
        },
        field="m11_pairing",
    )
    paired_sets = [
        pairing["confidence_filtered_frames"], pairing["localization_miss_frames"],
        pairing["matched_frames"],
    ]
    if (
        pairing["receipt_sha256"] != "cf6bc1c32c052ceec23345638d4be85a81d54884b8be4638defa96f31932bd5c"
        or pairing["pairing_is_descriptive_only"] is not True
        or any(not isinstance(items, list) for items in paired_sets)
        or set().union(*(set(items) for items in paired_sets)) != set(range(51))
        or sum(len(items) for items in paired_sets) != 51
    ):
        raise ValueError("M12 M11 pairing changed")
    stop = _exact_keys(
        document["stop"],
        {
            "pass_decision", "fail_decision", "invalid_decision",
            "development_pass_does_not_select_product_model", "validation_is_separate_goal",
        },
        field="stop",
    )
    if (
        stop["pass_decision"] != "CONTINUE_TO_SEPARATE_RESERVED_VALIDATION_GOAL"
        or stop["fail_decision"] != "STOP_RFDETR_SMALL_CANDIDATE"
        or stop["invalid_decision"] != "STOP_M12_INVALID_NO_RERUN"
        or stop["development_pass_does_not_select_product_model"] is not True
        or stop["validation_is_separate_goal"] is not True
    ):
        raise ValueError("M12 stop rule changed")
    return M12Contract(
        screen_id=document["screen_id"],
        config_hash=hashlib.sha256(raw).hexdigest(),
        source_config=source_config,
        weights_path=weights_path,
        adapter_path=adapter_path,
        class_id_map=tuple(zip(ids, names)),
        scored_labels=tuple(document["scored_labels"]),
        document=document,
    )


class OfflineNetworkGuard(AbstractContextManager["OfflineNetworkGuard"]):
    """Deny Python socket connections during third-party model construction/inference."""

    def __init__(self) -> None:
        self.attempts: list[str] = []
        self._originals: dict[str, Any] = {}

    def _deny(self, *args: object, **kwargs: object) -> Any:
        self.attempts.append("python_socket_connection")
        raise RuntimeError("M12_NETWORK_CONNECTION_DENIED")

    def __enter__(self) -> "OfflineNetworkGuard":
        self._originals = {
            "create_connection": socket.create_connection,
            "getaddrinfo": socket.getaddrinfo,
            "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex,
        }
        socket.create_connection = self._deny
        socket.getaddrinfo = self._deny
        socket.socket.connect = self._deny
        socket.socket.connect_ex = self._deny
        return self

    def __exit__(self, *exc_info: object) -> None:
        socket.create_connection = self._originals["create_connection"]
        socket.getaddrinfo = self._originals["getaddrinfo"]
        socket.socket.connect = self._originals["connect"]
        socket.socket.connect_ex = self._originals["connect_ex"]
        return None


class RecordingDetector:
    def __init__(self, detector: RFDetrDetector):
        self.detector = detector
        self.predictions: dict[int, tuple[Detection, ...]] = {}
        self.inference_calls = 0

    @property
    def producer_ref(self):
        return self.detector.producer_ref

    @property
    def device(self) -> str:
        return self.detector.device

    def detect(self, frame: VideoFrame) -> tuple[Detection, ...]:
        result = self.detector.detect(frame)
        frame_index = frame.position.frame_index
        if frame_index is None:
            raise ValueError("M12 requires indexed development frames")
        self.predictions[frame_index] = result
        self.inference_calls += 1
        return result

    def peak_vram_bytes(self) -> int | None:
        return self.detector.peak_vram_bytes()

    def runtime_metadata(self) -> dict[str, Any]:
        return self.detector.runtime_metadata()


def evaluate_gate(
    recall50: float,
    detector_p95_ms: float,
    peak_vram_bytes: int | None,
    *,
    contract: M12Contract,
) -> dict[str, Any]:
    if (
        not math.isfinite(recall50)
        or not math.isfinite(detector_p95_ms)
        or peak_vram_bytes is None
        or type(peak_vram_bytes) is not int
    ):
        raise ValueError("M12 metrics are missing or non-finite")
    gate = contract.document["gate"]
    checks = {
        "recall50": {
            "actual": recall50, "operator": ">=", "threshold": gate["minimum_recall50"],
            "passed": recall50 >= gate["minimum_recall50"],
        },
        "detector_p95_ms": {
            "actual": detector_p95_ms, "operator": "<",
            "threshold": gate["maximum_detector_p95_ms"],
            "passed": detector_p95_ms < gate["maximum_detector_p95_ms"],
        },
        "peak_vram_bytes": {
            "actual": peak_vram_bytes, "operator": "<",
            "threshold": gate["maximum_peak_vram_bytes"],
            "passed": peak_vram_bytes < gate["maximum_peak_vram_bytes"],
        },
    }
    passed = all(item["passed"] for item in checks.values())
    return {
        "checks": checks,
        "passed": passed,
        "decision": contract.document["stop"]["pass_decision" if passed else "fail_decision"],
    }


def paired_recovery(
    predictions: dict[int, tuple[Detection, ...]],
    ground_truth: dict[int, tuple[Any, ...]],
    *,
    contract: M12Contract,
) -> dict[str, Any]:
    matched_now: set[int] = set()
    for frame_index in range(51):
        targets = ground_truth[frame_index]
        if len(targets) != 1:
            raise ValueError("M12 expected exactly one visible target per frame")
        target = targets[0]
        if any(
            item.label == target.label and item.bbox.iou(target.bbox) >= 0.5
            for item in predictions.get(frame_index, ())
        ):
            matched_now.add(frame_index)
    pairing = contract.document["m11_pairing"]
    categories = {
        "m11_confidence_filtered": pairing["confidence_filtered_frames"],
        "m11_localization_miss": pairing["localization_miss_frames"],
        "m11_matched": pairing["matched_frames"],
    }
    by_prior_category = {
        name: {
            "matched_now": sum(index in matched_now for index in frames),
            "prior_frame_count": len(frames),
        }
        for name, frames in categories.items()
    }
    return {
        "by_prior_m11_category": by_prior_category,
        "matched_frame_count": len(matched_now),
        "matched_frame_indexes": sorted(matched_now),
        "net_matched_frame_delta_vs_m10": len(matched_now)
        - contract.document["m10_comparator"]["matched_frames"],
        "status": "DESCRIPTIVE_NOT_A_GATE",
    }


def _write_json(path: Path, document: dict[str, Any], *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def _update_attempt(path: Path, document: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    _write_json(temporary, document)
    temporary.replace(path)


def _runtime_versions(contract: M12Contract) -> dict[str, str]:
    environment = contract.document["environment"]
    distributions = {
        "rfdetr": "rfdetr", "pydantic": "pydantic", "pydeprecate": "pydeprecate",
        "supervision": "supervision", "tqdm": "tqdm", "transformers": "transformers",
        "torch": "torch", "torchvision": "torchvision", "numpy": "numpy",
        "pillow": "Pillow", "av": "av",
    }
    actual = {name: importlib.metadata.version(distribution) for name, distribution in distributions.items()}
    for name, version in actual.items():
        if version != environment[name + "_version"]:
            raise RuntimeError(f"M12_RUNTIME_VERSION_MISMATCH:{name}")
    if sys.version.split()[0] != environment["python_version"]:
        raise RuntimeError("M12_RUNTIME_VERSION_MISMATCH:python")
    return actual


def _driver_version() -> str:
    completed = subprocess.run(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    values = [item.strip() for item in completed.stdout.splitlines() if item.strip()]
    if len(values) != 1:
        raise RuntimeError("M12_GPU_DRIVER_QUERY_INVALID")
    return values[0]


def _require_process_environment(contract: M12Contract) -> None:
    runtime = contract.document["runtime"]
    required = {
        "PYTHONHASHSEED": runtime["pythonhashseed"],
        "CUDA_VISIBLE_DEVICES": runtime["cuda_visible_devices"],
        "CUBLAS_WORKSPACE_CONFIG": runtime["cublas_workspace_config"],
    }
    if any(os.environ.get(name) != value for name, value in required.items()):
        raise RuntimeError("M12_PROCESS_ENVIRONMENT_NOT_FROZEN")


def main() -> int:
    contract = load_contract()
    _require_process_environment(contract)
    revision, dirty = git_state(ROOT)
    if dirty:
        raise RuntimeError("M12_REQUIRES_CLEAN_WORKTREE")
    run_dir = ROOT / "runs" / contract.screen_id
    attempt_path = run_dir / "attempt.json"
    created_at = datetime.now(UTC).replace(microsecond=0)
    attempt = {
        "attempt_number": 1,
        "code_revision": revision,
        "config_hash": contract.config_hash,
        "created_at_utc": created_at.isoformat().replace("+00:00", "Z"),
        "reserved_image_or_mask_bytes_read": False,
        "schema_version": 1,
        "status": "STARTED",
    }
    _write_json(attempt_path, attempt, exclusive=True)
    detector: RFDetrDetector | None = None
    guard = OfflineNetworkGuard()
    try:
        actual_versions = _runtime_versions(contract)
        if _driver_version() != contract.document["environment"]["driver_version"]:
            raise RuntimeError("M12_GPU_DRIVER_VERSION_MISMATCH")
        source_document = contract.document["source"]
        if (
            not contract.weights_path.is_file()
            or contract.weights_path.stat().st_size != contract.document["weights_bytes"]
            or _sha256(contract.weights_path) != contract.document["weights_sha256"]
        ):
            raise RuntimeError("M12_WEIGHT_ARTIFACT_INVALID")
        dataset = load_vost_motion_screen_manifest(
            contract.source_config, repository_root=ROOT
        )
        source_spec = dataset.sequence(DEVELOPMENT_SEQUENCE_ID)
        if (
            source_spec.split != "development"
            or source_spec.frame_count != source_document["frame_count"]
            or source_spec.sequence_files_manifest_sha256 != source_document["content_hash"]
        ):
            raise RuntimeError("M12_SOURCE_CONTRACT_INVALID")
        source = load_vost_motion_sequence(dataset, DEVELOPMENT_SEQUENCE_ID)
        if (
            source.split != "development"
            or source.frame_count != 51
            or source.descriptor.content_hash != source_document["content_hash"]
            or source.annotation_hash != source_document["annotation_hash"]
        ):
            raise RuntimeError("M12_SOURCE_CONTRACT_INVALID")

        with guard:
            import numpy as np
            import torch

            random.seed(12)
            np.random.seed(12)
            torch.manual_seed(12)
            torch.cuda.manual_seed_all(12)
            torch.use_deterministic_algorithms(True)
            torch.backends.cudnn.benchmark = False
            if not torch.are_deterministic_algorithms_enabled():
                raise RuntimeError("M12_DETERMINISTIC_ALGORITHMS_DISABLED")
            detector = RFDetrDetector(
                RFDetrConfig(
                    weights_path=contract.weights_path,
                    weights_sha256=contract.document["weights_sha256"],
                    weights_md5=contract.document["weights_md5"],
                    weights_bytes=contract.document["weights_bytes"],
                    class_id_map=contract.class_id_map,
                    scored_labels=contract.scored_labels,
                    model_variant="small",
                    package_version="1.9.4",
                    confidence_threshold=0.25,
                    device="cuda",
                    inference_compile=False,
                    inference_dtype="float16",
                    inference_inplace=True,
                )
            )
            recording = RecordingDetector(detector)
            report = evaluate_frame_set(
                source,
                recording,
                tracker=None,
                warmup_frames=1,
                repository_root=ROOT,
                code_revision=revision,
                dirty_worktree=False,
            )
        if guard.attempts:
            raise RuntimeError("M12_NETWORK_ATTEMPT_DETECTED")
        if recording.inference_calls != 52 or len(recording.predictions) != 51:
            raise RuntimeError("M12_INCOMPLETE_DEVELOPMENT_SCREEN")
        runtime = report.environment.model_runtime
        expected_environment = contract.document["environment"]
        if (
            runtime.get("gpu_name") != expected_environment["gpu_name"]
            or runtime.get("cuda_version") != expected_environment["cuda_version"]
            or runtime.get("cudnn_version") != expected_environment["cudnn_version"]
        ):
            raise RuntimeError("M12_GPU_RUNTIME_MISMATCH")
        recovery = paired_recovery(
            recording.predictions, source.ground_truth, contract=contract
        )
        if not math.isclose(
            report.quality.recall50,
            recovery["matched_frame_count"] / 51,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise RuntimeError("M12_EVALUATOR_RECOVERY_DISAGREEMENT")
        gate = evaluate_gate(
            report.quality.recall50,
            report.cost.detector_latency_p95_ms,
            report.cost.peak_vram_bytes,
            contract=contract,
        )
        receipt = {
            "claim_ledger": [
                {
                    "claim_id": "M12-C1",
                    "evidence_class": "integrity/executable",
                    "permissible": "One immutable candidate completed one frozen 51-frame development screen.",
                    "forbidden": "The reserved source, household scenes, or other runtimes have the same result.",
                },
                {
                    "claim_id": "M12-C2",
                    "evidence_class": "behavioral/finite-development",
                    "permissible": "The complete adapter path met or missed the three predeclared gates on these frames.",
                    "forbidden": "RF-DETR architecture alone caused the result or latency is stable.",
                },
                {
                    "claim_id": "M12-C3",
                    "evidence_class": "descriptive/paired",
                    "permissible": "The paired counts describe which M11 frame groups this path matched now.",
                    "forbidden": "Small-object or localization failure is generally solved.",
                },
            ],
            "code_revision": revision,
            "config_hash": contract.config_hash,
            "created_at_utc": created_at.isoformat().replace("+00:00", "Z"),
            "environment_contract": {
                "actual_packages": actual_versions,
                "driver_version": expected_environment["driver_version"],
                "uv_lock_reproduces_gpu_environment": False,
            },
            "evidence_limit": (
                "Adaptive development-only evidence for one public egocentric VOST sequence. "
                "It does not establish detector causality, stable latency, indoor/fixed-camera "
                "transfer, tracking, movement, relation memory, live operation, or household readiness."
            ),
            "experiment_status": "VALID",
            "gate": gate,
            "m10_comparator": contract.document["m10_comparator"],
            "network": {
                "connection_attempt_count": len(guard.attempts),
                "guard": "run-scoped Python socket denial",
            },
            "operate": "DISABLED",
            "paired_recovery": recovery,
            "perception_report": report.as_dict(),
            "reserved_image_or_mask_bytes_read": False,
            "schema_version": 1,
            "screen_id": contract.screen_id,
            "test_source_used": False,
            "training_run": False,
            "validation_run": False,
        }
        receipt_path = run_dir / "receipt.json"
        _write_json(receipt_path, receipt, exclusive=True)
        attempt.update(
            {
                "completed_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "decision": gate["decision"],
                "receipt_sha256": _sha256(receipt_path),
                "status": "VALID_COMPLETED",
            }
        )
        _update_attempt(attempt_path, attempt)
        print(
            json.dumps(
                {
                    "gate": gate,
                    "paired_recovery": recovery,
                    "receipt": receipt_path.as_posix(),
                    "validation_run": False,
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    except Exception as error:
        attempt.update(
            {
                "completed_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "failure_code": type(error).__name__,
                "network_attempt_count": len(guard.attempts),
                "status": "INVALID_NO_RERUN",
            }
        )
        _update_attempt(attempt_path, attempt)
        raise
    finally:
        if detector is not None:
            del detector
        release_detector_runtime()


if __name__ == "__main__":
    raise SystemExit(main())
