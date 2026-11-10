#!/usr/bin/env python3
"""Package/replay the frozen synthetic check; no native jobs or fitting."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import validate_selected_features as validation
sha=validation.sha
read=validation.read
write=validation.write
need=validation.need


def package(output):
    need((output/'completion.json').is_file(),'Completed attempt required')
    archive=output/'raw-evidence.zip';need(not archive.exists(),'Archive already exists')
    raw=output/'raw';members={};omitted=[]
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as stream:
        for path in sorted(raw.rglob('*')):
            if not path.is_file():continue
            relative=path.relative_to(raw).as_posix()
            # Compiled intermediates are reproducible from retained actual source,
            # vectors, build log, tool identity, and successful comparison log.
            if 'obj_dir' in path.parts:
                omitted.append({'path':relative,'sha256':sha(path),'bytes':path.stat().st_size});continue
            stream.write(path,relative)
            members[relative]={'sha256':sha(path),'bytes':path.stat().st_size}
    (output/'.gitignore').write_text('raw/\n')
    write(output/'raw-evidence-manifest.json',{'archive':'raw-evidence.zip','archive_sha256':sha(archive),
        'members':members,'omitted_rebuildable_verilator_intermediates':omitted,
        'packaged_at_utc':validation.now(),'scope':'Exact source, labels, netlists, logs, feature manifests and verification vectors retained. Local raw files ignored; no scientific rerun.'})
    return {'archive_sha256':sha(archive),'member_count':len(members)}


def replay(output):
    # Authenticate recorded tool identities, without requiring installed tools.
    plan=read(output/'plan.json');amendment=read(output/'pre-native-amendment.json')
    need(amendment['original_plan_sha256']==sha(output/'plan.json'),'Original plan changed')
    for relative,digest in {**plan['sources'],**amendment['corrected_sources']}.items():
        need(sha(ROOT/relative)==digest,'Source differs:'+relative)
    for name,digest in plan['inputs'].items():need(sha(output/name)==digest,'Input differs:'+name)
    for name,digest in plan['pipeline_recovery'].items():
        need(sha(output/'recovered-pipeline'/name)==digest,'Recovered source differs')
    for relative,digest in read(output/'model-freeze.json')['models'].items():
        need(sha(ROOT/relative)==digest,'Frozen model differs')
    done=read(output/'completion.json');need(done['fits']==0,'No fits required')
    seal=read(output/'point-freeze.json')
    for key,name in [('plan_sha256','plan.json'),('model_freeze_sha256','model-freeze.json'),('features_sha256','features.json'),('predictions_sha256','predictions.json')]:
        need(seal[key]==sha(output/name),'Frozen payload differs:'+name)
    amendment=output/'pre-native-amendment.json'
    need(seal['pre_native_amendment_sha256']==sha(amendment),'Amendment seal differs')
    rows=read(output/'candidates.json');points=read(output/'predictions.json');labels=read(output/'labels.json')
    need(points['candidate_ids']==[r['candidate_id'] for r in rows],'Point cohort alignment differs')
    need([r['candidate_id'] for r in labels]==points['candidate_ids'],'Label alignment differs')
    manifest=read(output/'raw-evidence-manifest.json');archive=output/manifest['archive']
    need(sha(archive)==manifest['archive_sha256'],'Raw archive digest differs')
    with zipfile.ZipFile(archive) as stream:
        need(set(stream.namelist())==set(manifest['members']),'Archive membership differs')
        for name,record in manifest['members'].items():
            body=stream.read(name)
            need(len(body)==record['bytes'] and hashlib.sha256(body).hexdigest()==record['sha256'],'Raw evidence differs:'+name)
        proof=json.loads(stream.read('verification/result.json'))
        need(proof['verified'] is True and proof['formula_count']==40 and proof['vectors_per_formula']==2148 and proof['total_comparisons']==85920,'Original verification incomplete')
        need(hashlib.sha256(stream.read('verification/vectors.txt')).hexdigest()==proof['vectors_sha256'],'Verification vectors differ')
        need(hashlib.sha256(stream.read('verification/verification.v')).hexdigest()==proof['rtl_sha256'],'Verification RTL differs')
        for i,label in enumerate(labels):
            if label.get('status')!='complete':continue
            body=stream.read(f'labels/{i}/ice40-netlist.json')
            need(hashlib.sha256(body).hexdigest()==label['netlist_sha256'],'Mapped netlist differs')
            cells=json.loads(body)['modules']['candidate']['cells']
            counts=Counter(c['type'] for c in cells.values())
            need(counts['SB_LUT4']==label['lut4'] and counts['SB_CARRY']==label['carry'],'Mapped resources differ')
            from isaforge.rtl import generate_rtl
            rtl=stream.read(f'labels/{i}/candidate.v')
            need(rtl.decode()==generate_rtl(rows[i]['formula']) and hashlib.sha256(rtl).hexdigest()==label['rtl_sha256'],'Measured original RTL differs')
    if done['complete']:
        calculated=validation.metrics(rows,points['models'],labels)
        need(calculated==read(output/'metrics.json'),'Recomputed point metrics differ')
    return {'verified':True,'native_jobs':0,'fits':0,'complete':done['complete'],
            'label_count':done['label_count'],'raw_archive_sha256':manifest['archive_sha256']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['package','replay'])
    parser.add_argument('--output',type=Path,default=ROOT/'results/selection-validation')
    args=parser.parse_args();print(json.dumps((package if args.command=='package' else replay)(args.output.resolve()),indent=2))
