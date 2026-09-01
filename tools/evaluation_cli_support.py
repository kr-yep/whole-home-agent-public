"""Small shared helpers for repository-only offline evaluation runners."""

from __future__ import annotations

import gc
from pathlib import Path
import subprocess


def git_state(repository_root: Path) -> tuple[str, bool]:
    safe = f"safe.directory={repository_root.as_posix()}"
    revision = subprocess.run(
        ["git", "-c", safe, "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "-c", safe, "status", "--porcelain"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    )
    return revision, dirty


def release_detector_runtime() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
