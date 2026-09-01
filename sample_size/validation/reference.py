"""Independent validation-only calculations; never used for production results."""


def t_test_power(*, n: int, effect: float, alpha: float, test_type: str, alternative: str) -> float:
    from scipy.stats import nct, t
    if test_type in {"one.sample", "paired"}:
        df, ncp = n - 1, effect * n ** 0.5
    elif test_type == "two.sample":
        df, ncp = 2 * n - 2, effect * (n / 2) ** 0.5
    else:
        raise ValueError("unsupported t-test type")
    if alternative == "two.sided":
        critical = t.ppf(1 - alpha / 2, df)
        return float(nct.cdf(-critical, df, ncp) + nct.sf(critical, df, ncp))
    if alternative == "greater":
        return float(nct.sf(t.ppf(1 - alpha, df), df, ncp))
    return float(nct.cdf(t.ppf(alpha, df), df, ncp))


def anova_power(*, groups: int, n_per_group: int, cohen_f: float, alpha: float) -> float:
    from scipy.stats import f, ncf
    df1, df2 = groups - 1, groups * (n_per_group - 1)
    critical = f.ppf(1 - alpha, df1, df2)
    return float(ncf.sf(critical, df1, df2, groups * n_per_group * cohen_f ** 2))
