import re
"""
Graph Query Tool — wraps Neo4j queries as a LlamaIndex QueryEngine.

Strategy:
  1. LLM is given the query + schema + few-shot examples → generates Cypher.
  2. Cypher is executed; results are formatted as a markdown table.
  3. If execution fails, the error is fed back to the LLM for a corrected query
     (up to 2 retries).
  4. LLM synthesises results into a natural-language answer.

Improvements over v1:
  - Few-shot Cypher examples in prompt for higher accuracy.
  - Retry-with-error-feedback loop (up to 2 retries).
  - Cleaner error messages surfaced to the user.
"""
from llama_index.core.base.base_query_engine import BaseQueryEngine
from llama_index.core.callbacks import CallbackManager
from llama_index.core.schema import QueryBundle
from llama_index.core.base.response.schema import Response
from graph.neo4j_client import run_query

SCHEMA_SUMMARY = """
Neo4j graph schema for NBA data (2013-14 to 2022-23):

Nodes:
  Player   {player_id, name, position, height, weight, country,
             draft_year, draft_round, draft_pick, from_year, to_year,
             career_pts_avg, career_ast_avg, career_reb_avg}
  Team     {team_id, name, city, abbreviation, conference, division}
  Game     {game_id, date, season, season_type,
             home_team_id, away_team_id, home_score, away_score, winner_team_id}
  Season   {year}  -- e.g. "2015-16"
  Award    {award_id, award_type, season, player_name, player_id, team}
  PlayerSeasonStats {player_id, season, team_id,
                      games_played,
                      pts     -- points PER GAME average (e.g. 27.5, NOT total points),
                      ast     -- assists per game avg,
                      reb     -- rebounds per game avg,
                      stl     -- steals per game avg,
                      blk     -- blocks per game avg,
                      fg_pct, fg3_pct, ft_pct,
                      min     -- minutes per game avg,
                      tov, plus_minus}
  IMPORTANT: pts/ast/reb/stl/blk/min are already per-game averages.
  NEVER divide them by games_played — that would be wrong.

Relationships:
  (Player)-[:PLAYED_FOR {season, games_played}]->(Team)
  (Player)-[:HAS_SEASON_STATS]->(PlayerSeasonStats)
  (Player)-[:WON_AWARD]->(Award)
  (Team)-[:WON_CHAMPIONSHIP]->(Season)
  (Team)-[:PLAYED_GAME {home_or_away, score}]->(Game)
  (Game)-[:IN_SEASON]->(Season)

Season format: "2015-16" (string).
Award types include: "Most Valuable Player", "Defensive Player of the Year",
  "Rookie of the Year", "Finals MVP", "NBA Champion", "All-NBA", "All-Star".
"""

FEW_SHOT_EXAMPLES = """
Examples (question → Cypher):

Q: Who won the MVP award in 2016-17?
A: MATCH (a:Award) WHERE a.award_type = "Most Valuable Player" AND a.season = "2016-17"
   RETURN a.player_name AS player, a.team AS team, a.season AS season

Q: What were LeBron James's stats in the 2015-16 season?
A: MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:PlayerSeasonStats)
   WHERE toLower(p.name) CONTAINS "lebron james" AND s.season = "2015-16"
   RETURN p.name AS player, s.season AS season, s.pts AS ppg,
          s.ast AS apg, s.reb AS rpg, s.stl AS spg, s.blk AS bpg

Q: How many points per game did LeBron James average in the 2017-18 season?
A: MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:PlayerSeasonStats)
   WHERE toLower(p.name) CONTAINS "lebron james" AND s.season = "2017-18"
   RETURN p.name AS player, s.season AS season, s.pts AS ppg
   -- NOTE: s.pts is already the per-game average, do NOT divide by games_played

Q: Which team won the most championships?
A: MATCH (t:Team)-[:WON_CHAMPIONSHIP]->(s:Season)
   RETURN t.name AS team, count(s) AS championships
   ORDER BY championships DESC LIMIT 5

Q: Who were the top scorers in the 2022-23 season?
A: MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:PlayerSeasonStats)
   WHERE s.season = "2022-23" AND s.games_played >= 20
   RETURN p.name AS player, s.pts AS ppg, s.ast AS apg, s.reb AS rpg
   ORDER BY s.pts DESC LIMIT 10

Q: Which teams did Kevin Durant play for?
A: MATCH (p:Player)-[:PLAYED_FOR]->(t:Team)
   WHERE toLower(p.name) CONTAINS "kevin durant"
   RETURN t.name AS team, p.name AS player
   ORDER BY t.name

Q: What awards did Stephen Curry win?
A: MATCH (p:Player)-[:WON_AWARD]->(a:Award)
   WHERE toLower(p.name) CONTAINS "stephen curry"
   RETURN a.award_type AS award, a.season AS season, a.team AS team
   ORDER BY a.season

Q: How many wins did the Golden State Warriors have each season?
A: MATCH (t:Team)-[:PLAYED_GAME]->(g:Game)
   WHERE toLower(t.name) CONTAINS "golden state"
     AND g.winner_team_id = t.team_id
   RETURN g.season AS season, count(g) AS wins
   ORDER BY season

Q: Which players scored the most points total across all seasons?
A: MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:PlayerSeasonStats)
   RETURN p.name AS player, avg(s.pts) AS avg_ppg, count(s) AS seasons
   ORDER BY avg_ppg DESC LIMIT 10

Q: What is the head-to-head record between the Lakers and Celtics?
A: MATCH (t1:Team)-[:PLAYED_GAME]->(g:Game)<-[:PLAYED_GAME]-(t2:Team)
   WHERE toLower(t1.name) CONTAINS "lakers" AND toLower(t2.name) CONTAINS "celtics"
   RETURN count(g) AS total_games,
          sum(CASE WHEN g.winner_team_id = t1.team_id THEN 1 ELSE 0 END) AS lakers_wins,
          sum(CASE WHEN g.winner_team_id = t2.team_id THEN 1 ELSE 0 END) AS celtics_wins

Q: Who improved the most in scoring from their rookie season to their third season?
A: MATCH (p:Player)-[:HAS_SEASON_STATS]->(s1:PlayerSeasonStats)
   MATCH (p)-[:HAS_SEASON_STATS]->(s3:PlayerSeasonStats)
   WHERE s1.games_played >= 20 AND s3.games_played >= 20
     AND s1.season < s3.season
   WITH p, s1.pts AS rookie_pts, s3.pts AS year3_pts, s1.season AS s1, s3.season AS s3
   WHERE year3_pts - rookie_pts > 5
   RETURN p.name AS player, s1 AS season1, rookie_pts, s3 AS season3, year3_pts,
          round(year3_pts - rookie_pts, 1) AS pts_improvement
   ORDER BY pts_improvement DESC LIMIT 10

Q: Which player won the most awards overall?
A: MATCH (p:Player)-[:WON_AWARD]->(a:Award)
   WHERE NOT a.award_type IN ["All-Star", "All-NBA"]
   RETURN p.name AS player, count(a) AS total_awards, collect(DISTINCT a.award_type) AS award_types
   ORDER BY total_awards DESC LIMIT 10

Q: Which team dominated the 2015-16 to 2018-19 era, and what players drove that dominance?
A: MATCH (t:Team)-[:WON_CHAMPIONSHIP]->(s:Season)
   WHERE s.year >= "2015-16" AND s.year <= "2018-19"
   WITH t, count(s) AS championships, collect(s.year) AS seasons_won
   ORDER BY championships DESC LIMIT 1
   MATCH (p:Player)-[r:PLAYED_FOR]->(t)
   WHERE r.season >= "2015-16" AND r.season <= "2018-19"
   WITH t, championships, seasons_won, p, count(r) AS seasons_on_team
   MATCH (p)-[:HAS_SEASON_STATS]->(pss:PlayerSeasonStats)
   WHERE pss.season >= "2015-16" AND pss.season <= "2018-19"
   RETURN t.name AS dominant_team, championships, seasons_won,
          p.name AS player, seasons_on_team,
          round(avg(pss.pts), 1) AS avg_ppg,
          round(avg(pss.ast), 1) AS avg_apg,
          round(avg(pss.reb), 1) AS avg_rpg
   ORDER BY avg_ppg DESC LIMIT 8

Q: What were LeBron James's career averages across all seasons?
A: MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:PlayerSeasonStats)
   WHERE toLower(p.name) CONTAINS "lebron james"
   RETURN p.name AS player,
          round(avg(s.pts), 1) AS career_ppg,
          round(avg(s.ast), 1) AS career_apg,
          round(avg(s.reb), 1) AS career_rpg,
          round(avg(s.stl), 1) AS career_spg,
          count(s) AS seasons_played

Q: Who are the best three-point shooters in the 2022-23 season?
A: MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:PlayerSeasonStats)
   WHERE s.season = "2022-23" AND s.games_played >= 30
   RETURN p.name AS player, s.fg3_pct AS three_pct, s.pts AS ppg
   ORDER BY s.fg3_pct DESC LIMIT 10

Q: Which team scored the most points on average in the 2021-22 season?
A: MATCH (t:Team)-[:PLAYED_GAME]->(g:Game)
   WHERE g.season = "2021-22"
   WITH t, g,
     CASE WHEN g.home_team_id = t.team_id THEN g.home_score ELSE g.away_score END AS team_score
   RETURN t.name AS team, round(avg(team_score), 1) AS avg_pts, count(g) AS games
   ORDER BY avg_pts DESC LIMIT 10
"""

CYPHER_PROMPT = """You are a Neo4j Cypher expert for an NBA analytics system.
Given the schema below and a user question, write a Cypher query that answers the question.

Schema:
{schema}

{examples}

Rules:
- Use toLower() for case-insensitive name matching.
- Use CONTAINS for partial name matches.
- Always LIMIT results to 20 unless the user asks for all.
- Season format is "2022-23" — always use this string format.
- Award types use full names: "Most Valuable Player", not "MVP".
- Return only the Cypher query — no explanation, no markdown fences.
- If the question cannot be answered from this schema, return: UNSUPPORTED
- For multi-part questions, generate Cypher for the STRUCTURED data part only
  (stats, championships, awards, records). Ignore any prediction sub-question.
- For era/dominance queries ("which team dominated X to Y era"), ALWAYS use
  WON_CHAMPIONSHIP with s.year range: WHERE s.year >= "X" AND s.year <= "Y".

Question: {question}
Cypher:"""

CYPHER_RETRY_PROMPT = """You are a Neo4j Cypher expert. Your previous query failed with an error.
Fix the query based on the error message.

Schema:
{schema}

Original question: {question}

Previous (broken) Cypher:
{bad_cypher}

Error:
{error}

Write a corrected Cypher query. Return ONLY the query, no explanation.
Cypher:"""


_ERA_RE = re.compile(r'(\d{4}-\d{2})\s+to\s+(\d{4}-\d{2})', re.I)
_ERA_KEYWORDS = ("dominat", "era", "ruled", "dominated", "best team during", "drive")


def _build_era_cypher(question: str) -> str | None:
    """
    If the question asks about era/period dominance, return a pre-built Cypher
    that finds the top championship-winning team + their key players in that range.
    Bypasses LLM generation for this well-known pattern.
    """
    m = _ERA_RE.search(question)
    if not m:
        return None
    q_lower = question.lower()
    if not any(k in q_lower for k in _ERA_KEYWORDS):
        return None
    start, end = m.group(1), m.group(2)
    return f"""
MATCH (t:Team)-[:WON_CHAMPIONSHIP]->(s:Season)
WHERE s.year >= "{start}" AND s.year <= "{end}"
WITH t, count(s) AS championships, collect(s.year) AS seasons_won
ORDER BY championships DESC LIMIT 1
MATCH (p:Player)-[r:PLAYED_FOR]->(t)
WHERE r.season >= "{start}" AND r.season <= "{end}"
WITH t, championships, seasons_won, p, count(r) AS seasons_on_team
MATCH (p)-[:HAS_SEASON_STATS]->(pss:PlayerSeasonStats)
WHERE pss.season >= "{start}" AND pss.season <= "{end}"
RETURN t.name AS dominant_team, championships, seasons_won,
       p.name AS player, seasons_on_team,
       round(avg(pss.pts), 1) AS avg_ppg,
       round(avg(pss.ast), 1) AS avg_apg,
       round(avg(pss.reb), 1) AS avg_rpg
ORDER BY avg_ppg DESC LIMIT 8
""".strip()


def _extract_cypher(llm_output: str) -> str | None:
    """Parse LLM output to extract a valid Cypher statement."""
    text = llm_output.strip()
    # Strip markdown code fences if present
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip().lstrip("cypher").strip()
            if p.upper().startswith(("MATCH", "RETURN", "WITH", "CALL")):
                return p
    if text.upper().startswith(("MATCH", "RETURN", "WITH", "CALL")):
        return text
    return None


def _format_results(records: list[dict]) -> str:
    """Format Neo4j records as a markdown table."""
    if not records:
        return "No results found."
    if len(records) == 1 and len(records[0]) == 1:
        val = list(records[0].values())[0]
        return str(val)

    headers = list(records[0].keys())
    rows    = [[str(r.get(h, "")) for h in headers] for r in records]
    col_w   = [max(len(h), max((len(r[i]) for r in rows), default=0))
               for i, h in enumerate(headers)]

    sep  = "| " + " | ".join("-" * w for w in col_w) + " |"
    head = "| " + " | ".join(h.ljust(col_w[i]) for i, h in enumerate(headers)) + " |"
    body = "\n".join(
        "| " + " | ".join(v.ljust(col_w[i]) for i, v in enumerate(row)) + " |"
        for row in rows
    )
    return f"{head}\n{sep}\n{body}"


class GraphQueryEngine(BaseQueryEngine):
    def __init__(self, llm, max_retries: int = 2):
        self._llm        = llm
        self._max_retries = max_retries
        super().__init__(callback_manager=CallbackManager())

    def _get_prompt_modules(self):
        return {}

    def _generate_cypher(self, question: str) -> str | None:
        """First-pass Cypher generation."""
        prompt = CYPHER_PROMPT.format(
            schema=SCHEMA_SUMMARY,
            examples=FEW_SHOT_EXAMPLES,
            question=question,
        )
        raw = str(self._llm.complete(prompt))
        return _extract_cypher(raw)

    def _fix_cypher(self, question: str, bad_cypher: str, error: str) -> str | None:
        """Retry Cypher generation with error feedback."""
        prompt = CYPHER_RETRY_PROMPT.format(
            schema=SCHEMA_SUMMARY,
            question=question,
            bad_cypher=bad_cypher,
            error=error,
        )
        raw = str(self._llm.complete(prompt))
        return _extract_cypher(raw)

    def _query(self, query_bundle: QueryBundle) -> Response:
        question = query_bundle.query_str

        # ── Step 1: Generate Cypher ────────────────────────────────────────────
        # Try pattern-matched pre-built queries first (more reliable than LLM)
        cypher = _build_era_cypher(question) or self._generate_cypher(question)

        if not cypher:
            return Response(
                response=(
                    "I couldn't generate a valid graph query for this question. "
                    "Try rephrasing or ask about specific stats, awards, or team records."
                ),
                source_nodes=[],
            )

        if "UNSUPPORTED" in cypher.upper():
            return Response(
                response=(
                    "This question requires information not available in the structured "
                    "knowledge graph. Try the semantic search tool for narrative questions."
                ),
                source_nodes=[],
            )

        # ── Step 2: Execute with retry loop ───────────────────────────────────
        records = None
        last_error = ""
        for attempt in range(self._max_retries + 1):
            try:
                records = run_query(cypher)
                break  # success
            except Exception as e:
                last_error = str(e)
                if attempt < self._max_retries:
                    fixed = self._fix_cypher(question, cypher, last_error)
                    if fixed and fixed != cypher:
                        cypher = fixed
                    else:
                        break  # LLM couldn't improve; give up

        if records is None:
            return Response(
                response=(
                    f"The graph query failed after {self._max_retries + 1} attempts. "
                    f"Last error: {last_error}\n\nGenerated Cypher:\n{cypher}"
                ),
                source_nodes=[],
            )

        # ── Step 3: Format + Synthesise ────────────────────────────────────────
        table = _format_results(records)

        if table == "No results found.":
            return Response(
                response=(
                    "The query ran successfully but returned no results. "
                    "The data might not be available for the specified player, team, or season."
                ),
                source_nodes=[],
            )

        summary_prompt = (
            f"Question: {question}\n\n"
            f"Data retrieved from the NBA knowledge graph:\n{table}\n\n"
            "Provide a clear, specific answer using the data above. "
            "Cite exact numbers, player names, and seasons. "
            "Do not include any data not shown above."
        )
        answer = str(self._llm.complete(summary_prompt))
        return Response(response=answer, source_nodes=[])

    async def _aquery(self, query_bundle: QueryBundle) -> Response:
        return self._query(query_bundle)


def build_graph_query_engine(llm):
    return GraphQueryEngine(llm=llm)
