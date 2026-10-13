"""Score a completely measured, novel synthetic probe without model selection."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .area_model import _metrics, _validated_rows
from .features import parse_formula


def score_probe(training_rows, candidates, measured, predictions):
    """Require full identity coverage and canonical novelty; report all strata."""
    old = {parse_formula(r['formula']).canonical() for r in training_rows}
    def index(rows):
        result = {}
        for row in rows:
            key = (row['benchmark'], row['candidate_id'])
            if key in result:
                raise ValueError('duplicate candidate identity')
            result[key] = row
        return result
    declared, actual = index(candidates), index(measured)
    if not declared or set(declared) != set(actual):
        raise ValueError('probe measurement coverage differs from frozen candidates')
    formulas = [parse_formula(r['formula']).canonical() for r in candidates]
    if len(set(formulas)) != len(formulas) or old.intersection(formulas):
        raise ValueError('probe canonical formulas must be unique and novel')
    def number(v):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError('labels and predictions must be finite nonnegative numbers')
        return float(v)
    def metrics(keys, predicted):
        y = np.array([number(actual[k]['lut4_count']) for k in keys])
        p = np.array([number(predicted[k]['predicted_lut4']) for k in keys])
        result = _metrics(y.tolist(), p.tolist())
        positive, zero = y > 0, y == 0
        result['positive_mape_percent'] = float(100*np.mean(np.abs(y[positive]-p[positive])/y[positive])) if positive.any() else None
        result['positive_mape_count'] = int(positive.sum())
        result['zero_target_mae_lut4'] = float(np.mean(p[zero])) if zero.any() else None
        result['pearson'] = float(np.corrcoef(y, p)[0, 1]) if len(y)>1 and np.ptp(y)>0 and np.ptp(p)>0 else None
        return result
    for k, row in actual.items():
        if row['formula'] != declared[k]['formula'] or row.get('stratum') != declared[k]['stratum']:
            raise ValueError('measurement identity/formula/stratum mismatch')
        if row.get('correctness_verified') is not True or row.get('measurement_source') != 'rtl_synthesis':
            raise ValueError('probe requires verified actual synthesis labels')
    strata = sorted({r['stratum'] for r in candidates})
    report = {'evaluation_status':'Fresh synthetic probe; no real workload or published-system superiority claim',
              'candidate_count':len(candidates),'training_formula_count':len(old), 'models':{}}
    for name, rows in predictions.items():
        pred = index(rows)
        if set(pred) != set(declared):
            raise ValueError('prediction coverage differs from frozen candidates')
        if any(pred[k]['formula'] != declared[k]['formula'] for k in declared):
            raise ValueError('prediction formula mismatch')
        by_stratum = {s:metrics([k for k,r in declared.items() if r['stratum']==s], pred) for s in strata}
        report['models'][name] = {'pooled':metrics(list(declared), pred), 'by_stratum':by_stratum,
            'macro_stratum_mae_lut4':float(np.mean([m['mae_lut4'] for m in by_stratum.values()]))}
    if not predictions:
        raise ValueError('at least one complete prediction set is required')
    return report



def validate_model_freezes(training_rows, freeze_paths, prediction_paths, candidate_sha256):
    """Validate every comparator artifact and training cohort before label access.

    Hashes establish record consistency, not proof of who previously saw labels.
    """
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    validated = _validated_rows(training_rows)
    dataset_hash = hashlib.sha256(json.dumps(validated,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    count = len({r['formula'] for r in validated})
    artifacts, provenance = {}, []
    for path in freeze_paths:
        freeze = json.loads(path.read_text())
        try:
            timestamp = datetime.fromisoformat(freeze['frozen_at_utc'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('completed model freeze timestamp required') from error
        if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc):
            raise ValueError('model freeze timestamp must be timezone-aware and not in the future')
        if freeze.get('training_dataset_sha256') != dataset_hash or freeze.get('unique_formula_count') != count:
            raise ValueError('all comparator freezes must use the identical training dataset')
        sources = freeze.get('runtime_source_sha256')
        if not sources: raise ValueError('frozen runtime source hashes are required')
        for name, expected in sources.items():
            if Path(name).name != name or sha(Path(__file__).parent/name) != expected:
                raise ValueError('frozen model runtime source mismatch')
        if not freeze.get('artifacts'): raise ValueError('frozen comparator artifacts are required')
        for name, item in freeze['artifacts'].items():
            if name in artifacts: raise ValueError('duplicate frozen comparator name')
            artifact = Path(item['model_path'])
            if not artifact.is_file():
                local = [path.parent/artifact.name,path.parent/artifact.parent.name/artifact.name]
                artifact = next((p for p in local if p.is_file()),artifact)
            schema = json.loads(artifact.with_suffix('.json').read_text())
            digest = sha(artifact)
            if schema.get('artifact_sha256') != digest or schema.get('training_formula_count') != count:
                raise ValueError('frozen artifact integrity or training count mismatch')
            if item.get('artifact_sha256',digest) != digest:
                raise ValueError('preregistration artifact hash mismatch')
            artifacts[name] = digest
        provenance.append({'path':str(path),'sha256':sha(path),'frozen_at_utc':freeze['frozen_at_utc']})
    if set(artifacts) != set(prediction_paths):
        raise ValueError('all and only frozen comparators must be scored')
    for name, path in prediction_paths.items():
        timing = json.loads(path.with_suffix('.timing.json').read_text())
        if timing.get('model_sha256') != artifacts[name]:
            raise ValueError('prediction sidecar artifact hash mismatch')
        if timing.get('candidates_sha256',timing.get('candidate_sha256')) != candidate_sha256:
            raise ValueError('prediction sidecar candidate hash mismatch')
    return provenance


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training',type=Path,action='append',required=True)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--predictions',action='append',required=True,help='name=JSON path')
    parser.add_argument('--model-freeze',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    def read(p): return json.loads(p.read_text())
    def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    freeze=read(args.probe/'freeze.json'); completion=read(args.probe/'completion.json')
    if (not completion.get('complete') or completion['freeze_sha256']!=sha(args.probe/'freeze.json')
        or completion['dataset_sha256']!=sha(args.probe/'dataset.json')
        or freeze['candidate_sha256']!=sha(args.probe/'candidates.json')):
        raise ValueError('probe completion/freeze integrity failure')
    paths={}
    for value in args.predictions:
        name,path=value.split('=',1)
        if name in paths:raise ValueError('duplicate model name')
        paths[name]=Path(path)
    training = [r for p in args.training for r in read(p)]
    model_freezes = validate_model_freezes(training,args.model_freeze,paths,freeze['candidate_sha256'])
    report=score_probe(training,read(args.probe/'candidates.json'),
                       read(args.probe/'dataset.json'),{n:read(p) for n,p in paths.items()})
    # Timestamp ordering is a protocol property, not proof of absence of human
    # label access. Archive the precise model freeze used before scoring.
    report['provenance']={'probe_freeze_sha256':sha(args.probe/'freeze.json'),
        'dataset_sha256':sha(args.probe/'dataset.json'),'model_freezes':model_freezes,
        'scored_at_utc':datetime.now(timezone.utc).isoformat(),
        'prediction_sha256':{n:sha(p) for n,p in paths.items()},
        'training_dataset_sha256':{str(p):sha(p) for p in args.training},
        'evaluator_source_sha256':sha(Path(__file__))}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({n:v['pooled'] for n,v in report['models'].items()},indent=2))


if __name__=='__main__':main()
