"""Post-deploy smoke test against the live Pages site (or a local http server).

  python smoke.py https://phil-laporte-sh.github.io/nfl-charts-data
"""
from __future__ import annotations

import sys

import duckdb
import requests

MAHOMES = "00-0033873"


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}, want {want!r}")
    return ok


def main() -> int:
    base = sys.argv[1].rstrip("/")
    ok = True
    m = requests.get(f"{base}/manifest.json", timeout=30)
    m.raise_for_status()
    man = m.json()
    ok &= check("manifest has pbp_lite", "pbp_lite" in man["datasets"], True)

    url = f"{base}/pbp/play_by_play_2022.parquet"
    # Browsers send Accept-Encoding: identity on any request with a Range
    # header (Fetch standard). GitHub Pages gzips octet-stream otherwise, and
    # ranges then index into the gzip stream, so test the browser behaviour.
    r = requests.get(url, headers={"Range": "bytes=0-3", "Accept-Encoding": "identity"}, timeout=30)
    ok &= check("range request status", r.status_code, 206)
    ok &= check("parquet magic", r.content, b"PAR1")
    ok &= check("accept-ranges", r.headers.get("accept-ranges"), "bytes")
    if base.startswith("https://"):
        ok &= check("cors", r.headers.get("access-control-allow-origin"), "*")

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    q = lambda sql: con.execute(sql).fetchone()
    got = q(f"""SELECT sum(passing_yards)::INT, sum(passing_tds)::INT, sum(attempts)::INT, sum(completions)::INT
                FROM read_parquet('{base}/stats_player/stats_player_week_2022.parquet')
                WHERE player_id = '{MAHOMES}' AND season_type = 'REG'""")
    ok &= check("Mahomes 2022 (player_week)", got, (5250, 41, 648, 435))
    got = q(f"""SELECT sum(passing_yards)::INT FROM read_parquet('{base}/pbp/play_by_play_2022.parquet')
                WHERE season_type = 'REG' AND passer_player_id = '{MAHOMES}'""")
    ok &= check("Mahomes 2022 (pbp)", got, (5250,))
    got = q(f"""SELECT sum(passing_yards)::INT FROM read_parquet('{base}/pbp_lite/season=2022/pbp_lite.parquet')
                WHERE season_type = 'REG' AND passer_player_id = '{MAHOMES}'""")
    ok &= check("Mahomes 2022 (pbp_lite)", got, (5250,))
    got = q(f"SELECT count(*) FROM read_parquet('{base}/teams/teams_colors_logos.parquet')")
    ok &= check("teams rows (32 + 4 historical)", got, (36,))
    r = requests.head(f"{base}/logos/KC.png", timeout=30)
    ok &= check("KC logo", r.status_code, 200)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
