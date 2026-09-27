"""The two tools exposed to the LLM: reading files and making web requests.

Both are intentionally unrestricted — no path allowlist, no SSRF blocklist — so that the
lab's prompt-injection and SSRF demos actually succeed. ``TOOL_SCHEMAS`` is the
OpenAI-style function-calling advertisement, and ``dispatch`` runs a requested call.
"""

import json

import httpx

from .config import get_settings


def read_file(path: str) -> str:
    """Return the text contents of a file at an arbitrary path (traversal possible)."""
    settings = get_settings()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = fh.read(settings.max_file_chars + 1)
    except OSError as exc:
        return f"ERROR reading {path!r}: {exc}"

    if len(data) > settings.max_file_chars:
        data = data[: settings.max_file_chars] + "\n...[truncated]"
    return data


def http_request(
    url: str,
    method: str = "GET",
    body: str | None = None,
) -> str:
    """Make an HTTP request to ANY url (incl. localhost/private IPs — SSRF possible)."""
    settings = get_settings()
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.request(
                method.upper(),
                url,
                headers={"Metadata": "true"},
                content=body if body is not None else None,
            )
    except httpx.HTTPError as exc:
        return f"ERROR requesting {url!r}: {exc}"

    text = resp.text
    if len(text) > settings.max_http_tool_chars:
        text = text[: settings.max_http_tool_chars] + "\n...[truncated]"
    return f"HTTP {resp.status_code} {resp.reason_phrase}\n\n{text}"


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read and return the text contents of a file on the server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filesystem path of the file to read.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_request",
            "description": "Make an HTTP request to a URL and return the response body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to request."},
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, ...). Defaults to GET.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional request body for POST/PUT.",
                    },
                },
                "required": ["url"],
            },
        },
    },
]

_HANDLERS = {"read_file": read_file, "http_request": http_request}


def dispatch(name: str, arguments: str | dict) -> str:
    """Run tool ``name`` with the given arguments (JSON string or dict)."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"ERROR: unknown tool {name!r}"

    if isinstance(arguments, str):
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError as exc:
            return f"ERROR: could not parse arguments for {name!r}: {exc}"
    else:
        args = arguments or {}

    try:
        return handler(**args)
    except TypeError as exc:
        return f"ERROR: bad arguments for {name!r}: {exc}"
