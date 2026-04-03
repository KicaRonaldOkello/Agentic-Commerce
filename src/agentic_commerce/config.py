"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _repo_root() -> Path:
    # src/agentic_commerce/config.py -> parents: package, src, repo
    return Path(__file__).resolve().parent.parent.parent


# Repo root .env (OPENAI_API_KEY, etc.) — loaded before Config reads os.environ.
load_dotenv(_repo_root() / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-in-production")
    # Phase 1 assistant (OpenAI). For OpenRouter later: set OPENAI_BASE_URL=https://openrouter.ai/api/v1 and use an OpenRouter key.
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "").strip() or None

    REPO_ROOT = _repo_root()
    DATABASE_PATH = Path(
        os.environ.get("CATALOG_DATABASE", REPO_ROOT / "data" / "catalog.sqlite")
    ).resolve()
    DEAL_POLICY_PATH = (REPO_ROOT / "docs" / "DEAL_POLICY.md").resolve()
    PRODUCTS_PER_PAGE_DEFAULT = 16
    PRODUCTS_PER_PAGE_CHOICES = (10, 16, 20)
