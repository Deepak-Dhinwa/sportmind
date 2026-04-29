"""
Phase 2 — Step 2: Fetch team data for 2013-14 to 2022-23.

Strategy (fast — 10 requests total):
  - teams.get_teams()                  → static list of all 30 teams (instant)
  - LeagueDashTeamStats × 10 seasons  → season records (W, L, win%, pts, etc.)

Outputs:
  data/raw/teams.json         — [{id, name, city, abbreviation, conference, division}]
  data/raw/teams_stats.json   — [{TEAM_ID, TEAM_NAME, SEASON, W, L, W_PCT, PTS, ...}]
"""
import time
from tqdm import tqdm

from nba_api.stats.static import teams as static_teams
from nba_api.stats.endpoints import leaguedashteamstats

from ingestion.utils import RAW_DIR, SEASONS, SLEEP, request_with_retry, load_json, save_json


def fetch_static_teams() -> list[dict]:
    out_path = RAW_DIR / "teams.json"
    existing = load_json(out_path)
    if existing is not None:
        print(f"[skip] teams.json already exists ({len(existing)} teams)")
        return existing

    all_teams = static_teams.get_teams()
    save_json(out_path, all_teams)
    print(f"Saved {len(all_teams)} teams -> {out_path}")
    return all_teams


def fetch_team_season_stats() -> list[dict]:
    out_path = RAW_DIR / "teams_stats.json"
    existing = load_json(out_path)
    if existing is not None:
        print(f"[skip] teams_stats.json already exists ({len(existing)} rows)")
        return existing

    all_stats: list[dict] = []
    for season in tqdm(SEASONS, desc="Team season stats"):
        result = request_with_retry(
            lambda s=season: leaguedashteamstats.LeagueDashTeamStats(
                season=s,
                season_type_all_star="Regular Season",
                per_mode_detailed="PerGame",
            ),
            label=f"team stats {season}",
        )
        rows = result.get_normalized_dict()["LeagueDashTeamStats"]
        for row in rows:
            row["SEASON"] = season
        all_stats.extend(rows)
        time.sleep(SLEEP)

    save_json(out_path, all_stats)
    print(f"Saved {len(all_stats)} team-season rows -> {out_path}")
    return all_stats


def main():
    print("=" * 60)
    print("STEP 1: Static team list (instant)")
    print("=" * 60)
    fetch_static_teams()

    print("\n" + "=" * 60)
    print("STEP 2: Team season stats (10 requests)")
    print("=" * 60)
    fetch_team_season_stats()

    print("\nDone. Run fetch_games.py next.")


if __name__ == "__main__":
    main()
