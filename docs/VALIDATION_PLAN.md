# Sample-Size Method Validation Plan

## Purpose

Every numerical method exposed by the Clinical Development Agent must be traceable, reproducible, independently benchmarked, and appropriate for its advertised estimand and analysis. Historical implementation, a successful package call, agreement with a README example, or agreement between two ports of the same algorithm is insufficient for production status.

This plan applies per **method variant**, not merely per test key. A key that supports one- and two-sided tests, unequal allocation, several endpoint distributions, or analytical and simulation engines has a validation record for every supported combination. Unsupported combinations must fail explicitly.

## Lifecycle statuses

| status | meaning | permitted exposure |
|---|---|---|
| **EXPERIMENTAL** | Method definition or prototype is changing. Statistical interface and results are not approved. | Developer-only; never presented as a clinical sample-size result. |
| **VALIDATION_PENDING** | Statistical specification is frozen and implementation tests are running, but one or more required gates lack evidence or approval. | Internal/QA use with a visible validation-pending label; not for protocol or regulatory use. |
| **VALIDATED** | All applicable technical gates pass against pinned dependencies and an independent reviewer has approved the validation report. | Controlled expert use; result must identify method, assumptions, package/version, and validation record. |
| **PRODUCTION** | VALIDATED plus release, operational, documentation, monitoring, and change-control gates pass. | Available to the Clinical Development Agent for supported input domains. |

Status is attached to a versioned tuple:

`test_key + method_variant + implementation_version + engine + package_versions + statistical_spec_version`.

Changing any element triggers the change-control assessment below. No method becomes PRODUCTION solely because historical code exists or because its validation grade is V1.

## Required artifacts

Each method must have:

1. A statistical specification: estimand, null/alternative, sidedness, target power, sampling unit, allocation convention, analysis test, formula/package algorithm, rounding rule, and supported parameter domain.
2. A provenance record: primary methodological reference, package documentation, regulatory/guideline context, and the exact package function/API.
3. A machine-readable test manifest containing test vectors and tolerances.
4. An independent benchmark implementation or published oracle not copied from the production code.
5. A validation report with environment/session information, results, exceptions, reviewer, date, and status decision.
6. A user-facing assumptions/limitations block and an explicit error for unsupported designs.

## Validation gates

### 1. Specification and interface gate

Before numerical testing:

- Confirm that the advertised method matches the actual hypothesis and analysis.
- Define whether n is per arm, per sequence, per cluster, total subjects, or events.
- Define whether returned n is analyzable or enrolled n.
- Define effect orientation and beneficial direction for differences, ratios, odds ratios, risk ratios, and hazard ratios.
- Define alpha as one-sided or familywise and whether a two-sided alpha is split.
- Define allocation ratio numerator/denominator and rounding allocation.
- Separate precision, estimation, assurance, operating-characteristic simulation, and hypothesis-test power; do not label all of them “power.”
- Require all parameters that identify power. For example, paired binary designs require discordant-cell probabilities; OR/RR designs require baseline risk; multiple endpoints require a success rule and covariance.

### 2. Unit tests

Unit tests cover:

- Parameter parsing, units, aliases, and default resolution.
- Domain validation and informative rejection of invalid inputs.
- Effect-direction normalization and null-boundary handling.
- Per-arm/total/event/cluster labeling.
- Integer rounding and allocation preservation.
- Package-result extraction without relying on unstable print text.
- Deterministic dropout inflation and reporting.
- Serialization of the complete method metadata and session information.
- Known historical failure modes documented in `STATISTICAL_VALIDATION_MATRIX.md`.

Every branch, error condition, and supported method variant requires tests. Coverage percentage alone is not an acceptance criterion.

### 3. Numerical benchmark tests

At least two forms of numerical evidence are required where feasible:

- Published examples from the primary paper, package manual, textbook, regulatory example, or independently generated reference table.
- An independent calculation using a different algorithm, engine, or direct distributional inversion.

Benchmark grids include central clinical settings and parameter extremes. Expected values, source locator, package/version, tolerance, and rounding stage are stored in the manifest. A result copied from the historical repository is a regression fixture, not an authoritative benchmark.

Default acceptance tolerances:

- Closed-form/package scalar power: absolute difference ≤ 1e-6 before reporting-rounding when the same mathematical method is used.
- Independent analytical methods with documented numerical differences: predeclared method-specific tolerance, normally power difference ≤ 0.005 and sample-size difference ≤ max(2 subjects, 1%); larger differences require reconciliation, not silent averaging.
- Integer n: the selected n must meet target power and n-1 (or the immediately preceding feasible allocation) must fail it within numerical tolerance.

### 4. Cross-engine comparisons

Where two engines exist, compare R against an independent engine such as direct SciPy distribution inversion, validated SAS/PASS/nQuery output, or a separately implemented simulation. Cross-engine tests must not compare two wrappers around the same source function and call that independent.

For each comparison, record:

- Mathematical method and test statistic used by each engine.
- Continuity correction, variance convention, and rounding.
- Package/software versions.
- Any expected methodological difference.

Disagreement is resolved by statistical review; the system must never choose the smaller n automatically.

### 5. Edge-case tests

Each applicable method tests:

- Alpha near supported lower/upper bounds.
- Power near supported lower/upper bounds.
- Effect approaching the null or equivalence/NI boundary.
- Probabilities near 0 and 1 and invalid transformed probabilities.
- Ratios near 1 and extreme but permitted ratios.
- Very small and very large n.
- Zero events, rare events, complete separation, and zero discordant pairs where relevant.
- Near-singular endpoint covariance/correlation matrices.
- ICC near 0 and near its permitted upper range.
- Dropout near 0 and the maximum supported value.
- Accrual/follow-up combinations that yield negligible event probability.
- Package convergence failures, warnings, NA/Inf, and API changes.

The required behavior is either a validated finite result or an explicit, actionable refusal—never an unlabeled fallback to a different method.

### 6. Reverse power/sample-size consistency

For methods supporting both directions:

1. Solve n for target power.
2. Recalculate power at the returned feasible n.
3. Verify power meets or exceeds target within tolerance.
4. Recalculate at the preceding feasible n/allocation and verify it is below target, unless documented discreteness produces a plateau.
5. Repeat across the benchmark grid.

Forward and reverse calculations must use the same statistical engine and conventions. If a package supplies only one direction, the reverse solver must be validated as a root finder around that same power function.

### 7. Allocation-ratio tests

For every method advertising unequal allocation:

- Verify ratio orientation with an asymmetric fixture.
- Test 1:1, moderately unequal, and extreme supported ratios.
- Verify integer allocation rounding preserves or conservatively exceeds target power.
- Verify total n equals the sum of reported groups/sequences/clusters.
- For shared-control/multi-arm designs, verify covariance induced by the common control.
- Document whether allocation is fixed by subjects, events, exposure time, or clusters.

### 8. One-sided/two-sided alpha tests

- Test one-sided and two-sided modes against independent quantile calculations.
- Verify two-sided alpha splitting and one-sided NI/equivalence conventions.
- For TOST, verify each component test uses the intended one-sided alpha.
- For sequential/multiple-testing designs, verify overall rather than nominal per-look/per-hypothesis alpha.
- Test effect-direction reversal: reversing group labels must give the expected symmetric result or an explicit directional failure.

### 9. Dropout adjustment tests

Dropout is a reporting/enrollment layer unless the statistical model explicitly incorporates censoring or missingness.

- For simple endpoint-independent attrition, use the prespecified inflation rule and verify `ceil(n_analyzable / (1-d))` at the correct unit.
- Never apply dropout twice when a package already models withdrawal/censoring.
- Test group-specific, cluster-level, and period-specific dropout only for methods that explicitly support them.
- For survival/recurrent-event methods, distinguish loss to follow-up effects on event probability from simple enrollment inflation.
- Always report analyzable n, enrolled n, adjustment rule, and rounding separately.

### 10. Simulation reproducibility

Simulation methods must:

- Accept and report a user-visible seed.
- Use a documented random-number generator and RNG version.
- Avoid hidden hard-coded seeds.
- Produce identical results for identical seed, engine, package versions, parallelization mode, and platform within the documented reproducibility guarantee.
- Use independent random streams for parallel work and record the stream scheme.
- Store scenario inputs, replicate count, successes, estimate, standard error, and confidence interval.
- Include deterministic micro-scenarios for simulator logic plus stochastic operating-characteristic tests.

### 11. Monte Carlo error criteria

For a simulated probability `p_hat` from M replicates, report a binomial Monte Carlo standard error and a confidence interval. Sequential or nested simulations must also quantify error from the inner layer or demonstrate that it is negligible.

Default acceptance criteria:

- Confirmatory Type I error: the two-sided 95% Monte Carlo interval must contain the design target and MCSE must be ≤ 0.0005, unless a stricter protocol-specific criterion is set. Around p=0.025 this generally requires about 97,500 independent replicates for the MCSE threshold.
- Power/assurance: MCSE must be ≤ 0.002, normally requiring at least about 40,000 replicates near p=0.8; the exact M is calculated from the worst relevant p.
- Sample-size selection by simulation: the lower confidence bound at selected n must meet the target, or the selection rule and indifference zone must be prospectively defined. Neighboring feasible n values must be evaluated.
- Rare-error or strong-FWER claims require enough replicates for the smallest probability being assessed; a fixed 1,000 or 5,000 run default is not acceptable evidence.

Simulation validation uses several seeds and demonstrates convergence as M increases. A single favorable seed is never a pass.

### 12. Package and version pinning

- Pin R, every direct statistical package, and numerically material transitive dependencies in a lockfile and immutable runtime image.
- Record package source (CRAN snapshot or approved repository), version, checksum, and license.
- Prohibit runtime package installation in production.
- Treat a package upgrade as a validation-impacting change; run the full method suite and compare results before promotion.
- Detect missing functions or changed formal arguments at startup and fail closed.
- Retain the prior validated environment so results can be reproduced after an upgrade.

### 13. Reproducible session information

Every result and validation report records:

- Method/test key and statistical-specification version.
- Application and implementation commit.
- R version, platform, OS, BLAS/LAPACK where numerically relevant.
- `sessionInfo()` or `sessioninfo::session_info()` output.
- Package versions and lockfile/image digest.
- Locale and time zone where they can affect parsing or rendering.
- RNG kind/version, seed, replicate count, and parallel-stream configuration.
- Full normalized inputs, defaults, solve direction, rounding, warnings, and output units.
- Validation manifest version and benchmark identifiers.

## Method-class-specific requirements

### Exact/package and analytical methods

- Establish the exact package function and formal argument mapping.
- Verify every transformation of effect, variance, alpha, allocation, and dropout.
- Test monotonicity: n increases as effect decreases, power increases with n, and n behaves appropriately with alpha/power.
- Verify discreteness and minimality for exact tests.
- Do not silently substitute an asymptotic fallback when the package method fails.

### Asymptotic approximations

- Label the approximation in user output.
- State validity conditions such as expected cell counts, event counts, PH, normality, or equal variance.
- Define a conservative domain of use and refuse inputs outside it.
- Benchmark empirical T1E and power by simulation at the domain boundary.

### Simulation methods

- Validate the data-generating process separately from the analysis/stopping code.
- Under the null, verify marginal and strong Type I error as applicable.
- Under alternatives, verify power, bias, expected sample size/events, stopping probabilities, selection probabilities, and coverage as applicable.
- Include adverse scenarios: model misspecification, prior conflict, time trends, delayed outcomes, and nuisance-parameter uncertainty.

### Heuristics

Heuristics cannot be promoted beyond EXPERIMENTAL as sample-size calculations. They must be replaced by a statistical method, redesigned as an explicitly non-power planning aid, or deprecated.

## Promotion criteria

### EXPERIMENTAL → VALIDATION_PENDING

- Statistical specification approved by a statistician.
- Recommended package/function availability verified.
- Supported domain and failure behavior frozen.
- Test manifest and independent benchmark plan reviewed.

### VALIDATION_PENDING → VALIDATED

- All applicable gates pass in the pinned environment.
- No unresolved material benchmark discrepancies.
- Simulation precision criteria pass where applicable.
- Assumptions and limitations are accurate and user-visible.
- Independent statistical reviewer signs the validation report.

### VALIDATED → PRODUCTION

- Release and integration tests pass in the immutable production image.
- Clinical Development Agent routing cannot reach unsupported variants.
- Every response includes provenance, assumptions, output units, and validation record.
- Monitoring detects package/runtime drift and numerical regressions.
- Rollback environment and incident procedure are tested.
- Product owner and statistical owner approve exposure.

## Change control and revalidation

Full or targeted revalidation is required for changes to:

- Formula, algorithm, test statistic, approximation, or simulation model.
- Package/R version or numerically material dependency.
- Parameter defaults, transformations, allocation convention, sidedness, or rounding.
- Output unit or dropout/event conversion.
- RNG, parallelization, seed handling, or replicate count.
- Supported input domain or error/fallback behavior.

Documentation-only changes can bypass numerical revalidation only after confirming that they do not change method semantics or routing. Any discrepancy found after release immediately demotes the affected tuple to VALIDATION_PENDING or EXPERIMENTAL and blocks production routing until disposition.

## Validation record template

Each method's report should contain:

| field | required content |
|---|---|
| Identity | test key, variant, spec version, implementation commit |
| Status | current lifecycle status and date |
| Method | estimand, hypotheses, engine, package/function |
| Domain | supported inputs and explicit exclusions |
| Provenance | primary method and guideline references |
| Environment | session info, lockfile/image digest, RNG details |
| Evidence | unit, benchmark, cross-engine, edge, reverse, allocation, sidedness, dropout, simulation tests |
| Deviations | discrepancies, accepted tolerances, rationale |
| Limitations | model and operational limitations shown to users |
| Approval | implementer, independent statistician, release approver |
