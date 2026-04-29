"""
KB Loader — chunks markdown files and loads them into Weaviate.

Chunking strategy:
  - Section-aware: splits by ## headers first, keeping semantic units intact.
  - Each section becomes its own chunk, prefixed with document title for context.
  - Sections longer than MAX_SECTION_WORDS get sub-split by paragraph.

Incremental indexing:
  - Tracks MD5 hash of each file's content (stored in Weaviate as `content_hash`).
  - On each run: new files are indexed, changed files are re-indexed (old chunks
    deleted + new ones inserted), unchanged files are skipped.
  - Only changed/new content is ever processed — O(changed) not O(total).

Usage:
  python -m ingestion.load_weaviate           # smart incremental (default)
  python -m ingestion.load_weaviate --force   # wipe + full rebuild
  python -m ingestion.load_weaviate --dry-run # show what would change, no writes
"""
import sys
import uuid
import hashlib
from pathlib import Path
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from weaviate.classes.query import Filter

from rag.weaviate_client import get_client, ensure_collection, COLLECTION_NAME

KB_DIR           = Path("knowledge_base")
EMB_MODEL        = "all-MiniLM-L6-v2"
MAX_SECTION_WORDS = 380   # max words per chunk before sub-splitting


# ── Hashing ────────────────────────────────────────────────────────────────────

def _file_hash(path: Path) -> str:
    """MD5 of file bytes — fast and sufficient for change detection."""
    return hashlib.md5(path.read_bytes()).hexdigest()


# ── Section-aware chunking ─────────────────────────────────────────────────────

def chunk_markdown(text: str) -> list[dict]:
    """
    Split a markdown document into semantic chunks by ## section headers.

    Returns a list of dicts:
      {
        "content": str,   # the chunk text (with doc title prepended for context)
        "section": str,   # e.g. "Playing Style", "Team Overview", ""
      }

    Rules:
    - The # title is extracted and prepended to every chunk so retrieval has context.
    - Each ## section becomes one chunk.
    - Sections > MAX_SECTION_WORDS are sub-split by paragraph (keeping title prefix).
    - Files without any ## headers are returned as a single chunk.
    """
    lines  = text.split("\n")
    title  = ""
    chunks: list[dict] = []

    # ── Pass 1: collect sections ──────────────────────────────────────────────
    sections: list[dict] = []           # [{header, lines}]
    current_header = ""
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            # Top-level title
            title = stripped[2:].strip()
            current_lines.append(line)
        elif stripped.startswith("## "):
            # Save previous section
            if current_lines:
                sections.append({"header": current_header, "lines": list(current_lines)})
            current_header = stripped[3:].strip()
            current_lines  = [line]
        else:
            current_lines.append(line)

    # Save final section
    if current_lines:
        sections.append({"header": current_header, "lines": list(current_lines)})

    # ── Pass 2: build chunks from sections ────────────────────────────────────
    prefix = f"[{title}]\n" if title else ""

    for sec in sections:
        raw = "\n".join(sec["lines"]).strip()
        if not raw:
            continue

        full_text = prefix + raw
        words     = full_text.split()

        if len(words) <= MAX_SECTION_WORDS:
            # Whole section fits in one chunk
            chunks.append({"content": full_text, "section": sec["header"]})
        else:
            # Sub-split by paragraph, keeping title prefix on every sub-chunk
            paragraphs = raw.split("\n\n")
            buf: list[str] = []
            buf_words = 0

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                pw = len(para.split())

                if buf_words + pw <= MAX_SECTION_WORDS:
                    buf.append(para)
                    buf_words += pw
                else:
                    if buf:
                        chunks.append({
                            "content": prefix + "\n\n".join(buf),
                            "section": sec["header"],
                        })
                    buf       = [para]
                    buf_words = pw

            if buf:
                chunks.append({
                    "content": prefix + "\n\n".join(buf),
                    "section": sec["header"],
                })

    # Fallback: file with no sections at all → one chunk
    if not chunks and text.strip():
        chunks.append({"content": text.strip(), "section": ""})

    return chunks


# ── Snapshot of existing index ────────────────────────────────────────────────

def _load_existing_index(collection) -> dict[str, str]:
    """
    Fetch source_file → content_hash for every object already in Weaviate.
    Returns {source_file: hash} — one entry per unique source file.
    (Multiple chunks share the same source_file and hash.)
    """
    index: dict[str, str] = {}
    try:
        # Paginate in batches of 5000
        offset = 0
        batch  = 5000
        while True:
            resp = collection.query.fetch_objects(
                limit=batch,
                offset=offset,
                include_vector=False,
                return_properties=["source_file", "content_hash"],
            )
            if not resp.objects:
                break
            for obj in resp.objects:
                sf = obj.properties.get("source_file", "")
                h  = obj.properties.get("content_hash", "")
                if sf and sf not in index:
                    index[sf] = h
            if len(resp.objects) < batch:
                break
            offset += batch
    except Exception as e:
        print(f"  [index] Warning: could not load existing index — {e}")
    return index


def _delete_chunks_for_file(collection, src_key: str):
    """Delete all Weaviate objects whose source_file matches src_key."""
    try:
        collection.data.delete_many(
            where=Filter.by_property("source_file").equal(src_key)
        )
    except Exception as e:
        print(f"  [delete] Failed for {src_key}: {e}")


# ── Main loader ────────────────────────────────────────────────────────────────

def load_all_md_files(force: bool = False, dry_run: bool = False):
    print("Loading embedding model...")
    model = SentenceTransformer(EMB_MODEL)

    client = get_client()

    if force:
        print("  --force: wiping and recreating collection...")
        try:
            client.collections.delete(COLLECTION_NAME)
            print(f"  Deleted '{COLLECTION_NAME}'")
        except Exception:
            pass

    ensure_collection(client)
    collection = client.collections.get(COLLECTION_NAME)

    # ── Build existing index (source_file → hash) ─────────────────────────────
    existing = _load_existing_index(collection)
    print(f"  Existing index: {len(existing)} source files tracked")

    # ── Scan KB files ─────────────────────────────────────────────────────────
    md_files = sorted(KB_DIR.rglob("*.md"))
    print(f"  Found {len(md_files)} markdown files in knowledge_base/")

    to_add:    list[Path] = []   # brand-new files
    to_update: list[Path] = []   # files whose content changed
    to_skip:   list[Path] = []   # unchanged

    for md_file in md_files:
        src_key  = str(md_file)
        new_hash = _file_hash(md_file)
        if src_key not in existing:
            to_add.append(md_file)
        elif existing[src_key] != new_hash:
            to_update.append(md_file)
        else:
            to_skip.append(md_file)

    # Detect deleted files (in Weaviate but no longer on disk)
    disk_keys  = {str(f) for f in md_files}
    to_delete  = [k for k in existing if k not in disk_keys]

    print(f"  New: {len(to_add)}  |  Changed: {len(to_update)}  "
          f"|  Unchanged: {len(to_skip)}  |  Deleted: {len(to_delete)}")

    if dry_run:
        if to_add:    print(f"\n  NEW ({len(to_add)}):"); [print(f"    + {f.name}") for f in to_add[:10]]
        if to_update: print(f"\n  CHANGED ({len(to_update)}):"); [print(f"    ~ {f.name}") for f in to_update[:10]]
        if to_delete: print(f"\n  DELETED ({len(to_delete)}):"); [print(f"    - {k}") for k in to_delete[:10]]
        client.close()
        return

    # ── Delete orphaned chunks (deleted files) ────────────────────────────────
    if to_delete:
        print(f"  Removing {len(to_delete)} deleted file(s) from index...")
        for src_key in tqdm(to_delete, desc="Removing deleted"):
            _delete_chunks_for_file(collection, src_key)

    # ── Delete stale chunks for changed files ─────────────────────────────────
    if to_update:
        print(f"  Removing stale chunks for {len(to_update)} changed file(s)...")
        for md_file in tqdm(to_update, desc="Clearing stale"):
            _delete_chunks_for_file(collection, str(md_file))

    # ── Index new + changed files ─────────────────────────────────────────────
    files_to_index = to_add + to_update
    if not files_to_index:
        print("  Nothing to index — all files are up to date.")
        client.close()
        return

    total_chunks   = 0
    total_sections = 0

    for md_file in tqdm(files_to_index, desc="Indexing"):
        src_key  = str(md_file)
        new_hash = _file_hash(md_file)
        text     = md_file.read_text(encoding="utf-8")
        doc_type = md_file.parent.name                        # players/teams/seasons/games
        entity   = md_file.stem.replace("_", " ").title()

        # Extract season hint from path or filename
        season   = ""
        for part in md_file.parts:
            if len(part) == 7 and part[4] == "-":   # e.g. "2022-23"
                season = part
                break

        chunks   = chunk_markdown(text)
        if not chunks:
            continue

        # Embed all chunk texts at once
        texts   = [c["content"] for c in chunks]
        vectors = model.encode(texts, batch_size=32, show_progress_bar=False)

        with collection.batch.dynamic() as batch:
            for chunk, vector in zip(chunks, vectors):
                batch.add_object(
                    properties={
                        "content":      chunk["content"],
                        "doc_type":     doc_type,
                        "entity_name":  entity,
                        "section":      chunk["section"],
                        "season":       season,
                        "source_file":  src_key,
                        "content_hash": new_hash,
                    },
                    vector={"default": vector.tolist()},
                    uuid=str(uuid.uuid4()),
                )
        total_chunks   += len(chunks)
        total_sections += len({c["section"] for c in chunks})

    print(f"\n  Indexed {len(files_to_index)} file(s): "
          f"{total_chunks} chunks across {total_sections} unique sections")
    client.close()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    force   = "--force"   in sys.argv
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("SportMind KB Loader")
    if force:
        print("Mode: FORCE (full wipe + rebuild)")
    elif dry_run:
        print("Mode: DRY RUN (no writes)")
    else:
        print("Mode: INCREMENTAL (content-hash diff)")
    print("=" * 60)

    load_all_md_files(force=force, dry_run=dry_run)
    if not dry_run:
        print("\nDone.")


if __name__ == "__main__":
    main()
