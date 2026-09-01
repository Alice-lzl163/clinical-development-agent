---
slug: ct-samplesize
displayName: Clinical Trial Sample Size & Power / 临床试验样本量与检验效能专家
name: ct-samplesize
cn_name: 临床试验样本量与检验效能专家
version: 5.6.0
invocable: true
required_commands: [python]
summary: 为临床试验从业者提供的样本量与检验效能计算工具。本地无需安装 R，直接提供云端 R 计算服务（覆盖 49 种检验，并提供 SVG 出版级别图形）。自然语言驱动，默认回传完整 R 代码；默认按操作系统语言设定输出中文或英文（提示词可强制切换）。
license: MIT
description: "Sample size and power calculation tool for clinical trial practitioners. No local R install needed — a cloud R compute service covers all 49 test types and returns publication-grade SVG figures. Natural-language driven; full reproducible R code is returned by default; default output in Chinese or English per OS language setting (prompt can force-switch). / 为临床试验从业者提供的样本量与检验效能计算工具。本地无需安装 R，直接提供云端 R 计算服务（覆盖 49 种检验，并提供 SVG 出版级别图形）。自然语言驱动，默认回传完整 R 代码；默认按操作系统语言设定输出中文或英文（提示词可强制切换）。"
triggers:
  - "clinical trial sample size"
  - "样本量计算"
  - "clinical trial power"
  - "检验效能计算"
  - "临床试验 设计"
  - "non-inferiority sample size"
  - "equivalence sample size"
  - "survival analysis sample size"
  - "adaptive design"
  - "group sequential design"
  - "Bayesian clinical trial"
metadata: { openclaw: { emoji: "📊" }, authors: ["medstatstar", "phoe-zip"], license: "MIT", tags: [clinical-trial, sample-size, power, coze, adaptive-design, bayesian, win-ratio], homepage: "https://github.com/medstatstar/ct-samplesize" }
permissions:
  scope: "user-space-only"
  network: "required"
  network_note: "v5 requires the remote coze compute endpoint (CTSS_COZE_ENDPOINT, or CTSS_COZE_MOCK=1 for a local demo) — the published skill has no local compute fallback. Only trial-design parameters leave the machine (no patient data); every request also carries a hostname hash `query_origin` (sha256, for server attribution/rate-limit) and the OS-language-derived `locale`. Outbound authorization gate: the public endpoint is pre-whitelisted in config/config.json auto_approve_endpoints (never prompts, but the assistant states what is sent on first use); user-custom endpoints trigger a one-time AUTH-BLOCK user confirmation before any data leaves the machine. Payloads are sanitized (PII stripped) before sending."
  filesystem: "writes figures to CTSS_OUTPUT_DIR (default ./outputs) and optional curve PNGs; otherwise read-only"
  data: "no patient/external data leaves the boundary — only trial-design parameters plus the hostname hash (query_origin) and locale metadata are sent to the coze service"

---

# Clinical Trial Sample Size & Power

## Language

- **English guide** → [README.md](https://github.com/medstatstar/ct-samplesize/blob/main/README.md) · **中文指南** → [README_zh-CN.md](https://github.com/medstatstar/ct-samplesize/blob/main/README_zh-CN.md)
- Bilingual auto-switch: the answer language follows the user's question language (English question → English answer, Chinese question → Chinese answer).

## Purpose

This skill provides clinical trial researchers with an easy-to-use, comprehensive sample size & power calculation tool. **The default authoritative engine is a remote coze R compute service** (rpact / TrialSize / PowerTOST and 20+ other packages — running server-side, so your machine needs **no local R**), covering all 49 test types. Results come in Chinese or English per the OS language setting (prompt can force-switch). Reproducible R code is returned by default (coze returns it on every analysis).

---

## Features

| Capability | Description | Typical Scenario |
|:---|:---|:---|
| **① Sample size ⇄ Power (bidirectional)** | Solve n given target power, AND solve achievable power given fixed n. `--power` (forward) and `--nobs` (reverse) are mutually exclusive; covers all 49 types. | Sample size fixed, evaluate if power meets target |
| **② Power curve** | Given a sample-size sequence, batch-compute and plot the **Power curve** (x=sample size, y=power), with a target-power reference line. | Sample-size sensitivity analysis, protocol reporting |
| **③ Sample-size curve** | Given a power-target sequence, batch-compute and plot the **sample-size curve** (x=target power, y=required n). | Resource planning, feasibility assessment |
| **④ Deterministic NL pre-route (zero-LLM)** | `--nl "<natural language>"` runs a local zero-LLM deterministic detector that identifies `--test` and extracts params (power 80%→0.8, rate 70%→0.7, "enroll 30"→reverse-solve power, etc.), emitting a strong signal for the coze request; when confidence is low / params incomplete it prints a structured prompt and **never silently mis-params**, handing the rest to the coze LLM. Logic in `scripts/classify_test.py` + `scripts/param_aliases.py`; per-test contract baselines in `tests/coze_cases/` (`tests/coze_cases_regression.py` offline regression), 49-test enumeration in `adapters/coze/coze_contract.md`. | User phrases it colloquially, e.g. "non-inferiority survival trial, NI margin 1.25…" |

- ②③ curve mode: list `"20,40,200"` or auto-seq `"20:20:200"` (start:step:stop); overlay multiple effect-size curves for sensitivity (continuous/survival solvers; proportion solvers plot the single p1/p2 series); returns the figure (SVG default per the ct-* uniform figure spec, PNG fallback) **plus the numeric series as machine-readable stats (x/y arrays)**. Full parameters & 49-test examples → `references/cli_examples.md`.
- **Specialized curve modes (`--effect_seq` / `--dist_plot` / `--power_time_seq` / `--heatmap`, added 2026-08-28):** effect-axis / H0–H1 overlap / follow-up-power / 2-D sensitivity scans for the 9 curve solvers; full parameters & 49-test examples → `references/cli_examples.md`.
- **★ Default full figure-set (user rule 2026-08-20, expanded 2026-08-28):** when no figure is requested, the R engine auto-attaches the full set for the 9 curve solvers (curves + dist-overlap + heatmap) and the survival follow-up–power curve; each carries a `type` field + bilingual `caption`. Opt out via any explicit figure flag / `--dry-run`. coze emits all figures, stream does not inline — see Figure Output.
- **★ Default figure for *every* one of the 49 methods (v5.6):** all figure generation moved to the coze side — coze R (`coze_figure_layer.R`) is the primary plotter, `figure_kit.py` is the coze-internal fallback; the local CLI is a **thin client** consuming coze-returned `figures[]` — see [Default Figures (v5.6)](#default-figures-v56) and `references/default_figures.md`. **Zero new R packages** on the coze side.

---

## Interaction — Triage first

Before answering, triage the request into the four-level difficulty **Simple / Middle / Complex / Vague**:
- **Simple** (test already named, params mostly given) → answer directly, **no menu**.
- **Middle** (single-point but deep — ICH guidance detail, statistical parameter, compliance gray zone, needs 3–4 points) → still answer **directly, no menu** (same path as Simple; mark `difficulty = "middle"` for a richer multi-point answer). When Simple vs Middle is unclear, prefer **Middle**.
- **Complex** (pick test type / design family / many params) → show the **routing menu** below (**the `## Quick Menu` is for the Complex branch only**).
- **Vague** ("not sure which test to use") → **bounded grill-me** (branch-by-branch probing), do **not** dump the menu. **Hard cap: ≤3 rounds** (on reaching the cap with the test still undecided, **converge with the accumulated question profile** — pick the best-fit test family and confirm). Each round ask 1–3 focused questions with a recommended default; accumulate confirmed fields into a **question profile**; when the test is locked, **echo a "needs portrait + recommended test + missing params" summary for confirmation** before computing. (This 3-round cap targets locking the test; the global missing-parameter cap is **2 rounds then use defaults** per ct-base AGENTS.md §6.1 — different dimensions, no conflict.)

**Routing gate (audit follow-up — avoid accidental remote compute):** a **remote coze compute** (data leaves the machine) happens **only** when the user's intent is explicitly a sample-size / power / curve **calculation**. General consulting — "help me figure out my trial design", methodology questions, ICH guidance, "what test should I use" — must be answered **locally without sending anything**, and may use the menu / grill-me flow. Do not fire a coze request on vague or advisory phrasing; ask for the calculation intent first.

## Cross-turn Continuity (mandatory)

> **Runtime is stateless.** The coze R engine re-supplies `test`+`params` each call and never persists prior fields. Semantic drift (effect/α/power/n silently changing) = highest-risk failure for a stateless remote.

**Hard rules** (full rules → ct-base/references/continuity.md Mode A §5.1; minimal unit = `{test, effect, alpha, power, solve, side, sd}`, `—` = not-yet-known):
1. **Echo a `## 当前分析设定：` block after every calculation (mandatory):** `## 当前分析设定： test=ttest_ind | effect(d)=0.5 | alpha=0.05 | power=0.8 | solve=n | side=two | sd=1.0 | n=— | ratio=—`. No field omitted (`—` placeholder). `solve=n` solves n given power; `solve=power` reverses; `side=two/one_greater/one_less`.
2. **On follow-up, change only the changed fields:** read the most recent `## 当前分析设定：` block, override only the changed field, inherit the rest verbatim, then send to coze.
3. **Deterministic merge (default path, not optional):** every follow-up **MUST run** `merge_spec.py` for a lossless merge, then send the merged spec to coze — never assemble params from LLM memory alone. `echo '{"prev":{...},"cur":{"power":0.9}}' | python scripts/merge_spec.py` (dev: `ct-base/scripts/merge_spec.py`). If `missing_required` is non-empty, clarify first. (The `compute` payload also carries `resolved_spec`, a full snapshot — additive, landed.)

> Red line: ct-samplesize's coze is a **stateless remote compute**; continuity MUST be solved locally — the remote cannot help unless you actively send history. `merge_spec.py` is the local **deterministic merger** (code-fixed, LLM-executed), not a fragile classifier — upholds family red line 4.

## Quick Menu — two-level routing (level-1 only here; level-2 in `references/menu.md`)

> Authoritative layered menu: [`references/menu.md`](references/menu.md) · CLI examples & bidirectional solve: [`references/cli_examples.md`](references/cli_examples.md) · Operation SOP: [`references/operation_sop.md`](references/operation_sop.md).
>
> **Two-level routing rule (per Type-Compute, do NOT dump the full test list):** on a Complex request, first show **only this level-1 summary** (6 endpoint categories + high-frequency design families). After the user picks a category, go to `references/menu.md` **Part 1** for that category and show the **level-2 sub-list** (the specific `--test` options). Never present all ~49 tests in one screen.

**Level 1 — endpoint categories:**
- ① **Continuous** (means) · ② **Binary / Proportions** (rates, OR/RR, NI/BE) · ③ **Count / Rates** (Poisson) · ④ **Survival / Time-to-event** (logrank, HR, one-sample) · ⑤ **Diagnostic / Method comparison** (ROC, Bland-Altman) · ⑥ **Special / Advanced designs** (group-sequential, adaptive, Bayesian, MAMS, win-ratio, cluster …)

**Level 1 — high-frequency design-family entries** (non-exclusive; full list in `references/menu.md` Part 2): Group-Sequential · Adaptive · Equivalence / Non-inferiority / BE · Bayesian · Dose-escalation · MAMS · Historical control · Vaccine · Win-statistics · Cluster / Multiple endpoints

> ③ **Can't decide?** → say "explain the differences between these choices in detail", and I'll clarify the clinical/statistical meaning before you choose. (Family-standard wording, verbatim.)

> The menu is a *navigation aid*, not a strict taxonomy: the same test is reachable from multiple categories (e.g. `gsd_survival` from both ④ Survival and the Group-Sequential index). Still unsure where to start? Use **Part 0** in `references/menu.md` — find your test by *research question*, no jargon needed.

**Advanced:** `--test adaptive_simulate` empirically validates adaptive / group-sequential designs (power, type I error, expected N) — full guide → [`references/adaptive_simulator.md`](references/adaptive_simulator.md). `--verify` (default OFF) re-simulates an **analytic** solution with an **independent** Monte-Carlo engine (checks empirical power ±2 pp / type-I error ±0.5 pp; takes only the n as input, so a wrongly-derived n is caught) — supports `ttest_* / proportion_two / survival(log-rank) / group_sequential / adaptive_reestimate`; reports MC 95% CI, returns `INCONCLUSIVE` rather than a false PASS. Pure local, no network.

---

## Requirements

| Requirement | Details |
|:---|:---|
| **coze compute endpoint** | **Production default.** Set `CTSS_COZE_ENDPOINT` (or `COZE_ENDPOINT`) to the coze R service; covers all 49 tests. For a no-network demo, set `CTSS_COZE_MOCK=1`. |
| **Python** | ≥ 3.8, **stdlib only** (argparse / json / urllib). The v5 refactor removed the local pure-Python fallback and all third-party compute deps (statsmodels / numpy / scipy are no longer required). No local R required. |
| **R (dev / optional)** | **Not shipped in the published skill.** The coze R engine source is maintained in the coze-synced backend directory (excluded from the publish package). The legacy local-R backend and R templates are kept for offline dev / contribution only — **the v5 `select_backend` no longer routes to them**; they are not part of the published skill. |

---

## ⚠️ Safety

- **No local R / shell is ever executed.** The published skill never runs R or a shell on your machine. The default engine is the remote **coze** compute service: only trial-design parameters (never patient data) are sent, and results come back as numbers + optional figures — inherently safe (stateless compute, no local code execution).
- **SAFE PREVIEW is the default for inspection.** `--dry-run` prints the exact request envelope (test, params, mode) that *would* be sent to coze, without sending anything. `--show-code` reveals the coze request JSON (the R source coze used is included in every result by default). The legacy `--yes` gate applies only to the optional local-R dev backend (offline dev only).
- **First-use outbound disclosure (audit follow-up):** even though the public coze endpoint is pre-whitelisted (never prompts), the assistant MUST state on first outbound use in a session — in one line: "This will send your trial-design parameters plus a hostname hash (query_origin) and locale to the cloud service https://ct-samplesize.coze.site/run for computation — proceed?" (localized zh version in `references/security_model.md`). Custom endpoints still trigger the one-time AUTH-BLOCK confirmation. **Output for reference only; validate before regulatory submissions.**

### Security model (transparent disclosure)

> Full disclosure table (remote compute / server-side R / output / network / outbound gate / filesystem), upload confidentiality, and the natural-language outbound guidance → [`references/security_model.md`](references/security_model.md). Key guarantees: no local R/shell; SAFE PREVIEW default; only trial-design parameters ever leave the machine.

---

## User-Uploaded Documents

This skill is **parameter-driven** (design params via CLI / natural language). When the user uploads a document (protocol / SAP / design brief as `.docx` / `.pptx` / `.pdf` / `.doc`), **convert it to md/text first**, then extract the design parameters — the coze endpoint is a plain-text JSON contract and does **not** accept attachments. Converter: shared **`scripts/office_to_md.py`** (stdlib-only, single parser for docx+pptx):

| Uploaded format | Handling |
|---|---|
| `.docx` / `.pptx` | `python scripts/office_to_md.py <file>` → md (pptx sectioned by `### Slide N`) |
| `.pdf` / `.doc` / scanned | env `pdf` skill (OCR prompt) / word-reader / text-version prompt — never hand-write a parser |

**🔔 User notice before ANY conversion (show this exact notice first):**
> ⚠️ Every uploaded document is converted to **md** for processing; **PPT conversion tends to lose substantial information** (images, layout, animations, charts, and other non-text elements). We recommend you **convert to md and review the content yourself** before asking, so key details are not lost.

**Confidentiality:** the skill does **not** judge data confidentiality — the document is converted as-is; **only the extracted design parameters** (test, effect, α, power, n …) are ever sent to coze; the raw document md is used **locally for parameter extraction only** and never forwarded. If the user requires data-not-leaving, guide them to keep computation fully local (extract params and compute manually, or use the offline dev backend) — never send document content to coze.

---

## Implementation

**Bidirectional solve:** `--power` (default) solves required `n` given target power; `--nobs N` reverses to achievable power given fixed `n` (mutually exclusive, `--nobs` wins). Default = **SAFE PREVIEW**: `--dry-run` prints the coze request envelope without sending; `--show-code` reveals it (and, with `CTSS_RETURN_R_CODE=1`, the R source coze used); no `--yes` needed for coze (stateless remote compute). Full CLI examples (all 49 tests, reverse-solve, curve mode) → `references/cli_examples.md`; data format → `references/data_format_guide.md`.

**Common params:** `--side one|two` (default `two`, test direction); `--sd FLOAT` (optional, auto-computes Cohen's d = Δ/sd; omitted ⇒ `--effect` is d directly).

**Curve mode:** `--n_seq`/`--power_seq`/`--plot_effects`/`--effect_seq`/`--dist_plot`/`--power_time_seq`/`--heatmap` — see Features. **9 tests support curves** (`.curve_solvers`: ttest_ind/paired/one, anova, proportion_one/two, survival, equivalence, be_tost); `--dist_plot` covers `ttest*/proportion*/survival`; `--power_time_seq` survival-only; others return "curve not supported".

> **Architecture & security:** orchestration (`scripts/samplesize_power.py`) contains **no R code**; `ComputeBackend` (`scripts/compute_backend.py`) routes to `CozeBackend` (default authoritative, server-side R) — the only backend in v5. All R logic lives in the coze-synced, publish-excluded backend directory. Every user string reaching server-side R is validated against a strict allowlist. History → `CHANGELOG.md`.

---

## Figure Output & Rendering

Curves and any coze-returned `figures[].svg` follow the **uniform SVG spec shared across the ct-* family** (same pipeline as `meta-analysis`; no bespoke rendering).

- **★ Agent rule (mandatory, 2026-08-28 design revision):** the coze endpoint **emits all figures** (the 9 curve solvers attach curves by default, each with a `type` field); the conversation stream does **NOT** inline individual SVGs — figure presentation is fully delegated to the local `render_html_report`-generated **HTML aggregated report** (stats + all inlined SVGs + R reproduction script, single file openable in a browser). The conversation stream only needs to give the report entry point. To inline per-figure previews, set `CTSS_INLINE_WIDGET=1` to restore the `__SVG_WIDGET__` / `__FIGURE__` inline markers (off by default).
- **★ No hand-redraw:** present the skill-generated SVG as-is (axes, labels, power reference line included — the fallback generator draws the reference line itself, same `sy()` mapping as data points). Never rebuild curves with ad-hoc coordinates in the reply; charting stays under skill control.
- Details — figure_mode, render-hint thresholds, fallback ladder, reference line rule, reference implementation → [`references/rendering_rules.md`](references/rendering_rules.md).

---

## Default Figures (v5.6)

**Every** method produces at least one figure; all generation runs **on the coze side** (coze R `coze_figure_layer.R` primary → coze-internal `figure_kit.py` fallback), and the local CLI is a thin client that only consumes coze-returned `figures[]`. Engine figures come first, defaults are appended; when the engine already returned a power-N curve, the default primary is deduped out (alloc suite always kept). 8 default kinds (`power_n` / `power_events` / `power_n_multi` / `margin_tradeoff` / `icc_sens` / `gs_boundary` / `assurance_n` / secondary `alloc_suite`); curves are pinned exactly through the R anchor via the family-level noncentrality law (z/t/F/X), each with an effect ±20 % sensitivity band. Zero new R packages (`svglite` already tier1); coze platform deployment is manual (user-side), the local `adapters/coze/` mirror stays latest.

> Full spec — layer table, figure-kind table, alloc suite math (Schoenfeld identity, Neyman optimal k*), accuracy, env knobs → [`references/default_figures.md`](references/default_figures.md).

---

## Formulas & Reports

**Formulas:** `references/formulas.md` (all 49 types, incl. independent t / Schoenfeld survival / Cox-with-covariate / Cluster DEFF) | **Full functions:** `references/extended_functions.md`

---

## Errors

| Error | Fix |
|:---|:---|
| coze endpoint not configured / unreachable (coze may surface this as a Chinese or English `error_message`; the user-facing text is auto-localized via the i18n layer, key `error.coze_unreachable`) | Set `CTSS_COZE_ENDPOINT` (real) or `CTSS_COZE_MOCK=1` (demo); v5 has no local compute route (dev: run the legacy backend from the offline dev backend directly) |

## Bug Reporting

Agent behavior only; implementation → `adapters/bug_report.py`, protocol → `references/bug_report_endpoint.md`.

- **Trigger (strong signal, max 1 proposal/session):** unexpected non-zero exit / engine or compute error / user explicitly questions the result — **and** the same operation was retried ≥1. Weak signal (repeated tuning) never triggers. Explicit user request (e.g., "report a bug") also triggers, without the once-per-session limit.
- **Two-stage confirmation:** ① propose-with-preview — show the bilingual `confirm_prompt` **with** the full sanitized report (`render_report_text`); user may add a `description` (re-render & re-show before consent) → ② on explicit consent, `send_to_endpoint` (action=report, endpoint `https://ct-bugreport.coze.site/run`). If declined, never re-propose this session.
- **Sanitization is hard:** report carries only the 11-key whitelist — never raw data or subject records. `description` is the only free-text field, **user-reviewed**; hard boundary: no identifiable person/institution/subject info. If the session had **no** cloud call, `save_local_report()` writes locally (data never leaves the machine).
- **Client-only:** send `report` only. Governance actions (get/update/download/delete) are reserved for `ct-update`; never call them here.

---

## Related skills (ct- library, agent chains as needed)

- **Upstream (context)**: `ct-registry` (via `ct-pipeline` public-intel orchestration) · **Downstream**: `ct-protocol` (protocol skeleton) → `ct-ecrf` (CRF + SDTM mapping spec) · **Same category (design)**: `ct-protocol` / `ct-ecrf` / `ct-eligibility` · **Public-intel (Tier B)**: `ct-pipeline` (dispatches `ct-registry` / `ct-safety` / `ct-literature`)
