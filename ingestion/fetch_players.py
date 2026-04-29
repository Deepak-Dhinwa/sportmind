"""
Phase 2 — Step 1: Fetch player data for 2013-14 to 2022-23.

Strategy:
  - LeagueDashPlayerStats × 10 seasons  → all player season averages (10 requests)
  - CommonPlayerInfo for top 300 players by games played only.
    The other ~1100 are fringe/10-day players — their stats row has enough info.

Outputs:
  data/raw/players_stats.json  — list of {PLAYER_ID, PLAYER_NAME, SEASON, PTS, ...}
  data/raw/players_bio.json    — {player_id: {name, position, height, draft_year, ...}}
"""
import time
import random
from tqdm import tqdm

from nba_api.stats.endpoints import leaguedashplayerstats, commonplayerinfo

from ingestion.utils import RAW_DIR, SEASONS, SLEEP, request_with_retry, load_json, save_json

# Only fetch detailed bios for the players that actually matter
TOP_N_BIOS = 300


# ── Season stats ──────────────────────────────────────────────────────────────

def fetch_season_stats() -> list[dict]:
    out_path = RAW_DIR / "players_stats.json"
    existing = load_json(out_path)
    if existing is not None:
        print(f"[skip] players_stats.json already exists ({len(existing)} rows)")
        return existing

    all_stats: list[dict] = []
    for season in tqdm(SEASONS, desc="Season stats"):
        result = request_with_retry(
            lambda s=season: leaguedashplayerstats.LeagueDashPlayerStats(
                season=s,
                season_type_all_star="Regular Season",
                per_mode_detailed="PerGame",
            ),
            label=f"stats {season}",
        )
        rows = result.get_normalized_dict()["LeagueDashPlayerStats"]
        for row in rows:
            row["SEASON"] = season
        all_stats.extend(rows)
        time.sleep(SLEEP)

    save_json(out_path, all_stats)
    print(f"Saved {len(all_stats)} player-season rows -> {out_path}")
    return all_stats


# ── Rank players, pick top N ──────────────────────────────────────────────────

def rank_players(stats: list[dict]) -> list[int]:
    """Return player IDs sorted by total GP descending."""
    totals: dict[int, int] = {}
    for row in stats:
        pid = row["PLAYER_ID"]
        totals[pid] = totals.get(pid, 0) + (row.get("GP") or 0)
    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in ranked]


# ── Player bios ───────────────────────────────────────────────────────────────

def fetch_player_bios(player_ids: list[int], stats: list[dict]) -> dict:
    out_path = RAW_DIR / "players_bio.json"
    bios: dict = load_json(out_path) or {}

    # Drop previously cached error entries for players still in our target list
    # so they get a clean retry this run
    target_set = set(str(pid) for pid in player_ids)
    for key in list(bios.keys()):
        if key in target_set and bios[key].get("error"):
            del bios[key]

    done_ids = {int(k) for k in bios if not bios[k].get("error")}
    remaining = [pid for pid in player_ids if pid not in done_ids]
    print(f"Fetching bios: {len(remaining)} remaining, {len(done_ids)} already cached")

    for i, pid in enumerate(tqdm(remaining, desc="Player bios")):
        try:
            info = request_with_retry(
                lambda p=pid: commonplayerinfo.CommonPlayerInfo(player_id=p),
                label=f"bio {pid}",
            )
            data = info.get_normalized_dict()
            player_info = data["CommonPlayerInfo"][0] if data["CommonPlayerInfo"] else {}
            headline    = data.get("PlayerHeadlineStats", [{}])[0]
            bios[str(pid)] = {**player_info, "headline": headline}
        except Exception as e:
            print(f"  [skip] {pid}: {e}")
            bios[str(pid)] = {"PERSON_ID": pid, "error": True}

        # Jitter: vary sleep to avoid triggering rate limiting
        time.sleep(SLEEP + random.uniform(0.1, 0.5))

        # Checkpoint every 50 players
        if (i + 1) % 50 == 0:
            save_json(out_path, bios)

    # Fill in minimal records for players outside top-300 using stats data
    stats_lookup: dict[int, dict] = {}
    for row in stats:
        pid = row["PLAYER_ID"]
        if pid not in stats_lookup:
            stats_lookup[pid] = row

    all_player_ids = set(row["PLAYER_ID"] for row in stats)
    filled = 0
    for pid in all_player_ids:
        if str(pid) not in bios:
            row = stats_lookup.get(pid, {})
            bios[str(pid)] = {
                "PERSON_ID":         pid,
                "DISPLAY_FIRST_LAST": row.get("PLAYER_NAME", ""),
                "POSITION":          "",   # not in stats endpoint
                "HEIGHT":            "",
                "WEIGHT":            "",
                "COUNTRY":           "",
                "DRAFT_YEAR":        "",
                "DRAFT_ROUND":       "",
                "DRAFT_NUMBER":      "",
                "FROM_YEAR":         "",
                "TO_YEAR":           "",
                "_minimal":          True,  # flag: filled from stats, not API
            }
            filled += 1

    save_json(out_path, bios)
    print(f"Saved {len(bios)} player bios ({filled} minimal) -> {out_path}")
    return bios


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STEP 1: Player season stats (10 requests)")
    print("=" * 60)
    stats = fetch_season_stats()

    all_ids_ranked = rank_players(stats)
    print(f"\nFound {len(all_ids_ranked)} unique players across 2013-2023")
    print(f"Will fetch full bios for top {TOP_N_BIOS} by games played\n")

    print("=" * 60)
    print(f"STEP 2: Player bio info (top {TOP_N_BIOS} only, ~5 min)")
    print("=" * 60)
    top_ids = all_ids_ranked[:TOP_N_BIOS]
    fetch_player_bios(top_ids, stats)

    print("\nDone. Run fetch_teams.py next.")


if __name__ == "__main__":
    main()
