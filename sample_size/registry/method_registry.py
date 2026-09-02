from sample_size.engines.errors import UnknownMethodError
from sample_size.methods.fixed_designs import AnovaMethod, BioequivalenceMethod, MeanEquivalenceMethod, ProportionMarginMethod, ProportionOneMethod, ProportionPairedMethod, ProportionTwoMethod, TTestMethod

IMPLEMENTED_KEYS = frozenset({"ttest_one", "ttest_paired", "ttest_ind", "anova", "proportion_two", "be_tost", "proportion_one", "proportion_paired", "equivalence", "non_inferiority", "superiority_margin"})


def get_method(test_key, engine):
    if test_key == "ttest_one":
        return TTestMethod(engine, test_key, "one.sample")
    if test_key == "ttest_paired":
        return TTestMethod(engine, test_key, "paired")
    if test_key == "ttest_ind":
        return TTestMethod(engine, test_key, "two.sample")
    if test_key == "anova":
        return AnovaMethod(engine)
    if test_key == "proportion_two":
        return ProportionTwoMethod(engine)
    if test_key == "be_tost":
        return BioequivalenceMethod(engine)
    if test_key == "proportion_one":
        return ProportionOneMethod(engine)
    if test_key == "proportion_paired":
        return ProportionPairedMethod(engine)
    if test_key == "equivalence":
        return MeanEquivalenceMethod(engine)
    if test_key in {"non_inferiority", "superiority_margin"}:
        return ProportionMarginMethod(engine, test_key)
    raise UnknownMethodError(f"test_key is not implemented locally: {test_key!r}")
