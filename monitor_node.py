import psutil
import time
import argparse
import json
import sys


def find_process_by_name(name):
    matches = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
            if name in p.info["name"] or name in cmd:
                if "monitor_node.py" not in cmd:
                    matches.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return matches


def monitor(pid, interval, append_file=None):
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"[!] Error: No process found with PID {pid}")
        sys.exit(1)

    cmd_str = " ".join(p.cmdline())
    file_timestamp = int(time.perf_counter())
    out_file = f"resource_metrics_{file_timestamp}.json"
    if not append_file:
        append_file = out_file + "l"
    print(f"[*] Monitoring PID: {pid}")
    print(f"[*] Command: {cmd_str}")
    print(f"[*] Target Interval: {interval} seconds")
    print(f"[*] Appending live data to: {append_file}")
    print("-" * 50)

    time_history = []
    cpu_history = []
    mem_history = []

    p.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=True)

    start_time = time.perf_counter()

    append_handle = open(append_file, "a")

    try:
        while p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
            time.sleep(interval)

            if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                break

            current_time = time.perf_counter()
            cpu = p.cpu_percent(interval=None) / cpu_count
            mem_mb = p.memory_info().rss / (1024 * 1024)

            time_history.append(current_time)
            cpu_history.append(cpu)
            mem_history.append(mem_mb)

            print(
                f"Time: {current_time:11.2f}s  |  CPU: {cpu:5.1f}%  |  RAM: {mem_mb:7.2f} MB"
            )

            if append_handle:
                record = {
                    "time_seconds": current_time,
                    "cpu_percent": cpu,
                    "ram_mb": mem_mb,
                }
                append_handle.write(json.dumps(record) + "\n")
                append_handle.flush()

    except KeyboardInterrupt:
        print("\n[*] Monitoring manually stopped.")
    except psutil.NoSuchProcess:
        print("\n[*] Target process terminated.")
    finally:
        if append_handle:
            append_handle.close()

    duration = time.perf_counter() - start_time

    if not cpu_history:
        print("[!] No data collected.")
        return

    data_payload = {
        "process_id": pid,
        "command": cmd_str,
        "total_duration_seconds": duration,
        "samples_collected": len(cpu_history),
        "raw_data": {
            "time_seconds": time_history,
            "cpu_percent": cpu_history,
            "ram_mb": mem_history,
        },
    }

    with open(out_file, "w") as f:
        json.dump(data_payload, f, indent=4)

    print("-" * 50)
    print(f"[*] Done! Raw data successfully saved to: {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Monitor and record raw CPU/RAM of a specific script/process."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-p", "--pid", type=int, help="Process ID to monitor.")
    group.add_argument("-n", "--name", type=str, help="Name of the script to monitor.")

    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0)",
    )

    parser.add_argument(
        "-o", "--output", type=str, help="Append live metrics to a file (JSONL format)"
    )

    args = parser.parse_args()

    target_pid = args.pid

    if args.name:
        matches = find_process_by_name(args.name)
        if not matches:
            print(f"[!] No running process found matching: '{args.name}'")
            sys.exit(1)
        elif len(matches) > 1:
            print(f"[!] Multiple processes found matching '{args.name}':")
            for m in matches:
                print(f"    PID {m.pid}: {' '.join(m.info['cmdline'])}")
            print("\nPlease run this monitor again using the exact -p PID.")
            sys.exit(1)
        else:
            target_pid = matches[0].pid

    monitor(target_pid, args.interval, args.output)
