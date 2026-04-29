"""
Phase 4a — Auto-generate markdown knowledge base files.

Generates richly-narrated .md files for:
  - players/    top 300 players  (stats + awards + playing style + best seasons)
  - teams/      all 30 teams     (records + narrative + key players)
  - seasons/    10 seasons       (standings + awards + storylines + top performers)

These files are chunked and loaded into Weaviate for hybrid RAG retrieval.
"""
from pathlib import Path
from ingestion.utils import RAW_DIR, SEASONS, load_json

KB_DIR = Path("knowledge_base")

# ── Shared data ────────────────────────────────────────────────────────────────

CHAMPIONS = {
    "2013-14": "San Antonio Spurs",   "2014-15": "Golden State Warriors",
    "2015-16": "Cleveland Cavaliers", "2016-17": "Golden State Warriors",
    "2017-18": "Golden State Warriors","2018-19": "Toronto Raptors",
    "2019-20": "Los Angeles Lakers",  "2020-21": "Milwaukee Bucks",
    "2021-22": "Golden State Warriors","2022-23": "Denver Nuggets",
}

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

# Rich team narratives for notable franchises
TEAM_NARRATIVES = {
    "Golden State Warriors": (
        "The Warriors were the defining dynasty of the 2010s, winning four NBA championships "
        "in eight years (2015, 2017, 2018, 2022). Built around 'Splash Brothers' Stephen Curry "
        "and Klay Thompson under coach Steve Kerr, they revolutionized basketball with their "
        "three-point shooting and ball movement. Kevin Durant joined in 2016-17, forming one of "
        "the most talented rosters in NBA history. Their 73-9 regular season record in 2015-16 "
        "remains the best single-season record in NBA history. Stephen Curry became the first "
        "unanimous MVP in 2015-16."
    ),
    "Cleveland Cavaliers": (
        "The Cavaliers returned LeBron James to Cleveland in 2014 after his stint with Miami. "
        "They reached the Finals four consecutive years (2015-2018). Their 2016 championship "
        "stands as one of the greatest upsets in sports history — they became the first team "
        "to overcome a 3-1 Finals deficit, defeating the record-setting 73-win Warriors. "
        "LeBron James's chase-down block on Iguodala and Kyrie Irving's clutch three-pointer "
        "in Game 7 are iconic moments in NBA history."
    ),
    "San Antonio Spurs": (
        "The Spurs capped a dynasty under Gregg Popovich with the 2014 championship, defeating "
        "LeBron James's Miami Heat with beautiful team basketball. Tim Duncan, Tony Parker, and "
        "Manu Ginobili's final title run showcased textbook ball movement. They also developed "
        "Kawhi Leonard into a two-way star who would eventually lead Toronto to the 2019 title. "
        "The Spurs' sustained excellence across decades is unmatched in modern NBA history."
    ),
    "Miami Heat": (
        "The Heat's Big Three era (LeBron James, Dwyane Wade, Chris Bosh) ended with their 2014 "
        "Finals loss to San Antonio. LeBron then departed for Cleveland. Miami subsequently "
        "rebuilt and made a surprising run to the 2020 NBA Finals in the Orlando Bubble, "
        "showcasing Jimmy Butler's elite leadership and toughness. The Heat's culture emphasizes "
        "conditioning, hard work, and defensive intensity known as 'Heat Culture.'"
    ),
    "Toronto Raptors": (
        "The Raptors won their first and only NBA championship in 2018-19, powered by Kawhi "
        "Leonard's iconic 'Kawhi Shot' buzzer-beater in the second round against Philadelphia "
        "and his dominant Finals performance against an injury-depleted Warriors squad. Leonard's "
        "60-point, four-bounce buzzer-beater in the second round became one of the most memorable "
        "moments in NBA playoff history. Pascal Siakam developed into an All-Star alongside him."
    ),
    "Los Angeles Lakers": (
        "The Lakers ended a decade-long championship drought by winning the 2020 NBA title in the "
        "COVID Bubble in Orlando. LeBron James and Anthony Davis formed a dominant duo. LeBron "
        "became the first player to win Finals MVP with three different franchises. The franchise "
        "legend Kobe Bryant passed away in January 2020, adding emotional weight to the championship "
        "run as the team dedicated their title to his memory."
    ),
    "Milwaukee Bucks": (
        "Giannis Antetokounmpo developed from a raw, skinny 18-year-old into a two-time MVP and "
        "NBA champion. The Bucks won the 2021 championship with Giannis delivering an extraordinary "
        "50-point performance in the clinching Game 6 against Phoenix, finishing with 14 rebounds "
        "and 5 blocks. It was the Bucks' first title since 1971 and validated Giannis's decision "
        "to remain in Milwaukee despite being pursued by bigger-market teams."
    ),
    "Denver Nuggets": (
        "The Nuggets won their first NBA championship in 2022-23, led by Nikola Jokic's "
        "unprecedented three-time MVP dominance. Jokic's unique combination of scoring, passing, "
        "and rebounding at center redefined what the position could be. Jamal Murray's scoring "
        "punch complemented Jokic perfectly, and their chemistry was unmatched in the league. "
        "The Nuggets defeated the Miami Heat 4-1 in the Finals, with Jokic winning his first "
        "Finals MVP award."
    ),
    "Oklahoma City Thunder": (
        "The Thunder were a consistent Western Conference contender led by Kevin Durant and "
        "Russell Westbrook during the early part of the decade. Durant's 2014 MVP season, "
        "highlighted by his emotional 'You are the real MVP' speech to his mother, remains "
        "one of the most moving moments in NBA history. After Durant's departure to Golden State "
        "in 2016, Westbrook won the MVP with a historic 42-triple-double season in 2016-17."
    ),
    "Chicago Bulls": (
        "The Bulls were competitive in the early 2010s, led by Derrick Rose who won the MVP "
        "in 2010-11 as the youngest MVP in NBA history. Injuries derailed their championship "
        "window. Jimmy Butler emerged as a star during this era before eventually being traded. "
        "The team went through a difficult rebuild during the latter part of the decade."
    ),
}

# Season storylines with factual historical context
SEASON_STORYLINES = {
    "2013-14": (
        "The San Antonio Spurs won their fifth NBA championship in dominant fashion, defeating "
        "LeBron James's Miami Heat 4-1 in the Finals. The Spurs played arguably the most "
        "beautiful team basketball in NBA history, sharing the ball and moving without the ball "
        "in a way that left the Heat helpless. Kevin Durant of Oklahoma City won the MVP award "
        "in one of the most emotional acceptance speeches in NBA history. The Heat, seeking their "
        "third consecutive title, were simply outclassed by a veteran Spurs squad hungry for "
        "revenge after the 2013 Finals heartbreak."
    ),
    "2014-15": (
        "The Golden State Warriors won their first NBA championship in 40 years, defeating the "
        "Cleveland Cavaliers 4-2 in the Finals. Stephen Curry won his first MVP award as he led "
        "a revolution in three-point shooting. Andre Iguodala won Finals MVP after guarding "
        "LeBron James throughout the series. Coach Steve Kerr's first season resulted in a "
        "championship, with the Warriors' pace-and-space offense dazzling the league. The Cavaliers "
        "were hampered by injuries to Kevin Love and Kyrie Irving."
    ),
    "2015-16": (
        "The Golden State Warriors set the NBA record with 73 regular-season wins, surpassing "
        "the 1995-96 Chicago Bulls. Stephen Curry became the first unanimous MVP in NBA history, "
        "averaging 30.1 PPG and making 402 three-pointers. Despite this historic season, the "
        "Cleveland Cavaliers — led by LeBron James, Kyrie Irving, and Kevin Love — won the NBA "
        "championship in one of the greatest upsets in sports history. Coming back from a 3-1 "
        "deficit, LeBron James delivered his signature chase-down block and Kyrie Irving hit the "
        "go-ahead three in the final minute of Game 7."
    ),
    "2016-17": (
        "Kevin Durant made the most controversial free agency decision in NBA history, joining "
        "the Golden State Warriors after losing a 3-1 series lead to them the previous year. "
        "The resulting superteam was virtually unstoppable, sweeping the Cleveland Cavaliers "
        "4-1 in the Finals. Durant won Finals MVP. Russell Westbrook, spurned by his former "
        "co-star, responded by averaging a historic 31.6 PPG, 10.7 APG, and 10.4 RPG — the "
        "first player to average a triple-double for an entire season since Oscar Robertson."
    ),
    "2017-18": (
        "The NBA Finals featured a fourth consecutive Warriors-Cavaliers matchup — an "
        "unprecedented occurrence in NBA history. The Warriors swept the Cavaliers 4-0, with "
        "Kevin Durant again winning Finals MVP. LeBron James had an extraordinary individual "
        "performance, averaging 34 PPG in the Finals, but had little help. After the sweep, "
        "LeBron James left Cleveland for the Los Angeles Lakers, ending the Warriors-Cavaliers "
        "rivalry era."
    ),
    "2018-19": (
        "The Golden State Warriors faced a depleted roster in the Finals, losing Kevin Durant "
        "to injury before the series and Klay Thompson during Game 6. The Toronto Raptors, "
        "powered by Kawhi Leonard's transcendent performance, won their first-ever NBA "
        "championship. Leonard averaged 28.5 PPG in the Finals and won Finals MVP. His iconic "
        "buzzer-beater against Philadelphia in the second round had bounced on the rim four "
        "times before dropping. The Warriors' dynasty era effectively ended with this loss."
    ),
    "2019-20": (
        "The NBA season was suspended in March 2020 due to the COVID-19 pandemic and resumed "
        "in the NBA Bubble in Orlando starting in July. The Los Angeles Lakers, led by LeBron "
        "James and Anthony Davis, won the championship, defeating the Miami Heat 4-2. The "
        "season carried extra emotional weight following the tragic death of Kobe Bryant and "
        "his daughter Gianna in a helicopter crash in January 2020. LeBron won his fourth "
        "title and his fourth Finals MVP with a third different team."
    ),
    "2020-21": (
        "The Milwaukee Bucks won their first NBA championship since 1971, defeating the Phoenix "
        "Suns 4-2 in the Finals. Giannis Antetokounmpo delivered one of the greatest Finals "
        "performances in history, dropping 50 points, 14 rebounds, and 5 blocks in the "
        "clinching Game 6. The Greek Freak silenced questions about his ability to perform in "
        "crunch time and whether Milwaukee could win a title. Nikola Jokic won his first MVP "
        "award with the Denver Nuggets."
    ),
    "2021-22": (
        "The Golden State Warriors completed a dynasty comeback, winning their fourth "
        "championship in 8 years by defeating the Boston Celtics 4-2. Stephen Curry finally "
        "won his first Finals MVP award after three previous championships. The Warriors did it "
        "with a core of Curry, Klay Thompson, and Draymond Green supplemented by young players "
        "Jordan Poole and Andrew Wiggins. Nikola Jokic won his second consecutive MVP award."
    ),
    "2022-23": (
        "The Denver Nuggets won their first NBA championship in franchise history, defeating "
        "the Miami Heat 4-1 in the Finals. Nikola Jokic, playing in his prime as a three-time "
        "MVP, won Finals MVP with a historic triple-double performance across the series. Jamal "
        "Murray's dynamic scoring and playoff heroics complemented Jokic perfectly. The Nuggets "
        "were the clear best team in the NBA all season and delivered on that promise in the "
        "postseason."
    ),
}


def safe(val, default="N/A"):
    return val if val not in (None, "", 0, "0") else default


# ── Playing Style Inference ────────────────────────────────────────────────────

def infer_playing_style(stats_rows: list[dict]) -> str | None:
    """Infer a player's playing style from their career averages."""
    if not stats_rows:
        return None

    n = len(stats_rows)
    avg_pts = sum(r.get("PTS", 0) or 0 for r in stats_rows) / n
    avg_ast = sum(r.get("AST", 0) or 0 for r in stats_rows) / n
    avg_reb = sum(r.get("REB", 0) or 0 for r in stats_rows) / n
    avg_stl = sum(r.get("STL", 0) or 0 for r in stats_rows) / n
    avg_blk = sum(r.get("BLK", 0) or 0 for r in stats_rows) / n
    avg_fg3 = sum((r.get("FG3_PCT") or 0) for r in stats_rows) / n

    traits = []

    if avg_pts >= 25:
        traits.append(f"superstar scorer ({avg_pts:.1f} PPG)")
    elif avg_pts >= 20:
        traits.append(f"elite scorer ({avg_pts:.1f} PPG)")
    elif avg_pts >= 15:
        traits.append(f"reliable scorer ({avg_pts:.1f} PPG)")
    elif avg_pts >= 10:
        traits.append(f"contributor ({avg_pts:.1f} PPG)")

    if avg_ast >= 8:
        traits.append(f"elite point-making playmaker ({avg_ast:.1f} APG)")
    elif avg_ast >= 6:
        traits.append(f"strong playmaker ({avg_ast:.1f} APG)")
    elif avg_ast >= 4:
        traits.append(f"capable passer ({avg_ast:.1f} APG)")

    if avg_reb >= 11:
        traits.append(f"dominant rebounder ({avg_reb:.1f} RPG)")
    elif avg_reb >= 8:
        traits.append(f"solid rebounder ({avg_reb:.1f} RPG)")

    if avg_blk >= 2.0:
        traits.append(f"elite shot blocker ({avg_blk:.1f} BPG)")
    elif avg_blk >= 1.5:
        traits.append(f"rim protector ({avg_blk:.1f} BPG)")

    if avg_stl >= 1.8:
        traits.append(f"lockdown defender ({avg_stl:.1f} SPG)")
    elif avg_stl >= 1.3:
        traits.append(f"active defender ({avg_stl:.1f} SPG)")

    if avg_fg3 >= 0.40 and avg_pts >= 15:
        traits.append(f"sharpshooter ({avg_fg3 * 100:.1f}% from three)")
    elif avg_fg3 >= 0.37 and avg_pts >= 12:
        traits.append(f"three-point threat ({avg_fg3 * 100:.1f}% from three)")

    if not traits:
        return "A versatile contributor who provides value in multiple areas."

    if len(traits) == 1:
        return f"Known as a {traits[0]}."
    return "Known as a " + ", ".join(traits[:-1]) + f", and {traits[-1]}."


# ── Players ────────────────────────────────────────────────────────────────────

def generate_player_md(
    player_id: int,
    name: str,
    bio: dict,
    stats_rows: list[dict],
    player_awards: list[dict],
) -> str:
    pos    = safe(bio.get("POSITION"))
    height = safe(bio.get("HEIGHT"))
    weight = safe(bio.get("WEIGHT"))
    country = safe(bio.get("COUNTRY"))
    dy     = safe(bio.get("DRAFT_YEAR"))
    dr     = safe(bio.get("DRAFT_ROUND"))
    dp     = safe(bio.get("DRAFT_NUMBER"))
    fy     = safe(bio.get("FROM_YEAR"))
    ty     = safe(bio.get("TO_YEAR"))

    draft_str = f"{dy} NBA Draft, Round {dr}, Pick #{dp}" if dy != "N/A" else "Undrafted"
    teams_seen = sorted({r["TEAM_ABBREVIATION"] for r in stats_rows})

    lines = [
        f"# {name}",
        "",
        f"**Position:** {pos}  ",
        f"**Height / Weight:** {height} / {weight} lbs  ",
        f"**Country:** {country}  ",
        f"**Draft:** {draft_str}  ",
        f"**NBA Career:** {fy} – {ty}  ",
        f"**Teams (2013–2023):** {', '.join(teams_seen)}",
        "",
    ]

    # ── Playing Style ──────────────────────────────────────────────────────────
    style = infer_playing_style(stats_rows)
    if style:
        lines += [
            "## Playing Style",
            "",
            style,
            "",
        ]

    # ── Awards & Recognition ───────────────────────────────────────────────────
    # Filter to major individual awards (not All-Star which is very common)
    major_types = {
        "Most Valuable Player", "Defensive Player of the Year",
        "Rookie of the Year", "Finals MVP", "Most Improved Player",
        "All-NBA", "All-Defensive",
    }
    major_awards = [a for a in player_awards if a.get("award_type") in major_types]
    all_star_awards = [a for a in player_awards if a.get("award_type") == "All-Star"]

    if major_awards or all_star_awards:
        lines += ["## Awards & Recognition (2013–2023)", ""]
        for award in sorted(major_awards, key=lambda a: a.get("season", "")):
            lines.append(
                f"- **{award['award_type']}** — {award.get('season', '')} "
                f"({award.get('team', '')})"
            )
        if all_star_awards:
            all_star_seasons = [a.get("season", "") for a in all_star_awards]
            lines.append(
                f"- **All-Star selections:** {', '.join(sorted(all_star_seasons))}"
            )
        lines.append("")

    # ── Best Seasons ───────────────────────────────────────────────────────────
    if stats_rows:
        top3 = sorted(stats_rows, key=lambda r: r.get("PTS", 0), reverse=True)[:3]
        lines += ["## Peak Seasons", ""]
        for r in top3:
            season = r.get("SEASON", "")
            # Check if this season had any awards
            season_major = [a for a in major_awards if a.get("season") == season
                            and a["award_type"] in ("Most Valuable Player", "Defensive Player of the Year",
                                                     "Finals MVP", "Rookie of the Year")]
            award_tag = ""
            if season_major:
                award_tag = "  ⭐ " + ", ".join(a["award_type"] for a in season_major)
            lines.append(
                f"- **{season}** ({r['TEAM_ABBREVIATION']}): "
                f"{r.get('PTS', 0):.1f} PPG, {r.get('AST', 0):.1f} APG, "
                f"{r.get('REB', 0):.1f} RPG in {r.get('GP', 0)} games{award_tag}"
            )
        lines.append("")

    # ── Season-by-Season Stats ─────────────────────────────────────────────────
    lines += [
        "## Season-by-Season Stats (2013–2023)",
        "",
        "| Season | Team | GP | PTS | AST | REB | STL | BLK | FG% | 3P% |",
        "|--------|------|----|-----|-----|-----|-----|-----|-----|-----|",
    ]
    for r in sorted(stats_rows, key=lambda x: x["SEASON"]):
        lines.append(
            f"| {r['SEASON']} | {r['TEAM_ABBREVIATION']} "
            f"| {r.get('GP', 0)} "
            f"| {r.get('PTS', 0):.1f} "
            f"| {r.get('AST', 0):.1f} "
            f"| {r.get('REB', 0):.1f} "
            f"| {r.get('STL', 0):.1f} "
            f"| {r.get('BLK', 0):.1f} "
            f"| {(r.get('FG_PCT') or 0) * 100:.1f}% "
            f"| {(r.get('FG3_PCT') or 0) * 100:.1f}% |"
        )

    # ── Career Averages ────────────────────────────────────────────────────────
    if stats_rows:
        avg_pts = sum(r.get("PTS", 0) or 0 for r in stats_rows) / len(stats_rows)
        avg_ast = sum(r.get("AST", 0) or 0 for r in stats_rows) / len(stats_rows)
        avg_reb = sum(r.get("REB", 0) or 0 for r in stats_rows) / len(stats_rows)
        avg_stl = sum(r.get("STL", 0) or 0 for r in stats_rows) / len(stats_rows)
        avg_blk = sum(r.get("BLK", 0) or 0 for r in stats_rows) / len(stats_rows)
        lines += [
            "",
            "## Career Averages (2013–2023)",
            "",
            f"- **Points:** {avg_pts:.1f} PPG",
            f"- **Assists:** {avg_ast:.1f} APG",
            f"- **Rebounds:** {avg_reb:.1f} RPG",
            f"- **Steals:** {avg_stl:.1f} SPG",
            f"- **Blocks:** {avg_blk:.1f} BPG",
        ]

    return "\n".join(lines) + "\n"


def generate_all_player_files():
    print("Generating player markdown files...")
    bios   = load_json(RAW_DIR / "players_bio.json") or {}
    stats  = load_json(RAW_DIR / "players_stats.json") or []
    awards = load_json(RAW_DIR / "awards.json") or []

    # Build player_name → awards map (awards.json has names, not IDs)
    name_to_awards: dict[str, list] = {}
    for award in awards:
        pn = award.get("player_name", "")
        if pn:
            name_to_awards.setdefault(pn, []).append(award)

    # Rank players by total GP
    totals: dict[int, int] = {}
    for row in stats:
        pid = row["PLAYER_ID"]
        totals[pid] = totals.get(pid, 0) + (row.get("GP") or 0)
    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    top300 = {pid for pid, _ in ranked[:300]}

    by_player: dict[int, list] = {}
    names: dict[int, str] = {}
    for row in stats:
        pid = row["PLAYER_ID"]
        by_player.setdefault(pid, []).append(row)
        names[pid] = row["PLAYER_NAME"]

    out_dir = KB_DIR / "players"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for pid in top300:
        name = names.get(pid, f"player_{pid}")
        bio  = bios.get(str(pid), {})
        rows = by_player.get(pid, [])
        player_awards = name_to_awards.get(name, [])
        md   = generate_player_md(pid, name, bio, rows, player_awards)
        slug = name.lower().replace(" ", "_").replace(".", "").replace("'", "")
        (out_dir / f"{slug}.md").write_text(md, encoding="utf-8")
        count += 1

    print(f"  {count} player files -> {out_dir}")


# ── Teams ──────────────────────────────────────────────────────────────────────

def _team_narrative_from_data(team: dict, champ_seasons: list, team_stats_rows: list) -> str:
    """Generate a data-driven narrative for teams without a hardcoded story."""
    name = team["full_name"]
    abbr = team.get("abbreviation", "")
    conf, div = TEAM_META.get(abbr, ("", ""))

    if not team_stats_rows:
        return f"The {name} compete in the {conf}ern Conference, {div} Division."

    best = max(team_stats_rows, key=lambda r: r.get("W_PCT", 0))
    worst = min(team_stats_rows, key=lambda r: r.get("W_PCT", 0))
    avg_w = sum(r.get("W", 0) for r in team_stats_rows) / len(team_stats_rows)

    parts = [
        f"The {name} compete in the {conf}ern Conference, {div} Division. "
        f"Over the 2013-2023 decade, they averaged {avg_w:.0f} wins per season."
    ]

    if champ_seasons:
        parts.append(f"They won NBA championships in: {', '.join(champ_seasons)}.")

    parts.append(
        f"Their best season in this era was {best['SEASON']} "
        f"({best.get('W', 0)}-{best.get('L', 0)}, {best.get('W_PCT', 0):.3f} win%). "
        f"Their most difficult season was {worst['SEASON']} "
        f"({worst.get('W', 0)}-{worst.get('L', 0)})."
    )

    return " ".join(parts)


def _top_scorers_per_era(abbr: str, stats: list[dict]) -> str | None:
    """Find top scoring players for a team by looking at team abbr in player stats."""
    team_rows = [r for r in stats if r.get("TEAM_ABBREVIATION") == abbr]
    if not team_rows:
        return None

    # Sum pts*gp as a rough measure of team contribution
    player_pts: dict[str, float] = {}
    for r in team_rows:
        pname = r.get("PLAYER_NAME", "")
        pts   = (r.get("PTS") or 0)
        gp    = (r.get("GP") or 0)
        player_pts[pname] = player_pts.get(pname, 0) + pts * gp

    top5 = sorted(player_pts.items(), key=lambda x: x[1], reverse=True)[:5]
    if not top5:
        return None

    return ", ".join(f"**{name}**" for name, _ in top5)


def generate_team_md(team: dict, team_stats_rows: list[dict], all_player_stats: list[dict]) -> str:
    abbr = team.get("abbreviation", "")
    conf, div = TEAM_META.get(abbr, ("", ""))
    champ_seasons = [s for s, champ in CHAMPIONS.items() if champ == team["full_name"]]

    lines = [
        f"# {team['full_name']}",
        "",
        f"**Abbreviation:** {abbr}  ",
        f"**City:** {team.get('city', '')}  ",
        f"**Conference:** {conf}  ",
        f"**Division:** {div}  ",
    ]
    if champ_seasons:
        lines.append(f"**Championships (2013–2023):** {', '.join(champ_seasons)}")
    lines.append("")

    # ── Team Narrative ─────────────────────────────────────────────────────────
    narrative = TEAM_NARRATIVES.get(
        team["full_name"],
        _team_narrative_from_data(team, champ_seasons, team_stats_rows)
    )
    lines += [
        "## Team Overview",
        "",
        narrative,
        "",
    ]

    # ── Key Players ────────────────────────────────────────────────────────────
    top = _top_scorers_per_era(abbr, all_player_stats)
    if top:
        lines += [
            "## Key Players (2013–2023)",
            "",
            f"Top contributors by scoring volume: {top}",
            "",
        ]

    # ── Season Records ─────────────────────────────────────────────────────────
    lines += [
        "## Season Records (2013–2023)",
        "",
        "| Season | W | L | Win% | Notes |",
        "|--------|---|---|------|-------|",
    ]
    for r in sorted(team_stats_rows, key=lambda x: x["SEASON"]):
        w    = r.get("W", 0)
        l    = r.get("L", 0)
        pct  = r.get("W_PCT", 0.0)
        champ_flag = " 🏆 Champions" if CHAMPIONS.get(r["SEASON"]) == team["full_name"] else ""
        lines.append(f"| {r['SEASON']} | {w} | {l} | {pct:.3f} |{champ_flag} |")

    return "\n".join(lines) + "\n"


def generate_all_team_files():
    print("Generating team markdown files...")
    teams       = load_json(RAW_DIR / "teams.json") or []
    team_stats  = load_json(RAW_DIR / "teams_stats.json") or []
    player_stats = load_json(RAW_DIR / "players_stats.json") or []

    by_team: dict[int, list] = {}
    for row in team_stats:
        by_team.setdefault(row["TEAM_ID"], []).append(row)

    out_dir = KB_DIR / "teams"
    out_dir.mkdir(parents=True, exist_ok=True)
    for t in teams:
        rows = by_team.get(t["id"], [])
        md   = generate_team_md(t, rows, player_stats)
        slug = t["full_name"].lower().replace(" ", "_")
        (out_dir / f"{slug}.md").write_text(md, encoding="utf-8")

    print(f"  {len(teams)} team files -> {out_dir}")


# ── Seasons ────────────────────────────────────────────────────────────────────

def generate_season_md(season: str, team_stats_rows: list[dict], award_rows: list[dict]) -> str:
    champ = CHAMPIONS.get(season, "Unknown")

    lines = [
        f"# NBA Season {season}",
        "",
        f"**Champion:** {champ}  ",
        f"**Season:** {season}",
        "",
    ]

    # ── Season Storyline ───────────────────────────────────────────────────────
    storyline = SEASON_STORYLINES.get(season)
    if storyline:
        lines += [
            "## Season Storyline",
            "",
            storyline,
            "",
        ]

    # ── Award Winners ──────────────────────────────────────────────────────────
    lines += ["## Award Winners", ""]
    season_awards = [a for a in award_rows if a.get("season") == season]
    major_awards = [
        "Most Valuable Player", "Defensive Player of the Year",
        "Rookie of the Year", "Finals MVP", "Most Improved Player",
    ]
    for award_type in major_awards:
        match = next((a for a in season_awards if a["award_type"] == award_type), None)
        if match and match.get("player_name"):
            lines.append(
                f"- **{award_type}:** {match['player_name']} ({match.get('team', '')})"
            )
    lines.append("")

    # ── Top Performers ─────────────────────────────────────────────────────────
    # Derived from team_stats: top teams only. For players we'd need player stats.
    if team_stats_rows:
        sorted_teams = sorted(team_stats_rows, key=lambda x: x.get("W_PCT", 0), reverse=True)
        top5 = sorted_teams[:5]
        lines += ["## Top Teams (Regular Season)", ""]
        for i, r in enumerate(top5, 1):
            champ_flag = " 🏆" if r["TEAM_NAME"] == champ else ""
            lines.append(
                f"{i}. **{r['TEAM_NAME']}** — {r.get('W', 0)}-{r.get('L', 0)} "
                f"({r.get('W_PCT', 0):.3f}){champ_flag}"
            )
        lines.append("")

    # ── Full Standings ─────────────────────────────────────────────────────────
    lines += [
        "## Full Team Standings (Regular Season)",
        "",
        "| Rank | Team | W | L | Win% |",
        "|------|------|---|---|------|",
    ]
    sorted_all = sorted(team_stats_rows, key=lambda x: x.get("W_PCT", 0), reverse=True)
    for i, r in enumerate(sorted_all, 1):
        champ_flag = " 🏆" if r["TEAM_NAME"] == champ else ""
        lines.append(
            f"| {i} | {r['TEAM_NAME']}{champ_flag} "
            f"| {r.get('W', 0)} | {r.get('L', 0)} | {r.get('W_PCT', 0):.3f} |"
        )

    return "\n".join(lines) + "\n"


def generate_all_season_files():
    print("Generating season markdown files...")
    team_stats = load_json(RAW_DIR / "teams_stats.json") or []
    awards     = load_json(RAW_DIR / "awards.json") or []

    by_season: dict[str, list] = {}
    for row in team_stats:
        by_season.setdefault(row["SEASON"], []).append(row)

    out_dir = KB_DIR / "seasons"
    out_dir.mkdir(parents=True, exist_ok=True)
    for season in SEASONS:
        rows = by_season.get(season, [])
        md   = generate_season_md(season, rows, awards)
        slug = season.replace("-", "_")
        (out_dir / f"season_{slug}.md").write_text(md, encoding="utf-8")

    print(f"  {len(SEASONS)} season files -> {out_dir}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Generating knowledge base markdown files (enhanced)")
    print("=" * 60)
    generate_all_player_files()
    generate_all_team_files()
    generate_all_season_files()
    print("\nDone. Run generate_game_summaries.py next, then load_weaviate.py.")


if __name__ == "__main__":
    main()
