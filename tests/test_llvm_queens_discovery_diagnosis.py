"""Read-only checks for the preserved Queens discovery diagnosis."""
import hashlib
import json

from scripts import diagnose_llvm_queens_discovery as diagnosis


def test_pinned_queens_discovery_is_reproduced_as_source_rejection():
    report = diagnosis.calculate()
    assert report['qualification']['original_status'] == 'failed'
    assert report['qualification']['failed_phase'] == 'discover'
    assert report['qualification']['target_candidate_attempts'] == 0
    assert report['workload']['fixed_solves'] == 5000
    assert report['workload']['upstream_and_adapter_self_check_passed'] is True
    assert report['workload']['instrumented_discovery_cycles'] == 465269849
    assert report['extraction']['raw_formula_count'] == 3
    assert report['extraction']['calibrated_executable_formula_count'] == 3
    assert report['extraction']['required_pool_size'] == 12
    assert report['opportunity']['maximum_estimated_saved_cycles'] == 600
    assert report['opportunity']['joint_gate_passed'] is False
    assert report['classification'].startswith('source_rejected_')
    assert all(row['historical_operation_family_overlap'] in (True, False)
               for row in report['extraction']['candidate_rows'])


def test_queens_discovery_report_artifacts_are_deterministic_and_hash_bound():
    content = diagnosis.render(diagnosis.calculate())
    manifest = json.loads(content['manifest.json'])
    assert set(manifest) == {'diagnosis.json', 'README.md'}
    for name, expected in manifest.items():
        assert hashlib.sha256(content[name]).hexdigest() == expected
    assert content['manifest.json.sha256'].decode().strip() == hashlib.sha256(
        content['manifest.json']).hexdigest()
    assert content == diagnosis.render(diagnosis.calculate())
