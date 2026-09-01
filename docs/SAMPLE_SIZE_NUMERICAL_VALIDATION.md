# Sample-Size Numerical Validation — Round 4.2

## Outcome

All 24 frozen fixtures for `ttest_one`, `ttest_paired`, `ttest_ind`, `anova`, `proportion_two`, and `be_tost` passed all six validation gates. The run made 114 live R calculations; all 114 completed successfully. These six implementations are `BENCHMARK_VALIDATED`, while their specification lifecycle remains `VALIDATION_PENDING`; none is declared `PRODUCTION` by this validation.

Validation date: 2026-09-02. Basis commit: `3c8f9ba08fbb645189f4687ec3a422fbe5870c64`.

## Validated environment

| Component | Live version |
|---|---|
| Python | 3.12.7 |
| SciPy (independent reference only) | 1.18.1 |
| R | 4.6.1, x86_64-w64-mingw32 |
| jsonlite | 2.0.0 |
| pwr | 1.3.0 |
| TrialSize | 1.4.1 |
| PowerTOST | 1.5.7 |

The exact validated versions are pinned in `sample_size/r_dependencies.yaml` and `requirements-dev.txt`. Calculator results inherit `BENCHMARK_VALIDATED` only when the runtime R and statistical-package versions match this environment.

## Gate results

| Method | Authoritative reproduction | Forward/inverse | Independent reference | Allocation/dropout/rounding | Edge/monotonicity | Reproducibility | Fixtures |
|---|---|---|---|---|---|---|---|
| `ttest_one` | PASS | PASS | PASS | PASS | PASS | PASS | 4/4 |
| `ttest_paired` | PASS | PASS | PASS | PASS | PASS | PASS | 3/3 |
| `ttest_ind` | PASS | PASS | PASS | PASS | PASS | PASS | 4/4 |
| `anova` | PASS | PASS | PASS | PASS | PASS | PASS | 5/5 |
| `proportion_two` | PASS | PASS | PASS | PASS | PASS | PASS | 3/3 |
| `be_tost` | PASS | PASS | PASS | PASS | PASS | PASS | 5/5 |

Direct package calls and emitted reproducible R were executed independently. T-test power was checked with SciPy noncentral-t distributions, including signed `less` alternatives; ANOVA was checked with noncentral-F and its per-group-to-total-N derivation. `proportion_two` was checked against the TrialSize equation and the asymmetric control 0.20, treatment 0.35, ratio 2 benchmark. Bioequivalence was checked with an independent chi-square-conditioned TOST integration for declared 2x2 crossover and parallel designs. SciPy was never used as the production engine.

Exact raw calls, arguments, results, session/version information, round trips, independent comparisons, and monotonicity runs are stored in `sample_size/validation/round42_evidence.json`. The 24 frozen expected results and provenance are in `sample_size/validation/benchmarks/fixed_design_round4.yaml`.

## Discrepancy record

One implementation defect was found. TrialSize returned continuous treatment N 190.9894 for the mandatory asymmetric proportion case, producing 191 treatment and 96 control after integer rounding. The public forward-power validator incorrectly required the realized integer ratio to equal 2 exactly. The invariant now permits only the unavoidable one-subject allocation remainder (`abs(n_treatment - ratio * n_control) <= 1`); larger departures still fail. The affected fixture and the entire suite were rerun successfully.

No formula was changed to force agreement. No specification defect, independent-reference mismatch, numerical-tolerance issue, package/version behavior discrepancy, or unsupported-domain discrepancy remained after the run.

## Tolerance and status policy

Integer sample sizes and block balance are exact. Same-package raw values and power use absolute tolerance `1e-6`. Independent distribution checks use the predeclared method tolerances; observed differences were comfortably within them. A historical implementation, an installed package, or a passing unit test alone cannot confer `BENCHMARK_VALIDATED` or `PRODUCTION` status.
