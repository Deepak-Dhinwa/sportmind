"""Shared helpers for all ingestion scripts."""
import time
import json
from pathlib import Path

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

SEASONS = [
    "2013-14", "2014-15", "2015-16", "2016-17", "2017-18",
    "2018-19", "2019-20", "2020-21", "2021-22", "2022-23",
]

SLEEP = 0.65  # seconds between requests — stays under nba_api rate limit


def request_with_retry(fn, retries=3, label="request"):
    """Call fn(), retrying up to `retries` times with exponential backoff."""
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                print(f"  [FAIL] {label}: {e}")
                raise
            wait = (attempt + 1) * 3
            print(f"  [retry {attempt + 1}/{retries}] {label} — waiting {wait}s: {e}")
            time.sleep(wait)


def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
