# -*- coding: utf-8 -*-
"""Generate Part II technical report as Word document (Chinese, figures + three-line tables).

Usage: python build_report_word.py
Output: PartII_Technical_Report_zh.docx  in the same directory.
"""

from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import OxmlElement
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "PartII_Technical_Report_zh_v9.docx"
FIG_DIR = ROOT / "part2-report_定稿_72a7a5c" / "figures"
SUP_DIR = ROOT / "part2-report_定稿_72a7a5c" / "supplement_20261110"

# Windows 内部字体名（Word / WPS 都能认）
FONT_AS = "Times New Roman"
FONT_CN = "SimSun"     # 宋体
FONT_HD = "SimHei"     # 黑体
FONT_CODE = "Courier New"


# ---------- 字体 ----------

def set_run_font(run, size=None, bold=None, italic=None,
                 font_cn=None, font_as=None):
    """设置中西文字体，确保 Word 和 WPS 都能渲染。"""
    run.font.name = font_as or FONT_AS
    run.font.size = Pt(size) if size is not None else run.font.size
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    # eastAsia 必须用 Windows 内部字体名，不能用中文
    rPr = run._r.get_or_add_rPr()
    # 先移除已有的 eastAsia
    for existing in rPr.findall(qn("w:eastAsia")):
        rPr.remove(existing)
    ea = OxmlElement("w:eastAsia")
    ea.set(qn("w:type"), font_cn or FONT_CN)
    rPr.append(ea)


# ---------- 段落 ----------

def add_para(doc, text, size=12, bold=False, align=None,
             space_after=6, space_before=0, first_line_indent=None,
             line_spacing=1.5, font_cn=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, font_cn=font_cn)
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.line_spacing = line_spacing
    if first_line_indent is not None:
        p.paragraph_format.first_line_indent = Cm(first_line_indent)
    return p


def _set_paragraph_border_bottom(paragraph, sz="6", color="2b6cb0"):
    """给段落加底部装饰线（H1 标题下用）。"""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def add_heading(doc, text, level=1):
    """Level 1 = 章标题（二号黑体居中 + 装饰线），Level 2 = 节标题（小三号黑体）。"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    if level == 1:
        set_run_font(run, size=22, bold=True, font_cn=FONT_HD)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(24)
        p.paragraph_format.space_after = Pt(14)
        p.paragraph_format.line_spacing = 1.5
        _set_paragraph_border_bottom(p, sz="8", color="2b6cb0")
    elif level == 2:
        set_run_font(run, size=15, bold=True, font_cn=FONT_HD)
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(10)
        p.paragraph_format.line_spacing = 1.5
    elif level == 3:
        set_run_font(run, size=14, bold=True, font_cn=FONT_HD)
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.5
    return p


# ---------- 三线表 ----------

def _set_cell_shading(cell, color_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    # 移除已有的 shd
    for existing in tcPr.findall(qn("w:shd")):
        tcPr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color_hex)
    tcPr.append(shd)


def _set_table_borders_three_lines(table):
    """三线表：顶线粗、表头下细线、底线粗；无竖线、无边线。"""
    tbl = table._tbl
    tblPr = tbl.tblPr
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    for child in list(tblPr):
        if child.tag == qn("w:tblBorders"):
            tblPr.remove(child)
    borders = OxmlElement("w:tblBorders")
    # 顶线粗
    for side, sz in [("top", "12"), ("bottom", "12")]:
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), sz)
        b.set(qn("w:color"), "000000")
        borders.append(b)
    # 表头下细线（header bottom）
    b = OxmlElement("w:insideH")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), "4")
    b.set(qn("w:color"), "000000")
    borders.append(b)
    # 无边线、无竖线
    for side in ("left", "right", "insideV"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "none")
        borders.append(b)
    tblPr.append(borders)


def _set_cell_text(cell, text, size=10.5, bold=False,
                   align=WD_ALIGN_PARAGRAPH.CENTER, font_cn=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    run = p.add_run(str(text))
    set_run_font(run, size=size, bold=bold, font_cn=font_cn or FONT_CN)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)


def add_table(doc, headers, rows, col_widths=None):
    """三线表 + 表头灰底 + 交替行微灰。"""
    n_cols = len(headers)
    table = doc.add_table(rows=1 + len(rows), cols=n_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_borders_three_lines(table)

    # 表头：黑体居中 + 浅灰底
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        _set_cell_text(cell, h, size=10.5, bold=True, font_cn=FONT_HD)
        _set_cell_shading(cell, "D9E2F3")  # 浅蓝色表头底

    # 正文：宋体居中 + 交替行微灰
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = table.rows[r + 1].cells[c]
            _set_cell_text(cell, val, size=10.5, bold=False, font_cn=FONT_CN)
            if r % 2 == 0:
                _set_cell_shading(cell, "FFFFFF")
            else:
                _set_cell_shading(cell, "F2F2F2")

    # 列宽
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                if i < len(row.cells):
                    row.cells[i].width = Cm(w)
    return table


# ---------- 题注与图片 ----------

def add_caption(doc, text, kind="table"):
    """表题在上（黑体居中），图题在下（黑体居中）。"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, size=10.5, bold=True, font_cn=FONT_HD)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if kind == "table":
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
    else:
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(14)
    return p


def add_figure(doc, image_path, width_cm=15.0):
    """插入图片，居中。"""
    if not Path(image_path).exists():
        print("  [skip] missing:", image_path)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run()
    run.add_picture(str(image_path), width=Cm(width_cm))


# ---------- 代码片段 ----------

def add_code_block(doc, code_text, lang="python"):
    """等宽字体代码块，浅灰底。"""
    lines = code_text.rstrip().split("\n")
    for line in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = Pt(13)
        p.paragraph_format.left_indent = Cm(0.8)
        run = p.add_run(line if line else " ")
        run.font.name = FONT_CODE
        run.font.size = Pt(9)
        # 浅灰底：通过段落底纹实现
        pPr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), "F5F5F5")
        pPr.append(shd)
    # 尾部空行
    doc.add_paragraph().paragraph_format.space_before = Pt(0)


# ---------- 目录 ----------

def add_toc_items(doc, items):
    for text, level in items:
        p = doc.add_paragraph()
        run = p.add_run(text)
        if level == 0:
            set_run_font(run, size=14, bold=True, font_cn=FONT_HD)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(1)
        elif level == 1:
            set_run_font(run, size=12, font_cn=FONT_CN)
            p.paragraph_format.left_indent = Cm(1.0)
            p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.3


# ================================================================
#                           报告主体
# ================================================================

def build():
    doc = Document()

    # 页面设置：A4，上下 2.54cm，左右 2.8cm（中文报告常用）
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.8)

    # ================== 封面 ==================
    for _ in range(6):
        doc.add_paragraph()

    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_after = Pt(12)
    r = title_p.add_run("大语言模型辅助下的纵向跟驰控制探索")
    set_run_font(r, size=28, bold=True, font_cn=FONT_HD)

    en_p = doc.add_paragraph()
    en_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    en_p.paragraph_format.space_after = Pt(12)
    r = en_p.add_run("LLM-Assisted Longitudinal Car-Following Control: An Exploratory Study")
    set_run_font(r, size=14, font_cn=FONT_CN)

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub_p.add_run("Applications of AI in Electrical and Electronic Engineering")
    set_run_font(r, size=16, font_cn=FONT_CN)

    sub2_p = doc.add_paragraph()
    sub2_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub2_p.add_run("EEEE3134 · Coursework Part II · Technical Report")
    set_run_font(r, size=12, font_cn=FONT_CN)

    for _ in range(3):
        doc.add_paragraph()

    info_rows = [
        ["姓名 Name", "Yueyi LI"],
        ["学号 Student ID", "20905083"],
        ["课程 Module", "Applications of AI in Electrical and Electronic Engineering (EEEE3134)"],
        ["日期 Date", "2026 年 11 月 12 日"],
    ]
    for label, val in info_rows:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p.add_run(f"{label}：")
        set_run_font(r1, size=14, bold=True, font_cn=FONT_HD)
        r2 = p.add_run(val)
        set_run_font(r2, size=14, font_cn=FONT_CN)

    doc.add_page_break()

    # ================== 目录页 ==================
    toc_title = doc.add_paragraph()
    toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    toc_title.paragraph_format.space_after = Pt(14)
    r = toc_title.add_run("目  录")
    set_run_font(r, size=22, bold=True, font_cn=FONT_HD)

    toc_items = [
        ("1  Introduction and Objectives", 0),
        ("2  Methodology and Implementation", 0),
        ("  2.1  仿真环境与常规基线", 1),
        ("  2.2  规划器、护栏与执行器", 1),
        ("  2.3  统一需求、准入控制与可复现性", 1),
        ("  2.4  评价指标与有效范围", 1),
        ("3  Experiments and Results", 0),
        ("  3.1  真实 Qwen：车辆 60 在 IDM 车流中的表现", 1),
        ("  3.2  真实模型时—空对比与入口事件", 1),
        ("  3.3  离线规则规划器对照", 1),
        ("  3.4  解读的边界", 1),
        ("4  Challenges and Problem-Solving", 0),
        ("  4.1  使对照独立于随机数消耗", 1),
        ("  4.2  修正虚假的效率优势", 1),
        ("  4.3  分离事件、样本与失效有效性", 1),
        ("  4.4  区分模型决策与执行器干预", 1),
        ("  4.5  可审计性与交付约束", 1),
        ("5  Personal Reflection and Conclusions", 0),
        ("6  References", 0),
        ("7  Appendix: Evidence Sources and Calculations", 0),
    ]
    add_toc_items(doc, toc_items)

    doc.add_page_break()

    # ================== 1 引言与目标 ==================
    add_heading(doc, "1  Introduction and Objectives", level=1)

    add_para(doc,
        "本课程作业探究大语言模型（LLM）如何在课程提供的车辆跟驰仿真器中参与纵向控制。纵向控制指沿道路方向的加减速决策，其唯一的控制输出是加速度：加速度积分得到速度，速度积分得到位置，因此这一个量同时决定了单车轨迹、车与前车的间距以及整条道路的通行效率。课程提供的仿真器是单车道、不允许超车的模型，横向运动（换道与转向）不在其建模范围内，因此本报告只评估纵向维度。传统基线为智能驾驶员模型（IDM），它依据车速、与前车距离及相对速度计算期望加速度[1,2]。",
        first_line_indent=0.74)

    add_para(doc,
        "这里使用“LLM”而非泛称“AI”，是因为实验中被调用的 qwen-flash 是一个语言模型，而且语言确实参与了控制回路：模型读取的是一段用自然语言描述当前场景的提示词，返回的是同时包含数值字段和一段文字解释的结构化文本。LLM 是 AI 的一个子集；本报告不声称覆盖 AI 的其他分支（如强化学习或监督学习控制器），也不把规则规划器的结果当作 AI 性能的证据。",
        first_line_indent=0.74)

    add_para(doc,
        "项目采用分层控制框架：一个规划器提出目标速度与期望时距，一个 IDM 执行器在每个仿真步把这些量转化为加速度。证据分两类：第一类是真实 Qwen 模型控制一辆车在 IDM 车流中的闭环表现；第二类是更大规模的离线对照，使用显式编程的规则规划器。后者用于检验架构和策略选择，其结果不是 LLM 性能的测量。",
        first_line_indent=0.74)

    # ---- 插入架构图 ----
    add_para(doc, "规划器与执行器的分层交互如图 1 所示。规划器观测车辆当前状态与道路信息，输出目标速度和时距；护栏负责校验数值合法性，执行器再把计划值平滑到物理加速度。",
        first_line_indent=0.74)
    add_figure(doc, FIG_DIR / "architecture.png", width_cm=14.5)
    add_caption(doc, "图 1  规划器—护栏—执行器分层控制架构", kind="figure")

    add_para(doc, "本技术调查围绕三个问题展开：", first_line_indent=0.74)
    for item in [
        "Qwen 能否在闭环仿真循环中给出可被使用的结构化计划——包括单次请求失败的情况？",
        "在相同外部需求下，其轨迹、效率、安全代理量与舒适性指标相较 IDM 基线如何？",
        "哪些实现与测量选择限制了对这些差异的解读？",
    ]:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.74)
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(f"•  {item}")
        set_run_font(run, size=12, font_cn=FONT_CN)

    add_para(doc,
        "本工作是探索性的：不假设 LLM 一定优于 IDM。仿真器提供了一个受控环境来检验集成与测量问题，而不是证明该方案已经可以用于实车。",
        first_line_indent=0.74)

    # ================== 2 方法与实现 ==================
    add_heading(doc, "2  Methodology and Implementation", level=1)

    add_heading(doc, "2.1  仿真环境与常规基线", level=2)
    add_para(doc,
        "课程代码实现了一条开放单车道道路，道路下游接近末端处设有临时低速区。车辆在上游边界满足准入条件时进入，在 5000 m 处离开。不超车设定下，每辆车对前车有永久的跟驰参照。所有活跃车辆的加速度在任何车辆移动之前计算一次，避免了状态更新顺序的依赖。表 1 列出了从代码中直接读取的主要实现参数，它们并非校准后的实测值。",
        first_line_indent=0.74)

    add_caption(doc, "表 1  实现参数（直接取自课程代码，非校准值）")
    add_table(doc,
        ["设置", "取值"],
        [["道路长度 / 车长", "5000 m；5 m"],
         ["时间步长 / 观测窗口", "0.1 s；1000 s"],
         ["常规期望速度 / 入场速度", "30 m/s；30 m/s"],
         ["低速区（公共活动窗口）", "位置 4500–4700 m；受影响车辆限速 2 m/s；E1/E2 活动 100–300 s，E3/E4 活动至仿真结束"],
         ["逐车受影响标记", "按（seed, vehicle_id）确定性哈希，概率 0.7；与公共活动时间相互独立，逐车锁定"],
         ["IDM 最小间距 / 基线时距", "2 m；1.0 s"],
         ["最大加速度 / 舒适减速度", "1.5 m/s²；2.0 m/s²"],
         ["数值减速度上限", "8.0 m/s²"],
         ["相对速度感知噪声", "0.5 m/s"]],
        col_widths=[7, 9])

    add_para(doc,
        "低速状态仅对受影响车辆在区域活动期间生效，且受入场时间条件约束。因此它是一个简化的扰动模型，不是物理车道收窄或全车一致限速。参数描述的是本次作业实现，未对真实道路校准。",
        first_line_indent=0.74)

    add_caption(doc, "表 2  四种需求与扰动场景")
    add_table(doc,
        ["实验", "到达间距", "低速期"],
        [["E1", "固定，1.7 s", "100–300 s"],
         ["E2", "1.0 s + 均值 0.5 s 的指数扰动", "100–300 s"],
         ["E3", "固定，1.7 s", "100–1000 s"],
         ["E4", "1.0 s + 均值 0.5 s 的指数扰动", "100–1000 s"]],
        col_widths=[2, 7, 7])

    add_para(doc,
        "所用 IDM 方程保持自由流与跟驰相互作用的经典形式[2]，其未限幅加速度为：",
        first_line_indent=0.74)
    add_para(doc,
        "a_IDM = a·[1 − (v/v₀)^δ − (s*/s)²]，  s* = s₀ + max(0, vT + vΔv/(2√(ab)))",
        size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc,
        "其中 s 为前后保险杠间距，Δv > 0 表示接近前车。课程代码在此基础上加入了相对速度感知噪声与减速度硬限幅；速度被截到零；位置用前后速度平均推进。底层 IDM 方程被保留，但本实现未声称是已发表模型的原样复刻或经形式化验证的安全控制器。",
        first_line_indent=0.74)

    add_heading(doc, "2.2  规划器、护栏与执行器", level=2)
    add_para(doc,
        "规划器观测车辆当前速度、当前道路限速、前车间距与相对速度、低速区活动状态以及到区域起止点的距离（单位均为米与米/秒）。一条有效的回复需包含 target_speed、time_headway 及简短解释字段。三种控制模式见表 3。",
        first_line_indent=0.74)

    add_caption(doc, "表 3  三种控制模式")
    add_table(doc,
        ["模式", "规划器", "本次调查中的角色"],
        [["IDM", "无", "常规基线"],
         ["Mock / Mock no-ant", "确定性手写策略", "离线架构与策略对照"],
         ["Qwen + IDM", "真实 qwen-flash 请求", "小规模真实模型闭环案例"]],
        col_widths=[3, 4, 9])

    add_para(doc,
        "Mock 规划器在接近活跃低速区 300 m 范围内用斜坡降低目标速度。两个 Mock 变体在对前方足够快接近时请求时距 1.3 s，否则 1.0 s；无预判变体移除了接近斜坡。由于实现中低速区活动状态并非所有车辆通用，最终交通状态随之不同，相同的时距规则在不同变体下产生不同的时距历史。",
        first_line_indent=0.74)
    add_para(doc,
        "模型回复按结构、数值可转换性与有限值检查。接受值再经道路条件限速（目标速度）、时距硬限幅 [0.8, 2.0] s（时距）两层护栏。无效回复保留上一次缓存计划，护栏以 fail-operational 方式工作。一个显式的零速目标会走停止分支，避免在 IDM 中出现除零。",
        first_line_indent=0.74)

    # ---- 代码片段（伪代码）----
    add_para(doc, "规划器调用与护栏校验的核心逻辑（伪代码，依据 vehicle_llm.py 中 validate_plan 与执行流程简化）：", first_line_indent=0.74)
    add_code_block(doc,
"""obs = build_observation(vehicle, snapshot)
raw = qwen_client.call(obs, prompt="v2-tuned-2026-11")
# 1) 跨边界校验：类型 / 必需字段 / float 可转 / NaN-inf 拒绝
target, headway, err = validate_plan(raw)
# 2) 校验失败 → fail-operational：保留最近一次有效计划
if err is not None:
    target, headway = last_valid_plan
else:
    # 3) 数值护栏：限速 + 时距硬限幅，然后才写入缓存
    target = min(target, vehicle.speed_limit)
    headway = clamp(headway, 0.8, 2.0)
    last_valid_plan = (target, headway)
# 4) 执行器用 IDM 把 (target, headway) 转成加速度
a = idm_acceleration(vehicle, target, headway)""")

    add_para(doc,
        "执行器按顺序做三件事：应用道路速度上限、以 0.5 s 时距每秒缓慢增加时距、在车辆越过低速区末端之后恢复陈旧的低速目标。请求模型值、护栏计划值和执行器实际值分别有独立的日志与计数器。另有一条每秒采样的执行轨迹补充每次调用的决策记录；这条轨迹无法复现所有 0.1 s 级护栏事件，所以总括计数器仍是必须的。",
        first_line_indent=0.74)
    add_para(doc,
        "Mock 调用的最小间隔 2 s、周期刷新 15 s、预警距离 300 m。真实 Qwen 用 10 s、60 s、500 m。低速区切换与快速接近前车同样会触发一次调用，仍受最小间隔约束。这些差异意味着不能把 Mock 和 Qwen 当作同一个被测量策略的可互换实现。",
        first_line_indent=0.74)

    add_heading(doc, "2.3  统一需求、准入控制与可复现性", level=2)
    add_para(doc,
        "到达时间表在仿真之前用独立随机流生成。每个实验与种子下，所有模式共享同一张表。低速区影响分配与感知噪声按种子、车辆 ID 与时间步锁定，不走共享随机序列。时间表哈希与源文件哈希写入每一条结果行。",
        first_line_indent=0.74)
    add_para(doc,
        "准入被挡下时，需求在路外 FIFO 队列中等待。准入检查同时看入口间距条件与基于入场速度和前车速度的停距条件；后者是本次项目新增，应用于所有控制器。它的简化假设与固定高入场速度在边界附近会显著影响制动行为；统一的实现本身并不能让这个效应独立于所选策略。",
        first_line_indent=0.74)
    add_para(doc,
        '离线网格覆盖 4 个实验 × 8 个种子 × 3 个控制器共 96 场。真实模型规模为 8 场 Qwen 案例 + 8 场配对 IDM 基线（种子 1 和 2），只有车辆 60 由模型控制。Qwen 温度 0.2、提示词版本 v2-tuned-2026-11。API 以同步方式调用——仿真时间在 Python 等待响应时暂停。这些案例测试的是理想化的"仿真零延迟规划器"，不是实时部署。',
        first_line_indent=0.74)

    add_heading(doc, "2.4  评价指标与有效范围", level=2)
    add_para(doc,
        "对车辆 i，设 A_i 为计划到达时刻、E_i 为实际入场、X_i 为离开。完成旅行时间 = X_i − E_i；完成系统时间 = X_i − A_i。两者均值都不包含未离场车辆。均同时报告入场数、完成数与等待数。",
        first_line_indent=0.74)
    add_para(doc,
        "为了在共同观测窗口 H 内覆盖全部计划到达，定义有限时域累计系统时间：",
        first_line_indent=0.74)
    add_para(doc,
        "C̄_H = (1/N)·Σ [min(X_i, H) − A_i]",
        size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc,
        "未完成或从未入场车辆的终点取为 H。这是窗口内累计时间的均值，不是完成旅程时间均值，也不是自由流延迟。它把路外等待算进去，但不揭示 H 之后剩余队列需要多久清空。比较时同一指标与同一窗口必须匹配。",
        first_line_indent=0.74)
    add_para(doc,
        "出口吞吐量是 1000 s 内出口数换算为辆/小时，它是有限窗口输出率，不是经过校准的通行能力估计。安全代理量包括最小间距与碰撞时间 TTC：对于有正间距的接近前车的跟驰对，TTC = 间距 / 接近速度；代码对非接近样本赋一个大哨兵值。最小 TTC 本身不构成碰撞概率或整体安全的结论。",
        first_line_indent=0.74)
    add_para(doc,
        "低 TTC 暴露量是低于 3 s 与 1.5 s 的车辆对 × 时间单位之和；归一化暴露量把合格 pair-样本数除以全部观察到的 pair-样本数。急制动定义为加速度 ≤ −6 m/s²，停止为速度 < 0.1 m/s；事件是满足条件的连续样本段。时长都是车队求和，不是单辆车的经过时间。事件在起点 < 500 m 时归为入口区事件。平均绝对 jerk 测的是加速度每秒变化量。",
        first_line_indent=0.74)
    add_para(doc,
        "代码在第一次检测到任何车身重叠或紧邻的顺序穿越时，把 pair 统计和舒适性样本截断到先前区间并标记该场。本次正式数据集里没有标记为失效的场次；即使标记为失效的效率指标也不应继续使用，flag 的存在本身不使失效数据具有物理意义。",
        first_line_indent=0.74)

    # ================== 3 实验、结果与讨论 ==================
    add_heading(doc, "3  Experiments and Results", level=1)

    add_heading(doc, "3.1  真实 Qwen：车辆 60 在 IDM 车流中的表现", level=2)
    add_para(doc,
        "八场真实案例共 189 条调用记录，其中 4 条无效返回，日志里未见重试。每场都配对一份同到达时间表的 IDM 基线。模型计划通过执行器耦合到交通流——这是仿真闭环案例，不是脱离车辆反馈直接回答问题。",
        first_line_indent=0.74)

    add_caption(doc, "表 4  车辆 60 的八场配对旅行时间（per_vehicle['60'].travel_time_s）")
    add_table(doc,
        ["案例", "调用数", "IDM 旅行\ns", "Qwen 旅行\ns", "差值\ns", "车队 min TTC\nIDM / Qwen / s"],
        [["E1 S1", "15", "299.4", "301.7", "+2.3", "2.32 / 2.11"],
         ["E1 S2", "15", "296.9", "299.4", "+2.5", "2.27 / 1.98"],
         ["E2 S1", "16", "313.4", "315.6", "+2.2", "1.47 / 0.76"],
         ["E2 S2", "15", "309.8", "312.4", "+2.6", "2.28 / 2.28"],
         ["E3 S1", "34", "520.0", "583.0", "+63.0", "1.99 / 1.91"],
         ["E3 S2", "29", "511.7", "516.3", "+4.6", "1.96 / 1.96"],
         ["E4 S1", "35", "530.0", "632.3", "+102.3", "1.42 / 1.05"],
         ["E4 S2", "30", "521.9", "552.3", "+30.4", "1.91 / 1.98"]],
        col_widths=[1.3, 1.3, 2.0, 2.0, 1.3, 2.8])

    add_para(doc,
        "八个 ego 差值全部为正。均值 +26.2 s、中位数 +3.6 s、最大 +102.3 s。同时报告这三个统计量避免让两个长瓶颈惩罚被中位数掩盖。图 2 直观展示了八场 ego 旅行时间的对比与差值柱状图。",
        first_line_indent=0.74)

    add_caption(doc, "表 4b  车辆 60 的八场安全代理量（ego 车辆 60 自身的最小 TTC、最小间距、急制动事件数）")
    add_table(doc,
        ["案例", "ego min TTC\ns", "ego min gap\nm", "ego 急制动\n事件", "ego min TTC\nIDM / Qwen / s"],
        [["E1 S1", "2.86", "3.66", "0", "2.75 / 2.86"],
         ["E1 S2", "2.90", "3.61", "0", "2.82 / 2.90"],
         ["E2 S1", "2.83", "3.75", "2", "2.79 / 2.83"],
         ["E2 S2", "2.89", "3.81", "1", "2.80 / 2.89"],
         ["E3 S1", "2.86", "3.60", "0", "2.75 / 2.86"],
         ["E3 S2", "2.92", "3.68", "0", "2.82 / 2.92"],
         ["E4 S1", "2.82", "3.76", "0", "2.81 / 2.82"],
         ["E4 S2", "2.86", "3.86", "0", "2.86 / 2.86"]],
        col_widths=[1.3, 2.0, 1.8, 1.6, 2.8])

    add_para(doc,
        "ego 自身的安全代理量在八场中与 IDM 基线接近，最小 TTC 均在 2.8 s 以上，未出现 ego 近碰撞。车队级 min TTC 的极值（如 E2 S1 的 0.76 s）来自入口队列中的其他 IDM 车辆，不直接涉及 ego 车辆 60，见 3.2 节定位。",
        first_line_indent=0.74)

    add_figure(doc, FIG_DIR / "qwen_real_ego.png", width_cm=15.0)
    add_caption(doc, "图 2  八场 ego 旅行时间与差值（Qwen − IDM）", kind="figure")

    add_para(doc,
        "没有标记出任何车身重叠或顺序穿越。Qwen 案例的车队 min TTC：E4 S1 为 1.05 s，E2 S1 为 0.76 s。离线回放把后者定位到 t = 996.9 s、x ≈ 54 m：IDM 控制的车辆 665 以约 6.0 m/s 的接近速度、4.6 m 的间距追上静止在入口队列中的车辆 664。这是一个低速入口队列汇入事件，不是 Qwen 控制的 ego 车辆附近的事件；车辆 60 在 E2 S1 中的前车对最小 TTC 约为 2.83 s。0.76 s 这个车队级数值依然是那场混合系统运行的观测，但不构成 ego 近碰撞的证据，也无法单独归因于 Qwen。",
        first_line_indent=0.74)

    add_para(doc,
        "所有被接受的请求都没有触碰硬护栏边界：记录的模型值截断计数与道路限速上限计数均为零。恢复护栏在五场案例里各激活一次；时距渐变每场 12–28 步。因此产生的轨迹属于 Qwen–执行器组合系统，不是无约束的模型输出。有一次请求时距 1.8 s，超出了提示词建议的 1.0–1.6 s 范围但仍在硬限幅 [0.8, 2.0] s 之内——提示词指令和执行器强制约束是两套机制。",
        first_line_indent=0.74)

    add_para(doc,
        "例如，E4 S1 第一次决策在仿真时刻 90.1 s，观测到车速 30 m/s、跟驰间距 42.3 m、低速区未激活，请求目标速度 30 m/s 和时距 1.4 s。这证明了模型能产出结构化计划，但附带的理由文字本身不构成其内部推理过程忠实性的证据；后续结果必须来自状态与执行记录。",
        first_line_indent=0.74)

    add_para(doc,
        "189 条调用记录合并看，总耗时约 153.8 s，平均每次尝试 0.81 s。185 次成功调用贡献约 113.8 s（每次 0.61 s）；4 次失败共贡献约 40.0 s，每次约 10 s，与配置的超时一致，但历史记录未保存原始异常类型。之前客户端摘要中的 113.7 s 只统计了成功调用，不能称为总阻塞时间。这些都是请求层面的耗时，不是费用，也不是整场实验的运行时间。",
        first_line_indent=0.74)

    add_heading(doc, "3.2  真实模型时—空对比与入口事件", level=2)
    add_para(doc,
        "离线回放从存储的 Qwen 决策与快照代码中重建轨迹，无需新的网络调用。显式高亮的 ego 消除了之前 stride 抽样面板里的歧义。E4 S1 之所以拿来展示是因为它有最大的 ego 旅行时间惩罚 +102.3 s，不代表所有案例都类似。",
        first_line_indent=0.74)

    add_figure(doc, SUP_DIR / "fig_ego_highlight_E4S1.png", width_cm=15.0)
    add_caption(doc, "图 3  E4 S1 轨迹与 ego 车辆 60 高亮（真实 Qwen vs IDM 对照）", kind="figure")

    add_para(doc,
        "展示的轨迹是基于存储决策的重建，不是新的随机模型运行。入口队列 0.76 s TTC 事件的局部观察（图 4）把入口边界的低速汇入与 Qwen ego 的轨迹分开，同时说明为什么一个极端车队统计值必须先定位到具体车辆对与位置再解读。这条证据识别了事件，但不证明事件的发生独立于上游控制效果的影响；也不直接从 TTC 值得出碰撞概率结论。",
        first_line_indent=0.74)

    add_figure(doc, SUP_DIR / "fig_ttc_event_E2S1.png", width_cm=15.0)
    add_caption(doc, "图 4  E2 S1 入口队列局部视图：0.76 s 车队 min TTC 事件（车辆 665 → 车辆 664）", kind="figure")

    add_heading(doc, "3.3  全车队规则规划器对照（规模化验证，非真实 LLM）", level=2)
    add_para(doc,
        "本节与 3.1、3.2 的真实 Qwen 实验是两套独立的实验，解读时不可混用。3.1 中只有车辆 60 由真实 Qwen 控制，其余车辆全部 IDM，因此入场数几乎不变；本节用确定性规则规划器（Mock）控制全部车辆，目的是在不消耗 API 调用的情况下观察「当所有车辆都采用提前减速策略时系统层会发生什么」。本节的准入阻塞、吞吐量下降等结论只适用于全车队策略，不能外推到单车 LLM 实验。",
        first_line_indent=0.74)
    add_para(doc,
        "下文数值是八个种子上的算术平均，因此小数车辆数代表的是平均，不是部分车辆。完整的逐场记录与额外指标在 evidence 目录下提供。",
        first_line_indent=0.74)

    add_caption(doc, "表 5  需求、准入与累计时间对照（Mock 全车队实验，八种子均值）")
    add_table(doc,
        ["实验", "模式", "入场", "出口", "仍在路外", "有限时域累计系统时间 / s"],
        [["E1", "IDM", "589.0", "466.4", "0.0", "226.7"],
         ["E1", "Mock", "589.0", "458.5", "0.0", "235.6"],
         ["E1", "Mock no-ant", "589.0", "464.4", "0.0", "229.2"],
         ["E2", "IDM", "663.5", "466.4", "6.9", "261.5"],
         ["E2", "Mock", "575.8", "456.3", "94.6", "269.3"],
         ["E2", "Mock no-ant", "575.8", "459.5", "94.6", "264.2"],
         ["E3", "IDM", "589.0", "126.1", "0.0", "422.2"],
         ["E3", "Mock", "589.0", "123.1", "0.0", "425.6"],
         ["E3", "Mock no-ant", "589.0", "126.1", "0.0", "422.2"],
         ["E4", "IDM", "664.6", "126.1", "7.8", "432.7"],
         ["E4", "Mock", "575.9", "123.1", "96.5", "435.6"],
         ["E4", "Mock no-ant", "575.9", "126.1", "96.5", "432.7"]],
        col_widths=[1.2, 2.2, 1.5, 1.5, 2.2, 3.6])

    add_para(doc,
        'Mock 的有限时域累计系统时间在 E1–E4 分别比 IDM 高 8.9、7.8、3.4、2.9 s，同一场下每个种子的对比都是正的。出口吞吐量大约低 1.7%、2.2%、2.4%、2.4%。无预判版本惩罚更小，但这不构成"预判普遍有害"的结论。',
        first_line_indent=0.74)

    add_para(doc,
        'E2 凸显了"比较范围"的重要性：车队完成旅程均值，IDM 为 305.8 s、Mock 为 266.1 s，但后者有约 94.6 辆计划表车辆从未入场，而 IDM 仅 6.9 辆。准入差异约 87.8 辆（不是 95）。只比较共同完成的车辆 ID，Mock 的场内行驶时间确实更短（约 −39.8 s），但从计划到达时刻算起到离场的系统时间更长（约 +11.3 s）；两者都从 per-vehicle 的 completed_*_by_id_s 记录、对两种模式都完成的 ID 集合计算得来。额外等待不是旅行效率的提升。共同 ID 分析仍然排除了未完成旅程；有限时域指标与完成数提供互补覆盖。需要再次强调：这一准入阻塞效应仅出现在全车队 Mock 实验中；3.1 节真实 Qwen 单 ego 实验的入场数与 IDM 基本一致，E4 的两个种子各少入场一辆，未出现全车队 Mock 中约九十辆规模的入口积压差异。',
        first_line_indent=0.74)

    # ---- E2 轨迹对照 ----
    add_para(doc,
        "图 5 给出了 E2 seed1 的完整轨迹对比。观察到的现象有两点：（1）Mock 预判版在接近低速区时更早减速；（2）入场数减少、路外等待增加。这两点在数据上同时存在，但尚未能把入场数减少单一归因于提前减速——预判、时距调整、缓存机制与入口停距条件各自的贡献没有被分离。因此本段只报告现象，因果分析见 4.2 节。",
        first_line_indent=0.74)

    add_figure(doc, FIG_DIR / "exp2_idm_seed1_readable.png", width_cm=14.8)
    add_caption(doc, "图 5  E2 seed1 IDM 轨迹（全车队 Mock 实验的无预判对照组）", kind="figure")

    add_figure(doc, FIG_DIR / "exp2_llm_mock_seed1_readable.png", width_cm=14.8)
    add_caption(doc, "图 6  E2 seed1 Mock 预判版轨迹（全车队规则规划器，非真实 LLM；同种子同时间表，与图 5 对照）", kind="figure")

    add_para(doc,
        "为便于观察轨迹如何随时间演化，本实验另附一段动态补充材料：上排为道路俯视视图（每辆车以速度着色），下排为时空速度场随时间逐步显现，左右分别为 IDM 与全车队 Mock，同一随机种子与同一到达时间表。动态文件为 figures/animation_E2_idm_vs_mock.gif，作为补充材料随代码仓库提供，不在本报告中静态呈现。",
        first_line_indent=0.74)

    add_caption(doc, "表 6  安全与舒适性指标（Mock 全车队实验，八种子均值；急制动定义为加速度 ≤ −6 m/s²）")
    add_table(doc,
        ["实验", "模式", "run-min TTC / s", "TTC <3 s 暴露量 / pair·s", "急制动事件", "急制动总时长 / s", "停止总时长 / s"],
        [["E1", "IDM", "2.15", "292.7", "5.0", "6.5", "19.6"],
         ["E1", "Mock", "2.58", "10.2", "2.8", "0.3", "251.6"],
         ["E1", "Mock no-ant", "2.25", "39.4", "4.8", "6.4", "0.0"],
         ["E2", "IDM", "1.79", "1069.8", "625.9", "169.8", "7660.5"],
         ["E2", "Mock", "2.67", "7.5", "637.8", "593.5", "210.2"],
         ["E2", "Mock no-ant", "2.25", "41.3", "639.9", "599.6", "0.0"],
         ["E3", "IDM", "1.96", "4563.5", "5.0", "6.5", "18648.0"],
         ["E3", "Mock", "2.30", "98.5", "2.8", "0.3", "18753.9"],
         ["E3", "Mock no-ant", "2.24", "127.0", "4.8", "6.4", "16475.9"],
         ["E4", "IDM", "1.88", "5454.4", "632.8", "173.7", "31612.0"],
         ["E4", "Mock", "2.39", "63.2", "635.9", "589.4", "16118.5"],
         ["E4", "Mock no-ant", "2.25", "99.7", "638.1", "595.6", "14517.1"]],
        col_widths=[1.2, 2.2, 2.0, 3.2, 1.6, 2.4, 2.6])

    add_para(doc,
        "Mock 的均值 run-min TTC 更高、低 TTC 暴露量显著更少，但它在 E2、E4 的急制动总时长约为 IDM 的 3.5 倍和 3.4 倍，事件数接近。E3 停止时长反而略高而非更低。E1 停止情况也更差。这些指标不支持整体安全或舒适性有所提升，且它们仍是规则规划器而非真实 LLM 的结果。归一化之后，随机场景下低 TTC 的方向保持一致：低于 3 s 的 pair-样本比例，E2 中 IDM 约 0.00622 vs Mock 0.00006，E4 中 IDM 约 0.01899 vs Mock 0.00026。这些比例和绝对总量都不能解释为真实世界的碰撞率估计。",
        first_line_indent=0.74)

    # ---- E4 Qwen vs IDM ----
    add_para(doc,
        "图 7 与图 8 展示了 E4 seed1 下真实 Qwen 控制的车辆 60 与 IDM 基线的轨迹差异。两者来自两次独立的仿真运行（同种子同到达表），并非同一道路上的两辆车竞争，也没有发生超车。从轨迹可见：Qwen 控制的车辆 60 在接近低速区时减速时机更早，在低速区内跟驰时位置落后于 IDM 基线中的同编号车辆，后者更早到达 5000 m 出口。轨迹显示该车辆 60 的行程延长，但由于没有分阶段耗时与速度积分分析，尚不能确定 +102.3 s 差值的全部来源。",
        first_line_indent=0.74)

    add_figure(doc, FIG_DIR / "qwen_exp4_seed1_readable.png", width_cm=14.8)
    add_caption(doc, "图 7  E4 seed1 真实 Qwen 完整轨迹", kind="figure")

    add_figure(doc, FIG_DIR / "qwen_idm_exp4_seed1_readable.png", width_cm=14.8)
    add_caption(doc, "图 8  E4 seed1 IDM 基线完整轨迹（与图 7 同种子同时间表，车辆 60 独立运行 IDM）", kind="figure")

    add_heading(doc, "3.4  解读的边界", level=2)
    add_para(doc,
        "这些结果依赖于一条道路、当前配置的流入与扰动、课程原版 IDM 参数以及未校准的噪声实现。真实模型样本只用了一个模型、一个提示词、一个温度、每个场景两个种子，没有在同一条件下重复采样。不同提示词、触发时机、初始状态或通信延迟都可能改变结果。固定入场速度与边界门在随机到达场景下对制动行为影响很大。宏观层面的效果无法只归因于规划器的文字理由或某一个控制参数。",
        first_line_indent=0.74)
    add_para(doc,
        "仿真器没有建模 HTTP 响应等待期间的物理延迟、异步计划投递、转向或配置噪声以外的传感器不确定性。缓存和有界的执行器是有用的机制，但不是稳定性或安全性的形式化证明。这足以检验本次作业的集成问题，但不足以支撑部署到自动驾驶车辆的主张。",
        first_line_indent=0.74)

    # ================== 4 挑战、排查与问题求解 ==================
    add_heading(doc, "4  Challenges and Problem-Solving", level=1)

    sections = [
        ("4.1  使对照独立于随机数消耗",
         "最初实现中，交通生成和控制相关噪声共享同一随机序列。这样一来，策略不同会改变后续的需求或扰动，即使种子相同。修订后的代码让需求独立生成，其他噪声按车辆 ID 与时间步锁定。每对策略的时间表哈希相等，验证了共享的计划需求；但这并不意味着入场数或车辆状态相等。逐车数据让车辆 60 的对照可以直接做，不必用车队均值当它的基线。"),
        ("4.2  修正虚假的效率优势",
         "早期草稿报告了旅行时间比较下 9.5% 的改进。复审指出，旧指标混入了不同的入场数，且包含了未完成旅程。这些数字被移出正式结果表。修订后把已完成旅程、未完成旅程和路外等待拆开，并引入了有限时域累计系统时间。同时明确区分组均值之差和同车配对之差这两种口径。入口诊断为一个被提出的解释提供了反例：E2 S1 里，到 100 s 时需求 72 辆，IDM 已入场 69，两个 Mock 变体都是 61；此时带头车辆只有约 3000 m，入口差异在任何车辆到达 4500 m 瓶颈之前就已经存在，因此可以排除瓶颈回流是这个早期窗口差异的原因。Mock 下挡住路的车辆速度更低、请求时距更长，但每个机制的因果贡献尚未被隔离。"),
        ("4.3  分离事件、样本与失效有效性",
         "把每一个 0.1 s 制动样本都算成一个事件，会高估事件频率。实现现在报告连续事件段并汇总时长。类似地，只在某个时间点跳过一个重叠 pair 并不能让后续统计有效。我们写了一个合成回归案例：换序前 25 m、换序后 1 m，正确截断返回的最小间距是 25 m，只有换序前的两个 pair-样本，且排除了之后的制动与 jerk。原始复审快照里 15 项针对性检查全部通过，覆盖需求、计划校验、停止、恢复、计账、有效性与执行计数器。后续补充的 source_snapshot_fixed/ 新增了离线预算中止回归，并把预算异常与一般规划器失败区分开来，预算到达时保留已完成结果。原始实验没有任何案例触到 250 次调用上限。"),
        ("4.4  区分模型决策与执行器干预",
         '早期的错误 counter 把任何低于道路限速的目标都算作执行器覆盖。这样正常的低速规划被错误计入"干预"，而过期计划的恢复被漏掉。当前计数把模型值截断、道路限速上限、恢复激活和时距渐变步数分开。真实案例里模型值截断和道路限速上限都没发生，但恢复护栏激活了五次。这个区分是必要的——它让我们能把行为归因到组合系统，同时不夸大模型的自主性。'),
        ("4.5  可审计性与交付约束",
         "结果行记录 sim_version 3.0-fair-sim、metrics_version 3.0-metrics-v4 和十个源文件的哈希。复审数据含 96 条离线行和 16 条真实研究行。对 E4 S1 的 35 条 Qwen 决策做了离线回放，不调用新的网络请求即可复现所有日志观察值与主要报告指标。这类回放校验的是代码、计划与结果之间的一致性，不能独立确认计费账单或远端服务本身。交付包里保留了原始实验文件，包括早期的延迟摘要。另一份派生审计记录了修正后的延迟。原始证据不被覆盖。11 月 10 日补充内容提供了修复后的可执行代码、高亮 ego 的对照图和入口事件局部图。独立离线检查把回放观察值、采样执行轨迹与原始日志做了比对；结果存于 supplement_20261110/ 目录。原始实验源哈希仍对应原始快照；修复代码单独标识。本报告范围不需要新的模型调用、批量付费实验或全车队 LLM 实验。"),
    ]
    for h, body in sections:
        add_heading(doc, h, level=2)
        add_para(doc, body, first_line_indent=0.74)

    # ================== 5 个人反思与结论 ==================
    add_heading(doc, "5  Personal Reflection and Conclusions", level=1)

    add_para(doc,
        "这次课程作业让我从实践层面理解了一个关键问题：把大语言模型集成到现有的车辆控制框架中，最大的挑战不是让模型给出一个看起来合理的速度建议，而是如何把它放进一个闭环系统里，让模型的输出能被可靠地执行、能被审计、并且在出错时系统还能继续跑。",
        first_line_indent=0.74)
    add_para(doc,
        "分层架构（规划器—护栏—执行器）是这次项目里最重要的设计决定。一开始我试过直接让模型输出加速度，但这个方案在架构上不可控：一次异常的加速度值会直接作用于车辆，中间没有任何缓冲。在早期直接模式的测试中确实出现过非有限值或越界加速度（见 vehicle_llm_direct.py 的 isfinite 检查）。加入护栏之后，模型只负责提议目标速度和时距，执行器用 IDM 把它们变成具体的加速度。这样一来，即使模型偶尔给出奇怪的值，护栏也能把它限制在合理范围内；即使模型请求失败，最近一次的缓存计划也能保证仿真不崩。这种 fail-operational 的思路是我以前没有接触过的——在纯算法课里，模型输出总是被默认为完美，但在控制系统里，容错才是第一要求。",
        first_line_indent=0.74)
    add_para(doc,
        "结果本身也出乎意料：在我测试的 8 场真实 Qwen 案例里，车辆 60 的旅行时间全部比 IDM 基线更长。这不是说 Qwen 一定比 IDM 差，而是暴露了几个重要的边界。首先，同步 API 调用让仿真在等待响应时暂停——这是一个理想化假设，真实部署中不存在。其次，Mock 预判版在 E2、E4 里甚至导致了大量车辆无法入场，说明一个策略在局部看起来合理（早减速），在系统层面可能产生完全相反的效果。第三，车队级的 TTC 极值不一定发生在 LLM 控制的车辆附近，解读之前必须先定位具体是哪一对车。",
        first_line_indent=0.74)
    add_para(doc,
        "另一个重要教训是关于测量的。早期草稿里报告了一个 9.5% 的效率改进，但后来发现那组数据混入了不同的入场数，而且没有排除未完成旅程。修正之后，那些看起来亮眼的数字消失了。这个经历让我意识到，在对比两种控制策略时，'比较什么'和'怎么比较'比'谁更好'这个结论本身更重要。有限时域累计系统时间这个指标是这次项目里最有价值的东西之一——它把路外等待也算进去了，让系统层面的代价不再被忽略。",
        first_line_indent=0.74)
    add_para(doc,
        "如果要继续改进这个项目，我认为有三个方向。第一是真正引入通信延迟，把同步调用改成异步，让模型的决策在物理时间上与执行器解耦。第二是让模型控制多辆车，而不只是一辆 ego——这样才能观察车队层面的涌现行为。第三是替换掉手动写的 Mock 规划器，让规则本身也由 LLM 来生成，然后对比不同模型（或者不同提示词）生成的规则之间有什么差异。这些方向都超出了本次作业的范围，但它们才是 LLM 辅助驾驶控制真正有意思的问题。",
        first_line_indent=0.74)
    add_para(doc,
        "最后回到这门课本身。课程大纲一开始介绍的是传统车辆控制模型（IDM、Gipps 等），然后逐步引入 AI 的方法。这次作业把两条线接起来了——我用课上学的 IDM 做执行器，用 LLM 做规划器，在仿真器里观察它们如何交互。这个过程让我对'控制'这个词有了新的理解：它不只是公式和参数，更是一整套关于测量、容错、审计和边界的工程实践。",
        first_line_indent=0.74)

    # ================== 6 参考文献 ==================
    add_heading(doc, "6  References", level=1)
    refs = [
        "[1] Treiber, M., Hennecke, A. and Helbing, D. (2000). Congested traffic states in empirical observations and microscopic simulations. Physical Review E, 62, 1805–1824.",
        "[2] Treiber's traffic-simulation site. The Intelligent-Driver Model and its Variants. https://traffic-simulation.de/info/info_IDM.html. Accessed 9 November 2026.",
        "[3] Coursework.pdf. EEEE3134 课程作业说明。用于确定报告范围与评估哲学。",
        "[4] Course GitHub repository（课程提供的仿真器与作业框架代码）。",
    ]
    for r in refs:
        add_para(doc, r, size=11, space_after=3, first_line_indent=0.74)

    # ================== 7 附录 ==================
    add_heading(doc, "7  Appendix: Evidence Sources and Calculations", level=1)
    add_para(doc,
        "图表与资料索引把每张图与每个表对应到其来源文件。evidence/ 目录下是结果文件与 Qwen 日志（均为本地拷贝，不是新的 API 运行）。evidence/derived_audit.json 记录了延迟重算与若干比较。evidence/technical_summary.csv 提供未四舍五入的八种子派生摘要供表格编辑。报告中所有四舍五入差异均为展示选择。",
        first_line_indent=0.74)
    add_para(doc,
        "必要时，均值与标准差应在八个种子级统计量上计算，不把数百万个时间样本当作独立运行。主表强调方向与计数，完整证据保留种子级变化。真实模型每个场景只有两个种子，不做显著性声明。同车完成车辆的对比以两种模式都完成的 ID 集合为条件。",
        first_line_indent=0.74)

    doc.save(OUT)
    print("written:", OUT, "size:", OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    build()
