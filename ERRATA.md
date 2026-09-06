# Corrections after submission

`report/report.pdf` is a revised version of the report submitted for
assessment. Re-deriving every number in it from the benchmark data turned up
three faults in the derived data files and six errors in the report's text.
Both have been corrected here.

This page records what was wrong and what it is now, so that the revision is not
silent.

**No conclusion changed.** Chuffed is the best solver on both problems under
every measurement basis, and the ranking of the four solvers is unaffected. What
changed is the size of some margins.

---

## What was wrong in the data

No measurement was altered. Two of the three faults were in
`<variant>/results/processed/`, which is derived from the raw files;
`rebuild_processed.py` now regenerates that directory reproducibly. The third was
a wrong header line in eleven raw files, corrected without touching a single data
row.

### 1. `Time_Seconds` did not mean the same thing for every solver

The minimization benchmark runs two phases per instance — a satisfiability
search for the shortest plan length `k`, then cost minimization at that `k` —
timed separately in the raw files as `Time_SAT_Sec` and `Time_MIN_Sec`. The
processed files collapsed them into one `Time_Seconds` column, and did it two
different ways:

| | `Time_Seconds` held |
|---|---|
| Chuffed, Gecode, all 11 strategy runs | the minimization phase alone |
| HiGHS, OR-Tools | both phases |

So two of the four solvers were carrying about 1.3 s of extra work that the
other two were not, in a column presented as comparable.

`Time_Seconds` is now the total for the instance, `Time_SAT_Sec +
Time_MIN_Sec`, everywhere. The minimization files keep `Time_MIN_Sec` beside it,
so that the phase the solvers actually differ in is available without recombining
anything: that is the column the figures plot and the one Table 2 analyses. Table
2 gives both.

### 2. Nine HiGHS rows were corrupted

The nine instances HiGHS failed on — i64, i68, i82, i84, i88, i89, i92, i93,
i94 — were stored as `TIMEOUT` with `Time_Seconds = 0.00` and no `K_Found`,
discarding three facts the raw file holds. Restored, i64 now reads:

| | before | after |
|---|---|---|
| `K_Found` | *(empty)* | 8 |
| `SAT` | `TIMEOUT` | `ERROR_MIN` |
| `Time_Seconds` | 0.00 | 302.45 |

In the raw file each of those nine instances had found a plan length — 8, 9 or 10
— and had then spent about 300.3 seconds in the minimization phase without
returning a solution. In the processed file the status was replaced by `TIMEOUT`
and the time by zero, setting them aside.

Zero is not the same as excluded. The summary spreadsheet averages the column
over all 100 rows, so the nine zeros were averaged in: 91 real measurements
divided by 100. That is exactly the 102.83 the report prints, and it is 27
seconds below the true figure.

### 3. The strategy result files had a malformed header

`minimization/results/0.csv` through `10.csv` carried a seven-column header
copied from the base problem while every data row held nine fields. Read
naively, every column after `Solved_at_K` was silently mis-assigned: the cost
appeared under `Max_K`, the status under `Solved_at_K`, and the column labelled
`Time_Seconds` landed on `Time_MIN_Sec`. The header lines are corrected; no data
row was touched.

---

## What was corrected in the report

Table 2 now carries two columns, `Min. phase (s)` for the minimization phase
alone and `Total (s)` for both phases, with a sentence defining them. Three of
the four originally printed figures turned out to be correct values in the wrong
context:
Chuffed's 2.52 and Gecode's 61.54 (9.17) were minimization-phase figures,
OR-Tools' 39.63 (16.61) was a total. Only the HiGHS row was wrong outright.

| Location | Was | Now |
|---|---|---|
| Table 2, HiGHS | 102.83 (45.36) | 128.89 (44.50) in `MIN`, 130.19 (45.36) in `Total` |
| Table 2, OR-Tools | 39.63 (16.61) | 38.33 (15.56) in `MIN`, 39.63 (16.61) in `Total` |
| §2.3, speed ratios | 18× HiGHS, 6.6× OR-Tools | 17.7× and 6.2× |
| §2.3, HiGHS average | 102.83 s | 128.89 s |
| §2.3, OR-Tools average | 39.63 s (16.61 s) | 38.33 s (15.56 s) |
| §2.3.4, summary | same figures repeated | updated to match |
| §2.3.4, stated basis | "counted as 300 seconds" | "counted at the runtime recorded for them" |
| §3.1, conclusions list | OR-Tools 16.61 s, HiGHS 45.36 s | 15.56 s and 44.50 s |

Gecode's 3.6× ratio and Chuffed's 2.52 s were correct on the minimization-phase
basis the prose uses, and are unchanged.

Three presentation problems were fixed at the same time. The second column of
Table 2 was headed `SAT_MIN`, which named one of the status values used in the
result files while counting two of them, so the same token meant 92 instances in
the report and 10 in the data. It is now `Solved`, defined in the text without
reference to any file. Both table captions now state what the figures in
parentheses mean, which previously had to be inferred from the surrounding prose.
And the remaining status names borrowed from the result files were removed from
the report, so it can be read without opening the data.

Six claims in the text were wrong independently of the data:

**Seven times across five passages**, the report attributed the instances a
solver could not solve to memory exhaustion. Nothing in the benchmark records a
cause. The driver marks a failure whenever the solver's output contains no cost
line, and it passes `--time-limit 300000` to MiniZinc, so the solver is stopped
at 300 seconds whatever it was doing.

The recorded times show that is what happened: all 25 failed instances, across
the three solvers that had any, lie between 300.11 s and 300.31 s, none below
290 s. The instances that returned a solution without proving it optimal cluster
at the same 300 s — the same event, with a solution in hand.

What the timing does not tell us is *why* nothing came back. A solver still
searching and a solver thrashing against a memory ceiling both produce a process
that runs to the limit and returns nothing. The solvers' error output was not
kept, so neither can be confirmed.

The report now states the outcome — no solution returned before the limit — and
says explicitly that the cause was not recorded, instead of attributing it to
memory.

**§1.3.3, printed page 7.** "Instances with N=26 nodes can take up to 10-20
seconds" — no base-problem instance reaches 10 s with Chuffed. At N = 26 the
mean is 2.57 s and the maximum 3.77 s; the slowest instance overall, 6.50 s,
occurs at N = 22.

**§2.3.2, printed page 11.** "All instances solving in under 5 seconds" — 94 of
100 do, and the slowest takes 83.44 s. The 100 % proven-optimality claim beside
it was correct.

**§2.3.1, printed page 11.** An unproven solution "could bias the average
downward". It cannot. A feasible solution to a minimization problem is an upper
bound on the optimum, so including one can only raise a mean. Checked against the
optima Chuffed proved on the same instances, none of the 34 unproven solutions
across Gecode and HiGHS is better than the optimum: 21 are strictly worse and 13
are equal. The same passage guessed that HiGHS's unproven solutions might be
"close to optimal"; they average 16 % above it.

**§1.3.2, printed page 7, and §2.3.3, printed page 12.** The custom search
strategies were said to show "marginal differences" from the default, which
"often outperforms" them. Every one of the twenty-two is slower on the mean — by
1.3 to 12.2 times on the base problem, 1.8 to 14.5 on the minimization variant —
and the best of them wins on 7 of 33 and 5 of 20 instances respectively. The
conclusion the report draws from this is right; the description of the margin was
not.

**Figure captions, printed pages 6 and 11.** Failed instances were said to be
"shown as 300-second bars". The figures are line plots, and failures are drawn as
crosses above the 300-second line, not at it.

The stated basis for the base problem, "timeouts counted as 300 seconds", is
correct and unchanged: base-problem timeouts are recorded as exactly 300.0 s.

---

## A caveat that is not an error

`minimization/run_benchmark.py` line 198 passes the solver name to phase 1 as a
literal:

```python
status_k, time_k, solved_k = run_minizinc_incremental(
    base_model_path, str(inst_path), "Chuffed", k_max_limit)
```

So `--solver` selects the solver for the cost-minimization phase only; the
search for `k_min` is always done by Chuffed. The recorded `Time_SAT_Sec`
confirms it — 1.34, 1.39, 1.30 and 1.30 s on average across the four runs.

This does not affect the minimization comparison, which is what the report
analyses and what the `Min. phase (s)` column reports. It does mean the satisfiability
component of the `Total (s)` column is Chuffed's work rather than the named
solver's. It is left as it is; changing it would mean rerunning the benchmark.

---

## Other differences from the submitted package

- Two lines were added to the title page: one recording that the document was
  revised, one giving the address of this repository. The address is spelled out
  rather than hidden behind a link, so a printed or forwarded copy of the PDF can
  still be traced back to the models, the data and this page.
- The 14 minimization figures were regenerated from the corrected data and plot
  the cost-minimization phase, matching the text that describes them; the two
  minimization figures in `report/figures/` were updated to match. The 16
  base-problem figures are untouched: regenerating them from unchanged data
  reproduces the published images pixel for pixel, which is how the rebuild was
  validated.
- `rebuild_processed.py`, `plot_summary.py` and the chart it draws, `summary.png`,
  were added. None of them shipped with the submission.
