"""
REST endpoints for dashboard stats cards and graph explorer.
"""
from fastapi import APIRouter, HTTPException, Query
from graph.neo4j_client import run_query
from graph import queries

router = APIRouter()


# ── Player endpoints ──────────────────────────────────────────────────────────

@router.get("/stats/player/{player_name}")
async def get_player_stats(player_name: str, season: str = Query(None)):
    """Season stats for a player. Optional ?season=2021-22"""
    try:
        stats  = queries.get_player_season_stats(player_name, season)
        awards = queries.get_player_awards(player_name)
        bio    = queries.get_career_overview(player_name)
        return {
            "player":  bio[0] if bio else {},
            "stats":   stats,
            "awards":  awards,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/top-scorers")
async def get_top_scorers(season: str = Query("2022-23"), limit: int = Query(10)):
    try:
        return queries.get_top_scorers(season, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Team endpoints ────────────────────────────────────────────────────────────

@router.get("/stats/team/{team_name}")
async def get_team_stats(team_name: str, season: str = Query(None)):
    try:
        championships = queries.get_team_championships(team_name)
        record        = queries.get_team_season_record(team_name, season)
        return {"championships": championships, "record": record}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/team/{team_name}/roster")
async def get_team_roster(team_name: str, season: str = Query("2022-23")):
    try:
        return queries.get_team_roster(team_name, season)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Season endpoints ──────────────────────────────────────────────────────────

@router.get("/stats/champions")
async def get_all_champions():
    try:
        return queries.get_all_champions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/awards")
async def get_award_winners(
    award: str = Query("Most Valuable Player"),
    season: str = Query(None),
):
    try:
        return queries.get_award_winners(award, season)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── League overview graph ─────────────────────────────────────────────────────

@router.get("/graph/overview")
async def get_league_overview():
    """
    League-wide graph: all 30 teams + their championships + top 2 players per team.
    Used for the 'League View' in GraphExplorer.
    """
    try:
        # All teams
        teams = run_query("MATCH (t:Team) RETURN elementId(t) AS id, t.name AS name")
        # Championships
        champs = run_query("""
            MATCH (t:Team)-[:WON_CHAMPIONSHIP]->(s:Season)
            RETURN elementId(t) AS tid, elementId(s) AS sid, s.year AS year
        """)
        # Top 2 players per team by avg pts
        players = run_query("""
            MATCH (p:Player)-[:PLAYED_FOR]->(t:Team)
            OPTIONAL MATCH (p)-[:HAS_SEASON_STATS]->(ss:PlayerSeasonStats)
            WITH p, t, avg(ss.pts) AS avg_pts
            ORDER BY avg_pts DESC
            WITH t, collect({pid: elementId(p), name: p.name, avg_pts: avg_pts})[..2] AS top
            UNWIND top AS row
            RETURN row.pid AS pid, row.name AS pname,
                   elementId(t) AS tid, t.name AS tname,
                   row.avg_pts AS avg_pts
        """)

        seen_nodes: dict[str, dict] = {}
        links = []

        for t in teams:
            seen_nodes[t["id"]] = {"id": t["id"], "label": t["name"], "type": "Team"}

        for c in champs:
            sid = c["sid"]
            if sid not in seen_nodes:
                seen_nodes[sid] = {"id": sid, "label": str(c["year"]), "type": "Season"}
            links.append({"source": c["tid"], "target": sid, "type": "WON_CHAMPIONSHIP"})

        for p in players:
            pid = p["pid"]
            if pid not in seen_nodes:
                seen_nodes[pid] = {"id": pid, "label": p["pname"], "type": "Player"}
            links.append({"source": pid, "target": p["tid"], "type": "PLAYED_FOR"})

        # Deduplicate links
        seen_links: set[tuple] = set()
        unique_links = []
        for l in links:
            k = (l["source"], l["target"], l["type"])
            if k not in seen_links:
                seen_links.add(k)
                unique_links.append(l)

        return {"nodes": list(seen_nodes.values()), "links": unique_links}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Graph explorer endpoint ───────────────────────────────────────────────────

@router.get("/graph/neighborhood/{entity_name}")
async def get_graph_neighborhood(entity_name: str, depth: int = Query(2, le=3)):
    """
    Returns nodes + edges for react-force-graph centered on entity_name.
    Searches Players and Teams by name.
    """
    try:
        # Focused 2-query neighborhood (no APOC required):
        #  Query 1: center node + 1-hop (teams, awards, championships)
        #  Query 2: for each team found, get top-5 players by pts avg
        # This keeps the graph readable (<60 nodes).

        # Step 1: resolve center node
        center_records = run_query(
            """
            MATCH (center)
            WHERE (center:Player OR center:Team)
              AND toLower(center.name) CONTAINS toLower($name)
            RETURN elementId(center) AS cid, head(labels(center)) AS ctype,
                   center.name AS clabel
            LIMIT 1
            """,
            {"name": entity_name},
        )
        if not center_records:
            return {"nodes": [], "links": []}

        cid   = center_records[0]["cid"]
        ctype = center_records[0]["ctype"]
        clabel = center_records[0]["clabel"]

        seen_nodes: dict[str, dict] = {cid: {"id": cid, "label": clabel, "type": ctype}}
        links_raw: list[dict] = []
        team_ids: list[str] = []

        # Step 2a: 1-hop non-Player neighbors (awards, championships, teams played for)
        hop1_records = run_query(
            """
            MATCH (center)
            WHERE elementId(center) = $cid
            OPTIONAL MATCH (center)-[r1:PLAYED_FOR|WON_AWARD|WON_CHAMPIONSHIP]-(n1)
            WHERE NOT n1:Player
            RETURN elementId(n1) AS nid, head(labels(n1)) AS ntype,
                   coalesce(n1.name, n1.award_type, n1.year) AS nlabel,
                   type(r1) AS rel
            """,
            {"cid": cid},
        )
        for row in hop1_records:
            nid, ntype, nlabel = row.get("nid"), row.get("ntype"), row.get("nlabel")
            if nid and nid not in seen_nodes:
                seen_nodes[nid] = {"id": nid, "label": nlabel, "type": ntype}
                if ntype == "Team":
                    team_ids.append(nid)
            if nid:
                links_raw.append({"source": cid, "target": nid, "type": row.get("rel", "")})

        # Step 2b: if center is a Team, add it to team_ids for player lookup
        if ctype == "Team":
            team_ids.append(cid)

        # Step 3: for each team, get top-6 players by pts average
        if team_ids:
            teammates = run_query(
                """
                MATCH (p:Player)-[:PLAYED_FOR]->(t:Team)
                WHERE elementId(t) IN $team_ids
                OPTIONAL MATCH (p)-[:HAS_SEASON_STATS]->(s:PlayerSeasonStats)
                WITH p, t, avg(s.pts) AS avg_pts
                ORDER BY avg_pts DESC
                WITH t, collect({pid: elementId(p), pname: p.name, tid: elementId(t)})[..6] AS top
                UNWIND top AS row
                RETURN row.pid AS pid, row.pname AS pname, row.tid AS tid
                """,
                {"team_ids": team_ids},
            )
            for row in teammates:
                pid, pname, tid = row["pid"], row["pname"], row["tid"]
                if pid and pid not in seen_nodes and pid != cid:
                    seen_nodes[pid] = {"id": pid, "label": pname, "type": "Player"}
                if pid and tid:
                    links_raw.append({"source": pid, "target": tid, "type": "PLAYED_FOR"})

        records = [{"nodes": list(seen_nodes.values()), "links": links_raw}]
        if not records:
            return {"nodes": [], "links": []}

        # Deduplicate nodes and links
        seen_nodes: set[str] = set()
        seen_links: set[tuple] = set()
        nodes, links = [], []
        for row in records:
            for n in (row.get("nodes") or []):
                if n and n["id"] not in seen_nodes:
                    seen_nodes.add(n["id"])
                    nodes.append(n)
            for l in (row.get("links") or []):
                if l:
                    key = (l["source"], l["target"], l["type"])
                    if key not in seen_links:
                        seen_links.add(key)
                        links.append(l)

        return {"nodes": nodes, "links": links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Prediction endpoints (REST, non-streaming) ────────────────────────────────

# ── Player comparison endpoint ────────────────────────────────────────────────

@router.get("/stats/compare")
async def compare_players(
    player1: str = Query(...),
    player2: str = Query(...),
):
    """Side-by-side career averages + awards for two players."""
    def _summarise(name: str) -> dict:
        bio_rows   = queries.get_career_overview(name)
        bio        = bio_rows[0] if bio_rows else {}
        stats_rows = queries.get_player_season_stats(name)
        award_rows = queries.get_player_awards(name)
        summary    = dict(bio)
        if stats_rows:
            n = len(stats_rows)
            summary.update(
                career_pts    = round(sum((r.get("pts") or 0) for r in stats_rows) / n, 1),
                career_ast    = round(sum((r.get("ast") or 0) for r in stats_rows) / n, 1),
                career_reb    = round(sum((r.get("reb") or 0) for r in stats_rows) / n, 1),
                career_stl    = round(sum((r.get("stl") or 0) for r in stats_rows) / n, 1),
                career_blk    = round(sum((r.get("blk") or 0) for r in stats_rows) / n, 1),
                seasons_played = n,
            )
        summary["awards"] = [
            {"award": a.get("award"), "season": a.get("season")} for a in award_rows
        ]
        return summary

    try:
        p1 = _summarise(player1)
        p2 = _summarise(player2)
        if not p1.get("player") and not p2.get("player"):
            raise HTTPException(status_code=404, detail="Neither player found")
        return {"player1": p1, "player2": p2}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Head-to-head endpoint ─────────────────────────────────────────────────────

@router.get("/stats/head-to-head")
async def head_to_head(
    team1: str = Query(...),
    team2: str = Query(...),
    season: str = Query(None),
):
    """Win-loss record + recent game log between two teams."""
    try:
        games = queries.get_head_to_head(team1, team2, season)
        if not games:
            return {"team1": team1, "team2": team2,
                    "team1_wins": 0, "team2_wins": 0, "games": []}
        t1_name = games[0]["team1"]
        t2_name = games[0]["team2"]
        t1_wins = sum(1 for g in games if g.get("winner") == t1_name)
        t2_wins = sum(1 for g in games if g.get("winner") == t2_name)
        return {
            "team1": t1_name, "team2": t2_name,
            "team1_wins": t1_wins, "team2_wins": t2_wins,
            "games": games[-15:],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Prediction endpoints (REST, non-streaming) ────────────────────────────────

@router.get("/predict/win")
async def predict_win(
    home_team: str = Query(...),
    away_team: str = Query(...),
    home_rest: int = Query(2),
    away_rest: int = Query(2),
):
    try:
        from ml.predictor import predict_win_probability
        return predict_win_probability(home_team, away_team, home_rest, away_rest)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Win probability model not yet trained.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predict/player")
async def predict_player(
    player: str = Query(...),
    metric: str = Query("pts"),
    periods: int = Query(10),
):
    try:
        from ml.predictor import forecast_player_performance
        return forecast_player_performance(player, metric, periods)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Player forecast models not yet trained.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
