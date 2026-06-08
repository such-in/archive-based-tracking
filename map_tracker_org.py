"""
map_tracker_org.py  (Stage 4 of 4)
----------------------------------
Maps the tracker domains found in Stage 3 to their parent ORGANIZATIONS using
DuckDuckGo's Tracker Radar dataset (the `entities/*.json` files, cloned by
setup.sh). Multiple domains owned by one company (e.g. google-analytics.com,
doubleclick.net, googletagmanager.com -> Google) get grouped together, which
is what lets you measure ownership concentration.

Reads:  results/tracker_domains.csv   (from Stage 3)
Writes: results/tracker_org_mapping.csv  (domain -> org, with embed counts)
        results/org_totals.csv           (org -> total embeds, ranked)

Usage:
    python map_tracker_org.py
"""

import csv
import json
import os
from collections import defaultdict

from common import load_config, ensure_dir


def build_domain_to_org(entities_dir):
    """
    Build a {domain: organization} map from the Tracker Radar entity files.
    Each entity JSON lists a display name and the domains ('properties') it owns.
    """
    domain_to_org = {}
    if not os.path.isdir(entities_dir):
        print(f"  [warn] Tracker Radar not found at {entities_dir} (run setup.sh)")
        return domain_to_org

    files = [f for f in os.listdir(entities_dir) if f.endswith(".json")]
    for i, filename in enumerate(files, start=1):
        path = os.path.join(entities_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        org_name = data.get("displayName") or data.get("name")
        for domain in data.get("properties", []):
            domain_to_org[domain.lower()] = org_name
    print(f"  built domain->org map from {len(files)} entities ({len(domain_to_org)} domains)")
    return domain_to_org


def main():
    cfg = load_config()
    results_dir = ensure_dir(cfg["paths"]["results_dir"])
    entities_dir = cfg["paths"]["tracker_radar_entities"]

    domains_csv = os.path.join(results_dir, "tracker_domains.csv")
    if not os.path.exists(domains_csv):
        print(f"  [error] {domains_csv} not found -- run identify_tracker.py first")
        return

    domain_to_org = build_domain_to_org(entities_dir)

    # Read the tracker-domain frequencies from Stage 3.
    rows = []
    with open(domains_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((row["tracker_domain"], int(row["embed_count"])))

    # Map each domain to an org; unmapped domains are grouped as "Unknown"
    # (a conservative lower bound on concentration, as in the paper).
    org_totals = defaultdict(int)
    mapping_path = os.path.join(results_dir, "tracker_org_mapping.csv")
    with open(mapping_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tracker_domain", "organization", "embed_count"])
        for domain, count in rows:
            org = domain_to_org.get(domain.lower(), "Unknown")
            org_totals[org] += count
            w.writerow([domain, org, count])
    print(f"  wrote {mapping_path}")

    totals_path = os.path.join(results_dir, "org_totals.csv")
    with open(totals_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["organization", "total_embeds"])
        for org, total in sorted(org_totals.items(), key=lambda x: -x[1]):
            w.writerow([org, total])
    print(f"  wrote {totals_path}")

    print("Stage 4 complete.")


if __name__ == "__main__":
    main()
