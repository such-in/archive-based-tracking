"""
common.py
---------
Small shared helpers used across the pipeline stages so that each script
loads the config, reads the input list, and parses domains the same way.
"""

import csv
import os
import re

import yaml
import tldextract

# Use tldextract's bundled Public Suffix List snapshot instead of fetching a
# fresh copy on every run. This makes results deterministic and works offline.
# To refresh the list periodically, run:  tldextract --update
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())


def load_config(path="config.yaml"):
    """Load the YAML config file into a plain dict."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_input_csv(path):
    """
    Read the input list of websites.

    Expected columns: `country,website`
    Returns a list of (country, website) tuples.
    """
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country = (row.get("country") or "").strip()
            website = (row.get("website") or "").strip()
            if country and website:
                rows.append((country, website))
    return rows


def safe_name(domain):
    """Turn a domain into a filesystem-safe name (dots -> underscores)."""
    return domain.replace(".", "_").replace("/", "_")


def etld1(url_or_domain):
    """
    Return the effective top-level-domain-plus-one (eTLD+1) of a URL or domain.

    e.g. "https://www.google-analytics.com/ga.js" -> "google-analytics.com"
    Used to (a) group tracker domains and (b) classify first- vs third-party.
    """
    ext = _EXTRACT(url_or_domain)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}".lower()
    return (ext.domain or "").lower()


# The Internet Archive rewrites embedded URLs to point at its own cache, e.g.
#   https://web.archive.org/web/20220101000000/https://a.com/script.js
#   https://web.archive.org/web/20220101000000im_/https://a.com/logo.png
# This regex strips that prefix (including the optional "im_", "js_", "id_"
# modifier) so we recover the ORIGINAL embedded URL before tracker matching.
_WAYBACK_PREFIX = re.compile(
    r"https?://web\.archive\.org/web/\d+[a-z_]*/", re.IGNORECASE
)


def clean_wayback_url(url):
    """Strip any Internet Archive cache prefix to recover the original URL."""
    if not url:
        return url
    cleaned = _WAYBACK_PREFIX.sub("", url)
    # Some archived pages double-wrap; strip repeatedly until stable.
    while _WAYBACK_PREFIX.search(cleaned):
        cleaned = _WAYBACK_PREFIX.sub("", cleaned)
    return cleaned


def ensure_dir(path):
    """Create a directory (and parents) if it does not already exist."""
    os.makedirs(path, exist_ok=True)
    return path
