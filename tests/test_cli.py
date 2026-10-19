import json

import pytest

from isaforge.cli import main


def test_demo_runs_end_to_end(tmp_path):
    assert main(["demo", "--output", str(tmp_path)]) == 0
    rows = json.loads((tmp_path / "dataset.json").read_text())
    assert len(rows) == 24
    assert {row["measurement_source"] for row in rows} == {"synthetic"}
    assert json.loads((tmp_path / "evaluation.json").read_text())
    assert json.loads((tmp_path / "selection.json").read_text())


def test_cli_rejects_non_array_input(tmp_path):
    source = tmp_path / "wrong.json"
    source.write_text('{"not": "rows"}')
    with pytest.raises(SystemExit) as error:
        main(["dataset", "--benchmark", "example", "--candidates", str(source),
              "--output", str(tmp_path / "out.json")])
    assert error.value.code == 2
    assert not (tmp_path / "out.json").exists()
