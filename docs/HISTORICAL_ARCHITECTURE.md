# Historical Local Architecture and the v5 Coze Migration

## Audit boundary and evidence

This document describes repository behavior, not intended future behavior. The principal snapshots are:

- Initial release: [`d1832bf03b6b`](https://github.com/medstatstar/ct-samplesize/tree/d1832bf03b6b) (2026-07-12).
- Function-template refactor: [`7e71766d1513`](https://github.com/medstatstar/ct-samplesize/tree/7e71766d1513) (2026-07-17).
- Adaptive simulator milestones: [`ab8ee4b361a8`](https://github.com/medstatstar/ct-samplesize/tree/ab8ee4b361a8), [`8d993012c1ac`](https://github.com/medstatstar/ct-samplesize/tree/8d993012c1ac), and [`014624f41d4a`](https://github.com/medstatstar/ct-samplesize/tree/014624f41d4a) (2026-07-18).
- Last fully local release: v3.8.1, [`3417563d832b`](https://github.com/medstatstar/ct-samplesize/tree/3417563d832b) (2026-08-02).
- First coze-only release: v5.0.0, [`26db1ffa846e`](https://github.com/medstatstar/ct-samplesize/tree/26db1ffa846e) (2026-08-21).
- Current 49-key inventory: [`e540d441883b`](https://github.com/medstatstar/ct-samplesize/tree/e540d441883b).

The historical audit covered the requested v3.8.1 files: `scripts/r_templates/`, `scripts/samplesize_power.py`, `scripts/r_libs.py`, `scripts/adaptive_simulator.py`, `references/formulas.md`, `references/extended_functions.md`, root `ADVANCED.md`, and `CHANGELOG.md`. In current releases, `ADVANCED.md` is under `docs/`; at v3.8.1 it was at repository root.

## Architecture immediately before v5

At v3.8.1, one local Python CLI owned parsing, validation, dispatch, code generation, execution gating, and result presentation:

```text
natural-language host / direct CLI
              |
              v
 scripts/samplesize_power.py
   - argparse surface and defaults
   - token/path allowlist validation
   - test-key dispatch (49 keys)
   - R template interpolation
   - Rscript discovery and subprocess execution
   - safe-preview / --yes gate
   - package-install guidance
   - Python fallback routing
              |
      +-------+----------------------+------------------+
      |                              |                  |
      v                              v                  v
 scripts/r_templates/*.py       scripts/r_libs.py   adaptive_simulator.py
 prewritten R function strings  I18N_R +           NumPy/SciPy Monte Carlo
 and curve solvers              ADAPTIVE_SIM_R      fallback / legacy engine
      |                              |
      +---------------+--------------+
                      v
              temporary generated R
                      |
                      v
                 local Rscript
                      |
                      v
         local stdout / curve image files
```

### Responsibilities by component

`scripts/samplesize_power.py` was a monolithic orchestration boundary. It exposed the CLI parameters, validated all user-controlled strings that could reach R, selected the template for each test key, interpolated numeric/design parameters, optionally prepended package-install checks, and ran a generated temporary script through `Rscript`. From v3.4.1 onward, local R execution was opt-in: the default was safe preview, and `--yes` authorized execution. This was a safety gate, not a remote-service gate.

`scripts/r_templates/` was a Python package containing R source as string constants. The v3.3.x function refactor moved calculations into named R functions such as `ss_ttest`, `ss_prop_two`, `ss_survival_exact`, and `ss_mams`; the dispatcher generally selected and formatted these templates. The directory held:

- t-test and ANOVA package calls;
- one- and two-proportion functions;
- fixed and sequential survival methods;
- non-inferiority, equivalence, and bioequivalence;
- group-sequential rpact designs and simulations;
- mixed-model simulation;
- count, diagnostic, cluster, and vaccine formulas;
- Bayesian/adaptive/special-design approximations and simulations;
- curve-mode solver expressions.

`scripts/r_libs.py` existed because publishing filters removed standalone `.R` files. It embedded two complete R libraries as Python raw strings: `I18N_R` for bilingual messages and `ADAPTIVE_SIM_R` for the adaptive Monte Carlo engine. `run_r()` prepended the message library. The adaptive path materialized or injected the simulator library into a generated R program.

`scripts/adaptive_simulator.py` was the local Python Monte Carlo implementation introduced in v3.4.5. It provided alpha-spending boundaries, group-sequential simulation, promising-zone sample-size re-estimation, drop-the-loser simulation, and a sample-size grid search. In v3.4.6 the base-R port became primary when R was available; the Python module remained the no-R fallback. In v3.4.7 the R implementation was reorganized as a source-able function library. Unlike the other methods, this branch therefore had two independent local numerical implementations.

`scripts/i18n.py` supplied Python-side messages and OS-locale detection. `I18N_R` in `r_libs.py` supplied corresponding R-side messages. Language selection affected presentation, not statistical routing.

The `references/` and `ADVANCED.md` files served as operator and method notes. They were not the runtime truth source. Several claims in prose do not match the v3.8.1 executable branch—for example, ROC documentation mentions `pROC`, Dunnett documentation mentions `MCPAN`, and historical borrowing mentions `RBesT`, while the audited local templates use custom analytical expressions and do not call those packages. The recovery matrix treats executable source as primary and flags those mismatches.

### Local execution lifecycle

1. The host or user selected one of the test keys and supplied CLI parameters.
2. Python normalized defaults and derived dispatch inputs (including OR/RR-to-risk transforms).
3. String parameters were allowlist-validated; numeric parameters were interpolated into a prewritten R template.
4. Required R packages were identified from the test-to-package map.
5. By default the generated R was printed but not executed. With explicit `--yes`, Python located and validated `Rscript`, wrote a temporary R file, invoked it without a shell, sanitized output, and removed temporary files.
6. Curve mode used separate solver expressions and base-R graphics.
7. `adaptive_simulate` used the embedded base-R Monte Carlo library when R was available and the Python simulator when it was not.

This design was “fully local” in the operational sense: calculations, package calls, simulations, temporary scripts, and output files ran on the user's machine. Optional package installation could require CRAN network access, but no calculation service was required.

## How the local system evolved before v5

### v3.0 through v3.3

The first releases combined a Python CLI with generated R snippets. By the v3.3.x refactor, the repository advertised 37 test types and moved scattered snippets into prewritten `ss_*` functions under `scripts/r_templates/`. Security work then added Rscript validation, safer subprocess invocation, output sanitization, parameter allowlists, and safe preview as the default.

### v3.4 adaptive simulation

v3.4.5 added `adaptive_simulate` as a pure-Python engine. v3.4.6 ported the same algorithm to base R and made R primary; Python became a no-R fallback. v3.4.7 made the R code a reusable function library. These commits are the clearest historical source for the simulation algorithm and its reported empirical type-I-error checks.

### v3.6 and v3.8

The group-sequential family was expanded and standardized around `rpact`: means, proportions, survival, hazard, Poisson, and two survival simulation keys. v3.8.1 then performed a 100-case QA pass, fixed the one-proportion route, corrected group-sequential defaults/formatting issues, and embedded R libraries to survive packaging filters. The resulting snapshot contains routed local branches for the same 49 keys found in the latest repository.

## The transition: v4 was hybrid; v5 made remote computation mandatory

It is inaccurate to describe the migration as a single direct jump from v3.8 to v5. The repository's `CHANGELOG.md` records an intermediate v4 architecture:

- `ComputeBackend` was introduced as an abstraction.
- `CozeBackend` became the default authoritative engine.
- A non-authoritative `LocalPythonBackend` covered only five basic tests.
- A full `LocalRBackend` remained in development assets but was excluded from the published package.
- The published orchestration layer no longer carried R templates; server-side R became the truth source.

Thus, v4 first separated orchestration from computation and removed full local R from the published artifact. v5 then removed the remaining runtime routing choices.

## Exactly what changed in v5.0.0

The v5.0.0 commit and its changelog make the following concrete changes:

| Concern | v3.8.1 local architecture | v5.0.0 published architecture |
|---|---|---|
| Backend selection | Direct local dispatch inside `samplesize_power.py` | `select_backend()` returns only `CozeBackend` |
| Numerical execution | Local Rscript for all templates; Python adaptive fallback | HTTP request to remote coze R service for all 49 keys |
| Local R templates | Shipped in `scripts/r_templates/` and `scripts/r_libs.py` | Removed from published tree; maintained/deployed outside the published artifact |
| Local Python calculation | Adaptive simulator and some Python-side fallback logic | Removed from runtime routing; mock mode returns an envelope, not a calculation |
| Failure mode | Missing R could fall back for adaptive simulation or show install guidance | Unreachable coze endpoint is a hard configuration error; no silent local calculation |
| Preview | Generated R source shown locally before optional execution | JSON request envelope shown before optional network send |
| Confirmation semantics | `--yes` authorized local code execution | Coze is stateless remote compute; natural-language/direct compute triggers send, while dry-run only previews |
| Inputs leaving machine | None for calculation | Test key, aggregate design parameters, locale, and request metadata are sent to the service |
| Outputs | Local R stdout and local image files | Response envelope containing text/stats and optional figures/R source; client renders or stores figures |
| Dependencies | Local Python plus R/R packages | Published client uses Python standard library; R and packages live server-side |
| Reproducibility boundary | Source plus installed local package versions | Client source is insufficient; server code, package image, and deployed endpoint are also required |

At v5, `scripts/compute_backend.py::select_backend` explicitly ignores legacy `--local`, `CTSS_BACKEND`, and `CTSS_FORCE_R` routing requests and either returns `CozeBackend` or raises an “endpoint unreachable” error. `_load_local_r_backend()` remained as dead/development scaffolding pointing to a directory absent from the published snapshot, but `select_backend()` no longer calls it. This is why the presence of old flags or loader code must not be mistaken for a local fallback.

`adapters/coze_client.py` replaced local method dispatch with request construction and response parsing. It serializes a test key, normalized parameters, solve mode, locale, and curve fields into a JSON envelope; performs an HTTP POST; and converts the returned envelope into `Result`/`Figure` objects. `scripts/samplesize_power.py` retained the CLI surface, validation, preview, and rendering responsibilities, but ceased to be a numerical engine.

The v5 changelog also says the server-side implementation had already been refactored into functions and synchronized from private/development R assets before those assets were removed from the published tree. Those assets are not present in the audited v5.0.0 commit, so this audit cannot treat them as recoverable GitHub source. The recoverable public source is the v3.8.1 local implementation.

## Consequences for reconstruction

The appropriate recovery baseline is v3.8.1, not the current client's backend interface and not undocumented server behavior. A reconstruction should preserve three layers that v3.8.1 mixed together:

1. **Method layer** — one explicit implementation per test key, with package calls and formulas separated from presentation.
2. **Execution layer** — local R and simulation runners with pinned dependencies, deterministic seeds where applicable, and structured results.
3. **Interface layer** — parameter normalization, validation, solve direction, reporting, curves, and sub-agent interaction.

The recovery matrix identifies which historical functions can populate the method layer directly and which need refactoring. No calculation code has been restored or modified in this audit.

## Provenance cautions

- Repository labels such as “exact,” “Bayesian,” “McNemar,” “Andersen–Gill,” “Gray,” “MAP,” and “Dunnett” sometimes describe the desired scenario more strongly than the executable algorithm supports. The matrix records the implemented engine rather than repeating the label.
- A package named in `AGENTS.md`, `ADVANCED.md`, or `references/` is not credited as an implementation unless the historical executable source calls it.
- Changelog-reported numerical checks are useful regression evidence but are not independent validation.
- The repository has only one annotated Git tag (`v3.3.1`) in the GitHub tag list; later version boundaries were recovered from commit messages and `CHANGELOG.md`, so commit SHA is the stable locator used here.
