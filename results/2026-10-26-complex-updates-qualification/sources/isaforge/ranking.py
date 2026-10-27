"""Fixed XGBoost pairwise ranking of measured application performance.

Adapts the pairwise runtime-ranking objective discussed by Chen et al. (NeurIPS
2018), using the existing structural/profile features. This is not an AutoTVM
reproduction. Query groups are workload/build/input contexts, never a shuffled
mixture of unrelated programs. Rank scores are not speedup estimates.
"""
from __future__ import annotations

from . import codesign as c
from .model import feature_matrix, validate_training_rows

PARAMETERS = dict(objective='rank:pairwise', n_estimators=80, max_depth=2,
                  learning_rate=0.05, min_child_weight=1, reg_lambda=1.0,
                  subsample=1.0, colsample_bytree=1.0, tree_method='hist',
                  n_jobs=1, verbosity=0, lambdarank_pair_method='mean',
                  lambdarank_num_pair_per_sample=8)


def grouped_labels(rows):
    """Dense within-context relevance levels preserve ties and actual ordering."""
    validate_training_rows(rows)
    c.require(all(isinstance(r.get('benchmark'), str) and r['benchmark'] for r in rows),
              'Explicit workload/build/input query group required')
    c.require(len({r['candidate_id'] for r in rows}) == len(rows), 'Duplicate training identity')
    ordered = sorted(rows, key=lambda r: (r['benchmark'], r['candidate_id']))
    labels, qids, groups = [], [], []
    for qid, group in enumerate(sorted({r['benchmark'] for r in ordered})):
        members = [r for r in ordered if r['benchmark'] == group]
        levels = sorted({r['speedup'] for r in members})
        labels.extend(levels.index(r['speedup']) for r in members)
        qids.extend([qid] * len(members))
        groups.append({'benchmark': group, 'rows': len(members), 'distinct_labels': len(levels)})
    return ordered, labels, qids, groups


class SpeedupRanker:
    def __init__(self, seed=0):
        c.require(type(seed) is int and seed >= 0, 'Invalid seed')
        self.seed, self.model = seed, None
        self.warnings = ['Rank scores express ordering only; no speedup or uncertainty calibration.']

    def fit(self, rows):
        from xgboost import XGBRanker
        ordered, labels, qids, self.groups = grouped_labels(list(rows))
        c.require(any(g['distinct_labels'] > 1 for g in self.groups),
                  'Ranking needs a measured unequal pair within a query group')
        self.model = XGBRanker(**PARAMETERS, random_state=self.seed)
        self.model.fit(feature_matrix(ordered), labels, qid=qids)
        self.training_ids = [r['candidate_id'] for r in ordered]
        return self

    def predict(self, rows):
        import math
        c.require(self.model is not None, 'Fit before predict')
        rows = list(rows)
        if not rows:
            return []
        scores = self.model.predict(feature_matrix(rows))
        c.require(all(math.isfinite(float(score)) for score in scores), 'Nonfinite ranking prediction')
        return [{'candidate_id': row['candidate_id'], 'rank_score': float(score)}
                for row, score in zip(rows, scores)]
