"""
Player Performance Forecasting — EWMA v3

Improvements over v2:
  - Real game logs ONLY — no synthetic data from season averages
  - 7 metrics: PTS, AST, REB, STL, BLK, FG_PCT, MIN
  - Finer alpha calibration: 10 candidates (0.05–0.50)
  - Holdout evaluation (2022-23): per-metric aggregate MAE and RMSE
  - MIN column parsed from NBA API "MM:SS" format

Model file: ml/models/player_{player_id}_{metric}.pkl
"""
import json, pickle, warnings
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from ingestion.utils import RAW_DIR

warnings.filterwarnings("ignore")
MODELS_DIR = Path("ml/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

METRICS       = ["PTS", "AST", "REB", "STL", "BLK", "FG_PCT", "MIN"]
HOLDOUT       = "2022-23"
MIN_GAMES     = 20   # minimum training games to build a model
HISTORY_WINDOW = 60  # recent game values kept for inference-time rolling
ALPHA_CANDIDATES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_min(val) -> float:
    """Parse NBA API minutes format 'MM:SS' or plain float."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return np.nan
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if ":" in s:
        parts = s.split(":")
        try:
            return float(parts[0]) + float(parts[1]) / 60
        except (ValueError, IndexError):
            return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def _prep_column(df: pd.DataFrame, metric: str) -> pd.Series:
    """Return a numeric series for the metric, with MIN parsed from MM:SS."""
    if metric == "MIN":
        return df["MIN"].apply(_parse_min)
    return pd.to_numeric(df[metric], errors="coerce")


# ── Alpha calibration ──────────────────────────────────────────────────────────

def _calibrate_alpha(values: list[float]) -> float:
    """
    Pick EWMA alpha that minimises one-step-ahead MSE on training history.
    Tests 10 candidates from 0.05 to 0.50.
    """
    if len(values) < 10:
        return 0.25
    best_alpha, best_mse = 0.25, float("inf")
    for alpha in ALPHA_CANDIDATES:
        ewma = values[0]
        mse  = 0.0
        for v in values[1:]:
            mse += (ewma - v) ** 2
            ewma = alpha * v + (1 - alpha) * ewma
        mse /= max(len(values) - 1, 1)
        if mse < best_mse:
            best_mse, best_alpha = mse, alpha
    return best_alpha


# ── Build one EWMA model ───────────────────────────────────────────────────────

def train_one(player_id: int, logs: list[dict], metric: str) -> dict | None:
    """
    Fit an EWMA model for one player / metric combination.
    Returns a parameter dict or None if insufficient data.
    """
    df = pd.DataFrame(logs)
    if df.empty or metric not in df.columns:
        return None

    df["ds"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")
    df["y"]  = _prep_column(df, metric)
    df = df.dropna(subset=["ds", "y"]).sort_values("ds").reset_index(drop=True)
    df["month"] = df["ds"].dt.month

    train_df = df[df["SEASON"] != HOLDOUT]
    if len(train_df) < MIN_GAMES:
        return None

    values = train_df["y"].tolist()

    # Distribution statistics
    overall_mean = float(np.mean(values))
    overall_std  = float(np.std(values)) or 1.0
    recent       = values[-20:]
    recent_mean  = float(np.mean(recent))
    recent_std   = float(np.std(recent)) or overall_std
    l5_mean      = float(np.mean(values[-5:])) if len(values) >= 5 else recent_mean

    # Per-month averages (mild seasonal adjustment at inference time)
    monthly_avg: dict[int, float] = {}
    for m in range(1, 13):
        sub = train_df[train_df["month"] == m]["y"]
        monthly_avg[m] = float(sub.mean()) if len(sub) >= 3 else overall_mean

    # Calibrate alpha
    alpha = _calibrate_alpha(values)

    # Percentile bands for confidence intervals
    p10 = float(np.percentile(values, 10))
    p25 = float(np.percentile(values, 25))
    p75 = float(np.percentile(values, 75))
    p90 = float(np.percentile(values, 90))

    # Recent trend: linear slope of last 20 games
    if len(recent) >= 5:
        x     = np.arange(len(recent), dtype=float)
        slope = float(np.polyfit(x, recent, 1)[0])
    else:
        slope = 0.0

    # Keep last HISTORY_WINDOW values for inference-time rolling
    history = [float(v) for v in values[-HISTORY_WINDOW:]]

    return {
        "player_id":     player_id,
        "metric":        metric,
        "alpha":         alpha,
        "overall_mean":  overall_mean,
        "overall_std":   overall_std,
        "recent_mean":   recent_mean,
        "recent_std":    recent_std,
        "l5_mean":       l5_mean,
        "monthly_avg":   monthly_avg,
        "p10": p10, "p25": p25, "p75": p75, "p90": p90,
        "slope":         slope,
        "history":       history,
        "n_train_games": len(values),
    }


# ── Holdout evaluation ─────────────────────────────────────────────────────────

def _evaluate_holdout(
    model_dict: dict,
    logs: list[dict],
    metric: str,
) -> tuple[float, float] | None:
    """
    One-step-ahead EWMA prediction on holdout season.
    Returns (MAE, RMSE) or None if <5 holdout games.
    """
    df = pd.DataFrame(logs)
    if metric not in df.columns:
        return None

    df["ds"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")
    df["y"]  = _prep_column(df, metric)
    holdout  = df[df["SEASON"] == HOLDOUT].dropna(subset=["ds", "y"]).sort_values("ds")

    if len(holdout) < 5:
        return None

    # Start EWMA from end of training history
    history = model_dict["history"]
    alpha   = model_dict["alpha"]
    ewma    = history[-1] if history else model_dict["overall_mean"]

    errors = []
    for _, row in holdout.iterrows():
        actual = float(row["y"])
        errors.append(abs(ewma - actual))
        ewma = alpha * actual + (1 - alpha) * ewma

    mae  = float(np.mean(errors))
    rmse = float(np.sqrt(np.mean([e ** 2 for e in errors])))
    return mae, rmse


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Loading player game logs...")
    path = RAW_DIR / "player_gamelogs.json"
    if not path.exists():
        print("[ERROR] player_gamelogs.json not found — run fetch_games.py first")
        return

    gamelogs: dict = json.loads(path.read_text(encoding="utf-8"))
    print(f"  {len(gamelogs)} players with real game logs")

    # Remove stale model files
    old_models = list(MODELS_DIR.glob("player_*.pkl"))
    if old_models:
        print(f"  Removing {len(old_models)} old player model files...")
        for f in old_models:
            f.unlink()

    success  = 0
    skipped  = 0
    # Per-metric holdout errors for aggregate reporting
    holdout_errors: dict[str, list[tuple[float, float]]] = {m: [] for m in METRICS}

    for pid_str, logs in tqdm(gamelogs.items(), desc="Fitting EWMA models"):
        if not logs:
            continue
        pid = int(pid_str)

        for metric in METRICS:
            # Check metric exists in at least one log entry
            col = metric  # same key in game log dicts
            if not any(col in log for log in logs[:5]):
                skipped += 1
                continue

            result = train_one(pid, logs, metric)
            if result is None:
                skipped += 1
                continue

            # Holdout evaluation
            ho = _evaluate_holdout(result, logs, metric)
            if ho:
                holdout_errors[metric].append(ho)

            out = MODELS_DIR / f"player_{pid}_{metric.lower()}.pkl"
            with open(out, "wb") as f:
                pickle.dump(result, f)
            success += 1

    total = success + skipped
    print(f"\nFitted {success}/{total} models  ({skipped} skipped - insufficient data)")
    print(f"Models saved -> {MODELS_DIR}/")

    # ── Per-metric holdout summary ────────────────────────────────────────────
    print("\nHoldout evaluation (2022-23):")
    for metric in METRICS:
        errs = holdout_errors[metric]
        if not errs:
            print(f"  {metric:<8} no holdout data")
            continue
        avg_mae  = float(np.mean([e[0] for e in errs]))
        avg_rmse = float(np.mean([e[1] for e in errs]))
        n        = len(errs)
        print(f"  {metric:<8}  MAE={avg_mae:.3f}  RMSE={avg_rmse:.3f}  (n={n} players)")

    # ── Sample model ──────────────────────────────────────────────────────────
    sample_files = list(MODELS_DIR.glob("player_*_pts.pkl"))
    if sample_files:
        with open(sample_files[0], "rb") as f:
            sample = pickle.load(f)
        pid    = sample["player_id"]
        print(f"\nSample model (player {pid} PTS):")
        print(f"  alpha={sample['alpha']}  "
              f"overall_mean={sample['overall_mean']:.1f}  "
              f"recent_mean={sample['recent_mean']:.1f}  "
              f"slope={sample['slope']:+.3f}  "
              f"n_train={sample['n_train_games']}")
        print(f"  Percentiles: p10={sample['p10']:.1f}  p25={sample['p25']:.1f}  "
              f"p75={sample['p75']:.1f}  p90={sample['p90']:.1f}")


if __name__ == "__main__":
    main()
