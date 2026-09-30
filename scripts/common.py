"""Shared config for the nfl-charts-data pipeline."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

NFLVERSE_REPO = "nflverse/nflverse-data"
FIRST_SEASON = 1999

# Release tag -> list of (regex on asset name, destination path template).
# Destination paths are relative to the site root and are what the app reads.
WANTED: dict[str, list[tuple[str, str]]] = {
    "pbp": [(r"^play_by_play_(\d{4})\.parquet$", "pbp/play_by_play_{0}.parquet")],
    "stats_player": [
        (r"^stats_player_(week|reg|post|regpost)_(\d{4})\.parquet$", "stats_player/stats_player_{0}_{1}.parquet"),
    ],
    "stats_team": [
        (r"^stats_team_(week|reg|post|regpost)_(\d{4})\.parquet$", "stats_team/stats_team_{0}_{1}.parquet"),
    ],
    "teams": [(r"^teams_colors_logos\.parquet$", "teams/teams_colors_logos.parquet")],
    "players": [(r"^players\.parquet$", "players/players.parquet")],
    "schedules": [(r"^games\.parquet$", "schedules/games.parquet")],
}

# Historical / alternate abbreviations -> current franchise abbreviation.
# Mirrored in the app (src/db/teams.js). Keep the two in sync.
TEAM_ALIASES: dict[str, str] = {
    "STL": "LA", "SL": "LA", "LAR": "LA",
    "SD": "LAC",
    "OAK": "LV",
    "JAC": "JAX",
    "WSH": "WAS",
    "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU",
}

CURRENT_TEAMS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET",
    "GB", "HOU", "IND", "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO",
    "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
]

SCRIPTS_DIR = Path(__file__).resolve().parent


def season_of(path: str) -> int | None:
    m = re.search(r"(\d{4})", Path(path).name)
    return int(m.group(1)) if m else None


def canon_team_sql(expr: str) -> str:
    """SQL CASE expression mapping an abbreviation to the current franchise."""
    whens = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in TEAM_ALIASES.items())
    return f"(CASE {expr} {whens} ELSE {expr} END)"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def gh_headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "nfl-charts-data"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h
