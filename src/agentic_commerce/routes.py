from __future__ import annotations

from typing import Any

from pathlib import Path

from flask import Blueprint, Response, abort, current_app, render_template, request

from agentic_commerce.db import fetch_product_by_slug, search_products

bp = Blueprint("catalog", __name__)


def _db_or_503():
    path = current_app.config["DATABASE_PATH"]
    if not path.is_file():
        abort(
            503,
            description="Catalog database not found. Run: uv run python scripts/load_products_sqlite.py",
        )
    return path


def _optional_int(raw: str | None) -> int | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def _optional_float(raw: str | None) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(str(raw).strip())
    except ValueError:
        return None


def _parse_listing_filters() -> dict[str, Any]:
    """Parse GET params for search_products + template / nav."""
    cfg = current_app.config

    raw_cat = request.args.get("category", "all").strip().lower()
    if raw_cat in ("all", ""):
        category_key = "all"
        product_type = None
    elif raw_cat in ("phone", "phones"):
        category_key = "phone"
        product_type = "phone"
    elif raw_cat in ("television", "tv", "tvs", "televisions"):
        category_key = "television"
        product_type = "television"
    elif raw_cat in ("earphones", "earphone", "headphones", "headphone", "buds", "headsets"):
        category_key = "earphones"
        product_type = "earphones"
    elif raw_cat in ("power_bank", "power-bank", "powerbank", "powerbanks"):
        category_key = "power_bank"
        product_type = "power_bank"
    elif raw_cat in ("soundbar", "soundbars", "tv_speaker", "tv-speaker", "tv-speakers"):
        category_key = "soundbar"
        product_type = "soundbar"
    else:
        category_key = "all"
        product_type = None

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1

    try:
        per_page = int(request.args.get("per_page", str(cfg["PRODUCTS_PER_PAGE_DEFAULT"])))
    except ValueError:
        per_page = cfg["PRODUCTS_PER_PAGE_DEFAULT"]

    if per_page not in cfg["PRODUCTS_PER_PAGE_CHOICES"]:
        per_page = cfg["PRODUCTS_PER_PAGE_DEFAULT"]

    price_min = _optional_int(request.args.get("price_min"))
    price_max = _optional_int(request.args.get("price_max"))
    tier_raw = (request.args.get("tier") or "").strip().lower()
    tier = tier_raw if tier_raw in ("low", "mid", "high") else ""
    brand = (request.args.get("brand") or "").strip()
    q = (request.args.get("q") or "").strip()
    sort = (request.args.get("sort") or "name").strip().lower()
    if sort not in ("name", "price_asc", "price_desc", "rating", "deals"):
        sort = "name"
    in_stock_only = request.args.get("in_stock") in ("1", "on", "true", "yes")
    screen_inches = _optional_float(request.args.get("screen_inches"))

    return {
        "category_key": category_key,
        "product_type": product_type,
        "page": page,
        "per_page": per_page,
        "price_min": price_min,
        "price_max": price_max,
        "tier": tier,
        "brand": brand,
        "q": q,
        "sort": sort,
        "in_stock_only": in_stock_only,
        "screen_inches": screen_inches,
    }


def _nav_kwargs(f: dict[str, Any], *, for_endpoint: str) -> dict[str, Any]:
    """Query args for pagination / preserving filters (omit empties)."""
    out: dict[str, Any] = {
        "category": f["category_key"],
        "per_page": f["per_page"],
    }
    if for_endpoint == "catalog.products":
        out["sort"] = f["sort"]
    if f["price_min"] is not None:
        out["price_min"] = f["price_min"]
    if f["price_max"] is not None:
        out["price_max"] = f["price_max"]
    if f["tier"]:
        out["tier"] = f["tier"]
    if f["brand"]:
        out["brand"] = f["brand"]
    if f["q"]:
        out["q"] = f["q"]
    if f["in_stock_only"]:
        out["in_stock"] = "1"
    if f.get("screen_inches") is not None:
        out["screen_inches"] = f["screen_inches"]
    return out


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/deal-policy")
def deal_policy():
    path: Path = current_app.config["DEAL_POLICY_PATH"]
    if not path.is_file():
        abort(404)
    text = path.read_text(encoding="utf-8")
    return Response(text, mimetype="text/plain; charset=utf-8")


@bp.route("/products")
def products():
    db_path = _db_or_503()
    f = _parse_listing_filters()

    result = search_products(
        db_path,
        product_type=f["product_type"],
        price_min=f["price_min"],
        price_max=f["price_max"],
        tier=f["tier"] or None,
        brand=f["brand"] or None,
        q=f["q"] or None,
        in_stock_only=f["in_stock_only"],
        screen_inches=f.get("screen_inches"),
        sort=f["sort"],
        page=f["page"],
        per_page=f["per_page"],
    )

    nav = _nav_kwargs(f, for_endpoint="catalog.products")

    return render_template(
        "products.html",
        result=result,
        category=f["category_key"],
        per_page=f["per_page"],
        per_page_choices=current_app.config["PRODUCTS_PER_PAGE_CHOICES"],
        price_min=f["price_min"],
        price_max=f["price_max"],
        tier=f["tier"],
        brand=f["brand"],
        q=f["q"],
        sort=f["sort"],
        in_stock_only=f["in_stock_only"],
        screen_inches=f.get("screen_inches"),
        deals_mode=False,
        list_endpoint="catalog.products",
        nav_kwargs=nav,
    )


@bp.route("/deals")
def deals():
    db_path = _db_or_503()
    f = _parse_listing_filters()
    f["sort"] = "deals"

    result = search_products(
        db_path,
        product_type=f["product_type"],
        price_min=f["price_min"],
        price_max=f["price_max"],
        tier=f["tier"] or None,
        brand=f["brand"] or None,
        q=f["q"] or None,
        in_stock_only=True,
        screen_inches=f.get("screen_inches"),
        sort="deals",
        page=f["page"],
        per_page=f["per_page"],
    )

    nav = _nav_kwargs({**f, "in_stock_only": True}, for_endpoint="catalog.deals")

    return render_template(
        "products.html",
        result=result,
        category=f["category_key"],
        per_page=f["per_page"],
        per_page_choices=current_app.config["PRODUCTS_PER_PAGE_CHOICES"],
        price_min=f["price_min"],
        price_max=f["price_max"],
        tier=f["tier"],
        brand=f["brand"],
        q=f["q"],
        sort="deals",
        in_stock_only=True,
        screen_inches=f.get("screen_inches"),
        deals_mode=True,
        list_endpoint="catalog.deals",
        nav_kwargs=nav,
    )


@bp.route("/assistant")
def assistant_page():
    enabled = current_app.extensions.get("shopping_agent") is not None
    return render_template(
        "assistant.html",
        assistant_enabled=enabled,
        model=current_app.config.get("OPENAI_MODEL", ""),
    )


@bp.route("/products/<slug>")
def product_detail(slug: str):
    db_path = _db_or_503()
    product = fetch_product_by_slug(db_path, slug)
    if not product:
        abort(404)
    return render_template("product_detail.html", product=product)
