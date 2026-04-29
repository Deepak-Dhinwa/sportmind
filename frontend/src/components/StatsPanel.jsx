import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, Legend,
} from "recharts";
import {
  getTopScorers, getChampions, getAwardWinners,
  comparePlayers, getHeadToHead, getPlayerStats,
} from "../api/client";

const SEASONS = [
  "2013-14","2014-15","2015-16","2016-17","2017-18",
  "2018-19","2019-20","2020-21","2021-22","2022-23",
];
const COLORS = ["#f97316","#fb923c","#fdba74","#fed7aa","#ffedd5",
                 "#fef3c7","#fde68a","#fcd34d","#fbbf24","#f59e0b"];
const TOOLTIP_STYLE = {
  contentStyle: { background: "#1e293b", border: "1px solid #334155", borderRadius: 8 },
  labelStyle:   { color: "#f1f5f9" },
};

function SkeletonTable({ rows = 8 }) {
  return (
    <div className="skeleton-wrap">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton-bar" style={{ width: `${60 + (i % 4) * 10}%` }} />
      ))}
    </div>
  );
}

const TABS = [
  ["scorers",  "Scorers"],
  ["player",   "Player"],
  ["champions","Champs"],
  ["awards",   "Awards"],
  ["compare",  "Compare"],
  ["h2h",      "H2H"],
];

export default function StatsPanel() {
  const [tab, setTab]       = useState("scorers");
  const [season, setSeason] = useState("2022-23");

  const [scorers, setScorers]   = useState([]);
  const [scorersLoading, setSL] = useState(false);

  const [champions, setChamps]  = useState([]);
  const [champsLoading, setCL]  = useState(false);

  const [awardType, setAwardType] = useState("Most Valuable Player");
  const [awards, setAwards]       = useState([]);
  const [awardsLoading, setML]    = useState(false);

  const [p1, setP1]             = useState("LeBron James");
  const [p2, setP2]             = useState("Stephen Curry");
  const [compareResult, setCmp] = useState(null);
  const [cmpLoading, setCompL]  = useState(false);
  const [cmpError, setCmpErr]   = useState("");

  const [playerSearch, setPS]     = useState("Stephen Curry");
  const [playerData, setPD]       = useState(null);
  const [playerLoading, setPL]    = useState(false);
  const [playerError, setPErr]    = useState("");
  const [playerSeason, setPSeas]  = useState("");

  const [h2hTeam1, setH1]       = useState("Golden State Warriors");
  const [h2hTeam2, setH2]       = useState("Cleveland Cavaliers");
  const [h2hResult, setH2H]     = useState(null);
  const [h2hLoading, setH2L]    = useState(false);
  const [h2hError, setH2Err]    = useState("");

  useEffect(() => {
    if (tab === "scorers") {
      setSL(true);
      getTopScorers(season, 10).then(r => setScorers(r.data)).finally(() => setSL(false));
    }
  }, [tab, season]);

  useEffect(() => {
    if (tab === "champions" && !champions.length) {
      setCL(true);
      getChampions().then(r => setChamps(r.data)).finally(() => setCL(false));
    }
  }, [tab]);

  useEffect(() => {
    if (tab === "awards") {
      setML(true);
      setAwards([]);
      getAwardWinners(awardType).then(r => setAwards(r.data)).finally(() => setML(false));
    }
  }, [tab, awardType]);

  async function runPlayerLookup() {
    if (!playerSearch.trim()) return;
    setPL(true); setPErr(""); setPD(null);
    try {
      const r = await getPlayerStats(playerSearch.trim(), playerSeason || undefined);
      if (!r.data.player || !r.data.player.player) {
        setPErr("Player not found — check the spelling.");
      } else {
        setPD(r.data);
      }
    } catch (e) {
      setPErr(e?.response?.data?.detail || "Player lookup failed.");
    } finally { setPL(false); }
  }

  async function runCompare() {
    if (!p1.trim() || !p2.trim()) return;
    setCompL(true); setCmpErr(""); setCmp(null);
    try {
      const r = await comparePlayers(p1.trim(), p2.trim());
      setCmp(r.data);
    } catch (e) {
      setCmpErr(e?.response?.data?.detail || "Comparison failed — check player names.");
    } finally { setCompL(false); }
  }

  async function runH2H() {
    if (!h2hTeam1.trim() || !h2hTeam2.trim()) return;
    setH2L(true); setH2Err(""); setH2H(null);
    try {
      const r = await getHeadToHead(h2hTeam1.trim(), h2hTeam2.trim());
      if (!r.data.games?.length) {
        setH2Err("No matchup data found for these teams.");
      } else {
        setH2H(r.data);
      }
    } catch (e) {
      setH2Err(e?.response?.data?.detail || "Head-to-head query failed.");
    } finally { setH2L(false); }
  }

  return (
    <div className="stats-panel">
      <div className="tab-bar">
        {TABS.map(([key, label]) => (
          <button key={key} className={`tab ${tab === key ? "active" : ""}`} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>

      {/* ── Top Scorers ─────────────────────────────────────────────────────── */}
      {tab === "scorers" && (
        <div>
          <div className="controls">
            <select value={season} onChange={e => setSeason(e.target.value)}>
              {SEASONS.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          {scorersLoading ? <SkeletonTable rows={10} /> : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={scorers} layout="vertical" margin={{ left: 100 }}>
                  <XAxis type="number" domain={[0, 40]} tick={{ fill: "#cbd5e1", fontSize: 11 }} />
                  <YAxis dataKey="player" type="category" width={95} tick={{ fill: "#cbd5e1", fontSize: 11 }} />
                  <Tooltip {...TOOLTIP_STYLE} formatter={(v, n) => [`${v}`, n]} />
                  <Bar dataKey="pts" name="PPG" radius={[0, 4, 4, 0]}>
                    {scorers.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Player</th><th>Team</th><th>GP</th>
                    <th>PTS</th><th>AST</th><th>REB</th>
                    <th>STL</th><th>BLK</th><th>FG%</th><th>3P%</th>
                  </tr>
                </thead>
                <tbody>
                  {scorers.map((r, i) => (
                    <tr key={i}>
                      <td>{r.player}</td><td>{r.team}</td>
                      <td>{r.gp}</td><td><strong>{r.pts}</strong></td>
                      <td>{r.ast}</td><td>{r.reb}</td>
                      <td>{r.stl ?? "—"}</td><td>{r.blk ?? "—"}</td>
                      <td>{r.fg_pct != null ? (r.fg_pct * 100).toFixed(1) + "%" : "—"}</td>
                      <td>{r.fg3_pct != null ? (r.fg3_pct * 100).toFixed(1) + "%" : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {/* ── Player Lookup ───────────────────────────────────────────────────── */}
      {tab === "player" && (
        <div className="player-lookup">
          <div className="compare-inputs">
            <input
              value={playerSearch}
              onChange={e => setPS(e.target.value)}
              placeholder="Player name…"
              onKeyDown={e => e.key === "Enter" && runPlayerLookup()}
            />
            <select value={playerSeason} onChange={e => setPSeas(e.target.value)}>
              <option value="">All seasons</option>
              {SEASONS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button className="predict-btn" onClick={runPlayerLookup} disabled={playerLoading}>
              {playerLoading ? "Loading…" : "Search"}
            </button>
          </div>

          {playerError && <div className="error-msg">{playerError}</div>}
          {playerLoading && <SkeletonTable rows={6} />}

          {playerData && (() => {
            const bio = playerData.player;
            const stats = playerData.stats || [];
            const awards = playerData.awards || [];
            return (
              <>
                {/* Bio card */}
                <div className="player-bio-card">
                  <div className="player-bio-main">
                    <h3>{bio.player}</h3>
                    <span className="pos-tag">
                      {bio.position} · {bio.height} · {bio.weight} lbs ·{" "}
                      {bio.country} · Draft {bio.draft_year} R{bio.draft_round} #{bio.draft_pick}
                    </span>
                  </div>
                  {awards.length > 0 && (
                    <div className="awards-list" style={{ marginTop: 8 }}>
                      {[...new Map(awards.map(a => [a.award, a])).values()]
                        .slice(0, 6)
                        .map((a, i) => (
                          <span key={i} className="award-tag">{a.award}</span>
                        ))}
                      {awards.length > 6 && (
                        <span className="award-tag">+{awards.length - 6} more</span>
                      )}
                    </div>
                  )}
                </div>

                {/* Season stats table */}
                {stats.length > 0 && (
                  <table className="data-table" style={{ marginTop: 10 }}>
                    <thead>
                      <tr>
                        <th>Season</th><th>Team</th><th>GP</th>
                        <th>PTS</th><th>AST</th><th>REB</th>
                        <th>STL</th><th>BLK</th><th>FG%</th><th>3P%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.map((s, i) => (
                        <tr key={i}>
                          <td>{s.season}</td>
                          <td>{s.team || "—"}</td>
                          <td>{s.games_played ?? s.gp ?? "—"}</td>
                          <td><strong>{s.pts}</strong></td>
                          <td>{s.ast}</td><td>{s.reb}</td>
                          <td>{s.stl ?? "—"}</td><td>{s.blk ?? "—"}</td>
                          <td>{s.fg_pct != null ? (s.fg_pct * 100).toFixed(1) + "%" : "—"}</td>
                          <td>{s.fg3_pct != null ? (s.fg3_pct * 100).toFixed(1) + "%" : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* ── Champions ───────────────────────────────────────────────────────── */}
      {tab === "champions" && (
        champsLoading ? <SkeletonTable rows={10} /> : (
          <table className="data-table">
            <thead><tr><th>Season</th><th>Champion</th><th>Finals MVP</th></tr></thead>
            <tbody>
              {champions.map((r, i) => (
                <tr key={i}>
                  <td>{r.season}</td>
                  <td><strong>{r.champion}</strong></td>
                  <td>{r.finals_mvp || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}

      {/* ── Award History ─────────────────────────────────────────────────── */}
      {tab === "awards" && (
        <div>
          <div className="controls">
            <select value={awardType} onChange={e => setAwardType(e.target.value)}>
              <option value="Most Valuable Player">MVP</option>
              <option value="Defensive Player of the Year">DPOY</option>
              <option value="Rookie of the Year">Rookie of the Year</option>
              <option value="Finals MVP">Finals MVP</option>
              <option value="Most Improved Player">Most Improved</option>
              <option value="Sixth Man of the Year">Sixth Man</option>
            </select>
          </div>
          {awardsLoading ? <SkeletonTable rows={10} /> : (
            <table className="data-table">
              <thead><tr><th>Season</th><th>Winner</th><th>Team</th></tr></thead>
              <tbody>
                {awards.map((r, i) => (
                  <tr key={i}>
                    <td>{r.season}</td>
                    <td><strong>{r.player}</strong></td>
                    <td>{r.team}</td>
                  </tr>
                ))}
                {!awardsLoading && awards.length === 0 && (
                  <tr><td colSpan={3} style={{ textAlign: "center", color: "#64748b" }}>No data found</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Player Comparison ───────────────────────────────────────────────── */}
      {tab === "compare" && (
        <div className="compare-panel">
          <div className="compare-inputs">
            <input value={p1} onChange={e => setP1(e.target.value)}
              placeholder="Player 1" onKeyDown={e => e.key === "Enter" && runCompare()} />
            <span className="vs-badge">vs</span>
            <input value={p2} onChange={e => setP2(e.target.value)}
              placeholder="Player 2" onKeyDown={e => e.key === "Enter" && runCompare()} />
            <button className="predict-btn" onClick={runCompare} disabled={cmpLoading}>
              {cmpLoading ? "Loading…" : "Compare"}
            </button>
          </div>

          {cmpError && <div className="error-msg">{cmpError}</div>}
          {cmpLoading && <SkeletonTable rows={5} />}

          {compareResult && (() => {
            const d1 = compareResult.player1;
            const d2 = compareResult.player2;
            const stats  = ["PTS", "AST", "REB", "STL", "BLK"];
            const keys   = ["career_pts","career_ast","career_reb","career_stl","career_blk"];
            const chartData = stats.map((s, i) => ({
              stat: s,
              [d1.player || "P1"]: d1[keys[i]] || 0,
              [d2.player || "P2"]: d2[keys[i]] || 0,
            }));

            return (
              <>
                <ResponsiveContainer width="100%" height={190}>
                  <BarChart data={chartData}>
                    <XAxis dataKey="stat" tick={{ fill: "#cbd5e1", fontSize: 12 }} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <Tooltip {...TOOLTIP_STYLE} />
                    <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
                    <Bar dataKey={d1.player || "P1"} fill="#f97316" radius={[4,4,0,0]} />
                    <Bar dataKey={d2.player || "P2"} fill="#3b82f6" radius={[4,4,0,0]} />
                  </BarChart>
                </ResponsiveContainer>

                <div className="compare-cards">
                  {[d1, d2].map((d, ci) => (
                    <div key={ci} className="compare-card"
                      style={{ borderTopColor: ci === 0 ? "#f97316" : "#3b82f6" }}>
                      <h4>{d.player || "Unknown"}</h4>
                      <p className="pos-tag">{d.position}  ·  {d.seasons_played ?? "?"} seasons</p>
                      <div className="stat-grid">
                        {keys.map((k, i) => (
                          <div key={k} className="stat-item">
                            <span className="stat-label">{stats[i]}</span>
                            <span className="stat-val">{d[k] ?? "—"}</span>
                          </div>
                        ))}
                      </div>
                      {d.awards?.length > 0 && (
                        <div className="awards-list">
                          {d.awards.slice(0, 4).map((a, ai) => (
                            <span key={ai} className="award-tag">{a.award} {a.season}</span>
                          ))}
                          {d.awards.length > 4 && (
                            <span className="award-tag">+{d.awards.length - 4} more</span>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            );
          })()}
        </div>
      )}

      {/* ── Head-to-Head ────────────────────────────────────────────────────── */}
      {tab === "h2h" && (
        <div className="h2h-panel">
          <div className="compare-inputs">
            <input value={h2hTeam1} onChange={e => setH1(e.target.value)}
              placeholder="Team 1" onKeyDown={e => e.key === "Enter" && runH2H()} />
            <span className="vs-badge">vs</span>
            <input value={h2hTeam2} onChange={e => setH2(e.target.value)}
              placeholder="Team 2" onKeyDown={e => e.key === "Enter" && runH2H()} />
            <button className="predict-btn" onClick={runH2H} disabled={h2hLoading}>
              {h2hLoading ? "Loading…" : "Search"}
            </button>
          </div>

          {h2hError && <div className="error-msg">{h2hError}</div>}
          {h2hLoading && <SkeletonTable rows={8} />}

          {h2hResult && (
            <>
              <div className="h2h-summary">
                <div className="h2h-side">
                  <span className="h2h-name">{h2hResult.team1}</span>
                  <span className="h2h-wins orange">{h2hResult.team1_wins}W</span>
                </div>
                <span className="h2h-divider">—</span>
                <div className="h2h-side">
                  <span className="h2h-wins blue">{h2hResult.team2_wins}W</span>
                  <span className="h2h-name">{h2hResult.team2}</span>
                </div>
              </div>
              <p className="h2h-note">
                {h2hResult.team1_wins + h2hResult.team2_wins} total matchups ·
                last {h2hResult.games.length} shown
              </p>
              <table className="data-table">
                <thead>
                  <tr><th>Date</th><th>Season</th><th>Score</th><th>Winner</th></tr>
                </thead>
                <tbody>
                  {[...h2hResult.games].reverse().map((g, i) => (
                    <tr key={i} className={g.winner === h2hResult.team1 ? "row-orange" : "row-blue"}>
                      <td>{g.date}</td>
                      <td>{g.season}</td>
                      <td>{g.home_score} – {g.away_score}</td>
                      <td><strong>{g.winner}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}
