# Agentic Commerce

Demo storefront backed by a product catalog in SQLite. Data is authored as **JSON Lines** (`data/products.jsonl`), loaded into `data/catalog.sqlite`, and served by **Flask**.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or another way to install the package in editable mode

## Install

From the repository root:

```bash
uv sync
```

Or, with pip:

```bash
pip install -e .
```

Install dev tools (optional, for [Poe the Poet](https://poethepoet.natn.io/) tasks):

```bash
uv sync --group dev
```

## Adding catalog data

The app reads **only from SQLite**. You maintain the source of truth in **`data/products.jsonl`** (one JSON object per line), then load it into the database.

### 1. Generate sample data (optional)

To regenerate `data/products.jsonl` with ~2000 synthetic phone and TV listings:

```bash
uv run poe generate-products
```

Or without Poe:

```bash
python scripts/generate_products_jsonl.py
```

### 2. Edit or append rows manually

Each line must be a single JSON object. Field names use **camelCase** in JSON (the loader maps them into SQLite). Required shape matches what `scripts/load_products_sqlite.py` expects, including:

- **Identifiers:** `id`, `sku`, `name`, `slug` (unique), `brand`, `category`, `productType` (`phone` or `television` for storefront filters), `tier`, `currency`
- **Commerce:** `price` (integer), `compareAtPrice` (integer or `null`), `stockQuantity`, `availabilityStatus`
- **Social proof:** `ratingAverage`, `reviewCount`
- **Copy:** `shortDescription`, `description`
- **Structured:** `keyFeatures` (array), `specifications` (object), `whatsInTheBox` (array), `attributes` (object)
- **Media:** `thumbnail` (URL string), `images` (array of URLs), optional `imageAttribution`
- **Duplicates:** optional `isDuplicateListing`, `duplicateOfId`

Copy an existing line from `data/products.jsonl` and change `id`, `sku`, `slug`, and other fields to avoid collisions.

### 3. Load JSONL into SQLite

From the repository root:

```bash
uv run poe load-sqlite
```

Or:

```bash
python scripts/load_products_sqlite.py
```

Defaults:

- Database: `data/catalog.sqlite`
- Source file: `data/products.jsonl`

Custom paths:

```bash
python scripts/load_products_sqlite.py --db ./data/my_catalog.sqlite --jsonl ./data/products.jsonl
```

**First load only:** if the `products` table already has rows, the loader exits with an error unless you **replace** everything:

```bash
uv run poe load-sqlite-fresh
```

(equivalent to `python scripts/load_products_sqlite.py --recreate`)

To clear data without reloading:

```bash
uv run poe clear-sqlite          # DELETE all rows
uv run poe clear-sqlite-drop     # DROP table (next load recreates schema)
```

### Pointing the app at a different database

Set `CATALOG_DATABASE` to an absolute or relative path (resolved from the process working directory):

```bash
export CATALOG_DATABASE=/path/to/catalog.sqlite
```

If unset, the app uses `data/catalog.sqlite` under the project root (see `src/agentic_commerce/config.py`).

## Running the Flask app

From the repository root, with the package installed (e.g. after `uv sync`):

```bash
uv run flask --app agentic_commerce:create_app run --debug
```

With Poe:

```bash
uv run poe serve
```

Alternative entry points (same app factory, debug server on `127.0.0.1`):

```bash
uv run serve-catalog
# or
uv run python -m agentic_commerce
```

The dev server listens on port **5000** by default (`serve-catalog` / `python -m` honor the `PORT` environment variable).

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/) in a browser. For production, use a proper WSGI server and set a strong `SECRET_KEY`.

## Project layout (short)

| Path | Role |
|------|------|
| `data/products.jsonl` | Source catalog (JSON Lines) |
| `data/catalog.sqlite` | SQLite DB used at runtime |
| `scripts/load_products_sqlite.py` | Create schema + load JSONL |
| `scripts/sqlite_products_schema.py` | Table DDL shared by loaders |
| `src/agentic_commerce/` | Flask app (`create_app`), routes, templates |
