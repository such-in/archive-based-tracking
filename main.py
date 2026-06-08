"""
main.py
-------
Convenience runner that executes the whole pipeline end to end:

    Stage 1  snapshot_downloader.py   (Wayback capture indexes)
    Stage 2  archive_downloader.py    (download archived HTML)
    Stage 3  identify_tracker.py      (detect trackers + plot)
    Stage 4  map_tracker_org.py       (map domains -> organizations)

Each stage is launched as a separate process so it parses its own arguments
and runs in isolation; if any stage fails, the run stops with its exit code.

Examples:
    # run everything with the default config.yaml
    python main.py

    # run only the analysis stages (e.g. after data is already downloaded)
    python main.py --stages 3,4

    # run setup.sh first, then the full pipeline
    python main.py --setup

    # shard Stage 1 across machines (passed through to snapshot_downloader)
    python main.py --machine 0 --num-machines 3
"""

import argparse
import subprocess
import sys
import time

# Stage number -> (script filename, human-readable label)
STAGES = {
    1: ("snapshot_downloader.py", "Download Wayback capture indexes"),
    2: ("archive_downloader.py", "Download archived HTML snapshots"),
    3: ("identify_tracker.py", "Identify trackers and plot"),
    4: ("map_tracker_org.py", "Map tracker domains to organizations"),
}


def parse_stages(value):
    """Turn '--stages 1,3,4' (or 'all') into a sorted list of stage numbers."""
    if value.strip().lower() == "all":
        return sorted(STAGES)
    chosen = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        n = int(part)
        if n not in STAGES:
            raise SystemExit(f"Unknown stage '{n}'. Valid stages: {sorted(STAGES)}")
        chosen.append(n)
    return sorted(set(chosen))


def run(cmd):
    """Run a subprocess, streaming its output; return its exit code."""
    print(f"\n$ {' '.join(cmd)}\n", flush=True)
    return subprocess.run(cmd).returncode


def main():
    parser = argparse.ArgumentParser(description="Run the archive-based-tracking pipeline.")
    parser.add_argument("--config", default="config.yaml",
                        help="Path to the YAML config (default: config.yaml).")
    parser.add_argument("--stages", default="all",
                        help="Comma-separated stages to run, e.g. '1,2' or 'all' (default: all).")
    parser.add_argument("--setup", action="store_true",
                        help="Run setup.sh before the pipeline (install deps + download lists).")
    parser.add_argument("--machine", type=int, default=0,
                        help="This machine's index for sharding Stage 1 (default: 0).")
    parser.add_argument("--num-machines", type=int, default=1,
                        help="Total machines sharing Stage 1 work (default: 1).")
    args = parser.parse_args()

    stages = parse_stages(args.stages)
    py = sys.executable  # use the same interpreter that launched main.py

    overall_start = time.time()

    if args.setup:
        print("==> Running setup.sh")
        if run(["bash", "setup.sh"]) != 0:
            raise SystemExit("setup.sh failed; aborting.")

    for n in stages:
        script, label = STAGES[n]
        print("=" * 70)
        print(f"STAGE {n}: {label}  ({script})")
        print("=" * 70)

        cmd = [py, script, "--config", args.config]
        # Only Stage 1 understands the sharding flags.
        if n == 1:
            cmd += ["--machine", str(args.machine),
                    "--num-machines", str(args.num_machines)]

        start = time.time()
        code = run(cmd)
        elapsed = time.time() - start
        if code != 0:
            raise SystemExit(f"Stage {n} ({script}) failed with exit code {code}.")
        print(f"\n-- Stage {n} finished in {elapsed:.1f}s --")

    total = time.time() - overall_start
    print("\n" + "=" * 70)
    print(f"Pipeline complete. Ran stages {stages} in {total:.1f}s.")
    print("Results are in the 'results/' directory.")
    print("=" * 70)


if __name__ == "__main__":
    main()
