"""
Generate Benchmark Report
=========================

This module generates a professional PDF report from the CSV outputs of
`benchmark.py`.

Overview
--------
- Reads benchmark results (series + optional QPS throughput).
- Produces:
    * Results tables
    * Bar charts with threshold lines
    * Throughput (QPS) line chart (optional)
    * Compliance checks for 250k rows
    * Summary of best algorithms per mode

Thresholds (from task specification)
------------------------------------
- Cache mode (`REREAD_ON_QUERY=False`): < 0.5 ms/query at 250,000 rows
- Reread mode (`REREAD_ON_QUERY=True`): < 40 ms/query at 250,000 rows

Usage
-----
Run from the project root:

    python3 -m benchmarks.generate_report \
        --csv ./benchmarks/results.csv \
        --out ./reports/speed_report.pdf \
        --qps ./benchmarks/results_qps.csv
"""

import csv
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import argparse
import os
from collections import defaultdict
from typing import List, Dict, Any

# Performance thresholds
CACHE_THRESHOLD_MS = 0.5
REREAD_THRESHOLD_MS = 40.0


def read_csv(path: str) -> List[Dict[str, Any]]:
    """
    Read benchmark series CSV results.

    Args:
        path (str): Path to CSV file.

    Returns:
        List[Dict[str, Any]]: Parsed rows, each with keys:
            - size (int): dataset size
            - algorithm (str): algorithm name
            - mode (str): "cache" or "reread"
            - avg_ms (float): average execution time in ms
    """
    rows = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                rows.append(
                    {
                        "size": int(row["size"]),
                        "algorithm": row["algorithm"],
                        "mode": row["mode"],
                        "avg_ms": float(row["avg_ms"]),
                    }
                )
            except (KeyError, ValueError) as e:
                print(f"⚠️ Skipping malformed row in {path}: {row} ({e})")
    return rows


def read_qps_csv(path: str) -> List[Dict[str, Any]]:
    """
    Read throughput benchmark CSV results.

    Args:
        path (str): Path to QPS CSV file.

    Returns:
        List[Dict[str, Any]]: Rows with keys:
            - algorithm (str)
            - qps_target (int)
            - qps_achieved (float)
    """
    rows = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                rows.append(
                    {
                        "algorithm": row["algorithm"],
                        "qps_target": int(row["qps_target"]),
                        "qps_achieved": float(row["qps_achieved"]),
                    }
                )
            except (KeyError, ValueError) as e:
                print(f"⚠️ Skipping malformed row in {path}: {row} ({e})")
    return rows


def create_plots(rows: List[Dict[str, Any]], out_dir: str) -> List[str]:
    """
    Create bar charts for each (mode, size) combination with threshold lines.

    Args:
        rows (List[Dict[str, Any]]): Benchmark results.
        out_dir (str): Directory where charts will be saved.

    Returns:
        List[str]: Paths to generated chart PNG files.
    """
    os.makedirs(out_dir, exist_ok=True)
    imgs = []
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["mode"], r["size"])].append(r)

    for (mode, size), group in grouped.items():
        algs = [g["algorithm"] for g in group]
        vals = [g["avg_ms"] for g in group]

        plt.figure(figsize=(6, 4))
        plt.bar(algs, vals, color="skyblue")
        plt.axhline(
            CACHE_THRESHOLD_MS if mode == "cache" else REREAD_THRESHOLD_MS,
            color="red",
            linestyle="--",
            label="Threshold",
        )
        plt.title(f"Mode={mode.upper()} | File size {size}")
        plt.ylabel("ms/query")
        plt.xlabel("Algorithm")
        plt.legend()
        plt.tight_layout()

        png_path = os.path.join(out_dir, f"plot_{mode}_{size}.png")
        plt.savefig(png_path)
        plt.close()
        imgs.append((mode, size, png_path))
    return imgs


def create_qps_plot(rows: List[Dict[str, Any]], out_path: str) -> str:
    """
    Generate a throughput (QPS) line chart.

    Args:
        rows (List[Dict[str, Any]]): Throughput results.
        out_path (str): Path to save PNG file.

    Returns:
        str: Path to saved chart.
    """
    algs = sorted(set(r["algorithm"] for r in rows))
    plt.figure(figsize=(6, 4))
    for alg in algs:
        data = [r for r in rows if r["algorithm"] == alg]
        xs = [r["qps_target"] for r in data]
        ys = [r["qps_achieved"] for r in data]
        plt.plot(xs, ys, marker="o", label=alg)
    plt.title("Throughput Test (QPS achieved vs target)")
    plt.xlabel("Target QPS")
    plt.ylabel("Achieved QPS")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    return out_path


def best_per_mode(rows: List[Dict[str, Any]]) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """
    Find the best algorithm per file size for each mode.

    Args:
        rows (List[Dict[str, Any]]): Benchmark rows.

    Returns:
        Dict[str, Dict[int, Dict[str, Any]]]:
            {mode: {size: best_row}}
    """
    best = defaultdict(dict)
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["mode"], r["size"])].append(r)
    for (mode, size), group in grouped.items():
        best[mode][size] = min(group, key=lambda x: x["avg_ms"])
    return best


def best_qps(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Find the algorithm with the highest throughput overall.

    Args:
        rows (List[Dict[str, Any]]): Throughput results.

    Returns:
        Dict[str, Any]: Best throughput row.
    """
    return max(rows, key=lambda r: r["qps_achieved"])


def threshold_compliance(rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Check compliance with thresholds for 250k rows.

    Args:
        rows (List[Dict[str, Any]]): Benchmark results.

    Returns:
        Dict[str, str]: Mode -> compliance message.
    """
    compliance = {}
    for mode, threshold in [("cache", CACHE_THRESHOLD_MS), ("reread", REREAD_THRESHOLD_MS)]:
        candidates = [r for r in rows if r["size"] == 250000 and r["mode"] == mode]
        if not candidates:
            compliance[mode] = "⚠️ No data for 250k rows"
            continue
        best = min(candidates, key=lambda r: r["avg_ms"])
        if best["avg_ms"] <= threshold:
            compliance[mode] = f"✅ PASSED ({best['algorithm']} = {best['avg_ms']:.3f} ms)"
        else:
            compliance[mode] = f"❌ FAILED ({best['algorithm']} = {best['avg_ms']:.3f} ms, target {threshold} ms)"
    return compliance


def create_pdf(
    rows: List[Dict[str, Any]],
    images: List[str],
    out_pdf: str,
    qps_img: str = None,
    qps_rows: List[Dict[str, Any]] = None,
) -> None:
    """
    Generate final PDF report.

    Args:
        rows (List[Dict[str, Any]]): Benchmark results.
        images (List[str]): Paths to generated charts.
        out_pdf (str): Output PDF file path.
        qps_img (str, optional): Path to QPS chart PNG.
        qps_rows (List[Dict[str, Any]], optional): QPS results.
    """
    c = canvas.Canvas(out_pdf, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 770, "Algorithmic Sciences - Speed Test Report")
    c.setFont("Helvetica", 10)
    c.drawString(50, 755, "Benchmarked algorithms across cache and reread modes")

    # Results table
    y = 730
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "Mode")
    c.drawString(100, y, "Size")
    c.drawString(150, y, "Algorithm")
    c.drawString(250, y, "avg_ms")
    y -= 12
    c.setFont("Helvetica", 9)
    for r in rows:
        c.drawString(50, y, r["mode"])
        c.drawString(100, y, str(r["size"]))
        c.drawString(150, y, r["algorithm"])
        c.drawString(250, y, f"{r['avg_ms']:.3f}")
        y -= 10
        if y < 100:
            c.showPage()
            y = 750

    # Charts
    for mode, size, img in images:
        c.showPage()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, 770, f"Mode={mode.upper()} | File size {size}")
        c.drawImage(ImageReader(img), 50, 350, width=500, height=350)

    # QPS chart
    if qps_img:
        c.showPage()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, 770, "Throughput test (queries per second)")
        c.drawImage(ImageReader(qps_img), 50, 350, width=500, height=350)

    # Summary
    c.showPage()
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 770, "Summary of Best Algorithms & Compliance")

    best_size = best_per_mode(rows)
    y = 740
    for mode, sizes in best_size.items():
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, f"Mode={mode.upper()}")
        y -= 14
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "File Size")
        c.drawString(150, y, "Best Algorithm")
        c.drawString(300, y, "avg_ms")
        y -= 14
        c.setFont("Helvetica", 10)
        for size, rec in sizes.items():
            c.drawString(50, y, str(size))
            c.drawString(150, y, rec["algorithm"])
            c.drawString(300, y, f"{rec['avg_ms']:.3f}")
            y -= 12
        y -= 20

    # Threshold compliance
    compliance = threshold_compliance(rows)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Threshold Compliance (250k rows)")
    y -= 16
    c.setFont("Helvetica", 10)
    for mode, msg in compliance.items():
        c.drawString(50, y, f"{mode.upper()}: {msg}")
        y -= 14

    if qps_rows:
        best_throughput = best_qps(qps_rows)
        y -= 20
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Best throughput algorithm overall:")
        y -= 14
        c.setFont("Helvetica", 10)
        c.drawString(
            50,
            y,
            f"{best_throughput['algorithm']} "
            f"with {best_throughput['qps_achieved']:.1f} QPS "
            f"(target {best_throughput['qps_target']})",
        )

    c.save()


def main():
    """
    CLI entry point for report generator.

    Example:
        python3 -m benchmarks.generate_report \
            --csv ./benchmarks/results.csv \
            --out ./reports/speed_report.pdf \
            --qps ./benchmarks/results_qps.csv
    """
    parser = argparse.ArgumentParser(description="Generate benchmark report (PDF)")
    parser.add_argument("--csv", required=True, help="CSV file from benchmark.py (series)")
    parser.add_argument("--out", default="./reports/speed_report.pdf", help="Output PDF path")
    parser.add_argument("--qps", help="Optional QPS CSV for throughput chart")
    args = parser.parse_args()

    rows = read_csv(args.csv)
    if not rows:
        raise RuntimeError(f"No valid rows found in {args.csv}")

    images = create_plots(rows, "./reports/plots")

    qps_img, qps_rows = None, None
    if args.qps:
        qps_rows = read_qps_csv(args.qps)
        if qps_rows:
            qps_img = create_qps_plot(qps_rows, "./reports/plots/qps.png")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    create_pdf(rows, images, args.out, qps_img, qps_rows)
    print(f"✅ Wrote PDF report to {args.out}")


if __name__ == "__main__":
    main()
