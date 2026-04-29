"""
Win Probability Model — XGBoost v3

Improvements over v2:
  - 32 candidate features: L5 + L10 windows, H2H (directed), venue-specific win rates, rest_diff
  - Two-stage feature selection: Pearson correlation pruning (|r|>0.88) + XGBoost gain pruning (<0.8%)
  - 4-fold expanding-window cross-validation (temporal, no leakage)
  - 24-combo hyperparameter grid search scored by average validation AUC
  - Isotonic regression calibration on 2021-22 held-out predictions
  - Full evaluation: AUC, Accuracy, Brier score (raw vs calibrated)

Saved artifact: {model, calibrator, features, snapshot, h2h, name_to_id, abbr_to_id, id_to_name}
"""
import json, pickle
import numpy as np
import pandas as pd
from pathlib import Path
from collections import deque
from datetime import datetime
from itertools import product

import xgboost as xgb
from sklearn.metrics import roc_auc_score, accuracy_score, brier_score_loss
from sklearn.isotonic import IsotonicRegression

from ingestion.utils import RAW_DIR

MODELS_DIR = Path("ml/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

ALL_SEASONS = [
    "2013-14", "2014-15", "2015-16", "2016-17", "2017-18",
    "2018-19", "2019-20", "2020-21", "2021-22", "2022-23",
]
# 4-fold expanding CV: each tuple is (train_end_season, val_season)
CV_FOLDS = [
    (["2013-14","2014-15","2015-16","2016-17","2017-18"],                           "2018-19"),
    (["2013-14","2014-15","2015-16","2016-17","2017-18","2018-19"],                 "2019-20"),
    (["2013-14","2014-15","2015-16","2016-17","2017-18","2018-19","2019-20"],       "2020-21"),
    (["2013-14","2014-15","2015-16","2016-17","2017-18","2018-19","2019-20","2020-21"], "2021-22"),
]
CAL_SEASON  = "2021-22"   # isotonic calibration set
TEST_SEASON = "2022-23"   # held-out final evaluation

CANDIDATE_FEATURES = [
    "home_flag",
    # L5 rolling
    "home_win_rate_l5",    "away_win_rate_l5",
    # L10 rolling
    "home_win_rate_l10",   "away_win_rate_l10",
    # Season cumulative
    "home_win_rate_ssn",   "away_win_rate_ssn",
    # L5 offense / defense
    "home_pts_avg_l5",     "away_pts_avg_l5",
    "home_pa_avg_l5",      "away_pa_avg_l5",
    "home_net_l5",         "away_net_l5",
    # L10 offense / defense
    "home_pts_avg_l10",    "away_pts_avg_l10",
    "home_pa_avg_l10",     "away_pa_avg_l10",
    "home_net_l10",        "away_net_l10",
    # Rest / fatigue
    "home_rest_days",      "away_rest_days",
    "home_b2b",            "away_b2b",
    "rest_diff",
    # Streak
    "home_streak",         "away_streak",
    # Head-to-head (directed: this home team vs this away team, at home)
    "h2h_home_win_rate",
    # Venue-specific form
    "home_venue_win_rate", "away_venue_win_rate",
    # Composite diffs
    "win_rate_diff",
    "net_diff",
    "season_stage",
]

# 24 combinations: max_depth × lr × subsample × min_child_weight
HYPERPARAMETER_GRID = list(product(
    [4, 5, 6],      # max_depth
    [0.05, 0.1],    # learning_rate
    [0.8, 0.9],     # subsample
    [3, 5],         # min_child_weight
))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_mean(q: deque, default: float) -> float:
    return float(np.mean(list(q))) if q else default


def _season_stage(date_str: str, season_type: str) -> int:
    if season_type == "Playoffs":
        return 3
    try:
        m = datetime.strptime(date_str, "%Y-%m-%d").month
    except Exception:
        return 1
    return 0 if m in (10, 11) else 2 if m in (3, 4) else 1


def _update_streak(current: int, won: bool) -> int:
    if won:
        return current + 1 if current > 0 else 1
    return current - 1 if current < 0 else -1


# ── Feature engineering ────────────────────────────────────────────────────────

def build_features(games: list[dict]) -> pd.DataFrame:
    """
    Process all games chronologically and build the feature matrix.
    State is updated AFTER recording features to prevent data leakage.
    """
    df = pd.DataFrame(games)
    df = df.dropna(subset=["home_team_id", "away_team_id", "home_score", "away_score"])
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date_dt").reset_index(drop=True)

    # Per-team rolling state
    w_l5:    dict[int, deque] = {}
    w_l10:   dict[int, deque] = {}
    pts_l5:  dict[int, deque] = {}
    pa_l5:   dict[int, deque] = {}
    pts_l10: dict[int, deque] = {}
    pa_l10:  dict[int, deque] = {}
    home_w:  dict[int, list]  = {}   # [wins, games] when playing at home
    away_w:  dict[int, list]  = {}   # [wins, games] when playing on road
    last_dt: dict[int, datetime] = {}
    streak:  dict[int, int]   = {}
    ssn_w:   dict[tuple, int] = {}
    ssn_g:   dict[tuple, int] = {}
    # Directed H2H: (home_team_id, away_team_id) → deque of outcomes (1=home win)
    h2h:     dict[tuple, deque] = {}

    rows = []
    for _, g in df.iterrows():
        htid  = int(g["home_team_id"])
        atid  = int(g["away_team_id"])
        hs    = float(g["home_score"])
        as_   = float(g["away_score"])
        dt    = g["date_dt"]
        sea   = g["season"]
        stype = str(g.get("season_type", "Regular Season"))

        for tid in (htid, atid):
            w_l5.setdefault(tid,   deque(maxlen=5))
            w_l10.setdefault(tid,  deque(maxlen=10))
            pts_l5.setdefault(tid, deque(maxlen=5))
            pa_l5.setdefault(tid,  deque(maxlen=5))
            pts_l10.setdefault(tid,deque(maxlen=10))
            pa_l10.setdefault(tid, deque(maxlen=10))
            home_w.setdefault(tid, [0, 0])
            away_w.setdefault(tid, [0, 0])

        pair = (htid, atid)
        h2h.setdefault(pair, deque(maxlen=20))

        # ── Record features BEFORE updating state ─────────────────────────────
        h_rest = min((dt - last_dt[htid]).days if htid in last_dt else 3, 14)
        a_rest = min((dt - last_dt[atid]).days if atid in last_dt else 3, 14)

        h_wr5   = _safe_mean(w_l5[htid],   0.5)
        a_wr5   = _safe_mean(w_l5[atid],   0.5)
        h_wr10  = _safe_mean(w_l10[htid],  0.5)
        a_wr10  = _safe_mean(w_l10[atid],  0.5)

        hk = (htid, sea); ak = (atid, sea)
        h_ssn_wr = (ssn_w.get(hk, 0) / ssn_g[hk]) if ssn_g.get(hk, 0) > 0 else 0.5
        a_ssn_wr = (ssn_w.get(ak, 0) / ssn_g[ak]) if ssn_g.get(ak, 0) > 0 else 0.5

        h_pts5  = _safe_mean(pts_l5[htid],  110.0)
        a_pts5  = _safe_mean(pts_l5[atid],  110.0)
        h_pa5   = _safe_mean(pa_l5[htid],   110.0)
        a_pa5   = _safe_mean(pa_l5[atid],   110.0)
        h_pts10 = _safe_mean(pts_l10[htid], 110.0)
        a_pts10 = _safe_mean(pts_l10[atid], 110.0)
        h_pa10  = _safe_mean(pa_l10[htid],  110.0)
        a_pa10  = _safe_mean(pa_l10[atid],  110.0)

        hw = home_w[htid]; aw = away_w[atid]
        h_venue_wr = (hw[0] / hw[1]) if hw[1] > 0 else 0.5
        a_venue_wr = (aw[0] / aw[1]) if aw[1] > 0 else 0.5

        h2h_wr = _safe_mean(h2h[pair], 0.5)
        h_stk  = max(-5, min(5, streak.get(htid, 0)))
        a_stk  = max(-5, min(5, streak.get(atid, 0)))

        home_win = 1 if g.get("winner_team_id") == htid else 0

        rows.append({
            "home_flag":           1,
            "home_win_rate_l5":    h_wr5,     "away_win_rate_l5":    a_wr5,
            "home_win_rate_l10":   h_wr10,    "away_win_rate_l10":   a_wr10,
            "home_win_rate_ssn":   h_ssn_wr,  "away_win_rate_ssn":   a_ssn_wr,
            "home_pts_avg_l5":     h_pts5,    "away_pts_avg_l5":     a_pts5,
            "home_pa_avg_l5":      h_pa5,     "away_pa_avg_l5":      a_pa5,
            "home_net_l5":         h_pts5 - h_pa5,    "away_net_l5":  a_pts5 - a_pa5,
            "home_pts_avg_l10":    h_pts10,   "away_pts_avg_l10":    a_pts10,
            "home_pa_avg_l10":     h_pa10,    "away_pa_avg_l10":     a_pa10,
            "home_net_l10":        h_pts10 - h_pa10,  "away_net_l10": a_pts10 - a_pa10,
            "home_rest_days":      h_rest,    "away_rest_days":      a_rest,
            "home_b2b":            1 if h_rest <= 1 else 0,
            "away_b2b":            1 if a_rest <= 1 else 0,
            "rest_diff":           h_rest - a_rest,
            "home_streak":         h_stk,     "away_streak":         a_stk,
            "h2h_home_win_rate":   h2h_wr,
            "home_venue_win_rate": h_venue_wr,
            "away_venue_win_rate": a_venue_wr,
            "win_rate_diff":       h_wr10 - a_wr10,
            "net_diff":            (h_pts10 - h_pa10) - (a_pts10 - a_pa10),
            "season_stage":        _season_stage(str(g["date"]), stype),
            "season":              sea,
            "home_win":            home_win,
        })

        # ── Update state AFTER recording ──────────────────────────────────────
        is_h = home_win; is_a = 1 - is_h

        w_l5[htid].append(is_h);    w_l5[atid].append(is_a)
        w_l10[htid].append(is_h);   w_l10[atid].append(is_a)
        pts_l5[htid].append(hs);    pts_l5[atid].append(as_)
        pa_l5[htid].append(as_);    pa_l5[atid].append(hs)
        pts_l10[htid].append(hs);   pts_l10[atid].append(as_)
        pa_l10[htid].append(as_);   pa_l10[atid].append(hs)

        home_w[htid][0] += is_h;    home_w[htid][1] += 1
        away_w[atid][0] += is_a;    away_w[atid][1] += 1

        ssn_w[hk] = ssn_w.get(hk, 0) + is_h
        ssn_g[hk] = ssn_g.get(hk, 0) + 1
        ssn_w[ak] = ssn_w.get(ak, 0) + is_a
        ssn_g[ak] = ssn_g.get(ak, 0) + 1

        h2h[pair].append(is_h)

        streak[htid] = _update_streak(streak.get(htid, 0), bool(is_h))
        streak[atid] = _update_streak(streak.get(atid, 0), bool(is_a))
        last_dt[htid] = dt
        last_dt[atid] = dt

    return pd.DataFrame(rows)


def build_team_snapshot(games: list[dict]) -> tuple[dict, dict]:
    """
    Replay all games chronologically to capture final rolling state.

    Returns:
        snapshot:  {team_id: {win_rate_l5, win_rate_l10, ..., venue_win_rate_home, ...}}
        h2h_dict:  {(home_team_id, away_team_id): win_rate}  — directed H2H
    """
    df = pd.DataFrame(games)
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date_dt").reset_index(drop=True)

    w_l5:    dict[int, deque] = {}
    w_l10:   dict[int, deque] = {}
    pts_l5:  dict[int, deque] = {}
    pa_l5:   dict[int, deque] = {}
    pts_l10: dict[int, deque] = {}
    pa_l10:  dict[int, deque] = {}
    home_w:  dict[int, list]  = {}
    away_w:  dict[int, list]  = {}
    last_dt: dict[int, datetime] = {}
    streak:  dict[int, int]   = {}
    ssn_w:   dict[tuple, int] = {}
    ssn_g:   dict[tuple, int] = {}
    h2h:     dict[tuple, deque] = {}

    for _, g in df.iterrows():
        htid = int(g["home_team_id"])
        atid = int(g["away_team_id"])
        hs   = float(g["home_score"])
        as_  = float(g["away_score"])
        dt   = g["date_dt"]
        sea  = g["season"]

        for tid in (htid, atid):
            w_l5.setdefault(tid,   deque(maxlen=5))
            w_l10.setdefault(tid,  deque(maxlen=10))
            pts_l5.setdefault(tid, deque(maxlen=5))
            pa_l5.setdefault(tid,  deque(maxlen=5))
            pts_l10.setdefault(tid,deque(maxlen=10))
            pa_l10.setdefault(tid, deque(maxlen=10))
            home_w.setdefault(tid, [0, 0])
            away_w.setdefault(tid, [0, 0])

        pair = (htid, atid)
        h2h.setdefault(pair, deque(maxlen=20))

        home_win = 1 if g.get("winner_team_id") == htid else 0
        is_h = home_win; is_a = 1 - is_h

        w_l5[htid].append(is_h);    w_l5[atid].append(is_a)
        w_l10[htid].append(is_h);   w_l10[atid].append(is_a)
        pts_l5[htid].append(hs);    pts_l5[atid].append(as_)
        pa_l5[htid].append(as_);    pa_l5[atid].append(hs)
        pts_l10[htid].append(hs);   pts_l10[atid].append(as_)
        pa_l10[htid].append(as_);   pa_l10[atid].append(hs)

        home_w[htid][0] += is_h;    home_w[htid][1] += 1
        away_w[atid][0] += is_a;    away_w[atid][1] += 1

        hk = (htid, sea); ak = (atid, sea)
        ssn_w[hk] = ssn_w.get(hk, 0) + is_h; ssn_g[hk] = ssn_g.get(hk, 0) + 1
        ssn_w[ak] = ssn_w.get(ak, 0) + is_a; ssn_g[ak] = ssn_g.get(ak, 0) + 1

        h2h[pair].append(is_h)

        streak[htid] = _update_streak(streak.get(htid, 0), bool(is_h))
        streak[atid] = _update_streak(streak.get(atid, 0), bool(is_a))
        last_dt[htid] = dt
        last_dt[atid] = dt

    snapshot: dict[int, dict] = {}
    for tid in w_l10:
        # Pick the most recent season key for this team
        team_ssn_keys = sorted([k for k in ssn_g if k[0] == tid], key=lambda k: k[1], reverse=True)
        hk = team_ssn_keys[0] if team_ssn_keys else None
        ssn_wr = (ssn_w[hk] / ssn_g[hk]) if (hk and ssn_g.get(hk, 0) > 0) else 0.5

        hw = home_w.get(tid, [0, 0])
        aw = away_w.get(tid, [0, 0])

        snapshot[tid] = {
            "win_rate_l5":         _safe_mean(w_l5[tid],   0.5),
            "win_rate_l10":        _safe_mean(w_l10[tid],  0.5),
            "win_rate_ssn":        ssn_wr,
            "pts_avg_l5":          _safe_mean(pts_l5[tid], 110.0),
            "pa_avg_l5":           _safe_mean(pa_l5[tid],  110.0),
            "net_l5":              _safe_mean(pts_l5[tid], 110.0) - _safe_mean(pa_l5[tid], 110.0),
            "pts_avg_l10":         _safe_mean(pts_l10[tid],110.0),
            "pa_avg_l10":          _safe_mean(pa_l10[tid], 110.0),
            "net_l10":             _safe_mean(pts_l10[tid],110.0) - _safe_mean(pa_l10[tid], 110.0),
            "streak":              max(-5, min(5, streak.get(tid, 0))),
            "last_game_date":      last_dt.get(tid, datetime(2023, 4, 10)).strftime("%Y-%m-%d"),
            "venue_win_rate_home": (hw[0] / hw[1]) if hw[1] > 0 else 0.5,
            "venue_win_rate_away": (aw[0] / aw[1]) if aw[1] > 0 else 0.5,
        }

    # Convert H2H deques to scalar win rates
    h2h_dict = {pair: _safe_mean(vals, 0.5) for pair, vals in h2h.items() if vals}

    return snapshot, h2h_dict


# ── Feature selection ──────────────────────────────────────────────────────────

def select_features(df: pd.DataFrame) -> list[str]:
    """
    Two-stage feature selection on the training partition:
      Stage 1 — Pearson |r| > 0.88: drop one of each correlated pair
      Stage 2 — XGBoost gain < 0.8%: drop low-importance features
    """
    feat_cols = [c for c in CANDIDATE_FEATURES if c in df.columns]
    X = df[feat_cols].copy()
    y = df["home_win"]

    # Stage 1: correlation pruning
    corr   = X.corr().abs()
    upper  = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1))
    to_drop: set[str] = set()
    for col in upper.columns:
        high = upper[col][upper[col] > 0.88].index.tolist()
        for drop_col in high:
            if drop_col not in to_drop:
                to_drop.add(drop_col)

    after_corr = [f for f in feat_cols if f not in to_drop]
    print(f"  Correlation pruning: {len(feat_cols)} -> {len(after_corr)} "
          f"(dropped: {sorted(to_drop)})")

    # Stage 2: importance pruning with a probe model
    probe = xgb.XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
        eval_metric="auc", use_label_encoder=False,
    )
    probe.fit(X[after_corr], y)

    scores  = probe.get_booster().get_score(importance_type="gain")
    imp     = pd.Series(scores).reindex(after_corr, fill_value=0.0)
    total   = imp.sum()
    imp_pct = imp / total if total > 0 else imp

    selected = imp_pct[imp_pct >= 0.008].index.tolist()
    print(f"  Importance pruning: {len(after_corr)} -> {len(selected)} features")
    print("  Importances (%):")
    for f in sorted(imp_pct.index, key=lambda x: -imp_pct[x]):
        marker = "  [keep]" if f in selected else "  [drop]"
        print(f"    {marker} {f:<30} {imp_pct[f]*100:.2f}%")

    return selected


# ── CV hyperparameter search ───────────────────────────────────────────────────

def cv_grid_search(df: pd.DataFrame, features: list[str]) -> dict:
    """4-fold expanding-window grid search. Returns best hyperparameter dict."""
    results = []

    for md, lr, ss, mcw in HYPERPARAMETER_GRID:
        fold_aucs = []
        for train_seasons, val_season in CV_FOLDS:
            tr = df[df["season"].isin(train_seasons)]
            va = df[df["season"] == val_season]
            if len(va) < 10:
                continue

            m = xgb.XGBClassifier(
                n_estimators=500,
                max_depth=md, learning_rate=lr, subsample=ss, min_child_weight=mcw,
                colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0,
                eval_metric="auc", early_stopping_rounds=25,
                random_state=42, use_label_encoder=False,
            )
            m.fit(
                tr[features], tr["home_win"],
                eval_set=[(va[features], va["home_win"])],
                verbose=False,
            )
            probs = m.predict_proba(va[features])[:, 1]
            fold_aucs.append(roc_auc_score(va["home_win"], probs))

        if not fold_aucs:
            continue
        avg_auc = float(np.mean(fold_aucs))
        results.append((avg_auc, {"max_depth": md, "learning_rate": lr,
                                   "subsample": ss, "min_child_weight": mcw}))

    results.sort(key=lambda x: -x[0])
    print("\n  Top-5 CV results:")
    for auc, params in results[:5]:
        print(f"    AUC={auc:.4f}  {params}")

    best_auc, best_params = results[0]
    print(f"  Best: AUC={best_auc:.4f}  {best_params}")
    return best_params


# ── Training orchestrator ──────────────────────────────────────────────────────

def train():
    print("Loading games...")
    games = json.loads((RAW_DIR / "games.json").read_text(encoding="utf-8"))
    print(f"  {len(games)} games")

    print("\nBuilding feature matrix...")
    feat_df = build_features(games)
    print(f"  {len(feat_df)} rows  ({len(CANDIDATE_FEATURES)} candidate features)")

    # Use everything except the final test season for selection + CV
    dev_df  = feat_df[feat_df["season"] != TEST_SEASON].copy()
    test_df = feat_df[feat_df["season"] == TEST_SEASON].copy()
    cal_df  = feat_df[feat_df["season"] == CAL_SEASON].copy()
    # Training set for final model: all dev seasons except calibration season
    final_train_df = feat_df[
        ~feat_df["season"].isin([TEST_SEASON, CAL_SEASON])
    ].copy()

    print(f"\n  Dev: {len(dev_df)}  Train: {len(final_train_df)}  "
          f"Cal: {len(cal_df)}  Test: {len(test_df)}")
    print(f"  Home-win rate: dev={dev_df['home_win'].mean():.3f}  "
          f"test={test_df['home_win'].mean():.3f}")

    # ── Feature selection ─────────────────────────────────────────────────────
    print("\nSelecting features...")
    features = select_features(dev_df)

    # ── CV hyperparameter search ──────────────────────────────────────────────
    print(f"\nRunning CV grid search ({len(HYPERPARAMETER_GRID)} combos × {len(CV_FOLDS)} folds)...")
    best_params = cv_grid_search(dev_df, features)

    # ── Final model ───────────────────────────────────────────────────────────
    X_tr = final_train_df[features]; y_tr = final_train_df["home_win"]
    X_ca = cal_df[features];         y_ca = cal_df["home_win"]
    X_te = test_df[features];        y_te = test_df["home_win"]

    print(f"\nTraining final model on {len(X_tr)} games (early-stop on {len(X_ca)} cal games)...")
    model = xgb.XGBClassifier(
        n_estimators=700,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        eval_metric="auc",
        early_stopping_rounds=35,
        random_state=42,
        use_label_encoder=False,
        **best_params,
    )
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_ca, y_ca)],
        verbose=100,
    )
    print(f"  Best iteration: {model.best_iteration}")

    # ── Isotonic calibration ──────────────────────────────────────────────────
    raw_cal = model.predict_proba(X_ca)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(raw_cal, y_ca)

    # ── Evaluation ────────────────────────────────────────────────────────────
    print("\nEvaluation:")
    for name, X_s, y_s in [("2021-22 (cal)", X_ca, y_ca), ("2022-23 (test)", X_te, y_te)]:
        raw   = model.predict_proba(X_s)[:, 1]
        cal   = calibrator.predict(raw)
        cal   = np.clip(cal, 0.01, 0.99)
        auc   = roc_auc_score(y_s, cal)
        acc   = accuracy_score(y_s, (cal >= 0.5).astype(int))
        brier = brier_score_loss(y_s, cal)
        raw_b = brier_score_loss(y_s, raw)
        print(f"  {name}: AUC={auc:.4f}  Acc={acc:.4f}  Brier={brier:.4f}  (raw Brier={raw_b:.4f})")

    # ── Feature importance ────────────────────────────────────────────────────
    print("\nFeature importances (gain):")
    imp = pd.Series(model.get_booster().get_score(importance_type="gain"))
    for feat, score in imp.sort_values(ascending=False).items():
        print(f"  {feat:<30} {score:.1f}")

    # ── Build inference snapshot ──────────────────────────────────────────────
    print("\nBuilding team snapshot and H2H records...")
    snapshot, h2h_dict = build_team_snapshot(games)
    print(f"  {len(snapshot)} teams  |  {len(h2h_dict)} directed H2H matchups")

    teams_raw  = json.loads((RAW_DIR / "teams.json").read_text(encoding="utf-8"))
    name_to_id = {t["full_name"].lower(): t["id"] for t in teams_raw}
    abbr_to_id = {t["abbreviation"].lower(): t["id"] for t in teams_raw}
    id_to_name = {t["id"]: t["full_name"] for t in teams_raw}

    # ── Save artifact ─────────────────────────────────────────────────────────
    out = MODELS_DIR / "win_probability.pkl"
    with open(out, "wb") as f:
        pickle.dump({
            "model":      model,
            "calibrator": calibrator,
            "features":   features,
            "snapshot":   snapshot,    # {team_id: feature dict}
            "h2h":        h2h_dict,    # {(home_tid, away_tid): float win_rate}
            "name_to_id": name_to_id,
            "abbr_to_id": abbr_to_id,
            "id_to_name": id_to_name,
        }, f)
    print(f"\nSaved -> {out}")
    print(f"  {len(features)} selected features: {features}")


if __name__ == "__main__":
    train()
