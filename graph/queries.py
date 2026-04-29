"""
Pre-built Cypher query functions used by the RAG graph tool.
Each function returns a list of dicts (Neo4j records).
"""
from graph.neo4j_client import run_query


# ── Player queries ────────────────────────────────────────────────────────────

def get_player_season_stats(player_name: str, season: str = None) -> list[dict]:
    """Stats for a player, optionally filtered to one season."""
    if season:
        return run_query(
            """
            MATCH (p:Player)-[:HAS_SEASON_STATS]->(pss:PlayerSeasonStats)
            WHERE toLower(p.name) CONTAINS toLower($name)
              AND pss.season = $season
            MATCH (t:Team {team_id: pss.team_id})
            RETURN p.name AS player, t.name AS team, pss.season AS season,
                   pss.games_played AS gp,
                   pss.pts AS pts, pss.ast AS ast, pss.reb AS reb,
                   pss.stl AS stl, pss.blk AS blk,
                   pss.fg_pct AS fg_pct, pss.fg3_pct AS fg3_pct
            ORDER BY pss.season
            """,
            {"name": player_name, "season": season},
        )
    return run_query(
        """
        MATCH (p:Player)-[:HAS_SEASON_STATS]->(pss:PlayerSeasonStats)
        WHERE toLower(p.name) CONTAINS toLower($name)
        MATCH (t:Team {team_id: pss.team_id})
        RETURN p.name AS player, t.name AS team, pss.season AS season,
               pss.games_played AS gp,
               pss.pts AS pts, pss.ast AS ast, pss.reb AS reb,
               pss.stl AS stl, pss.blk AS blk,
               pss.fg_pct AS fg_pct, pss.fg3_pct AS fg3_pct
        ORDER BY pss.season
        """,
        {"name": player_name},
    )


def get_player_teams(player_name: str) -> list[dict]:
    """All teams a player played for and in which seasons."""
    return run_query(
        """
        MATCH (p:Player)-[r:PLAYED_FOR]->(t:Team)
        WHERE toLower(p.name) CONTAINS toLower($name)
        RETURN p.name AS player, t.name AS team, r.season AS season
        ORDER BY r.season
        """,
        {"name": player_name},
    )


def get_player_awards(player_name: str) -> list[dict]:
    return run_query(
        """
        MATCH (p:Player)-[:WON_AWARD]->(a:Award)
        WHERE toLower(p.name) CONTAINS toLower($name)
        RETURN p.name AS player, a.award_type AS award, a.season AS season, a.team AS team
        ORDER BY a.season
        """,
        {"name": player_name},
    )


def get_career_overview(player_name: str) -> list[dict]:
    return run_query(
        """
        MATCH (p:Player)
        WHERE toLower(p.name) CONTAINS toLower($name)
        RETURN p.name AS player, p.position AS position,
               p.height AS height, p.weight AS weight,
               p.country AS country, p.draft_year AS draft_year,
               p.draft_round AS draft_round, p.draft_pick AS draft_pick,
               p.from_year AS from_year, p.to_year AS to_year,
               p.career_pts_avg AS career_pts,
               p.career_ast_avg AS career_ast,
               p.career_reb_avg AS career_reb
        """,
        {"name": player_name},
    )


# ── Team queries ──────────────────────────────────────────────────────────────

def get_team_season_record(team_name: str, season: str = None) -> list[dict]:
    """
    Returns W/L record for a team per season, derived from Game results.
    No APOC needed — pure Cypher aggregation.
    """
    if season:
        return run_query(
            """
            MATCH (t:Team)-[:PLAYED_GAME]->(g:Game)
            WHERE (toLower(t.name) CONTAINS toLower($name)
               OR toLower(t.abbreviation) = toLower($name))
              AND g.season = $season
            WITH t, g,
                 CASE WHEN g.winner_team_id = t.team_id THEN 1 ELSE 0 END AS win
            RETURN t.name AS team, g.season AS season,
                   sum(win) AS W,
                   count(g) - sum(win) AS L,
                   round(toFloat(sum(win)) / count(g), 3) AS W_PCT
            """,
            {"name": team_name, "season": season},
        )
    return run_query(
        """
        MATCH (t:Team)-[:PLAYED_GAME]->(g:Game)
        WHERE toLower(t.name) CONTAINS toLower($name)
           OR toLower(t.abbreviation) = toLower($name)
        WITH t, g,
             CASE WHEN g.winner_team_id = t.team_id THEN 1 ELSE 0 END AS win
        RETURN t.name AS team, g.season AS season,
               sum(win) AS W,
               count(g) - sum(win) AS L,
               round(toFloat(sum(win)) / count(g), 3) AS W_PCT,
               t.conference AS conference, t.division AS division
        ORDER BY g.season
        """,
        {"name": team_name},
    )


def get_team_championships(team_name: str) -> list[dict]:
    return run_query(
        """
        MATCH (t:Team)-[:WON_CHAMPIONSHIP]->(s:Season)
        WHERE toLower(t.name) CONTAINS toLower($name)
           OR toLower(t.abbreviation) = toLower($name)
        RETURN t.name AS team, s.year AS season
        ORDER BY s.year
        """,
        {"name": team_name},
    )


def get_team_roster(team_name: str, season: str) -> list[dict]:
    return run_query(
        """
        MATCH (p:Player)-[r:PLAYED_FOR]->(t:Team)
        WHERE (toLower(t.name) CONTAINS toLower($name)
            OR toLower(t.abbreviation) = toLower($name))
          AND r.season = $season
        MATCH (p)-[:HAS_SEASON_STATS]->(pss:PlayerSeasonStats {season: $season, team_id: t.team_id})
        RETURN p.name AS player, p.position AS position,
               pss.pts AS pts, pss.ast AS ast, pss.reb AS reb,
               pss.games_played AS gp
        ORDER BY pss.pts DESC
        """,
        {"name": team_name, "season": season},
    )


# ── Season / Championship queries ─────────────────────────────────────────────

def get_season_champion(season: str) -> list[dict]:
    return run_query(
        """
        MATCH (t:Team)-[:WON_CHAMPIONSHIP]->(s:Season {year: $season})
        OPTIONAL MATCH (p:Player)-[:WON_AWARD]->(a:Award)
        WHERE a.season = $season AND a.award_type = 'Finals MVP'
        RETURN t.name AS champion, p.name AS finals_mvp
        """,
        {"season": season},
    )


def get_all_champions() -> list[dict]:
    return run_query(
        """
        MATCH (t:Team)-[:WON_CHAMPIONSHIP]->(s:Season)
        OPTIONAL MATCH (p:Player)-[:WON_AWARD]->(a:Award)
        WHERE a.season = s.year AND a.award_type = 'Finals MVP'
        RETURN s.year AS season, t.name AS champion, p.name AS finals_mvp
        ORDER BY s.year
        """
    )


def get_award_winners(award_type: str, season: str = None) -> list[dict]:
    if season:
        return run_query(
            """
            MATCH (a:Award)
            WHERE toLower(a.award_type) CONTAINS toLower($award_type)
              AND a.season = $season
            OPTIONAL MATCH (p:Player)-[:WON_AWARD]->(a)
            RETURN a.season AS season, a.award_type AS award,
                   coalesce(p.name, a.player_name) AS player, a.team AS team
            ORDER BY a.season
            """,
            {"award_type": award_type, "season": season},
        )
    return run_query(
        """
        MATCH (a:Award)
        WHERE toLower(a.award_type) CONTAINS toLower($award_type)
        OPTIONAL MATCH (p:Player)-[:WON_AWARD]->(a)
        RETURN a.season AS season, a.award_type AS award,
               coalesce(p.name, a.player_name) AS player, a.team AS team
        ORDER BY a.season
        """,
        {"award_type": award_type},
    )


# ── Top performers ────────────────────────────────────────────────────────────

def get_top_scorers(season: str, limit: int = 10) -> list[dict]:
    return run_query(
        """
        MATCH (p:Player)-[:HAS_SEASON_STATS]->(pss:PlayerSeasonStats {season: $season})
        MATCH (t:Team {team_id: pss.team_id})
        WHERE pss.games_played >= 30
        RETURN p.name AS player, t.name AS team,
               pss.pts AS pts, pss.ast AS ast, pss.reb AS reb,
               pss.stl AS stl, pss.blk AS blk,
               pss.fg_pct AS fg_pct, pss.fg3_pct AS fg3_pct,
               pss.games_played AS gp
        ORDER BY pss.pts DESC
        LIMIT $limit
        """,
        {"season": season, "limit": limit},
    )


def get_players_on_multiple_teams(team1: str, team2: str) -> list[dict]:
    """Players who appeared for both teams across any season."""
    return run_query(
        """
        MATCH (p:Player)-[:PLAYED_FOR]->(t1:Team)
        WHERE toLower(t1.name) CONTAINS toLower($team1)
           OR toLower(t1.abbreviation) = toLower($team1)
        WITH p, collect(t1.name) AS t1s
        MATCH (p)-[:PLAYED_FOR]->(t2:Team)
        WHERE toLower(t2.name) CONTAINS toLower($team2)
           OR toLower(t2.abbreviation) = toLower($team2)
        RETURN p.name AS player, t1s AS team1_seasons
        """,
        {"team1": team1, "team2": team2},
    )


def get_head_to_head(team1: str, team2: str, season: str = None) -> list[dict]:
    base = """
        MATCH (t1:Team)-[:PLAYED_GAME]->(g:Game)<-[:PLAYED_GAME]-(t2:Team)
        WHERE (toLower(t1.name) CONTAINS toLower($team1) OR toLower(t1.abbreviation) = toLower($team1))
          AND (toLower(t2.name) CONTAINS toLower($team2) OR toLower(t2.abbreviation) = toLower($team2))
    """
    if season:
        base += " AND g.season = $season"
    base += """
        RETURN g.date AS date, g.season AS season,
               t1.name AS team1, t2.name AS team2,
               g.home_score AS home_score, g.away_score AS away_score,
               CASE WHEN g.winner_team_id = t1.team_id THEN t1.name ELSE t2.name END AS winner
        ORDER BY g.date
    """
    return run_query(base, {"team1": team1, "team2": team2, "season": season or ""})


# ── Convenience dispatcher (called by graph_tool) ─────────────────────────────

QUERY_REGISTRY = {
    "player_stats":         get_player_season_stats,
    "player_teams":         get_player_teams,
    "player_awards":        get_player_awards,
    "player_overview":      get_career_overview,
    "team_record":          get_team_season_record,
    "team_championships":   get_team_championships,
    "team_roster":          get_team_roster,
    "season_champion":      get_season_champion,
    "all_champions":        get_all_champions,
    "award_winners":        get_award_winners,
    "top_scorers":          get_top_scorers,
    "players_on_both_teams": get_players_on_multiple_teams,
    "head_to_head":         get_head_to_head,
}
