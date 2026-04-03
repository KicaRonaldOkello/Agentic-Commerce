#!/usr/bin/env python3
"""Build or refresh the local Chroma index from catalog.sqlite (Phase 2).

Requires OPENAI_API_KEY (e.g. in repo-root .env). Run after loading SQLite:

  uv run python scripts/load_products_sqlite.py
  uv run python scripts/embed_catalog_chroma.py

Recreate the collection from scratch:

  uv run python scripts/embed_catalog_chroma.py --reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from dotenv import load_dotenv

load_dotenv(_REPO / ".env")

from agentic_commerce.chroma_catalog import embed_and_upsert_catalog  # noqa: E402
from agentic_commerce.config import Config  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Embed catalog into Chroma")
    p.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing collection before re-embedding.",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Embedding batch size (default 64).",
    )
    args = p.parse_args()

    db_path = Config.DATABASE_PATH
    if not db_path.is_file():
        print(f"Error: database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    key = (Config.OPENAI_API_KEY or "").strip()
    if not key:
        print("Error: OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    n = embed_and_upsert_catalog(
        db_path=db_path,
        chroma_path=Config.CHROMA_PATH,
        collection_name=Config.CHROMA_COLLECTION_NAME,
        api_key=key,
        embedding_model=Config.OPENAI_EMBEDDING_MODEL,
        openai_api_base=Config.OPENAI_BASE_URL,
        batch_size=max(1, args.batch_size),
        reset=args.reset,
    )
    print(f"Upserted {n} product vectors into Chroma at {Config.CHROMA_PATH}")


if __name__ == "__main__":
    main()
