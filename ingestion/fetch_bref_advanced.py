"""
Fetch advanced stats from Basketball-Reference for all seasons 2013-14 to 2022-23.
Saves CSV files under data/bref_advanced/

Advanced stats include: PER, TS%, 3PAr, FTr, ORB%, DRB%, TRB%, AST%,
STL%, BLK%, TOV%, USG%, OWS, DWS, WS, WS/48, OBPM, DBPM, BPM, VORP

These are NOT in our current NBA API data and significantly improve
the win probability model and player comparisons.

Run: python -m ingestion.fetch_bref_advanced

NOTE: Basketball-Reference throttles at ~20 req/min. Script sleeps accordingly.
"""
import os, time
import pandas as pd
from pathlib import Path

OUT_DIR = Path("data/bref_advanced")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEASONS = {
    "2013-14": 2014,
    "2014-15": 2015,
    "2015-16": 2016,
    "2016-17": 2017,
    "2017-18": 2018,
    "2018-19": 2019,
    "2019-20": 2020,
    "2020-21": 2021,
    "2021-22": 2022,
    "2022-23": 2023,
}


def fetch_season(season_label: str, year: int) -> pd.DataFrame | None:
    import requests
    from io import StringIO
    url = f"https://www.basketball-reference.com/leagues/NBA_{year}_advanced.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text), header=0)
        # The advanced stats table is the first one
        df = tables[0]
        # Drop repeated header rows (bref inserts them every 20 rows)
        df = df[df["Player"] != "Player"].copy()
        # Drop rows with no player name
        df = df[df["Player"].notna() & (df["Player"] != "")].copy()
        # Add season label
        df["season"] = season_label
        # Keep only useful columns (drop bref-specific rank col)
        drop_cols = [c for c in df.columns if "Unnamed" in str(c) or c == "Rk"]
        df.drop(columns=drop_cols, inplace=True, errors="ignore")
        # Convert numeric cols
        skip = {"Player", "Pos", "Tm", "season"}
        for col in df.columns:
            if col not in skip:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception as e:
        print(f"  ERROR {season_label}: {e}")
        return None


if __name__ == "__main__":
    all_dfs = []
    for label, year in SEASONS.items():
        out_path = OUT_DIR / f"{label}.csv"
        if out_path.exists():
            print(f"  skip {label} (exists)")
            df = pd.read_csv(out_path)
            all_dfs.append(df)
            continue

        print(f"Fetching {label} (year={year})...")
        df = fetch_season(label, year)
        if df is not None:
            df.to_csv(out_path, index=False)
            print(f"  -> {len(df)} rows, cols: {list(df.columns[:8])}...")
            all_dfs.append(df)
        else:
            print(f"  -> FAILED")

        time.sleep(4)   # respect rate limit: ~15 req/min max

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined.to_csv(OUT_DIR / "all_seasons.csv", index=False)
        print(f"\nCombined: {len(combined)} rows across {len(all_dfs)} seasons")
        print(f"Columns: {list(combined.columns)}")
    else:
        print("No data fetched.")
