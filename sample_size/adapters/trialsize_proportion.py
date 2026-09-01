from .base import AdapterResult, PackageAdapter, r_literal


class TrialSizeProportionAdapter(PackageAdapter):
    package = "TrialSize"
    function = "TrialSize::TwoSampleProportion.Equality"

    def calculate(self, *, treatment_probability: float, control_probability: float, allocation_ratio: float, alpha: float, power: float) -> AdapterResult:
        beta = 1 - power
        arguments = {"alpha": alpha, "beta": beta, "p1": treatment_probability, "p2": control_probability, "k": allocation_ratio}
        code = f'''package_n1 <- TrialSize::TwoSampleProportion.Equality(
  alpha = {r_literal(alpha)}, beta = {r_literal(beta)}, p1 = {r_literal(treatment_probability)},
  p2 = {r_literal(control_probability)}, k = {r_literal(allocation_ratio)}
)
n_treatment <- ceiling(as.numeric(package_n1))
n_control <- ceiling(as.numeric(package_n1) / {r_literal(allocation_ratio)})
z_alpha <- stats::qnorm(1 - {r_literal(alpha)} / 2)
variance <- {r_literal(treatment_probability)} * (1 - {r_literal(treatment_probability)}) / n_treatment +
  {r_literal(control_probability)} * (1 - {r_literal(control_probability)}) / n_control
z_beta <- abs({r_literal(treatment_probability)} - {r_literal(control_probability)}) / sqrt(variance) - z_alpha
achieved_power <- stats::pnorm(z_beta)
list(package_n_treatment = as.numeric(package_n1), analysis_n_treatment = n_treatment,
     analysis_n_control = n_control, achieved_power = achieved_power)'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(TrialSize)\n\n" + code)
