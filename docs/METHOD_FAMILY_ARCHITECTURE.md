# Sample-Size Method Family Architecture

## Purpose

The 49 test keys are stable user-facing routing names, not a mandate for 49 independent numerical implementations. Each key resolves to a versioned statistical specification, then to a reusable `method_id`, then to an engine family and—when applicable—a pinned R package function. The YAML specifications in `sample_size/specs/` are the normative source; this document is the human-readable architecture index.

No calculator is implemented in this phase. Every method remains `EXPERIMENTAL` or `VALIDATION_PENDING` and must pass `VALIDATION_PLAN.md` before exposure.

## Normative execution boundary

```text
ClinicalInput
    ↓ validated against the user-facing input contract
StatisticalDesignSpec
    ↓ explicit component adapter (when a package-native design object is needed)
DerivedParameters
    ↓ named formulas with declared inputs, units, and assumptions
PackageAdapter
    ↓ structured parameter_mapping and output_mapping
PackageFunction
```

Package-native objects are not clinical inputs. For example, `SequentialDesignSpec` is a user-facing statistical design and its adapter alone may construct the object returned by `rpact::getDesignGroupSequential`. Similarly, survival inputs are split into `SurvivalEndpointSpec`, `AccrualSpec`, and `DropoutSpec`; their declared derivations produce hazards and package arguments.

Every transformation crossing a layer is represented as structured data. A `derived_parameters` entry declares its formula, dependencies, output unit, and assumptions. A parameter mapping declares one package argument, its source type, its source, and any transformation. Combined prose placeholders are not executable contracts and are forbidden in `SPEC_FROZEN` specifications.

This separation prevents aliases such as `gsd_survival` and `gsd_hazard` from becoming duplicate calculators. It also prevents historically broad labels such as `adaptive`, `bayesian`, and `multiple_endpoints` from running until design-identifying inputs are complete.

## Reusable statistical design components

- `SequentialDesignSpec` declares looks, information rates, overall alpha, target power, sidedness, efficacy and futility boundary families, binding behavior, and spending parameters. Its R adapter constructs an `rpact` design; the object is internal and never supplied by a user.
- `SurvivalEndpointSpec` currently permits exponential event times only and declares control median and alternative hazard ratio.
- `AccrualSpec` declares uniform accrual duration, additional follow-up, and the event-time horizon.
- `DropoutSpec` declares exponential independent dropout, cumulative dropout probability, and its defining horizon. A positive cumulative probability without a horizon is invalid.

`specification_status` is independent of `lifecycle_status`. `SPEC_FROZEN` means the statistical and adapter contract is ready for calculator implementation; it does not mean the method is validated or production-ready.

## Consolidation summary

- User-facing test keys: **49**
- Unique method IDs: **45**
- Calculation engine families: **20**
- Required R packages: **17**
- Method classifications by user-facing key: `analytical_asymptotic` **21**, `analytical_exact` **6**, `numerical` **8**, `operating_characteristics` **6**, `precision` **1**, `simulation` **7**.

Required packages at specification freeze: `MKpower`, `MedianaDesigner`, `PowerTOST`, `RBesT`, `TrialSize`, `WRestimates`, `cmprsk`, `escalation`, `gsDesign`, `gsDesignNB`, `mvtnorm`, `pROC`, `powerMediation`, `powerSurvEpi`, `pwr`, `rpact`, `simr`.

## User key → method → engine map

| test_key | method_id | endpoint family | design family | method type | runtime | engine family | R package | authoritative function | lifecycle |
|---|---|---|---|---|---|---|---|---|---|
| `adaptive` | `adaptive_combination_design` | continuous_or_binary | adaptive | operating_characteristics | R | `rpact` | `rpact` | `rpact::getSimulationMeans` | EXPERIMENTAL |
| `adaptive_simulate` | `adaptive_simulation` | continuous_or_binary | adaptive_simulation | simulation | PYTHON | `custom_sim` | — | specification-frozen custom engine | EXPERIMENTAL |
| `anova` | `anova_oneway_balanced` | continuous | fixed_multi_arm | analytical_exact | R | `pwr_anova` | `pwr` | `pwr::pwr.anova.test` | VALIDATION_PENDING |
| `assurance` | `bayesian_assurance_sim` | binary_or_continuous | bayesian_assurance | operating_characteristics | PYTHON | `custom_sim` | — | specification-frozen custom engine | EXPERIMENTAL |
| `bayesian` | `bayesian_binary_decision_sim` | binary | bayesian_parallel | simulation | PYTHON | `custom_sim` | — | specification-frozen custom engine | EXPERIMENTAL |
| `be_tost` | `bioequivalence_tost` | continuous_pk | bioequivalence | numerical | R | `powertost` | `PowerTOST` | `PowerTOST::sampleN.TOST` | VALIDATION_PENDING |
| `bland_altman` | `bland_altman_precision` | method_comparison | paired_precision | precision | NONE | `analytical` | — | specification-frozen custom engine | VALIDATION_PENDING |
| `cluster` | `cluster_design_effect_equal` | generic | cluster_randomized | analytical_asymptotic | NONE | `analytical` | — | specification-frozen custom engine | VALIDATION_PENDING |
| `competing_risks` | `competing_risk_sim` | time_to_event_competing | fixed_parallel | simulation | R | `cmprsk` | `cmprsk` | `cmprsk::cuminc` | EXPERIMENTAL |
| `conditional_power` | `conditional_power_design` | continuous_or_binary | interim_monitoring | analytical_asymptotic | R | `rpact` | `rpact` | `rpact::getConditionalPower` | VALIDATION_PENDING |
| `cox_covariate` | `cox_covariate_effect` | time_to_event | regression | analytical_asymptotic | R | `powersurvepi` | `powerSurvEpi` | `powerSurvEpi::ssizeEpi / powerSurvEpi::ssizeEpiCont` | VALIDATION_PENDING |
| `dose_escalation` | `dose_escalation_oc` | binary_toxicity | phase_i_dose_finding | operating_characteristics | R | `escalation` | `escalation` | `escalation::simulate_trials` | EXPERIMENTAL |
| `dunnett` | `dunnett_many_to_one` | continuous | multiple_treatments_control | numerical | R | `mvtnorm` | `mvtnorm` | `mvtnorm::qmvt` | VALIDATION_PENDING |
| `equivalence` | `mean_equivalence_tost` | continuous | fixed_parallel_equivalence | analytical_exact | R | `trialsize` | `TrialSize` | `TrialSize::TwoSampleMean.Equivalence` | VALIDATION_PENDING |
| `group_sequential` | `gs_mean` | continuous | group_sequential | numerical | R | `rpact` | `rpact` | `rpact::getSampleSizeMeans` | VALIDATION_PENDING |
| `gsd_hazard` | `gs_survival` | time_to_event | group_sequential | numerical | R | `rpact` | `rpact` | `rpact::getSampleSizeSurvival` | VALIDATION_PENDING |
| `gsd_hazard_sim` | `gs_survival_sim` | time_to_event | group_sequential_simulation | simulation | R | `rpact` | `rpact` | `rpact::getSimulationSurvival` | VALIDATION_PENDING |
| `gsd_poisson` | `gs_counts` | count | group_sequential | numerical | R | `rpact` | `rpact` | `rpact::getSampleSizeCounts` | VALIDATION_PENDING |
| `gsd_proportion` | `gs_binary_rates` | binary | group_sequential | numerical | R | `rpact` | `rpact` | `rpact::getSampleSizeRates` | VALIDATION_PENDING |
| `gsd_survival` | `gs_survival` | time_to_event | group_sequential | numerical | R | `rpact` | `rpact` | `rpact::getSampleSizeSurvival` | VALIDATION_PENDING |
| `gsd_survival_sim` | `gs_survival_sim` | time_to_event | group_sequential_simulation | simulation | R | `rpact` | `rpact` | `rpact::getSimulationSurvival` | VALIDATION_PENDING |
| `historical_controls` | `map_historical_borrowing` | binary_or_continuous | external_control_borrowing | operating_characteristics | R | `rbest` | `RBesT` | `RBesT::gMAP` | EXPERIMENTAL |
| `mams` | `mams_simulation` | multiple_arms | multi_arm_multi_stage | operating_characteristics | R | `rpact` | `rpact` | `rpact::getSimulationMultiArmMeans` | EXPERIMENTAL |
| `mediation` | `linear_mediation_sobel` | continuous | mediation | analytical_asymptotic | R | `powermediation` | `powerMediation` | `powerMediation::ssMediation.Sobel` | VALIDATION_PENDING |
| `mixed_model` | `mixed_model_longitudinal_sim` | continuous_longitudinal | repeated_measures | simulation | R | `simr` | `simr` | `simr::powerSim` | EXPERIMENTAL |
| `multiple_endpoints` | `multiplicity_operating_characteristics` | multiple_endpoints | multiple_primary | operating_characteristics | R | `mediana` | `MedianaDesigner` | `MedianaDesigner::MultAdj` | EXPERIMENTAL |
| `must_win` | `coprimary_conjunctive_power` | multiple_endpoints | co_primary | analytical_asymptotic | R | `mkpower` | `MKpower` | `MKpower::power.mpe.known.var` | VALIDATION_PENDING |
| `ni_survival` | `cox_margin_design` | time_to_event | noninferiority | analytical_asymptotic | R | `trialsize` | `TrialSize` | `TrialSize::Cox.NIS` | VALIDATION_PENDING |
| `non_inferiority` | `binary_risk_difference_margin` | binary | fixed_parallel_noninferiority | analytical_exact | R | `trialsize` | `TrialSize` | `TrialSize::TwoSampleProportion.NIS` | VALIDATION_PENDING |
| `odds_ratio` | `binary_farrington_manning_or` | binary | fixed_parallel | analytical_asymptotic | R | `gsdesign` | `gsDesign` | `gsDesign::nBinomial` | VALIDATION_PENDING |
| `poisson` | `count_two_sample` | count | fixed_parallel | analytical_asymptotic | R | `rpact` | `rpact` | `rpact::getSampleSizeCounts` | VALIDATION_PENDING |
| `proportion_one` | `binary_one_sample` | binary | one_sample | analytical_asymptotic | R | `trialsize` | `TrialSize` | `TrialSize::OneSampleProportion.Equality` | VALIDATION_PENDING |
| `proportion_paired` | `binary_paired_mcnemar` | binary | paired | analytical_asymptotic | R | `trialsize` | `TrialSize` | `TrialSize::McNemar.Test` | VALIDATION_PENDING |
| `proportion_two` | `binary_two_sample_difference` | binary | fixed_parallel | analytical_asymptotic | R | `trialsize` | `TrialSize` | `TrialSize::TwoSampleProportion.Equality` | VALIDATION_PENDING |
| `recurrent_events` | `recurrent_event_design` | recurrent_count | fixed_parallel | analytical_asymptotic | R | `gsdesignnb` | `gsDesignNB` | `gsDesignNB::sample_size_nbinom` | EXPERIMENTAL |
| `risk_ratio` | `binary_farrington_manning_rr` | binary | fixed_parallel | analytical_asymptotic | R | `gsdesign` | `gsDesign` | `gsDesign::nBinomial` | VALIDATION_PENDING |
| `roc` | `roc_auc_design` | diagnostic | case_control | analytical_asymptotic | R | `proc` | `pROC` | `pROC::power.roc.test` | EXPERIMENTAL |
| `superiority_margin` | `binary_risk_difference_margin` | binary | fixed_parallel_superiority_margin | analytical_asymptotic | R | `trialsize` | `TrialSize` | `TrialSize::TwoSampleProportion.NIS` | VALIDATION_PENDING |
| `survival` | `survival_schoenfeld_fixed` | time_to_event | fixed_parallel | analytical_asymptotic | R | `powersurvepi` | `powerSurvEpi` | `powerSurvEpi::ssizeCT` | VALIDATION_PENDING |
| `survival_equivalence` | `cox_equivalence_tost` | time_to_event | equivalence | analytical_asymptotic | R | `trialsize` | `TrialSize` | `TrialSize::Cox.Equivalence` | VALIDATION_PENDING |
| `survival_exact` | `survival_rpact_accrual` | time_to_event | fixed_parallel_accrual | numerical | R | `rpact` | `rpact` | `rpact::getSampleSizeSurvival` | VALIDATION_PENDING |
| `survival_historical` | `historical_survival_sensitivity` | time_to_event | single_arm_external_control | simulation | PYTHON | `custom_sim` | — | specification-frozen custom engine | EXPERIMENTAL |
| `survival_one_sample` | `one_sample_exponential_survival` | time_to_event | one_sample | analytical_asymptotic | NONE | `analytical` | — | specification-frozen custom engine | EXPERIMENTAL |
| `survival_superiority` | `cox_margin_design` | time_to_event | superiority_margin | analytical_asymptotic | R | `trialsize` | `TrialSize` | `TrialSize::Cox.NIS` | VALIDATION_PENDING |
| `ttest_ind` | `mean_t_two_sample` | continuous | fixed_parallel | analytical_exact | R | `pwr_t` | `pwr` | `pwr::pwr.t.test` | VALIDATION_PENDING |
| `ttest_one` | `mean_t_one_sample` | continuous | one_sample | analytical_exact | R | `pwr_t` | `pwr` | `pwr::pwr.t.test` | VALIDATION_PENDING |
| `ttest_paired` | `mean_t_paired` | continuous | paired | analytical_exact | R | `pwr_t` | `pwr` | `pwr::pwr.t.test` | VALIDATION_PENDING |
| `vaccine_efficacy` | `vaccine_incidence_design` | binary_incidence | vaccine_parallel | analytical_asymptotic | R | `trialsize` | `TrialSize` | `TrialSize::Vaccine.RDI / TrialSize::Vaccine.ELDI` | EXPERIMENTAL |
| `win_ratio` | `win_ratio_design` | hierarchical_composite | fixed_parallel | analytical_asymptotic | R | `wrestimates` | `WRestimates` | `WRestimates::wr.ss` | EXPERIMENTAL |

## Shared method families

Only method IDs used by more than one routing key are listed here; all other method IDs still reuse an engine adapter even when their statistical method is distinct.

| method_id | user-facing keys | reason for sharing |
|---|---|---|
| `binary_risk_difference_margin` | `non_inferiority`, `superiority_margin` | The same TrialSize margin method is parameterized by hypothesis direction and signed boundary. |
| `cox_margin_design` | `ni_survival`, `survival_superiority` | The same Cox margin method supports NI or superiority after explicit log-HR orientation. |
| `gs_survival` | `gsd_hazard`, `gsd_survival` | Survival and hazard labels are semantic routes to one rpact group-sequential survival method. |
| `gs_survival_sim` | `gsd_hazard_sim`, `gsd_survival_sim` | Both labels route to the same rpact survival operating-characteristics simulation. |

## Multiple-endpoint method-ID decision

`multiple_endpoint_joint_power` has been retired because it conflated statistically different success criteria and multiplicity structures.

- `must_win` now uses `coprimary_conjunctive_power`: an intersection-union design in which every co-primary endpoint must succeed. For the currently specified continuous, known-covariance domain, it routes to `MKpower::power.mpe.known.var`.
- `multiple_endpoints` now uses `multiplicity_operating_characteristics`: simulation of a fully specified FWER-controlling procedure and endpoint model, currently routed to `MedianaDesigner::MultAdj`.
- Gatekeeping and graphical multiplicity are not silently treated as aliases of conjunctive or disjunctive power. They are procedure variants under `multiplicity_operating_characteristics` only when the complete hierarchy/graph, transition/recycling rules, endpoint model, and success criterion are supplied. If a future package adapter or validation record differs materially, they must receive separate method IDs.

Thus co-primary conjunctive power and general multiple-primary FWER-controlled operating characteristics are separate statistical methods. Gatekeeping and graphical procedures remain explicit, fail-closed variants of the latter—not one generic scalar-correlation method.

## Engine-family responsibilities

| engine family | keys | responsibility boundary |
|---|---|---|
| `analytical` | `bland_altman`, `cluster`, `survival_one_sample` | Run only a separately validated, specification-owned analytical method; no undocumented fallback. |
| `cmprsk` | `competing_risks` | Translate validated user inputs to pinned `cmprsk` formal arguments; normalize outputs without changing the hypothesis. |
| `custom_sim` | `adaptive_simulate`, `assurance`, `bayesian`, `survival_historical` | Run a specification-owned simulation with frozen data generation, analysis, RNG, Monte Carlo error, and search rules. |
| `escalation` | `dose_escalation` | Translate validated user inputs to pinned `escalation` formal arguments; normalize outputs without changing the hypothesis. |
| `gsdesign` | `odds_ratio`, `risk_ratio` | Translate validated user inputs to pinned `gsDesign` formal arguments; normalize outputs without changing the hypothesis. |
| `gsdesignnb` | `recurrent_events` | Translate validated user inputs to pinned `gsDesignNB` formal arguments; normalize outputs without changing the hypothesis. |
| `mediana` | `multiple_endpoints` | Translate validated user inputs to pinned `MedianaDesigner` formal arguments; normalize outputs without changing the hypothesis. |
| `mkpower` | `must_win` | Translate validated user inputs to pinned `MKpower` formal arguments; normalize outputs without changing the hypothesis. |
| `mvtnorm` | `dunnett` | Translate validated user inputs to pinned `mvtnorm` formal arguments; normalize outputs without changing the hypothesis. |
| `powermediation` | `mediation` | Translate validated user inputs to pinned `powerMediation` formal arguments; normalize outputs without changing the hypothesis. |
| `powersurvepi` | `cox_covariate`, `survival` | Translate validated user inputs to pinned `powerSurvEpi` formal arguments; normalize outputs without changing the hypothesis. |
| `powertost` | `be_tost` | Translate validated user inputs to pinned `PowerTOST` formal arguments; normalize outputs without changing the hypothesis. |
| `proc` | `roc` | Translate validated user inputs to pinned `pROC` formal arguments; normalize outputs without changing the hypothesis. |
| `pwr_anova` | `anova` | Translate validated user inputs to pinned `pwr` formal arguments; normalize outputs without changing the hypothesis. |
| `pwr_t` | `ttest_ind`, `ttest_one`, `ttest_paired` | Translate validated user inputs to pinned `pwr` formal arguments; normalize outputs without changing the hypothesis. |
| `rbest` | `historical_controls` | Translate validated user inputs to pinned `RBesT` formal arguments; normalize outputs without changing the hypothesis. |
| `rpact` | `adaptive`, `conditional_power`, `group_sequential`, `gsd_hazard`, `gsd_hazard_sim`, `gsd_poisson`, `gsd_proportion`, `gsd_survival`, `gsd_survival_sim`, `mams`, `poisson`, `survival_exact` | Translate validated user inputs to pinned `rpact` formal arguments; normalize outputs without changing the hypothesis. |
| `simr` | `mixed_model` | Translate validated user inputs to pinned `simr` formal arguments; normalize outputs without changing the hypothesis. |
| `trialsize` | `equivalence`, `ni_survival`, `non_inferiority`, `proportion_one`, `proportion_paired`, `proportion_two`, `superiority_margin`, `survival_equivalence`, `survival_superiority`, `vaccine_efficacy` | Translate validated user inputs to pinned `TrialSize` formal arguments; normalize outputs without changing the hypothesis. |
| `wrestimates` | `win_ratio` | Translate validated user inputs to pinned `WRestimates` formal arguments; normalize outputs without changing the hypothesis. |

## Fail-closed routing rules

1. The router must load the exact YAML named by `test_key`; unknown keys fail.
2. Required design-identifying inputs are not inferred. Missing endpoint distributions, covariance, event process, decision rule, interim rule, or historical-data model fail with an explicit unsupported/underidentified error.
3. Package adapters accept only parameter mappings declared in the YAML. They do not substitute a different package function or historical fallback.
4. `REPLACE` and `REDESIGN` keys use the intended production method in their specification. Their historical algorithm is prohibited by the `DO_NOT_REPRODUCE_HISTORICAL_BEHAVIOR` warning.
5. A package name or successful package call is not validation. Version pinning and all benchmark gates remain mandatory.
6. Analytical and simulation engines may be shared as infrastructure, but each `method_id` retains its own hypothesis, supported domain, benchmarks, and validation record.

## Package/function provenance policy

Function names and structured formal arguments in the YAML were checked against official package documentation. The `formal_arguments` records capture the package interface relevant to the adapter; `parameter_mapping` separately records how clinical inputs are derived or transformed. Where no verified function exactly represents the frozen method, package/function are null and the method remains experimental rather than inventing an API.

Verification sources include official CRAN help pages and package-owned documentation for `pwr`, `TrialSize`, `PowerTOST`, `rpact`, `simr`, `gsDesign`, `gsDesignNB`, `powerSurvEpi`, `cmprsk`, `pROC`, `mvtnorm`, `WRestimates`, `MKpower`, `MedianaDesigner`, `powerMediation`, `escalation`, and `RBesT`. Exact versions are intentionally not frozen here: the validation lockfile will select a version, record session information, and trigger revalidation on change.
