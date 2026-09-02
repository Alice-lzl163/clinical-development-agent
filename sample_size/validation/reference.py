"""Independent validation-only calculations; never used for production results."""

import math


def one_proportion_arcsine_power(*, n, p1, p0, alpha, alternative):
    from scipy.stats import norm
    h = 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p0))
    if alternative == "two_sided":
        z = norm.ppf(1 - alpha / 2)
        return float(norm.cdf(-z - h * math.sqrt(n)) + norm.sf(z - h * math.sqrt(n)))
    if alternative == "greater":
        return float(norm.sf(norm.ppf(1 - alpha) - h * math.sqrt(n)))
    return float(norm.cdf(norm.ppf(alpha) - h * math.sqrt(n)))


def mcnemar_power(*, n, p01, p10, alpha):
    """TrialSize McNemar asymptotic power, independently transcribed."""
    from scipy.stats import norm
    psi, paid = p01 / p10, p01 + p10
    za = norm.ppf(1 - alpha / 2)
    scale = math.sqrt((psi + 1) ** 2 - (psi - 1) ** 2 * paid)
    zb = (math.sqrt(n * (psi - 1) ** 2 * paid) - za * (psi + 1)) / scale
    return float(norm.cdf(zb))


def mean_equivalence_normal_power(*, n_treatment, n_control, difference, sd, margin, alpha):
    """Independent normal-approximation TOST power matching the declared TrialSize method."""
    from scipy.stats import norm
    se = sd * math.sqrt(1 / n_treatment + 1 / n_control)
    z = norm.ppf(1 - alpha)
    return float(max(0, norm.cdf((margin - difference) / se - z) - norm.cdf((-margin - difference) / se + z)))


def mean_equivalence_exact_tost_power(*, n_treatment, n_control, difference, sd, margin, alpha):
    """Validation-only exact pooled-variance TOST power by chi-square integration."""
    from scipy.integrate import quad
    from scipy.stats import chi2, norm, t
    df = n_treatment + n_control - 2
    se = sd * math.sqrt(1 / n_treatment + 1 / n_control)
    critical = t.ppf(1 - alpha, df)
    q_max = df * (margin / (critical * se)) ** 2
    def integrand(q):
        width = critical * se * math.sqrt(q / df)
        conditional = max(0.0, norm.cdf((margin-width-difference)/se) - norm.cdf((-margin+width-difference)/se))
        return conditional * chi2.pdf(q, df)
    value, _ = quad(integrand, 0, q_max, epsabs=1e-12, epsrel=1e-11, limit=300)
    return float(value)


def risk_difference_margin_power(*, n_treatment, n_control, p1, p2, margin, alpha):
    from scipy.stats import norm
    se = math.sqrt(p1 * (1 - p1) / n_treatment + p2 * (1 - p2) / n_control)
    return float(norm.cdf((p1 - p2 - margin) / se - norm.ppf(1 - alpha)))


def gsdesign_ratio_reference(*, n_treatment, n_control, p1, p2, null_ratio, alpha, scale):
    """Independent Python implementation of the nBinomial Farrington-Manning equations."""
    from scipy.stats import norm
    ratio = n_control / n_treatment
    if scale == "RR":
        rr = null_ratio
        a = 1 + ratio
        b = -(rr * (1 + ratio * p2) + ratio + p1)
        c = rr * (p1 + ratio * p2)
        p10 = (-b - math.sqrt(b * b - 4 * a * c)) / (2 * a)
        p20 = p10 / rr
        sigma0 = math.sqrt((ratio + 1) * (p10 * (1-p10) + rr**2 * p20 * (1-p20) / ratio))
        sigma1 = math.sqrt((ratio + 1) * (p1 * (1-p1) + rr**2 * p2 * (1-p2) / ratio))
        effect = p1 - rr * p2
    elif scale == "OR":
        inv_or = 1 / null_ratio
        a = inv_or - 1
        b = 1 + ratio * inv_or + (1-inv_or) * (ratio*p2+p1)
        c = -(ratio*p2+p1)
        p10 = (-b + math.sqrt(b*b-4*a*c))/(2*a) if abs(a) > 1e-14 else (p1+ratio*p2)/(1+ratio)
        p20 = inv_or*p10/(1+p10*(inv_or-1))
        sigma0 = math.sqrt((ratio+1)*(1/p10/(1-p10)+1/p20/(1-p20)/ratio))
        sigma1 = math.sqrt((ratio+1)*(1/p1/(1-p1)+1/p2/(1-p2)/ratio))
        effect = math.log(inv_or / p2 * (1-p2) * p1/(1-p1))
    else:
        raise ValueError("scale must be OR or RR")
    total = n_treatment + n_control
    power = norm.cdf(-(norm.ppf(1-alpha) - math.sqrt(total)*effect/sigma0)*sigma0/sigma1)
    return {"power": float(power), "p10": p10, "p20": p20, "sigma0": sigma0, "sigma1": sigma1}


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
