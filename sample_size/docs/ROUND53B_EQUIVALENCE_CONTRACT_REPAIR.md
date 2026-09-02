# Round 5.3B — equivalence TOST contract repair investigation

## Decision

`equivalence` is marked **SPEC_REPAIR_REQUIRED** in this governance record. Its calculator remains `IMPLEMENTED_UNVALIDATED`; its frozen specification and implementation have not been silently changed. No benchmark tolerance was changed and neither failed fixture was suppressed.

Recommendation: **Option B**, replace `TrialSize::TwoSampleMean.Equivalence` with `PowerTOST::power.TOST` as the authoritative exact forward-power engine, using `logscale=FALSE`, `design="parallel"`, `method="exact"`, explicit bounds, true mean difference, common SD, and explicit integer arm sizes. A project-owned deterministic allocation-constrained integer search should call that authoritative forward function; it must not reimplement the statistical power equation. The repaired specification must be approved and refrozen before implementation.

PowerTOST is preferred over TOSTER because PowerTOST 1.5.7 is already an installed project dependency, directly documents original-scale mean differences, exact Owen-Q/bivariate noncentral-t methods, parallel designs, and unbalanced group vectors. This is a new method-specific use and therefore still requires separate qualification; prior bioequivalence validation does not automatically validate this contract.

## Intended target method

- Two independent parallel groups with a continuous endpoint and common population SD `sigma`.
- Estimand `theta = mean_treatment - mean_control`.
- Symmetric bounds `L=-M`, `U=+M`, with `M>0` and `abs(theta)<M`.
- TOST hypotheses `H01: theta<=L` versus `theta>L`, and `H02: theta>=U` versus `theta<U`.
- Success requires rejection of both component null hypotheses at one-sided alpha.
- Arbitrary expected `theta` inside the bounds and a prospectively fixed `n_treatment/n_control` allocation ratio.
- Analysis output is integer participants in each arm; dropout inflation occurs only after the analyzable design is finalized.

This target is not equivalent to sizing only against the closest bound with a symmetric tail approximation.

## Deterministic defect reproduction

The following values are copied from `round5_fixed_design_evidence.json`. Repeated executions in Round 5.3 produced the same package and independent results.

| Fixture | theta | M | SD | alpha | target power | nT/nC | TrialSize continuous return | integer nT/nC | adapter power | independent joint-normal power | discrepancy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `eq_k2` | 0.1 | 0.5 | 1.0 | 0.05 | 0.80 | 2 | 160.5721378250 | 161/81 | 0.8034682368 | 0.8988411360 | 0.0953728992 |
| `eq_khalf` | -0.1 | 0.5 | 1.2 | 0.05 | 0.90 | 0.5 | 146.0993465212 | 147/293 | 0.9016900119 | 0.9503651537 | 0.0486751417 |

A read-only candidate check with installed PowerTOST 1.5.7 returned exact powers 0.8972844 and 0.9498308 for the same integer arm sizes. These are candidate-audit results, not new passing equivalence benchmarks.

The zero-difference fixture passed because the two component distances are then equal. The defect appears when the expected difference is not centered.

## TrialSize 1.4.1 source and documentation

The installed function has formals `(alpha, beta, sigma, k, delta, margin)` and executes:

```text
n2 = (qnorm(1-alpha) + qnorm(1-beta/2))^2
     * sigma^2 * (1 + 1/k)
     / (delta - abs(margin))^2
n1 = k * n2
return(n1)
```

Consequences directly established from this source:

1. It is a closed-form normal-quantile calculation, not an exact finite-sample joint TOST calculation.
2. `abs(margin)` forces symmetric treatment of `+theta` and `-theta`.
3. `delta-abs(margin) = M-|theta|` is the distance to the nearest equivalence bound.
4. `qnorm(1-beta/2)` allocates beta symmetrically, effectively using the centered approximation `2*Phi((M-|theta|)/SE-z_alpha)-1`. For nonzero theta, the two true component rejection probabilities are unequal, so this is not their joint probability.
5. Unequal allocation only enters the variance multiplier through `k`; it does not repair the symmetric-power approximation.
6. The help page describes the hypothesis and sample-size function but does not claim exact TOST power. The source establishes the approximation.

There is also an allocation-label ambiguity that must be repaired. The help page says `k=n1/n2`, defines `margin=mu2-mu1` with test `mu2` and control `mu1`, and says `k=2` represents a “1 to 2 test-control allocation.” Combined with `n1=k*n2`, this implies `k=n_control/n_treatment`, not the frozen public `n_treatment/n_control`. Restricting theta to zero would not resolve that mapping problem.

Package provenance: TrialSize 1.4.1 is the installed and CRAN version audited here; CRAN lists publication on 2024-11-05. Official package page: https://cran.r-project.org/package=TrialSize

## Independent exact joint-TOST reference

Let `c=1/nT+1/nC`, `nu=nT+nC-2`, `D` be the observed treatment-minus-control difference, and `Q=nu*S_p^2/sigma^2`. Under the common-normal-variance model:

- `D ~ Normal(theta, sigma^2*c)`;
- `Q ~ ChiSquare(nu)`;
- `D` and `Q` are independent.

With `tcrit=t_(1-alpha,nu)`, both TOST components reject exactly when

```text
-M + tcrit*sigma*sqrt(c*Q/nu) < D
and
D < M - tcrit*sigma*sqrt(c*Q/nu).
```

Therefore exact joint power is the one-dimensional integral

```text
Integral from 0 to qmax of
  [Phi((M-w(q)-theta)/(sigma*sqrt(c)))
   - Phi((-M+w(q)-theta)/(sigma*sqrt(c)))]
  * chi_square_density(q; nu) dq,

w(q) = tcrit*sigma*sqrt(c*q/nu),
qmax = nu * [M/(tcrit*sigma*sqrt(c))]^2.
```

The integrand is zero if the interval is empty. This is equivalent to evaluation through Owen's Q or the joint/bivariate noncentral-t distribution. The new `mean_equivalence_exact_tost_power` helper is validation-only and preserves this target definition; it is not a production calculator or an approved authority.

Primary statistical references named by the candidate packages are Phillips (1990), DOI 10.1007/BF01063556, and Diletti, Hauschke & Steinijans (1991).

## Candidate R audit

No package was installed during this investigation. TrialSize 1.4.1 and PowerTOST 1.5.7 were already installed; TOSTER was not installed and was evaluated from CRAN documentation/source only.

| Package/function | Status and formals | Nonzero theta / bounds | Unequal allocation | Solve N / forward power | Output and documentation assessment |
|---|---|---|---|---|---|
| `TrialSize::TwoSampleMean.Equivalence` | CRAN 1.4.1; installed. `(alpha,beta,sigma,k,delta,margin)` | Accepts nonzero margin and symmetric M, but uses nearest-bound symmetric approximation | `k` exists, but help/source group labels conflict with frozen orientation | Sample-size scalar only; no forward function | Returns continuous `n1`; documentation does not identify an exact method. Not suitable for the full target. |
| `PowerTOST::power.TOST` | CRAN 1.5-7; installed. `(alpha=0.05,logscale=TRUE,theta1,theta2,theta0,CV,n,design="2x2",method="exact",robust=FALSE)` | Yes: `logscale=FALSE`, theta0 true difference, theta1/theta2 explicit bounds | Yes for forward power: `n` may be a vector of group sizes; documentation says balanced and unbalanced formulas are covered | Exact forward power. `sampleN.TOST(alpha,targetpower,logscale,theta0,theta1,theta2,CV,design,method,robust,print,details,imax)` solves total N under its built-in allocation, not an arbitrary public ratio | `power.TOST` returns power; `sampleN.TOST` returns total N and achieved power. Strong method documentation, exact Owen-Q or bivariate noncentral-t options. Current CRAN publication 2025-09-23. |
| `TOSTER::power_t_TOST` | CRAN 0.8.6, lifecycle “Stable”; not installed. `(n=NULL,delta=0,sd=1,eqb,low_eqbound=NULL,high_eqbound=NULL,alpha=NULL,power=NULL,type="two.sample")` | Yes; scalar `eqb` creates symmetric bounds and `delta` is true difference | Forward power accepts a two-element `n` vector | Solves N with `n=NULL`, but its uniroot solves a scalar equal-per-group N; arbitrary allocation would require external integer search | Returns a `power.htest`-style object. Documentation explicitly claims exact Owen-Q/direct bivariate noncentral-t power. Current CRAN publication 2025-08-22. |

Official documentation:

- PowerTOST package and maintenance metadata: https://cran.r-project.org/package=PowerTOST
- PowerTOST exact power arguments: https://rdrr.io/cran/PowerTOST/man/power.TOST.html
- PowerTOST sample-size arguments/output: https://rdrr.io/cran/PowerTOST/man/sampleN.TOST.html
- TOSTER package and maintenance metadata: https://cran.r-project.org/package=TOSTER
- TOSTER `power_t_TOST` reference: https://cran.r-project.org/web/packages/TOSTER/TOSTER.pdf

## Option comparison

| Option | Fidelity | Complexity | Validation burden | Maintenance/dependency | Regulatory auditability and reproducibility |
|---|---|---|---|---|---|
| A — restrict TrialSize to theta=0 | Correct only at the center after separately repairing allocation orientation; loses the explicitly intended arbitrary-theta domain | Low | Moderate because allocation mapping and zero-only boundary must be requalified | Lowest dependency change | Auditable if labeled narrowly, but clinically restrictive and invites misuse outside theta=0 |
| B — PowerTOST exact forward authority plus deterministic allocation search | Highest fidelity to the specified pooled-variance TOST, arbitrary theta, and unequal integer arms | Moderate | New method-specific package qualification, direct reproduction, independent integral, monotonicity, allocation search, and cross-platform evidence | Reuses existing PowerTOST; no new package. Version remains pinned | Strong: named mature package, reproducible calls, explicit arm search, and independent mathematical reference |
| C — project-owned exact solver and inversion | Potentially identical if correctly implemented | Highest | Highest: quadrature, tails, root/integer search, error bounds, and cross-engine validation all become project responsibility | No additional R dependency, but substantial long-term numerical maintenance | Fully inspectable but more difficult to justify and maintain than a mature package authority |

## Required repaired contract before implementation

The equivalence spec must be deliberately unfrozen and refrozen with at least:

- engine `PowerTOST::power.TOST`, exact method, original scale, parallel design;
- explicit mapping `theta0=expected_difference`, `theta1=-M`, `theta2=+M`, `CV=sd`, one-sided `alpha`;
- explicit vector order for `n` and independent confirmation that it maps to treatment/control as declared;
- public allocation ratio `n_treatment/n_control` and a deterministic integer enumeration/search rule;
- minimum arm sizes, search bounds, monotonicity/failure behavior, and tie-breaking;
- sample-size output per arm and total, followed by per-arm dropout inflation;
- forward power as a supported solve mode only if separately approved;
- exact package version policy and a new equivalence benchmark ID;
- independent exact-integration, direct-package, simulation, allocation, and cross-platform gates.

Until that governance action occurs, the existing TrialSize calculator and its two failed Round 5 fixtures remain diagnostic evidence only. Implementation change is required, but implementation is explicitly deferred from Round 5.3B.

## Preservation

- Six Round 5 `BENCHMARK_VALIDATED` methods were not modified.
- Round 4 methods and evidence were not modified.
- Round 5 passing fixtures and all validation tolerances were not modified.
- No equivalence benchmark was fabricated or promoted.
