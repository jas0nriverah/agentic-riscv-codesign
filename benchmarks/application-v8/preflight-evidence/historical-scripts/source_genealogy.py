"""Conservative source-lineage evidence; heuristic body matches never prove independence."""
from pathlib import Path
import hashlib,json,re,collections
OUT=Path(__file__).resolve().parent;REPO=OUT.parent/'agentic-riscv-codesign';REF=OUT.parent/'references/tacle-bench'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(s):return re.sub(r'/\*.*?\*/|//[^\n]*',' ',s,flags=re.S)
def bodies(path):
 text=clean(path.read_text(errors='replace'));position=0;result=[]
 pattern=re.compile(r'\b([A-Za-z_]\w*)\s*\(([^;{}]*?)\)\s*\{',re.S)
 while True:
  match=pattern.search(text,position)
  if not match:break
  name=match.group(1);start=match.end();depth=1;cursor=start
  while cursor<len(text) and depth:
   depth+=int(text[cursor]=='{')-int(text[cursor]=='}');cursor+=1
  position=cursor
  if name in {'if','for','while','switch'}:continue
  result.append((name,text[start:cursor-1]))
 return result
KEYWORDS=set('if else for while do switch case default return break continue sizeof struct union enum const volatile unsigned signed long short int char float double void static extern register auto typedef'.split())
def normalized(body):
 tokens=re.findall(r'0[xX][0-9a-fA-F]+[uUlL]*|\b[0-9]+[uUlL]*\b|[A-Za-z_]\w*|>>=|<<=|==|!=|<=|>=|\+\+|--|<<|>>|&&|\|\||[^\s]',body)
 names={};result=[]
 for t in tokens:
  if re.fullmatch(r'[A-Za-z_]\w*',t) and t not in KEYWORDS:
   t=names.setdefault(t,'id'+str(len(names)))
  elif re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]*',t):
   number=re.sub('[uUlL]+$','',t);t=str(int(number,16 if number.lower().startswith('0x') else 10))
  result.append(t)
 return tuple(result)
def grams(tokens):return set(zip(*(tokens[i:] for i in range(5)))) if len(tokens)>=5 else set()
consumed=[];paths=sorted((REPO/'benchmarks/embench/src').rglob('*.c'))
for path in paths:
 for name,body in bodies(path):
  tokens=normalized(body)
  if len(tokens)>=40:consumed.append({'path':str(path.relative_to(REPO)),'name':name,'tokens':tokens,'grams':grams(tokens)})
programs={'bitcount':REF/'bench/kernel/bitcount','isqrt':REF/'bench/kernel/isqrt','fft':REF/'bench/kernel/fft','ndes':REF/'bench/sequential/ndes','mpeg2':REF/'bench/sequential/mpeg2','h264_dec':REF/'bench/sequential/h264_dec'}
records={}
for p,directory in programs.items():
 result=[]
 for path in sorted(directory.glob('*.c')):
  for name,body in bodies(path):
   if not name.startswith(p+'_'):continue
   tokens=normalized(body)
   if len(tokens)<40:continue
   g=grams(tokens);rank=[]
   for c in consumed:
    exact=tokens==c['tokens'];score=len(g&c['grams'])/len(g|c['grams']) if g|c['grams'] else 0
    rank.append((score,c['path'],c['name'],exact,len(c['tokens'])))
   top=sorted(rank,reverse=True)[:3]
   result.append({'function':name,'source':str(path.relative_to(REF)),'source_sha256':sha(path),'normalized_body_tokens':len(tokens),
    'normalized_body_sha256':hashlib.sha256(json.dumps(tokens,separators=(',',':')).encode()).hexdigest(),
    'exact_alpha_renamed_body_matches':[{'path':b,'function':c} for a,b,c,e,n in rank if e],
    'top_5gram_jaccard_candidates':[{'jaccard':a,'path':b,'function':c,'exact':e,'token_count':n} for a,b,c,e,n in top]})
 records[p]=result
special=[REPO/'benchmarks/embench/src/cubic/basicmath_small.c',REPO/'benchmarks/embench/src/cubic/snipmath.h',REPO/'benchmarks/embench/src/cubic/libcubic.c',REF/'bench/kernel/isqrt/isqrt.c',REF/'bench/kernel/isqrt/snipmath.h',REF/'bench/kernel/isqrt/ChangeLog.txt']
report={'status':'input-only-source-genealogy-not-proved-family-independence','consumed_c_files':len(paths),'consumed_nontrivial_function_bodies':len(consumed),
 'method':'Stripcomments; extractbalancedfunctionbodies; tokenizewithoperators/numericvaluespreserved and identifiersalpharenamedinfirstappearanceorder; compareexactbodiesand5gramJaccard. >=40tokens; noCpreprocessing/ASTsemanticnonequivalenceproof. Smallfunctions/headers/macros/manualancestryrequireseparatereview.',
 'records':records,'special_ancestry_file_sha256':{str(p.relative_to(REPO)) if REPO in p.parents else 'tacle/'+str(p.relative_to(REF)):sha(p) for p in special},
 'isqrt_manual_verdict':'Relatedsourcefamily/commonMiBenchbasicmath_small+SNIPPETSumbrella withconsumedcubic; sharedint_sqrt declaration differsinfieldwidth. Currentpinnedcubic executesSolveCubic only, noactualusqrtimplementation/callfound. DoNOTclaimsameexecutedkernel; doNOTclaimfullyuntouchedsourcefamily. Keeprelated-sourcecontroloutsidefreshprimary.',
 'bitcount_manual_verdict':'SourceSnippets collection alsoappearsincubic ancestry, butdifferentkernel/package thanbasicmath. Noidentifiedexecutedpopcountkernel inconsumed19; exactformula/codeheuristics areseparate. Broadsourcecollectionoverlap remains.',
 'ndes_manual_verdict':'PaperclassifiesMRTCorigin; pinnedCauthor/sourcefieldunknown/blank. NoDESkernelfoundinconsumed19, AEScryptodomainisrelatedbroadly. License/remoteancestrynotprovedbylocaltokenchecks; retainpinnedupstreamnoticeanduncertainty.',
 'limits':'No matchdoesnotproveindependentorigin/no equivalentfunction. Matchmaybegenericboilerplate. No area labels,sourceexecution,models/fits/testassignmentseal.'}
(OUT/'source-genealogy.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print('Compared',len(paths),'consumedCfiles,',len(consumed),'nontrivialbodies')
for name,rs in records.items():
 exact=[(r['function'],r['exact_alpha_renamed_body_matches']) for r in rs if r['exact_alpha_renamed_body_matches']]
 print(name,'examined',len(rs),'exactrenamedmatches',exact)
