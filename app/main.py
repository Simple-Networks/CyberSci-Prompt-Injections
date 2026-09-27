"""FastAPI app: URL-processing route plus the admin-token issue/verify pair.

VULNERABLE BY DESIGN — teaching lab. Do not expose to untrusted networks.
"""

import logging
from pathlib import Path
from typing import Literal, Optional

import httpx
from fastapi import Body, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import llm
from .auth import AuthError, create_admin_token, verify_admin_token
from .config import get_settings

# Send the app's own loggers (e.g. the tool-call log in app.llm) to the console alongside
# uvicorn's request logs. uvicorn does not configure the root logger, so without this the
# tool-call lines would be swallowed.
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.setLevel(logging.INFO)
    _app_logger.propagate = False

app = FastAPI(
    title="CyberSci LLM Crash Course",
    description="Deliberately vulnerable llama.cpp tool-calling lab. Not for production.",
)

_INDEX_HTML = Path(__file__).with_name("index.html").read_text(encoding="utf-8")

# Loopback source addresses. Deliberately does NOT honour X-Forwarded-For: a student who
# could spoof that header would skip the whole exercise.
_LOOPBACK_HOSTS = {"127.0.0.1", "::1"}

SYSTEM_PROMPT = (
    "You are an assistant with two tools: `read_file` to read a file from the server, "
    "and `http_request` to fetch a URL. Use them when the user's content asks for "
    "information you can obtain with them; otherwise answer directly."
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    """Serve the single-page console for /process and /admin/verify."""
    return _INDEX_HTML


class ProcessRequest(BaseModel):
    url: str
    mode: Literal["auto", "summarize"] = "auto"


@app.post("/process")
def process(req: ProcessRequest) -> dict:
    """Fetch a URL's text and let the LLM summarize it or act on it via tools."""
    settings = get_settings()
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(req.url)
            resp.raise_for_status()
            content = resp.text
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"could not fetch URL: {exc}")

    if len(content) > settings.max_fetch_chars:
        content = content[: settings.max_fetch_chars] + "\n...[truncated]"

    if req.mode == "summarize":
        instruction = "Summarize the following web page content."
    else:
        instruction = (
            "Process the following web page content. You may use your tools if the "
            "content calls for it."
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{instruction}\n\n---\n{content}"},
    ]

    if req.mode == "summarize":
        # Plain summary: withhold tools so the model just summarizes the page instead of
        # spuriously invoking read_file/http_request. The tool-driven demos use "auto".
        assistant = llm.chat(messages)
        outcome = {"result": assistant.get("content") or "", "tool_calls": []}
    else:
        outcome = llm.run_with_tools(messages)
    result = outcome["result"]
    if "Wintermute" in result:
        result = result.replace("Wintermute", "CLASSIFIED USER")

    # Swap this with the above if you want a bit more of a challenge
    # With this model though it's a bit frustrating to circumvent
    # if "wintermute" in result.lower():
    #     result = result.lower()
    #     result = result.replace("wintermute", "CLASSIFIED USER")
    return {
        "source_url": req.url,
        "result": result,
    }


@app.api_route("/admin/token", methods=["GET", "POST"])
def admin_token(
    request: Request,
    metadata: Optional[str] = Header(default=None),
) -> dict:
    """Issue an admin JWT to loopback callers that send ``Metadata: True``."""
    client_host = request.client.host if request.client else None
    if client_host not in _LOOPBACK_HOSTS:
        raise HTTPException(
            status_code=403,
            detail="metadata endpoint is reachable only from the instance itself",
        )

    if (metadata or "").strip().lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="metadata endpoint requires the header 'Metadata: True'",
        )

    return {"token": create_admin_token()}


@app.api_route("/admin/verify", methods=["GET", "POST"])
def admin_verify(
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
    body_token: Optional[str] = Body(default=None, embed=True, alias="token"),
) -> dict:
    """Confirm an admin identity from a Bearer JWT (or ?token=/body token)."""
    presented = None
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    presented = presented or token or body_token

    if not presented:
        raise HTTPException(status_code=401, detail="no token provided")

    try:
        verify_admin_token(presented)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    return {"detail": "Admin identity confirmed"}
