"""
Orchestrator for fast-scrapers.

Usage:
    python orchestrator.py --all       # Run all scrapers (a, b, c, d, f)
    python orchestrator.py --local     # Run local scrapers (a, b, c)
    python orchestrator.py --aws       # Run AWS scrapers (d, f)
"""

import argparse
import os
import subprocess
import sys
import signal
from datetime import datetime
from pathlib import Path

SCRAPERS_DIR = Path(__file__).parent
LOGS_DIR = SCRAPERS_DIR / "logs"
PYTHON_SCRAPERS_DIR = SCRAPERS_DIR.parent / "python-scrapers"

SCRAPERS = {
    "a": "a_sunarp_scraper.py",
    "b": "b_consulta_vehicular_scraper.py",
    "c": "c_sbs_scraper.py",
    "d": "d_inspeccion_tecnica_scraper.py",
    "f": "f_soat_apeseg.py",
}

LOCAL_SCRAPERS = ["a", "b", "c"]
AWS_SCRAPERS = ["d", "f"]
ALL_SCRAPERS = LOCAL_SCRAPERS + AWS_SCRAPERS


def launch_scrapers(keys: list[str], run_id: str) -> list[tuple[str, subprocess.Popen, Path]]:
    LOGS_DIR.mkdir(exist_ok=True)
    processes = []
    for key in keys:
        script = SCRAPERS_DIR / SCRAPERS[key]
        log_path = LOGS_DIR / f"{key}_{run_id}.log"
        log_file = open(log_path, "w", buffering=1, encoding="utf-8")
        print(f"[orchestrator] Starting scraper {key}: {script.name}  →  logs/{log_path.name}")
        env = os.environ.copy()
        extra_paths = [str(SCRAPERS_DIR), str(PYTHON_SCRAPERS_DIR)]
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(extra_paths + ([existing] if existing else []))
        proc = subprocess.Popen(
            [sys.executable, "-u", str(script)],
            cwd=str(SCRAPERS_DIR),
            stdout=log_file,
            stderr=log_file,
            env=env,
        )
        processes.append((key, proc, log_path, log_file))
    return processes


def wait_for_all(processes: list[tuple[str, subprocess.Popen, Path, object]]) -> None:
    def shutdown(signum, frame):
        print("\n[orchestrator] Shutting down all scrapers...")
        for key, proc, log_path, log_file in processes:
            if proc.poll() is None:
                proc.terminate()
                print(f"[orchestrator] Terminated scraper {key} (pid {proc.pid})  log → {log_path.name}")
            log_file.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"[orchestrator] Running {len(processes)} scraper(s). Press Ctrl+C to stop all.")
    for key, proc, log_path, log_file in processes:
        proc.wait()
        log_file.close()
        print(f"[orchestrator] Scraper {key} finished with exit code {proc.returncode}  log → {log_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Fast-scrapers orchestrator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run all scrapers (a, b, c, d, f)")
    group.add_argument("--local", action="store_true", help="Run local scrapers (a, b, c)")
    group.add_argument("--aws", action="store_true", help="Run AWS scrapers (d, f)")
    args = parser.parse_args()

    if args.all:
        keys = ALL_SCRAPERS
    elif args.local:
        keys = LOCAL_SCRAPERS
    else:
        keys = AWS_SCRAPERS

    print(f"[orchestrator] Mode: {'--all' if args.all else '--local' if args.local else '--aws'}")
    print(f"[orchestrator] Scrapers to run: {', '.join(keys)}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    processes = launch_scrapers(keys, run_id)
    wait_for_all(processes)


if __name__ == "__main__":
    main()
