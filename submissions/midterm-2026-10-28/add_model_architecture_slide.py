"""Insert an editable, evidence-accurate XGBoost architecture slide.

Run with the presentation Python environment:
  python add_model_architecture_slide.py [input.pptx] [output.pptx]

The script preserves the existing slide objects and inserts the new slide after
the dataset slide.  It only changes the hard-coded footer numbers on slides
that move as a result of that insertion.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "isaforge-midterm-progress-slides-final.pptx"
DEFAULT_OUTPUT = DEFAULT_INPUT

NAVY = RGBColor(0x17, 0x32, 0x4D)
BLUE = RGBColor(0x28, 0x78, 0xA8)
TEXT = RGBColor(0x26, 0x36, 0x48)
SLATE = RGBColor(0x60, 0x72, 0x86)
EDGE = RGBColor(0xD5, 0xE0, 0xEA)
PALE = RGBColor(0xF3, 0xF7, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def add_text(slide, x, y, w, h, value, *, size, color=TEXT, bold=False,
             align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.MIDDLE):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.03)
    frame.margin_right = Inches(0.03)
    frame.margin_top = Inches(0.015)
    frame.margin_bottom = Inches(0.015)
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.space_before = Pt(0)
    paragraph.space_after = Pt(0)
    paragraph.font.name = "Arial"
    paragraph.font.size = Pt(size)
    paragraph.font.bold = bold
    paragraph.font.color.rgb = color
    paragraph.text = value
    return box


def add_card(slide, x, y, w, h, heading, body, *, body_size=13.2):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = PALE
    shape.line.color.rgb = EDGE
    shape.line.width = Pt(1.0)
    add_text(slide, x + 0.14, y + 0.10, w - 0.28, 0.26, heading,
             size=11.2, color=BLUE, bold=True)
    add_text(slide, x + 0.14, y + 0.39, w - 0.28, h - 0.47, body,
             size=body_size, color=TEXT, valign=MSO_ANCHOR.TOP)
    return shape


def add_arrow(slide, x, y, w=0.25, h=0.20):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = BLUE
    shape.line.fill.background()
    return shape


def set_footer(slide, number):
    for shape in slide.shapes:
        if not getattr(shape, "has_text_frame", False):
            continue
        text = shape.text
        if text.startswith("ISAForge") and "ECE 4803" in text:
            shape.text = re.sub(r"\d+\s*$", str(number), text)
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.name = "Arial"
                    run.font.size = Pt(9)
                    run.font.color.rgb = SLATE
            return


def populate_slide(slide, page_number):
    add_text(slide, 0.71, 0.44, 11.67, 0.60,
             "Inside the XGBoost ranker", size=32.25, color=NAVY, bold=True)
    rule = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.71), Inches(1.14), Inches(11.92), Inches(0.012)
    )
    rule.fill.solid()
    rule.fill.fore_color.rgb = EDGE
    rule.line.fill.background()
    add_text(
        slide, 0.75, 1.34, 11.85, 0.40,
        "ISAForge uses boosted decision trees, not a neural network. The ranker learns candidate order from measured whole-program speedups.",
        size=16.2, color=TEXT, bold=True,
    )

    y, h = 2.02, 1.66
    xs = [0.75, 3.83, 7.28, 9.83]
    widths = [2.62, 2.98, 2.15, 2.75]
    add_card(
        slide, xs[0], y, widths[0], h, "TRAINING DATA",
        "122 verified labels · 14 groups\n35 structural/profile features\nLabel: baseline ÷ candidate cycles\nGrouped by workload context",
        body_size=12.2,
    )
    add_card(
        slide, xs[1], y, widths[1], h, "PAIRWISE XGBOOST RANKER",
        "80 boosted trees · depth 2\nrank:pairwise objective\nLearns which candidate is faster within each workload group",
        body_size=13.0,
    )
    add_card(
        slide, xs[2], y, widths[2], h, "RANK OUTPUT",
        "rank_score\nOrders candidates\nNot a speedup or confidence estimate",
        body_size=12.0,
    )
    add_card(
        slide, xs[3], y, widths[3], h, "SELECTION POLICY",
        "Use scores and paid results to choose the next candidate. Respect the query budget and hardware limits. Policy: heuristic or bounded LLM.",
        body_size=12.0,
    )
    add_arrow(slide, 3.48, 2.75, 0.23, 0.18)
    add_arrow(slide, 6.91, 2.75, 0.23, 0.18)
    add_arrow(slide, 9.55, 2.75, 0.20, 0.18)

    band = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.75), Inches(3.94), Inches(11.83), Inches(0.72),
    )
    band.fill.solid()
    band.fill.fore_color.rgb = WHITE
    band.line.color.rgb = EDGE
    band.line.width = Pt(1.0)
    add_text(slide, 0.91, 4.06, 2.27, 0.44, "SEPARATE SPEEDUP MODEL",
             size=10.8, color=BLUE, bold=True)
    add_text(
        slide, 3.38, 4.04, 8.94, 0.48,
        "20 bootstrapped XGBoost regressors predict the speedup ratio; their spread is model disagreement, not calibrated uncertainty.",
        size=12.3, color=TEXT,
    )

    add_text(slide, 0.75, 4.88, 11.8, 0.27, "A paid query produces new ground truth",
             size=12.0, color=BLUE, bold=True)
    y2, h2 = 5.22, 0.91
    xs2 = [0.75, 4.08, 7.88]
    ws2 = [3.02, 3.42, 4.70]
    add_card(slide, xs2[0], y2, ws2[0], h2, "ONE CANDIDATE", "Spend one query from the fixed budget.", body_size=12.4)
    add_card(slide, xs2[1], y2, ws2[1], h2, "PICORV32 EVALUATION", "Lower · execute · verify · synthesize and route.", body_size=12.4)
    add_card(slide, xs2[2], y2, ws2[2], h2, "MEASURED OUTCOME", "Whole-program cycles and speedup · added LUT4 · routed Fmax · correctness.", body_size=12.4)
    add_arrow(slide, 3.78, 5.58, 0.22, 0.18)
    add_arrow(slide, 7.55, 5.58, 0.22, 0.18)

    add_text(
        slide, 0.75, 6.30, 11.85, 0.48,
        "The rank score does not predict area or timing. Final feasibility uses measured hardware results; paid outcomes update the live history, while the frozen model is not retrained mid-search.",
        size=10.8, color=SLATE,
    )
    add_text(slide, 0.71, 7.15, 11.92, 0.19,
             f"ISAForge  /  ECE 4803                                    {page_number}",
             size=9.0, color=SLATE)
    return slide


def clear_slide_content(slide):
    # Preserve the required nonvisual group nodes; replace only editable shapes.
    tree = slide.shapes._spTree
    for element in list(tree)[2:]:
        tree.remove(element)


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    prs = Presentation(input_path)
    if len(prs.slides) < 3:
        raise SystemExit("Expected the existing midterm deck with a dataset slide.")
    existing = next((slide for slide in prs.slides if any(
        getattr(sh, "has_text_frame", False) and sh.text == "Inside the XGBoost ranker"
        for sh in slide.shapes)), None)
    if existing is None:
        # The authored deck contains only its single custom blank layout.
        slide = prs.slides.add_slide(prs.slides[2].slide_layout)
    else:
        slide = existing
        clear_slide_content(slide)
    populate_slide(slide, 4)

    # New slides append; move the editable architecture slide to position four.
    slide_ids = prs.slides._sldIdLst
    slide_id = next(item for item in slide_ids if int(item.id) == slide.slide_id)
    slide_ids.remove(slide_id)
    slide_ids.insert(3, slide_id)

    for index, slide in enumerate(prs.slides, start=1):
        set_footer(slide, index)

    prs.save(output_path)
    print(f"Saved {output_path} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
