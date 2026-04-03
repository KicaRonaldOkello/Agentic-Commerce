"""Vercel WSGI entry — matches official Flask template (``vercel.json`` → ``/api/index``)."""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agentic_commerce.vercel_entry import app

__all__ = ["app"]
