"""Closed semantic inventory demo; it adds no video, model, or live source."""

from __future__ import annotations

from pathlib import Path

from .memory import ReplayArchive
from .fixture import load_fixture
from .orchestrator import run_fixture


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_FIXTURE = REPOSITORY_ROOT / "examples" / "fixtures" / "b0_home_inventory_v1.json"


def _fixture_path() -> Path:
    if INVENTORY_FIXTURE.is_file():
        return INVENTORY_FIXTURE
    installed = Path(__import__("sys").prefix) / "wha" / "examples" / "fixtures" / INVENTORY_FIXTURE.name
    if installed.is_file():
        return installed
    raise FileNotFoundError("the fixed home-inventory fixture is not installed")


def remember_inventory_demo(*, archive: ReplayArchive, replay_run_id: str) -> dict[str, object]:
    """Commit and explicitly archive the fixed multi-object semantic replay."""

    session = run_fixture(load_fixture(_fixture_path()), replay_run_id=replay_run_id)
    receipt = archive.save_completed(session)
    return {
        "archive": receipt.as_dict(),
        "governance": {
            "allowed_data": "D0_SYNTHETIC",
            "mode": "OFFLINE_SEMANTIC_REPLAY",
            "operate": "DISABLED",
            "physical_truth_claimed": False,
        },
        "inventory": {
            "fixture_id": session.fixture_id,
            "item_ids": ["key", "wallet", "remote", "book"],
            "container_ids": ["bag", "drawer"],
            "location_ids": ["sofa", "desk", "table", "shelf"],
        },
    }
