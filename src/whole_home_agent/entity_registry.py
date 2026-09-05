"""Dynamic entity registry for user-confirmed household objects.

Allows residents to register custom objects naturally (e.g. "這是水杯", "這是我的手機",
"幫我記這個是阿公的藥袋"). Registered entities receive the highest epistemic status
('user_confirmed') in accordance with the repository constitution.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .natural_query import DEFAULT_ENTITY_ALIASES

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = Path(".whole-home-agent/custom_entities.json")

# Regex patterns matching natural user registration intents
_REGISTRATION_PATTERNS = [
    re.compile(r"^(?:請?幫我記(?:一下)?(?:這個[是叫]|這是)?)(?:我(?:新買的|剛買的|的|嘅)?)?([a-zA-Z0-9_\u4e00-\u9fff]{1,16})"),
    re.compile(r"^(?:這個?叫(?:做|作|為)|這個?叫|這個?名稱是)(?:我(?:新買的|剛買的|的|嘅)?)?([a-zA-Z0-9_\u4e00-\u9fff]{1,16})"),
    re.compile(r"^(?:這是|這個是|這是一[個隻把支件杯])(?:我(?:新買的|剛買的|的|嘅)?)?([a-zA-Z0-9_\u4e00-\u9fff]{1,16})(?:喔|吧|啦|阿|啊)?$"),
    re.compile(r"^(?:我(?:新買的|剛買的)|新買的|剛買的)([a-zA-Z0-9_\u4e00-\u9fff]{1,16})(?:喔|吧|啦|阿|啊)?$"),
    re.compile(r"^(?:記住[，,\s]*(?:這[個是]|這是))(?:我(?:新買的|剛買的|的|嘅)?)?([a-zA-Z0-9_\u4e00-\u9fff]{1,16})"),
]

_COMMON_CLASSIFIERS = ("一個", "一隻", "一把", "台", "支", "本", "個", "雙", "條", "件", "杯")
_PURCHASE_PREFIXES = ("新買的", "剛買的", "買的", "我的", "我新買的", "我剛買的")
_TRAILING_PARTICLES = ("喔", "吧", "啦", "阿", "啊", "耶", "捏", "呦")


def _clean_entity_name(raw: str) -> str:
    cleaned = raw.strip("。！？!?~～ \t\r\n")
    for classifier in _COMMON_CLASSIFIERS:
        if cleaned.startswith(classifier):
            cleaned = cleaned[len(classifier) :]
            break
    for prefix in _PURCHASE_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    for particle in _TRAILING_PARTICLES:
        if cleaned.endswith(particle):
            cleaned = cleaned[: -len(particle)]
            break
    return cleaned.strip()


class EntityRegistry:
    """Thread-safe registry for user-confirmed custom entities."""

    def __init__(self, storage_path: Path = DEFAULT_REGISTRY_PATH) -> None:
        self.storage_path = storage_path
        self._lock = threading.RLock()
        self._entities: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.storage_path.exists():
                self._entities = {}
                return
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._entities = data
            except Exception as error:
                logger.warning("Failed to load entity registry: %s", error)
                self._entities = {}

    def _save(self) -> None:
        with self._lock:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(
                json.dumps(self._entities, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def register(
        self,
        name: str,
        *,
        aliases: list[str] | None = None,
        visual_category: str | None = None,
    ) -> dict[str, Any]:
        """Register a new user-confirmed entity or update existing aliases."""
        with self._lock:
            clean_name = _clean_entity_name(name)
            if not clean_name:
                raise ValueError("entity name cannot be empty")

            # Determine entity ID (slug or custom_ prefix)
            entity_id = f"custom_{clean_name}"
            # Standard common mappings
            if clean_name in ("手機", "手提電話", "phone"):
                entity_id = "phone"
            elif clean_name in ("水杯", "杯子", "保溫杯", "cup"):
                entity_id = "cup"
            elif clean_name in ("筆電", "筆記型電腦", "laptop"):
                entity_id = "laptop"

            existing_aliases = set(self._entities.get(entity_id, {}).get("aliases", []))
            existing_aliases.add(clean_name)
            if aliases:
                for a in aliases:
                    cleaned_a = _clean_entity_name(a)
                    if cleaned_a:
                        existing_aliases.add(cleaned_a)

            record = {
                "entity_id": entity_id,
                "display_name": clean_name,
                "aliases": sorted(list(existing_aliases)),
                "provenance": "user_confirmed",
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "visual_category": visual_category,
            }

            self._entities[entity_id] = record
            self._save()
            return record

    def list_entities(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entities.values())

    def get_aliases_map(self) -> dict[str, tuple[str, ...]]:
        """Return merged aliases combining DEFAULT_ENTITY_ALIASES and custom entities."""
        with self._lock:
            merged: dict[str, tuple[str, ...]] = dict(DEFAULT_ENTITY_ALIASES)
            # Default built-in extra aliases
            if "phone" not in merged:
                merged["phone"] = ("phone", "cellphone", "手機", "手机", "手提電話")
            if "cup" not in merged:
                merged["cup"] = ("cup", "water cup", "水杯", "杯子", "保溫杯", "水壺")
            if "laptop" not in merged:
                merged["laptop"] = ("laptop", "notebook", "筆電", "筆記型電腦", "電腦")

            for entity_id, info in self._entities.items():
                custom_aliases = tuple(info.get("aliases", []))
                existing = merged.get(entity_id, ())
                merged[entity_id] = tuple(sorted(set(existing + custom_aliases + (entity_id,))))
            return merged


_GLOBAL_REGISTRY: EntityRegistry | None = None


def get_global_registry() -> EntityRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = EntityRegistry()
    return _GLOBAL_REGISTRY


def try_parse_registration(question: str) -> str | None:
    """Return the object name if question is an entity registration intent."""
    normalized = question.strip()
    # Guard against queries like "這是什麼" or questions containing question marks
    if any(q_mark in normalized for q_mark in ("什麼", "甚麼", "誰", "哪裡", "在哪", "嗎", "?", "？")):
        return None

    for pattern in _REGISTRATION_PATTERNS:
        match = pattern.match(normalized)
        if match:
            target = _clean_entity_name(match.group(1))
            if target and target not in ("什麼", "甚麼", "誰", "東西"):
                return target
    return None
