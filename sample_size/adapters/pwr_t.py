from .base import AdapterResult, PackageAdapter, r_literal


class PwrTAdapter(PackageAdapter):
    package = "pwr"
    function = "pwr::pwr.t.test"
    ALTERNATIVES = {"two_sided": "two.sided", "greater": "greater", "less": "less"}

    def calculate(self, *, effect: float, alpha: float, power: float, alternative: str, test_type: str) -> AdapterResult:
        package_alternative = self.ALTERNATIVES[alternative]
        arguments = {"d": effect, "sig.level": alpha, "power": power, "type": test_type, "alternative": package_alternative}
        inversion = f'''result <- pwr::pwr.t.test(
  d = {r_literal(effect)}, sig.level = {r_literal(alpha)}, power = {r_literal(power)},
  type = {r_literal(test_type)}, alternative = {r_literal(package_alternative)}
)
analysis_n <- ceiling(result$n)
forward <- pwr::pwr.t.test(
  n = analysis_n, d = {r_literal(effect)}, sig.level = {r_literal(alpha)},
  type = {r_literal(test_type)}, alternative = {r_literal(package_alternative)}
)
list(package_n = unname(result$n), analysis_n = analysis_n, achieved_power = unname(forward$power))'''
        reproducible = "library(pwr)\n\n" + inversion
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=inversion)
        return AdapterResult(raw, arguments, reproducible, self.function)

    def power(self, *, n: int, effect: float, alpha: float, alternative: str, test_type: str) -> AdapterResult:
        package_alternative = self.ALTERNATIVES[alternative]
        arguments = {"n": n, "d": effect, "sig.level": alpha, "type": test_type, "alternative": package_alternative}
        code = f'''result <- pwr::pwr.t.test(
  n = {n}, d = {r_literal(effect)}, sig.level = {r_literal(alpha)},
  type = {r_literal(test_type)}, alternative = {r_literal(package_alternative)}
)
list(achieved_power = unname(result$power))'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(pwr)\n\n" + code, self.function)
