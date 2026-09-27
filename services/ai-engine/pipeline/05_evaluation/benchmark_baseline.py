"""Reproducible filter, queue, and real-Forge generation timing for issue #68."""

import argparse
import csv
import json
import platform
import statistics
import threading
import uuid
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


def latency_summary(samples):
    """Return report-ready latency statistics for a nonempty sample."""
    if not samples or any(isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
                          for value in samples):
        raise ValueError("latency samples must be nonnegative numbers")
    values = np.asarray(samples, dtype=float)
    return {
        "samples": int(values.size),
        "min_s": float(values.min()),
        "p50_s": float(np.percentile(values, 50)),
        "p95_s": float(np.percentile(values, 95)),
        "max_s": float(values.max()),
    }


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


def generation_trial_order(steps, repeats):
    """Return a cyclic order so each step count occupies each trial position."""
    if (not steps or len(set(steps)) != len(steps)
            or any(isinstance(step, bool) or not isinstance(step, int) or step < 1
                   for step in steps)):
        raise ValueError("steps must contain unique positive integers")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    steps = tuple(steps)
    return [
        (trial + 1, position + 1, steps[(trial + position) % len(steps)])
        for trial in range(repeats)
        for position in range(len(steps))
    ]


def record_generation_baseline(output_dir, ai_url, steps=(10, 20, 30), repeats=3,
                               sampler_name="DPM++ 2M", scheduler="Karras",
                               forge_model="record when running", max_attempts=3,
                               cooldown_seconds=2.0):
    """Measure real HTTP generation by step count; never use mock results as GPU evidence."""
    output_dir.mkdir(parents=True, exist_ok=True)
    endpoint = ai_url.rstrip("/") + "/forge/txt2img"
    rows = []

    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    if cooldown_seconds < 0:
        raise ValueError("cooldown_seconds must be nonnegative")

    def generate(step_count):
        for attempt in range(1, max_attempts + 1):
            start = perf_counter()
            try:
                response = requests.post(endpoint, json={
                    "prompt": "a small tree", "steps": step_count, "seed": 12345,
                    "width": 512, "height": 512, "sampler_name": sampler_name,
                    "scheduler": scheduler,
                }, timeout=180)
                elapsed = perf_counter() - start
                response.raise_for_status()
                result = response.json()
                if not result.get("images") or not isinstance(result.get("seed_used"), int):
                    raise ValueError("AI engine did not return an image and seed_used")
                threading.Event().wait(cooldown_seconds)
                return elapsed, attempt - 1
            except requests.RequestException:
                if attempt == max_attempts:
                    raise
                threading.Event().wait(max(5.0, cooldown_seconds))

    trial_order = generation_trial_order(steps, repeats)
    generate(steps[0])  # Exclude model loading and first-request compilation from the trials.
    for trial, position, step_count in trial_order:
        latency, retries = generate(step_count)
        rows.append({"mode": "single", "steps": step_count, "trial": trial,
                     "position": position, "retries": retries, "latency_s": latency})

    _write_csv(output_dir / "generation_by_steps_raw.csv", rows,
               ["mode", "steps", "trial", "position", "retries", "latency_s"])
    summary = []
    for step_count in steps:
        samples = [row["latency_s"] for row in rows if row["mode"] == "single" and row["steps"] == step_count]
        summary.append({"steps": step_count, "p50_s": float(np.percentile(samples, 50)),
                        "p95_s": float(np.percentile(samples, 95))})
    _write_csv(output_dir / "generation_by_steps_summary.csv", summary, ["steps", "p50_s", "p95_s"])
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.plot([row["steps"] for row in summary], [row["p50_s"] for row in summary], marker="o", label="p50")
    axis.plot([row["steps"] for row in summary], [row["p95_s"] for row in summary], marker="o", label="p95")
    axis.set(xlabel="Generation steps (count)", ylabel="HTTP response time (s)",
             title="Real Forge generation time by diffusion steps")
    axis.legend()
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "generation_by_steps.png", dpi=160)
    plt.close(figure)
    (output_dir / "generation_by_steps_metadata.json").write_text(json.dumps({
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint, "mode": "real_forge_steps", "repeats_per_step": repeats,
        "warmup_steps": steps[0],
        "trial_order": [step_count for _, _, step_count in trial_order],
        "max_attempts": max_attempts, "cooldown_seconds": cooldown_seconds,
        "successful_trial_retries": sum(row["retries"] for row in rows),
        "sampler_name": sampler_name, "scheduler": scheduler, "forge_model": forge_model,
        "machine": platform.platform(), "python": platform.python_version(),
        "note": "These values are valid only when ai-engine points to a real Forge/GPU model.",
    }, indent=2) + "\n", encoding="utf-8")
    return summary


def _csrf_headers(session):
    token = session.cookies.get("csrf_token")
    if not token:
        raise ValueError("backend did not provide a csrf_token cookie")
    return {"X-CSRFToken": token}


def _authenticated_session(backend_url):
    """Create an isolated benchmark account and return its logged-in session."""
    session = requests.Session()
    base = backend_url.rstrip("/")
    response = session.get(base + "/", timeout=10)
    response.raise_for_status()
    suffix = uuid.uuid4().hex[:12]
    credentials = {
        "email": f"benchmark-{suffix}@example.invalid",
        "displayName": f"benchmark-{suffix}",
        "password": "benchmark-password-68",
    }
    response = session.post(base + "/api/auth/register", json=credentials,
                            headers=_csrf_headers(session), timeout=10)
    response.raise_for_status()
    response = session.post(base + "/api/auth/login", json={
        "email": credentials["email"], "password": credentials["password"],
    }, headers=_csrf_headers(session), timeout=10)
    response.raise_for_status()
    return session


def _session_with_cookies(source):
    session = requests.Session()
    session.cookies.update(source.cookies)
    return session


def record_queue_comparison(output_dir, backend_url, ai_url, batches=3,
                            jobs_per_batch=5, poll_interval=0.25, timeout=300):
    """Measure synchronous and queued HTTP paths against the same Forge target.

    The synchronous path calls the AI engine directly, matching the blocking work
    done before the backend queue. The queued path measures both the immediate 202
    response and the time until each job reaches ``done``. Run the mock Forge with
    a fixed delay for reproducible queue evidence; real Forge step timing is kept
    separate because a mock cannot prove the relationship between steps and GPU
    processing time.
    """
    for name, value in (("batches", batches), ("jobs_per_batch", jobs_per_batch)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if poll_interval <= 0 or timeout <= 0:
        raise ValueError("poll_interval and timeout must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    backend = backend_url.rstrip("/")
    ai_endpoint = ai_url.rstrip("/") + "/forge/txt2img"
    authenticated = _authenticated_session(backend)
    raw_rows = []
    poll_latencies = []

    def synchronous_request(batch, position):
        started = perf_counter()
        response = requests.post(ai_endpoint, json={
            "prompt": f"queue benchmark {batch}-{position}", "steps": 20,
            "seed": 680000 + batch * 100 + position, "width": 512, "height": 512,
        }, timeout=timeout)
        latency = perf_counter() - started
        response.raise_for_status()
        payload = response.json()
        if not payload.get("images") or not isinstance(payload.get("seed_used"), int):
            raise ValueError("synchronous AI response did not contain an image and seed_used")
        return latency

    for batch in range(1, batches + 1):
        with ThreadPoolExecutor(max_workers=jobs_per_batch) as workers:
            futures = [workers.submit(synchronous_request, batch, position)
                       for position in range(1, jobs_per_batch + 1)]
            for position, future in enumerate(futures, 1):
                latency = future.result()
                raw_rows.append({
                    "phase": "synchronous_response", "batch": batch, "job": position,
                    "job_id": "", "latency_s": latency, "completion_s": latency,
                })

    def submit_job(batch, position):
        session = _session_with_cookies(authenticated)
        started = perf_counter()
        response = session.post(backend + "/api/generate", json={
            "prompt": f"queue benchmark {batch}-{position}", "steps": 20,
            "seed": 690000 + batch * 100 + position, "width": 512, "height": 512,
        }, headers=_csrf_headers(session), timeout=10)
        latency = perf_counter() - started
        if response.status_code != 202:
            raise ValueError(f"queued submission returned {response.status_code}: {response.text}")
        payload = response.json()
        if not isinstance(payload.get("job_id"), int):
            raise ValueError("queued submission did not return an integer job_id")
        return payload["job_id"], latency

    for batch in range(1, batches + 1):
        batch_started = perf_counter()
        with ThreadPoolExecutor(max_workers=jobs_per_batch) as workers:
            futures = [workers.submit(submit_job, batch, position)
                       for position in range(1, jobs_per_batch + 1)]
            submitted = [future.result() for future in futures]

        outstanding = {job_id: position for position, (job_id, _) in enumerate(submitted, 1)}
        completed = {}
        deadline = batch_started + timeout
        while outstanding:
            if perf_counter() >= deadline:
                raise TimeoutError(f"queue batch {batch} did not finish within {timeout} seconds")
            for job_id in tuple(outstanding):
                started = perf_counter()
                response = authenticated.get(backend + f"/api/jobs/{job_id}", timeout=10)
                poll_latencies.append(perf_counter() - started)
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") == "failed":
                    raise RuntimeError(f"job {job_id} failed: {payload.get('error')}")
                if payload.get("status") == "done":
                    completed[job_id] = perf_counter() - batch_started
                    outstanding.pop(job_id)
            if outstanding:
                threading.Event().wait(poll_interval)

        for position, (job_id, submit_latency) in enumerate(submitted, 1):
            raw_rows.append({
                "phase": "queued_submission", "batch": batch, "job": position,
                "job_id": job_id, "latency_s": submit_latency,
                "completion_s": completed[job_id],
            })

    synchronous = [row["latency_s"] for row in raw_rows if row["phase"] == "synchronous_response"]
    submissions = [row["latency_s"] for row in raw_rows if row["phase"] == "queued_submission"]
    completions = [row["completion_s"] for row in raw_rows if row["phase"] == "queued_submission"]
    summary = []
    for endpoint, samples in (
        ("POST ai-engine /forge/txt2img (synchronous)", synchronous),
        ("POST backend /api/generate (queued 202)", submissions),
        ("GET backend /api/jobs/<id> (poll)", poll_latencies),
        ("queued job completion", completions),
    ):
        summary.append({"endpoint": endpoint, **latency_summary(samples)})

    _write_csv(output_dir / "queue_comparison_raw.csv", raw_rows,
               ["phase", "batch", "job", "job_id", "latency_s", "completion_s"])
    _write_csv(output_dir / "queue_comparison_summary.csv", summary,
               ["endpoint", "samples", "min_s", "p50_s", "p95_s", "max_s"])

    sync_stats = latency_summary(synchronous)
    submit_stats = latency_summary(submissions)
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    labels = ["Synchronous\nresponse", "Queued\nsubmission"]
    median_values = [sync_stats["p50_s"], submit_stats["p50_s"]]
    bars = axes[0].bar(labels, median_values,
                       yerr=[sync_stats["p95_s"] - sync_stats["p50_s"],
                             submit_stats["p95_s"] - submit_stats["p50_s"]], capsize=5)
    axes[0].set_yscale("log")
    for bar, value in zip(bars, median_values):
        axes[0].text(bar.get_x() + bar.get_width() / 2, value * 1.15,
                     f"{value:.3f} s", ha="center", va="bottom")
    axes[0].set(ylabel="HTTP response time (s)", title="Queue response time: p50 with p95 cap")
    axes[0].grid(axis="y", alpha=0.25)
    completion_by_rank = []
    for rank in range(jobs_per_batch):
        values = []
        for batch in range(1, batches + 1):
            batch_values = sorted(
                row["completion_s"] for row in raw_rows
                if row["phase"] == "queued_submission" and row["batch"] == batch
            )
            values.append(batch_values[rank])
        completion_by_rank.append(float(np.median(values)))
    axes[1].plot(range(1, jobs_per_batch + 1), completion_by_rank, marker="o")
    axes[1].set(xlabel="Actual completion rank in batch", ylabel="Median time until done (s)",
                title="One backend worker completes jobs sequentially")
    axes[1].set_xticks(range(1, jobs_per_batch + 1))
    axes[1].grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "queue_comparison.png", dpi=160)
    plt.close(figure)

    metadata = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend_url": backend, "ai_url": ai_url.rstrip("/"),
        "batches": batches, "jobs_per_batch": jobs_per_batch,
        "poll_interval_s": poll_interval, "timeout_s": timeout,
        "steps": 20, "image_size_px": [512, 512],
        "machine": platform.platform(), "python": platform.python_version(),
        "interpretation": (
            "Synchronous latency measures direct AI-engine response time; queued submission "
            "measures time until backend returns HTTP 202. Completion time remains bounded by "
            "the single worker and Forge processing time."
        ),
    }
    (output_dir / "queue_comparison_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ai-url", help="AI engine URL; omit to run only the filter benchmark")
    parser.add_argument("--backend-url", help="Backend URL; with --ai-url, measure before/after queue")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--batches", type=int, default=3)
    parser.add_argument("--jobs-per-batch", type=int, default=5)
    parser.add_argument("--poll-interval", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--measure-real-steps", action="store_true",
                        help="Measure generation time by steps; use only with a real Forge target")
    parser.add_argument("--sampler-name", default="DPM++ 2M")
    parser.add_argument("--scheduler", default="Karras")
    parser.add_argument("--forge-model", default="record when running")
    arguments = parser.parse_args()
    result = record_filter_baseline(arguments.output, repeats=arguments.repeats)
    print(f"Box filter: {result['speedup']:.2f}x speedup with separable convolution")
    if arguments.backend_url:
        if not arguments.ai_url:
            parser.error("--backend-url requires --ai-url")
        summary = record_queue_comparison(
            arguments.output, arguments.backend_url, arguments.ai_url,
            batches=arguments.batches, jobs_per_batch=arguments.jobs_per_batch,
            poll_interval=arguments.poll_interval, timeout=arguments.timeout,
        )
        print(f"Queue: measured {len(summary)} endpoint/completion groups")
    if arguments.measure_real_steps or (arguments.ai_url and not arguments.backend_url):
        if not arguments.ai_url:
            parser.error("--measure-real-steps requires --ai-url")
        summary = record_generation_baseline(
            arguments.output, arguments.ai_url, sampler_name=arguments.sampler_name,
            scheduler=arguments.scheduler, forge_model=arguments.forge_model,
        )
        print(f"Generation: measured {len(summary)} real-Forge step settings")


if __name__ == "__main__":
    main()
