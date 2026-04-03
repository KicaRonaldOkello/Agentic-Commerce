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

### Browse, filters, and best deals

- **Products** (`/products`): category, tier, min/max price (UGX), brand substring, search on name/description, sort (name, price, rating, **best deal order**), per-page size, optional **in stock only**.
- **Best deals** (`/deals`): same filters where relevant; always **in stock** and sorted by the [deal policy](docs/DEAL_POLICY.md) (discount %, then rating, then price).
- **Deal policy (plain text)** (`/deal-policy`): serves `docs/DEAL_POLICY.md`.

### JSON API (Phase 0 tools)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/products` | Paginated list; query params mirror the browse filters (`category`, `price_min`, `price_max`, `tier`, `brand`, `q`, `sort`, `page`, `per_page`, `in_stock_only`). |
| GET | `/api/products/<id or slug>` | One product; tries `id` first, then `slug`. |
| POST | `/api/chat` | Assistant: JSON `{ "message": "...", "thread_id": "optional-uuid" }` → `{ "thread_id", "reply", "products" }`. Requires `OPENAI_API_KEY`. |

### Shopping assistant (LangGraph + OpenAI)

1. Set **`OPENAI_API_KEY`** in the environment and restart the server.
2. Open **`/assistant`** in the browser (also linked from the header).
3. Optional: **`OPENAI_MODEL`** (default `gpt-4o-mini`), **`OPENAI_BASE_URL`** (e.g. later for OpenRouter: `https://openrouter.ai/api/v1`).
4. **Semantic discovery (Phase 2):** after loading SQLite, build the Chroma index once: **`uv run python scripts/embed_catalog_chroma.py`** (or `uv run poe embed-chroma`). Uses the same **`OPENAI_API_KEY`** and writes under **`data/chroma_db/`** (see **`CHROMA_PATH`** / **`OPENAI_EMBEDDING_MODEL`** in `config.py`). Without this, the **`discover_catalog`** tool returns an error and the model should fall back to **`search_catalog`**.

The assistant uses a **Phase 3 LangGraph** parent graph (`shopping_phase3_graph.py`): a **router** sends each turn to **clarify**, **browse**, **deals**, or **compare**; each branch runs a focused **`create_react_agent`** subgraph with a subset of tools (`chat_tools.py`: `BROWSE_TOOLS`, `DEALS_TOOLS`, `COMPARE_TOOLS`). An **evaluator** step in `POST /api/chat` blocks non-shopping requests before the graph runs. Conversation memory uses **`thread_id`** (`MemorySaver`; stored in `localStorage` on `/assistant`).

## Roadmap (Phases 2+)

Further work (complements, evals, richer state): **[docs/SHOPPING_ASSISTANT_ROADMAP.md](docs/SHOPPING_ASSISTANT_ROADMAP.md)**.

## Project layout (short)

| Path | Role |
|------|------|
| `data/products.jsonl` | Source catalog (JSON Lines) |
| `data/catalog.sqlite` | SQLite DB used at runtime |
| `scripts/load_products_sqlite.py` | Create schema + load JSONL (`--recreate` after schema changes, e.g. `screen_diagonal_inches`) |
| `scripts/embed_catalog_chroma.py` | Phase 2: embed catalog into local Chroma (`data/chroma_db/`) |
| `scripts/sqlite_products_schema.py` | Table DDL shared by loaders |
| `src/agentic_commerce/` | Flask app, catalog + API + assistant (`chat_agent.py`, `chat_tools.py`) |
| `docs/SHOPPING_ASSISTANT_ROADMAP.md` | Phased plan for the shopping chatbot |
| `docs/DEAL_POLICY.md` | How “best deals” are ranked in SQL |
