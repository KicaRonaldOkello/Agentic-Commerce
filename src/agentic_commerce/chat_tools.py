"""LangChain tools for the shopping assistant (SQLite-backed; Phase 1)."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from flask import current_app
from langchain_core.tools import tool

from agentic_commerce.db import (
    fetch_product_by_id,
    fetch_product_by_slug,
    row_to_api_detail,
    row_to_api_summary,
    search_products,
)

SortLiteral = Literal["name", "price_asc", "price_desc", "rating", "deals"]


def _db_path():
    return current_app.config["DATABASE_PATH"]


def _db_error() -> str:
    return json.dumps({"error": "Catalog database is missing. Load data with the sqlite loader script."})


@tool
def search_catalog(
    category: Annotated[
        Literal["all", "phone", "television"],
        "Product category: all, phone, or television.",
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
        sort=sort if sort in ("name", "price_asc", "price_desc", "rating", "deals") else "name",
        page=1,
        per_page=lim,
    )

    payload = {
        "total_matching": result.total,
        "returned": len(result.items),
        "products": [row_to_api_summary(r) for r in result.items],
    }
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
def top_deals(
    category: Annotated[
        Literal["all", "phone", "television"],
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


SHOPPING_TOOLS = [search_catalog, get_product_details, top_deals]
