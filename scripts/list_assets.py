"""List the nflverse release assets we mirror. Prints JSON to stdout.

The output doubles as the GitHub Actions cache key: if nothing upstream
changed, the hash of this file is identical and the cached site/ is reused.
"""
from __future__ import annotations

import json
import re
import sys

import requests

from common import NFLVERSE_REPO, WANTED, gh_headers


def list_release_assets(tag: str) -> list[dict]:
    s = requests.Session()
    s.headers.update(gh_headers())
    rel = s.get(f"https://api.github.com/repos/{NFLVERSE_REPO}/releases/tags/{tag}", timeout=60)
    rel.raise_for_status()
    rid = rel.json()["id"]
    out, page = [], 1
    while True:
        r = s.get(
            f"https://api.github.com/repos/{NFLVERSE_REPO}/releases/{rid}/assets",
            params={"per_page": 100, "page": page},
            timeout=60,
        )
        r.raise_for_status()
        batch = r.json()
        out.extend(batch)
        if len(batch) < 100:
            return out
        page += 1


def main() -> int:
    wanted = []
    for tag, rules in WANTED.items():
        for a in list_release_assets(tag):
            for pattern, dest in rules:
                m = re.match(pattern, a["name"])
                if m:
                    wanted.append({
                        "tag": tag,
                        "name": a["name"],
                        "dest": dest.format(*m.groups()),
                        "size": a["size"],
                        "updated_at": a["updated_at"],
                        "url": a["browser_download_url"],
                    })
    wanted.sort(key=lambda x: x["dest"])
    json.dump(wanted, sys.stdout, indent=1)
    sys.stdout.write("\n")
    print(f"{len(wanted)} assets", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
