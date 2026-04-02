"""Shared SQLite schema DDL for the products catalog."""

PRODUCTS_TABLE = "products"

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {PRODUCTS_TABLE} (
    id TEXT PRIMARY KEY,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    product_type TEXT NOT NULL,
    tier TEXT NOT NULL,
    currency TEXT NOT NULL,
    price INTEGER NOT NULL,
    compare_at_price INTEGER,
    stock_quantity INTEGER NOT NULL,
    availability_status TEXT NOT NULL,
    rating_average REAL NOT NULL,
    review_count INTEGER NOT NULL,
    short_description TEXT NOT NULL,
    description TEXT NOT NULL,
    key_features_json TEXT NOT NULL,
    specifications_json TEXT NOT NULL,
    whats_in_box_json TEXT NOT NULL,
    attributes_json TEXT NOT NULL,
    thumbnail TEXT NOT NULL,
    images_json TEXT NOT NULL,
    image_attribution TEXT,
    is_duplicate_listing INTEGER NOT NULL DEFAULT 0,
    duplicate_of_id TEXT,
    loaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_products_product_type ON {PRODUCTS_TABLE}(product_type);
CREATE INDEX IF NOT EXISTS idx_products_tier ON {PRODUCTS_TABLE}(tier);
CREATE INDEX IF NOT EXISTS idx_products_brand ON {PRODUCTS_TABLE}(brand);
CREATE INDEX IF NOT EXISTS idx_products_price ON {PRODUCTS_TABLE}(price);
CREATE INDEX IF NOT EXISTS idx_products_availability ON {PRODUCTS_TABLE}(availability_status);
CREATE INDEX IF NOT EXISTS idx_products_sku ON {PRODUCTS_TABLE}(sku);
CREATE INDEX IF NOT EXISTS idx_products_slug ON {PRODUCTS_TABLE}(slug);
"""

DROP_SQL = f"DROP TABLE IF EXISTS {PRODUCTS_TABLE};"
