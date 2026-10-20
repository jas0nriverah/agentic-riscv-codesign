import copy
import pytest
from isaforge.workload_probe import validate_baseline


def test_generic_benchmark_harness_requires_self_check_counters_and_no_custom_execution():
    raw={'status':0x600d600d,'words':[0x49534146,123,1000,200,1], 'fault':0,'partial_report_bits':0,
         'pcpi_handshakes':0,'pcpi_valid_cycles':0,'pcpi_wait_cycles':0}
    assert validate_baseline(raw)['cycles']==1000
    for key in ('fault','partial_report_bits','pcpi_handshakes','pcpi_valid_cycles','pcpi_wait_cycles'):
        bad=copy.deepcopy(raw);bad[key]+=1
        with pytest.raises(ValueError):validate_baseline(bad)
    for index in (0,2,3,4):
        bad=copy.deepcopy(raw);bad['words'][index]=0
        with pytest.raises(ValueError):validate_baseline(bad)
