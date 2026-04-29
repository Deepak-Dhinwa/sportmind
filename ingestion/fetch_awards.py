"""
Phase 2 — Step 4: Fetch NBA awards for 2013-14 to 2022-23.

Strategy (two-part):
  Part A — hardcoded major individual awards (MVP, DPOY, ROTY, Finals MVP,
            Champions) — zero API calls, perfectly reliable historical facts.
  Part B — PlayerAwards endpoint for top 100 players → All-NBA / All-Star /
            All-Defensive selections (supplements Part A).

Output:
  data/raw/awards.json  — [{season, award_type, player_name, team, note}]
"""
import time
from tqdm import tqdm

from nba_api.stats.endpoints import playerawards

from ingestion.utils import RAW_DIR, SEASONS, SLEEP, request_with_retry, load_json, save_json


# ── Part A: hardcoded individual awards 2013-14 → 2022-23 ────────────────────
# Source: basketball-reference.com / official NBA records

HARDCODED_AWARDS = [
    # MVP
    {"season": "2013-14", "award_type": "Most Valuable Player", "player_name": "Kevin Durant",           "team": "Oklahoma City Thunder"},
    {"season": "2014-15", "award_type": "Most Valuable Player", "player_name": "Stephen Curry",          "team": "Golden State Warriors"},
    {"season": "2015-16", "award_type": "Most Valuable Player", "player_name": "Stephen Curry",          "team": "Golden State Warriors"},
    {"season": "2016-17", "award_type": "Most Valuable Player", "player_name": "Russell Westbrook",      "team": "Oklahoma City Thunder"},
    {"season": "2017-18", "award_type": "Most Valuable Player", "player_name": "James Harden",           "team": "Houston Rockets"},
    {"season": "2018-19", "award_type": "Most Valuable Player", "player_name": "Giannis Antetokounmpo", "team": "Milwaukee Bucks"},
    {"season": "2019-20", "award_type": "Most Valuable Player", "player_name": "Giannis Antetokounmpo", "team": "Milwaukee Bucks"},
    {"season": "2020-21", "award_type": "Most Valuable Player", "player_name": "Nikola Jokic",           "team": "Denver Nuggets"},
    {"season": "2021-22", "award_type": "Most Valuable Player", "player_name": "Nikola Jokic",           "team": "Denver Nuggets"},
    {"season": "2022-23", "award_type": "Most Valuable Player", "player_name": "Joel Embiid",            "team": "Philadelphia 76ers"},
    # Defensive Player of the Year
    {"season": "2013-14", "award_type": "Defensive Player of the Year", "player_name": "Joakim Noah",            "team": "Chicago Bulls"},
    {"season": "2014-15", "award_type": "Defensive Player of the Year", "player_name": "Kawhi Leonard",          "team": "San Antonio Spurs"},
    {"season": "2015-16", "award_type": "Defensive Player of the Year", "player_name": "Kawhi Leonard",          "team": "San Antonio Spurs"},
    {"season": "2016-17", "award_type": "Defensive Player of the Year", "player_name": "Draymond Green",         "team": "Golden State Warriors"},
    {"season": "2017-18", "award_type": "Defensive Player of the Year", "player_name": "Rudy Gobert",            "team": "Utah Jazz"},
    {"season": "2018-19", "award_type": "Defensive Player of the Year", "player_name": "Rudy Gobert",            "team": "Utah Jazz"},
    {"season": "2019-20", "award_type": "Defensive Player of the Year", "player_name": "Giannis Antetokounmpo", "team": "Milwaukee Bucks"},
    {"season": "2020-21", "award_type": "Defensive Player of the Year", "player_name": "Rudy Gobert",            "team": "Utah Jazz"},
    {"season": "2021-22", "award_type": "Defensive Player of the Year", "player_name": "Marcus Smart",           "team": "Boston Celtics"},
    {"season": "2022-23", "award_type": "Defensive Player of the Year", "player_name": "Evan Mobley",            "team": "Cleveland Cavaliers"},
    # Rookie of the Year
    {"season": "2013-14", "award_type": "Rookie of the Year", "player_name": "Michael Carter-Williams", "team": "Philadelphia 76ers"},
    {"season": "2014-15", "award_type": "Rookie of the Year", "player_name": "Andrew Wiggins",          "team": "Minnesota Timberwolves"},
    {"season": "2015-16", "award_type": "Rookie of the Year", "player_name": "Karl-Anthony Towns",      "team": "Minnesota Timberwolves"},
    {"season": "2016-17", "award_type": "Rookie of the Year", "player_name": "Malcolm Brogdon",         "team": "Milwaukee Bucks"},
    {"season": "2017-18", "award_type": "Rookie of the Year", "player_name": "Ben Simmons",             "team": "Philadelphia 76ers"},
    {"season": "2018-19", "award_type": "Rookie of the Year", "player_name": "Luka Doncic",             "team": "Dallas Mavericks"},
    {"season": "2019-20", "award_type": "Rookie of the Year", "player_name": "Ja Morant",               "team": "Memphis Grizzlies"},
    {"season": "2020-21", "award_type": "Rookie of the Year", "player_name": "LaMelo Ball",             "team": "Charlotte Hornets"},
    {"season": "2021-22", "award_type": "Rookie of the Year", "player_name": "Scottie Barnes",          "team": "Toronto Raptors"},
    {"season": "2022-23", "award_type": "Rookie of the Year", "player_name": "Paolo Banchero",          "team": "Orlando Magic"},
    # Finals MVP
    {"season": "2013-14", "award_type": "Finals MVP", "player_name": "Kawhi Leonard",          "team": "San Antonio Spurs"},
    {"season": "2014-15", "award_type": "Finals MVP", "player_name": "Andre Iguodala",         "team": "Golden State Warriors"},
    {"season": "2015-16", "award_type": "Finals MVP", "player_name": "LeBron James",           "team": "Cleveland Cavaliers"},
    {"season": "2016-17", "award_type": "Finals MVP", "player_name": "Kevin Durant",           "team": "Golden State Warriors"},
    {"season": "2017-18", "award_type": "Finals MVP", "player_name": "Kevin Durant",           "team": "Golden State Warriors"},
    {"season": "2018-19", "award_type": "Finals MVP", "player_name": "Kawhi Leonard",          "team": "Toronto Raptors"},
    {"season": "2019-20", "award_type": "Finals MVP", "player_name": "LeBron James",           "team": "Los Angeles Lakers"},
    {"season": "2020-21", "award_type": "Finals MVP", "player_name": "Giannis Antetokounmpo", "team": "Milwaukee Bucks"},
    {"season": "2021-22", "award_type": "Finals MVP", "player_name": "Stephen Curry",         "team": "Golden State Warriors"},
    {"season": "2022-23", "award_type": "Finals MVP", "player_name": "Nikola Jokic",          "team": "Denver Nuggets"},
    # NBA Champion (team)
    {"season": "2013-14", "award_type": "NBA Champion", "player_name": None, "team": "San Antonio Spurs"},
    {"season": "2014-15", "award_type": "NBA Champion", "player_name": None, "team": "Golden State Warriors"},
    {"season": "2015-16", "award_type": "NBA Champion", "player_name": None, "team": "Cleveland Cavaliers"},
    {"season": "2016-17", "award_type": "NBA Champion", "player_name": None, "team": "Golden State Warriors"},
    {"season": "2017-18", "award_type": "NBA Champion", "player_name": None, "team": "Golden State Warriors"},
    {"season": "2018-19", "award_type": "NBA Champion", "player_name": None, "team": "Toronto Raptors"},
    {"season": "2019-20", "award_type": "NBA Champion", "player_name": None, "team": "Los Angeles Lakers"},
    {"season": "2020-21", "award_type": "NBA Champion", "player_name": None, "team": "Milwaukee Bucks"},
    {"season": "2021-22", "award_type": "NBA Champion", "player_name": None, "team": "Golden State Warriors"},
    {"season": "2022-23", "award_type": "NBA Champion", "player_name": None, "team": "Denver Nuggets"},
    # Most Improved Player
    {"season": "2013-14", "award_type": "Most Improved Player", "player_name": "Goran Dragic",       "team": "Phoenix Suns"},
    {"season": "2014-15", "award_type": "Most Improved Player", "player_name": "Jimmy Butler",       "team": "Chicago Bulls"},
    {"season": "2015-16", "award_type": "Most Improved Player", "player_name": "C.J. McCollum",     "team": "Portland Trail Blazers"},
    {"season": "2016-17", "award_type": "Most Improved Player", "player_name": "Giannis Antetokounmpo", "team": "Milwaukee Bucks"},
    {"season": "2017-18", "award_type": "Most Improved Player", "player_name": "Victor Oladipo",    "team": "Indiana Pacers"},
    {"season": "2018-19", "award_type": "Most Improved Player", "player_name": "Pascal Siakam",     "team": "Toronto Raptors"},
    {"season": "2019-20", "award_type": "Most Improved Player", "player_name": "Brandon Ingram",    "team": "New Orleans Pelicans"},
    {"season": "2020-21", "award_type": "Most Improved Player", "player_name": "Julius Randle",     "team": "New York Knicks"},
    {"season": "2021-22", "award_type": "Most Improved Player", "player_name": "Dejounte Murray",   "team": "San Antonio Spurs"},
    {"season": "2022-23", "award_type": "Most Improved Player", "player_name": "Lauri Markkanen",   "team": "Utah Jazz"},
]


# ── Part B: PlayerAwards for top 100 players (All-NBA / All-Star / All-Def) ──

SEASON_SET = set(SEASONS)

AWARD_TYPES_FROM_API = {
    "All-NBA",
    "All-Defensive Team",
    "All-Star",
}


def get_top100_player_ids() -> list[int]:
    stats = load_json(RAW_DIR / "players_stats.json")
    if not stats:
        raise FileNotFoundError("players_stats.json missing — run fetch_players.py first")

    totals: dict[int, int] = {}
    for row in stats:
        pid = row["PLAYER_ID"]
        totals[pid] = totals.get(pid, 0) + (row.get("GP") or 0)

    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in ranked[:100]]


def fetch_player_awards_api(player_ids: list[int]) -> list[dict]:
    results: list[dict] = []
    for pid in tqdm(player_ids, desc="PlayerAwards API"):
        try:
            data = request_with_retry(
                lambda p=pid: playerawards.PlayerAwards(player_id=p),
                label=f"awards {pid}",
            )
            rows = data.get_normalized_dict().get("PlayerAwards", [])
            for row in rows:
                season = row.get("SEASON", "")
                # API seasons are like "2013-14" — keep only our window
                if season not in SEASON_SET:
                    continue
                desc = row.get("DESCRIPTION", "") or ""
                if not any(t in desc for t in AWARD_TYPES_FROM_API):
                    continue
                results.append({
                    "season":      season,
                    "award_type":  desc,
                    "player_name": f"{row.get('FIRST_NAME', '')} {row.get('LAST_NAME', '')}".strip(),
                    "team":        row.get("TEAM", ""),
                    "conference":  row.get("CONFERENCE", ""),
                    "all_nba_team_number": row.get("ALL_NBA_TEAM_NUMBER"),
                })
            time.sleep(SLEEP)
        except Exception as e:
            print(f"  [skip] player {pid}: {e}")

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    out_path = RAW_DIR / "awards.json"
    if out_path.exists():
        data = load_json(out_path)
        print(f"[skip] awards.json already exists ({len(data)} records)")
        return data

    print("Part A: hardcoded major awards (no API calls)")
    all_awards = list(HARDCODED_AWARDS)
    print(f"  {len(all_awards)} records loaded")

    print("\nPart B: All-NBA / All-Star / All-Defensive via PlayerAwards API (~100 requests)")
    try:
        top100 = get_top100_player_ids()
        api_awards = fetch_player_awards_api(top100)
        all_awards.extend(api_awards)
        print(f"  {len(api_awards)} additional records from API")
    except FileNotFoundError as e:
        print(f"  [warn] Skipping Part B: {e}")

    save_json(out_path, all_awards)
    print(f"\nSaved {len(all_awards)} total award records -> {out_path}")

    from collections import Counter
    counts = Counter(a["award_type"] for a in all_awards)
    print("\nBreakdown:")
    for award, count in sorted(counts.items()):
        print(f"  {award:40s}  {count}")

    return all_awards


if __name__ == "__main__":
    main()
