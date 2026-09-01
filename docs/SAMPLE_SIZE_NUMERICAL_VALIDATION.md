# Sample-Size Numerical Validation — Round 4.2

## 1. Scope and outcome

This round attempted live numerical validation of `ttest_one`, `ttest_paired`, `ttest_ind`, `anova`, `proportion_two`, and `be_tost`. It followed the permitted dependency-blocked path. No new calculator or statistical engine was added, no frozen method was changed, and no method was promoted.

Outcome: **DEPENDENCY_MISSING_R_RUNTIME** and **DEPENDENCY_MISSING_VALIDATION_REFERENCE**. Zero live R calculations were executed and no pending benchmark value was populated.

## 2. Environment

Validation date: 2026-09-01. Basis commit: `fb9ed65`.

| Component | Observed result |
|---|---|
| Rscript | Not found in PATH, `C:\Program Files\R`, `C:\Program Files (x86)\R`, `%LOCALAPPDATA%\Programs\R`, `C:\R`, or R-core registry keys |
| R version/platform/architecture | Unavailable; not inferred |
| Python | 3.12.13, 64-bit AMD64 |
| Platform | Windows 11, build 26100 |
| SciPy | Not installed; version unavailable |
| jsonlite, pwr, TrialSize, PowerTOST | Not auditable without R; versions and library paths unavailable |

## 3. Validation methodology

The planned gates were direct package reproduction, rounded inverse/forward consistency, independent reference comparison, rounding/dropout/allocation invariants, edge/monotonicity checks, and reproducible-code re-execution with version capture. The first mandatory gate could not start without R. Per the stop rule, downstream numerical gates were classified `BLOCKED`, not passed or skipped-as-success.

The existing non-R contract suite remains useful evidence for mappings and deterministic transformations, but it is not numerical validation.

## 4. Tolerance policy

The following predeclared tolerances remain pending use:

- Rounded sample sizes and balance/block counts: exact integer equality.
- Identical package raw continuous results: absolute difference at most `1e-6`.
- Same-package power reproduction: absolute difference at most `1e-6`.
- Independent noncentral-distribution power: initial absolute tolerance `1e-6` to `1e-5`, with any wider tolerance requiring a method-specific numerical investigation.

No tolerance was evaluated or widened.

## 5. Results by method

| Method | Package reproduction | Round trip | Independent reference | Monotonicity | Dropout/rounding | Reproducible code | Final status |
|---|---|---|---|---|---|---|---|
| `ttest_one` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | IMPLEMENTED_UNVALIDATED |
| `ttest_paired` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | IMPLEMENTED_UNVALIDATED |
| `ttest_ind` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | IMPLEMENTED_UNVALIDATED |
| `anova` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | IMPLEMENTED_UNVALIDATED |
| `proportion_two` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | IMPLEMENTED_UNVALIDATED |
| `be_tost` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | IMPLEMENTED_UNVALIDATED |

## 6. Benchmarks

The fixture contains 24 cases: 18 sample-size and 6 public-power cases. Numerically executed: 0; passed: 0; failed: 0; pending: 24. Existing null expectations were preserved. No raw R output, expected N, or expected power was invented.

## 7–11. Numerical gates

- Round-trip results: blocked before execution.
- Independent-reference results: blocked because SciPy is absent; independent analytical reference code was not treated as executed.
- Monotonicity results: blocked for live statistical calculations.
- Dropout/rounding results: deterministic non-R tests pass, but the complete numerical gate remains blocked because package-derived analyzable N was not produced live.
- Reproducibility results: generated code was not executed and is therefore not marked reproduced.

## 12. Deviations and discrepancies

No numerical discrepancy exists because no numerical comparison was run. The two environment blockers are classified `ENVIRONMENT_DEPENDENCY`. There were no resolved discrepancies to report.

## 13. Validation status

All six methods remain `IMPLEMENTED_UNVALIDATED`. None reached `PACKAGE_REPRODUCED` or `BENCHMARK_VALIDATED`.

## 14. Remaining limitations and setup

Install R manually, then run the repository-provided setup helper explicitly:

```powershell
& 'C:\Program Files\R\R-<version>\bin\Rscript.exe' sample_size/validation/install_r_dependencies.R
& 'C:\Program Files\R\R-<version>\bin\Rscript.exe' --version
python sample_size/validation/environment_probe.py
```

For independent validation, install the development-only Python reference dependency into the chosen validation environment:

```powershell
python -m pip install "scipy==<reviewed-version>"
```

Select and record the actual SciPy version before freezing it; this report does not nominate an untested version. Package installation remains user-initiated and is never performed by the calculator.

## 15. Exact validated software versions

None. `sample_size/r_dependencies.yaml` remains unpinned because no R or package version was executed and validated. Exact versions may be frozen only after all required gates pass.
