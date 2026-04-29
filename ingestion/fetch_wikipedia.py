"""
Fetch Wikipedia full article text for NBA players and teams.
Saves one .txt file per entity under knowledge_base/wikipedia/players/
and knowledge_base/wikipedia/teams/

Run: python -m ingestion.fetch_wikipedia
"""
import os, time, re, unicodedata, requests
from pathlib import Path

# ── output dirs ───────────────────────────────────────────────────────────────
BASE = Path("knowledge_base/wikipedia")
PLAYER_DIR = BASE / "players"
TEAM_DIR   = BASE / "teams"
PLAYER_DIR.mkdir(parents=True, exist_ok=True)
TEAM_DIR.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "SportMindNBAProject/1.0 (educational)"})

WIKI_API = "https://en.wikipedia.org/w/api.php"

# ── player list ───────────────────────────────────────────────────────────────
PLAYERS = [
    "LeBron James","Stephen Curry","Kevin Durant","James Harden","Luka Dončić",
    "Joel Embiid","Damian Lillard","Trae Young","Anthony Davis","Giannis Antetokounmpo",
    "Kyrie Irving","Devin Booker","Russell Westbrook","DeMar DeRozan","Jayson Tatum",
    "Ja Morant","Paul George","Kawhi Leonard","Klay Thompson","Jimmy Butler",
    "Nikola Jokić","Karl-Anthony Towns","Bradley Beal","Zach LaVine","Chris Paul",
    "Dwyane Wade","Carmelo Anthony","Blake Griffin","Kevin Love","DeMarcus Cousins",
    "Donovan Mitchell","Shai Gilgeous-Alexander","Anthony Edwards","Jaylen Brown",
    "Bam Adebayo","Pascal Siakam","Kyle Lowry","Jrue Holiday","Jamal Murray",
    "Khris Middleton","Julius Randle","Chris Bosh","LaMarcus Aldridge","John Wall",
    "CJ McCollum","Kemba Walker","Darius Garland","Nikola Vučević","Kobe Bryant",
    "Dirk Nowitzki","Zion Williamson","LaMelo Ball","Andrew Wiggins","De'Aaron Fox",
    "Kristaps Porzingis","Brandon Ingram","Paolo Banchero","Cade Cunningham",
    "Jalen Green","Tyler Herro","Lauri Markkanen","Deandre Ayton","Franz Wagner",
    "Scottie Barnes","Tyrese Maxey","Tyrese Haliburton","Evan Mobley",
    "Domantas Sabonis","Brook Lopez","Gordon Hayward","Isaiah Thomas",
    "Victor Oladipo","Lou Williams","Monta Ellis","Zach Randolph","Eric Gordon",
    "Jaren Jackson Jr.","Mike Conley","Jordan Clarkson","Bojan Bogdanovic",
    "Tobias Harris","Malcolm Brogdon","Kevin Martin","Buddy Hield","Jordan Poole",
    "RJ Barrett","Collin Sexton","Desmond Bane","Keldon Johnson","John Collins",
    "Kyle Kuzma","Jaden Ivey","Bennedict Mathurin","JJ Redick",
    # coaches
    "Gregg Popovich","Steve Kerr","Erik Spoelstra","Doc Rivers","Ty Lue",
    "Mike Budenholzer","Nick Nurse","Frank Vogel",
]

TEAMS = [
    "Golden State Warriors","Los Angeles Lakers","Boston Celtics","Miami Heat",
    "San Antonio Spurs","Cleveland Cavaliers","Chicago Bulls","Oklahoma City Thunder",
    "Houston Rockets","Dallas Mavericks","Toronto Raptors","Milwaukee Bucks",
    "Denver Nuggets","Phoenix Suns","Brooklyn Nets","Philadelphia 76ers",
    "Atlanta Hawks","Memphis Grizzlies","New Orleans Pelicans","Utah Jazz",
    "Portland Trail Blazers","Minnesota Timberwolves","Indiana Pacers",
    "Charlotte Hornets","Detroit Pistons","Sacramento Kings","New York Knicks",
    "Orlando Magic","Washington Wizards","Los Angeles Clippers",
]


def _slug(name: str) -> str:
    """Filesystem-safe filename."""
    n = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^\w\s-]", "", n).strip().replace(" ", "_").lower()


def fetch_wikipedia_article(title: str) -> str | None:
    """
    Fetches the full plain-text extract of a Wikipedia article.
    Uses the Extracts API (faster than parsing wikitext).
    Returns None if not found.
    """
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,       # plain text, no HTML
        "exsectionformat": "plain",
        "redirects": True,
    }
    try:
        r = SESSION.get(WIKI_API, params=params, timeout=15)
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        page  = next(iter(pages.values()))
        if "missing" in page:
            return None
        text = page.get("extract", "").strip()
        return text if len(text) > 200 else None
    except Exception as e:
        print(f"  ERROR fetching '{title}': {e}")
        return None


def search_wikipedia_title(query: str) -> str | None:
    """If direct fetch fails, search for the best matching title."""
    params = {
        "action": "opensearch",
        "format": "json",
        "search": query,
        "limit": 3,
    }
    try:
        r = SESSION.get(WIKI_API, params=params, timeout=10)
        titles = r.json()[1]
        return titles[0] if titles else None
    except:
        return None


def save(path: Path, name: str, text: str):
    path.write_text(f"# {name}\n\n{text}", encoding="utf-8")


def run(entities: list[str], out_dir: Path, label: str):
    print(f"\n=== Fetching {label} ({len(entities)}) ===")
    ok = skip = fail = 0
    for name in entities:
        slug = _slug(name)
        fpath = out_dir / f"{slug}.txt"
        if fpath.exists():
            skip += 1
            continue

        text = fetch_wikipedia_article(name)
        if not text:
            # try search fallback
            alt = search_wikipedia_title(name)
            if alt and alt.lower() != name.lower():
                text = fetch_wikipedia_article(alt)

        if text:
            save(fpath, name, text)
            words = len(text.split())
            print(f"  [{ok+1}] {name} -> {words:,} words")
            ok += 1
        else:
            print(f"  [!] NOT FOUND: {name}")
            fail += 1

        time.sleep(0.3)   # be polite to Wikipedia

    print(f"  Done: {ok} saved, {skip} skipped (already exist), {fail} not found")


if __name__ == "__main__":
    run(PLAYERS, PLAYER_DIR, "Players + Coaches")
    run(TEAMS,   TEAM_DIR,   "Teams")
    total = sum(1 for _ in BASE.rglob("*.txt"))
    print(f"\nTotal Wikipedia files: {total}")
