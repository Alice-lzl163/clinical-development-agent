# Round 5.3C — equivalence specification repair and refreeze

## Outcome

Only `sample_size/specs/equivalence.yaml` was statistically repaired. It is refrozen as `SPEC_FROZEN` with lifecycle `VALIDATION_PENDING`; it is not `BENCHMARK_VALIDATED`, `PRODUCTION_CANDIDATE`, or `PRODUCTION`. The replacement calculator is intentionally not implemented in this round.

The repaired method is an exact pooled-variance TOST for two independent parallel groups, common SD, treatment-minus-control mean difference, symmetric bounds `(-M,+M)`, arbitrary expected difference strictly inside those bounds, and fixed analyzable allocation `n_treatment/n_control`.

## Authoritative mapping

The intended numerical authority is `PowerTOST::power.TOST` from exact version 1.5.7:

| Package argument | Project value |
|---|---|
| `alpha` | one-sided TOST `alpha`, passed directly |
| `logscale` | `FALSE` |
| `theta0` | `expected_difference` |
| `theta1` | `-equivalence_margin` |
| `theta2` | `+equivalence_margin` |
| `CV` | common original-scale `sd` |
| `n` | `c(analyzable_treatment, analyzable_control)` |
| `design` | `"parallel"` |
| `method` | `"exact"` |
| `robust` | `FALSE` |

`sampleN.TOST` is not the inverse authority because it does not expose the project's arbitrary fixed allocation contract. The deterministic project search calls only `power.TOST` for numerical power; it does not implement TOST power itself.

## Verification of the two-element n vector

PowerTOST 1.5.7 documentation says a vector `n` contains the group counts and must have length equal to the number of groups. `known.designs()` identifies `parallel` as two parallel groups. Installed source inspection establishes that, for this common-variance parallel design, the function computes `nc=sum(1/n)` and then `n=sum(n)`. Thus the exact power is structurally invariant to swapping the two elements.

Asymmetric-arm live checks confirmed that invariance exactly at printed double precision:

| Inputs | `n=c(treatment,control)` | swapped n | exact power both ways |
|---|---|---|---:|
| theta 0.1, SD 1, bounds ±0.5 | `c(161,81)` | `c(81,161)` | 0.8972844142790725 |
| theta -0.1, SD 1.2, bounds ±0.5 | `c(147,293)` | `c(293,147)` | 0.9498308356243010 |

Consequently PowerTOST does not attach statistically distinguishable treatment/control meaning to vector position under the declared common-SD model. The project freezes `c(treatment,control)` as its traceability convention, and records both counts separately. Unequal variances or any model in which group position changes power is explicitly unsupported and would require a new contract.

## Allocation and deterministic integer search

Public allocation is `allocation_ratio=n_treatment/n_control`.

The structured `sample_size_search` contract is:

1. Minimum arm size is 2 and maximum arm size is 1,000,000.
2. Enumerate integer `analyzable_control` from 2 upward in steps of one.
3. For each candidate, set `analyzable_treatment=ceil(allocation_ratio*analyzable_control)`.
4. Reject a candidate exceeding either per-arm maximum.
5. Call exact `PowerTOST::power.TOST` on the candidate vector.
6. Accept the first candidate for which `achieved_power >= target_power`.
7. The first accepted control size is the deterministic tie-break.
8. If no candidate is accepted, raise a calculation-convergence error and return no result.

This gives an explicit finite-integer realization. The realized ratio is reported and may be slightly above the requested ratio because treatment N is ceiled. No continuous package N or randomized N is reverse-engineered into analyzable counts.

## Solve modes and outputs

Both modes are specified but remain numerically unvalidated:

- `sample_size`: requires expected difference, SD, margin, allocation ratio, alpha, target power, and dropout rate; uses the deterministic search.
- `power`: requires explicit integer `analyzable_treatment` and `analyzable_control`; target power, dropout, allocation ratio, and randomized counts are not accepted.

The result contract specifies analyzable treatment, analyzable control, analyzable total, achieved power, randomized treatment, randomized control, and randomized total. Dropout is applied with a separate ceiling per arm only after exact power accepts the analyzable design. Forward power never uses dropout-inflated enrollment.

## Domain and fail-closed rules

The specification requires positive SD, positive margin, positive allocation, alpha and power strictly between zero and one, and `abs(expected_difference)<equivalence_margin`. It explicitly excludes log-scale/bioequivalence targets, crossover or paired designs, asymmetric bounds, unequal population variances, covariate adjustment, clustering, stratification, and adaptive designs.

## Historical mapping

`TrialSize::TwoSampleMean.Equivalence` remains preserved in Round 5.3 evidence as diagnostic history. It is no longer the intended engine. Its nearest-bound symmetric approximation disagrees for nonzero expected differences, and its allocation labels are ambiguous relative to the project's public convention. The failed fixtures and their tolerances were not changed or deleted.

## Remaining qualification

A later implementation/validation round must:

- implement the adapter and integer search exactly as specified;
- verify exact package calls for centered and noncentered alternatives and allocation ratios 1, 2, and 0.5;
- compare against the independent pooled-variance joint-TOST integral and simulation;
- prove accepted-design power and preceding-candidate minimality;
- test alpha, dropout, monotonicity, maximum-bound failure, malformed outputs, and missing dependencies;
- establish cross-platform evidence and only then assign a new equivalence benchmark ID.

No old TrialSize equivalence benchmark may be inherited.

## Preservation

No production calculator or adapter was changed. The six Round 5 benchmark-validated methods, all Round 4 methods, Round 4 evidence, Round 5 passing fixtures, failed diagnostic evidence, and existing validation tolerances are unchanged.
