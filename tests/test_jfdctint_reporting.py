"""Derived tables and the expanded corpus retain measured evidence and costs."""
import csv
import pytest

from isaforge import codesign as c
from scripts import report_jfdctint as report
from scripts import export_jfdctint_corpus as corpus


@pytest.fixture
def evidence():
    if not report.CAMPAIGN.exists(): pytest.skip('completed DCT campaign not yet collected')
    return report.CAMPAIGN, report.SELECTION, report.PREREG


def test_all_twelve_policy_tables_and_measured_residuals(evidence, tmp_path):
    output = tmp_path/'report'
    result = report.build(*evidence, output)
    assert result['policies'] == 12 and result['endpoint_summaries'] == 108 and result['candidates'] == 6
    with (output/'candidates.csv').open(newline='') as stream: rows = list(csv.DictReader(stream))
    assert len(rows) == 6 and all(float(row['saved_cycle_residual']) == 0 for row in rows)
    assert all(float(row['outer_operation_seconds']) >= float(row['charged_wall_seconds']) for row in rows)
    summary = c.unseal(output/'summary.json')
    assert summary['superiority_established'] is False
    assert all(row['calibrated'] is False for row in summary['feasibility'])
    with pytest.raises(ValueError, match='Fresh report'): report.build(*evidence, output)


def test_new_source_export_preserves_historical_rows_failures_and_costs(evidence, tmp_path):
    campaign, _, prereg = evidence
    output = tmp_path/'corpus'
    old = c.unseal(corpus.PREVIOUS/'corpus.json')
    result = corpus.export(corpus.PREVIOUS, campaign, prereg, output)
    assert result['rows'][:39] == old['rows']
    assert result['failed_attempts'] == old['failed_attempts']
    assert result['successful_labels'] == 45 and result['total_candidate_attempts'] == 48
    assert len(result['independent_workload_groups']) == 7 and len(result['contexts']) == 8
    new = result['rows'][39:]
    assert {row['workload_group'] for row in new} == {'beebs-jfdctint'}
    assert all(row['correctness_verified'] and row['outer_operation_seconds'] >= row['measurement_seconds'] for row in new)
    assert result['total_candidate_attempt_wall_seconds'] == old['total_candidate_attempt_wall_seconds']+result['new_candidate_wall_seconds']
    assert sum(row.get('reference_censored') is True for row in result['failed_attempts']) == 1
    with pytest.raises(ValueError, match='Fresh corpus'): corpus.export(corpus.PREVIOUS, campaign, prereg, output)
