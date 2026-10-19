"""Label-free original/normalized generic graphs for a new V5 experiment.

Generic Yosys synthesis deliberately omits ABC and target technology mapping.
Word-level add/sub/multiply descriptors are carry-work proxies, never measured
dedicated carry-cell counts. Retained paths are relative to each cache entry.
No labels, training, FPGA mapping or old-artifact changes are performed here.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import threading
import time

import numpy as np

from .area_model_v4 import GRAPH_COLUMNS, graph_features
from .features import parse_formula
from .masterrtl_baseline import tool_identity
from .rtl import generate_rtl

SCHEMA = 'isaforge-v5-generic-graph-v1'
PIPELINE = ('read_verilog candidate.v\n'
            'hierarchy -check -top candidate\nproc\nflatten\nopt\n'
            'write_json word.json\n'
            'synth -top candidate -noabc\ncheck -assert\n'
            'write_json graph.json\n')
PRIMITIVES = {'$_AND_': ('A', 'B'), '$_OR_': ('A', 'B'),
              '$_XOR_': ('A', 'B'), '$_NOT_': ('A',),
              '$_MUX_': ('A', 'B', 'S')}
WORD_COLUMNS = ('word_cell_count', 'word_add_count', 'word_sub_count',
                'word_mul_count', 'word_arithmetic_output_bits',
                'word_carry_span_proxy', 'word_carry_span_max_proxy',
                'word_multiply_operand_bits', 'word_multiply_partial_terms_proxy',
                'word_signed_arithmetic_count')
BIT_COLUMNS = tuple('primitive_' + k for k in ('and', 'or', 'xor', 'not', 'mux'))
CHANNEL_COLUMNS = tuple(GRAPH_COLUMNS) + BIT_COLUMNS + WORD_COLUMNS
COLUMNS = (tuple('original_' + c for c in CHANNEL_COLUMNS)
           + tuple('normalized_' + c for c in CHANNEL_COLUMNS)
           + tuple('absolute_channel_delta_' + c for c in CHANNEL_COLUMNS))
FEATURE_COLUMNS = COLUMNS
_LOCK_GUARD = threading.Lock()
_LOCKS: dict[str, threading.Lock] = {}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    # Reused helpers' complete recorded runtime dependencies remain covered.
    from .area_model_v4 import source_hashes as prior_sources
    result = prior_sources()
    directory = Path(__file__).parent
    for name in ('graph_features_v5.py', 'structural_features_v5.py'):
        path = directory / name
        if path.exists():
            result[name] = _sha(path)
    return result


def _normalize_formula(formula):
    # No silent substitution with another revision's normalizer.
    from .structural_features_v5 import normalize_formula
    return normalize_formula(formula)


def _normalized_root(formula):
    # The discovery grammar requires an operation root. Semantic normalization
    # may legitimately produce a bare wire or integer; render those explicitly.
    if formula in ('in0', 'in1'):
        formula = f'ori({formula},0)'
    elif isinstance(formula, str) and re.fullmatch(r'-?[0-9]+', formula):
        formula = f'lui({formula})'
    return parse_formula(formula).canonical()


def validate_primitive_graph(netlist):
    """Reject target cells, ambiguous signals, unsupported primitives and X/Z."""
    if set(netlist.get('modules', {})) != {'candidate'}:
        raise ValueError('Expected exactly one flattened candidate module')
    module = netlist['modules']['candidate']
    inputs = {b for p in module['ports'].values() if p['direction'] == 'input'
              for b in p['bits']}
    if any(type(b) is not int for b in inputs):
        raise ValueError('Expected variable input bits')
    drivers = set()
    referenced = []
    for cell in module.get('cells', {}).values():
        kind = cell['type']
        if kind not in PRIMITIVES:
            raise ValueError(f'Unsupported generic primitive: {kind}')
        expected = {*PRIMITIVES[kind], 'Y'}
        if set(cell['connections']) != expected or set(cell['port_directions']) != expected:
            raise ValueError('Primitive port schema mismatch')
        for port, bits in cell['connections'].items():
            if len(bits) != 1 or cell['port_directions'][port] != ('output' if port == 'Y' else 'input'):
                raise ValueError('Expected one-bit primitive ports')
            bit = bits[0]
            if port == 'Y':
                if type(bit) is not int or bit in drivers or bit in inputs:
                    raise ValueError('Invalid or multiple graph driver')
                drivers.add(bit)
            else:
                referenced.append(bit)
    referenced.extend(b for p in module['ports'].values() if p['direction'] == 'output'
                      for b in p['bits'])
    for bit in referenced:
        if type(bit) is int:
            if bit not in inputs and bit not in drivers:
                raise ValueError('Undriven graph bit')
        elif bit not in ('0', '1'):
            raise ValueError('Undefined graph constant')
    # The reused topology traversal independently rejects cycles.
    return graph_features(netlist)


def _parameter(cell, name, default=0):
    value = cell.get('parameters', {}).get(name, default)
    if isinstance(value, str):
        if not value or set(value) - {'0', '1'}:
            raise ValueError(f'Invalid arithmetic parameter {name}')
        return int(value, 2)
    if type(value) is not int or value < 0:
        raise ValueError(f'Invalid arithmetic parameter {name}')
    return value


def word_features(netlist):
    """Generic arithmetic widths retained BEFORE techmap removes adders.

    The spans intentionally overapproximate carry propagation; they are neither
    iCE40 carry usage nor a guarantee about active output bits after mapping.
    """
    if set(netlist.get('modules', {})) != {'candidate'}:
        raise ValueError('Expected flattened word-level module')
    cells = list(netlist['modules']['candidate'].get('cells', {}).values())
    if any(not c['type'].startswith('$') or c['type'].startswith('$_') for c in cells):
        raise ValueError('Word graph must contain generic word-level cells')
    counts = Counter(c['type'] for c in cells)
    arithmetic = [c for c in cells if c['type'] in ('$add', '$sub', '$mul')]
    carries = [_parameter(c, 'Y_WIDTH') for c in arithmetic if c['type'] in ('$add', '$sub')]
    multiplies = [c for c in arithmetic if c['type'] == '$mul']
    values = [len(cells), counts['$add'], counts['$sub'], counts['$mul'],
              sum(_parameter(c, 'Y_WIDTH') for c in arithmetic), sum(carries),
              max(carries, default=0),
              sum(_parameter(c, 'A_WIDTH') + _parameter(c, 'B_WIDTH') for c in multiplies),
              sum(_parameter(c, 'A_WIDTH') * _parameter(c, 'B_WIDTH') for c in multiplies),
              sum(bool(_parameter(c, 'A_SIGNED') or _parameter(c, 'B_SIGNED')) for c in arithmetic)]
    return np.asarray(values, dtype=float)


def channel_features(graph, word):
    topology = validate_primitive_graph(graph)
    counts = Counter(c['type'] for c in graph['modules']['candidate'].get('cells', {}).values())
    bits = [counts['$_' + kind.upper() + '_'] for kind in ('and', 'or', 'xor', 'not', 'mux')]
    values = np.concatenate((topology, np.asarray(bits, dtype=float), word_features(word)))
    if len(values) != len(CHANNEL_COLUMNS) or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError('Invalid generic graph features')
    return values


class GraphExtractor:
    def __init__(self, cache_dir, *, yosys='yosys', timeout=120, frozen_tool=None):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError('timeout must be positive')
        self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.yosys = yosys
        self.timeout = timeout
        identity = frozen_tool if frozen_tool is not None else tool_identity(yosys)
        # Tool paths are invocation details, not graph content identity.
        self.tool = {k: identity[k] for k in ('version', 'executable_sha256')}
        self.context = {'schema': SCHEMA, 'pipeline': PIPELINE, 'tool': self.tool,
                        'runtime_source_sha256': source_hashes(),
                        'feature_columns': list(CHANNEL_COLUMNS),
                        'scope': 'generic combinational synthesis; no ABC, target mapping or measured labels'}

    def key(self, formula):
        canonical = parse_formula(formula).canonical()
        content = json.dumps({'formula': canonical, 'context': self.context}, sort_keys=True, separators=(',', ':'))
        return canonical, hashlib.sha256(content.encode()).hexdigest()

    def _channel(self, formula):
        canonical, key = self.key(formula)
        directory = self.cache_dir / key
        with _LOCK_GUARD:
            lock = _LOCKS.setdefault(str(directory), threading.Lock())
        with lock:
            return self._channel_locked(canonical, key, directory)

    def _channel_locked(self, canonical, key, directory):
        path = directory / 'features.json'
        if path.exists():
            record = json.loads(path.read_text())
            if record.get('cache_key') != key or record.get('formula') != canonical or record.get('context') != self.context:
                raise ValueError('V5 graph cache identity mismatch')
            for filename in ('candidate.v', 'extract.ys', 'word.json', 'graph.json', 'extract.log'):
                if not (directory / filename).is_file() or _sha(directory / filename) != record.get('files_sha256', {}).get(filename):
                    raise ValueError('V5 graph cache file hash mismatch')
            if (directory / 'candidate.v').read_text() != generate_rtl(canonical):
                raise ValueError('Cached RTL differs from formula renderer')
            values = channel_features(json.loads((directory / 'graph.json').read_text()),
                                      json.loads((directory / 'word.json').read_text())).tolist()
            if values != record.get('feature_values'):
                raise ValueError('Cached features differ from retained generic graph')
            return {**record, 'cache_hit': True}
        directory.mkdir(parents=True, exist_ok=True)
        actual = tool_identity(self.yosys)
        if any(actual[k] != self.tool[k] for k in self.tool):
            raise ValueError('Cold generic extraction requires the declared Yosys version and executable hash')
        (directory / 'candidate.v').write_text(generate_rtl(canonical))
        (directory / 'extract.ys').write_text(PIPELINE)
        started = time.perf_counter()
        try:
            result = subprocess.run([actual['executable'], '-s', 'extract.ys'], cwd=directory,
                                    capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as error:
            (directory / 'extract.log').write_text(f'Generic extraction timeout after {self.timeout}s\n')
            raise RuntimeError(f'Generic extraction timed out: {directory}') from error
        (directory / 'extract.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'Generic extraction failed: {directory / "extract.log"}')
        values = channel_features(json.loads((directory / 'graph.json').read_text()),
                                  json.loads((directory / 'word.json').read_text())).tolist()
        record = {'formula': canonical, 'cache_key': key, 'context': self.context,
                  'feature_columns': list(CHANNEL_COLUMNS), 'feature_values': values,
                  'paths': {'rtl': 'candidate.v', 'word_graph': 'word.json', 'primitive_graph': 'graph.json',
                            'script': 'extract.ys', 'log': 'extract.log'},
                  'files_sha256': {n: _sha(directory / n) for n in ('candidate.v', 'extract.ys', 'word.json', 'graph.json', 'extract.log')},
                  'cold_seconds': time.perf_counter() - started}
        temporary = directory / 'features.json.tmp'
        temporary.write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
        temporary.replace(path)
        return {**record, 'cache_hit': False}

    def extract(self, formula):
        if self.context['runtime_source_sha256'] != source_hashes():
            raise ValueError('V5 runtime sources changed during graph extraction')
        canonical = parse_formula(formula).canonical()
        normalized = _normalized_root(_normalize_formula(canonical))
        original = self._channel(canonical)
        other = self._channel(normalized)
        a, b = np.asarray(original['feature_values']), np.asarray(other['feature_values'])
        values = np.concatenate((a, b, abs(a - b))).tolist()
        if self.context['runtime_source_sha256'] != source_hashes():
            raise ValueError('V5 runtime sources changed during graph extraction')
        return {'formula': canonical, 'normalized_formula': normalized,
                'feature_columns': list(COLUMNS), 'feature_values': values, 'values': values,
                'original': original, 'normalized': other,
                'cache_hit': original['cache_hit'] and other['cache_hit'],
                'provenance': self.context}

    def matrix(self, rows, workers=2):
        formulas = [r['formula'] if isinstance(r, dict) else r for r in rows]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(self.extract, formulas))
        return np.asarray([r['feature_values'] for r in records], dtype=float).reshape(len(records), len(COLUMNS)), records
