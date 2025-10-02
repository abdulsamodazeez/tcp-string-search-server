"""
Benchmark Script for Algorithmic Sciences Task
==============================================

This module benchmarks multiple search algorithms under two modes:

1. **Cache Mode (REREAD_ON_QUERY=False)**  
   - Dataset is loaded once and reused.  
   - Optimized for speed (target <0.5 ms per query).  

2. **Reread Mode (REREAD_ON_QUERY=True)**  
   - Dataset is reloaded on every query.  
   - Ensures freshness (target <40 ms per query at 250k lines).  

Algorithms Tested:
------------------
- set
- list
- mmap
- binary
- grep

Outputs:
--------
- CSV file with average query time for each (size, algorithm, mode).
- Optional throughput (QPS) benchmark.

Usage:
------
    python3 -m benchmarks.benchmark --sizes 1000 5000 10000 50000 250000 --out ./benchmarks/results.csv
    python3 -m benchmarks.benchmark --sizes 1000 5000 10000 50000 250000 --out ./benchmarks/results.csv --qps
"""

from typing import List
import time
import csv
import argparse
import os
import random
from server import search_algorithms as sa

ALGORITHMS = ["set", "list", "mmap", "binary", "grep"]


def make_testfile(path: str, n: int) -> None:
    """Generate a test file with n dummy lines.

    Args:
        path (str): Output file path.
        n (int): Number of lines to generate.
    """
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(f"line_{i}\n")


def time_single(path: str, algorithm: str, needles: List[str], reread: bool) -> float:
    """Measure average query time for one algorithm and file.

    Args:
        path (str): Path to test file.
        algorithm (str): Algorithm to benchmark.
        needles (List[str]): Queries to search.
        reread (bool): If True, reload dataset per query.

    Returns:
        float: Average milliseconds per query.
    """
    t0 = time.perf_counter()
    if reread:
        # Reload each time
        for n in needles:
            if algorithm == "set":
                data = sa.load_lines_set(path)
                _ = n in data
            elif algorithm == "list":
                data = sa.load_lines_list(path)
                _ = n in data
            elif algorithm == "mmap":
                _ = sa.mmap_search(path, n)
            elif algorithm == "binary":
                lines = sorted(sa.load_lines_list(path))
                _ = sa.binary_search_sorted(lines, n)
            elif algorithm == "grep":
                _ = sa.grep_subprocess(path, n)
    else:
        # Cache dataset once
        if algorithm == "set":
            data = sa.load_lines_set(path)
            results = [n in data for n in needles]
        elif algorithm == "list":
            data = sa.load_lines_list(path)
            results = [n in data for n in needles]
        elif algorithm == "mmap":
            results = [sa.mmap_search(path, n) for n in needles]
        elif algorithm == "binary":
            lines = sorted(sa.load_lines_list(path))
            results = [sa.binary_search_sorted(lines, n) for n in needles]
        elif algorithm == "grep":
            results = [sa.grep_subprocess(path, n) for n in needles]
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0 / len(needles)


def run_series(sizes: List[int], algorithms: List[str], out_csv: str) -> None:
    """Run benchmark across file sizes and algorithms.

    Args:
        sizes (List[int]): List of dataset sizes.
        algorithms (List[str]): Algorithms to test.
        out_csv (str): Output CSV file path.
    """
    rows = []
    tmpdir = "./benchmarks/tmp"
    os.makedirs(tmpdir, exist_ok=True)

    for size in sizes:
        testfile = os.path.join(tmpdir, f"file_{size}.txt")
        make_testfile(testfile, size)
        lines = sa.load_lines_list(testfile)
        needles = [random.choice(lines) for _ in range(20)]
        needles += [f"nonexistent_{i}" for i in range(5)]

        for alg in algorithms:
            for reread in [False, True]:
                ms = time_single(testfile, alg, needles, reread)
                mode = "reread" if reread else "cache"
                rows.append({"size": size, "algorithm": alg, "mode": mode, "avg_ms": ms})
                print(f"{alg} size={size} mode={mode} avg_ms={ms:.3f} ms")

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["size", "algorithm", "mode", "avg_ms"])
        writer.writeheader()
        writer.writerows(rows)


def throughput_test(path: str, algorithm: str, qps: int, duration_sec: int = 3) -> float:
    """Measure achieved queries per second under load.

    Args:
        path (str): Path to dataset file.
        algorithm (str): Algorithm to test.
        qps (int): Target queries per second.
        duration_sec (int): Duration of test.

    Returns:
        float: Achieved queries per second.
    """
    lines = sa.load_lines_list(path)
    needles = [random.choice(lines) for _ in range(qps)]
    start = time.perf_counter()
    end = start + duration_sec
    count = 0
    while time.perf_counter() < end:
        for n in needles:
            if algorithm == "set":
                data = sa.load_lines_set(path)
                _ = n in data
            elif algorithm == "list":
                data = sa.load_lines_list(path)
                _ = n in data
            elif algorithm == "mmap":
                _ = sa.mmap_search(path, n)
            elif algorithm == "binary":
                lines2 = sorted(sa.load_lines_list(path))
                _ = sa.binary_search_sorted(lines2, n)
            elif algorithm == "grep":
                _ = sa.grep_subprocess(path, n)
            count += 1
    elapsed = time.perf_counter() - start
    return count / elapsed


def run_qps(path: str, algorithms: List[str], qps_levels: List[int], out_csv: str) -> None:
    """Run throughput test and save results.

    Args:
        path (str): Path to dataset file.
        algorithms (List[str]): Algorithms to test.
        qps_levels (List[int]): List of target QPS levels.
        out_csv (str): Output CSV file path.
    """
    rows = []
    for alg in algorithms:
        for qps in qps_levels:
            avg_qps = throughput_test(path, alg, qps, duration_sec=3)
            rows.append({"algorithm": alg, "qps_target": qps, "qps_achieved": avg_qps})
            print(f"{alg} qps_target={qps} qps_achieved={avg_qps:.1f}")

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["algorithm", "qps_target", "qps_achieved"])
        writer.writeheader()
        writer.writerows(rows)


def main():
    """CLI entry point for benchmark script."""
    parser = argparse.ArgumentParser(description="Benchmark search algorithms")
    parser.add_argument("--out", default="./benchmarks/results.csv", help="CSV path for results")
    parser.add_argument("--sizes", nargs="+", type=int,
                        default=[1000, 5000, 10000, 50000, 250000, 1000000],
                        help="File sizes to test")
    parser.add_argument("--qps", action="store_true", help="Run throughput benchmark")
    args = parser.parse_args()

    run_series(args.sizes, ALGORITHMS, args.out)
    print(f"✅ Wrote results to {args.out}")

    if args.qps:
        bigfile = "./benchmarks/tmp/file_250000.txt"
        run_qps(bigfile, ALGORITHMS, [10, 50, 100, 200, 500], "./benchmarks/results_qps.csv")
        print("✅ Wrote QPS results to ./benchmarks/results_qps.csv")


if __name__ == "__main__":
    main()
