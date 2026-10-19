"""Measured-selector synthetic boundary/identity tests; no native tools or fits."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('select_v10d_implementations',ROOT/'scripts/select_v10d_implementations.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('Native execution forbidden'))


@pytest.fixture
def audited():
    pairs=[];mapped=[];routes=[]
    for constant,context in itertools.product(m.CONSTANTS,m.CONTEXTS):
        formula=m.expected_formula(constant,context);pid='v10-csd:'+m.hashlib.sha256(formula.encode()).hexdigest()
        pairs.append({'pair_id':pid,'formula':formula,'constant_u32':constant,'context':context})
        for arm in m.ARMS:
            mapped.append({'pair_id':pid,'arm':arm,'formula':formula if arm=='original' else 'synthetic-csd('+formula+')',
                'primitive_counts':{'SB_DFF':132,'SB_LUT4':100 if arm=='original' else 90,'SB_CARRY':20 if arm=='original' else 30},
                'bare_lut4':68,'bare_carry':20,'transactions':2148,'inventory':{'ff_count':132},'sequential_error':None})
            for seed in m.SEEDS:
                fmax=100 if arm=='original' else 125
                routes.append({'pair_id':pid,'arm':arm,'seed':seed,'success':True,'status':'complete','fmax_mhz':fmax,'period_ns':1000/fmax,
                    'constraint_mhz':12,'meets_12mhz':True,'utilization':{'ICESTORM_LC':{'used':200 if arm=='original' else 190,'available':7680},
                    'ICESTORM_RAM':{'used':0,'available':32},'ICESTORM_PLL':{'used':0,'available':2},'SB_IO':{'used':4,'available':206},'SB_GB':{'used':1,'available':8}},
                    'packed_inventory':{'ff_count':132},'path_classification':'unknown','path_audit':{'classification':'unknown','reason':'retained synthetic alias failure'},
                    'command':['synthetic','seed',str(seed)],'log_sha256':'e'*64})
    return {'schema':'isaforge-v10d-timing-independent-portable-audit-v1','complete':True,'status':'pass','failures':[],
        'mappings_recounted':64,'routes_verified':192,'successful_routes':192,'sequential_transactions_checked':64*2148,
        'sequential_edge_lane_comparisons':64*2148*99,'mapped_arms':mapped,'routes':routes,'per_pair':pairs,
        **{k:'a'*64 for k in ('preparation_sha256','completion_sha256','archive_sha256','audit_source_sha256','shared_sequential_checker_sha256','area_completion_sha256')}}


def arms(audited):return m.alternatives_from_audit(audited)[0][1]


def set_period(alternative,seed,period):
    row=alternative['observations'][seed-1];row['fmax_mhz']=1000/period;row['period_ns']=1000/row['fmax_mhz']


@pytest.mark.parametrize('value',[None,{}, {'max_wrapped_lut4':0,'max_carry':0,'max_packed_lc':0,'max_ff':0,'min_fmax_mhz':0}, {'min_fmax_mhz':0.0}])
def test_explicit_zero_and_omitted_constraints(value):
    assert m.validate_budgets(value)==({} if value is None else value)


@pytest.mark.parametrize('value',[[],1,True,{'unknown':1},{'max_ff':None},{'max_ff':True},{'max_ff':132.0},{'max_ff':-1},
    {'min_fmax_mhz':True},{'min_fmax_mhz':None},{'min_fmax_mhz':-0.1},{'min_fmax_mhz':float('nan')},{'min_fmax_mhz':float('inf')},{'min_fmax_mhz':10**400}])
def test_budgets_reject_wrong_types_nonfinite_negative_and_unknown(value):
    with pytest.raises(ValueError):m.validate_budgets(value)


@pytest.mark.parametrize('text',['{"max_ff":132,"max_ff":131}','{"min_fmax_mhz":NaN}','{"min_fmax_mhz":Infinity}','{"min_fmax_mhz":1e999}','null','[1]','{"max_ff":'])
def test_cli_json_rejects_duplicates_nonfinite_and_nonobject(text):
    with pytest.raises(ValueError):m.parse_budgets(text)


def test_unconstrained_all_evidence_and_no_implicit_budget(audited):
    before=copy.deepcopy(audited);result=m.select_audited(audited)
    assert result['budgets']=={} and result['counts']['chosen_csd']==32 and result['counts']['seed_observations']==192
    first=result['formulas'][0];assert first['chosen_arm']=='csd' and first['current_feasible'] is True
    assert first['pareto_front_all']==['original','csd'] # lower LUT/LC vs higher carry
    assert first['alternatives'][1]['path_classification_counts']=={'unknown':3}
    assert first['alternatives'][1]['observations'][2]['route_evidence']==audited['routes'][5]
    assert first['alternatives'][1]['observations'][2]['path_audit']['reason']=='retained synthetic alias failure'
    assert result['native_jobs_run']==result['model_fits']==result['labels_rewritten']==0 and audited==before
    assert result['authentication']['audit_result_canonical_sha256']==m.data_sha(audited)
    first['alternatives'][0]['observations'][0]['route_evidence']['command'].append('mutation')
    assert audited==before


def test_all_caps_inclusive_at_equality_and_no_hidden_margin(audited):
    budget={'max_wrapped_lut4':100,'max_carry':30,'max_packed_lc':200,'max_ff':132,'min_fmax_mhz':100}
    result=m.choose(arms(audited),budget)
    assert result['chosen_arm']=='csd' and all(a['feasible'] for a in result['alternatives'])
    budget['min_fmax_mhz']=125;result=m.choose(arms(audited),budget)
    assert result['status']=='csd-only-feasible' and result['current_feasible'] is False
    budget['min_fmax_mhz']=125.00000000000001;result=m.choose(arms(audited),budget)
    assert result['chosen_arm'] is None and result['status']=='no-feasible-implementation'
    assert result['pareto_front_feasible']==[] and result['chosen_worst_minus_original_period_ns'] is None


def test_one_seed_resource_breach_cannot_hide_behind_average(audited):
    alternatives=arms(audited);alternatives[1]['observations'][2]['packed_lc']=201
    result=m.choose(alternatives,{'max_packed_lc':200})
    csd=result['alternatives'][1]
    assert result['chosen_arm']=='original' and result['status']=='original-only-feasible'
    assert csd['violations']==[{'budget':'max_packed_lc','limit':200,'comparison':'observed <= cap','failed_seeds':[3],
        'observed_by_seed':{'1':190,'2':190,'3':201}}]
    assert csd['resource_maximum_seeds']['packed_lc']==[3]


def test_one_seed_timing_breach_and_worst_ids_not_mean(audited):
    alternatives=arms(audited)
    for seed,period in enumerate((5,5,14),1):set_period(alternatives[1],seed,period)
    result=m.choose(alternatives)
    assert sum(x['period_ns'] for x in alternatives[1]['observations'])/3<10
    assert result['chosen_arm']=='original' and result['csd_worst_minus_original_period_ns']==4
    assert result['alternatives'][1]['worst_period_seeds']==[3] and result['alternatives'][1]['minimum_fmax_seeds']==[3]
    constrained=m.choose(alternatives,{'min_fmax_mhz':100})
    assert constrained['alternatives'][1]['violations'][0]['failed_seeds']==[3]


def test_distinct_resource_caps_carry_forces_original_and_ff_can_force_none(audited):
    assert m.choose(arms(audited),{'max_carry':20})['chosen_arm']=='original'
    result=m.choose(arms(audited),{'max_ff':131})
    assert result['chosen_arm'] is None and all(a['violations'][0]['failed_seeds']==[1,2,3] for a in result['alternatives'])
    assert m.choose(arms(audited),{'min_fmax_mhz':0})['chosen_arm']=='csd'


def test_perfect_tie_retains_both_front_original_chosen_independent_of_input_order(audited):
    alternatives=arms(audited);alternatives[1]['observations']=copy.deepcopy(alternatives[0]['observations'])
    result=m.choose(list(reversed(alternatives)))
    assert result['pareto_front_all']==result['pareto_front_feasible']==['original','csd']
    assert result['chosen_arm']=='original' and result['status']=='original-chosen' and result['changed_from_current'] is False


def test_period_tie_uses_documented_resource_lexicographic_order_without_sum(audited):
    alternatives=arms(audited)
    for seed in m.SEEDS:set_period(alternatives[1],seed,10)
    for row in alternatives[1]['observations']:row['carry']=10000;row['packed_lc']=5000
    result=m.choose(alternatives)
    assert result['pareto_front_all']==['original','csd'] and result['chosen_arm']=='csd' # LUT90 beats100; no sum


def test_dominated_alternative_removed_only_within_function(audited):
    alternatives=arms(audited)
    for row in alternatives[1]['observations']:row['carry']=10
    result=m.choose(alternatives)
    assert result['pareto_front_all']==['csd'] and result['pareto_front_feasible']==['csd']


@pytest.mark.parametrize('poison',['missing-seed','duplicate-seed','foreign-seed','bool-seed','foreign-arm','foreign-pair','duplicate-map','missing-map',
    'missing-pair','duplicate-pair','formula','cohort','incomplete','denominator','audit-hash','failed-route','nan-fmax','inf-period','wrong-period','bool-count','fractional-count','negative-count','path-status','FF','fractional-FF','fractional-transactions','fractional-inventory','sequential-error'])
def test_incomplete_or_malformed_audited_evidence_rejected(audited,poison):
    if poison=='missing-seed':audited['routes'].pop()
    elif poison=='duplicate-seed':audited['routes'][-1]=copy.deepcopy(audited['routes'][-2])
    elif poison=='foreign-seed':audited['routes'][0]['seed']=4
    elif poison=='bool-seed':audited['routes'][0]['seed']=True
    elif poison=='foreign-arm':audited['routes'][0]['arm']='alternate'
    elif poison=='foreign-pair':audited['routes'][0]['pair_id']='v10-csd:'+'f'*64
    elif poison=='duplicate-map':audited['mapped_arms'][-1]=copy.deepcopy(audited['mapped_arms'][0])
    elif poison=='missing-map':audited['mapped_arms'].pop()
    elif poison=='missing-pair':audited['per_pair'].pop()
    elif poison=='duplicate-pair':audited['per_pair'][-1]=copy.deepcopy(audited['per_pair'][0])
    elif poison=='formula':audited['per_pair'][0]['formula']='different function'
    elif poison=='cohort':audited['per_pair'][0]['constant_u32']=12
    elif poison=='incomplete':audited['complete']=False
    elif poison=='denominator':audited['successful_routes']=191
    elif poison=='audit-hash':audited['archive_sha256']='bad'
    elif poison=='failed-route':audited['routes'][0]['success']=False
    elif poison=='nan-fmax':audited['routes'][0]['fmax_mhz']=float('nan')
    elif poison=='inf-period':audited['routes'][0]['period_ns']=float('inf')
    elif poison=='wrong-period':audited['routes'][0]['period_ns']=5
    elif poison=='bool-count':audited['mapped_arms'][0]['primitive_counts']['SB_LUT4']=True
    elif poison=='fractional-count':audited['routes'][0]['utilization']['ICESTORM_LC']['used']=3.0
    elif poison=='negative-count':audited['mapped_arms'][0]['primitive_counts']['SB_CARRY']=-1
    elif poison=='path-status':audited['routes'][0]['path_classification']='datapath-boundary'
    elif poison=='FF':audited['routes'][0]['packed_inventory']['ff_count']=131
    elif poison=='fractional-FF':audited['routes'][0]['packed_inventory']['ff_count']=132.0
    elif poison=='fractional-transactions':audited['mapped_arms'][0]['transactions']=2148.0
    elif poison=='fractional-inventory':audited['mapped_arms'][0]['inventory']['ff_count']=132.0
    else:audited['mapped_arms'][0]['sequential_error']='wrong transaction'
    with pytest.raises(ValueError):m.select_audited(audited)


def test_select_invokes_frozen_auditor_once_and_binds_exact_source(audited,monkeypatch,tmp_path):
    calls=[];audited['audit_source_sha256']=m.file_sha(m.frozen_audit.__file__)
    monkeypatch.setattr(m.frozen_audit,'run',lambda root:(calls.append(root),audited)[1])
    result=m.select(tmp_path,{'max_ff':132})
    assert calls==[tmp_path.resolve()] and result['authentication']['mode']=='frozen audit_v10d_timing.run(root) replay'
    assert result['authentication']['audit_source_sha256']==m.file_sha(m.frozen_audit.__file__)
    audited['audit_source_sha256']='f'*64
    with pytest.raises(ValueError,match='auditor source'):m.select(tmp_path)


def test_semantically_identical_budget_key_order_has_identical_choices_and_reasons(audited):
    a={'max_ff':131,'min_fmax_mhz':130,'max_carry':10}
    b=dict(reversed(list(a.items())))
    assert m.select_audited(audited,a)==m.select_audited(audited,b)


def test_cli_huge_integer_frequency_rejected_without_overflow():
    with pytest.raises(ValueError,match='finite nonnegative'):
        m.parse_budgets('{"min_fmax_mhz":'+str(10**400)+'}')
    assert m.parse_budgets('{"max_ff":'+str(10**400)+'}')['max_ff']==10**400
