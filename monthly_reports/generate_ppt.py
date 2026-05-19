import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import argparse
import shutil
import json
from datetime import datetime
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
from core.generate_commentary import generate_monthly_slide_content
from monthly_reports.generate_visualisation import render_graph, initialise_brand, BRAND

initialise_brand()

# ── SLIDE LAYOUT INDICES ──────────────────────────────────────────────────────
SLD_LAYOUT_COVER                      = 0
SLD_LAYOUT_SECTION_SEPARATOR          = 1
SLD_LAYOUT_SUNSET_SECTION_SEPARATOR   = 2
SLD_LAYOUT_BURNT_ORANGE_SECTION_SEPARATOR = 3
SLD_LAYOUT_QUOTATION                  = 4
SLD_LAYOUT_TITLE_AND_BODY             = 5
SLD_LAYOUT_TITLE_AND_BODY_1           = 6
SLD_LAYOUT_TITLE_AND_BODY_2           = 7
SLD_LAYOUT_TITLE_AND_BODY_3           = 8
SLD_LAYOUT_2_COLUMN                   = 9
SLD_LAYOUT_3_COLUMN                   = 10
SLD_LAYOUT_4_COLUMN                   = 11
SLD_LAYOUT_BIG_NUMBER                 = 12
SLD_LAYOUT_BLANK                      = 13

# ── BRAND COLOURS ─────────────────────────────────────────────────────────────
C = {
    "gold":   RGBColor(0xFE, 0xC0, 0x42),
    "orange": RGBColor(0xF2, 0x7D, 0x39),
    "teal":   RGBColor(0x4F, 0xA6, 0xA4),
    "dark":   RGBColor(0x2B, 0x2D, 0x42),
    "white":  RGBColor(0xFF, 0xFF, 0xFF),
    "light":  RGBColor(0xFF, 0xF7, 0xE4),
    "grey":   RGBColor(0xD9, 0xD9, 0xD9),
}

STATUS_COLOURS = {
    "Complete":    C["teal"],
    "In Progress": C["gold"],
    "Scheduled":   C["grey"],
    "Blocked":     C["orange"],
}


# ── PRIVATE HELPERS ───────────────────────────────────────────────────────────

def _set_text(tf, text, size=Pt(14)):
    tf.text = text
    for p in tf.paragraphs:
        for run in p.runs:
            run.font.size = size


def _shrink_bullet(p, pct=70):
    pPr = p._p.get_or_add_pPr()
    for el in pPr.findall(qn('a:buSzPct')):
        pPr.remove(el)
    bu = pPr.makeelement(qn('a:buSzPct'), attrib={'val': str(pct * 1000)})
    pPr.append(bu)


def _populate_bullets(tf, bullets, size=Pt(12)):
    tf.clear()
    for i, bullet in enumerate(bullets):
        text = bullet['point'] if isinstance(bullet, dict) else bullet
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = text
        p.level = 0
        _shrink_bullet(p)
    for p in tf.paragraphs:
        for run in p.runs:
            run.font.size = size


def _add_chart_image(slide, chart_path, left=Inches(5), top=Inches(1.5), width=Inches(4.5)):
    with Image.open(chart_path) as img:
        img_w, img_h = img.size
    height = int(width * img_h / img_w)
    slide.shapes.add_picture(chart_path, left=left, top=top, width=width, height=height)


def _add_title_textbox(slide, title):
    tb = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.8))
    tf = tb.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = title
    run.font.name = BRAND["font"]
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = C["dark"]


def _style_cell(cell, text, bg_colour=None, text_colour=None, bold=False,
                size=Pt(10), align=PP_ALIGN.LEFT):
    if bg_colour:
        cell.fill.solid()
        cell.fill.fore_color.rgb = bg_colour
    cell.text = text
    tf = cell.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    for run in p.runs:
        run.font.name = BRAND["font"]
        run.font.size = size
        run.font.bold = bold
        if text_colour:
            run.font.color.rgb = text_colour


def _add_table_shape(slide, headers, rows, left, top, width, height, status_col=None):
    n_rows = len(rows) + 1
    n_cols = len(headers)
    tbl = slide.shapes.add_table(n_rows, n_cols, left, top, width, height).table

    for j, header in enumerate(headers):
        _style_cell(tbl.cell(0, j), header,
                    bg_colour=C["dark"], text_colour=C["white"],
                    bold=True, align=PP_ALIGN.CENTER)

    for i, row in enumerate(rows):
        row_bg = C["light"] if i % 2 == 0 else C["white"]
        for j, val in enumerate(row):
            cell_bg = STATUS_COLOURS.get(val, row_bg) if (status_col is not None and j == status_col) else row_bg
            _style_cell(tbl.cell(i + 1, j), val, bg_colour=cell_bg, text_colour=C["dark"], align=PP_ALIGN.CENTER)

    return tbl


def _add_kpi_boxes(slide, kpis, start_x=Inches(7.1), start_y=None,
                   box_w=Inches(2.5), box_h=Inches(0.95), gap=Inches(0.1)):
    if start_y is None:
        n = len(kpis)
        total_h = n * box_h + (n - 1) * gap
        # Body content area on TITLE_AND_BODY layout: top=1.30", bottom=4.62"
        body_top    = Inches(1.30)
        body_bottom = Inches(4.62)
        start_y = body_top + (body_bottom - body_top - total_h) / 2

    box_colours = [C["gold"], C["orange"], C["teal"]]

    for i, (label, data) in enumerate(kpis):
        y = start_y + i * (box_h + gap)
        shape = slide.shapes.add_shape(1, start_x, y, box_w, box_h)
        shape.fill.solid()
        shape.fill.fore_color.rgb = box_colours[i % len(box_colours)]
        shape.line.fill.background()

        tf = shape.text_frame
        tf.word_wrap = False
        tf.margin_top    = Inches(0.1)
        tf.margin_bottom = Inches(0.08)
        tf.margin_left   = Inches(0.1)
        tf.margin_right  = Inches(0.1)

        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = label
        run.font.name = BRAND["font"]
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = C["dark"]

        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        run2 = p2.add_run()
        run2.text = data.get('curr', '—')
        run2.font.name = BRAND["font"]
        run2.font.size = Pt(17)
        run2.font.bold = True
        run2.font.color.rgb = C["dark"]

        p3 = tf.add_paragraph()
        p3.alignment = PP_ALIGN.CENTER
        run3 = p3.add_run()
        run3.text = f"vs {data.get('prev', '—')}  ({data.get('pct', '—')})"
        run3.font.name = BRAND["font"]
        run3.font.size = Pt(9)
        run3.font.color.rgb = C["dark"]


def _build_kpis(client):
    paid_total = client.get('paid_data', {}).get('Total', {})
    if client.get('account_type') == 'Lead Gen':
        return [
            ('Cost',        paid_total.get('Cost', {})),
            ('Conversions', paid_total.get('Conversions', {})),
            ('CPA',         paid_total.get('CPA', {})),
        ]
    return [
        ('Cost',    paid_total.get('Cost', {})),
        ('Revenue', paid_total.get('Transaction Revenue', {})),
        ('ROAS',    paid_total.get('ROAS', {})),
    ]


def _extract_current_tasks(plan_json):
    if not plan_json:
        return []
    if isinstance(plan_json, list):
        return plan_json
    if 'tasks' in plan_json and 'plan_status' not in plan_json:
        return plan_json['tasks']
    for quarter_data in plan_json.values():
        if isinstance(quarter_data, dict) and quarter_data.get('plan_status') == 'current':
            tasks = quarter_data.get('tasks', [])
            return tasks if isinstance(tasks, list) else []
    return []


def _fmt_date(date_str):
    if not date_str:
        return ''
    for fmt in ('%d/%m/%y', '%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%d/%m/%Y')
        except ValueError:
            continue
    return date_str


# ── PUBLIC SLIDE TEMPLATES ────────────────────────────────────────────────────

def slide_cover(prs, title):
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_COVER])
    slide.placeholders[0].text = title
    return slide


def slide_section_separator(prs, title, variant='navy'):
    layout_map = {
        'navy':   SLD_LAYOUT_SECTION_SEPARATOR,
        'gold':   SLD_LAYOUT_SUNSET_SECTION_SEPARATOR,
        'orange': SLD_LAYOUT_BURNT_ORANGE_SECTION_SEPARATOR,
    }
    slide = prs.slides.add_slide(prs.slide_layouts[layout_map.get(variant, SLD_LAYOUT_SECTION_SEPARATOR)])
    slide.placeholders[0].text = title
    return slide


def slide_commentary(prs, title, summary, bullets):
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_TITLE_AND_BODY])
    slide.placeholders[0].text = title
    try:
        _set_text(slide.placeholders[4].text_frame, summary)
    except (KeyError, IndexError):
        pass
    try:
        _populate_bullets(slide.placeholders[1].text_frame, bullets)
    except (KeyError, IndexError):
        pass
    return slide


def slide_chart_commentary(prs, title, summary, bullets, chart_path, date_range=None):
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_TITLE_AND_BODY])
    slide.placeholders[0].text = title
    try:
        if date_range:
            slide.placeholders[2].text = f"{date_range['start']} to {date_range['end']}"
    except (KeyError, IndexError):
        pass
    try:
        _set_text(slide.placeholders[4].text_frame, summary)
    except (KeyError, IndexError):
        pass
    try:
        _populate_bullets(slide.placeholders[1].text_frame, bullets)
    except (KeyError, IndexError):
        pass
    _add_chart_image(slide, chart_path)
    return slide


def slide_scorecard_commentary(prs, title, summary, bullets, kpis):
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_TITLE_AND_BODY])
    slide.placeholders[0].text = title
    try:
        _set_text(slide.placeholders[4].text_frame, summary)
    except (KeyError, IndexError):
        pass
    try:
        _populate_bullets(slide.placeholders[1].text_frame, bullets)
    except (KeyError, IndexError):
        pass
    _add_kpi_boxes(slide, kpis)
    return slide


def slide_scorecard(prs, title, kpis):
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_BLANK])
    _add_title_textbox(slide, title)

    n = len(kpis)
    box_w  = Inches(2.5)
    box_h  = Inches(1.1)
    gap    = Inches(0.2)
    total_w = n * box_w + (n - 1) * gap
    start_x = (prs.slide_width - total_w) // 2
    start_y = (prs.slide_height - box_h) // 2
    box_colours = [C["gold"], C["orange"], C["teal"]]

    for i, (label, data) in enumerate(kpis):
        x = start_x + i * (box_w + gap)
        shape = slide.shapes.add_shape(1, x, start_y, box_w, box_h)
        shape.fill.solid()
        shape.fill.fore_color.rgb = box_colours[i % len(box_colours)]
        shape.line.fill.background()

        tf = shape.text_frame
        tf.word_wrap = False
        tf.margin_top    = Inches(0.1)
        tf.margin_bottom = Inches(0.08)
        tf.margin_left   = Inches(0.1)
        tf.margin_right  = Inches(0.1)

        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = label
        run.font.name = BRAND["font"]
        run.font.size = Pt(10)
        run.font.bold = True
        run.font.color.rgb = C["dark"]

        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        run2 = p2.add_run()
        run2.text = data.get('curr', '—')
        run2.font.name = BRAND["font"]
        run2.font.size = Pt(17)
        run2.font.bold = True
        run2.font.color.rgb = C["dark"]

        p3 = tf.add_paragraph()
        p3.alignment = PP_ALIGN.CENTER
        run3 = p3.add_run()
        run3.text = f"vs {data.get('prev', '—')}  ({data.get('pct', '—')})"
        run3.font.name = BRAND["font"]
        run3.font.size = Pt(9)
        run3.font.color.rgb = C["dark"]

    return slide


def slide_table(prs, title, headers, rows, status_col=None):
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_BLANK])
    _add_title_textbox(slide, title)
    table_top = Inches(1.2)
    table_h = prs.slide_height - table_top - Inches(0.2)
    _add_table_shape(slide, headers, rows,
                     left=Inches(0.5), top=table_top,
                     width=prs.slide_width - Inches(1.0), height=table_h,
                     status_col=status_col)
    return slide


def slide_table_commentary(prs, title, headers, rows, bullets, status_col=None):
    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_BLANK])
    _add_title_textbox(slide, title)

    table_top = Inches(1.2)
    content_h = prs.slide_height - table_top - Inches(0.2)

    tb = slide.shapes.add_textbox(Inches(0.5), table_top, Inches(4.0), content_h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, bullet in enumerate(bullets):
        text = bullet['point'] if isinstance(bullet, dict) else bullet
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = text
        p.level = 0
        _shrink_bullet(p)
        for run in p.runs:
            run.font.size = Pt(11)
            run.font.name = BRAND["font"]
            run.font.color.rgb = C["dark"]

    _add_table_shape(slide, headers, rows,
                     left=Inches(4.7), top=table_top,
                     width=prs.slide_width - Inches(5.0), height=content_h,
                     status_col=status_col)
    return slide


def _render_gantt_chart(tasks, title):
    STATUS_HEX = {
        "Complete":    BRAND["tertiary"],
        "In Progress": BRAND["primary"],
        "Scheduled":   "#D9D9D9",
        "Blocked":     BRAND["secondary"],
    }

    parsed = []
    for t in tasks:
        start_str = _fmt_date(t.get('start_date', ''))
        end_str   = _fmt_date(t.get('end_date', ''))
        try:
            start = datetime.strptime(start_str, '%d/%m/%Y')
            end   = datetime.strptime(end_str,   '%d/%m/%Y')
        except ValueError:
            continue
        parsed.append({
            'name':     t.get('name', ''),
            'start':    start,
            'end':      end,
            'status':   t.get('status', 'Scheduled'),
            'platform': t.get('platform', ''),
        })

    if not parsed:
        return None

    fig, ax = plt.subplots(figsize=(12, max(3.5, len(parsed) * 0.75 + 1.0)))

    for i, task in enumerate(reversed(parsed)):
        start_n = mdates.date2num(task['start'])
        end_n   = mdates.date2num(task['end'])
        dur     = max(end_n - start_n, 1)
        colour  = STATUS_HEX.get(task['status'], "#D9D9D9")

        ax.barh(i, dur, left=start_n, height=0.55,
                color=colour, edgecolor='white', linewidth=1.5)
        ax.text(start_n + dur / 2, i, task['status'],
                ha='center', va='center', fontsize=8,
                fontweight='bold', color=BRAND["quaternary"])

    ax.set_yticks(range(len(parsed)))
    ax.set_yticklabels([t['name'] for t in reversed(parsed)], fontsize=9)
    ax.yaxis.set_tick_params(length=0)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.get_xticklabels(), rotation=30, ha='right', fontsize=9)

    ax.set_title(title, fontsize=14, fontweight='bold', pad=12, color=BRAND["quaternary"])
    ax.grid(True, alpha=0.2, axis='x')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    legend_handles = [
        Patch(facecolor=c, label=s, edgecolor='white')
        for s, c in STATUS_HEX.items()
    ]
    ax.legend(handles=legend_handles, loc='lower right', fontsize=8,
              facecolor=BRAND["background"], edgecolor=BRAND["quaternary"])

    plt.tight_layout()
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}_gantt.png")
    fig.savefig(path, bbox_inches='tight', dpi=150)
    plt.close(fig)
    return path


def slide_planning_gantt(prs, title, tasks):
    if not tasks:
        return None

    chart_path = _render_gantt_chart(tasks, title)
    if not chart_path:
        return None

    slide = prs.slides.add_slide(prs.slide_layouts[SLD_LAYOUT_BLANK])
    _add_title_textbox(slide, title)
    _add_chart_image(slide, chart_path, left=Inches(0.4), top=Inches(1.1), width=Inches(9.2))
    return slide


# ── PIPELINE ORCHESTRATOR ─────────────────────────────────────────────────────

def generate_ppt(client_name, output_path=None, slide_content=None):
    data_path = os.path.join(PROJECT_ROOT, "storage", f"{client_name}_monthly_data.json")
    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"No monthly data file found for '{client_name}'. "
            f"Run: python -m monthly_reports.main --client \"{client_name}\""
        )
    with open(data_path, "r", encoding="utf-8") as f:
        client = json.load(f)

    if slide_content is None:
        slide_content = generate_monthly_slide_content(client)
    client['slide_content'] = slide_content
    content_path = os.path.join(PROJECT_ROOT, "storage", f"{client_name}_monthly_content.json")
    with open(content_path, "w", encoding="utf-8") as f:
        json.dump(client['slide_content'], f, ensure_ascii=False, indent=2)

    current_month = datetime.strptime(client['start_date_string'], "%d/%m/%Y").strftime("%B")

    if output_path is None:
        output_path = os.path.join(PROJECT_ROOT, "slides", f"{client_name}_monthly.pptx")
    template_path = os.path.join(PROJECT_ROOT, "slides", "template.pptx")
    shutil.copy(template_path, output_path)
    prs = Presentation(output_path)

    slide_rid = prs.slides._sldIdLst[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
    prs.part.drop_rel(slide_rid)
    prs.slides._sldIdLst.remove(prs.slides._sldIdLst[0])

    kpis = _build_kpis(client)
    sc   = client['slide_content']

    slide_cover(prs, f'{client["name"]} Monthly Deck')

    slide_section_separator(prs, 'Paid Media', variant='navy')

    slide_section_separator(prs, 'Performance Overview', variant='gold')
    slide_scorecard_commentary(
        prs,
        title=   'Top Level View',
        summary= sc['overview']['summary'],
        bullets= sc['overview']['bullets'],
        kpis=    kpis,
    )

    slide_section_separator(prs, 'Top Level Trends', variant='gold')
    for trend in sc['trends']:
        chart_path = render_graph(client, trend['graph'])
        slide_chart_commentary(
            prs,
            title=      trend['title'],
            summary=    trend['summary'],
            bullets=    trend['bullets'],
            chart_path= chart_path,
            date_range= trend['graph']['date_range'],
        )

    slide_section_separator(prs, f'{current_month} Actions', variant='gold')
    action_bullets = [
        f"{action['task']}: {action['summary']} - {action['status']}"
        for action in sc['actions']
    ]
    slide_commentary(prs, f'{current_month} Actions', '', action_bullets)

    plan_json = client.get('plan_json')
    if plan_json:
        tasks = _extract_current_tasks(plan_json)
        if tasks:
            slide_planning_gantt(prs, '90 Day Plan', tasks)

    prs.save(output_path)
    print(f"Saved {output_path} with {len(prs.slides)} slide(s)")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, help="Client name as it appears in config.json")
    parser.add_argument("--output", default=None, help="Output path for the generated PPTX")
    args = parser.parse_args()
    generate_ppt(args.client, args.output)
