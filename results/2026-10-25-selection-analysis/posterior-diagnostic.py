import json,numpy as np,csv,math
from scipy.spatial.distance import cdist
from scipy.linalg import cho_factor,cho_solve
from scipy.special import ndtr
from isaforge.semantic_selection import semantic_matrix
from isaforge.budgeted_selection import PUBLIC_KEYS
from isaforge.codesign import digest
base='results/2026-10-22-bitcount-preregistration/'
s=json.load(open(base+'targets/tacle-bitcount/semantic/snapshot.json'));h={r['candidate_id']:r for r in json.load(open(base+'inputs/history.json'))};train=[h[i] for i in s['training_ids']];public=json.load(open(base+'targets/tacle-bitcount/public.json'));live=json.load(open('results/2026-10-22-bitcount-report/live.json'))['search'];cs=list(csv.DictReader(open('results/2026-10-22-bitcount-report/candidates.csv')));names={r['candidate_id']:r['candidate'] for r in cs};trmap={r['candidate_id']:r for r in public};actual={r['candidate_id']:float(r['added_lut4']) for r in cs}
def matrix(rows):return np.asarray(semantic_matrix([{k:r[k] for k in PUBLIC_KEYS} for r in rows]))
print('training',len(train),'feature count',len(s['columns']),'feature hash exact',digest(matrix(train).tolist())==s['feature_matrix_sha256']);print('scaler area output',s['outputs'])
for e in [e for e in live['events'] if e['action']=='acquire']:
 print('QUERY',e['charged_before_query']+1)
 for p in sorted(e['hardware_predictions'],key=lambda p:-(trmap[p['candidate_id']]['latency_features']['estimated_speedup']-1)*ndtr((64-p['area_delta_lut4_mean'])/p['area_delta_lut4_std'])):
  g=trmap[p['candidate_id']]['latency_features']['estimated_speedup']-1;prob=ndtr((64-p['area_delta_lut4_mean'])/p['area_delta_lut4_std']);timing=ndtr((p['routed_fmax_min_mhz_mean']-12)/p['routed_fmax_min_mhz_std']);score=g*prob*timing*p['device_fit_probability'];print(names[p['candidate_id']], 'gain',round(g,7),'area',round(p['area_delta_lut4_mean'],5),round(p['area_delta_lut4_std'],5),'p',round(prob,6),'score',round(score,9))
X=(matrix(train)-s['scaler']['mean'])/s['scaler']['scale'];Z=(matrix(public)-s['scaler']['mean'])/s['scaler']['scale'];
def kern(a,b):
 r=np.sqrt(3)*cdist(a,b);return (1+r)*np.exp(-r)
K=kern(X,X)+1e-4*np.eye(len(X));ks=kern(Z,X);cov=kern(Z,Z)-ks@cho_solve(cho_factor(K),ks.T);area=s['outputs']['area_delta_lut4'];y=np.array([r['area_delta_lut4'] for r in train]);mu=area['mean']+ks@cho_solve(cho_factor(K),(y-area['mean'])/area['scale'])*area['scale'];std=np.sqrt(np.diag(cov))*area['scale'];initial=[e for e in live['events'] if e['action']=='acquire'][0];pred={r['candidate_id']:r for r in initial['hardware_predictions']};print('reconstructed mean max abs',max(abs(mu[i]-pred[r['candidate_id']]['area_delta_lut4_mean']) for i,r in enumerate(public)),'std max abs',max(abs(std[i]-pred[r['candidate_id']]['area_delta_lut4_std']) for i,r in enumerate(public)))
corr=cov/np.sqrt(np.outer(np.diag(cov),np.diag(cov)));ni={names[r['candidate_id']]:i for i,r in enumerate(public)};print('posterior correlations')
for a in ['candidate_00','candidate_14','candidate_11','candidate_08','candidate_31','candidate_28']:
 print(a, {b:round(float(corr[ni[a],ni[b]]),9) for b in ['candidate_00','candidate_14','candidate_11','candidate_08','candidate_31','candidate_28']})
print('nearest training, prior k max, initial marginal fraction of prior variance')
for i,r in enumerate(public):
 j=np.argmin(cdist(Z[i:i+1],X)[0]);print(names[r['candidate_id']],round(float(cdist(Z[i:i+1],X)[0,j]),5),round(float(ks[i,j]),6),round(float(cov[i,i]),7),train[j]['formula'])
for a,b in [('candidate_00','candidate_14'),('candidate_00','candidate_11'),('candidate_14','candidate_11'),('candidate_00','candidate_31'),('candidate_11','candidate_08')]:
 i,j=ni[a],ni[b];sq=(Z[i]-Z[j])**2;inds=np.argsort(-sq);print('distance decomposition',a,b,'distance',float(np.sqrt(sq.sum())),[(s['columns'][k],round(float(sq[k]),5)) for k in inds if sq[k]>1e-15])
print('area residuals')
for i,r in enumerate(public):print(names[r['candidate_id']],actual[r['candidate_id']]-mu[i])
# Read-only drift diagnosis: reproduce moments and conditional algebra, never fit.
paid=[e['observation'] for e in live['events'] if e['action']=='measure-complete']
print('PAID MOMENT DRIFT (no fits)')
for n in range(3):
 rows=train+paid[:n];m=matrix(rows);means=m.mean(0);scales=m.std(0);scales=np.where(scales==0,1.,scales);a=np.asarray([r['area_delta_lut4'] for r in rows]);f=np.asarray([r['routed_fmax_min_mhz'] for r in rows]);print('prefix',n,'nrows',len(rows),'area_center',a.mean(),'area_scale',a.std(),'timing_center',f.mean(),'timing_scale',f.std(),'device_fit',(1+sum(r['device_fits'] for r in rows))/(len(rows)+2))
 if n:
  drift=np.abs(scales/np.asarray(s['scaler']['scale'])-1);print('max scale changes',[(s['columns'][k],float(np.asarray(s['scaler']['scale'])[k]),float(scales[k]),float(drift[k])) for k in np.argsort(-drift)[:7]])
print('FROZEN INITIAL POSTERIOR CONDITIONING vs ACTUAL DYNAMIC REFIT')
acqs=[e for e in live['events'] if e['action']=='acquire'];cov_lut=cov*area['scale']**2;noise=1e-4*area['scale']**2
for n in [1,2]:
 obs=[ni[names[r['candidate_id']]] for r in paid[:n]];unobs=[ni[names[r['candidate_id']]] for r in acqs[n]['hardware_predictions']];v=np.asarray([r['area_delta_lut4'] for r in paid[:n]])-mu[obs];fmu=mu+cov_lut[:,obs]@np.linalg.solve(cov_lut[np.ix_(obs,obs)]+noise*np.eye(n),v);fcov=cov_lut-cov_lut[:,obs]@np.linalg.solve(cov_lut[np.ix_(obs,obs)]+noise*np.eye(n),cov_lut[obs,:]);record={r['candidate_id']:r for r in acqs[n]['hardware_predictions']}
 for name in ['candidate_14','candidate_11','candidate_31']:
  idx=ni[name];ident=public[idx]['candidate_id']
  if ident in record:print('paid_prefix',n,name,'fixed_condition_mean',float(fmu[idx]),'fixed_condition_std',float(np.sqrt(fcov[idx,idx])),'actual_mean',record[ident]['area_delta_lut4_mean'],'actual_std',record[ident]['area_delta_lut4_std'])
print('INITIAL ERROR SUMMARIES')
err=np.asarray([actual[r['candidate_id']]-mu[i] for i,r in enumerate(public)]);print('bias',float(err.mean()),'MAE',float(abs(err).mean()),'min',float(err.min()),'max',float(err.max()),'noise_std_LUT',float(np.sqrt(noise)))
