# SportMind — Concepts & Technologies Explained

A deep-dive reference covering every major technology and technique used in this project. Written as self-contained chapters so you can read them in any order.

---

## Table of Contents

1. [Graph Databases & Neo4j](#chapter-1-graph-databases--neo4j)
2. [Vector Databases & Weaviate](#chapter-2-vector-databases--weaviate)
3. [Embeddings — How Machines Read Text](#chapter-3-embeddings--how-machines-read-text)
4. [Retrieval-Augmented Generation (RAG)](#chapter-4-retrieval-augmented-generation-rag)
5. [Advanced RAG Techniques](#chapter-5-advanced-rag-techniques)
6. [Large Language Models & Prompting](#chapter-6-large-language-models--prompting)
7. [Machine Learning Models Used](#chapter-7-machine-learning-models-used)
8. [Docker — Containers & Infrastructure](#chapter-8-docker--containers--infrastructure)
9. [FastAPI, WebSockets & Async Python](#chapter-9-fastapi-websockets--async-python)
10. [How Everything Connects in SportMind](#chapter-10-how-everything-connects-in-sportmind)

---

# Chapter 1: Graph Databases & Neo4j

## 1.1 Why Not Just Use a Regular Database?

Before understanding graph databases, it helps to understand the problem with relational databases when data is deeply connected.

In a relational database (like PostgreSQL or MySQL), data lives in tables. When you want to connect data across tables, you use **JOINs**. For simple relationships this is fine. But imagine this query:

> "Find all players who played for teams that were coached by coaches who also coached a championship team."

In SQL this requires 4–5 JOINs across multiple tables. The deeper the relationship chain, the slower and more complex the query. Relational databases were designed for tabular data, not for traversing chains of relationships.

This is where **graph databases** shine.

## 1.2 What Is a Graph?

In mathematics and computer science, a **graph** is a structure made of:
- **Nodes** (also called vertices) — the things you're modeling (a person, a city, a product)
- **Edges** (also called relationships or links) — the connections between things ("works at", "friends with", "sold to")

A graph database stores data natively in this node-edge structure. Everything is about relationships — they are first-class citizens, not an afterthought bolted on via JOINs.

```
(Stephen Curry) --[PLAYED_FOR]--> (Golden State Warriors)
(Stephen Curry) --[WON_AWARD]--> (MVP 2015-16)
(Golden State Warriors) --[WON_CHAMPIONSHIP]--> (2022 Season)
```

This is instantly readable and directly matches how we think about the NBA domain.

## 1.3 Property Graph Model

Neo4j uses the **labeled property graph model**. This means:

**Nodes** have:
- A **label** — the type of thing (`:Player`, `:Team`, `:Game`)
- **Properties** — key-value pairs attached to the node (`name: "LeBron James"`, `age: 39`)

**Relationships** have:
- A **type** — the nature of the connection (`PLAYED_FOR`, `WON_AWARD`)
- A **direction** — relationships go from one node to another (`Player → Team`)
- **Properties** — metadata on the relationship itself (`season: "2022-23"`, `games_played: 82`)

```
(:Player {name: "Stephen Curry", position: "PG", height: "6-2"})
    -[:PLAYED_FOR {season: "2022-23", games: 56}]->
(:Team {name: "Golden State Warriors", conference: "West"})
```

## 1.4 Cypher — The Query Language of Neo4j

Cypher is Neo4j's declarative query language. It's designed to be visual and readable — queries look like ASCII diagrams of the graph you want to match.

**Basic syntax:**
- `(n)` — a node
- `(n:Label)` — a node with a label
- `(n:Label {prop: value})` — a node with a label and property filter
- `-[r:TYPE]->` — a directed relationship of a specific type
- `-[r]->` — any relationship

**MATCH** — find patterns in the graph:
```cypher
MATCH (p:Player {name: "LeBron James"})-[:PLAYED_FOR]->(t:Team)
RETURN p.name, t.name
```

**CREATE** — add new nodes/relationships:
```cypher
CREATE (p:Player {player_id: 2544, name: "LeBron James", position: "SF"})
```

**MERGE** — create if it doesn't exist, otherwise match it (this is what we use in ingestion for idempotency):
```cypher
MERGE (p:Player {player_id: 2544})
SET p.name = "LeBron James", p.position = "SF"
```

**WHERE** — filter results:
```cypher
MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:PlayerSeasonStats)
WHERE s.pts > 25 AND s.season = "2022-23"
RETURN p.name, s.pts
ORDER BY s.pts DESC
LIMIT 10
```

**Variable-length paths** — traverse chains of unknown depth:
```cypher
MATCH (a:Player)-[:PLAYED_FOR*1..3]->(t:Team)
```
This matches players connected to a team through 1, 2, or 3 hops — useful for finding indirect connections.

**OPTIONAL MATCH** — like a SQL LEFT JOIN (returns null if the pattern isn't found):
```cypher
MATCH (p:Player {name: "Stephen Curry"})
OPTIONAL MATCH (p)-[:WON_AWARD]->(a:Award)
RETURN p.name, collect(a.name) AS awards
```

**Aggregation:**
```cypher
MATCH (t:Team)-[:PLAYED_GAME]->(g:Game {season: "2022-23"})
RETURN t.name, count(g) AS games_played
```

## 1.5 Indexes and Constraints

For performance, Neo4j allows:

**Unique constraints** — enforce uniqueness and auto-create an index:
```cypher
CREATE CONSTRAINT player_id_unique IF NOT EXISTS
FOR (p:Player) REQUIRE p.player_id IS UNIQUE
```

**Range indexes** — speed up property lookups and range queries:
```cypher
CREATE INDEX player_name_idx IF NOT EXISTS FOR (p:Player) ON (p.name)
```

Without indexes, Neo4j scans all nodes with a given label. With indexes, lookups by property are O(log n).

## 1.6 Why We Used Neo4j in SportMind

The NBA domain is inherently a graph:
- Players have relationships with teams (per season)
- Teams participate in games
- Games belong to seasons
- Players win awards in specific seasons
- Coaches coach teams for specific periods

Questions like "which teams did LeBron play for?" or "who won the MVP in 2018?" are naturally expressed as graph traversals. Neo4j lets us answer these with clean Cypher queries that map directly to the question, rather than building complex SQL with multiple JOINs.

We also use it as the **structured facts layer** in our RAG pipeline — when a user asks about stats or records, we query Neo4j first because it gives exact, reliable numerical answers (unlike an LLM which might hallucinate).

---

# Chapter 2: Vector Databases & Weaviate

## 2.1 The Problem That Vector Databases Solve

Traditional databases are great for exact lookups: "give me all players where pts = 27.4". But they fail at **semantic** or **meaning-based** queries: "give me documents about dominant big men in the modern NBA."

This second type of query requires understanding *meaning*, not matching exact strings. The solution is to represent text as **vectors** (lists of numbers) where similar meaning = similar vectors, then search by vector similarity. This is what a vector database does.

## 2.2 How Vector Search Works

Each piece of text is converted into a high-dimensional vector (an **embedding**) by a machine learning model. For example, our embedding model produces 384-dimensional vectors.

Think of each vector as a point in 384-dimensional space. Semantically similar texts produce points that are **close to each other** in this space. "LeBron's scoring ability" and "James is an elite scorer" will produce vectors that are very close together, even though they share no words.

When you run a query:
1. The query text is embedded into a vector
2. The database finds the stored vectors closest to the query vector
3. Those closest documents are returned

**Distance metrics** — how "closeness" is measured:
- **Cosine similarity** — measures the angle between vectors (most common for text, range -1 to 1, higher = more similar)
- **Euclidean distance** — straight-line distance between points (lower = more similar)
- **Dot product** — similar to cosine but sensitive to vector magnitude

## 2.3 Approximate Nearest Neighbor (ANN) Search

With millions of vectors, comparing a query against every single stored vector is too slow. Vector databases use **Approximate Nearest Neighbor** algorithms that trade a tiny bit of accuracy for massive speed improvements.

The most popular is **HNSW** (Hierarchical Navigable Small World) — a graph-based index that organizes vectors into layers, allowing the search to quickly zoom in on the nearest neighbors without exhausting every vector. This is what Weaviate uses internally.

## 2.4 BM25 — Keyword Search

BM25 (Best Match 25) is a classical information retrieval algorithm that ranks documents by keyword relevance. It's an improvement over simple TF-IDF:

- **TF (Term Frequency)** — how often the keyword appears in the document
- **IDF (Inverse Document Frequency)** — how rare the keyword is across all documents (rare words are more informative)
- **BM25 adds length normalization** — longer documents don't get unfairly boosted just for containing a word more times

BM25 is still excellent for queries with specific names, numbers, or rare terms. If you search for "Stephen Curry 2022-23 three-pointers", BM25 will find documents containing those exact terms.

## 2.5 Hybrid Search — Best of Both Worlds

The key insight: **dense (vector) search and sparse (keyword) search are complementary**.

- Dense search: great for conceptual, semantic queries ("who is the best defender?")
- Sparse search: great for specific terms, names, stats ("Curry 402 three-pointers 2015-16")

**Hybrid search** combines both scores. Weaviate uses a parameter called **alpha**:
- `alpha = 1.0` → pure vector search
- `alpha = 0.0` → pure BM25 keyword search
- `alpha = 0.75` → 75% vector, 25% BM25

The scores from both systems are merged using **Reciprocal Rank Fusion (RRF)** — a technique that combines ranked lists from multiple retrieval systems by taking the reciprocal of each document's rank in each list and summing them.

We use hybrid search in SportMind because NBA queries often combine semantic intent ("best scorer") with specific entity names ("LeBron James in 2020").

## 2.6 Weaviate Architecture

Weaviate is an open-source vector database written in Go. Key concepts:

**Collections** (previously called "classes") — like a table in SQL. We have one collection: `SportDocument`.

**Schema** — defines the properties of documents in a collection:
```python
{
    "content": "text",       # the chunk text
    "doc_type": "text",      # player, team, game, etc.
    "entity_name": "text",   # Stephen Curry, Warriors, etc.
    "section": "text",       # which ## heading
    "season": "text",        # 2022-23
    "source_file": "text",   # path to markdown file
    "content_hash": "text",  # MD5 for change detection
}
```

**Vectors** — stored alongside each object. We use `NONE` vectorizer (we provide our own vectors computed outside Weaviate using sentence-transformers).

**Weaviate Modules** — pluggable components for vectorization (text2vec-openai, text2vec-cohere, etc.). We skip these and provide vectors directly, giving us more control.

## 2.7 Querying Weaviate

Weaviate's Python v4 client uses a builder pattern:

```python
# Hybrid search
response = collection.query.hybrid(
    query="best point guard in NBA history",
    vector=query_embedding,      # dense vector
    alpha=0.75,                  # weight for dense vs keyword
    limit=10,
    return_metadata=MetadataQuery(score=True),
)

# Filtered search (only player documents)
response = collection.query.hybrid(
    query="Stephen Curry stats",
    filters=Filter.by_property("entity_name").equal("Stephen Curry"),
    limit=5,
)
```

## 2.8 Incremental Indexing with MD5 Hashing

A naive approach re-indexes all documents every time you run ingestion. That's slow and wastes computation. Our approach:

1. When indexing a file, compute its **MD5 hash** and store it in Weaviate as a property
2. Next time the ingestion runs, compute the current MD5 of the file
3. If hashes match → file unchanged → skip
4. If hashes differ → delete all chunks from that file → re-chunk and re-index
5. If file is new → chunk and index

This means re-running the ingestion is O(changed files) not O(all files) — crucial when you have hundreds of markdown documents.

---

# Chapter 3: Embeddings — How Machines Read Text

## 3.1 The Core Problem: Text Is Not Numbers

Machine learning models work on numbers. Text is not numbers. The question is: how do you convert words and sentences into numbers in a way that preserves meaning?

Early approaches were primitive:
- **One-hot encoding** — a vector with a 1 at the position of each word in the vocabulary. "cat" → [0,0,1,0,0...]. These are enormous and carry no semantic information.
- **TF-IDF** — better, but still a sparse representation with no understanding of meaning.

## 3.2 Word2Vec and the Embedding Breakthrough

In 2013, Google researchers discovered that you could train a shallow neural network on a simple task ("predict the next word" or "predict surrounding words") and the hidden layer weights would encode surprising semantic relationships.

The result: vectors where **semantic relationships become geometric relationships**.

Famous examples:
- `king - man + woman ≈ queen`
- `Paris - France + Germany ≈ Berlin`

Words with similar meanings ended up with similar vectors. This is because words that appear in similar contexts have similar meanings — "cat" and "dog" both appear near "pet", "food", "fur" — so their vectors converge.

## 3.3 Sentence Transformers

Word2Vec gives word-level embeddings. For RAG, we need **sentence or paragraph-level embeddings** that capture the meaning of entire passages, not just individual words.

**Sentence Transformers** (the library we use) fine-tune BERT-family models specifically for semantic similarity tasks. The model `all-MiniLM-L6-v2` we use:
- Is based on a 6-layer miniaturized BERT
- Was trained on over 1 billion sentence pairs
- Produces **384-dimensional** vectors
- Runs fast — important for ingesting thousands of chunks

The output for "Stephen Curry won 4 championships with Golden State" is a single vector of 384 floats that encodes the meaning of that entire sentence.

## 3.4 Cross-Encoders for Reranking

There are two types of transformer-based models for text similarity:

**Bi-encoders** (like all-MiniLM-L6-v2):
- Encode the query and document *independently* into vectors
- Similarity = cosine distance between the two vectors
- Fast: compute document embeddings once, store them, compare at query time
- Good for first-stage retrieval over millions of documents

**Cross-encoders** (like ms-marco-MiniLM-L-6-v2):
- Take *both* the query and document as input simultaneously
- The model can attend to interactions between query and document tokens
- Much more accurate at judging relevance
- Slow: must re-process every (query, document) pair at query time
- Used for **reranking** a small set of candidates (e.g., top 20 → keep top 5)

Our RAG pipeline uses both:
1. Bi-encoder (all-MiniLM-L6-v2) → hybrid search → top 20 candidates (fast)
2. Cross-encoder (ms-marco-MiniLM-L-6-v2) → rerank → top 5 (accurate)

This two-stage approach gives you the speed of bi-encoders for initial retrieval with the accuracy of cross-encoders for final ranking.

## 3.5 Why 384 Dimensions?

More dimensions = more expressive power, but also:
- More storage (each float is 4 bytes; 1M vectors × 384 dims = ~1.5 GB)
- Slower search (distance calculations in higher dimensions cost more)
- Suffers from the **curse of dimensionality** (distances become less meaningful at very high dims)

`all-MiniLM-L6-v2` at 384 dimensions is a sweet spot — small enough to be fast, large enough to capture nuanced meaning. OpenAI's `text-embedding-ada-002` uses 1536 dimensions for greater quality at higher cost.

---

# Chapter 4: Retrieval-Augmented Generation (RAG)

## 4.1 The Problem RAG Solves

Large language models like GPT-4 or Llama 3 are trained on huge amounts of text up to a cutoff date. They have broad knowledge but two critical problems:

1. **Knowledge cutoff** — they don't know about events after training ended
2. **Hallucination** — when they don't know something, they often make up a plausible-sounding but wrong answer
3. **No private/domain knowledge** — they weren't trained on your specific documents, database, or proprietary data

You could fine-tune an LLM on your data, but fine-tuning is expensive, slow, and the model still tends to hallucinate facts from training data rather than reliably retrieving exact numbers.

**RAG** solves this by giving the LLM the relevant information at query time, injecting it directly into the prompt. The LLM's job shifts from "remember this fact" to "read these passages and answer the question." This is more reliable because:
- The answer is grounded in specific retrieved text
- You can show users the sources
- Updating knowledge means updating your document store, not retraining a model

## 4.2 The RAG Pipeline

A basic RAG system has two phases:

### Indexing Phase (done once / on data change)
```
Raw documents (PDFs, markdown, web pages)
    ↓
Chunking (split into manageable pieces)
    ↓
Embedding (each chunk → vector)
    ↓
Store in vector database
```

### Query Phase (done at query time)
```
User query
    ↓
Embed query → query vector
    ↓
Vector similarity search → top-K relevant chunks
    ↓
Inject chunks into LLM prompt
    ↓
LLM generates answer grounded in retrieved context
    ↓
Return answer + sources to user
```

## 4.3 Chunking Strategies

How you split documents dramatically affects retrieval quality. Poor chunking = poor retrieval = bad answers.

**Fixed-size chunking** — split every N tokens or characters:
- Simple to implement
- Often cuts sentences or ideas in the middle
- Good as a baseline but rarely optimal

**Sentence-level chunking** — split on sentence boundaries:
- Preserves grammatical units
- Problem: a single sentence often lacks context

**Paragraph-level chunking** — split on blank lines:
- Usually the right granularity for prose
- Risk: some paragraphs are very short (one-liners) or very long

**Section-aware chunking** (what we use) — split on `##` headers in markdown:
- Each chunk = one logical section of a document
- Preserves context within a section
- The section heading is kept with the chunk so it knows "this is about Awards"
- If a section is too long (>380 words), split it further at paragraph boundaries

**Semantic chunking** — use an embedding model to find natural semantic break points:
- Most sophisticated
- Splits where the topic shifts
- Computationally expensive

**The chunk size trade-off:**
- Too small → chunks lack context, retrieval finds fragments that don't answer the question
- Too large → chunks contain multiple topics, a single chunk may drown out the relevant sentence with irrelevant content, LLM has trouble focusing

## 4.4 Retrieval Quality Metrics

When evaluating a RAG system's retrieval:

**Recall@K** — of all relevant documents, what fraction appears in the top-K results?
**Precision@K** — of the top-K results, what fraction is actually relevant?
**MRR (Mean Reciprocal Rank)** — how highly ranked is the first relevant result?
**NDCG (Normalized Discounted Cumulative Gain)** — rewards having relevant docs ranked higher

For our use case (user chat), we care most that at least one highly relevant chunk is in the top-5 returned to the LLM.

## 4.5 The Context Window and Retrieval Budget

LLMs have a **context window** — a limit on how many tokens they can process at once. Modern models support 8K to 2M tokens. Practical limits for good performance are typically 4K–32K.

Your retrieval budget = how many chunks you can afford to send to the LLM. More chunks = more context = better coverage, but:
- Cost increases (API providers charge per token)
- Latency increases
- "Lost in the middle" problem — LLMs struggle to use information buried in the middle of a long context

We send the top 5 chunks after reranking. That's enough to answer most NBA questions while keeping prompts tight.

## 4.6 Grounding and Hallucination Reduction

The most important benefit of RAG is **grounding** — forcing the LLM to base its answer on retrieved text rather than its training memory.

In our system prompt we tell the LLM:
- Answer based on the provided context
- If the context doesn't contain the answer, say so
- Don't invent statistics or facts

This dramatically reduces hallucinations. The LLM is now a **reader and synthesizer**, not a recall machine.

---

# Chapter 5: Advanced RAG Techniques

## 5.1 The Naive RAG Problem

Naive RAG (embed → search → prompt) has known failure modes:

- **Query-document mismatch**: the user's question phrasing doesn't match how the answer is phrased in the document
- **Missing context**: a chunk is retrieved but lacks the surrounding context needed to understand it
- **Irrelevant retrieval**: top-K results are topically adjacent but don't actually answer the question
- **Multi-hop questions**: the answer requires combining information from multiple documents

Advanced RAG addresses these with a suite of techniques.

## 5.2 Query Transformation

The idea: don't search with the raw user query — transform it first.

**Query Expansion / HyDE (Hypothetical Document Embeddings)**
Instead of embedding the question, generate a *hypothetical answer* using the LLM, then embed that:

```
User: "What year did LeBron win his first MVP?"
HyDE: LLM generates: "LeBron James won his first MVP award in the 2008-09 season with the Cleveland Cavaliers, averaging 28.4 points..."
→ Embed this hypothetical answer → search
```

The hypothetical answer is in the same linguistic style as the actual document, so it matches better.

**Query Rewriting**
Ask the LLM to rewrite the user's question into a better search query before retrieval.

**Multi-Query Retrieval**
Generate multiple versions of the query and run them all, then deduplicate results. Covers different phrasings of the same intent.

**Step-Back Prompting**
For specific questions, first ask a more abstract version:
- Specific: "What was Curry's PPG in 2015-16?"
- Step-back: "What are Stephen Curry's career highlights?" → broader context → more relevant docs retrieved

## 5.3 Reranking

We covered this in Chapter 3. The pattern is:

1. **First-stage retrieval** — fast approximate search, returns top 20–50 candidates
2. **Reranking** — slower but more accurate cross-encoder scores all candidates against the query
3. Keep top 5 for the LLM

Reranking is one of the highest-ROI improvements to a RAG system. It's cheap to add and significantly improves precision.

## 5.4 Hybrid Retrieval (Dense + Sparse)

We covered this in Chapter 2. The key insight bears repeating: BM25 and vector search have complementary strengths:

- BM25 excels with rare/specific terms (names, numbers, proper nouns)
- Vector search excels with semantic/conceptual queries

Hybrid search with RRF fusion consistently outperforms either alone, especially in domains like sports where exact names matter but conceptual understanding also matters.

## 5.5 Contextual Retrieval (Prepending Context)

Anthropic released research showing that prepending a short description of the full document to each chunk before embedding significantly improves retrieval.

Without context: *"He averaged 30.1 points per game and shot 50% from the field."*
With context: *"This chunk is from the player profile of LeBron James (Cleveland Cavaliers, 2017-18 season). He averaged 30.1 points per game..."*

The added context helps the embedding model produce a more specific vector. We implement a version of this by prepending the document title and entity name to every chunk.

## 5.6 Two-Stage (Graph + Vector) Retrieval

This is what we built in SportMind. Instead of a single vector search, we run two retrieval stages from different sources:

**Stage 1: Structured retrieval from Neo4j**
- For fact-based questions, query the graph database for exact data
- Returns numbers, records, award lists — no hallucination possible
- Fast and precise: `MATCH (p:Player {name: "LeBron James"}) RETURN p.career_pts_avg`

**Stage 2: Semantic retrieval from Weaviate**
- Search the vector store for narrative context, analysis, biographical info
- Returns rich text that explains *why* and *how*, not just *what*

**Fusion**: inject both into the LLM prompt together:
```
Graph facts: LeBron James, career PPG: 27.1, 4 championships
Vector chunks: [5 most relevant passage excerpts]
```

The LLM synthesizes a complete answer using exact facts from the graph and narrative context from the vector store. This is called **GraphRAG** (graph-augmented RAG) and is a significant improvement over pure vector RAG for structured domains.

## 5.7 Intent Classification

Before retrieval, classify the user's intent to route the query to the right systems:

| Intent | What to do |
|---|---|
| Stat lookup | Query Neo4j first, minimal vector search needed |
| Prediction | Run ML model, include its output in the prompt |
| Comparison | Query Neo4j for both entities, vector search for analysis |
| Narrative/story | Vector search dominant, minimal graph needed |
| Custom docs | Only search custom KB collection |

We implement intent classification with **regex patterns** rather than an LLM call. This is faster (no extra API call) and reliable enough for well-defined intent categories. The cost is lower flexibility — you must anticipate intent categories in advance.

## 5.8 Source Filtering

After the LLM generates its answer, not all retrieved sources are actually relevant to the response. Showing irrelevant sources confuses users and makes the system look unreliable.

We filter sources by checking whether the entity name from each source chunk appears somewhere in the LLM's final answer. Sources whose entity names aren't mentioned get filtered out. This is a simple heuristic but effective in practice.

## 5.9 Streaming Responses

Rather than waiting for the complete LLM response and sending it all at once, we **stream tokens** as they're generated:

- WebSocket sends `{type: "token", data: "Stephen"}` → `{type: "token", data: " Curry"}` → ...
- Frontend appends each token to the displayed text in real-time
- User sees the answer "typing out" rather than waiting for a blank screen

This dramatically improves perceived responsiveness. Users feel the system is thinking, rather than frozen. For a 200-word answer at 50 tokens/sec, streaming means the user starts reading within 100ms instead of waiting 4 seconds.

## 5.10 Response Caching

Not every query is unique. "Who is the NBA's all-time leading scorer?" will be asked many times. Re-running the full RAG pipeline (embed query + vector search + Neo4j query + LLM call) every time is wasteful.

We use an **LRU (Least Recently Used) cache** keyed on the user query string. Cache hits return instantly with no API cost. The cache holds up to 100 queries; the oldest entries are evicted when it fills up.

A more sophisticated approach would use **semantic caching** — cache based on query *embedding* similarity, so "Who leads in career scoring?" hits the same cache entry as "Who has scored the most points in NBA history?"

---

# Chapter 6: Large Language Models & Prompting

## 6.1 What Is a Large Language Model?

LLMs are deep neural networks (specifically Transformer architectures) trained on vast amounts of text to predict the next token given a sequence of tokens. Through this simple objective at enormous scale, they develop emergent capabilities: reasoning, instruction following, code generation, translation, summarization.

**Tokens** are the fundamental unit — not words, but subword pieces. "basketball" might be one token; "championships" might be split into "champion" + "ships". On average, 1 token ≈ 0.75 words for English text.

**The Transformer** — the architecture behind all modern LLMs:
- **Self-attention**: every token attends to every other token in the context, learning which parts are relevant to each other
- **Multi-head attention**: multiple attention patterns run in parallel, capturing different types of relationships
- **Feed-forward layers**: after attention, each position is processed through a small neural network
- **Layer normalization and residual connections**: make deep networks trainable

The model is trained by feeding it text, masking the last token, predicting it, and backpropagating the error. This happens billions of times across trillions of tokens.

## 6.2 The Models We Use

**Groq** hosts open-source models on specialized hardware (LPUs — Language Processing Units) that run inference extremely fast.

- `llama-3.3-70b-versatile` — Meta's Llama 3.3, 70 billion parameters. Strong reasoning, following complex instructions, producing structured output. Our primary model.
- `llama-3.1-8b-instant` — 8 billion parameters. Faster, less capable, used as fallback when the 70B hits rate limits.

**Google Gemini**:
- `gemini-2.5-flash` — Google's efficient model, good speed/quality tradeoff. Third in our fallback chain.
- `gemini-3-27b-it` — Instruction-tuned, used last.

**Rate limits**: API providers limit how many tokens you can process per minute (TPM) and per day. Our fallback system automatically rotates models when limits are hit, keeping the chat online even under heavy use.

## 6.3 Prompt Engineering

The quality of an LLM's output is highly dependent on how you frame the input. This is called **prompt engineering**.

**System prompt** — sets the model's role, behavior, and constraints. Processed once per conversation:
```
You are SportMind, an expert NBA analytics assistant.
Answer questions based on the provided context only.
If the context doesn't contain the answer, say "I don't have that information."
Use specific stats and cite your sources.
Never invent statistics.
```

**User prompt** — the actual query, plus injected context:
```
Context from knowledge base:
[chunk 1: Stephen Curry bio...]
[chunk 2: 2015-16 season stats...]
[chunk 3: MVP award history...]

Graph data:
name: Stephen Curry | mvp_count: 2 | career_ppg: 24.8

User question: How many MVP awards has Stephen Curry won?
```

**Few-shot prompting** — include examples of good input/output pairs in the prompt:
```
Example: Q: "Who won MVP in 2016?" A: "Stephen Curry won the 2015-16 MVP..."
Example: Q: "Best scorer?" A: "LeBron James leads in career scoring..."
Now answer: Q: "Who has the most championships?"
```

**Chain-of-thought prompting** — instruct the model to reason step by step:
```
Think through this step by step before giving your final answer.
```
This activates the model's reasoning capabilities and reduces errors on complex questions.

## 6.4 Temperature and Sampling

LLMs don't just produce one fixed output — they produce a probability distribution over possible next tokens. **Temperature** controls randomness:

- `temperature = 0.0` → always pick the most probable token (deterministic, factual, repetitive)
- `temperature = 0.7` → balanced (default, good for most uses)
- `temperature = 1.0+` → more random, creative, sometimes incoherent

For a factual QA system like SportMind, we use low temperature (0.1–0.3) to get reliable, consistent answers. For creative writing, higher temperatures produce more variety.

## 6.5 Instruction Tuning and RLHF

Raw pre-trained models are good at continuing text but not at following instructions. Two training steps turn them into useful assistants:

**Instruction tuning (Supervised Fine-Tuning / SFT)** — fine-tune on thousands of (instruction, good response) pairs. The model learns to answer questions, follow directions, be helpful.

**RLHF (Reinforcement Learning from Human Feedback)** — human raters compare model outputs and rank them. A reward model learns these preferences, then the LLM is trained to maximize reward via RL. This is what makes models like ChatGPT significantly more helpful and safe than base models.

## 6.6 Context Window and Long-Context Challenges

As of 2024-2025, LLMs support context windows from 8K to 1M+ tokens. But longer context has challenges:

**Lost in the middle**: research shows LLMs are better at using information at the start or end of the context. Important information buried in the middle of a long context is sometimes ignored. This is why we send only top-5 chunks, not top-20.

**Cost**: API providers charge per input token. Sending 100K tokens per query gets expensive fast.

**Latency**: more input = more time to process before the first output token appears.

---

# Chapter 7: Machine Learning Models Used

## 7.1 XGBoost — Win Probability Model

**What is XGBoost?**

XGBoost (eXtreme Gradient Boosting) is an ensemble method based on **gradient boosted decision trees**. It's consistently one of the best-performing algorithms on tabular data — the kind of structured, row-column data we have for basketball games.

**Decision Trees:**
A single decision tree makes predictions by asking a series of yes/no questions about features:
```
Is home team's L10 win rate > 0.6?
    Yes → Is rest differential > 1?
        Yes → Predict: home wins (80%)
        No → Predict: home wins (65%)
    No → Predict: away wins (55%)
```
Single trees are weak and overfit easily.

**Boosting:**
Instead of one tree, build many trees sequentially. Each new tree focuses on the samples the previous trees got wrong. The final prediction is the weighted sum of all trees:

```
prediction = tree1(x) + tree2(x) + tree3(x) + ... + tree_n(x)
```

Each tree corrects the residual errors of the combined ensemble so far.

**Gradient in Gradient Boosting:**
"Gradient" refers to fitting each new tree on the *gradient of the loss function* — essentially, each tree is trained to predict what direction the ensemble needs to move to reduce error. It's gradient descent, but in function space.

**XGBoost improvements over vanilla GBM:**
- Regularization (L1 and L2) to prevent overfitting
- Tree pruning (removes branches that don't improve the score)
- Column subsampling (only uses a random subset of features per tree — like Random Forests)
- Efficient handling of sparse data and missing values
- Parallelized tree construction

**Hyperparameters we tuned:**
- `n_estimators` — number of trees (more = potentially better but slower)
- `max_depth` — max depth per tree (deeper = more complex = more overfit risk)
- `learning_rate` — how much weight each new tree has (lower = more trees needed but better generalization)
- `subsample` — fraction of training samples used per tree (reduces overfitting)

## 7.2 Feature Selection

We start with 32 candidate features. Too many features can cause overfitting and make the model less generalizable. We apply two pruning stages:

**Stage 1: Pearson Correlation Pruning**

If two features are highly correlated (e.g., `home_l5_win_rate` and `home_l10_win_rate` often move together), they carry redundant information. We compute the correlation between every pair of features, and when `|r| > 0.88`, we drop the feature with the lower XGBoost importance score.

**Stage 2: XGBoost Gain-Based Pruning**

After an initial fit, XGBoost scores each feature by its total **gain** — how much each feature improves the quality of splits across all trees. Features with gain < 0.8% of the maximum gain provide negligible predictive value and are removed.

This two-stage approach keeps the model lean and interpretable.

## 7.3 Cross-Validation with Temporal Folds

For time-series data (like sports games), random cross-validation is **wrong**. If you randomly split games into train/test, you'd train on 2022 games to predict 2018 games — data leakage that makes results look better than they are.

**Expanding window cross-validation:**
- Fold 1: Train on 2013-17 → Test on 2017-18
- Fold 2: Train on 2013-18 → Test on 2018-19
- Fold 3: Train on 2013-19 → Test on 2019-21
- Fold 4: Train on 2013-21 → Test on 2021-22
- Final test: Train on 2013-22 → Test on 2022-23

Each fold is strictly in time order — we never use future data to predict the past. The CV AUC is the average across all 4 folds.

## 7.4 Isotonic Regression Calibration

A model that predicts 70% win probability should win about 70% of the time in reality. A model that is **well-calibrated** means its predicted probabilities match actual frequencies.

Raw XGBoost probabilities are often miscalibrated — the model might output extreme values (0.9 or 0.1) more often than warranted.

**Calibration:**
- Take the trained XGBoost model
- On a validation set, collect (predicted_probability, actual_outcome) pairs
- Fit an **isotonic regression** (a monotonically increasing step function) that maps raw probabilities to calibrated probabilities
- At prediction time: raw_prob → isotonic regression → calibrated_prob

Isotonic regression is non-parametric (no assumed shape) and monotonic (if the model predicts A > B before calibration, it predicts calibrated_A > calibrated_B after). It's more flexible than Platt Scaling (logistic sigmoid) for complex distributions.

## 7.5 EWMA — Player Forecast Model

**What is EWMA?**

Exponentially Weighted Moving Average (EWMA) is a time-series forecasting method that gives more weight to recent observations:

```
EWMA_t = alpha * x_t + (1 - alpha) * EWMA_{t-1}
```

Where:
- `x_t` = current observation (e.g., points scored in today's game)
- `alpha` = smoothing factor (0 to 1)
- `EWMA_t` = new estimate

High alpha (e.g., 0.5) → reacts quickly to recent games, more volatile
Low alpha (e.g., 0.05) → slow to change, smoother, relies more on history

**Why EWMA for player forecasting?**

Players have form (hot streaks, slumps), injuries, role changes, age-related decline. EWMA naturally captures all of these because it continuously updates based on the most recent game logs. More complex models (ARIMA, Prophet, LSTM) require much more data and tuning for marginally better results on a per-game forecasting task.

**Per-player alpha calibration:**

Different players have different volatility patterns. A player with consistent 25-point games needs a different alpha than a player who alternates between 10 and 40 points. We test 10 alpha values (0.05 to 0.50) and pick the one that minimizes mean squared one-step-ahead prediction error on that player's training history.

**What the model stores:**
```python
{
    "alpha": 0.20,               # calibrated smoothing factor
    "overall_mean": 26.6,        # career average
    "recent_mean": 28.4,         # last 20 games average
    "l5_mean": 30.1,             # last 5 games average
    "monthly_avg": {10: 25.1, 11: 26.3, ...},  # seasonal pattern
    "slope": +0.15,              # trend direction (linear fit on last 20)
    "p10": 15.0,                 # 10th percentile
    "p25": 20.0,                 # 25th percentile (confidence band lower)
    "p75": 33.0,                 # 75th percentile (confidence band upper)
    "p90": 38.0,                 # 90th percentile
    "history": [28, 31, 25, ...] # last 60 game values for inference
}
```

**Generating forecasts:**

```python
ewma = history[-1]  # start from last known value
for game in range(periods):
    predicted = ewma  # next prediction is current EWMA
    ewma = alpha * predicted + (1 - alpha) * ewma  # update (trend drift)
    upper = predicted + std
    lower = predicted - std
```

---

# Chapter 8: Docker — Containers & Infrastructure

## 8.1 The "Works on My Machine" Problem

You've built an application. It works perfectly on your development machine. You send it to a colleague. They try to run it. It crashes. Why?

- Different Python version (3.11 vs 3.9)
- Different OS (Windows vs Linux)
- Different library versions installed system-wide
- Missing environment variables
- Different file paths

This is the classic **"works on my machine"** problem. It's one of the biggest pain points in software deployment. Docker solves it.

## 8.2 What Is a Container?

A **container** is a lightweight, isolated process that includes:
- The application code
- All dependencies (libraries, runtime, system packages)
- Environment variables
- A minimal OS filesystem

Crucially, containers are **isolated** from the host system and from each other — they can't see each other's files, processes, or network by default. But they share the **host OS kernel**, which is why they're much lighter than virtual machines.

## 8.3 Containers vs Virtual Machines

| | Virtual Machine | Container |
|---|---|---|
| Includes | Full guest OS | Only app + dependencies |
| Startup time | Minutes | Seconds or milliseconds |
| Size | Gigabytes | Megabytes to ~1 GB |
| Isolation | Complete (separate kernel) | Process-level (shared kernel) |
| Overhead | High (hypervisor + guest OS) | Low (just the process) |
| Portability | Good | Excellent |

VMs run a complete operating system inside the host. Containers share the host kernel and only package what's different. This makes containers much faster and smaller.

## 8.4 Docker Architecture

**Docker Engine** — the daemon running on your machine that manages containers and images. When you run `docker run`, you're talking to this daemon.

**Docker Image** — a read-only template containing your application and all its dependencies. Think of it as a blueprint or a snapshot. Images are **layered** — each instruction in a Dockerfile adds a layer on top of the previous one. Layers are cached, so rebuilds only redo changed layers.

**Docker Container** — a running instance of an image. You can run many containers from the same image. Containers are ephemeral — when stopped, any data written inside them is lost (unless stored in a volume).

**Docker Registry** — a repository for images. Docker Hub is the public registry. When you run `docker pull neo4j:5.15`, Docker downloads the image from Docker Hub.

## 8.5 Dockerfile

A Dockerfile is a text file containing instructions to build an image:

```dockerfile
# Start from an official Python 3.11 slim image (base layer)
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system packages (each RUN = new layer)
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements file first (separate layer — cached unless requirements change)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8000

# Command to run when container starts
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Layer caching** is important for build speed. Expensive steps (pip install) should come before frequently changing files (application code). That way, changing a source file only rebuilds the layers after the pip install layer.

**Multi-stage builds** — use multiple FROM instructions to keep the final image small:
```dockerfile
# Stage 1: builder
FROM python:3.11 AS builder
RUN pip install --user -r requirements.txt

# Stage 2: final image (no build tools)
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY . .
CMD ["uvicorn", "backend.main:app", ...]
```

## 8.6 Docker Compose

Running a single container is simple. But SportMind needs:
- A FastAPI backend container
- A React frontend container
- A Neo4j container
- A Weaviate container

Managing 4 containers manually (start order, networking, volumes) is tedious. **Docker Compose** defines all services in a single YAML file:

```yaml
version: "3.9"

services:
  neo4j:
    image: neo4j:5.15
    ports:
      - "7474:7474"    # HTTP browser
      - "7687:7687"    # Bolt protocol
    environment:
      - NEO4J_AUTH=neo4j/sportmind123
    volumes:
      - neo4j_data:/data   # persist data across restarts

  weaviate:
    image: semitechnologies/weaviate:1.24.1
    ports:
      - "8080:8080"
    environment:
      - DEFAULT_VECTORIZER_MODULE=none
      - PERSISTENCE_DATA_PATH=/var/lib/weaviate
    volumes:
      - weaviate_data:/var/lib/weaviate

  backend:
    build: .           # build from Dockerfile in current directory
    ports:
      - "8000:8000"
    depends_on:
      - neo4j
      - weaviate
    env_file: .env     # load environment variables from .env file

  frontend:
    build: ./frontend
    ports:
      - "3000:80"      # Nginx in container on 80, exposed on 3000
    depends_on:
      - backend

volumes:
  neo4j_data:
  weaviate_data:
```

Commands:
```bash
docker compose up -d        # start all services (detached mode)
docker compose down         # stop all services
docker compose logs -f      # stream all logs
docker compose ps           # show running services
docker compose build        # rebuild images
```

## 8.7 Volumes — Persisting Data

By default, data written inside a container disappears when the container is removed. For databases, this is catastrophic. **Volumes** are Docker-managed directories that live outside containers and are mounted into them:

```yaml
volumes:
  neo4j_data:/data
```

This creates a volume named `neo4j_data` on the host (managed by Docker, stored in `/var/lib/docker/volumes/` on Linux) and mounts it at `/data` inside the container. When the container is removed and replaced with a new one, the data persists.

**Types:**
- **Named volumes** (above) — Docker manages the location, portable, recommended
- **Bind mounts** — mount a specific host directory: `./data:/app/data`

**The path mangling problem we hit:**
When running Docker commands in Git Bash on Windows, forward slashes are converted to Windows paths. The flag `-e PERSISTENCE_DATA_PATH=/var/lib/weaviate` becomes `-e PERSISTENCE_DATA_PATH=C:/Program Files/Git/var/lib/weaviate` inside the container — completely wrong. The fix is to use PowerShell for Docker commands on Windows, where this conversion doesn't happen.

## 8.8 Networking

By default, Docker Compose puts all services in the same **network**. Containers can reach each other by **service name**:
- The backend connects to Neo4j at `bolt://neo4j:7687` (not `localhost:7687`)
- The backend connects to Weaviate at `http://weaviate:8080`

From outside (your browser), you access through the published ports: `localhost:8000`, `localhost:7474`, etc.

```
Your Browser → localhost:5173 → frontend container → localhost:8000
                                                       → backend container → neo4j container (bolt://neo4j:7687)
                                                                          → weaviate container (http://weaviate:8080)
```

## 8.9 Common Docker Commands

```bash
# Images
docker pull image:tag           # download an image
docker images                   # list local images
docker rmi image:tag            # remove an image
docker build -t name:tag .      # build image from Dockerfile

# Containers
docker run image:tag            # create and start a container
docker run -d image:tag         # run in background (detached)
docker run -p 8000:8000 image   # map host:container port
docker run -e KEY=value image   # set environment variable
docker run -v vol:/path image   # mount volume
docker ps                       # list running containers
docker ps -a                    # list all containers (including stopped)
docker stop container_id        # stop container gracefully
docker rm container_id          # remove stopped container
docker logs container_id        # view container logs
docker logs -f container_id     # stream logs (follow)
docker exec -it container bash  # open shell inside running container

# System cleanup
docker system prune             # remove all stopped containers, unused images
docker volume prune             # remove unused volumes
docker system df                # show disk usage by Docker

# Compose
docker compose up -d
docker compose down
docker compose down -v          # also remove volumes (destroys data!)
docker compose build --no-cache # rebuild ignoring cache
docker compose exec service bash # shell into a compose service
```

## 8.10 The Disk Space Problem We Encountered

Docker stores images, containers, volumes, and build cache on the host machine. The main issues we hit:

**Large images**: Our backend image was initially ~10 GB because `sentence-transformers` depends on PyTorch, and pip defaults to installing the CUDA (GPU) version of PyTorch — a ~2 GB binary. We never needed GPU support. The fix:

```dockerfile
# Install CPU-only PyTorch before sentence-transformers
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install -r requirements.txt
```

This reduced the image from ~10 GB to ~3.4 GB.

**Volume conflicts**: Docker Compose prefixes volume names with the project directory name. A volume named `neo4j_data` in a compose file becomes `sportmind_neo4j_data` — a new, empty volume, not the existing `neo4j_data` with data. Fix:

```yaml
volumes:
  neo4j_data:
    external: true   # use the pre-existing volume, don't create a new one
```

**Build cache**: Each `docker build` run caches intermediate layers in `/var/lib/docker`. After many builds, this can grow to many GB. `docker system prune` clears it.

**Docker Desktop on Windows** stores all Docker data in a virtual disk image (VHDX) at `%APPDATA%\Docker\`. This VHDX grows automatically but doesn't shrink when you delete containers. You must `docker system prune` to reclaim space within the VHDX, or compact the VHDX file itself.

---

# Chapter 9: FastAPI, WebSockets & Async Python

## 9.1 FastAPI

FastAPI is a modern Python web framework for building APIs. Key properties:

**Type annotations → automatic validation:**
```python
@app.get("/stats/player/{name}")
async def player_stats(name: str, season: str | None = None):
    ...
```
FastAPI reads the function signature and automatically:
- Parses path parameters (`name` from the URL)
- Parses optional query parameters (`season` from `?season=2022-23`)
- Validates types (if you expect `int` and get `"abc"`, returns 422 automatically)
- Generates OpenAPI documentation at `/docs` and `/redoc`

**Pydantic models** for request/response validation:
```python
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None
```

**Dependency injection** — FastAPI's DI system allows sharing resources across endpoints:
```python
def get_db():
    db = Database()
    yield db
    db.close()

@app.get("/players")
async def players(db = Depends(get_db)):
    ...
```

## 9.2 Async Python

Python is single-threaded by default — when code makes a network request (e.g., querying Neo4j), it blocks and waits, doing nothing useful. For a web server handling many concurrent users, this is terrible.

**Async/await** (Python's `asyncio`) uses cooperative multitasking:
- When a coroutine hits an `await`, it pauses and yields control to the event loop
- The event loop can run other coroutines while the first one waits
- When the I/O completes (Neo4j responds), the coroutine resumes

```python
async def get_player_stats(name: str):
    # Hit an await point → other requests can be served while waiting for Neo4j
    result = await neo4j_session.run("MATCH (p:Player {name: $n}) RETURN p", n=name)
    return result
```

Without async, one slow database query blocks the entire server. With async, the server can handle hundreds of concurrent queries — each waiting for their own I/O without blocking others.

**Important**: async only helps with I/O-bound operations (network, disk). CPU-bound operations (like running a ML model) still block the event loop and should be offloaded to a thread pool with `asyncio.run_in_executor`.

## 9.3 WebSockets

HTTP is request-response: client sends a request, server sends one response, connection closes. This model doesn't fit streaming AI responses well.

**WebSockets** provide a persistent, full-duplex connection. Both sides can send messages at any time without a new HTTP request.

**Lifecycle:**
1. Client sends an HTTP request with `Upgrade: websocket` header
2. Server responds with `101 Switching Protocols`
3. Connection is now a WebSocket — raw TCP, not HTTP
4. Either side can send frames at any time
5. Either side can close the connection

**Our chat protocol:**
```
Client → Server: {"query": "Who is the best scorer?"}
Server → Client: {"type": "thinking"}
Server → Client: {"type": "token", "data": "LeBron"}
Server → Client: {"type": "token", "data": " James"}
Server → Client: {"type": "token", "data": " is"}
...
Server → Client: {"type": "done", "data": "full_answer", "sources": [...]}
```

In FastAPI:
```python
@app.websocket("/chat")
async def chat(ws: WebSocket):
    await ws.accept()
    while True:
        data = await ws.receive_json()
        query = data["query"]

        # Stream tokens as LLM generates them
        async for token in llm.stream(query):
            await ws.send_json({"type": "token", "data": token})

        await ws.send_json({"type": "done", "data": full_response})
```

## 9.4 CORS — Cross-Origin Resource Sharing

Browsers enforce the **same-origin policy** — JavaScript on `http://localhost:5173` (the React app) cannot make requests to `http://localhost:8000` (the FastAPI server) unless the server explicitly allows it.

**CORS** (Cross-Origin Resource Sharing) is the mechanism servers use to say "these other origins are allowed to talk to me." The server adds HTTP headers to responses:

```
Access-Control-Allow-Origin: http://localhost:5173
Access-Control-Allow-Methods: GET, POST, DELETE, PUT
Access-Control-Allow-Headers: *
```

In FastAPI:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

In development, it's tempting to use `allow_origins=["*"]` (allow all origins). This is dangerous in production — it allows any website to make requests to your API, enabling cross-site request forgery attacks. We restrict to only known frontend origins.

## 9.5 Lifespan Events

FastAPI allows running code on startup and shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: runs before accepting requests
    build_agent()      # warm up the RAG agent
    print("Server ready")

    yield              # server is now running

    # Shutdown: runs after accepting no more requests
    close_driver()     # close Neo4j connection pool
    close_client()     # close Weaviate connection

app = FastAPI(lifespan=lifespan)
```

The warm-up on startup is important — loading the sentence-transformer model for the first time takes a few seconds. Better to do this before the first user request than to make the first user wait.

---

# Chapter 10: How Everything Connects in SportMind

## 10.1 The Full Data Journey

Let's trace what happens when a user asks: **"What was Stephen Curry's PPG in his MVP season?"**

### Indexing (happened before the user asked)

1. `fetch_players.py` called nba_api and got Curry's season stats including 2015-16 PPG = 30.1
2. `generate_md_files.py` generated `knowledge_base/players/stephen_curry.md` with a stats table
3. `load_weaviate.py` chunked this file by sections, embedded each chunk with all-MiniLM-L6-v2, stored vectors + metadata in Weaviate
4. `load_neo4j.py` created a `PlayerSeasonStats` node `{season: "2015-16", pts: 30.1}` linked to Curry's `Player` node
5. `train_player_forecast.py` trained an EWMA model for Curry's PTS (player_201939_pts.pkl)

### Query time

1. User types the question in the React chat interface
2. **Frontend** sends JSON over WebSocket: `{"query": "What was Stephen Curry's PPG in his MVP season?"}`
3. **Backend** (`backend/routes/chat.py`) receives the message
4. Checks the LRU cache — no match
5. **RAG Orchestrator** (`rag/orchestrator.py`) takes over:
   a. **Intent classification**: matches "PPG" and "season" → intent = `stat`
   b. **Graph query** (`rag/graph_tool.py`): extracts "Stephen Curry" → runs Cypher against Neo4j → returns: `name: Stephen Curry | season: 2015-16 | pts: 30.1 | mvp: 1`
   c. **Enrich query**: appends "Stephen Curry" to vector search query
   d. **Vector search** (`rag/vector_tool.py`):
      - Embeds "What was Stephen Curry's PPG in his MVP season? Stephen Curry"
      - Runs hybrid search against Weaviate (BM25 + dense, alpha=0.75)
      - Gets top 20 candidates
      - Cross-encoder reranks → top 5 chunks (excerpts from Curry's bio, 2015-16 stats section, MVP award section)
   e. **LLM synthesis**: builds prompt with graph facts + top 5 chunks → calls Groq Llama-3.3-70B
   f. LLM streams back: "Stephen Curry averaged **30.1 points per game** in his historic 2015-16 season, earning him his second consecutive MVP award..."
6. **Streaming**: each token is sent to the frontend via WebSocket as `{"type": "token", "data": "Stephen"}`
7. **Frontend** appends each token to the displayed message in real time
8. When done, `{"type": "done", "sources": [...]}` is sent, frontend shows source cards
9. Response + sources are stored in `localStorage` for chat history

## 10.2 Why This Architecture Works

**Graph + Vector hybrid gives the best of both worlds:**
- Neo4j: exact stats, never hallucinates numbers
- Weaviate: rich narrative context, historical analysis, comparisons

**LLM as synthesizer, not oracle:**
- The LLM never needs to "remember" facts
- It reads retrieved context and writes a coherent answer in natural language
- Hallucinations are reduced because the right information is in the prompt

**Streaming for UX:**
- Users start reading within 100–200ms of asking
- Long answers don't create a frozen screen

**Fallback chain for reliability:**
- Four LLM models means the chat stays online even during API rate limits

**Separation of concerns:**
- Ingestion is entirely separate from serving (run it once, re-run as data updates)
- ML training is separate from inference (train once, serve forever until retrained)
- Frontend only talks to FastAPI — it never touches Neo4j or Weaviate directly

## 10.3 The Knowledge Graph as Structured Memory

One way to think about this system: the LLM has no long-term memory. Neo4j is its structured memory — a permanent, queryable store of every NBA fact we've ingested. When someone asks a factual question, we "look it up" from this memory and give it to the LLM rather than relying on the LLM's potentially stale or hallucinated recall.

Weaviate is the narrative memory — all the rich prose, context, and analysis about those facts. The combination is far more powerful than either alone.

## 10.4 The ML Models as Specialized Oracles

The LLM cannot run statistical models or do time-series forecasting. When someone asks "predict LeBron's next 5 games", we:
1. Detect the prediction intent
2. Call `forecast_player_performance("LeBron James", "pts", 5)` — a deterministic computation
3. Inject the ML prediction into the LLM prompt
4. The LLM wraps it in natural language with context

This pattern — **tool use** or **function calling** — is how modern AI systems extend LLM capabilities with deterministic, specialized computation. The LLM is not doing the math; it's presenting the result of math done by a proper ML model.

## 10.5 What Makes This "Production-Quality"

- **Idempotent ingestion**: re-running any ingestion script is safe — MERGE in Neo4j, MD5 hashing in Weaviate
- **Schema constraints + indexes**: Neo4j enforces data integrity and queries are fast
- **Model calibration**: win probabilities are calibrated so 70% really means 70%
- **Temporal cross-validation**: ML models never see future data during training
- **Rate limit handling**: the system stays online under API pressure with automatic fallback
- **Incremental indexing**: updating one file doesn't re-index the entire knowledge base
- **Source filtering**: users see only relevant sources, not every retrieved chunk
- **CORS restriction**: only known origins can access the API
- **Streaming**: perceived responsiveness is excellent regardless of response length

---

*End of learn.md*
