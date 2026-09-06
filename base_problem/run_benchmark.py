#!/usr/bin/env python3
import subprocess
import os
import csv
import time
import re
import argparse
from pathlib import Path
import sys

INSTANCES_DIR = "instances"
OUTPUT_DIR = "results"
OUTPUT_CSV = OUTPUT_DIR + "/results_" + \
    time.strftime("%Y-%m-%d_%H-%M-%S") + ".csv"
TIMEOUT_SECONDS = 300


def run_minizinc(model_path, data_path, solver_name):
    cmd = [
        "minizinc",
        model_path,
        data_path,
        "--solver", solver_name,
        "--output-time",
    ]

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS
        )
        elapsed = time.time() - start_time
        stdout = result.stdout
        stdout_lower = stdout.lower()

        if "----------" in stdout or "plan length" in stdout_lower or "goal reached" in stdout_lower:
            match = re.search(r'plan\s*length\s*[:=]\s*(\d+)', stdout_lower)
            actual_k = match.group(1) if match else "found"
            return "SAT", elapsed, actual_k

        elif "unsatisfiable" in stdout_lower:
            return "UNSAT", elapsed, "N/A"

        else:
            if result.stderr:
                print(f"\n[Errore Solver]: {result.stderr[:100]}")
            return "UNKNOWN", elapsed, "N/A"

    except subprocess.TimeoutExpired:
        return "TIMEOUT", TIMEOUT_SECONDS, "N/A"


def get_params_from_dzn(filepath):
    try:
        content = Path(filepath).read_text()
        n_match = re.search(r'N\s*=\s*(\d+)', content)
        k_match = re.search(r'k\s*=\s*(\d+)', content)
        if not k_match:
            k_match = re.search(r'%\s*k\s*=\s*(\d+)', content)

        n_val = n_match.group(1) if n_match else "??"
        k_val = k_match.group(1) if k_match else "??"
        return n_val, k_val
    except IOError as e:
        print(
            f"Errore nella lettura del file {filepath}: {e}", file=sys.stderr)
        return "??", "??"


def run_minizinc_incremental(model_path, data_path, solver_name, k_max):
    overall_start_time = time.time()

    for current_k in range(1, int(k_max) + 1):
        time_spent_so_far = time.time() - overall_start_time
        time_remaining = TIMEOUT_SECONDS - time_spent_so_far

        if time_remaining <= 0:
            return "TIMEOUT", TIMEOUT_SECONDS, "N/A"

        timeout_ms = int(time_remaining * 1000)

        cmd = [
            "minizinc",
            model_path,
            data_path,
            "--solver", solver_name,
            "-D", f"k={current_k}",
            "--time-limit", str(timeout_ms)
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=time_remaining
            )
            stdout = result.stdout.lower()

            if "----------" in stdout or "plan length" in stdout:
                total_elapsed = time.time() - overall_start_time
                return "SAT", total_elapsed, current_k

        except subprocess.TimeoutExpired:
            return "TIMEOUT", TIMEOUT_SECONDS, "N/A"

    total_elapsed = time.time() - overall_start_time
    return "UNSAT", total_elapsed, "N/A"


def main():
    parser = argparse.ArgumentParser(description='Benchmark Trucks Problem')
    parser.add_argument('--model', type=str, default='trucks.mzn',
                        help='Percorso del file .mzn (default: trucks.mzn)')
    parser.add_argument('--solver', type=str, default='Chuffed',
                        choices=['Chuffed', 'Gecode', 'ortools', 'HiGHS'], help='Solver da utilizzare')
    args = parser.parse_args()

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    model_path = Path(args.model)
    if not model_path.is_file():
        print(
            f"Errore: Il file del modello '{args.model}' non esiste.", file=sys.stderr)
        sys.exit(1)

    instances_dir = Path(INSTANCES_DIR)
    if not instances_dir.is_dir():
        print(
            f"La cartella delle istanze '{INSTANCES_DIR}' non esiste. Interruzione.", file=sys.stderr)
        sys.exit(1)

    instances = sorted(list(instances_dir.glob("*.dzn")))
    if not instances:
        print(
            f"Nessuna istanza (.dzn) trovata in '{INSTANCES_DIR}'. Interruzione.", file=sys.stderr)
        return

    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Instance", "Nodes", "Max_K",
                        "Solved_at_K", "Status", "Time_Seconds"])

    for inst_path in instances:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        n_val, k_max = get_params_from_dzn(inst_path)
        print(
            f"[{timestamp}] {inst_path.name} (N={n_val}, Max_K={k_max})...", end=" ", flush=True)

        if k_max == "??":
            status, duration, solved_k = "SKIPPED", 0, "N/A"
            print("SKIPPED (Max_K non trovato)")
        else:
            try:
                solver = 'OR Tools CP-SAT' if args.solver == 'ortools' else args.solver
                status, duration, solved_k = run_minizinc_incremental(
                    str(model_path), str(inst_path), solver, k_max)
                print(f"{status} in {duration:.2f}s (Min_K found: {solved_k})")
            except ValueError:
                status, duration, solved_k = "ERROR", 0, "N/A"
                print(f"ERRORE (Max_K non è un intero valido: {k_max})")

        with open(OUTPUT_CSV, 'a', newline='') as f:
            csv.writer(f).writerow(
                [timestamp, inst_path.name, n_val, k_max, solved_k, status, f"{duration:.4f}"])

    print(f"\nBenchmark completato! Risultati in {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
