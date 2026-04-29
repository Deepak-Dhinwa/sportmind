import { useState, useCallback, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { getGraphNeighborhood, getLeagueOverview } from "../api/client";

const NODE_COLORS = {
  Player: "#f97316",
  Team:   "#3b82f6",
  Award:  "#a855f7",
  Season: "#22c55e",
  Game:   "#64748b",
  PlayerSeasonStats: "#0ea5e9",
};

const QUICK_NODES = [
  "LeBron James","Stephen Curry","Kevin Durant",
  "Golden State Warriors","Cleveland Cavaliers","Miami Heat",
];

export default function GraphExplorer() {
  const [viewMode, setViewMode]       = useState("neighborhood"); // "neighborhood" | "league"
  const [query, setQuery]             = useState("");
  const [graphData, setGraphData]     = useState({ nodes: [], links: [] });
  const [selected, setSelected]       = useState(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");
  const [history, setHistory]         = useState([]);
  const [centerLabel, setCenterLabel] = useState("");
  const fgRef = useRef();

  // ── Neighborhood mode ────────────────────────────────────────────────────────
  async function loadGraph(entityName, pushHistory = false) {
    const name = (entityName || query).trim();
    if (!name) return;
    setLoading(true); setError(""); setSelected(null);
    try {
      const r = await getGraphNeighborhood(name);
      const { nodes, links } = r.data;
      if (!nodes?.length) {
        setError(`No graph data found for "${name}"`);
        setGraphData({ nodes: [], links: [] });
      } else {
        if (pushHistory && centerLabel) {
          setHistory(h => [...h, centerLabel]);
        }
        setGraphData({ nodes, links });
        setCenterLabel(name);
        setQuery(name);
        setTimeout(() => fgRef.current?.zoomToFit(400, 40), 300);
      }
    } catch(e) {
      setError("Graph query failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  function goBack() {
    const prev = history[history.length - 1];
    if (!prev) return;
    setHistory(h => h.slice(0, -1));
    loadGraph(prev, false);
  }

  // ── League overview mode ─────────────────────────────────────────────────────
  async function loadLeagueOverview() {
    setLoading(true); setError(""); setSelected(null);
    try {
      const r = await getLeagueOverview();
      const { nodes, links } = r.data;
      if (!nodes?.length) {
        setError("No league data returned.");
        setGraphData({ nodes: [], links: [] });
      } else {
        setGraphData({ nodes, links });
        setTimeout(() => fgRef.current?.zoomToFit(600, 60), 400);
      }
    } catch(e) {
      setError("League overview failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  // ── Switch view mode ─────────────────────────────────────────────────────────
  function switchMode(mode) {
    setViewMode(mode);
    setGraphData({ nodes: [], links: [] });
    setSelected(null);
    setError("");
    setHistory([]);
    setCenterLabel("");
    if (mode === "league") {
      loadLeagueOverview();
    }
  }

  // ── Node rendering ───────────────────────────────────────────────────────────
  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const label    = node.label || "";
    const fontSize = Math.max(10 / globalScale, 3);
    const r        = 6;
    const color    = NODE_COLORS[node.type] || "#94a3b8";
    const isCenter = viewMode === "neighborhood" && node.label === centerLabel;

    ctx.beginPath();
    ctx.arc(node.x, node.y, isCenter ? r + 2 : r, 0, 2 * Math.PI);
    ctx.fillStyle = node === selected ? "#fff" : color;
    ctx.fill();
    ctx.strokeStyle = isCenter ? "#fff" : color;
    ctx.lineWidth   = isCenter ? 2.5 : (node === selected ? 2 : 0.5);
    ctx.stroke();

    if (globalScale > 1.2) {
      ctx.font         = `${fontSize}px Sans-Serif`;
      ctx.fillStyle    = "#e2e8f0";
      ctx.textAlign    = "center";
      ctx.textBaseline = "top";
      ctx.fillText(label.length > 18 ? label.slice(0, 16) + "…" : label, node.x, node.y + r + 2);
    }
  }, [selected, centerLabel, viewMode]);

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="graph-explorer">

      {/* View mode toggle */}
      <div className="graph-mode-toggle">
        <button
          className={`mode-btn ${viewMode === "neighborhood" ? "active" : ""}`}
          onClick={() => switchMode("neighborhood")}
        >
          🔍 Neighborhood
        </button>
        <button
          className={`mode-btn ${viewMode === "league" ? "active" : ""}`}
          onClick={() => switchMode("league")}
        >
          🏀 League View
        </button>
      </div>

      {/* Neighborhood controls */}
      {viewMode === "neighborhood" && (
        <>
          <div className="graph-search">
            {history.length > 0 && (
              <button className="back-btn" onClick={goBack}
                title={`Back to ${history[history.length - 1]}`}>
                ← Back
              </button>
            )}
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && loadGraph(query, !!centerLabel)}
              placeholder="Enter player or team name..."
            />
            <button onClick={() => loadGraph(query, !!centerLabel)}
              disabled={loading || !query.trim()}>
              {loading ? "Loading..." : "Explore"}
            </button>
          </div>

          <div className="quick-chips">
            {QUICK_NODES.map(n => (
              <button key={n} className="chip"
                onClick={() => loadGraph(n, !!centerLabel)}>
                {n}
              </button>
            ))}
          </div>
        </>
      )}

      {/* League view header */}
      {viewMode === "league" && (
        <div className="league-view-header">
          <span>All 30 NBA teams · championships · top players</span>
          <button className="chip" onClick={loadLeagueOverview} disabled={loading}>
            {loading ? "Loading…" : "↺ Refresh"}
          </button>
        </div>
      )}

      {/* Legend */}
      <div className="graph-legend">
        {Object.entries(NODE_COLORS).slice(0, 4).map(([type, color]) => (
          <span key={type} className="legend-item">
            <span className="legend-dot" style={{ background: color }} />
            {type}
          </span>
        ))}
        <span className="legend-item graph-hint">· click to select · double-click to explore</span>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Graph canvas */}
      <div className="graph-canvas">
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={fgRef}
            graphData={graphData}
            nodeId="id"
            nodeCanvasObject={nodeCanvasObject}
            nodeCanvasObjectMode={() => "replace"}
            linkColor={() => "#334155"}
            linkWidth={1}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            backgroundColor="#0f172a"
            onNodeClick={node => {
              if (node === selected) {
                setSelected(null);
                if (node.type === "Player" || node.type === "Team") {
                  setViewMode("neighborhood");
                  setHistory([]);
                  setCenterLabel("");
                  loadGraph(node.label, false);
                }
              } else {
                setSelected(node);
              }
            }}
            enableZoomInteraction
            enablePanInteraction
          />
        ) : (
          <div className="graph-empty">
            {loading
              ? "Building graph…"
              : viewMode === "league"
                ? "Loading league overview…"
                : "Search for a player or team to explore their connections"}
          </div>
        )}
      </div>

      {/* Selected node detail panel */}
      {selected && (
        <div className="node-detail">
          <div className="node-detail-header">
            <div>
              <h4>{selected.label}</h4>
              <span className="node-type-badge"
                style={{ background: NODE_COLORS[selected.type] || "#475569" }}>
                {selected.type}
              </span>
            </div>
            {(selected.type === "Player" || selected.type === "Team") && (
              <button className="explore-node-btn"
                onClick={() => {
                  setSelected(null);
                  setViewMode("neighborhood");
                  setHistory([]);
                  setCenterLabel("");
                  loadGraph(selected.label, false);
                }}>
                Explore →
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
