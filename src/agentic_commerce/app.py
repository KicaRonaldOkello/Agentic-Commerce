from __future__ import annotations

from pathlib import Path

from flask import Flask, url_for

from agentic_commerce.api import api_bp
from agentic_commerce.chat_agent import init_shopping_agent
from agentic_commerce.config import Config
from agentic_commerce.routes import bp as catalog_bp


def create_app(config_class: type = Config) -> Flask:
    pkg_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(pkg_dir / "templates"),
        static_folder=str(pkg_dir / "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)
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
