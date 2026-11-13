#!/usr/bin/env python3
"""Render concise documentation SVGs; archived scientific figures stay immutable."""
from pathlib import Path
from html import escape

OUT = Path(__file__).resolve().parents[1] / 'docs/assets'
INK, MUTED = '#172b4d', '#52657d'


def text(x, y, label, size=14, bold=False, color=None):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color or INK}" font-weight="{600 if bold else 400}">{escape(label)}</text>'


def card(x, y, title, detail, width=176, height=84, accent=False):
    return (f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="6" fill="{"#edf3fa" if accent else "#f7f9fc"}" stroke="{"#a8bfd9" if accent else "#c7d0db"}"/>'
            + text(x+16,y+29,title,17,True) + text(x+16,y+55,detail,color=MUTED))


def arrow(path):
    return f'<path d="{path}" fill="none" stroke="{MUTED}" stroke-width="1.5" marker-end="url(#arrow)"/>'


def save(name, title, description, height, body, note):
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="{height}" viewBox="0 0 1040 {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M1 1 L7 4 L1 7" fill="none" stroke="{MUTED}" stroke-width="1.5"/></marker></defs>
<rect width="1040" height="{height}" rx="8" fill="#ffffff"/>
<g font-family="Arial, Helvetica, sans-serif">
{text(32,40,title,22,True)}
{body}
{text(32,height-28,note,15,color=MUTED)}
</g></svg>
'''
    (OUT/name).write_text(svg)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    body = card(32,162,'RV32 formula','Two-input computation')
    body += card(232,162,'Graph features','336 cached → 217 used')
    body += arrow('M208 204 H228')
    for y,title in [(72,'Tree 1'),(162,'Tree 2'),(252,'Tree 300')]:
        body += card(432,y,title,'Randomized splits',height=72)
        body += arrow(f'M408 204 H420 V{y+36} H428')
        body += arrow(f'M608 {y+36} H620 V204 H628')
    body += card(632,162,'Average','Equal tree weights')
    body += card(832,162,'Area estimate','Predicted iCE40 LUT4',accent=True)
    body += arrow('M808 204 H828')
    body += text(432,60,'300-TREE ENSEMBLE',14,color=MUTED)
    save('ml-model.svg','The ML model',
         '217 selected circuit features feed 300 ExtraTrees regressors. Each tree sees the same 1,665 training circuits with randomized splits; tree predictions are averaged. Three representative trees are shown.',
         390,body,'1,665 training circuits · all trees see the same training set · estimates are not calibrated safety bounds.')

    body=''
    for i,(title,detail) in enumerate([
        ('Declare','Hypothesis + limits'),('Develop','Features or coverage'),
        ('Freeze','Model + fresh inputs'),('Measure','New circuit labels'),('Evaluate','Accuracy + budgets')]):
        x=32+200*i
        body+=card(x,78,title,detail,accent=i==4)
        if i<4:body+=arrow(f'M{x+176} 120 H{x+196}')
    save('model-validation.svg','How a model earns promotion',
         'Declare a bounded experiment, develop the model, freeze its predictions and fresh inputs, measure circuits, then check both accuracy and hardware-budget errors. Failures and incomplete cohorts keep the default unchanged.',
         240,body,'Promote only when all gates pass. Failed or incomplete validation keeps the current default.')

    body=''
    rows=[('Representation','192 synthetic circuits','34.33 → 32.16 LUT4','6.32% lower MAE','Base retained'),
          ('Training coverage','327 application circuits','0.5066 → 0.5252 LUT4','3.68% worse family MAE','No transfer gain'),
          ('Arithmetic coverage','32 related circuits','15.52 → 12.01 LUT4','22.63% lower MAE','Worse underprediction tail')]
    for i,(title,cohort,metric,gain,decision) in enumerate(rows):
        x=32+332*i
        body+=card(x,78,title,cohort,width=312,height=170)
        body+=text(x+16,167,metric,20,True)
        body+=text(x+16,194,gain,15,color=MUTED)
        body+=text(x+16,225,decision,14,True)
    save('model-improvement.svg','What improved — and what did not',
         'Three separate studies. Mapping descriptors reduce MAE from34.33 to32.16 on192 synthetic circuits. Added training coverage worsens application family-macro MAE from0.5066 to0.5252. Arithmetic coverage reduces MAE from15.52 to12.01 on32 related circuits but worsens worst underprediction.',
         310,body,'Separate cohorts and metrics, not one learning curve. Better mean error alone does not justify promotion.')

    body=card(32,78,'Training coverage','1,889 → 1,921 circuits',width=312,height=120)
    body+=text(48,172,'One fit · 233 unchanged features',15,color=MUTED)
    body+=card(364,78,'Budget decisions','7 retained false accepts',width=312,height=120)
    body+=text(380,172,'4 new · candidate not promoted',15,color=MUTED)
    body+=card(696,78,'Fresh validation','16 / 55 area labels complete',width=312,height=120)
    body+=text(712,172,'Fresh MAE / MAPE unavailable',15,color=MUTED)
    save('research-status.svg','Latest coverage experiment: not promoted',
         '32 training circuits were added. Retained panels have seven false acceptances, four newly introduced. Fresh validation is incomplete with16 of55 labels. No fresh accuracy conclusion is available.',
         260,body,'288.69 / 300 worker-seconds · two workers maximum · failed cases and missing outcomes retained.')


if __name__ == '__main__':
    main()
