# nfl-charts-data

A GitHub Pages mirror of [nflverse](https://github.com/nflverse/nflverse-data) parquet files for the
[nfl-charts](https://github.com/Phil-LaPorte-SH/nfl-charts) app.

nflverse publishes its data as GitHub Release assets. Those downloads support HTTP range requests but send no
CORS headers, so a browser cannot read them. GitHub Pages does send CORS and range headers, so this repo's
workflow copies the files here, and the app's in-browser DuckDB reads only the byte ranges each query needs.

## What gets published

| Path | Contents |
|---|---|
| `manifest.json` | File list, sizes, cache keys, column schemas, season coverage |
| `pbp/play_by_play_{season}.parquet` | Raw nflverse play-by-play, 1999 to present, untouched |
| `pbp_lite/season={season}/pbp_lite.parquet` | 168 curated pbp columns, uniform types, canonical team columns |
| `stats_player/`, `stats_team/` | nflverse weekly and season (`reg`, `post`, `regpost`) summary stats |
| `teams/`, `players/`, `schedules/` | Team colors and logo URLs, player IDs, schedule and scores |
| `logos/{TEAM}.png` | Team logos and wordmarks, served same-origin so PNG export works |

## Schedule

`refresh-data` runs Tuesday and Thursday in season, monthly off-season, and on manual dispatch. It only
re-downloads files whose upstream size or timestamp changed; the previous site is restored from the Actions cache.

## Local use

```bash
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
cd scripts
../.venv/bin/python list_assets.py > ../assets.json
../.venv/bin/python sync.py --dest ../site --assets ../assets.json            # everything (~640 MB)
../.venv/bin/python sync.py --dest ../site --assets ../assets.json --seasons 2024,2025   # a subset
../.venv/bin/python fetch_logos.py --dest ../site
../.venv/bin/python build_manifest.py --dest ../site
../.venv/bin/python smoke.py http://127.0.0.1:8765   # after: npx http-server ../site -p 8765 --cors
```

## Attribution

Data from nflverse, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This mirror adds the
`pbp_lite` column subset, canonical team columns, and a manifest; the raw files are unmodified. nflverse is a
community project and is not affiliated with the NFL.
