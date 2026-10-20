"""Compiler/input adapter invariants; measurements remain in raw snapshots."""
import pytest

from isaforge import codesign as c
from isaforge import compact_workload as compact
from isaforge import workload_experiment as w


def test_compact_flags_keep_isa_and_restore_on_failure():
    original = w.FLAGS
    with pytest.raises(RuntimeError):
        with compact.compiler_flags():
            assert '-Os' in w.FLAGS and '-O2' not in w.FLAGS
            assert '-march=rv32i_zicsr' in w.FLAGS and '-mabi=ilp32' in w.FLAGS
            raise RuntimeError('fixture')
    assert w.FLAGS is original


def test_compact_check_rejects_a_wrong_compiler_invocation(tmp_path):
    plan = {'build_variant': {'required_entrypoint': compact.SOURCE},
            'compiler_flags': list(compact.FLAGS),
            'source_bindings': {compact.SOURCE: c.sha(compact.__file__)},
            'tools': {'gcc': {'path': '/fixture/gcc'}}}
    c.seal(tmp_path/'plan.json', plan)
    c.seal(tmp_path/'commands.json', [{'argv': ['/fixture/gcc', *compact.FLAGS]}])
    compact.check(tmp_path)
    c.seal(tmp_path/'commands.json', [{'argv': ['/fixture/gcc', *w.FLAGS]}])
    with pytest.raises(ValueError, match='Compiler invocation'):
        compact.check(tmp_path)
