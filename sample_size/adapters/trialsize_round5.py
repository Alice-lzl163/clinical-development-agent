from .base import AdapterResult, PackageAdapter, r_literal


class TrialSizeMcNemarAdapter(PackageAdapter):
    package = "TrialSize"
    function = "TrialSize::McNemar.Test"

    def calculate(self, *, p_treatment_only: float, p_control_only: float, alpha: float, power: float) -> AdapterResult:
        beta = 1 - power
        psai = p_treatment_only / p_control_only
        paid = p_treatment_only + p_control_only
        arguments = {"alpha": alpha, "beta": beta, "psai": psai, "paid": paid}
        code = f'''package_n <- TrialSize::McNemar.Test(
  alpha = {r_literal(alpha)}, beta = {r_literal(beta)},
  psai = {r_literal(psai)}, paid = {r_literal(paid)}
)
analysis_n <- ceiling(as.numeric(package_n))
z_alpha <- stats::qnorm(1 - {r_literal(alpha)} / 2)
numerator_scale <- sqrt(({r_literal(psai)} + 1)^2 - ({r_literal(psai)} - 1)^2 * {r_literal(paid)})
z_beta <- (sqrt(analysis_n * ({r_literal(psai)} - 1)^2 * {r_literal(paid)}) -
  z_alpha * ({r_literal(psai)} + 1)) / numerator_scale
list(package_n = as.numeric(package_n), analysis_n = analysis_n,
     achieved_power = stats::pnorm(z_beta))'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(TrialSize)\n\n" + code, self.function)


class TrialSizeMeanEquivalenceAdapter(PackageAdapter):
    package = "TrialSize"
    function = "TrialSize::TwoSampleMean.Equivalence"

    def calculate(self, *, expected_difference: float, sd: float, equivalence_margin: float, allocation_ratio: float, alpha: float, power: float) -> AdapterResult:
        beta = 1 - power
        arguments = {"alpha": alpha, "beta": beta, "sigma": sd, "k": allocation_ratio, "delta": equivalence_margin, "margin": expected_difference}
        code = f'''package_n1 <- TrialSize::TwoSampleMean.Equivalence(
  alpha = {r_literal(alpha)}, beta = {r_literal(beta)}, sigma = {r_literal(sd)},
  k = {r_literal(allocation_ratio)}, delta = {r_literal(equivalence_margin)},
  margin = {r_literal(expected_difference)}
)
n_treatment <- ceiling(as.numeric(package_n1))
n_control <- ceiling(as.numeric(package_n1) / {r_literal(allocation_ratio)})
k_realized <- n_treatment / n_control
z_alpha <- stats::qnorm(1 - {r_literal(alpha)})
gap <- {r_literal(equivalence_margin)} - abs({r_literal(expected_difference)})
z_beta_half <- gap * sqrt(n_treatment / (k_realized * {r_literal(sd)}^2 * (1 + 1 / k_realized))) - z_alpha
achieved_power <- 1 - 2 * (1 - stats::pnorm(z_beta_half))
list(package_n_treatment = as.numeric(package_n1), analysis_n_treatment = n_treatment,
     analysis_n_control = n_control, achieved_power = achieved_power)'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(TrialSize)\n\n" + code, self.function)


class TrialSizeProportionMarginAdapter(PackageAdapter):
    package = "TrialSize"
    function = "TrialSize::TwoSampleProportion.NIS"

    def calculate(self, *, treatment_probability: float, control_probability: float, allocation_ratio: float, margin: float, alpha: float, power: float) -> AdapterResult:
        beta = 1 - power
        delta = treatment_probability - control_probability
        arguments = {"alpha": alpha, "beta": beta, "p1": treatment_probability, "p2": control_probability, "k": allocation_ratio, "delta": delta, "margin": margin}
        code = f'''package_n1 <- TrialSize::TwoSampleProportion.NIS(
  alpha = {r_literal(alpha)}, beta = {r_literal(beta)},
  p1 = {r_literal(treatment_probability)}, p2 = {r_literal(control_probability)},
  k = {r_literal(allocation_ratio)}, delta = {r_literal(delta)}, margin = {r_literal(margin)}
)
n_treatment <- ceiling(as.numeric(package_n1))
n_control <- ceiling(as.numeric(package_n1) / {r_literal(allocation_ratio)})
k_realized <- n_treatment / n_control
variance_term <- {r_literal(treatment_probability)} * (1 - {r_literal(treatment_probability)}) / k_realized +
  {r_literal(control_probability)} * (1 - {r_literal(control_probability)})
z_beta <- ({r_literal(delta)} - {r_literal(margin)}) * sqrt(n_treatment / (k_realized * variance_term)) -
  stats::qnorm(1 - {r_literal(alpha)})
list(package_n_treatment = as.numeric(package_n1), analysis_n_treatment = n_treatment,
     analysis_n_control = n_control, achieved_power = stats::pnorm(z_beta))'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(TrialSize)\n\n" + code, self.function)
