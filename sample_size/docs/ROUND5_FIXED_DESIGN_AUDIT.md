# Round 5.1 Fixed-Design Statistical Audit

## Decision summary

This is a specification audit, not numerical implementation or validation. Historical source establishes provenance only. Package behavior below was checked against installed TrialSize 1.4.1 and pwr 1.3.0 code, formals, and help. `gsDesign` was not installed locally, so its OR/RR mappings remain draft and require official-package verification before freeze.

| test_key | historical_method | historical_issue | target_statistical_method | candidate_authoritative_engine | migration_action | remaining_spec_issue | freeze_ready |
|---|---|---|---|---|---|---|---|
| `proportion_one` | Cohen-h one-proportion approximation via `pwr::pwr.p.test` | Approximate, not exact binomial; earlier history referenced a nonexistent function | One-sample arcsine-transformed asymptotic proportion test with explicit p/p0 and tail | `pwr::pwr.p.test` | KEEP | Numerical validation is future work | YES |
| `proportion_paired` | `pwr::pwr.2p.test` on marginal proportions | Independent-proportion surrogate, not paired binary power | Two-sided asymptotic McNemar design based on both directional discordances | `TrialSize::McNemar.Test` | REPLACE | Forward power and one-sided designs are intentionally unsupported | YES |
| `equivalence` | TrialSize mean-equivalence inversion plus unrelated normal fallback/reverse path | Forward/reverse engines differed; expected difference and margin semantics were incomplete | Parallel continuous-mean TOST with common SD and one symmetric margin | `TrialSize::TwoSampleMean.Equivalence` | KEEP_AND_VALIDATE | Asymmetric bounds and forward power are unsupported | YES |
| `non_inferiority` | `TwoSampleProportion.NIS` with custom fallback | Silent fallback and signed margin ambiguity | One-sided independent binary risk-difference NI, higher success favorable | `TrialSize::TwoSampleProportion.NIS` | KEEP_AND_VALIDATE | Lower-is-better endpoints require explicit recoding; forward power unsupported | YES |
| `superiority_margin` | Equality routine plus custom nonzero-margin fallback | Package and fallback represented different hypotheses | One-sided independent binary superiority over a positive risk-difference margin | `TrialSize::TwoSampleProportion.NIS` | REPLACE | Forward power unsupported | YES |
| `odds_ratio` | Convert OR to treatment risk, then power Cohen-h risk difference | Surrogate test; OR alone is underidentified | Independent binary Farrington–Manning planning on OR scale with baseline risk | candidate `gsDesign::nBinomial(scale="OR")` | REPLACE | Local package unavailable; p1/p2 orientation, returned units, and forward power require official verification | NO |
| `risk_ratio` | Convert RR to treatment risk, then power Cohen-h risk difference | Surrogate test and weak boundary handling | Independent binary Farrington–Manning planning on RR scale with baseline risk | candidate `gsDesign::nBinomial(scale="RR")` | REPLACE | Same unverified package semantics as OR; derived-risk feasibility needs adapter validation | NO |

## Frozen statistical contracts

### One-sample proportion

The endpoint is one Bernoulli outcome per participant. The estimand is `p - p0`; `null_probability` is always p0 and `alternative_probability` is always the design p. The public direction is `two_sided`, `greater`, or `less`; direction is never inferred from whether an event sounds favorable. The derived signed Cohen h is `2 asin(sqrt(p)) - 2 asin(sqrt(p0))`. The selected pwr method is explicitly asymptotic. It supports inverse sample size and forward power; power requires `analyzable_sample_size`, never randomized N. Package `n` is total analyzable participants.

### Paired proportion

The unit is a complete matched participant/pair with two binary measurements. Public inputs are `p_treatment_only = P(T=1,C=0)` and `p_control_only = P(T=0,C=1)`. Their difference drives power; concordant cells affect neither McNemar contrast, but the two discordances must be jointly feasible. TrialSize documents `psai=p01/p10` and `paid=p01+p10`; this contract fixes p01 as treatment-only and p10 as control-only. The returned scalar is analyzable complete pairs. Only two-sided inverse sample size is declared because the function uses `qnorm(1-alpha/2)` and has no forward-power interface. Marginal success probabilities alone fail closed. Historical `pwr.2p.test` behavior is prohibited.

### Continuous-mean equivalence

This key is not average bioequivalence; `be_tost` remains separate. It represents two independent parallel groups, a common outcome SD, expected treatment-minus-control mean difference, and a symmetric interval `(-equivalence_margin,+equivalence_margin)`. H0 is outside/on the interval and H1 is strictly inside. TrialSize accepts one `delta`, so asymmetric bounds are not claimed. Its `k=n1/n2` is treatment/control allocation and it returns continuous n1 (treatment), from which control n is derived before upward integer/allocation checks. Alpha is the one-sided component level of TOST. Only inverse sample size is declared.

### Binary non-inferiority and superiority margin

Both keys share the statistical method identity `binary_parallel_risk_difference_margin_normal`: independent Bernoulli groups with treatment-minus-control risk difference and `k=n_treatment/n_control`. They remain distinct public questions. NI accepts a positive clinical loss magnitude Δ and derives package `margin=-Δ`, testing H0 `pT-pC <= -Δ`. Superiority accepts a positive required gain M and passes `margin=M`, testing H0 `pT-pC <= M`. The expected package `delta` is always `pT-pC`. TrialSize returns treatment-group n1; control n follows from k. Alpha is one-sided. The historical fallback paths must not return. Only higher-success-is-better, inverse sample size is frozen.

## Draft OR/RR contracts

OR is defined as `[pT/(1-pT)]/[pC/(1-pC)]`; RR is `pT/pC`. Neither ratio determines sample size without `control_probability`, and both require explicit null and alternative ratios plus direction. Derived alternative risks must remain strictly within (0,1). These keys do not represent logistic regression, case-control studies, matched data, hazard ratios, or relative risk reduction. They remain `DRAFT`: the candidate gsDesign package is unavailable locally, so the exact p1/p2 orientation, output unit, null-scale mapping, supported allocation, and forward-power route have not been treated as verified.

## Package audit

| Function | Verified formals | Actual method/output semantics | Declared modes and limitations |
|---|---|---|---|
| `pwr::pwr.p.test` | `h,n,sig.level,power,alternative` | Arcsine one-proportion asymptotic power; `n` is total observations | Sample size and power; not exact binomial |
| `TrialSize::McNemar.Test` | `alpha,beta,psai,paid` | Two-sided normal approximation; `psai=p01/p10`, `paid=p01+p10`; scalar complete-pair n | Sample size only; no one-sided or exact claim |
| `TrialSize::TwoSampleMean.Equivalence` | `alpha,beta,sigma,k,delta,margin` | Symmetric normal-approximation mean equivalence; returns n1 with k=n1/n2 | Sample size only; common SD, symmetric margin |
| `TrialSize::TwoSampleProportion.NIS` | `alpha,beta,p1,p2,k,delta,margin` | One-sided normal approximation H0 `p1-p2 <= margin`; returns n1 | Sample size only; explicit sign mapping required |
| candidate `gsDesign::nBinomial` | Existing draft records `p1,p2,beta,alpha,sided,delta0,ratio,scale,np` | Not locally verified in this round | OR/RR stay draft; no implementation authorization |

## General sample-size and unsupported-domain policy

Analyzable quantities are kept separate from operational dropout inflation. Group or pair quantities are rounded upward, allocation is rechecked after integer rounding, and dropout is applied per applicable unit. Power mode is declared only for one-sample proportion and requires analyzable N explicitly. Clustered, stratified, repeated, covariate-adjusted, exact-test, and boundary designs fail closed unless expressly included in an individual specification.
