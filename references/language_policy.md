# Language Policy

> This file is the detailed companion to the "Language policy" section in SKILL.md.
> Why it applies: this skill is a statistical-analysis skill published on ClawHub,
> so its **documentation follows the English-only rule defined in ct-base §13.2**.
> Runtime output language still follows the OS language setting (see below).

## Three core rules

1. **Follow OS language setting**: Output language (Chinese or English) is determined by the OS language setting — Chinese on a Chinese-OS, English otherwise.
2. **Prompt can force-switch**: The user may override the OS-based default at any time by explicitly requesting a language (e.g. "switch to English").
3. **Code output unaffected**: R/Python code itself is always English, shown per `--show-code`; not affected by the language policy.

## Chinese-OS detection method

|Platform|Detection method|
|:---|:---|
|Linux / macOS|Read `LANG`, `LC_ALL`, `LANGUAGE`; check if the language code starts with `zh` (e.g. `zh_CN.UTF-8`)|
|Windows|Use `Get-Culture` / `Get-WinSystemLocale` PowerShell cmdlets, or read the `os` env to check if the language code starts with `zh` (e.g. `zh-CN`)|

If the OS language is set to Chinese, output Chinese; otherwise output English.

## Module tiers: runtime output coverage

### Common modules (runtime output may be EN + ZH)

- **Common test types**: `ttest_ind`, `ttest_paired`, `ttest_one`, `anova`, `proportion_one`, `proportion_two`, `proportion_paired`, `odds_ratio`, `risk_ratio`, `roc`, `poisson`, `non_inferiority`, `superiority_margin`, `be_tost`, `equivalence`, `survival`, `ni_survival`, `cluster`, `dunnett`
- **Shared components**: report template (`report_template.md`), quick menu, flag reference — these may keep EN/ZH bilingual runtime output.

### Complex/rare modules (EN-only for now)

`group_sequential`, `adaptive`, `mixed_model`, `bayesian`, `win_ratio`, `must_win`, `historical_controls`, `assurance`, `conditional_power`, `dose_escalation`, `bland_altman`, `vaccine_efficacy`, `mams`, `survival_exact`, `mediation`

> When maintaining, if the user frequently uses one of the above, prioritize adding Chinese prompt content to promote it to a "common module".

## Doc language convention (for maintainers)

- `README.md`: English only (keep the top EN/CN switch menu).
- `README_zh-CN.md`: Chinese only.
- `SKILL.md`, `AGENTS.md`, `report_template.md`, `cli_examples.md` etc.: **English-only** (per ct-base §13.2). Do not keep bilingual titles or bilingual menus in the documentation itself.
- When editing docs, the documentation must be English-only; existing Chinese documentation fragments should be removed, not preserved.
