"""Reproducible pre-queue filter and generation timing for issue #68."""

import argparse
import csv
import json
import platform
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import cv2
import matplotlib
import numpy as np
import requests

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def benchmark_box_filter(image, kernel_size=15, repeats=10):
    """Compare a true 2D box convolution with two separable 1D passes."""
    if image.dtype != np.uint8 or image.ndim != 2 or image.size == 0:
        raise ValueError("image must be a nonempty grayscale uint8 array")
    if isinstance(kernel_size, bool) or not isinstance(kernel_size, int) or kernel_size < 3 or kernel_size % 2 == 0:
        raise ValueError("kernel_size must be an odd integer at least 3")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 2:
        raise ValueError("repeats must be at least 2")

    one_dimensional = np.full((kernel_size, 1), 1 / kernel_size, dtype=np.float32)
    two_dimensional = one_dimensional @ one_dimensional.T

    def direct():
        return cv2.filter2D(image, cv2.CV_32F, two_dimensional, borderType=cv2.BORDER_REFLECT_101)

    def separable():
        return cv2.sepFilter2D(image, cv2.CV_32F, one_dimensional, one_dimensional, borderType=cv2.BORDER_REFLECT_101)

    operations = {"box_2d": direct, "box_separable": separable}
    timings = {name: [] for name in operations}
    outputs = {name: operation() for name, operation in operations.items()}
    for trial in range(repeats):
        order = tuple(operations.items())
        for name, operation in (order if trial % 2 == 0 else reversed(order)):
            start = perf_counter()
            operation()
            timings[name].append((perf_counter() - start) * 1000)

    median_2d = statistics.median(timings["box_2d"])
    median_separable = statistics.median(timings["box_separable"])
    return {
        "box_2d_ms": median_2d,
        "box_separable_ms": median_separable,
        "speedup": median_2d / median_separable,
        "max_pixel_difference": float(np.max(np.abs(outputs["box_2d"] - outputs["box_separable"]))),
    }


def _write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _save_bar_chart(path, names, values, ylabel, title):
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.bar(names, values)
    axis.set(ylabel=ylabel, title=title)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def record_filter_baseline(output_dir, image_size=1024, kernel_size=15, repeats=10):
    """Save measured filter timings, graph, and machine context."""
    image = np.random.default_rng(68).integers(0, 256, (image_size, image_size), dtype=np.uint8)
    result = benchmark_box_filter(image, kernel_size, repeats)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "box_filter.csv", [result], list(result))
    _save_bar_chart(
        output_dir / "box_filter.png",
        ["2D box", "Separable box"],
        [result["box_2d_ms"], result["box_separable_ms"]],
        "Median processing time (ms)", "Box filter timing",
    )
    metadata = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "machine": platform.platform(), "python": platform.python_version(),
        "opencv": cv2.__version__, "image_size_px": image_size,
        "kernel_size_px": kernel_size, "repeats": repeats,
        "input": "deterministic synthetic grayscale image (RNG seed 68)",
    }
    (output_dir / "box_filter_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return result


def record_generation_baseline(output_dir, ai_url, steps=(10, 20, 30), repeats=3):
    """Measure real HTTP generation before queue deployment; never use a mock for report data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    endpoint = ai_url.rstrip("/") + "/forge/txt2img"
    rows = []

    def generate(step_count):
        start = perf_counter()
        response = requests.post(endpoint, json={
            "prompt": "a small tree", "steps": step_count, "seed": 12345,
            "width": 512, "height": 512,
        }, timeout=180)
        elapsed = perf_counter() - start
        response.raise_for_status()
        result = response.json()
        if not result.get("images") or not isinstance(result.get("seed_used"), int):
            raise ValueError("AI engine did not return an image and seed_used")
        return elapsed

    for step_count in steps:
        for trial in range(1, repeats + 1):
            rows.append({"mode": "single", "steps": step_count, "trial": trial,
                         "latency_s": generate(step_count)})

    with ThreadPoolExecutor(max_workers=2) as workers:
        start = perf_counter()
        pair = list(workers.map(generate, (steps[0], steps[0])))
        total = perf_counter() - start
    for trial, elapsed in enumerate(pair, 1):
        rows.append({"mode": "two_users_before_queue", "steps": steps[0],
                     "trial": trial, "latency_s": elapsed})

    _write_csv(output_dir / "generation_before_queue.csv", rows, ["mode", "steps", "trial", "latency_s"])
    summary = []
    for step_count in steps:
        samples = [row["latency_s"] for row in rows if row["mode"] == "single" and row["steps"] == step_count]
        summary.append({"steps": step_count, "p50_s": float(np.percentile(samples, 50)),
                        "p95_s": float(np.percentile(samples, 95))})
    _write_csv(output_dir / "generation_summary.csv", summary, ["steps", "p50_s", "p95_s"])
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.plot([row["steps"] for row in summary], [row["p50_s"] for row in summary], marker="o", label="p50")
    axis.plot([row["steps"] for row in summary], [row["p95_s"] for row in summary], marker="o", label="p95")
    axis.set(xlabel="Generation steps (count)", ylabel="HTTP response time (s)",
             title="Generation timing before job queue")
    axis.legend()
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "generation_before_queue.png", dpi=160)
    plt.close(figure)
    (output_dir / "generation_metadata.json").write_text(json.dumps({
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint, "mode": "before_queue", "repeats_per_step": repeats,
        "two_user_wall_time_s": total, "two_user_latencies_s": pair,
        "machine": platform.platform(), "python": platform.python_version(),
        "note": "Record the Forge host, model, sampler, and deployment configuration with the report.",
    }, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ai-url", help="Real AI engine URL; omit to run only the filter benchmark")
    parser.add_argument("--repeats", type=int, default=10)
    arguments = parser.parse_args()
    result = record_filter_baseline(arguments.output, repeats=arguments.repeats)
    print(f"Box filter: {result['speedup']:.2f}x speedup with separable convolution")
    if arguments.ai_url:
        summary = record_generation_baseline(arguments.output, arguments.ai_url)
        print(f"Generation: measured {len(summary)} step settings before queue")


if __name__ == "__main__":
    main()
