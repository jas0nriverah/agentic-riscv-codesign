"""Authenticated training evidence from the incomplete Ascon v5 campaign.

This deliberately does not implement the ordinary measured-corpus schema.
The three measured rows are useful history; nine unmeasured outcomes prevent
using this supplement as a test pool, complete oracle, or selection benchmark.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

from . import budgeted_selection as b, codesign as c
from .model import feature_matrix, validate_training_rows
from .ranking import grouped_labels
from .speedup_corpus import family

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'isaforge/ascon_training_supplement.py'
SCHEMA = 'isaforge-training-only-ascon-supplement-v1'
SOURCE_ROOT = ROOT/'results/2026-10-27-ascon-selector-chat-run-v5'
HISTORY_ROOT = ROOT/'results/2026-10-26-lift-selection-corpus'
OUTPUT = ROOT/'results/2026-10-28-ascon-training-supplement-r1'
GROUP = 'ascon128v13-kat-v13'
PINS = {
    'report.json': '744ef43c510b260c4db1eb2fc819eb331008ddbb7f5d51dcdd9b06a91539aa6b',
    'raw-manifest.json': 'ca9d11e8741e86d6579b0908b91f75d7858553c91efe23349c65890eb0c86a54',
    'raw-evidence.zip': 'b69c5f082a33b68c71104760054babef4f4d3138cfa9f6104df8a80879fc8acf',
}
HISTORY_PINS = {
    'corpus.json': '901413111da94933a1c14f0e758c1cf96f959bde44325e79ded6e47c4b8743ef',
    'manifest.json': '219806a8a9c569f783ecbbe82561f2c3199dcb1faa83054710141fdfef0930c8',
}
AUDIT_PINS = (
    '1cf479d87ccaed4f993606f5789ea131d292dd00b2bcc4f3a6425c0fb519cc70',
    '97ed475d33262f20ba48280d15151a25052acd139ee23de8d08a5c72092a1b0b',
    '8e29bec430a1c8cc7555f41cb54f8b5d395538b9c69afbf12897a9530fa26839',
)
TIMER_SCOPE = ('guarded native attempt-ledger monotonic elapsed including validation; '
               'measurement-record and outer controller durations are separate overlapping scopes')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _relative(name):
    c.require(isinstance(name, str) and name and '\\' not in name,
              'Nonempty portable relative evidence path required')
    path = PurePosixPath(name)
    c.require(not path.is_absolute() and '..' not in path.parts and str(path) == name,
              'Unsafe or noncanonical evidence path')
    return path


def _manifest(root):
    value = c.unseal(root/'manifest.json')
    c.require(isinstance(value, dict) and value, 'Nonempty evidence manifest required')
    for name, digest in value.items():
        _relative(name)
        path = root/name
        c.require(path.is_file() and not path.is_symlink() and c.sha(path) == digest,
                  'Evidence manifest member changed: '+name)


def _authenticate_archive(source, destination):
    """Authenticate the exact archived release before restoring regular files."""
    for name, digest in PINS.items():
        c.require(c.sha(source/name) == digest, 'Pinned Ascon source changed: '+name)
    c.require((source/'raw-manifest.sha256').read_text().split() ==
              [PINS['raw-manifest.json'], 'raw-manifest.json'], 'Raw manifest seal changed')
    report, manifest = c.read(source/'report.json'), c.read(source/'raw-manifest.json')
    c.require(manifest['report_sha256'] == PINS['report.json'] and
              manifest['raw_archive_sha256'] == report['raw_archive_sha256'] == PINS['raw-evidence.zip'],
              'Archive/report binding differs')
    members = manifest['members']
    c.require(len(members) == manifest['member_count'] == report['raw_archive_member_count'] == 679,
              'Exact archived member inventory required')
    inventory = {row['path']: row for row in members}
    c.require(len(inventory) == len(members), 'Duplicate raw manifest path')
    with zipfile.ZipFile(source/'raw-evidence.zip') as archive:
        entries = archive.infolist()
        c.require(len(entries) == len({row.filename for row in entries}) == 679 and
                  {row.filename for row in entries} == set(inventory), 'Archive member inventory differs')
        c.require(sum(row.file_size for row in entries) == 36_267_147, 'Archive expanded size differs')
        contents = {}
        for entry in entries:
            _relative(entry.filename)
            mode = entry.external_attr >> 16
            c.require(not entry.is_dir() and (not stat.S_IFMT(mode) or stat.S_ISREG(mode)),
                      'Only regular archived evidence files are supported')
            data = archive.read(entry)
            expected = inventory[entry.filename]
            c.require(len(data) == expected['bytes'] and _sha(data) == expected['sha256'],
                      'Archived evidence bytes differ: '+entry.filename)
            contents[entry.filename] = data
        for name, data in contents.items():
            if name+'.sha256' in contents:
                c.require(contents[name+'.sha256'].decode().split() == [_sha(data)],
                          'Archived paired seal differs: '+name)
        for name, data in contents.items():
            path = destination/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    return report, inventory


def validate(value, *, purpose='training'):
    """Validate the separate training view; reject evaluation/oracle use."""
    c.require(purpose == 'training', 'Incomplete Ascon supplement is training-only; test/oracle use is forbidden')
    c.require(value.get('schema') == SCHEMA and value.get('training_only') is True and
              value.get('evaluation_eligible') is False and value.get('complete_pool') is False and
              type(value.get('independent_confirmatory_families')) is int and
              value['independent_confirmatory_families'] == 0 and value.get('oracle') is None,
              'Training-only incomplete-pool contract differs')
    c.require('rows' not in value and 'failed_attempts' not in value,
              'Supplement must not masquerade as an evaluation corpus')
    c.require(value['source_artifacts'] == PINS and value['historical_artifacts'] == HISTORY_PINS and
              value['audit_prefix_sha256'] == list(AUDIT_PINS), 'Pinned input/audit bindings differ')
    rows, roster = value['training_rows'], value['full_target_roster']
    ids = [row['candidate_id'] for row in rows]
    public = {row['candidate_id']: row for row in roster}
    c.require(len(rows) == len(set(ids)) == 3 and len(roster) == len(public) == 12,
              'Exactly three measured rows and twelve public candidates required')
    c.require(set(ids) <= set(public) and value['unmeasured_candidate_ids'] == sorted(set(public)-set(ids)) and
              len(value['unmeasured_candidate_ids']) == 9, 'Unmeasured target inventory differs')
    c.require(value['coverage'] == dict(measured_successes=3, pool_candidates=12, unmeasured_candidates=9,
              new_expression_families=0), 'Incomplete-pool coverage differs')
    validate_training_rows(rows)
    feature_matrix(rows)
    b.structural_matrix(rows)
    grouped_labels(rows)
    evidence = value['row_evidence']
    c.require(set(evidence) == set(ids), 'Exact per-row provenance required')
    for row in rows:
        identity = row['candidate_id']
        c.require(row['status'] == 'success' and row['workload_group'] == GROUP and
                  row['candidate_family'] == family(row['formula']) and
                  row['measurement_timer_scope'] == TIMER_SCOPE and
                  b.validate_outcome(row, public[identity]), 'Invalid verified training row')
        item = evidence[identity]
        c.require(item['derived_training_row_sha256'] == c.digest(row) and
                  item['audit_sha256'] in AUDIT_PINS and item['historical_family_matches'] and
                  item['formula_family'] == row['candidate_family'] and
                  item['terminal_native_status'] == 'success', 'Training row provenance differs')
    c.require(value['new_model_fits'] == value['new_model_predictions'] == value['new_native_jobs'] == 0,
              'Importer cannot create model or native results')
    return copy.deepcopy(rows)


def build(*, source=SOURCE_ROOT, historical=HISTORY_ROOT):
    """Recount archived raw evidence; do not train or execute a native tool."""
    from . import ascon_workload as ascon, guarded_evidence
    source, historical = Path(source).resolve(), Path(historical).resolve()
    for name, digest in HISTORY_PINS.items():
        c.require(c.sha(historical/name) == digest, 'Frozen historical corpus changed: '+name)
    _manifest(historical)
    history = c.unseal(historical/'corpus.json')
    c.require(len(history['rows']) == history['successful_labels'] == 122 and
              len(history['failed_attempts']) == 4, 'Original historical evidence required')
    old_ids = {row['candidate_id'] for row in history['rows']+history['failed_attempts']}
    with tempfile.TemporaryDirectory(prefix='isaforge-ascon-training-audit-') as temporary:
        report, inventory = _authenticate_archive(source, Path(temporary))
        root = Path(temporary)/'campaign'
        public = c.unseal(root/'public.json')
        commands = c.unseal(root/'commands.json')
        attempts = report['attempts']
        c.require([row['slot'] for row in attempts] == [1, 2, 3] and
                  [row['audit_sha256'] for row in attempts] == list(AUDIT_PINS),
                  'Exact three charged Ascon attempts required')
        evidence, rows = {}, []
        for attempt in attempts:
            name, slot = attempt['name'], attempt['slot']
            native_path = f'campaign/attempt-ledger/{name}.json'
            measurement_path = f'campaign/measurements/{name}/measurement.json'
            slot_path = f'campaign/selector-controller/attempt-{slot:02d}.json'
            terminal = c.unseal(Path(temporary)/slot_path)
            ledger = c.unseal(Path(temporary)/native_path)
            measurement = c.unseal(Path(temporary)/measurement_path)
            outcome = attempt['outcome']
            c.require(attempt == terminal and attempt['status'] == ledger['status'] == 'success' and
                      ledger['record_sha256'] == inventory[measurement_path]['sha256'],
                      'Terminal controller/native measurement binding differs')
            c.require(outcome['candidate_id'] not in old_ids and outcome['candidate_id'] == measurement['candidate_id'],
                      'New unique measured context identity required')
            row = dict(copy.deepcopy(outcome), status='success', measurement_timer_scope=TIMER_SCOPE)
            matches = [dict(candidate_id=old['candidate_id'], workload_group=old['workload_group'], formula=old['formula'])
                       for old in history['rows'] if family(old['formula']) == family(row['formula'])]
            evidence[row['candidate_id']] = dict(slot=slot, handle=attempt['handle'], name=name,
                formula_family=family(row['formula']), historical_family_matches=matches,
                terminal_native_status=ledger['status'], audit_sha256=attempt['audit_sha256'],
                native_ledger_path=native_path, native_ledger_sha256=inventory[native_path]['sha256'],
                measurement_path=measurement_path, measurement_sha256=inventory[measurement_path]['sha256'],
                controller_slot_path=slot_path, controller_slot_sha256=inventory[slot_path]['sha256'],
                archived_outcome_sha256=c.digest(outcome), derived_training_row_sha256=c.digest(row),
                outer_controller_elapsed_seconds=attempt['controller_elapsed_seconds'])
            rows.append(row)
        # Recover each original paid prefix exactly. Temporary changes never touch
        # archived/native evidence; the audit itself runs no native subprocesses.
        for count in (3, 2, 1):
            attempt = attempts[count-1]
            ledger = c.unseal(root/'attempt-ledger'/(attempt['name']+'.json'))
            c.seal(root/'commands.json', commands[:ledger['receipt_end']])
            with ascon.registration():
                audited = guarded_evidence.audit(root)
            c.require(c.digest(audited) == AUDIT_PINS[count-1] and
                      audited['charged_candidate_attempts'] == len(audited['outcomes']) == count and
                      audited['attempt_collection_complete'] is False,
                      'Exact historical native audit prefix differs')
            by_id = {row['candidate_id']: row for row in audited['outcomes']}
            for paid in attempts[:count]:
                derived = dict(by_id[paid['candidate_id']], workload_group=GROUP,
                               candidate_family=family(paid['formula']))
                c.require(derived == paid['outcome'], 'Raw audited label differs from archived controller outcome')
            shutil.rmtree(root/'measurements'/attempt['name'])
            for suffix in ('.json', '.json.sha256'):
                (root/'attempt-ledger'/(attempt['name']+suffix)).unlink()
    value = dict(schema=SCHEMA, training_only=True, evaluation_eligible=False, complete_pool=False,
        independent_confirmatory_families=0, oracle=None, scope='Consumed same-domain crypto training evidence only.',
        source_artifacts=dict(PINS), historical_artifacts=dict(HISTORY_PINS),
        audit_prefix_sha256=list(AUDIT_PINS), campaign_context_id=report['campaign_context_id'],
        training_rows=rows, row_evidence=evidence, full_target_roster=public,
        unmeasured_candidate_ids=sorted({row['candidate_id'] for row in public}-{row['candidate_id'] for row in rows}),
        coverage=dict(measured_successes=3, pool_candidates=12, unmeasured_candidates=9, new_expression_families=0),
        fit_rule='Use only in a new frozen training release; exclude the entire target workload and every target-roster formula family.',
        limitations=['All three expression families occur in the existing 122-label history.',
            'Selected measurements are not a random sample; the other nine outcomes remain unknown.',
            'Same-domain crypto development contributes zero independent confirmatory families.',
            'Target uses a 32-bit KAT fingerprint plus runtime checks, not bytewise target KAT equality.',
            'The historical agent run had stale adaptive-GP predictions; importing valid raw outcomes does not repair that run.',
            'No comparative selection result or complete-pool oracle follows from this supplement.',
            'The earlier v2 charged unknown reservation is outside this v5-only supplement and remains preserved separately.'],
        new_model_fits=0, new_model_predictions=0, new_native_jobs=0)
    validate(value)
    return value


def export(output=OUTPUT, *, source=SOURCE_ROOT, historical=HISTORY_ROOT):
    output, source, historical = map(lambda path: Path(path).resolve(), (output, source, historical))
    c.require(not output.exists() and not any(output.is_relative_to(path) or path.is_relative_to(output)
              for path in (source, historical)), 'Fresh output outside frozen inputs required')
    value = build(source=source, historical=historical)
    output.mkdir(parents=True)
    c.seal(output/'supplement.json', value)
    c.seal(output/'provenance.json', dict(schema=SCHEMA+'-provenance',
        importer_source_sha256=c.sha(ROOT/SOURCE), source_artifacts=dict(PINS), historical_artifacts=dict(HISTORY_PINS),
        supplement_sha256=c.sha(output/'supplement.json'), authenticated_archive_members=679,
        reproduced_native_audit_prefixes=3, historical_rows_modified=0, historical_reports_modified=0,
        new_model_fits=0, new_model_predictions=0, new_native_jobs=0))
    (output/'README.md').write_text(README)
    c.seal(output/'manifest.json', {path.name: c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return value


def load(root, *, purpose='training'):
    c.require(purpose == 'training', 'Incomplete Ascon supplement is training-only; test/oracle use is forbidden')
    root = Path(root).resolve()
    _manifest(root)
    value = c.unseal(root/'supplement.json')
    provenance = c.unseal(root/'provenance.json')
    c.require(provenance['supplement_sha256'] == c.sha(root/'supplement.json') and
              provenance['importer_source_sha256'] == c.sha(ROOT/SOURCE) and
              provenance['source_artifacts'] == PINS and provenance['historical_artifacts'] == HISTORY_PINS,
              'Supplement provenance differs')
    return validate(value, purpose=purpose)


README = '''# Ascon training-only measurement supplement

This separate release imports three verified native Ascon v5 measurements from
the preserved October 27 archive. It authenticates the report, raw manifest,
all 679 ZIP members and their paired seals, then reproduces all three original
native audit-prefix hashes. It runs no native job, predictor fit or prediction.
The original 122-row corpus and every frozen result remain unchanged.

The supplement contains three training rows, the full twelve-candidate public
roster, and nine explicitly unmeasured IDs. It is `training_only=true`,
`evaluation_eligible=false`, `complete_pool=false`, with no oracle and zero new
independent confirmatory families. Every imported expression family already
occurs in the original history. These are additional context/area observations,
not new family coverage or evidence of an ML/agent advantage.

| Handle | Measured cycles | Speedup | Added LUT4 | Minimum routed MHz | Correct |
| --- | ---: | ---: | ---: | ---: | --- |
| C01 | 242,448,246 | 1.019698 | 73 | 62.992 | yes; exceeds +64 LUT4 |
| C06 | 243,085,014 | 1.017027 | 41 | 67.069 | yes |
| C02 | 241,493,094 | 1.023731 | 42 | 64.620 | yes |

Baseline: 247,224,006 cycles at a common 12 MHz. Target verification includes
round-trip/tamper checks and a 32-bit KAT fingerprint; it is not bytewise RV32 KAT
comparison. The stale adaptive-GP behavior in the original agent run remains a
preserved limitation. The earlier v2 unknown reservation remains separately
preserved and is outside this v5-only supplement.

Use `isaforge.ascon_training_supplement.load(path, purpose="training")` to obtain
the three rows. Any evaluation/oracle purpose is rejected. This file deliberately
uses `training_rows`, not the generic evaluation corpus's `rows`. A future frozen
training release must exclude the entire target workload and every family in its
full public candidate roster before adding this history. Do not run a new model
sweep, replace old scores or construct a three-candidate oracle from this data.

Reproduce to a fresh directory:

```sh
../work/audit-venv/bin/python scripts/export_ascon_training_supplement.py \\
  --output generated/ascon-training-supplement-reproduction
```
'''
