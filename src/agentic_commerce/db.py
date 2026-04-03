"""SQLite access for the product catalog."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIST_SELECT = """
    id, sku, name, slug, brand, product_type, tier, currency,
    price, compare_at_price, stock_quantity, availability_status,
    rating_average, review_count, short_description, thumbnail,
    screen_diagonal_inches
"""

CATALOG_PRODUCT_TYPES: frozenset[str] = frozenset(
    {"phone", "television", "earphones", "power_bank", "soundbar"}
)


def screen_size_bucket(inches: float | int) -> int:
    """Integer inch bucket (5.6 → 5); matches SQLite CAST(diagonal AS INTEGER) for positive sizes."""
    return int(float(inches))


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


def _parse_json_row(d: dict[str, Any]) -> None:
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


def _build_search_where(
    *,
    product_type: str | None,
    price_min: int | None,
    price_max: int | None,
    tier: str | None,
    brand: str | None,
    q: str | None,
    in_stock_only: bool,
    screen_inches: float | int | None = None,
) -> tuple[str, list[Any]]:
    wheres: list[str] = ["1 = 1"]
    params: list[Any] = []

    if product_type in CATALOG_PRODUCT_TYPES:
        wheres.append("product_type = ?")
        params.append(product_type)
    if price_min is not None:
        wheres.append("price >= ?")
        params.append(price_min)
    if price_max is not None:
        wheres.append("price <= ?")
        params.append(price_max)
    if tier in ("low", "mid", "high"):
        wheres.append("tier = ?")
        params.append(tier)
    if brand and brand.strip():
        wheres.append("LOWER(brand) LIKE ?")
        params.append(f"%{brand.strip().lower()}%")
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        wheres.append("(LOWER(name) LIKE ? OR LOWER(short_description) LIKE ?)")
        params.extend([term, term])
    if in_stock_only:
        wheres.append("availability_status = 'in_stock'")
    if screen_inches is not None:
        bucket = screen_size_bucket(screen_inches)
        wheres.append("screen_diagonal_inches IS NOT NULL")
        wheres.append("CAST(screen_diagonal_inches AS INTEGER) = ?")
        params.append(bucket)

    return " AND ".join(wheres), params


def _order_clause(sort: str) -> str:
    if sort == "deals":
        return """CASE WHEN compare_at_price IS NOT NULL AND compare_at_price > price
                THEN 0 ELSE 1 END ASC,
            CASE WHEN compare_at_price IS NOT NULL AND compare_at_price > price
                THEN (compare_at_price - price) * 1.0 / compare_at_price END DESC,
            rating_average DESC,
            price ASC,
            name COLLATE NOCASE"""
    if sort == "price_asc":
        return "price ASC, name COLLATE NOCASE"
    if sort == "price_desc":
        return "price DESC, name COLLATE NOCASE"
    if sort == "rating":
        return "rating_average DESC, review_count DESC, name COLLATE NOCASE"
    return "brand COLLATE NOCASE, name COLLATE NOCASE"


def search_products(
    db_path: Path,
    *,
    product_type: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    tier: str | None = None,
    brand: str | None = None,
    q: str | None = None,
    in_stock_only: bool = False,
    screen_inches: float | int | None = None,
    sort: str = "name",
    page: int = 1,
    per_page: int = 16,
) -> ProductListResult:
    """
    Filter catalog rows with optional text search on name and short_description.

    sort: name | price_asc | price_desc | rating | deals (see docs/DEAL_POLICY.md)
    """
    per_page = max(1, min(per_page, 100))
    if sort not in ("name", "price_asc", "price_desc", "rating", "deals"):
        sort = "name"

    where_sql, params = _build_search_where(
        product_type=product_type,
        price_min=price_min,
        price_max=price_max,
        tier=tier,
        brand=brand,
        q=q,
        in_stock_only=in_stock_only,
        screen_inches=screen_inches,
    )
    order_sql = _order_clause(sort)

    count_sql = f"SELECT COUNT(*) AS c FROM products WHERE {where_sql}"
    list_sql = f"""
        SELECT {LIST_SELECT.strip()}
        FROM products
        WHERE {where_sql}
        ORDER BY {order_sql}
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


def fetch_list_rows_by_ids_ordered(
    db_path: Path,
    ids_ordered: list[str],
    *,
    product_type: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    tier: str | None = None,
    brand: str | None = None,
    in_stock_only: bool = False,
    screen_inches: float | int | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """List rows for ids that pass catalog filters, preserving first-seen order from ``ids_ordered``."""
    if not ids_ordered:
        return []
    limit = max(1, min(int(limit), 100))
    in_ph = ",".join("?" * len(ids_ordered))
    id_clause = f"id IN ({in_ph})"
    filter_where, filter_params = _build_search_where(
        product_type=product_type,
        price_min=price_min,
        price_max=price_max,
        tier=tier,
        brand=brand,
        q=None,
        in_stock_only=in_stock_only,
        screen_inches=screen_inches,
    )
    full_where = f"({id_clause}) AND ({filter_where})"
    params: list[Any] = list(ids_ordered) + filter_params
    sql = f"""
        SELECT {LIST_SELECT.strip()}
        FROM products
        WHERE {full_where}
    """
    with get_connection(db_path) as conn:
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
    by_id = {r["id"]: r for r in rows}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pid in ids_ordered:
        if pid in by_id and pid not in seen:
            seen.add(pid)
            out.append(by_id[pid])
            if len(out) >= limit:
                break
    return out


def fetch_products(
    db_path: Path,
    *,
    category: str | None,
    page: int = 1,
    per_page: int = 16,
) -> ProductListResult:
    """Backward-compatible wrapper: category = product_type."""
    return search_products(
        db_path,
        product_type=category,
        page=page,
        per_page=per_page,
    )


def fetch_product_by_slug(db_path: Path, slug: str) -> dict[str, Any] | None:
    sql = """
        SELECT
            id, sku, name, slug, brand, category, product_type, tier, currency,
            price, compare_at_price, stock_quantity, availability_status,
            rating_average, review_count, short_description, description,
            key_features_json, specifications_json, whats_in_box_json, attributes_json,
            thumbnail, images_json, image_attribution,
            is_duplicate_listing, duplicate_of_id, screen_diagonal_inches
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
    _parse_json_row(d)
    return d


def fetch_product_by_id(db_path: Path, product_id: str) -> dict[str, Any] | None:
    sql = """
        SELECT
            id, sku, name, slug, brand, category, product_type, tier, currency,
            price, compare_at_price, stock_quantity, availability_status,
            rating_average, review_count, short_description, description,
            key_features_json, specifications_json, whats_in_box_json, attributes_json,
            thumbnail, images_json, image_attribution,
            is_duplicate_listing, duplicate_of_id, screen_diagonal_inches
        FROM products
        WHERE id = ?
        LIMIT 1
    """
    with get_connection(db_path) as conn:
        cur = conn.execute(sql, (product_id,))
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    _parse_json_row(d)
    return d


def row_to_api_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Stable JSON shape for list endpoints."""
    return {
        "id": row["id"],
        "sku": row["sku"],
        "name": row["name"],
        "slug": row["slug"],
        "brand": row["brand"],
        "product_type": row["product_type"],
        "tier": row["tier"],
        "currency": row["currency"],
        "price": row["price"],
        "compare_at_price": row["compare_at_price"],
        "stock_quantity": row["stock_quantity"],
        "availability_status": row["availability_status"],
        "rating_average": row["rating_average"],
        "review_count": row["review_count"],
        "short_description": row["short_description"],
        "thumbnail": row["thumbnail"],
        "screen_diagonal_inches": row.get("screen_diagonal_inches"),
    }


def row_to_api_detail(d: dict[str, Any]) -> dict[str, Any]:
    """Full product for API detail; strips raw *_json keys if parsed copies exist."""
    out = {k: v for k, v in d.items() if not k.endswith("_json")}
    for k in ("key_features", "specifications", "whats_in_box", "attributes", "images"):
        if k in d:
            out[k] = d[k]
    return out
