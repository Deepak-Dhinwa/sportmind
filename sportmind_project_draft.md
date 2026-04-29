# SportMind — NBA Intelligent Analytics RAG System
### Full Project Draft

---

## Project Overview

SportMind is an intelligent NBA analytics system that combines a knowledge graph (Neo4j), a semantic vector store (Weaviate), and a classical ML prediction layer — all orchestrated by a LlamaIndex RAG agent powered by the Groq API. Users interact through a chat interface that can answer relational queries, semantic questions, and prediction requests about NBA history.

**Data range:** 2013–14 to 2022–23 seasons (10 seasons). This covers the entire Golden State Warriors dynasty, the LeBron Miami/Cleveland/LA eras, rich play-by-play records, and well-documented player/team narratives. The `nba_api` Python package covers this range completely with structured data.

**Test/validation split:** 2022–23 season is held out as the "test year". The knowledge graph and vector store are built on 2013–2022 data. Queries about the 2022–23 season test retrieval and prediction quality against data the model hasn't been trained on.

---

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Data ingestion | `nba_api` Python package | Pull player, team, game stats |
| Knowledge graph | Neo4j 5.x | Structured relational data + Cypher queries |
| Vector store | Weaviate (self-hosted) | `.md` file embeddings + semantic search |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Local, free, no API key needed |
| RAG orchestration | LlamaIndex (`RouterQueryEngine`) | Query routing + tool calling |
| LLM | Groq API — Llama 3 70B | Fast, free-tier inference |
| ML prediction | scikit-learn + XGBoost + Prophet | Win prob, player performance |
| Backend API | FastAPI + WebSocket | REST + streaming chat responses |
| Frontend | React + Recharts + react-force-graph | Chat UI + stats + graph explorer |
| Containerization | Docker Compose | All services in one `docker-compose up` |

---

## Folder Structure

```
sportmind/
│
├── docker-compose.yml
├── .env.example
├── README.md
│
├── ingestion/                        # Data pipeline scripts
│   ├── fetch_players.py              # Pull player bio + career stats
│   ├── fetch_teams.py                # Pull team records per season
│   ├── fetch_games.py                # Pull game logs + box scores
│   ├── fetch_awards.py               # Pull MVP, DPOY, All-Star selections
│   ├── load_neo4j.py                 # ETL: structured data → Neo4j
│   ├── generate_md_files.py          # Auto-generate .md files from structured data
│   └── load_weaviate.py              # Chunk + embed .md files → Weaviate
│
├── knowledge_base/                   # Hand-crafted + auto-generated .md files
│   ├── players/
│   │   ├── lebron_james.md
│   │   ├── stephen_curry.md
│   │   ├── kevin_durant.md
│   │   ├── giannis_antetokounmpo.md
│   │   └── ... (one file per key player)
│   ├── teams/
│   │   ├── golden_state_warriors.md
│   │   ├── cleveland_cavaliers.md
│   │   ├── miami_heat.md
│   │   └── ...
│   ├── games/
│   │   ├── 2016_nba_finals_game7.md
│   │   ├── 2019_nba_finals.md
│   │   └── ...
│   ├── seasons/
│   │   ├── 2015_16_season.md         # Season narrative summaries
│   │   └── ...
│   ├── coaches/
│   │   ├── gregg_popovich.md
│   │   ├── steve_kerr.md
│   │   └── ...
│   └── venues/
│       ├── chase_center.md
│       └── ...
│
├── graph/                            # Neo4j schema + query helpers
│   ├── schema.cypher                 # Constraints + indexes
│   ├── queries.py                    # Pre-built Cypher query functions
│   └── neo4j_client.py              # Neo4j Python driver wrapper
│
├── ml/                               # Prediction models
│   ├── train_win_probability.py      # XGBoost win probability model
│   ├── train_player_forecast.py      # Prophet player performance forecasting
│   ├── predictor.py                  # Inference wrapper — called as a tool
│   └── models/                       # Saved model artifacts (.pkl, .json)
│
├── rag/                              # RAG orchestration
│   ├── agent.py                      # LlamaIndex RouterQueryEngine setup
│   ├── graph_tool.py                 # Neo4j query tool
│   ├── vector_tool.py                # Weaviate retrieval tool
│   ├── prediction_tool.py            # ML predictor tool
│   ├── prompts.py                    # System prompt + tool descriptions
│   └── weaviate_client.py            # Weaviate Python client wrapper
│
├── backend/                          # FastAPI app
│   ├── main.py                       # App entrypoint + routes
│   ├── routes/
│   │   ├── chat.py                   # WebSocket streaming chat endpoint
│   │   └── stats.py                  # REST endpoints for dashboard stats
│   └── Dockerfile
│
├── frontend/                         # React app
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ChatPanel.jsx         # Chat UI with streaming
│   │   │   ├── GraphExplorer.jsx     # react-force-graph knowledge graph
│   │   │   ├── StatsCard.jsx         # Reusable stat display card
│   │   │   └── PredictionPanel.jsx   # Win prob + forecast display
│   │   └── api/
│   │       └── client.js             # API + WebSocket client
│   ├── package.json
│   └── Dockerfile
│
└── notebooks/                        # Exploration + validation
    ├── 01_data_exploration.ipynb
    ├── 02_neo4j_queries.ipynb
    ├── 03_rag_testing.ipynb
    └── 04_ml_validation.ipynb
```

---

## Docker Compose Setup

```yaml
# docker-compose.yml
version: "3.9"

services:
  neo4j:
    image: neo4j:5.15
    ports:
      - "7474:7474"   # Browser UI
      - "7687:7687"   # Bolt protocol
    environment:
      NEO4J_AUTH: neo4j/sportmind123
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

  weaviate:
    image: semitechnologies/weaviate:1.24.1
    ports:
      - "8080:8080"
    environment:
      QUERY_DEFAULTS_LIMIT: 25
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: "true"
      PERSISTENCE_DATA_PATH: /var/lib/weaviate
      DEFAULT_VECTORIZER_MODULE: none        # We bring our own embeddings
      ENABLE_MODULES: ""
    volumes:
      - weaviate_data:/var/lib/weaviate

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: sportmind123
      WEAVIATE_URL: http://weaviate:8080
      GROQ_API_KEY: ${GROQ_API_KEY}
    depends_on:
      - neo4j
      - weaviate
    volumes:
      - ./ml/models:/app/ml/models
      - ./knowledge_base:/app/knowledge_base

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  neo4j_data:
  neo4j_logs:
  weaviate_data:
```

**`.env.example`**
```
GROQ_API_KEY=your_groq_api_key_here
```

---

## Phase 1 — Data Ingestion Pipeline

### What to pull with `nba_api`

```python
# ingestion/fetch_players.py
from nba_api.stats.static import players
from nba_api.stats.endpoints import playercareerstats, commonplayerinfo
import pandas as pd, time, json

def fetch_all_players(season_range=("2013-14", "2022-23")):
    all_players = players.get_active_players()
    # Filter to players active in our range — approx 500–600 players
    results = []
    for p in all_players:
        try:
            info = commonplayerinfo.CommonPlayerInfo(player_id=p["id"])
            career = playercareerstats.PlayerCareerStats(player_id=p["id"])
            results.append({
                "id": p["id"],
                "name": p["full_name"],
                "info": info.get_normalized_dict(),
                "career_stats": career.get_normalized_dict()
            })
            time.sleep(0.6)   # Respect rate limits
        except Exception as e:
            print(f"Failed {p['full_name']}: {e}")
    return results
```

Pull and save as JSON locally before loading into DBs. Order of operations:

1. `fetch_players.py` → `data/raw/players.json`
2. `fetch_teams.py` → `data/raw/teams.json`
3. `fetch_games.py` → `data/raw/games_{season}.json` (one file per season)
4. `fetch_awards.py` → `data/raw/awards.json`

---

## Phase 2 — Neo4j Knowledge Graph

### Schema Design

```cypher
-- graph/schema.cypher

-- Constraints (run once on fresh DB)
CREATE CONSTRAINT player_id IF NOT EXISTS FOR (p:Player) REQUIRE p.player_id IS UNIQUE;
CREATE CONSTRAINT team_id IF NOT EXISTS FOR (t:Team) REQUIRE t.team_id IS UNIQUE;
CREATE CONSTRAINT game_id IF NOT EXISTS FOR (g:Game) REQUIRE g.game_id IS UNIQUE;
CREATE CONSTRAINT season_id IF NOT EXISTS FOR (s:Season) REQUIRE s.year IS UNIQUE;
CREATE CONSTRAINT coach_id IF NOT EXISTS FOR (c:Coach) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT award_id IF NOT EXISTS FOR (a:Award) REQUIRE a.award_id IS UNIQUE;

-- Indexes for fast lookups
CREATE INDEX player_name IF NOT EXISTS FOR (p:Player) ON (p.name);
CREATE INDEX team_name IF NOT EXISTS FOR (t:Team) ON (t.name);
```

### Node Properties

```
Player {
  player_id, name, position, height, weight,
  draft_year, draft_round, draft_pick, country,
  career_pts_avg, career_ast_avg, career_reb_avg
}

Team {
  team_id, name, city, abbreviation, conference, division
}

Game {
  game_id, date, season, home_team_id, away_team_id,
  home_score, away_score, winner_team_id, arena, attendance
}

Season {
  year,           -- e.g. "2015-16"
  champion_team_id,
  finals_mvp_player_id
}

Coach {
  name, active_years
}

Award {
  award_id,       -- e.g. "MVP_2016"
  type,           -- MVP, DPOY, ROY, AllStar, AllNBA
  season, player_id
}

PlayerSeasonStats {
  player_id, season, team_id,
  games_played, pts, ast, reb, stl, blk,
  fg_pct, fg3_pct, ft_pct, per, ts_pct
}
```

### Key Relationships

```cypher
(Player)-[:PLAYED_FOR {season, games, role}]->(Team)
(Player)-[:WON_AWARD]->(Award)
(Player)-[:PLAYED_IN {pts, ast, reb, result}]->(Game)
(Player)-[:DRAFTED_BY {year, round, pick}]->(Team)
(Coach)-[:COACHED {seasons, record}]->(Team)
(Team)-[:WON_CHAMPIONSHIP]->(Season)
(Team)-[:PLAYED_GAME {home_or_away, score}]->(Game)
(Game)-[:IN_SEASON]->(Season)
(Player)-[:TEAMMATES_WITH {season}]->(Player)   -- derived, very useful
```

### Example Cypher Queries

```cypher
-- "Which players won a championship with Golden State?"
MATCH (p:Player)-[:PLAYED_FOR]->(t:Team {name: "Golden State Warriors"})
      -[:WON_CHAMPIONSHIP]->(s:Season)
RETURN p.name, s.year ORDER BY s.year

-- "Who were LeBron's teammates in the 2016 championship?"
MATCH (lebron:Player {name: "LeBron James"})-[:PLAYED_FOR]->(t:Team)
      -[:WON_CHAMPIONSHIP]->(s:Season {year: "2015-16"})
MATCH (teammate:Player)-[:PLAYED_FOR]->(t)
WHERE teammate.name <> "LeBron James"
RETURN teammate.name

-- "Top scorers in the 2018-19 season"
MATCH (p:Player)-[r:PLAYED_FOR]->(t:Team)
WHERE r.season = "2018-19"
MATCH (s:PlayerSeasonStats {player_id: p.player_id, season: "2018-19"})
RETURN p.name, t.name, s.pts ORDER BY s.pts DESC LIMIT 10
```

---

## Phase 3 — Weaviate Vector Store + Markdown Knowledge Base

### Weaviate Schema

```python
# rag/weaviate_client.py
import weaviate

def create_schema(client):
    schema = {
        "class": "SportDocument",
        "description": "NBA knowledge base documents",
        "vectorizer": "none",     # We provide our own vectors
        "properties": [
            {"name": "content", "dataType": ["text"]},
            {"name": "doc_type", "dataType": ["text"]},   # player/team/game/coach/venue/season
            {"name": "entity_name", "dataType": ["text"]},
            {"name": "season", "dataType": ["text"]},
            {"name": "source_file", "dataType": ["text"]},
        ]
    }
    client.schema.create_class(schema)
```

### Markdown File Template

Every auto-generated player `.md` file follows this template (the `generate_md_files.py` script fills it from structured data, and you can manually enrich any file):

```markdown
# LeBron James

**Position:** Small Forward / Power Forward  
**Teams (2013–2023):** Miami Heat, Cleveland Cavaliers, Los Angeles Lakers  
**Draft:** 2003 NBA Draft, Pick #1, Cleveland Cavaliers

## Career Overview
LeBron James is widely considered one of the greatest players in NBA history.
His decade 2013–2023 spanned three franchises and two additional championships...

## Season-by-Season Highlights (2013–2023)
### 2015–16 (Cleveland Cavaliers)
- Stats: 25.3 PPG / 7.4 RPG / 6.8 APG
- Led Cavaliers to first championship in franchise history
- Finals MVP — famous Game 7 block + chase-down vs Warriors

### 2019–20 (Los Angeles Lakers)
- Stats: 25.3 PPG / 7.8 RPG / 10.2 APG
- Won championship in the NBA Bubble (Disney World)
- Finals MVP

## Playing Style
LeBron is a physically dominant wing with elite court vision...

## Legacy and Impact
...
```

### Chunking + Embedding Strategy

```python
# ingestion/load_weaviate.py
from sentence_transformers import SentenceTransformer
from pathlib import Path
import weaviate, uuid

model = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_markdown(text, chunk_size=400, overlap=50):
    """Split by paragraphs first, then by token limit."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current.split()) + len(para.split()) < chunk_size:
            current += "\n\n" + para
        else:
            if current:
                chunks.append(current.strip())
            current = para
    if current:
        chunks.append(current.strip())
    return chunks

def load_all_md_files(client, kb_path="knowledge_base/"):
    for md_file in Path(kb_path).rglob("*.md"):
        doc_type = md_file.parent.name    # players/teams/games etc.
        entity_name = md_file.stem.replace("_", " ").title()
        text = md_file.read_text()
        chunks = chunk_markdown(text)
        for chunk in chunks:
            vector = model.encode(chunk).tolist()
            client.data_object.create(
                data_object={
                    "content": chunk,
                    "doc_type": doc_type,
                    "entity_name": entity_name,
                    "source_file": str(md_file),
                },
                class_name="SportDocument",
                uuid=str(uuid.uuid4()),
                vector=vector
            )
```

---

## Phase 4 — ML Prediction Layer

### Model 1 — Win Probability (XGBoost)

**Features per game:**
- Home/away flag
- Team's last 10 games win rate
- Opponent's last 10 games win rate
- Average points for/against (season running average)
- Star player available (binary — injured or not)
- Days rest for each team
- Season stage (early / mid / playoffs)

```python
# ml/train_win_probability.py
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
import pickle

def train_win_probability_model(games_df):
    features = [
        "home_flag", "home_win_rate_l10", "away_win_rate_l10",
        "home_pts_avg", "away_pts_avg", "home_rest_days",
        "away_rest_days", "season_stage"
    ]
    X = games_df[features]
    y = games_df["home_win"]

    tscv = TimeSeriesSplit(n_splits=5)
    model = xgb.XGBClassifier(n_estimators=200, max_depth=4,
                               learning_rate=0.05, use_label_encoder=False)
    model.fit(X, y)

    with open("ml/models/win_probability.pkl", "wb") as f:
        pickle.dump(model, f)
    return model
```

### Model 2 — Player Performance Forecast (Prophet)

```python
# ml/train_player_forecast.py
from prophet import Prophet
import pandas as pd, pickle

def train_player_model(player_game_logs_df, player_id, metric="pts"):
    """Train a Prophet model for one player, one metric."""
    df = player_game_logs_df[player_game_logs_df["player_id"] == player_id]
    df = df[["game_date", metric]].rename(columns={"game_date": "ds", metric: "y"})
    df["ds"] = pd.to_datetime(df["ds"])

    model = Prophet(weekly_seasonality=False, yearly_seasonality=True,
                    changepoint_prior_scale=0.05)
    model.fit(df)

    with open(f"ml/models/player_{player_id}_{metric}.pkl", "wb") as f:
        pickle.dump(model, f)
    return model
```

### Predictor Tool (called by the RAG agent)

```python
# ml/predictor.py
import pickle, numpy as np

def predict_win_probability(home_team: str, away_team: str,
                            home_rest: int, away_rest: int,
                            context: dict) -> dict:
    """
    Called by LlamaIndex prediction tool.
    context contains pre-computed rolling stats from Neo4j.
    """
    with open("ml/models/win_probability.pkl", "rb") as f:
        model = pickle.load(f)

    features = [[
        1,                                      # home flag
        context.get("home_win_rate_l10", 0.5),
        context.get("away_win_rate_l10", 0.5),
        context.get("home_pts_avg", 110),
        context.get("away_pts_avg", 110),
        home_rest, away_rest,
        context.get("season_stage", 1)
    ]]
    prob = model.predict_proba(features)[0][1]
    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_win_probability": round(float(prob), 3),
        "away_win_probability": round(1 - float(prob), 3),
    }

def forecast_player_performance(player_id: str, metric: str,
                                 periods: int = 10) -> dict:
    with open(f"ml/models/player_{player_id}_{metric}.pkl", "rb") as f:
        model = pickle.load(f)
    future = model.make_future_dataframe(periods=periods)
    forecast = model.predict(future)
    last = forecast.tail(periods)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    return last.to_dict(orient="records")
```

---

## Phase 5 — RAG Orchestration

### LlamaIndex Agent Setup

```python
# rag/agent.py
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core.tools import QueryEngineTool, FunctionTool
from llama_index.llms.groq import Groq
from rag.graph_tool import build_graph_query_engine
from rag.vector_tool import build_vector_query_engine
from rag.prediction_tool import build_prediction_tool
from rag.prompts import SYSTEM_PROMPT

def build_agent():
    llm = Groq(model="llama3-70b-8192", api_key=GROQ_API_KEY)

    graph_tool = QueryEngineTool.from_defaults(
        query_engine=build_graph_query_engine(),
        name="graph_query",
        description=(
            "Use for structured, relational, or statistical questions. "
            "Examples: player stats per season, championship history, trade records, "
            "team rosters, head-to-head records, award winners, game scores."
        )
    )

    vector_tool = QueryEngineTool.from_defaults(
        query_engine=build_vector_query_engine(),
        name="semantic_search",
        description=(
            "Use for narrative, contextual, or descriptive questions. "
            "Examples: player playing style, team dynasty story, coach philosophy, "
            "what made a game or season significant, legacy and impact questions."
        )
    )

    prediction_tool = build_prediction_tool()   # FunctionTool wrapping predictor.py

    router = RouterQueryEngine(
        selector=LLMSingleSelector.from_defaults(llm=llm),
        query_engine_tools=[graph_tool, vector_tool, prediction_tool],
        verbose=True
    )
    return router
```

### System Prompt

```python
# rag/prompts.py
SYSTEM_PROMPT = """
You are SportMind, an expert NBA analytics assistant.
You have access to a knowledge graph covering 2013–2022 NBA seasons,
a rich narrative knowledge base about players, teams, games, coaches, and venues,
and a machine learning prediction engine.

When answering:
- For stats and factual queries: use the graph tool and cite specific numbers.
- For narrative/contextual questions: use the semantic search tool.
- For prediction questions ("chances", "likely", "forecast", "predict"): use the prediction tool.
- You may combine tools if needed — get facts from the graph AND context from the knowledge base.
- Always be specific. Mention seasons, exact stats, and names.
- The test year is 2022–23. For queries about this season, note it is your evaluation set.

Never make up statistics. If the data is not available, say so clearly.
"""
```

---

## Phase 6 — FastAPI Backend

```python
# backend/main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from rag.agent import build_agent
import json

app = FastAPI(title="SportMind API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

agent = build_agent()

@app.websocket("/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    history = []
    while True:
        user_msg = await websocket.receive_text()
        history.append({"role": "user", "content": user_msg})
        response = await agent.aquery(user_msg)
        full = str(response)
        # Stream token by token
        for token in full.split(" "):
            await websocket.send_text(json.dumps({"type": "token", "data": token + " "}))
        await websocket.send_text(json.dumps({"type": "done", "data": full}))
        history.append({"role": "assistant", "content": full})

@app.get("/stats/player/{player_name}")
async def get_player_stats(player_name: str, season: str = None):
    """Returns structured stats for dashboard cards."""
    # Query Neo4j directly for fast stats display
    ...

@app.get("/graph/neighborhood/{entity_name}")
async def get_graph_neighborhood(entity_name: str, depth: int = 2):
    """Returns nodes + edges for graph explorer."""
    # Returns JSON suitable for react-force-graph
    ...

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## Phase 7 — React Frontend

### Component Plan

**`App.jsx`** — two-panel layout: left = chat, right = tabbed panel (graph explorer / stats cards)

**`ChatPanel.jsx`** — WebSocket-connected chat, streams tokens in real time, renders markdown responses, shows tool call badges ("Used: graph_query", "Used: prediction_tool")

**`GraphExplorer.jsx`** — `react-force-graph` 2D graph, nodes colored by type (Player=blue, Team=orange, Game=gray, Award=gold), click a node to load its neighborhood, sidebar shows node properties

**`StatsCard.jsx`** — reusable card showing player/team stat summaries, powered by `/stats/` REST endpoints, uses Recharts bar/line charts

**`PredictionPanel.jsx`** — input two teams, get win probability back as a gauge chart

### Key dependencies

```json
{
  "dependencies": {
    "react": "^18",
    "react-force-graph-2d": "^1.25",
    "recharts": "^2.10",
    "react-markdown": "^9",
    "axios": "^1.6"
  }
}
```

---

## Data Split Strategy

| Dataset | Seasons | Purpose |
|---|---|---|
| Training data | 2013–14 to 2020–21 | Build knowledge graph, train ML models, embed most .md files |
| Validation data | 2021–22 | Tune ML hyperparameters, test retrieval quality |
| Test data | 2022–23 | Final evaluation — query chatbot, measure prediction accuracy |

When the graph and vector store are fully loaded with 2013–2022 data, run evaluation queries like:

- *"Who will win more games — Warriors or Lakers in 2022–23?"* → compare against actual results
- *"Predict LeBron's scoring average for 2022–23"* → compare against actual 28.9 PPG
- *"Who were the top 3 scorers in the 2022–23 season?"* → test if graph query + 2022-23 data retrieves correctly

---

## Example Queries to Test

| Query | Expected tool | Expected behaviour |
|---|---|---|
| "Who won the 2016 championship?" | graph_query | Returns Cleveland Cavaliers, pulls from Season node |
| "What made the 2016 Finals so special?" | semantic_search | Returns narrative from `games/2016_nba_finals.md` |
| "LeBron's stats in the 2018-19 season" | graph_query | Returns PlayerSeasonStats node for LeBron, 2018-19 |
| "Describe Stephen Curry's playing style" | semantic_search | Returns narrative chunk from `players/stephen_curry.md` |
| "Who coached the Warriors during their dynasty?" | graph_query | Returns Steve Kerr via COACHED relationship |
| "Chances Warriors beat the Celtics?" | prediction_tool | Returns win probability from XGBoost model |
| "Predict Giannis scoring over next 10 games" | prediction_tool | Returns Prophet forecast |
| "Which players played for both Miami and Cleveland?" | graph_query | Graph traversal across PLAYED_FOR relationships |

---

## Build Order (Recommended)

```
Week 1 — Data + Storage
  [ ] Run all ingestion scripts, save raw JSON
  [ ] Load Neo4j: run schema.cypher, then load_neo4j.py
  [ ] Write + generate knowledge_base/ .md files
  [ ] Load Weaviate: run load_weaviate.py

Week 2 — ML + RAG
  [ ] Train win probability model
  [ ] Train Prophet models for top 20 players
  [ ] Build LlamaIndex agent with all three tools
  [ ] Test in notebook: 03_rag_testing.ipynb

Week 3 — Backend + Frontend
  [ ] FastAPI: chat WebSocket + stats endpoints + graph endpoint
  [ ] React: ChatPanel + GraphExplorer + StatsCard
  [ ] Wire up Docker Compose, test full stack

Week 4 — Evaluation + Polish
  [ ] Run test queries against 2022-23 holdout
  [ ] Evaluate ML predictions vs actual results
  [ ] Improve .md files for weak retrieval areas
  [ ] Add PredictionPanel to frontend
```

---

## Environment Setup

```bash
# Clone and setup
git clone <your-repo>
cd sportmind
cp .env.example .env
# Fill in GROQ_API_KEY in .env

# Start all services
docker-compose up -d

# Run ingestion (once, outside Docker or in a separate container)
pip install nba_api sentence-transformers neo4j weaviate-client
python ingestion/fetch_players.py
python ingestion/fetch_teams.py
python ingestion/fetch_games.py
python ingestion/load_neo4j.py
python ingestion/generate_md_files.py
python ingestion/load_weaviate.py

# Train ML models
pip install xgboost prophet scikit-learn
python ml/train_win_probability.py
python ml/train_player_forecast.py

# Frontend dev
cd frontend && npm install && npm run dev
```

---

## Key Design Decisions (for reference in new chat)

1. **No live API** — all data is pulled once, stored statically. The knowledge graph does not change after ingestion. This makes the system deterministic and testable.

2. **Embeddings are local** — `sentence-transformers/all-MiniLM-L6-v2` runs in-process with no API key. Fast enough for this scale (~5000 chunks expected).

3. **Weaviate with `none` vectorizer** — we pass pre-computed vectors ourselves. This keeps embedding logic in Python, not in Weaviate.

4. **LLM is Groq (Llama 3 70B)** — free tier, very fast inference (~300 tokens/sec), no local GPU needed. Fallback: Gemma 2 27B on Groq if rate-limited.

5. **ML is a tool, not a retrieval path** — the router agent calls `predict_win_probability()` as a function tool. It does not go through the RAG pipeline. This keeps prediction fast and deterministic.

6. **Graph explorer pulls neighborhood** — the `/graph/neighborhood/{entity}` endpoint returns 2-hop subgraph from Neo4j as JSON (nodes + links), fed directly to `react-force-graph-2d`. Click any node to re-center.

7. **Test year = 2022–23** — held completely out of ML training. Used only for evaluation. The knowledge graph contains 2022–23 game data (for querying) but the ML models are not trained on it.
