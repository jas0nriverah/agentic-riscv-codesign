"""Pinned-source, ABI, group and scoped evaluator registration contracts."""
import copy
import pytest
from isaforge import beebs_workload as w, codesign as c, guarded_workload as g


def test_exact_pinned_benchmark_and_external_warmup():
    source = c.ROOT/w.PROGRAM
    assert source.stat().st_size == 13463
    assert c.sha(source) == w.PROGRAM_SHA256
    assert 'for (i=0; i<64; ++i)' in source.read_text()
    assert 'seed = 1;' in source.read_text()
    assert 'warm_caches' not in source.read_text()
    assert 'void warm_caches(int heat) { (void)heat; }' in w.WARMUP
    assert (c.ROOT/w.LICENSE).is_file()


def test_scoped_registration_restores_globals_and_nested_calls():
    before = g.SOURCE, g.WORKLOADS, w.evidence._public
    with pytest.raises(RuntimeError):
        with w.registration():
            assert g.SOURCE == w.SOURCE
            assert set(g.WORKLOADS) == {'jfdctint'}
            with w.registration(): assert w.evidence._public == w.public_projection
            raise RuntimeError('test')
    assert (g.SOURCE, g.WORKLOADS, w.evidence._public) == before


def test_public_projection_has_beebs_source_identity(monkeypatch):
    original = [{'benchmark': 'embench-jfdctint:context', 'candidate_id': 'candidate'}]
    monkeypatch.setattr(w, 'PUBLIC', lambda *args: copy.deepcopy(original))
    result = w.public_projection(None, {'context_id': 'context'}, None, None, None)
    assert result[0]['benchmark'] == 'beebs-jfdctint:context'
    assert original[0]['benchmark'] == 'embench-jfdctint:context'
    assert result[0]['candidate_id'] == 'candidate'


def test_new_plan_binds_source_adapter_and_rejects_old_entrypoint():
    root = c.ROOT/'generated/beebs-jfdctint-2026-10-21-r2'
    if not root.exists(): pytest.skip('native qualification context unavailable')
    plan = c.unseal(root/'plan.json')
    w.check_plan(plan)
    with pytest.raises(ValueError): g.check_plan(plan)
    assert plan['workload_group'] == 'beebs-jfdctint'
    assert plan['memory_partition'] == w.PARTITION
    assert plan['inputs']['program.c'] == w.PROGRAM_SHA256
    assert (root/'inputs/embench_firmware.c').read_text() == (c.ROOT/'hardware/embench_firmware.c').read_text()+w.WARMUP
    assert all('..' not in key for key in plan['source_bindings'])
    assert all(name in plan['source_bindings'] for name in (w.SOURCE,w.GUARDED_SOURCE,w.PROGRAM,w.LICENSE))


def test_qualified_public_context_and_strict_audit_share_beebs_group():
    root = c.ROOT/'generated/beebs-jfdctint-2026-10-21-r2'
    if not (root/'evaluation-protocol.json').exists(): pytest.skip('native baseline unavailable')
    rows, context, before = (c.unseal(root/name) for name in ('public.json','context.json','before.json'))
    assert {row['benchmark'].split(':')[0] for row in rows} == {'beebs-jfdctint'}
    assert context['workload_group'] == before['workload'] == 'beebs-jfdctint'
    audited = w.audit(root)
    assert audited['public'] == rows
    assert audited['charged_candidate_attempts'] + len(audited['unattempted']) == 6
    assert all(record['status'] == 'success' for record in
               (c.unseal(path) for path in (root/'outer-timing').glob('*.json'))
               if record['command'] in ('prepare','discover','baseline','public','freeze'))
