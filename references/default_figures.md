# Default Figures (v5.6) — Full Specification

> Extracted from SKILL.md (2026-08-30 slimming, §16.1). SKILL.md keeps only the summary; this file is the authoritative detail.

**Every** method produces at least one figure. All generation happens **on the coze side** (v5.6); the local CLI is a thin client that only consumes coze-returned `figures[]`.

## Layer model

| Layer | What it produces | Where it runs | When |
|:---|:---|:---|:---|
| **coze R** (`coze_figure_layer.R`) | Exact default chart for **all 49** methods (native noncentral distributions) | coze workflow | primary — whenever coze computes the method |
| **coze-internal `figure_kit.py`** | Same default charts (Python, stdlib only) | coze workflow | fallback — only if R produced no SVG (svglite missing / R error) |
| **coze R engine** | Authoritative curves for the 9 curve solvers | coze workflow | whenever coze returns `figures[]` for a curve solver |

> **Deployment boundary:** the R + figure_kit layer lives in `adapters/coze/scripts/` (the canonical coze-side mirror, which must always be kept at the latest version); the **coze platform deployment step is manual (user-side)**. Full deploy + fallback-chain guide → `adapters/coze/DEPLOY.md`.

**Figure merge & dedup (2026-08-30):** coze-internal `samplesize.py::_run_figure_layer` appends default figures after engine figures. When an engine figure caption already contains "curve/曲线" (the default primary is redundant with the engine power-N curve), the default primary (`*_default_1.svg`) is **filtered out**; the `alloc_suite` secondary set is always kept. Result: engine-fig methods get engine + alloc only; engine-less methods get the full default set.

## How the R layer stays honest

It never re-derives a sample-size formula. It takes the R-returned anchor `(n*, power*)` and inverts the **family-level** noncentrality relation with R's native `pnorm`/`pt`/`pf`/`pchisq`, which is mathematically exact:

| Family | Noncentrality scales as | Reference law | Members |
|:---|:---|:---|:---|
| `z` | `λ(n) = λ*·√(n/n*)` | Normal | rates, OR/RR, most survival, Poisson, Win-ratio… |
| `t` | `ncp(n) = ncp*·√(n/n*)` | noncentral t | t-tests, Dunnett, cluster, MMRM, Bland-Altman, TOST |
| `F` | `λ(n) = λ*·(n/n*)` | noncentral F | ANOVA |
| `X` | `λ(n) = λ*·(n/n*)` | noncentral χ² | Cox with covariate |

The curve is **pinned through the R anchor exactly** (residual ≤ 1e-16, verified for all 49 methods at 3 anchors each). The Python `figure_kit.py` fallback uses the same family law with a self-implemented kernel (cross-checked against R 4.6.1); it is precise for large samples and approximate for n < 20 or methods with continuity correction. Every chart carries an **effect-size ±20 % sensitivity band**: the visible consequence of that assumption, drawn rather than hidden.

> **Charts communicate; they do not compute.** Read trend and trade-offs off the figure; quote the R number (the red anchor dot) in the protocol.

## Figure kinds

Mapped per method in `adapters/coze/scripts/coze_figure_layer.R::METHOD_FIGURES`, mirrored to `tests/coze_cases/_contract_index.json::default_figure` and `scripts/figure_kit.py::METHOD_FIGURES`:

| Kind | Axis pair | Methods | Answers |
|:---|:---|:---|:---|
| `power_n` | N → Power | 20 (t-tests, rates, ROC, Win-ratio…) | how steeply does power fall if I recruit fewer |
| `power_events` | Events → Power | 6 (survival family) | event-driven: what D buys me headroom |
| `power_n_multi` | N → Power, one series per arm count | 5 (ANOVA, Dunnett, MAMS, multiple endpoints, dose escalation) | cost of adding an arm |
| `margin_tradeoff` | margin multiple → Power | 4 (non-inferiority, superiority margin, equivalence, TOST) | what relaxing the margin buys |
| `icc_sens` | ICC → Power | 2 (cluster, MMRM) | design-effect exposure to ICC mis-specification |
| `gs_boundary` | information fraction → z boundary | 10 (all group-sequential / adaptive) | OBF vs Pocock spending, Lan-DeMets closed form |
| `assurance_n` | N → Assurance | 2 (bayesian, assurance) | probability-of-success planning |
| `alloc_suite` *(secondary)* | allocation ratio k = n2/n1 | **13 two-group methods** | what unequal allocation costs — 4 charts + lookup table |

## Allocation-ratio suite (`alloc_suite`)

The v5.5 addition for unequal group sizes, rendered by `scripts/alloc_curve.py`:

- **A** required total N vs ratio (U-shape, minimum at 1:1)
- **B** power vs ratio at fixed N (inverted-U)
- **C** iso-power contour in the (n1, n2) plane, tangent to the 1:1 diagonal — the geometric proof that equal allocation is optimal
- **D** power loss stratified by effect size

Governing identity: `N(k)/N(1) = (1+k)²/(4k)` (Schoenfeld inflation), identical for means, proportions and log-rank.

Four backends feed it: `ttest_ind` (noncentral t), `prop` (unpooled z), `logrank` (Schoenfeld), and **`z`** — a generic two-independent-group z family (`ncp = θ·√(n₁n₂/N)`) covering `poisson`, `vaccine_efficacy` and `win_ratio`. Those three have no common effect-size scale (rate ratio, VE, win ratio), so θ is **solved back from the R anchor** (`theta_from_anchor`) and the suite is pinned to the same anchor as the main chart — verified: θ reproduces the anchor to ≤1.1e-16, and `N(k)/N(1)` matches `(1+k)²/(4k)` to ≤4.4e-16.

⚠️ **Proportions break the 1:1 rule.** For two rates the cost-minimising allocation is Neyman's `k* = √(p₂(1−p₂)/p₁(1−p₁))`, not 1. At p₁=0.10 vs p₂=0.30 that is k*=1.53 (n1:n2 = 2:3): **113 subjects instead of 118**, a 4.2 % saving *and* higher power. The optimal-ratio marker is therefore solved from the actual curve (ternary search), never hardcoded — otherwise the single most valuable case would be labelled wrong.

## Env knobs

`CTSS_FIGURE_DEBUG=1` prints why a figure was skipped · `CTSS_OUTPUT_DIR` relocates output · `CTSS_INLINE_WIDGET=1` restores inline markers (off by default).

## Accuracy

Distribution kernels cross-validated against R 4.6.1 — central χ²/F and noncentral χ² agree to ≤5e-13, noncentral F to ≤3e-10, `qf`/`qchisq` to ≤8e-11. Zero third-party dependencies (stdlib `math` only).

## Dependencies: zero new R packages (a deploy step is required)

All figure generation runs on the coze side in v5.6, so the coze workflow must deploy the figure layer from `adapters/coze/scripts/` (4 files: `coze_figure_layer.R`, `figure_kit.py`, `alloc_curve.py`, `coze_fallback.py`) — but **no new R package is installed**: `svglite` is already in the tier1 list (`scripts/install_r_packages.R`) alongside `pwr`/`rpact`/`TrialSize`/`PowerTOST`/`powerSurvEpi`/`simr`/`lme4`/`survival`, which cover every statistic involved. The only two places a package *could* have helped (`clusterPower` for ICC, `bsurvival` for assurance) use closed-form approximations anchored to the R number instead, with the residual uncertainty drawn as the sensitivity band — cheaper than a new image build. Local side needs **no** figure dependencies at all (thin client).
