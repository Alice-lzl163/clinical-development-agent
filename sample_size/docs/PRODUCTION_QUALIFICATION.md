# Sample Size Production Qualification

Round 4.3 separates lifecycle governance from statistical calculation. It introduces no new calculator and promotes no method to production.

## Lifecycle model

Four independent dimensions prevent a single label from making ambiguous claims:

| Dimension | States | Meaning |
|---|---|---|
| Statistical specification | `SPEC_DRAFT`, `SPEC_FROZEN` | Whether the statistical contract is authorized and change-controlled |
| Implementation | `IMPLEMENTED_UNVALIDATED`, `BENCHMARK_VALIDATED` | Whether executable code exists and has passed numerical benchmarks |
| Numerical validation | `NOT_RUN`, `FAILED`, `BENCHMARK_VALIDATED` | Recorded outcome of the numerical gates |
| Production qualification | `NOT_ASSESSED`, `PRODUCTION_CANDIDATE`, `PRODUCTION` | Operational readiness and release approval |

This is the smallest backward-compatible change: existing specification fields remain valid, while the authoritative multidimensional state and qualification assessment live in `production_qualification.yaml`. Result objects retain `validation_status` for compatibility and add environment-match and versioned protocol metadata.

## Benchmark-validated contract

`BENCHMARK_VALIDATED` requires authoritative package reproduction, inverse/forward consistency, an independent numerical reference, allocation/dropout/rounding checks, edge and monotonicity checks, reproducible source-call replay, exact validated versions, fixture evidence, and every required gate passing.

It does not claim regulatory qualification, production readiness, universal validity outside declared assumptions, or equivalence under arbitrary dependency versions.

## Production-candidate gate

The machine-readable checklist covers the statistical contract, numerical validation, API behavior, runtime failures, reproducibility, protocol-ready output, and regression/change control. `PRODUCTION_CANDIDATE` requires every checklist item to be evidenced. `PRODUCTION` additionally requires independent release approval and operational controls; it cannot be inferred from historical code or benchmarks.

Runtime paths fail closed. Missing R or packages, package-contract errors, malformed JSON, process errors, timeouts, and non-finite output raise explicit errors. They never invoke an LLM, SciPy, remote execution, or a historical surrogate. SciPy remains validation-only.

## Dependency versions

- Exact R 4.6.1 and exact validated method-package version: `MATCHED_VALIDATED_ENVIRONMENT`.
- A different executable version: `UNVALIDATED_VERSION`, warning emitted, benchmark-equivalence status withheld.
- A version entered in the incompatibility registry: `INCOMPATIBLE_VERSION`, execution fails closed.

The validated package versions are pwr 1.3.0, TrialSize 1.4.1, and PowerTOST 1.5.7. The system never installs, upgrades, or downgrades dependencies automatically. The incompatible-version registry is intentionally empty until evidence identifies a version; absence from the registry is not evidence of compatibility.

## Protocol-ready output

`SampleSizeResult.to_protocol_dict()` separates statistical results, operational dropout/rounding adjustments, method metadata, validation metadata, interpretation, and exact reproducibility material. It does not create unsupported narrative claims. The legacy flat `to_dict()` remains unchanged for compatibility.

## Revalidation

Documentation-only formatting or wording changes are `NO_REVALIDATION`. Non-statistical serialization and error-mapping changes normally require `TARGETED_REVALIDATION`. Formula, method specification, adapter, allocation, dropout, rounding, authoritative function or package version, tolerance, and benchmark changes require `FULL_METHOD_REVALIDATION`. A change-control reviewer may always escalate the scope.

## Six-method gap assessment

All six Round 4.2 methods remain `BENCHMARK_VALIDATED`; none is a `PRODUCTION_CANDIDATE`. Their statistical, numerical, API, reproducibility, output, and change-control contracts are complete for this assessment. Runtime qualification remains incomplete because no evidence-backed incompatible-version registry exists and Linux/macOS runtime behavior has not been demonstrated. These gaps apply to `ttest_one`, `ttest_paired`, `ttest_ind`, `anova`, `proportion_two`, and `be_tost`.
