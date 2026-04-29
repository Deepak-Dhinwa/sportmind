"""
Custom Knowledge Base management endpoints.

Allows uploading, listing, and deleting custom .md / .txt files
that get chunked, embedded, and indexed into Weaviate automatically.

Custom files live in knowledge_base/custom/ and participate in RAG
exactly like the built-in player/team/coach files.

Endpoints:
  POST   /knowledge/upload           — upload + index a file
  GET    /knowledge/files            — list all custom files
  DELETE /knowledge/files/{filename} — remove file + Weaviate chunks
  PUT    /knowledge/files/{filename} — replace content + re-index
"""
import uuid
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from weaviate.classes.query import Filter

router = APIRouter()

CUSTOM_DIR   = Path("knowledge_base/custom")
MANIFEST_PATH = CUSTOM_DIR / "_manifest.json"
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT  = {".md", ".txt"}
MAX_FILE_SIZE = 2 * 1024 * 1024   # 2 MB


# ── Manifest helpers ──────────────────────────────────────────────────────────

def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_manifest(data: dict):
    MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Chunking + indexing (mirrors load_weaviate logic) ─────────────────────────

def _chunk_text(text: str, filename: str) -> list[dict]:
    """Chunk plain text or markdown into 350-word pieces with overlap context."""
    from ingestion.load_weaviate import chunk_markdown
    # If .txt, wrap in a minimal markdown structure so chunker works
    if not text.strip().startswith("#"):
        stem = Path(filename).stem.replace("_", " ").title()
        text = f"# {stem}\n\n{text}"
    return chunk_markdown(text)


def _index_file(filepath: Path, entity: str) -> int:
    """Chunk + embed + insert into Weaviate. Returns number of chunks indexed."""
    from sentence_transformers import SentenceTransformer
    from rag.weaviate_client import get_client, COLLECTION_NAME

    text   = filepath.read_text(encoding="utf-8")
    chunks = _chunk_text(text, filepath.name)
    if not chunks:
        return 0

    model   = SentenceTransformer("all-MiniLM-L6-v2")
    texts   = [c["content"] for c in chunks]
    vectors = model.encode(texts, batch_size=32, show_progress_bar=False)
    fhash   = hashlib.md5(filepath.read_bytes()).hexdigest()
    src_key = str(filepath)

    client     = get_client()
    collection = client.collections.get(COLLECTION_NAME)

    with collection.batch.dynamic() as batch:
        for chunk, vector in zip(chunks, vectors):
            batch.add_object(
                properties={
                    "content":      chunk["content"],
                    "doc_type":     "custom",
                    "entity_name":  entity,
                    "section":      chunk.get("section", ""),
                    "season":       "",
                    "source_file":  src_key,
                    "content_hash": fhash,
                },
                vector={"default": vector.tolist()},
                uuid=str(uuid.uuid4()),
            )
    client.close()
    return len(chunks)


def _delete_from_weaviate(filepath: Path):
    """Remove all Weaviate chunks for this file."""
    from rag.weaviate_client import get_client, COLLECTION_NAME
    src_key = str(filepath)
    client  = get_client()
    try:
        client.collections.get(COLLECTION_NAME).data.delete_many(
            where=Filter.by_property("source_file").equal(src_key)
        )
    finally:
        client.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/knowledge/upload")
async def upload_file(
    file: UploadFile = File(...),
    description: str = Form(""),
):
    """
    Upload a .md or .txt file. It will be chunked, embedded,
    and indexed into Weaviate so the RAG agent can use it.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400,
            detail=f"Only .md and .txt files allowed. Got: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400,
            detail=f"File too large (max 2 MB). Got {len(content)//1024} KB")

    # Sanitise filename
    safe_name = "".join(
        c if (c.isalnum() or c in "-_.") else "_"
        for c in file.filename
    ).strip("_")
    if not safe_name:
        safe_name = f"custom_{uuid.uuid4().hex[:8]}{ext}"

    filepath = CUSTOM_DIR / safe_name

    # If file already exists, delete old Weaviate chunks first
    manifest = _load_manifest()
    if safe_name in manifest:
        _delete_from_weaviate(filepath)

    # Write file
    filepath.write_bytes(content)

    # Index
    entity      = Path(safe_name).stem.replace("_", " ").title()
    chunk_count = _index_file(filepath, entity)

    # Update manifest
    manifest[safe_name] = {
        "filename":    safe_name,
        "entity":      entity,
        "description": description,
        "size_bytes":  len(content),
        "chunk_count": chunk_count,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_manifest(manifest)

    return {
        "filename":    safe_name,
        "entity":      entity,
        "chunk_count": chunk_count,
        "message":     f"Indexed {chunk_count} chunks into knowledge base.",
    }


@router.get("/knowledge/files")
async def list_files():
    """List all custom files with metadata."""
    manifest = _load_manifest()
    return list(manifest.values())


@router.put("/knowledge/files/{filename}")
async def update_file(filename: str, file: UploadFile = File(...)):
    """Replace an existing custom file's content and re-index it."""
    manifest = _load_manifest()
    if filename not in manifest:
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Only .md and .txt files allowed.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2 MB).")

    filepath = CUSTOM_DIR / filename

    # Remove old chunks
    _delete_from_weaviate(filepath)

    # Write new content
    filepath.write_bytes(content)

    # Re-index
    entity      = manifest[filename]["entity"]
    chunk_count = _index_file(filepath, entity)

    manifest[filename].update({
        "size_bytes":  len(content),
        "chunk_count": chunk_count,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })
    _save_manifest(manifest)

    return {
        "filename":    filename,
        "chunk_count": chunk_count,
        "message":     f"Re-indexed {chunk_count} chunks.",
    }


@router.delete("/knowledge/files/{filename}")
async def delete_file(filename: str):
    """Remove a custom file and all its Weaviate chunks."""
    manifest = _load_manifest()
    if filename not in manifest:
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")

    filepath = CUSTOM_DIR / filename
    _delete_from_weaviate(filepath)
    if filepath.exists():
        filepath.unlink()

    del manifest[filename]
    _save_manifest(manifest)

    return {"message": f"'{filename}' removed from knowledge base."}
