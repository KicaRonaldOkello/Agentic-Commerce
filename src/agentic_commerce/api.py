"""JSON API for catalog search (Phase 0) and chat (Phase 1)."""

from __future__ import annotations

import uuid

from flask import Blueprint, abort, current_app, jsonify, request

from agentic_commerce.db import (
    fetch_product_by_id,
    fetch_product_by_slug,
    row_to_api_detail,
    row_to_api_summary,
    search_products,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _db_or_503():
    path = current_app.config["DATABASE_PATH"]
    if not path.is_file():
        abort(
            503,
            description="Catalog database not found. Run: uv run python scripts/load_products_sqlite.py",
        )
    return path


def _parse_category() -> str | None:
    raw = request.args.get("category", "all").strip().lower()
    if raw in ("all", ""):
        return None
    if raw in ("phone", "phones"):
        return "phone"
    if raw in ("television", "tv", "tvs", "televisions"):
        return "television"
    return None


def _parse_int_arg(name: str) -> int | None:
    v = request.args.get(name, type=str)
    if v is None or v.strip() == "":
        return None
    try:
        return int(v.strip())
    except ValueError:
        return None


@api_bp.get("/products")
def api_list_products():
    db_path = _db_or_503()
    product_type = _parse_category()

    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", type=int) or current_app.config["PRODUCTS_PER_PAGE_DEFAULT"]
    per_page = max(1, min(per_page, 100))

    price_min = _parse_int_arg("price_min")
    price_max = _parse_int_arg("price_max")
    tier = request.args.get("tier", type=str)
    tier = tier.strip().lower() if tier else None
    if tier not in (None, "", "low", "mid", "high"):
        tier = None
    brand = request.args.get("brand", type=str) or None
    q = request.args.get("q", type=str) or None
    in_stock_only = request.args.get("in_stock_only", "false").lower() in ("1", "true", "yes")
    sort = request.args.get("sort", "name", type=str) or "name"
    if sort not in ("name", "price_asc", "price_desc", "rating", "deals"):
        sort = "name"

    result = search_products(
        db_path,
        product_type=product_type,
        price_min=price_min,
        price_max=price_max,
        tier=tier if tier else None,
        brand=brand,
        q=q,
        in_stock_only=in_stock_only,
        sort=sort,
        page=page,
        per_page=per_page,
    )

    return jsonify(
        {
            "page": result.page,
            "per_page": result.per_page,
            "total": result.total,
            "total_pages": result.total_pages,
            "products": [row_to_api_summary(r) for r in result.items],
        }
    )


@api_bp.get("/products/<path:identifier>")
def api_product_one(identifier: str):
    db_path = _db_or_503()
    row = fetch_product_by_id(db_path, identifier)
    if not row:
        row = fetch_product_by_slug(db_path, identifier)
    if not row:
        abort(404)
    return jsonify(row_to_api_detail(row))


@api_bp.post("/chat")
def api_chat():
    """LangGraph + OpenAI ReAct agent; tools read the SQLite catalog."""
    _db_or_503()

    if current_app.extensions.get("shopping_agent") is None:
        return jsonify(
            {
                "error": "Assistant is not configured. Set the OPENAI_API_KEY environment variable and restart the app.",
            }
        ), 503

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    if len(message) > 8000:
        return jsonify({"error": "message is too long (max 8000 characters)"}), 400

    thread_id = (data.get("thread_id") or "").strip() or str(uuid.uuid4())

    try:
        from agentic_commerce.chat_agent import invoke_agent

        out = invoke_agent(current_app, thread_id=thread_id, user_message=message)
    except RuntimeError as e:
        if str(e) == "assistant_disabled":
            return jsonify({"error": "Assistant is disabled."}), 503
        raise
    except Exception as e:
        current_app.logger.exception("chat invoke failed")
        return jsonify(
            {
                "error": "The assistant request failed. Check logs and API credentials.",
                "detail": str(e),
            }
        ), 502

    return jsonify(
        {
            "thread_id": thread_id,
            "reply": out["reply"],
            "products": out["products"],
        }
    )
