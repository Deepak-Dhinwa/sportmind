import { useState, useEffect, useRef } from "react";
import {
  listKnowledgeFiles,
  uploadKnowledgeFile,
  deleteKnowledgeFile,
  updateKnowledgeFile,
} from "../api/client";

function fmt(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function fmtDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

export default function KnowledgePanel() {
  const [files, setFiles]       = useState([]);
  const [loading, setLoading]   = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError]       = useState("");
  const [success, setSuccess]   = useState("");
  const [desc, setDesc]         = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef();
  const updateRefs   = useRef({});   // {filename: fileInputRef}

  async function loadFiles() {
    setLoading(true);
    try {
      const r = await listKnowledgeFiles();
      setFiles(r.data);
    } catch (e) {
      setError("Could not load files.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadFiles(); }, []);

  function flash(msg, isErr = false) {
    if (isErr) { setError(msg); setSuccess(""); }
    else        { setSuccess(msg); setError(""); }
    setTimeout(() => { setError(""); setSuccess(""); }, 4000);
  }

  async function handleUpload(fileObj) {
    if (!fileObj) return;
    const ext = fileObj.name.split(".").pop().toLowerCase();
    if (!["md","txt"].includes(ext)) {
      return flash("Only .md or .txt files are supported.", true);
    }
    setUploading(true);
    try {
      const r = await uploadKnowledgeFile(fileObj, desc);
      flash(`"${r.data.filename}" indexed — ${r.data.chunk_count} chunks added to RAG.`);
      setDesc("");
      loadFiles();
    } catch (e) {
      flash(e?.response?.data?.detail || "Upload failed.", true);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(filename) {
    if (!confirm(`Remove "${filename}" from the knowledge base?`)) return;
    try {
      await deleteKnowledgeFile(filename);
      flash(`"${filename}" removed.`);
      loadFiles();
    } catch (e) {
      flash(e?.response?.data?.detail || "Delete failed.", true);
    }
  }

  async function handleUpdate(filename, fileObj) {
    if (!fileObj) return;
    try {
      const r = await updateKnowledgeFile(filename, fileObj);
      flash(`"${filename}" re-indexed — ${r.data.chunk_count} chunks.`);
      loadFiles();
    } catch (e) {
      flash(e?.response?.data?.detail || "Update failed.", true);
    }
  }

  // Drag and drop
  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const fileObj = e.dataTransfer.files[0];
    if (fileObj) handleUpload(fileObj);
  }

  return (
    <div className="knowledge-panel">
      <h3 className="kb-title">Custom Knowledge Base</h3>
      <p className="kb-subtitle">
        Upload your own .md or .txt files. They'll be chunked, embedded,
        and used by the RAG agent immediately.
      </p>

      {/* Upload zone */}
      <div
        className={`kb-drop-zone ${dragOver ? "drag-over" : ""}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <span className="kb-drop-icon">📄</span>
        <span className="kb-drop-text">
          {uploading ? "Indexing…" : "Click or drag a .md / .txt file here"}
        </span>
        <input
          ref={fileInputRef}
          type="file"
          accept=".md,.txt"
          style={{ display: "none" }}
          onChange={e => handleUpload(e.target.files[0])}
        />
      </div>

      {/* Optional description */}
      <input
        className="kb-desc-input"
        value={desc}
        onChange={e => setDesc(e.target.value)}
        placeholder="Optional: short description of this file"
      />

      {/* Status messages */}
      {error   && <div className="error-msg">{error}</div>}
      {success && <div className="success-msg">{success}</div>}

      {/* File list */}
      <div className="kb-file-list">
        <div className="kb-list-header">
          <span>Your files ({files.length})</span>
          <button className="kb-refresh-btn" onClick={loadFiles} disabled={loading}>
            {loading ? "…" : "↻"}
          </button>
        </div>

        {files.length === 0 && !loading && (
          <p className="kb-empty">No custom files yet. Upload one above.</p>
        )}

        {files.map(f => (
          <div key={f.filename} className="kb-file-row">
            <div className="kb-file-info">
              <span className="kb-file-name">{f.filename}</span>
              <span className="kb-file-meta">
                {f.chunk_count} chunks · {fmt(f.size_bytes)} · {fmtDate(f.uploaded_at)}
              </span>
              {f.description && (
                <span className="kb-file-desc">{f.description}</span>
              )}
            </div>
            <div className="kb-file-actions">
              {/* Hidden file input for update */}
              <input
                type="file"
                accept=".md,.txt"
                style={{ display: "none" }}
                ref={el => updateRefs.current[f.filename] = el}
                onChange={e => handleUpdate(f.filename, e.target.files[0])}
              />
              <button
                className="kb-btn update"
                title="Replace file content"
                onClick={() => updateRefs.current[f.filename]?.click()}
              >
                Update
              </button>
              <button
                className="kb-btn delete"
                title="Remove from knowledge base"
                onClick={() => handleDelete(f.filename)}
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Info section */}
      <div className="kb-info">
        <p>💡 <strong>Tips:</strong></p>
        <ul>
          <li>Use <code>## Section</code> headers to help the chunker split content logically.</li>
          <li>Start with a <code># Title</code> line — it's prepended to every chunk for context.</li>
          <li>Max file size: 2 MB. Supported formats: <code>.md</code>, <code>.txt</code></li>
          <li>After upload, ask the chat anything about your file immediately.</li>
        </ul>
      </div>
    </div>
  );
}
