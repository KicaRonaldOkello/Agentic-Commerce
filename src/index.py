"""Vercel file-based Flask entry (``src/index.py``).

Vercel imports this file without always running ``pip install -e .``, so the
``agentic_commerce`` package is not on ``sys.path`` by default. Put ``src/`` on
the path first, then import the WSGI ``app``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_src_root = Path(__file__).resolve().parent
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from agentic_commerce.vercel_entry import app

__all__ = ["app"]
