"""Complete static inventory/notices and input-only overlap; no program execution."""
from pathlib import Path
import collections,hashlib,json,re,sys
OUT=Path(__file__).resolve().parent;REPO=OUT.parent/'agentic-riscv-codesign';REF=OUT.parent/'references/tacle-bench'
sys.path[:0]=[str(REPO/'src'),str(REPO)]
from candidates import readProgram,extractCandidates
from isaforge import structural_features_v5 as v5
from isaforge.features import parse_formula

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def selected(s,name,allowed):
 return bool(s) and any(s==x or s.startswith(x+'.') or (x.endswith('_') and s.startswith(x)) for x in allowed) and s not in {name+'_init',name+'_return',name+'_main'}
if (OUT/'complete-static-inventory.json').exists():raise ValueError('Existing evidence immutable')
original=read(OUT/'static-preflight.json');paths=[REPO/'results/2026-10-14-v6/corpus/consumed-features.json',REPO/'results/2026-10-14-v6/corpus/calibration/features.json',REPO/'results/2026-10-14-v6/corpus/test/features.json']
consumed=sum((read(p)['records'] for p in paths),[])
exact={parse_formula(r['formula']).canonical() for r in consumed};normalized={r['normalized_formula'] for r in consumed}
records={}
for name,r in original['records'].items():
 if r['status']!='compiled-static-legality-only':records[name]=r;continue
 elf=OUT/('static-'+name)/(name+'.elf');program=readProgram(elf,str(OUT.parent/'toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-objdump'))
 starts={}
 for pc,row in program.items():starts.setdefault(row.get('symbol'),pc)
 candidates=extractCandidates(program,collections.Counter({pc:1 for pc in program}),set(starts.values()),maxSize=4)
 all_patterns=[]
 for p in candidates:
  occurrences=[{'blockStart':o['blockStart'],'pcs':o['pcs'],'size':o['size'],'symbols':o['symbols'],
    'in_declared_kernel':bool(o['symbols']) and all(selected(s,name,r['kernel_symbol_filter']) for s in o['symbols'])} for o in p['occurrences']]
  canonical=parse_formula(p['formula']).canonical();norm=v5.normalize_formula(canonical)
  all_patterns.append({'formula':canonical,'normalized_v5_formula':norm,'sizes':p['sizeVariants'],
   'occurrences':occurrences,'exact_consumed':canonical in exact,'normalized_v5_consumed':norm in normalized})
 kept=[p for p in all_patterns if any(o['in_declared_kernel'] for o in p['occurrences'])]
 assert len(kept)==r['kernel_static_unique_formulas']
 source=REF/Path(r['source_files'][0]).parent;notice=OUT/'source-notices'/name;notice.mkdir(parents=True)
 for sourcepath in sorted(p for p in source.iterdir() if p.is_file()):
  text=sourcepath.read_text(errors='replace')
  if sourcepath.name.lower() in ('license','copying','copyright.txt'):
   (notice/sourcepath.name).write_bytes(sourcepath.read_bytes())
  elif sourcepath.suffix in ('.c','.h'):
   head=re.match(r'\s*(/\*.*?\*/)',text,re.S)
   if head:(notice/(sourcepath.name+'.notice.txt')).write_text(head.group(1)+'\n')
 records[name]={'all_static_patterns':all_patterns,'kernel_static_unique_formulas':len(kept),
  'kernel_exact_overlap_count':sum(p['exact_consumed'] for p in kept),
  'kernel_normalized_v5_overlap_count':sum(p['normalized_v5_consumed'] for p in kept),
  'kernel_neither_exact_nor_normalized_overlap':sum(not(p['exact_consumed'] or p['normalized_v5_consumed']) for p in kept),
  'all_static_formulas_retained':True,'helper_init_excluded_static_patterns':len(all_patterns)-len(kept)}
 print(name,records[name]['kernel_static_unique_formulas'],records[name]['kernel_exact_overlap_count'],records[name]['kernel_normalized_v5_overlap_count'],flush=True)
write(OUT/'complete-static-inventory.json',{'status':'unsealed-input-only-static-inventory','consumed_unique_formulas':len(exact),
 'consumed_input_files_sha256':{str(p.relative_to(REPO)):sha(p) for p in paths},'preflight_sha256':sha(OUT/'static-preflight.json'),
 'script_sha256':sha(__file__),'source_normalization_runtime_sha256':{'structural_features_v5.py':sha(REPO/'isaforge/structural_features_v5.py')},
 'records':records,'new_labels_models_sourceexecution_native_mapping':False,
 'novelty_limits':'Exact/V5normalized only; no generic feature vectors/skeletons/strongsemantic components acquired. Counts are static plausible pools, not executed candidates, complete application coverage, strict novelty or performance.'})
