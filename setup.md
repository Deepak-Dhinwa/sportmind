# SportMind — Local Setup

## 1. Create & activate Python virtual environment

```bash
cd D:/projects/sportmind
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> Prophet can take a few minutes to install on Windows — that's normal.

## 2. Fill in your .env

Edit `.env` (copied from `.env.example`):
- `GROQ_API_KEY` — from console.groq.com
- `NEO4J_PASSWORD` — whatever password you set in Neo4j Desktop

## 3. Start Neo4j + Weaviate (Docker — two containers)

**Neo4j:**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/sportmind123 \
  -e NEO4J_PLUGINS='["apoc"]' \
  -v neo4j_data:/data \
  -v neo4j_logs:/logs \
  neo4j:5.15
```

Verify: http://localhost:7474 (login: neo4j / sportmind123)

## 4. Start Weaviate (Docker — single container)

```bash
docker run -d \
  --name weaviate \
  -p 8081:8080 \
  -p 50051:50051 \
  -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
  -e DEFAULT_VECTORIZER_MODULE=none \
  -e ENABLE_MODULES="" \
  -v weaviate_data:/var/lib/weaviate \
  semitechnologies/weaviate:1.24.1
```

Verify it's up: http://localhost:8081/v1/meta

The `docker run` commands above create the containers once. They do not start again by themselves when Docker Desktop opens.

## Each time you open the app

`.\run.ps1` starts the API and the frontend only. With Docker Desktop open, including after you quit Docker and start it again:

```powershell
docker start neo4j weaviate
.\run.ps1
```

API: http://localhost:8000. App: http://localhost:5173.

The existing Docker volumes `neo4j_data` and `weaviate_data` already hold the graph and the vector index. Do not delete those volumes. If Neo4j exits immediately with "already running (pid:7)", that is a stale pid file inside the old container, not missing data. Recreate the container against the same `neo4j_data` volume instead of wiping it.

## 5. Apply Neo4j schema

In Neo4j Browser (http://localhost:7474), run the contents of `graph/schema.cypher`.
Or use the Python helper:

```bash
python -c "
from graph.neo4j_client import run_write
import pathlib
for stmt in pathlib.Path('graph/schema.cypher').read_text().split(';'):
    s = stmt.strip()
    if s and not s.startswith('//'):
        run_write(s)
print('Schema applied.')
"
```
