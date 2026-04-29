"""
Generate markdown files for key NBA head coaches (2013-2023).
Covers coaching philosophy, notable seasons, playoff records, and legacy.
Output: knowledge_base/coaches/{coach_slug}.md
"""
from pathlib import Path

COACHES_DIR = Path("knowledge_base/coaches")
COACHES_DIR.mkdir(parents=True, exist_ok=True)

COACHES = [
    {
        "name": "Gregg Popovich",
        "team": "San Antonio Spurs",
        "seasons": "2013-2023",
        "slug": "gregg_popovich",
        "content": """# Gregg Popovich — Head Coach, San Antonio Spurs

**Tenure with Spurs:** 1996–present
**Record (2013–2023):** Approx. 530–330 regular season
**Championships:** 2013-14 (5th title overall)

## Coaching Philosophy

Gregg Popovich is widely regarded as the greatest coach in NBA history. His system emphasizes selfless basketball — ball movement, high basketball IQ, and team-first mentality. "Pop" demands accountability and trust, building a culture where stars and role players buy in equally. He developed the famous "Spurs system" of motion offense, spatial spacing, and interior-exterior passing that influenced the entire league.

Key pillars of his approach:
- **Ball movement**: The Spurs consistently led the league in assists and shot quality
- **Defense first**: Disciplined help defense, switching schemes, and late-clock execution
- **Player development**: Transformed international players (Parker, Ginobili, Gasol) into stars
- **Veteran management**: Extended careers of Tim Duncan, Manu Ginobili, and Tony Parker

## Notable Seasons (2013–2023)

| Season | W-L | Playoffs | Result |
|--------|-----|----------|--------|
| 2013-14 | 62-20 | Champion | Beat Miami Heat 4-1 (revenge for 2013) |
| 2014-15 | 55-27 | WC Semis | Lost to LAC |
| 2015-16 | 67-15 | WC Semis | Lost to OKC |
| 2016-17 | 61-21 | WC Finals | Lost to GSW (Kawhi injury) |
| 2017-18 | 47-35 | 1st Round | Lost to GSW |
| 2018-19 | 48-34 | Missed | — |
| 2019-20 | 22-43 | Missed | COVID season |
| 2020-21 | 33-39 | Play-In | Lost |
| 2021-22 | 34-48 | Missed | — |
| 2022-23 | 22-60 | Missed | Rebuilding with Wembanyama slot |

## The 2013-14 Championship Season

The 2013-14 Spurs were a masterpiece. After losing the 2013 Finals to Miami in heartbreaking fashion (Ray Allen's corner three), Popovich retooled. The team averaged 26 assists per game — a modern NBA record. In the Finals rematch against the Heat, the Spurs played the most beautiful basketball of the decade: 72.6% shooting on ball movement plays, holding Miami to 87 points per game. Tony Parker won Finals MVP.

## Legacy

Popovich's influence extends beyond San Antonio. Hundreds of NBA coaches have studied the Spurs system. His insistence on international players (he was first to build a dynasty around non-American stars: Parker (French), Ginobili (Argentine), Gasol (Spanish)) changed how teams evaluate talent globally. His five championships place him among the most decorated coaches in professional sports history.
""",
    },
    {
        "name": "Steve Kerr",
        "team": "Golden State Warriors",
        "seasons": "2014-2023",
        "slug": "steve_kerr",
        "content": """# Steve Kerr — Head Coach, Golden State Warriors

**Tenure with Warriors:** 2014–present
**Record (2014–2023):** Approx. 480–210 regular season
**Championships:** 2014-15, 2016-17, 2017-18, 2021-22 (4 titles)

## Coaching Philosophy

Steve Kerr inherited a talented Warriors core and turned them into a dynasty by implementing an open, motion offense that maximized Stephen Curry's shooting and Draymond Green's playmaking. His philosophy centers on:

- **Ball and player movement**: "Death lineup" with five shooters keeping the defense in constant rotation
- **Empowerment**: Giving players autonomy; players call their own timeouts and defensive adjustments
- **Three-point revolution**: Warriors led the league in threes attempted and made every season
- **Culture**: Prioritizing joy, trust, and authenticity over fear and rigid structure

Kerr played under Phil Jackson and absorbed the triangle offense and mindfulness approach. He brought a "player-first" mentality that was rare in NBA coaching at the time.

## Notable Seasons (2014–2023)

| Season | W-L | Playoffs | Result |
|--------|-----|----------|--------|
| 2014-15 | 67-15 | Champion | Beat Cleveland 4-2 |
| 2015-16 | 73-9 | Finals | Lost to Cleveland 3-4 (3-1 collapse) |
| 2016-17 | 67-15 | Champion | Beat Cleveland 4-1 (with Durant) |
| 2017-18 | 58-24 | Champion | Beat Cleveland 4-0 |
| 2018-19 | 57-25 | Finals | Lost to Toronto 2-4 |
| 2019-20 | 15-50 | Missed | Durant/Thompson injured |
| 2020-21 | 39-33 | Play-In | Lost |
| 2021-22 | 53-29 | Champion | Beat Boston 4-2 |
| 2022-23 | 44-38 | 2nd Round | Lost to LAL |

## The 73-9 Season (2015-16)

Kerr guided the Warriors to the greatest regular season record in NBA history: 73-9, breaking the 1995-96 Bulls' 72-10. Stephen Curry's unanimous MVP, record-breaking three-point shooting (402 in a season), and a 24-game winning streak made it historically dominant. The collapse in the Finals — blowing a 3-1 lead to LeBron's Cavaliers — remains the biggest upset in Finals history.

## The 2021-22 Comeback

After three years without Klay Thompson (ACL + Achilles injuries), Kerr managed a rebuilding core (Jordan Poole, Andrew Wiggins, young players) while keeping culture intact. When Thompson returned, Kerr blended veterans and youth seamlessly. The 2022 championship validated that the dynasty was built on culture, not just star power.

## Legacy

Kerr became the fastest coach to reach 200, 300, and 400 wins in NBA history. His four championships in eight years put him alongside Phil Jackson, Pat Riley, and Red Auerbach as transformative coaches. His Warriors changed how basketball is played globally: the three-pointer became the primary weapon across all levels of the game.
""",
    },
    {
        "name": "Erik Spoelstra",
        "team": "Miami Heat",
        "seasons": "2013-2023",
        "slug": "erik_spoelstra",
        "content": """# Erik Spoelstra — Head Coach, Miami Heat

**Tenure with Heat:** 2008–present
**Record (2013–2023):** Approx. 490–360 regular season
**Championships:** 2011-12, 2012-13 (pre-2013), 2019-20 (Finals loss), 2022-23 (Finals loss)

## Coaching Philosophy

Erik Spoelstra is one of the most adaptive coaches in NBA history. His approach evolves with his roster — he won with LeBron's athleticism, survived without stars, and built a new identity with Bam Adebayo and Jimmy Butler. Core principles:

- **Defensive intensity**: Heat defense sets the tone every possession
- **Culture over talent**: "Heat Culture" — conditioning, toughness, and accountability — transforms undrafted players into role players
- **Adaptability**: Switched from traditional to small-ball to hybrid schemes over a decade
- **Player empowerment**: Trusts players in high-leverage moments; famous for unconventional lineup decisions

## Notable Seasons (2013–2023)

| Season | W-L | Playoffs | Result |
|--------|-----|----------|--------|
| 2013-14 | 54-28 | EC Finals | Lost to Indiana Pacers |
| 2014-15 | 37-45 | Missed | Post-LeBron rebuilding |
| 2015-16 | 48-34 | 1st Round | Lost to Charlotte |
| 2016-17 | 41-41 | Missed | — |
| 2017-18 | 44-38 | 1st Round | Lost to Philadelphia |
| 2018-19 | 39-43 | Missed | — |
| 2019-20 | 53-19 | Finals | Lost to LAL (bubble) |
| 2020-21 | 40-32 | 1st Round | Lost to Milwaukee |
| 2021-22 | 53-29 | EC Finals | Lost to Boston |
| 2022-23 | 44-38 | Finals | Lost to Denver |

## The 2019-20 Bubble Run

Without a traditional superstar, Spoelstra took a Bam Adebayo + Jimmy Butler + depth roster to the NBA Finals in the Disney bubble. Undrafted players (Duncan Robinson, Kendrick Nunn) became key contributors. Bam's defensive versatility (guarding 1-through-5) and Butler's clutch performances defined "Heat Culture" nationally. The Goran Dragic and Bam Adebayo injuries in the Finals against the Lakers were pivotal.

## The 2022-23 Cinderella Run

As an 8-seed in the first year of the Play-In Tournament, the Heat beat the #1 Milwaukee Bucks in the first round. They eliminated #1 overall seeded Milwaukee, swept Boston, and reached the Finals. Undrafted Duncan Robinson, Caleb Martin, and 6-foot-nothing Kyle Lowry were key contributors. Spoelstra maximized every player — widely considered his best coaching performance.

## Legacy

Spoelstra proved that coaching scheme, culture, and player development can outperform raw talent. His ability to consistently maximize rosters — whether LeBron's super-team or journeymen — makes him one of the most respected coaches of his generation.
""",
    },
    {
        "name": "Doc Rivers",
        "team": "Los Angeles Clippers / Philadelphia 76ers",
        "seasons": "2013-2023",
        "slug": "doc_rivers",
        "content": """# Doc Rivers — Head Coach, Los Angeles Clippers / Philadelphia 76ers

**Tenure:** LAC 2013-2020, PHI 2020-2023
**Championships:** None (2013-2023)

## Coaching Philosophy

Doc Rivers is an experienced communicator and players' coach known for managing superstar personalities. His offense emphasizes isolation for star players, pick-and-roll execution, and transition opportunities. Defensively, he implemented the "Lob City" era attack mentality with the Clippers.

## Notable Seasons (2013–2023)

| Season | Team | W-L | Best Result |
|--------|------|-----|-------------|
| 2013-14 | LAC | 57-25 | WC Semis (lost to OKC) |
| 2014-15 | LAC | 56-26 | WC Semis (lost to HOU) |
| 2015-16 | LAC | 53-29 | 1st Round (lost to Portland) |
| 2016-17 | LAC | 51-31 | 1st Round (lost to Utah) |
| 2017-18 | LAC | 42-40 | Missed |
| 2018-19 | LAC | 48-34 | 1st Round (lost to GSW) |
| 2019-20 | LAC | 49-23 | Bubble Collapse (3-1 up vs DAL, lost) |
| 2020-21 | PHI | 49-23 | 2nd Round (lost to ATL) |
| 2021-22 | PHI | 51-31 | 2nd Round (lost to MIA) |
| 2022-23 | PHI | 54-28 | 2nd Round (lost to BOS) |

## The 2020 Bubble Collapse

Leading Dallas 3-1 in the second round, the Clippers blew the series — the biggest collapse in modern playoff history. Kawhi Leonard and Paul George disappeared in Games 5-7. Rivers was fired after the season, ending a 7-year run with Los Angeles.

## Philadelphia 76ers Era

Rivers led the Process-era 76ers (Embiid, Harden/Simmons) to three straight second-round exits. The Ben Simmons saga — a player refusing to play — was a defining controversy of his tenure. Rivers was fired in 2023 despite a 54-win season.
""",
    },
    {
        "name": "Tyronn Lue",
        "team": "Cleveland Cavaliers / Los Angeles Clippers",
        "seasons": "2016-2023",
        "slug": "tyronn_lue",
        "content": """# Tyronn Lue — Head Coach, Cleveland Cavaliers / Los Angeles Clippers

**Tenure:** CLE 2016-2018, LAC 2020-present
**Championships:** 2015-16 (Cleveland Cavaliers)

## Coaching Philosophy

Tyronn Lue is known for managing LeBron James-level superstars and adapting game-to-game tactically. His style is offense-first, trusting stars in late-game situations. He prefers versatile lineups and is known for in-game adjustments, particularly defending specific opponents.

## The 2016 Championship

Lue took over mid-season from David Blatt when Cleveland was 30-11. His biggest achievement was engineering the greatest comeback in Finals history: down 3-1 to the 73-win Golden State Warriors, the Cavs won three straight. LeBron James, Kyrie Irving, and the "Block + Shot" Game 7 moment defined the season. The city's 52-year championship drought ended.

## Notable Seasons (2016–2023)

| Season | Team | W-L | Result |
|--------|------|-----|--------|
| 2015-16 | CLE | 57-25 | Champion |
| 2016-17 | CLE | 51-31 | Finals (lost to GSW) |
| 2017-18 | CLE | 50-32 | Finals (lost to GSW) |
| 2020-21 | LAC | 47-25 | Semis (lost to Suns) |
| 2021-22 | LAC | 42-40 | 1st Round |
| 2022-23 | LAC | 44-38 | 2nd Round |

## Legacy

Lue's 2016 championship is remembered as one of the most dramatic coaching achievements in NBA history — rallying a team from 3-1 down against a record-breaking opponent. His ability to keep LeBron confident and focused under pressure defined his Cleveland tenure.
""",
    },
    {
        "name": "Mike Budenholzer",
        "team": "Atlanta Hawks / Milwaukee Bucks",
        "seasons": "2013-2023",
        "slug": "mike_budenholzer",
        "content": """# Mike Budenholzer — Head Coach, Atlanta Hawks / Milwaukee Bucks

**Tenure:** ATL 2013-2018, MIL 2018-2023
**Championships:** 2020-21 (Milwaukee Bucks)

## Coaching Philosophy

Mike Budenholzer is a disciple of Gregg Popovich (he spent 17 years under Pop in San Antonio). He implements motion offense, heavy three-point shooting, and transition defense. His system transformed Giannis Antetokounmpo from a raw athlete into an MVP.

Key elements:
- **Three-point volume**: Bucks consistently in top-5 for threes attempted
- **Drop coverage**: Controversial but effective scheme for protecting the paint with Giannis
- **Spacing + cutting**: Open floor for Giannis's drives and Khris Middleton's mid-range

## The 2020-21 Championship

Budenholzer led the Bucks to their first NBA title since 1971, defeating the Phoenix Suns 4-2. This came after Giannis's historic 50-point Game 6 performance and overcoming a 2-0 deficit to Brooklyn in the second round (Harden injured). The Bucks' defense — allowing under 100 points per game — was the backbone of the run.

## Notable Seasons (2013–2023)

| Season | Team | W-L | Result |
|--------|------|-----|--------|
| 2013-14 | ATL | 38-44 | 1st Round |
| 2014-15 | ATL | 60-22 | EC Finals (lost to Cleveland) |
| 2015-16 | ATL | 48-34 | 1st Round |
| 2016-17 | ATL | 43-39 | 1st Round |
| 2017-18 | ATL | 24-58 | Missed |
| 2018-19 | MIL | 60-22 | EC Finals (lost to Toronto) |
| 2019-20 | MIL | 56-17 | 2nd Round (lost to Miami, bubble) |
| 2020-21 | MIL | 46-26 | Champion |
| 2021-22 | MIL | 51-31 | 2nd Round (lost to Boston) |
| 2022-23 | MIL | 58-24 | 1st Round (lost to Miami, 1-seed upset) |

## Legacy

Budenholzer's 2014-15 Atlanta Hawks were one of the most aesthetically pleasing teams in recent memory — four players averaging double digits, no true superstar, pure ball movement. In Milwaukee, he maximized Giannis into a two-time MVP and champion.
""",
    },
    {
        "name": "Nick Nurse",
        "team": "Toronto Raptors",
        "seasons": "2018-2023",
        "slug": "nick_nurse",
        "content": """# Nick Nurse — Head Coach, Toronto Raptors

**Tenure with Raptors:** 2018-2023
**Championships:** 2018-19 (Toronto Raptors — Canada's first NBA title)

## Coaching Philosophy

Nick Nurse is one of the most innovative defensive coaches in the modern NBA. He implemented:

- **Junk defenses**: Box-and-one on Stephen Curry (2019 Finals), diamond-and-one on Giannis (2019 Playoffs)
- **Positionless basketball**: Five-out lineups, interchangeable defenders
- **Challenge culture**: One of the highest rates of successful coach's challenges in the league
- **Pace manipulation**: Mixing fast breaks with late-shot-clock efficiency

## The 2019 Championship

Nurse guided a roster led by Finals MVP Kawhi Leonard and Pascal Siakam to the franchise's first title. Kawhi's buzzer-beater in Game 7 vs Philadelphia (the "bounce four times" shot) and his 30+ point performances against Golden State — who lost Durant and Klay Thompson to injuries — defined the run. The "box-and-one" on Curry in the Finals became legendary.

## Notable Seasons (2018–2023)

| Season | W-L | Result |
|--------|-----|--------|
| 2018-19 | 58-24 | Champion |
| 2019-20 | 53-19 | 2nd Round (lost to Boston, bubble) |
| 2020-21 | 27-45 | Missed |
| 2021-22 | 48-34 | 1st Round (lost to Philadelphia) |
| 2022-23 | 41-41 | Play-In exit |

## Legacy

Nurse won Coach of the Year in 2019-20 (bubble season with no Kawhi, went 53-19). His willingness to use unconventional tactics — including switching all five defenders on every screen — influenced defensive schemes league-wide. He was fired after 2023 and went on to coach the Philadelphia 76ers.
""",
    },
    {
        "name": "Frank Vogel",
        "team": "Indiana Pacers / Los Angeles Lakers",
        "seasons": "2013-2022",
        "slug": "frank_vogel",
        "content": """# Frank Vogel — Head Coach, Indiana Pacers / Los Angeles Lakers

**Tenure:** IND 2013-2016, LAL 2019-2022
**Championships:** 2019-20 (Los Angeles Lakers)

## Coaching Philosophy

Frank Vogel is fundamentally a defensive coach. His Indiana Pacers teams were the best defensive units of the 2013-2014 era, regularly holding opponents below 95 points when league average was 101. His defensive philosophy:

- **Pack the paint**: Force mid-range shots rather than threes or layups
- **Help defense**: Heavy rotation, disciplined help assignments
- **Defensive identity first**: Offense follows from getting stops

## The 2019-20 Championship

Vogel won the Lakers' first title since 2010 in the Disney bubble. LeBron James won Finals MVP, but the defensive identity Vogel installed (Anthony Davis as the anchor, Alex Caruso, Danny Green as perimeter defenders) was decisive. The Bubble championship required 6 weeks of isolation, unusual conditions Vogel navigated effectively.

## Pacers Era (2013-2016)

The 2013-14 Pacers were arguably the best defensive team in the league — Paul George, Roy Hibbert, Lance Stephenson, and David West created a system that nearly beat LeBron's Heat twice. Back-to-back Eastern Conference Finals appearances established Vogel as an elite defensive strategist.

## Legacy

Vogel's reputation as a defensive architect is secure. His Lakers championship validated that defense-first coaching works in the modern era — even when the league tilted heavily toward offensive schemes.
""",
    },
]


def write_coach_file(coach: dict):
    path = COACHES_DIR / f"{coach['slug']}.md"
    path.write_text(coach["content"].strip(), encoding="utf-8")
    print(f"  Written: {path.name}")


def main():
    print(f"Writing {len(COACHES)} coach files to {COACHES_DIR}/")
    for coach in COACHES:
        write_coach_file(coach)
    print("Done.")


if __name__ == "__main__":
    main()
