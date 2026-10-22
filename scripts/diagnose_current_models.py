"""Arithmetic diagnosis of consumed measurements and cached predictions; no fits.

The cost-free comparisons below change only the first acquisition ranking from
already sealed GP predictions. They are retrospective diagnostics, not a new
policy evaluation, a tuned model, or a prospective result.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import hashlib
import json
import math
from pathlib import Path,PurePosixPath
import random
import statistics
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import budgeted_selection as b,codesign as c
from isaforge.features import FEATURE_COLUMNS
from isaforge.speedup_corpus import family
from isaforge.structural_features_v3 import feature_dict
from scripts.diagnose_factorized_selection import folds
from scripts.export_guarded_corpus import _csv
from scripts.report_budget_campaign import table
from scripts.reproduce_guarded_sha256 import _manifest

CORPUS=ROOT/'results/2026-10-22-eleven-source-corpus/corpus.json'
EXPANDED=ROOT/'results/2026-10-22-expanded-history-verified'
LIVE=ROOT/'results/2026-10-22-live-gp-campaign'
OUTPUT=ROOT/'results/2026-10-22-model-research-diagnosis'
TARGETS=('beebs-aha-compress','beebs-ndes','beebs-nettle-md5','beebs-jfdctint')
GP_POLICIES=('hybrid_gp_zero_shot','hybrid_gp_adapt')
ARCHIVE_FOLDERS=(
    'results/2026-10-19-automatic-aha-mont64','results/2026-10-20-automatic-crc32',
    'results/2026-10-20-slre-transfer','results/2026-10-20-budget-campaign',
    'results/2026-10-21-sha256-campaign/native','results/2026-10-21-disjoint-sha256-campaign/native',
    'results/2026-10-21-jfdctint-campaign/native',
    *(f'results/2026-10-21-blind-campaign/targets/{source}/native' for source in TARGETS[:3]),
    'results/2026-10-22-live-gp-campaign/native')
DISCOVERY_MEMBER='discovery/discovery.json'


def original_discovery_path(context):
    return Path(context['baseline_provenance']['root'])/DISCOVERY_MEMBER


def archived_discovery(folder,record,expected):
    """Use the existing raw-archive contract without extracting any paths.

    Matches the membership/regular-file/checksum safeguards of
    reproduce_codesign.restore_archive and report_blind_campaign's bounded
    reader. Return the original bytes, not reserialized substitute metadata.
    """
    name=PurePosixPath(record['archive'])
    c.require(len(name.parts)==1 and not name.is_absolute(),'Safe archive filename required')
    path=Path(folder)/str(name)
    c.require(c.sha(path)==record['sha256'],'Discovery archive checksum differs')
    entries={entry['path']:entry for entry in record['files']}
    c.require(len(entries)==len(record['files'])<=5000 and DISCOVERY_MEMBER in entries,
              'Complete unique discovery archive inventory required')
    entry=entries[DISCOVERY_MEMBER]
    c.require(entry['sha256']==expected and 0<entry['bytes']<=2*1024**2,
              'Exact bounded context-bound discovery bytes required')
    with tarfile.open(path,'r:gz') as archive:
        members=archive.getmembers()
        c.require(len(members)==len(entries) and {member.name for member in members}==set(entries),
                  'Discovery archive membership differs')
        for member in members:
            relative=PurePosixPath(member.name)
            c.require(member.isfile() and not relative.is_absolute() and '..' not in relative.parts and
                      member.size==entries[member.name]['bytes'],'Only exact regular archived files allowed')
        with archive.extractfile(DISCOVERY_MEMBER) as stream:payload=stream.read(2*1024**2+1)
    c.require(len(payload)==entry['bytes'] and hashlib.sha256(payload).hexdigest()==expected,
              'Context-bound archived discovery checksum differs')
    return payload


def discovery_inputs(contexts,read,bindings):
    """Canonical archive bindings make present/missing generated roots equivalent."""
    wanted={context['baseline_provenance']['artifacts'][DISCOVERY_MEMBER] for context in contexts.values()}
    catalog={}
    for name in ARCHIVE_FOLDERS:
        folder=ROOT/name;manifest=read(folder/'archive-manifest.json')
        records=[manifest] if 'files' in manifest else list(manifest.values())
        for record in records:
            matches=[entry for entry in record['files'] if entry['path']==DISCOVERY_MEMBER and entry['sha256'] in wanted]
            if matches:
                c.require(len(matches)==1,'Unique discovery member required')
                digest=matches[0]['sha256']
                if digest not in catalog:catalog[digest]=(folder,record)
    c.require(set(catalog)==wanted,'Every current context needs an authenticated committed discovery archive')
    result={}
    for benchmark,context in contexts.items():
        expected=context['baseline_provenance']['artifacts'][DISCOVERY_MEMBER]
        folder,record=catalog[expected]
        archived=archived_discovery(folder,record,expected)
        path=original_discovery_path(context)
        if path.is_file():
            original=path.read_bytes()
            c.require(hashlib.sha256(original).hexdigest()==expected and original==archived,
                      'Original and archived discovery bytes differ')
        bindings[(folder/record['archive']).relative_to(ROOT).as_posix()]=record['sha256']
        result[benchmark]=archived
    return result


def rank_pairs(rows):
    """Available within-context comparisons, never independent sample counts."""
    result=[]
    for context in sorted({row['benchmark'] for row in rows}):
        members=[row for row in rows if row['benchmark']==context]
        pairs=list(combinations(members,2))
        unequal=[(a,z) for a,z in pairs if a['speedup']!=z['speedup']]
        conflicts={str(cap):sum((a['speedup']>z['speedup'] and not b._feasible(a,cap,12) and b._feasible(z,cap,12)) or
            (z['speedup']>a['speedup'] and not b._feasible(z,cap,12) and b._feasible(a,cap,12)) for a,z in unequal)
            for cap in (32,64,128)}
        result.append(dict(benchmark=context,source=members[0]['workload_group'],rows=len(members),
            distinct_speedup_levels=len({row['speedup'] for row in members}),all_pairs=len(pairs),
            unequal_pairs=len(unequal),tied_pairs=len(pairs)-len(unequal),
            faster_infeasible_slower_feasible_pairs=conflicts))
    return result


def aliases(rows,columns):
    grouped=defaultdict(list)
    for row in rows:grouped[tuple(row[key] for key in columns)].append(row)
    duplicates=[members for members in grouped.values() if len(members)>1]
    return dict(columns=list(columns),unique_vectors=len(grouped),duplicate_groups=len(duplicates),
        rows_in_duplicate_groups=sum(map(len,duplicates)),groups=[
            [dict(candidate_id=row['candidate_id'],source=row['workload_group'],benchmark=row['benchmark'],
                  formula=row['formula'],added_lut4=row['area_delta_lut4'],
                  measured_saved_cycles=row['baseline_cycles']-row['candidate_cycles']) for row in members]
            for members in duplicates])


def acquisition(row,estimate,cap):
    """Exactly the frozen first-query GP acquisition decomposed into factors."""
    gain=max(0.,row['latency_features']['estimated_speedup']-1.)
    p_area=b._probability_below(estimate['area_delta_lut4_mean'],estimate['area_delta_lut4_std'],cap)
    p_clock=b._probability_below(-estimate['routed_fmax_min_mhz_mean'],estimate['routed_fmax_min_mhz_std'],-12.)
    inverse_time=math.exp(max(-700,min(700,-estimate['log_measurement_seconds_mean']+
                                     .5*estimate['log_measurement_seconds_std']**2)))
    probability=p_area*p_clock*estimate['device_fit_probability']
    # Preserve the frozen multiplication order, including near-tied AHA scores.
    count_score=gain*p_area*p_clock*estimate['device_fit_probability']
    value=count_score*inverse_time
    c.require(value==b.hybrid_score(row,estimate,1.,cap,12.),'Frozen first-query score differs')
    return dict(positive_calibrated_speedup_gain=gain,
        public_cycle_reduction=row['latency_features']['estimated_cycle_reduction'],
        p_area=p_area,p_clock=p_clock,fit_rate=estimate['device_fit_probability'],
        independent_feasibility_product=probability,expected_inverse_seconds=inverse_time,
        count_only_score=count_score,frozen_cost_score=value)


def choose(public,values,seed,key='frozen_cost_score'):
    ordered=list(public);random.Random(seed).shuffle(ordered)
    return max(ordered,key=lambda row:(values[row['candidate_id']][key],
                   row['latency_features']['estimated_speedup']))['candidate_id']


def scale_summary(training,public):
    scales={key:statistics.pstdev(row[key] for row in training) or 1. for key in b.STRUCTURAL_COLUMNS}
    means={key:statistics.mean(row[key] for row in training) for key in b.STRUCTURAL_COLUMNS}
    nearest=[]
    for row in public:
        distances=sorted([(math.sqrt(sum(((row[key]-old[key])/scales[key])**2 for key in b.STRUCTURAL_COLUMNS)),old)
                          for old in training],key=lambda pair:pair[0])
        distance,old=distances[0]
        nearest.append(dict(candidate_id=row['candidate_id'],formula=row['formula'],
            nearest_training_id=old['candidate_id'],nearest_training_source=old['workload_group'],
            nearest_training_formula=old['formula'],nearest_training_added_lut4=old['area_delta_lut4'],
            standardized_euclidean_distance=distance,differences={key:[row[key],old[key]]
                for key in b.STRUCTURAL_COLUMNS if row[key]!=old[key]}))
    return dict(means=means,population_standard_deviations=scales,nearest_training_neighbors=nearest)


def descriptor_pair(rows,left,right):
    matches=[next(row for row in rows if row['formula']==formula) for formula in (left,right)]
    features=[feature_dict(formula) for formula in (left,right)]
    return dict(formulas=[left,right],added_lut4=[row['area_delta_lut4'] for row in matches],
        original_hardware_features_equal=all(matches[0][key]==matches[1][key] for key in b.STRUCTURAL_COLUMNS),
        differing_original_features={key:[matches[0][key],matches[1][key]] for key in b.STRUCTURAL_COLUMNS
            if matches[0][key]!=matches[1][key]},
        existing_v3_features_equal=features[0]==features[1],
        differing_v3_features={key:[features[0][key],features[1][key]] for key in features[0] if features[0][key]!=features[1][key]},
        feature_vectors=features,
        limitation='Formula-only representation check; zero fits, area-weight imports or decision-validation claims.')


def run(output):
    output=Path(output).resolve()
    c.require(not output.exists() and not any(output.is_relative_to(path) for path in (CORPUS.parent,EXPANDED,LIVE)),
              'Fresh diagnosis outside all sealed inputs required')
    bindings={}
    def read(path):
        path=Path(path);bindings[path.relative_to(ROOT).as_posix()]=c.sha(path)
        return c.unseal(path)
    for folder in (CORPUS.parent,EXPANDED,LIVE):_manifest(folder)
    corpus=read(CORPUS);rows=corpus['rows'];failed=corpus['failed_attempts']
    c.require(len(rows)==87 and len(failed)==3 and corpus['total_candidate_attempts']==90,
              'Exact current87-label/90-attempt corpus required')
    label_summary=dict(successful_labels=len(rows),failed_attempts=len(failed),charged_attempts=90,
        source_workloads=len(corpus['independent_workload_groups']),contexts=len(corpus['contexts']),
        formula_families=len({family(row['formula']) for row in rows}),
        failures_by_class=dict(Counter(row['failure_class'] for row in failed)),
        known_correctness_failures=sum(row['correctness_verified'] is False for row in failed),
        unknown_outcomes=sum(row['reference_censored'] for row in failed),
        candidate_cost_seconds=corpus['total_candidate_attempt_wall_seconds'],
        device_fit_negatives=sum(not row['device_fits'] for row in rows),
        timing_negatives_at_12mhz=sum(row['routed_fmax_min_mhz']<12 for row in rows),
        fmax_range_mhz=[min(row['routed_fmax_min_mhz'] for row in rows),max(row['routed_fmax_min_mhz'] for row in rows)],
        area_increment_range=[min(row['area_delta_lut4'] for row in rows),max(row['area_delta_lut4'] for row in rows)],
        feasible_counts={str(cap):sum(b._feasible(row,cap,12) for row in rows) for cap in (32,64,128)},
        analytic_latency_exact_rows=sum(row['baseline_cycles']-row['candidate_cycles']==row['latency_features']['estimated_saved_cycles'] for row in rows),
        actual_calendar_wall_seconds=None)
    source_counts=[dict(source=source,successful_labels=sum(row['workload_group']==source for row in rows),
        contexts=len({row['benchmark'] for row in rows if row['workload_group']==source}),
        candidate_weight=sum(row['workload_group']==source for row in rows)/len(rows),equal_source_weight=1/11)
        for source in corpus['independent_workload_groups']]
    current_folds=[{key:value for key,value in fold.items() if key not in ('target','public','fitting')}
                   for fold in folds(corpus)]
    headroom=[];coverage=[]
    discoveries=discovery_inputs(corpus['contexts'],read,bindings)
    for context,mapping in corpus['contexts'].items():
        members=[row for row in rows if row['benchmark']==context]
        for cap in (32,64,128):
            feasible=[row for row in members if b._feasible(row,cap,12)]
            oracle=max([0.]+[(row['baseline_cycles']-row['candidate_cycles'])/row['baseline_cycles'] for row in feasible])
            headroom.append(dict(source=members[0]['workload_group'],benchmark=context,cap=cap,
                verified_candidates=len(members),feasible_candidates=len(feasible),oracle_cycle_reduction=oracle,
                oracle_saved_cycles=max([0]+[row['baseline_cycles']-row['candidate_cycles'] for row in feasible]),
                reference_censored=any(row['benchmark']==context and row['reference_censored'] for row in failed)))
        expected=mapping['baseline_provenance']['artifacts'][DISCOVERY_MEMBER]
        discovery=json.loads(discoveries[context])
        eligible=discovery.get('eligible_formula_count');executable=len(discovery['executable_candidates'])
        coverage.append(dict(source=members[0]['workload_group'],benchmark=context,
            measured_pool_size=len(discovery['pool']),eligible_calibrated_formulas=eligible,
            executable_formulas=executable,eligible_pool_fraction=len(discovery['pool'])/eligible if eligible else None,
            executable_pool_fraction=len(discovery['pool'])/executable,
            selected_rank_indices=discovery.get('selected_rank_indices'),pool_rule=discovery['pool_rule'],
            missing_hardware_labels_outside_declared_pool=True,discovery_sha256=expected))
    descriptor_checks=[descriptor_pair(rows,*pair) for pair in (
        ('add(in0,slli(in1,2))','slli(add(in0,in1),2)'),
        ('addi(andi(sub(0,sltiu(in0,1)),998),2)','sub(addi(0,4),in0)'),
        ('addi(lui(-16384),315)','addi(lui(4096),-1650)'))]
    expanded=read(EXPANDED/'report.json');cases=[];decomposed=[];choices=[];cohorts=[];classifier_pairs=[]
    observed={row['candidate_id']:row for row in rows+failed}
    for phase,source,path in [(phase,source,EXPANDED/'experiments'/phase/source)
        for phase in ('old','expanded') for source in TARGETS]+[('fresh','beebs-expint',LIVE/'selection')]:
        public=read(path/'controls11/model/public.json');training=read(path/'controls11/model/history.json')
        predictions=read(path/'controls11/model/predictions.json');report=read(path/'report.json');protocol=read(path/'protocol.json')
        c.require({row['candidate_id'] for row in training}==set(protocol['historical_training_ids']), 'Exact fitting cohort required')
        support=read(path/'support-diagnostics.json')
        classifier=read(path/'feasibility-predictions.json')
        if source in ('beebs-jfdctint','beebs-ndes'):
            formulas=('addi(lui(-16384),315)','addi(lui(4096),-1650)') if source=='beebs-jfdctint' else (
                'add(in0,slli(in1,2))','slli(add(in0,in1),2)')
            identities=[next(row['candidate_id'] for row in public if row['formula']==formula) for formula in formulas]
            for prediction in classifier:
                for cap,values in prediction['by_cap'].items():
                    pair=[next(row for row in values if row['candidate_id']==identity) for identity in identities]
                    classifier_pairs.append(dict(cohort=phase,source=source,seed=prediction['seed'],cap=int(cap),
                        formulas=list(formulas),feasibility_score_means=[row['feasibility_score_mean'] for row in pair],
                        complete_member_scores_equal=pair[0]['feasibility_scores']==pair[1]['feasibility_scores'],
                        actual_area_feasibility=[b._feasible(observed[identity],int(cap),12) for identity in identities]))
        cohorts.append(dict(cohort=phase,source=source,training_rows=len(training),
            training_groups=dict(Counter(row['workload_group'] for row in training)),
            training_rank_pairs=rank_pairs(training),
            unequal_training_pairs=sum(row['unequal_pairs'] for row in rank_pairs(training)),
            target_outside_training_ranges=sum(bool(row['outside_training_range']) for row in support['candidates']),
            fitting_ids=protocol['historical_training_ids'],scaling=scale_summary(training,public)))
        case=dict(cohort=phase,source=source,public=public,training=training,predictions=predictions,report=report)
        cases.append(case)
        for seed,prediction in enumerate(predictions):
            c.require(prediction['seed']==seed,'Five ordered prediction seeds required')
            hardware={row['candidate_id']:row for row in prediction['hardware']}
            for cap in (32,64,128):
                values={row['candidate_id']:acquisition(row,hardware[row['candidate_id']],cap) for row in public}
                selected=choose(public,values,seed);count_selected=choose(public,values,seed,'count_only_score')
                gains=[(observed[identity]['baseline_cycles']-observed[identity]['candidate_cycles'])/observed[identity]['baseline_cycles']
                       if b._feasible(observed[identity],cap,12) else 0. for identity in (selected,count_selected)]
                oracle=max([0.]+[(observed[row['candidate_id']]['baseline_cycles']-observed[row['candidate_id']]['candidate_cycles'])/
                    observed[row['candidate_id']]['baseline_cycles'] for row in public if b._feasible(observed[row['candidate_id']],cap,12)])
                for policy in GP_POLICIES:
                    trace=next(run for run in report['runs'] if (run['policy'],run['cap'],run['seed'])==(policy,cap,seed))
                    c.require(trace['events'][0]['candidate_id']==selected and
                        math.isclose(trace['events'][0]['score'][0],values[selected]['frozen_cost_score'],rel_tol=1e-14),
                        'Existing cached acquisition does not reproduce archived first choice')
                    choices.append(dict(cohort=phase,source=source,cap=cap,seed=seed,policy=policy,
                        actual_first_id=selected,count_only_first_id=count_selected,cost_changes_first_choice=selected!=count_selected,
                        frozen_actual_cycle_reduction=gains[0],count_only_actual_cycle_reduction=gains[1],
                        count_only_minus_frozen_actual_gain=gains[1]-gains[0],oracle_cycle_reduction=oracle,
                        frozen_actual_regret=oracle-gains[0],count_only_actual_regret=oracle-gains[1],
                        first_query_only=True,independent_case=False))
                    for row in public:
                        decomposed.append(dict(cohort=phase,source=source,cap=cap,seed=seed,policy=policy,
                            formula=row['formula'],**hardware[row['candidate_id']],
                            **values[row['candidate_id']],frozen_selected=row['candidate_id']==selected,
                            count_only_selected=row['candidate_id']==count_selected))
    # Cross only the two cached first-query factors, never refit or replay a variant.
    reversals=[]
    for source in TARGETS:
        old=next(case for case in cases if case['source']==source and case['cohort']=='old')
        new=next(case for case in cases if case['source']==source and case['cohort']=='expanded')
        c.require(old['public']==new['public'],'Fixed target public pool required')
        for cap in (32,64,128):
            for seed in range(5):
                estimates=[{row['candidate_id']:row for row in case['predictions'][seed]['hardware']} for case in (old,new)]
                values=[{row['candidate_id']:acquisition(row,h[row['candidate_id']],cap) for row in old['public']} for h in estimates]
                picks={}
                for feasibility_index,cost_index,name in ((0,0,'old'),(1,1,'expanded'),(0,1,'old_feasibility_new_duration'),(1,0,'new_feasibility_old_duration')):
                    scores={identity:dict(frozen_cost_score=value['count_only_score']*values[cost_index][identity]['expected_inverse_seconds'])
                            for identity,value in values[feasibility_index].items()}
                    picks[name]=choose(old['public'],scores,seed)
                reversals.append(dict(source=source,cap=cap,seed=seed,**picks,
                    changed=picks['old']!=picks['expanded'],
                    limitation='Factor crossing cannot isolate which added rows, input scaling, output scaling or kernel effects caused posterior changes.'))
    negative=read(ROOT/'results/2026-10-21-structure-feasibility-development/replay/report.json')
    pairs=rank_pairs(rows)
    result=dict(schema='isaforge-current-model-diagnosis-v1',scope='Consumed-data arithmetic and cached first-query counterfactual only',
        corpus=label_summary,source_counts=source_counts,source_folds=current_folds,ranking_pairs=pairs,
        total_within_context_pairs=sum(row['all_pairs'] for row in pairs),
        unequal_within_context_pairs=sum(row['unequal_pairs'] for row in pairs),
        headroom_by_context=headroom,pool_coverage=coverage,
        structural_aliases=aliases(rows,b.STRUCTURAL_COLUMNS),raw_ranking_feature_aliases=aliases(rows,FEATURE_COLUMNS),
        existing_descriptor_checks=descriptor_checks,frozen_cohorts=cohorts,
        cached_classifier_pair_checks=classifier_pairs,
        development_primary=expanded['primary'],development_query2=expanded['secondary_query2'],
        development_dct32=expanded['dct_tight_cap'],development_source_endpoints=expanded['endpoints'],
        fresh_source_endpoints=read(LIVE/'endpoints.json'),
        first_query_choices=choices,first_query_factor_crossings=reversals,
        unique_first_query_cases=len(choices)//2,cost_changed_unique_first_choices=sum(row['cost_changes_first_choice'] for row in choices)//2,
        count_only_first_query_outcomes=dict(improved=sum(row['count_only_minus_frozen_actual_gain']>0 for row in choices)//2,
            worsened=sum(row['count_only_minus_frozen_actual_gain']<0 for row in choices)//2,
            tied=sum(row['count_only_minus_frozen_actual_gain']==0 for row in choices)//2),
        unique_cases_note='135 source/cohort/cap/dependent-seed combinations; the two GP policies share their initial prediction. These are not135 independent sources.',
        preserved_negative_ordered_descriptor_diagnostics=negative['diagnostics'],
        new_model_fits=0,new_model_predictions=0,new_native_jobs=0,new_policy_trajectories=0,
        superiority_established=False,calibration_established=False)
    output.mkdir(parents=True)
    discovery_hashes={}
    for benchmark,payload in discoveries.items():
        name='inputs/discovery/'+corpus['contexts'][benchmark]['context_id']+'.json'
        destination=output/name;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(payload);digest=hashlib.sha256(payload).hexdigest()
        Path(str(destination)+'.sha256').write_text(digest+'\n');discovery_hashes[name]=digest
    c.seal(output/'diagnosis.json',result);c.seal(output/'first-query-decomposition.json',decomposed)
    for name,values in (('sources.csv',source_counts),('headroom.csv',headroom),('pool-coverage.csv',coverage),
        ('ranking-pairs.csv',pairs),('first-query-choices.csv',choices),('first-query-factor-crossings.csv',reversals),
        ('first-query-decomposition.csv',decomposed),('development-primary.csv',expanded['primary'])):_csv(output/name,values)
    sources=('scripts/diagnose_current_models.py','isaforge/structural_features_v3.py','isaforge/area_model_v2.py',
        'isaforge/budgeted_selection.py','isaforge/features.py','isaforge/speedup_corpus.py','isaforge/ranking.py',
        'scripts/diagnose_factorized_selection.py','scripts/export_guarded_corpus.py','scripts/report_budget_campaign.py',
        'scripts/reproduce_codesign.py')
    c.seal(output/'provenance.json',dict(input_bindings=bindings,source_bindings={name:c.sha(ROOT/name) for name in sources},
        original_discovery_bytes=discovery_hashes,
        source_unit='Entire source workload; compiler contexts grouped, five seeds dependent.',new_model_fits=0,new_native_jobs=0))
    text=['# Current model and data diagnosis',
        'Consumed-data arithmetic and existing cached predictions only: zero fits, new model predictions, native jobs or variant trajectories. '
        'The independent units are11 source workloads, with12 contexts; dependent seeds and candidate pairs are not new sources.',
        'Discovery inputs are authenticated from committed raw archives and matched to each frozen context’s expected hash. '
        'If original generated files exist, their bytes must agree exactly; absent generated roots require no native rebuild or metadata substitution. '
        'The original discovery JSON bytes are preserved under inputs/discovery/.',
        f"87 verified labels, three failures (two known validation failures, one unknown infrastructure outcome),90 charged attempts. "
        f"All87 cycle deltas match calibrated latency. Area feasibility counts at+32/+64/+128 are12/44/87; all87 measured designs fit the device and clear12MHz. "
        f"Routed minima range{label_summary['fmax_range_mhz'][0]:.6f}–{label_summary['fmax_range_mhz'][1]:.6f}MHz. "
        'The classifier therefore has no observed timing/device negative examples; cap replicas do not turn87 physical measurements into261 independent labels.',
        '## Pool coverage',
        table([['Source/context','Selected','Eligible calibrated','Coverage'],['---']*4]+[
            [row['benchmark'],row['measured_pool_size'],row['eligible_calibrated_formulas'],
             '' if row['eligible_pool_fraction'] is None else f"{100*row['eligible_pool_fraction']:.3f}%"] for row in coverage]),
        'Early AHA/CRC use top instruction-saving pools; subsequent pools span evenly spaced instruction-saving ranks rather than a simple top-K cutoff. '
        'Those are public merit-stratified convenience subsets, not random formulas. Outside-pool hardware labels are absent; no full-source hardware optimum or unbiased population error is identifiable. '
        'SHA contexts exclude earlier literal formulas and remain one source. Headroom is retained separately for every context/cap in headroom.csv.',
        '## Ranking and representation',
        f"The12 context groups provide319 unordered candidate pairs:294 unequal-performance pairs and25 ties. "
        'At+64,78 unequal pairs favor a faster but infeasible candidate over a slower feasible candidate; at+32 there are38. '
        'The pure speedup ranker is trained to favor these faster candidates. Its raw scores are not constraint-aware or magnitude-calibrated. '
        'Pair counts share rows and do not provide294 independent observations;198 of319 pairs come from the three twelve-candidate sources.',
        'The31 hardware features yield79 unique vectors among87 rows, five duplicate groups covering13 rows. Only one same-context duplicate group contains different formulas: '
        'NDES add(in0,slli(in1,2)) costs70LUT4 and saves3280cycles; slli(add(in0,in1),2) costs40 and saves720. '
        'At+64 their feasibility labels differ but the GP/classifier representation is identical. Full35 profile/structural features are unique across87 rows; this specific exact alias does not apply to the raw/ranking input.',
        'Existing formula-only v3 bit-cone descriptors separate the NDES pair and expose Expint’s cheap Boolean-conditioned constant expression. '
        'They collapse both DCT constant formulas to the same zero-LUT proxy despite measured integrated additions33 and15. '
        'The original31 DCT features differ in max_abs_constant16384vs4096; the cached classifier nevertheless gives both formulas identical member outputs at every cap/seed in both cohorts. This is a fitted-score equivalence, not an exact original-feature collision. '
        'This is representation diagnosis, not successful prediction. The earlier45-descriptor ablation remains negative: adaptive SHA optimum moves query2→3, so no descriptor bundle is promoted.',
        '## First-query acquisition and data transfer',
        f"Cached acquisition arithmetic exactly reproduces both GP policies’ first choice for all270 policy/cohort/source/cap/seed entries. "
        f"Removing inverse-time only changes{result['cost_changed_unique_first_choices']} of{result['unique_first_query_cases']} distinct initial cases: "
        'all five old-AHA seeds at each cap, and all five fresh-Expint seeds at+64. The other initial choices stay the same. '
        'Old AHA flips are extremely close scores for two equal-benefit formulas, both infeasible at+32/+64; exact choices are recorded without treating tiny floating differences as robust evidence. '
        f"Measured first-query outcomes improve in{result['count_only_first_query_outcomes']['improved']} cases, worsen in{result['count_only_first_query_outcomes']['worsened']} and tie in{result['count_only_first_query_outcomes']['tied']}; these dependent cases are descriptive, not an independent-source statistical test.",
        'Fresh Expint at+64 is a substantive flip: the frozen cost score chooses add(in0,slli(in1,3)) (+71LUT4, infeasible), while the same gain×predicted-feasibility without inverse-time chooses the actual11-cycle optimum (+17LUT4). '
        'This is a first-query retrospective counterfactual only; it is not a replayed policy, a whole-trajectory improvement or a wall-time result. '
        'Full decompositions retain mean/std area, timing and logtime, positive analytic speedup gain, Gaussian probability factors, fit rate, inverse time and scores.',
        'Expint’s initial area prediction for that infeasible query is40.002±0.214LUT4. Its nearest standardized history row is NDES slli(add(in0,in1),2), actual40LUT4, at distance2.699e-9. '
        'The only differing numeric feature is constant magnitude3vs2, divided by historical standard deviation370,562,752.59. '
        'Whole-family exclusion correctly removes add(input,shift(input,constant)) examples but retains the differently ordered graph. Missing operator order and raw-constant scaling make them effectively identical to this GP. '
        'Family exclusion should remain; the representation, not leakage protection, needs scrutiny.',
        'Expanded-history GP regression is concentrated on AHA: its old44-row vs expanded68-row post-family cohorts are each disjoint from the target source and excluded related families, yet expanding history loses its+64 oracle in the adaptive three-query runs. '
        'Cached factor crossings and input scale summaries expose changes without identifying a unique training-row/scaler cause. More data changes input standardization, posterior area/timing/time estimates and paid-update geometry together. '
        'Do not infer that source balancing or a kernel change will fix it without a single declared development test and later untouched-source validation.',
        '## Bounded next research questions',
        '1. Does matching acquisition to the primary charged-count objective prevent avoidable first-query losses? A fixed no-inverse-time ablation using unchanged models is justified by Expint’s observed cost flip; compare query-count and qualified-time endpoints separately, preserve every control, and validate on untouched useful-headroom sources. No new fit was made here.',
        '2. Can a small existing formula-only bit-demand/order representation distinguish the demonstrated hardware aliases without worsening transfers? Reuse the frozen descriptors before engineering graphs/embeddings, preserve the DCT counterexample and earlier negative ordered ablation, and avoid selecting feature variants on these consumed labels.',
        '3. Can new measurements add useful constraint and source diversity? Current+128 labels are all feasible, timing is far from12MHz, and several sources offer negligible headroom. Predeclare independent-source pools spanning boundary area/semantic cases and materially useful benefit. Do not post-curate outcomes or claim missing timing/device classes have been learned.',
        'All results remain consumed-data diagnostics. No policy/model promotion, calibrated confidence, independent-seed significance or total historical-cost advantage is established.']
    (output/'README.md').write_text('\n\n'.join(text)+'\n')
    c.seal(output/'manifest.json',{path.relative_to(output).as_posix():c.sha(path)
        for path in sorted(output.rglob('*')) if path.is_file()})
    return dict(successful_labels=87,sources=11,contexts=12,cached_first_choices=len(choices),
                unique_first_cases=len(choices)//2,cost_flips=result['cost_changed_unique_first_choices'],new_model_fits=0,new_native_jobs=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=OUTPUT)
    print(run(parser.parse_args().output))
