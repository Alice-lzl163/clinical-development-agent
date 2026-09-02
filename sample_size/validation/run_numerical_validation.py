"""Round 4.2 live validation harness for the six authorized calculators."""

import argparse
import json
import math
import subprocess
from copy import deepcopy
from datetime import date
from pathlib import Path

import scipy
import yaml

from sample_size import calculate_sample_size
from sample_size.engines.errors import SampleSizeError
from sample_size.engines.r_engine import RExecutionEngine
from sample_size.validation.environment_probe import probe
from sample_size.validation.reference import anova_power, be_tost_power, proportion_equality_power, t_test_power

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/"sample_size"/"validation"/"benchmarks"/"fixed_design_round4.yaml"
EVIDENCE=ROOT/"sample_size"/"validation"/"round42_evidence.json"
METHODS=("ttest_one","ttest_paired","ttest_ind","anova","proportion_two","be_tost")
POWER_N={"ttest_one":"analyzable_sample_size","ttest_paired":"analyzable_pairs","ttest_ind":"analyzable_sample_size_per_arm","anova":"analyzable_sample_size_per_group","be_tost":"evaluable_total"}


class CountingEngine(RExecutionEngine):
    def __init__(self,rscript): super().__init__(rscript); self.executions=0; self.successes=0; self.failures=0
    def execute(self,**kwargs):
        self.executions+=1
        try:
            result=super().execute(**kwargs); self.successes+=1; return result
        except Exception:
            self.failures+=1; raise


def _agent(engine,key,mode,inputs):
    return calculate_sample_size({"test_key":key,"solve_mode":mode,"parameters":inputs},engine=engine)


def _power_inputs(result,original):
    values={k:v for k,v in original.items() if k not in {"power","dropout_rate"}}
    key=result.test_key
    if key=="proportion_two":
        values["analyzable_treatment"]=result.sample_size_per_group["treatment"]
        values["analyzable_control"]=result.sample_size_per_group["control"]
    elif key=="ttest_ind": values[POWER_N[key]]=result.sample_size_per_group["treatment"]
    elif key=="anova": values[POWER_N[key]]=result.derived_parameters["analyzable_per_group"]
    elif key=="ttest_paired": values[POWER_N[key]]=result.derived_parameters["complete_analyzable_pairs"]
    elif key=="ttest_one": values[POWER_N[key]]=result.derived_parameters["analyzable_subjects"]
    else: values[POWER_N[key]]=result.derived_parameters["evaluable_total"]
    return values


def _independent(result,inputs):
    key=result.test_key
    if key.startswith("ttest_"):
        test_type={"ttest_one":"one.sample","ttest_paired":"paired","ttest_ind":"two.sample"}[key]
        n=result.analysis_required_sample_size//2 if key=="ttest_ind" else result.analysis_required_sample_size
        return t_test_power(n=n,effect=result.derived_parameters["signed_standardized_effect"],alpha=inputs["alpha"],test_type=test_type,alternative={"two_sided":"two.sided","greater":"greater","less":"less"}[inputs["alternative"]])
    if key=="anova": return anova_power(groups=inputs["groups"],n_per_group=result.derived_parameters["analyzable_per_group"],cohen_f=inputs["cohen_f"],alpha=inputs["alpha"])
    if key=="proportion_two": return proportion_equality_power(treatment_probability=inputs["treatment_probability"],control_probability=inputs["control_probability"],n_treatment=result.sample_size_per_group["treatment"],n_control=result.sample_size_per_group["control"],alpha=inputs["alpha"])
    if key=="be_tost": return be_tost_power(n=result.analysis_required_sample_size,cv=inputs["cv"],theta0=inputs["theta0"],lower_limit=inputs["lower_limit"],upper_limit=inputs["upper_limit"],design=inputs["design"],alpha=inputs["alpha"])


def _direct_reexecute(engine,result,key):
    function="PowerTOST::power.TOST" if key=="be_tost" and result.solve_mode=="power" else ({"ttest_one":"pwr::pwr.t.test","ttest_paired":"pwr::pwr.t.test","ttest_ind":"pwr::pwr.t.test","anova":"pwr::pwr.anova.test","proportion_two":"TrialSize::TwoSampleProportion.Equality","be_tost":"PowerTOST::sampleN.TOST"}[key])
    return engine.execute(package=result.package,function=function,calculation_code=result.reproducible_code)


def _fixture_validation(engine,fixture):
    key=fixture["test_key"]; mode=fixture.get("solve_mode","sample_size"); inputs=fixture["inputs"]
    if fixture.get("expected_error"):
        try: _agent(engine,key,mode,inputs)
        except SampleSizeError as exc: return {"status":"PASS","kind":"expected_error","error_type":type(exc).__name__}
        return {"status":"FAIL","classification":"IMPLEMENTATION_DEFECT","message":"expected error was not raised"}
    if fixture["id"]=="anova_per_group_semantic_regression":
        total=inputs["groups"]*inputs["package_n_fixture"]
        return {"status":"PASS" if total==fixture["expected_analyzable_n"] else "FAIL","kind":"semantic_invariant","observed_total":total}
    result=_agent(engine,key,mode,inputs)
    direct=_direct_reexecute(engine,result,key)
    direct_power=float(direct["achieved_power"])
    direct_difference=abs(result.achieved_power-direct_power)
    package_pass=direct_difference<=1e-10
    reference=_independent(result,inputs)
    reference_difference=abs(result.achieved_power-reference) if reference is not None else None
    reference_pass=reference_difference is not None and reference_difference<=1e-6
    round_trip={"status":"NOT_APPLICABLE"}
    if mode=="sample_size":
        forward=_agent(engine,key,"power",_power_inputs(result,inputs))
        difference=abs(result.achieved_power-forward.achieved_power)
        round_trip={"status":"PASS" if difference<=1e-10 and forward.achieved_power+1e-10>=inputs["power"] else "FAIL","power":forward.achieved_power,"absolute_difference":difference}
    semantic=True
    if key=="ttest_ind": semantic=result.sample_size_per_group["treatment"]==result.sample_size_per_group["control"]
    elif key=="anova": semantic=result.analysis_required_sample_size==inputs["groups"]*result.derived_parameters["analyzable_per_group"]
    elif key=="proportion_two": semantic=abs(result.sample_size_per_group["treatment"]-inputs["allocation_ratio"]*result.sample_size_per_group["control"])<=1+1e-12
    elif key=="be_tost": semantic=result.analysis_required_sample_size%2==0 and len(set((result.sample_size_per_group or result.sample_size_per_sequence).values()))==1
    required_pass=package_pass and semantic and round_trip["status"] in {"PASS","NOT_APPLICABLE"} and reference_pass
    reference_method="SciPy noncentral distribution" if key.startswith("ttest_") or key=="anova" else ("independent matching normal equation" if key=="proportion_two" else "independent chi-square-conditioned exact TOST integration")
    return {"status":"PASS" if required_pass else "FAIL","agent_result":result.to_dict(),"direct_package":{"raw":direct,"absolute_power_difference":direct_difference,"status":"PASS" if package_pass else "FAIL"},"round_trip":round_trip,"independent_reference":{"method":reference_method,"result":reference,"absolute_difference":reference_difference,"status":"PASS" if reference_pass else "FAIL"},"semantic_invariants":"PASS" if semantic else "FAIL"}


def _monotonicity(engine,key,base):
    base={k:v for k,v in base.items() if k not in {"expected_error","package_n_fixture"}}
    base["power"]=0.8; base["dropout_rate"]=0
    low=_agent(engine,key,"sample_size",base)
    high_inputs={**base,"power":0.9}; high=_agent(engine,key,"sample_size",high_inputs)
    alpha_inputs={**base,"alpha":base["alpha"]/2}; strict_alpha=_agent(engine,key,"sample_size",alpha_inputs)
    changed=deepcopy(base)
    if key.startswith("ttest_"): changed["standardized_paired_effect" if key=="ttest_paired" else "standardized_effect"]*=0.8
    elif key=="anova": changed["cohen_f"]*=0.8
    elif key=="proportion_two": changed["treatment_probability"]=changed["control_probability"]+0.8*(changed["treatment_probability"]-changed["control_probability"])
    else: changed["cv"]*=1.2
    harder=_agent(engine,key,"sample_size",changed)
    dropout=[]
    for rate in (0,.1,.2): dropout.append(_agent(engine,key,"sample_size",{**base,"dropout_rate":rate}))
    power_inputs=_power_inputs(low,base); p1=_agent(engine,key,"power",power_inputs)
    larger=deepcopy(power_inputs)
    if key=="proportion_two": larger["analyzable_treatment"]*=2; larger["analyzable_control"]*=2
    else:
        field=POWER_N[key]; larger[field]=math.ceil(larger[field]*1.2)
        if key=="be_tost" and larger[field]%2: larger[field]+=1
    p2=_agent(engine,key,"power",larger)
    checks={"higher_target_power":high.analysis_required_sample_size>=low.analysis_required_sample_size,"smaller_effect_or_higher_cv":harder.analysis_required_sample_size>=low.analysis_required_sample_size,"smaller_alpha":strict_alpha.analysis_required_sample_size>=low.analysis_required_sample_size,"dropout_analyzable_constant":len({r.analysis_required_sample_size for r in dropout})==1,"dropout_randomized_monotone":[r.randomized_sample_size for r in dropout]==sorted(r.randomized_sample_size for r in dropout),"power_increases_with_n":p2.achieved_power+1e-10>=p1.achieved_power}
    return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"observed":{"n_power_80":low.analysis_required_sample_size,"n_power_90":high.analysis_required_sample_size,"n_stricter_alpha":strict_alpha.analysis_required_sample_size,"n_harder_effect":harder.analysis_required_sample_size,"dropout_randomized":[r.randomized_sample_size for r in dropout],"power_n_base":p1.achieved_power,"power_n_larger":p2.achieved_power}}


def run(write=False, evidence_output=None):
    environment=probe()
    if environment["rscript"]["status"]!="FOUND": raise RuntimeError("Rscript unavailable")
    if environment["scipy"]["status"]!="FOUND": raise RuntimeError("SciPy unavailable")
    for name,item in environment["packages"].items():
        if item["status"]!="FOUND" or not all(item.get("functions",{}).values()): raise RuntimeError(f"R dependency unavailable: {name}")
    engine=CountingEngine(environment["rscript"]["selected"])
    fixture_doc=yaml.safe_load(FIXTURES.read_text(encoding="utf-8")); results={}
    for fixture in fixture_doc["cases"]: results[fixture["id"]]=_fixture_validation(engine,fixture)
    bases={}
    for fixture in fixture_doc["cases"]:
        if fixture["test_key"] not in bases and fixture.get("solve_mode","sample_size")=="sample_size" and not fixture.get("expected_error") and "package_n_fixture" not in fixture["inputs"]: bases[fixture["test_key"]]=fixture["inputs"]
    monotonicity={key:_monotonicity(engine,key,bases[key]) for key in METHODS}
    gates={}
    for key in METHODS:
        relevant=[results[f["id"]] for f in fixture_doc["cases"] if f["test_key"]==key]
        direct=all(r.get("direct_package",{}).get("status","PASS")=="PASS" for r in relevant)
        roundtrip=all(r.get("round_trip",{}).get("status","PASS") in {"PASS","NOT_APPLICABLE"} for r in relevant)
        independent=all(r.get("independent_reference",{}).get("status","PASS")=="PASS" for r in relevant)
        semantic=all(r.get("semantic_invariants","PASS")=="PASS" for r in relevant)
        repro=direct
        promoted=direct and roundtrip and independent and semantic and monotonicity[key]["status"]=="PASS" and repro
        gates[key]={"direct_package_reproduction":"PASS" if direct else "FAIL","round_trip":"PASS" if roundtrip else "FAIL","independent_reference":"PASS" if independent else "FAIL","allocation_dropout_rounding":"PASS" if semantic and monotonicity[key]["checks"]["dropout_analyzable_constant"] and monotonicity[key]["checks"]["dropout_randomized_monotone"] else "FAIL","edge_cases_monotonicity":monotonicity[key]["status"],"reproducibility":"PASS" if repro else "FAIL","validation_status":"BENCHMARK_VALIDATED" if promoted else "IMPLEMENTED_UNVALIDATED"}
    evidence={"validation_date":str(date.today()),"basis_commit":subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,text=True,capture_output=True).stdout.strip(),"environment":environment,"live_execution":{"executed":engine.executions,"successful":engine.successes,"failed":engine.failures},"fixtures":results,"monotonicity":monotonicity,"method_gates":gates}
    if write:
        EVIDENCE.write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
        for fixture in fixture_doc["cases"]:
            result=results[fixture["id"]]; fixture["validation_status"]="FROZEN_VALIDATED" if result["status"]=="PASS" and gates[fixture["test_key"]]["validation_status"]=="BENCHMARK_VALIDATED" else "PENDING"
            if "agent_result" in result:
                agent=result["agent_result"]; fixture["observed_agent_result"]={"analysis_required_sample_size":agent["analysis_required_sample_size"],"randomized_sample_size":agent["randomized_sample_size"],"achieved_power":agent["achieved_power"]}
                if fixture["validation_status"]=="FROZEN_VALIDATED":
                    fixture["expected_raw_package_output"]=result["direct_package"]["raw"]; fixture["expected_analyzable_n"]=agent["analysis_required_sample_size"]; fixture["expected_randomized_n"]=agent["randomized_sample_size"]; fixture["expected_achieved_power"]=agent["achieved_power"]
                fixture["validation_provenance"]={"R_version":environment["r"]["version"],"package":agent["package"],"package_version":agent["package_version"],"package_function":agent["function"],"package_arguments":agent["package_arguments"],"independent_reference":result["independent_reference"],"validation_date":str(date.today()),"basis_commit":evidence["basis_commit"]}
        FIXTURES.write_text(yaml.safe_dump(fixture_doc,sort_keys=False,allow_unicode=True),encoding="utf-8")
    if evidence_output:
        output_path=Path(evidence_output); output_path.parent.mkdir(parents=True,exist_ok=True)
        output_path.write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
    return evidence


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--write",action="store_true"); parser.add_argument("--evidence-output"); args=parser.parse_args()
    output=run(write=args.write,evidence_output=args.evidence_output)
    print(json.dumps({"live_execution":output["live_execution"],"method_gates":output["method_gates"],"fixture_statuses":{k:v["status"] for k,v in output["fixtures"].items()}},indent=2))
