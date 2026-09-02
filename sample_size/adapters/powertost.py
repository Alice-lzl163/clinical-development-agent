from .base import AdapterResult, PackageAdapter, r_literal


class PowerTOSTAdapter(PackageAdapter):
    package = "PowerTOST"
    function = "PowerTOST::sampleN.TOST"

    def calculate(self, *, cv: float, theta0: float, lower_limit: float, upper_limit: float, design: str, alpha: float, power: float) -> AdapterResult:
        arguments = {"alpha": alpha, "targetpower": power, "theta0": theta0, "theta1": lower_limit, "theta2": upper_limit, "CV": cv, "design": design, "print": False}
        code = f'''result <- PowerTOST::sampleN.TOST(
  alpha = {r_literal(alpha)}, targetpower = {r_literal(power)}, theta0 = {r_literal(theta0)},
  theta1 = {r_literal(lower_limit)}, theta2 = {r_literal(upper_limit)}, CV = {r_literal(cv)},
  design = {r_literal(design)}, print = FALSE
)
evaluable_total <- as.integer(result[["Sample size"]][1])
forward_power <- PowerTOST::power.TOST(
  alpha = {r_literal(alpha)}, theta0 = {r_literal(theta0)}, theta1 = {r_literal(lower_limit)},
  theta2 = {r_literal(upper_limit)}, CV = {r_literal(cv)}, design = {r_literal(design)}, n = evaluable_total
)
list(package_n = as.numeric(result[["Sample size"]][1]), evaluable_total = evaluable_total,
     package_achieved_power = as.numeric(result[["Achieved power"]][1]), achieved_power = as.numeric(forward_power))'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(PowerTOST)\n\n" + code, self.function)

    def power(self, *, n: int, cv: float, theta0: float, lower_limit: float, upper_limit: float, design: str, alpha: float) -> AdapterResult:
        function = "PowerTOST::power.TOST"
        arguments = {"n": n, "alpha": alpha, "theta0": theta0, "theta1": lower_limit, "theta2": upper_limit, "CV": cv, "design": design}
        code = f'''result <- PowerTOST::power.TOST(
  n = {n}, alpha = {r_literal(alpha)}, theta0 = {r_literal(theta0)},
  theta1 = {r_literal(lower_limit)}, theta2 = {r_literal(upper_limit)}, CV = {r_literal(cv)}, design = {r_literal(design)}
)
list(achieved_power = as.numeric(result))'''
        raw = self.engine.execute(package=self.package, function=function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(PowerTOST)\n\n" + code, function)


class PowerTOSTMeanEquivalenceAdapter(PackageAdapter):
    """Exact original-scale parallel TOST power and deterministic inversion."""

    package = "PowerTOST"
    function = "PowerTOST::power.TOST"
    maximum_per_arm = 1_000_000

    @staticmethod
    def _call(*, expected_difference, sd, equivalence_margin, alpha, n_treatment, n_control):
        return f'''PowerTOST::power.TOST(
    alpha = {r_literal(alpha)}, logscale = FALSE,
    theta0 = {r_literal(expected_difference)}, theta1 = {-equivalence_margin!r},
    theta2 = {r_literal(equivalence_margin)}, CV = {r_literal(sd)},
    n = c({n_treatment}, {n_control}), design = "parallel",
    method = "exact", robust = FALSE
  )'''

    def calculate(self, *, expected_difference: float, sd: float, equivalence_margin: float,
                  allocation_ratio: float, alpha: float, power: float) -> AdapterResult:
        power_call = self._call(
            expected_difference=expected_difference, sd=sd,
            equivalence_margin=equivalence_margin, alpha=alpha,
            n_treatment="candidate_treatment", n_control="candidate_control",
        )
        code = f'''target_power <- {r_literal(power)}
allocation_ratio <- {r_literal(allocation_ratio)}
maximum_per_arm <- {self.maximum_per_arm}L
accepted <- FALSE
previous_power <- NA_real_
previous_treatment <- NA_integer_
previous_control <- NA_integer_
package_calls <- 0L
for (candidate_control in 2L:maximum_per_arm) {{
  candidate_treatment <- as.integer(ceiling(allocation_ratio * candidate_control))
  if (candidate_treatment > maximum_per_arm) stop("SEARCH_CONVERGENCE_FAILURE: arm maximum exceeded")
  if (candidate_treatment < 2L) next
  candidate_power <- as.numeric({power_call})
  package_calls <- package_calls + 1L
  if (length(candidate_power) != 1L || !is.finite(candidate_power) || candidate_power < 0 || candidate_power > 1)
    stop("PACKAGE_MAPPING_DEFECT: malformed power.TOST output")
  if (candidate_power >= target_power) {{
    accepted <- TRUE
    break
  }}
  previous_power <- candidate_power
  previous_treatment <- candidate_treatment
  previous_control <- candidate_control
}}
if (!accepted) stop("SEARCH_CONVERGENCE_FAILURE: no candidate achieved target power")
list(
  analysis_n_treatment = candidate_treatment,
  analysis_n_control = candidate_control,
  achieved_power = candidate_power,
  has_preceding_candidate = candidate_control > 2L,
  preceding_n_treatment = previous_treatment,
  preceding_n_control = previous_control,
  preceding_power = previous_power,
  search_iterations = package_calls,
  authoritative_package_calls = package_calls
)'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        arguments = {
            "alpha": alpha, "logscale": False, "theta0": expected_difference,
            "theta1": -equivalence_margin, "theta2": equivalence_margin, "CV": sd,
            "n": [raw.get("analysis_n_treatment"), raw.get("analysis_n_control")],
            "design": "parallel", "method": "exact", "robust": False,
        }
        return AdapterResult(raw, arguments, "library(PowerTOST)\n\n" + code, self.function)

    def power(self, *, expected_difference: float, sd: float, equivalence_margin: float,
              alpha: float, n_treatment: int, n_control: int) -> AdapterResult:
        call = self._call(
            expected_difference=expected_difference, sd=sd,
            equivalence_margin=equivalence_margin, alpha=alpha,
            n_treatment=n_treatment, n_control=n_control,
        )
        code = f'''result <- {call}
result <- as.numeric(result)
if (length(result) != 1L || !is.finite(result) || result < 0 || result > 1)
  stop("PACKAGE_MAPPING_DEFECT: malformed power.TOST output")
list(achieved_power = result, authoritative_package_calls = 1L)'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        arguments = {
            "alpha": alpha, "logscale": False, "theta0": expected_difference,
            "theta1": -equivalence_margin, "theta2": equivalence_margin, "CV": sd,
            "n": [n_treatment, n_control], "design": "parallel", "method": "exact",
            "robust": False,
        }
        return AdapterResult(raw, arguments, "library(PowerTOST)\n\n" + code, self.function)
