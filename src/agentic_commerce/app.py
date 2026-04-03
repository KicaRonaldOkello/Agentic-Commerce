from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, url_for

from agentic_commerce.api import api_bp
from agentic_commerce.chat_agent import init_shopping_agent
from agentic_commerce.config import Config
from agentic_commerce.routes import bp as catalog_bp


def _apply_runtime_env_overrides(app: Flask) -> None:
    """Prefer live ``os.environ`` for secrets/paths (Vercel injects at cold start, not via .env)."""
    str_keys = (
        "SECRET_KEY",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_BASE_URL",
        "OPENAI_EMBEDDING_MODEL",
        "OPENAI_EVALUATOR_MODEL",
        "CHROMA_COLLECTION_NAME",
    )
    for key in str_keys:
        raw = os.environ.get(key)
        if raw is not None and str(raw).strip() != "":
            app.config[key] = raw.strip()
    if raw := os.environ.get("CATALOG_DATABASE", "").strip():
        app.config["DATABASE_PATH"] = Path(raw).resolve()
    if raw := os.environ.get("CHROMA_PATH", "").strip():
        app.config["CHROMA_PATH"] = Path(raw).resolve()


def create_app(config_class: type = Config) -> Flask:
    pkg_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(pkg_dir / "templates"),
        static_folder=str(pkg_dir / "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)
    _apply_runtime_env_overrides(app)
    init_shopping_agent(app)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(api_bp)

    @app.template_global()
    def catalog_page_url(endpoint: str, page: int, nav_kwargs: dict | None = None) -> str:
        args = dict(nav_kwargs or {})
        args["page"] = page
        return url_for(endpoint, **args)

    @app.template_filter("ugx")
    def format_ugx(value: int | None) -> str:
        if value is None:
            return "—"
        return f"UGX {int(value):,}"

    return app
