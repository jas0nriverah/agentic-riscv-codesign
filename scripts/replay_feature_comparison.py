#!/usr/bin/env python3
"""Verify the retained feature comparison using the Python standard library only."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VIEWS=('mapping217','original336','selected128')


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def mean(values):return sum(values)/len(values)


def metrics(rows,view):
    groups=defaultdict(list);errors=[];positive=[];zero=[];under=[]
    for row in rows:
        y,p=row['actual_lut4'],row['predicted_lut4'][view]
        assert math.isfinite(y) and math.isfinite(p) and y>=0 and p>=0
        error=abs(p-y);errors.append(error);groups[row['group']].append(error)
        if y>0:positive.append(error/y)
        else:zero.append(error)
        under.append(max(y-p,0))
    result={'count':len(rows),'group_count':len(groups),
        'group_macro_mae_lut4':mean([mean(values) for values in groups.values()]),
        'pooled_mae_lut4':mean(errors),'positive_count':len(positive),
        'positive_mape_percent':mean(positive)*100 if positive else None,
        'zero_count':len(zero),'zero_mae_lut4':mean(zero) if zero else None,
        'maximum_underprediction_lut4':max(under),'caps':{}}
    for cap in (32,64,128):
        safe=[r for r in rows if r['predicted_lut4'][view]<=cap]
        actual=[r for r in rows if r['actual_lut4']<=cap]
        false_safe=sum(r['actual_lut4']>cap for r in safe)
        rejected=sum(r['predicted_lut4'][view]>cap for r in actual)
        result['caps'][str(cap)]={'predicted_safe_count':len(safe),'false_safe_count':false_safe,
            'false_safe_fraction_of_predicted_safe':false_safe/len(safe) if safe else None,
            'actually_safe_count':len(actual),'false_rejection_count':rejected,
            'false_rejection_fraction_of_actually_safe':rejected/len(actual) if actual else None}
    return result


def equal(actual,expected):
    if isinstance(expected,dict):
        assert set(actual)==set(expected)
        for key in expected:equal(actual[key],expected[key])
    elif isinstance(expected,list):
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected):equal(a,b)
    elif isinstance(expected,float):assert math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12),(actual,expected)
    else:assert actual==expected,(actual,expected)


def replay(output):
    output=Path(output);manifest=read(output/'manifest.json');protocol=read(output/'protocol.json')
    for name,digest in manifest['files_sha256'].items():assert sha(output/name)==digest,name
    for name,digest in protocol['input_sha256'].items():assert sha(output/name)==digest,name
    assert protocol['runner_sha256']==sha(ROOT/'scripts/compare_features.py')
    summary=read(output/'summary.json');rows=read(output/'predictions.json');folds=read(output/'folds.json')
    assert len(rows)==1665 and summary['fits_completed']==15 and summary['total_wall_seconds']<=600
    assert summary['protocol_sha256']==sha(output/'protocol.json')
    assert read(output/'run-start.json')['protocol_sha256']==sha(output/'protocol.json')
    seen=defaultdict(set)
    for i,(row,fold) in enumerate(zip(rows,folds)):
        assert row['row_index']==fold['row_index']==i
        assert row['group']==fold['group'] and row['validation_fold']==fold['validation_fold']
        seen[row['group']].add(row['validation_fold'])
        if row['original_zero_override']:assert all(row['predicted_lut4'][v]==0 for v in VIEWS)
    assert all(len(f)==1 for f in seen.values())
    selections=read(output/'selected-columns.json');columns=read(output/'columns.json')
    assert len(selections)==5
    for fold,selection in enumerate(selections):
        importance=selection['full336_training_importances']
        expected=sorted(sorted(range(336),key=lambda i:(-importance[i],i))[:128])
        assert selection['selected_indices']==expected and selection['selected_columns']==[columns[i] for i in expected]
        assert selection['training_rows']==[i for i,row in enumerate(rows) if row['validation_fold']!=fold]
    timings=read(output/'timings.json');assert len(timings)==15
    assert {(r['fold'],r['view']) for r in timings}=={(f,v) for f in range(5) for v in VIEWS}
    strata=sorted({r['stratum'] for r in rows})
    for view in VIEWS:
        result=metrics(rows,view)
        result['by_stratum']={s:metrics([r for r in rows if r['stratum']==s],view) for s in strata}
        result['stratum_macro_mae_lut4']=mean([result['by_stratum'][s]['pooled_mae_lut4'] for s in strata])
        result['by_fold']=[metrics([r for r in rows if r['validation_fold']==f],view) for f in range(5)]
        equal(result,summary['metrics'][view])
    print(json.dumps({'status':'pass','rows':len(rows),'groups':len(seen),'folds':5,'verified_fits':15,'new_fits':0}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/feature-comparison')
    replay(parser.parse_args().output)
