# Round 5.1B gsDesign OR/RR Contract Introspection

## Environment

Local commands were executed with `C:/Program Files/R/R-4.6.1/bin/Rscript.exe`. The captured values were:

```text
R version 4.6.1 (2026-06-24 ucrt)
gsDesign 3.11.0
.libPaths():
C:/Users/ZhuoChang/AppData/Local/R/win-library/4.6
C:/Program Files/R/R-4.6.1/library
```

gsDesign 3.11.0 is `INSTALLED_UNVALIDATED`. Introspection and successful exploratory calls are not numerical validation.

## Commands

The pass captured `R.version.string`, `packageVersion("gsDesign")`, `.libPaths()`, `args(gsDesign::nBinomial)`, `formals(gsDesign::nBinomial)`, and the installed function body. Installed help was resolved through `help("nBinomial", package="gsDesign")`; its Rd topic is `varBinomial.Rd` and was rendered with `tools::Rd2txt(tools::Rd_db("gsDesign")[["varBinomial.Rd"]])`.

The exact 3.11.0 signature is:

```r
nBinomial(
  p1, p2, alpha = 0.025, beta = 0.1, delta0 = 0,
  ratio = 1, sided = 1, outtype = 1,
  scale = "Difference", n = NULL
)
```

## Authoritative package semantics

- `p1` and `p2` are group 1 and group 2 event rates under the alternative. Shared help and examples conventionally use group 1 as control and group 2 as experimental, but the calculation itself is group-labelled. The project explicitly binds group 1 to treatment and group 2 to control so its effect is treatment/control and the supported upper-tail direction is coherent.
- `ratio` is `n2/n1`. Under the project binding, sample-size mode therefore passes `1/allocation_ratio`, where public allocation is treatment/control. Power mode passes the realized `analyzable_control/analyzable_treatment` ratio.
- `alpha` is type-I error. `sided=1` uses `qnorm(1-alpha)`; `sided=2` uses `qnorm(1-alpha/2)`. The frozen contracts use one-sided alpha and `sided=1`.
- `beta` is type-II error. In inverse mode output `Power` is `1-beta`; when `n` is supplied the function calculates power and returns computed beta.
- Accepted scale identifiers in the installed source are case-insensitive `Difference`, `RR`, `OR`, and `LNOR`. `OR` and `LNOR` enter the same source branch and produced identical results, including with nonzero `delta0`. The project selects `OR` explicitly.
- For `scale="RR"`, the source sets the null group-1/group-2 risk ratio to `exp(delta0)`. Thus `delta0=log(null_risk_ratio)` under the project binding.
- For `scale="OR"` or `"LNOR"`, package checks and empirical calls establish that `delta0` is the natural log of the null group-1/group-2 odds ratio. Thus `delta0=log(null_odds_ratio)` under the project binding. It is not a raw OR.
- `n=NULL` solves continuous total sample size. `outtype=1` returns total `n`; `outtype=2` returns continuous `n1` and `n2`; `outtype=3` returns `n`, `n1`, `n2`, alpha, sidedness, beta, Power, variances, alternative rates, delta0, and constrained null rates.
- Supplying `n` requests forward power, and `n` is total analyzable sample size. Allocation is applied as `n1=n/(1+ratio)` and `n2=ratio*n/(1+ratio)`. The package does not round. Sample-size implementations must ceil `n1` and `n2` separately, then re-run power using their integer total and realized `n2/n1` ratio before dropout inflation.

## Empirical orientation calls

Prespecified discovery calls used control `0.20`, treatment `0.35`, and public treatment/control allocation `2`. Calls varied `p1/p2`, package ratio `0.5/2`, scales, and output types.

With `p1=.35`, `p2=.20`, and `ratio=.5`, `outtype=2` returned:

| Scale | Total n | n1 | n2 |
|---|---:|---:|---:|
| RR | 316.366426206 | 210.910950804 | 105.455475402 |
| OR | 300.927658277 | 200.618438852 | 100.309219426 |
| LNOR | 300.927658277 | 200.618438852 | 100.309219426 |

Changing package ratio to `2` made `n2` twice `n1`; reversing probabilities and ratios produced the corresponding swapped allocation results. This directly confirms `ratio=n2/n1`.

For a non-unity null ratio of `1.2`, the project mapping used `p1=.35`, `p2=.20`, `ratio=.5`, and `delta0=log(1.2)`. RR inverse output was `n=731.431736228`, `n1=487.621157485`, `n2=243.810578743`; after rounding to 488/244, the supplied-`n` call returned power `0.800318198397`. OR inverse output was `n=527.711039583`, `n1=351.807359722`, `n2=175.903679861`; after rounding to 352/176, forward power was `0.800204498581`.

These are contract-discovery observations, not frozen numerical benchmarks.

## Frozen project contracts

Both contracts define group 1 as treatment and group 2 as control, require a strictly interior control probability, derive the treatment probability from the public treatment/control ratio, and reject infeasible probabilities. Both support only `H1: treatment/control ratio > null ratio` with favorable success coding, one-sided alpha, and `sided=1`. Lower-tail, two-sided, adverse-event-without-recoding, exact, adjusted, clustered, matched, stratified, and covariate-adjusted designs are unsupported.

Public power mode takes analyzable treatment and control counts, never randomized counts. It derives total `n` and the realized control/treatment package ratio. Dropout is relevant only to inverse sample-size mode and is applied after integer analyzable arm sizes are established.

## Freeze decisions

- `odds_ratio`: `SPEC_FROZEN` using `scale="OR"`, `delta0=log(null_odds_ratio)`, and the declared upper-tail project binding.
- `risk_ratio`: `SPEC_FROZEN` using `scale="RR"`, `delta0=log(null_risk_ratio)`, and the declared upper-tail project binding.

No calculators were implemented and no validation or production status was assigned.
