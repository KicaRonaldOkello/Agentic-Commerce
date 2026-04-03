"""Vercel file-based Flask entry (``src/index.py``); WSGI ``app`` lives in ``vercel_entry``."""

from agentic_commerce.vercel_entry import app

__all__ = ["app"]
