"""CLI entry: `serve-catalog` or `python -m agentic_commerce`."""

from __future__ import annotations

import os

from agentic_commerce.app import create_app


def main() -> None:
    app = create_app()
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=True, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
