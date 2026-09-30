"""Copy team logos + wordmarks next to the data so the app serves them
same-origin (cross-origin images would taint the canvas on PNG export)."""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import requests

from common import CURRENT_TEAMS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    teams = a.dest / "teams" / "teams_colors_logos.parquet"
    rows = duckdb.execute(
        f"SELECT team_abbr, team_logo_espn, team_wordmark FROM read_parquet('{teams}')"
    ).fetchall()
    out = a.dest / "logos"
    out.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    n = 0
    for abbr, logo, wordmark in rows:
        if abbr not in CURRENT_TEAMS:
            continue
        for url, path in ((logo, out / f"{abbr}.png"), (wordmark, out / f"wordmark_{abbr}.png")):
            if not url or (path.exists() and not a.force):
                continue
            r = s.get(url, timeout=60)
            r.raise_for_status()
            path.write_bytes(r.content)
            n += 1
    print(f"logos: fetched {n}, total {len(list(out.glob('*.png')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
