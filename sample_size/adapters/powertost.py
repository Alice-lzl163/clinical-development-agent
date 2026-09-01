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
