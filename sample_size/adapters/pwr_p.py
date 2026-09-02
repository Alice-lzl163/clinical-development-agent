import math

from .base import AdapterResult, PackageAdapter, r_literal


class PwrProportionAdapter(PackageAdapter):
    package = "pwr"
    function = "pwr::pwr.p.test"
    ALTERNATIVES = {"two_sided": "two.sided", "greater": "greater", "less": "less"}

    @staticmethod
    def cohen_h(alternative_probability: float, null_probability: float) -> float:
        return 2 * math.asin(math.sqrt(alternative_probability)) - 2 * math.asin(math.sqrt(null_probability))

    def calculate(self, *, alternative_probability: float, null_probability: float, alpha: float, power: float, alternative: str) -> AdapterResult:
        effect = self.cohen_h(alternative_probability, null_probability)
        package_alternative = self.ALTERNATIVES[alternative]
        arguments = {"h": effect, "sig.level": alpha, "power": power, "alternative": package_alternative}
        code = f'''result <- pwr::pwr.p.test(
  h = {r_literal(effect)}, sig.level = {r_literal(alpha)}, power = {r_literal(power)},
  alternative = {r_literal(package_alternative)}
)
analysis_n <- ceiling(result$n)
forward <- pwr::pwr.p.test(
  h = {r_literal(effect)}, n = analysis_n, sig.level = {r_literal(alpha)},
  alternative = {r_literal(package_alternative)}
)
list(package_n = unname(result$n), analysis_n = analysis_n,
     achieved_power = unname(forward$power))'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(pwr)\n\n" + code, self.function)

    def power(self, *, n: int, alternative_probability: float, null_probability: float, alpha: float, alternative: str) -> AdapterResult:
        effect = self.cohen_h(alternative_probability, null_probability)
        package_alternative = self.ALTERNATIVES[alternative]
        arguments = {"h": effect, "n": n, "sig.level": alpha, "alternative": package_alternative}
        code = f'''result <- pwr::pwr.p.test(
  h = {r_literal(effect)}, n = {n}, sig.level = {r_literal(alpha)},
  alternative = {r_literal(package_alternative)}
)
list(achieved_power = unname(result$power))'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(pwr)\n\n" + code, self.function)
