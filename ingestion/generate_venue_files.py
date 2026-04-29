"""
Generate markdown files for key NBA arenas (2013-2023).
Output: knowledge_base/venues/{arena_slug}.md
"""
from pathlib import Path

VENUES_DIR = Path("knowledge_base/venues")
VENUES_DIR.mkdir(parents=True, exist_ok=True)

VENUES = [
    {
        "slug": "chase_center",
        "content": """# Chase Center — Golden State Warriors

**Location:** San Francisco, CA
**Opened:** 2019
**Capacity:** 18,064
**Previous home:** Oracle Arena (Oakland, 1966-2019)

## Overview

Chase Center opened in 2019 as the first privately financed arena in San Francisco. The Warriors moved from Oracle Arena in Oakland, ending a 47-year run in the East Bay. The arena sits in the Mission Bay neighborhood and cost approximately $1.4 billion to build.

## Oracle Arena Legacy

Oracle Arena — nicknamed "Roaracle" for its deafening crowd noise — was one of the loudest buildings in the NBA. The Warriors' 2013-2019 dynasty years (four Finals, three championships) were built in Oakland. The crowd atmosphere played a measurable home-court advantage role during the Stephen Curry era. Warriors home games in Oakland had some of the highest documented crowd noise levels in professional basketball.

## Notable Games

The 2019 NBA Finals (Warriors vs. Raptors) was split between Oracle Arena (Games 3-5) and Scotiabank Arena. Game 6, when Kawhi Leonard and the Raptors clinched their first title at Oracle Arena, was the last playoff game at the venue.
""",
    },
    {
        "slug": "scotiabank_arena",
        "content": """# Scotiabank Arena — Toronto Raptors

**Location:** Toronto, Ontario, Canada
**Opened:** 1999 (as Air Canada Centre)
**Capacity:** 19,800
**Renamed:** 2018 (from Air Canada Centre to Scotiabank Arena)

## Overview

Scotiabank Arena is the only NBA arena located in Canada, making it a unique cultural venue. Toronto's passionate fan base created one of the best home-court atmospheres in the league during the Raptors' championship era.

## 2019 Championship Run

Scotiabank Arena witnessed the Raptors' first NBA Finals home games in franchise history. The "Jurassic Park" viewing party outside drew 15,000+ fans per game. Kawhi Leonard's playoff performances — including the iconic Game 7 buzzer-beater against Philadelphia — electrified the building and the city.

## Home Court Advantage

The Raptors had the 4th-best home record in the East during 2018-19 (31-10 at home). The building's relatively tight sightlines created an intimate, loud atmosphere that opposing teams cited as one of the toughest road environments.
""",
    },
    {
        "slug": "td_garden",
        "content": """# TD Garden — Boston Celtics

**Location:** Boston, MA
**Opened:** 1995
**Capacity:** 19,156

## Overview

TD Garden sits above North Station in downtown Boston, the spiritual successor to the famous Boston Garden. The Celtics' storied history (17 championships, most in NBA history) makes this building one of the most historic venues in basketball.

## 2013-2023 Era

The Celtics underwent a full rebuild after trading away Kevin Garnett and Paul Pierce in 2013. They developed Jayson Tatum and Jaylen Brown through the late 2010s, returning to relevance by 2020. TD Garden hosted Eastern Conference Finals games in 2018 (lost to Cleveland), 2020 (bubble, no fans), 2022 (won, went to Finals), and 2023 (lost to Miami).

## Home Court Atmosphere

Boston fans are among the most knowledgeable in the NBA. The Garden's parquet floor tradition — though the modern building uses a replica pattern — maintains the historical connection. The crowd's reaction to three-pointers and defensive stops creates distinctive energy.
""",
    },
    {
        "slug": "fiserv_forum",
        "content": """# Fiserv Forum — Milwaukee Bucks

**Location:** Milwaukee, WI
**Opened:** 2018
**Capacity:** 17,341

## Overview

Fiserv Forum replaced the BMO Harris Bradley Center (1988-2018) and is one of the newest arenas in the NBA. The building was completed just in time for the Bucks' championship window under Giannis Antetokounmpo.

## 2021 Championship

Fiserv Forum hosted the Bucks' first championship series games since 1974. The "Deer District" — a massive outdoor plaza surrounding the arena — became a cultural phenomenon during the 2021 Finals. Over 65,000 fans gathered outside for Games 3-4, one of the largest sports gatherings in Wisconsin history.

Giannis Antetokounmpo's historic 50-point performance in Game 6 vs. Phoenix, sealing the Bucks' first title in 50 years, happened before a sold-out Fiserv Forum crowd. The moment is considered the peak of the arena's short history.
""",
    },
    {
        "slug": "staples_center_crypto_arena",
        "content": """# Crypto.com Arena (formerly Staples Center) — Los Angeles Lakers / Clippers

**Location:** Los Angeles, CA
**Opened:** 1999
**Capacity:** 19,067
**Renamed:** 2021 (from Staples Center to Crypto.com Arena)

## Overview

Staples Center / Crypto.com Arena is the only arena to host two NBA teams (Lakers and Clippers). It's located in the heart of downtown Los Angeles and is adjacent to the LA Live entertainment complex.

## Lakers Legacy

The Lakers won three championships at Staples Center (2000, 2001, 2002) in the Shaquille O'Neal / Kobe Bryant era, and another in 2010 (Kobe Bryant). The 2019-20 championship was won in the bubble, but the celebration happened at Staples Center.

## 2013-2023 Era

- **Lakers**: Kobe Bryant's retirement in 2016 (60-point finale) is one of the arena's most iconic events. LeBron James signed in 2018; the 2020 championship featured no fans (bubble). The team returned to the building for a championship celebration.
- **Clippers**: The "Lob City" era (Griffin, Paul, Jordan) drew large crowds. The franchise has yet to win a championship.

## Cultural Significance

Staples Center hosted the 2018 NBA All-Star Game and the memorial service for Kobe Bryant in 2020. The arena's celebrity seating (courtside) is among the most famous in sports entertainment.
""",
    },
]


def main():
    print(f"Writing {len(VENUES)} venue files to {VENUES_DIR}/")
    for v in VENUES:
        path = VENUES_DIR / f"{v['slug']}.md"
        path.write_text(v["content"].strip(), encoding="utf-8")
        print(f"  Written: {path.name}")
    print("Done.")


if __name__ == "__main__":
    main()
