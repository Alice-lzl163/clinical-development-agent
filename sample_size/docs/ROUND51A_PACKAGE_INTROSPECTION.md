# Round 5.1A Package Introspection

## Scope and environment

This pass changes statistical specifications and specification tests only. It does not implement calculators or make numerical-validation claims. Introspection used local R 4.6.1 and TrialSize 1.4.1. `packageVersion("gsDesign")` failed because gsDesign is not installed in this pinned local environment; it was not installed as part of this pass.

## TrialSize 1.4.1 findings

### `McNemar.Test(alpha, beta, psai, paid)`

The installed function computes its normal critical value with `qnorm(1-alpha/2)`, so its contract is two-sided only. Package help defines `psai` as `p01/p10` and `paid` as `p10+p01`. With the package's before/after table interpreted as control/treatment, `p01` is control failure followed by treatment success (treatment-only) and `p10` is control success followed by treatment failure (control-only). The returned scalar is the required number of complete matched observations. The public power solve mode remains unsupported.

The documented call `McNemar.Test(0.05, 0.2, 0.2/0.5, 0.7)` returned `58.63224` before upward rounding.

### `TwoSampleMean.Equivalence(alpha, beta, sigma, k, delta, margin)`

The installed body uses `qnorm(1-alpha)` directly, so public `alpha` is the one-sided significance level for each TOST component and is not divided by two by an adapter. The function defines `k=n1/n2`, calculates `n2`, and returns `n1=k*n2`. `delta` is the positive symmetric equivalence margin, and the body uses `abs(margin)` for the assumed mean difference. Package help labels `margin=mu2-mu1` with test `mu2` and control `mu1`; the project contract independently binds the returned `n1` to treatment and `n2` to control. This binding and allocation interpretation require numerical validation before implementation.

The documented call `TwoSampleMean.Equivalence(0.1, 0.1, 0.1, 1, 0.05, 0.01)` returned `107.0481`. With otherwise identical arguments, `k=2` returned `160.5721` and `k=0.5` returned `80.28607`, consistent with the source's returned `n1=k*n2` calculation.

### `TwoSampleProportion.NIS(alpha, beta, p1, p2, k, delta, margin)`

Package help and source define `p1` as test/treatment, `p2` as reference/control, `k=n1/n2`, and `delta=p1-p2`. The stated test is `H0: p1-p2 <= margin` versus `H1: p1-p2 > margin`. Thus a positive clinical non-inferiority loss magnitude maps to a negative package margin, while a positive superiority margin is passed directly. The returned scalar is `n1`, the treatment-group analyzable size under the project contract.

The package example `TwoSampleProportion.NIS(0.05, 0.2, 0.65, 0.85, 1, 0.2, 0.05)` returned `97.54701` before upward rounding.

## gsDesign `nBinomial` finding and freeze decision

Live `args(gsDesign::nBinomial)`, `formals(gsDesign::nBinomial)`, package source/help, and empirical calls could not be obtained because gsDesign is absent. Consequently the following cannot be locally verified in this pass: `p1`/`p2` orientation, allocation-ratio orientation, `scale="OR"` and `scale="RR"`, `delta0`, superiority/non-inferiority direction, sidedness and alpha conventions, inverse versus `n` forward-power behavior, total versus arm-level output, `outtype`, and rounding implications.

The clinical contracts remain explicit: OR is treatment odds divided by control odds, RR is treatment risk divided by control risk, control probability is required, and the alternative treatment probability transformation is machine-readable and must be feasible. Package mappings remain unresolved. Both `odds_ratio` and `risk_ratio` therefore remain `DRAFT`; freezing either without live package evidence would be inference.

## Benchmark-language boundary

For every specification in this pass whose public power solve mode is false, benchmark language now describes any forward-power calculation as an independent validation calculation only. It does not advertise or imply a public power solve mode.
