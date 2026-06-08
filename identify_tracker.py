"""
identify_tracker.py  (Stage 3 of 4)
-----------------------------------
Walks the archived HTML downloaded in Stage 2 and, for each page:

  1. extracts every embedded URL (script/img/link/iframe src+href, plus URLs
     that appear inside inline scripts),
  2. strips the Internet Archive cache prefix to recover the ORIGINAL URL,
  3. flags a URL as a tracker if it matches any EasyList / EasyPrivacy rule
     (plus a few manual rules), exactly as in the original pipeline,
  4. classifies each matched tracker as FIRST-party (same eTLD+1 as the
     government site) or THIRD-party (different eTLD+1).

It then aggregates to one row per (country, website, year) -- a site-year is
counted as "has tracker" if ANY of its snapshots that year contains one --
writes results/tracker_results.csv and results/tracker_domains.csv, and draws
one line plot per country (year vs % of websites with trackers).

HTML parsing and regex matching are CPU-bound, so they are spread across
multiple worker processes. Control the worker count with `num_workers` in
config.yaml or the --workers flag (default: all CPU cores).

Usage:
    python identify_tracker.py
    python identify_tracker.py --workers 8
"""

import csv
import os
import re
from collections import defaultdict

from bs4 import BeautifulSoup

from common import (
    load_config, read_input_csv, safe_name, etld1,
    clean_wayback_url, ensure_dir,
)

# A few extra rules kept from the original pipeline.
MANUAL_RULES = ["googleapis.com", "cloudfront.net", "googlesyndication.com"]

# Find bare URLs embedded inside inline <script> blocks and attributes.
URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>\\)]+", re.IGNORECASE)


def load_tracker_pattern_strings(list_files, manual_rules):
    """
    Build a list of regex pattern STRINGS from EasyList/EasyPrivacy rules.

    We return uncompiled strings (rather than compiled regexes) because they
    are cheap to ship to worker processes, which each compile them once.

    EasyList syntax is rich; here we keep the simple, domain/substring style
    network rules (which is what matters for matching embedded URLs) and skip:
      * comments / metadata          (lines starting with ! or [)
      * exception rules              (@@...)
      * cosmetic / element-hiding    (## , #@# , #?# , #$#)
    Wildcards (*) and separators (^, |) are translated to regex.
    """
    patterns = set()
    for fname in list_files:
        if not os.path.exists(fname):
            print(f"  [warn] filter list not found: {fname} (run setup.sh)")
            continue
        with open(fname, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith(("!", "[", "@")):
                    continue
                if any(tok in line for tok in ("##", "#@#", "#?#", "#$#")):
                    continue
                # Drop EasyList rule options (everything after the first '$').
                rule = line.split("$", 1)[0]
                # Strip anchors/separators that don't map cleanly to substrings.
                rule = rule.strip("|").replace("^", "").replace("||", "")
                if not rule:
                    continue
                # Escape, then turn EasyList wildcards back into regex wildcards.
                rx = re.escape(rule).replace(r"\*", ".*").replace(r"\?", ".")
                patterns.add(rx)

    for rule in manual_rules:
        patterns.add(re.escape(rule).replace(r"\*", ".*").replace(r"\?", "."))

    pattern_list = [p for p in patterns if p]
    print(f"  loaded {len(pattern_list)} tracker patterns")
    return pattern_list


def is_tracker(url, patterns):
    """Return True if the URL matches any tracker pattern."""
    for pat in patterns:
        if pat.search(url):
            return True
    return False


# --- Worker process state ----------------------------------------------------
# Each worker compiles the patterns ONCE in its initializer and stores them in
# this module-level global, so we never re-compile or re-ship them per file.
_WORKER_PATTERNS = None


def _init_worker(pattern_strings):
    """Pool initializer: compile the regex patterns once per worker process."""
    global _WORKER_PATTERNS
    _WORKER_PATTERNS = [re.compile(p, re.IGNORECASE) for p in pattern_strings]


def _process_file(task):
    """
    Process a single archived HTML file (runs inside a worker process).

    `task` is (country, website, site_etld1, filepath). Returns a tuple:
        (country, website, year, has_any, has_first, has_third, domain_counts)
    where domain_counts is a {tracker_etld1: count} dict for this one file.
    A result is returned even when the page has no trackers, so the site-year
    is still counted in the denominator for percentage calculations.
    """
    country, website, site_e, path = task
    year = year_of(path)
    has_any = has_first = has_third = False
    domain_counts = {}

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        for url in extract_urls(html):
            if not is_tracker(url, _WORKER_PATTERNS):
                continue
            tdomain = etld1(url)
            if not tdomain:
                continue
            domain_counts[tdomain] = domain_counts.get(tdomain, 0) + 1
            has_any = True
            if tdomain == site_e:
                has_first = True
            else:
                has_third = True
    except Exception as e:
        # A single unreadable/garbled snapshot shouldn't kill the whole run.
        print(f"  [warn] failed to process {path}: {e}")

    return (country, website, year, has_any, has_first, has_third, domain_counts)


def extract_urls(html):
    """Pull every plausibly-embedded URL out of an archived HTML page."""
    urls = set()
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "img", "link", "iframe", "source", "embed"]):
        for attr in ("src", "href", "data-src"):
            val = tag.get(attr)
            if val:
                urls.add(val)
        # URLs sitting inside inline scripts.
        if tag.name == "script" and tag.string:
            urls.update(URL_IN_TEXT.findall(tag.string))
    return {clean_wayback_url(u) for u in urls}


def year_of(filename):
    """Snapshot files are named <timestamp>.html; the year is the first 4 chars."""
    base = os.path.basename(filename)
    return base[:4] if base[:4].isdigit() else None


def main():
    import argparse
    import multiprocessing as mp

    parser = argparse.ArgumentParser(description="Identify trackers and plot prevalence.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--workers", type=int, default=None,
                        help="Number of parallel worker processes "
                             "(default: config 'num_workers' or all CPU cores).")
    args = parser.parse_args()

    cfg = load_config(args.config)
    rows = read_input_csv(cfg["paths"]["input_csv"])
    snap_dir = cfg["paths"]["snapshots_dir"]
    results_dir = ensure_dir(cfg["paths"]["results_dir"])

    pattern_strings = load_tracker_pattern_strings(cfg["paths"]["tracker_lists"], MANUAL_RULES)

    # Decide how many worker processes to use.
    workers = args.workers or cfg.get("num_workers") or os.cpu_count() or 1
    workers = max(1, int(workers))

    # Build the task list: one task per archived HTML file.
    tasks = []
    for country, website in rows:
        site_e = etld1(website)
        site_path = os.path.join(snap_dir, country, safe_name(website))
        if not os.path.isdir(site_path):
            continue
        for fname in os.listdir(site_path):
            if fname.endswith(".html") and year_of(fname):
                tasks.append((country, website, site_e, os.path.join(site_path, fname)))

    print(f"  processing {len(tasks)} snapshot files using {workers} worker(s)")

    # (country, website, year) -> flags about what trackers we saw
    site_year = defaultdict(lambda: {"any": False, "first": False, "third": False})
    # tracker eTLD+1 -> how many times embedded (feeds Stage 4 org mapping)
    domain_counts = defaultdict(int)

    def aggregate(result):
        """Merge one file's result into the global tallies (order-independent)."""
        country, website, year, has_any, has_first, has_third, dcounts = result
        # Registering the key also counts tracker-free site-years in the
        # denominator for the "percentage of websites with trackers" plots.
        entry = site_year[(country, website, year)]
        entry["any"] = entry["any"] or has_any
        entry["first"] = entry["first"] or has_first
        entry["third"] = entry["third"] or has_third
        for dom, cnt in dcounts.items():
            domain_counts[dom] += cnt

    done = 0
    total = len(tasks)
    if workers > 1 and total > 1:
        # Parallel path: spread file parsing + regex matching across cores.
        with mp.Pool(workers, initializer=_init_worker, initargs=(pattern_strings,)) as pool:
            for result in pool.imap_unordered(_process_file, tasks, chunksize=8):
                aggregate(result)
                done += 1
                if done % 500 == 0 or done == total:
                    print(f"    {done}/{total} files processed")
    else:
        # Serial fallback (workers == 1, or only one file): no process overhead.
        _init_worker(pattern_strings)
        for task in tasks:
            aggregate(_process_file(task))
            done += 1
            if done % 500 == 0 or done == total:
                print(f"    {done}/{total} files processed")

    # ---- Write the per-site-year results table -----------------------------
    results_csv = os.path.join(results_dir, "tracker_results.csv")
    with open(results_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["country", "website", "year", "has_tracker", "has_first_party", "has_third_party"])
        for (country, website, year), flags in sorted(site_year.items()):
            w.writerow([country, website, year,
                        int(flags["any"]), int(flags["first"]), int(flags["third"])])
    print(f"  wrote {results_csv} ({len(site_year)} site-year rows)")

    # ---- Write the tracker-domain frequency table (used by Stage 4) --------
    domains_csv = os.path.join(results_dir, "tracker_domains.csv")
    with open(domains_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tracker_domain", "embed_count"])
        for dom, cnt in sorted(domain_counts.items(), key=lambda x: -x[1]):
            w.writerow([dom, cnt])
    print(f"  wrote {domains_csv} ({len(domain_counts)} tracker domains)")

    # ---- Per-country line plots: year (x) vs % of websites with trackers ---
    # For each (country, year): denominator = distinct websites sampled that
    # year; numerator = those with any tracker. One line plot is written per
    # country, plus a combined overview with one line per country.
    #
    # Import matplotlib here (not at module top) so the worker processes above
    # don't pay to import it.
    import matplotlib
    matplotlib.use("Agg")  # headless: write PNGs without a display
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    # counts[country][year] = [num_with_tracker, num_sampled]
    counts = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for (country, _, year), flags in site_year.items():
        cell = counts[country][int(year)]
        cell[1] += 1                 # sampled
        if flags["any"]:
            cell[0] += 1             # with tracker

    plots_dir = ensure_dir(os.path.join(results_dir, "plots"))

    # Also write a tidy country-year percentage CSV alongside the plots.
    trend_csv = os.path.join(results_dir, "tracker_percentage_by_country_year.csv")
    with open(trend_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["country", "year", "websites_with_tracker", "websites_sampled", "percentage"])
        for country in sorted(counts):
            for year in sorted(counts[country]):
                ntrk, ntot = counts[country][year]
                pct = 100 * ntrk / ntot if ntot else 0
                w.writerow([country, year, ntrk, ntot, f"{pct:.1f}"])
    print(f"  wrote {trend_csv}")

    # One line plot per country.
    for country in sorted(counts):
        years = sorted(counts[country])
        pct = [100 * counts[country][y][0] / counts[country][y][1]
               if counts[country][y][1] else 0 for y in years]

        plt.figure(figsize=(7, 4))
        plt.plot(years, pct, marker="o", color="#4C72B0")
        plt.ylabel("% of websites with trackers")
        plt.xlabel("Year")
        plt.title(f"Tracker prevalence on websites — {country}")
        plt.ylim(0, 105)
        plt.grid(True, alpha=0.3)
        ax = plt.gca()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))  # whole years only
        ax.ticklabel_format(axis="x", useOffset=False, style="plain")
        plt.tight_layout()
        out_path = os.path.join(plots_dir, f"{country}.png")
        plt.savefig(out_path, dpi=150)
        plt.close()
    print(f"  wrote {len(counts)} per-country line plots to {plots_dir}/")

    # Combined overview: one line per country on a single chart.
    if counts:
        plt.figure(figsize=(9, 5))
        for country in sorted(counts):
            years = sorted(counts[country])
            pct = [100 * counts[country][y][0] / counts[country][y][1]
                   if counts[country][y][1] else 0 for y in years]
            plt.plot(years, pct, marker="o", markersize=3, label=country)
        plt.ylabel("% of websites with trackers")
        plt.xlabel("Year")
        plt.title("Tracker prevalence on websites by country")
        plt.ylim(0, 105)
        plt.grid(True, alpha=0.3)
        ax = plt.gca()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))  # whole years only
        ax.ticklabel_format(axis="x", useOffset=False, style="plain")
        plt.legend(fontsize=8, ncol=2, loc="upper left")
        plt.tight_layout()
        combined_path = os.path.join(results_dir, "tracker_trends_all_countries.png")
        plt.savefig(combined_path, dpi=150)
        plt.close()
        print(f"  wrote {combined_path}")

    print("Stage 3 complete.")


if __name__ == "__main__":
    main()
