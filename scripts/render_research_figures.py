#!/usr/bin/env python3
"""Render original publication-style research diagrams from saved findings.

No model loading, feature extraction, training or hardware commands. The four
comparisons have separate cohorts/metrics and must not form a learning curve.
Values are self-contained transcriptions from the saved reports at SOURCE_COMMIT;
no deleted historical result path is needed to regenerate the artifacts.
"""
from pathlib import Path
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, FancyArrowPatch, Rectangle

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/figures/research'
SOURCE_COMMIT='b64716a2b94b332fdbced677869620bb949c073d'
NAVY='#14283F'; INK='#23394F'; MUTED='#617487'; LINE='#DCE5EB'
TEAL='#087F83'; TEAL_LIGHT='#E5F3F1'; BLUE='#416C9B'; BLUE_LIGHT='#EDF3F9'
GOLD='#D68A25'; GOLD_LIGHT='#FFF2DA'; RED='#B54E48'; RED_LIGHT='#FBEEEB'
PAPER='#F7FAFB'; WHITE='#FFFFFF'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,
    'svg.fonttype':'none','pdf.fonttype':42,'ps.fonttype':42,
    'axes.unicode_minus':False,'savefig.facecolor':PAPER})


def text(ax,x,y,s,size=12,color=INK,weight='normal',ha='left',va='center',**kw):
    return ax.text(x,y,s,fontsize=size,color=color,fontweight=weight,ha=ha,va=va,**kw)


def box(ax,x,y,w,h,face=WHITE,edge=LINE,r=.012,lw=1.1):
    p=FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0,rounding_size={r}',
        linewidth=lw,edgecolor=edge,facecolor=face,zorder=1)
    ax.add_patch(p); return p


def dot(ax,xy,r,**kw):
    # Keep nodes circular in physical output, despite the wide diagram axes.
    fw,fh=ax.figure.get_size_inches()
    return Ellipse(xy,2*r,2*r*fw/fh,**kw)


def arrow(ax,start,end,color=BLUE,lw=1.8,style='-|>',**kw):
    p=FancyArrowPatch(start,end,arrowstyle=style,mutation_scale=13,
        linewidth=lw,color=color,zorder=4,**kw)
    ax.add_patch(p); return p


def canvas(w,h):
    fig=plt.figure(figsize=(w,h),facecolor=PAPER)
    ax=fig.add_axes((0,0,1,1));ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
    return fig,ax


def save(fig,name,out):
    out.mkdir(parents=True,exist_ok=True)
    provenance='Saved research reports at '+SOURCE_COMMIT+'; model settings from isaforge/area_model_v6.py; comparisons from '+', '.join(d['source'] for d in PANELS)+'. Separate cohorts and weighting; no learning curve.'
    for ext in ('svg','png','pdf'):
        metadata={'Creator':'Original research figures; Matplotlib','Title':name}
        metadata['Subject' if ext=='pdf' else 'Description']=provenance
        fig.savefig(out/f'{name}.{ext}',dpi=180,metadata=metadata)
    plt.close(fig)


def tree(ax,cx,top,width=.075,height=.16,index='1',route='left'):
    # A schematic of an individual ExtraTree, not a data sampling diagram.
    points={'r':(cx,top),'a':(cx-width*.29,top-height*.43),'b':(cx+width*.29,top-height*.43),
        'aa':(cx-width*.45,top-height),'ab':(cx-width*.13,top-height),
        'ba':(cx+width*.13,top-height),'bb':(cx+width*.45,top-height)}
    selected={'r','a','ab'} if route=='left' else {'r','b','ba'}
    for a,b in [('r','a'),('r','b'),('a','aa'),('a','ab'),('b','ba'),('b','bb')]:
        highlight=a in selected and b in selected
        ax.plot([points[a][0],points[b][0]],[points[a][1],points[b][1]],
            color=GOLD if highlight else '#B7C8D5',lw=2.4 if highlight else 1.4,zorder=3)
    for key,(x,y) in points.items():
        leaf=len(key)==2; fill=GOLD if key in selected else TEAL if leaf else WHITE
        ax.add_patch(dot(ax,(x,y),.0068 if leaf else .0085,facecolor=fill,
            edgecolor=GOLD if key in selected else TEAL if leaf else BLUE,linewidth=1.4,zorder=5))
    text(ax,cx,top+.053,'Tree '+index,13,NAVY,'bold',ha='center')
    text(ax,cx,top-height-.041,r'$\hat{y}_{'+index+r'}$',18,TEAL,ha='center')


def model_figure(out):
    fig,ax=canvas(18,9.5)
    text(ax,.035,.942,'From RV32 computation to predicted LUT area',27,NAVY,'bold')
    text(ax,.035,.888,'One fixed feature representation, followed by an equally weighted ensemble of 300 ExtraTrees.',13,MUTED)
    cards=[(.035,.185,'01  INPUT'),(.245,.205,'02  FEATURES'),(.477,.335,'03  FOREST'),(.842,.123,'04  OUTPUT')]
    for x,w,label in cards:
        text(ax,x,.817,label,10,MUTED,'bold')
        box(ax,x,.282,w,.474)
    # Formula and its original arithmetic syntax.
    text(ax,.052,.716,'RV32 computation',15,NAVY,'bold')
    box(ax,.050,.593,.155,.075,BLUE_LIGHT,BLUE_LIGHT,.008)
    text(ax,.1275,.631,'(in0 × 31) XOR in1',12.5,NAVY,ha='center',fontfamily='DejaVu Sans Mono')
    nodes=[(.127,.531,'xor'),(.087,.449,'mul'),(.168,.449,'in1'),(.060,.367,'in0'),(.114,.367,'31')]
    for a,b in [(0,1),(0,2),(1,3),(1,4)]:
        ax.plot([nodes[a][0],nodes[b][0]],[nodes[a][1]-.015,nodes[b][1]+.015],color='#BCCBD6',lw=1.6,zorder=2)
    for x,y,label in nodes:
        box(ax,x-.020,y-.018,.040,.036,BLUE_LIGHT,LINE,.005)
        text(ax,x,y,label,10.5,BLUE,ha='center')
    text(ax,.052,.309,'32-bit integer semantics',10.3,MUTED)
    # Feature engineering, prior to physical target mapping.
    text(ax,.262,.716,'Circuit representation',15,NAVY,'bold')
    text(ax,.262,.673,'Static syntax + pre-mapping graphs',10.5,MUTED)
    graph_nodes=[(.272,.588),(.302,.625),(.335,.580),(.365,.620),(.407,.582)]
    for a,b in [(0,1),(0,2),(1,3),(2,3),(3,4)]:
        ax.plot([graph_nodes[a][0],graph_nodes[b][0]],[graph_nodes[a][1],graph_nodes[b][1]],color='#89B6BD',lw=1.7)
    for x,y in graph_nodes:ax.add_patch(dot(ax,(x,y),.007,facecolor=TEAL,edgecolor=WHITE,lw=1.5,zorder=3))
    text(ax,.3475,.540,'Original · normalized · operator graphs',9.5,MUTED,ha='center')
    box(ax,.262,.438,.170,.065,BLUE_LIGHT,BLUE_LIGHT,.007)
    text(ax,.347,.474,'336',22,NAVY,'bold',ha='center')
    text(ax,.347,.450,'descriptors computed',9.5,MUTED,ha='center')
    arrow(ax,(.347,.430),(.347,.400),TEAL,1.5)
    box(ax,.262,.317,.170,.075,TEAL_LIGHT,TEAL_LIGHT,.007)
    text(ax,.347,.363,'217',24,TEAL,'bold',ha='center')
    text(ax,.347,.336,'fixed model inputs',10,TEAL,ha='center')
    # The forest uses the full dataset in every tree: no bootstrap/subset framing.
    text(ax,.495,.716,'300 randomized decision trees',15,NAVY,'bold')
    text(ax,.495,.675,'Each sees all training circuits and all 217 inputs.',10.5,MUTED)
    tree(ax,.536,.577,index='1',route='left')
    tree(ax,.643,.577,index='2',route='right')
    text(ax,.703,.507,'···',25,MUTED,ha='center')
    tree(ax,.759,.577,index='300',route='left')
    text(ax,.644,.313,'Random split thresholds  ·  No bootstrap sampling',10.1,MUTED,ha='center')
    # Equally weighted within-forest aggregation.
    text(ax,.9035,.716,'Mean',17,NAVY,'bold',ha='center')
    text(ax,.9035,.650,'Equal weight',10.5,MUTED,ha='center')
    text(ax,.9035,.575,r'$\hat{y}=\frac{1}{300}\sum_{t=1}^{300}\hat{y}_t$',17,TEAL,ha='center')
    box(ax,.855,.359,.097,.110,TEAL_LIGHT,TEAL_LIGHT,.008)
    text(ax,.9035,.427,'LUT4',22,TEAL,'bold',ha='center')
    text(ax,.9035,.392,'predicted count',10,TEAL,ha='center')
    text(ax,.9035,.309,'Area point estimate',9.6,MUTED,ha='center')
    for a,b in [((.220,.518),(.245,.518)),((.450,.518),(.477,.518)),((.812,.518),(.842,.518))]:arrow(ax,a,b)
    # Separate fixed routing from within-forest averaging.
    box(ax,.035,.082,.930,.135,WHITE,LINE,.012)
    text(ax,.052,.180,'OPTIONAL COVERAGE POLICY',10,MUTED,'bold')
    text(ax,.052,.135,'Fixed arithmetic gate',13,NAVY,'bold')
    arrow(ax,(.244,.135),(.278,.135),MUTED,1.4)
    box(ax,.291,.105,.165,.060,BLUE_LIGHT,BLUE_LIGHT,.007)
    text(ax,.3735,.135,'Base forest',12,BLUE,'bold',ha='center')
    text(ax,.473,.135,'or',11,MUTED,ha='center')
    box(ax,.491,.105,.165,.060,TEAL_LIGHT,TEAL_LIGHT,.007)
    text(ax,.5735,.135,'Coverage forest',12,TEAL,'bold',ha='center')
    arrow(ax,(.674,.135),(.710,.135),MUTED,1.4)
    text(ax,.728,.143,'Return one selected prediction',12,NAVY,'bold')
    text(ax,.728,.112,'Selection across models; averaging stays inside each forest.',9.2,MUTED)
    text(ax,.035,.037,'Isolated original-RTL LUT4 area • uncalibrated points • no CPU speed, timing, power or uncertainty-bound claim',10,MUTED)
    save(fig,'model',out)


PANELS=[
    {'title':'Mapping-aware descriptors','cohort':'192 newly measured test circuits',
     'metric':'Equal-stratum MAE · LUT4','baseline':'Graph control','updated':'Mapping descriptors',
     'a':34.332,'b':32.161,'fmt':'.3f','pct':'6.32% lower','good':True,
     'note':'Same 1,665 fitting circuits; 23 descriptors added.',
     'source':'docs/v6-results.md'},
    {'title':'Targeted training coverage','cohort':'Previously consumed application panel',
     'metric':'Equal-family MAE · LUT4','baseline':'Base forest','updated':'Coverage forest',
     'a':3.4092,'b':2.5434,'fmt':'.4f','pct':'25.40% lower','good':True,
     'note':'48 targeted circuits added; this is a development result.',
     'source':'docs/v9-coverage-results.md'},
    {'title':'Reserved-program transfer','cohort':'327 originals · 521 program memberships',
     'metric':'Equal-family / eligible-program MAE · LUT4','baseline':'Base forest','updated':'Coverage forest',
     'a':.506605,'b':.525239,'fmt':'.6f','pct':'3.68% higher','good':False,
     'note':'Five eligible families; empty recursion error remains undefined.',
     'source':'docs/v11e-transfer-results.md'},
    {'title':'Scoped arithmetic stress','cohort':'32 new related circuits · four templates',
     'metric':'Equal-template MAE · LUT4','baseline':'Base forest','updated':'Scoped policy',
     'a':15.5211458,'b':12.0092708,'fmt':'.4f','pct':'22.63% lower','good':True,
     'note':'All 32 select the coverage forest; scoped policy equals it.',
     'source':'docs/v15-scoped-results.md'}]


def comparison_card(ax,rect,number,d):
    x,y,w,h=rect
    box(ax,x,y,w,h,WHITE,LINE,.014)
    text(ax,x+.020,y+h-.037,f'{number:02d}',10,MUTED,'bold')
    text(ax,x+.055,y+h-.037,d['title'],17,NAVY,'bold')
    text(ax,x+.020,y+h-.080,d['cohort'],11,MUTED)
    text(ax,x+.020,y+h-.116,d['metric'],10,MUTED)
    color=TEAL if d['good'] else RED
    # Independent local scale, always based at zero. No cross-panel axis or line.
    left=x+.162; end=x+w-.085; length=end-left
    maximum=max(d['a'],d['b'])*1.13
    by=[y+.145,y+.085];bh=.026
    for yy,label,value,c in [(by[0],d['baseline'],d['a'],BLUE),(by[1],d['updated'],d['b'],color)]:
        text(ax,x+.020,yy,label,11,INK)
        ax.add_patch(Rectangle((left,yy-bh/2),length,bh,facecolor='#F1F5F7',edgecolor='none',zorder=2))
        bar=length*value/maximum
        ax.add_patch(Rectangle((left,yy-bh/2),bar,bh,facecolor=c,edgecolor='none',zorder=3))
        text(ax,left+bar+.007,yy,format(value,d['fmt']),11,c,'bold')
    badgew=.108
    box(ax,x+w-badgew-.020,y+h-.145,badgew,.047,TEAL_LIGHT if d['good'] else RED_LIGHT,
        TEAL_LIGHT if d['good'] else RED_LIGHT,.008)
    text(ax,x+w-badgew/2-.020,y+h-.121,d['pct'],11,color,'bold',ha='center')
    text(ax,x+.020,y+.031,d['note'],9.3,MUTED)


def improvement_figure(out):
    fig,ax=canvas(17.5,11)
    text(ax,.035,.949,'What improved — and where it did not',28,NAVY,'bold')
    text(ax,.035,.902,'Four separate matched comparisons. Lower MAE is better; cohorts, weighting and panel scales differ.',12.7,MUTED)
    positions=[(.035,.531,.452,.308),(.513,.531,.452,.308),(.035,.183,.452,.308),(.513,.183,.452,.308)]
    for i,(rect,d) in enumerate(zip(positions,PANELS),1):comparison_card(ax,rect,i,d)
    box(ax,.035,.052,.930,.092,GOLD_LIGHT,GOLD_LIGHT,.010)
    text(ax,.052,.116,'AVERAGE ERROR IS ONLY PART OF THE RESULT',10,'#855A1D','bold')
    text(ax,.052,.083,'Scoped stress: worst underprediction grows  2.83 → 32.01 LUT4.',15,'#855A1D','bold')
    text(ax,.625,.084,'Experimental policy; no conservative budget guarantee.',10.7,'#855A1D')
    text(ax,.035,.025,'Saved comparisons: mapping descriptors · consumed applications · reserved source programs · covered-domain synthetic stress',9.5,MUTED)
    save(fig,'improvement',out)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=OUT)
    args=p.parse_args();model_figure(args.output);improvement_figure(args.output)
    print('Rendered model and improvement in SVG, PNG and PDF: '+str(args.output.resolve()))


if __name__=='__main__':main()
