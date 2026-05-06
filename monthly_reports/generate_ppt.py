import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import shutil
import json
from datetime import datetime
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from PIL import Image
from lxml import etree
from core.generate_commentary import generate_monthly_slide_content
from monthly_reports.generate_visualisation import render_graph, initialise_brand, BRAND

initialise_brand()

# Initialise the names of the slide layouts
SLD_LAYOUT_COVER = 0
SLD_LAYOUT_SECTION_SEPARATOR = 1
SLD_LAYOUT_SUNSET_SECTION_SEPARATOR = 2
SLD_LAYOUT_BURNT_ORANGE_SECTION_SEPARATOR = 3
SLD_LAYOUT_QUOTATION = 4
SLD_LAYOUT_TITLE_AND_BODY = 5
SLD_LAYOUT_TITLE_AND_BODY_1 = 6
SLD_LAYOUT_TITLE_AND_BODY_2 = 7
SLD_LAYOUT_TITLE_AND_BODY_3 = 8
SLD_LAYOUT_2_COLUMN = 9
SLD_LAYOUT_3_COLUMN = 10
SLD_LAYOUT_4_COLUMN = 11
SLD_LAYOUT_BIG_NUMBER = 12
SLD_LAYOUT_BLANK = 13



def generate_ppt(client_name, output_path=None):
    data_path = f"storage/{client_name}_monthly_data.json"
    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"No monthly data file found for '{client_name}'. "
            f"Run: python -m monthly_reports.main --client \"{client_name}\""
        )
    with open(data_path, "r", encoding="utf-8") as f:
        client = json.load(f)

    client['slide_content'] = generate_monthly_slide_content(client)
    with open(f"storage/{client_name}_monthly_content.json", "w", encoding="utf-8") as f:
        json.dump(client['slide_content'], f, ensure_ascii=False, indent=2)

    current_month = datetime.strptime(client['start_date_string'], "%d/%m/%Y").strftime("%B")

    if output_path is None:
        output_path = f"slides/{client_name}_monthly.pptx"
    shutil.copy('slides/template.pptx', output_path)
    prs = Presentation(output_path)

    # Remove the single placeholder slide
    slide_rid = prs.slides._sldIdLst[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
    prs.part.drop_rel(slide_rid)
    prs.slides._sldIdLst.remove(prs.slides._sldIdLst[0])

    # Title Slide
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_COVER])
    slide.placeholders[0].text = f'{client["name"]} Monthly Deck'

    # Paid Separator Slide
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_SECTION_SEPARATOR])
    slide.placeholders[0].text = 'Paid Media'

    # Overall Summary Slide
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_SUNSET_SECTION_SEPARATOR])
    slide.placeholders[0].text = 'Performance Overview'
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_TITLE_AND_BODY])
    slide.placeholders[0].text = 'Top Level View'
    tf = slide.placeholders[4].text_frame
    tf.text = client['slide_content']['overview']['summary']
    for p in tf.paragraphs:
        for run in p.runs:
            run.font.size = Pt(14)
    tf = slide.placeholders[1].text_frame
    tf.clear()
    for i, bullet in enumerate(client['slide_content']['overview']['bullets']):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = bullet['point']
        p.level = 0
    for p in tf.paragraphs:
        for run in p.runs:
            run.font.size = Pt(12)
    add_kpi_boxes(slide, client)

    # Trends
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_SUNSET_SECTION_SEPARATOR])
    slide.placeholders[0].text = 'Top Level Trends'
    for trend in client['slide_content']['trends']:
        slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_TITLE_AND_BODY])
        slide.placeholders[0].text = trend['title']
        slide.placeholders[2].text = f"{trend['graph']['date_range']['start']} to {trend['graph']['date_range']['end']}"
        tf = slide.placeholders[4].text_frame
        tf.text = trend['summary']
        for p in tf.paragraphs:
            for run in p.runs:
                run.font.size = Pt(14)
        tf = slide.placeholders[1].text_frame
        tf.clear()
        for i, bullet in enumerate(trend['bullets']):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = bullet['point']
            p.level = 0
        for p in tf.paragraphs:
            for run in p.runs:
                run.font.size = Pt(12)
        chart_path = render_graph(client, trend['graph'])
        add_chart_to_slide(slide, chart_path)

    # Actions
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_SUNSET_SECTION_SEPARATOR])
    slide.placeholders[0].text = f'{current_month} Actions'
    for action in client['slide_content']['actions']:
        slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_TITLE_AND_BODY])
        slide.placeholders[0].text = action['task']
        slide.placeholders[1].text = action['summary']
        tf = slide.placeholders[4].text_frame
        tf.text = action['status']
        for p in tf.paragraphs:
            for run in p.runs:
                run.font.size = Pt(14)
        if action['graph'] is not None:
            slide.placeholders[2].text = f"{action['graph']['date_range']['start']} to {action['graph']['date_range']['end']}"
            chart_path = render_graph(client, action['graph'])
            add_chart_to_slide(slide, chart_path)

    prs.save(output_path)
    print(f"Saved {output_path} with {len(prs.slides)} slide(s)")


def add_kpi_boxes(slide, client):
    paid_total = client.get('paid_data', {}).get('Total', {})
    account_type = client.get('account_type', 'Ecommerce')

    if account_type == 'Ecommerce':
        kpis = [
            ('Cost',    paid_total.get('Cost', {})),
            ('Revenue', paid_total.get('Transaction Revenue', {})),
            ('ROAS',    paid_total.get('ROAS', {})),
        ]
    else:
        kpis = [
            ('Cost',        paid_total.get('Cost', {})),
            ('Conversions', paid_total.get('Conversions', {})),
            ('CPA',         paid_total.get('CPA', {})),
        ]

    box_colours = [
        RGBColor(0xFE, 0xC0, 0x42),
        RGBColor(0xF2, 0x7D, 0x39),
        RGBColor(0x4F, 0xA6, 0xA4),
    ]
    text_colour = RGBColor(0x2B, 0x2D, 0x42)

    box_w = Inches(2.6)
    box_h = Inches(1.4)
    gap   = Inches(0.15)
    start_x = Inches(7.1)
    # Align the centre of the middle box (index 1) to the vertical midpoint of the slide
    start_y = Inches(3.75) - box_h * 1.5 - gap

    font_name = BRAND["font"]

    for i, (label, data) in enumerate(kpis):
        y = start_y + i * (box_h + gap)
        shape = slide.shapes.add_shape(1, start_x, y, box_w, box_h)
        shape.fill.solid()
        shape.fill.fore_color.rgb = box_colours[i]
        shape.line.fill.background()

        tf = shape.text_frame
        tf.word_wrap = False
        tf.margin_top    = Inches(0.1)
        tf.margin_bottom = Inches(0.08)
        tf.margin_left   = Inches(0.1)
        tf.margin_right  = Inches(0.1)

        # Metric label
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = label
        run.font.name = font_name
        run.font.size = Pt(10)
        run.font.bold = True
        run.font.color.rgb = text_colour

        # Current value
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        run2 = p2.add_run()
        run2.text = data.get('curr', '—')
        run2.font.name = font_name
        run2.font.size = Pt(17)
        run2.font.bold = True
        run2.font.color.rgb = text_colour

        # vs previous  (% change)
        p3 = tf.add_paragraph()
        p3.alignment = PP_ALIGN.CENTER
        run3 = p3.add_run()
        run3.text = f"vs {data.get('prev', '—')}  ({data.get('pct', '—')})"
        run3.font.name = font_name
        run3.font.size = Pt(9)
        run3.font.color.rgb = text_colour


def add_chart_to_slide(slide, chart_path, left=Inches(5), top=Inches(1.5), width=Inches(4.5)):
    """
    Adds a chart image to a slide preserving its aspect ratio.
    
    Args:
        slide:       the pptx slide object to add the image to
        chart_path:  path to the chart image file
        left:        distance from left edge of slide (default 5 inches)
        top:         distance from top of slide (default 1.5 inches)
        width:       desired width of the chart (default 4.5 inches)
    """
    with Image.open(chart_path) as img:
        img_width, img_height = img.size
        aspect_ratio = img_height / img_width

    height = int(width * aspect_ratio)

    slide.shapes.add_picture(
        chart_path,
        left=left,
        top=top,
        width=width,
        height=height
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, help="Client name as it appears in config.json")
    parser.add_argument("--output", default=None, help="Output path for the generated PPTX")
    args = parser.parse_args()
    generate_ppt(args.client, args.output)