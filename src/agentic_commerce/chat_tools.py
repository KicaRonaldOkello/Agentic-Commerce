"""LangChain tools for the shopping assistant (SQLite-backed; Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from flask import current_app
from langchain_core.tools import tool

from agentic_commerce.chroma_catalog import chroma_collection_count, semantic_search_product_ids
from agentic_commerce.complements import fetch_complement_rows
from agentic_commerce.db import (
    fetch_list_rows_by_ids_ordered,
    fetch_product_by_id,
    fetch_product_by_slug,
    row_to_api_detail,
    row_to_api_summary,
    screen_size_bucket,
    search_products,
)

SortLiteral = Literal["name", "price_asc", "price_desc", "rating", "deals"]

CatalogCategoryLiteral = Literal[
    "all",
    "phone",
    "television",
    "earphones",
    "power_bank",
    "soundbar",
]


def _db_path():
    return current_app.config["DATABASE_PATH"]


def _db_error() -> str:
    return json.dumps({"error": "Catalog database is missing. Load data with the sqlite loader script."})


@tool
def search_catalog(
    category: Annotated[
        CatalogCategoryLiteral,
        "Product category: all, phone, television, earphones, power_bank, or soundbar.",
    ] = "all",
    price_min: Annotated[int | None, "Minimum price in UGX (inclusive). Omit if not needed."] = None,
    price_max: Annotated[int | None, "Maximum price in UGX (inclusive). Omit if not needed."] = None,
    tier: Annotated[
        Literal["low", "mid", "high"] | None,
        "Market tier filter, or omit for any tier.",
    ] = None,
    brand: Annotated[str | None, "Substring match on brand name (case-insensitive)."] = None,
    search_query: Annotated[
        str | None,
        "Keywords to match in product name or short description.",
    ] = None,
    sort: Annotated[
        SortLiteral,
        "Sort order: name, price_asc, price_desc, rating, or deals (best discount % first per deal policy).",
    ] = "name",
    in_stock_only: Annotated[bool, "If true, only products with availability_status in_stock."] = False,
    screen_inches: Annotated[
        float | None,
        "Diagonal screen inches (e.g. 5.6). Matches the integer inch bucket only (5.6→5 with 5.0–5.99″); products without a recorded diagonal are excluded. Omit if not needed.",
    ] = None,
    limit: Annotated[int, "Max products to return (1–25)."] = 10,
) -> str:
    """Search and filter the product catalog. Always use this for lists, prices, and filters—not memory."""
    path = _db_path()
    if not path.is_file():
        return _db_error()

    pt = None if category == "all" else category
    lim = max(1, min(int(limit), 25))

    result = search_products(
        path,
        product_type=pt,
        price_min=price_min,
        price_max=price_max,
        tier=tier,
        brand=brand.strip() if brand else None,
        q=search_query.strip() if search_query else None,
        in_stock_only=in_stock_only,
        screen_inches=screen_inches,
        sort=sort if sort in ("name", "price_asc", "price_desc", "rating", "deals") else "name",
        page=1,
        per_page=lim,
    )

    payload = {
        "total_matching": result.total,
        "returned": len(result.items),
        "products": [row_to_api_summary(r) for r in result.items],
    }
    if screen_inches is not None:
        payload["screen_inch_bucket"] = screen_size_bucket(screen_inches)
    return json.dumps(payload, ensure_ascii=False)


@tool
def get_product_details(
    product_identifier: Annotated[
        str,
        "Product id (e.g. prod_phone_…) or URL slug from the catalog.",
    ],
) -> str:
    """Load one full product record including description, specs, and images. Use for comparisons or deep questions."""
    path = _db_path()
    if not path.is_file():
        return _db_error()

    row = fetch_product_by_id(path, product_identifier.strip())
    if not row:
        row = fetch_product_by_slug(path, product_identifier.strip())
    if not row:
        return json.dumps({"error": f"No product found for identifier: {product_identifier!r}"})

    detail = row_to_api_detail(row)
    return json.dumps(detail, ensure_ascii=False)


@tool
def get_complements(
    product_identifier: Annotated[
        str,
        "Product id or slug for the item the user chose (anchor). Required—complements are always for one specific catalog product.",
    ],
    limit: Annotated[int, "How many complement suggestions to return (2–5)."] = 5,
) -> str:
    """In-stock accessories and related categories that pair with a specific product. Use only after the user has a chosen product (id/slug from tools or thread). Never invent SKUs."""
    path = _db_path()
    if not path.is_file():
        return _db_error()

    ident = product_identifier.strip()
    row = fetch_product_by_id(path, ident) or fetch_product_by_slug(path, ident)
    if not row:
        return json.dumps({"error": f"No product found for identifier: {product_identifier!r}"})

    lim = max(2, min(int(limit), 5))
    comp_rows = fetch_complement_rows(path, anchor_row=row, limit=lim)
    source = {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "brand": row["brand"],
        "product_type": row["product_type"],
        "price": row["price"],
        "currency": row["currency"],
    }
    payload = {
        "source_product": source,
        "products": [row_to_api_summary(r) for r in comp_rows],
        "returned": len(comp_rows),
        "note": "Complements are rule-based by category; describe only these rows.",
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
def top_deals(
    category: Annotated[
        CatalogCategoryLiteral,
        "Restrict deals to this category, or all.",
    ] = "all",
    limit: Annotated[int, "How many deals to return (1–25)."] = 8,
) -> str:
    """Best in-stock deals ranked by discount percentage, then rating (see deal policy). Use when the user asks for deals or savings."""
    path = _db_path()
    if not path.is_file():
        return _db_error()

    pt = None if category == "all" else category
    lim = max(1, min(int(limit), 25))

    result = search_products(
        path,
        product_type=pt,
        sort="deals",
        in_stock_only=True,
        page=1,
        per_page=lim,
    )

    payload = {
        "total_matching": result.total,
        "returned": len(result.items),
        "products": [row_to_api_summary(r) for r in result.items],
        "note": "Sorted by deal ranking (discount % when compare_at_price is set, else rating/price). In-stock only.",
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
def discover_catalog(
    query: Annotated[
        str,
        "Natural-language discovery: use case, room, or vague features (e.g. bright room TV, long battery phone). Not for exact brand/SKU.",
    ],
    category: Annotated[
        CatalogCategoryLiteral,
        "Product type filter, or all.",
    ] = "all",
    price_min: Annotated[int | None, "Minimum price UGX (inclusive)."] = None,
    price_max: Annotated[int | None, "Maximum price UGX (inclusive)."] = None,
    tier: Annotated[
        Literal["low", "mid", "high"] | None,
        "Tier filter, or omit.",
    ] = None,
    brand: Annotated[str | None, "Substring on brand (applied after semantic rank)."] = None,
    in_stock_only: Annotated[bool, "If true, prefer in-stock in the index and SQL."] = False,
    screen_inches: Annotated[
        float | None,
        "Diagonal inches for integer bucket filter (e.g. 5.6→5″ class). Excludes products without recorded diagonal in Chroma/SQL. Omit if not needed.",
    ] = None,
    limit: Annotated[int, "Max products to return (1–25)."] = 10,
) -> str:
    """Semantic search over product descriptions (Chroma + embeddings), then SQL filters for prices/stock. Use for vague or lifestyle queries; use search_catalog for exact filters."""
    path = _db_path()
    if not path.is_file():
        return _db_error()

    cfg = current_app.config
    chroma_path = Path(cfg["CHROMA_PATH"])
    coll_name = cfg["CHROMA_COLLECTION_NAME"]
    if chroma_collection_count(chroma_path, coll_name) == 0:
        return json.dumps(
            {
                "error": "Semantic index is empty. Run: uv run python scripts/embed_catalog_chroma.py",
            },
            ensure_ascii=False,
        )

    api_key = (cfg.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return json.dumps({"error": "OPENAI_API_KEY is required for semantic search."})

    lim = max(1, min(int(limit), 25))
    pt_filter = None if category == "all" else category

    ids = semantic_search_product_ids(
        chroma_path=chroma_path,
        collection_name=coll_name,
        query=query.strip(),
        api_key=api_key,
        embedding_model=cfg["OPENAI_EMBEDDING_MODEL"],
        openai_api_base=cfg.get("OPENAI_BASE_URL") or None,
        category=category,
        in_stock_only=in_stock_only,
        screen_inches=screen_inches,
        top_k=120,
    )

    rows = fetch_list_rows_by_ids_ordered(
        path,
        ids,
        product_type=pt_filter,
        price_min=price_min,
        price_max=price_max,
        tier=tier,
        brand=brand.strip() if brand else None,
        in_stock_only=in_stock_only,
        screen_inches=screen_inches,
        limit=lim,
    )

    payload = {
        "method": "semantic_search",
        "candidates_ranked": len(ids),
        "returned": len(rows),
        "products": [row_to_api_summary(r) for r in rows],
        "note": "Ranked by language similarity, then filtered in SQL for price/tier/brand/stock.",
    }
    if screen_inches is not None:
        payload["screen_inch_bucket"] = screen_size_bucket(screen_inches)
    return json.dumps(payload, ensure_ascii=False)


SHOPPING_TOOLS = [
    search_catalog,
    discover_catalog,
    get_product_details,
    get_complements,
    top_deals,
]

# Phase 3 specialist subgraphs (subset of tools per node)
BROWSE_TOOLS = [search_catalog, discover_catalog, get_product_details, get_complements]
DEALS_TOOLS = [top_deals, search_catalog]
COMPARE_TOOLS = [get_product_details, search_catalog, get_complements]
