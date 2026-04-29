"""
Phase 2 — Step 3: Fetch game data for 2013-14 to 2022-23.

Strategy:
  - LeagueGameLog × 10 seasons (regular) + × 10 (playoffs) = 20 requests
    → all ~12,300 regular season + playoff games, deduplicated
  - PlayerGameLog for top 50 players × 10 seasons = 500 requests (~5 min)
    → per-game logs needed to train Prophet forecasting models

Outputs:
  data/raw/games.json               — deduplicated game records
  data/raw/player_gamelogs.json     — per-game logs for top 50 players
"""
import time
import json
from pathlib import Path
from tqdm import tqdm

from nba_api.stats.endpoints import leaguegamelog, playergamelog

from ingestion.utils import RAW_DIR, SEASONS, SLEEP, request_with_retry, load_json, save_json


# ── All games ─────────────────────────────────────────────────────────────────

def fetch_all_games() -> list[dict]:
    out_path = RAW_DIR / "games.json"
    existing = load_json(out_path)
    if existing is not None:
        print(f"[skip] games.json already exists ({len(existing)} games)")
        return existing

    seen_game_ids: set[str] = set()
    games: list[dict] = []

    for season_type in ["Regular Season", "Playoffs"]:
        for season in tqdm(SEASONS, desc=f"{season_type} games"):
            result = request_with_retry(
                lambda s=season, st=season_type: leaguegamelog.LeagueGameLog(
                    season=s,
                    season_type_all_star=st,
                    player_or_team_abbreviation="T",   # team-level rows
                ),
                label=f"games {season} {season_type}",
            )
            rows = result.get_normalized_dict()["LeagueGameLog"]
            time.sleep(SLEEP)

            # Each game appears twice (once per team); deduplicate by GAME_ID
            # and reconstruct home/away from MATCHUP ("TEAM vs. OPP" = home)
            for row in rows:
                gid = row["GAME_ID"]
                if gid in seen_game_ids:
                    continue
                seen_game_ids.add(gid)

                is_home = "vs." in row["MATCHUP"]
                game = {
                    "game_id":       gid,
                    "date":          row["GAME_DATE"],
                    "season":        season,
                    "season_type":   season_type,
                    "home_team_id":  row["TEAM_ID"]        if is_home else None,
                    "away_team_id":  row["TEAM_ID"]        if not is_home else None,
                    "home_team_abbr": row["TEAM_ABBREVIATION"] if is_home else None,
                    "away_team_abbr": row["TEAM_ABBREVIATION"] if not is_home else None,
                    "home_score":    row["PTS"]            if is_home else None,
                    "away_score":    row["PTS"]            if not is_home else None,
                    "winner":        "home" if (is_home and row["WL"] == "W") else "away",
                    "matchup":       row["MATCHUP"],
                }
                games.append(game)

    # Second pass: fill in the missing side for each game
    # We stored partial data when we first encountered each game_id;
    # now fix games where we only captured one team's perspective.
    game_map: dict[str, dict] = {g["game_id"]: g for g in games}

    # Re-scan the raw rows for the "other" team of each game
    for season_type in ["Regular Season", "Playoffs"]:
        for season in SEASONS:
            out_path_raw = RAW_DIR / f"_raw_gamelog_{season_type.replace(' ','_')}_{season}.json"
            if out_path_raw.exists():
                rows = json.loads(out_path_raw.read_text(encoding="utf-8"))
            else:
                continue
            for row in rows:
                gid = row["GAME_ID"]
                if gid not in game_map:
                    continue
                g = game_map[gid]
                is_home = "vs." in row["MATCHUP"]
                if is_home and g["home_team_id"] is None:
                    g["home_team_id"]   = row["TEAM_ID"]
                    g["home_team_abbr"] = row["TEAM_ABBREVIATION"]
                    g["home_score"]     = row["PTS"]
                if not is_home and g["away_team_id"] is None:
                    g["away_team_id"]   = row["TEAM_ID"]
                    g["away_team_abbr"] = row["TEAM_ABBREVIATION"]
                    g["away_score"]     = row["PTS"]

    save_json(out_path, list(game_map.values()))
    print(f"Saved {len(game_map)} unique games -> {out_path}")
    return list(game_map.values())


# ── Better approach: two-pass with raw cache ──────────────────────────────────

def fetch_all_games_v2() -> list[dict]:
    """
    Two-pass strategy:
      Pass 1 — fetch and cache raw team game log rows per season/type
      Pass 2 — deduplicate + merge home+away into one game record
    """
    out_path = RAW_DIR / "games.json"
    existing = load_json(out_path)
    if existing is not None:
        print(f"[skip] games.json already exists ({len(existing)} games)")
        return existing

    raw_cache_dir = RAW_DIR / "_game_cache"
    raw_cache_dir.mkdir(exist_ok=True)

    # ── Pass 1: fetch raw rows ────────────────────────────────────────────────
    all_rows: list[dict] = []
    for season_type in ["Regular Season", "Playoffs"]:
        st_key = season_type.replace(" ", "_")
        for season in tqdm(SEASONS, desc=f"{season_type}"):
            cache_file = raw_cache_dir / f"{st_key}_{season}.json"
            if cache_file.exists():
                rows = json.loads(cache_file.read_text(encoding="utf-8"))
            else:
                result = request_with_retry(
                    lambda s=season, st=season_type: leaguegamelog.LeagueGameLog(
                        season=s,
                        season_type_all_star=st,
                        player_or_team_abbreviation="T",
                    ),
                    label=f"{season} {season_type}",
                )
                rows = result.get_normalized_dict()["LeagueGameLog"]
                for row in rows:
                    row["SEASON"]      = season
                    row["SEASON_TYPE"] = season_type
                cache_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")
                time.sleep(SLEEP)
            all_rows.extend(rows)

    # ── Pass 2: merge into one record per game ────────────────────────────────
    game_map: dict[str, dict] = {}
    for row in all_rows:
        gid = row["GAME_ID"]
        is_home = "vs." in row["MATCHUP"]

        if gid not in game_map:
            game_map[gid] = {
                "game_id":     gid,
                "date":        row["GAME_DATE"],
                "season":      row["SEASON"],
                "season_type": row["SEASON_TYPE"],
                "home_team_id": None, "home_team_abbr": None, "home_score": None,
                "away_team_id": None, "away_team_abbr": None, "away_score": None,
                "winner_team_id": None,
            }

        g = game_map[gid]
        if is_home:
            g["home_team_id"]   = row["TEAM_ID"]
            g["home_team_abbr"] = row["TEAM_ABBREVIATION"]
            g["home_score"]     = row["PTS"]
            if row["WL"] == "W":
                g["winner_team_id"] = row["TEAM_ID"]
        else:
            g["away_team_id"]   = row["TEAM_ID"]
            g["away_team_abbr"] = row["TEAM_ABBREVIATION"]
            g["away_score"]     = row["PTS"]
            if row["WL"] == "W":
                g["winner_team_id"] = row["TEAM_ID"]

    games = list(game_map.values())
    save_json(out_path, games)
    print(f"Saved {len(games)} unique games -> {out_path}")
    return games


# ── Top-50 player game logs ───────────────────────────────────────────────────

def get_top50_player_ids() -> list[int]:
    """Rank players by total games played across all seasons, return top 100."""
    stats = load_json(RAW_DIR / "players_stats.json")
    if not stats:
        raise FileNotFoundError("Run fetch_players.py first — players_stats.json missing")

    totals: dict[int, dict] = {}
    for row in stats:
        pid  = row["PLAYER_ID"]
        name = row["PLAYER_NAME"]
        gp   = row.get("GP", 0) or 0
        if pid not in totals:
            totals[pid] = {"name": name, "gp": 0}
        totals[pid]["gp"] += gp

    ranked = sorted(totals.items(), key=lambda x: x[1]["gp"], reverse=True)
    top50  = [pid for pid, _ in ranked[:100]]
    print("Top 100 players by career games (2013-2023):")
    for pid, info in ranked[:100]:
        try:
            print(f"  {info['name']:30s}  {info['gp']} GP")
        except UnicodeEncodeError:
            print(f"  {info['name'].encode('ascii', 'replace').decode():30s}  {info['gp']} GP")
    return top50


def fetch_player_gamelogs(player_ids: list[int]) -> dict:
    out_path = RAW_DIR / "player_gamelogs.json"
    existing: dict = load_json(out_path) or {}

    for pid in tqdm(player_ids, desc="Player game logs"):
        pid_key = str(pid)
        if pid_key in existing and len(existing[pid_key]) > 0:
            continue   # already cached

        player_logs: list[dict] = []
        for season in SEASONS:
            try:
                result = request_with_retry(
                    lambda p=pid, s=season: playergamelog.PlayerGameLog(
                        player_id=p, season=s
                    ),
                    label=f"gamelog {pid} {season}",
                )
                rows = result.get_normalized_dict()["PlayerGameLog"]
                for row in rows:
                    row["SEASON"] = season
                player_logs.extend(rows)
                time.sleep(SLEEP)
            except Exception as e:
                print(f"  [skip] player {pid} season {season}: {e}")

        existing[pid_key] = player_logs
        # Checkpoint after each player
        save_json(out_path, existing)

    print(f"Saved game logs for {len(existing)} players -> {out_path}")
    return existing


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STEP 1: All game results (20 requests)")
    print("=" * 60)
    fetch_all_games_v2()

    print("\n" + "=" * 60)
    print("STEP 2: Per-game logs for top 50 players (~500 requests, ~5 min)")
    print("=" * 60)
    top50 = get_top50_player_ids()
    fetch_player_gamelogs(top50)

    print("\nDone. Run fetch_awards.py next.")


if __name__ == "__main__":
    main()
