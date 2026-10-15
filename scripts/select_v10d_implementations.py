#!/usr/bin/env python3
"""Choose measured V10d implementations under explicit per-formula hard caps.

This is a postmeasurement development oracle, not a learned selector or a CPU
performance result. No native tools, fitting, target relabeling or cap search.
Omitted budgets are unconstrained. Resource caps are nonnegative integer counts;
min_fmax_mhz is finite and nonnegative, with zero explicitly allowed.
"""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import audit_v10d_timing as frozen_audit

ARMS = ('original', 'csd')
SEEDS = (1, 2, 3)
CONSTANTS = (11, 44, 85, 340, 341, 511, 1364, 2044)
CONTEXTS = ('direct_product', 'add_after_product', 'sub_before_product', 'masked_sub_before_product')
RESOURCE_KEYS = ('wrapped_lut4', 'carry', 'packed_lc', 'ff')
CAPS = {'max_wrapped_lut4':'wrapped_lut4', 'max_carry':'carry', 'max_packed_lc':'packed_lc', 'max_ff':'ff'}
PATH_CLASSES = {'datapath-boundary', 'wrapper-boundary', 'unknown'}
OBJECTIVE = ['worst_period_ns', 'max_wrapped_lut4', 'max_carry', 'max_packed_lc', 'max_ff', 'arm_original_before_csd']


def need(condition, message):
    if not condition: raise ValueError(message)


def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def data_sha(value): return hashlib.sha256(canonical(value)).hexdigest()
def file_sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def integer(value): return type(value) is int and value >= 0

def finite(value, *, positive=False):
    if type(value) not in (int,float): return False
    try: return math.isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError: return False


def validate_budgets(budgets=None):
    """Omit an optional constraint to leave it unconstrained; null is invalid."""
    if budgets is None: return {}
    need(type(budgets) is dict, 'Budgets must be a JSON object')
    need(set(budgets) <= set(CAPS) | {'min_fmax_mhz'}, 'Unknown budget key')
    result = {}
    for name in (*CAPS,'min_fmax_mhz'):
        if name not in budgets: continue
        value = budgets[name]
        need(integer(value) if name in CAPS else finite(value),
            name + (' requires a nonnegative integer count' if name in CAPS else ' requires finite nonnegative MHz'))
        result[name] = value
    return result


def parse_budgets(text):
    def unique(items):
        value = {}
        for key,item in items:
            need(key not in value, 'Duplicate budget key');value[key] = item
        return value
    try:
        value = json.loads(text, object_pairs_hook=unique,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON budget: '+value)))
    except (json.JSONDecodeError, TypeError) as error: raise ValueError('Invalid budget JSON') from error
    need(type(value) is dict, 'Supplied budget JSON must be an object; omit keys for unconstrained')
    return validate_budgets(value)


def expected_formula(constant, context):
    operand = 'in0' if context in CONTEXTS[:2] else 'sub(in0,in1)' if context == CONTEXTS[2] else 'sub(andi(in0,63),in1)'
    product = f'mul({operand},addi(0,{constant}))'
    return f'add({product},in1)' if context == CONTEXTS[1] else product


def _index(rows, fields, expected, message):
    need(type(rows) is list, message)
    result = {}
    for row in rows:
        need(type(row) is dict and all(k in row for k in fields), message)
        key = tuple(row[k] for k in fields)
        need(key in expected and key not in result, message)
        if 'seed' in fields: need(type(row['seed']) is int and row['seed'] in SEEDS, 'Exact integer seed1/2/3 required')
        result[key] = row
    need(set(result) == expected, message)
    return result


def _observation(seed, mapping, route):
    need(route.get('success') is True and route.get('status') == 'complete', 'Every measured route must succeed')
    fmax,period = route.get('fmax_mhz'),route.get('period_ns')
    need(finite(fmax,positive=True) and finite(period,positive=True) and period == 1000/fmax,
        'Positive finite reciprocal-Fmax period required')
    need(type(route.get('constraint_mhz')) in (int,float) and route['constraint_mhz'] == 12
        and type(route.get('meets_12mhz')) is bool and route['meets_12mhz'] is (fmax >= 12), 'Authenticated12MHz route metadata required')
    need(route.get('path_classification') in PATH_CLASSES and type(route.get('path_audit')) is dict
        and route['path_audit'].get('classification') == route['path_classification'], 'Retain explicit matching path-attribution status')
    utilization = route.get('utilization');need(type(utilization) is dict, 'Packed resource inventory required')
    for name,row in utilization.items():
        need(type(name) is str and type(row) is dict and set(row) == {'used','available'}
            and integer(row['used']) and integer(row['available']) and row['used'] <= row['available'], 'Invalid packed resource count')
    need('ICESTORM_LC' in utilization and all(utilization.get(k,{}).get('used') == v for k,v in [('ICESTORM_RAM',0),('ICESTORM_PLL',0),('SB_IO',4),('SB_GB',1)]),
        'Complete fixed-harness packed inventory required')
    need(type(route.get('packed_inventory',{}).get('ff_count')) is int and route['packed_inventory']['ff_count'] == 132, '132 packed harness FFs required')
    counts = mapping['primitive_counts']
    return {'seed':seed,'wrapped_lut4':counts.get('SB_LUT4',0),'carry':counts.get('SB_CARRY',0),
        'packed_lc':utilization['ICESTORM_LC']['used'],'ff':counts['SB_DFF'],
        'fmax_mhz':fmax,'period_ns':period,'path_classification':route['path_classification'],
        'path_audit':copy.deepcopy(route['path_audit']), 'route_evidence':copy.deepcopy(route)}


def alternatives_from_audit(audit):
    """Defend the pure replay API too: only the complete32/64/192 grid is valid."""
    need(type(audit) is dict and audit.get('schema') == 'isaforge-v10d-timing-independent-portable-audit-v1'
        and audit.get('complete') is True and audit.get('status') == 'pass' and audit.get('failures') == [], 'Complete passing frozen raw audit required')
    for name,count in [('mappings_recounted',64),('routes_verified',192),('successful_routes',192),
        ('sequential_transactions_checked',64*2148),('sequential_edge_lane_comparisons',64*2148*99)]:
        need(type(audit.get(name)) is int and audit[name] == count, 'Complete audit denominator differs: '+name)
    for key in ('preparation_sha256','completion_sha256','archive_sha256','audit_source_sha256','shared_sequential_checker_sha256','area_completion_sha256'):
        need(type(audit.get(key)) is str and re.fullmatch('[0-9a-f]{64}',audit[key]), 'Exact audit/input SHA256 required')
    pairs = audit.get('per_pair')
    need(type(pairs) is list and len(pairs) == 32, 'Exactly32 formula records required')
    cohorts = list(itertools.product(CONSTANTS,CONTEXTS));ids = set();formulas = set()
    for pair,(constant,context) in zip(pairs,cohorts):
        need(type(pair) is dict and pair.get('constant_u32') == constant and type(pair['constant_u32']) is int
            and pair.get('context') == context and pair.get('formula') == expected_formula(constant,context)
            and type(pair.get('pair_id')) is str and re.fullmatch('v10-csd:[0-9a-f]{64}',pair['pair_id'])
            and pair['pair_id'] not in ids and pair['formula'] not in formulas, 'Exact ordered32 distinct fixed formulas required')
        ids.add(pair['pair_id']);formulas.add(pair['formula'])
    mapping = _index(audit.get('mapped_arms'),('pair_id','arm'),{(pid,a) for pid in ids for a in ARMS}, 'Complete unique64 mapped arms required')
    routes = _index(audit.get('routes'),('pair_id','arm','seed'),{(pid,a,s) for pid in ids for a in ARMS for s in SEEDS}, 'Complete unique192 routes required')
    result = []
    for pair in pairs:
        arms = []
        for arm in ARMS:
            mapped = mapping[pair['pair_id'],arm];counts = mapped.get('primitive_counts')
            need(type(counts) is dict and set(counts) <= {'SB_DFF','SB_LUT4','SB_CARRY'} and all(integer(x) for x in counts.values())
                and counts.get('SB_DFF') == 132, 'Exact nonnegative wrapped LUT4/carry/132FF counts required')
            need(type(mapped.get('transactions')) is int and mapped['transactions'] == 2148 and mapped.get('sequential_error') is None
                and type(mapped.get('inventory',{}).get('ff_count')) is int and mapped['inventory']['ff_count'] == 132, 'All mapped sequential checks must pass')
            need(type(mapped.get('formula')) is str and (arm != 'original' or mapped['formula'] == pair['formula']), 'Implementation formula identity differs')
            arms.append({'pair_id':pair['pair_id'],'arm':arm,'formula':mapped['formula'],
                'mapping_evidence':copy.deepcopy(mapped),'observations':[_observation(seed,mapped,routes[pair['pair_id'],arm,seed]) for seed in SEEDS]})
        result.append(({k:pair[k] for k in ('pair_id','formula','constant_u32','context')},arms))
    return result


def _evaluate(alternative,budgets):
    value = copy.deepcopy(alternative);rows = value.get('observations')
    need(type(rows) is list and len(rows) == 3 and [r.get('seed') for r in rows] == list(SEEDS)
        and all(type(r['seed']) is int for r in rows), 'Exactly three ordered seed observations required')
    for row in rows:
        need(all(integer(row.get(k)) for k in RESOURCE_KEYS) and finite(row.get('fmax_mhz'),positive=True)
            and finite(row.get('period_ns'),positive=True) and row['period_ns'] == 1000/row['fmax_mhz'], 'Valid count/reciprocal observations required')
    maxima = {key:max(r[key] for r in rows) for key in RESOURCE_KEYS}
    worst = max(r['period_ns'] for r in rows);minimum = min(r['fmax_mhz'] for r in rows)
    violations = []
    for name,limit in budgets.items():
        field = CAPS.get(name,'fmax_mhz')
        failed = [r for r in rows if (r[field] > limit if name in CAPS else r[field] < limit)]
        if failed: violations.append({'budget':name,'limit':limit,'comparison':'observed <= cap' if name in CAPS else 'observed >= minimum',
            'failed_seeds':[r['seed'] for r in failed],'observed_by_seed':{str(r['seed']):r[field] for r in rows}})
    value.update({'feasible':not violations,'violations':violations,'max_resources':maxima,'worst_period_ns':worst,
        'worst_period_seeds':[r['seed'] for r in rows if r['period_ns'] == worst], 'minimum_fmax_mhz':minimum,
        'minimum_fmax_seeds':[r['seed'] for r in rows if r['fmax_mhz'] == minimum],
        'resource_maximum_seeds':{k:[r['seed'] for r in rows if r[k] == maximum] for k,maximum in maxima.items()},
        'pareto_vector':{**maxima,'worst_period_ns':worst},'path_classification_counts':dict(Counter(r.get('path_classification','unknown') for r in rows))})
    return value


def dominates(left,right):
    """Within one function: all four distinct resource maxima and worst period."""
    dimensions = (*RESOURCE_KEYS,'worst_period_ns')
    a,b = left['pareto_vector'],right['pareto_vector']
    return all(a[k] <= b[k] for k in dimensions) and any(a[k] < b[k] for k in dimensions)


def choose(alternatives,budgets=None):
    """Pure two-arm choice; observations use the schema from alternatives_from_audit.

    Caps apply to each seed independently. Pareto fronts compare maxima of the
    four distinct resource counts and worst seed period. Objective is exactly
    worst period, then LUT4, carry, LC, FF, then original before CSD. No sums,
    margins, mean-period substitution, across-function front or fallback.
    """
    budgets = validate_budgets(budgets)
    need(type(alternatives) is list and len(alternatives) == 2 and {x.get('arm') for x in alternatives} == set(ARMS)
        and len({x.get('pair_id') for x in alternatives}) == 1, 'Original/CSD alternatives for exactly one function required')
    byarm = {a['arm']:_evaluate(a,budgets) for a in alternatives};values = [byarm[a] for a in ARMS]
    front = [x['arm'] for x in values if not any(dominates(y,x) for y in values)]
    feasible = [x for x in values if x['feasible']]
    feasible_front = [x['arm'] for x in feasible if not any(dominates(y,x) for y in feasible)]
    chosen = min(feasible,key=lambda x:(x['worst_period_ns'],*(x['max_resources'][k] for k in RESOURCE_KEYS),ARMS.index(x['arm']))) if feasible else None
    original = byarm['original'];csd = byarm['csd']
    status = ('no-feasible-implementation' if chosen is None else 'original-only-feasible' if original['feasible'] and not csd['feasible']
        else 'csd-only-feasible' if csd['feasible'] and not original['feasible'] else chosen['arm']+'-chosen')
    return {'alternatives':values,'pareto_front_all':front,'pareto_front_feasible':feasible_front,
        'chosen_arm':chosen['arm'] if chosen else None,'status':status,'current_arm':'original','current_feasible':original['feasible'],
        'changed_from_current':chosen is not None and chosen['arm'] != 'original',
        'chosen_worst_minus_original_period_ns':chosen['worst_period_ns']-original['worst_period_ns'] if chosen else None,
        'csd_worst_minus_original_period_ns':csd['worst_period_ns']-original['worst_period_ns'],
        'choice_reason':'No implementation satisfies every explicit cap at every seed; no fallback.' if chosen is None else
            'Minimum worst-seed period among feasible alternatives; exact ties use wrappedLUT4,carry,packedLC,FF,original-before-csd.'}


def select_audited(audit,budgets=None):
    """Pure replay over a supplied complete audit; caller authenticates its source.

    Production callers should use select(root), which invokes the frozen raw
    auditor. This function exists for deterministic synthetic tests and explicit
    postmeasurement policy comparisons over the same authenticated audit.
    """
    budgets = validate_budgets(budgets);candidates = alternatives_from_audit(audit)
    rows = [{**pair,**choose(alternatives,budgets)} for pair,alternatives in candidates]
    return {'schema':'isaforge-v10d-measured-implementation-selection-v1','scope':'Postmeasurement per-formula development oracle; not ML, prospective selection, CPU performance, power or population evidence.',
        'budget_scope':'Each standalone wrapped implementation independently; no sum over32 functions or CPU/workload budget.',
        'budgets':budgets,'omitted_budgets':'unconstrained; no implied budget','constraint_policy':'Inclusive equality, every seed; no tolerance or violating fallback.',
        'objective':list(OBJECTIVE),'pareto_dimensions':[*RESOURCE_KEYS,'worst_period_ns'],
        'pareto_scope':'Original versus CSD for the same formula; resources use worst-seed maxima, time uses maximum reciprocal Fmax.',
        'authentication':{'mode':'supplied-audit; caller is responsible for frozen-auditor authentication',
            'audit_result_canonical_sha256':data_sha(audit),'canonical_encoding':'UTF-8 JSON sort_keys=True,separators=(comma,colon),allow_nan=False',
            **{k:audit[k] for k in ('audit_source_sha256','preparation_sha256','completion_sha256','archive_sha256','shared_sequential_checker_sha256','area_completion_sha256')},
            'selector_source_sha256':file_sha(__file__)},'native_jobs_run':0,'model_fits':0,'labels_rewritten':0,
        'formulas':rows,'counts':{'formulas':32,'alternatives':64,'seed_observations':192,
            'chosen_original':sum(r['chosen_arm']=='original' for r in rows),'chosen_csd':sum(r['chosen_arm']=='csd' for r in rows),
            'no_feasible_implementation':sum(r['chosen_arm'] is None for r in rows),'current_original_feasible':sum(r['current_feasible'] for r in rows),
            'csd_only_feasible':sum(r['status']=='csd-only-feasible' for r in rows)}}


def select(root,budgets=None):
    budgets = validate_budgets(budgets);root = Path(root).resolve();source = Path(frozen_audit.__file__).resolve();before = file_sha(source)
    audit = frozen_audit.run(root)
    need(file_sha(source) == before == audit.get('audit_source_sha256'),'Frozen auditor source changed or result identity differs')
    result = select_audited(audit,budgets);result['authentication']['mode'] = 'frozen audit_v10d_timing.run(root) replay'
    result['authentication']['root'] = root.relative_to(ROOT).as_posix() if root.is_relative_to(ROOT) else str(root)
    result['authentication']['auditor_source_path'] = source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else str(source)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--budgets',default='{}',help='Explicit JSON object; omitted keys are unconstrained. Count caps are integers; min_fmax_mhz>=0.')
    parser.add_argument('--output',type=Path,help='Fresh output file; existing evidence is never overwritten.')
    args = parser.parse_args()
    try: result = select(args.root,parse_budgets(args.budgets))
    except ValueError as error:parser.error(str(error))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    else:print(json.dumps(result,indent=2,allow_nan=False))
