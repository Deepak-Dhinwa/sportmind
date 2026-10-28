# SportMind — NBA Intelligent Analytics Platform

One-page summary: open `poster.html` in a browser.
Start: with Docker Desktop open, `docker start neo4j weaviate`, then `.\run.ps1`. The script starts the API and the frontend only.

An end-to-end NBA analytics system combining a **Knowledge Graph**, **RAG (Retrieval-Augmented Generation)**, and **Machine Learning** to answer natural-language basketball questions, visualize player/team relationships, and predict game outcomes and player performance.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [Features](#features)
5. [Data Pipeline](#data-pipeline)
6. [Knowledge Graph](#knowledge-graph)
7. [RAG Pipeline](#rag-pipeline)
8. [ML Models & Results](#ml-models--results)
9. [Backend API](#backend-api)
10. [Frontend](#frontend)
11. [Project Structure](#project-structure)
12. [Setup & Installation](#setup--installation)
13. [Environment Variables](#environment-variables)
14. [Running the Application](#running-the-application)

---

## Overview

SportMind ingests 10 seasons of NBA data (2013-14 through 2022-23), builds a structured Neo4j knowledge graph and a Weaviate vector store, trains ML forecasting models, and exposes everything through a FastAPI backend with a streaming WebSocket chat interface and a React frontend.

**Data coverage:**
- ~1,400 players with career stats, bios, and awards
- ~12,800 regular season + playoff games
- 94 players with per-game logs for forecasting models
- 6,246 document chunks indexed in the vector store
- 658 EWMA player forecast models (94 players × 7 metrics)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Data Sources                              │
│   nba_api · Basketball-Reference · Wikipedia · LLM-generated     │
└────────────────────────────┬─────────────────────────────────────┘
                             │ ingestion/
                             ▼
                    data/raw/ (JSON)
                    knowledge_base/ (Markdown)
                             │
             ┌───────────────┼───────────────┐
             ▼               ▼               ▼
          Neo4j          Weaviate        ml/models/
      Knowledge Graph   Vector Store    (XGBoost + EWMA)
      (nodes + edges)   (chunks + BM25)  (658 .pkl files)
             │               │               │
             └───────────────┼───────────────┘
                             │
                    ┌────────▼────────┐
                    │  FastAPI Backend │
                    │   (port 8000)    │
                    │                  │
                    │  RAG Orchestrator│
                    │  ├─ Intent class │
                    │  ├─ Graph query  │
                    │  ├─ Vector search│
                    │  ├─ ML predict   │
                    │  └─ LLM synth    │
                    └────────┬────────┘
                             │ WebSocket / REST
                    ┌────────▼────────┐
                    │  React Frontend  │
                    │   (port 5173)    │
                    │  Chat · Stats    │
                    │  Predict · Graph │
                    │  Knowledge       │
                    └─────────────────┘
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, Vite, Axios, react-force-graph-2d, Recharts |
| **Backend API** | FastAPI, Uvicorn, WebSockets |
| **RAG Framework** | LlamaIndex Core |
| **LLM** | Groq (Llama 3.3-70B, Llama 3.1-8B), Google Gemini 2.5 Flash |
| **Vector Store** | Weaviate 1.24 (hybrid BM25 + dense search) |
| **Knowledge Graph** | Neo4j 5.15 |
| **Embeddings** | sentence-transformers `all-MiniLM-L6-v2` (384-dim) |
| **Reranking** | cross-encoder `ms-marco-MiniLM-L-6-v2` |
| **ML (Win)** | XGBoost + isotonic calibration |
| **ML (Player)** | Exponentially Weighted Moving Average (EWMA) |
| **Data Ingestion** | nba_api, pandas, requests |

---

## Features

### Conversational AI Chat
- Streaming WebSocket chat powered by RAG
- Answers questions about players, teams, seasons, awards, championships, and strategies
- Auto-rotates through 4 LLM models on rate-limit or quota exhaustion (Groq × 2 → Gemini × 2)
- In-process LRU cache (100 queries) to avoid redundant LLM calls
- Sources displayed alongside answers

### Player & Team Statistics
- Season-by-season and career stats for ~1,400 players
- Team win/loss records, championships, and rosters by season
- Top scorers leaderboard, award winners (MVP, DPOY, All-NBA, etc.)
- Head-to-head team comparisons and player comparisons

### Win Probability Prediction
- Predict win probability for any home vs. away matchup
- Inputs: teams, rest days, season stage
- 32-feature XGBoost model with isotonic regression calibration
- Outputs calibrated probability with uncertainty awareness

### Player Performance Forecasting
- Multi-step forecast (default: 10 games) for any player
- 7 metrics: PTS, AST, REB, STL, BLK, FG%, MIN
- Per-game prediction with upper/lower confidence bands (p25–p75)
- Trend direction (trending up / stable / trending down)

### Knowledge Graph Visualization
- Interactive force-directed graph (react-force-graph-2d)
- Explore neighborhood of any player or team
- Shows PLAYED_FOR, WON_AWARD, PLAYED_GAME relationships

### Custom Knowledge Base
- Upload `.md` or `.txt` files to extend the knowledge base
- Automatically chunked, embedded, and indexed into Weaviate
- Files can be updated or deleted; re-indexing is incremental (MD5-based)

---

## Data Pipeline

The ingestion pipeline runs in ~12–15 minutes total and is fully idempotent (safe to re-run).

```
python -m ingestion.run_ingestion
```

### Stages

| Step | Script | Output | Time |
|---|---|---|---|
| 1 | `fetch_players.py` | `data/raw/players.json`, `players_stats.json` | ~5-6 min |
| 2 | `fetch_teams.py` | `data/raw/teams.json`, `teams_stats.json` | ~15 sec |
| 3 | `fetch_games.py` | `data/raw/games.json`, `player_gamelogs.json` | ~6-7 min |
| 4 | `fetch_awards.py` | `data/raw/awards.json` | ~10 sec |
| 5 | `generate_md_files.py` | `knowledge_base/players/`, `teams/`, etc. | ~1 min |
| 6 | `load_neo4j.py` | Neo4j graph populated | ~2 min |
| 7 | `load_weaviate.py` | Weaviate collection populated | ~3 min |

### Player Game Logs
Game logs are fetched for the **top 100 players by career games played** (2013–2023). The fetch is incremental — already-cached players are skipped on re-runs.

### Markdown Generation
Each player and team gets a structured markdown file covering:
- Bio (birthdate, height, weight, country, draft info)
- Season-by-season stats table
- Career awards
- Playing style notes and context

### Weaviate Chunking Strategy
- Documents split by `##` section headers
- Max 380 words per chunk
- Document title prepended to every chunk for context
- MD5 hash stored per file — only changed files are re-indexed

---

## Knowledge Graph

**Neo4j** stores the structured relational facts about the NBA.

### Node Types

| Node | Key Properties |
|---|---|
| `Player` | name, position, height, weight, country, draft info, career averages |
| `Team` | name, city, abbreviation, conference, division |
| `Game` | date, season, home/away scores, winner |
| `PlayerSeasonStats` | pts, ast, reb, stl, blk, fg_pct, fg3_pct, games_played |
| `Season` | year |
| `Award` | name, season |
| `Coach` | name, seasons |
| `Venue` | name, city, capacity |

### Relationship Types

| Relationship | Meaning |
|---|---|
| `PLAYED_FOR` | Player → Team (per season) |
| `HAS_SEASON_STATS` | Player → PlayerSeasonStats |
| `PLAYED_GAME` | Team → Game |
| `IN_SEASON` | Game → Season |
| `WON_AWARD` | Player → Award |
| `WON_CHAMPIONSHIP` | Team → Season |
| `COACHED` | Coach → Team |

### Scale
- ~1,400 Player nodes
- 30 Team nodes
- ~12,800 Game nodes
- ~14,000 PlayerSeasonStats nodes
- Unique constraints on all ID fields; indexes on name/date fields

---

## RAG Pipeline

The RAG pipeline is implemented as an **OrchestratedAgent** that routes each query through multiple retrieval sources before synthesizing a response.

### Intent Classification (regex-based, no LLM call)

| Intent | Trigger Keywords |
|---|---|
| `prediction` | predict, win, forecast, next game, will beat |
| `compare` | vs, versus, better than, compare |
| `stat` | points, assists, career, championship, season, award |
| `narrative` | general basketball questions |
| `custom` | matches uploaded custom documents |

### Retrieval Steps

```
User Query
    │
    ▼
1. Intent Classification
    │
    ▼
2. Graph Query (Neo4j)
   └─ Exact facts: stats, awards, records, rosters
    │
    ▼
3. Enrich Query
   └─ Extract entity names from graph result
   └─ Append to vector search query
    │
    ▼
4. Vector Search (Weaviate)
   ├─ General hybrid search (BM25 + dense) on enriched query
   ├─ Entity-filtered search (targeted retrieval for named players/teams)
   └─ Cross-encoder reranking → top 5 chunks
    │
    ▼
5. ML Prediction (if intent == prediction)
   └─ Win probability or player forecast
    │
    ▼
6. Unified LLM Synthesis
   └─ Single prompt: query + graph results + top 5 chunks + ML output
    │
    ▼
7. Source Filtering
   └─ Only show sources actually cited in the answer
```

### LLM Model Roster (with auto-rotation)

| Priority | Model | Provider |
|---|---|---|
| 1 (primary) | `llama-3.3-70b-versatile` | Groq |
| 2 | `llama-3.1-8b-instant` | Groq |
| 3 | `gemini-2.5-flash` | Google |
| 4 | `gemini-3-27b-it` | Google |

Rate limit handling:
- **TPM limit** → sleep briefly, retry same model
- **Daily/quota limit** → rotate to next model
- **All exhausted** → return error to user

---

## ML Models & Results

### Win Probability Model (XGBoost v3)

**Training approach:**
- 4-fold expanding-window cross-validation (no data leakage)
- Training folds: 2013-14 to 2021-22 seasons
- Test set: 2022-23 season
- 32 candidate features → 2-stage feature selection (Pearson correlation pruning + XGBoost gain pruning)
- Hyperparameter grid search: 24 combinations (n_estimators, max_depth, learning_rate, subsample)
- Isotonic regression calibration applied to raw probabilities

**Selected feature categories:**
- Rolling win rates: L5 and L10 windows (home, away, season-to-date)
- Rolling offense/defense: points per game, points allowed, net rating
- Rest-related: rest days, back-to-back flag, rest differential
- Momentum: current win/loss streak
- Head-to-head: directed H2H win rate (this specific home team vs this specific away team at home, last 20 meetings)
- Venue-specific: home team's win rate at home, away team's win rate on road
- Season stage: early (0), mid (1), late (2), playoffs (3)

**Results:**

| Metric | Score |
|---|---|
| CV AUC (4-fold) | 0.6745 |
| Test AUC (2022-23) | 0.6264 |
| Test Accuracy | 61.0% |
| Brier Score (calibrated) | 0.2348 |

> Note: 62–63% AUC is near the theoretical ceiling for box-score-only features without in-game data. Professional sports prediction services using similar features report 58–65% accuracy.

### Player Performance Forecast (EWMA v3)

**Approach:**
- Exponentially Weighted Moving Average per player per metric
- Real game logs only (no synthetic data from season averages)
- Alpha selected from 10 candidates (0.05–0.50) by minimising one-step-ahead MSE on training history
- Holds out 2022-23 season for evaluation
- Minimum 20 training games required to build a model

**Coverage:**
- 94 players with game logs fetched
- 658 models total (94 × 7 metrics, all successful — 0 skipped)

**Per-metric holdout evaluation (2022-23, n=82 players):**

| Metric | MAE | RMSE |
|---|---|---|
| PTS | 5.24 | 6.62 |
| AST | 1.61 | 2.03 |
| REB | 2.15 | 2.71 |
| STL | 0.77 | 0.98 |
| BLK | 0.53 | 0.71 |
| FG_PCT | 0.18 | 0.23 |
| MIN | 4.82 | 6.26 |

**Each model stores:**
- Calibrated alpha, overall mean, recent mean (last 20 games), L5 mean
- Per-month seasonal averages (months 1–12)
- Recent trend slope (linear fit on last 20 games)
- Percentile bands (p10, p25, p75, p90) for confidence intervals
- Rolling history window (last 60 games) for inference

---

## Backend API

The FastAPI server runs on `http://localhost:8000`. Interactive docs at `/docs`.

### WebSocket

| Endpoint | Description |
|---|---|
| `WS /chat` | Streaming RAG chat. Send `{"query": "..."}`, receive `{type: "token", data: "..."}` and `{type: "done", data: "...", sources: [...]}` |

### Stats

| Method | Endpoint | Description |
|---|---|---|
| GET | `/stats/player/{name}` | Player stats, awards, bio. Optional `?season=2022-23` |
| GET | `/stats/team/{name}` | Team record + championships. Optional `?season=` |
| GET | `/stats/team/{name}/roster` | Team roster. Required `?season=2022-23` |
| GET | `/stats/top-scorers` | Top scorers. `?season=2022-23&limit=10` |
| GET | `/stats/champions` | All championship winners |
| GET | `/stats/awards` | Award winners. `?award=Most%20Valuable%20Player&season=` |
| GET | `/stats/compare` | Compare two players. `?player1=&player2=` |
| GET | `/stats/head-to-head` | H2H record. `?team1=&team2=&season=` |

### Graph

| Method | Endpoint | Description |
|---|---|---|
| GET | `/graph/neighborhood/{entity}` | Subgraph for react-force-graph visualization |
| GET | `/graph/overview` | League-wide node overview |

### Predictions

| Method | Endpoint | Description |
|---|---|---|
| GET | `/predict/win` | Win probability. `?home_team=&away_team=&home_rest=2&away_rest=2` |
| GET | `/predict/player` | Player forecast. `?player=&metric=pts&periods=10` |

### Knowledge Base Management

| Method | Endpoint | Description |
|---|---|---|
| GET | `/knowledge/files` | List all custom files |
| POST | `/knowledge/upload` | Upload `.md`/`.txt` (multipart, max 2 MB) |
| PUT | `/knowledge/files/{filename}` | Replace + re-index existing file |
| DELETE | `/knowledge/files/{filename}` | Remove file and its Weaviate chunks |

### System

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/system/info` | ML model counts, KB size, graph node counts, cache state |

---

## Frontend

Built with **React 19 + Vite**. Runs on `http://localhost:5173` in development.

### Layout

Split-pane design: persistent chat on the left, tabbed panels on the right.

### Tabs

| Tab | Component | Description |
|---|---|---|
| Stats | `StatsPanel` | Search players/teams, view season stats, charts |
| Predict | `PredictionPanel` | Win probability + player forecasting UI |
| Graph | `GraphExplorer` | Interactive force-directed knowledge graph |
| Knowledge | `KnowledgePanel` | Upload, list, and delete custom KB documents |

### Chat Features
- Real-time token streaming via WebSocket
- Chat history persisted in `localStorage` (max 60 messages)
- 8 quick-start suggested questions
- Sources panel displayed with each answer

---

## Project Structure

```
sportmind/
├── backend/
│   ├── main.py                 # FastAPI app, CORS, lifespan
│   └── routes/
│       ├── chat.py             # WS /chat — streaming RAG
│       ├── stats.py            # REST stats + graph endpoints
│       └── knowledge.py        # Custom KB CRUD endpoints
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── api/client.js       # Axios + WebSocket helpers
│   │   └── components/
│   │       ├── ChatPanel.jsx
│   │       ├── StatsPanel.jsx
│   │       ├── PredictionPanel.jsx
│   │       ├── GraphExplorer.jsx
│   │       └── KnowledgePanel.jsx
│   ├── package.json
│   └── vite.config.js
├── rag/
│   ├── agent.py                # LLM model roster + rotation
│   ├── orchestrator.py         # Intent → Graph → Vector → ML → LLM
│   ├── graph_tool.py           # Neo4j query wrapper
│   ├── vector_tool.py          # Weaviate hybrid search + reranking
│   ├── weaviate_client.py      # Weaviate singleton
│   ├── prediction_tool.py      # ML prediction bridge
│   └── prompts.py              # System/user prompt templates
├── graph/
│   ├── schema.cypher           # Neo4j constraints + indexes
│   ├── neo4j_client.py         # Driver singleton + query helpers
│   └── queries.py              # Pre-built Cypher queries
├── ml/
│   ├── train_win_probability.py # XGBoost v3 training
│   ├── train_player_forecast.py # EWMA v3 training
│   ├── predictor.py             # Inference functions
│   └── models/                  # Serialized .pkl files
├── ingestion/
│   ├── run_ingestion.py         # Pipeline orchestrator
│   ├── fetch_players.py
│   ├── fetch_teams.py
│   ├── fetch_games.py
│   ├── fetch_awards.py
│   ├── generate_md_files.py
│   ├── generate_game_summaries.py
│   ├── load_neo4j.py
│   ├── load_weaviate.py
│   └── utils.py
├── knowledge_base/
│   ├── players/                 # Player markdown files
│   ├── teams/                   # Team markdown files
│   ├── coaches/
│   ├── games/
│   ├── venues/
│   ├── seasons/
│   ├── wikipedia/
│   └── custom/                  # User-uploaded files
├── data/
│   └── raw/                     # Fetched JSON from nba_api
├── requirements.txt
└── .env
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop (for Neo4j and Weaviate)
- Groq API key (free tier works)
- Google Gemini API key (optional, used as fallback)

### 1. Clone and create virtual environment

```bash
git clone <repo>
cd sportmind
python -m venv venv
source venv/Scripts/activate   # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

### 2. Start Neo4j

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/sportmind123 \
  -v neo4j_data:/data \
  neo4j:5.15
```

### 3. Start Weaviate

```bash
docker run -d --name weaviate \
  -p 8081:8080 -p 50051:50051 \
  -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  -e DEFAULT_VECTORIZER_MODULE=none \
  -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
  -v weaviate_data:/var/lib/weaviate \
  semitechnologies/weaviate:1.24.1
```

These `docker run` commands are for the first time only. They do not run again on their own after Docker Desktop restarts. See [Running the Application](#running-the-application).

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys and DB passwords
```

### 5. Run the ingestion pipeline

```bash
python -m ingestion.run_ingestion
```

This populates Neo4j and Weaviate. Takes 12–15 minutes on first run.

### 6. Train ML models

```bash
python -m ml.train_win_probability
python -m ml.train_player_forecast
```

### 7. Install frontend dependencies

```bash
cd frontend
npm install
```

---

## Environment Variables

Create a `.env` file in the project root:

```bash
# LLM
GROQ_API_KEY=your_groq_api_key_here
GOOGLE_API_KEY=your_gemini_api_key_here   # optional

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=sportmind123

# Weaviate
WEAVIATE_URL=http://localhost:8081
WEAVIATE_HOST=localhost
WEAVIATE_PORT=8081
```

---

## Running the Application

Open Docker Desktop first. Quit and reopen Docker, and the Neo4j and Weaviate containers stay stopped. Start them, then the app:

```powershell
docker start neo4j weaviate
.\run.ps1
```

`.\run.ps1` opens the API at http://localhost:8000 and the frontend at http://localhost:5173. It does not start the databases. The graph and the vectors stay in the `neo4j_data` and `weaviate_data` volumes.

The same two processes can be started by hand:

### Backend

```bash
source venv/Scripts/activate   # Windows
python -m backend.main
# Server: http://localhost:8000
# Docs:   http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm run dev
# App: http://localhost:5173
```

Open `http://localhost:5173` in your browser.

---

## Example Queries

**Chat:**
- "How many MVP awards has LeBron James won?"
- "Compare Stephen Curry and Kevin Durant's career stats"
- "Which team won the most championships between 2013 and 2023?"
- "Predict the win probability for Golden State Warriors vs Boston Celtics"
- "What was Giannis Antetokounmpo's best season?"

**REST:**
```bash
# Player stats
curl "http://localhost:8000/stats/player/LeBron%20James?season=2022-23"

# Win probability
curl "http://localhost:8000/predict/win?home_team=Golden%20State%20Warriors&away_team=Boston%20Celtics"

# Player forecast
curl "http://localhost:8000/predict/player?player=Stephen%20Curry&metric=pts&periods=5"

# Top scorers
curl "http://localhost:8000/stats/top-scorers?season=2022-23&limit=10"
```
