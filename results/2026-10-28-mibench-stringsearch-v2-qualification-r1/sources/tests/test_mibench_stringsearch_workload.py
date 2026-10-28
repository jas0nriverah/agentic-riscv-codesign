from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

from isaforge import codesign as c
from isaforge import mibench_stringsearch_workload as workload


def _c_array(source: str, name: str) -> list[str]:
    match = re.search(
        r'char\s*\*\s*' + re.escape(name) + r'\[\]\s*=\s*\{(.*?)\};',
        source, re.S)
    assert match is not None
    return [ast.literal_eval(token) for token in
            re.findall(r'"(?:\\.|[^"\\])*"', match.group(1))]


def test_pinned_source_and_python_oracle_match_all_literal_cases():
    record = workload.source_record()
    source = (c.ROOT / workload.PROGRAM).read_text()
    needles = _c_array(source, 'find_strings')
    haystacks = _c_array(source, 'search_strings')
    assert len(needles) == len(haystacks) == 57
    offsets = [text.find(needle) for needle, text in zip(needles, haystacks)]
    assert sum(offset >= 0 for offset in offsets) == 29
    assert sum(offset < 0 for offset in offsets) == 28
    assert hashlib.sha256(','.join(map(str, offsets)).encode()).hexdigest() == \
        record['oracle_offsets_sha256']


def test_host_adapter_records_and_verifies_every_search_result(tmp_path: Path):
    compiler = shutil.which('cc') or shutil.which('clang')
    assert compiler is not None
    runner = tmp_path / 'host_runner.c'
    runner.write_text('''
extern int benchmark(void);
extern void initialise_benchmark(void);
extern void warm_caches(int);
extern int verify_benchmark(int);
int main(void) {
    initialise_benchmark();
    warm_caches(1);
    int result = benchmark();
    return verify_benchmark(result) ? 0 : 1;
}
''')
    executable = tmp_path / 'mibench-stringsearch-host'
    subprocess.run([compiler, '-std=gnu11', '-O2', '-fno-builtin',
        str(c.ROOT / workload.ADAPTER), str(runner), '-o', str(executable)],
        check=True, capture_output=True, text=True)
    subprocess.run([str(executable)], check=True, capture_output=True, text=True)


def test_plan_registration_restores_shared_pipeline_globals():
    from isaforge import guarded_workload as guarded
    before = (guarded.SOURCE, guarded.WORKLOADS, guarded.POOL_SIZE,
              guarded.NATIVE_LIMITS, guarded.q.WORKLOADS,
              guarded.q.POOL_SIZE, guarded.q.bounded.POOL_SIZE,
              guarded.q.bounded.campaign.POOL_SIZE)
    with workload.registration():
        assert guarded.SOURCE == workload.SOURCE
        assert guarded.WORKLOADS == workload.WORKLOADS
        assert guarded.POOL_SIZE == 12
        assert guarded.q.WORKLOADS == workload.WORKLOADS
        assert guarded.q.POOL_SIZE == 12
    after = (guarded.SOURCE, guarded.WORKLOADS, guarded.POOL_SIZE,
             guarded.NATIVE_LIMITS, guarded.q.WORKLOADS,
             guarded.q.POOL_SIZE, guarded.q.bounded.POOL_SIZE,
             guarded.q.bounded.campaign.POOL_SIZE)
    assert after == before
