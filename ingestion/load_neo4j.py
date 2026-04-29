"""
Phase 3 — Load all raw JSON data into Neo4j.

Run after all fetch_*.py scripts complete.
All operations use MERGE — safe to re-run at any time.

Order:
  1. Apply schema (constraints + indexes)
  2. Season nodes
  3. Team nodes
  4. Player nodes
  5. PlayerSeasonStats nodes  (+ PLAYED_FOR + HAS_SEASON_STATS edges)
  6. Game nodes               (+ IN_SEASON + PLAYED_GAME edges)
  7. Award nodes              (+ WON_AWARD edges)
  8. WON_CHAMPIONSHIP edges   (derived from awards)
"""
import pathlib
from tqdm import tqdm
from graph.neo4j_client import get_driver, run_query
from ingestion.utils import RAW_DIR, SEASONS, load_json

# ── Conference / Division lookup (not in nba_api static data) ────────────────
TEAM_META = {
    "ATL": ("East", "Southeast"), "BOS": ("East", "Atlantic"),
    "BKN": ("East", "Atlantic"),  "CHA": ("East", "Southeast"),
    "CHI": ("East", "Central"),   "CLE": ("East", "Central"),
    "DAL": ("West", "Southwest"), "DEN": ("West", "Northwest"),
    "DET": ("East", "Central"),   "GSW": ("West", "Pacific"),
    "HOU": ("West", "Southwest"), "IND": ("East", "Central"),
    "LAC": ("West", "Pacific"),   "LAL": ("West", "Pacific"),
    "MEM": ("West", "Southwest"), "MIA": ("East", "Southeast"),
    "MIL": ("East", "Central"),   "MIN": ("West", "Northwest"),
    "NOP": ("West", "Southwest"), "NYK": ("East", "Atlantic"),
    "OKC": ("West", "Northwest"), "ORL": ("East", "Southeast"),
    "PHI": ("East", "Atlantic"),  "PHX": ("West", "Pacific"),
    "POR": ("West", "Northwest"), "SAC": ("West", "Pacific"),
    "SAS": ("West", "Southwest"), "TOR": ("East", "Atlantic"),
    "UTA": ("West", "Northwest"), "WAS": ("East", "Southeast"),
}

BATCH = 500   # UNWIND batch size


def batch(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def apply_schema():
    print("Applying schema (constraints + indexes)...")
    schema_path = pathlib.Path("graph/schema.cypher")
    stmts = [
        s.strip()
        for s in schema_path.read_text(encoding="utf-8").split(";")
        if s.strip() and not s.strip().startswith("//")
    ]
    driver = get_driver()
    with driver.session() as session:
        for stmt in stmts:
            try:
                session.run(stmt)
            except Exception as e:
                print(f"  [warn] {e}")
    print(f"  {len(stmts)} statements applied")


# ── 1. Season nodes ───────────────────────────────────────────────────────────

def load_seasons():
    print("Loading Season nodes...")
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            UNWIND $seasons AS s
            MERGE (n:Season {year: s})
            """,
            seasons=SEASONS,
        )
    print(f"  {len(SEASONS)} seasons merged")


# ── 2. Team nodes ─────────────────────────────────────────────────────────────

def load_teams():
    print("Loading Team nodes...")
    teams_raw = load_json(RAW_DIR / "teams.json") or []
    teams_stats = load_json(RAW_DIR / "teams_stats.json") or []

    params = []
    for t in teams_raw:
        abbr = t.get("abbreviation", "")
        conf, div = TEAM_META.get(abbr, ("", ""))
        params.append({
            "team_id":      t["id"],
            "name":         t["full_name"],
            "city":         t["city"],
            "abbreviation": abbr,
            "nickname":     t.get("nickname", ""),
            "conference":   conf,
            "division":     div,
        })

    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            UNWIND $teams AS t
            MERGE (n:Team {team_id: t.team_id})
            SET n.name         = t.name,
                n.city         = t.city,
                n.abbreviation = t.abbreviation,
                n.nickname     = t.nickname,
                n.conference   = t.conference,
                n.division     = t.division
            """,
            teams=params,
        )
    print(f"  {len(params)} teams merged")


# ── 3. Player nodes ───────────────────────────────────────────────────────────

def load_players():
    print("Loading Player nodes...")
    bios  = load_json(RAW_DIR / "players_bio.json") or {}
    stats = load_json(RAW_DIR / "players_stats.json") or []

    # Career averages: mean across all seasons
    career: dict[int, dict] = {}
    counts: dict[int, int]  = {}
    for row in stats:
        pid = row["PLAYER_ID"]
        if pid not in career:
            career[pid]  = {"pts": 0.0, "ast": 0.0, "reb": 0.0}
            counts[pid]  = 0
        career[pid]["pts"] += row.get("PTS", 0) or 0
        career[pid]["ast"] += row.get("AST", 0) or 0
        career[pid]["reb"] += row.get("REB", 0) or 0
        counts[pid] += 1

    params = []
    seen: set[int] = set()
    for row in stats:
        pid = row["PLAYER_ID"]
        if pid in seen:
            continue
        seen.add(pid)

        bio = bios.get(str(pid), {})
        n   = counts.get(pid, 1) or 1
        params.append({
            "player_id":       pid,
            "name":            row.get("PLAYER_NAME", bio.get("DISPLAY_FIRST_LAST", "")),
            "position":        bio.get("POSITION", ""),
            "height":          bio.get("HEIGHT", ""),
            "weight":          bio.get("WEIGHT", ""),
            "country":         bio.get("COUNTRY", ""),
            "draft_year":      bio.get("DRAFT_YEAR", ""),
            "draft_round":     bio.get("DRAFT_ROUND", ""),
            "draft_pick":      bio.get("DRAFT_NUMBER", ""),
            "from_year":       bio.get("FROM_YEAR", ""),
            "to_year":         bio.get("TO_YEAR", ""),
            "career_pts_avg":  round(career[pid]["pts"] / n, 1),
            "career_ast_avg":  round(career[pid]["ast"] / n, 1),
            "career_reb_avg":  round(career[pid]["reb"] / n, 1),
        })

    driver = get_driver()
    for b in tqdm(list(batch(params, BATCH)), desc="  Players"):
        with driver.session() as session:
            session.run(
                """
                UNWIND $players AS p
                MERGE (n:Player {player_id: p.player_id})
                SET n.name           = p.name,
                    n.position       = p.position,
                    n.height         = p.height,
                    n.weight         = p.weight,
                    n.country        = p.country,
                    n.draft_year     = p.draft_year,
                    n.draft_round    = p.draft_round,
                    n.draft_pick     = p.draft_pick,
                    n.from_year      = p.from_year,
                    n.to_year        = p.to_year,
                    n.career_pts_avg = p.career_pts_avg,
                    n.career_ast_avg = p.career_ast_avg,
                    n.career_reb_avg = p.career_reb_avg
                """,
                players=b,
            )
    print(f"  {len(params)} players merged")


# ── 4. PlayerSeasonStats + PLAYED_FOR + HAS_SEASON_STATS ─────────────────────

def load_player_season_stats():
    print("Loading PlayerSeasonStats nodes + edges...")
    stats = load_json(RAW_DIR / "players_stats.json") or []

    params = [
        {
            "player_id":    row["PLAYER_ID"],
            "season":       row["SEASON"],
            "team_id":      row.get("TEAM_ID"),
            "games_played": row.get("GP", 0),
            "pts":          row.get("PTS", 0.0),
            "ast":          row.get("AST", 0.0),
            "reb":          row.get("REB", 0.0),
            "stl":          row.get("STL", 0.0),
            "blk":          row.get("BLK", 0.0),
            "fg_pct":       row.get("FG_PCT", 0.0),
            "fg3_pct":      row.get("FG3_PCT", 0.0),
            "ft_pct":       row.get("FT_PCT", 0.0),
            "min":          row.get("MIN", 0.0),
            "tov":          row.get("TOV", 0.0),
            "plus_minus":   row.get("PLUS_MINUS", 0.0),
        }
        for row in stats
    ]

    driver = get_driver()
    for b in tqdm(list(batch(params, BATCH)), desc="  PlayerSeasonStats"):
        with driver.session() as session:
            session.run(
                """
                UNWIND $rows AS r
                MATCH (p:Player {player_id: r.player_id})
                MATCH (t:Team   {team_id:   r.team_id})
                MATCH (s:Season {year:      r.season})

                MERGE (pss:PlayerSeasonStats {
                    player_id: r.player_id,
                    season:    r.season,
                    team_id:   r.team_id
                })
                SET pss.games_played = r.games_played,
                    pss.pts          = r.pts,
                    pss.ast          = r.ast,
                    pss.reb          = r.reb,
                    pss.stl          = r.stl,
                    pss.blk          = r.blk,
                    pss.fg_pct       = r.fg_pct,
                    pss.fg3_pct      = r.fg3_pct,
                    pss.ft_pct       = r.ft_pct,
                    pss.min          = r.min,
                    pss.tov          = r.tov,
                    pss.plus_minus   = r.plus_minus

                MERGE (p)-[:HAS_SEASON_STATS]->(pss)
                MERGE (p)-[:PLAYED_FOR {season: r.season, games_played: r.games_played}]->(t)
                """,
                rows=b,
            )
    print(f"  {len(params)} stat rows merged")


# ── 5. Game nodes + IN_SEASON + PLAYED_GAME ───────────────────────────────────

def load_games():
    print("Loading Game nodes + edges...")
    games = load_json(RAW_DIR / "games.json") or []

    params = [
        {
            "game_id":       g["game_id"],
            "date":          g["date"],
            "season":        g["season"],
            "season_type":   g.get("season_type", "Regular Season"),
            "home_team_id":  g.get("home_team_id"),
            "away_team_id":  g.get("away_team_id"),
            "home_score":    g.get("home_score"),
            "away_score":    g.get("away_score"),
            "winner_team_id": g.get("winner_team_id"),
        }
        for g in games
        if g.get("home_team_id") and g.get("away_team_id")
    ]

    driver = get_driver()
    for b in tqdm(list(batch(params, BATCH)), desc="  Games"):
        with driver.session() as session:
            session.run(
                """
                UNWIND $games AS g
                MERGE (game:Game {game_id: g.game_id})
                SET game.date          = g.date,
                    game.season        = g.season,
                    game.season_type   = g.season_type,
                    game.home_team_id  = g.home_team_id,
                    game.away_team_id  = g.away_team_id,
                    game.home_score    = g.home_score,
                    game.away_score    = g.away_score,
                    game.winner_team_id = g.winner_team_id

                WITH game, g
                MATCH (s:Season {year: g.season})
                MERGE (game)-[:IN_SEASON]->(s)

                WITH game, g
                MATCH (home:Team {team_id: g.home_team_id})
                MERGE (home)-[:PLAYED_GAME {home_or_away: 'home', score: g.home_score}]->(game)

                WITH game, g
                MATCH (away:Team {team_id: g.away_team_id})
                MERGE (away)-[:PLAYED_GAME {home_or_away: 'away', score: g.away_score}]->(game)
                """,
                games=b,
            )
    print(f"  {len(params)} games merged")


# ── 6. Award nodes + WON_AWARD + WON_CHAMPIONSHIP ────────────────────────────

def load_awards():
    print("Loading Award nodes + WON_AWARD edges...")
    awards = load_json(RAW_DIR / "awards.json") or []
    stats  = load_json(RAW_DIR / "players_stats.json") or []

    # Name → player_id lookup
    name_to_id: dict[str, int] = {}
    for row in stats:
        name_to_id[row["PLAYER_NAME"].lower()] = row["PLAYER_ID"]

    # Team name → team_id lookup
    teams = load_json(RAW_DIR / "teams.json") or []
    team_name_to_id: dict[str, int] = {}
    for t in teams:
        team_name_to_id[t["full_name"].lower()] = t["id"]

    award_params = []
    for i, a in enumerate(awards):
        pid = None
        if a.get("player_name"):
            pid = name_to_id.get(a["player_name"].lower())
        award_params.append({
            "award_id":    f"{a['award_type'].replace(' ','_')}_{a['season']}_{i}",
            "award_type":  a["award_type"],
            "season":      a["season"],
            "player_name": a.get("player_name"),
            "player_id":   pid,
            "team":        a.get("team", ""),
            "conference":  a.get("conference", ""),
            "all_nba_team_number": a.get("all_nba_team_number"),
        })

    driver = get_driver()
    # Create Award nodes + WON_AWARD
    for b in tqdm(list(batch(award_params, BATCH)), desc="  Awards"):
        with driver.session() as session:
            session.run(
                """
                UNWIND $awards AS a
                MERGE (aw:Award {award_id: a.award_id})
                SET aw.award_type  = a.award_type,
                    aw.season      = a.season,
                    aw.player_name = a.player_name,
                    aw.player_id   = a.player_id,
                    aw.team        = a.team,
                    aw.conference  = a.conference,
                    aw.all_nba_team_number = a.all_nba_team_number

                WITH aw, a
                WHERE a.player_id IS NOT NULL
                MATCH (p:Player {player_id: a.player_id})
                MERGE (p)-[:WON_AWARD]->(aw)
                """,
                awards=b,
            )

    # WON_CHAMPIONSHIP edges
    print("  Adding WON_CHAMPIONSHIP edges...")
    champs = [a for a in awards if a["award_type"] == "NBA Champion"]
    driver = get_driver()
    with driver.session() as session:
        for a in champs:
            tid = team_name_to_id.get((a.get("team") or "").lower())
            if not tid:
                continue
            session.run(
                """
                MATCH (t:Team {team_id: $tid})
                MATCH (s:Season {year: $season})
                MERGE (t)-[:WON_CHAMPIONSHIP]->(s)
                """,
                tid=tid, season=a["season"],
            )
    print(f"  {len(award_params)} awards merged, {len(champs)} championships linked")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  Neo4j Loader")
    print("=" * 60 + "\n")

    apply_schema()
    load_seasons()
    load_teams()
    load_players()
    load_player_season_stats()
    load_games()
    load_awards()

    # Quick sanity check
    print("\nSanity check:")
    checks = [
        ("MATCH (n:Player)  RETURN count(n) AS c", "Players"),
        ("MATCH (n:Team)    RETURN count(n) AS c", "Teams"),
        ("MATCH (n:Game)    RETURN count(n) AS c", "Games"),
        ("MATCH (n:Season)  RETURN count(n) AS c", "Seasons"),
        ("MATCH (n:Award)   RETURN count(n) AS c", "Awards"),
        ("MATCH ()-[r:PLAYED_FOR]->() RETURN count(r) AS c", "PLAYED_FOR edges"),
        ("MATCH ()-[r:WON_CHAMPIONSHIP]->() RETURN count(r) AS c", "WON_CHAMPIONSHIP edges"),
    ]
    for cypher, label in checks:
        result = run_query(cypher)
        print(f"  {label:30s} {result[0]['c']}")

    print("\nDone. Neo4j is loaded.")


if __name__ == "__main__":
    main()
