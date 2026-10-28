"""Extend authenticated expanded r2 after two completed forward studies.

Read-only evidence consumption; no fitting, target jobs or prospective claim.
The two new studies fit the earlier 156-label corpus, never this later export.
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c, budgeted_selection as b
from scripts import export_expanded_selection_corpus as base_export

BASE = ROOT / 'results/2026-10-28-expanded-selection-corpus-r2'
DEFAULT_OUTPUT = ROOT / 'results/2026-10-28-expanded-selection-corpus-r3'
STUDIES = (
    ('results/2026-10-28-countnegative-v2-selection-r1',4,'tacle-countnegative'),
    ('results/2026-10-28-mibench-stringsearch-v2-selection-r1',2,'mibench-stringsearch-pbm'),
)
SCHEMA = 'isaforge-incremental-selection-development-corpus-v1'
require, verify_manifest = base_export.require, base_export.verify_manifest


def _bind(bindings, *paths):
    for path in paths:
        path = Path(path).resolve()
        require(path.is_relative_to(ROOT),'Source binding escapes repository')
        for item in (path,Path(str(path)+'.sha256')):
            bindings[item.relative_to(ROOT).as_posix()] = c.sha(item)


def _context(study_root, context_id, group, *, forward=False):
    """Load actual contexts through sealed release → prereg manifest bindings."""
    folder = (ROOT/study_root).resolve()
    require(folder.is_relative_to(ROOT),'Study path escapes repository')
    manifest = verify_manifest(folder)
    release_path = folder/'release.json'
    require(manifest.get('release.json') == c.sha(release_path),'Release not bound by study manifest')
    release = c.unseal(release_path)
    prereg = (ROOT/release['preregistration']).resolve()
    require(prereg.is_relative_to(ROOT),'Preregistration path escapes repository')
    prereg_manifest = prereg/'manifest.json'
    require(release['preregistration_manifest_sha256'] == c.sha(prereg_manifest),
            'Released preregistration manifest differs')
    pmanifest = c.unseal(prereg_manifest)
    context_path = prereg/'inputs/context.json'
    require(pmanifest.get('inputs/context.json') == c.sha(context_path),
            'Source context differs from sealed preregistration')
    context = c.unseal(context_path)
    require(context['context_id'] == context_id == release['target_context_id'] and
            context['workload_group'] == group,'Source context/group identity differs')
    bindings = {}
    _bind(bindings,folder/'manifest.json',release_path,prereg_manifest,context_path)
    metadata = dict(study_root=study_root,context_id=context_id,source_id=group+':'+context_id)
    if forward:
        protocol_path = prereg/'preregistration.json'
        require(pmanifest.get('preregistration.json') == c.sha(protocol_path),
                'Forward study preregistration is not sealed')
        protocol = c.unseal(protocol_path)
        require(protocol['historical_rows'] == 156 and protocol['target_labels_read'] == 0 and
                protocol['target_labels_observed'] == 0 and protocol['candidate_attempts_before_fit'] == 0 and
                protocol['target_context_id'] == context_id and protocol['target_workload'] == group,
                'Forward study did not freeze against zero-label target and 156-label history')
        _bind(bindings,protocol_path)
        metadata.update(prelabel_historical_successes=156,
            family_filtered_training_rows=protocol['family_excluded_training_rows'],
            prelabel_commit=release['prelabel_commit'])
    return context,bindings,metadata,release


def _read_study(rel,count,group):
    folder = (ROOT/rel).resolve()
    manifest = verify_manifest(folder)
    require(all(n in manifest for n in ('outcomes.json','native-audit.json','release.json')),
            'Study outcome/audit/release not sealed')
    outcomes = c.unseal(folder/'outcomes.json')
    audit = c.unseal(folder/'native-audit.json')
    require(audit.get('schema') == 'isaforge-guarded-evidence-v1' and
            audit.get('attempt_collection_complete') is True and
            audit.get('candidate_wall_seconds_complete') is True and
            audit.get('charged_candidate_attempts') == count and not audit.get('unattempted') and
            len(outcomes) == len(audit['outcomes']) == count,
            'Complete charged study with known attempt costs required')
    public,names = audit['public'],audit['pool_names']
    require(len(public) == len(names) == len(set(names)) == count,'Public pool count/names differ')
    context,bindings,metadata,release = _context(rel,audit['context_id'],group,forward=True)
    pool = {r['candidate_id']:(r,name) for r,name in zip(public,names)}
    require(len(pool) == count and release['pool_names'] == names and
            release['pool_roster'] == [dict(name=name,candidate_id=r['candidate_id'],formula=r['formula'])
                                      for r,name in zip(public,names)],'Released roster differs from audited public pool')
    indexed = {r['candidate_id']:r for r in outcomes}
    audited = {r['candidate_id']:r for r in audit['outcomes']}
    require(len(indexed) == len(audited) == count and set(indexed) == set(audited) == set(pool),
            'Duplicate or missing outcome identities')
    successful = {r['candidate_id']:r for r in audit['successful']}
    failed = {r['name']:r for r in audit['failed_or_interrupted']}
    require(len(successful) == len(audit['successful']) and len(failed) == len(audit['failed_or_interrupted']) and
            len(successful)+len(failed) == count,'Success/failure audit partition differs')
    rows,failures = [],[]
    for identity,row in indexed.items():
        public_row,name = pool[identity]
        require(row == audited[identity],'Native audit disagrees with sealed outcome')
        require(row['benchmark'] == group+':'+audit['context_id'] and
                identity == c.digest([audit['context_id'],row['formula']]),'Outcome source/formula identity differs')
        success = b.validate_outcome(row,public_row)
        normal = base_export._normalise(row,group=group,consumed=success)
        if success:
            require(identity in successful and name not in failed and
                    successful[identity]['name'] == name and
                    successful[identity]['measurement_seconds'] == row['measurement_seconds'] and
                    successful[identity]['speedup'] == row['speedup'] and
                    successful[identity]['cycles'] == row['candidate_cycles'] and
                    successful[identity]['area_delta_lut4'] == row['area_delta_lut4'],
                    'Successful outcome cost/measurement differs from native audit record')
            rows.append(normal)
        else:
            require(identity not in successful and name in failed and failed[name]['status'] == 'failed' and
                    failed[name]['elapsed_seconds'] == row['measurement_seconds'] and
                    failed[name]['reference_censored'] == row['reference_censored'] and
                    failed[name]['classification'] == row['failure_class'],
                    'Failed/unknown outcome cost/classification differs from native audit')
            failures.append(normal)
    require(set(audit['reference_censored_candidates']) ==
            {name for name,value in failed.items() if value['reference_censored']},
            'Reference-censored failure roster differs from known failed outcomes')
    total = sum(r['measurement_seconds'] for r in outcomes)
    require(math.isfinite(audit['candidate_wall_seconds']) and
            math.isclose(total,audit['candidate_wall_seconds'],rel_tol=0,abs_tol=1e-6),
            'Study attempt costs do not equal audited charged total')
    _bind(bindings,folder/'outcomes.json',folder/'native-audit.json')
    metadata.update(successful_rows=len(rows),failed_attempts=len(failures),charged_attempts=count,
        candidate_wall_seconds=audit['candidate_wall_seconds'],
        reference_censored_candidate_names=list(audit['reference_censored_candidates']))
    return rows,failures,context,bindings,metadata


def _collect():
    base,manifest = base_export.authenticate(BASE)
    rows,failures = list(base['rows']),list(base['failed_attempts'])
    contexts,bindings = dict(base['contexts']),{}
    _bind(bindings,BASE/'manifest.json',BASE/'corpus.json',BASE/'provenance.json')
    for source in base['new_source_contexts']:
        group = source['source_id'].split(':',1)[0]
        context,bound,_,_ = _context(source['study_root'],source['context_id'],group)
        require(source['source_id'] == group+':'+context['context_id'],'Base source context differs')
        require(source['source_id'] not in contexts or contexts[source['source_id']] == context,
                'Conflicting base context')
        contexts[source['source_id']] = context
        bindings.update(bound)
    added_contexts,studies,new_cost,new_attempts = [],[],0.0,0
    for rel,count,group in STUDIES:
        added,failed,context,bound,metadata = _read_study(rel,count,group)
        rows.extend(added);failures.extend(failed)
        key = group+':'+context['context_id']
        require(key not in contexts or contexts[key] == context,'Conflicting incremental context')
        contexts[key] = context
        added_contexts.append(dict(source_id=key,context_id=context['context_id'],study_root=rel))
        bindings.update(bound);studies.append(metadata)
        new_cost += metadata['candidate_wall_seconds'];new_attempts += count
    ids = [r['candidate_id'] for r in rows+failures]
    require(len(ids) == len(set(ids)),'Duplicate candidate identity across successes/failures')
    require({r['benchmark'] for r in rows+failures} <= set(contexts),
            'Actual authenticated provenance context required for every row')
    require(len(rows)+len(failures) == base['total_candidate_attempts']+new_attempts,
            'Incremental attempt totals differ')
    corpus = dict(schema=SCHEMA,scope='Consumed development data; new forward studies fit only the earlier 156-label corpus.',
        rows=rows,failed_attempts=failures,contexts=contexts,
        new_source_contexts=[*base['new_source_contexts'],*added_contexts],
        successful_labels=len(rows),failed_attempt_count=len(failures),total_candidate_attempts=len(ids),
        independent_workload_groups=sorted({r['workload_group'] for r in rows}),
        base_successful_labels=base['successful_labels'],base_failed_attempts=len(base['failed_attempts']),
        base_total_candidate_attempt_wall_seconds=base['total_candidate_attempt_wall_seconds'],
        incremental_candidate_attempts=new_attempts,incremental_candidate_wall_seconds=new_cost,
        total_candidate_attempt_wall_seconds=base['total_candidate_attempt_wall_seconds']+new_cost,
        timer_note='Base156 cumulative audited attempt cost added once; only the two new studies contribute incremental costs. Native/outer scopes overlap and are not added.',
        new_native_jobs=0,all_rows_consumed_for_development=True)
    provenance = dict(exporter_sha256=c.sha(__file__),base_exporter_sha256=c.sha(base_export.__file__),
        source_bindings=bindings,studies=studies,base_manifest_sha256=c.sha(BASE/'manifest.json'),
        forward_studies_frozen_history_successful_labels=156)
    return corpus,provenance


def export(output=DEFAULT_OUTPUT):
    output = Path(output).resolve()
    require(not output.exists(),'Fresh corpus output required')
    corpus,provenance = _collect()
    output.mkdir(parents=True)
    c.seal(output/'corpus.json',corpus);c.seal(output/'provenance.json',provenance)
    c.seal(output/'manifest.json',{p.name:c.sha(p) for p in sorted(output.iterdir()) if p.is_file()})
    return corpus


def authenticate(path):
    folder = Path(path).resolve()
    manifest = verify_manifest(folder)
    corpus,provenance = c.unseal(folder/'corpus.json'),c.unseal(folder/'provenance.json')
    require(provenance['exporter_sha256'] == c.sha(__file__),'Incremental exporter source changed')
    expected,expected_provenance = _collect()
    require(corpus == expected and provenance == expected_provenance,
            'Incremental corpus/provenance differs from rederived authenticated sources')
    return corpus,manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--verify',type=Path)
    args = parser.parse_args()
    result = authenticate(args.verify)[0] if args.verify else export(args.output)
    print({k:result[k] for k in ('successful_labels','failed_attempt_count','total_candidate_attempts','total_candidate_attempt_wall_seconds')})
