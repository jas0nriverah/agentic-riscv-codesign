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
const s=slide(5,'Dataset: measured programs, not synthetic labels',40,'Our first hardware-cost study grew from 301 to 713 distinct synthesized formulas across benchmark collections. Those isolated LUT labels are separate from the current whole-program dataset: 122 candidate-program measurements across fourteen workload groups, plus four charged failures. The chart shows its three benchmark suites. We hold out entire workloads. Our thirteen-policy screen includes 2,925 replays of existing measurements, not new hardware runs.','Earlier area study: initial 301 formulas, later three collections 1,098 program/formula rows and 713 distinct formulas from 17 candidate-bearing programs; isolated LUT4 labels, not processor cycles. The frozen original-301 model evaluated 331 novel final formulas: structural linear 23.154 LUT4 MAE versus original XGBoost 87.595. Later all-713 deployment refit lacks a fresh independent test. See results/2026-10-13-prospective/README.md and docs/methodology-history.md. Current dataset: submissions/midterm-2026-10-28/dataset/; results/2026-10-27-final-selection-scorecard/scorecard.json. 15 build/input contexts;12 complete measured-pool oracles,2 censored. Embench39 labels/6 groups; BEEBS48/5; TACLeBench35/3. Original teammate hardware-branch data uses a distinct context and is not silently merged.');
chart(s,['Embench','BEEBS','TACLeBench'],[{name:'Successful labels',values:[39,48,35],fill:C.blue}],{left:55,top:173,width:680,height:390},{yAxis:{min:0,max:60,majorUnit:20,title:{text:'Measured candidate/program pairs'},textStyle:{fontSize:19,fill:C.ink},majorGridlines:solid(C.grid)}});
txt(s,'122 successful labels',790,178,420,55,34,C.navy,true);txt(s,'14 workload groups\n15 build/input contexts',790,248,420,90,27);txt(s,'4 failures retained',790,365,420,45,29,C.navy,true);txt(s,'Earlier cost study: 713 formulas\nSeparate isolated-LUT labels',790,430,420,90,26);
txt(s,'Train on other workloads; test on the entire held-out workload.',72,594,1136,50,28,C.blue,true);
}
{
const s=slide(6,'The ML model: shallow boosted-tree ranking',40,'Our main challenger is XGBoost pairwise ranking, not a neural network. Thirty-five premeasurement features describe each candidate. We use measured speedup to order pairs within a workload, then fit eighty shallow trees. The output is a relative ranking, not a speedup or confidence probability. We tried eight learned policies in the final screen and five controls. Separate experiments tested Gaussian-process active learning. We assess selection quality, not just prediction error.','isaforge/ranking.py: XGBRanker rank:pairwise;80 estimators,max_depth2,learning_rate0.05,min_child_weight1,reg_lambda1,subsample1,colsample_bytree1,hist,n_jobs1. isaforge/features.py:35 features. Relevance preserves ties within context. Measured target outcomes excluded from input features.');
flow(s,[['35 input features','Profile opportunity\nStructure + operations'],['80 shallow trees','Depth 2\nLearning rate 0.05'],['Ranking score','Relative ordering\nNot a probability'],['Choose queries','Measure promising\ncandidates first']]);
txt(s,'Training signal: measured speedup(A) > measured speedup(B)',72,404,1136,50,30,C.navy,true);
txt(s,'Pairwise objective → encourage score(A) > score(B)',72,467,1136,50,29,C.blue,true);
txt(s,'13 policies tested • 8 learned • 2,925 retrospective replays',72,571,1136,65,25);
}
{
const s=slide(7,'Explainability and uncertainty',40,'Tree contributions show what drives the ranking: estimated instruction savings alone accounts for about forty-seven percent of normalized attribution. This describes the model’s behavior; it is not a causal explanation. A useful failure case is bitcount’s top-ranked candidate: it passes correctness and speeds up execution, but adds sixty-five LUT4 cells, exceeding the cap by one. Uncertainty should help us choose what to measure next. Ensemble disagreement and Gaussian-process estimates are available, but they are not yet calibrated confidence, and the ranker itself does not provide a confidence interval.','results/2026-10-27-ranker-explainability/explanation.json; global_feature_contributions.csv. Normalized absolute additive tree contributions macro-averaged over14 held-out workloads; profile opportunity features account for66.39%. Local add(in0,andi(in1,15)) rank1/12;1.008782x,+65LUT4,61.82MHz. Uncertainty calibration remains unproved.');
chart(s,['Savings %','Locations','Size','Frequency','Other'],[{name:'Attribution share',values:[47.1035,11.1000,7.2663,5.4586,29.0716],fill:C.blue}],{left:50,top:165,width:700,height:380},{yAxis:{min:0,max:60,majorUnit:20,title:{text:'Normalized contribution (%)'},textStyle:{fontSize:19,fill:C.ink},majorGridlines:solid(C.grid)},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.0',textStyle:{fontSize:19,fill:C.ink}}});
txt(s,'A high rank can still fail',790,176,410,70,30,C.navy,true);txt(s,'Bitcount: top-ranked\n1.0088× cycle speedup\n+65 LUT4 > +64 cap',790,267,410,135,27);txt(s,'Correctness passed;\narea made it infeasible.',790,428,410,85,25,C.amber,true);
txt(s,'Uncertainty guides questions; measured correctness and feasibility decide.',72,588,1136,60,27,C.blue,true);
}
{
const s=slide(8,'ML-guided agentic instruction selection',45,'Read this diagram from left to right. During model training, measured examples provide candidate features and speedup-based ranking labels. We train an XGBoost ranker and evaluate it on held-out workloads. At selection time, the LLM queries predictions and receives approved historical memory. It chooses an action, but the host controls the measurement budget and checks correctness, area and timing. Paid outcomes update the episode state and inform the next choice. The final output is the best verified feasible design. We train the predictor, not the language model. Our live Luna pilot exercised this loop using archived hardware outcomes; it does not establish a general advantage over heuristics.','Training: 35 premeasurement features, rank:pairwise, relevance derived from measured within-context speedup order. Split entire workloads and related formula families; held-out labels do not enter fitting or retrieval. Diagram trees are schematic, not an actual fitted-tree explanation. The trained ranker returns a ranking score, not calibrated speedup. Runtime also supports other frozen predictors and a hardware GP; this diagram focuses on the trained ranker connection. Selected models are not retrained on hidden target labels. Paid observations update episode state and may support an explicitly configured hardware-GP update, not XGBoost or LLM fine-tuning. Four tools: list_candidates, predict, measure, finalize. Historical memory uses local lexical TF-IDF + latent-semantic SVD retrieval and RRF, scoped to approved history. Host feasibility is measured correctness, integrated area and timing. Live pilot: results/2026-10-28-live-luna-memory/README.md. Two fresh gpt-6-luna agents, one trial each, archived SHA256 evidence. Both 1.0213847x, +50 LUT4, 65.99353 MHz; memory 2 queries, no retrieval 3, cost heuristic 1. No causal claim, new hardware or fine-tuned LLM. Local LLMOps covers protocol versioning and SQLite traces; token/model-only latency unavailable in live pilot.');
// Editable architecture diagram; colors distinguish training, retrieval and execution.
s.background.fill='#0B1426';
const white='#EAF1FC', muted='#A5B6D0', cyan='#64D5F4', green='#66D9AB', gold='#FFC978';
addRect(s,{left:55,top:30,width:1170,height:87},'#0B1426');
txt(s,'ISAForge  /  ML-guided agent architecture',68,43,1144,57,40,white,true);
function node(x,y,w,h,title,detail,color=cyan){addRect(s,{left:x,top:y,width:w,height:h},'#14243B',solid(color,1.2),'roundRect');txt(s,title,x+14,y+12,w-28,32,23,color,true);if(detail)txt(s,detail,x+14,y+48,w-28,h-51,20,white);}
function right(x,y,w=28,color=cyan){addRect(s,{left:x,top:y,width:w,height:16},color,noneLine,'rightArrow');}
function down(x,y,h=24,color=cyan){addRect(s,{left:x,top:y,width:16,height:h},color,noneLine,'downArrow');}
txt(s,'01  MODEL TRAINING',68,139,300,29,22,cyan,true);
node(68,183,275,84,'Measured examples','Features + speedup labels');down(198,271);
node(68,301,275,190,'XGBoost ensemble','',cyan);
for(const x of [117,205,293]){
 addLine(s,x,358,x,375,cyan,2);addLine(s,x-22,375,x+22,375,cyan,2);
 for(const z of [x-22,x+22]){addLine(s,z,375,z,399,cyan,2);addLine(s,z-10,412,z+10,412,cyan,1);addLine(s,z,399,z,412,cyan,1);for(const q of [z-10,z+10]){addLine(s,q,412,q,426,cyan,1);addRect(s,{left:q-4,top:423,width:8,height:8},cyan,noneLine,'ellipse');}}
 for(const [xx,yy] of [[x,358],[x-22,399],[x+22,399]])addRect(s,{left:xx-6,top:yy-6,width:12,height:12},'#244965',solid(cyan,1),'ellipse');
}
txt(s,'s(x) = Σ tree scores',85,451,245,29,23,white,true);
txt(s,'Whole-workload holdouts\nFrozen ranker during selection',68,510,280,62,20,muted);
txt(s,'02  MEMORY + AGENT',389,139,480,29,22,green,true);
node(389,183,476,62,'Approved historical evidence','',green);
node(389,263,222,72,'Lexical search','Exact terms',green);
node(633,263,232,72,'Semantic search','Latent SVD vectors',green);
addLine(s,500,245,500,261,green,1.5);addLine(s,747,245,747,261,green,1.5);
addLine(s,500,336,500,350,green,1.5);addLine(s,500,350,747,350,green,1.5);addLine(s,747,336,747,350,green,1.5);
txt(s,'Hybrid rank fusion',390,354,250,28,20,green,true);
down(739,351,28,green);
addRect(s,{left:658,top:386,width:177,height:148},'#193C43',solid(green,2.5),'ellipse');
txt(s,'LLM',704,414,100,37,30,white,true);txt(s,'selection agent',674,456,150,29,21,green,true);
node(389,403,215,89,'Legal candidates','Workload + budget',green);right(614,443,34,green);
addLine(s,343,473,365,473,cyan,2);addLine(s,365,473,365,552,cyan,2);addLine(s,365,552,746,552,cyan,2);addRect(s,{left:738,top:535,width:16,height:18},cyan,noneLine,'upArrow');
txt(s,'predict(): ranking + diagnostics',390,564,440,28,20,cyan,true);
txt(s,'03  TOOLS + VERIFICATION',913,139,310,29,22,gold,true);
node(913,183,299,103,'Structured function calls','list_candidates  /  predict\nmeasure  /  finalize',gold);
node(913,344,299,113,'Host-enforced budget','Charge each attempt\nReject invalid selections',gold);
right(842,441,59,gold);addLine(s,1063,287,1063,320,gold,1.5);down(1055,316,23,gold);
node(913,484,299,105,'Verified outcome','Correctness + cycles\nArea + timing',gold);down(1055,460,20,gold);
addLine(s,855,540,912,540,green,2);addLine(s,855,495,855,540,green,2);addRect(s,{left:831,top:487,width:25,height:16},green,noneLine,'leftArrow');
txt(s,'Paid feedback to agent',913,601,299,27,19,green,true);
addLine(s,68,638,1212,638,'#304460',1);
txt(s,'LLMOps + observability',68,652,340,29,22,white,true);
txt(s,'Versioned runs   /   SQL traces   /   Best verified feasible design',410,652,802,29,21,muted);

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
const s=slide(11,'Next milestone: an independent selection test',35,'We now have an end-to-end research system: real workloads, executable custom instructions, measured outcomes, learned ranking, and bounded agent tools. The next step is to freeze the policies before observing new workload results, then compare the agent and non-agent methods under identical budgets. We need better workload diversity and validated uncertainty before adding model complexity. Finally, we must implement and measure the selected one-to-three-instruction combination together. Individual speedups cannot be added. A reproducible heuristic win is still a useful scientific result.','docs/HANDOFF.md; docs/ACTIVE_GOAL.md. Research paused at presentation checkpoint; no new collection implied by this deck. Next experiments require frozen controllers/policies, legal lowering and blind measurement contracts. Keep the original CRC32 and aha-mont64 experiments and all negative outcomes. No RTL-rewriting optimization agent.');
txt(s,'Working now',72,157,500,45,31,C.navy,true);txt(s,'Real workload → executable candidate\nMeasured cycles, area and timing\nWhole-workload ML evaluation\nExplainability + bounded agent tools',72,224,550,220,27);
txt(s,'Next, in order',700,157,500,45,31,C.navy,true);txt(s,'1  Freeze policies; test untouched workloads\n2  Compare agent vs non-agent fairly\n3  Validate uncertainty and total cost\n4  Measure 1–3 instructions jointly',700,224,510,250,25);
txt(s,'Success = better verified feasible performance per evaluation—not more models.',72,565,1136,80,31,C.blue,true);
}
await fs.mkdir(work,{recursive:true});
for(const [i,s]of presentation.slides.items.entries()){const png=await presentation.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(work,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));}
const candidate=path.join(work,'candidate.pptx'),validated=path.join(work,'validated.pptx');
await(await PresentationFile.exportPptx(presentation)).save(candidate);
await fs.mkdir(path.join(root,".codex-build/slides-11-validation"),{recursive:true});
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:validated,explicitTotalSlideCount:11,pythonExecutable:'/Users/jasonrivera/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','3'],requiredNativeTableOwnerSlides:[3],requiredNativeChartOwnerSlides:[5,7,10],materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(root,'.codex-build/slides-11-validation',`${path.basename(work)}.json`)});
await fs.writeFile(path.join(work,'speaker-notes.md'),'# ISAForge — 11-slide, seven-minute script\n\nTotal scheduled time: '+notes.reduce((a,n)=>a+n.time,0)+' seconds. Sources and Q&A material are not part of the spoken script.\n\n'+notes.map(n=>`## ${n.n}. ${n.title} (${n.time} seconds)\n\n${n.script}\n\n### Sources / Q&A\n\n${n.source}\n`).join('\n'));
console.log(JSON.stringify({slides:11,seconds:notes.reduce((a,n)=>a+n.time,0),spokenWords:notes.map(n=>n.script).join(' ').split(/\s+/).length,validated}));
