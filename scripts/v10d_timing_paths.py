"""Conservative attribution of native routed paths to the fixed timing boundary.

No native tools run here. The mapped boundary uses the separately reviewed
sequential checker. Packed identity follows exact verified signal aliases and
actual FF/IO/global-buffer wiring, never packed cell-name substrings. This is
attribution of a reported full-harness path, not arithmetic-only delay recovery.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

import prepare_v10_timing as sequential


def need(value, message):
    if not value:
        raise ValueError(message)


def bit(bits):
    need(type(bits) is list and len(bits) == 1 and type(bits[0]) is int and bits[0] >= 0,
         'Defined scalar packed wire required')
    return bits[0]


def one(items, message):
    need(len(items) == 1, message)
    return items[0]


def resolve_boundary(mapped, packed, report):
    """Return the verified132FF packed correspondence, or raise ValueError.

    Exact aliases are first checked against the mapped FF Q wires. nextpnr
    scalarizes vectors and replaces output_q[0] with the output IO's D_OUT_0.
    That one alias is recovered through PACKAGE_PIN connectivity.
    """
    network = sequential.SequentialNetlist(mapped)
    source = mapped['modules']['timing_top']
    definitions = []
    for group, stem in [('launch', 'launch_q'), ('result', 'result_q'), ('output', 'output_q')]:
        names = sequential.GROUPS[group]
        wires = source['netnames'][stem]['bits']
        need(len(wires) == len(names), 'Mapped boundary alias width differs')
        for index, name in enumerate(names):
            need(type(wires[index]) is int and wires[index] == network.flops[name]['Q'],
                 'Mapped alias does not identify verified boundary FF')
            definitions.append((name, group, index, f'{stem}[{index}]'))
    for name, alias in [('serial_sample0', 'serial_s0'), ('serial_sample1', 'serial_s1'),
                        ('capture_sample0', 'capture_s0'), ('capture_sample1', 'capture_s1')]:
        need(bit(source['netnames'][alias]['bits']) == network.flops[name]['Q'],
             'Mapped sampling alias differs')
        definitions.append((name, 'sampling', sequential.GROUPS['sampling'].index(name), alias))

    need(type(packed.get('modules')) is dict and len(packed['modules']) == 1,
         'Exactly one packed module required')
    module = next(iter(packed['modules'].values()))
    cells, ports, nets = module['cells'], module['ports'], module['netnames']
    need(all(cell['type'] in ('ICESTORM_LC', 'SB_IO', 'SB_GB') for cell in cells.values()),
         'Unexpected packed primitive prevents boundary attribution')
    need(set(ports) == {'clk', 'serial_in', 'capture', 'serial_out'}
         and all(p['direction'] == ('output' if name == 'serial_out' else 'input')
                 for name, p in ports.items()), 'Exact scalar wrapper ports required')
    for port in ports.values():
        bit(port['bits'])
    ios = {name: cell for name, cell in cells.items() if cell['type'] == 'SB_IO'}
    need(len(ios) == 4, 'Exactly four packed IOs required')
    def io(port):
        return one([(name, cell) for name, cell in ios.items()
                    if cell['connections']['PACKAGE_PIN'] == ports[port]['bits']],
                   'Unique package IO correspondence required')
    need(len({io(port)[0] for port in ports}) == 4, 'Package IO aliases collide')
    clock_input = bit(io('clk')[1]['connections']['D_IN_0'])
    buffers = [(name, cell) for name, cell in cells.items() if cell['type'] == 'SB_GB']
    gb_name, gb = one(buffers, 'Exactly one packed global buffer required')
    need(gb['connections']['USER_SIGNAL_TO_GLOBAL_BUFFER'] == [clock_input],
         'Global clock must directly follow wrapper clock IO')
    clock = bit(gb['connections']['GLOBAL_BUFFER_OUTPUT'])
    need(type(report.get('fmax')) is dict and len(report['fmax']) == 1,
         'Exactly one reported clock required')
    clock_name = next(iter(report['fmax']))
    need(type(clock_name) is str and bit(nets[clock_name]['bits']) == clock,
         'Reported clock does not identify packed wrapper clock')
    lcs = {name: cell for name, cell in cells.items() if cell['type'] == 'ICESTORM_LC'}
    need(all(cell['parameters']['DFF_ENABLE'] in ('0', '1') for cell in lcs.values()),
         'Unknown packed FF enable representation')
    flops = {name: cell for name, cell in lcs.items() if cell['parameters']['DFF_ENABLE'] == '1'}
    need(len(flops) == 132 and all(cell['connections']['CLK'] == [clock]
         and cell['parameters']['NEG_CLK'] == '0' for cell in flops.values()),
         'Exactly132 rising-edge FFs on the wrapper clock required')
    outputs = {}
    for name, cell in flops.items():
        wire = bit(cell['connections']['O'])
        need(wire not in outputs, 'Packed boundary FF outputs collide')
        outputs[wire] = name
    boundary = {}
    for original, group, index, alias in definitions:
        if group == 'output' and index == 0:
            wire = bit(io('serial_out')[1]['connections']['D_OUT_0'])
            need(alias not in nets or bit(nets[alias]['bits']) == wire,
                 'Retained output0 alias contradicts actual output IO driver')
            correspondence = 'serial_out PACKAGE_PIN -> SB_IO.D_OUT_0'
        else:
            wire = bit(nets[alias]['bits'])
            correspondence = alias
        need(wire in outputs and outputs[wire] not in boundary,
             'Exact boundary alias needs a distinct packed FF O driver')
        boundary[outputs[wire]] = {'mapped_cell': original, 'group': group, 'index': index,
                                  'wire': wire, 'correspondence': correspondence}
    need(set(boundary) == set(flops), 'Exact132 aliases must cover every packed FF')
    digest = hashlib.sha256(json.dumps(boundary, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'boundary': boundary, 'boundary_sha256': digest, 'clock': clock_name,
            'clock_wire': clock, 'global_buffer_cell': gb_name}


def _checked_path(module, path):
    cells, nets = module['cells'], module['netnames']
    segments = path['path']
    need(type(segments) is list and len(segments) >= 2, 'Complete critical-path segments required')
    for segment in segments:
        need(type(segment['delay']) in (int, float) and math.isfinite(segment['delay'])
             and segment['delay'] >= 0, 'Finite nonnegative native segment delay required')
        need(segment['type'] in ('clk-to-q', 'routing', 'logic', 'setup', 'source'),
             'Unrecognized native path segment kind')
        for side in ('from', 'to'):
            endpoint = segment[side]
            cell = cells[endpoint['cell']]
            bit(cell['connections'][endpoint['port']])
            location = re.fullmatch(r'X(\d+)/Y(\d+)/(?:lc\d+|io\d+|gb)', cell['attributes']['NEXTPNR_BEL'])
            need(location is not None and type(endpoint['loc']) is list
                 and all(type(value) is int for value in endpoint['loc'])
                 and endpoint['loc'] == [int(location[1]), int(location[2])],
                 'Native path location disagrees with packed BEL')
        start, end = segment['from'], segment['to']
        if segment['type'] == 'routing':
            need(cells[start['cell']]['connections'][start['port']]
                 == cells[end['cell']]['connections'][end['port']]
                 == nets[segment['net']]['bits'], 'Native routing endpoints/net are disconnected')
        else:
            need(start['cell'] == end['cell'], 'Native internal segment crosses cells')
    need(all(a['to'] == b['from'] for a, b in zip(segments, segments[1:])),
         'Native critical-path segments are discontinuous')
    return segments


def classify_paths(mapped, packed, report):
    """Conservatively classify the sole reported synchronous critical path.

    Unresolved identity/clock/segment evidence returns unknown, never a guessed
    arithmetic endpoint. Full-harness Fmax validity is a separate audit check.
    """
    scope = 'Reported full-harness clock path only; no arithmetic-only delay or Fmax recovery.'
    counts = {'mapped_ff_count': None, 'packed_ff_count': None}
    try:
        counts['mapped_ff_count'] = len(sequential.SequentialNetlist(mapped).flops)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        pass
    try:
        need(len(packed['modules']) == 1, 'One packed module required for count')
        cells = next(iter(packed['modules'].values()))['cells']
        need(all(cell['type'] in ('ICESTORM_LC', 'SB_IO', 'SB_GB') for cell in cells.values()), 'Unknown packed primitive')
        lcs = [cell for cell in cells.values() if cell['type'] == 'ICESTORM_LC']
        need(all(cell['parameters']['DFF_ENABLE'] in ('0', '1') for cell in lcs), 'Unknown packed FF enable')
        counts['packed_ff_count'] = sum(cell['parameters']['DFF_ENABLE'] == '1' for cell in lcs)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        pass
    try:
        resolved = resolve_boundary(mapped, packed, report)
        event = 'posedge ' + resolved['clock']
        path = one([path for path in report.get('critical_paths', [])
                    if path.get('from') == event and path.get('to') == event],
                   'Exactly one synchronous critical path required')
        module = next(iter(packed['modules'].values()))
        segments = _checked_path(module, path)
        need(segments[0]['type'] == 'clk-to-q' and segments[-1]['type'] == 'setup',
             'Native synchronous path must run clk-to-q through setup')
        first, last = segments[0]['from'], segments[-1]['to']
        need(segments[0]['from'] == segments[0]['to'] and segments[-1]['from'] == segments[-1]['to']
             and first['port'] == 'O' and last['port'] in ('I0', 'I1', 'I2', 'I3'),
             'Unresolved packed register endpoint ports')
        need(first['cell'] in resolved['boundary'] and last['cell'] in resolved['boundary'],
             'Critical endpoint lacks verified boundary identity')
        start = {'cell': first['cell'], **resolved['boundary'][first['cell']]}
        end = {'cell': last['cell'], **resolved['boundary'][last['cell']]}
        classification = 'datapath-boundary' if start['group'] == 'launch' and end['group'] == 'result' else 'wrapper-boundary'
        return {'classification': classification, 'clock': resolved['clock'], 'start': start, 'end': end,
                'boundary_ff_count': 132, 'boundary_sha256': resolved['boundary_sha256'], **counts, 'scope': scope}
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        return {'classification': 'unknown', 'reason': str(error), **counts, 'scope': scope}
