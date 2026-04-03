"""Rule-based complementary products (Phase 4): deterministic pairs by product_type."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_commerce.db import CATALOG_PRODUCT_TYPES, search_products

# Anchor category → ordered list of complement categories (in-stock picks filled first).
COMPLEMENT_PRODUCT_TYPES: dict[str, list[str]] = {
    "television": ["soundbar", "earphones", "power_bank"],
    "phone": ["earphones", "power_bank"],
    "soundbar": ["earphones", "power_bank", "television"],
    "earphones": ["power_bank", "phone"],
    "power_bank": ["earphones", "phone"],
}

DEFAULT_COMPLEMENT_TYPES: list[str] = ["earphones", "power_bank"]


def complement_types_for(anchor_product_type: str) -> list[str]:
    raw = COMPLEMENT_PRODUCT_TYPES.get(anchor_product_type) or DEFAULT_COMPLEMENT_TYPES
    return [t for t in raw if t in CATALOG_PRODUCT_TYPES and t != anchor_product_type] or list(
        DEFAULT_COMPLEMENT_TYPES
    )


def fetch_complement_rows(
    db_path: Path,
    *,
    anchor_row: dict[str, Any],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Return up to ``limit`` catalog rows that pair with the anchor product.
    Uses only SQLite + search_products; no LLM. Excludes the anchor id.
    Picks round-robin across complement categories so results mix (e.g. TV → soundbar + earphones).
    """
    limit = max(2, min(int(limit), 5))
    anchor_id = anchor_row["id"]
    pt = str(anchor_row.get("product_type") or "")
    targets = complement_types_for(pt)

    seen: set[str] = {anchor_id}
    # Queue per category (deal-ranked); fetch enough candidates for round-robin.
    per_fetch = max(limit, 8)
    queues: dict[str, list[dict[str, Any]]] = {}
    for t in targets:
        result = search_products(
            db_path,
            product_type=t,
            in_stock_only=True,
            sort="deals",
            page=1,
            per_page=per_fetch,
        )
        queues[t] = [r for r in result.items if r["id"] not in seen]

    collected: list[dict[str, Any]] = []
    while len(collected) < limit and targets:
        progressed = False
        for t in targets:
            if len(collected) >= limit:
                break
            q = queues.get(t) or []
            while q and q[0]["id"] in seen:
                q.pop(0)
            if not q:
                continue
            row = q.pop(0)
            rid = row["id"]
            if rid in seen:
                continue
            seen.add(rid)
            collected.append(row)
            progressed = True
        if not progressed:
            break

    return collected[:limit]
