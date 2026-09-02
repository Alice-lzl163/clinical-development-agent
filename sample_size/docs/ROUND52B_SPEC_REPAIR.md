# Round 5.2B Narrow Specification Repair

Implementation exposed one inconsistency in the frozen OR/RR power contracts. `allocation_ratio` was marked required in power mode even though power mode is defined by supplied analyzable treatment and control counts and passes their realized `n_control/n_treatment` ratio to gsDesign. Requiring a planned ratio would be redundant and could conflict with the realized allocation.

The `odds_ratio` and `risk_ratio` specifications now permit `allocation_ratio` only in sample-size mode. Power mode requires `analyzable_treatment` and `analyzable_control`, derives total analyzable N and the realized package ratio, and rejects a supplied planned allocation ratio as an unsupported field for that solve mode. No statistical method, effect orientation, hypothesis, package scale, or formula changed.
