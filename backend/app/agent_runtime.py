from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from .tools import ALL_TOOLS, tools_by_name


@dataclass
class RunResult:
    text: str
    tool_calls: list[dict]
    messages: list[BaseMessage]


EventEmitter = Callable[[dict], Awaitable[None]]


async def run_agent(
    model: BaseChatModel,
    messages: list[BaseMessage],
    *,
    emit: Optional[EventEmitter] = None,
    use_tools: bool = True,
    max_iters: int = 4,
) -> RunResult:
    """Run a tool-using agent loop with streaming.

    Streams token chunks via `emit({"type":"token","delta":..., "agent":...})`
    and emits `tool_start` / `tool_end` events as tools execute.
    Returns the final assistant text plus the assembled tool-call trace.
    """

    bound = model.bind_tools(ALL_TOOLS) if use_tools else model
    convo: list[BaseMessage] = list(messages)
    accumulated_tool_calls: list[dict] = []
    final_text = ""

    for _ in range(max_iters):
        # Stream this turn.
        gathered: Optional[AIMessageChunk] = None
        async for chunk in bound.astream(convo):
            if not isinstance(chunk, AIMessageChunk):
                continue
            gathered = chunk if gathered is None else gathered + chunk
            if emit and chunk.content:
                if isinstance(chunk.content, str):
                    if chunk.content:
                        await emit({"type": "token", "delta": chunk.content})
                else:
                    # Anthropic returns list of content blocks; pull text deltas only.
                    for block in chunk.content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                await emit({"type": "token", "delta": text})

        if gathered is None:
            break

        ai_msg = AIMessage(
            content=_normalize_content(gathered.content),
            tool_calls=getattr(gathered, "tool_calls", []) or [],
        )
        convo.append(ai_msg)

        if not ai_msg.tool_calls:
            final_text = _content_text(ai_msg.content)
            break

        # Execute tools sequentially and append ToolMessages.
        registry = tools_by_name()
        for call in ai_msg.tool_calls:
            name = call.get("name")
            args = call.get("args") or {}
            tool_call_id = call.get("id") or name
            accumulated_tool_calls.append({"name": name, "args": args, "id": tool_call_id})
            if emit:
                await emit({"type": "tool_start", "name": name, "args": args, "id": tool_call_id})
            try:
                tool = registry.get(name)
                if tool is None:
                    output = f"Tool desconocida: {name}"
                else:
                    output = tool.invoke(args)
            except Exception as exc:  # pragma: no cover - defensive
                output = f"Error ejecutando tool {name}: {exc}"
            if not isinstance(output, str):
                try:
                    output = json.dumps(output, ensure_ascii=False, default=str)
                except Exception:
                    output = str(output)
            if emit:
                await emit({"type": "tool_end", "name": name, "id": tool_call_id, "output": output})
            convo.append(ToolMessage(content=output, tool_call_id=tool_call_id))
    else:
        # Hit max_iters without natural stop; capture last AI text if any.
        for m in reversed(convo):
            if isinstance(m, AIMessage):
                final_text = _content_text(m.content)
                break

    if emit:
        await emit({"type": "final", "text": final_text})

    return RunResult(text=final_text, tool_calls=accumulated_tool_calls, messages=convo)


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                out.append(block.get("text", ""))
            elif isinstance(block, str):
                out.append(block)
        return "".join(out)
    return str(content)


def _normalize_content(content):
    # AIMessage accepts both str and list[dict]; we keep the original shape.
    return content


def build_system_messages(*chunks: str) -> list[SystemMessage]:
    return [SystemMessage(content=c) for c in chunks if c]


def user(content: str) -> HumanMessage:
    return HumanMessage(content=content)
