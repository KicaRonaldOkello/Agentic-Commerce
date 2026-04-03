"""Shopping assistant: Phase 3 multi-node LangGraph + product extraction (Phases 1–2 tools)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from flask import Flask
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from agentic_commerce.agent_prompts import BROWSE_SYSTEM_PROMPT
from agentic_commerce.evaluator_agent import build_evaluator_runnable
from agentic_commerce.shopping_phase3_graph import get_phase3_graph

# Backward-compatible name for docs / imports
SYSTEM_PROMPT = BROWSE_SYSTEM_PROMPT

_checkpointer = MemorySaver()

# User chose an item from a prior list (ordinal / colloquial)—used to append complement CTA deterministically.
_PICK_FROM_LIST_RE = re.compile(
    r"(?i)\b("
    r"the\s+(first|second|third|fourth|fifth|last)\b|"
    r"\b(1st|2nd|3rd|4th|5th)\b|"
    r"\btake\s+the\b|"
    r"i'?ll\s+take\b|"
    r"i\s+think\s+i\s+will\s+take\b|"
    r"going\s+with\s+the\b|"
    r"\blast\s+one\b|"
    r"\bfirst\s+one\b|"
    r"\blast\s+item\b|"
    r"\bfirst\s+item\b|"
    r"\bthis\s+one\b|"
    r"\bthat\s+one\b"
    r")"
)

_COMPLEMENT_CTA_PHRASES = (
    "say yes",
    "say **yes**",
    "list them with ugx prices",
)

# Shown in the assistant UI below the chosen product card (plain text; no markdown).
COMPLEMENT_INVITE_UI_TEXT = (
    "If you’d like, I can suggest complementary items from our catalog that pair with "
    "this product—say yes and I’ll list them with UGX prices."
)


def _last_human_index(messages: list[BaseMessage]) -> int:
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return i
    return -1


def _effective_tool_name(m: ToolMessage) -> str | None:
    """LangGraph / LangChain usually set ``name``; fall back to JSON shape if missing."""
    n = (getattr(m, "name", None) or "").strip()
    if n:
        return n
    raw = _tool_message_body(m.content).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("source_product") and isinstance(data.get("products"), list):
        return "get_complements"
    if isinstance(data.get("products"), list) and data.get("total_matching") is not None:
        return "search_catalog"
    if isinstance(data.get("products"), list) and data.get("method") == "semantic_search":
        return "discover_catalog"
    if data.get("note") and "deal" in str(data.get("note", "")).lower() and isinstance(
        data.get("products"), list
    ):
        return "top_deals"
    # Single-product detail payload (get_product_details)
    if data.get("id") and data.get("slug") and not data.get("error"):
        if data.get("description") is not None or data.get("specifications") is not None:
            return "get_product_details"
    return None


def _tool_names_after_human(messages: list[BaseMessage], last_human_idx: int) -> list[str]:
    if last_human_idx < 0:
        return []
    out: list[str] = []
    for m in messages[last_human_idx + 1 :]:
        if isinstance(m, ToolMessage):
            eff = _effective_tool_name(m)
            if eff:
                out.append(eff)
    return out


def _user_signals_list_pick(user_text: str) -> bool:
    t = (user_text or "").strip()
    if not t:
        return False
    if _PICK_FROM_LIST_RE.search(t):
        return True
    if re.search(r"(?i)\b(which|pick|choose|selected)\b.+\b(list|options|above)\b", t):
        return True
    return False


def _should_append_complement_cta(
    messages: list[BaseMessage], *, user_message: str, reply: str
) -> bool:
    """After details for a list pick, ensure the user always sees an explicit path to get_complements."""
    if not _user_signals_list_pick(user_message):
        return False
    rlow = reply.lower()
    if any(p.lower() in rlow for p in _COMPLEMENT_CTA_PHRASES):
        return False
    idx = _last_human_index(messages)
    if idx < 0:
        return False
    names = _tool_names_after_human(messages, idx)
    if "get_product_details" not in names:
        return False
    if "get_complements" in names:
        return False
    # Confirm a successful product-detail tool payload in this turn.
    for m in messages[idx + 1 :]:
        if not isinstance(m, ToolMessage):
            continue
        eff = _effective_tool_name(m)
        if eff != "get_product_details":
            continue
        raw = _tool_message_body(m.content).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and not data.get("error") and data.get("id"):
            return True
    return False


def _anchor_product_id_from_detail_tools(
    messages: list[BaseMessage], last_human_idx: int
) -> str | None:
    """First successful get_product_details ``id`` in this turn (for UI placement)."""
    if last_human_idx < 0:
        return None
    for m in messages[last_human_idx + 1 :]:
        if not isinstance(m, ToolMessage):
            continue
        if _effective_tool_name(m) != "get_product_details":
            continue
        raw = _tool_message_body(m.content).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and not data.get("error") and data.get("id"):
            return str(data["id"])
    return None


def _reply_with_complement_cta(reply: str) -> str:
    suffix = (
        "\n\nIf you’d like, I can suggest complementary items from our catalog that pair with "
        "this product—**say yes** and I’ll list them with UGX prices."
    )
    return (reply.rstrip() + suffix).strip()


def _text_from_message(msg: BaseMessage) -> str:
    """Plain text for human/assistant messages (skip tool-call-only AI turns)."""
    if isinstance(msg, AIMessage):
        if getattr(msg, "tool_calls", None):
            return ""
        return _format_ai_content(msg)
    c = msg.content
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts).strip()
    return str(c).strip()


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


def format_conversation_tail_for_evaluator(
    messages: list[BaseMessage],
    *,
    max_messages: int = 16,
    max_line_chars: int = 900,
) -> str:
    """Compact transcript for the intent gate (human + plain AI only; no tool payloads)."""
    if not messages:
        return ""
    lines: list[str] = []
    for m in messages[-max_messages:]:
        if isinstance(m, HumanMessage):
            t = _text_from_message(m)[:max_line_chars]
            if t:
                lines.append(f"User: {t}")
        elif isinstance(m, AIMessage):
            t = _text_from_message(m)[:max_line_chars]
            if t:
                lines.append(f"Assistant: {t}")
    return "\n".join(lines)


def prior_conversation_for_evaluator(app: Flask, *, thread_id: str) -> str:
    """Load checkpointed thread history (before the current request) for shopping-intent classification."""
    agent = app.extensions.get("shopping_agent")
    if agent is None or not (thread_id or "").strip():
        return ""
    try:
        snap = agent.get_state({"configurable": {"thread_id": thread_id.strip()}})
        if snap is None:
            return ""
        vals = getattr(snap, "values", None) or {}
        msgs = vals.get("messages") or []
        if not isinstance(msgs, list):
            return ""
        return format_conversation_tail_for_evaluator(msgs)
    except Exception:
        app.logger.debug("prior_conversation_for_evaluator failed", exc_info=True)
        return ""


def init_shopping_agent(app: Flask) -> None:
    """Attach Phase 3 graph + intent evaluator to app.extensions."""
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

    key = (app.config.get("OPENAI_API_KEY") or "").strip()
    if not key:
        app.extensions["shopping_agent"] = None
        app.extensions["shopping_intent_evaluator"] = None
        return

    base_url = (app.config.get("OPENAI_BASE_URL") or "").strip() or None
    graph = get_phase3_graph(
        model=app.config["OPENAI_MODEL"],
        api_key=key,
        base_url=base_url,
        checkpointer=_checkpointer,
    )
    app.extensions["shopping_agent"] = graph

    eval_model = app.config.get("OPENAI_EVALUATOR_MODEL") or app.config["OPENAI_MODEL"]
    app.extensions["shopping_intent_evaluator"] = build_evaluator_runnable(
        model=eval_model,
        api_key=key,
        base_url=base_url,
    )


def invoke_agent(
    app: Flask, *, thread_id: str, user_message: str
) -> dict[str, Any]:
    """Run one user turn (router → specialist); must run inside Flask request context for tools.

    Returns ``reply``, ``products`` (card-shaped dicts), and optional ``complement_invite``
    ``{ "text", "product_id" }`` when the UI should show the pairing prompt under that card.
    """
    agent = app.extensions.get("shopping_agent")
    if agent is None:
        raise RuntimeError("assistant_disabled")

    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config,
    )
    msgs = result["messages"]
    reply = extract_reply_text(msgs)
    complement_invite: dict[str, str] | None = None
    if _should_append_complement_cta(msgs, user_message=user_message, reply=reply):
        hidx = _last_human_index(msgs)
        anchor_id = _anchor_product_id_from_detail_tools(msgs, hidx)
        if anchor_id:
            complement_invite = {
                "text": COMPLEMENT_INVITE_UI_TEXT,
                "product_id": anchor_id,
            }
        else:
            reply = _reply_with_complement_cta(reply)
    return {
        "reply": reply,
        "products": extract_products_from_last_turn(msgs),
        "complement_invite": complement_invite,
    }
