#!/usr/bin/env python3
"""
Clear product data from the SQLite catalog.

Usage:
  python3 scripts/clear_products_sqlite.py              # DELETE all rows (keeps table + indexes)
  python3 scripts/clear_products_sqlite.py --drop        # DROP TABLE (next load recreates schema)
  python3 scripts/clear_products_sqlite.py --vacuum    # reclaim space after DELETE
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from sqlite_products_schema import DROP_SQL, PRODUCTS_TABLE

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "catalog.sqlite"


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear products from SQLite.")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite database file (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="DROP the products table entirely (indexes go with it).",
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Run VACUUM after clearing (shrinks file; only useful after DELETE).",
    )
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"Error: database file not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (PRODUCTS_TABLE,),
        )
        if not cur.fetchone():
            print(f"No table {PRODUCTS_TABLE!r} in {args.db}; nothing to clear.")
            return 0

        if args.drop:
            conn.executescript(DROP_SQL)
            conn.commit()
            print(f"Dropped table {PRODUCTS_TABLE!r} in {args.db}.")
        else:
            cur.execute(f"SELECT COUNT(*) FROM {PRODUCTS_TABLE}")
            n = cur.fetchone()[0]
            cur.execute(f"DELETE FROM {PRODUCTS_TABLE}")
            conn.commit()
            print(f"Deleted {n} row(s) from {PRODUCTS_TABLE!r} in {args.db}.")

        if args.vacuum and not args.drop:
            conn.execute("VACUUM")
            conn.commit()
            print("VACUUM complete.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
