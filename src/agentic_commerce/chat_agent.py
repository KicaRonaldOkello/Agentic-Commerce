"""LangGraph ReAct agent for Phase 1 shopping assistant (OpenAI; OpenRouter-ready via base URL)."""

from __future__ import annotations

import json
import os
from typing import Any

from flask import Flask
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from agentic_commerce.chat_tools import SHOPPING_TOOLS

SYSTEM_PROMPT = """You are a shopping assistant for Agentic Commerce (Uganda-style demo catalog, prices in UGX).

Rules:
- For any product lists, prices, discounts, stock, or specs, you MUST call the provided tools. Never invent SKUs, prices, or product names.
- After tools return JSON, explain results in clear, friendly language. Mention product names and UGX prices from the tool output.
- If search returns no products, say so and suggest broadening filters (e.g. raise budget or try another category).
- For "best deal" or "on sale" requests, prefer the top_deals tool or search_catalog with sort=deals.
- Keep answers concise unless the user asks for detail. You may suggest 2–3 follow-up questions.
- Listed products also appear as clickable cards below your message; summarize in prose without pasting full tables.

Currency: always UGX as shown in tool data."""

_checkpointer = MemorySaver()
_agent_cache: dict[str, Any] = {}


def _format_ai_content(msg: AIMessage) -> str:
    c = msg.content
    if isinstance(c, str):
        return c.strip() or ""
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts).strip()
    return str(c).strip()


def extract_reply_text(messages: list[BaseMessage]) -> str:
    """Last assistant text message without pending tool calls."""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            if getattr(m, "tool_calls", None):
                continue
            text = _format_ai_content(m)
            if text:
                return text
    return "I could not generate a reply. Please try again or rephrase your question."


def _tool_message_body(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _card_payload_from_row(p: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(p, dict):
        return None
    pid, slug = p.get("id"), p.get("slug")
    if not pid or not slug:
        return None
    name = p.get("name")
    if not name:
        return None
    return {
        "id": str(pid),
        "slug": str(slug),
        "name": str(name),
        "brand": str(p.get("brand") or ""),
        "short_description": str(p.get("short_description") or ""),
        "price": p.get("price"),
        "compare_at_price": p.get("compare_at_price"),
        "tier": str(p.get("tier") or ""),
        "thumbnail": str(p.get("thumbnail") or ""),
        "availability_status": p.get("availability_status"),
    }


def extract_products_from_last_turn(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    """Collect catalog products returned by tools since the latest user message (deduped by id)."""
    last_human = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human = i
            break
    if last_human < 0:
        return []

    by_id: dict[str, dict[str, Any]] = {}
    for m in messages[last_human + 1 :]:
        if not isinstance(m, ToolMessage):
            continue
        raw = _tool_message_body(m.content).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or data.get("error"):
            continue

        products = data.get("products")
        if isinstance(products, list):
            for p in products:
                row = _card_payload_from_row(p)
                if row:
                    by_id[row["id"]] = row
            continue

        row = _card_payload_from_row(data)
        if row:
            by_id[row["id"]] = row

    return list(by_id.values())


def build_agent_graph(*, model: str, api_key: str, base_url: str | None) -> Any:
    """Create a compiled LangGraph ReAct agent (cached per model+base_url)."""
    cache_key = f"{model}|{base_url or ''}"
    if cache_key in _agent_cache:
        return _agent_cache[cache_key]

    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "temperature": 0.2,
    }
    if base_url:
        kwargs["base_url"] = base_url

    llm = ChatOpenAI(**kwargs)
    graph = create_react_agent(
        llm,
        SHOPPING_TOOLS,
        prompt=SYSTEM_PROMPT,
        checkpointer=_checkpointer,
    )
    _agent_cache[cache_key] = graph
    return graph


def init_shopping_agent(app: Flask) -> None:
    """Attach compiled graph to app.extensions or disable assistant."""
    # Reduce surprise LangSmith prompts in local dev
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

    key = (app.config.get("OPENAI_API_KEY") or "").strip()
    if not key:
        app.extensions["shopping_agent"] = None
        return

    graph = build_agent_graph(
        model=app.config["OPENAI_MODEL"],
        api_key=key,
        base_url=(app.config.get("OPENAI_BASE_URL") or "").strip() or None,
    )
    app.extensions["shopping_agent"] = graph


def invoke_agent(
    app: Flask, *, thread_id: str, user_message: str
) -> dict[str, Any]:
    """Run one user turn; must be called inside Flask request context (for tools).

    Returns ``reply`` (assistant text) and ``products`` (card-shaped dicts with slug for links).
    """
    agent = app.extensions.get("shopping_agent")
    if agent is None:
        raise RuntimeError("assistant_disabled")

    from langchain_core.messages import HumanMessage

    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config,
    )
    msgs = result["messages"]
    return {
        "reply": extract_reply_text(msgs),
        "products": extract_products_from_last_turn(msgs),
    }
