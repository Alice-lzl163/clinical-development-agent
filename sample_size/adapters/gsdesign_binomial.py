import math

from .base import AdapterResult, PackageAdapter, r_literal


class GsDesignBinomialAdapter(PackageAdapter):
    package = "gsDesign"
    function = "gsDesign::nBinomial"

    def calculate(self, *, treatment_probability: float, control_probability: float, null_ratio: float, allocation_ratio: float, alpha: float, power: float, scale: str) -> AdapterResult:
        beta = 1 - power
        package_ratio = 1 / allocation_ratio
        delta0 = math.log(null_ratio)
        inverse_arguments = {"p1": treatment_probability, "p2": control_probability, "alpha": alpha, "beta": beta, "delta0": delta0, "ratio": package_ratio, "sided": 1, "outtype": 3, "scale": scale, "n": None}
        code = f'''inverse <- gsDesign::nBinomial(
  p1 = {r_literal(treatment_probability)}, p2 = {r_literal(control_probability)},
  alpha = {r_literal(alpha)}, beta = {r_literal(beta)}, delta0 = {r_literal(delta0)},
  ratio = {r_literal(package_ratio)}, sided = 1, outtype = 3,
  scale = {r_literal(scale)}, n = NULL
)
raw_total <- as.numeric(inverse$n[[1]])
raw_n1 <- as.numeric(inverse$n1[[1]])
raw_n2 <- as.numeric(inverse$n2[[1]])
n_treatment <- ceiling(raw_n1)
n_control <- ceiling(raw_n2)
target_power <- {r_literal(power)}
forward_power <- function(nt, nc) {{
  forward <- gsDesign::nBinomial(
    p1 = {r_literal(treatment_probability)}, p2 = {r_literal(control_probability)},
    alpha = {r_literal(alpha)}, delta0 = {r_literal(delta0)}, ratio = nc / nt,
    sided = 1, outtype = 3, scale = {r_literal(scale)}, n = nt + nc
  )
  list(power = as.numeric(forward$Power[[1]]), p10 = as.numeric(forward$p10[[1]]),
       p20 = as.numeric(forward$p20[[1]]), n1 = as.numeric(forward$n1[[1]]),
       n2 = as.numeric(forward$n2[[1]]))
}}
checked <- forward_power(n_treatment, n_control)
increments <- 0L
while (checked$power + 1e-12 < target_power) {{
  if (n_treatment / {r_literal(allocation_ratio)} <= n_control) {{
    n_treatment <- n_treatment + 1L
  }} else {{
    n_control <- n_control + 1L
  }}
  increments <- increments + 1L
  if (increments > 100000L) stop("ROUNDING_CONVERGENCE_FAILURE")
  checked <- forward_power(n_treatment, n_control)
}}
list(package_total = raw_total, package_n1 = raw_n1, package_n2 = raw_n2,
     analysis_n_treatment = n_treatment, analysis_n_control = n_control,
     achieved_power = checked$power, constrained_null_p1 = checked$p10,
     constrained_null_p2 = checked$p20, checked_n1 = checked$n1,
     checked_n2 = checked$n2, rounding_increments = increments,
     realized_package_ratio = n_control / n_treatment)'''
        arguments = {
            "inverse": inverse_arguments,
            "forward_recheck": {"p1": treatment_probability, "p2": control_probability, "alpha": alpha, "delta0": delta0, "ratio": "analysis_n_control / analysis_n_treatment", "sided": 1, "outtype": 3, "scale": scale, "n": "analysis_n_treatment + analysis_n_control"},
        }
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(gsDesign)\n\n" + code, self.function)

    def power(self, *, treatment_probability: float, control_probability: float, null_ratio: float, n_treatment: int, n_control: int, alpha: float, scale: str) -> AdapterResult:
        delta0 = math.log(null_ratio)
        total = n_treatment + n_control
        package_ratio = n_control / n_treatment
        arguments = {"p1": treatment_probability, "p2": control_probability, "alpha": alpha, "beta": None, "delta0": delta0, "ratio": package_ratio, "sided": 1, "outtype": 3, "scale": scale, "n": total}
        code = f'''forward <- gsDesign::nBinomial(
  p1 = {r_literal(treatment_probability)}, p2 = {r_literal(control_probability)},
  alpha = {r_literal(alpha)}, delta0 = {r_literal(delta0)},
  ratio = {r_literal(package_ratio)}, sided = 1, outtype = 3,
  scale = {r_literal(scale)}, n = {total}
)
list(achieved_power = as.numeric(forward$Power[[1]]),
     checked_n1 = as.numeric(forward$n1[[1]]), checked_n2 = as.numeric(forward$n2[[1]]),
     constrained_null_p1 = as.numeric(forward$p10[[1]]),
     constrained_null_p2 = as.numeric(forward$p20[[1]]),
     realized_package_ratio = {r_literal(package_ratio)})'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(gsDesign)\n\n" + code, self.function)
