import { useState } from "react";
import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
  ReferenceLine, ResponsiveContainer, Legend,
} from "recharts";
import { predictWin, predictPlayer } from "../api/client";

const TEAMS = [
  "Atlanta Hawks","Boston Celtics","Brooklyn Nets","Charlotte Hornets","Chicago Bulls",
  "Cleveland Cavaliers","Dallas Mavericks","Denver Nuggets","Detroit Pistons",
  "Golden State Warriors","Houston Rockets","Indiana Pacers","Los Angeles Clippers",
  "Los Angeles Lakers","Memphis Grizzlies","Miami Heat","Milwaukee Bucks",
  "Minnesota Timberwolves","New Orleans Pelicans","New York Knicks",
  "Oklahoma City Thunder","Orlando Magic","Philadelphia 76ers","Phoenix Suns",
  "Portland Trail Blazers","Sacramento Kings","San Antonio Spurs","Toronto Raptors",
  "Utah Jazz","Washington Wizards",
];

const METRIC_LABEL = { pts: "Points", ast: "Assists", reb: "Rebounds" };

const TREND_COLOR = {
  "trending up":   "#22c55e",
  "trending down": "#ef4444",
  "stable":        "#94a3b8",
};

function WinBar({ homeTeam, awayTeam, homeProb, awayProb }) {
  const homePct = Math.round(homeProb * 100);
  const awayPct = Math.round(awayProb * 100);
  return (
    <div className="win-bar-wrap">
      <div className="win-bar-labels">
        <span className="wbl home">{homeTeam.replace(/.* /, "")}</span>
        <span className="wbl away">{awayTeam.replace(/.* /, "")}</span>
      </div>
      <div className="win-bar">
        <div className="win-bar-home" style={{ width: `${homePct}%` }}>
          <span className="win-bar-pct">{homePct}%</span>
        </div>
        <div className="win-bar-away" style={{ width: `${awayPct}%` }}>
          <span className="win-bar-pct">{awayPct}%</span>
        </div>
      </div>
    </div>
  );
}

function ForecastStats({ forecast }) {
  const trend = forecast.trend || "stable";
  return (
    <div className="forecast-stats">
      <div className="fstat-card">
        <span className="fstat-label">Predicted avg</span>
        <span className="fstat-val orange">{forecast.avg_predicted}</span>
      </div>
      <div className="fstat-card">
        <span className="fstat-label">Recent mean</span>
        <span className="fstat-val">{forecast.recent_mean}</span>
      </div>
      <div className="fstat-card">
        <span className="fstat-label">Career mean</span>
        <span className="fstat-val">{forecast.overall_mean}</span>
      </div>
      <div className="fstat-card">
        <span className="fstat-label">Trend</span>
        <span className="fstat-val" style={{ color: TREND_COLOR[trend] || "#94a3b8", fontSize: 12 }}>
          {trend === "trending up" ? "▲" : trend === "trending down" ? "▼" : "—"} {trend}
        </span>
      </div>
    </div>
  );
}

export default function PredictionPanel() {
  const [tab, setTab]         = useState("win");

  const [homeTeam, setHome]     = useState("Golden State Warriors");
  const [awayTeam, setAway]     = useState("Boston Celtics");
  const [homeRest, setHomeRest] = useState(2);
  const [awayRest, setAwayRest] = useState(2);
  const [winResult, setWinR]    = useState(null);
  const [winLoading, setWinL]   = useState(false);
  const [winError, setWinErr]   = useState("");

  const [player, setPlayer]     = useState("LeBron James");
  const [metric, setMetric]     = useState("pts");
  const [periods, setPeriods]   = useState(10);
  const [forecast, setForecast] = useState(null);
  const [fLoading, setFLoad]    = useState(false);
  const [fError, setFErr]       = useState("");

  async function runWinPred() {
    setWinL(true); setWinR(null); setWinErr("");
    try {
      const r = await predictWin(homeTeam, awayTeam, homeRest, awayRest);
      setWinR(r.data);
    } catch (e) {
      setWinErr(e?.response?.data?.detail || "Win prediction failed — model may not be trained.");
    } finally { setWinL(false); }
  }

  async function runForecast() {
    setFLoad(true); setForecast(null); setFErr("");
    try {
      const r = await predictPlayer(player, metric, periods);
      if (r.data.error) { setFErr(r.data.error); setForecast(null); }
      else setForecast(r.data);
    } catch (e) {
      setFErr(e?.response?.data?.detail || "Forecast failed — player may not have a trained model.");
    } finally { setFLoad(false); }
  }

  // Build chart data: combine predicted/upper/lower into AreaChart-friendly shape
  const chartData = forecast?.forecast?.map(f => ({
    ...f,
    band: [f.lower, f.upper],          // for reference
    range: f.upper - f.lower,          // area height
    base: f.lower,                     // area start
    date: f.date.slice(5),             // "04-10" format
  })) ?? [];

  return (
    <div className="prediction-panel">
      <div className="tab-bar">
        <button className={`tab ${tab === "win" ? "active" : ""}`}
          onClick={() => setTab("win")}>Win Probability</button>
        <button className={`tab ${tab === "forecast" ? "active" : ""}`}
          onClick={() => setTab("forecast")}>Player Forecast</button>
      </div>

      {/* ── Win probability ──────────────────────────────────────────────────── */}
      {tab === "win" && (
        <div className="pred-form">
          <div className="form-row">
            <div>
              <label>Home Team</label>
              <select value={homeTeam} onChange={e => setHome(e.target.value)}>
                {TEAMS.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div className="vs-badge">vs</div>
            <div>
              <label>Away Team</label>
              <select value={awayTeam} onChange={e => setAway(e.target.value)}>
                {TEAMS.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>
          {/* Rest days */}
          <div className="rest-row">
            <div className="rest-item">
              <label>Home rest days: <strong>{homeRest}</strong></label>
              <input type="range" min={0} max={7} value={homeRest}
                onChange={e => setHomeRest(Number(e.target.value))} />
            </div>
            <div className="rest-item">
              <label>Away rest days: <strong>{awayRest}</strong></label>
              <input type="range" min={0} max={7} value={awayRest}
                onChange={e => setAwayRest(Number(e.target.value))} />
            </div>
          </div>

          <button className="predict-btn" onClick={runWinPred} disabled={winLoading}>
            {winLoading ? "Predicting…" : "Predict"}
          </button>

          {winError && <div className="error-msg">{winError}</div>}

          {winResult && (
            <div className="win-result">
              <WinBar
                homeTeam={homeTeam} awayTeam={awayTeam}
                homeProb={winResult.home_win_probability}
                awayProb={winResult.away_win_probability}
              />
              <p className="pred-note">{winResult.note}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Player forecast ───────────────────────────────────────────────────── */}
      {tab === "forecast" && (
        <div className="pred-form">
          <div className="form-row col">
            <div>
              <label>Player Name</label>
              <input
                value={player}
                onChange={e => setPlayer(e.target.value)}
                onKeyDown={e => e.key === "Enter" && runForecast()}
                placeholder="e.g. LeBron James"
              />
            </div>
            <div className="form-row">
              <div>
                <label>Metric</label>
                <select value={metric} onChange={e => setMetric(e.target.value)}>
                  <option value="pts">Points</option>
                  <option value="ast">Assists</option>
                  <option value="reb">Rebounds</option>
                </select>
              </div>
              <div>
                <label>Games</label>
                <select value={periods} onChange={e => setPeriods(Number(e.target.value))}>
                  {[5, 10, 15, 20].map(n => <option key={n}>{n}</option>)}
                </select>
              </div>
            </div>
          </div>
          <button className="predict-btn" onClick={runForecast} disabled={fLoading}>
            {fLoading ? "Forecasting…" : "Forecast"}
          </button>

          {fError && <div className="error-msg">{fError}</div>}

          {forecast && (
            <div className="forecast-result">
              <ForecastStats forecast={forecast} />

              {/* Confidence band area + predicted line */}
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <defs>
                    <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#f97316" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#f97316" stopOpacity={0.03} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 10 }} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 10 }} domain={["auto", "auto"]} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: "#f1f5f9" }}
                    formatter={(val, name) => [
                      typeof val === "number" ? val.toFixed(1) : val,
                      name === "base" ? "Lower" : name === "range" ? "Upper" : "Predicted",
                    ]}
                  />
                  {/* Confidence band: stacked areas */}
                  <Area type="monotone" dataKey="base"  stroke="none" fill="transparent" stackId="band" />
                  <Area type="monotone" dataKey="range" stroke="none" fill="url(#bandGrad)" stackId="band" />
                  {/* Predicted line on top */}
                  <Line type="monotone" dataKey="predicted" stroke="#f97316" strokeWidth={2.5}
                    dot={{ r: 3, fill: "#f97316" }} name={METRIC_LABEL[metric]} />
                  <ReferenceLine y={forecast.recent_mean} stroke="#475569"
                    strokeDasharray="4 2" label={{ value: "recent avg", fill: "#475569", fontSize: 10 }} />
                </AreaChart>
              </ResponsiveContainer>

              {forecast.note && (
                <p className="pred-note">{forecast.note}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
