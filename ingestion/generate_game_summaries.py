"""
Phase 4c — Generate playoff series + Finals summary markdown files.

Creates knowledge_base/games/ folder with:
  - One file per playoff series (grouped by season + team matchup)
  - Finals series get extra championship context

These fill the previously empty games/ folder, allowing the RAG system to answer
questions like "What happened in the 2016 NBA Finals?" or "How did the Raptors
beat the Warriors in 2019?"

Run after generate_md_files.py.
"""
from pathlib import Path
from collections import defaultdict
from ingestion.utils import RAW_DIR, load_json

KB_DIR  = Path("knowledge_base")
OUT_DIR = KB_DIR / "games"

CHAMPIONS = {
    "2013-14": "San Antonio Spurs",   "2014-15": "Golden State Warriors",
    "2015-16": "Cleveland Cavaliers", "2016-17": "Golden State Warriors",
    "2017-18": "Golden State Warriors","2018-19": "Toronto Raptors",
    "2019-20": "Los Angeles Lakers",  "2020-21": "Milwaukee Bucks",
    "2021-22": "Golden State Warriors","2022-23": "Denver Nuggets",
}

TEAM_META = {
    "ATL": "East", "BOS": "East", "BKN": "East", "CHA": "East", "CHI": "East",
    "CLE": "East", "DAL": "West", "DEN": "West", "DET": "East", "GSW": "West",
    "HOU": "West", "IND": "East", "LAC": "West", "LAL": "West", "MEM": "West",
    "MIA": "East", "MIL": "East", "MIN": "West", "NOP": "West", "NYK": "East",
    "OKC": "West", "ORL": "East", "PHI": "East", "PHX": "West", "POR": "West",
    "SAC": "West", "SAS": "West", "TOR": "East", "UTA": "West", "WAS": "East",
}

# Full team names by abbreviation
ABBR_TO_NAME = {
    "ATL": "Atlanta Hawks",         "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",         "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",         "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",      "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",       "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",       "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",  "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",     "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",       "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",  "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers","SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",     "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",             "WAS": "Washington Wizards",
    # Occasional old abbreviation
    "NJN": "New Jersey Nets",       "NOH": "New Orleans Hornets",
    "SEA": "Seattle SuperSonics",   "VAN": "Vancouver Grizzlies",
}

# Champion context per Finals matchup
FINALS_CONTEXT = {
    "2013-14": {
        "teams": ("SAS", "MIA"),
        "context": (
            "The San Antonio Spurs avenged their 2013 Finals loss to the Miami Heat with a "
            "masterclass in team basketball. Kawhi Leonard won Finals MVP in just his third "
            "season. The Spurs' beautiful ball movement was epitomized by their 25-consecutive-"
            "pass scoring play in Game 4. LeBron James and the Heat had no answer."
        ),
    },
    "2014-15": {
        "teams": ("GSW", "CLE"),
        "context": (
            "The Golden State Warriors won their first championship in 40 years. Andre Iguodala "
            "won Finals MVP, becoming the first Finals MVP since 1969 to not start every game. "
            "The Cavaliers were severely hampered by injuries to Kyrie Irving (broken kneecap) "
            "and Kevin Love (dislocated shoulder). LeBron James was heroic but undermanned."
        ),
    },
    "2015-16": {
        "teams": ("CLE", "GSW"),
        "context": (
            "The most dramatic Finals in modern NBA history. The Cleveland Cavaliers became the "
            "first team to overcome a 3-1 series deficit in Finals history. LeBron James "
            "produced the greatest individual Finals performance ever — 29.7 PPG, 11.3 RPG, "
            "8.9 APG. His chase-down block on Andre Iguodala and Kyrie Irving's three-pointer "
            "with 53 seconds left in Game 7 are the defining moments. The Warriors had won a "
            "record 73 regular-season games but could not close out the series."
        ),
    },
    "2016-17": {
        "teams": ("GSW", "CLE"),
        "context": (
            "Kevin Durant's first championship with Golden State, silencing critics about his "
            "Finals performance under pressure. Durant averaged 35.2 PPG and won Finals MVP. "
            "The Warriors won 4-1, with Durant's dominant performances in Games 3, 4, and 5 "
            "being essentially unanswerable. LeBron James again averaged a triple-double but "
            "the talent gap was simply too large."
        ),
    },
    "2017-18": {
        "teams": ("GSW", "CLE"),
        "context": (
            "The fourth consecutive Warriors-Cavaliers Finals matchup — the first time the same "
            "two teams had met in four straight Finals since the Celtics and Lakers rivalry of "
            "the 1960s. The Warriors swept 4-0. LeBron averaged 34 PPG in the sweep but had "
            "limited support. JR Smith's inexplicable dribble-out in Game 1 overtime remains "
            "one of the most discussed moments in NBA Finals history."
        ),
    },
    "2018-19": {
        "teams": ("TOR", "GSW"),
        "context": (
            "The Toronto Raptors won their first NBA championship, defeating the Warriors 4-2. "
            "Golden State lost Kevin Durant to an Achilles injury in Game 5 and Klay Thompson "
            "to an ACL injury in Game 6. Kawhi Leonard averaged 28.5 PPG and won Finals MVP. "
            "The Raptors were the first non-American team to win an NBA title. The Warriors "
            "dynasty effectively ended in this series."
        ),
    },
    "2019-20": {
        "teams": ("LAL", "MIA"),
        "context": (
            "The Finals were played in the NBA Bubble in Orlando with no fans due to COVID-19. "
            "The Lakers won 4-2, with LeBron James averaging 29.8 PPG, 11.8 APG, and 8.5 RPG "
            "to win his fourth Finals MVP. Anthony Davis was dominant inside. Jimmy Butler had "
            "an extraordinary series for Miami (35.9 PPG in Game 3) but the Heat couldn't sustain "
            "it. The victory was dedicated to the memory of Kobe Bryant."
        ),
    },
    "2020-21": {
        "teams": ("MIL", "PHX"),
        "context": (
            "The Milwaukee Bucks defeated the Phoenix Suns 4-2. Giannis Antetokounmpo was "
            "superhuman — his 50-point, 14-rebound, 5-block Game 6 clincher stands as one of "
            "the greatest individual Finals performances ever. Devin Booker averaged 27 PPG for "
            "Phoenix. The Bucks' victory ended a 50-year championship drought and validated "
            "Giannis's loyalty to the franchise."
        ),
    },
    "2021-22": {
        "teams": ("GSW", "BOS"),
        "context": (
            "The Golden State Warriors won their fourth title in eight years, defeating the "
            "Boston Celtics 4-2. Stephen Curry finally won his first Finals MVP after three "
            "previous championships. Curry averaged 31.2 PPG in the Finals. The Warriors "
            "overcame a 2-3 series deficit with back-to-back road wins. Andrew Wiggins emerged "
            "as a two-way hero in this series."
        ),
    },
    "2022-23": {
        "teams": ("DEN", "MIA"),
        "context": (
            "The Denver Nuggets won their first championship in franchise history, defeating the "
            "Miami Heat 4-1. Nikola Jokic won Finals MVP with a historic triple-double series "
            "performance (30.2 PPG, 14.0 RPG, 7.2 APG). Jamal Murray averaged 26 PPG. The Heat "
            "made the Finals as an 8-seed — the first 8-seed to reach the Finals since 1999 — "
            "but were outmatched by Denver's depth and Jokic's dominance."
        ),
    },
}


def is_finals(abbr1: str, abbr2: str) -> bool:
    """Determine if a series is the Finals (East team vs West team)."""
    conf1 = TEAM_META.get(abbr1, "")
    conf2 = TEAM_META.get(abbr2, "")
    return conf1 != "" and conf2 != "" and conf1 != conf2


def generate_series_md(
    season: str,
    abbr1: str,
    abbr2: str,
    games: list[dict],
    is_final: bool,
) -> str:
    name1 = ABBR_TO_NAME.get(abbr1, abbr1)
    name2 = ABBR_TO_NAME.get(abbr2, abbr2)

    # Sort games by date
    games_sorted = sorted(games, key=lambda g: g["date"])

    # Tally wins
    wins1 = sum(1 for g in games_sorted if g["winner_team_abbr"] == abbr1)
    wins2 = sum(1 for g in games_sorted if g["winner_team_abbr"] == abbr2)

    if wins1 > wins2:
        series_winner, series_loser = name1, name2
        w, l = wins1, wins2
    else:
        series_winner, series_loser = name2, name1
        w, l = wins2, wins1

    title_suffix = "NBA Finals" if is_final else "Playoff Series"
    lines = [
        f"# {season} {title_suffix}: {name1} vs {name2}",
        "",
        f"**Season:** {season}  ",
        f"**Type:** {'NBA Finals' if is_final else 'NBA Playoffs'}  ",
        f"**Result:** {series_winner} won {w}-{l}",
        "",
    ]

    # Finals context
    if is_final:
        # Look up specific finals context
        ctx = None
        for fkey, fval in FINALS_CONTEXT.items():
            if fkey == season:
                teams = fval.get("teams", ())
                if abbr1 in teams and abbr2 in teams:
                    ctx = fval.get("context")
                    break
        if ctx:
            lines += [
                "## Series Story",
                "",
                ctx,
                "",
            ]

    # Game log
    lines += [
        "## Game-by-Game Results",
        "",
        "| Game | Date | Home | Away | Score | Winner |",
        "|------|------|------|------|-------|--------|",
    ]
    for i, g in enumerate(games_sorted, 1):
        home_name = ABBR_TO_NAME.get(g["home_team_abbr"], g["home_team_abbr"])
        away_name = ABBR_TO_NAME.get(g["away_team_abbr"], g["away_team_abbr"])
        winner_name = ABBR_TO_NAME.get(g["winner_team_abbr"], g["winner_team_abbr"])
        score = f"{g['home_score']}-{g['away_score']}"
        lines.append(
            f"| {i} | {g['date']} | {home_name} | {away_name} | {score} | {winner_name} |"
        )

    lines += [
        "",
        "## Series Summary",
        "",
        f"{series_winner} defeated {series_loser} {w} games to {l}. "
        f"The series lasted {len(games_sorted)} games.",
    ]

    return "\n".join(lines) + "\n"


def generate_all_game_summaries():
    print("Generating playoff series summary files...")
    games_all = load_json(RAW_DIR / "games.json") or []

    # Filter to playoff games only
    playoffs = [g for g in games_all if g.get("season_type") == "Playoffs"]
    print(f"  Found {len(playoffs)} playoff games across all seasons")

    # Add winner_team_abbr field for convenience
    for g in playoffs:
        if g["winner_team_id"] == g["home_team_id"]:
            g["winner_team_abbr"] = g["home_team_abbr"]
        else:
            g["winner_team_abbr"] = g["away_team_abbr"]

    # Group by (season, sorted matchup key)
    series_map: dict[tuple, list] = defaultdict(list)
    for g in playoffs:
        abbrs = tuple(sorted([g["home_team_abbr"], g["away_team_abbr"]]))
        key = (g["season"], abbrs[0], abbrs[1])
        series_map[key].append(g)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    for (season, abbr1, abbr2), games in series_map.items():
        if len(games) < 2:
            continue  # Skip any orphaned single game

        finals = is_finals(abbr1, abbr2)
        md = generate_series_md(season, abbr1, abbr2, games, is_final=finals)

        season_slug = season.replace("-", "_")
        file_name   = f"{season_slug}_{abbr1}_vs_{abbr2}.md"
        (OUT_DIR / file_name).write_text(md, encoding="utf-8")
        count += 1

        if finals:
            winner_abbr = abbr1 if sum(1 for g in games if g["winner_team_abbr"] == abbr1) > \
                                   sum(1 for g in games if g["winner_team_abbr"] == abbr2) else abbr2
            winner_name = ABBR_TO_NAME.get(winner_abbr, winner_abbr)
            print(f"  Finals {season}: {winner_name} ✓")

    print(f"  {count} series summary files -> {OUT_DIR}")


def main():
    print("=" * 60)
    print("Generating game / playoff series summary files")
    print("=" * 60)
    generate_all_game_summaries()
    print("\nDone. Run load_weaviate.py next.")


if __name__ == "__main__":
    main()
