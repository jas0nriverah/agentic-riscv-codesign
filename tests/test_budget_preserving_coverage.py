"""Pointwise policy invariants cover boundaries, every cap region, and tails."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

SPEC=importlib.util.spec_from_file_location('preserving',Path(__file__).parents[1]/'scripts/budget_preserving_coverage.py')
p=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(p)


def test_policy_preserves_all_cap_decisions_at_and_around_boundaries():
    b=np.array([0.,31.,32.,np.nextafter(32.,np.inf),63.,64.,np.nextafter(64.,np.inf),127.,128.,np.nextafter(128.,np.inf),500.])
    for s in (np.zeros_like(b),np.full_like(b,1000.),b+5,b-0):
        q=p.policy(b,s);check=p.invariants(b,q)
        assert p.passed(check)
        for cap in (32,64,128):assert np.array_equal(q<=cap,b<=cap)
    assert p.policy([31.,33.,65.,129.],[1000.]*4).tolist()==[32.,64.,128.,1000.]


def test_pointwise_underprediction_never_increases_for_any_target():
    rng=np.random.default_rng(20261109)
    b=rng.uniform(0,600,2000);s=rng.uniform(0,600,2000);y=rng.integers(0,1000,2000)
    q=p.policy(b,s)
    assert np.all(np.maximum(y-q,0)<=np.maximum(y-b,0))
    assert p.passed(p.invariants(b,q))


def test_policy_rejects_nonfinite_negative_and_misaligned_inputs():
    for b,s in (([1.],[1.,2.]),([-1.],[0.]),([1.],[float('nan')]),([[1.]],[[2.]])):
        with pytest.raises(ValueError):p.policy(b,s)


def test_unchanged_budget_decisions_preserve_existing_errors_and_can_worsen_mae():
    b=[40.,100.];y=[33.,80.];q=p.policy(b,[50.,200.])
    base=p.prior.model_metrics(b,y);candidate=p.prior.model_metrics(q,y)
    assert p.passed(p.invariants(b,q))
    assert candidate['caps']==base['caps']
    assert candidate['mae_lut4']>base['mae_lut4']
