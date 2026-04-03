"""WSGI ``app`` for Vercel (see ``[project.scripts] app`` in pyproject.toml)."""

from agentic_commerce.app import create_app

app = create_app()
