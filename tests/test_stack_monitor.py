"""Compile a tiny passive-monitor harness; no processor or workload jobs."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_stack_monitor_contract(tmp_path):
    compiler = shutil.which('c++')
    if compiler is None:
        pytest.skip('C++ compiler unavailable')
    source = tmp_path / 'monitor.cpp'
    source.write_text(r'''
#include "stack_monitor.hpp"
#include <cassert>
int main() {
    StackMonitor m(4224,4000,4352);
    assert(m.valid_configuration());
    m.observe_sp(0,0); assert(!m.initialized && m.checked_cycles==0);
    m.observe_sp(8192,4); m.observe_sp(4352,8);
    assert(m.initialized && m.min_sp==4352 && m.max_stack_bytes()==3840);
    assert(m.checked_cycles==2 && m.violations==0);
    m.observe_write(4000,15,12); m.observe_write(4220,15,12);
    m.observe_write(4352,15,12); m.observe_write(8188,15,12);
    m.observe_write(0x10000000,15,12);
    assert(m.violations==0);
    m.observe_write(4224,1,16);
    assert(m.violations==1 && m.first_pc==16 && m.first_address==4224);
    m.observe_sp(4351,20); m.observe_sp(8192,24);
    assert(m.violations==2 && m.first_pc==16 && m.min_sp==4351);
    StackMonitor bytes(4223,4001,4352);
    bytes.observe_write(4000,2,0); bytes.observe_write(4220,7,0);
    assert(bytes.violations==0);
    bytes.observe_write(4001,1,4); // bus word aligned: lane0 is4000
    assert(bytes.violations==1 && bytes.first_address==4000);
    bytes.observe_write(4220,8,8);
    assert(bytes.violations==2);
    StackMonitor high(4224,4000,4352);
    high.observe_sp(8192,0); high.observe_sp(8193,4);
    assert(high.violations==1);
    StackMonitor jump(4224,4000,4352);
    jump.observe_sp(8192,0); jump.observe_sp(32,4);
    jump.observe_sp(8192,8); assert(jump.violations==1);
    assert(!StackMonitor(4225,4000,4352).valid_configuration());
    assert(!StackMonitor(4224,4225,4352).valid_configuration());
    assert(!StackMonitor(4224,4000,4096).valid_configuration());
}
''')
    executable = tmp_path / 'monitor'
    subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                    '-I', str(ROOT / 'hardware'), str(source), '-o', str(executable)],
                   check=True, capture_output=True, text=True)
    subprocess.run([str(executable)], check=True, capture_output=True, text=True)
