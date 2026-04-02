"""SQLite access for the product catalog."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


@dataclass
class ProductListResult:
    items: list[dict[str, Any]]
    total: int
    page: int
    per_page: int

    @property
    def total_pages(self) -> int:
        if self.total <= 0:
            return 1
        return (self.total + self.per_page - 1) // self.per_page

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


def fetch_products(
    db_path: Path,
    *,
    category: str | None,
    page: int = 1,
    per_page: int = 16,
) -> ProductListResult:
    """
    category: 'phone', 'television', or None for all.
    """
    per_page = max(1, min(per_page, 100))

    where = ""
    params: list[Any] = []
    if category in ("phone", "television"):
        where = "WHERE product_type = ?"
        params.append(category)

    count_sql = f"SELECT COUNT(*) AS c FROM products {where}"
    list_sql = f"""
        SELECT
            id, sku, name, slug, brand, product_type, tier, currency,
            price, compare_at_price, stock_quantity, availability_status,
            rating_average, review_count, short_description, thumbnail
        FROM products
        {where}
        ORDER BY brand COLLATE NOCASE, name COLLATE NOCASE
        LIMIT ? OFFSET ?
    """

    with get_connection(db_path) as conn:
        cur = conn.execute(count_sql, params)
        total = int(cur.fetchone()["c"])

        total_pages = max(1, (total + per_page - 1) // per_page) if total else 1
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page

        cur = conn.execute(list_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]

    return ProductListResult(items=rows, total=total, page=page, per_page=per_page)


def fetch_product_by_slug(db_path: Path, slug: str) -> dict[str, Any] | None:
    sql = """
        SELECT
            id, sku, name, slug, brand, category, product_type, tier, currency,
            price, compare_at_price, stock_quantity, availability_status,
            rating_average, review_count, short_description, description,
            key_features_json, specifications_json, whats_in_box_json, attributes_json,
            thumbnail, images_json, image_attribution,
            is_duplicate_listing, duplicate_of_id
        FROM products
        WHERE slug = ?
        LIMIT 1
    """
    with get_connection(db_path) as conn:
        cur = conn.execute(sql, (slug,))
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    json_map = (
        ("key_features_json", "key_features"),
        ("specifications_json", "specifications"),
        ("whats_in_box_json", "whats_in_box"),
        ("attributes_json", "attributes"),
        ("images_json", "images"),
    )
    for src, dest in json_map:
        raw = d.get(src)
        if isinstance(raw, str) and raw.strip():
            try:
                d[dest] = json.loads(raw)
            except json.JSONDecodeError:
                pass
    return d
