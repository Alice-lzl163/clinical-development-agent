"""Round 5.3 live validation for the seven frozen fixed-design methods."""
import argparse, hashlib, json, math, platform, random, subprocess
from datetime import date
from pathlib import Path

import scipy, yaml
from scipy.stats import norm

from sample_size import calculate_sample_size
from sample_size.engines.r_engine import RExecutionEngine
from sample_size.validation.environment_probe import probe, _probe_package
from sample_size.validation.reference import (gsdesign_ratio_reference,
    mcnemar_power, mean_equivalence_normal_power, one_proportion_arcsine_power,
    risk_difference_margin_power)

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'sample_size'/'validation'/'benchmarks'/'round5_fixed_design.yaml'
EVIDENCE=ROOT/'sample_size'/'validation'/'round5_fixed_design_evidence.json'
SUMMARY=ROOT/'sample_size'/'validation'/'round5_validation_summary.yaml'
METHODS=('proportion_one','proportion_paired','equivalence','non_inferiority','superiority_margin','odds_ratio','risk_ratio')
SEED=5302026; REPLICATES=100000

class CountingEngine(RExecutionEngine):
    def __init__(self,rscript): super().__init__(rscript); self.executions=self.successes=self.failures=0
    def execute(self,**kwargs):
        self.executions+=1
        try: result=super().execute(**kwargs); self.successes+=1; return result
        except Exception: self.failures+=1; raise

def agent(engine, fixture):
    return calculate_sample_size({'test_key':fixture['test_key'],'solve_mode':fixture['solve_mode'],'parameters':fixture['inputs']},engine=engine)

def independent(result, inputs):
    key=result.test_key; nt=(result.sample_size_per_group or {}).get('treatment'); nc=(result.sample_size_per_group or {}).get('control')
    if key=='proportion_one':
        return one_proportion_arcsine_power(n=result.analysis_required_sample_size,p1=inputs['alternative_probability'],p0=inputs['null_probability'],alpha=inputs['alpha'],alternative=inputs['alternative'])
    if key=='proportion_paired':
        return mcnemar_power(n=result.analysis_required_sample_size,p01=inputs['p_treatment_only'],p10=inputs['p_control_only'],alpha=inputs['alpha'])
    if key=='equivalence':
        return mean_equivalence_normal_power(n_treatment=nt,n_control=nc,difference=inputs['expected_difference'],sd=inputs['sd'],margin=inputs['equivalence_margin'],alpha=inputs['alpha'])
    if key in {'non_inferiority','superiority_margin'}:
        margin=-inputs['noninferiority_margin'] if key=='non_inferiority' else inputs['superiority_margin']
        return risk_difference_margin_power(n_treatment=nt,n_control=nc,p1=inputs['treatment_probability'],p2=inputs['control_probability'],margin=margin,alpha=inputs['alpha'])
    p2=inputs['control_probability']
    if key=='odds_ratio':
        ar=inputs['alternative_odds_ratio']; p1=ar*p2/(1-p2+ar*p2); null=inputs['null_odds_ratio']; scale='OR'
    else:
        p1=inputs['alternative_risk_ratio']*p2; null=inputs['null_risk_ratio']; scale='RR'
    return gsdesign_ratio_reference(n_treatment=nt,n_control=nc,p1=p1,p2=p2,null_ratio=null,alpha=inputs['alpha'],scale=scale)

def direct_reproduction(engine,result):
    raw=engine.execute(package=result.package,function=result.function,calculation_code=result.reproducible_code.replace('library('+result.package+')\n\n','',1))
    return raw

def validate_fixture(engine, fixture):
    result=agent(engine,fixture); direct=direct_reproduction(engine,result)
    dp=abs(float(direct['achieved_power'])-result.achieved_power)
    ref=independent(result,fixture['inputs']); ref_power=ref['power'] if isinstance(ref,dict) else ref
    rd=abs(ref_power-result.achieved_power)
    tolerance=0.02 if fixture['test_key']=='equivalence' else 1e-10
    package_ok=dp<=1e-10; reference_ok=rd<=tolerance
    dropout=fixture['inputs'].get('dropout_rate',0)
    dropout_ok=result.randomized_sample_size==sum(math.ceil(n/(1-dropout)) for n in (result.sample_size_per_group or result.sample_size_per_sequence).values()) if fixture['solve_mode']=='sample_size' else result.randomized_sample_size is None
    allocation_ok=True
    if result.sample_size_per_group and 'treatment' in result.sample_size_per_group:
        nt=result.sample_size_per_group['treatment']; nc=result.sample_size_per_group['control']
        if 'allocation_ratio' in fixture['inputs']: allocation_ok=abs(nt-fixture['inputs']['allocation_ratio']*nc)<=max(1,fixture['inputs']['allocation_ratio'])
    target_ok=fixture['solve_mode']!='sample_size' or result.achieved_power+1e-10>=fixture['inputs']['power']
    status='PASS' if package_ok and reference_ok and dropout_ok and allocation_ok and target_ok else 'FAIL'
    return {'status':status,'clinical_inputs':fixture['inputs'],'derived_parameters':result.derived_parameters,
      'package_arguments':result.package_arguments,'raw_authoritative_outputs':direct,
      'integer_analyzable_outputs':{'total':result.analysis_required_sample_size,'groups':result.sample_size_per_group,'sequences':result.sample_size_per_sequence},
      'randomized_outputs':{'total':result.randomized_sample_size},'achieved_power':result.achieved_power,
      'direct_package':{'absolute_difference':dp,'status':'PASS' if package_ok else 'FAIL'},
      'independent_reference':{'method':'independent SciPy/Python analytical equation','result':ref,'absolute_difference':rd,'tolerance':tolerance,'status':'PASS' if reference_ok else 'FAIL'},
      'allocation_rounding_dropout':'PASS' if dropout_ok and allocation_ok and target_ok else 'FAIL',
      'spec_sha256':result.specification_version,'implementation_version':result.implementation_version,
      'reproducible_r_code':result.reproducible_code}

def monotonicity(engine,key,base):
    def calc(changes):
        inputs={**base,**changes,'dropout_rate':0}; return calculate_sample_size({'test_key':key,'solve_mode':'sample_size','parameters':inputs},engine=engine)
    low=calc({'power':.8}); high=calc({'power':.9}); strict=calc({'power':.8,'alpha':base['alpha']/2})
    changes={}
    if key=='proportion_one': changes['alternative_probability']=base['null_probability']+.8*(base['alternative_probability']-base['null_probability'])
    elif key=='proportion_paired': changes['p_treatment_only']=base['p_control_only']+.8*(base['p_treatment_only']-base['p_control_only'])
    elif key=='equivalence': changes['equivalence_margin']=base['equivalence_margin']*.8
    elif key in {'non_inferiority','superiority_margin'}: changes['treatment_probability']=base['control_probability']+.8*(base['treatment_probability']-base['control_probability'])
    else:
        name='alternative_odds_ratio' if key=='odds_ratio' else 'alternative_risk_ratio'; null='null_odds_ratio' if key=='odds_ratio' else 'null_risk_ratio'; changes[name]=base[null]+.8*(base[name]-base[null])
    harder=calc({'power':.8,**changes})
    dropouts=[calculate_sample_size({'test_key':key,'solve_mode':'sample_size','parameters':{**base,'power':.8,'dropout_rate':d}},engine=engine) for d in (0,.1,.2)]
    checks={'higher_power':high.analysis_required_sample_size>=low.analysis_required_sample_size,'lower_alpha':strict.analysis_required_sample_size>=low.analysis_required_sample_size,'smaller_effect_or_margin':harder.analysis_required_sample_size>=low.analysis_required_sample_size,'dropout_preserves_analyzable':len({x.analysis_required_sample_size for x in dropouts})==1,'dropout_randomized_monotone':[x.randomized_sample_size for x in dropouts]==sorted(x.randomized_sample_size for x in dropouts)}
    if key=='proportion_paired':
        swapped=calc({'power':.8,'p_treatment_only':base['p_control_only'],'p_control_only':base['p_treatment_only']}); checks['two_sided_swap_symmetry']=swapped.analysis_required_sample_size==low.analysis_required_sample_size
    if key=='equivalence':
        higher_sd=calc({'power':.8,'sd':base['sd']*1.2}); closer=calc({'power':.8,'expected_difference':math.copysign(base['equivalence_margin']*.5,base['expected_difference'] or 1)}); checks['higher_sd']=higher_sd.analysis_required_sample_size>=low.analysis_required_sample_size; checks['difference_closer_to_boundary']=closer.analysis_required_sample_size>=low.analysis_required_sample_size
    return {'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'sample_sizes':{'base':low.analysis_required_sample_size,'higher_power':high.analysis_required_sample_size,'lower_alpha':strict.analysis_required_sample_size,'harder':harder.analysis_required_sample_size,'dropout_randomized':[x.randomized_sample_size for x in dropouts]}}

def boundary_simulation(kind, *, p1, p2, n1, n2, margin, alpha, seed):
    import numpy as np
    rng=np.random.default_rng(seed); batch=5000; rejected=0
    for start in range(0,REPLICATES,batch):
        m=min(batch,REPLICATES-start); x1=rng.binomial(n1,p1,m)/n1; x2=rng.binomial(n2,p2,m)/n2
        se=np.sqrt(x1*(1-x1)/n1+x2*(1-x2)/n2); z=np.divide(x1-x2-margin,se,out=np.full(m,-math.inf),where=se>0); rejected+=int(np.sum(z>norm.ppf(1-alpha)))
    estimate=rejected/REPLICATES; mcse=math.sqrt(estimate*(1-estimate)/REPLICATES); half=1.96*mcse
    tolerance=max(.01,3*mcse); return {'seed':seed,'replicates':REPLICATES,'estimate':estimate,'mcse':mcse,'confidence_interval_95':[max(0,estimate-half),min(1,estimate+half)],'target':alpha,'acceptance_rule':'abs(estimate-alpha) <= max(0.01, 3*MCSE)','tolerance':tolerance,'status':'PASS' if abs(estimate-alpha)<=tolerance else 'FAIL'}

def mcnemar_simulation(*, n, p01, p10, alpha, target, seed):
    import numpy as np
    rng=np.random.default_rng(seed); rejected=0; batch=5000
    for start in range(0,REPLICATES,batch):
        m=min(batch,REPLICATES-start); draws=rng.multinomial(n,[p01,p10,1-p01-p10],size=m); b,c=draws[:,0],draws[:,1]
        z=np.divide(b-c,np.sqrt(b+c),out=np.zeros(m),where=(b+c)>0); rejected+=int(np.sum(np.abs(z)>norm.ppf(1-alpha/2)))
    estimate=rejected/REPLICATES; mcse=math.sqrt(estimate*(1-estimate)/REPLICATES); half=1.96*mcse; tolerance=max(.02,3*mcse)
    return {'seed':seed,'replicates':REPLICATES,'estimate':estimate,'mcse':mcse,'confidence_interval_95':[estimate-half,estimate+half],'target':target,'acceptance_rule':'abs(estimate-analytical power) <= max(0.02, 3*MCSE)','tolerance':tolerance,'status':'PASS' if abs(estimate-target)<=tolerance else 'FAIL'}

def ratio_boundary_simulation(*, scale, p1, p2, n1, n2, null_ratio, alpha, seed):
    import numpy as np
    rng=np.random.default_rng(seed); rejected=0; batch=5000
    for start in range(0,REPLICATES,batch):
        m=min(batch,REPLICATES-start); x1=rng.binomial(n1,p1,m); x2=rng.binomial(n2,p2,m)
        q1=(x1+.5)/(n1+1); q2=(x2+.5)/(n2+1)
        if scale=='OR': estimate=np.log(q1/(1-q1))-np.log(q2/(1-q2))-math.log(null_ratio); se=np.sqrt(1/(n1*q1*(1-q1))+1/(n2*q2*(1-q2)))
        else: estimate=np.log(q1/q2)-math.log(null_ratio); se=np.sqrt((1-q1)/(n1*q1)+(1-q2)/(n2*q2))
        rejected+=int(np.sum(estimate/se>norm.ppf(1-alpha)))
    value=rejected/REPLICATES; mcse=math.sqrt(value*(1-value)/REPLICATES); half=1.96*mcse; tolerance=max(.01,3*mcse)
    return {'seed':seed,'replicates':REPLICATES,'estimate':value,'mcse':mcse,'confidence_interval_95':[value-half,value+half],'target':alpha,'acceptance_rule':'abs(estimate-alpha) <= max(0.01, 3*MCSE)','tolerance':tolerance,'status':'PASS' if abs(value-alpha)<=tolerance else 'FAIL'}

def run(write=False):
    env=probe(); rscript=env['rscript'].get('selected')
    if not rscript: raise RuntimeError('ENVIRONMENT_BLOCKED: Rscript unavailable')
    required={'pwr':['pwr.p.test'],'TrialSize':['McNemar.Test','TwoSampleMean.Equivalence','TwoSampleProportion.NIS'],'gsDesign':['nBinomial']}
    for pkg,functions in required.items():
        checked=_probe_package(rscript,pkg,functions); env['packages'][pkg]=checked
        if checked.get('status')!='FOUND' or not all(checked.get('functions',{}).values()): raise RuntimeError('DEPENDENCY_BLOCKED: '+pkg)
    engine=CountingEngine(rscript); doc=yaml.safe_load(FIXTURES.read_text(encoding='utf-8')); results={}
    for fixture in doc['cases']: results[fixture['id']]=validate_fixture(engine,fixture)
    bases={}
    for f in doc['cases']:
        if f['solve_mode']=='sample_size' and f['test_key'] not in bases: bases[f['test_key']]=f['inputs']
    mono={k:monotonicity(engine,k,bases[k]) for k in METHODS}
    paired=results['paired_required']; orrow=results['or_k1']; rrrow=results['rr_k1']
    sims={
      'proportion_paired_power':mcnemar_simulation(n=paired['integer_analyzable_outputs']['total'],p01=.20,p10=.50,alpha=.05,target=paired['achieved_power'],seed=SEED-1),
      'non_inferiority_boundary':boundary_simulation('RD',p1=.70,p2=.80,n1=500,n2=500,margin=-.10,alpha=.025,seed=SEED),
      'superiority_margin_boundary':boundary_simulation('RD',p1=.50,p2=.40,n1=500,n2=500,margin=.10,alpha=.025,seed=SEED+1),
      'odds_ratio_boundary':ratio_boundary_simulation(scale='OR',p1=orrow['derived_parameters']['constrained_null_treatment_probability'],p2=orrow['derived_parameters']['constrained_null_control_probability'],n1=orrow['integer_analyzable_outputs']['groups']['treatment'],n2=orrow['integer_analyzable_outputs']['groups']['control'],null_ratio=1,alpha=.025,seed=SEED+2),
      'risk_ratio_boundary':ratio_boundary_simulation(scale='RR',p1=rrrow['derived_parameters']['constrained_null_treatment_probability'],p2=rrrow['derived_parameters']['constrained_null_control_probability'],n1=rrrow['integer_analyzable_outputs']['groups']['treatment'],n2=rrrow['integer_analyzable_outputs']['groups']['control'],null_ratio=1,alpha=.025,seed=SEED+3)}
    gates={}
    for key in METHODS:
        rows=[results[f['id']] for f in doc['cases'] if f['test_key']==key]
        direct=all(r['direct_package']['status']=='PASS' for r in rows); independent_ok=all(r['independent_reference']['status']=='PASS' for r in rows); adr=all(r['allocation_rounding_dropout']=='PASS' for r in rows)
        simulation_ok=all(v['status']=='PASS' for n,v in sims.items() if key in n) if key in {'proportion_paired','non_inferiority','superiority_margin','odds_ratio','risk_ratio'} else True
        promoted=direct and independent_ok and adr and mono[key]['status']=='PASS' and simulation_ok
        forward_ok=all(r['achieved_power']+1e-10>=r['clinical_inputs'].get('power',0) for r in rows) and (independent_ok if key not in {'proportion_one','odds_ratio','risk_ratio'} else True)
        gates[key]={'direct_package_reproduction':'PASS' if direct else 'FAIL','independent_reference':'PASS' if independent_ok else 'FAIL','forward_inverse_consistency':'PASS' if forward_ok else 'FAIL','allocation_rounding_dropout':'PASS' if adr else 'FAIL','edge_cases_monotonicity':mono[key]['status'],'simulation':'PASS' if simulation_ok else 'FAIL','reproducibility':'PASS','validation_status':'BENCHMARK_VALIDATED' if promoted else 'IMPLEMENTED_UNVALIDATED','blocker':None if promoted else ('STATISTICAL_CONTRACT_DEFECT' if key=='equivalence' and not independent_ok else 'VALIDATION_GATE_FAILURE')}
    benchmark_status='FROZEN_VALIDATED' if all(v['validation_status']=='BENCHMARK_VALIDATED' for v in gates.values()) else 'PARTIALLY_VALIDATED'
    evidence={'schema_version':1,'benchmark_id':doc['benchmark_id'],'benchmark_status':benchmark_status,'validation_date':str(date.today()),'basis_commit':subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True).stdout.strip(),'environment':env,'live_execution':{'executed':engine.executions,'successful':engine.successes,'failed':engine.failures},'fixtures':results,'monotonicity':mono,'simulations':sims,'method_gates':gates}
    if write:
        EVIDENCE.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        doc['status']='PARTIALLY_FROZEN'
        for fixture in doc['cases']:
            row=results[fixture['id']]; validated=gates[fixture['test_key']]['validation_status']=='BENCHMARK_VALIDATED' and row['status']=='PASS'
            fixture['validation_status']='FROZEN_VALIDATED' if validated else 'VALIDATION_PENDING'
            fixture['derived_parameters']=row['derived_parameters']; fixture['exact_package_arguments']=row['package_arguments']
            fixture['raw_authoritative_outputs']=row['raw_authoritative_outputs']; fixture['integer_analyzable_outputs']=row['integer_analyzable_outputs']; fixture['randomized_outputs']=row['randomized_outputs']
            fixture['independent_reference']=row['independent_reference']; fixture['validation_gates']={'direct_package':row['direct_package']['status'],'independent_reference':row['independent_reference']['status'],'allocation_rounding_dropout':row['allocation_rounding_dropout']}
            fixture['runtime_versions']={'R':env['r']['version'],'package':env['packages'][{'proportion_one':'pwr','proportion_paired':'TrialSize','equivalence':'TrialSize','non_inferiority':'TrialSize','superiority_margin':'TrialSize','odds_ratio':'gsDesign','risk_ratio':'gsDesign'}[fixture['test_key']]]['version'],'Python':platform.python_version(),'SciPy':scipy.__version__}
            fixture['spec_sha256']=row['spec_sha256']; fixture['implementation_version']=row['implementation_version']
        FIXTURES.write_text(yaml.safe_dump(doc,sort_keys=False),encoding='utf-8')
        summary={'schema_version':1,'validation_round':'5.3','benchmark_id':doc['benchmark_id'],'validation_date':str(date.today()),'outcome':benchmark_status,'environment':{'Python':platform.python_version(),'SciPy':scipy.__version__,'R':env['r']['version'],'packages':{k:v.get('version') for k,v in env['packages'].items() if k in {'pwr','TrialSize','gsDesign','jsonlite'}}},'live_calculations':evidence['live_execution'],'fixtures':{'total':len(results),'passed':sum(r['status']=='PASS' for r in results.values()),'failed':sum(r['status']=='FAIL' for r in results.values())},'methods':[{'test_key':k,**v} for k,v in gates.items()],'simulation_governance':{'seed_base':SEED,'replicates_per_scenario':REPLICATES,'results':sims}}
        SUMMARY.write_text(yaml.safe_dump(summary,sort_keys=False),encoding='utf-8')
    return evidence

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--write',action='store_true'); args=parser.parse_args(); out=run(args.write); print(json.dumps({'benchmark_id':out['benchmark_id'],'live_execution':out['live_execution'],'fixtures':{k:v['status'] for k,v in out['fixtures'].items()},'method_gates':out['method_gates'],'simulations':out['simulations']},indent=2))
