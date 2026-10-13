import json

from isaforge.real_experiment import select_candidates


def test_sampling_keeps_top_merit_and_is_reproducible(tmp_path):
    candidates = [dict(formula=f"addi(add(in0,in1),{i})", size=2,
                       runs=i+1, places=1, saved=i+1, savedPercent=i+1,
                       traceTotalInstructions=100, overlapSafeSaved=i+1,
                       overlapSafeSavedPercent=i+1) for i in range(20)]
    (tmp_path / "bench.json").write_text(json.dumps(candidates))
    first, summary = select_candidates(tmp_path, 8, 9)
    assert (first, summary) == select_candidates(tmp_path, 8, 9)
    assert len(first) == 8
    assert len({row["candidate_id"] for row in first}) == 8
    assert {row["runs"] for row in first if row["selection_stratum"] == "top_merit"} == {17,18,19,20}
    assert summary[0]["candidate_count"] == 20
