// ── Constraints (run once on a fresh DB) ──────────────────────────────────────
CREATE CONSTRAINT player_id IF NOT EXISTS FOR (p:Player) REQUIRE p.player_id IS UNIQUE;
CREATE CONSTRAINT team_id   IF NOT EXISTS FOR (t:Team)   REQUIRE t.team_id   IS UNIQUE;
CREATE CONSTRAINT game_id   IF NOT EXISTS FOR (g:Game)   REQUIRE g.game_id   IS UNIQUE;
CREATE CONSTRAINT season_id IF NOT EXISTS FOR (s:Season) REQUIRE s.year      IS UNIQUE;
CREATE CONSTRAINT coach_id  IF NOT EXISTS FOR (c:Coach)  REQUIRE c.name      IS UNIQUE;
CREATE CONSTRAINT award_id  IF NOT EXISTS FOR (a:Award)  REQUIRE a.award_id  IS UNIQUE;

// ── Indexes ────────────────────────────────────────────────────────────────────
CREATE INDEX player_name IF NOT EXISTS FOR (p:Player) ON (p.name);
CREATE INDEX team_name   IF NOT EXISTS FOR (t:Team)   ON (t.name);
CREATE INDEX game_date   IF NOT EXISTS FOR (g:Game)   ON (g.date);
CREATE INDEX season_year IF NOT EXISTS FOR (s:Season) ON (s.year);
