# Artifact Appendix

Paper title: **The Empire Strikes Back (at Your Privacy): An Archaeology of Tracking on Government Websites**

Requested Badge(s):
  - [x] **Available**
  - [x] **Functional**
  - [ ] **Reproduced**

## Description

This artifact accompanies the paper:

> Sachin Kumar Singh, Faisal Mahmud, Robert Ricci, and Sandra Siby.
> *The Empire Strikes Back (at Your Privacy): An Archaeology of Tracking on
> Government Websites.* Proceedings on Privacy Enhancing Technologies (PoPETs),
> 2026(2).

The artifact is the end-to-end measurement pipeline used in the paper. It
reconstructs, for a list of government websites, whether and when each site
embedded web trackers, using historical homepage snapshots from the Internet
Archive's Wayback Machine. The pipeline runs in four stages:

1. **`snapshot_downloader.py`** — queries the Internet Archive CDX API for the
   index of all captures of each website.
2. **`archive_downloader.py`** — selects snapshots per year according to
   `config.yaml` (the first capture of each year plus random additional ones)
   and downloads the archived HTML.
3. **`identify_tracker.py`** — extracts embedded URLs from each page, matches
   them against the EasyList/EasyPrivacy filter lists, classifies each tracker
   as first- or third-party (by eTLD+1), and produces a per-country line plot of
   tracker prevalence over time plus supporting CSVs.
4. **`map_tracker_org.py`** — maps the detected tracker domains to their parent
   organizations using DuckDuckGo's Tracker Radar dataset.

This directly supports the paper's measurement of tracker prevalence over time
(RQ1), per-country heterogeneity (RQ2), and ownership concentration among a
small set of organizations (RQ3). An orchestrator, `main.py`, runs the whole
pipeline.

For a quick run, do:
 
```bash
# 1. Get the code and install everything (deps + filter lists + Tracker Radar)
git clone https://github.com/such-in/archive-based-tracking.git
cd archive-based-tracking
bash setup.sh
 
# 2. (Optional) narrow the year range in config.yaml so the demo is fast,
#    e.g. set years.start: 2020 and years.end: 2022
 
# 3. Run the full pipeline on the bundled sample input.csv
python main.py
```


### Security/Privacy Issues and Ethical Concerns

The artifact poses no security risk to the evaluator's machine. It does **not**
disable any security mechanism, and it does **not** execute any archived or
third-party code. Archived pages are treated purely as text: the pipeline reads
their HTML and matches embedded resource URLs as **strings** against filter
lists. Archived JavaScript (including from domains later found to be malicious,
such as the `polyfill.io` compromise discussed in the paper) is never fetched or
run.

All inputs are public: archived web pages from the Internet Archive, the
community-maintained EasyList/EasyPrivacy filter lists, and the public DuckDuckGo
Tracker Radar dataset. The artifact involves no human subjects and no personal
data, so no IRB/ethics review applies.

The only operational consideration is courtesy toward the Internet Archive,
which is a free public service. The downloaders insert a configurable delay
between requests (`request_delay` in `config.yaml`, default 5 s) and skip work
already on disk. 

## Basic Requirements

### Hardware Requirements

Can run on a desktop/laptop (no special hardware requirements). A network connection is
needed for the data-collection stages. More CPU cores speed up the tracker
identification stage (it parses HTML and runs regex matching across worker
processes) but are not required.

### Software Requirements

1. **Operating system:** Developed and tested on Ubuntu 24.04. The artifact is
   pure Python plus two shell tools (`git`, `curl`) and has no OS-specific
   dependencies; it is expected to run on other Linux distributions, macOS, and
   Windows.
2. **OS packages:** `git` and `curl` (used by `setup.sh` to fetch the filter
   lists and clone Tracker Radar).
3. **Container runtime:** None required. The artifact runs directly in a Python
   environment; no Docker image or VM is needed.
4. **Interpreter:** Python 3.9 or newer (tested with Python 3.12).
5. **Python packages:** Listed in `requirements.txt` and installed by
   `setup.sh`:
   - `requests >= 2.28`
   - `PyYAML >= 6.0`
   - `pandas >= 1.5`
   - `beautifulsoup4 >= 4.11`
   - `tldextract >= 3.4`
   - `matplotlib >= 3.6`
6. **Machine-learning models:** None.
7. **Datasets:**
   - **Website list (input):** a CSV of `country,website` rows. A small sample
     (`input.csv`, sites across several countries) is included to
     demonstrate the expected format and to allow a quick functional run. The
     full study uses the government-website list of Kumar et al. (IMC 2024); the
     paper's complete list can be substituted by replacing `input.csv`.
   - **Snapshots:** downloaded live from the Internet Archive at runtime (not
     shipped with the artifact).
   - **Filter lists:** EasyList and EasyPrivacy, downloaded by `setup.sh`.
   - **Organization mapping:** DuckDuckGo Tracker Radar, cloned by `setup.sh`.

### Estimated Time and Storage Consumption

- **Functional evaluation (recommended small configuration):** about 15
  human-minutes of interaction and 10–15 compute-minutes of mostly
  network-bound time, consuming well under 1 GB of disk (sample website list, a
  narrow year range, the filter lists, and the Tracker Radar clone).
- **Full study run (not required for these badges):** the data collection is
  network-bound and dominated by the polite per-request delay. Collecting
  snapshots for the complete website list across 1996–2025 takes on the order of
  days to weeks on a single machine (substantially less when sharded across
  several machines, as in the paper), and consumes on the order of tens of GB of
  disk for the archived HTML.

## Environment

### Accessibility

The artifact is hosted on GitHub:

> https://github.com/such-in/archive-based-tracking


### Set up the environment

```bash
# 1. Clone the repository
git clone https://github.com/such-in/archive-based-tracking.git
cd archive-based-tracking

# 2. (Recommended) create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate

# 3. Install dependencies, download EasyList/EasyPrivacy, clone Tracker Radar
bash setup.sh
```

After `setup.sh` completes you should see:

- `tracker_list/easylist.txt` and `tracker_list/easyprivacy.txt`
- a `tracker-radar/` directory containing the cloned dataset (with an
  `entities/` subfolder)
- the Python dependencies installed in your environment

### Testing the Environment

A quick check that the environment is set up correctly:

```bash
# (a) dependencies import cleanly
python -c "import requests, yaml, bs4, tldextract, matplotlib, pandas; print('deps OK')"

# (b) the data downloaded by setup.sh is present
ls tracker_list/easylist.txt tracker_list/easyprivacy.txt
ls tracker-radar/entities | head

# (c) the pipeline can reach the Internet Archive (downloads a handful of
#     small CDX index files for the sample sites; takes ~1 minute)
python snapshot_downloader.py
ls data/cdx/*/*.json | head
```

Expected output: `deps OK` from step (a); the two filter-list files and a list
of Tracker Radar entity files from step (b); and one JSON file per sample
website under `data/cdx/<COUNTRY>/` from step (c). If all three succeed, the
software is functioning correctly.

## Artifact Evaluation

 
### Main Results and Claims
 
We apply for the **Available** and **Functional** badges. We therefore do not
claim reproduction of the paper's specific quantitative results (exact tracker
prevalence percentages, per-country rankings, or figures), which require the
full website list and the long data-collection run.
 
Instead, the experiments below demonstrate that the artifact correctly performs
the measurements underlying the paper's claims — detecting trackers per site and
year, distinguishing first- from third-party trackers, plotting per-country
prevalence over time, and mapping trackers to their owning organizations — on a
small, fast sample. The numbers produced on this sample are illustrative of the
pipeline's functionality, not the values reported in the paper.

### Experiments
 
The experiment is configured through `config.yaml`. The included `input.csv` is used
as the website list.
 
#### Experiment 1: Full pipeline run
 
- Time: ~10 human-minutes + ~15 compute-minutes (mostly network-bound).
- Storage: < 1 GB.
This single experiment runs the whole pipeline end to end — all four stages —
on the sample website list and the configured years. It downloads the archived
snapshots, identifies trackers, classifies them as first- vs third-party, plots
per-country prevalence over time, and maps the trackers to their owning
organizations.
 
```bash
python main.py
```
 
(`main.py` runs the four stages in order; you can also run them individually as
`python snapshot_downloader.py`, `python archive_downloader.py`,
`python identify_tracker.py`, and `python map_tracker_org.py`. Stage 3 uses all
CPU cores by default; cap it with `--workers N` or the `num_workers` config
option. All stages skip work already on disk, so the run is safe to re-run and
resume.)
 
Expected results:
 
- Capture indexes under `data/cdx/<COUNTRY>/` and archived pages under
  `data/snapshots/<COUNTRY>/<site>/<timestamp>.html`.
- In `results/`:
  - `tracker_results.csv` — one row per `(country, website, year)` with
    `has_tracker`, `has_first_party`, `has_third_party` flags.
  - `tracker_percentage_by_country_year.csv` — per country and year, the count
    of sites with a tracker, the count sampled, and the percentage.
  - `plots/<COUNTRY>.png` — one line plot per country (x = year, y = % of that
    country's sites with a tracker), plus `tracker_trends_all_countries.png`.
  - `tracker_domains.csv` — detected tracker domains and embed counts.
  - `tracker_org_mapping.csv` and `org_totals.csv` — tracker domains mapped to
    their parent organizations (unmapped domains grouped as `Unknown`) and
    organizations ranked by total embeds.
This demonstrates the functionality on the small sample and the
exact numbers are illustrative of the pipeline's functionality, not the values
reported in the paper.
 

## Limitations

- The artifact demonstrates the full measurement methodology but, for the
  Functional badge, is exercised on a small sample website list and a narrow
  year range. Reproducing the paper's exact prevalence percentages, country
  rankings, and figures requires the complete government-website list and the
  long, network-bound data-collection run, which is impractical during artifact
  review and is not claimed for the Available/Functional badges.
- Results depend on live data that changes over time: the Internet Archive may
  add captures, and `setup.sh` downloads the current EasyList/EasyPrivacy lists
  rather than the June 2025 snapshot pinned in the paper. Detection therefore
  remains functional, but exact counts on identical inputs can drift relative to
  the paper.
- As discussed in the paper, archive coverage is uneven across countries and
  time, only homepages are fetched, and filter-list detection is a conservative
  lower bound so the measurements should be read as trends rather than exact rates.

## Notes on Reusability

The pipeline is not specific to government websites. Any list of sites can be
studied by replacing `input.csv` with `country,website` rows, where the
"country" column is just a grouping label (any string works). All collection and
analysis parameters — the year range, snapshots per year, request delay, worker
count, and file paths — are centralized in `config.yaml`, and each of the four
stages can be run, re-run, or replaced independently.

Reusers can adapt the artifact by, for example: substituting a different filter
list or adding rules in `identify_tracker.py`; pinning historical EasyList
versions for time labeling; pointing the organization mapper at an
updated Tracker Radar clone; or consuming the emitted CSVs
(`tracker_results.csv`, `tracker_percentage_by_country_year.csv`,
`tracker_domains.csv`) to build additional analyses such as concentration
indices or trend tests. The shared helpers in `common.py` (config loading,
eTLD+1 extraction, Wayback URL cleaning) are reusable in other archive-based web
measurement studies.
