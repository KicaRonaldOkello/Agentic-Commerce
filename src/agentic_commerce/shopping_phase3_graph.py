"""Phase 3 LangGraph: router → clarify | browse | deals | compare (evaluator stays in API, pre-graph)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from flask import has_request_context
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from typing_extensions import Required, TypedDict

from agentic_commerce.agent_prompts import (
    BROWSE_SYSTEM_PROMPT,
    COMPARE_SYSTEM_PROMPT,
    DEALS_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
)
from agentic_commerce.chat_tools import BROWSE_TOOLS, COMPARE_TOOLS, DEALS_TOOLS


class RouteDecision(BaseModel):
    route: Literal["browse", "deals", "compare", "clarify"]
    reason: str = Field(description="One-line rationale for logs.")
    clarify_hint: str | None = Field(
        None,
        description="If route is clarify, what the follow-up question should focus on.",
    )


class ShoppingState(TypedDict, total=False):
    messages: Required[Annotated[list[BaseMessage], add_messages]]
    route: str
    router_reason: str
    clarify_hint: str


def _msg_text(m: BaseMessage) -> str:
    c = m.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(c)


def _last_user_and_prior_ai(messages: list[BaseMessage]) -> tuple[str, str]:
    """Latest human text and the most recent plain AI reply before it (for routing follow-ups)."""
    last_user = ""
    idx_user = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_user = _msg_text(messages[i]).strip()
            idx_user = i
            break
    prior_ai = ""
    if idx_user > 0:
        for j in range(idx_user - 1, -1, -1):
            m = messages[j]
            if isinstance(m, AIMessage) and not (getattr(m, "tool_calls", None) or []):
                t = _msg_text(m).strip()
                if t:
                    prior_ai = t[:800]
                    break
    return last_user, prior_ai


def _recent_transcript_for_router(
    messages: list[BaseMessage], *, max_messages: int = 18, max_line_chars: int = 700
) -> str:
    """Multi-turn excerpt so routing does not depend only on the last user line."""
    lines: list[str] = []
    for m in messages[-max_messages:]:
        if isinstance(m, HumanMessage):
            t = _msg_text(m).strip()[:max_line_chars]
            if t:
                lines.append(f"User: {t}")
        elif isinstance(m, AIMessage) and not (getattr(m, "tool_calls", None) or []):
            t = _msg_text(m).strip()[:max_line_chars]
            if t:
                lines.append(f"Assistant: {t}")
    return "\n".join(lines)


def build_shopping_phase3_graph(
    *,
    model: str,
    api_key: str,
    base_url: str | None,
    checkpointer: Any,
) -> Any:
    """Compile parent graph with checkpointer; specialist ReAct subgraphs are stateless."""
    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "temperature": 0.2,
    }
    if base_url:
        kwargs["base_url"] = base_url

    llm = ChatOpenAI(**kwargs)
    router_llm = llm.with_structured_output(RouteDecision)

    browse_react = create_react_agent(
        llm,
        BROWSE_TOOLS,
        prompt=BROWSE_SYSTEM_PROMPT,
        checkpointer=None,
    )
    deals_react = create_react_agent(
        llm,
        DEALS_TOOLS,
        prompt=DEALS_SYSTEM_PROMPT,
        checkpointer=None,
    )
    compare_react = create_react_agent(
        llm,
        COMPARE_TOOLS,
        prompt=COMPARE_SYSTEM_PROMPT,
        checkpointer=None,
    )

    clarify_kw: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "temperature": 0.3,
        "max_tokens": 200,
    }
    if base_url:
        clarify_kw["base_url"] = base_url
    clarify_llm = ChatOpenAI(**clarify_kw)

    def _log(line: str) -> None:
        if has_request_context():
            try:
                from flask import current_app

                current_app.logger.info("phase3 %s", line)
            except Exception:
                pass

    def router_node(state: ShoppingState) -> dict[str, Any]:
        messages = state["messages"]
        user_txt, _prior_ai = _last_user_and_prior_ai(messages)
        transcript = _recent_transcript_for_router(messages)
        ctx_parts = [f"Recent conversation:\n{transcript}" if transcript else ""]
        ctx_parts.append(f"Latest user message:\n{user_txt}")
        human_block = "\n\n".join(p for p in ctx_parts if p)
        decision: RouteDecision = router_llm.invoke(
            [
                SystemMessage(content=ROUTER_SYSTEM_PROMPT),
                HumanMessage(content=human_block),
            ]
        )
        trace = f"router:{decision.route}:{decision.reason[:160]}"
        _log(trace)
        return {
            "route": decision.route,
            "router_reason": decision.reason,
            "clarify_hint": (decision.clarify_hint or "").strip(),
        }

    def clarify_node(state: ShoppingState) -> dict[str, Any]:
        hint = (state.get("clarify_hint") or "").strip() or (
            "Ask what product category they want (e.g. phone, TV) and roughly their budget in UGX."
        )
        sys = (
            "You are a shopping assistant. The user's request was too vague. "
            f"Instruction: {hint}\n"
            "Reply with exactly ONE short, friendly question (no bullet list, no preamble)."
        )
        ai = clarify_llm.invoke(
            [SystemMessage(content=sys), HumanMessage(content="Write the question only.")]
        )
        if not isinstance(ai, AIMessage):
            ai = AIMessage(content=str(ai))
        _log("node:clarify")
        return {"messages": [ai]}

    def _react_delta(subgraph: Any, state: ShoppingState, tag: str) -> dict[str, Any]:
        msgs = list(state["messages"])
        n0 = len(msgs)
        out = subgraph.invoke({"messages": msgs})
        full = out.get("messages") or []
        delta = full[n0:] if len(full) >= n0 else full
        _log(f"node:{tag} delta_messages={len(delta)}")
        return {"messages": delta}

    def browse_node(state: ShoppingState) -> dict[str, Any]:
        return _react_delta(browse_react, state, "browse")

    def deals_node(state: ShoppingState) -> dict[str, Any]:
        return _react_delta(deals_react, state, "deals")

    def compare_node(state: ShoppingState) -> dict[str, Any]:
        return _react_delta(compare_react, state, "compare")

    def route_edge(state: ShoppingState) -> Literal["browse", "deals", "compare", "clarify"]:
        r = (state.get("route") or "browse").lower()
        if r in ("browse", "deals", "compare", "clarify"):
            return r  # type: ignore[return-value]
        return "browse"

    g = StateGraph(ShoppingState)
    g.add_node("router", router_node)
    g.add_node("clarify", clarify_node)
    g.add_node("browse", browse_node)
    g.add_node("deals", deals_node)
    g.add_node("compare", compare_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        route_edge,
        {
            "clarify": "clarify",
            "browse": "browse",
            "deals": "deals",
            "compare": "compare",
        },
    )
    g.add_edge("clarify", END)
    g.add_edge("browse", END)
    g.add_edge("deals", END)
    g.add_edge("compare", END)

    return g.compile(checkpointer=checkpointer)


_phase3_cache: dict[str, Any] = {}


def get_phase3_graph(
    *,
    model: str,
    api_key: str,
    base_url: str | None,
    checkpointer: Any,
) -> Any:
    key = f"p3|{model}|{base_url or ''}|{id(checkpointer)}"
    if key not in _phase3_cache:
        _phase3_cache[key] = build_shopping_phase3_graph(
            model=model,
            api_key=api_key,
            base_url=base_url,
            checkpointer=checkpointer,
        )
    return _phase3_cache[key]
