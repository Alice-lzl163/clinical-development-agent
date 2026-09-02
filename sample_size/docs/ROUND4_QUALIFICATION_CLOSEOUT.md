# Round 4 Qualification Closeout

## Outcome

The six fixed-design calculators—`ttest_one`, `ttest_paired`, `ttest_ind`, `anova`, `proportion_two`, and `be_tost`—are now `PRODUCTION_CANDIDATE`. Their independent lifecycle states are specification `SPEC_FROZEN`, implementation `IMPLEMENTED`, numerical validation `BENCHMARK_VALIDATED`, and production qualification `PRODUCTION_CANDIDATE`. None is `PRODUCTION`.

## Evidence history

Round 4.2 froze 24 fixtures after 114 successful live R calculations, authoritative-package reproduction, inverse/forward checks, independent numerical references, operational invariants, monotonicity, and reproducibility checks. Round 4.3 added fail-closed behavior, protocol output, version classification, and change control. Round 4.4 added exact dependency and OS qualification plus predeclared cross-platform tolerances.

Three CI infrastructure failures were resolved before closeout. File-path execution initially prevented Python package discovery; a Windows-only test failed to isolate R discovery; and the comparator initially lacked declared Python dependencies. Each occurred before its affected validation operation and was classified as infrastructure/test-isolation—not statistical failure or numerical discrepancy.

Successful GitHub Actions Run [33595483882](https://github.com/Alice-lzl163/clinical-development-agent/actions/runs/33595483882) at commit `02ed81369fe7924695fd8e6148381f4f28cecf8a` passed Windows, Ubuntu, macOS, all required steps, artifact uploads, and comparison. The public API exposed job/step conclusions and artifact metadata; artifact-content download required authentication in the closeout environment, so unavailable runner architecture fields remain null rather than inferred.

## Cross-platform result

All platforms used the declared Python 3.12.7, SciPy 1.18.1, R 4.6.1, jsonlite 2.0.0, pwr 1.3.0, TrialSize 1.4.1, and PowerTOST 1.5.7 setup. The comparison used benchmark `fixed-design-round4-v1` and the same 24 fixture identities. Integer, allocation, and rounding quantities matched exactly; floating quantities remained within the predeclared absolute tolerances; no discrepancy was reported and no tolerance was changed.

## Production-candidate gates

| Method | A contract | B numerical | C API | D fail closed | E reproducibility | F output | G change control | H OS/runtime | I environment | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| `ttest_one` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | CANDIDATE |
| `ttest_paired` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | CANDIDATE |
| `ttest_ind` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | CANDIDATE |
| `anova` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | CANDIDATE |
| `proportion_two` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | CANDIDATE |
| `be_tost` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | CANDIDATE |

Traceability, specification hashes, implementation version, package versions, benchmark ID, OS evidence, comparator evidence, and regression evidence are machine-readable in `production_qualification.yaml` and `hosted_run_33595483882.yaml`.
