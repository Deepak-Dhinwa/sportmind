"""
Semantic Search Tool — hybrid (BM25 + dense) retrieval from Weaviate
followed by cross-encoder reranking.

Pipeline:
  query → entity detection → hybrid search (general + entity-filtered)
        → merge & deduplicate → cross-encoder rerank → top 5 → LLM synthesis

Improvements over v1:
  - Entity-aware filtering: detects player/team names in query and runs an
    additional filtered search so entity-specific chunks rank higher.
  - Adaptive top_k: broader recall for complex multi-entity queries.
  - Richer synthesis prompt with source attribution.
"""
import re
from llama_index.core.base.base_query_engine import BaseQueryEngine
from llama_index.core.callbacks import CallbackManager
from llama_index.core.schema import QueryBundle
from llama_index.core.base.response.schema import Response
from sentence_transformers import SentenceTransformer, CrossEncoder
from weaviate.classes.query import Filter

from rag.weaviate_client import get_client, COLLECTION_NAME

# ── Model singletons ───────────────────────────────────────────────────────────

_embed_model: SentenceTransformer | None = None
_rerank_model: CrossEncoder | None = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def _get_rerank_model() -> CrossEncoder:
    global _rerank_model
    if _rerank_model is None:
        _rerank_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _rerank_model


# ── Entity Detection ───────────────────────────────────────────────────────────

# Words to exclude from entity detection (common NBA terms that look like names)
_ENTITY_STOPWORDS = {
    "NBA", "Finals", "Playoffs", "Regular Season", "Most Valuable",
    "Defensive Player", "Rookie Year", "Most Improved", "All Star",
    "All NBA", "Eastern Conference", "Western Conference", "Triple Double",
    "Point Guard", "Shooting Guard", "Small Forward", "Power Forward",
    "Head Coach", "Head Coaches",
}


def _extract_entity_names(query: str) -> list[str]:
    """
    Extract likely player/team names from query text.
    Looks for sequences of 2-4 consecutive Title-Case words.
    Returns up to 3 candidate entity names.
    """
    pattern = r'\b([A-Z][a-zA-Z\'-]+(?:\s+[A-Z][a-zA-Z\'-]+){1,3})\b'
    matches = re.findall(pattern, query)
    results = []
    for m in matches:
        if m not in _ENTITY_STOPWORDS and len(m) > 5:
            results.append(m)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for r in results:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique[:3]  # limit to top 3 entities


def _entity_to_slug(name: str) -> str:
    """Convert 'LeBron James' → 'lebron_james' to match entity_name field."""
    return name.lower().replace(" ", "_").replace(".", "").replace("'", "")


# ── Retrieval ──────────────────────────────────────────────────────────────────

def hybrid_search(
    query: str,
    top_k: int = 20,
    alpha: float = 0.75,
    entity_filter: str | None = None,
) -> list[dict]:
    """
    Hybrid search combining BM25 and dense vector retrieval.

    Args:
        query:         User query text.
        top_k:         Number of results to return.
        alpha:         0 → pure BM25, 1 → pure dense. Default 0.75 (semantic-leaning).
        entity_filter: If provided, filter results to documents whose entity_name
                       contains this string (wildcard match).
    """
    embed  = _get_embed_model()
    vector = embed.encode(query).tolist()

    client     = get_client()
    collection = client.collections.get(COLLECTION_NAME)

    kwargs = dict(
        query=query,
        vector=vector,
        target_vector="default",
        alpha=alpha,
        limit=top_k,
        return_properties=["content", "doc_type", "entity_name", "source_file"],
    )

    if entity_filter:
        # Partial case-insensitive match on entity_name (spaces, no slug conversion)
        name_lower = entity_filter.lower()
        kwargs["filters"] = Filter.by_property("entity_name").like(f"*{name_lower}*")

    result = collection.query.hybrid(**kwargs)

    hits = []
    for obj in result.objects:
        hits.append({
            "content":     obj.properties.get("content", ""),
            "doc_type":    obj.properties.get("doc_type", ""),
            "entity_name": obj.properties.get("entity_name", ""),
            "source_file": obj.properties.get("source_file", ""),
        })
    return hits


def _is_junk_chunk(content: str) -> bool:
    """Return True for chunks that are links lists or near-empty headers."""
    lines = [l.strip() for l in content.strip().split("\n") if l.strip()]
    if len(lines) == 0:
        return True
    # Too short
    if len(content.split()) < 25:
        return True
    # Mostly link-list lines: "Name at Site" or URLs
    link_lines = sum(
        1 for l in lines
        if (" at " in l and len(l) < 80) or l.startswith("http") or l.startswith("- http")
    )
    if link_lines > 0 and link_lines >= len(lines) * 0.5:
        return True
    return False


def rerank(query: str, hits: list[dict], top_n: int = 5) -> list[dict]:
    """Apply cross-encoder reranking to hybrid search results.
    Filters out near-empty and link-list chunks before scoring."""
    if not hits:
        return []
    substantive = [h for h in hits if not _is_junk_chunk(h["content"])]
    if not substantive:
        substantive = hits   # fallback: use all if everything filtered
    reranker = _get_rerank_model()
    pairs    = [(query, h["content"]) for h in substantive]
    scores   = reranker.predict(pairs)
    ranked   = sorted(zip(scores, substantive), key=lambda x: x[0], reverse=True)
    return [h for _, h in ranked[:top_n]]


def retrieve(query: str, top_k: int = 20, top_n: int = 6, alpha: float = 0.75) -> list[dict]:
    """
    Full retrieval pipeline:
      1. General hybrid search (top_k results)
      2. Entity-specific filtered search for any detected names
      3. Merge + deduplicate
      4. Cross-encoder rerank → top_n
    """
    # Step 1: General search
    general_hits = hybrid_search(query, top_k=top_k, alpha=alpha)

    # Step 2: Entity-specific searches
    entities   = _extract_entity_names(query)
    extra_hits = []
    for entity in entities[:2]:  # process at most 2 entities
        filtered = hybrid_search(query, top_k=12, alpha=alpha, entity_filter=entity)
        extra_hits.extend(filtered)

    # Step 3: Merge, deduplicate by content
    seen_content: set[str] = set()
    merged: list[dict] = []
    # Entity-specific results first (higher priority before reranking)
    for h in extra_hits + general_hits:
        key = h["content"][:120]  # first 120 chars as dedup key
        if key not in seen_content:
            seen_content.add(key)
            merged.append(h)

    # Step 4: Rerank merged pool
    return rerank(query, merged[:40], top_n=top_n)


# ── Source attribution tracking ────────────────────────────────────────────────
# Stores the sources from the last retrieval so the chat layer can include them.
_last_sources: list[dict] = []


def get_last_sources() -> list[dict]:
    """Return sources from the most recent vector retrieval."""
    return list(_last_sources)


# ── Query Engine ───────────────────────────────────────────────────────────────

SYNTHESIS_PROMPT = """You are SportMind, an expert NBA analytics assistant covering the 2013–2023 era.
Use ONLY the retrieved context below to answer the question.
Be specific and narrative — mention player names, teams, seasons, stats, and key moments.
If the context is insufficient, say so clearly rather than speculating.

Question: {question}

Retrieved context:
{context}

Answer:"""


class VectorQueryEngine(BaseQueryEngine):
    def __init__(self, llm):
        self._llm = llm
        super().__init__(callback_manager=CallbackManager())

    def _get_prompt_modules(self):
        return {}

    def _query(self, query_bundle: QueryBundle) -> Response:
        global _last_sources
        question = query_bundle.query_str

        # For multi-entity queries (compare / vs / both), run a separate
        # focused retrieval per entity so the reranker can't drop one of them.
        entities = _extract_entity_names(question)
        if len(entities) >= 2 and any(
            kw in question.lower()
            for kw in ("compare", " vs ", " versus ", " and ", "both", "difference")
        ):
            per_entity: list[dict] = []
            for ent in entities[:3]:
                # Focused sub-query: entity name + career/stats context
                sub_q = f"{ent} career statistics achievements awards performance NBA"
                hits  = hybrid_search(sub_q, top_k=15, alpha=0.75, entity_filter=ent)
                # Rerank the sub-results against the original full question
                top   = rerank(question, hits, top_n=3)
                per_entity.extend(top)
            # Deduplicate while preserving per-entity order
            seen: set[str] = set()
            chunks: list[dict] = []
            for h in per_entity:
                k = h["content"][:120]
                if k not in seen:
                    seen.add(k)
                    chunks.append(h)
        else:
            chunks = retrieve(question, top_k=20, top_n=6)

        if not chunks:
            _last_sources = []
            return Response(
                response="No relevant documents found in the knowledge base for this query.",
                source_nodes=[],
            )

        # Track sources for attribution
        _last_sources = [
            {
                "entity": c["entity_name"],
                "doc_type": c["doc_type"],
                "file": c["source_file"].split("/")[-1].replace("_", " ").replace(".md", ""),
            }
            for c in chunks
            if c.get("entity_name") or c.get("source_file")
        ]

        context_parts = []
        for c in chunks:
            doc_label = f"[{c['doc_type'].upper()} — {c['entity_name']}]"
            context_parts.append(f"{doc_label}\n{c['content']}")
        context = "\n\n---\n\n".join(context_parts)

        prompt = SYNTHESIS_PROMPT.format(question=question, context=context)
        answer = str(self._llm.complete(prompt))
        return Response(response=answer, source_nodes=[])

    async def _aquery(self, query_bundle: QueryBundle) -> Response:
        return self._query(query_bundle)


def build_vector_query_engine(llm):
    return VectorQueryEngine(llm=llm)
