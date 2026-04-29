"""
SportMind FastAPI backend.

Endpoints:
  WS  /chat                          — streaming RAG chat
  GET /stats/player/{name}           — player stats + awards + bio
  GET /stats/top-scorers             — top scorers for a season
  GET /stats/team/{name}             — team record + championships
  GET /stats/team/{name}/roster      — team roster for a season
  GET /stats/champions               — all championship winners
  GET /stats/awards                  — award winners (MVP, DPOY, etc.)
  GET /graph/neighborhood/{entity}   — subgraph for react-force-graph
  GET /predict/win                   — win probability
  GET /predict/player                — player performance forecast
  GET /health                        — health check
"""
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.chat      import router as chat_router
from backend.routes.stats     import router as stats_router
from backend.routes.knowledge import router as knowledge_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up: pre-build the agent so first request isn't slow
    try:
        from rag.agent import build_agent
        build_agent()
        print("[startup] RAG agent ready")
    except Exception as e:
        print(f"[startup] Agent init warning: {e}")
    yield
    # Shutdown: close DB connections
    try:
        from graph.neo4j_client import close_driver
        from rag.weaviate_client import close_client
        close_driver()
        close_client()
    except Exception:
        pass


app = FastAPI(
    title="SportMind API",
    description="NBA Intelligent Analytics — RAG + Knowledge Graph + ML",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # vite dev server
        "http://localhost:4173",   # vite preview
        "http://localhost:3000",   # docker nginx
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(stats_router)
app.include_router(knowledge_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sportmind"}


@app.get("/system/info")
async def system_info():
    """Quick stats about the system: model counts, KB size, cache state."""
    info: dict = {"service": "sportmind"}
    try:
        from pathlib import Path
        models_dir = Path("ml/models")
        player_models = len(list(models_dir.glob("player_*.pkl")))
        win_model     = (models_dir / "win_probability.pkl").exists()
        info["ml"] = {
            "win_probability_model": win_model,
            "player_forecast_models": player_models,
            "unique_players": player_models // 7,   # 7 metrics per player
        }
    except Exception:
        pass
    try:
        from rag.weaviate_client import get_client, COLLECTION_NAME
        client = get_client()
        col    = client.collections.get(COLLECTION_NAME)
        total  = col.aggregate.over_all(total_count=True).total_count
        info["knowledge_base"] = {"total_chunks": total}
    except Exception:
        pass
    try:
        from graph.neo4j_client import run_query
        r = run_query("MATCH (p:Player) RETURN count(p) AS n")
        info["graph"] = {"players": r[0]["n"] if r else 0}
    except Exception:
        pass
    try:
        from backend.routes.chat import _query_cache
        info["cache"] = {"cached_queries": len(_query_cache)}
    except Exception:
        pass
    return info


@app.get("/")
async def root():
    return {
        "message": "SportMind API",
        "docs":    "/docs",
        "chat_ws": "ws://localhost:8000/chat",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
