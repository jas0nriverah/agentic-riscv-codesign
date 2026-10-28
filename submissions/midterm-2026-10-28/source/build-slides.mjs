import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const skillDir = "/Users/jasonrivera/.codex/plugins/cache/openai-primary-runtime/presentations/26.1017.22136/skills/presentations";
const buildDir = path.join(root, ".codex-build/midterm-2026-10-28");
const finalDir = path.join(root, "submissions/midterm-2026-10-28");
const draftDir = path.join(buildDir, "rendered-draft");
const draftPptx = path.join(buildDir, "candidate.pptx");
const finalPptx = path.join(finalDir, "isaforge-midterm-progress-slides-final.pptx");
const FONT = "Arial";
const C = {
  navy: "#17324D",
  ink: "#263648",
  muted: "#607286",
  blue: "#2878A8",
  blueLight: "#DCECF5",
  teal: "#18856B",
  red: "#B94A48",
  amber: "#A65A00",
  amberLight: "#FFF1DF",
  grid: "#D9E1E8",
  pale: "#F4F7FA",
  white: "#FFFFFF",
  gray: "#8593A1",
};
const noneLine = { style: "solid", fill: "none", width: 0 };
const solid = (color = C.grid, width = 1) => ({ style: "solid", fill: color, width });

function addText(slide, value, pos, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: pos,
    fill: "none",
    line: noneLine,
  });
  shape.text = value;
  shape.text.style = {
    typeface: FONT,
    fontSize: 22,
    color: C.ink,
    ...style,
  };
  shape.text.insets = 0;
  return shape;
}

function addRect(slide, pos, fill, line = noneLine, geometry = "rect") {
  return slide.shapes.add({ geometry, position: pos, fill, line });
}

function addLine(slide, x1, y1, x2, y2, color = C.grid, width = 1) {
  return slide.shapes.add({
    geometry: "line",
    position: { left: x1, top: y1, width: x2 - x1, height: y2 - y1 },
    fill: "none",
    line: solid(color, width),
  });
}

function newSlide(presentation, number, title) {
  const slide = presentation.slides.add();
  slide.background.fill = C.white;
  if (title) {
    addText(slide, title, { left: 68, top: 42, width: 1120, height: 58 },
      { fontSize: 43, bold: true, color: C.navy });
    addLine(slide, 68, 112, 1212, 112, C.grid, 1);
  }
  addText(slide, `ISAForge  /  ECE 4803                                    ${number}`, {
    left: 68, top: 686, width: 1144, height: 18,
  }, { fontSize: 12, color: C.muted });
  return slide;
}

function setNotes(slide, text) {
  slide.speakerNotes.text = text;
}

function addChartFont(chart, applyFont) {
  applyFont(chart, { fontFamily: FONT });
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const keys = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const values = line.split(",");
    return Object.fromEntries(keys.map((key, index) => [key, values[index]]));
  });
}

function addPillText(slide, label, detail, x, y, width) {
  addText(slide, label, { left: x, top: y, width, height: 32 },
    { fontSize: 26, bold: true, color: C.navy });
  addText(slide, detail, { left: x, top: y + 37, width, height: 56 },
    { fontSize: 17, color: C.muted });
}

function styleTable(table, rows, cols, headerRow = true, fontSize = 16) {
  table.borders.assign({ style: "solid", fill: C.grid, width: 1 });
  table.styleOptions = { headerRow: false, bandedRows: false };
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const cell = table.getCell(r, c);
      cell.fill = headerRow && r === 0 ? C.navy : (r % 2 ? C.white : C.pale);
      cell.text.style = {
        typeface: FONT,
        fontSize: r === 0 && headerRow ? fontSize : fontSize - 1,
        color: headerRow && r === 0 ? C.white : C.ink,
        bold: headerRow && r === 0,
      };
    }
  }
}

const work=path.join(root,`.codex-build/slides-11-${Date.now()}`);
const notes=[];
const presentation=Presentation.create({slideSize:{width:1280,height:720}});
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(skillDir,'container_tools/artifact_tool_utils.mjs')).href);
function txt(s,t,x,y,w,h=60,size=26,color=C.ink,bold=false){return addText(s,t,{left:x,top:y,width:w,height:h},{fontSize:size,color,bold});}
function slide(n,title,time,script,source){const s=newSlide(presentation,n,title);setNotes(s,`SLIDE ${n} — ${time} seconds\n\nSPOKEN SCRIPT\n${script}\n\nSOURCES / Q&A (not part of timed script)\n${source}`); notes.push({n,title,time,script,source});return s;}
function flow(s,items,y=215){const w=245,g=48;items.forEach((a,i)=>{const x=72+i*(w+g);addRect(s,{left:x,top:y,width:w,height:130},C.pale,solid(C.grid));txt(s,a[0],x+14,y+14,w-28,38,25,C.blue,true);txt(s,a[1],x+14,y+57,w-28,65,22);if(i<items.length-1)addRect(s,{left:x+w+9,top:y+53,width:30,height:24},C.blue,noneLine,'rightArrow');});}
function chart(s,categories,series,pos,opts={}){const c=s.charts.add('bar',{position:pos,categories,series,barOptions:{direction:'column',grouping:'clustered',gapWidth:90},hasLegend:series.length>1,legend:{position:'bottom',overlay:false,textStyle:{fontSize:19,fill:C.ink}},chartFill:'none',chartLine:noneLine,plotAreaFill:C.white,plotAreaLine:noneLine,xAxis:{textStyle:{fontSize:20,fill:C.ink},majorGridlines:null,line:solid(C.grid)},yAxis:{min:0,textStyle:{fontSize:18,fill:C.muted},majorGridlines:solid(C.grid),line:solid(C.grid)},dataLabels:{showValue:true,position:'outEnd',textStyle:{fontSize:20,fill:C.ink}},...opts});applyPresentationChartFont(c,{fontFamily:FONT});return c;}
{
const s=slide(1,'ISAForge',25,'ISAForge asks whether learned predictions and an AI selection agent can find better RISC-V custom instructions with fewer expensive evaluations. We optimize verified whole-program performance under hardware constraints. Our contribution is the connection from real programs to measured labels to budgeted selection. Today we have a working pipeline, measured data, and preliminary comparisons—not yet a consistent machine-learning win.','Scope: README.md; docs/research-foundation.md. Guarded AI-track results are separate from other hardware contexts in the team report.');
txt(s,'AI-guided RISC-V program optimization',72,164,1120,70,44,C.blue,true);
txt(s,'Can learned selection find better feasible designs\nwith fewer hardware evaluations?',72,280,1100,130,38,C.navy,true);
txt(s,'Real workloads → measured outcomes → intelligent selection',72,459,1120,60,28);
txt(s,'Midterm progress • ECE 4803 • October 28, 2026',72,577,1120,40,23,C.muted);
}
{
const s=slide(2,'Research foundations',30,'We build on established methods rather than inventing another enumerator. Atasu provides the dataflow and architectural constraints for legal instruction candidates. CIDRE emphasizes that benefits depend on the processor and its timing. AutoTVM motivates ranking alternatives using measured performance. Constrained Bayesian optimization motivates measuring promising candidates while accounting for feasibility. ISAForge tests this combination on whole-program PicoRV32 outcomes; we do not claim to reproduce these complete systems.','Atasu, Pozzi & Ienne. Automatic Application-Specific Instruction-Set Extensions Under Microarchitectural Constraints. DAC 2003, 256–261. DOI 10.1145/775832.775897; methods §§4–7.\nRezunov et al. Automatic Microarchitecture-Aware Custom Instruction Design for RISC-V Processors. ICCAD 2025. DOI 10.1109/ICCAD66269.2025.11240781; arxiv.org/html/2509.15782v2, §§II–IV.\nChen et al. Learning to Optimize Tensor Programs. NeurIPS 2018. arxiv.org/pdf/1805.08166v4, §§3–4, Algorithm 1.\nGardner et al. Bayesian Optimization with Inequality Constraints. ICML 2014, PMLR32(2):937–945. https://proceedings.mlr.press/v32/gardner14.pdf, §§3.1–3.2.\nRepository method reviews: docs/research-foundation.md; docs/selection-methods-review.md.');
const rows=[['Atasu et al. • DAC 2003','Legal dataflow candidates','Input/output limits and convexity'],['CIDRE • ICCAD 2025','Architecture-aware evaluation','Account for processor latency and timing'],['AutoTVM • NeurIPS 2018','Learn from measured performance','Pairwise ranking of alternatives'],['Gardner et al. • ICML 2014','Constrained Bayesian optimization','Balance benefit, feasibility, and measurement']];
rows.forEach((r,i)=>{let y=153+i*105;txt(s,r[0],72,y,440,35,25,C.navy,true);txt(s,r[1],540,y,650,35,27,C.blue,true);txt(s,r[2],540,y+40,650,40,23);if(i<3)addLine(s,72,y+86,1208,y+86);});
txt(s,'Our test: measurement-efficient selection, validated on real processor outcomes.',72,601,1135,55,25,C.navy,true);
}
{
const s=slide(3,'Timeline and team contributions',20,'We started by collecting real benchmark traces and synthesizing isolated circuits for a hardware-cost model. Next we connected candidates to whole-program execution on PicoRV32, expanded the dataset, and tested selection policies. Two project chats record about forty-six hours of turn duration, including waits and interruptions, not training time. Team roles are provisional and need confirmation.','Dated results directories October19–27; git history; docs/original-project-proposal.txt; supplied AgenticRiscPredictor.pdf. Codex history snapshot: two project chats record 15.82 and 29.97 hours of ended turn duration, approximately 45.8 hours combined, including tool waits and interruptions. The earlier 15.82 hours includes 4.51 hours across two interrupted turns. 72 distinct directly spawned subagent threads; activity is not training time or a research outcome. See codex-history-and-baseline.md. Team must confirm roles and aliases; Git alone cannot measure contribution shares.');
const dates=['OCT 13–18','OCT 19','OCT 20–26','OCT 27'];const detail=['Traces + synthesis\nearly cost models','CRC32 + aha\nprocessor pipeline','More workloads\n+ selection tests','122-label scorecard\n+ agent pilot'];
addLine(s,95,210,1170,210,C.blue,4);dates.forEach((d,i)=>{let x=72+i*293;txt(s,d,x,154,250,34,24,C.blue,true);addRect(s,{left:x+12,top:201,width:18,height:18},C.blue,noneLine,'ellipse');txt(s,detail[i],x,244,260,85,25,C.navy,true);});
const values=[['Contributor / evidence','Primary contribution area'],['Jason • Git evidence','ML, budgeted selection, agent tools, analysis'],['Yuuto • Git evidence','Hardware, selection engine, measurement tests'],['Sooraj • report attribution','Compiler, tracing, extraction and toolchain']];const t=s.tables.add({rows:4,columns:2,left:72,top:366,width:1136,height:228,columnWidths:[390,746],values});styleTable(t,4,2,true,24);
txt(s,'Two project chats: ~46 h recorded turn time • roles need confirmation',72,619,1136,35,20,C.muted);
}
{
const s=slide(4,'From workload to verified improvement',35,'We wrote scripts that compile and profile workloads, extract legal candidates, and lower them to custom instructions. The evaluator executes each modified program with Verilator and checks correctness; Yosys and nextpnr measure integrated area and timing. The unmodified CRC32 reference took 32.39 million simulated cycles. The best candidate took 30.82 million, a 1.051 times common-clock speedup. These are simulation and FPGA tool results, not physical-chip stopwatch measurements.','src/candidates.py extracts legal candidates; isaforge/workload_experiment.py orchestrates workload preparation and collection; isaforge/codesign.py implements ProcessorEvaluator; Verilator simulates, Yosys synthesizes, nextpnr routes. docs/codesign-loop.md; results/2026-10-19-codesign/independent-audit.json. Embench CRC32,170 benchmark repetitions; startup, independent checksum, warm-up and serial reporting excluded from counter window. Same RV32I PicoRV32, 8KiB RAM and 12MHz target. Baseline 32,387,382 cycles,1653 LUT4; index_offset 30,820,662 cycles,1684 LUT4 (+31), 1.050833x. Both correctness checked; same-clock speedup, not measured board runtime. Baseline synth/routing Fmax 68.49–77.16 MHz. Distinguish this unmodified reference from heuristic selection baselines.');
flow(s,[['1  Discover','Compile + trace\nlegal dataflow'],['2  Implement','Lower custom opcode\nPicoRV32 PCPI'],['3  Verify','Program output\n+ cycle count'],['4  Measure','Integrated LUT4\n+ routed Fmax']]);
['candidates.py','workload_experiment.py','Verilator','Yosys + nextpnr'].forEach((label,i)=>addText(s,label,{left:72+i*293,top:355,width:245,height:30},{fontSize:18,color:C.muted,alignment:'center'}));
txt(s,'CRC32 reference: 32.39M cycles → 30.82M cycles = 1.051×',72,401,1136,65,30,C.navy,true);
txt(s,'Unmodified program/core → compare cycles → verify area and timing',72,500,1136,45,29,C.teal,true);
txt(s,'Restricted RV32 integer support • RTL simulation + FPGA synthesis/routing',72,583,1136,55,23,C.muted);
}
{
const s=slide(5,'Dataset: measured programs, not synthetic labels',40,'Our first hardware-cost study grew from 301 to 713 distinct synthesized formulas across benchmark collections. Those isolated LUT labels are separate from the current whole-program dataset: 122 candidate-program measurements across fourteen workload groups, plus four charged failures: two candidate correctness failures and two censored evaluations. The chart shows its three benchmark suites. We hold out entire workloads. Our thirteen-policy screen includes 2,925 replays of existing measurements, not new hardware runs.','Earlier area study: initial 301 formulas, later three collections 1,098 program/formula rows and 713 distinct formulas from 17 candidate-bearing programs; isolated LUT4 labels, not processor cycles. The frozen original-301 model evaluated 331 novel final formulas: structural linear 23.154 LUT4 MAE versus original XGBoost 87.595. Later all-713 deployment refit lacks a fresh independent test. See results/2026-10-13-prospective/README.md and docs/methodology-history.md. Current dataset: submissions/midterm-2026-10-28/dataset/; results/2026-10-27-final-selection-scorecard/scorecard.json. 15 build/input contexts;12 complete measured-pool oracles,2 censored. Embench39 labels/6 groups; BEEBS48/5; TACLeBench35/3. Original teammate hardware-branch data uses a distinct context and is not silently merged. Why few new workload labels: the fixed pool gate rejects countnegative (4 legal of 12 required), stringsearch (2), fannkuch-redux (2), and strstr (0). These are pre-measurement rejections, not missing or silently dropped data. The four charged failures are separate: EDN memory-guard violation at address 5956; UD self-check output flag zero; UD storage below 2 GiB; G.723 nextpnr route seed 3 exceeded 180 seconds. The last two are censored and have no performance/hardware label.');
chart(s,['Embench','BEEBS','TACLeBench'],[{name:'Successful labels',values:[39,48,35],fill:C.blue}],{left:55,top:173,width:680,height:390},{yAxis:{min:0,max:60,majorUnit:20,title:{text:'Measured candidate/program pairs'},textStyle:{fontSize:19,fill:C.ink},majorGridlines:solid(C.grid)}});
txt(s,'122 successful labels',790,178,420,55,34,C.navy,true);txt(s,'14 workload groups\n15 build/input contexts',790,248,420,90,27);txt(s,'4 failures retained',790,365,420,45,29,C.navy,true);txt(s,'Earlier cost study: 713 formulas\nSeparate isolated-LUT labels',790,430,420,90,26);
txt(s,'Train on other workloads; test on the entire held-out workload.',72,594,1136,50,28,C.blue,true);
}
{
const s=slide(6,'The model: training, predictions and explanation',40,'Our principal ranking model is XGBoost. Thirty-five features describe candidate structure, operations and execution opportunity. Measured speedup orders candidate pairs within each workload. Eighty depth-two trees learn a ranking score. We test on entire held-out workloads and exclude related formula families. The score is neither predicted speedup nor confidence. The contribution plot shows that estimated instruction savings strongly influences ranking, but attribution is not causal. Other predictor tools expose hardware estimates and uncertainty. Feasibility still requires measurement: one bitcount candidate passed correctness but exceeded its area cap by one LUT.','XGBRanker: rank:pairwise,80 estimators,max_depth2,learning_rate0.05; isaforge/ranking.py and features.py.35 premeasurement features. Pair relevance derived from measured within-context speedup order with ties. Workload/family holdouts prevent using target labels. The ranker is frozen during selection; no LLM fine-tuning. Other selectable predictors include regression and hardware GP; GP uncertainty is not calibrated confidence. Explanations: results/2026-10-27-ranker-explainability/explanation.json and global_feature_contributions.csv. Chart normalized absolute additive tree contributions macro-averaged over14 held-out workloads: savings47.1035%, locations11.1%, size7.2663%, frequency5.4586%, other29.0716%. Bitcount top rank add(in0,andi(in1,15)),1.008782x,+65LUT4 versus+64 cap. Current successful cycle labels match calibrated processor latency; ranking is not established superior to the heuristic.');
txt(s,'INPUTS',72,147,450,30,23,C.blue,true);txt(s,'35 features available before evaluation',72,188,540,42,27,C.navy,true);
txt(s,'Operation mix and expression structure\nExecution frequency and estimated savings',72,238,550,72,24);
txt(s,'TRAINING',72,333,450,30,23,C.blue,true);
txt(s,'Measured speedup(A) > speedup(B)\nLearn score(A) > score(B)',72,377,550,85,28,C.navy,true);
txt(s,'80 boosted trees   /   depth 2   /   rate 0.05',72,478,550,38,23);
txt(s,'Entire workload + related families held out',72,535,550,60,25,C.teal,true);
txt(s,'WHAT DRIVES THE RANKING?',665,147,540,32,23,C.blue,true);
chart(s,['Savings %','Locations','Size','Frequency','Other'],[{name:'Attribution share',values:[47.1035,11.1000,7.2663,5.4586,29.0716],fill:C.blue}],{left:640,top:195,width:580,height:325},{yAxis:{min:0,max:60,majorUnit:20,title:{text:'Normalized contribution (%)'},textStyle:{fontSize:17,fill:C.ink},majorGridlines:solid(C.grid)},xAxis:{textStyle:{fontSize:16,fill:C.ink},majorGridlines:null,line:solid(C.grid)},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.0',textStyle:{fontSize:18,fill:C.ink}}});
txt(s,'Rank score ≠ speedup ≠ confidence',665,543,540,42,25,C.amber,true);
txt(s,'A high rank can still violate the area budget.',665,594,540,55,23,C.muted);
}
{
const s=slide(7,'The agent: decisions, memory and feedback',40,'The LLM chooses which candidate to measure; XGBoost and heuristics score it. The host owns charging, correctness, and area/timing checks. In one archived SHA-256 pilot, hybrid memory reached the feasible design in two measurements; no retrieval took three and made three rejected finalization requests. The strongest heuristic needed one. Selector v2 exposes the host-computed incumbent, rejects stale final choices, and returns measured facts separately from the model note. The router now permits one stronger-model recovery after malformed output or a host incumbent correction. This recovery path has software tests, but we have not run a live v2 comparison.','isaforge/agent_memory.py: fixed query over unattempted formulas; local TF-IDF/LSA hybrid, RRF k60, top3 source-linked history; not pretrained embeddings or general RAG. Both arms can access full history; retrieval changes ordering/emphasis. Four structured tools; host owns attempt charging and final acceptance. The ranker is not retrained; configured hardware GP can update on paid successes. The live Luna pilot is one archived-data trial per arm with cooperative file restrictions; hybrid used two queries/four turns, no retrieval three queries/nine turns, three rejected finalizations, and both reached 1.0213847x, +50 LUT4, 65.99353 MHz. The heuristic reached the same design in one query. Selector v2 names the incumbent, enforces it at finalize, and returns canonical measured fields separately from unverified agent_summary. Recovery router v2 escalates once after a malformed structured action or an explicit host incumbent correction, under the shared model-call cap; it does not retry measurement or transport failures. 84 focused tests pass; zero live v2 LLM calls or native jobs. No causal memory or superiority claim.');
s.background.fill='#0B1426';addRect(s,{left:55,top:30,width:1170,height:87},'#0B1426');
txt(s,'The agent: decisions, memory and feedback',68,43,1144,57,40,'#EAF1FC',true);
const ac='#66D9AB', aw='#EAF1FC', am='#A5B6D0';
const stages=[['OBSERVE','Candidates + budget\nPaid observations'],['CONSULT','Query predictors\nRetrieve history'],['DECIDE','Primary model\nOptional recovery'],['ACT + VERIFY','Host checks action\nRecord outcome']];
stages.forEach((item,i)=>{const x=68+i*294;addRect(s,{left:x,top:175,width:260,height:132},'#14243B',solid(ac,1.2),'roundRect');txt(s,item[0],x+14,190,235,32,22,ac,true);txt(s,item[1],x+14,235,235,66,22,aw);if(i<3)addRect(s,{left:x+265,top:233,width:25,height:18},ac,noneLine,'rightArrow');});
addLine(s,1090,308,1090,338,ac,2);addLine(s,180,338,1090,338,ac,2);addRect(s,{left:172,top:309,width:16,height:29},ac,noneLine,'upArrow');
txt(s,'Repeat within budget; one stronger-model recovery follows invalid output or host incumbent correction.',120,353,1080,38,25,ac,true);
txt(s,'LIVE GPT-6 LUNA PILOT',72,421,900,32,23,ac,true);
txt(s,'Without retrieval',72,475,340,34,27,aw,true);txt(s,'3 queries   /   9 turns\n3 rejected finalizations',72,521,350,76,25,am);
txt(s,'With hybrid memory',463,475,355,34,27,aw,true);txt(s,'2 queries   /   4 turns\n0 rejected finalizations',463,521,350,76,25,am);
txt(s,'Same verified result',875,475,340,34,27,aw,true);txt(s,'1.0214× speedup\n+50 LUT4, 65.99 MHz',875,521,340,76,25,am);
txt(s,'One archived trial per arm. Recovery is offline-tested; no live v2 LLM run. Heuristic: 1 query.',72,632,1136,38,22,'#FFC978',true);
}
{
const s=slide(8,'Tools and observability: execution we can audit',45,'Our four tools separate language-model proposals from trusted execution. List exposes legal candidates; predict returns model estimates; measure charges an attempt before evaluation; finalize accepts only the host-computed best paid, verified feasible improvement; baseline is allowed only when none exists. Invalid and repeated measurement attempts still cost budget. Observability connects each decision to its tool call, retrieved record and outcome. We version the protocol and source hashes, preserve failed actions, and export verified traces to SQLite. The router records whether an escalation followed malformed output or a host incumbent correction. These are working local LLMOps components. The live pilot has thirteen recorded model turns, but token usage and model-only latency are unavailable. Production deployment and automated restart remain future work.','Tools: isaforge/selection_provider.py strict remote function schemas; isaforge/codex_chat_selector.py interactive JSON bridge. Host: bounded_selector.py. Measure reserves charge before lookup while budget remains. Invalid/repeated attempts count; repeats do not redispatch evaluator. Finalize accepts only the current host-computed best paid feasible improvement; null is allowed only with no improvement. Host returns canonical measured fields; the model text is an unverified agent_summary. Finite model/tool calls, incumbent fallback, fresh output paths; no restart/resume guarantee. Observability: export_agent_observability.py verifies manifest/protocol/ledger hashes and creates releases, episodes, decisions, model_calls, retrievals and tools tables. Raw ledgers authoritative. Live13 turns,4 retrievals; 3 rejected finalizations. Interactive elapsed time includes orchestration; tokens SQLNULL. Remote provider records tokens only if returned. LLMOps here is local versioning, reproducible evaluation and inspection, not production cloud operations. Selector v2 and recovery routing pass 84 focused tests; recovery routing has no live v2 comparison. A 10-policy/30-endpoint SHA256 control replay matches archived trajectories exactly, with zero LLM/native jobs. Retrieval fits are not new speedup model versions.');
txt(s,'FUNCTION CALLING',72,145,550,32,23,C.blue,true);
const rows=[['list_candidates','Legal patterns and public constraints'],['predict','Rankings and hardware estimates'],['measure','Charge attempt, return measured result'],['finalize','Finalize the host-computed best measured feasible result']];
rows.forEach(([name,detail],i)=>{const y=201+i*89;txt(s,name,72,y,530,32,26,C.navy,true);txt(s,detail,72,y+38,545,32,22,C.muted);if(i<3)addLine(s,72,y+79,607,y+79,C.grid,1);});
addLine(s,642,151,642,568,C.grid,1);
txt(s,'OBSERVABILITY + LLMOPS',680,145,540,32,23,C.blue,true);
txt(s,'Versioned experiment identity',680,201,520,34,27,C.navy,true);txt(s,'Model / prompt / code / data hashes',680,244,520,32,22,C.muted);
txt(s,'Linked decision traces',680,301,520,34,27,C.navy,true);txt(s,'Episode → decision → tool → outcome\nRetrieved IDs, errors and charged attempts',680,345,520,72,22,C.muted);
txt(s,'Verified SQLite export',680,441,520,34,27,C.navy,true);txt(s,'Inspect decisions, tool calls and recovery trigger\nPreserve failures and missing metadata',680,485,520,72,22,C.muted);
txt(s,'Host guardrails: correctness + area + timing + incumbent + finite budgets',72,590,1136,38,25,C.teal,true);
txt(s,'84 focused tests pass. Recovery router not live-compared; tokens / inference latency unavailable.',72,641,1136,33,21,C.muted);

}
{
const s=slide(9,'Baselines and a fair measurement budget',35,'The unmodified program gives the performance reference. A different kind of baseline is a selection policy: frequency counts occurrences, while merit estimates operations eliminated times executions. We compare these with latency-aware heuristics, random search, and learned policies. Every method gets the same pool and one, two, or three charged attempts; unqueried results remain hidden. The measured oracle knows all outcomes and gives a retrospective ceiling, not a deployable policy. Historical training cost is tracked separately.','Protocol: docs/research-foundation.md; scorecard.json. Simple merit uses projected instruction savings; do not label it a CIDRE reproduction. Primary endpoint best verified feasible cycle reduction; regret only for complete pools. Track target evaluations and elapsed time, historical training cost, fit/inference and agent costs separately. Exact isolated ranker fit/inference timing remains incomplete.');
txt(s,'Required comparisons',72,156,530,45,30,C.navy,true);txt(s,'Frequency\nMerit: operations saved × executions\nLatency / cost-aware heuristics\nRandom + non-agent active learning\nXGBoost + bounded LLM agent',72,222,560,265,27);
txt(s,'Same rules for every policy',700,156,500,45,30,C.navy,true);txt(s,'1 / 2 / 3 charged attempts\nAdded area ≤ 64 LUT4\nRouted timing ≥ 12 MHz\nCorrectness must pass\nUnqueried outcomes remain hidden',700,222,500,265,27);
txt(s,'Endpoint: best VERIFIED, FEASIBLE performance found per evaluation budget.',72,558,1136,75,29,C.blue,true);
}
{
const s=slide(10,'Results: early gains, no consistent ML win',75,'Here is the main selection result. The vertical axis is mean cycle-reduction regret relative to the best measured feasible candidate in each complete pool; lower is better. At one attempt, merit has 1.132 percent regret and the ranker has 0.842 percent. At two attempts they are almost tied. At three attempts, merit is better. The paired workload confidence intervals include zero for the early-budget advantages, so we cannot claim consistent superiority. Twelve workload groups have complete pool oracles; two incomplete groups are excluded from this regret calculation. The 2,925 policy-budget replays are dependent analyses of the existing measurements, not new hardware experiments. There is also an important diagnosis: all 122 historical cycle-speedup labels match the independently calibrated processor-latency calculation. This dataset therefore does not demonstrate a residual speedup relationship requiring machine learning. Our remaining challenge is learning which useful designs will be hardware-feasible and worth measuring. A previous three-source blind campaign favored both GP policies over merit at three attempts, but a later bitcount test favored the latency-cost heuristic. Those mixed results do not establish a general advantage. The Ascon pilot has no matched controls.','results/2026-10-27-final-selection-scorecard/scorecard.json. Paired difference = merit regret minus ranker regret (percentage points): B1 +0.290 [−0.065,+0.849]; B2 +0.027 [−0.097,+0.177]; B3 −0.056 [−0.167,0.000]. Workload bootstrap;12 complete pools.14-group cycle-reduction means merit1.086/1.657/2.043%;ranker1.334/1.680/1.996%. Earlier frozen three-source campaign: GP 1.602185% mean cycle reduction vs merit 1.144539% at B3; only three sources and cooperative replay, no total-cost win established. Later bitcount B3 latency-cost heuristic found 0.174118% improvement while both GP policies returned baseline. docs/blind-source-campaign.md; results/2026-10-22-bitcount-report/results.md. Timing floor weakly tested:minimum selected feasible Fmax59.13MHz vs12MHz. Target mean eval time merit55.67/114.24/169.76s;ranker56.29/115.69/171.46s. No total-cost advantage established.');
chart(s,['1 attempt','2 attempts','3 attempts'],[{name:'Merit',values:[1.132,.465,.015],fill:'#607286'},{name:'XGB ranker',values:[.842,.439,.070],fill:C.blue}],{left:45,top:161,width:760,height:420},{yAxis:{min:0,max:1.4,majorUnit:.35,numberFormatCode:'0.00',title:{text:'Mean oracle regret (%) ↓'},textStyle:{fontSize:19,fill:C.ink},majorGridlines:solid(C.grid)},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.000',textStyle:{fontSize:18,fill:C.ink}}});
txt(s,'Paired advantage of XGB',840,167,360,70,28,C.navy,true);txt(s,'1 attempt: +0.290 pp\n95% CI [−0.065, +0.849]\n\n2 attempts: +0.027 pp\n95% CI [−0.097, +0.177]',840,258,360,210,23);txt(s,'Merit is better at 3.\nEarly intervals include zero.',840,498,360,85,25,C.amber,true);
txt(s,'12 complete workload pools • retrospective comparison • merit remains fallback',72,616,1136,38,24,C.navy,true);
}
{
const s=slide(11,'Next milestone: an independent selection test',35,'We now have an end-to-end research system: real workloads, executable custom instructions, measured outcomes, learned ranking, and bounded agent tools. The next step is to freeze the policies before observing new workload results, then compare the agent and non-agent methods under identical budgets. We need better workload diversity and validated uncertainty before adding model complexity. Finally, we must implement and measure the selected one-to-three-instruction combination together. Individual speedups cannot be added. A reproducible heuristic win is still a useful scientific result.','docs/HANDOFF.md; docs/ACTIVE_GOAL.md. Owner resumed a 10-hour evidence-driven improvement block on October 28; no new workload labels were produced in this checkpoint. Next experiments require frozen controllers/policies, legal lowering and blind measurement contracts. Keep the original CRC32 and aha-mont64 experiments and all negative outcomes. No RTL-rewriting optimization agent.');
txt(s,'Working now',72,157,500,45,31,C.navy,true);txt(s,'Real workload → executable candidate\nMeasured cycles, area and timing\nWhole-workload ML evaluation\nExplainability + bounded agent tools',72,224,550,220,27);
txt(s,'Next, in order',700,157,500,45,31,C.navy,true);txt(s,'1  Freeze policies; test untouched workloads\n2  Compare agent vs non-agent fairly\n3  Validate uncertainty and total cost\n4  Measure 1–3 instructions jointly',700,224,510,250,25);
txt(s,'Success = better verified feasible performance per evaluation—not more models.',72,565,1136,80,31,C.blue,true);
}
await fs.mkdir(work,{recursive:true});
for(const [i,s]of presentation.slides.items.entries()){const png=await presentation.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(work,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));}
const candidate=path.join(work,'candidate.pptx'),validated=path.join(work,'validated.pptx');
await(await PresentationFile.exportPptx(presentation)).save(candidate);
await fs.mkdir(path.join(root,".codex-build/slides-11-validation"),{recursive:true});
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:validated,explicitTotalSlideCount:11,pythonExecutable:'/Users/jasonrivera/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','3'],requiredNativeTableOwnerSlides:[3],requiredNativeChartOwnerSlides:[5,6,10],materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(root,'.codex-build/slides-11-validation',`${path.basename(work)}.json`)});
await fs.writeFile(path.join(work,'speaker-notes.md'),'# ISAForge — 11-slide, seven-minute script\n\nTotal scheduled time: '+notes.reduce((a,n)=>a+n.time,0)+' seconds. Sources and Q&A material are not part of the spoken script.\n\n'+notes.map(n=>`## ${n.n}. ${n.title} (${n.time} seconds)\n\n${n.script}\n\n### Sources / Q&A\n\n${n.source}\n`).join('\n'));
console.log(JSON.stringify({slides:11,seconds:notes.reduce((a,n)=>a+n.time,0),spokenWords:notes.map(n=>n.script).join(' ').split(/\s+/).length,validated}));
