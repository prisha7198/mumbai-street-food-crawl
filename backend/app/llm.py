"""Thin wrapper around the Anthropic SDK.

Claude is only used for language: reading the request and writing the
why-lines. Every call has a hard timeout, no retries, and an in-memory cache
keyed by a hash of the input, so the same request never costs twice. Any
failure returns None and the caller falls back to the offline path.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from typing import Any

from . import config

log = logging.getLogger("crawl.llm")
_cache: dict[str, Any] = {}
_lock = threading.Lock()
_client = None
_auth_failed = False          # a bad key will not get better: stop trying until restart
last_error: str | None = None


def available() -> bool:
    return bool(config.ANTHROPIC_API_KEY) and config.USE_CLAUDE and not _auth_failed


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=0)
    return _client


def cache_key(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _remember(key: str, value: Any) -> Any:
    with _lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[key] = value
    return value


def _fail(reason: str) -> None:
    global last_error
    last_error = reason
    log.warning("Claude call skipped: %s", reason)


def _status_error(e) -> None:
    global _auth_failed
    if e.status_code in (401, 403):
        _auth_failed = True
    return _fail(f"API error {e.status_code}: {e.message}")


def call_tool(system: str, user: str, tool: dict, timeout: float, max_tokens: int = 1024) -> dict | None:
    """Ask Claude to call `tool` once and return its validated input, or None."""
    if not available():
        return None
    key = cache_key("tool", config.ANTHROPIC_MODEL, system, user, tool)
    if key in _cache:
        return _cache[key]
    import anthropic
    try:
        resp = _get_client().with_options(timeout=timeout).messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            tools=[{**tool, "strict": True}],
            # Forced tool_choice is rejected by the newest models, so we ask
            # for the call in the prompt and rely on strict schema validation.
            tool_choice={"type": "auto"},
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APITimeoutError:
        return _fail("timeout")
    except anthropic.APIConnectionError as e:
        return _fail(f"connection error: {e}")
    except anthropic.APIStatusError as e:
        return _status_error(e)
    except Exception as e:  # noqa: BLE001 - the demo must never crash on the LLM
        return _fail(f"unexpected error: {e!r}")
    if resp.stop_reason == "refusal":
        return _fail("refusal")
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool["name"]:
            return _remember(key, dict(block.input))
    return _fail("no tool call in response")


def call_json(system: str, user: str, schema: dict, timeout: float, max_tokens: int = 2048) -> dict | None:
    """Structured JSON output that matches `schema`, or None."""
    if not available():
        return None
    key = cache_key("json", config.ANTHROPIC_MODEL, system, user, schema)
    if key in _cache:
        return _cache[key]
    import anthropic
    try:
        resp = _get_client().with_options(timeout=timeout).messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APITimeoutError:
        return _fail("timeout")
    except anthropic.APIConnectionError as e:
        return _fail(f"connection error: {e}")
    except anthropic.APIStatusError as e:
        return _status_error(e)
    except Exception as e:  # noqa: BLE001
        return _fail(f"unexpected error: {e!r}")
    if resp.stop_reason in ("refusal", "max_tokens"):
        return _fail(f"stop_reason {resp.stop_reason}")
    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        return _remember(key, json.loads(text))
    except json.JSONDecodeError:
        return _fail("response was not valid JSON")
