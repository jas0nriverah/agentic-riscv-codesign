"""Check discovered formulas against removal/replacement in their actual RV32 blocks.

This is randomized software equivalence with modeled memory/control effects, not
formal verification or a modified-processor execution test. It complements the
Verilator check of synthesized formula semantics.
"""
import argparse
import json
from pathlib import Path
import random

from candidates import ELIGIBLE, JUMPS, findBlocks, findSources, readProgram
from isaforge.rtl import MASK, evaluate_formula


def signed(value):
    return value - (1 << 32) if value & (1 << 31) else value


def execute(block, program, state, replacements):
    """Return all architectural registers, written memory, and branch destination."""
    memory, exit_target = {}, None
    skipped = {member for replacement in replacements for member in replacement['members']}
    at_last = {max(r['members']): r for r in replacements}
    sources = findSources(block, program)

    def load_byte(addr):
        addr &= MASK
        return memory.get(addr, ((addr * 2654435761) ^ (addr >> 5)) & 255)

    def load(addr, width, is_signed):
        value = sum(load_byte(addr + i) << (8 * i) for i in range(width))
        if is_signed and value & (1 << (width * 8 - 1)):
            value -= 1 << (width * 8)
        return value & MASK

    for index, pc in enumerate(block):
        record = program[pc]
        op, rd = record['op'], record['rd']
        if index in skipped:
            if index not in at_last:
                continue
            replacement = at_last[index]
            names = {}
            def collect(member):
                for reg, writer in sources[member]:
                    if writer in replacement['members']:
                        collect(writer)
                    else:
                        names.setdefault((reg, writer), f'in{len(names)}')
            collect(index)
            inputs = {name: state[reg] for (reg, _), name in names.items()}
            value = evaluate_formula(replacement['formula'], inputs.get('in0', 0), inputs.get('in1', 0))
        else:
            a = state[record['rs1']] if record['rs1'] is not None else 0
            b = state[record['rs2']] if record['rs2'] is not None else record['imm']
            if op in ELIGIBLE:
                args = [a] if record['rs1'] is not None else []
                if record['rs2'] is not None:
                    args.append(b)
                if record['imm'] is not None:
                    args.append(record['imm'])
                value = evaluate_formula(f"{op}({','.join(map(str,args))})", 0, 0)
            elif op in {'lb', 'lh', 'lw', 'lbu', 'lhu'}:
                value = load(a + record['imm'], {'lb':1,'lbu':1,'lh':2,'lhu':2,'lw':4}[op], op in {'lb','lh'})
            elif op in {'sb', 'sh', 'sw'}:
                width = {'sb':1,'sh':2,'sw':4}[op]
                for offset in range(width):
                    memory[(a + record['imm'] + offset) & MASK] = (b >> (8 * offset)) & 255
                continue
            elif op == 'auipc':
                value = pc + record['imm']
            elif op == 'jal':
                value, exit_target = pc + 4, (pc + record['imm']) & MASK
            elif op == 'jalr':
                value, exit_target = pc + 4, ((a + record['imm']) & MASK) & ~1
            elif op in JUMPS:
                taken = {'beq':a==b, 'bne':a!=b, 'blt':signed(a)<signed(b),
                         'bge':signed(a)>=signed(b), 'bltu':a<b, 'bgeu':a>=b}[op]
                exit_target = (pc + (record['imm'] if taken else 4)) & MASK
                continue
            elif op in {'div', 'divu', 'rem', 'remu'}:
                left, right = (signed(a), signed(b)) if op in {'div','rem'} else (a,b)
                quotient = (abs(left) // abs(right)) * (-1 if (left<0) != (right<0) else 1) if right else -1
                value = quotient if op in {'div','divu'} else (left - quotient * right if right else left)
            else:
                raise ValueError(f'Unsupported block operation {op}')
        if rd:
            state[rd] = value & MASK
    return state, memory, exit_target


def verify_candidates(candidate_dir, program_dir, objdump, vectors=16, seed=20261013):
    if vectors < 1:
        raise ValueError("vectors must be positive")
    rng = random.Random(seed)
    results = []
    for path in sorted(Path(candidate_dir).glob('*.json')):
        rows = json.loads(path.read_text())
        program = readProgram(Path(program_dir) / (path.stem + '.elf'), objdump)
        starts = {int(o['blockStart'],16) for row in rows for o in row['occurrences']}
        blocks = {b[0]: b for b in findBlocks(program, starts)}
        groups = {}
        for row in rows:
            for occurrence in row['occurrences']:
                start = int(occurrence['blockStart'],16)
                block = blocks[start]
                members = {block.index(int(pc,16)) for pc in occurrence['pcs']}
                groups.setdefault(start, []).append(dict(formula=row['formula'], members=members,
                                                         selected=occurrence['selectedForSavings']))
        checked, skipped, comparisons, joint_comparisons = 0, 0, 0, 0
        for start, occurrences in groups.items():
            block = blocks[start]
            if any(program[pc]['op'] == 'unknown' for pc in block):
                skipped += len(occurrences)
                continue
            states = [{reg: rng.getrandbits(32) if reg else 0 for reg in range(32)} for _ in range(vectors)]
            baseline = [execute(block, program, state.copy(), []) for state in states]
            for occurrence in occurrences:
                for state, expected in zip(states, baseline):
                    if execute(block, program, state.copy(), [occurrence]) != expected:
                        raise ValueError(f'Fusion mismatch: {path.stem} block {start:#x} {occurrence}')
                    comparisons += 1
                checked += 1
            by_formula = {}
            for occurrence in occurrences:
                if occurrence['selected']:
                    by_formula.setdefault(occurrence['formula'], []).append(occurrence)
            for replacements in by_formula.values():
                for state, expected in zip(states, baseline):
                    if execute(block, program, state.copy(), replacements) != expected:
                        raise ValueError(f'Joint fusion mismatch: {path.stem} block {start:#x} {replacements}')
                    joint_comparisons += 1
        results.append(dict(benchmark=path.stem, checked_occurrences=checked, skipped_opaque_block_occurrences=skipped,
                            vectors_per_occurrence=vectors, individual_comparisons=comparisons,
                            joint_formula_block_comparisons=joint_comparisons))
    return dict(seed=seed, benchmarks=results, passed=True,
                limitation='Randomized software register/memory/control equivalence on static blocks; no formal proof or modified processor execution.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', default='generated/real/candidates')
    parser.add_argument('--programs', default='generated/programs')
    parser.add_argument('--objdump', default='riscv64-unknown-elf-objdump')
    parser.add_argument('--vectors', type=int, default=16)
    parser.add_argument('--output', default='generated/real/extraction_equivalence.json')
    args = parser.parse_args()
    result = verify_candidates(args.candidates, args.programs, args.objdump, args.vectors)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
