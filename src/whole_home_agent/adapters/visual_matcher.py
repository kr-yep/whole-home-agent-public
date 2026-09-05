"""Visual feature extraction and few-shot matching adapter for user-enrolled objects.

Provides zero-external-egress visual enrollment and verification:
- Users can show an object to the camera to enroll its visual appearance.
- Extracts compact, normalized deep feature embeddings using MobileNetV3-Small
  when available (cached locally, zero cloud egress), with a robust spatial
  color-distribution fallback.
- Matches candidate detection boxes against enrolled samples using Cosine Similarity.
- Supports automatic stop once target sample count (e.g. 5 frames) is reached.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

# Pillow is imported where it is used rather than here. The annotations below
# name Image.Image, but `from __future__ import annotations` keeps those as
# strings, so this module stays importable on an install without the video
# extra -- which is what the historical CI job runs.

logger = logging.getLogger(__name__)

DEFAULT_SAMPLES_STORAGE = Path(".whole-home-agent/visual_samples/enrolled_features.json")
DEFAULT_TARGET_SAMPLES = 5
DEFAULT_SAMPLE_INTERVAL_SECONDS = 0.25  # 250ms interval between sample captures
DEFAULT_SIMILARITY_THRESHOLD = 0.82

_TORCH_MODEL: Any = None
_TORCH_TRANSFORM: Any = None
_DEVICE: str = "cpu"


def _init_torch_extractor() -> bool:
    global _TORCH_MODEL, _TORCH_TRANSFORM, _DEVICE
    if _TORCH_MODEL is not None:
        return True
    try:
        import torch
        import torchvision.models as models
        from torchvision import transforms

        _DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
        model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
        model.classifier = torch.nn.Identity()
        model.to(_DEVICE)
        model.eval()
        _TORCH_MODEL = model
        _TORCH_TRANSFORM = transforms.Compose(
            [
                transforms.Resize((128, 128)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )
        logger.info("MobileNetV3 feature extractor initialized on %s", _DEVICE)
        return True
    except Exception as error:
        logger.debug("Falling back to spatial color-texture extractor: %s", error)
        return False


def extract_feature_vector(image: Image.Image) -> list[float]:
    """Extract a normalized visual feature vector from an image crop.

    Uses local MobileNetV3-Small if available (576 dims), or spatial color-gradient
    distribution fallback (512 dims). Both are L2-normalized.
    """
    if _init_torch_extractor():
        try:
            import torch

            img = image.convert("RGB")
            tensor = _TORCH_TRANSFORM(img).unsqueeze(0).to(_DEVICE)
            with torch.no_grad():
                feat = _TORCH_MODEL(tensor).squeeze(0)
                norm = feat.norm()
                if float(norm) > 1e-6:
                    feat = feat / norm
                return [float(x) for x in feat.cpu().tolist()]
        except Exception as error:
            logger.debug("Torch inference failed, using fallback: %s", error)

    # Fallback: 512-dim spatial color-difference & aspect representation
    w, h = image.size
    aspect_ratio = min(3.0, max(0.2, w / max(1.0, float(h))))
    from PIL import Image

    resized = image.convert("RGB").resize((8, 8), Image.Resampling.BILINEAR)

    r_vals: list[float] = []
    g_vals: list[float] = []
    b_vals: list[float] = []
    rg_diff: list[float] = []
    rb_diff: list[float] = []
    gb_diff: list[float] = []
    gray_vals: list[float] = []

    for y in range(8):
        for x in range(8):
            r, g, b = resized.getpixel((x, y))
            rf = r / 255.0
            gf = g / 255.0
            bf = b / 255.0
            r_vals.append(rf)
            g_vals.append(gf)
            b_vals.append(bf)
            rg_diff.append(rf - gf)
            rb_diff.append(rf - bf)
            gb_diff.append(gf - bf)
            gray_vals.append(0.299 * rf + 0.587 * gf + 0.114 * bf)

    aspect_cues = [aspect_ratio] * 64

    features = (
        r_vals
        + g_vals
        + b_vals
        + rg_diff
        + rb_diff
        + gb_diff
        + gray_vals
        + aspect_cues
    )  # 64 * 8 = 512 dimensions
    norm = math.sqrt(sum(x * x for x in features)) + 1e-8
    return [x / norm for x in features]


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Calculate cosine similarity between two unit-normalized vectors."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    return max(-1.0, min(1.0, dot))


@dataclass
class VisualEnrollmentSession:
    """Active visual enrollment session triggered by user voice/intent."""

    entity_id: str
    display_name: str
    target_samples: int = DEFAULT_TARGET_SAMPLES
    sample_interval: float = DEFAULT_SAMPLE_INTERVAL_SECONDS
    samples: list[list[float]] = field(default_factory=list)
    last_sample_time: float = 0.0
    completed: bool = False
    just_completed: bool = False

    def add_sample(self, crop: Image.Image) -> bool:
        """Attempt to add a sample from an object crop. Returns True if accepted."""
        if self.completed:
            return False
        now = time.time()
        if now - self.last_sample_time < self.sample_interval:
            return False

        # Verify crop quality (must have reasonable size)
        w, h = crop.size
        if w < 24 or h < 24:
            return False

        feature = extract_feature_vector(crop)
        self.samples.append(feature)
        self.last_sample_time = now

        if len(self.samples) >= self.target_samples:
            self.completed = True
            self.just_completed = True
            logger.info(
                "Visual enrollment for %s (%s) completed with %d samples.",
                self.entity_id,
                self.display_name,
                len(self.samples),
            )
        return True

    def progress(self) -> dict[str, Any]:
        """Return status payload for Web UI & API."""
        return {
            "active": not self.completed,
            "entity_id": self.entity_id,
            "display_name": self.display_name,
            "collected": len(self.samples),
            "target": self.target_samples,
            "completed": self.completed,
            "just_completed": self.just_completed,
        }


class VisualFeatureMatcher:
    """Thread-safe visual matcher holding enrolled templates."""

    def __init__(self, storage_path: Path = DEFAULT_SAMPLES_STORAGE) -> None:
        self.storage_path = storage_path
        self._lock = threading.RLock()
        self._enrolled: dict[str, dict[str, Any]] = {}
        self._active_session: Optional[VisualEnrollmentSession] = None
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.storage_path.exists():
                self._enrolled = {}
                return
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._enrolled = data
            except Exception as error:
                logger.warning("Failed to load enrolled visual features: %s", error)
                self._enrolled = {}

    def _save(self) -> None:
        with self._lock:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(
                json.dumps(self._enrolled, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def start_session(
        self,
        entity_id: str,
        display_name: str,
        *,
        target_samples: int = DEFAULT_TARGET_SAMPLES,
    ) -> VisualEnrollmentSession:
        """Start a new visual enrollment session for an entity."""
        with self._lock:
            session = VisualEnrollmentSession(
                entity_id=entity_id,
                display_name=display_name,
                target_samples=target_samples,
            )
            self._active_session = session
            return session

    def get_active_session(self) -> Optional[VisualEnrollmentSession]:
        with self._lock:
            return self._active_session

    def cancel_session(self) -> None:
        with self._lock:
            self._active_session = None

    def feed_crop(self, crop: Image.Image) -> Optional[dict[str, Any]]:
        """Feed a candidate crop into the active session if one exists."""
        with self._lock:
            session = self._active_session
            if session is None:
                return None
            session.just_completed = False
            session.add_sample(crop)
            if session.completed:
                # Save enrolled vectors
                self._enrolled[session.entity_id] = {
                    "entity_id": session.entity_id,
                    "display_name": session.display_name,
                    "samples": session.samples,
                    "enrolled_at": time.time(),
                }
                self._save()
                status = session.progress()
                self._active_session = None
                return status
            return session.progress()

    def match(
        self,
        crop: Image.Image,
        *,
        candidate_ids: Optional[Sequence[str]] = None,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> tuple[Optional[str], float]:
        """Match a crop against enrolled templates.

        Returns (best_entity_id, best_score) if score >= threshold, else (None, best_score).
        """
        with self._lock:
            if not self._enrolled:
                return None, 0.0

            feature = extract_feature_vector(crop)
            best_id: Optional[str] = None
            best_score = -1.0

            for entity_id, record in self._enrolled.items():
                if candidate_ids and entity_id not in candidate_ids:
                    continue
                samples = record.get("samples", [])
                for sample in samples:
                    score = cosine_similarity(feature, sample)
                    if score > best_score:
                        best_score = score
                        best_id = entity_id

            if best_score >= threshold:
                return best_id, best_score
            return None, max(0.0, best_score)

    def is_enrolled(self, entity_id: str) -> bool:
        with self._lock:
            return entity_id in self._enrolled


_GLOBAL_MATCHER: Optional[VisualFeatureMatcher] = None


def get_global_matcher() -> VisualFeatureMatcher:
    global _GLOBAL_MATCHER
    if _GLOBAL_MATCHER is None:
        _GLOBAL_MATCHER = VisualFeatureMatcher()
    return _GLOBAL_MATCHER
