"""
Run the full ingestion pipeline in order.
Each script is idempotent — safe to re-run if interrupted.

Estimated time:
  fetch_players  ~5-6 min  (bio requests dominate)
  fetch_teams    ~15 sec
  fetch_games    ~6-7 min  (player game logs dominate)
  fetch_awards   ~10 sec
  ─────────────────────────
  Total          ~12-15 min
"""
from ingestion.fetch_players import main as players
from ingestion.fetch_teams   import main as teams
from ingestion.fetch_games   import main as games
from ingestion.fetch_awards  import main as awards

if __name__ == "__main__":
    print("\n" + "█" * 60)
    print("  SportMind — Data Ingestion Pipeline")
    print("█" * 60 + "\n")

    print("── 1/4  Players ──────────────────────────────────────────")
    players()

    print("\n── 2/4  Teams ────────────────────────────────────────────")
    teams()

    print("\n── 3/4  Games ────────────────────────────────────────────")
    games()

    print("\n── 4/4  Awards ───────────────────────────────────────────")
    awards()

    print("\n" + "█" * 60)
    print("  Ingestion complete. data/raw/ is populated.")
    print("  Next: python -m ingestion.load_neo4j")
    print("█" * 60)
