"""
RAG Agent — OrchestratedAgent (replaces LlamaIndex RouterQueryEngine).

Pipeline:
  1. Intent classification (regex, no LLM call)
  2. Graph query  → exact facts from Neo4j
  3. Enriched vector query → entities from graph appended to query
  4. Vector search → Weaviate hybrid + rerank
  5. Prediction  → ML models (if intent == prediction)
  6. Unified synthesis → single LLM call with all context
  7. Source filtering → only sources mentioned in the answer

Model fallback order:
  Groq llama-3.3-70b-versatile
  → Groq llama-3.1-8b-instant
  → Groq gemma2-9b-it
  → Google Gemini 1.5 Flash  (GEMINI_API_KEY)
"""
import os
from dotenv import load_dotenv

from llama_index.core import Settings
from llama_index.llms.groq import Groq

from rag.orchestrator import OrchestratedAgent

load_dotenv()

# ── Model roster ───────────────────────────────────────────────────────────────
# Each entry: (provider, model_name)
_MODEL_ROSTER = [
    ("groq",   "llama-3.3-70b-versatile"),   # 100K TPD — primary
    ("groq",   "llama-3.1-8b-instant"),       # 100K TPD, 6K TPM
    ("gemini", "gemini-2.5-flash"),            # 20 RPD, 250K TPM
    ("gemini", "gemma-3-27b-it"),              # 14.4K RPD — high-volume fallback
]

_agent       = None
_model_index = 0    # index into _MODEL_ROSTER


def _build_llm(provider: str, model: str):
    """Instantiate the right LlamaIndex LLM for the given provider."""
    if provider == "groq":
        return Groq(
            model=model,
            api_key=os.getenv("GROQ_API_KEY"),
            max_retries=0,   # disable built-in retry so OUR rotation runs immediately
        )

    if provider == "gemini":
        from llama_index.llms.google_genai import GoogleGenAI
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")
        return GoogleGenAI(model=model, api_key=api_key)

    raise ValueError(f"Unknown provider: {provider}")


def _current_roster_entry():
    return _MODEL_ROSTER[_model_index]


def build_agent():
    """Build and return the OrchestratedAgent. Cached after first call."""
    global _agent, _model_index
    if _agent is not None:
        return _agent

    provider, model = _current_roster_entry()
    print(f"[agent] Initialising with {provider} / {model}")
    llm = _build_llm(provider, model)
    Settings.llm = llm

    _agent = OrchestratedAgent(llm=llm)
    print("[agent] Ready.")
    return _agent


class ModelsExhaustedError(Exception):
    """Raised when every model in the roster has failed."""


def rotate_model():
    """
    Switch to the next model in the roster.
    Raises ModelsExhaustedError if already on the last entry.
    """
    global _agent, _model_index

    if _model_index >= len(_MODEL_ROSTER) - 1:
        raise ModelsExhaustedError("All models in roster are exhausted.")

    _model_index += 1
    provider, model = _current_roster_entry()
    print(f"[agent] Rate limit — rotating to {provider} / {model}")

    try:
        llm = _build_llm(provider, model)
        Settings.llm = llm
        _agent = OrchestratedAgent(llm=llm)
        print(f"[agent] Now using {provider} / {model}")
    except Exception as e:
        print(f"[agent] Failed to initialise {provider}/{model}: {e} — trying next")
        return rotate_model()   # recurse to skip broken entry

    return _agent


def active_model() -> str:
    """Return a human-readable string of the currently active model."""
    provider, model = _current_roster_entry()
    return f"{provider}/{model.split('/')[-1]}"


def reset_agent():
    global _agent, _model_index
    _agent       = None
    _model_index = 0
