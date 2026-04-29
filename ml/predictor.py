"""
ML inference — win probability + player performance forecast.

Both functions are cached in-process after the first call.

Win probability model (v3):
  - Selected features from 32 candidates (correlation + importance pruning)
  - Isotonic-calibrated XGBoost with H2H and venue-specific win rates
  - Artifact keys: model, calibrator, features, snapshot, h2h,
                   name_to_id, abbr_to_id, id_to_name

Player forecast model (v3, EWMA):
  - 7 metrics: PTS, AST, REB, STL, BLK, FG_PCT, MIN
  - Per-player alpha calibrated from 10 candidates
  - Returns predicted value + confidence band + trend direction
"""
import json
import pickle
import unicodedata
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from ingestion.utils import RAW_DIR

MODELS_DIR = Path("ml/models")

VALID_METRICS = ("PTS", "AST", "REB", "STL", "BLK", "FG_PCT", "MIN")

# ── Model cache ────────────────────────────────────────────────────────────────

_win_artifact:  dict | None = None
_player_models: dict        = {}     # {(player_id, metric_lower): model_dict}
_player_id_map: dict | None = None   # name_lower → player_id


def _load_win_artifact() -> dict:
    global _win_artifact
    if _win_artifact is None:
        path = MODELS_DIR / "win_probability.pkl"
        if not path.exists():
            raise FileNotFoundError(
                "Win probability model not found — run: "
                "python -m ml.train_win_probability"
            )
        with open(path, "rb") as f:
            _win_artifact = pickle.load(f)
    return _win_artifact


def _load_player_model(player_id: int, metric: str) -> dict | None:
    key = (player_id, metric.lower())
    if key not in _player_models:
        path = MODELS_DIR / f"player_{player_id}_{metric.lower()}.pkl"
        if not path.exists():
            return None
        with open(path, "rb") as f:
            _player_models[key] = pickle.load(f)
    return _player_models.get(key)


def _build_player_id_map() -> dict:
    global _player_id_map
    if _player_id_map is None:
        stats = json.loads((RAW_DIR / "players_stats.json").read_text(encoding="utf-8"))
        m: dict[str, int] = {}
        for row in stats:
            name = row.get("PLAYER_NAME", "")
            if name:
                m[name.lower()] = row["PLAYER_ID"]
        _player_id_map = m
    return _player_id_map


# ── Win probability ────────────────────────────────────────────────────────────

def predict_win_probability(
    home_team:      str,
    away_team:      str,
    home_rest_days: int = 2,
    away_rest_days: int = 2,
    season_stage:   int = 1,
) -> dict:
    """
    Predict P(home team wins).

    Args:
        home_team / away_team: team name or abbreviation (partial match OK)
        home_rest_days / away_rest_days: days since last game (default 2)
        season_stage: 0=early 1=mid 2=late 3=playoffs

    Returns dict with home/away win probability and an explanatory note.
    """
    artifact   = _load_win_artifact()
    model      = artifact["model"]
    calibrator = artifact.get("calibrator")
    features   = artifact["features"]
    snapshot   = artifact.get("snapshot", {})         # {team_id: feature dict}
    h2h_dict   = artifact.get("h2h", {})              # {(h_tid, a_tid): float}
    name_to_id = artifact.get("name_to_id", {})
    abbr_to_id = artifact.get("abbr_to_id", {})
    id_to_name = artifact.get("id_to_name", {})

    def _resolve_id(name: str) -> int | None:
        nl = name.lower()
        if nl in name_to_id: return name_to_id[nl]
        if nl in abbr_to_id: return abbr_to_id[nl]
        for k, v in name_to_id.items():
            if nl in k or k in nl: return v
        for k, v in abbr_to_id.items():
            if nl in k or k in nl: return v
        return None

    _SNAP_DEFAULTS = {
        "win_rate_l5": 0.5,  "win_rate_l10": 0.5,  "win_rate_ssn": 0.5,
        "pts_avg_l5":  110.0, "pa_avg_l5":   110.0, "net_l5":       0.0,
        "pts_avg_l10": 110.0, "pa_avg_l10":  110.0, "net_l10":      0.0,
        "streak": 0,
        "venue_win_rate_home": 0.5, "venue_win_rate_away": 0.5,
    }

    def _lookup(tid: int | None) -> dict:
        if tid and tid in snapshot:
            return snapshot[tid]
        return dict(_SNAP_DEFAULTS)

    h_id = _resolve_id(home_team)
    a_id = _resolve_id(away_team)
    h    = _lookup(h_id)
    a    = _lookup(a_id)

    h2h_wr = h2h_dict.get((h_id, a_id), 0.5) if (h_id and a_id) else 0.5
    h_b2b  = 1 if home_rest_days <= 1 else 0
    a_b2b  = 1 if away_rest_days <= 1 else 0
    h_stk  = max(-5, min(5, h["streak"]))
    a_stk  = max(-5, min(5, a["streak"]))

    all_feat = {
        "home_flag":           1,
        "home_win_rate_l5":    h["win_rate_l5"],     "away_win_rate_l5":    a["win_rate_l5"],
        "home_win_rate_l10":   h["win_rate_l10"],    "away_win_rate_l10":   a["win_rate_l10"],
        "home_win_rate_ssn":   h["win_rate_ssn"],    "away_win_rate_ssn":   a["win_rate_ssn"],
        "home_pts_avg_l5":     h["pts_avg_l5"],      "away_pts_avg_l5":     a["pts_avg_l5"],
        "home_pa_avg_l5":      h["pa_avg_l5"],       "away_pa_avg_l5":      a["pa_avg_l5"],
        "home_net_l5":         h["net_l5"],           "away_net_l5":         a["net_l5"],
        "home_pts_avg_l10":    h["pts_avg_l10"],     "away_pts_avg_l10":    a["pts_avg_l10"],
        "home_pa_avg_l10":     h["pa_avg_l10"],      "away_pa_avg_l10":     a["pa_avg_l10"],
        "home_net_l10":        h["net_l10"],          "away_net_l10":        a["net_l10"],
        "home_rest_days":      home_rest_days,        "away_rest_days":      away_rest_days,
        "home_b2b":            h_b2b,                "away_b2b":            a_b2b,
        "rest_diff":           home_rest_days - away_rest_days,
        "home_streak":         h_stk,                "away_streak":         a_stk,
        "h2h_home_win_rate":   h2h_wr,
        "home_venue_win_rate": h.get("venue_win_rate_home", 0.5),
        "away_venue_win_rate": a.get("venue_win_rate_away", 0.5),
        "win_rate_diff":       h["win_rate_l10"] - a["win_rate_l10"],
        "net_diff":            h["net_l10"] - a["net_l10"],
        "season_stage":        season_stage,
    }

    X        = pd.DataFrame([{f: all_feat.get(f, 0.0) for f in features}])
    raw_prob = float(model.predict_proba(X)[0][1])

    if calibrator is not None:
        prob_home = float(calibrator.predict([raw_prob])[0])
    else:
        prob_home = raw_prob

    prob_home = round(max(0.01, min(0.99, prob_home)), 3)
    prob_away = round(1.0 - prob_home, 3)

    h_name   = id_to_name.get(h_id, home_team) if h_id else home_team
    a_name   = id_to_name.get(a_id, away_team) if a_id else away_team
    h2h_note = (f" H2H (at home): {round(h2h_wr * 100)}% home-win rate."
                if (h_id and a_id and (h_id, a_id) in h2h_dict) else "")
    b2b_note = ""
    if h_b2b: b2b_note += f" {h_name} is on a back-to-back."
    if a_b2b: b2b_note += f" {a_name} is on a back-to-back."

    note = (
        f"{h_name} (home) last-10 win rate: {round(h['win_rate_l10']*100)}% vs "
        f"{a_name} (away): {round(a['win_rate_l10']*100)}%. "
        f"Net-rating edge: {h['net_l10'] - a['net_l10']:+.1f} pts.{h2h_note}{b2b_note}"
    )

    return {
        "home_team":            home_team,
        "away_team":            away_team,
        "home_win_probability": prob_home,
        "away_win_probability": prob_away,
        "note":                 note,
    }


# ── Player performance forecast ────────────────────────────────────────────────

def _ewma_forecast(
    history:     list[float],
    alpha:       float,
    n_games:     int,
    monthly_avg: dict[int, float],
    p25:         float,
    p75:         float,
    slope:       float,
) -> list[dict]:
    """EWMA forecast for n_games future games with percentile confidence band."""
    if not history:
        return []

    ewma = history[0]
    for v in history[1:]:
        ewma = alpha * v + (1 - alpha) * ewma

    # Trend adjustment capped at ±20% of current ewma
    trend_adj = min(abs(slope) * 0.5, abs(ewma) * 0.20) * (1 if slope >= 0 else -1)

    base_date = datetime.now()
    band_half = (p75 - p25) / 2
    results   = []

    for i in range(n_games):
        game_date = base_date + timedelta(days=i * 2)
        month     = game_date.month
        m_avg     = monthly_avg.get(month, ewma)
        predicted = 0.90 * (ewma + trend_adj * (i / max(n_games, 1))) + 0.10 * m_avg
        predicted = max(0.0, predicted)
        results.append({
            "game":      i + 1,
            "date":      game_date.strftime("%Y-%m-%d"),
            "predicted": round(predicted, 3 if p75 < 1.1 else 1),   # more decimals for FG_PCT
            "upper":     round(max(0.0, predicted + band_half), 3 if p75 < 1.1 else 1),
            "lower":     round(max(0.0, predicted - band_half), 3 if p75 < 1.1 else 1),
        })
    return results


def _normalize(s: str) -> str:
    """Strip accents for fuzzy name matching (e.g. 'Jokić' → 'Jokic')."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def _find_player_id(player_name: str) -> int | None:
    id_map  = _build_player_id_map()
    name_l  = player_name.lower()
    name_n  = _normalize(player_name)
    norm_map = {_normalize(k): v for k, v in id_map.items()}

    if name_l in id_map:    return id_map[name_l]
    if name_n in norm_map:  return norm_map[name_n]
    for k, v in norm_map.items():
        if name_n in k:     return v
    for k, v in id_map.items():
        if name_l in k:     return v
    return None


def forecast_player_performance(
    player_name: str,
    metric:      str = "pts",
    periods:     int = 10,
) -> dict:
    """
    Forecast a player's per-game stat for the next N games.

    Supported metrics: pts, ast, reb, stl, blk, fg_pct, min

    Returns dict with avg_predicted, trend, confidence band, and per-game forecast list.
    """
    metric_upper = metric.upper()
    if metric_upper not in VALID_METRICS:
        valid_str = ", ".join(m.lower() for m in VALID_METRICS)
        return {"error": f"Unknown metric '{metric}'. Use: {valid_str}."}

    pid = _find_player_id(player_name)
    if pid is None:
        return {"error": f"Player '{player_name}' not found."}

    mdl = _load_player_model(pid, metric_upper)
    if mdl is None:
        return {
            "error": (
                f"No forecast model for {player_name} ({metric_upper}). "
                "Player may have insufficient game log data."
            )
        }

    forecast = _ewma_forecast(
        history     = mdl["history"],
        alpha       = mdl["alpha"],
        n_games     = periods,
        monthly_avg = mdl["monthly_avg"],
        p25         = mdl["p25"],
        p75         = mdl["p75"],
        slope       = mdl["slope"],
    )

    if not forecast:
        return {"error": "Forecast generation failed."}

    avg_pred    = round(float(np.mean([f["predicted"] for f in forecast])),
                        3 if mdl["p75"] < 1.1 else 1)
    trend_label = (
        "trending up"   if mdl["slope"] > 0.05 else
        "trending down" if mdl["slope"] < -0.05 else
        "stable"
    )

    return {
        "player":          player_name,
        "metric":          metric_upper,
        "periods":         periods,
        "avg_predicted":   avg_pred,
        "recent_mean":     round(mdl["recent_mean"],  3 if mdl["p75"] < 1.1 else 1),
        "overall_mean":    round(mdl["overall_mean"], 3 if mdl["p75"] < 1.1 else 1),
        "trend":           trend_label,
        "confidence_band": {
            "p25": round(mdl["p25"], 3 if mdl["p75"] < 1.1 else 1),
            "p75": round(mdl["p75"], 3 if mdl["p75"] < 1.1 else 1),
        },
        "forecast": forecast,
    }
