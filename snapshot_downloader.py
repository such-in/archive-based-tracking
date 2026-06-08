"""
snapshot_downloader.py  (Stage 1 of 4)
--------------------------------------
For every website in input.csv, query the Internet Archive's CDX API to get
the *index* of all available snapshots (one row per capture: timestamp,
original URL, mimetype, HTTP status, digest, ...).

This does NOT download the page content yet -- it only records WHICH snapshots
exist. Stage 2 (archive_downloader.py) uses these records to decide what to
actually fetch, based on the year / snapshots_per_year settings in config.yaml.

Output: data/cdx/<COUNTRY>/<website_with_underscores>.json

Usage:
    python snapshot_downloader.py
    # optional parallelism across N machines (run one per machine):
    python snapshot_downloader.py --machine 0 --num-machines 3
"""

import argparse
import json
import os
import time

import requests

from common import load_config, read_input_csv, safe_name, ensure_dir

# CDX = "Capture inDeX". This endpoint returns the list of archived captures.
CDX_API = "https://web.archive.org/cdx/search/cdx"
HEADERS = {"User-Agent": "archive-based-tracking/1.0 (research; contact: you@example.org)"}


def fetch_cdx_records(website, out_path, delay):
    """Fetch and save the CDX records for a single website (skip if cached)."""
    if os.path.exists(out_path):
        print(f"  [skip] already have {out_path}")
        return

    params = {"url": website, "output": "json"}
    try:
        resp = requests.get(CDX_API, params=params, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        data = resp.json()  # first row is a header: [urlkey, timestamp, original, ...]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        n = max(len(data) - 1, 0)  # minus header row
        print(f"  [ok]   {website}: {n} snapshot records")
    except Exception as e:
        # Log failures rather than crashing the whole run.
        print(f"  [fail] {website}: {e}")
        fail_dir = ensure_dir(os.path.join("data", "failures"))
        with open(os.path.join(fail_dir, "cdx_failures.tsv"), "a", encoding="utf-8") as f:
            f.write(f"{website}\t{e}\n")
    finally:
        # Be polite to the free public archive.
        time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description="Download Wayback CDX snapshot records.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--machine", type=int, default=0,
                        help="This machine's index (0-based) when sharding work.")
    parser.add_argument("--num-machines", type=int, default=1,
                        help="Total number of machines sharing the work.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    rows = read_input_csv(cfg["paths"]["input_csv"])
    cdx_dir = cfg["paths"]["cdx_dir"]
    delay = cfg.get("request_delay", 3)

    # Optionally split the work across machines: machine i handles every
    # num_machines-th website. With defaults (0 of 1) it does everything.
    rows = [r for i, r in enumerate(rows) if i % args.num_machines == args.machine]
    print(f"Machine {args.machine}/{args.num_machines} -> {len(rows)} websites")

    for idx, (country, website) in enumerate(rows, start=1):
        country_dir = ensure_dir(os.path.join(cdx_dir, country))
        out_path = os.path.join(country_dir, f"{safe_name(website)}.json")
        print(f"[{idx}/{len(rows)}] {country} :: {website}")
        fetch_cdx_records(website, out_path, delay)

    print("Stage 1 complete.")


if __name__ == "__main__":
    main()
