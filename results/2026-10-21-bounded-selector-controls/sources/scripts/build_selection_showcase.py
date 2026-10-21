#!/usr/bin/env python3
"""Build a shareable offline view of authenticated, consumed six-workload evidence.

No fitting, native measurements, network requests or LLM calls. Frozen source
copies are authenticated as artifacts; current runtime source need not match.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from isaforge import codesign as c

CORPUS = 'results/2026-10-21-six-workload-corpus'
SELECTIONS = (
    'results/2026-10-20-budget-campaign/selection/embench-edn',
    'results/2026-10-20-budget-campaign/selection/embench-ud',
    'results/2026-10-21-sha256-selection/model',
)
CANDIDATE_COLUMNS = ('workload_group', 'candidate_id', 'formula', 'status',
    'speedup', 'area_delta_lut4', 'routed_fmax_min_mhz', 'correctness_verified',
    'baseline_cycles', 'candidate_cycles', 'measurement_seconds',
    'measurement_timer_scope', 'failure_class', 'reference_censored')
ENDPOINT_COLUMNS = ('workload', 'policy', 'seed', 'cap', 'budget', 'best_speedup',
    'selected_id', 'target_measurement_seconds', 'inference_seconds',
    'failed_attempts', 'historical_available_labels', 'historical_candidate_wall_seconds')


def checked_files(directory, entries):
    directory = Path(directory).resolve()
    c.require(isinstance(entries, dict) and entries, 'Nonempty artifact inventory required')
    for name, expected in entries.items():
        path = (directory / name).resolve()
        c.require(path.is_relative_to(directory) and not Path(name).is_absolute(), 'Artifact escapes snapshot')
        c.require(path.is_file() and c.sha(path) == expected, 'Artifact checksum differs: ' + name)


def load_evidence(root=c.ROOT):
    """Authenticate inputs and check frozen endpoint selections against paid outcomes."""
    root = Path(root)
    folder = root / CORPUS
    checked_files(folder, c.unseal(folder / 'manifest.json'))
    corpus = c.unseal(folder / 'corpus.json')
    rows = corpus['rows'] + corpus['failed_attempts']
    c.require(len(corpus['rows']) == 33 and len(corpus['failed_attempts']) == 3
        and len(corpus['independent_workload_groups']) == 6, 'Expected frozen six-workload corpus')
    candidates = [{key: row.get(key) for key in CANDIDATE_COLUMNS} for row in rows]
    for row in candidates:
        row['status'] = row['status'] or 'success'
    by_id = {r['candidate_id']: r for r in rows}
    endpoints, comparisons, sources = [], [], []
    for relative in SELECTIONS:
        folder = root / relative
        protocol = c.unseal(folder / 'protocol.json')
        report = c.unseal(folder / 'report.json')
        c.require(protocol['schema'] == 'isaforge-budgeted-selection-v1'
            and protocol['target_labels_read'] == 0, 'Expected label-free frozen selection')
        checked_files(folder, protocol['artifacts'])
        for name in protocol['artifacts']:
            if name.endswith('.json'):
                c.unseal(folder / name)
        c.require(report['protocol_sha256'] == c.sha(folder / 'protocol.json'), 'Report/protocol binding differs')
        public = c.unseal(folder / 'public.json')
        observations = {}
        expected_runs = {(policy, seed, cap) for policy in protocol['policies']
            for seed in protocol['seeds'] for cap in protocol['area_caps']}
        actual_runs = [(r['policy'], r['seed'], r['area_delta_lut4_cap']) for r in report['runs']]
        c.require(len(actual_runs) == len(expected_runs) and set(actual_runs) == expected_runs, 'Replay run grid differs')
        for run in report['runs']:
            c.require([p['budget'] for p in run['curve']] == protocol['budgets'], 'Replay budgets differ')
            paid = {}
            for event in run['events']:
                if 'observation' in event:
                    obs = event['observation']; identity = obs['candidate_id']
                    c.require(identity in by_id, 'Observation outside corpus')
                    if identity in observations:
                        c.require(observations[identity] == obs, 'Inconsistent replay observation')
                    observations[identity] = obs
                    paid[identity] = obs
            for point in run['curve']:
                cap = run['area_delta_lut4_cap']
                attempts = point['attempted_ids']
                c.require(len(attempts) == point['budget'] and len(set(attempts)) == len(attempts)
                    and set(attempts) <= set(paid), 'Charged attempt prefix differs')
                successes = [i for i in attempts if paid[i].get('status', 'success') == 'success']
                c.require(point['measured_ids'] == successes and point['failed_attempts'] == len(attempts)-len(successes), 'Paid success/failure accounting differs')
                c.require(abs(point['target_measurement_seconds']-sum(paid[i]['measurement_seconds'] for i in attempts)) < 1e-8, 'Charged attempt time differs')
                available = [paid[i] for i in successes]
                feasible = [v for v in available if v.get('status', 'success') == 'success'
                    and v['device_fits'] and v['area_delta_lut4'] <= cap
                    and v['routed_fmax_min_mhz'] >= protocol['clock_mhz'] and v['speedup'] > 1]
                best = min(feasible, key=lambda v: (-v['speedup'], v['area_delta_lut4'], v['candidate_id'])) if feasible else None
                c.require(point['selected_id'] == (best['candidate_id'] if best else None)
                    and point['best_speedup'] == (best['speedup'] if best else 1), 'Endpoint paid feasible selection differs')
                endpoints.append(dict(workload=protocol['target_workload'], policy=run['policy'],
                    seed=run['seed'], cap=cap, **{k:point[k] for k in ENDPOINT_COLUMNS if k in point}))
        ordered = [observations[r['candidate_id']] for r in public]
        c.require(c.digest(ordered) == report['outcomes_sha256'], 'Report outcome binding differs')
        for obs in ordered:
            original = by_id[obs['candidate_id']]
            for key in ('formula', 'speedup', 'area_delta_lut4', 'routed_fmax_min_mhz', 'measurement_seconds'):
                c.require(obs.get(key) == original.get(key), 'Corpus/report outcome differs: ' + key)
        c.require(report['policy_seed_cap_budget_outcomes'] == 450, 'Expected 450 dependent endpoints per target')
        comparisons.append(dict(workload=protocol['target_workload'], oracles=report['oracles'],
            historical_available_labels=protocol['historical_available_rows'],
            historical_fit_labels=protocol['historical_fit_rows'],
            historical_candidate_wall_seconds=protocol['historical_candidate_wall_seconds'],
            reference='Best verified reference; one infrastructure-censored outcome, full-pool optimum unresolved' if protocol['target_workload'] == 'embench-ud' else 'Measured oracle over the frozen six-candidate pool'))
        sources.append(dict(path=relative, protocol_sha256=c.sha(folder/'protocol.json'), report_sha256=c.sha(folder/'report.json')))
    c.require(len(endpoints) == 1350, 'Expected 1,350 dependent replay endpoints')
    return dict(candidates=candidates, endpoints=endpoints, comparisons=comparisons,
        sources=sources, corpus_sha256=c.sha(root/CORPUS/'corpus.json'),
        timer_note=corpus['timer_note'], historical_costs=corpus['historical_costs'],
        total_candidate_attempt_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
        reference_censored_candidates=corpus['reference_censored_candidates'])


def write_csv(path, columns, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)


def build(output, *, root=c.ROOT):
    data = load_evidence(root)
    output = Path(output).resolve()
    c.require(not output.exists(), 'Use a fresh output directory; preserve prior showcases')
    output.mkdir(parents=True)
    write_csv(output/'candidates.csv', CANDIDATE_COLUMNS, data['candidates'])
    write_csv(output/'verified-labels.csv', CANDIDATE_COLUMNS,
              [r for r in data['candidates'] if r['status'] == 'success'])
    write_csv(output/'policy-endpoints.csv', ENDPOINT_COLUMNS, data['endpoints'])
    with sqlite3.connect(output/'evidence.sqlite') as db:
        for table, columns, rows in [('candidates', CANDIDATE_COLUMNS, data['candidates']),
                                      ('endpoints', ENDPOINT_COLUMNS, data['endpoints'])]:
            db.execute('CREATE TABLE ' + table + ' (' + ','.join(columns) + ')')
            db.executemany('INSERT INTO ' + table + ' VALUES (' + ','.join('?' for _ in columns) + ')',
                           [[r.get(k) for k in columns] for r in rows])
        db.execute('CREATE TABLE provenance (path TEXT, protocol_sha256 TEXT, report_sha256 TEXT)')
        db.executemany('INSERT INTO provenance VALUES (:path,:protocol_sha256,:report_sha256)', data['sources'])
    (output/'queries.sql').write_text("""-- Real candidate performance and hardware tradeoffs, including failures.
SELECT workload_group, formula, status, speedup, area_delta_lut4, measurement_timer_scope FROM candidates ORDER BY workload_group, speedup DESC;
-- Mean over five dependent model/tie seeds, not five independent workloads.
SELECT workload, policy, cap, budget, AVG(best_speedup) AS speedup, AVG(target_measurement_seconds) AS replayed_target_seconds FROM endpoints GROUP BY workload, policy, cap, budget ORDER BY workload, cap, budget, speedup DESC;
-- Baseline fallback is represented by selected_id IS NULL and speedup=1.
SELECT workload, policy, COUNT(*) AS baseline_endpoints FROM endpoints WHERE selected_id IS NULL GROUP BY workload, policy;
""")
    (output/'provenance.json').write_text(json.dumps({k:v for k,v in data.items() if k not in ('candidates','endpoints')}, indent=2)+'\n')
    payload = json.dumps(data, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026')
    (output/'index.html').write_text(HTML.replace('__DATA__', payload))
    return output


HTML = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ISAForge · measured instruction selection</title>
<style>:root{font:15px/1.55 system-ui;color:#203348;background:#f3f6fa}body{margin:0}main{max-width:1180px;margin:auto;padding:42px 24px}h1{font-size:clamp(30px,5vw,52px);letter-spacing:-2px;line-height:1.1;margin:12px 0}h2{font-size:23px;margin-top:0}p{max-width:900px}small,.muted{color:#5a6e84}.tag{color:#126658;font-weight:700;letter-spacing:2px;font-size:12px}.card{background:white;border:1px solid #dbe4ef;border-radius:16px;padding:24px;margin:20px 0;overflow:auto}.stats,.flow{display:flex;gap:12px;flex-wrap:wrap}.stats div{flex:1;min-width:130px;background:#e8eff8;border-radius:12px;padding:16px}.stats b{display:block;font-size:28px}.flow span{background:#eaf5f1;padding:8px 12px;border-radius:8px}.controls{display:flex;gap:18px;flex-wrap:wrap}select{font:inherit;padding:7px;border:1px solid #bdcddd;border-radius:6px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:9px;border-bottom:1px solid #e1e8ef}th{color:#52677f}code{font-size:12px}svg{width:100%;height:auto;min-width:600px}a{color:#076c92}.note{border-left:4px solid #dfa341;padding:12px 18px;background:#fff8e9}.legend{display:flex;gap:18px;flex-wrap:wrap}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}button{font:inherit;padding:6px 10px}footer{margin:30px 0;color:#5a6e84}</style>
<main><div class="tag">ISAFORGE / REPRODUCIBLE SYSTEMS + MACHINE LEARNING</div><h1>Which instruction is worth<br>an expensive measurement?</h1><p>Automatic RISC-V instruction discovery meets whole-program execution, integrated hardware validation and constrained selection. Explore the actual evidence and see where simple heuristics beat learned acquisition.</p>
<div class="stats"><div><b>33</b>verified labels</div><div><b>6</b>consumed workloads</div><div><b>3</b>preserved failures</div><div><b>39 / 117</b>designs / routing runs</div><div><b>1,350</b>dependent replay endpoints</div></div>
<p class="note"><b>Consumed development replay.</b> These endpoints reuse recorded outcomes; they are not new hardware measurements or independent generalization tests. ML has not beaten the strongest heuristic. The bounded LLM comparison and joint final instruction sets remain unfinished; this view makes no agent advantage claim.</p>
<div class="card"><h2>The engineering connection</h2><div class="flow"><span>Real workload + fixed input</span><span>→ legal formulas + lowering</span><span>→ whole-program processor checks</span><span>→ area + 3 routing seeds</span><span>→ frozen predictions</span><span>→ bounded paid selection</span></div><p class="muted">PicoRV32 · RV32I + PCPI · integrated 8 KiB RAM · iCE40 HX8K · common 12 MHz feasible clock. Compiler and memory partitions differ by recorded context. Single-candidate results cannot be added to predict joint sets.</p></div>
<div class="card"><h2>Budgeted selection comparison</h2><div class="controls"><label>Target <select id="workload"></select></label><label>Added LUT4 cap <select id="cap"><option>32</option><option selected>64</option><option>128</option></select></label><label>Paid attempts <select id="budget"><option>1</option><option>2</option><option selected>3</option></select></label></div><p id="reference"></p><p id="history" class="muted"></p><div class="legend"><span><i class="dot" style="background:#167b73"></i>Heuristic / random</span><span><i class="dot" style="background:#7360ba"></i>Learned policy</span><span>Bar = mean verified gain over five dependent seeds</span></div><svg id="bars" role="img" aria-label="Policy speedup comparison"></svg><div id="policyTable"></div></div>
<div class="card"><h2>Measured candidates, including failure evidence</h2><p>Area and timing here are privileged analysis labels. A selector receives these only after a charged query. Baseline fallback is always available at 1.000000× and +0 LUT4.</p><label>Workload <select id="candidateWorkload"></select></label><svg id="scatter" role="img" aria-label="Actual candidate speedup versus added hardware area"></svg><div id="candidateTable"></div></div>
<div class="card"><h2>Costs and reproducibility</h2><p id="cost"></p><p>Candidate wall, baseline/setup command, calibration and inference timers are separate scopes. Command and wall scopes overlap and must not be added. Historical failures are charged separately from successful training labels. SHA measurement seconds include ledger validation; older rows use narrower historical record timers. These mixed scopes do not establish time-efficiency superiority.</p><p>All successful cycle deltas match independently calibrated latency; learned hardware feasibility and uncertainty remain decision weaknesses. Model spreads are uncalibrated. The SHA reference covers six measured candidates from 56 eligible formulas.</p><p><a href="verified-labels.csv">33 verified labels CSV</a> · <a href="candidates.csv">All 36 attempts CSV</a> · <a href="policy-endpoints.csv">1,350 endpoints CSV</a> · <a href="evidence.sqlite">SQLite database</a> · <a href="queries.sql">Useful SQL</a> · <a href="provenance.json">Hashes and timer provenance</a></p><code>python scripts/build_selection_showcase.py --output generated/selection-showcase-new</code></div><footer>Standalone offline artifact · no external dependencies · no fitting, native jobs or LLM calls. Copy this directory to share the page and evidence; index.html also works by itself.</footer></main>
<script id="evidence" type="application/json">__DATA__</script><script>
const D=JSON.parse(document.getElementById('evidence').textContent),$=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
const short=x=>x.replace('embench-',''), fmt=(x,n=6)=>x==null?'—':Number(x).toFixed(n),heuristic=p=>['frequency','merit','calibrated_latency','latency_cost_heuristic','random'].includes(p);
function option(id,values){for(const v of values){let o=document.createElement('option');o.value=v;o.textContent=short(v);$(id).append(o)}}
function cell(row,value,tag='td'){let c=document.createElement(tag);c.textContent=value;row.append(c)}
function table(id,heads,rows){let t=document.createElement('table'),h=t.insertRow();heads.forEach(x=>cell(h,x,'th'));rows.forEach(v=>{let r=t.insertRow();v.forEach(x=>cell(r,x))});$(id).replaceChildren(t)}
function shape(svg,tag,attrs,text){let n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!=null)n.textContent=text;svg.append(n);return n}
option('workload',D.comparisons.map(x=>x.workload));$('workload').value='embench-nettle-sha256';option('candidateWorkload',[...new Set(D.candidates.map(x=>x.workload_group))]);$('candidateWorkload').value='embench-nettle-sha256';
function render(){let w=$('workload').value,cap=+$('cap').value,b=+$('budget').value,c=D.comparisons.find(x=>x.workload===w),o=c.oracles.find(x=>x.area_delta_lut4_cap===cap);$('reference').textContent=c.reference+': '+fmt(o.speedup)+'×. Baseline is the incumbent whenever no paid feasible improvement is found.';$('history').textContent=`Historical training: ${c.historical_available_labels} available labels; ${c.historical_fit_labels} fitted after family exclusions. ${fmt(c.historical_candidate_wall_seconds,3)} successful-label seconds, with historical failed attempts charged separately.`;
let points=D.endpoints.filter(x=>x.workload===w&&x.cap===cap&&x.budget===b),groups=[...new Set(points.map(x=>x.policy))].map(p=>{let a=points.filter(x=>x.policy===p),mean=k=>a.reduce((s,x)=>s+x[k],0)/a.length;return{p,s:mean('best_speedup'),t:mean('target_measurement_seconds'),f:mean('failed_attempts'),i:mean('inference_seconds'),n:a.length}}).sort((a,b)=>b.s-a.s||a.p.localeCompare(b.p));
let svg=$('bars');svg.replaceChildren();svg.setAttribute('viewBox','0 0 1040 410');let max=Math.max(o.speedup-1,...groups.map(x=>x.s-1),.001);groups.forEach((g,i)=>{let y=20+i*36;shape(svg,'text',{x:0,y:y+16,'font-size':13},g.p);shape(svg,'rect',{x:225,y,width:Math.max(1,(g.s-1)/max*600),height:23,rx:4,fill:heuristic(g.p)?'#167b73':'#7360ba'});shape(svg,'text',{x:840,y:y+16,'font-size':13},fmt(g.s)+'×')});shape(svg,'text',{x:225,y:397,'font-size':12,fill:'#52677f'},'Gain above unmodified baseline; cap and budget apply equally');table('policyTable',['Policy','Mean speedup','Target seconds¹','Inference seconds','Mean failures','Seeds'],groups.map(g=>[g.p,fmt(g.s)+'×',fmt(g.t,3),fmt(g.i,3),fmt(g.f,1),g.n]));}
function candidates(){let w=$('candidateWorkload').value,a=D.candidates.filter(x=>x.workload_group===w).sort((a,b)=>(b.speedup||0)-(a.speedup||0)),s=$('scatter');s.replaceChildren();s.setAttribute('viewBox','0 0 1040 265');let ok=a.filter(x=>x.status==='success'),maxX=Math.max(128,...ok.map(x=>x.area_delta_lut4)),maxY=Math.max(.005,...ok.map(x=>x.speedup-1));shape(s,'path',{d:'M80 20V210H980',fill:'none',stroke:'#95a9bd'});[0,32,64,128].forEach(x=>{let pos=80+x/maxX*880;shape(s,'line',{x1:pos,y1:20,x2:pos,y2:210,stroke:'#dae3ed'});shape(s,'text',{x:pos,y:230,'font-size':12},x)});shape(s,'text',{x:360,y:255,'font-size':12},'Added integrated LUT4 (vertical guides: area caps)');shape(s,'text',{x:80,y:14,'font-size':12},'Whole-program speedup; baseline 1.000000× at origin');shape(s,'circle',{cx:80,cy:210,r:5,fill:'#52677f'});ok.forEach((r,i)=>{let x=80+r.area_delta_lut4/maxX*880,y=210-(r.speedup-1)/maxY*175;let n=shape(s,'circle',{cx:x,cy:y,r:7,fill:'#167b73'});let title=document.createElementNS(NS,'title');title.textContent=r.formula+' · '+fmt(r.speedup)+'× · +'+r.area_delta_lut4+' LUT4';n.append(title);shape(s,'text',{x:x+10,y:y-7,'font-size':12},fmt(r.speedup)+'×')});table('candidateTable',['Formula','Outcome / correctness','Speedup','Added LUT4','Min Fmax MHz','Attempt seconds¹','Timer scope'],a.map(r=>[r.formula,r.status==='success'?'verified':r.failure_class,r.speedup==null?'unknown':fmt(r.speedup)+'×',r.area_delta_lut4??'unknown',fmt(r.routed_fmax_min_mhz,3),fmt(r.measurement_seconds,3),r.measurement_timer_scope]));}
['workload','cap','budget'].forEach(x=>$(x).addEventListener('change',render));$('candidateWorkload').addEventListener('change',candidates);$('cost').textContent='Recorded candidate attempts across six workloads: '+fmt(D.total_candidate_attempt_wall_seconds,3)+' seconds (33 successes plus three failures). No new native evaluations were launched to build this view. ¹ Replayed recorded attempt cost, not current offline rendering time.';render();candidates();
</script></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    print(build(args.output) / 'index.html')


if __name__ == '__main__':
    main()
