#!/usr/bin/env python3
"""
Rebuild every derived results file from the raw benchmark output.

The raw measurements in ``<variant>/results/*.csv`` are the ground truth and are
never written to by this script. Everything under ``<variant>/results/processed/``
is regenerated from them, so the whole chain is reproducible.

Timing convention
-----------------
``Time_Seconds`` is the **total wall time the solver spent on the instance**.

For the base problem there is a single phase, so it is simply the recorded time.

For the minimization problem the benchmark runs two phases — a satisfiability
search for the shortest plan length ``k``, then cost minimization at that ``k`` —
timed separately as ``Time_SAT_Sec`` and ``Time_MIN_Sec``. Here ``Time_Seconds``
is their **sum**, for every solver and every strategy alike.

The previously published processed files applied this inconsistently: for
Chuffed and Gecode they held the minimization phase alone, for HiGHS and
OR-Tools the sum. See ERRATA.md.

Minimization files also carry ``Time_MIN_Sec``, the cost-minimization phase on
its own. That is the phase the solvers actually differ in — the search for ``k``
is always run with Chuffed — so it is the one the figures and the report compare.

Failed instances keep the time that was actually measured for them; they are
never recorded as zero.

Usage
-----
    python rebuild_processed.py            # rewrite the processed files
    python rebuild_processed.py --check    # report what would change, write nothing
"""

import argparse
import os
import re
import sys

import pandas as pd

BASE_COLUMNS = ["Timestamp", "Instance", "Nodes", "Max_K", "Solved_at_K",
                "Status", "Time_Seconds"]
MIN_COLUMNS = ["Timestamp", "Instance", "Nodes", "Max_K", "Solved_at_K",
               "Min_Cost", "Min_Status", "Time_SAT_Sec", "Time_MIN_Sec"]

SOLVERS = ["chuffed", "gecode", "HiGHs", "ortools"]
VARIANTS = {
    "base_problem": {"kind": "base", "strategies": range(13)},
    "minimization": {"kind": "min", "strategies": range(11)},
}


def instance_id(filename):
    """instance_n10_c0_k11_i2.dzn -> i2"""
    m = re.search(r"_i(\d+)\.dzn", str(filename))
    return "i" + m.group(1) if m else None


def read_raw(path, kind):
    """Read a raw results file, ignoring its header row.

    The header is ignored deliberately: the minimization strategy files ship a
    seven-column header copied from the base problem while carrying nine fields
    per row. Positional reading is the only thing that is correct for every file.
    """
    names = BASE_COLUMNS if kind == "base" else MIN_COLUMNS
    df = pd.read_csv(path, header=None, skiprows=1, names=names)
    df["Instance_id"] = df["Instance"].map(instance_id)
    return df


def build_processed(raw, kind):
    out = pd.DataFrame({"Instance": raw["Instance_id"]})
    out["K_Found"] = pd.to_numeric(raw["Solved_at_K"], errors="coerce").astype("Int64")
    if kind == "min":
        out["Min_Cost"] = pd.to_numeric(raw["Min_Cost"], errors="coerce").astype("Int64")
        out["SAT"] = raw["Min_Status"].astype(str).str.strip()
        minimization = pd.to_numeric(raw["Time_MIN_Sec"], errors="coerce")
        total = minimization + pd.to_numeric(raw["Time_SAT_Sec"], errors="coerce")
        out["Time_Seconds"] = total.round(2)
        out["Time_MIN_Sec"] = minimization.round(2)
    else:
        out["SAT"] = raw["Status"].astype(str).str.strip()
        out["Time_Seconds"] = pd.to_numeric(raw["Time_Seconds"], errors="coerce")
    return out.sort_values("Instance", key=lambda s: s.str[1:].astype(int)).reset_index(drop=True)


def build_comparison(frames, kind):
    """Merge the four per-solver tables into one wide table."""
    merged = None
    for solver, df in frames.items():
        renamed = df.rename(columns={c: f"{solver}_{c}" for c in df.columns
                                     if c != "Instance"})
        merged = renamed if merged is None else merged.merge(renamed, on="Instance",
                                                             how="outer")
    return merged.sort_values("Instance",
                              key=lambda s: s.str[1:].astype(int)).reset_index(drop=True)


def write_comparison_csv(df, path):
    """Italian number format: semicolon separator, comma decimal."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype.kind == "f":
            out[col] = out[col].map(lambda v: "" if pd.isna(v) else str(v).replace(".", ","))
    out.to_csv(path, sep=";", index=False)


def update_comparison_xlsx(df, path, kind):
    """Refresh the data cells of an existing workbook, in place.

    The spreadsheets are authored artefacts, not derived ones: the base-problem
    workbook carries hand-written cross-solver consistency checks alongside the
    data. So this rewrites only the per-instance cells and leaves the layout,
    the summary formulas and any extra columns exactly as they are.
    """
    import openpyxl

    if not os.path.exists(path):
        print(f"  no workbook at {path}, skipped")
        return False

    columns = ["K_Found", "Min_Cost", "SAT", "Time_Seconds"] if kind == "min" \
        else ["K_Found", "SAT", "Time_Seconds"]
    width = len(columns)

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    by_instance = df.set_index("Instance")

    changed = 0
    for row in range(4, ws.max_row + 1):
        instance = ws.cell(row, 1).value
        if instance not in by_instance.index:
            continue
        record = by_instance.loc[instance]
        for i, solver in enumerate(SOLVERS):
            first = 2 + i * width
            for j, name in enumerate(columns):
                v = record.get(f"{solver}_{name}")
                v = None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
                cell = ws.cell(row, first + j)
                if cell.value != v:
                    cell.value = v
                    changed += 1

    if not changed:
        print(f"  unchanged: {path}")
        return False

    wb.save(path)
    print(f"  updated {changed} cells in {path}")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report what would change without writing anything")
    args = ap.parse_args()

    changed = 0
    for variant, cfg in VARIANTS.items():
        kind = cfg["kind"]
        processed_dir = os.path.join(variant, "results", "processed")
        frames = {}
        targets = list(SOLVERS) + [str(i) for i in cfg["strategies"]]

        for name in targets:
            raw_path = os.path.join(variant, "results", f"{name}.csv")
            if not os.path.exists(raw_path):
                print(f"  missing raw file, skipped: {raw_path}")
                continue
            new = build_processed(read_raw(raw_path, kind), kind)
            if name in SOLVERS:
                frames[name] = new

            out_path = os.path.join(processed_dir, f"{name}.csv")
            text = new.to_csv(index=False, lineterminator="\n")
            old = open(out_path, encoding="utf-8").read() if os.path.exists(out_path) else None
            if old == text:
                continue
            changed += 1
            print(f"  {'would change' if args.check else 'rewrote'}: {out_path}")
            if not args.check:
                with open(out_path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)

        if len(frames) == len(SOLVERS) and not args.check:
            comparison = build_comparison(frames, kind)
            write_comparison_csv(comparison,
                                 os.path.join(processed_dir, "solver_comparison.csv"))
            print(f"  rewrote: {processed_dir}/solver_comparison.csv")
            update_comparison_xlsx(comparison,
                                   os.path.join(processed_dir, "solver_comparison.xlsx"),
                                   kind)

    print(f"\n{changed} per-instance file(s) {'differ' if args.check else 'rewritten'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
