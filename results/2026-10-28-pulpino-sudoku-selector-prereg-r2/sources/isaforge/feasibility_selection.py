"""Fixed feasibility classification multiplied by public analytic cycle benefit.

Member outputs are uncalibrated scores. Their bootstrap spread describes
estimator disagreement, not predictive coverage or calibrated confidence.
Whole-source/family exclusions and paid selection belong to the experiment caller.
"""
from __future__ import annotations

import importlib.metadata
from pathlib import Path
import statistics

from . import budgeted_selection as b, codesign as c
from .model import _number, validate_training_rows

AREA_CAPS = (32, 64, 128)
CLOCK_MHZ = 12.0
MODEL_SETTINGS = dict(ensemble_size=20, n_estimators=80, max_depth=2,
    learning_rate=.05, min_child_weight=1, reg_lambda=1.0, subsample=1.0,
    colsample_bytree=1.0, tree_method='hist', n_jobs=1, objective='binary:logistic',
    bootstrap='n measured candidates with replacement; every draw expands all caps',
    cap_replica_sample_weight=1/3,
    single_class='per-member constant 0 or 1; consume model-seed RNG draw regardless')
BUDGET_FEATURE = 'area_cap / (training_median_lut4_per_tree_op * tree_op_count)'
SOURCES = ('isaforge/feasibility_selection.py', *b.SOURCES)
PACKAGES = ('numpy', 'scipy', 'xgboost', 'scikit-learn')
TARGET = 'verified device fit and integrated area <= cap and routed minimum Fmax >= 12 MHz'
DECISION_RULE = 'mean uncalibrated feasibility score * max(0, public estimated_saved_cycles / baseline_cycles)'


def _cap(area_cap):
    c.require(not isinstance(area_cap,bool) and area_cap in AREA_CAPS, 'Unsupported area cap')


def feasibility_label(row, area_cap):
    """Hardware feasibility only; failed/unknown measurements are not negatives."""
    _cap(area_cap)
    c.require(b.validate_outcome(row), 'Failed attempts have unknown feasibility labels')
    return int(b._feasible(row, area_cap, CLOCK_MHZ))


class FeasibilitySelectionPredictor:
    """One fixed candidate-bootstrap ensemble; no benefit regression or tuning."""
    def __init__(self, seed=0):
        c.require(type(seed) is int and seed >= 0, 'Invalid model seed')
        self.seed = seed
        self.models = None
        self.constants = None
        self.member_seeds = None
        self.area_per_op = None
        self.training_ids = None

    def _matrix(self, rows, area_cap):
        _cap(area_cap)
        c.require(self.area_per_op is not None, 'Fit feasibility model first')
        matrix = []
        for row, base in zip(rows,b.structural_matrix(rows)):
            ops = _number(row['tree_op_count'],'tree operations',positive=True)
            denominator = _number(self.area_per_op*ops,'historical proxy LUT4',positive=True)
            context = _number(area_cap/denominator,'cap-relative historical proxy')
            matrix.append(base+[context])
        return matrix

    def fit(self, rows):
        import numpy as np
        from xgboost import XGBClassifier
        rows = list(rows)
        c.require(rows, 'Measured historical rows required')
        # Validate status before requiring performance labels: failures are unknown,
        # even if a caller happens to provide plausible public structural features.
        for row in rows:
            c.require(b.validate_outcome(row), 'Failed attempts cannot train feasibility labels')
        validate_training_rows(rows)
        ids = [row['candidate_id'] for row in rows]
        c.require(all(isinstance(identity,str) and identity for identity in ids) and len(set(ids))==len(ids),
                  'Unique nonempty measured candidate IDs required')
        self.area_per_op = _number(statistics.median(
            row['area_delta_lut4']/_number(row['tree_op_count'],'tree operations',positive=True)
            for row in rows),'historical LUT4 per operation',positive=True)
        matrices = {cap:self._matrix(rows,cap) for cap in AREA_CAPS}
        x = np.asarray([matrices[cap][index] for index in range(len(rows)) for cap in AREA_CAPS],dtype=float)
        y = np.asarray([feasibility_label(row,cap) for row in rows for cap in AREA_CAPS],dtype=int)
        c.require(np.isfinite(x).all(), 'Nonfinite feasibility training matrix')
        self.training_ids = ids
        self.models, self.constants, self.member_seeds = [], [], []
        rng = np.random.default_rng(self.seed)
        for _ in range(MODEL_SETTINGS['ensemble_size']):
            candidates = rng.integers(0,len(rows),size=len(rows))
            indices = np.asarray([int(index)*len(AREA_CAPS)+offset for index in candidates
                                  for offset in range(len(AREA_CAPS))])
            model_seed = int(rng.integers(0,2**31-1))
            self.member_seeds.append(model_seed)
            labels = y[indices]
            if np.all(labels==labels[0]):
                self.models.append(None)
                self.constants.append(float(labels[0]))
            else:
                model = XGBClassifier(objective='binary:logistic', n_estimators=80,
                    max_depth=2,learning_rate=.05,min_child_weight=1,reg_lambda=1.0,
                    subsample=1.0,colsample_bytree=1.0,tree_method='hist',n_jobs=1,
                    random_state=model_seed,verbosity=0)
                model.fit(x[indices],labels,sample_weight=np.full(len(indices),1/len(AREA_CAPS)))
                self.models.append(model)
                self.constants.append(None)
        return self

    def predict(self, rows, *, area_cap):
        """Strict public-only features; expose scores and estimator disagreement."""
        import numpy as np
        _cap(area_cap)
        c.require(self.models is not None, 'Fit feasibility model first')
        if not rows:return []
        rows = b.public_rows(rows)
        x = self._matrix(rows,area_cap)
        samples = np.stack([np.full(len(rows),constant) if constant is not None
                            else model.predict_proba(x)[:,1]
                            for model,constant in zip(self.models,self.constants)])
        c.require(samples.shape==(20,len(rows)) and np.isfinite(samples).all() and
                  ((samples>=0)&(samples<=1)).all(), 'Invalid feasibility member scores')
        result = []
        for index,row in enumerate(rows):
            values = row['latency_features']
            saved = _number(values.get('estimated_saved_cycles'),'public estimated saved cycles')
            baseline = _number(values['baseline_cycles'],'public baseline cycles',positive=True)
            benefit = max(0.0,_number(saved/baseline,'analytic fractional cycle savings'))
            mean = float(samples[:,index].mean())
            result.append(dict(candidate_id=row['candidate_id'],area_cap=area_cap,
                feasibility_scores=[float(value) for value in samples[:,index]],
                feasibility_score_mean=mean,feasibility_score_std=float(samples[:,index].std()),
                analytic_fractional_cycle_savings=benefit,
                decision_score=_number(mean*benefit,'factorized decision score'),
                uncertainty_kind='bootstrap estimator disagreement',calibrated=False))
        return result

    def save(self, output):
        """Portable JSON classifiers and constant members, with bound dependencies."""
        c.require(self.models is not None, 'Fit feasibility model first')
        output = Path(output)
        c.require(not output.exists(), 'Fresh exported feasibility model directory required')
        output.mkdir(parents=True)
        members,artifacts = [],{}
        for index,(model,constant,seed) in enumerate(zip(self.models,self.constants,self.member_seeds)):
            if constant is not None:
                members.append(dict(model_seed=seed,constant=constant))
            else:
                name = f'member-{index:02d}.json'
                model.save_model(output/name)
                artifacts[name] = c.sha(output/name)
                members.append(dict(model_seed=seed,artifact=name))
        schema = dict(schema='isaforge-feasibility-selection-xgb-v1',seed=self.seed,
            settings=MODEL_SETTINGS,area_caps=list(AREA_CAPS),clock_mhz=CLOCK_MHZ,
            columns=list(b.STRUCTURAL_COLUMNS),budget_feature=BUDGET_FEATURE,
            target=TARGET,decision_rule=DECISION_RULE,area_per_op=self.area_per_op,
            training_ids=list(self.training_ids),members=members,model_artifacts=artifacts,
            source_bindings={name:c.sha(c.ROOT/name) for name in SOURCES},
            packages={name:importlib.metadata.version(name) for name in PACKAGES},
            uncertainty_kind='bootstrap estimator disagreement',calibrated=False)
        c.seal(output/'schema.json',schema)
        return schema

    @classmethod
    def load(cls, output):
        """Require identical code/settings/packages and exact JSON booster hashes."""
        from xgboost import XGBClassifier
        output = Path(output).resolve()
        schema = c.unseal(output/'schema.json')
        c.require(schema.get('schema')=='isaforge-feasibility-selection-xgb-v1', 'Unknown feasibility schema')
        c.require(schema['settings']==MODEL_SETTINGS and schema['area_caps']==list(AREA_CAPS)
                  and schema['clock_mhz']==CLOCK_MHZ and schema['columns']==list(b.STRUCTURAL_COLUMNS)
                  and schema['budget_feature']==BUDGET_FEATURE and schema['target']==TARGET
                  and schema['decision_rule']==DECISION_RULE and schema['calibrated'] is False
                  and schema['uncertainty_kind']=='bootstrap estimator disagreement', 'Exported feasibility contract differs')
        c.require(set(schema['source_bindings'])==set(SOURCES), 'Missing feasibility source bindings')
        for name,expected in schema['source_bindings'].items():
            c.require(c.sha(c.ROOT/name)==expected, 'Exported feasibility source changed: '+name)
        c.require(set(schema['packages'])==set(PACKAGES), 'Missing feasibility dependency bindings')
        for name,expected in schema['packages'].items():
            c.require(importlib.metadata.version(name)==expected, 'Exported feasibility dependency changed: '+name)
        model = cls(schema['seed'])
        model.area_per_op = _number(schema['area_per_op'],'exported historical proxy',positive=True)
        model.training_ids = schema['training_ids']
        c.require(isinstance(model.training_ids,list) and model.training_ids and
                  all(isinstance(identity,str) and identity for identity in model.training_ids) and
                  len(set(model.training_ids))==len(model.training_ids), 'Invalid exported feasibility training IDs')
        c.require(isinstance(schema['members'],list) and len(schema['members'])==20 and
                  isinstance(schema['model_artifacts'],dict), 'Incomplete feasibility ensemble')
        model.models,model.constants,model.member_seeds = [],[],[]
        used = set()
        for index,entry in enumerate(schema['members']):
            c.require(isinstance(entry,dict) and type(entry.get('model_seed')) is int and
                      0<=entry['model_seed']<2**31-1, 'Invalid exported feasibility member seed')
            model.member_seeds.append(entry['model_seed'])
            if 'constant' in entry:
                c.require(set(entry)=={'model_seed','constant'} and
                          not isinstance(entry['constant'],bool) and entry['constant'] in (0,1),
                          'Invalid constant feasibility member')
                model.models.append(None);model.constants.append(float(entry['constant']))
            else:
                name = f'member-{index:02d}.json'
                c.require(set(entry)=={'model_seed','artifact'} and entry['artifact']==name and
                          name in schema['model_artifacts'], 'Invalid feasibility booster descriptor')
                path = (output/name).resolve()
                c.require(path.is_relative_to(output) and c.sha(path)==schema['model_artifacts'][name],
                          'Exported feasibility booster changed')
                member = XGBClassifier();member.load_model(path)
                model.models.append(member);model.constants.append(None);used.add(name)
        c.require(used==set(schema['model_artifacts']), 'Unreferenced feasibility booster artifact')
        return model
