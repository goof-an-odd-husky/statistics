import json
import glob
import os
import csv
import statistics

NAV_FILES_PATTERN = "data/nav_metrics_*.json"
RES_FILES_PATTERN = "data/resource_metrics_*.jsonl"
OUTPUT_CSV = "results_per_run.csv"
OUTPUT_JSON = "results_global_summary.json"


def calculate_stats(data_list):
    data = [x for x in data_list if x is not None]
    if not data:
        return None

    n = len(data)
    mean = statistics.mean(data)
    std = statistics.stdev(data) if n > 1 else 0.0

    data_sorted = sorted(data)

    p5_idx = max(0, int(n * 0.05))
    p95_idx = min(n - 1, int(n * 0.95))

    q1_idx = max(0, int(n * 0.25))
    q3_idx = min(n - 1, int(n * 0.75))

    return {
        "total_samples": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": round(data_sorted[0], 4),
        "p5": round(data_sorted[p5_idx], 4),
        "q1": round(data_sorted[q1_idx], 4),
        "median": round(statistics.median(data_sorted), 4),
        "q3": round(data_sorted[q3_idx], 4),
        "p95": round(data_sorted[p95_idx], 4),
        "max": round(data_sorted[-1], 4),
    }


def main():
    print("Looking for files...")
    nav_files = glob.glob(NAV_FILES_PATTERN)
    res_files = glob.glob(RES_FILES_PATTERN)

    if not nav_files or not res_files:
        print("Error: Required data files not found.")
        return

    resources = []
    with open(res_files[0], "r") as f:
        for line in f:
            if line.strip():
                resources.append(json.loads(line))
    resources.sort(key=lambda x: x["time_seconds"])

    global_cpu_measurements = []
    global_ram_measurements = []
    global_freq_measurements = []

    per_run_results = []
    for nav_file in nav_files:
        with open(nav_file, "r") as f:
            nav = json.load(f)

        t_start, t_end = nav.get("nav_start_time", 0), nav.get("last_update_time", 0)

        history = nav.get("control_frame_ms_history", nav.get("elapsed_ms_history", []))
        run_freqs = [1000.0 / ms for ms in history if ms > 0]
        global_freq_measurements.extend(run_freqs)

        run_resources = [r for r in resources if t_start <= r["time_seconds"] <= t_end]
        cpu_list = [r["cpu_percent"] for r in run_resources]
        ram_list = [r["ram_mb"] for r in run_resources]
        global_cpu_measurements.extend(cpu_list)
        global_ram_measurements.extend(ram_list)

        per_run_results.append(
            {
                "run_id": os.path.basename(nav_file),
                "status": nav.get("status", "unknown"),
                "is_success": ("success" in nav.get("status")),
                "time_s": nav.get("total_time_s", 0),
                "path_efficiency": nav.get("path_efficiency", None),
                "freq_hz_avg": statistics.mean(run_freqs) if run_freqs else 0,
                "cpu_percent_avg": statistics.mean(cpu_list) if cpu_list else None,
                "ram_mb_avg": statistics.mean(ram_list) if ram_list else None,
            }
        )

    success_runs = [r for r in per_run_results if r["is_success"]]
    total_count = len(per_run_results)
    success_count = len(success_runs)

    global_stats = {
        "summary": {
            "success_rate": round((success_count / total_count) * 100, 2)
            if total_count > 0
            else 0,
            "total_runs": total_count,
            "success_runs": success_count,
        },
        "metrics": {
            "Travel Time (s)": calculate_stats([r["time_s"] for r in success_runs]),
            "Path Efficiency": calculate_stats(
                [r["path_efficiency"] for r in success_runs]
            ),
            "Control Freq (Hz)": calculate_stats(global_freq_measurements),
            "CPU Utilization (%)": calculate_stats(global_cpu_measurements),
            "Memory (MB)": calculate_stats(global_ram_measurements),
        },
    }

    print("\n" + "=" * 75)
    print(
        f" FINAL EXPERIMENT METRICS (Success Rate: {global_stats['summary']['success_rate']}% "
        + f"- {global_stats['summary']['success_runs']}/{global_stats['summary']['total_runs']})"
    )
    print("=" * 75)

    metric_configs = [
        ("Control Freq (Hz)", "p5", "Bottom 5% (Worst Lag)"),
        ("Path Efficiency", "p5", "Bottom 5% (Worst Paths)"),
        ("Travel Time (s)", "p95", "Top 5% (Slowest Runs)"),
        ("CPU Utilization (%)", "p95", "Top 5% (Peak Spikes)"),
        ("Memory (MB)", "p95", "Top 5% (Peak Footprint)"),
    ]

    for label, p_key, p_label in metric_configs:
        s = global_stats["metrics"][label]
        if s:
            print(
                f"{label:20} | Mean: {s['mean']:<8} | Std: {s['std']:<8} | {p_label}: {s[p_key]}"
            )
            print(
                f"{'':20} | Boxplot: [Min: {s['min']}, Q1: {s['q1']}, Med: {s['median']}, Q3: {s['q3']}, Max: {s['max']}]"
            )
            print("-" * 75)

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=per_run_results[0].keys())
        writer.writeheader()
        writer.writerows(per_run_results)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(global_stats, f, indent=4)


if __name__ == "__main__":
    main()
