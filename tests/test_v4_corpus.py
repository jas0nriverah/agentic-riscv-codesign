import json
from collections import Counter

import pytest

from isaforge.v4_corpus import (DEVELOPMENT_SEED, TEST_SEED, MUL_OPS,
                                _validate_release, generate)


def test_disjoint_balanced_pools_have_explicit_regimes():
    excluded = {'add(in0,in1)'}
    development = generate(excluded, 384, DEVELOPMENT_SEED, 'development')
    test = generate(excluded | {r['formula'] for r in development}, 256, TEST_SEED, 'test')
    assert development == generate(excluded, 384, DEVELOPMENT_SEED, 'development')
    assert len({r['formula'] for r in development + test}) == 640
    assert not excluded.intersection(r['formula'] for r in development + test)
    for rows, per_stratum, per_variant in ((development, 48, 12), (test, 32, 8)):
        assert len(Counter(r['stratum'] for r in rows)) == 8
        assert set(Counter(r['stratum'] for r in rows).values()) == {per_stratum}
        mul = [r for r in rows if r['stratum'] == 'multiplication']
        assert Counter(r['multiply_variant'] for r in mul) == dict.fromkeys(MUL_OPS, per_variant)
        assert len({r['operand_regime'] for r in mul}) == 8
        assert all('template' in r and 'operand_regime' in r for r in rows)
        assert all('lut4_count' not in r and 'predicted_lut4' not in r for r in rows)


def test_release_requires_parent_authorization_and_frozen_artifacts(tmp_path):
    release = tmp_path / 'release.json'
    release.write_text(json.dumps({'test_candidate_sha256': 'pool', 'authorized_by_parent': True}))
    with pytest.raises(ValueError, match='frozen models'):
        _validate_release(release, [], {'candidate_sha256': 'pool'})
    release.write_text(json.dumps({'test_candidate_sha256': 'pool', 'authorized_by_parent': False}))
    with pytest.raises(ValueError, match='explicitly authorize'):
        _validate_release(release, [], {'candidate_sha256': 'pool'})


@pytest.mark.parametrize('count', [0, 31, 193, True])
def test_invalid_pool_sizes(count):
    with pytest.raises(ValueError):
        generate(set(), count, DEVELOPMENT_SEED, 'development')
