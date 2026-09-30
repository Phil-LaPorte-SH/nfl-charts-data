"""Build pbp_lite/season=YYYY/pbp_lite.parquet from a raw nflverse pbp file.

- Keeps the curated columns in pbp_lite_columns.txt (missing ones become NULL,
  so every season has an identical schema even when nflverse adds columns).
- Adds canonical team columns (posteam_canon, defteam_canon, home_team_canon,
  away_team_canon, penalty_team_canon) so historical abbreviations (STL, SD,
  OAK) line up with current franchises and logos.
- Drops `season` (it comes from the hive path) and sorts by game/play.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from common import SCRIPTS_DIR, canon_team_sql, season_of

TYPES_FALLBACK = "VARCHAR"


def lite_columns() -> list[str]:
    out = []
    for line in (SCRIPTS_DIR / "pbp_lite_columns.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def describe(con, path: Path) -> dict[str, str]:
    return {r[0]: r[1] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()}


def reference_types(raw: Path, con) -> dict[str, str]:
    """Column types from the newest raw pbp file next to `raw`.

    nflverse types drift a little across seasons (goal_to_go is INTEGER in
    some years, DOUBLE in others). Casting every season to the newest file's
    types keeps pbp_lite's schema identical across all partitions.
    """
    newest = max(raw.parent.glob("play_by_play_*.parquet"), key=lambda p: season_of(str(p)) or 0)
    return describe(con, newest)


def build(raw: Path, dest_root: Path, con: duckdb.DuckDBPyConnection | None = None) -> Path:
    con = con or duckdb.connect()
    season = season_of(str(raw))
    have = describe(con, raw)
    ref = reference_types(raw, con)
    select = []
    for c in lite_columns():
        q = f'"{c}"'
        typ = ref.get(c) or have.get(c) or TYPES_FALLBACK
        src = q if c in have else "NULL"
        select.append(f"CAST({src} AS {typ}) AS {q}")
    for c in ("posteam", "defteam", "home_team", "away_team", "penalty_team"):
        select.append(f"{canon_team_sql(c)} AS {c}_canon")
    out = dest_root / f"season={season}" / "pbp_lite.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    con.execute(
        f"""COPY (SELECT {", ".join(select)} FROM read_parquet('{raw}') ORDER BY game_id, play_id)
            TO '{tmp}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)"""
    )
    tmp.replace(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="+", type=Path)
    ap.add_argument("--dest", type=Path, required=True, help="pbp_lite root dir")
    a = ap.parse_args()
    con = duckdb.connect()
    for r in a.raw:
        p = build(r, a.dest, con)
        print(f"lite {p} {p.stat().st_size/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
