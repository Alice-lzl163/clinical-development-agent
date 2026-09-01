# Golden-Path Statistical Specification Freeze

## Scope and decision rule

This report covers the first ten calculator candidates only. `PASS` means no change was required by the independent review, `MODIFY` means the specification was corrected and now meets the frozen contract, and `BLOCK` means a defect still prevents calculator implementation.

All ten required modifications. After correction, all ten have `specification_status: SPEC_FROZEN`. Their lifecycle remains `VALIDATION_PENDING`; statistical specification freeze is not numerical validation and is not production approval.

| test_key | review disposition | resulting status | frozen correction |
|---|---|---|---|
| `ttest_ind` | MODIFY | SPEC_FROZEN | Equal allocation only; explicit alpha, power, alternative, and per-arm dropout/rounding contract. |
| `ttest_one` | MODIFY | SPEC_FROZEN | Explicit directional alternative and complete `pwr.t.test` argument provenance. |
| `ttest_paired` | MODIFY | SPEC_FROZEN | Paired-test label, no generic crossover claim, and output defined as complete analyzable pairs. |
| `anova` | MODIFY | SPEC_FROZEN | Upper-tail omnibus F convention, non-applicable sidedness, and balanced allocation only. |
| `proportion_two` | MODIFY | SPEC_FROZEN | TrialSize orientation fixed as `p1=treatment`, `p2=control`, `k=n_treatment/n_control`; asymmetric benchmark required. |
| `be_tost` | MODIFY | SPEC_FROZEN | Evaluable and randomized totals separated; 2x2 dropout inflation rounds to an even sequence-balanced block. |
| `group_sequential` | MODIFY | SPEC_FROZEN | Opaque R design input replaced by `SequentialDesignSpec` and an explicit `getDesignGroupSequential` adapter. |
| `gsd_proportion` | MODIFY | SPEC_FROZEN | Shared sequential component plus explicit binary endpoint adapter; alpha and beta provenance retained. |
| `survival_exact` | MODIFY | SPEC_FROZEN | Renamed display method, historical “exact” qualifier rejected, and exponential event/dropout derivations declared. |
| `gsd_survival` | MODIFY | SPEC_FROZEN | Shared sequential, endpoint, accrual, and dropout components feed the survival package adapter. |

Totals: **PASS 0**, **MODIFY 10**, **BLOCK 0**. Result after modification: **10 SPEC_FROZEN**.

## Guardrails before calculator work

The schema and semantic suite now reject unequal allocation for the initial independent t-test and ANOVA contracts, crossover labeling for the paired test, reversed TrialSize arm orientation, loss of 2x2 sequence balance, incomplete sequential designs, unanchored dropout conversions, non-exponential median-to-hazard conversion, missing sequential alpha/beta provenance, and vague frozen mappings.

No numerical calculator or package execution code was added in this phase.

## Round 3.7 final correction audit

The five reviewed methods were re-evaluated from their current content rather than retaining freeze status by inheritance.

| test_key | Round 3.7 result | correction |
|---|---|---|
| `ttest_ind` | PASS | No statistical specification change was required. The shared package-contract invariant recognizes package `n` as the intentionally unsupplied inverse-solve target. |
| `anova` | MODIFIED_AND_FROZEN | Corrected `pwr::pwr.anova.test$n` from total N to analyzable subjects per group; added explicit analyzable and randomized per-group and total derivations. |
| `be_tost` | MODIFIED_AND_FROZEN | Froze balanced allocation for both 2x2 and parallel designs and defined a two-subject randomization block plus equal sequence/arm totals. |
| `group_sequential` | MODIFIED_AND_FROZEN | Added prespecified `alternative_direction` and the conditional `directionUpper` mapping; direction is never inferred from the mean difference. |
| `survival_exact` | MODIFIED_AND_FROZEN | Restored explicit alpha, beta/power, and sidedness; declared `followUpTime`; and froze uniform relative accrual with `accrualIntensity = 1` and `accrualIntensityType = "relative"`. |

All five remain `VALIDATION_PENDING`; none is `VALIDATED` or `PRODUCTION`.

### Package-signature finding

Official `rpact` source for `getSampleSizeSurvival` declares `followUpTime = NA_real_` and `accrualIntensityType = c("auto", "absolute", "relative")`. The previous frozen adapter mapped `followUpTime` without listing it and did not override the automatic accrual-intensity interpretation. Fixed-design `alpha`, `beta`, and `sided` are accepted through `getSampleSizeSurvival(...)` and forwarded to `getDesignFixed`; the specification now records that forwarding and supplies all three explicitly.

The package-contract invariant is applied to every active `SPEC_FROZEN` package engine and design-component adapter. Explicitly unresolved mappings in non-executable `DRAFT` specifications remain validation work and are not treated as active adapters.

The shared invariant found the same missing `followUpTime` declaration in `gsd_survival`; only its formal-argument declaration was corrected. Its statistical design and mappings were not changed.

### Regression coverage added

- ANOVA package `n = 32` with three groups implies analyzable total 96, never 32.
- Bioequivalence evaluable N 24 with 10% dropout implies randomized N 28 and balanced 14/14 allocation for both 2x2 and parallel designs.
- One-sided higher and lower sequential alternatives map distinctly to `directionUpper = TRUE` and `FALSE`; two-sided maps to `NA` by contract.
- Fixed survival power and sidedness are explicit package-call inputs, and uniform relative accrual is explicit.
- Every active frozen package mapping names a declared formal; unmapped formals must be an inverse-solve output or document intentional reliance on a package default.

Round 3.7 result: **PASS 1**, **MODIFIED_AND_FROZEN 4**, **BLOCKED 0**. No remaining specification blocker prevents calculator implementation for these five methods; numerical validation remains mandatory before lifecycle promotion.
