from __future__ import annotations

import shutil
import subprocess

import pytest

from isaforge import codesign as c
from isaforge import strstr_workload as w


def test_pinned_source_and_original_offsets(tmp_path):
    record = w.source_record()
    assert record['commit'] == '049ded9f3aeb5591f553879d3a0376b8614e9422'
    assert record['source_sha256'] == w.SOURCE_SHA256

    compiler = shutil.which('cc')
    assert compiler is not None, 'C compiler required for the original-source host check'
    (tmp_path / 'support.h').write_text('')
    (tmp_path / 'check.c').write_text(r'''
extern char *text;
extern char *substr;
extern char *strstr(const char *, const char *);
extern int benchmark(void);
extern int verify_benchmark(int);
int main(void) {
  const int expected[] = {4, 17, 31, 36, 45, 50, 64};
  int found = 0, calls = 0;
  char *f = text;
  do {
    f = strstr(f + 1, substr);
    ++calls;
    if (f != 0) {
      if (found >= 7 || f - text != expected[found]) return 10;
      ++found;
    }
  } while (f != 0);
  if (found != 7 || calls != 8) return 11;
  if (!verify_benchmark(benchmark())) return 12;
  return 0;
}
''')
    binary = tmp_path / 'strstr-host-check'
    build = subprocess.run([compiler, '-std=gnu11', '-fno-builtin',
        '-I', str(tmp_path), str(c.ROOT / w.PROGRAM), str(tmp_path / 'check.c'),
        '-o', str(binary)], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(binary)], capture_output=True, text=True)
    assert run.returncode == 0, f'{run.returncode}: {run.stderr}'


def test_opportunity_gate_requires_one_candidate_to_meet_both_thresholds():
    def row(name, reduction, occurrences):
        return dict(name=name, runs=occurrences, latency_features=dict(
            estimated_cycle_reduction=reduction,
            baseline_instructions=1000,
            replacement_execution_fraction=occurrences / 1000,
            dynamic_custom_cycles=occurrences * 5,
            region_custom_instructions=occurrences))

    result = w.opportunity_gate([
        row('enough-cycles', .006, 9),
        row('enough-occurrences', .004, 10),
        row('both', .005, 10),
    ])
    assert result['passed'] is True
    assert result['qualifying_candidate_ids'] == ['both']
    assert result['target_candidate_attempts'] == 0
    assert result['measured_candidate_labels_used'] is False


def test_opportunity_gate_rejects_separate_candidates_that_split_thresholds():
    def row(name, reduction, occurrences):
        return dict(name=name, runs=occurrences, latency_features=dict(
            estimated_cycle_reduction=reduction,
            baseline_instructions=1000,
            replacement_execution_fraction=occurrences / 1000,
            dynamic_custom_cycles=occurrences * 5,
            region_custom_instructions=occurrences))

    result = w.opportunity_gate([row('a', .006, 9), row('b', .004, 10)])
    assert result['passed'] is False
    assert result['qualifying_candidate_ids'] == []


def test_dispatch_is_disabled_during_qualification():
    evaluator = object.__new__(w.Evaluator)
    with pytest.raises(ValueError, match='Candidate dispatch disabled'):
        w.Evaluator.measure(evaluator, 'candidate_00')


def test_registration_restores_shared_pipeline_globals_after_error():
    before = (w.bw.SOURCE, w.bw.WORKLOADS, w.bw.POOL_SIZE,
              w.g.SOURCE, w.g.WORKLOADS, w.g.POOL_SIZE)
    with pytest.raises(RuntimeError):
        with w.registration():
            assert w.g.WORKLOADS == {w.WORKLOAD: '../../beebs/strstr/libstrstr.c'}
            raise RuntimeError('exercise restoration')
    after = (w.bw.SOURCE, w.bw.WORKLOADS, w.bw.POOL_SIZE,
             w.g.SOURCE, w.g.WORKLOADS, w.g.POOL_SIZE)
    assert after == before
