"""Calibrated, label-free latency merit for the restricted PicoRV32 context.

This is an established software-latency minus hardware-latency heuristic, not
a learned model or measured application speedup. Count actual lowered DAG
instructions, not expanded expression-tree nodes. Sets still require joint
lowering and evaluation. No area, routed timing, or confidence is predicted.
"""
from __future__ import annotations

from .codesign import require

SHIFTS = ('slli', 'srli', 'srai')


def latency_table(calibration):
    require(calibration.get('rule_matches_all') is True and
            calibration.get('semantic_checks_passed') is True and
            calibration.get('stock_trap_control_passed') is True,
            'Successful independent processor calibration required')
    table = {}
    for row in calibration['rows']:
        key = row['op'], row['immediate']
        require(type(row['cycles']) is int and row['cycles'] > 0, 'Invalid operation latency')
        require(key not in table or table[key] == row['cycles'], 'Context-dependent calibration latency')
        table[key] = row['cycles']
    require(('pcpi', None) in table, 'Missing PCPI calibration')
    return table


def instruction_latency(instruction, table):
    op = instruction['op']
    immediate = instruction.get('imm') if op in SHIFTS else None
    if op in SHIFTS:
        require(type(immediate) is int and 0 <= immediate < 32, 'Invalid RV32 shift immediate')
    require((op, immediate) in table and op != 'pcpi', 'Unsupported operation latency: '+op)
    return table[op, immediate]


def candidate_features(candidate, program, baseline_cycles, baseline_instructions, calibration):
    """Consume baseline-only data and exact occurrences; never candidate labels.

    Caller must bind core, RAM, PCPI interface, compiler and baseline provenance
    to the calibration context. Prediction assumes surrounding instruction
    costs stay unchanged after relocation. This is checked empirically, not
    guaranteed. Unsupported variable shifts fail closed.
    """
    require(type(baseline_cycles) is int and baseline_cycles > 0, 'Invalid baseline cycles')
    require(type(baseline_instructions) is int and baseline_instructions > 0, 'Invalid baseline instructions')
    table = latency_table(calibration)
    used, sizes, software, custom, runs, shift_extra, replaced = set(), [], 0, 0, 0, 0, 0
    require(candidate.get('occurrences'), 'Executable occurrences required')
    for occurrence in candidate['occurrences']:
        pcs = [int(pc, 16) if isinstance(pc, str) else pc for pc in occurrence['pcs']]
        count = occurrence['blockRuns']
        require(type(count) is int and count > 0, 'Invalid occurrence count')
        require(all(type(pc) is int and pc >= 0 and pc % 4 == 0 for pc in pcs), 'Invalid instruction address')
        require(2 <= len(pcs) <= 4 and len(set(pcs)) == len(pcs) and
                occurrence['size'] == len(pcs), 'Invalid distinct instruction count')
        require(used.isdisjoint(pcs), 'Overlapping lowered occurrences')
        used.update(pcs); sizes.append(len(pcs)); runs += count; replaced += len(pcs) * count
        for pc in pcs:
            require(pc in program, 'Missing baseline instruction')
            instruction = program[pc]
            latency = instruction_latency(instruction, table)
            software += latency * count
            if instruction['op'] in SHIFTS:
                shift_extra += (latency - table[instruction['op'], 0]) * count
        custom += table['pcpi', None] * count
    require(replaced <= baseline_instructions, 'Occurrences exceed baseline execution count')
    savings = software - custom
    require(baseline_cycles - savings > 0, 'Estimated program duration must be positive')
    return dict(baseline_cycles=baseline_cycles, baseline_instructions=baseline_instructions,
                baseline_cpi=baseline_cycles / baseline_instructions,
                replacement_execution_fraction=runs / baseline_instructions,
                occurrence_size_min=min(sizes), occurrence_size_max=max(sizes),
                dynamic_software_cycles=software, dynamic_custom_cycles=custom,
                dynamic_shift_extra_cycles=shift_extra, estimated_saved_cycles=savings,
                estimated_cycle_reduction=savings / baseline_cycles,
                estimated_speedup=baseline_cycles / (baseline_cycles - savings))
