"""Legality and accounting checks for the real trace candidate extractor."""
from collections import Counter
from pathlib import Path
import importlib.util
import json
import sys

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
spec = importlib.util.spec_from_file_location("discovery_candidates", SRC / "candidates.py")
candidates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidates)


def instruction(op="addi", rd=1, rs1=1, rs2=None, imm=1):
    return {"op": op, "rd": rd, "rs1": rs1, "rs2": rs2, "imm": imm}


def legal(program, members):
    block = sorted(program)
    return candidates.followsRules(set(members), block, program,
                                  candidates.findSources(block, program),
                                  candidates.findLastWrites(block, program))


def test_overlapping_occurrences_are_retained_but_savings_are_disjoint():
    program = {4 * i: instruction() for i in range(6)}
    ranked = candidates.extractCandidates(program, Counter({pc: 10 for pc in program}),
                                         {0}, maxSize=2)
    assert len(ranked) == 1
    row = ranked[0]
    assert row["formula"] == "addi(addi(in0,1),1)"
    assert (row["size"], row["places"], row["runs"], row["saved"]) == (2, 5, 50, 50)
    assert row["traceTotalInstructions"] == 60
    assert row["nonOverlappingPlaces"] == 3
    assert row["nonOverlappingRuns"] == 30
    assert row["overlapSafeSaved"] == 30
    assert row["overlapSafeSavedPercent"] == 50
    selected = [o for o in row["occurrences"] if o["selectedForSavings"]]
    pcs = [pc for occurrence in selected for pc in occurrence["pcs"]]
    assert len(pcs) == len(set(pcs))
    assert ranked == candidates.extractCandidates(program, Counter({pc: 10 for pc in program}),
                                                 {0}, maxSize=2)


def test_connected_dead_branch_cannot_inflate_formula_savings():
    program = {0: instruction(rd=3, rs1=1),
               4: instruction(rd=4, rs1=3),
               8: instruction(rd=3, rs1=3),
               12: instruction(rd=4, rs1=0)}
    assert not legal(program, {0, 1, 2})  # member 1 contributes nothing to result
    assert legal(program, {0, 2}) is False  # outside member 1 consumes member 0


def test_overwritten_external_input_is_rejected_at_replacement_point():
    program = {0: instruction(rd=3, rs1=1),
               4: instruction(rd=1, rs1=0),
               8: instruction(rd=3, rs1=3)}
    assert not legal(program, {0, 2})


def test_internal_output_used_early_or_live_at_exit_is_rejected():
    early_use = {0: instruction(rd=3, rs1=1),
                 4: instruction("sw", rd=None, rs1=3, rs2=2, imm=0),
                 8: instruction(rd=3, rs1=3)}
    assert not legal(early_use, {0, 2})
    live_out = {0: instruction(rd=3, rs1=1), 4: instruction(rd=4, rs1=3)}
    assert not legal(live_out, {0, 1})


def test_unknown_instruction_is_an_opaque_barrier():
    program = {0: instruction(), 4: instruction("unknown", None, None, None, None),
               8: instruction()}
    assert not legal(program, {0, 2})


def test_zero_register_is_not_an_input_or_dependency():
    program = {0: instruction(rd=0, rs1=1), 4: instruction(rd=3, rs1=0),
               8: instruction(rd=3, rs1=3)}
    block = sorted(program)
    assert candidates.findArrows(block, program) == [(1, 2)]
    assert legal(program, {1, 2})
    assert candidates.describe({1, 2}, block, program,
                               candidates.findSources(block, program)) == "addi(addi(0,1),1)"


def test_formula_merging_reports_distinct_original_sizes_deterministically():
    program = {0: instruction("add", 3, 1, 2, None),
               4: instruction("add", 3, 3, 3, None),
               8: instruction("add", 3, 1, 2, None),
               12: instruction("add", 4, 1, 2, None),
               16: instruction("add", 3, 3, 4, None),
               20: instruction(rd=4, rs1=0)}
    rows = candidates.extractCandidates(program, Counter({pc: 10 for pc in program}), {0, 8})
    row = next(r for r in rows if r["formula"] == "add(add(in0,in1),add(in0,in1))")
    assert row["sizeVariants"] == [2, 3]
    assert row["size"] == 2
    assert row["saved"] == (row["size"] - 1) * row["runs"] == 20
    assert row["occurrenceSaved"] == row["overlapSafeSaved"] == 30


def test_trace_region_end_cuts_static_block(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text('\n'.join(json.dumps({"pc": hex(pc)}) for pc in [0, 4]) + '\n')
    runs, starts = candidates.readTrace(trace)
    assert starts == {0, 8}
    program = {0: instruction(), 4: instruction(), 8: instruction()}
    assert len(candidates.extractCandidates(program, runs, starts)) == 1


def test_max_size_limit_missing_addresses_and_inconsistent_blocks():
    program = {4 * i: instruction() for i in range(6)}
    counts = Counter({pc: 1 for pc in program})
    rows = candidates.extractCandidates(program, counts, {0}, maxSize=4)
    assert {r["size"] for r in rows} == {2, 3, 4}
    assert candidates.extractCandidates(program, counts, {0}, maxSize=4, limit=1) == rows[:1]
    assert candidates.extractCandidates(program, Counter(), {0}) == []
    with pytest.raises(ValueError, match="absent"):
        candidates.extractCandidates(program, Counter({100: 1}), {100})
    with pytest.raises(ValueError, match="MIXED"):
        candidates.extractCandidates(program, Counter({0: 1}), {0})
    with pytest.raises(ValueError, match="at least 2"):
        candidates.extractCandidates(program, counts, {0}, maxSize=1)


def test_objdump_failures_are_not_treated_as_empty_programs(monkeypatch):
    def fail(*args, **kwargs):
        assert args[0] == ["custom-objdump", "-d", "test.elf"]
        assert kwargs["check"] is True
        raise candidates.subprocess.CalledProcessError(1, args[0])
    monkeypatch.setattr(candidates.subprocess, "run", fail)
    with pytest.raises(candidates.subprocess.CalledProcessError):
        candidates.readProgram("test.elf", "custom-objdump")


def test_cli_preserves_positionals_and_accepts_study_options(tmp_path, monkeypatch):
    trace = tmp_path / "trace.jsonl"
    trace.write_text('\n'.join(json.dumps({"pc": hex(pc)}) for pc in [0, 4]) + '\n')
    output = tmp_path / "out.json"
    program = {0: instruction(), 4: instruction()}
    monkeypatch.setattr(candidates, "readProgram", lambda elf, objdump: program)
    candidates.main([str(trace), "example.elf", str(output), "--max-size", "4",
                     "--objdump", "custom-objdump", "--limit", "1"])
    assert json.loads(output.read_text())[0]["traceTotalInstructions"] == 2


def test_legal_fusions_preserve_rv32_register_state_on_random_small_blocks():
    """Exercise actual removal/replacement, including register reuse and wraparound."""
    import random
    from isaforge.features import parse_formula

    rng = random.Random(17)
    checked = 0
    mask = (1 << 32) - 1

    def operation(op, a, b):
        return {"add": lambda: a + b, "addi": lambda: a + b,
                "sub": lambda: a - b, "xor": lambda: a ^ b,
                "and": lambda: a & b, "or": lambda: a | b}[op]() & mask

    def execute(program, state, members=None):
        block = sorted(program)
        sources = candidates.findSources(block, program)
        formula = parse_formula(candidates.describe(members, block, program, sources)) if members else None
        # Input numbering follows the expression's left-to-right traversal.
        names = {}
        def collect(member):
            for reg, writer in sources[member]:
                if writer in members:
                    collect(writer)
                else:
                    names.setdefault((reg, writer), f"in{len(names)}")
        if members:
            collect(max(members))

        def evaluate(node, inputs):
            if not node.children:
                return node.value if isinstance(node.value, int) else inputs[node.value]
            return operation(node.value, *(evaluate(child, inputs) for child in node.children))

        for i, pc in enumerate(block):
            record = program[pc]
            if members and i in members:
                if i != max(members):
                    continue
                value = evaluate(formula, {name: state[reg] for (reg, _), name in names.items()})
            else:
                second = record["imm"] if record["rs2"] is None else state[record["rs2"]]
                value = operation(record["op"], state[record["rs1"]], second)
            if record["rd"]:
                state[record["rd"]] = value
        return state

    for _ in range(120):
        program = {}
        for i in range(7):
            op = rng.choice(["add", "sub", "xor", "and", "or", "addi"])
            program[4 * i] = instruction(op, rng.randrange(1, 5), rng.randrange(5),
                                         None if op == "addi" else rng.randrange(5),
                                         rng.randrange(-8, 8) if op == "addi" else None)
        block = sorted(program)
        for members in candidates.findPotentialCandidates(block, program,
                                                           candidates.findArrows(block, program), 4):
            if not legal(program, members):
                continue
            for _ in range(3):
                state = {reg: rng.randrange(1 << 32) for reg in range(1, 5)} | {0: 0}
                assert execute(program, state.copy()) == execute(program, state.copy(), members)
            checked += 1
    assert checked >= 20


def test_actual_block_equivalence_models_memory_and_branch_outputs():
    from verify_candidate_fusions import execute
    program = {0: instruction(rd=3, rs1=1), 4: instruction(rd=3, rs1=3),
               8: instruction('sw', None, 2, 3, 0),
               12: instruction('lw', 4, 2, None, 0),
               16: instruction('bne', None, 3, 4, 8)}
    block = sorted(program)
    state = {reg: reg * 997 for reg in range(32)}
    replacement = {'formula': 'addi(addi(in0,1),1)', 'members': {0, 1}}
    baseline = execute(block, program, state.copy(), [])
    assert execute(block, program, state.copy(), [replacement]) == baseline
    assert baseline[2] == 20  # store/reload agrees, so branch is not taken
    incorrect = {'formula': 'addi(addi(in0,1),2)', 'members': {0, 1}}
    assert execute(block, program, state.copy(), [incorrect]) != baseline


def test_actual_equivalence_report_checks_joint_selected_occurrences(tmp_path, monkeypatch):
    import verify_candidate_fusions
    program = {4 * i: instruction() for i in range(6)}
    rows = candidates.extractCandidates(program, Counter({pc: 2 for pc in program}), {0}, maxSize=2)
    directory = tmp_path / 'candidates'
    directory.mkdir()
    (directory / 'example.json').write_text(json.dumps(rows))
    monkeypatch.setattr(verify_candidate_fusions, 'readProgram', lambda *args: program)
    result = verify_candidate_fusions.verify_candidates(directory, tmp_path, 'objdump', vectors=4)
    assert result['passed']
    assert result['benchmarks'][0]['checked_occurrences'] == 5
    assert result['benchmarks'][0]['individual_comparisons'] == 20
    assert result['benchmarks'][0]['joint_formula_block_comparisons'] == 4
