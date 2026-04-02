"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    # src/agentic_commerce/config.py -> parents: package, src, repo
    return Path(__file__).resolve().parent.parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-in-production")
    DATABASE_PATH = Path(
        os.environ.get("CATALOG_DATABASE", _repo_root() / "data" / "catalog.sqlite")
    ).resolve()
    PRODUCTS_PER_PAGE_DEFAULT = 16
    PRODUCTS_PER_PAGE_CHOICES = (10, 16, 20)
