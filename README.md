# Archive-Based Tracking

A pipeline for measuring third-party **web trackers on websites over time**,
using historical snapshots from the [Internet Archive](https://archive.org)'s
Wayback Machine.

Given a list of websites (and the country each belongs to), the pipeline
reconstructs, for each site and year, whether it embedded tracking technology,
who operated that tracking (first-party vs. third-party), and which parent
organizations dominate. It was built for a longitudinal study of tracking on
**government websites** across 61 countries (1996–2025), but works for any list
of sites.

---

## How it works

The pipeline has four stages. Each reads its settings from `config.yaml`, so
that file is the single place to control which years and how many snapshots you
collect.

```
input.csv ─► snapshot_downloader ─► archive_downloader ─► identify_tracker ─► map_tracker_org
            (list of captures)     (actual archived HTML)  (trackers + plot)   (domain → org)
```

| Stage | Script | What it does | Output |
|------:|--------|--------------|--------|
| 1 | `snapshot_downloader.py` | For every site in `input.csv`, ask the Wayback CDX API for the index of all captures. | `data/cdx/<COUNTRY>/<site>.json` |
| 2 | `archive_downloader.py` | For each year in `config.yaml`, pick `snapshots_per_year` captures (first-of-year + random) and download the real archived HTML. | `data/snapshots/<COUNTRY>/<site>/<timestamp>.html` |
| 3 | `identify_tracker.py` | Extract embedded URLs from each page, match them against EasyList/EasyPrivacy, classify first- vs third-party, and plot prevalence per country. | `results/tracker_results.csv`, `results/tracker_domains.csv`, `results/tracker_percentage_by_country_year.csv`, `results/plots/<COUNTRY>.png` |
| 4 | `map_tracker_org.py` | Map tracker domains to their parent organizations via DuckDuckGo Tracker Radar. | `results/tracker_org_mapping.csv`, `results/org_totals.csv` |

---

## Setup

Requires Python 3.9+ and `git`/`curl`.

```bash
bash setup.sh
```

`setup.sh` installs the Python dependencies (`requirements.txt`), downloads the
**EasyList** and **EasyPrivacy** filter lists into `tracker_list/`, and clones
**DuckDuckGo Tracker Radar** into `tracker-radar/`.

---

## Inputs

### `input.csv`

One row per website, with a country code (any label you like — ISO-2 is
recommended) and the domain:

```csv
country,website
US,aftermath.site
US,404media.co
US,www.cs.utah.edu/apply-for-seeds-2024/
IN,indianstartupnews.com
IN,www.cs.utah.edu/apply-for-seeds-2024/
```

### `config.yaml`

Controls the collection window and sampling. The key knobs:

```yaml
years:
  start: 2024      # earliest year to download
  end: 2026        # latest year to download
snapshots_per_year: 2   # captures to download per site per year
random_seed: 42         # makes the random picks reproducible
only_status_200: true   # ignore captures that weren't HTTP 200
request_delay: 5     # seconds between archive requests
```

**Snapshot selection rule:** for each year, the *first* capture of that year is
always taken, and any remaining slots are filled with *random* captures from the
same year. So `snapshots_per_year: 2` means "first-of-year plus one random".

---

## Running the pipeline

The quickest way is the orchestrator, which runs all four stages in order:

```bash
python main.py
```

Useful variations:

```bash
python main.py --setup            # run setup.sh first, then the full pipeline
python main.py --stages 3,4       # run only specific stages (e.g. re-analyze)
python main.py --config my.yaml   # use an alternate config file
```

If any stage fails, the run stops with that stage's exit code. The orchestrator
prints a banner and timing for each stage.

### Running stages individually

You can also run the stages by hand, in order:

```bash
python snapshot_downloader.py     # Stage 1: capture indexes
python archive_downloader.py      # Stage 2: download archived HTML
python identify_tracker.py        # Stage 3: detect trackers + plot
python map_tracker_org.py         # Stage 4: map domains to organizations
```

Stages 1 and 2 are network-bound and can take a while for large lists — they
skip work that is already on disk, so they are safe to re-run / resume.

Stage 3 is CPU-bound (HTML parsing + regex matching) and runs across multiple
worker processes. By default it uses all CPU cores; cap it with `num_workers`
in `config.yaml` or at runtime:

```bash
python identify_tracker.py --workers 8
```

---

## Outputs

After a full run, `results/` contains:

- **`tracker_results.csv`** — one row per `(country, website, year)` with
  `has_tracker`, `has_first_party`, `has_third_party` flags. A site-year is
  flagged if *any* of its snapshots that year contained a tracker. Sites that
  were sampled but had no tracker are still recorded (so percentages are
  computed against all sampled sites, not just the tracked ones).
- **`tracker_percentage_by_country_year.csv`** — for each country and year, the
  number of websites with a tracker, the number sampled, and the percentage.
- **`tracker_domains.csv`** — every tracker domain (eTLD+1) seen and how many
  times it was embedded.
- **`tracker_org_mapping.csv`** — each tracker domain mapped to its parent
  organization (unmapped domains are grouped as `Unknown`).
- **`org_totals.csv`** — organizations ranked by total embeds.
- **`plots/<COUNTRY>.png`** — one line plot per country: x-axis = year,
  y-axis = percentage of that country's websites with trackers.
- **`tracker_trends_all_countries.png`** — a single overview chart with one
  line per country.

---

## Method notes & caveats

- **First- vs. third-party** is decided by comparing the tracker's eTLD+1 to the
  website's eTLD+1. It is domain-based and does not infer ownership, so a tracker
  hosted by a *different* government agency counts as third-party.
- **Wayback URL rewriting:** the archive rewrites embedded URLs to point at its
  own cache; `common.clean_wayback_url()` strips that prefix to recover the
  original URL before matching.
- **Filter lists are a lower bound.** EasyList/EasyPrivacy do not capture every
  tracker, and a single recent snapshot of the lists is applied to all years.
  Tracker counts should be read as conservative lower bounds.
- **Archive coverage is uneven** across countries and time, and only homepages
  are fetched, so deeper-page trackers are missed. Treat measurements as trends,
  not exact rates.

---

## Project layout

```
.
├── README.md
├── setup.sh                 # install deps + download EasyList + Tracker Radar
├── requirements.txt
├── config.yaml              # years / snapshots-per-year / paths
├── input.csv                # (country, website) list to study
├── common.py                # shared helpers (config, eTLD+1, URL cleaning)
├── main.py                  # orchestrator: runs all stages in order
├── snapshot_downloader.py   # Stage 1
├── archive_downloader.py    # Stage 2
├── identify_tracker.py      # Stage 3
└── map_tracker_org.py       # Stage 4
```

## Data sources & licenses

- Snapshots: [Internet Archive Wayback Machine](https://archive.org/web/)
- Tracker detection: [EasyList & EasyPrivacy](https://easylist.to/)
- Organization mapping: [DuckDuckGo Tracker Radar](https://github.com/duckduckgo/tracker-radar)

