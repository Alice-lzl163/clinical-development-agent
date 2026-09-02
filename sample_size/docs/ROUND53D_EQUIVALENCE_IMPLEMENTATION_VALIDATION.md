# Round 5.3D — exact equivalence TOST implementation and validation

## Outcome

`equivalence` is **BENCHMARK_VALIDATED** against the new benchmark `round5-equivalence-powertost-v1`. It is not `PRODUCTION_CANDIDATE` or `PRODUCTION`. The production calculator now uses only `PowerTOST::power.TOST` 1.5.7 with `logscale=FALSE`, symmetric bounds, `design="parallel"`, `method="exact"`, and `robust=FALSE`. The historical `TrialSize::TwoSampleMean.Equivalence` implementation is not called.

The inverse calculator enumerates control-arm N from 2, realizes treatment N as `ceil(allocation_ratio * control N)`, and accepts the first exact package power at or above target. This establishes minimum control-arm N under that declared realization rule; it does not claim a global minimum total N over arbitrary integer pairs. Dropout is applied per arm only after acceptance.

## Frozen validation

The six retained fixtures cover centered, positive nonzero, and negative nonzero expected differences; allocation ratios 1, 2, and 0.5; sample-size and explicit-arm forward-power modes; and the historical `eq_k2` and `eq_khalf` configurations. All required gates passed with predeclared absolute tolerances of `1e-12` for direct package reproduction and `1e-9` for the independent exact integral.

| Fixture | Treatment/control | Exact power | Preceding power | Independent integral difference |
|---|---:|---:|---:|---:|
| `eq_centered_sample` | 70/70 | 0.8059311816274025 | 0.7985117775368249 | 7.27e-14 |
| `eq_k2_repaired` | 124/62 | 0.8065493607543245 | 0.7998664843513544 | 1.14e-13 |
| `eq_khalf_repaired` | 118/235 | 0.9011199416062228 | 0.8991870226695483 | 4.86e-13 |
| `eq_centered_power` | 80/80 | 0.8673773151111428 | not applicable | 7.36e-14 |
| `eq_k2_historical_arms_power` | 161/81 | 0.8972844142790725 | not applicable | below 1e-9 |
| `eq_khalf_historical_arms_power` | 147/293 | 0.949830835624301 | not applicable | below 1e-9 |

The two historical arm configurations now agree with the independent pooled-variance joint-TOST integral where the old nearest-bound TrialSize approximation differed. The original failed fixtures and evidence remain unchanged and explicitly failed; this benchmark is separate.

## Simulation and invariants

Independent pooled-normal TOST simulations used seeds 5,303,004 through 5,303,006 and 100,000 replicates per scenario. Centered, noncentered, and unequal-allocation scenarios all met the predeclared `max(0.01, 3*MCSE)` tolerance. Observed MCSEs ranged from 0.000946 to 0.001252.

Monotonicity passed for narrower margins, larger SD, alternatives closer to a bound, higher target power, and smaller alpha. Dropout rates 0, 0.10, and 0.20 preserved analyzable N and exact achieved power while randomized N increased monotonically. Every sample-size fixture passed the accepted/preceding-candidate minimality check.

## Environment and governance

Validation ran locally on Python 3.12.7, SciPy 1.18.1, R 4.6.1 (`x86_64-w64-mingw32`), jsonlite 2.0.0, and PowerTOST 1.5.7. SciPy and the project-owned exact integral are validation references only, never production authorities. The run executed 21 successful R subprocesses and 1,410 authoritative `power.TOST` evaluations with no R failures.

PowerTOST 1.5.7 now has a distinct method-specific qualification record for `equivalence`; its earlier `be_tost` qualification was not inherited. No compatibility is inferred for other package versions. Search exhaustion, missing runtime/package, malformed or nonfinite output, invalid domains, and arm counts above 1,000,000 fail closed without SciPy, LLM, remote, or surrogate fallback.

Full machine-readable results, exact R calls, package arguments, session information, specification hashes, simulations, and preservation hashes are in `sample_size/validation/round5_equivalence_powertost_evidence.json` and its frozen benchmark YAML.
