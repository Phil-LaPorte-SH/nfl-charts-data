"""Incrementally mirror nflverse parquet into site/ and build derived files.

Skips any file whose upstream size + updated_at match what we downloaded last
time (tracked in site/.state.json, which rides along in the Actions cache).

  python sync.py --dest site --assets assets.json                   # everything, incremental
  python sync.py --dest ../nfl-charts/public/data --seasons 2023,2025  # dev subset
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import requests

from build_pbp_lite import build as build_lite
from common import TEAM_ALIASES, load_json, season_of


def parse_seasons(s: str) -> set[int] | None:
    if s in ("auto", "all", "", None):
        return None
    out: set[int] = set()
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.replace(dest)


def write_aliases(dest: Path) -> None:
    out = dest / "teams" / "team_aliases.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = ", ".join(f"('{k}', '{v}')" for k, v in TEAM_ALIASES.items())
    duckdb.execute(
        f"COPY (SELECT * FROM (VALUES {rows}) t(alias, team_abbr)) TO '{out}' (FORMAT PARQUET)"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--assets", type=Path, required=True)
    ap.add_argument("--seasons", default="auto", help="auto | all | 2023,2025 | 2018-2026")
    ap.add_argument("--no-lite", action="store_true")
    ap.add_argument("--rebuild-lite", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    assets = json.loads(a.assets.read_text())
    seasons = parse_seasons(a.seasons)
    state_path = a.dest / ".state.json"
    state = load_json(state_path, {})
    a.dest.mkdir(parents=True, exist_ok=True)

    changed_pbp: list[Path] = []
    n_dl = n_skip = 0
    for x in assets:
        s = season_of(x["dest"]) if x["tag"] in ("pbp", "stats_player", "stats_team") else None
        if seasons is not None and s is not None and s not in seasons:
            continue
        path = a.dest / x["dest"]
        prev = state.get(x["dest"])
        fresh = prev and prev["size"] == x["size"] and prev["updated_at"] == x["updated_at"]
        if fresh and path.exists() and not a.force:
            n_skip += 1
            continue
        print(f"get  {x['dest']} ({x['size']/1e6:.1f} MB)", flush=True)
        download(x["url"], path)
        state[x["dest"]] = {"size": x["size"], "updated_at": x["updated_at"]}
        state_path.write_text(json.dumps(state, indent=1, sort_keys=True))
        n_dl += 1
        if x["tag"] == "pbp":
            changed_pbp.append(path)
    print(f"downloaded {n_dl}, unchanged {n_skip}")

    if not a.no_lite:
        con = duckdb.connect()
        raws = sorted((a.dest / "pbp").glob("play_by_play_*.parquet"))
        for raw in raws:
            s = season_of(str(raw))
            if seasons is not None and s not in seasons:
                continue
            lite = a.dest / "pbp_lite" / f"season={s}" / "pbp_lite.parquet"
            if a.rebuild_lite or raw in changed_pbp or not lite.exists():
                p = build_lite(raw, a.dest / "pbp_lite", con)
                print(f"lite {p.relative_to(a.dest)} {p.stat().st_size/1e6:.1f} MB", flush=True)

    write_aliases(a.dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
