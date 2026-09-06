# Trucks planning in MiniZinc

Constraint models for a graph-based transport planning problem, solved as
satisfiability first and as cost minimization second, benchmarked across four
solvers on 100 instances per variant and against 22 custom search strategies.

Coursework for **Constraint Programming**, Master's Degree in Computer Science,
University of Parma, academic year 2025/2026 — project 16.

---

## The problem

A single truck must redistribute `h` indistinguishable objects over an
undirected graph. The objects begin scattered across a set of source nodes; the
truck starts empty at a given node, and the plan succeeds when every node of a
designated target set holds at least one object.

Three primitives are available: load an object, unload an object, and cross an
edge. Two rules make the problem hard:

- the truck carries **at most two objects** at a time;
- a truck **already full may not pass through a node that still has an object
  sitting on it**.

That second rule is what gives the problem its character. It couples the truck's
payload to the state of the graph, so a route that is legal when the truck is
half-loaded becomes illegal when it is full, and the legality of a move depends
on the entire history of loads and unloads that preceded it. In the model the
rule is enforced at arrival: a truck reaching an occupied node with two objects
aboard must drop at least one before moving on.

Two variants are modelled here:

| Variant | Question | Directory |
|---|---|---|
| **Base** | Does a valid plan of exactly `k` steps exist? | `base_problem/` |
| **Minimization** | Among the plans of length `k`, which costs least to travel? | `minimization/` |

The problem statement is an assignment from the course. It is restated above in
our own words and is not reproduced here; see [NOTICE](NOTICE).

---

## What we found

**Lazy clause generation is the deciding factor.** Chuffed solved all 100
instances of both variants and proved optimality on all 100 of the
minimization variant, averaging 1.85 s and 2.52 s. Gecode and HiGHS, which rely
on propagation and search heuristics without clause learning, timed out on 14 %
and 25 % of the base instances respectively. OR-Tools CP-SAT — also a
clause-learning solver — was the only one to keep pace, at roughly twice
Chuffed's runtime on the base problem. On the minimization variant the gap is
six-fold when each solver is measured over the instances it proved optimal, and
wider still — 28-fold — on the 92 instances both of them closed.

![Solvers plotted by how many of the 100 minimization instances they proved optimal against how long they took on those instances. Chuffed sits alone in the top-left corner at 100 of 100 and 2.5 s; OR-Tools is at 92 and 15.6 s, Gecode at 82 and 9.2 s, HiGHS at 67 and 44.5 s.](summary.png)

The two measures usually pull against each other, and between Gecode and
OR-Tools they do: Gecode is quicker on the instances it closes but proves ten
fewer of them. Chuffed is the only solver that trades neither, and HiGHS is
beaten on both.

**Twenty-two hand-written search strategies did not beat the default.** We
wrote twelve custom search annotations for the base problem and ten for the
minimization variant — sequential timestep orderings, position-first and
action-first variable selection, max-regret, smallest-domain, adaptive
splitting. Not one improved on Chuffed's default configuration. On the
hard-instance subsets used for this comparison, every single strategy was
slower on average — by 1.3× to 12.2× on the base problem and 1.8× to 14.5× on
the minimization variant — and the best of them beat the default on only 7 of
33 instances. This is the result we did not expect, and it is the one we would
carry to another problem: on a model with this structure, effort spent on the
model pays and effort spent on search annotations does not.

**Removing the objective variable made the model faster.** The first model
carried a `plan_length` decision variable and minimized it under `plan_length ≤ k`.
Since the benchmark already searches `k = 1, 2, 3, …` and stops at the first
satisfiable value, any plan found at that `k` is already of minimal length. The
variable was redundant. Dropping it in favour of `solve satisfy` shrank the
search space and simplified propagation.

**Cost optimization is a separate phase, not a modified objective.** The
workflow first finds the shortest feasible plan length `k_min` with the
satisfiability model, then minimizes travel cost at that fixed `k_min`. Keeping
the two phases apart means the constraint set never changes between them, so
feasibility results carry over unmodified.

---

## Results

The solver comparison runs on 100 instances per variant: graph sizes
`|V| = 10, 14, 18, 22, 26`, search horizons `k = 5, 8, 11, 14, 17`, four
repetitions of each combination. Timeout 300 s per instance, per phase.

The two variants do not share instances. Each generator was run separately, so
`base_problem/instances/` and `minimization/instances/` contain different graphs
under the same filenames; runtimes from one variant are not comparable to the
other instance by instance.

The search-strategy comparison runs on smaller, harder subsets held in
`*/strategies/instances/`: 33 instances for the base problem and 20 for the
minimization variant. Both subsets contain only the larger graphs
(`|V| ≥ 18`), where the default configuration is slow enough for a strategy to
have room to improve on it.

### Base problem — satisfiability

| Solver | Solved | Timeouts | Mean runtime | Mean over solved |
|---|---|---|---|---|
| **Chuffed** | **100/100** | 0 | **1.85 s** | 1.85 s |
| OR-Tools CP-SAT | 100/100 | 0 | 3.96 s | 3.96 s |
| Gecode | 86/100 | 14 | 53.49 s | 13.36 s |
| HiGHS | 75/100 | 25 | 93.70 s | 24.93 s |

Timeouts are counted as 300 s in the "mean runtime" column. All 39 timeouts,
across both solvers that had any, fall on graphs with `|V| ≥ 18`.

### Minimization — cost optimization at fixed `k`

| Solver | Proven optimal | Solution found | Mean cost | Minimization phase | Total |
|---|---|---|---|---|---|
| **Chuffed** | **100/100** | 100/100 | 50.45 | **2.52 s** | 3.86 s |
| OR-Tools CP-SAT | 92/100 | 92/100 | 47.47 | 38.33 s | 39.63 s |
| Gecode | 82/100 | 92/100 | 47.90 | 61.54 s | 62.93 s |
| HiGHS | 67/100 | 91/100 | 50.25 | 128.89 s | 130.19 s |

Restricted to the instances each solver proved optimal, the minimization phase
takes 2.52 s for Chuffed, 9.17 s for Gecode, 15.56 s for OR-Tools and 44.50 s for
HiGHS.

Two figures are given because the benchmark runs two phases: a satisfiability
search for the shortest plan length, then cost minimization at that length. The
first column is the minimization phase alone, which is what distinguishes the
solvers; the total adds the roughly 1.3 s the preceding search costs. Failed
instances are counted at the runtime recorded for them.

The mean costs are **not comparable across solvers**: each is averaged over
that solver's own subset of instances, and the solvers that failed on the
harder instances are averaging over an easier subset. This is why Gecode and
OR-Tools show a lower mean cost than Chuffed despite solving fewer instances.

---

## Repository layout

```
base_problem/            satisfiability variant
  trucks_optimized.mzn     the model
  create_instances.py      instance generator
  run_benchmark.py         incremental search over k, one solver per run
  view_t0.py               render an instance's initial state
  view_schedule.py         solve an instance and render the plan
  instances/               100 benchmark instances (.dzn)
  strategies/              12 search-annotation variants of the model, plus the
                             unannotated baseline they are measured against
    instances/             33 harder instances, the strategy benchmark set
  results/                 raw CSV, processed CSV/XLSX, 16 figures

minimization/            cost-minimization variant
  trucks_minimize.mzn      the model with the cost objective
  trucks_optimized.mzn     satisfiability model used for phase 1
  trucks_example_ww.dzn    a worked example instance
  create_instances.py      instance generator, adds a Dijkstra distance matrix
  run_benchmark.py         two-phase driver: find k_min, then minimize
  view_t0.py               render an instance's initial state
  view_schedule.py         solve an instance and render the plan
  view_schedule_min.py     render a cost-optimal plan
  instances/               100 benchmark instances, with distance matrices
  strategies/              10 search-annotation variants of the model, the
                             unannotated baseline, and one further variant that
                             constrains the objective (never benchmarked)
    instances/             20 harder instances, the strategy benchmark set
  results/                 raw CSV, processed CSV/XLSX, 14 figures

report/                  report.tex, report.pdf and 4 of the figures
rebuild_processed.py     rebuilds */results/processed/ from the raw CSV files
plot_results.py          regenerates the 30 figures from the CSV data
plot_summary.py          redraws summary.png, the figure in "What we found"
summary.png              the solver comparison in one chart
ERRATA.md                every correction made after submission, and why
```

Instances are named
`instance_n<nodes>_c<repetition>_k<search horizon>_i<index>.dzn`. The `k` in the
name is the upper bound the benchmark searches up to, not the length of the plan
that is eventually found.

---

## Reproducing

Requires MiniZinc on the `PATH`, plus `pandas`, `numpy`, `matplotlib`,
`networkx` and `openpyxl`. The viewers need `networkx` to draw the graph; the
rebuild script needs `openpyxl` to refresh the spreadsheets.

```bash
# look at an instance before solving it
cd base_problem
python view_t0.py instances/instance_n10_c0_k5_i0.dzn

# solve one instance at a given plan length and render the resulting plan
python view_schedule.py -m trucks_optimized.mzn \
                        -i instances/instance_n10_c0_k5_i0.dzn -k 3

# full benchmark for one solver, incrementing k until a plan is found
python run_benchmark.py --model trucks_optimized.mzn --solver Chuffed
```

`view_schedule.py` requires all three flags. It solves at exactly the `-k` you
give it, so pick a length the instance admits — the benchmark CSVs record one
per instance in the `K_Found` column. The `k5` in the filename is the search
horizon, not the answer: this instance solves at `k = 3`.

On Windows, these scripts print box-drawing and arrow characters that a cp1252
console cannot encode, and will stop with a `UnicodeEncodeError`. Set
`PYTHONIOENCODING=utf-8` before running them.

`--solver` accepts `Chuffed`, `Gecode`, `ortools` or `HiGHS`. Pass `--model`
explicitly: the script's built-in default names a file that is not part of this
repository, and it will stop with an error if you omit the flag.

The two-phase minimization benchmark defaults to the right models and needs
only a solver:

```bash
cd minimization
python run_benchmark.py --solver Chuffed
```

Note that `--solver` selects the solver for the cost-minimization phase only.
The search for `k_min` that precedes it is hardcoded to Chuffed, so the
`Time_SAT_Sec` column is Chuffed's time in every run. See [ERRATA.md](ERRATA.md).

Rebuild the derived data and the figures, from the repository root:

```bash
python rebuild_processed.py    # */results/processed/ from the raw CSV files
python plot_results.py         # the 30 figures under */results/figures/
python plot_summary.py         # summary.png, the chart above
```

`rebuild_processed.py` never writes to the raw measurement files. Run it with
`--check` to compare the per-instance files without touching anything; the two
`solver_comparison` files are skipped in that mode, so a full run is what
confirms those.

`report/figures/` holds the four figures used by the report. The plotting script
does not write there; they are copies, kept alongside the LaTeX source.

Budget the time. Summing the recorded runtimes across both variants, the
published benchmark cost 6.22 h for HiGHS, 3.23 h for Gecode and 1.21 h for
OR-Tools. Chuffed took 9.5 minutes.

### Environment

The published results were produced with **MiniZinc 2.9.4**, using the solvers
bundled with it: Chuffed 0.13.2, Gecode 6.3.0, HiGHS 1.11.0 and OR-Tools CP-SAT
9.14.6206. Figures were generated with matplotlib 3.9.1.post1.

The machine the benchmark ran on was not recorded, so absolute runtimes are not
reproducible. The comparisons between solvers are, since all four ran on the
same machine under the same 300 s limit.

---

## Report

[`report/report.pdf`](report/report.pdf) — 15 pages covering the state
representation, the transition semantics, the constraint set, both benchmarks
and the search-strategy analysis. The LaTeX source is alongside it.

It is a revised version of the report submitted for assessment: six errors in the
text and three faults in the data behind it were found afterwards and corrected,
and Table 2 now separates the two benchmark phases. [ERRATA.md](ERRATA.md)
records every change. No conclusion moved.

---

## References

Nethercote, N., Stuckey, P. J., Becket, R., Brand, S., Duck, G. J., Tack, G.
(2007). MiniZinc: Towards a Standard CP Modelling Language. *Principles and
Practice of Constraint Programming — CP 2007*, Lecture Notes in Computer
Science, Springer, 529–543. <https://doi.org/10.1007/978-3-540-74970-7_38>

Ohrimenko, O., Stuckey, P. J., Codish, M. (2009). Propagation via lazy clause
generation. *Constraints* 14(3), 357–391.
<https://doi.org/10.1007/s10601-008-9064-x> — the mechanism behind Chuffed's
advantage on these instances.

Schulte, C., Stuckey, P. J. (2008). Efficient constraint propagation engines.
*ACM Transactions on Programming Languages and Systems* 31(1), 1–43.
<https://doi.org/10.1145/1452044.1452046>

Huangfu, Q., Hall, J. A. J. (2018). Parallelizing the dual revised simplex
method. *Mathematical Programming Computation* 10(1), 119–142.
<https://doi.org/10.1007/s12532-017-0130-5>

Solver implementations: [Chuffed](https://github.com/chuffed/chuffed),
[Gecode](https://www.gecode.org/), [HiGHS](https://highs.dev/),
[OR-Tools](https://developers.google.com/optimization).

---

## Authors

- Samuel Seligardi — [@0-Sam-0](https://github.com/0-Sam-0)
- Luca Marchesi — [@17marche](https://github.com/17marche)
- Francesco Minei — [@FrancescoMinei12](https://github.com/FrancescoMinei12)

## Licence

Code (`*.mzn`, `*.py`) under the [MIT License](LICENSE). Report, figures and
benchmark data under [CC BY 4.0](LICENSE-DOCS). Attribution details and the
provenance of everything in this repository are in [NOTICE](NOTICE).
