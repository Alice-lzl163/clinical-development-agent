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
