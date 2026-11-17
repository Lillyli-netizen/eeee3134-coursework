"""把 Part1_Report_Webpage_zh.md 生成 Word 报告（封面 + 正文 + 表格 + 页码）。"""
from pathlib import Path
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "Part1_Report_Webpage_zh.md"
OUT = ROOT / "Part1_Report_Webpage_zh.docx"

SERIF_LATIN = "Times New Roman"
SERIF_CN = "宋体"
SANS_CN = "黑体"


def set_run_font(run, size=None, bold=None, latin=SERIF_LATIN, east=SERIF_CN, color=None):
    run.font.name = latin
    run._element.rPr.rFonts.set(qn("w:eastAsia"), east)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def add_runs(paragraph, text, size=11, bold=False, latin=SERIF_LATIN, east=SERIF_CN):
    """处理 **加粗** 行内标记。"""
    for i, chunk in enumerate(text.split("**")):
        if not chunk:
            continue
        run = paragraph.add_run(chunk)
        set_run_font(run, size=size, bold=(bold or i % 2 == 1), latin=latin, east=east)


def add_page_number(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    set_run_font(run, size=9)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def style_heading(paragraph, text, level):
    run = paragraph.add_run(text)
    if level == 1:
        set_run_font(run, size=15, bold=True, latin="Arial", east=SANS_CN, color=RGBColor(0x1F, 0x2A, 0x44))
        paragraph.paragraph_format.space_before = Pt(18)
        paragraph.paragraph_format.space_after = Pt(8)
    else:
        set_run_font(run, size=12.5, bold=True, latin="Arial", east=SANS_CN, color=RGBColor(0x1F, 0x2A, 0x44))
        paragraph.paragraph_format.space_before = Pt(12)
        paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.keep_with_next = True


def add_table(doc, rows):
    header, body = rows[0], rows[1:]
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    widths = [Cm(2.6), Cm(6.6), Cm(7.0)] if len(header) == 3 else None

    def fill(cell, text, bold=False):
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        add_runs(p, text, size=9.5, bold=bold)

    for i, text in enumerate(header):
        fill(table.rows[0].cells[i], text, bold=True)
    for row in body:
        cells = table.add_row().cells
        for i, text in enumerate(row):
            fill(cells[i], text)
    if widths:
        for row in table.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = w
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def parse_md(text):
    lines = text.splitlines()
    cover, body, in_body = [], [], False
    for line in lines:
        if line.startswith("## 1 "):
            in_body = True
        (body if in_body else cover).append(line)
    return cover, body


def build():
    raw = SRC.read_text(encoding="utf-8")
    cover, body = parse_md(raw)

    doc = Document()
    section = doc.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21.0)
    section.top_margin = section.bottom_margin = Cm(2.4)
    section.left_margin = section.right_margin = Cm(2.4)
    add_page_number(section)

    normal = doc.styles["Normal"]
    normal.font.name = SERIF_LATIN
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), SERIF_CN)

    # ---------- 封面 ----------
    for _ in range(2):
        doc.add_paragraph()
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_runs(title, "个人网页开发报告", size=24, bold=True, latin="Arial", east=SANS_CN)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.paragraph_format.space_before = Pt(10)
    add_runs(sub, "EEEE3134 Applications of AI in Electrical and Electronic Engineering", size=12)
    sub2 = doc.add_paragraph()
    sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_runs(sub2, "Coursework Part I: Personal Webpage Development", size=12)

    doc.add_paragraph()
    for line in cover:
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("- ") or "Coursework Part I" in s:
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(4)
        add_runs(p, s, size=11.5)

    doc.add_paragraph()
    h = doc.add_paragraph()
    h.paragraph_format.space_before = Pt(18)
    h.paragraph_format.space_after = Pt(6)
    add_runs(h, "已发布网页", size=14, bold=True, latin="Arial", east=SANS_CN)
    for line in cover:
        s = line.strip()
        if not s.startswith("- "):
            continue
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.space_after = Pt(6)
        label, _, url = s[2:].partition("：")
        add_runs(p, f"{label}：", size=11, bold=True)
        add_runs(p, url, size=11)

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---------- 正文 ----------
    i = 0
    while i < len(body):
        line = body[i].rstrip()
        s = line.strip()
        i += 1
        if not s:
            continue
        if s.startswith("### "):
            p = doc.add_paragraph()
            style_heading(p, s[4:], 2)
        elif s.startswith("## "):
            p = doc.add_paragraph()
            style_heading(p, s[3:], 1)
        elif s.startswith("|"):
            rows = [s]
            while i < len(body) and body[i].strip().startswith("|"):
                rows.append(body[i].strip())
                i += 1
            parsed = []
            for r in rows:
                cells = [c.strip() for c in r.strip("|").split("|")]
                if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    continue
                parsed.append(cells)
            add_table(doc, parsed)
        elif s.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
            add_runs(p, s[2:], size=11)
        else:
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.first_line_indent = Pt(22)
            pf.line_spacing = 1.4
            pf.space_after = Pt(6)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_runs(p, s, size=11)

    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    build()
