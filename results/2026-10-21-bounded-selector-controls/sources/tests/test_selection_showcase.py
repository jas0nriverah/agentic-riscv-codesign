"""Current showcase binds real frozen evidence, without refitting or native jobs."""
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from isaforge import codesign as c
from scripts import build_selection_showcase as showcase


@pytest.fixture(scope='module')
def evidence():
    return showcase.load_evidence()


def snapshot(tmp_path):
    for name in (showcase.CORPUS, *showcase.SELECTIONS):
        shutil.copytree(c.ROOT/name, tmp_path/name)
    return tmp_path


def test_real_counts_and_preserved_failures(evidence):
    assert len(evidence['candidates']) == 36
    assert sum(r['status'] == 'success' for r in evidence['candidates']) == 33
    assert len({r['workload_group'] for r in evidence['candidates']}) == 6
    assert len(evidence['endpoints']) == 1350
    failures = [r for r in evidence['candidates'] if r['status'] != 'success']
    assert len(failures) == 3
    assert sum(bool(r['reference_censored']) for r in failures) == 1
    assert all(r['speedup'] is None for r in failures)
    assert any('unresolved' in r['reference'] for r in evidence['comparisons'])


def test_sha_heuristic_win_and_baseline_fallback(evidence):
    points = [r for r in evidence['endpoints'] if r['workload'] == 'embench-nettle-sha256'
              and r['cap'] == 64 and r['budget'] == 1]
    heuristic = [r for r in points if r['policy'] == 'latency_cost_heuristic']
    learned = [r for r in points if r['policy'] == 'hybrid_gp_adapt']
    assert len(heuristic) == len(learned) == 5
    assert all(r['best_speedup'] == pytest.approx(1.0213846648661133) for r in heuristic)
    assert all(r['best_speedup'] == 1 and r['selected_id'] is None for r in learned)
    assert all(r['target_measurement_seconds'] > 0 for r in learned)


def test_shareable_exports_and_sql_queries(tmp_path, evidence):
    output = showcase.build(tmp_path/'demo')
    page = (output/'index.html').read_text()
    payload = page.split('<script id="evidence" type="application/json">')[1].split('</script>')[0]
    assert json.loads(payload) == evidence
    assert 'Consumed development replay' in page
    assert 'not new hardware measurements' in page
    assert 'https://' not in page and '<script src=' not in page
    with sqlite3.connect(output/'evidence.sqlite') as db:
        assert db.execute('SELECT COUNT(*) FROM candidates').fetchone()[0] == 36
        assert db.execute('SELECT COUNT(*) FROM endpoints').fetchone()[0] == 1350
        assert db.execute('SELECT COUNT(*) FROM candidates WHERE status="success"').fetchone()[0] == 33
        for query in (output/'queries.sql').read_text().split(';'):
            if query.strip():
                db.execute(query).fetchall()
    assert len((output/'verified-labels.csv').read_text().splitlines()) == 34
    with pytest.raises(ValueError, match='fresh output'):
        showcase.build(output)


def test_rejects_changed_corpus_artifact(tmp_path):
    root = snapshot(tmp_path)
    (root/showcase.CORPUS/'verified-labels.csv').write_text('tampered')
    with pytest.raises(ValueError, match='checksum'):
        showcase.load_evidence(root)


def test_rejects_report_protocol_binding_even_when_resealed(tmp_path):
    root = snapshot(tmp_path)
    path = root/showcase.SELECTIONS[0]/'report.json'
    report = c.unseal(path); report['protocol_sha256'] = '0'*64
    c.seal(path, report)
    with pytest.raises(ValueError, match='Report/protocol'):
        showcase.load_evidence(root)


def test_rejects_unpaid_final_choice_even_when_resealed(tmp_path):
    root = snapshot(tmp_path)
    path = root/showcase.SELECTIONS[2]/'report.json'
    report = c.unseal(path)
    report['runs'][0]['curve'][0]['selected_id'] = 'unpaid-candidate'
    c.seal(path, report)
    with pytest.raises(ValueError, match='paid feasible'):
        showcase.load_evidence(root)


def test_rejects_artifact_path_escape(tmp_path):
    outside = tmp_path/'outside'; outside.write_text('test')
    folder = tmp_path/'folder'; folder.mkdir()
    with pytest.raises(ValueError, match='escapes'):
        showcase.checked_files(folder, {'../outside': c.sha(outside)})
