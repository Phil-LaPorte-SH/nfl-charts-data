"""Write site/manifest.json: the contract between the pipeline and the app.

It lists every file per dataset (with size + short sha256 used as a browser
cache key), each dataset's column schema, and the season/week coverage.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import duckdb

from common import TEAM_ALIASES, season_of

SCHEMA_VERSION = 1

# dataset name -> (glob relative to site root, load mode)
# "buffer" = app downloads the whole file once and caches it (small tables)
# "http"   = app reads byte ranges on demand (big play-by-play files)
DATASETS = {
    "pbp": ("pbp/play_by_play_*.parquet", "http"),
    "pbp_lite": ("pbp_lite/season=*/pbp_lite.parquet", "http"),
    "player_week": ("stats_player/stats_player_week_*.parquet", "buffer"),
    "player_reg": ("stats_player/stats_player_reg_*.parquet", "buffer"),
    "player_post": ("stats_player/stats_player_post_*.parquet", "buffer"),
    "player_regpost": ("stats_player/stats_player_regpost_*.parquet", "buffer"),
    "team_week": ("stats_team/stats_team_week_*.parquet", "buffer"),
    "team_reg": ("stats_team/stats_team_reg_*.parquet", "buffer"),
    "team_post": ("stats_team/stats_team_post_*.parquet", "buffer"),
    "team_regpost": ("stats_team/stats_team_regpost_*.parquet", "buffer"),
    "teams": ("teams/teams_colors_logos.parquet", "buffer"),
    "team_aliases": ("teams/team_aliases.parquet", "buffer"),
    "players": ("players/players.parquet", "buffer"),
    "games": ("schedules/games.parquet", "buffer"),
}


def sha12(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True)
    a = ap.parse_args()
    root = a.dest
    con = duckdb.connect()
    state = json.loads((root / ".state.json").read_text()) if (root / ".state.json").exists() else {}

    datasets = {}
    for name, (pattern, load) in DATASETS.items():
        files = sorted(root.glob(pattern), key=lambda p: (season_of(str(p)) or 0, str(p)))
        if not files:
            continue
        entries, schemas = [], set()
        for f in files:
            rel = f.relative_to(root).as_posix()
            e = {"path": rel, "bytes": f.stat().st_size, "v": sha12(f)}
            if "_" in name or name.startswith("pbp"):
                s = season_of(rel)
                if s:
                    e["season"] = s
            if rel in state:
                e["source_updated_at"] = state[rel]["updated_at"]
            entries.append(e)
            schemas.add(tuple(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{f}')").fetchall()))
        newest = files[-1]
        cols = [{"name": r[0], "type": r[1]} for r in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{newest}')").fetchall()]
        d = {"load": load, "files": entries, "columns": cols, "schema_uniform": len(schemas) == 1}
        if name == "pbp_lite":
            d["hive"] = True
            d["columns"] = [{"name": "season", "type": "INTEGER"}] + cols
        datasets[name] = d

    games = root / "schedules" / "games.parquet"
    cur, week = con.execute(f"""
        WITH g AS (SELECT * FROM read_parquet('{games}'))
        SELECT max(season), max(week) FILTER (WHERE result IS NOT NULL AND season = (SELECT max(season) FROM g))
        FROM g WHERE result IS NOT NULL
    """).fetchone()
    pbp_seasons = [e["season"] for e in datasets.get("pbp", {}).get("files", [])]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "nflverse (github.com/nflverse/nflverse-data), CC BY 4.0",
        "seasons": {
            "min": min(pbp_seasons) if pbp_seasons else None,
            "max": max(pbp_seasons) if pbp_seasons else None,
            "list": pbp_seasons,
            "current": cur,
            "last_completed_week": week,
        },
        "team_aliases": TEAM_ALIASES,
        "logos": {"pattern": "logos/{team}.png", "wordmark_pattern": "logos/wordmark_{team}.png"},
        "datasets": datasets,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1))
    total = sum(e["bytes"] for d in datasets.values() for e in d["files"])
    print(f"manifest: {len(datasets)} datasets, {total/1e6:.0f} MB, seasons {manifest['seasons']['min']}-{manifest['seasons']['max']}, current {cur} wk {week}")
    for n, d in datasets.items():
        if not d["schema_uniform"]:
            print(f"  note: {n} schema varies across files (app uses union_by_name)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
