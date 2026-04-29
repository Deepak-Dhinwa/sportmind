"""
OrchestratedAgent — replaces LlamaIndex RouterQueryEngine.

Pipeline for every query:
  1. Classify intent  (regex, no LLM call)
  2. Graph query      (Neo4j → exact facts, for NBA questions)
  3. Enrich query     (extract entity names from graph result → append to vector query)
  4. Vector search    (Weaviate hybrid + rerank with enriched query)
  5. Prediction       (ML models, if intent == prediction)
  6. Unified synthesis (single LLM call with all context)
  7. Source filtering (only sources whose entity appears in the answer)
"""
import re
import json
from dataclasses import dataclass

from llama_index.core.schema import QueryBundle

from rag.graph_tool import GraphQueryEngine
from rag.vector_tool import retrieve, _extract_entity_names
from rag._prediction_engine_adapter import PredictionQueryEngine


# ── Intent classification ─────────────────────────────────────────────────────

_PREDICT_RE  = re.compile(
    r'\b(predict|will\s+win|win\s+probability|forecast|next\s+game|chance|upcoming\s+game)\b', re.I)
_COMPARE_RE  = re.compile(
    r'\b(compare|vs\.?|versus|better\s+than|head.to.head|difference\s+between)\b', re.I)
_STAT_RE     = re.compile(
    r'\b(stats?|points?|assists?|rebounds?|average|ppg|apg|rpg|career|season|record|wins?|'
    r'scoring|championship|award|mvp|roster|top\s+scorer|games?\s+played)\b', re.I)
_NBA_RE      = re.compile(
    r'\b(nba|basketball|player|team|lakers|warriors|celtics|heat|bulls|spurs|curry|'
    r'lebron|durant|harden|playoff|finals|season)\b', re.I)


def _classify_intent(question: str) -> str:
    if _PREDICT_RE.search(question):
        return "prediction"
    if _COMPARE_RE.search(question):
        return "compare"
    entities = _extract_entity_names(question)
    is_nba   = bool(entities) or bool(_NBA_RE.search(question))
    if not is_nba:
        return "custom"   # custom uploaded doc, skip graph
    if _STAT_RE.search(question):
        return "stat"
    return "narrative"


# ── Entity extraction from graph result ──────────────────────────────────────

def _entities_from_graph(graph_text: str) -> list[str]:
    """
    Parse a markdown table returned by the graph tool and extract
    entity names (player/team names) to enrich the vector query.
    Only extracts names — NOT numbers or stats.
    """
    entities = []
    seen     = set()
    for line in graph_text.split("\n"):
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        for cell in cells:
            # Skip separator lines, numbers, season strings
            if re.match(r'^[-\s]+$', cell):
                continue
            if re.match(r'^\d', cell):
                continue
            if re.match(r'^\d{4}-\d{2}$', cell):
                continue
            # Must look like a name: starts uppercase, 2+ words
            if re.match(r'^[A-Z][a-zA-Z\'-]+(?: [A-Z][a-zA-Z\'-]+)+$', cell):
                if cell not in seen and len(cell) > 5:
                    seen.add(cell)
                    entities.append(cell)
    return entities[:6]


# ── Source filtering ──────────────────────────────────────────────────────────

def _filter_sources(answer: str, graph_entities: list[str], chunks: list[dict]) -> list[dict]:
    """
    Return only sources whose entity is actually mentioned in the answer.
    Avoids showing irrelevant sources from vector retrieval.
    """
    answer_lower = answer.lower()
    sources = []
    seen    = set()

    # Graph sources first
    for ent in graph_entities:
        key = ent.lower()
        if key in seen:
            continue
        # Check if any word of the entity name (>4 chars) is in the answer
        words = [w for w in ent.lower().split() if len(w) > 4]
        if any(w in answer_lower for w in words):
            sources.append({"entity": ent, "doc_type": "graph", "file": "neo4j"})
            seen.add(key)

    # Vector sources
    for c in chunks:
        ent  = c.get("entity_name", "")
        if not ent:
            continue
        key  = ent.lower()
        if key in seen:
            continue
        words = [w for w in ent.lower().replace("_", " ").split() if len(w) > 4]
        if any(w in answer_lower for w in words):
            sources.append({
                "entity":   ent,
                "doc_type": c.get("doc_type", ""),
                "file":     c.get("source_file", "").replace("\\", "/").split("/")[-1],
            })
            seen.add(key)

    return sources[:6]


# ── Synthesis prompt ──────────────────────────────────────────────────────────

_SYNTHESIS_PROMPT = """\
You are SportMind, an expert NBA analytics assistant covering the 2013–2023 era.
Answer the question using ONLY the context provided below.

RULES:
- Use Graph Facts for ALL specific numbers, statistics, records, and awards.
  Do NOT invent or recall statistics not present in Graph Facts.
- Use Knowledge Base for narrative, playing style, historical context, and story.
- If information is missing from both sources, say so clearly.
- Be specific: cite player names, teams, seasons, and exact numbers from the data.
- DATA WINDOW: The database only covers seasons 2013-14 to 2022-23. If a player
  has fewer seasons than expected (e.g. Kobe Bryant, who retired in 2016), mention
  this limitation — their earlier career is not in this dataset.

Question: {question}

=== GRAPH FACTS (structured data — use for all numbers) ===
{graph_result}

=== KNOWLEDGE BASE (narrative and contextual documents) ===
{vector_context}
===

Answer:"""

_SYNTHESIS_PROMPT_NO_GRAPH = """\
You are SportMind, an expert assistant.
Answer the question using ONLY the context provided below.
If the answer is not in the context, say you don't have that information.

Question: {question}

=== KNOWLEDGE BASE ===
{vector_context}
===

Answer:"""


# ── Response dataclass ────────────────────────────────────────────────────────

@dataclass
class OrchestratedResponse:
    response: str
    sources:  list[dict]

    def __str__(self):
        return self.response


# ── Main orchestrator ─────────────────────────────────────────────────────────

class OrchestratedAgent:
    def __init__(self, llm):
        self._llm   = llm
        self._graph = GraphQueryEngine(llm=llm)
        self._pred  = PredictionQueryEngine(llm=llm)

    def query(self, question: str) -> OrchestratedResponse:
        intent = _classify_intent(question)

        # ── Step 1: Graph query ───────────────────────────────────────────────
        graph_text    = ""
        graph_entities: list[str] = []

        if intent != "custom":
            try:
                graph_resp = self._graph._query(QueryBundle(question))
                raw_graph  = str(graph_resp.response)
                # Treat as empty if graph returned an error / no data
                _bad = ("couldn't generate", "no results", "failed after",
                        "not available", "try rephrasing", "unsupported",
                        "requires information not available")
                if not any(b in raw_graph.lower() for b in _bad):
                    graph_text    = raw_graph
                    graph_entities = _entities_from_graph(raw_graph)
            except Exception:
                pass   # graph failure is non-fatal

        # ── Step 2: Enriched vector query ─────────────────────────────────────
        # Append entity names from graph (NOT stats) to focus vector search
        enriched_q = question
        if graph_entities:
            suffix     = " ".join(graph_entities[:4])
            enriched_q = f"{question} {suffix}"

        chunks      = retrieve(enriched_q, top_k=20, top_n=6)
        vector_ctx  = _format_vector_chunks(chunks)

        # ── Step 3: Prediction (if needed) ────────────────────────────────────
        pred_text = ""
        if intent == "prediction":
            try:
                pred_resp = self._pred._query(QueryBundle(question))
                pred_text = str(pred_resp.response)
            except Exception as e:
                pred_text = f"Prediction unavailable: {e}"

        # ── Step 4: Unified synthesis ─────────────────────────────────────────
        if intent == "prediction" and pred_text and "unavailable" not in pred_text:
            # Prediction answers are already self-contained
            answer = pred_text
        elif intent == "custom" or not graph_text:
            prompt = _SYNTHESIS_PROMPT_NO_GRAPH.format(
                question=question,
                vector_context=vector_ctx or "No relevant documents found.",
            )
            answer = str(self._llm.complete(prompt))
        else:
            combined_graph = graph_text
            if pred_text:
                combined_graph += f"\n\nPrediction: {pred_text}"
            prompt = _SYNTHESIS_PROMPT.format(
                question=question,
                graph_result=combined_graph,
                vector_context=vector_ctx or "No narrative context available.",
            )
            answer = str(self._llm.complete(prompt))

        # ── Step 5: Source filtering ──────────────────────────────────────────
        sources = _filter_sources(answer, graph_entities, chunks)

        return OrchestratedResponse(response=answer, sources=sources)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_vector_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for c in chunks:
        label = f"[{c.get('doc_type','').upper()} — {c.get('entity_name','')}]"
        parts.append(f"{label}\n{c['content']}")
    return "\n\n---\n\n".join(parts)
