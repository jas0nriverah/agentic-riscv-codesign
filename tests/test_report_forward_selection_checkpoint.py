"""Checks on authenticated measured checkpoints, without fitting or dispatch."""
import copy
from scripts import report_forward_selection_checkpoint as report


def test_authenticated_r3_cycle_savings_match_public_latency_estimates_exactly():
    corpus,_=report.incremental_corpus.authenticate(report.CORPUS)
    rows,diagnostic=report.residual_diagnostic(corpus)
    assert len(rows)==diagnostic['successful_rows']==162
    assert diagnostic['nonzero_residual_rows']==0
    assert diagnostic['max_absolute_residual_cycles']==0
    assert diagnostic['rows_sha256']==report.c.digest(rows)
    changed=copy.deepcopy(corpus)
    changed['rows'][0]['latency_features']['estimated_saved_cycles']+=1
    _,altered=report.residual_diagnostic(changed)
    assert altered['nonzero_residual_rows']==1
    assert altered['max_absolute_residual_cycles']==1


def test_all_controls_and_effective_budget_aliases_preserve_agent64_only():
    data=report.load_studies(report.STUDIES)
    summaries,trajectories=report.budgets(data)
    assert len(summaries)==222 and len(trajectories)==1086
    assert {r['cap'] for r in summaries if r['policy']=='agent'}=={64}
    assert {r['cap'] for r in trajectories if r['policy']=='agent'}=={64}
    for workload in ('countnegative','stringsearch'):
        for cap in (32,64,128):
            assert len({r['policy'] for r in summaries if r['workload']==workload and
                        r['cap']==cap and r['policy']!='agent'})==12
    for row in (r for r in summaries if r['workload']=='stringsearch' and r['requested_budget']==3):
        earlier=next(r for r in summaries if r['workload']==row['workload'] and
                     r['cap']==row['cap'] and r['policy']==row['policy'] and r['requested_budget']==2)
        assert row['effective_budget']==2 and row['alias']
        assert row['mean_reduction_percent']==earlier['mean_reduction_percent']
        assert row['mean_paid_attempt_seconds']==earlier['mean_paid_attempt_seconds']
