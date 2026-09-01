# AGENTS.md — ct-samplesize v5.0.3

## Overview

`ct-samplesize`: An easy-to-use sample size & power tool for clinical trial practitioners. The **default authoritative engine is a remote coze R compute service** (rpact/TrialSize/PowerTOST etc., 20+ packages running server-side — no local R required); it performs all 49 test types via natural-language prompts (output in Chinese or English per OS language setting, prompt can force-switch). In the published skill **no R or shell runs locally and there is no local compute fallback**; only trial-design parameters are sent to coze, and full R code can be returned on request for verification, submission, or re-run.

---

## Core Rules

### 1. Compute Backend Detection (coze only)
- **Published skill:** the ONLY backend is the coze R service (`CTSS_COZE_ENDPOINT`, default pre-whitelisted `https://ct-samplesize.coze.site/run`); all 49 tests compute server-side, no local R and **no local compute fallback**. If the endpoint is unreachable, the skill reports the missing config — it never silently degrades.
- **Dev-only (not shipped):** a legacy local-R backend exists in `adapters/coze/ct_r_lib/` (`CTSS_BACKEND=local-r` / `CTSS_FORCE_R=1`), used only for offline development/contribution; it is not routed by the v5 `select_backend` and is excluded from the published package.

### 2. Extended Tool Selection

> All rows below run **server-side on coze** in the published skill (only design params are sent).

|User Need|Path|
|:----------|:-----|
| Basic stats (t-test/ANOVA/proportion) | coze (R) |
| Longitudinal / Repeated measures | R: `simr` (mixed model) |
| Diagnostic trial | R: `pROC` (ROC formula) |
| Count data / Recurrent events | R: custom Wald test |
| Cluster randomized | R: design effect formula |
| Method comparison | R: Bland-Altman (Lu et al.) |
| Bioequivalence | R: `PowerTOST` (TOST) |
| Group sequential / Adaptive | R: `rpact` (gsDesign on-demand only) |
| Non-inferiority | R: `TrialSize` (exact) / `powerSurvEpi` |
| Survival | R: `rpact` |
| Vaccine efficacy | R: Halloran formula |
| Bayesian design | R: `BayesCTDesign` |
| Dose escalation | R: `escalation` |
| Multiple endpoints | R: correlation method |
| Win-Ratio composite | R: `BuyseTest` power simulation |
| Must-Win / Co-Primary | R: correlation inflation factor |
| Historical Controls | R: `RBesT` MAP prior |
| MAMS | R: `rpact` |
| Conditional Power / SSR | R: `rpact` |
| Superiority by Margin | R: custom formula |
| Assurance | R: Monte Carlo simulation |
| Dunnett comparisons | R: `MCPAN` |
| Mediation | R: `powerMediation` |

### 3. Code Execution
- **Published skill:** no local R/shell and no local compute fallback. The orchestration layer (`scripts/samplesize_power.py`) routes via `ComputeBackend` (`scripts/compute_backend.py`) to `CozeBackend` — the only backend in v5 (legacy local-R dev backend in `adapters/coze/ct_r_lib/` is dev-only, not shipped).
- **Default: safe preview.** `--dry-run` prints the exact coze request envelope (no send); the natural-language trigger ("please compute" / 请直接计算) is what sends and computes — **`--yes` is not needed for coze** (stateless remote compute; the legacy `--yes` gate applies only to the optional local-R dev backend).
- Python (orchestration + fallback) via the bundled interpreter; figures from coze are written to `CTSS_OUTPUT_DIR` (default `./outputs`).

### 4. Result Output (v3.4.4)

Every analysis includes:
- Input parameters + defaults used
- Calculation result (sample size / power / effect size)
- Dropout adjustment (if applicable)
- Assumptions & limitations
- **Default = SAFE PREVIEW (coze request envelope shown, NOT sent)**; the natural-language trigger ("please compute" / 请直接计算) sends to coze & computes — **no `--yes` needed for coze** (stateless remote compute; `--yes` applies only to the legacy local-R dev backend). `--show-code` displays the coze request JSON (no send), `--dry-run` previews only.
- The optional local-R dev backend (adapters/coze/ct_r_lib) behaves like v3.x: R code is shown but NOT run unless `--yes` is given; `-y`/`--yes` explicitly executes locally.
- **`--test adaptive_simulate`**: the authoritative engine is the inlined pure base-R function library `ADAPTIVE_SIM_R` (maintained in `adapters/coze/ct_r_lib/local_r_backend.py`, no extra packages) running **server-side on coze** in the published skill. A legacy pure-Python module `adapters/coze/ct_r_lib/legacy/adaptive_simulator.py` is retained for offline dev/testing. The CLI shows the coze request envelope in SAFE PREVIEW and computes via coze. See `references/adaptive_simulator.md`.

### 5. Language Detection
- **Follow OS language setting**: Output language (Chinese or English) follows the OS language setting — Chinese on a Chinese-OS, English otherwise.
- **Prompt can force-switch**: The user may override the OS-based default anytime via an explicit language request (e.g. "switch to English").
- **Detection method**: Linux/macOS read `LANG`/`LC_ALL`/`LANGUAGE`; Windows use `Get-Culture`/`Get-WinSystemLocale` or `os` env to check if the language code starts with `zh`; if the `<response_language>` tag specifies a language, follow it.
- **Docs are English-only (ct-base §4)**: The skill documentation (SKILL.md, AGENTS.md, references, etc.) is English-only. Runtime output for common modules may still be English + Chinese per OS setting; complex/rare modules are English-only.
- **Complex/rare modules may be English-only**: e.g. `group_sequential`, `adaptive`, `mixed_model`, `bayesian`, `win_ratio`, `mams`, `vaccine_efficacy` etc.
- **This policy does not affect code output**: R/Python code is always English, shown per `--show-code`.

### 6. Mixed Model Specifics
- Use `simr::makeLmer()` / `makeGlmer()` to build model from literature parameters
- Run `powerSim()` with nsim ≥ 500 for stable estimates
- Always run `powerCurve()` to find minimum sample size
- Report computation time (can be 1-5 min for complex models)

### 7. Menu Navigation Design — Non-Exclusive
- The interactive "quick menu" that guides users to pick a test type MUST NOT be a mutually-exclusive tree. The same test can appear under multiple top-level entries, mirroring PASS's menu design.
- Rationale: with 49 test types, classification dimensions intersect (design family × endpoint type). A strict tree would hide reachable paths. The menu is a *navigation aid*, not a taxonomy.
- Example: sequential survival analysis (`gsd_survival` = `group_sequential` + survival endpoint) must be reachable BOTH from a **Survival Analysis** top-level menu AND from a **Sequential Group-Sequential Design** top-level menu.
- Rule of thumb for future extensions: any test classifiable along multiple axes (e.g. sequential/adaptive × means/proportion/survival/rate) must be listed under every relevant top-level entry — do NOT hang it on a single node.
- **Menu structure is now formalized in `references/menu.md`** (primary tree by endpoint + design-family cross-index) and surfaced in SKILL.md `## Quick Menu`. When guiding a user to pick a test, read `references/menu.md` to stay consistent with the canonical classification.

### 8. Triage (ct-base §6.2) — Four-Way Interaction

Before any user interaction, triage first (ct-base §6.2) into **Simple / Middle / Complex / Vague**, then decide whether / how to show a menu.

|Class|Trigger|Action|
|:---|:---|:---|
|**Simple**|Direct t-test/ANOVA/proportion-style question with clear how/why|Answer directly; 1–2 turns; pick from the 49 test types; no menu|
|**Middle**|Single-point but deep (ICH guidance detail, statistical parameter, compliance gray zone; needs 3–4 points)|Still answer directly, **no menu** (same path as Simple); mark `difficulty = "middle"` for a richer multi-point answer. When Simple vs Middle is unclear, prefer **Middle**|
|**Complex**|Multi-step or design-family question (sequential/adaptive/mixed/survival)|Consult `references/menu.md` → present the relevant menu; guide step-by-step|
|**Vague**|Under-specified ask (missing endpoint, design, or effect size)|Use `grill-me` to ask 1–3 clarifying questions → then re-triage|

- Choose menu depth based on simple vs complex.
- `references/menu.md` defines the **Complex** path; Simple and Vague rarely need the full menu.
- **Routing gate (audit follow-up — avoid accidental remote compute):** a remote coze compute (data leaves the machine) fires **only** when the user's intent is explicitly a sample-size / power / curve **calculation**. Advisory / consulting asks — "help me figure it out", methodology, ICH guidance, "what test should I use" — are answered **locally, nothing sent** (menu / grill-me flow as needed). On ambiguous phrasing, ask for calculation intent before any coze call.

---

## Security Fixes (v3.3+)

|Fix|Implementation|
|:----|:--------------|
| Default dry-run | R code displayed, not executed unless `-y` confirmed |
| Output sanitization | `sanitize_output()` strips paths, truncates |
| No hardcoded R path | RSCRIPT_PATH env + PATH lookup |
| Narrowed triggers | Removed generic terms like "sample size" alone |
| Permissions declared | `permissions` block in SKILL.md frontmatter (top-level) |
| User warnings | `## ⚠️ User Warnings` section |
| Fixed `minfup` | Examples: `minfup <- T - R` (24 months, matches prose) |
| Fixed dropout code | Valid R syntax throughout |

---

## Dependencies

### R Packages (dev / coze-side — NOT in published skill)
In the published skill, all R packages run **server-side on coze**; you never install them locally. This section applies only when running the optional local-R backend (`CTSS_BACKEND=local-r`, requires `adapters/coze/ct_r_lib/`):
R packages do NOT need to be pre-installed all at once. When the dev backend detects a missing package it prints the install command in output; the user runs it once.

|Tier|Package|Used for|
|:---|:---|:---|
|**Core (high-freq)**|`TrialSize`, `pwr`, `rpact`, `PowerTOST`, `powerSurvEpi`|NI, equivalence, survival, superiority margin, group-sequential, BE etc.|
|**Aux (mid-freq)**|`simr`, `lme4`, `pROC`, `survival`|mixed model, ROC, exact survival ROC|
|**Low-freq**|`BayesCTDesign`, `escalation`, `BuyseTest`, `RBesT`, `MCPAN`, `powerMediation`, `BlandAltmanLeh`|vaccine, dose escalation, Win-Ratio, historical control, Dunnett, mediation|
|**No R package**|—|`ttest_*` (partial), `anova`, `poisson`, `cluster`, `bland_altman`, `vaccine_efficacy`, `bayesian`, `dose_escalation`, `assurance`, `multiple_endpoints`, `must_win`, `mediation`|

**When the user requests one-click install (dev backend only), run**
```r
install.packages(c("TrialSize", "pwr", "rpact", "PowerTOST", "simr", "lme4", "pROC", "powerSurvEpi", "survival"))
```
(Note: the legacy CLI flag `--install-all-packages` was removed in v5.0.2 — use the R snippet above for the dev backend; the published coze engine needs no local install.)

### Python (v5: stdlib only — no third-party compute deps)
```
# No pip requirements for the published skill: argparse / json / urllib / math (stdlib only).
# The v5 refactor removed statsmodels / numpy / scipy (no local Python computation).
# Optional: cairosvg — only for --figure-mode png_file (local SVG→PNG rasterization).
```
