from .base import AdapterResult, PackageAdapter, r_literal


class PwrAnovaAdapter(PackageAdapter):
    package = "pwr"
    function = "pwr::pwr.anova.test"

    def calculate(self, *, groups: int, cohen_f: float, alpha: float, power: float) -> AdapterResult:
        arguments = {"k": groups, "f": cohen_f, "sig.level": alpha, "power": power}
        code = f'''result <- pwr::pwr.anova.test(k = {groups}, f = {r_literal(cohen_f)}, sig.level = {r_literal(alpha)}, power = {r_literal(power)})
analysis_n <- ceiling(result$n)
forward <- pwr::pwr.anova.test(k = {groups}, n = analysis_n, f = {r_literal(cohen_f)}, sig.level = {r_literal(alpha)})
list(package_n = unname(result$n), analysis_n_per_group = analysis_n, achieved_power = unname(forward$power))'''
        raw = self.engine.execute(package=self.package, function=self.function, calculation_code=code)
        return AdapterResult(raw, arguments, "library(pwr)\n\n" + code)
