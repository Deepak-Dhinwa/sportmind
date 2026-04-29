import axios from "axios";

const BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

export const api = axios.create({ baseURL: BASE });

// ── REST helpers ──────────────────────────────────────────────────────────────
export const getTopScorers  = (season = "2022-23", limit = 10) =>
  api.get(`/stats/top-scorers?season=${season}&limit=${limit}`);

export const getPlayerStats = (name, season) =>
  api.get(`/stats/player/${encodeURIComponent(name)}${season ? `?season=${season}` : ""}`);

export const getTeamStats   = (name, season) =>
  api.get(`/stats/team/${encodeURIComponent(name)}${season ? `?season=${season}` : ""}`);

export const getChampions   = () => api.get("/stats/champions");

export const getAwardWinners = (award = "Most Valuable Player", season) =>
  api.get(`/stats/awards?award=${encodeURIComponent(award)}${season ? `&season=${season}` : ""}`);

export const getGraphNeighborhood = (entity) =>
  api.get(`/graph/neighborhood/${encodeURIComponent(entity)}`);

export const getLeagueOverview = () =>
  api.get("/graph/overview");

export const predictWin = (homeTeam, awayTeam, homeRest = 2, awayRest = 2) =>
  api.get(`/predict/win?home_team=${encodeURIComponent(homeTeam)}&away_team=${encodeURIComponent(awayTeam)}&home_rest=${homeRest}&away_rest=${awayRest}`);

export const predictPlayer = (player, metric = "pts", periods = 10) =>
  api.get(`/predict/player?player=${encodeURIComponent(player)}&metric=${metric}&periods=${periods}`);

export const comparePlayers = (player1, player2) =>
  api.get(`/stats/compare?player1=${encodeURIComponent(player1)}&player2=${encodeURIComponent(player2)}`);

export const getHeadToHead = (team1, team2, season) =>
  api.get(`/stats/head-to-head?team1=${encodeURIComponent(team1)}&team2=${encodeURIComponent(team2)}${season ? `&season=${season}` : ""}`);

// ── Knowledge base management ─────────────────────────────────────────────────
export const listKnowledgeFiles = () =>
  api.get("/knowledge/files");

export const uploadKnowledgeFile = (file, description = "") => {
  const form = new FormData();
  form.append("file", file);
  form.append("description", description);
  return api.post("/knowledge/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const deleteKnowledgeFile = (filename) =>
  api.delete(`/knowledge/files/${encodeURIComponent(filename)}`);

export const updateKnowledgeFile = (filename, file) => {
  const form = new FormData();
  form.append("file", file);
  return api.put(`/knowledge/files/${encodeURIComponent(filename)}`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

// ── WebSocket chat ────────────────────────────────────────────────────────────
export function createChatSocket(onToken, onDone, onError) {
  const ws = new WebSocket(`${WS_BASE}/chat`);

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "thinking") return;
    if (msg.type === "token")   onToken(msg.data);
    if (msg.type === "done")    onDone(msg.data, msg.sources || []);
  };

  ws.onerror = onError;
  return ws;
}
