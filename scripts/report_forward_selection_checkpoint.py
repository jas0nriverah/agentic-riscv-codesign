"""Report two sealed forward studies; never read in-progress native artifacts.

All plotting and summaries consume completed study packages only. Models and
controllers remain unchanged; this code performs no fitting or target jobs.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import statistics
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c
from scripts import audit_agent_episode_decisions as episode_audit
from scripts import export_incremental_selection_corpus as incremental_corpus

STUDIES = (
    ('countnegative','Countnegative',ROOT/'results/2026-10-28-countnegative-v2-selection-r1'),
    ('stringsearch','Stringsearch',ROOT/'results/2026-10-28-mibench-stringsearch-v2-selection-r1'),
)
OUTPUT = ROOT/'reports/2026-10-28-forward-selection-checkpoint'
CORPUS = ROOT/'results/2026-10-28-expanded-selection-corpus-r3'
CONVENTIONAL = {'frequency','merit','calibrated_latency','latency_cost_heuristic','random'}
LABELS = dict(frequency='Frequency',merit='Merit',calibrated_latency='Calibrated latency',
    latency_cost_heuristic='Latency / cost',random='Random',ranking='Pairwise XGBoost',
    raw_regression='Raw regression',normalized_xgb='Normalized XGBoost',
    feasible_benefit_xgb='Feasible-benefit XGBoost',factorized_feasibility_xgb='Factorized XGBoost',
    hybrid_gp_zero_shot='GP zero shot',hybrid_gp_adapt='GP paid updates',agent='LLM relay (one episode)')


def require(ok,message):
    c.require(bool(ok),message)


def pct(speedup):
    return 100*(1-1/speedup)


def load_studies(studies):
    # Refuse the checkpoint before BOTH final packages exist; no native-path IO.
    require(all((Path(root)/'manifest.json').is_file() for _,_,root in studies),
            'Both sealed final studies must exist before report generation')
    data = []
    for key,label,root in studies:
        root = Path(root).resolve()
        manifest = c.unseal(root/'manifest.json')
        for name,digest in manifest.items():
            path = (root/name).resolve()
            require(path.is_relative_to(root) and path.is_file() and c.sha(path) == digest,
                    'Sealed study artifact differs: '+str(path))
        report,audit = c.unseal(root/'study-report.json'),c.unseal(root/'native-audit.json')
        outcomes,policies = c.unseal(root/'outcomes.json'),c.unseal(root/'factorized-policy-report.json')
        require(report['historical_labels'] == 156,'Forward studies must retain frozen156-label history')
        require(audit['attempt_collection_complete'] and len(outcomes) == len(audit['public']) ==
                len(audit['pool_names']) == audit['charged_candidate_attempts'],
                'Complete physically charged pool required')
        require({r['candidate_id']:r for r in outcomes} == {r['candidate_id']:r for r in audit['outcomes']},
                'Final outcome projection differs from native audit')
        data.append(dict(key=key,label=label,root=root,report=report,audit=audit,outcomes=outcomes,
            policies=policies,outer_times=c.unseal(root/'outer-times.json'),manifest_sha256=c.sha(root/'manifest.json')))
    return data


def candidates(data):
    rows = []
    for study in data:
        names = {r['candidate_id']:name for r,name in zip(study['audit']['public'],study['audit']['pool_names'])}
        for row in study['outcomes']:
            success = row.get('status','success') == 'success'
            rows.append(dict(workload=study['key'],candidate=names[row['candidate_id']],
                candidate_id=row['candidate_id'],formula=row['formula'],status=row.get('status','success'),
                baseline_cycles=row.get('baseline_cycles'),cycles=row.get('candidate_cycles'),
                speedup=row.get('speedup'),cycle_reduction_percent=pct(row['speedup']) if success else None,
                delta_lut4=row.get('area_delta_lut4'),total_lut4=row.get('area'),
                min_fmax_mhz=row.get('routed_fmax_min_mhz'),correctness_verified=row.get('correctness_verified'),
                device_fits=row.get('device_fits'),reference_censored=row.get('reference_censored',False),
                paid_attempt_seconds=row['measurement_seconds'],
                enclosing_wrapper_seconds=study['outer_times'][row['candidate_id']],
                measured_by_agent=row['candidate_id'] in study['report']['agent']['attempted_ids']))
    return sorted(rows,key=lambda r:(r['workload'],r['candidate']))


def budgets(data):
    summaries,trajectories = [],[]
    for study in data:
        n = len(study['outcomes'])
        runs = study['policies']['runs']
        policies = sorted({r['policy'] for r in runs})
        require(len(policies) == 12,'All twelve existing control policies required')
        for cap in (32,64,128):
            for policy in policies:
                selected = [r for r in runs if r['policy'] == policy and r.get('cap',r.get('area_delta_lut4_cap')) == cap]
                require(len(selected) == 5 and len({r['seed'] for r in selected}) == 5,
                        'Five dependent seeded replay trajectories required')
                for requested in (1,2,3):
                    effective = min(requested,n)
                    points = []
                    for run in selected:
                        point = next((p for p in run['curve'] if p['budget'] == effective),None)
                        require(point is not None,'Missing effective-budget replay point')
                        points.append(point)
                        trajectories.append(dict(workload=study['key'],policy=policy,cap=cap,
                            seed=run['seed'],requested_budget=requested,effective_budget=effective,
                            alias=requested != effective,cycle_reduction_percent=pct(point['best_speedup']),
                            best_speedup=point['best_speedup'],selected_id=point.get('selected_id'),
                            attempted_ids=';'.join(point.get('attempted_ids',[])),
                            charged_attempt_seconds=point['target_measurement_seconds'],
                            enclosing_wrapper_seconds=point.get('target_outer_operation_seconds'),
                            scope='posthoc paid-prefix replay; seeds dependent'))
                    values = [pct(p['best_speedup']) for p in points]
                    summaries.append(dict(workload=study['key'],policy=policy,cap=cap,
                        requested_budget=requested,effective_budget=effective,alias=requested != effective,
                        dependent_seed_count=5,mean_reduction_percent=statistics.mean(values),
                        min_reduction_percent=min(values),max_reduction_percent=max(values),
                        mean_paid_attempt_seconds=statistics.mean(p['target_measurement_seconds'] for p in points),
                        mean_actual_attempts=statistics.mean(len(p.get('attempted_ids',[])) for p in points),
                        scope='five dependent seeded counterfactual replays on one measured pool'))
        # No relabelled agent curve at32/128: this episode ran only at64.
        for point in study['report']['agent']['budget_endpoints']:
            value = 100*point['best_so_far_cycle_reduction']
            requested = point['budget']
            paid_ids = point['attempted_candidate_ids']
            paid_costs = {r['candidate_id']:r for r in study['report']['agent']['target_attempt_costs']}
            times = [paid_costs[i]['measurement_seconds'] for i in paid_ids]
            outer = [paid_costs[i]['outer_operation_seconds'] for i in paid_ids]
            prefix_seconds = sum(times) if all(t is not None for t in times) else None
            prefix_outer = sum(outer) if all(t is not None for t in outer) else None
            trajectories.append(dict(workload=study['key'],policy='agent',cap=64,seed=0,
                requested_budget=requested,effective_budget=min(requested,n),alias=requested > n,
                cycle_reduction_percent=value,best_speedup=point['best_verified_feasible_speedup'],
                selected_id=point['selected_id'],attempted_ids=';'.join(paid_ids),
                charged_attempt_seconds=prefix_seconds,enclosing_wrapper_seconds=prefix_outer,
                scope='one live episode at +64 LUT4; early-stop carry-forward'))
            summaries.append(dict(workload=study['key'],policy='agent',cap=64,
                requested_budget=requested,effective_budget=min(requested,n),alias=requested > n,
                dependent_seed_count=1,mean_reduction_percent=value,min_reduction_percent=value,
                max_reduction_percent=value,
                mean_paid_attempt_seconds=prefix_seconds,
                mean_actual_attempts=point['actual_attempts_used'],
                scope='one live relay episode at +64 LUT4; early-stop result carried forward'))
    return summaries,trajectories


def residual_diagnostic(corpus):
    """Exact descriptive residual on authenticated rows; no fitted correction."""
    rows=[]
    for row in corpus['rows']:
        actual=row['baseline_cycles']-row['candidate_cycles']
        estimate=row['latency_features']['estimated_saved_cycles']
        rows.append(dict(candidate_id=row['candidate_id'],benchmark=row['benchmark'],
            workload_group=row['workload_group'],formula=row['formula'],
            baseline_cycles=row['baseline_cycles'],candidate_cycles=row['candidate_cycles'],
            measured_saved_cycles=actual,public_estimated_saved_cycles=estimate,
            residual_saved_cycles=actual-estimate))
    rows.sort(key=lambda r:(r['benchmark'],r['candidate_id']))
    return rows,dict(successful_rows=len(rows),
        nonzero_residual_rows=sum(r['residual_saved_cycles'] != 0 for r in rows),
        max_absolute_residual_cycles=max((abs(r['residual_saved_cycles']) for r in rows),default=0),
        rows_sha256=c.digest(rows),
        interpretation='Descriptive equality for these supported current fixed-latency patterns only; not a guarantee for arbitrary workloads, cores or instruction patterns.')


def csv_write(path,rows):
    with path.open('w',newline='') as handle:
        writer = csv.DictWriter(handle,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)


def save(fig,output,name):
    fig.savefig(output/(name+'.png'),dpi=220,facecolor='white')
    fig.savefig(output/(name+'.svg'),facecolor='white')
    svg = output/(name+'.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


def area_plot(data,rows,output):
    fig,axes = plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    for ax,study in zip(axes,data):
        selected = [r for r in rows if r['workload'] == study['key'] and r['status'] == 'success']
        ax.axvspan(0,32,color='#23836c',alpha=.06)
        ax.axvline(32,color='#23836c',linestyle=':',label='+32 LUT4')
        ax.axvline(64,color='#233c59',linestyle='--',label='+64 LUT4')
        seen_labels = set()
        for row in selected:
            feasible = row['correctness_verified'] and row['device_fits'] and row['min_fmax_mhz'] >= 12 and row['delta_lut4'] <= 64
            point_label = 'Eligible at +64' if feasible else 'Outside +64 constraints'
            ax.scatter([row['delta_lut4']],[row['cycle_reduction_percent']],s=80,
                c='#197b6b' if feasible else '#c16b3d',zorder=4,
                label=point_label if point_label not in seen_labels else None)
            seen_labels.add(point_label)
            ax.annotate(row['candidate'].replace('candidate_','C'),
                (row['delta_lut4'],row['cycle_reduction_percent']),xytext=(5,5),textcoords='offset points')
            if row['measured_by_agent']:
                ax.scatter([row['delta_lut4']],[row['cycle_reduction_percent']],s=190,
                    facecolors='none',edgecolors='#121d2a',linewidths=1.5,zorder=5)
        ax.axhline(0,color='#88929b',linewidth=.8)
        ax.set(title=study['label']+f" ({len(study['outcomes'])} candidates)",xlabel='Added LUT4 cells',
            ylabel='Measured whole-program cycle reduction (%)')
        ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False,fontsize=9)
    fig.suptitle('Measured area–benefit tradeoffs; outlined points were paid probes in the live episode at +64 LUT4')
    save(fig,output,'candidate-tradeoffs')


def budget_plot(data,rows,cap,output):
    fig,axes = plt.subplots(2,2,figsize=(13,9),sharex=True)
    colors = plt.get_cmap('tab10').colors
    for study,axisrow in zip(data,axes):
        for ax,conventional in zip(axisrow,(True,False)):
            keys = sorted({r['policy'] for r in rows if r['workload'] == study['key'] and
                r['cap'] == cap and r['policy'] != 'agent' and (r['policy'] in CONVENTIONAL) == conventional})
            for i,key in enumerate(keys):
                series = sorted((r for r in rows if r['workload'] == study['key'] and
                    r['policy'] == key and r['cap'] == cap),key=lambda r:r['requested_budget'])
                ax.plot([r['requested_budget'] for r in series],[r['mean_reduction_percent'] for r in series],
                    color=colors[i],marker=['o','s','^','D','v','P','X'][i%7],markersize=5,
                    linewidth=1.5,label=LABELS[key],alpha=.85)
            if cap == 64:
                series = sorted((r for r in rows if r['workload'] == study['key'] and
                    r['policy'] == 'agent'),key=lambda r:r['requested_budget'])
                ax.plot([r['requested_budget'] for r in series],[r['mean_reduction_percent'] for r in series],
                    color='#121d2a',marker='*',markerfacecolor='white',markersize=11,linewidth=2,
                    linestyle='--',label=LABELS['agent'],zorder=7)
                actual = [r for r in series if r['requested_budget'] <= study['report']['agent']['charged_attempts']]
                ax.scatter([r['requested_budget'] for r in actual],[r['mean_reduction_percent'] for r in actual],
                    color='#121d2a',marker='*',s=140,zorder=8)
            ax.set(title=study['label']+(' — conventional' if conventional else ' — learned'),
                xticks=[1,2,3],ylabel='Best feasible cycle reduction (%)',xlabel='Requested paid-evaluation budget cap')
            values = [r['mean_reduction_percent'] for r in rows if r['workload'] == study['key'] and r['cap'] == cap]
            upper = max(values)
            ax.set_ylim(0, upper*1.1 if upper > 0 else .001)
            if upper == 0:
                ax.set_yticks([0])
                ax.text(.5,.75,'No feasible improvement at this cap',transform=ax.transAxes,ha='center',fontsize=9,color='#58646f')
            eligible = [r['speedup'] for r in study['outcomes'] if r.get('status','success') == 'success' and
                r['correctness_verified'] and r['device_fits'] and r['area_delta_lut4'] <= cap and r['routed_fmax_min_mhz'] >= 12]
            ax.axhline(pct(max([1.]+eligible)),color='#84909b',linestyle=':',linewidth=1,
                label='Measured feasible oracle' if study['report']['complete_measured_reference_pool'] else 'Best verified lower bound')
            ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
            if len(study['outcomes']) == 2:
                ax.axvspan(2,3,color='#8f99a2',alpha=.07)
                ax.text(.98,.03,'B3 aliases B2: pool exhausted',transform=ax.transAxes,
                    ha='right',fontsize=8,color='#4e5965')
    for ax in axes[-1]:
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.20),ncol=2,frameon=False,fontsize=8)
    fig.suptitle(f'Best performance by budget | +{cap} LUT4, 12 MHz floor',fontsize=14)
    note = ('Relay is one episode at +64 LUT4; dashed carry-forward adds no probes.' if cap == 64 else
            'No agent episode at +32 LUT4 was run.')
    fig.text(.5,.935,'Control means: five dependent seeds on each pool. '+note,ha='center',fontsize=9)
    fig.subplots_adjust(top=.89,bottom=.22,hspace=.34,wspace=.21)
    save(fig,output,f'budget-plus{cap}')


def fmt(value,digits=6):
    if value is None:return '—'
    return f'{value:.{digits}f}' if isinstance(value,float) else str(value)


def build(studies=STUDIES,output=OUTPUT):
    data = load_studies(studies)
    rows = candidates(data);summary,trajectories = budgets(data)
    corpus,corpus_manifest = incremental_corpus.authenticate(CORPUS)
    residual_rows,residual = residual_diagnostic(corpus)
    output = Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    csv_write(output/'measured-candidates.csv',rows)
    csv_write(output/'analytic-latency-residuals.csv',residual_rows)
    residual['authenticated_corpus_manifest_sha256']=c.sha(CORPUS/'manifest.json')
    residual['authenticated_corpus_sha256']=c.sha(CORPUS/'corpus.json')
    residual['authenticator_sha256']=c.sha(incremental_corpus.__file__)
    c.seal(output/'analytic-latency-diagnostic.json',residual)
    csv_write(output/'matched-budget-summary.csv',summary)
    csv_write(output/'all-policy-trajectories.csv',trajectories)
    area_plot(data,rows,output)
    for cap in (64,32):budget_plot(data,summary,cap,output)
    episodes = {s['key']:episode_audit.build(s['root'],output/'episodes'/s['key']) for s in data}
    lines = ['# Forward selection checkpoint', '',
        'Two small measured pools under unchanged model recipes. No calibration promotion, model-recipe change or demonstrated general superiority. '
        'Both source-family-excluded forward studies fitted the same authenticated156-label history; later outcomes did not enter their fits.', '',
        '| Workload | Pool | Training rows /156 | Agent paid probes | Physical pool cost (s) | Enclosing wrapper (s) |',
        '|---|---:|---:|---:|---:|---:|']
    for s in data:
        r=s['report'];cost=r['actual_dataset_collection']
        lines.append('| '+' | '.join(map(str,[s['label'],len(s['outcomes']),r['family_filtered_training_rows'],
            r['agent']['charged_attempts'],fmt(cost['candidate_wall_seconds'],3),
            fmt(cost['candidate_outer_operation_seconds'],3)]))+' |')
    physical = sum(s['report']['actual_dataset_collection']['candidate_wall_seconds'] for s in data)
    lines += ['', f'Total physical paid-attempt cost for the two new pools: **{physical:.3f} seconds**.', '', 'Physical collection measured each pool member once. Replay prefix costs reuse those paid observations and are not additional physical experiments. '
        'Attempt-ledger, enclosing-wrapper and native-command durations overlap; do not sum them. '
        'Model-refit costs during paid-prefix replays do not demonstrate that new training improves decisions.', '',
        '![Area and benefit](candidate-tradeoffs.png)', '', '![Primary64-cap comparison](budget-plus64.png)', '',
        '![32-cap sensitivity](budget-plus32.png)', '',
        'The agent ran once at +64 LUT4; no agent results are claimed at +32 or +128. '
        'Each control mean aggregates five dependent policy seeds, with every trajectory retained in CSV. '
        'For Stringsearch, requested B3 has effective budget2 and aliases B2 after both candidates are exhausted. '
        'Early-stop relay choices carry forward without spending unused budget. Pool exhaustion is not evidence of sample efficiency.', '',
        '## Every measured candidate', '',
        '| Workload | Candidate | Cycles | Speedup | Reduction % | ΔLUT4 | Total LUT4 | Min MHz | Correct | Paid seconds |',
        '|---|---|---:|---:|---:|---:|---:|---:|---|---:|']
    for r in rows:
        lines.append('| '+' | '.join(fmt(r[k]) for k in ('workload','candidate','cycles','speedup',
            'cycle_reduction_percent','delta_lut4','total_lut4','min_fmax_mhz','correctness_verified','paid_attempt_seconds'))+' |')
    c32 = {r['policy']:r for r in summary if r['workload']=='countnegative' and r['cap']==32 and r['requested_budget']==2}
    lines += ['', f"At Countnegative +32/B2, factorized XGBoost mean reduction is {c32['factorized_feasibility_xgb']['mean_reduction_percent']:.6f}% versus merit {c32['merit']['mean_reduction_percent']:.6f}%. This sensitivity comparison does not override the primary +64 endpoint or establish general model superiority.", '', 'Formulas, identities, failures, censoring, device fit, wrapper cost and agent membership are in [measured-candidates.csv](measured-candidates.csv).', '']
    for s in data:
        for cap in (32,64,128):
            selected = [r for r in summary if r['workload'] == s['key'] and r['cap'] == cap]
            lines += [f"## {s['label']}: +{cap} LUT4 same-budget comparison", '',
                '| Policy | B1 reduction % | B2 reduction % | B3 reduction % | Scope |',
                '|---|---:|---:|---:|---|']
            for policy in sorted({r['policy'] for r in selected}):
                table={r['requested_budget']:r for r in selected if r['policy']==policy}
                values=[fmt(table[b]['mean_reduction_percent'])+(' (alias B2)' if table[b]['alias'] else '') for b in (1,2,3)]
                lines.append('| '+' | '.join([LABELS[policy],*values,
                    'One live relay at +64 LUT4' if policy=='agent' else 'Mean of five dependent replays'])+' |')
            lines += ['']
    lines += ['## Audited episode explanations', '']
    for s in data:
        e=episodes[s['key']]
        lines += [f"- [{s['label']}](episodes/{s['key']}/README.md): {e['charged_probes']} paid probes, "
            f"{e['unused_budget']} unused attempts, {e['model_decisions']} model decisions. Logged reasons are unverified notes; public advice is independently reconstructed."]
    lines += ['', '## Analytic latency residual diagnostic', '',
        f"The authenticated r3 corpus has **{residual['successful_rows']}** verified successful outcomes. Actual simulated cycle savings (`baseline_cycles - candidate_cycles`) equal public prelabel `estimated_saved_cycles` exactly in **{residual['successful_rows']-residual['nonzero_residual_rows']}** rows; nonzero residual rows: **{residual['nonzero_residual_rows']}**, maximum absolute residual: **{residual['max_absolute_residual_cycles']} cycles**.", '',
        'For these supported current fixed-latency patterns, learned benefit regression has no demonstrated cycle-savings residual to correct. '
        'These observations locate the practical selection bottleneck in hardware feasibility and search; they do not demonstrate that performance ML improves the analytic estimate. '
        'Target cycles come from verified processor simulations; latency features were public before candidate labels. '
        'This descriptive exactness does not extend automatically to arbitrary workloads, cores or instruction patterns.', '',
        'Every row and source identity is retained in [analytic-latency-residuals.csv](analytic-latency-residuals.csv); canonical row digest and authenticated source bindings are in [analytic-latency-diagnostic.json](analytic-latency-diagnostic.json).', '',
        '## Next blocker', '',
        'These two low-cardinality pools do not establish that ML or the relay beats strong heuristics, nor that an expanded fit improves selection. '
        'A useful next test needs a separately frozen source/family holdout with enough alternatives to avoid near-exhaustive budgets, '
        'and matched controls under the same budget. Any proposed model or reviewer change needs a prospective release before new labels. '
        'Individual-instruction results also leave jointly measured instruction-set composition unresolved.', '',
        '## Reproduction', '', '```sh', '.venv/bin/python scripts/report_forward_selection_checkpoint.py', '```', '',
        'Only sealed final study packages are decoded. No in-progress native artifacts, fits or hardware evaluations are consumed or launched. '
        'Full per-seed B1/B2/B3 trajectories at all three caps: [all-policy-trajectories.csv](all-policy-trajectories.csv).']
    (output/'README.md').write_text('\n'.join(lines)+'\n')
    c.seal(output/'provenance.json',dict(script_sha256=c.sha(__file__),
        episode_auditor_sha256=c.sha(episode_audit.__file__),matplotlib=matplotlib.__version__,
        corpus_manifest_sha256=c.sha(CORPUS/'manifest.json'),corpus_authenticator_sha256=c.sha(incremental_corpus.__file__),
        residual_rows_sha256=residual['rows_sha256'],
        input_manifests={s['root'].relative_to(ROOT).as_posix():s['manifest_sha256'] for s in data},
        physical_paid_attempt_seconds=sum(s['report']['actual_dataset_collection']['candidate_wall_seconds'] for s in data),
        models_changed=False,new_native_jobs=0,agent_caps=[64],control_caps=[32,64,128],
        artifacts={p.relative_to(output).as_posix():c.sha(p) for p in output.rglob('*') if p.is_file() and
                   p.name not in ('provenance.json','provenance.json.sha256')}))
    return dict(workloads=len(data),candidates=len(rows),summary_rows=len(summary),output=str(output))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    print(build(output=args.output))
