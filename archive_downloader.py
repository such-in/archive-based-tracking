"""
archive_downloader.py  (Stage 2 of 4)
-------------------------------------
Reads the CDX records produced by Stage 1, then for each website:

  * keeps only snapshots inside the configured [years.start, years.end] range,
  * (optionally) keeps only captures that returned HTTP 200,
  * groups the remaining snapshots BY YEAR,
  * selects `snapshots_per_year` captures from each year:
        - the FIRST capture of the year is always taken,
        - remaining slots are filled with RANDOM captures from that year,
  * downloads the actual archived HTML for each selected snapshot.

Output: data/snapshots/<COUNTRY>/<website_with_underscores>/<timestamp>.html

Usage:
    python archive_downloader.py
"""

import json
import os
import random
import time
from collections import defaultdict

import requests

from common import load_config, read_input_csv, safe_name, ensure_dir

HEADERS = {"User-Agent": "archive-based-tracking/1.0 (research; contact: you@example.org)"}


def parse_cdx(cdx_path):
    """
    Load a CDX JSON file into a list of dict rows.
    The first row of the file is a header naming the columns.
    """
    with open(cdx_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data or len(data) < 2:
        return []
    header, *records = data
    return [dict(zip(header, rec)) for rec in records]


def select_snapshots(records, year, per_year, only_200, rng):
    """
    From all `records`, pick the snapshots to download for a single `year`.
    Returns a list of CDX rows (each has at least 'timestamp' and 'original').
    """
    in_year = []
    for r in records:
        ts = r.get("timestamp", "")
        if len(ts) < 4 or ts[:4] != str(year):
            continue
        if only_200 and r.get("statuscode") != "200":
            continue
        in_year.append(r)

    if not in_year:
        return []

    # Sort chronologically so the first element is the earliest capture.
    in_year.sort(key=lambda r: r["timestamp"])
    selected = [in_year[0]]            # always take the first of the year
    remaining = in_year[1:]
    extra = per_year - 1               # how many more random ones we want
    if extra > 0 and remaining:
        rng.shuffle(remaining)
        selected.extend(remaining[:extra])
    return selected


def download_snapshot(record, out_path, delay):
    """Download one archived HTML page (skip if already on disk)."""
    if os.path.exists(out_path):
        print(f"    [skip] {os.path.basename(out_path)}")
        return

    ts = record["timestamp"]
    original = record["original"]
    # The plain (rewritten) snapshot URL. The Wayback prefix on embedded URLs
    # is cleaned later in identify_tracker.py via common.clean_wayback_url().
    url = f"https://web.archive.org/web/{ts}/{original}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        with open(out_path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(resp.text)
        print(f"    [ok]   {ts}")
    except Exception as e:
        print(f"    [fail] {ts}: {e}")
        fail_dir = ensure_dir(os.path.join("data", "failures"))
        with open(os.path.join(fail_dir, "archive_failures.tsv"), "a", encoding="utf-8") as f:
            f.write(f"{url}\t{e}\n")
    finally:
        time.sleep(delay)


def main():
    cfg = load_config()
    rows = read_input_csv(cfg["paths"]["input_csv"])
    cdx_dir = cfg["paths"]["cdx_dir"]
    snap_dir = cfg["paths"]["snapshots_dir"]

    year_start = cfg["years"]["start"]
    year_end = cfg["years"]["end"]
    per_year = cfg.get("snapshots_per_year", 2)
    only_200 = cfg.get("only_status_200", True)
    delay = cfg.get("request_delay", 3)
    rng = random.Random(cfg.get("random_seed", 42))

    for idx, (country, website) in enumerate(rows, start=1):
        cdx_path = os.path.join(cdx_dir, country, f"{safe_name(website)}.json")
        if not os.path.exists(cdx_path):
            print(f"[{idx}/{len(rows)}] {website}: no CDX file, run snapshot_downloader.py first")
            continue

        records = parse_cdx(cdx_path)
        print(f"[{idx}/{len(rows)}] {country} :: {website} ({len(records)} total captures)")

        out_base = ensure_dir(os.path.join(snap_dir, country, safe_name(website)))
        for year in range(year_start, year_end + 1):
            picks = select_snapshots(records, year, per_year, only_200, rng)
            for rec in picks:
                out_path = os.path.join(out_base, f"{rec['timestamp']}.html")
                download_snapshot(rec, out_path, delay)

    print("Stage 2 complete.")


if __name__ == "__main__":
    main()
