"""
WebSocket chat endpoint — streams tokens back to the client.
Includes a simple LRU-style in-process response cache for repeated queries.

Model fallback logic:
  - TPM (per-minute) error  → sleep the suggested delay, retry same model
  - TPD / quota / daily limit / rejected or expired key → rotate to next model
  - ModelsExhaustedError     → tell user all models are unavailable
"""
import json
import asyncio
import re
from collections import OrderedDict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from rag.agent import build_agent, rotate_model, ModelsExhaustedError

router = APIRouter()

# ── Response cache (max 100 entries, LRU eviction) ───────────────────────────
_CACHE_MAX   = 100
_query_cache: OrderedDict[str, tuple[str, list]] = OrderedDict()


def _cache_key(msg: str) -> str:
    return msg.strip().lower()


def _cache_get(msg: str):
    key = _cache_key(msg)
    if key in _query_cache:
        _query_cache.move_to_end(key)
        return _query_cache[key]
    return None


def _cache_set(msg: str, text: str, sources: list):
    key = _cache_key(msg)
    _query_cache[key] = (text, sources)
    _query_cache.move_to_end(key)
    if len(_query_cache) > _CACHE_MAX:
        _query_cache.popitem(last=False)


# ── Error classification ──────────────────────────────────────────────────────
def _is_retriable(err: Exception) -> bool:
    s = str(err).lower()
    return any(k in s for k in (
        "rate_limit", "rate limit", "429", "quota",
        "resource_exhausted", "decommissioned",
        "model_not_found", "model not found",
        "invalid api key", "invalid_api_key", "expired_api_key",
        "error code: 401",
    ))


def _is_tpm(err: Exception) -> bool:
    """True when it's a per-minute limit (short wait recovers it)."""
    s = str(err).lower()
    return "per minute" in s or "per_minute" in s or "tokens per min" in s


def _wait_seconds(err: Exception) -> float:
    """Extract suggested retry delay from error message, cap at 10s."""
    m = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", str(err).lower())
    return min(float(m.group(1)) + 1, 10) if m else 5.0


# ── Core query with fallback ──────────────────────────────────────────────────
_MAX_TPM_RETRIES = 2   # after this many TPM sleeps on one model, rotate


async def _run_query(loop, agent, user_msg: str) -> tuple[str, list]:
    """
    Run agent.query() with automatic model fallback.
    Returns (full_text, sources).
    """
    current_agent = agent
    tpm_retries   = 0

    while True:
        try:
            a = current_agent   # capture for lambda
            response = await loop.run_in_executor(None, lambda: a.query(user_msg))
            text    = response.response
            sources = getattr(response, "sources", [])
            print(f"[chat] Answer ({len(text)} chars) from model")
            return text, sources

        except Exception as e:
            print(f"[chat] Model error: {e}")

            if not _is_retriable(e):
                return f"Sorry, I encountered an error: {e}", []

            if _is_tpm(e) and tpm_retries < _MAX_TPM_RETRIES:
                # Per-minute limit: sleep briefly and retry same model
                tpm_retries += 1
                wait = _wait_seconds(e)
                print(f"[chat] TPM limit (retry {tpm_retries}/{_MAX_TPM_RETRIES}) — sleeping {wait:.1f}s")
                await asyncio.sleep(wait)
                continue  # retry same model

            # Daily / quota exhausted OR too many TPM retries: rotate
            tpm_retries = 0
            try:
                current_agent = rotate_model()
            except ModelsExhaustedError:
                return (
                    "All AI models are currently at their rate limits. "
                    "Please try again in a few minutes.",
                    [],
                )


@router.websocket("/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    agent   = build_agent()
    history: list[dict] = []

    try:
        while True:
            user_msg = await websocket.receive_text()
            if not user_msg.strip():
                continue

            history.append({"role": "user", "content": user_msg})
            await websocket.send_text(json.dumps({"type": "thinking"}))

            sources:   list[dict] = []
            cached = _cache_get(user_msg)
            if cached:
                full_text, sources = cached
            else:
                loop      = asyncio.get_event_loop()
                full_text, sources = await _run_query(loop, agent, user_msg)
                if not full_text.startswith("Sorry") and not full_text.startswith("All AI"):
                    _cache_set(user_msg, full_text, sources)

            # Stream word-by-word
            for word in full_text.split(" "):
                await websocket.send_text(
                    json.dumps({"type": "token", "data": word + " "})
                )
                await asyncio.sleep(0.01)

            await websocket.send_text(
                json.dumps({"type": "done", "data": full_text, "sources": sources})
            )
            history.append({"role": "assistant", "content": full_text})

    except WebSocketDisconnect:
        pass
