# Local Sample-Size Execution — Round 4

## Scope and authority

The local pipeline implements sample-size inversion for exactly six fixed-design keys: `ttest_one`, `ttest_paired`, `ttest_ind`, `anova`, `proportion_two`, and `be_tost`. Group-sequential, survival, adaptive, Bayesian, simulation-heavy, and V4/V5 historical-surrogate methods are not routed to local calculators.

The YAML file for each method remains authoritative. Execution follows:

```text
ClinicalInput → frozen specification → package adapter → local R package
              → deterministic rounding/dropout → structured SampleSizeResult
```

The agent/LLM layer is never a numerical authority. A successful numerical result must originate from the declared R package. Python validates requests, routes methods, performs frozen deterministic derivations and rounding, and assembles results. It does not substitute statistical formulas when R or a package is missing.

## Runtime dependencies

Install a local `Rscript` and the packages declared in `sample_size/r_dependencies.yaml`: `jsonlite`, `pwr`, `TrialSize`, and `PowerTOST`. Packages are never installed automatically. Every result records the R version, statistical package version, function, package arguments, warnings, session information, and the executed calculation code.

Exact validated package versions have not yet been pinned because this environment has no R runtime. Successful calculations therefore remain `IMPLEMENTED_UNVALIDATED` and include a version-validation warning.

## Python use

```python
from sample_size import calculate_sample_size

result = calculate_sample_size({
    "test_key": "ttest_ind",
    "solve_mode": "sample_size",
    "parameters": {
        "standardized_effect": 0.5,
        "allocation_ratio": 1,
        "alpha": 0.05,
        "power": 0.8,
        "dropout_rate": 0.1,
        "alternative": "two_sided",
    },
})
print(result.to_dict())
```

Public power calculation uses the same adapters' forward-power path and method-specific analyzable sizes. It does not require target power or dropout:

```python
power_result = calculate_sample_size({
    "test_key": "ttest_ind",
    "solve_mode": "power",
    "parameters": {
        "standardized_effect": 0.5,
        "allocation_ratio": 1,
        "alpha": 0.05,
        "alternative": "less",
        "analyzable_sample_size_per_arm": 64,
    },
})
```

The public t-test effect is always a strictly positive magnitude. The specification and adapter derive package `d` as follows: `greater → +magnitude`, `less → -magnitude`, and `two_sided → +magnitude` as the canonical symmetric representation. Users never enter a package-specific negative magnitude.

### Power-mode analyzable sizes

| Method | Public input | Package/statistical meaning |
|---|---|---|
| `ttest_one` | `analyzable_sample_size` | `pwr.t.test(n=...)` participants |
| `ttest_paired` | `analyzable_pairs` | `pwr.t.test(n=...)` complete participant pairs, not measurements |
| `ttest_ind` | `analyzable_sample_size_per_arm` | Equal-allocation `pwr.t.test(n=...)` per arm |
| `anova` | `analyzable_sample_size_per_group` | `pwr.anova.test(n=...)` per group |
| `proportion_two` | `analyzable_treatment`, `analyzable_control` | Explicit treatment (`p1`) and control (`p2`) arm sizes; their ratio must equal `allocation_ratio` |
| `be_tost` | `evaluable_total` | Balanced evaluable N passed to `PowerTOST::power.TOST(n=...)` |

Power mode never derives analyzable N from randomized enrollment or dropout. `randomized_sample_size`, `dropout_assumption`, and `target_power` are not applicable and are returned as null. Sample-size mode continues to invert target power, round analyzable N, calculate achieved power at analyzable N, and only then inflate enrollment for dropout.

Failures are typed: unknown/unimplemented method, invalid request, unsupported solve mode, runtime dependency, package contract, or package execution. No remote service is used.

## Result semantics

`analysis_required_sample_size` is the analyzable population used in the forward power calculation. `randomized_sample_size` is enrollment after dropout inflation and balance/block rounding. Per-group or per-sequence counts are separate. Achieved power is recalculated at the rounded analyzable size, never at the dropout-inflated enrollment size.

For ANOVA, package `n` is per group. For TrialSize two proportions, `p1` is treatment, `p2` is control, and `k = n_treatment / n_control`. For bioequivalence, PowerTOST evaluable N is distinct from balanced randomized N.

## Tests and benchmarks

Run:

```powershell
python -m unittest discover -s tests -v
```

Non-R tests cover validation, routing, adapter code generation, output semantics, dropout, allocation, and block rounding. R-dependent execution reports a dependency error when R is absent. Machine-readable fixtures are in `sample_size/validation/benchmarks/`; their numerical expectations intentionally remain null until captured from pinned package versions and independently reviewed. They are not claimed as passed benchmarks.

## Known blockers and unsupported cases

- `ttest_ind` supports 1:1 allocation only. ANOVA is balanced. Bioequivalence supports balanced `2x2` and `parallel` only.
- TrialSize exposes sample-size inversion but no distinct forward-power function for this method. The power adapter executes in R and algebraically inverts the official `TwoSampleProportion.Equality` equation with explicit treatment/control sizes; live validation remains pending.
- Numerical package benchmarks, independent noncentral-distribution comparisons, version pinning, and round-trip grids remain validation pending until an R runtime and packages are available.

No method is marked production or regulatory validated.
