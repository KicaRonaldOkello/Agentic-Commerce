"""Chroma-backed semantic discovery (Phase 2). SQLite remains source of truth for prices/stock."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings

from agentic_commerce.db import CATALOG_PRODUCT_TYPES, get_connection, screen_size_bucket


def _specifications_excerpt(spec_json: str | None, max_chars: int = 3500) -> str:
    if not isinstance(spec_json, str) or not spec_json.strip():
        return ""
    try:
        spec = json.loads(spec_json)
    except json.JSONDecodeError:
        return ""
    if isinstance(spec, dict):
        lines = [f"{k}: {v}" for k, v in spec.items()]
        text = "; ".join(lines)
        return text[:max_chars] + ("…" if len(text) > max_chars else "")
    return str(spec)[:max_chars]


def build_product_chunk_text(row: dict[str, Any]) -> str:
    """Single document per product for embedding."""
    parts: list[str] = [
        f"Name: {row['name']}",
        f"Brand: {row['brand']}",
        f"Product type: {row['product_type']}",
        f"Tier: {row['tier']}",
        f"Short description: {row['short_description']}",
        row.get("description") or "",
    ]
    sd = row.get("screen_diagonal_inches")
    if sd is not None:
        try:
            parts.insert(4, f"Diagonal screen size (inches): {float(sd)}")
        except (TypeError, ValueError):
            pass
    raw_kf = row.get("key_features_json")
    if isinstance(raw_kf, str) and raw_kf.strip():
        try:
            kf = json.loads(raw_kf)
        except json.JSONDecodeError:
            kf = None
        if isinstance(kf, list) and kf:
            feats = "; ".join(str(x) for x in kf[:25])
            parts.append(f"Key features: {feats}")
        elif isinstance(kf, dict):
            parts.append(f"Key features: {json.dumps(kf, ensure_ascii=False)[:2000]}")
    spec_ex = _specifications_excerpt(row.get("specifications_json"))
    if spec_ex:
        parts.append(f"Specifications: {spec_ex}")
    return "\n\n".join(p for p in parts if p)


def _iter_embedding_source_rows(db_path: Path) -> list[dict[str, Any]]:
    sql = """
        SELECT id, name, brand, product_type, tier, short_description, description,
               key_features_json, specifications_json, price, availability_status,
               screen_diagonal_inches
        FROM products
    """
    with get_connection(db_path) as conn:
        cur = conn.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def get_chroma_collection(
    persist_directory: Path,
    collection_name: str,
) -> chromadb.Collection:
    client = chromadb.PersistentClient(
        path=str(persist_directory),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def embed_and_upsert_catalog(
    *,
    db_path: Path,
    chroma_path: Path,
    collection_name: str,
    api_key: str,
    embedding_model: str,
    openai_api_base: str | None,
    batch_size: int = 64,
    reset: bool = False,
) -> int:
    """Embed all products into Chroma. Returns number of vectors written."""
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(chroma_path),
        settings=Settings(anonymized_telemetry=False),
    )
    if reset:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    rows = _iter_embedding_source_rows(db_path)
    if not rows:
        return 0

    emb_kwargs: dict[str, Any] = {"model": embedding_model, "api_key": api_key}
    if openai_api_base:
        emb_kwargs["openai_api_base"] = openai_api_base
    embeddings = OpenAIEmbeddings(**emb_kwargs)

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        ids = [r["id"] for r in batch]
        documents = [build_product_chunk_text(r) for r in batch]
        metadatas: list[dict[str, Any]] = []
        for r in batch:
            md: dict[str, Any] = {
                "product_type": r["product_type"],
                "price": int(r["price"]),
                "tier": r["tier"],
                "availability_status": r["availability_status"],
            }
            sd = r.get("screen_diagonal_inches")
            if sd is not None:
                try:
                    md["screen_bucket"] = int(screen_size_bucket(float(sd)))
                except (TypeError, ValueError):
                    pass
            metadatas.append(md)
        vectors = embeddings.embed_documents(documents)
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=vectors,
        )
        total += len(ids)
    return total


def chroma_collection_count(chroma_path: Path, collection_name: str) -> int:
    if not chroma_path.is_dir():
        return 0
    try:
        client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )
        coll = client.get_collection(collection_name)
        return int(coll.count())
    except Exception:
        return 0


def semantic_search_product_ids(
    *,
    chroma_path: Path,
    collection_name: str,
    query: str,
    api_key: str,
    embedding_model: str,
    openai_api_base: str | None,
    category: str,
    in_stock_only: bool,
    screen_inches: float | int | None,
    top_k: int,
) -> list[str]:
    """Return product ids ranked by similarity (Chroma only; SQL filters applied later)."""
    client = chromadb.PersistentClient(
        path=str(chroma_path),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection(collection_name)

    emb_kwargs: dict[str, Any] = {"model": embedding_model, "api_key": api_key}
    if openai_api_base:
        emb_kwargs["openai_api_base"] = openai_api_base
    embeddings = OpenAIEmbeddings(**emb_kwargs)
    qv = embeddings.embed_query(query.strip())

    where: dict[str, Any] | None = None
    clauses: list[dict[str, Any]] = []
    if category in CATALOG_PRODUCT_TYPES:
        clauses.append({"product_type": {"$eq": category}})
    if in_stock_only:
        clauses.append({"availability_status": {"$eq": "in_stock"}})
    if screen_inches is not None:
        clauses.append(
            {"screen_bucket": {"$eq": int(screen_size_bucket(float(screen_inches)))}}
        )
    if len(clauses) == 1:
        where = clauses[0]
    elif len(clauses) > 1:
        where = {"$and": clauses}

    res = collection.query(
        query_embeddings=[qv],
        n_results=max(1, min(int(top_k), 200)),
        where=where,
        include=["distances"],
    )
    ids = res.get("ids") or []
    if not ids or not ids[0]:
        return []
    return list(ids[0])
