"""Independent validation-only calculations; never used for production results."""

import math


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


def proportion_equality_power(*, treatment_probability: float, control_probability: float, n_treatment: int, n_control: int, alpha: float) -> float:
    """Independent normal approximation matching TrialSize equality assumptions.

    Uses a two-sided z critical value and the alternative unpooled variance
    p1(1-p1)/n1 + p2(1-p2)/n2. The frozen orientation is n1=treatment.
    """
    from scipy.stats import norm
    variance=treatment_probability*(1-treatment_probability)/n_treatment+control_probability*(1-control_probability)/n_control
    z_beta=abs(treatment_probability-control_probability)/(variance**0.5)-norm.ppf(1-alpha/2)
    return float(norm.cdf(z_beta))


def be_tost_power(*, n: int, cv: float, theta0: float, lower_limit: float, upper_limit: float, design: str, alpha: float) -> float:
    """Independent exact TOST power by conditioning on residual variance.

    For balanced 2x2 and parallel designs, the log-estimate is normal and
    independent of the residual chi-square variance estimate. Integrating the
    conditional probability that both one-sided t inequalities hold avoids
    PowerTOST and its Owen-Q implementation.
    """
    from scipy.integrate import quad
    from scipy.stats import chi2, norm, t
    if n % 2 or n < 4: raise ValueError("balanced TOST reference requires even total n >= 4")
    design_factor={"2x2":2.0,"parallel":4.0}.get(design)
    if design_factor is None: raise ValueError("unsupported design")
    df=n-2
    sigma=math.sqrt(math.log1p(cv**2))*math.sqrt(design_factor/n)
    lower,upper,mu=math.log(lower_limit),math.log(upper_limit),math.log(theta0)
    critical=t.ppf(1-alpha,df)
    q_max=df*((upper-lower)/(2*critical*sigma))**2
    def integrand(q):
        width=critical*sigma*math.sqrt(q/df)
        conditional=max(0.0,norm.cdf((upper-width-mu)/sigma)-norm.cdf((lower+width-mu)/sigma))
        return conditional*chi2.pdf(q,df)
    value,error=quad(integrand,0,q_max,epsabs=1e-12,epsrel=1e-12,limit=250)
    return float(value)
