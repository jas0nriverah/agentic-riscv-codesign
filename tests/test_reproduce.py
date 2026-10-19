import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from reproduce import metrics, summarize, run


def test_mape_is_mean_of_percentages_and_zeros_stay_in_mae():
    result = metrics([0, 2, 100], [9, 3, 110])
    assert result['mape_percent'] == 30
    assert result['mae_lut4'] == pytest.approx(20/3)
    assert result['positive_n'] == 2 and result['zero_n'] == 1
    assert result['zero_mae_lut4'] == 9
    assert metrics([0], [2])['mape_percent'] is None


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, True])
def test_invalid_metrics_fail(value):
    with pytest.raises(ValueError):
        metrics([1], [value])


def test_duplicate_physical_circuits_fail():
    row = {'id': 'same', 'measured_lut4': 2, 'predictions': {'base': 3}, 'group': 'arithmetic'}
    with pytest.raises(ValueError, match='Duplicate'):
        summarize({'scope': 'test', 'rows': [row, row]})


def test_saved_complete_result_replays():
    import json
    root = Path(__file__).resolve().parents[1]
    assert run() == json.loads((root/'results/summary.json').read_text())
