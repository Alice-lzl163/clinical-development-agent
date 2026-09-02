# Runtime and Dependency Qualification — Round 4.4

This round qualifies portability behavior without adding or changing a statistical method. Evidence, not semantic versioning, determines compatibility.

## Version model

`MATCHED_VALIDATED_ENVIRONMENT` is the exact canonical Windows environment used for the Round 4.2 freeze. `TESTED_COMPATIBLE_VERSION` is available for a different version that passes the complete relevant suite, but it does not replace the canonical environment. `UNVALIDATED_VERSION` is executable without sufficient evidence and receives an explicit warning with benchmark runtime status withheld. `INCOMPATIBLE_VERSION` requires empirical evidence and fails closed. `NOT_TESTABLE` records an installation/reproducibility limitation without making a compatibility claim.

Only pwr 1.3.0, TrialSize 1.4.1, PowerTOST 1.5.7, and jsonlite 2.0.0 were actually executed. No adjacent version was installed in an isolated reproducible environment, so adjacent candidates are `NOT_TESTABLE`, not compatible or incompatible. The incompatible-version registry remains empty.

## Operating-system evidence

| OS | State | Evidence |
|---|---|---|
| Windows | `QUALIFIED` | Hosted Run 33595483882 passed probe, frozen numerical qualification, qualification tests, and full regression |
| Linux | `QUALIFIED` | Hosted Run 33595483882 passed the same required pipeline |
| macOS | `QUALIFIED` | Hosted Run 33595483882 passed the same required pipeline |

Importability is not qualification. A platform becomes `QUALIFIED` only after its environment probe, frozen fixtures, production qualification tests, and complete regression suite pass and its artifact is reviewed.

## Cross-platform acceptance

Acceptance thresholds were declared before Linux/macOS execution: all analyzable, group, randomized, and block-rounded counts must match exactly; achieved power and exposed intermediates use absolute tolerance `1e-6`; derived effects use `1e-12`. Hosted Run 33595483882 compared the same 24 fixture identities and benchmark ID across all three platforms: integer/allocation/rounding outputs matched exactly, floating outputs stayed within the predeclared tolerances, and no discrepancy was reported. No tolerance changed after results.

The GitHub Actions matrix runs local `Rscript` calculations on Windows, Ubuntu, and macOS runners. It installs declared runtimes and exact package versions where the repositories can reproduce them, runs the probe, writes separate numerical evidence (never overwriting Round 4.2 evidence), runs qualification and regression tests, and uploads all artifacts. Failure to install an exact version is a failed/pending CI qualification—not permission to substitute a newer version.

### Round 4.4.1 CI infrastructure correction

The first GitHub-hosted qualification run failed before numerical validation because `run_numerical_validation.py` was executed by file path. In that execution mode Python placed `sample_size/validation` rather than the checkout root on its import path, so `from sample_size import calculate_sample_size` failed. The repository has no installable-package metadata, making an editable installation inappropriate. Package-internal workflow entry points now use `python -m sample_size.validation.<module>` from the checkout root. The failed hosted run is classified as Python package-discovery infrastructure failure: no fixture ran, and it is not an R failure, statistical failure, benchmark failure, or cross-platform discrepancy. Windows, Linux, and macOS qualification require a fresh workflow run after this correction.

### Round 4.4.2 Windows test-isolation correction

The next hosted run passed on Ubuntu and macOS. Windows reached production qualification testing, where 11 of 12 tests passed. Its missing-runtime test constructed `RExecutionEngine(rscript=None)`, but `None` means “discover Rscript with `shutil.which`,” not “disable R.” Because setup-r exposed Rscript to the Windows Python process, production discovery succeeded and the expected `RuntimeDependencyError` was not raised. This is a test-isolation defect, not a runtime, R, statistical, benchmark, or cross-platform numerical discrepancy. The test now patches the production discovery boundary to return no executable; package absence is independently simulated through the R dependency-check response. Real discovery selection remains separately tested. The cross-platform comparison stayed blocked and all three hosted jobs require rerun. No Windows artifact from the failed hosted run was available in the local workspace, so this document does not claim that its 24 frozen fixtures passed; if `numerical-evidence.json` is recovered, it must be reviewed separately from the later test failure.

### Round 4.4.3 comparator dependency bootstrap

Hosted Run #4 passed the complete Windows, Ubuntu, and macOS matrix jobs. The comparison job then failed before loading evidence because its fresh Python environment had not installed the repository requirements: module execution imports `sample_size`, whose validation modules require PyYAML and jsonschema. `requirements.txt` already pins both, so the comparator job now installs that declaration rather than duplicating package names or versions in workflow YAML. The comparator also fails closed unless artifacts for all three expected runners exist, parse as complete evidence, share one benchmark ID and an identical fixture set, and contain every required comparison field. Run #4 observed no cross-platform numerical discrepancy because comparison never began; a rerun is required. No method status is promoted by this repair.

## Production-candidate decision

All six methods retain `BENCHMARK_VALIDATED` numerical status and now reach `PRODUCTION_CANDIDATE` after all nine qualification gates passed. No method is promoted to `PRODUCTION`.

### Round 5.4.1 exact-dependency bootstrap correction

The first Round 5 hosted qualification attempt failed before numerical qualification because gsDesign was unavailable when `run_numerical_validation` performed its fail-closed dependency audit. The Round 4 harness probes the complete declared dependency manifest, which now includes the Round 5 OR/RR authority; therefore no frozen calculation began and the platform comparison did not begin. This is `ENVIRONMENT_BLOCKED`: no numerical discrepancy was observed, and no statistical method, OR/RR calculation, equivalence calculation, benchmark, or tolerance is implicated.

The repository previously had two inconsistent installation paths. The workflow contained inline exact-version calls, while `install_r_dependencies.R` remained an unpinned missing-package helper that omitted gsDesign. The R script is now the single executable CI bootstrap. It installs and then verifies exactly jsonlite 2.0.0, pwr 1.3.0, TrialSize 1.4.1, PowerTOST 1.5.7, and gsDesign 3.11.0. Any missing package or version mismatch stops the job. The workflow invokes this bootstrap before every probe or qualification stage and invokes its verification-only mode again after the regression suite to capture the exact versions.

Method-specific validation scope is unchanged: gsDesign 3.11.0 is qualified only for `odds_ratio` and `risk_ratio`; PowerTOST 1.5.7 is qualified independently for `be_tost` and `equivalence`. A fresh three-platform hosted run is required.
