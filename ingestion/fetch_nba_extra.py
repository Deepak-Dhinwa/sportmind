"""
Fetch additional NBA data we don't have yet:
  1. Player career stats (totals + per-game across ALL seasons, not just 2013-23)
  2. Team season records (wins, losses, pace, offensive/defensive rating)
  3. Season leaders (PTS, AST, REB, STL, BLK, FG%, 3P% leaders per season)

Saves to data/nba_extra/

Run: python -m ingestion.fetch_nba_extra
"""
import os, time, json
import pandas as pd
from pathlib import Path
from nba_api.stats.endpoints import (
    leagueleaders,
    teamestimatedmetrics,
    commonteamroster,
)
from nba_api.stats.static import teams as nba_teams_static

OUT = Path("data/nba_extra")
OUT.mkdir(parents=True, exist_ok=True)

SEASONS = [
    "2013-14","2014-15","2015-16","2016-17","2017-18",
    "2018-19","2019-20","2020-21","2021-22","2022-23",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer":    "https://www.nba.com/",
    "Origin":     "https://www.nba.com",
}


def fetch_league_leaders(season: str) -> pd.DataFrame | None:
    """Top 200 players by PTS for a season — includes many useful per-game cols."""
    try:
        r = leagueleaders.LeagueLeaders(
            season=season,
            stat_category_abbreviation="PTS",
            per_mode48="PerGame",
            scope="S",
            season_type_all_star="Regular Season",
        )
        df = r.get_data_frames()[0]
        df["season"] = season
        return df
    except Exception as e:
        print(f"  ERROR leaders {season}: {e}")
        return None


def fetch_team_metrics(season: str) -> pd.DataFrame | None:
    """Team estimated net rating, pace, off/def rating per season."""
    try:
        r = teamestimatedmetrics.TeamEstimatedMetrics(
            season=season,
            season_type="Regular Season",
        )
        df = r.get_data_frames()[0]
        df["season"] = season
        return df
    except Exception as e:
        print(f"  ERROR team metrics {season}: {e}")
        return None


if __name__ == "__main__":
    # ── 1. League leaders per season ─────────────────────────────────────────
    print("=== League leaders ===")
    leaders_all = []
    for season in SEASONS:
        p = OUT / f"leaders_{season}.csv"
        if p.exists():
            print(f"  skip {season}")
            leaders_all.append(pd.read_csv(p))
            continue
        print(f"  Fetching {season}...")
        df = fetch_league_leaders(season)
        if df is not None:
            df.to_csv(p, index=False)
            print(f"  -> {len(df)} rows")
            leaders_all.append(df)
        time.sleep(1.5)

    if leaders_all:
        combined = pd.concat(leaders_all, ignore_index=True)
        combined.to_csv(OUT / "leaders_all.csv", index=False)
        print(f"Leaders total: {len(combined)} rows")
        print(f"Columns: {list(combined.columns[:10])}")

    # ── 2. Team metrics per season ────────────────────────────────────────────
    print("\n=== Team metrics ===")
    metrics_all = []
    for season in SEASONS:
        p = OUT / f"team_metrics_{season}.csv"
        if p.exists():
            print(f"  skip {season}")
            metrics_all.append(pd.read_csv(p))
            continue
        print(f"  Fetching {season}...")
        df = fetch_team_metrics(season)
        if df is not None:
            df.to_csv(p, index=False)
            print(f"  -> {len(df)} rows, cols: {list(df.columns)}")
            metrics_all.append(df)
        time.sleep(1.5)

    if metrics_all:
        combined = pd.concat(metrics_all, ignore_index=True)
        combined.to_csv(OUT / "team_metrics_all.csv", index=False)
        print(f"Team metrics total: {len(combined)} rows")

    print("\nDone. Check data/nba_extra/")
