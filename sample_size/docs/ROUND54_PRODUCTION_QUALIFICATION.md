# Round 5.4 — production qualification

## Current decision

All seven Round 5 methods passed the local production-qualification preflight, but none is promoted to `PRODUCTION_CANDIDATE` in this commit. Gates A–G and I pass; gate H remains `PENDING` because the updated exact-version GitHub Actions workflow has not yet executed on Windows, Ubuntu, and macOS. Local evidence cannot be represented as hosted OS evidence.

The independent lifecycle state is therefore `SPEC_FROZEN`, `IMPLEMENTED`, `BENCHMARK_VALIDATED`, and production qualification `NOT_ASSESSED`. No method is `PRODUCTION`.

## Gate matrix

| Method | A | B | C | D | E | F | G | H | I | Final status |
|---|---|---|---|---|---|---|---|---|---|---|
| `proportion_one` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PENDING | PASS | BENCHMARK_VALIDATED / NOT_ASSESSED |
| `proportion_paired` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PENDING | PASS | BENCHMARK_VALIDATED / NOT_ASSESSED |
| `equivalence` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PENDING | PASS | BENCHMARK_VALIDATED / NOT_ASSESSED |
| `non_inferiority` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PENDING | PASS | BENCHMARK_VALIDATED / NOT_ASSESSED |
| `superiority_margin` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PENDING | PASS | BENCHMARK_VALIDATED / NOT_ASSESSED |
| `odds_ratio` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PENDING | PASS | BENCHMARK_VALIDATED / NOT_ASSESSED |
| `risk_ratio` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PENDING | PASS | BENCHMARK_VALIDATED / NOT_ASSESSED |

A–I denote statistical contract, numerical validation, API behavior, fail-closed runtime, reproducibility, protocol-ready output, change control, hosted OS qualification, and validated-environment classification respectively. There are no gate waivers.

## Local evidence

The unified Round 5 runner executed 25 retained fixtures and 50 direct live R executions without failure. It covers `round5-fixed-design-v1` for six methods and `round5-equivalence-powertost-v1` for equivalence. It checks exact integer analyzable and randomized outputs, frozen achieved-power tolerances, direct reproducible-R replay, package versions, specification hashes, implementation versions, and result metadata.

The validated local environment was Python 3.12.7, SciPy 1.18.1 (validation only), R 4.6.1, jsonlite 2.0.0, pwr 1.3.0, TrialSize 1.4.1, gsDesign 3.11.0, and PowerTOST 1.5.7. Package qualification remains method-specific. Unknown versions remain `UNVALIDATED_VERSION`; compatibility is never inferred.

## Hosted qualification path

The existing workflow now installs exact gsDesign 3.11.0 in addition to the already pinned dependencies. Each OS runs the Round 4 qualification unchanged, the new Round 5 frozen runner, production tests, the full suite, and artifact capture. The comparator now supports the two legitimate Round 5 benchmark IDs and additionally compares rounding declarations and derived analyzable/randomized arm counts exactly. Existing floating tolerances remain unchanged.

No hosted Windows, Ubuntu, or macOS result is claimed here. After this commit reaches GitHub, the workflow must be rerun. Only a three-platform PASS plus a PASS cross-platform comparison can close gate H and authorize a later evidence-backed promotion to `PRODUCTION_CANDIDATE`.

No statistical formula, frozen fixture, frozen evidence, or numerical tolerance was changed in this round.
