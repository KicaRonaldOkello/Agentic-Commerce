#!/usr/bin/env python3
"""
Create the SQLite catalog database (if needed) and load rows from data/products.jsonl.

Usage:
  python3 scripts/load_products_sqlite.py
  python3 scripts/load_products_sqlite.py --db ./data/my_catalog.sqlite --jsonl ./data/products.jsonl
  python3 scripts/load_products_sqlite.py --recreate   # DROP TABLE + reload (destructive)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from sqlite_products_schema import DROP_SQL, PRODUCTS_TABLE, SCHEMA_SQL

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "catalog.sqlite"
DEFAULT_JSONL = ROOT / "data" / "products.jsonl"

INSERT_SQL = f"""
INSERT INTO {PRODUCTS_TABLE} (
    id, sku, name, slug, brand, category, product_type, tier, currency,
    price, compare_at_price, stock_quantity, availability_status,
    rating_average, review_count, short_description, description,
    key_features_json, specifications_json, whats_in_box_json, attributes_json,
    thumbnail, images_json, image_attribution,
    is_duplicate_listing, duplicate_of_id, screen_diagonal_inches
) VALUES (
    ?, ?, ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?,
    ?, ?, ?
)
"""


def _screen_diagonal_inches(obj: dict) -> float | None:
    attrs = obj.get("attributes")
    if not isinstance(attrs, dict):
        return None
    raw = attrs.get("screenInches")
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v


def row_from_json(obj: dict) -> tuple:
    return (
        obj["id"],
        obj["sku"],
        obj["name"],
        obj["slug"],
        obj["brand"],
        obj["category"],
        obj["productType"],
        obj["tier"],
        obj["currency"],
        int(obj["price"]),
        int(obj["compareAtPrice"]) if obj.get("compareAtPrice") is not None else None,
        int(obj["stockQuantity"]),
        obj["availabilityStatus"],
        float(obj["ratingAverage"]),
        int(obj["reviewCount"]),
        obj["shortDescription"],
        obj["description"],
        json.dumps(obj["keyFeatures"], ensure_ascii=False),
        json.dumps(obj["specifications"], ensure_ascii=False),
        json.dumps(obj["whatsInTheBox"], ensure_ascii=False),
        json.dumps(obj["attributes"], ensure_ascii=False),
        obj["thumbnail"],
        json.dumps(obj["images"], ensure_ascii=False),
        obj.get("imageAttribution"),
        1 if obj.get("isDuplicateListing") else 0,
        obj.get("duplicateOfId"),
        _screen_diagonal_inches(obj),
    )


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load products.jsonl into SQLite.")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite database file (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=DEFAULT_JSONL,
        help=f"Source JSONL (default: {DEFAULT_JSONL})",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop the products table before creating and loading (destructive).",
    )
    parser.add_argument(
        "--single-file",
        action="store_true",
        help=(
            "After load, switch journal mode to DELETE and checkpoint WAL so the DB "
            "is a single .sqlite file (better for read-only / serverless deploys)."
        ),
    )
    args = parser.parse_args()

    if not args.jsonl.is_file():
        print(f"Error: JSONL not found: {args.jsonl}", file=sys.stderr)
        return 1

    args.db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")

        if args.recreate:
            conn.executescript(DROP_SQL)
            conn.commit()

        apply_schema(conn)
        conn.commit()

        rows: list[tuple] = []
        with open(args.jsonl, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(row_from_json(json.loads(line)))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    print(f"Error: line {line_no}: {e}", file=sys.stderr)
                    return 1

        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {PRODUCTS_TABLE}")
        existing = cur.fetchone()[0]
        if existing and not args.recreate:
            print(
                f"Error: {PRODUCTS_TABLE} already has {existing} row(s). "
                "Use --recreate to drop and reload, or run clear_products_sqlite.py first.",
                file=sys.stderr,
            )
            return 1

        conn.executemany(INSERT_SQL, rows)
        conn.commit()

        cur.execute(f"SELECT COUNT(*) FROM {PRODUCTS_TABLE}")
        total = cur.fetchone()[0]
        print(f"Loaded {len(rows)} rows into {args.db} (table {PRODUCTS_TABLE}, total {total}).")

        if args.single_file:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.execute("PRAGMA journal_mode=DELETE;")
            conn.commit()
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
