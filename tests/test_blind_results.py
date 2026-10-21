"""Blind campaign presenters use measured gains, independent sources and all costs."""
import copy
import csv
import hashlib
import io
import json
import statistics
import tarfile

import pytest

from isaforge import codesign as c
from scripts import report_blind_campaign as report
from scripts import export_blind_corpus as corpus


def fixture_report(*, reference=2.0, censored=False):
    """Small arithmetic fixture only; no hardware or learned result is claimed."""
    outcomes = [dict(candidate_id=str(index), speedup=speedup, device_fits=True,
        area_delta_lut4=10, routed_fmax_min_mhz=20, measurement_seconds=index+1)
        for index, speedup in enumerate((reference, 1.0, 1.0))]
    runs = []
    for policy in report.POLICY_LABELS:
        for cap in report.e.AREA_CAPS:
            for seed in report.e.SEEDS:
                order = [0, 1, 2] if seed % 2 == 0 else [1, 0, 2]
                curve = []
                for budget in report.e.BUDGETS:
                    attempted = [outcomes[index] for index in order[:budget]]
                    curve.append(dict(budget=budget, attempted_ids=[row['candidate_id'] for row in attempted],
                        best_speedup=max([1.0]+[row['speedup'] for row in attempted]),
                        target_measurement_seconds=sum(row['measurement_seconds'] for row in attempted),
                        target_outer_operation_seconds=2*sum(row['measurement_seconds'] for row in attempted),
                        known_infeasible_attempts=0, unknown_attempts=0))
                runs.append(dict(policy=policy, cap=cap, seed=seed, curve=curve))
    return dict(runs=runs, reference_censored=censored), outcomes


def test_cycle_gain_is_saved_cycles_not_raw_speedup():
    frozen, labels = fixture_report()
    rows = report.endpoints_for_source('source-a', frozen, labels)
    assert len(rows) == 12*3*3
    first = next(row for row in rows if row['budget'] == 1)
    assert first['mean_best_verified_speedup'] == pytest.approx(1.6)
    assert first['mean_verified_cycle_reduction'] == pytest.approx(.3)
    assert first['mean_verified_cycle_reduction'] != report.cycle_reduction(first['mean_best_verified_speedup'])
    assert first['mean_cycle_reduction_regret'] == pytest.approx(.2)
    assert first['mean_oracle_cycle_reduction_fraction'] == pytest.approx(.6)
    assert first['at_least_90_percent_oracle_gain_runs'] == 3
    assert all(row['mean_charged_attempts'] == row['budget'] for row in rows)


def test_baseline_only_never_receives_oracle_gain_or_ninety_percent_success():
    frozen, labels = fixture_report(reference=1.0)
    rows = report.endpoints_for_source('baseline-source', frozen, labels)
    assert all(row['mean_verified_cycle_reduction'] == row['mean_cycle_reduction_regret'] == 0 for row in rows)
    assert all(row['mean_oracle_cycle_reduction_fraction'] is None and
        row['at_least_90_percent_oracle_gain_runs'] == row['improving_reference_hits'] == 0 for row in rows)
    macro = report.source_macro(rows)
    assert all(row['baseline_only_sources'] == 1 and row['oracle_gain_fraction_source_count'] == 0 and
               row['mean_oracle_cycle_reduction_fraction'] is None for row in macro)


def test_macro_gives_sources_equal_weight_and_censorship_is_visible():
    frozen, labels = fixture_report()
    first = report.endpoints_for_source('source-a', frozen, labels)
    frozen, labels = fixture_report(reference=1.25, censored=True)
    second = report.endpoints_for_source('source-b', frozen, labels)
    # Duplicate irrelevant pool candidates must not make a source receive greater macro weight.
    assert all(row['regret_is_lower_bound'] and not row['reference_complete'] for row in second)
    macro = report.source_macro(first+second)
    assert len(macro) == 108
    for row in macro:
        matching = [value for value in first+second
                    if (value['policy'], value['cap'], value['budget']) == (row['policy'], row['cap'], row['budget'])]
        assert row['source_count'] == 2 and row['censored_sources'] == 1
        assert row['mean_verified_cycle_reduction'] == statistics.mean(value['mean_verified_cycle_reduction'] for value in matching)
    with pytest.raises(ValueError, match='One endpoint per independent source'):
        report.source_macro(first+second+[first[0]])


@pytest.mark.parametrize('mutation', ['seed', 'policy', 'queries', 'identity', 'benefit', 'cost'])
def test_incomplete_or_forged_paid_policy_grid_is_rejected(mutation):
    frozen, labels = fixture_report()
    if mutation == 'seed': frozen['runs'][0]['seed'] = frozen['runs'][1]['seed']
    if mutation == 'policy': frozen['runs'].pop()
    if mutation == 'queries': frozen['runs'][0]['curve'].pop()
    if mutation == 'identity': frozen['runs'][0]['curve'][0]['attempted_ids'] = ['not-a-candidate']
    if mutation == 'benefit': frozen['runs'][0]['curve'][0]['best_speedup'] = 3
    if mutation == 'cost': frozen['runs'][0]['curve'][0]['target_measurement_seconds'] = 0
    with pytest.raises(ValueError): report.endpoints_for_source('source', frozen, labels)


def fake_target():
    """Borrow schema fields from historical evidence, replacing only fixture identity."""
    old = c.unseal(corpus.PREVIOUS/'corpus.json')
    template = copy.deepcopy(old['rows'][0])
    group = 'beebs-fixture-only'
    template.update(candidate_id='fixture-success', benchmark=group+':fixture-context', workload_group=group)
    template['status'] = 'success'
    public = report.b.public_rows([{key: template[key] for key in report.b.PUBLIC_KEYS}])[0]
    failed = {key: copy.deepcopy(value) for key, value in public.items()}
    failed.update(candidate_id='fixture-failure', status='failed', measurement_seconds=7.0,
        failure_class='infrastructure_unknown', reference_censored=True, error='fixture infrastructure failure')
    failed_public = report.b.public_rows([{key: failed[key] for key in report.b.PUBLIC_KEYS}])[0]
    audit = dict(charged_candidate_attempts=2, candidate_wall_seconds=template['measurement_seconds']+7,
        native_command_seconds=1.0, native_command_count=1, baseline_wall_seconds=2.0, baseline_record_seconds=1.0)
    return dict(workload=group, audit=audit, outcomes=[template, failed], public=[public, failed_public],
        context=dict(workload_group=group, context_id='fixture-context'),
        outer_times={'fixture-success': template['measurement_seconds']+2, 'fixture-failure': 9})


def test_export_preserves_old45_and_three_failures_charges_unknown_without_labels(tmp_path, monkeypatch):
    old = c.unseal(corpus.PREVIOUS/'corpus.json')
    target = fake_target()
    monkeypatch.setattr(corpus, 'load_targets', lambda *_: [target])
    monkeypatch.setattr(corpus, 'collection_costs', lambda *_: dict(manifest_sha256='fixture-only'))
    # The loader is replaced only for this schema/accounting fixture.
    campaign, prereg = tmp_path/'campaign', tmp_path/'prereg'
    campaign.mkdir(); prereg.mkdir()
    c.seal(campaign/'manifest.json', {}); c.seal(prereg/'manifest.json', {})
    c.seal(prereg/'cohort.json', dict(qualification=dict(setup_subprocess_seconds=12.0),
        historical_costs=dict(source_corpus_sha256=c.sha(corpus.PREVIOUS/'corpus.json'))))
    output = tmp_path/'corpus'
    value = corpus.export(corpus.PREVIOUS, campaign, prereg, output)
    assert value['rows'][:45] == old['rows']
    assert value['failed_attempts'][:3] == old['failed_attempts']
    assert value['successful_labels'] == 46 and len(value['failed_attempts']) == 4
    assert value['total_candidate_attempts'] == 50
    failure = value['failed_attempts'][-1]
    assert failure['correctness_verified'] is None and failure['reference_censored'] is True
    assert not {'speedup', 'candidate_cycles', 'area_delta_lut4'} & set(failure)
    assert value['total_candidate_attempt_wall_seconds'] == old['total_candidate_attempt_wall_seconds']+target['audit']['candidate_wall_seconds']
    assert value['contexts'][target['public'][0]['benchmark']]['workload_group'] == target['workload']
    assert len(value['contexts']) == 9 and len(value['independent_workload_groups']) == 8
    with pytest.raises(ValueError, match='Fresh corpus'):
        corpus.export(corpus.PREVIOUS, campaign, prereg, output)


def test_bounded_regular_packed_measurement_reader_checks_resources_and_hashes(tmp_path):
    record = dict(resources=dict(lut4_count=123, flip_flop_count=45, carry_count=6),
                  routes=[dict(seed=seed, limiting_internal_fmax_mhz=30-seed) for seed in (1, 2, 3)])
    payload = json.dumps(record).encode()
    name = 'measurements/baseline/measurement.json'
    with tarfile.open(tmp_path/'raw.tar.gz', 'w:gz') as archive:
        member = tarfile.TarInfo(name); member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    manifest = dict(archive='raw.tar.gz', sha256=c.sha(tmp_path/'raw.tar.gz'),
        files=[dict(path=name, bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())])
    c.seal(tmp_path/'archive-manifest.json', manifest)
    records = report.packed_measurements(tmp_path, ['baseline'])
    resources = report._record_resources(records['baseline'])
    assert resources == dict(total_lut4=123, flip_flops=45, carry_cells=6, min_fmax_mhz=27, route_seed_count=3)
    manifest['files'][0]['sha256'] = '0'*64
    c.seal(tmp_path/'archive-manifest.json', manifest)
    with pytest.raises(ValueError, match='measurement checksum'):
        report.packed_measurements(tmp_path, ['baseline'])
    record['routes'][0]['seed'] = 2
    with pytest.raises(ValueError, match='three unique'):
        report._record_resources(record)


def test_presenter_consumes_real_packed_dct_schema_without_fit_or_native_jobs(tmp_path, monkeypatch):
    """Consumed DCT is an integration schema fixture, not a new blind result."""
    campaign = report.ROOT/'results/2026-10-21-jfdctint-campaign'
    if not campaign.exists(): pytest.skip('consumed DCT archive unavailable')
    selection = report.ROOT/'results/2026-10-21-jfdctint-selection'
    audit = c.unseal(campaign/'audit.json')
    frozen = c.unseal(selection/'report.json')
    protocol = c.unseal(selection/'protocol.json')
    old = c.unseal(corpus.PREVIOUS/'corpus.json')
    protocol['cost_provenance']['historical_training_available'] = dict(successful_labels=45,
        failed_attempts=3, total_candidate_attempts=48,
        total_candidate_wall_seconds=old['total_candidate_attempt_wall_seconds'])
    target = dict(workload='beebs-jfdctint', native=campaign/'native', selection=selection,
        audit=audit, outcomes=audit['outcomes'], report=frozen, protocol=protocol,
        outer_times=c.unseal(campaign/'outer-times.json'))
    second = dict(target, workload='fixture-second-source')
    monkeypatch.setattr(report, 'load_targets', lambda *_: [target, second])
    monkeypatch.setattr(report, 'collection_costs', lambda *_: dict(
        complete_subprocess_seconds=2*sum(target['outer_times'].values())+10,
        successful=12, failed=0, manifest_sha256='fixture-only'))
    prereg = tmp_path/'prereg'; prereg.mkdir()
    c.seal(prereg/'cohort.json', dict(qualification=dict(setup_subprocess_seconds=20), freeze_outer_operation_seconds=5))
    c.seal(prereg/'manifest.json', {})
    result = report.build(campaign, prereg, tmp_path/'report')
    assert result == dict(sources=2, candidates=12, policies=12, endpoint_summaries=216,
                         macro_endpoints=108, new_model_fits=0, new_native_jobs=0)
    costs = c.unseal(tmp_path/'report/costs.json')
    assert costs['total_candidate_attempts'] == 60
    assert costs['total_candidate_attempt_wall_seconds'] == old['total_candidate_attempt_wall_seconds']+2*audit['candidate_wall_seconds']
    assert costs['new_candidate_wall_seconds'] == 2*audit['candidate_wall_seconds']
    assert costs['collection']['complete_subprocess_seconds'] != costs['new_candidate_wall_seconds']
    assert costs['qualification']['setup_subprocess_seconds'] == 20
    with (tmp_path/'report/candidates.csv').open(newline='') as stream: rows = list(csv.DictReader(stream))
    assert all(row['route_seed_count'] == '3' for row in rows)
    assert all(float(row['saved_cycle_residual']) == 0 for row in rows)


def test_primary_source_comparisons_keep_losses_and_ties_without_significance_claims():
    frozen, labels = fixture_report()
    first = report.endpoints_for_source('source-a', frozen, labels)
    second = copy.deepcopy(first)
    for row in second:
        row['workload_group'] = 'source-b'
        if row['policy'] == report.e.POLICY and row['budget'] == 3:
            row['mean_verified_cycle_reduction'] = 0
    rows, counts = report.primary_comparisons(first+second)
    assert len(rows) == 8
    assert all(row['win'] == 0 and row['tie'] == row['loss'] == 1 for row in counts)
    assert all(row['significance_established'] is False for row in rows+counts)


def test_complete_subprocess_costs_bind_failed_attempt_and_enclose_ledger(tmp_path):
    target = fake_target()
    target['audit']['pool_names'] = ['candidate_00', 'candidate_01']
    collection, campaign, prereg = [tmp_path/name for name in ('collection', 'campaign', 'prereg')]
    for path in (collection, campaign, prereg): path.mkdir()
    c.seal(campaign/'release.json', dict(fixture=True))
    c.seal(campaign/'provenance.json', dict(prelabel_commit='fixture-commit'))
    history = dict(successful_labels=45, failed_attempts=3, total_candidate_attempts=48)
    cohort = dict(historical_costs=history,
        targets={target['workload']: dict(native_order=target['audit']['pool_names'])})
    c.seal(prereg/'cohort.json', cohort)
    c.seal(prereg/'manifest.json', {})
    c.seal(collection/'protocol.json', dict(schema='isaforge-blind-collection-v1',
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'), release_sha256=c.sha(campaign/'release.json'),
        prelabel_commit='fixture-commit', source_sha256=c.sha(report.ROOT/'scripts/collect_blind_campaign.py'),
        workers=1, attempts_per_candidate=1, order={target['workload']: target['audit']['pool_names']}))
    commands = [dict(workload_group=target['workload'], candidate=name,
        elapsed_seconds=target['outer_times'][row['candidate_id']]+1,
        ledger_seconds=row['measurement_seconds'], attempt_status=row.get('status', 'success'),
        returncode=0 if row.get('status', 'success') == 'success' else 1)
        for name, row in zip(target['audit']['pool_names'], target['outcomes'])]
    c.seal(collection/'commands.json', commands)
    c.seal(collection/'summary.json', dict(attempted_candidates=2, successful=1, failed=1,
        complete_subprocess_seconds=sum(row['elapsed_seconds'] for row in commands),
        ledger_seconds=sum(row['ledger_seconds'] for row in commands), historical_costs=history))
    def seal_manifest():
        c.seal(collection/'manifest.json', {path.name: c.sha(path) for path in collection.iterdir()
            if path.name not in ('manifest.json', 'manifest.json.sha256')})
    seal_manifest()
    value = report.collection_costs(collection, campaign, prereg, [target])
    assert value['failed'] == 1 and value['attempted_candidates'] == 2
    assert value['complete_subprocess_seconds'] > value['ledger_seconds']
    assert value['candidates'][1]['candidate_id'] == 'fixture-failure'
    commands[1]['ledger_seconds'] = 0
    c.seal(collection/'commands.json', commands); seal_manifest()
    with pytest.raises(ValueError, match='Collection status/timer'):
        report.collection_costs(collection, campaign, prereg, [target])


def test_completed_campaign_report_and_export_when_available(tmp_path):
    if not (report.CAMPAIGN/'manifest.json').exists(): pytest.skip('blind native campaign not collected yet')
    result = report.build(report.CAMPAIGN, report.PREREG, tmp_path/'report')
    assert result['policies'] == 12 and result['macro_endpoints'] == 108
    assert result['endpoint_summaries'] == result['sources']*108
    with (tmp_path/'report/candidates.csv').open(newline='') as stream: rows = list(csv.DictReader(stream))
    assert len(rows) == result['candidates']
    assert all(row['route_seed_count'] == '3' for row in rows if row['status'] == 'verified')
    value = corpus.export(corpus.PREVIOUS, report.CAMPAIGN, report.PREREG, tmp_path/'corpus')
    assert value['total_candidate_attempts'] == 48+result['candidates']
    assert value['successful_labels']+len(value['failed_attempts']) == value['total_candidate_attempts']
