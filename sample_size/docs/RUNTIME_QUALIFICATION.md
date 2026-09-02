# Runtime and Dependency Qualification — Round 4.4

This round qualifies portability behavior without adding or changing a statistical method. Evidence, not semantic versioning, determines compatibility.

## Version model

`MATCHED_VALIDATED_ENVIRONMENT` is the exact canonical Windows environment used for the Round 4.2 freeze. `TESTED_COMPATIBLE_VERSION` is available for a different version that passes the complete relevant suite, but it does not replace the canonical environment. `UNVALIDATED_VERSION` is executable without sufficient evidence and receives an explicit warning with benchmark runtime status withheld. `INCOMPATIBLE_VERSION` requires empirical evidence and fails closed. `NOT_TESTABLE` records an installation/reproducibility limitation without making a compatibility claim.

Only pwr 1.3.0, TrialSize 1.4.1, PowerTOST 1.5.7, and jsonlite 2.0.0 were actually executed. No adjacent version was installed in an isolated reproducible environment, so adjacent candidates are `NOT_TESTABLE`, not compatible or incompatible. The incompatible-version registry remains empty.

## Operating-system evidence

| OS | State | Evidence |
|---|---|---|
| Windows AMD64 | `QUALIFIED` | Probe passed; 24/24 fixtures and 114/114 live R calls passed; 74/74 Round 4.3 regression tests passed |
| Linux | `UNQUALIFIED` | Workflow created, not executed in this workspace |
| macOS | `UNQUALIFIED` | Workflow created, not executed in this workspace |

Importability is not qualification. A platform becomes `QUALIFIED` only after its environment probe, frozen fixtures, production qualification tests, and complete regression suite pass and its artifact is reviewed.

## Cross-platform acceptance

Acceptance thresholds were declared before Linux/macOS execution: all analyzable, group, randomized, and block-rounded counts must match exactly; achieved power and exposed intermediates use absolute tolerance `1e-6`; derived effects use `1e-12`. Discrepancies must be assigned one of the classes recorded in `os_qualification.yaml`. Cross-platform comparison remains `PENDING` because only Windows has executed.

The GitHub Actions matrix runs local `Rscript` calculations on Windows, Ubuntu, and macOS runners. It installs declared runtimes and exact package versions where the repositories can reproduce them, runs the probe, writes separate numerical evidence (never overwriting Round 4.2 evidence), runs qualification and regression tests, and uploads all artifacts. Failure to install an exact version is a failed/pending CI qualification—not permission to substitute a newer version.

### Round 4.4.1 CI infrastructure correction

The first GitHub-hosted qualification run failed before numerical validation because `run_numerical_validation.py` was executed by file path. In that execution mode Python placed `sample_size/validation` rather than the checkout root on its import path, so `from sample_size import calculate_sample_size` failed. The repository has no installable-package metadata, making an editable installation inappropriate. Package-internal workflow entry points now use `python -m sample_size.validation.<module>` from the checkout root. The failed hosted run is classified as Python package-discovery infrastructure failure: no fixture ran, and it is not an R failure, statistical failure, benchmark failure, or cross-platform discrepancy. Windows, Linux, and macOS qualification require a fresh workflow run after this correction.

## Production-candidate decision

All six methods remain `BENCHMARK_VALIDATED`. None reaches `PRODUCTION_CANDIDATE` until reviewed Linux and macOS artifacts complete the portability gate and any dependency versions used outside the canonical environment have explicit registry evidence. No method is promoted to `PRODUCTION` in this round.
