"""
Weaviate client — connection + schema management.

Collection: SportDocument
  - Hybrid search (BM25 + dense vectors, self_provided)
  - Properties: content, doc_type, entity_name, section, season, source_file, content_hash
  - content_hash enables smart incremental re-indexing (only changed files)
  - section tracks which ## header the chunk came from (e.g. "Playing Style")
"""
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from dotenv import load_dotenv
import os

load_dotenv()

COLLECTION_NAME = "SportDocument"

_client = None


def get_client() -> weaviate.WeaviateClient:
    global _client
    if _client is None:
        _client = weaviate.connect_to_local(
            host=os.getenv("WEAVIATE_HOST", "localhost"),
            port=int(os.getenv("WEAVIATE_PORT", "8081")),
        )
    return _client


def close_client():
    global _client
    if _client:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


def ensure_collection(client: weaviate.WeaviateClient):
    """
    Create the SportDocument collection if it doesn't exist.
    If it exists but is missing the newer properties (content_hash, section),
    add them transparently — no --force required.
    """
    if not client.collections.exists(COLLECTION_NAME):
        client.collections.create(
            name=COLLECTION_NAME,
            description="NBA knowledge base — players, teams, seasons, game summaries",
            vector_config=Configure.Vectors.self_provided(),
            properties=[
                Property(name="content",      data_type=DataType.TEXT),
                Property(name="doc_type",     data_type=DataType.TEXT),
                Property(name="entity_name",  data_type=DataType.TEXT),
                Property(name="section",      data_type=DataType.TEXT),
                Property(name="season",       data_type=DataType.TEXT),
                Property(name="source_file",  data_type=DataType.TEXT),
                Property(name="content_hash", data_type=DataType.TEXT),
            ],
        )
        return

    # Collection already exists — migrate missing properties if needed
    col    = client.collections.get(COLLECTION_NAME)
    config = col.config.get()
    existing_props = {p.name for p in config.properties}

    for prop_name, dtype in [("content_hash", DataType.TEXT), ("section", DataType.TEXT)]:
        if prop_name not in existing_props:
            try:
                col.config.add_property(Property(name=prop_name, data_type=dtype))
                print(f"  [schema] Added missing property '{prop_name}'")
            except Exception as e:
                print(f"  [schema] Could not add '{prop_name}': {e}")
