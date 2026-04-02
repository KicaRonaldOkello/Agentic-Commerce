from __future__ import annotations

from flask import Blueprint, abort, current_app, render_template, request

from agentic_commerce.db import fetch_product_by_slug, fetch_products

bp = Blueprint("catalog", __name__)


def _db_or_503():
    path = current_app.config["DATABASE_PATH"]
    if not path.is_file():
        abort(
            503,
            description="Catalog database not found. Run: uv run python scripts/load_products_sqlite.py",
        )
    return path


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/products")
def products():
    db_path = _db_or_503()

    raw = request.args.get("category", "all").strip().lower()
    if raw in ("all", ""):
        category_key = "all"
        category = None
    elif raw in ("phone", "phones"):
        category_key = "phone"
        category = "phone"
    elif raw in ("television", "tv", "tvs", "televisions"):
        category_key = "television"
        category = "television"
    else:
        category_key = "all"
        category = None

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1

    cfg = current_app.config
    try:
        per_page = int(request.args.get("per_page", str(cfg["PRODUCTS_PER_PAGE_DEFAULT"])))
    except ValueError:
        per_page = cfg["PRODUCTS_PER_PAGE_DEFAULT"]

    if per_page not in cfg["PRODUCTS_PER_PAGE_CHOICES"]:
        per_page = cfg["PRODUCTS_PER_PAGE_DEFAULT"]

    result = fetch_products(db_path, category=category, page=page, per_page=per_page)

    return render_template(
        "products.html",
        result=result,
        category=category_key,
        per_page=per_page,
        per_page_choices=cfg["PRODUCTS_PER_PAGE_CHOICES"],
    )


@bp.route("/products/<slug>")
def product_detail(slug: str):
    db_path = _db_or_503()
    product = fetch_product_by_slug(db_path, slug)
    if not product:
        abort(404)
    return render_template("product_detail.html", product=product)
