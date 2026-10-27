"""Build a fresh disabled protocol; authenticate saved models with zero new fits."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import md5_protocol_bridge as bridge


def build(output):
    output=Path(output).resolve();parent=ROOT/bridge.PREREG
    bridge.require(output.parent==parent and not output.exists(),'Fresh direct protocol directory required')
    raise bridge.ProtocolIncomplete('Incomplete bridge: build remains unconditionally disabled; no protocol artifact may be sealed')
    pool,model,public,history=bridge.authenticate_model_metadata()
    sources={name:bridge.sha(ROOT/name) for name in bridge.SOURCES}
    archived_plan=Path('generated/blind-cohort-2026-10-21/nettle-md5/plan.json')
    bridge.require(bridge.sha(ROOT/archived_plan)==model['source_bindings'][str(archived_plan)],'Archived baseline plan changed')
    plan=json.loads((ROOT/archived_plan).read_text())
    context=bridge.declared_context(json.loads((ROOT/bridge.identity.V1/'controller-contract.json').read_text()),
        plan,bridge.MODEL_MANIFEST_SHA,sources,archived_plan_file_sha256=model['source_bindings'][str(archived_plan)])
    mapping=bridge.native_remap(pool.validate(),context)
    authentication=bridge.authenticate_zero_paid_models(public,history)
    # Recheck the complete frozen package after model loads/proof computations.
    bridge.authenticate_model_metadata()
    for name,expected in sources.items():bridge.require(bridge.sha(ROOT/name)==expected,'Protocol source changed')
    value=bridge.protocol(context,mapping,model,authentication)
    output.mkdir()
    def seal(name,item):
        path=output/name;path.write_bytes(bridge.identity.pack(item)+b'\n')
        path.with_name(path.name+'.sha256').write_text(bridge.sha(path)+'\n')
    for name,item in (('evaluation-protocol.json',value),('native-id-remap.json',mapping),
                      ('zero-paid-model-authentication.json',authentication),('source-bindings.json',sources)):
        seal(name,item)
    (output/'README.md').write_text('# MD5 disabled candidate-evaluation protocol\n\n'
        '**Dispatch is hard-disabled. This is a declared protocol, not a hardware/runtime release.**\n\n'
        'Review [protocol](evaluation-protocol.json), [explicit ID remap](native-id-remap.json), '
        '[zero-paid authentication](zero-paid-model-authentication.json) and [source bindings](source-bindings.json). '
        'The declared native namespace is distinct from the frozen model/preparation namespace and archived hardware context. '
        'No actual native plan or enabled evaluator is authenticated.\n\n'
        'A future evaluator must hold its lock across proof, reservation and terminal ledger sealing, preserve original native '
        'record/ledger bytes and IDs before logical projection, and reconstruct only each policy’s own charged verified prefix. '
        'Dynamic refits and fixed-joint conditioning remain different. Synthetic-only paths test these contracts without real paid updates.\n\n'
        'Baseline guards, 6400/6528 partition, 8KiB RAM, PCPI and full-program correctness, integrated SoC area/device fit '
        'and minimum three-seed Fmax >=12MHz remain required. Offline lowering and initial model proofs do not establish them. '
        'Only a separately approved release may permit the3live+9reference sequence; failures consume slots, unknowns stop, no retries. '
        'Matched replay is logical paid-prefix accounting, not85 native campaigns or equal elapsed time.\n')
    seal('artifact-manifest.json',{p.name:bridge.sha(p) for p in sorted(output.iterdir()) if p.is_file()})
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/bridge.PREREG/'evaluation-protocol-v1')
    value=build(parser.parse_args().output)
    print(json.dumps({k:value[k] for k in ('status','candidate_dispatch_enabled','authenticated_native_plan','model_fits','native_jobs')}))
