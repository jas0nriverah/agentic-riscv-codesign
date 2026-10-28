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
const s=slide(3,'Timeline and team contributions',20,'We progressed from CRC32 and aha-mont64 to a multi-workload measured corpus, then added budgeted comparisons, explanations, and bounded LLM tools. Software, hardware, and machine learning connect through one measurement contract. The contribution mapping shown is provisional: Git evidence supports the named author areas, while the software role comes from the team report and needs team confirmation.','Dated results directories October19–27; git history; docs/original-project-proposal.txt; supplied AgenticRiscPredictor.pdf. Contribution names, author aliases and actual work must be confirmed by the team before submission. Git alone does not measure contribution shares.');
const dates=['OCT 19–21','OCT 22','OCT 25–26','OCT 27'];const detail=['CRC32 + aha\nworking pipeline','Cross-workload\nselection tests','Broader corpus\n+ agent tools','122-label scorecard\n+ Ascon pilot'];
addLine(s,95,210,1170,210,C.blue,4);dates.forEach((d,i)=>{let x=72+i*293;txt(s,d,x,154,250,34,24,C.blue,true);addRect(s,{left:x+12,top:201,width:18,height:18},C.blue,noneLine,'ellipse');txt(s,detail[i],x,244,260,85,25,C.navy,true);});
const values=[['Contributor / evidence','Primary contribution area'],['Jason • Git evidence','ML, budgeted selection, agent tools, analysis'],['Yuuto • Git evidence','Hardware, selection engine, measurement tests'],['Sooraj • report attribution','Compiler, tracing, extraction and toolchain']];const t=s.tables.add({rows:4,columns:2,left:72,top:366,width:1136,height:228,columnWidths:[390,746],values});styleTable(t,4,2,true,24);
txt(s,'Provisional mapping: confirm names, aliases and actual roles with the team.',72,619,1136,35,20,C.muted);
}
{
const s=slide(4,'From workload to verified improvement',35,'A supported RV32 integer workload is compiled and traced. We extract repeated dataflow patterns and reject illegal operations, unsafe dependencies, or excess inputs and outputs. The selected expression is lowered to a custom opcode connected through PicoRV32’s PCPI interface. We then execute the modified program, verify its output, and measure cycles plus integrated area and routed timing. Only a correct design within the constraints becomes an improvement. Cycle speedup assumes a common clock; these are simulation and synthesis measurements, not physical-chip timings.','Existing extractor, lowering and PicoRV32 PCPI evaluation; README.md and docs/HANDOFF.md. Restricted integer patterns, two register inputs/one output. Reject unsafe/unsupported rewrites. Integrated hardware metrics must stay separate from standalone LUT predictors.');
flow(s,[['1  Discover','Compile + trace\nlegal dataflow'],['2  Implement','Lower custom opcode\nPicoRV32 PCPI'],['3  Verify','Program output\n+ cycle count'],['4  Measure','Integrated LUT4\n+ routed Fmax']]);
txt(s,'Baseline cycles ÷ modified-program cycles = measured cycle speedup',72,401,1136,65,30,C.navy,true);
txt(s,'Correctness gate  +  area budget  +  timing floor',72,500,1136,45,29,C.teal,true);
txt(s,'Restricted RV32 integer support • RTL simulation + FPGA synthesis/routing',72,583,1136,55,23,C.muted);
}
{
const s=slide(5,'Dataset: measured programs, not synthetic labels',40,'Our frozen corpus contains 122 successful candidate-program measurements from fourteen workload groups, with four failed attempts retained and charged. The chart shows coverage from three benchmark suites. Each row contains premeasurement candidate features and separately recorded whole-program speedup, area, timing, and correctness. Candidates from one program are related, so we hold out entire workloads and exclude related expression families. The three later Ascon measurements remain separate. Thousands of policy replays reuse these labels; they are not thousands of new hardware experiments.','Dataset: submissions/midterm-2026-10-28/dataset/; results/2026-10-27-final-selection-scorecard/scorecard.json. 15 build/input contexts;12 complete measured-pool oracles,2 censored. Embench39 labels/6 groups; BEEBS48/5; TACLeBench35/3. Original teammate hardware-branch data uses a distinct context and is not silently merged.');
chart(s,['Embench','BEEBS','TACLeBench'],[{name:'Successful labels',values:[39,48,35],fill:C.blue}],{left:55,top:173,width:680,height:390},{yAxis:{min:0,max:60,majorUnit:20,title:{text:'Measured candidate/program pairs'},textStyle:{fontSize:19,fill:C.ink},majorGridlines:solid(C.grid)}});
txt(s,'122 successful labels',790,178,420,55,34,C.navy,true);txt(s,'14 workload groups\n15 build/input contexts',790,248,420,90,27);txt(s,'4 failures retained',790,365,420,45,29,C.navy,true);txt(s,'+ 3 later Ascon labels\nreported separately',790,430,420,90,26);
txt(s,'Train on other workloads; test on the entire held-out workload.',72,594,1136,50,28,C.blue,true);
}
{
const s=slide(6,'The ML model: shallow boosted-tree ranking',40,'Our main learned challenger is XGBoost pairwise ranking, not a neural network. Thirty-five premeasurement features describe the expression, constants, operations, and trace opportunity. Training pairs are ordered using actual measured speedup within the same workload context. Eighty shallow trees produce a relative ranking score. That score is neither a predicted speedup nor a confidence probability. We also tried regression, feasibility models, and active learning; those are comparisons, not evidence that every new model helped. The goal is better selection, not simply lower prediction error.','isaforge/ranking.py: XGBRanker rank:pairwise;80 estimators,max_depth2,learning_rate0.05,min_child_weight1,reg_lambda1,subsample1,colsample_bytree1,hist,n_jobs1. isaforge/features.py:35 features. Relevance preserves ties within context. Measured target outcomes excluded from input features.');
flow(s,[['35 input features','Profile opportunity\nStructure + operations'],['80 shallow trees','Depth 2\nLearning rate 0.05'],['Ranking score','Relative ordering\nNot a probability'],['Choose queries','Measure promising\ncandidates first']]);
txt(s,'Training signal: measured speedup(A) > measured speedup(B)',72,404,1136,50,30,C.navy,true);
txt(s,'Pairwise objective → encourage score(A) > score(B)',72,467,1136,50,29,C.blue,true);
txt(s,'Whole-workload holdouts + related-expression exclusions prevent easy leakage.',72,571,1136,65,25);
}
{
const s=slide(7,'Explainability and uncertainty',40,'Tree contributions show what drives the ranking: estimated instruction savings alone accounts for about forty-seven percent of normalized attribution. This describes the model’s behavior; it is not a causal explanation. A useful failure case is bitcount’s top-ranked candidate: it passes correctness and speeds up execution, but adds sixty-five LUT4 cells, exceeding the cap by one. Uncertainty should help us choose what to measure next. Ensemble disagreement and Gaussian-process estimates are available, but they are not yet calibrated confidence, and the ranker itself does not provide a confidence interval.','results/2026-10-27-ranker-explainability/explanation.json; global_feature_contributions.csv. Normalized absolute additive tree contributions macro-averaged over14 held-out workloads; profile opportunity features account for66.39%. Local add(in0,andi(in1,15)) rank1/12;1.008782x,+65LUT4,61.82MHz. Uncertainty calibration remains unproved.');
chart(s,['Savings %','Locations','Size','Frequency','Other'],[{name:'Attribution share',values:[47.1035,11.1000,7.2663,5.4586,29.0716],fill:C.blue}],{left:50,top:165,width:700,height:380},{yAxis:{min:0,max:60,majorUnit:20,title:{text:'Normalized contribution (%)'},textStyle:{fontSize:19,fill:C.ink},majorGridlines:solid(C.grid)},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.0',textStyle:{fontSize:19,fill:C.ink}}});
txt(s,'A high rank can still fail',790,176,410,70,30,C.navy,true);txt(s,'Bitcount: top-ranked\n1.0088× cycle speedup\n+65 LUT4 > +64 cap',790,267,410,135,27);txt(s,'Correctness passed;\narea made it infeasible.',790,428,410,85,25,C.amber,true);
txt(s,'Uncertainty guides questions; measured correctness and feasibility decide.',72,588,1136,60,27,C.blue,true);
}
{
const s=slide(8,'The LLM agent: choose, measure, respond',45,'The LLM selector uses controlled tools to inspect candidates, query predictions, request a bounded measurement, and return a validated selection. Paid outcomes feed its next decision, and failed requests consume budget. This is an actual agentic loop, separate from the coding assistants used for implementation, debugging, and analysis. The Ascon pilot measured three correct candidates; the best feasible one achieved about 1.024 times cycle speedup. But nine candidates remain unmeasured and there are no matched controls. A status-handling bug prevented live GP updates; the fix was verified afterward. We also have not implemented dynamic routing between language models.','Agent protocol and logs: results/2026-10-27-codex-chat-agent-edn-b64-s0/; Ascon results and docs/HANDOFF.md. EDN consumed replay:2 charged attempts including1 invalid ID, matched oracle and ordinary policies. Ascon C01:1.019698x,+73LUT4,62.992MHz; C06:1.017027x,+41LUT4,67.069MHz; C02:1.023731x,+42LUT4,64.620MHz.3/12 measured; correctness passed for all3. No claim of agent superiority or successful live GP refitting.');
flow(s,[['Inspect','Legal candidates\n+ constraints'],['Predict','ML scores\n+ model diagnostics'],['Measure','One charged attempt\nReveal real outcome'],['Select','Best verified feasible\nresult within budget']],186);
addLine(s,1100,345,1100,380,C.blue,2);addLine(s,420,380,1100,380,C.blue,2);txt(s,'Paid outcomes inform the next query',430,393,660,38,24,C.blue,true);
txt(s,'Selector AI',72,463,490,38,28,C.navy,true);txt(s,'Ascon pilot: 3 measured candidates\nBest feasible: 1.0237×, +42 LUT4',72,513,540,85,25);
txt(s,'Development AI',690,463,510,38,28,C.navy,true);txt(s,'Coding, debugging, literature and analysis\nHuman review owns claims and scope',690,513,510,85,24);
txt(s,'No matched agent win yet • live GP update defect disclosed • no dynamic LLM routing',72,625,1136,32,19,C.amber,true);
}
{
const s=slide(9,'Baselines and a fair measurement budget',35,'We compare against frequency, simple merit, architecture-aware heuristics, random search, and non-agent active learning. Merit prioritizes repeated instruction savings; it is already a strong baseline. Every policy should see the same pool and information, with one, two, or three charged attempts. Outcomes stay hidden until a permitted query. A result counts only if correct and feasible. The measured oracle is a retrospective reference, not a deployable policy. Historical training cost must be reported separately; this current development cohort is not untouched confirmation.','Protocol: docs/research-foundation.md; scorecard.json. Simple merit uses projected instruction savings; do not label it a CIDRE reproduction. Primary endpoint best verified feasible cycle reduction; regret only for complete pools. Track target evaluations and elapsed time, historical training cost, fit/inference and agent costs separately. Exact isolated ranker fit/inference timing remains incomplete.');
txt(s,'Required comparisons',72,156,530,45,30,C.navy,true);txt(s,'Frequency\nMerit: repeated instruction savings\nLatency / cost-aware heuristics\nRandom + non-agent active learning\nXGBoost + bounded LLM agent',72,222,560,265,27);
txt(s,'Same rules for every policy',700,156,500,45,30,C.navy,true);txt(s,'1 / 2 / 3 charged attempts\nAdded area ≤ 64 LUT4\nRouted timing ≥ 12 MHz\nCorrectness must pass\nUnqueried outcomes remain hidden',700,222,500,265,27);
txt(s,'Endpoint: best VERIFIED, FEASIBLE performance found per evaluation budget.',72,558,1136,75,29,C.blue,true);
}
{
const s=slide(10,'Results: early gains, no consistent ML win',75,'Here is the main selection result. The vertical axis is mean cycle-reduction regret relative to the best measured feasible candidate in each complete pool; lower is better. At one attempt, merit has 1.132 percent regret and the ranker has 0.842 percent. At two attempts they are almost tied. At three attempts, merit is better. The paired workload confidence intervals include zero for the early-budget advantages, so we cannot claim consistent superiority. Twelve workload groups have complete pool oracles; two incomplete groups are excluded from this regret calculation. The 2,925 policy-budget replays are dependent analyses of the existing measurements, not new hardware experiments. There is also an important diagnosis: all 122 historical cycle-speedup labels match the independently calibrated processor-latency calculation. This dataset therefore does not demonstrate a residual speedup relationship requiring machine learning. Our remaining challenge is learning which useful designs will be hardware-feasible and worth measuring. The Ascon pilot proves the selection-to-measurement connection, but its incomplete pool and missing controls prevent an agent-performance claim.','results/2026-10-27-final-selection-scorecard/scorecard.json. Paired difference = merit regret minus ranker regret (percentage points): B1 +0.290 [−0.065,+0.849]; B2 +0.027 [−0.097,+0.177]; B3 −0.056 [−0.167,0.000]. Workload bootstrap;12 complete pools.14-group cycle-reduction means merit1.086/1.657/2.043%;ranker1.334/1.680/1.996%. Timing floor weakly tested:minimum selected feasible Fmax59.13MHz vs12MHz. Target mean eval time merit55.67/114.24/169.76s;ranker56.29/115.69/171.46s. No total-cost advantage established.');
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
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:validated,explicitTotalSlideCount:11,pythonExecutable:'/Users/jasonrivera/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','3'],requiredNativeTableOwnerSlides:[3],requiredNativeChartOwnerSlides:[5,7,10],materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(root,'.codex-build/slides-11-validation/validation.json')});
await fs.writeFile(path.join(work,'speaker-notes.md'),'# ISAForge — 11-slide, seven-minute script\n\nTotal scheduled time: '+notes.reduce((a,n)=>a+n.time,0)+' seconds. Sources and Q&A material are not part of the spoken script.\n\n'+notes.map(n=>`## ${n.n}. ${n.title} (${n.time} seconds)\n\n${n.script}\n\n### Sources / Q&A\n\n${n.source}\n`).join('\n'));
console.log(JSON.stringify({slides:11,seconds:notes.reduce((a,n)=>a+n.time,0),spokenWords:notes.map(n=>n.script).join(' ').split(/\s+/).length,validated}));
