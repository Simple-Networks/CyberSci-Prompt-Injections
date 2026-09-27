"""Client for the llama.cpp OpenAI-compatible server plus the tool-calling loop."""

import logging

import httpx

from .config import get_settings
from .tools import TOOL_SCHEMAS, dispatch

logger = logging.getLogger(__name__)


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """POST to /chat/completions and return the assistant message object."""
    settings = get_settings()
    payload: dict = {"model": settings.llama_model, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {"Authorization": f"Bearer {settings.llama_api_key}"}
    url = f"{settings.llama_base_url.rstrip('/')}/chat/completions"

    with httpx.Client(timeout=settings.llama_timeout) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]


def run_with_tools(messages: list[dict]) -> dict:
    """Drive the model with tools available, executing any tool calls it emits.

    Returns ``{"result": <final assistant text>, "tool_calls": [<trace>]}``. Each tool
    invocation and its result is also logged server-side as it fires; the trace in the
    return value is retained for tests and internal callers, but ``/process`` does not
    expose it to clients.

    """
    settings = get_settings()
    convo = list(messages)
    trace: list[dict] = []
    results: list[tuple[str, str]] = []

    for _ in range(settings.max_tool_iterations):
        assistant = chat(convo, tools=TOOL_SCHEMAS)

        tool_calls = assistant.get("tool_calls") or []
        if not tool_calls:
            # No tools used yet: this is a plain answer, return it directly. If tools
            # *were* already used, don't trust this in-loop reply — the accumulated
            # context makes small models hallucinate here — and drop to the clean
            # synthesis step below instead.
            if not results:
                return {"result": assistant.get("content") or "", "tool_calls": trace}
            break

        convo.append(assistant)
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")
            result = dispatch(name, raw_args)
            logger.info("tool call: %s args=%s", name, raw_args)
            logger.info("tool result: %s ->\n%s", name, result)
            trace.append({"name": name, "arguments": raw_args, "result": result})
            results.append((name, result))
            convo.append(
                {
                    "role": "user",
                    "content": f"Result of calling the {name} tool:\n{result}",
                }
            )

    if not results:
        # Model neither called a tool nor answered — nothing to synthesise from.
        return {"result": "", "tool_calls": trace}

    # Tools were used. Produce the final answer from a clean context — the original
    # messages plus the restated tool outputs, with tools withheld — rather than from
    # the in-loop conversation. This both stops the model re-calling tools and avoids
    # the hallucinated "I can't access that" replies it gives amid the loop context.
    joined = "\n\n".join(f"Output of {name}:\n{result}" for name, result in results)
    synthesis = list(messages) + [
        {
            "role": "user",
            "content": (
                f"Here are the results of the tools you ran:\n\n{joined}\n\n"
                "Using these results, answer the original request. Do not call any tools."
            ),
        }
    ]
    final = chat(synthesis)
    return {"result": final.get("content") or "", "tool_calls": trace}
