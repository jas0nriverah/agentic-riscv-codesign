"""Conservative RV32 assembly fusion using the existing dataflow extractor.

Labels let the linker relocate branches/data after instructions are removed.
Only complete, single-word assembly statements are eligible; pseudo-op pairs,
opaque operations, linker-generated code, and cross-block fusions are excluded.
"""
from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path
import random
import re
import sys

from .codesign import require
from .features import extract_features

SRC = Path(__file__).resolve().parents[1] / 'src'
# These are the repository's original extractor and block interpreter, not a
# second extraction algorithm. Their scripts use sibling absolute imports.
def _load(name):
    spec = importlib.util.spec_from_file_location(name, SRC / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

tracing = _load('tracing')
discovery = _load('candidates')
interpreter = _load('verify_candidate_fusions')


def mark_assembly(source):
    """Mark source statements without changing a single emitted byte."""
    lines, sites, function = [], [], None
    functions = set(re.findall(r'^\s*\.type\s+(\S+),\s*@function', source, re.M))
    for number, line in enumerate(source.splitlines()):
        stripped = line.strip()
        if stripped.endswith(':') and stripped[:-1] in functions:
            function = stripped[:-1]
        if re.match(r'^\s*\.size\s+' + re.escape(function or '!') + r'\s*,', line):
            function = None
        if function and stripped and not stripped.startswith(('.', '#')) and not stripped.endswith(':'):
            require(';' not in line, 'Multiple assembly statements on one line are unsupported')
            site = len(sites)
            sites.append({'site': site, 'source_line': number, 'function': function, 'assembly': line})
            lines += [f'__isaforge_begin_{site}:', line, f'__isaforge_end_{site}:']
        else:
            lines.append(line)
    require(sites, 'No function instructions found')
    return '\n'.join(lines) + '\n', sites


def map_sites(sites, symbols):
    addresses = {row.split()[-1]: int(row.split()[0], 16)
                 for row in symbols.splitlines() if len(row.split()) == 3}
    result = {}
    for site in sites:
        begin, end = (addresses.get(f'__isaforge_{kind}_{site["site"]}') for kind in ('begin', 'end'))
        if begin is not None and end == begin + 4:
            require(begin not in result, 'Duplicate instruction mapping')
            result[begin] = site
    return result


def read_program(disassembly):
    program, symbol = {}, None
    for line in disassembly.splitlines():
        heading = re.match(r'^[0-9a-f]+ <(.+)>:', line)
        if heading:
            symbol = heading[1]
        match = re.match(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s', line)
        if match:
            op, rd, rs1, rs2, imm = tracing.decode(int(match[2], 16))
            program[int(match[1], 16)] = dict(op=op, rd=rd, rs1=rs1, rs2=rs2,
                                             imm=imm, symbol=symbol, raw=int(match[2], 16))
    require(program, 'Empty disassembly')
    return program


def inputs_for(members, block, program):
    sources, names = discovery.findSources(block, program), {}
    def visit(member):
        for reg, writer in sources[member]:
            if writer in members:
                visit(writer)
            else:
                names.setdefault((reg, writer), len(names))
    visit(max(members))
    require(len(names) <= 2, 'More than two input values')
    return [reg for reg, _ in names]


def extract(program, profile, site_map, pool_size=6):
    """Freeze the highest-merit executable formulas before any hardware labels."""
    require(type(pool_size) is int and 1 <= pool_size <= 30, 'Invalid pool size')
    runs = Counter({int(k): v for k, v in profile['region_counts'].items()})
    starts = set(profile['block_starts'])
    require(sum(runs.values()) + 1 == profile['words'][3], 'Profile/counter mismatch')
    # CSR observations have opaque effects in the old decoder. Isolate them.
    for pc, instruction in program.items():
        if instruction['op'] == 'unknown':
            starts.update((pc, pc + 4))
        if pc in site_map:
            instruction['symbol'] = site_map[pc]['function']
    blocks = {block[0]: block for block in discovery.findBlocks(program, starts)}
    raw = discovery.extractCandidates(program, runs, starts, maxSize=4)
    executable, rejections = [], Counter()
    for row in raw:
        occurrences = []
        for occurrence in row['occurrences']:
            pcs = [int(pc, 16) for pc in occurrence['pcs']]
            block = blocks[int(occurrence['blockStart'], 16)]
            if not all(pc in site_map for pc in pcs):
                rejections['not_whole_source_statements'] += 1
                continue
            # Keep independent verification strict; unsupported blocks are not
            # silently counted as checked.
            if any(program[pc]['op'] == 'unknown' for pc in block):
                rejections['opaque_block'] += 1
                continue
            members = {block.index(pc) for pc in pcs}
            inputs = inputs_for(members, block, program)
            occurrences.append({**occurrence, 'sites': [site_map[pc]['site'] for pc in pcs],
                                'inputs': inputs, 'output': program[pcs[-1]]['rd']})
        used, chosen = set(), []
        for occurrence in sorted(occurrences, key=lambda o: (-o['size'], o['pcs'])):
            if used.isdisjoint(occurrence['pcs']):
                chosen.append(occurrence)
                used.update(occurrence['pcs'])
        if not chosen:
            continue
        runs_sum = sum(o['blockRuns'] for o in chosen)
        size = min(o['size'] for o in chosen)
        saving = sum((o['size'] - 1) * o['blockRuns'] for o in chosen)
        features = extract_features({**row, 'size': size, 'runs': runs_sum, 'places': len(chosen),
                                     'saved': (size - 1) * runs_sum,
                                     'savedPercent': 100 * (size - 1) * runs_sum / sum(runs.values())})
        executable.append({'formula': row['formula'], 'occurrences': chosen, 'features': features,
                           'expected_instruction_reduction': saving,
                           'region_custom_instructions': runs_sum,
                           'total_custom_instructions': sum(profile['total_counts'].get(str(int(o['pcs'][-1], 16)), 0)
                                                            for o in chosen)})
    executable.sort(key=lambda row: (-row['expected_instruction_reduction'], row['formula']))
    for index, row in enumerate(executable):
        row['name'] = f'candidate_{index:02d}'
    return {'raw_formula_count': len(raw), 'executable_formula_count': len(executable),
            'rejected_occurrences': dict(rejections), 'block_starts': sorted(starts),
            'pool_rule': 'Top overlap-safe dynamic instruction savings, then formula; max four operations; frozen before candidate cycles/area.',
            'pool': executable[:pool_size], 'executable_candidates': executable}


def lower(marked, candidate):
    removed, replacements = set(), {}
    for occurrence in candidate['occurrences']:
        sites = occurrence['sites']
        require(removed.isdisjoint(sites), 'Overlapping occurrences')
        removed.update(sites)
        inputs = occurrence['inputs'] + [0, 0]
        replacements[sites[-1]] = f'\t.insn r 0x0b, 0, 1, x{occurrence["output"]}, x{inputs[0]}, x{inputs[1]}'
    lines, current = [], None
    seen = set()
    for line in marked.splitlines():
        begin = re.fullmatch(r'__isaforge_begin_(\d+):', line)
        end = re.fullmatch(r'__isaforge_end_(\d+):', line)
        if begin:
            current = int(begin[1]); seen.add(current); lines.append(line)
        elif end:
            require(current == int(end[1]), 'Malformed statement markers')
            current = None; lines.append(line)
        elif current in removed:
            if current in replacements:
                lines.append(replacements.pop(current))
        else:
            lines.append(line)
    require(removed <= seen and not replacements, 'Missing replacement sites')
    return '\n'.join(lines) + '\n'


def verify_lowering(candidate, program, starts, vectors=64):
    blocks = {b[0]: b for b in discovery.findBlocks(program, starts)}
    groups = {}
    for occurrence in candidate['occurrences']:
        start = int(occurrence['blockStart'], 16)
        block = blocks[start]
        members = {block.index(int(pc, 16)) for pc in occurrence['pcs']}
        sources = discovery.findSources(block, program)
        require(discovery.followsRules(members, block, program, sources, discovery.findLastWrites(block, program)), 'Illegal fusion')
        require(discovery.describe(members, block, program, sources) == candidate['formula'], 'Formula differs from original instructions')
        require(inputs_for(members, block, program) == occurrence['inputs'], 'Input binding changed')
        require(program[block[max(members)]]['rd'] == occurrence['output'], 'Output binding changed')
        groups.setdefault(start, []).append({'members': members, 'formula': candidate['formula']})
    rng, comparisons = random.Random(20261019), 0
    for start, replacements in groups.items():
        block = blocks[start]
        require(all(program[pc]['op'] != 'unknown' for pc in block), 'Unsupported block')
        for _ in range(vectors):
            state = {reg: rng.getrandbits(32) if reg else 0 for reg in range(32)}
            original = interpreter.execute(block, program, state.copy(), [])
            fused = interpreter.execute(block, program, state.copy(), replacements)
            require(original == fused, 'Fusion changes architectural state/memory/control')
            comparisons += 1
    return {'passed': True, 'blocks': len(groups), 'comparisons': comparisons,
            'scope': 'Sampled full-register, memory and branch equivalence per block, including jointly lowered occurrences; not a universal program proof.'}
