import { useState } from "react";
import ChatPanel       from "./components/ChatPanel";
import StatsPanel      from "./components/StatsPanel";
import PredictionPanel from "./components/PredictionPanel";
import GraphExplorer   from "./components/GraphExplorer";
import KnowledgePanel  from "./components/KnowledgePanel";
import "./App.css";

const TABS = [
  { id: "stats",     label: "📊 Stats"     },
  { id: "predict",   label: "🎯 Predict"   },
  { id: "graph",     label: "🕸️ Graph"    },
  { id: "knowledge", label: "📁 Knowledge" },
];

export default function App() {
  const [rightTab, setRightTab] = useState("stats");

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <span className="logo-icon">🏀</span>
          <span className="logo-text">SportMind</span>
          <span className="logo-sub">NBA Analytics · 2013–2023</span>
        </div>
      </header>

      <main className="app-main">
        <section className="left-pane">
          <ChatPanel />
        </section>

        <section className="right-pane">
          <div className="right-tab-bar">
            {TABS.map(t => (
              <button
                key={t.id}
                className={`right-tab ${rightTab === t.id ? "active" : ""}`}
                onClick={() => setRightTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="right-content">
            {rightTab === "stats"     && <StatsPanel />}
            {rightTab === "predict"   && <PredictionPanel />}
            {rightTab === "graph"     && <GraphExplorer />}
            {rightTab === "knowledge" && <KnowledgePanel />}
          </div>
        </section>
      </main>
    </div>
  );
}
