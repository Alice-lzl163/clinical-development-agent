# Round 5.3 numerical validation

## Outcome

Round 5 benchmark ID `round5-fixed-design-v1` was frozen on 2026-09-02 for six methods. `proportion_one`, `proportion_paired`, `non_inferiority`, `superiority_margin`, `odds_ratio`, and `risk_ratio` passed their required gates and are `BENCHMARK_VALIDATED`. `equivalence` remains `IMPLEMENTED_UNVALIDATED` because independent TOST validation exposed a `STATISTICAL_CONTRACT_DEFECT`. No method was promoted to `PRODUCTION_CANDIDATE` or `PRODUCTION`.

The candidate set contains 22 fixtures: 20 passed and were retained as validated evidence; the two failing equivalence cases remain diagnostic, explicitly `VALIDATION_PENDING`, and were not represented as passing benchmarks. All 96 authoritative R executions completed successfully.

## Environment

- Python 3.12.7
- SciPy 1.18.1 (validation only)
- R 4.6.1 (2026-06-24 ucrt), x86_64-w64-mingw32
- jsonlite 2.0.0
- pwr 1.3.0
- TrialSize 1.4.1
- gsDesign 3.11.0

Only these exact versions are covered by this local evidence. gsDesign 3.11.0 moved from `INSTALLED_UNVALIDATED` to the validated dependency set for `odds_ratio` and `risk_ratio` only. No compatibility is inferred for other gsDesign versions or methods.

## Gate results

| Method | Package | Direct | Independent | Inverse/forward | Allocation/dropout | Edge/monotonicity | Simulation | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| proportion_one | pwr::pwr.p.test | PASS | PASS | PASS | PASS | PASS | N/A | BENCHMARK_VALIDATED |
| proportion_paired | TrialSize::McNemar.Test | PASS | PASS | independent forward PASS | PASS | PASS | PASS | BENCHMARK_VALIDATED |
| equivalence | TrialSize::TwoSampleMean.Equivalence | PASS | **FAIL** | independent forward FAIL | PASS | PASS | N/A | IMPLEMENTED_UNVALIDATED |
| non_inferiority | TrialSize::TwoSampleProportion.NIS | PASS | PASS | independent forward PASS | PASS | PASS | PASS | BENCHMARK_VALIDATED |
| superiority_margin | TrialSize::TwoSampleProportion.NIS | PASS | PASS | independent forward PASS | PASS | PASS | PASS | BENCHMARK_VALIDATED |
| odds_ratio | gsDesign::nBinomial | PASS | PASS | PASS | PASS | PASS | PASS | BENCHMARK_VALIDATED |
| risk_ratio | gsDesign::nBinomial | PASS | PASS | PASS | PASS | PASS | PASS | BENCHMARK_VALIDATED |

Unsupported public power modes were not added. Their forward evaluations are validation evidence only.

## Independent references

- `proportion_one`: independently evaluated Cohen-h arcsine normal power for greater, less, and two-sided alternatives.
- `proportion_paired`: independently transcribed McNemar asymptotic equation plus paired multinomial simulation. Swapping discordant cells produced identical two-sided sample size.
- `equivalence`: independently evaluated joint two-one-sided normal power at the final integer arm sizes. This is stricter than merely reproducing TrialSize's inverse formula.
- `non_inferiority` and `superiority_margin`: independent treatment-minus-control risk-difference normal power and null-boundary binomial simulations.
- `odds_ratio` and `risk_ratio`: independent Python Farrington-Manning equations, including constrained null probabilities, scale, tail, treatment/control orientation, and `ratio=n_control/n_treatment`. The validation did not use a second gsDesign call as its independent reference.

## Equivalence defect

TrialSize 1.4.1 computes sample size using a symmetric approximation based on `abs(margin)` and `qnorm(1-beta/2)`. Its adapter-derived power similarly treats both TOST components symmetrically. The independent joint TOST probability agrees at expected difference zero but not away from the interval center:

- `eq_k2`: adapter/package-derived power 0.8034682368; independent joint TOST power 0.8988411360; absolute difference 0.0953728992.
- `eq_khalf`: adapter/package-derived power 0.9016900119; independent joint TOST power 0.9503651537; absolute difference 0.0486751417.

Classification: `STATISTICAL_CONTRACT_DEFECT`. The frozen implementation was not silently changed. Before promotion, the method requires a repaired specification selecting a production engine and power definition that genuinely implement parallel-group TOST with the declared expected difference and allocation semantics.

## Simulation governance

All scenarios used 100,000 replicates and prespecified seeds. The acceptance rules were declared in the harness: boundary error must differ from alpha by no more than `max(0.01, 3*MCSE)`; McNemar simulated power must differ from analytical power by no more than `max(0.02, 3*MCSE)`.

| Scenario | Seed | Estimate | MCSE | 95% CI | Target | Status |
|---|---:|---:|---:|---|---:|---:|
| McNemar alternative power | 5302025 | 0.80724 | 0.00124741 | [0.804795, 0.809685] | 0.802568 | PASS |
| NI null boundary | 5302026 | 0.02454 | 0.00048926 | [0.023581, 0.025499] | 0.025 | PASS |
| superiority-margin boundary | 5302027 | 0.02527 | 0.00049630 | [0.024297, 0.026243] | 0.025 | PASS |
| OR constrained null boundary | 5302028 | 0.02322 | 0.00047624 | [0.022287, 0.024153] | 0.025 | PASS |
| RR constrained null boundary | 5302029 | 0.02249 | 0.00046887 | [0.021571, 0.023409] | 0.025 | PASS |

The qualification simulation is not intended for every routine CI run. Lightweight regression tests verify the frozen evidence structure and independent reference equations.

## Rounding, allocation, and dropout

Every method was checked at dropout 0, 0.10, and 0.20 on an otherwise fixed design. Analyzable N remained constant and randomized N was monotone. OR/RR continuous `n1` and `n2` were ceiled separately, realized allocation was passed to a forward power check, and achieved power met target. Equivalence, NI, and superiority arm interpretation was checked for treatment/control ratios 1, 2, and 0.5. McNemar output remained complete matched pairs.

## Evidence and preservation

- Inputs and frozen outputs: `sample_size/validation/benchmarks/round5_fixed_design.yaml`
- Full R calls, arguments, outputs, independent results, hashes, and session metadata: `sample_size/validation/round5_fixed_design_evidence.json`
- Machine-readable outcome: `sample_size/validation/round5_validation_summary.yaml`
- Reproducible harness: `python -m sample_size.validation.run_round5_validation --write`

Round 4 evidence was not rewritten. Its Git blob hash remains `867f020c151dcf62c44f9a7ffdb5f4e2380d82aa` and file SHA-256 remains `7935b2c1dd1cc90cc960dcd9adfaea03f259a369f455c36c0ec1df271f8659a0`.
