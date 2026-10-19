"""生成 TUIA 工作簿：周衍图（The Universal Isotope Atlas）。

输出：dist/TUIA_同位素可及性全景扩展.xlsx
"""

from __future__ import annotations

import datetime as dt
import pathlib
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.drawing.image import Image as XLImage
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from elements import GRID  # noqa: E402
from scoring import GRADES, METHOD_SCORE, TIER_LABEL, WEIGHTS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIGS = ROOT / "docs" / "figs"
DIST = ROOT / "dist"
OUT = DIST / "TUIA_同位素可及性全景扩展.xlsx"

NAVY = "0F2740"
NAVY2 = "1B3B5A"
GOLD = "C9A227"
CREAM = "FAF7F0"
SAND = "EFE9DC"
INK = "1B1B1B"
MUTED = "5A5A5A"

GRADE_FILL = {
    "S": "1B5E20", "A": "2E7D32", "B": "7CB342",
    "C": "F2C14E", "D": "E58E7B", "E": "9B2226",
}
GRADE_TEXT = {"S": "FFFFFF", "A": "FFFFFF", "B": "1B1B1B",
              "C": "1B1B1B", "D": "FFFFFF", "E": "FFFFFF"}

THIN = Side(style="thin", color="D9D3C6")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


# ------------------------------------------------------------------ 样式工具

def title_block(ws, title: str, subtitle: str, width_cols: int = 12) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width_cols)
    c = ws.cell(row=1, column=1, value=title)
    c.font = Font(name="微软雅黑", size=20, bold=True, color=NAVY)
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 34

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width_cols)
    c = ws.cell(row=2, column=2 - 1, value=subtitle)
    c.font = Font(name="微软雅黑", size=10, color=MUTED)
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[2].height = 20


def header_row(ws, row: int, headers: list[str], widths: list[float],
               height: int = 34) -> None:
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=row, column=i, value=h)
        cell.font = Font(name="微软雅黑", size=9.5, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
        cell.border = BOX
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = height


def write_table(ws, df: pd.DataFrame, start_row: int, widths: list[float],
                header: list[str] | None = None, band: bool = True,
                wrap_cols: list[int] | None = None, score_cols: list[int] | None = None,
                num_format: dict[int, str] | None = None) -> int:
    headers = header or list(df.columns)
    header_row(ws, start_row, headers, widths)
    wrap_cols = wrap_cols or []
    num_format = num_format or {}
    for r_i, rec in enumerate(df.itertuples(index=False), start=start_row + 1):
        for c_i, val in enumerate(rec, start=1):
            if pd.isna(val):
                val = None
            cell = ws.cell(row=r_i, column=c_i, value=val)
            cell.font = Font(name="微软雅黑", size=9, color=INK)
            cell.border = BOX
            cell.alignment = Alignment(
                vertical="center",
                horizontal="left" if c_i in wrap_cols else "center",
                wrap_text=c_i in wrap_cols,
            )
            if band and (r_i - start_row) % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=CREAM)
            if c_i in num_format:
                cell.number_format = num_format[c_i]
    if score_cols:
        last = start_row + len(df)
        for c_i in score_cols:
            col = get_column_letter(c_i)
            ws.conditional_formatting.add(
                f"{col}{start_row + 1}:{col}{last}",
                ColorScaleRule(start_type="num", start_value=0, start_color="F8696B",
                               mid_type="num", mid_value=55, mid_color="FFEB84",
                               end_type="num", end_value=100, end_color="63BE7B"),
            )
    return start_row + len(df)


def note_row(ws, row: int, text: str, ncols: int, size: float = 9,
             color: str = MUTED) -> None:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name="微软雅黑", size=size, color=color)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[row].height = max(18, 15 * (1 + len(text) // 90))


def section(ws, row: int, text: str, ncols: int) -> None:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name="微软雅黑", size=12, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=NAVY2)
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[row].height = 26


# ------------------------------------------------------------------ 各工作表

def sheet_cover(wb: Workbook, nuclides: pd.DataFrame, focus: pd.DataFrame,
                elems: pd.DataFrame) -> None:
    ws = wb.active
    ws.title = "00_封面"
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDEFGH", [3, 26, 26, 26, 26, 26, 26, 3]):
        ws.column_dimensions[col].width = w

    ws.merge_cells("B2:G3")
    c = ws["B2"]
    c.value = "TUIA"
    c.font = Font(name="Georgia", size=54, bold=True, color=NAVY)
    c.alignment = Alignment(vertical="center")

    ws.merge_cells("B4:G4")
    c = ws["B4"]
    c.value = "The Universal Isotope Atlas"
    c.font = Font(name="Georgia", size=22, italic=True, color=GOLD)

    ws.merge_cells("B5:G5")
    c = ws["B5"]
    c.value = "周衍图：同位素可及性视角下的周期表全景扩展"
    c.font = Font(name="微软雅黑", size=15, bold=True, color=NAVY2)

    ws.merge_cells("B7:G9")
    c = ws["B7"]
    c.value = (
        "元素周期表回答「有哪些元素」，IPTEI 回答「它们有哪些同位素」。\n"
        "本图回答第三个问题：这些同位素，你能不能拿到？拿多少？多贵？受什么限制？\n\n"
        "灵感起点是氮-空位（NV）金刚石色心：它要求 12C 丰度达到 99.9% 以上，因为 13C 的核自旋\n"
        "会把量子相干时间压到微秒级。一个化学上「最普通」的元素，在同位素维度上可以贵四个数量级。"
    )
    c.font = Font(name="微软雅黑", size=11, color=INK)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[7].height = 30
    ws.row_dimensions[8].height = 30
    ws.row_dimensions[9].height = 30

    stats = [
        ("核素总数", f"{len(nuclides):,}"),
        ("元素覆盖", f"{elems.shape[0]}"),
        ("策展核素", f"{len(focus)}"),
        ("可及性维度", "7"),
    ]
    row = 11
    for i, (k, v) in enumerate(stats):
        col = 2 + i * 1 if i < 4 else 2
        cell = ws.cell(row=row, column=col + i * 0, value=None)
    labels = ["核素总数", "元素覆盖", "策展核素", "可及性维度"]
    values = [f"{len(nuclides):,}", str(elems.shape[0]), f"{len(focus)}", "7"]
    for i, (lab, val) in enumerate(zip(labels, values)):
        r = row + (i // 2) * 3
        cc = 2 + (i % 2) * 3
        ws.merge_cells(start_row=r, start_column=cc, end_row=r, end_column=cc + 1)
        cell = ws.cell(row=r, column=cc, value=lab)
        cell.font = Font(name="微软雅黑", size=9, color=MUTED)
        cell.alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=r + 1, start_column=cc, end_row=r + 1, end_column=cc + 1)
        cell = ws.cell(row=r + 1, column=cc, value=val)
        cell.font = Font(name="Georgia", size=24, bold=True, color=GOLD)
        cell.alignment = Alignment(horizontal="center")
        ws.row_dimensions[r + 1].height = 32

    ws.merge_cells("B18:G18")
    c = ws["B18"]
    c.value = (f"版本 0.1 · 构建于 {dt.date.today().isoformat()} · "
               "数据源：NIST Atomic Weights and Isotopes（核素质量/丰度）+ "
               "Wikipedia Isotopes of each element（半衰期/衰变/自旋）+ 人工策展（成本/量级/管制）")
    c.font = Font(name="微软雅黑", size=8.5, color=MUTED)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[18].height = 28


def sheet_readme(wb: Workbook) -> None:
    ws = wb.create_sheet("01_导读")
    title_block(ws, "导读：怎么用这张图", "五分钟看懂结构，十分钟看懂口径", 6)
    for col, w in zip("ABCDEF", [4, 22, 60, 34, 18, 3]):
        ws.column_dimensions[col].width = w

    section(ws, 4, "一、工作簿结构", 5)
    rows = [
        ("02_周衍图", "矢量图的静态大图：IPTEI 式方框 + 同位素饼图 + 分离国 + 可及性徽标", "看整体格局"),
        ("02b_可及性热力格", "与周期表同构的格子版：元素 / 评分 / 分离产业国，可筛选", "查细节"),
        ("03_元素总表", "118 元素的同位素统计 + 最佳可及核素 + 可及性评分与跨度", "横向比较元素"),
        ("04_IPTEI扩展", "IPTEI 的每元素同位素视图，加上「可及性」一列", "对照官方图表"),
        ("05_同位素全景", f"全部核素逐条列出，含推定可及性评分", "查单个核素"),
        ("06_可及性目录", "人工策展的焦点核素：用途、路线、成本、量级、一句话要点", "读细节"),
        ("07_评分模型", "七个子维度的定义、权重、映射表与合成公式", "改模型前必读"),
        ("08_生产路线图鉴", "各条获取路线的工艺门槛、周期、TRL 与代表设施", "理解为什么贵"),
        ("09_再生闭环", "哪些核素衰变/消耗后能「回炉」再生，哪些不能", "本图的核心洞见"),
        ("10_场景推演", "NV 色心、硅量子、靶向α治疗、聚变、双β 等场景的可及性判读", "把图用起来"),
        ("11_数据源", "逐字段的出处与置信度", "复核"),
        ("12_使用与局限", "口径、易错点、如何扩展到数千个核素", "别踩坑"),
        ("13_供应格局", "哪些国家有这条分离产线、置信度多少、口径是什么", "看供应链"),
        ("14_同质异能态", "2050 条激发态：99mTc、229mTh、178m2Hf 都在这里", "查 m 态"),
        ("15_NUBASE对账", "与 IAEA/AMDC 评估表逐条比半衰期，标出分歧", "验数据"),
        ("16_衰变链与发生器", "由衰变分支算出的子体、长链，与可作发生器的母体-子体对", "找发生器"),
    ]
    header_row(ws, 5, ["#", "工作表", "内容", "什么时候打开"], [4, 22, 60, 34])
    for i, (a, b, c) in enumerate(rows, start=1):
        for j, v in enumerate((i, a, b, c), start=1):
            cell = ws.cell(row=5 + i, column=j, value=v)
            cell.font = Font(name="微软雅黑", size=9.5, color=INK)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=(j == 3))
            if i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=CREAM)

    last_row = 5 + len(rows)
    section(ws, last_row + 2, "二、三个必须先说清的口径", 5)
    notes = [
        "① 「可及性」≠「重要性」。它是采购难度，不是科学价值。半衰期只有几小时的核素往往评分很低，"
        "但它们恰恰是最有价值的诊疗核素——低分说明的是「你必须就在它旁边生产」，不是「它没用」。",
        "② 成本与量级是量级判断，不是报价。T0–T4 是数量级分层，用于横向比较；真实价格随反应堆档期、"
        "合同规模、同位素纯度剧烈波动，可能相差 3–5 倍。",
        "③ 「推定」与「策展」要分清。焦点目录里的 227 条是人工逐条读过路线与量级后写的；"
        "其余三千余条的可及性评分是由丰度与元素级工艺推出的估计值，只适合看趋势。",
    ]
    r = last_row + 3
    for n in notes:
        note_row(ws, r, n, 4, size=9.5)
        ws.row_dimensions[r].height = 44
        r += 1

    section(ws, r + 1, "三、等级图例", 5)
    header_row(ws, r + 2, ["等级", "分数区间", "含义", "典型例子"],
               [4, 22, 60, 34])
    examples = {
        "S": "1H、16O、27Al、23Na",
        "A": "9Be（76.7）、56Fe（69.2）、11B（70.3）",
        "B": "12C（55.9）、28Si（54.8）、18O（63.1）",
        "C": "235U（43.0）、13C（49.7）、76Ge（42.3）",
        "D": "3H（33.8）、229Th（21.8）、238Pu（26.3）",
        "E": "225Ac（12.1）、252Cf（19.0）、超重元素",
    }
    rng = {"S": "80–100", "A": "65–80", "B": "50–65", "C": "35–50",
           "D": "20–35", "E": "0–20"}
    for i, (lo, g, label) in enumerate(GRADES, start=1):
        vals = (g, rng[g], f"{label} —— 需要什么条件才能拿到", examples[g])
        for j, v in enumerate(vals, start=1):
            cell = ws.cell(row=r + 2 + i, column=j, value=v)
            cell.font = Font(name="微软雅黑", size=9.5, bold=(j == 1),
                             color=GRADE_TEXT[g] if j == 1 else INK)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=(j == 4))
            if j == 1:
                cell.fill = PatternFill("solid", fgColor=GRADE_FILL[g])
            elif i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=CREAM)
        ws.row_dimensions[r + 2 + i].height = 26


def sheet_periodic_image(wb: Workbook) -> None:
    """02_周衍图：矢量图的静态大图（一页看全）。"""
    ws = wb.create_sheet("02_周衍图")
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 60
    ws.column_dimensions["A"].width = 3

    ws["A1"] = "周衍图 · 同位素可及性全景扩展"
    ws["A1"].font = Font(name="微软雅黑", size=16, bold=True, color=NAVY)
    ws["A2"] = ("本页是矢量图的静态大图（矢量版：docs/figs/tuia-periodic.svg）。"
                "徽标实心 = 人工策展（62 个元素），空心 = 模型推定（56 个）。"
                "要筛选、排序、看单条核素，请用 02b、03、05、06 页。")
    ws["A2"].font = Font(name="微软雅黑", size=9, color=MUTED)
    ws.row_dimensions[1].height = 24

    png = FIGS / "tuia-periodic.png"
    if png.exists():
        img = XLImage(str(png))
        w0, h0 = img.width, img.height
        img.width = 1250                       # 显示宽度（像素 @96dpi ≈ 33cm）
        img.height = int(1250 * h0 / w0)       # 按原始比例缩放，避免拉伸
        ws.add_image(img, "A4")
    else:
        ws["A4"] = "缺少 docs/figs/tuia-periodic.png，请先运行 tools/render_png.py"
        ws["A4"].font = Font(name="微软雅黑", size=10, color="9B2226")


def sheet_periodic(wb: Workbook, elems: pd.DataFrame) -> None:
    ws = wb.create_sheet("02b_可及性热力格")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 7
    for i in range(2, 20):
        ws.column_dimensions[get_column_letter(i)].width = 8.6

    ws.merge_cells("B1:S1")
    c = ws["B1"]
    c.value = "周衍图 · 同位素可及性全景"
    c.font = Font(name="Georgia", size=22, bold=True, color=NAVY)
    ws.row_dimensions[1].height = 32

    ws.merge_cells("B2:S2")
    c = ws["B2"]
    c.value = ("每格 = 元素 / 原子序数 / 该元素「最佳可及同位素」的可及性评分。"
               "颜色越深绿越易得，越红越难。注意：这一格只代表该元素最容易拿到的那条路，"
               "同元素内部的跨度可能高达 70 分（见 03_元素总表「可及性跨度」）。")
    c.font = Font(name="微软雅黑", size=9, color=MUTED)
    c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[2].height = 30

    for g in range(1, 19):
        cell = ws.cell(row=3, column=1 + g, value=g)
        cell.font = Font(name="微软雅黑", size=7.5, color=MUTED)
        cell.alignment = Alignment(horizontal="center")

    by_z = elems.set_index("Z")
    for z, (col, row) in GRID.items():
        rec = by_z.loc[z]
        r = 3 + row
        cell = ws.cell(row=r, column=col + 1)
        g = rec["元素可及性等级"]
        try:
            cell.value = CellRichText([
                TextBlock(InlineFont(rFont="Calibri", sz=7, color=GRADE_TEXT[g]),
                          f"{z}\n"),
                TextBlock(InlineFont(rFont="Calibri", sz=12, b=1, color=GRADE_TEXT[g]),
                          f"{rec['元素']}\n"),
                TextBlock(InlineFont(rFont="Calibri", sz=8.5, color=GRADE_TEXT[g]),
                          f"{rec['元素可及性评分']:.0f}"),
            ])
        except Exception:  # noqa: BLE001
            cell.value = f"{z}\n{rec['元素']}\n{rec['元素可及性评分']:.0f}"
        cell.fill = PatternFill("solid", fgColor=GRADE_FILL[g])
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(left=Side(style="thin", color="FFFFFF"),
                             right=Side(style="thin", color="FFFFFF"),
                             top=Side(style="thin", color="FFFFFF"),
                             bottom=Side(style="thin", color="FFFFFF"))
        cell.font = Font(name="Calibri", size=9, color=GRADE_TEXT[g])

    for r in range(4, 14):
        ws.row_dimensions[r].height = 42
    ws.row_dimensions[11].height = 10

    for i, lab in enumerate(["1", "2", "3", "4", "5", "6", "7"]):
        cell = ws.cell(row=4 + i, column=1, value=lab)
        cell.font = Font(name="微软雅黑", size=8, color=MUTED)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for i, lab in enumerate(["镧系", "锕系"]):
        cell = ws.cell(row=12 + i, column=1, value=lab)
        cell.font = Font(name="微软雅黑", size=7.5, color=MUTED)
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 图例
    lr = 16
    ws.cell(row=lr, column=2, value="图例").font = Font(name="微软雅黑", size=9, bold=True,
                                                        color=NAVY)
    for i, (lo, g, label) in enumerate(GRADES):
        cell = ws.cell(row=lr + 1, column=2 + i, value=f"{g} {label}")
        cell.fill = PatternFill("solid", fgColor=GRADE_FILL[g])
        cell.font = Font(name="微软雅黑", size=8, color=GRADE_TEXT[g])
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(2 + i)].width = 12
    ws.row_dimensions[lr + 1].height = 20

    note_row(ws, lr + 3,
             "读法示例：C（碳）拿到 55 分、等级 B —— 因为 12C 天然占 98.93%，但要把 13C 压到 1‰ 以下"
             "需要低温蒸馏 CO 或离心，成本跳到 T3；而 N（氮）只有 51 分，是因为 N2 的 15N 富集级联更长。"
             "反过来 H（氢）拿到 80 分：D 可以靠化学交换吨级生产，但 T（氚）完全是另一条路——"
             "见 09_再生闭环。", 19)


def sheet_elements(wb: Workbook, elems: pd.DataFrame) -> None:
    ws = wb.create_sheet("03_元素总表")
    title_block(ws, "03 · 元素总表", "118 元素 × 同位素结构 × 最佳可及性", 15)
    cols = ["Z", "元素", "中文", "英文", "类别", "已知核素数", "稳定同位素数",
            "天然丰度范围%", "最长寿命同位素", "最长寿命", "最佳可及同位素", "最佳可及来源",
            "元素可及性评分", "元素可及性等级", "可及性跨度", "主流富集工艺"]
    widths = [5, 6, 7, 13, 10, 9, 10, 17, 15, 14, 14, 9, 11, 11, 9, 22]
    df = elems[cols].copy()
    end = write_table(ws, df, 4, widths, wrap_cols=[16], score_cols=[13])
    for r in range(5, end + 1):
        g = ws.cell(row=r, column=14).value
        if g in GRADE_FILL:
            c = ws.cell(row=r, column=14)
            c.fill = PatternFill("solid", fgColor=GRADE_FILL[g])
            c.font = Font(name="微软雅黑", size=9, bold=True, color=GRADE_TEXT[g])
    ws.auto_filter.ref = f"A4:P{end}"
    ws.freeze_panes = "C5"
    note_row(ws, end + 2,
             "「可及性跨度」= 该元素最高与最低核素评分之差。跨度大的元素（如 H、U、Ca）说明"
             "「同一元素的不同同位素是完全不同的产品」——这正是本图想强调的事。"
             "「最佳可及来源」标注该格是人工策展还是模型推定。", 16)


def sheet_iptei(wb: Workbook, elems: pd.DataFrame, focus: pd.DataFrame) -> None:
    ws = wb.create_sheet("04_IPTEI扩展")
    title_block(ws, "04 · IPTEI 扩展", "在 IUPAC 同位素周期表（IPTEI）的每元素视图上，加一列可及性", 10)
    rows = []
    for _, e in elems.iterrows():
        sub = focus[focus["sym"] == e["元素"]]
        tags = ""
        if len(sub):
            tags = "；".join(sorted({t for tt in sub["tags"].dropna() for t in tt.split("·")})[:4])
        rows.append({
            "Z": e["Z"], "元素": e["元素"], "中文": e["中文"],
            "稳定同位素": e["稳定同位素数"],
            "已知核素": e["已知核素数"],
            "天然丰度范围%": e["天然丰度范围%"],
            "最长寿命同位素": e["最长寿命同位素"],
            "最长寿命": e["最长寿命"],
            "最佳可及同位素": e["最佳可及同位素"],
            "可及性评分": e["元素可及性评分"],
            "等级": e["元素可及性等级"],
            "焦点应用": tags or "—",
        })
    df = pd.DataFrame(rows)
    widths = [5, 6, 8, 9, 8, 18, 15, 14, 14, 10, 7, 40]
    end = write_table(ws, df, 4, widths, wrap_cols=[12], score_cols=[10])
    for r in range(5, end + 1):
        g = ws.cell(row=r, column=11).value
        if g in GRADE_FILL:
            c = ws.cell(row=r, column=11)
            c.fill = PatternFill("solid", fgColor=GRADE_FILL[g])
            c.font = Font(name="微软雅黑", size=9, bold=True, color=GRADE_TEXT[g])
    ws.auto_filter.ref = f"A4:L{end}"
    ws.freeze_panes = "C5"
    note_row(ws, end + 2,
             "IPTEI 原图用方块表示每种稳定/长寿命同位素的丰度与半衰期。本表保留这些量，"
             "并新增「最佳可及同位素 / 可及性评分 / 焦点应用」三列 —— 这样一眼能看出"
             "「这个元素的哪个同位素是真正能被工程使用的」。", 12)


def sheet_nuclides(wb: Workbook, nuclides: pd.DataFrame) -> None:
    ws = wb.create_sheet("05_同位素全景")
    title_block(ws, "05 · 同位素全景",
                f"{len(nuclides):,} 个已知核素（质量 AME2020；半衰期/自旋/衰变 NUBASE2020 + Wikipedia）", 18)
    cols = ["z", "sym", "isotope", "A", "N", "天然丰度%", "mass_u", "质量过剩_keV",
            "半衰期", "half_life_s", "decay_modes", "自旋", "稳定性",
            "可及性评分", "可及性等级", "工艺类别", "可得量级", "策展"]
    df = nuclides[cols].copy()
    df.columns = ["Z", "元素", "同位素", "A", "N", "天然丰度%", "原子质量 u",
                  "质量过剩 keV", "半衰期", "半衰期(秒)", "衰变模式", "自旋 I",
                  "稳定性", "可及性评分", "等级", "工艺类别", "可得量级", "策展"]
    widths = [5, 6, 9, 5, 5, 11, 14, 12, 16, 12, 26, 16, 12, 10, 6, 13, 10, 6]
    end = write_table(ws, df, 4, widths, score_cols=[14],
                      num_format={7: "0.000####", 8: "0.0", 10: "0.000E+00"})
    for r in range(5, end + 1):
        g = ws.cell(row=r, column=15).value
        if g in GRADE_FILL:
            c = ws.cell(row=r, column=14)
            c.fill = PatternFill("solid", fgColor=GRADE_FILL[g])
            c.font = Font(name="微软雅黑", size=8.5, bold=True, color=GRADE_TEXT[g])
    ws.auto_filter.ref = f"A4:R{end}"
    ws.freeze_panes = "D5"
    note_row(ws, end + 2,
             "本表绝大多数核素没有人工策展，其可及性评分由「天然丰度 + 元素级主流工艺 + 推定成本层级」"
             "推出，属趋势性估计（「策展」列为否）。要做采购决策，请看 06_可及性目录。", 18)


def sheet_focus(wb: Workbook, focus: pd.DataFrame) -> None:
    ws = wb.create_sheet("06_可及性目录")
    title_block(ws, "06 · 可及性目录", f"{len(focus)} 个焦点核素：逐条读过路线、成本与量级之后写成", 12)
    cols = ["isotope", "cn", "tags", "route", "成本等级", "可得量级", "纯度上限",
            "可及性评分", "可及性等级", "再生性", "note"]
    df = focus[cols].copy()
    df["成本等级"] = df["成本等级"].map(lambda x: f"T{int(x)}")
    df.columns = ["核素", "元素", "用途标签", "主流获取路线", "成本", "可得量级",
                  "纯度上限", "可及性评分", "等级", "再生性", "要点"]
    widths = [9, 7, 26, 30, 7, 10, 11, 10, 6, 24, 60]
    end = write_table(ws, df, 4, widths, wrap_cols=[3, 4, 10, 11], score_cols=[8])
    for r in range(5, end + 1):
        g = ws.cell(row=r, column=9).value
        if g in GRADE_FILL:
            c = ws.cell(row=r, column=9)
            c.fill = PatternFill("solid", fgColor=GRADE_FILL[g])
            c.font = Font(name="微软雅黑", size=9, bold=True, color=GRADE_TEXT[g])
    ws.auto_filter.ref = f"A4:K{end}"
    ws.freeze_panes = "C5"
    note_row(ws, end + 2,
             "成本列 T0–T4 是数量级分层：T0 大宗商品 / T1 万元每公斤级 / T2 十万元每公斤级 / "
             "T3 百万元以上每公斤级 / T4 只能按活度或原子数计。可得量级混用质量与活度口径，"
             "短半衰期核素按居里（Ci）计。", 11)


def sheet_model(wb: Workbook) -> None:
    ws = wb.create_sheet("07_评分模型")
    title_block(ws, "07 · 评分模型", "透明、可改：把权重和映射表改了，后面的表会跟着变（需重跑脚本）", 7)
    for col, w in zip("ABCDEFG", [10, 24, 10, 14, 52, 16, 4]):
        ws.column_dimensions[col].width = w

    section(ws, 4, "一、合成公式", 6)
    note_row(ws, 5, "TUIA = Base × (0.60 + 0.40 × min(S_A2…S_A7) / 100)，其中 Base = Σ w_i · S_i", 6,
             size=11, color=NAVY2)
    note_row(ws, 6, "加权平均衡量总体，短板折损项衡量「最堵的那一环」——因为可获得性由最差的维度决定。"
                    "短板只在 A2–A7 上取：A1（天然丰度）是「白送的福利分」，不是工程瓶颈；"
                    "人工核素的丰度天然为 0，其门槛已经体现在 A2（必须合成）上。", 6)
    ws.row_dimensions[6].height = 30

    section(ws, 8, "二、七个子维度与权重", 6)
    header_row(ws, 9, ["代号", "子维度", "权重", "取值来源", "说明"], [10, 24, 10, 14, 52])
    desc = {
        "A1": "天然丰度 → 100 + 12.5·log10(f)。天然占 100% 得 100 分，占 1% 得 75 分，占 1ppm 得 25 分，人工核素得 0 分。",
        "A2": "由富集工艺类别或核合成路线查映射表（见下方三）。",
        "A3": "由成本层级 T0–T4 映射：100 / 82 / 62 / 38 / 12。",
        "A4": "由可得量级映射：吨 100、公斤 82、克 62、毫克 44、微克 26、原子 8；活度口径按千居 70 / 居 48 / 毫居 28。",
        "A5": "由量级与成本层级推出：是否商业化、是否有稳定供应商与货期。",
        "A6": "按元素与放射性分类：稳定核素 90，原生放射性 28–45，锕系与易裂变材料 12–20。",
        "A7": "由工艺类别给出可达的同位素纯度上限（气体离心 99.9%，电磁分离 99.99%，加速器产物为放射化学纯）。",
    }
    for i, (code, name, w) in enumerate(WEIGHTS):
        vals = (code, name, w, "见 05/06 表", desc[code])
        for j, v in enumerate(vals, start=1):
            cell = ws.cell(row=10 + i, column=j, value=v)
            cell.font = Font(name="微软雅黑", size=9.5, color=INK)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=(j == 5),
                                       horizontal="left" if j == 5 else "center")
            if i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=CREAM)
        ws.row_dimensions[10 + i].height = 32

    r = 18
    section(ws, r, "三、工艺类别映射表", 6)
    header_row(ws, r + 1, ["工艺类别", "生产难度 A2", "纯化上限 A7", "典型同位素纯度", "说明"],
               [10, 24, 10, 14, 52])
    explain = {
        "无需富集": "天然单同位素或单一稳定核素，直接提纯即可",
        "低温蒸馏": "H/D、He、Ne、Kr、Xe、CO、NO 等轻分子，工业级成熟",
        "化学交换": "Girdler 硫化氢法产重水、COLEX 法产 6Li，吨级规模",
        "气体离心": "UF6/SiF4/GeF4/WF6 等挥发性化合物，需大规模级联",
        "离子交换色谱": "稀土与过渡金属的常规手段，单级分离系数小、需多次循环",
        "热扩散": "老工艺，产量小、能耗高",
        "电磁分离": "calutron，纯度高但产量以毫克计，成本极高",
        "激光分离": "AVLIS/SILEX 型，选择性强、TRL 偏低、设备昂贵",
        "反应堆活化": "(n,γ)/(n,p) 路线，取决于靶材与反应堆档期",
        "裂变产物分离": "从乏燃料中提取，依附后处理能力，政治敏感",
        "发生器洗脱": "母体-子体发生器，医院的「同位素水龙头」",
        "加速器合成": "回旋/直线加速器，短半衰期核素的唯一来源",
        "散裂/放射性束": "散裂靶与在线同位素分离，产量以原子计",
    }
    for i, (k, (a2, a7, pur)) in enumerate(METHOD_SCORE.items()):
        vals = (k, a2, a7, pur, explain.get(k, ""))
        for j, v in enumerate(vals, start=1):
            cell = ws.cell(row=r + 2 + i, column=j, value=v)
            cell.font = Font(name="微软雅黑", size=9.5, color=INK)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=(j == 5),
                                       horizontal="left" if j == 5 else "center")
            if i % 2 == 1:
                cell.fill = PatternFill("solid", fgColor=CREAM)

    r2 = r + 2 + len(METHOD_SCORE) + 1
    section(ws, r2, "四、成本层级定义", 6)
    header_row(ws, r2 + 1, ["层级", "含义", "", "", "价格量级（同位素产品）"], [10, 24, 10, 14, 52])
    tier_desc = [
        ("T0", "大宗商品", "低于 1 元/g，百吨级流通"),
        ("T1", "工业品", "万元/kg 量级，吨级流通"),
        ("T2", "专门品", "十万元/kg 量级，公斤级流通"),
        ("T3", "稀缺品", "百万元/kg 量级，克–公斤级"),
        ("T4", "战略/实验品", "只能按活度（Ci）或原子数计，无公开市场"),
    ]
    for i, (t, lab, note) in enumerate(tier_desc):
        cell = ws.cell(row=r2 + 2 + i, column=1, value=t)
        cell.font = Font(name="Ubuntu Mono", size=10, bold=True, color=NAVY)
        cell.alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=r2 + 2 + i, start_column=2, end_row=r2 + 2 + i, end_column=4)
        cell = ws.cell(row=r2 + 2 + i, column=2, value=lab)
        cell.font = Font(name="微软雅黑", size=9.5, bold=True)
        cell = ws.cell(row=r2 + 2 + i, column=5, value=note)
        cell.font = Font(name="微软雅黑", size=9.5)
        for j in range(1, 6):
            ws.cell(row=r2 + 2 + i, column=j).border = BOX

    r3 = r2 + 2 + len(tier_desc) + 1
    section(ws, r3, "五、等级阈值", 6)
    note_row(ws, r3 + 1,
             "S ≥ 80（随手可得） · A 65–80（常规采购） · B 50–65（需专门渠道） · "
             "C 35–50（稀缺/受限） · D 20–35（实验室级别） · E < 20（基本不可得）", 6,
             size=10, color=NAVY2)


def sheet_routes(wb: Workbook) -> None:
    ws = wb.create_sheet("08_生产路线图鉴")
    title_block(ws, "08 · 生产路线图鉴", "同一个核素，走不同路线，可得量级能差六个数量级", 8)
    rows = [
        ("气体离心", "挥发性化合物在高速离心场中按质量差逐级富集",
         "UF6、SiF4、GeF4、WF6、MoF6", "需要千级联，投资十亿量级", "3–18 个月",
         "9", "级联投资与能耗；化合物必须易挥发", "Urenco、Rosatom、中核"),
        ("低温蒸馏", "利用沸点差做低温精馏",
         "CO（13C/12C）、NO（15N）、He、Ne、Kr、Xe", "低温装置 + 高塔板数", "1–6 个月",
         "9", "能耗与冷量；同系物沸点差极小", "ORNL、Cambridge Isotope、中科院"),
        ("化学交换", "利用同位素在两相间的平衡常数差",
         "D2O（Girdler 法）、6Li（COLEX 法）", "大流量塔器，化工级投资", "数周",
         "9", "回流比大、停留时间长；但工艺简单可放大", "加拿大重水厂、中核"),
        ("离子交换色谱", "利用树脂上的同位素效应做置换色谱",
         "稀土（Gd-157、Yb-171/173、Lu-176）、Zn、Cd", "数百米柱长", "数周–数月",
         "8", "分离系数极小、产率低、溶剂消耗大", "ORNL、Eckert & Ziegler"),
        ("电磁分离（calutron）", "离子束在磁场中按质量分离",
         "Mg-26、Ca-48、Pt-195、多种稀土", "单一装置产能以毫克计",
         "数周", "7", "产能极低、电耗巨大、维护昂贵", "ORNL（历史）、俄罗斯"),
        ("激光分离", "利用同位素位移选择性电离或解离",
         "Yb、Ca、Li、U（AVLIS 型）", "中等规模中试", "研发阶段",
         "5–7", "激光器成本、选择性与通量的矛盾", "多家实验室"),
        ("反应堆中子活化", "(n,γ)/(n,p)/(n,α) 反应",
         "Co-60、Ir-192、Mo-99、Lu-177、I-131、P-32", "研究堆 + 热室",
         "1–6 个月（含冷却）", "9", "受研究堆档期与大修计划制约", "HFIR、BR-2、HFR、CARR"),
        ("裂变产物分离", "从乏燃料中提取特定裂变产物",
         "Mo-99、Cs-137、Sr-90、I-131、Ru-106", "后处理设施",
         "依赖后处理排期", "9", "政治与核安保限制；设施稀缺", "La Hague、Mayak"),
        ("发生器洗脱", "母体衰变产生子体，现场洗脱",
         "99Mo/99mTc、68Ge/68Ga、90Sr/90Y、188W/188Re", "母体供应决定一切",
         "母体 66 h – 271 d", "9", "母体产能是唯一瓶颈", "多家核药企业"),
        ("加速器合成", "质子/氘核/α 束打靶",
         "F-18、Ga-68、Zr-89、At-211、Ac-225（部分）", "回旋加速器 + 放射化学",
         "数小时–数天", "8–9", "射程与靶材；短半衰期决定必须就近", "各地 PET 中心"),
        ("散裂 / 在线同位素分离", "高能束打散裂靶，在线分离产物",
         "Ac-225、超重元素、丰中子束流", "大型散裂源", "按束流时间排期",
         "6–7", "束流时间极稀缺；化学分离复杂", "TRIUMF、LANL、CERN-ISOLDE"),
        ("天然提取", "直接从矿石/卤水/空气中分离",
         "Li、B、He、Ne、Ar、Rb、U、Th、Ra", "矿业规模", "周–月",
         "9", "资源分布与地缘政治", "各矿业公司"),
    ]
    df = pd.DataFrame(rows, columns=["路线", "原理", "代表核素", "规模门槛",
                                     "典型周期", "TRL", "主要瓶颈", "代表设施"])
    widths = [16, 30, 30, 22, 14, 6, 30, 22]
    end = write_table(ws, df, 4, widths, wrap_cols=[2, 3, 4, 7, 8])
    ws.auto_filter.ref = f"A4:H{end}"
    ws.freeze_panes = "B5"
    for r in range(5, end + 1):
        ws.row_dimensions[r].height = 42
    note_row(ws, end + 2,
             "TRL = 技术成熟度（1–9）。轨道的选择往往比核素本身更能决定价格："
             "同一个 99Mo，走反应堆 (n,γ) 路线比活度低两个数量级，但不需要后处理设施；"
             "走裂变分离路线比活度高，却被后处理能力卡死。", 8)


def sheet_loops(wb: Workbook) -> None:
    ws = wb.create_sheet("09_再生闭环")
    title_block(ws, "09 · 再生闭环", "哪些核素在消耗之后还能「回炉」，哪些只能一次性消耗", 8)
    note_row(ws, 3, "这是本图最想提出的一个观察：放射性不是「有半衰期所以不能用」，"
                    "而是「半衰期之后有没有路回去」。能闭合的循环，等价于把人造核素的寿命"
                    "变成了材料寿命；不能闭合的，才是真正的消耗品。", 8, size=9.5)
    ws.row_dimensions[3].height = 34

    rows = [
        ("钍–铀循环", "232Th + n → 233Th →(β−) 233Pa →(β−) 233U",
         "232Th（天然 100%）", "233U", "连续（需后处理）", "闭合",
         "增殖比可大于 1；但 233U 伴生 232U，其子体 Tl-208 强 γ 使燃料制造必须远程操作"),
        ("锂–氚循环", "6Li + n → 3H + α", "6Li（天然 7.6%，需富集）", "3H",
         "在线（包层内）", "闭合",
         "聚变堆自持氚的关键；6Li 富集能力直接决定聚变堆能否不依赖外部氚供应"),
        ("镎–钚循环", "237Np + n → 238Np →(β−) 238Pu", "237Np（乏燃料）", "238Pu",
         "数周", "闭合",
         "RTG 电源的替代路线；瓶颈是 237Np 的获取与高比活度靶的制造"),
        ("钴–60 换装", "59Co + n → 60Co", "59Co（天然 100%）", "60Co",
         "数年（半衰期 5.27 a）", "半闭合",
         "辐照源必须定期换装，退役源可回收再辐照；「再生」依赖反应堆档期而非物理"),
        ("钼–锝发生器", "98Mo + n → 99Mo →(β−) 99mTc", "98Mo 或裂变产物", "99mTc",
         "66 h / 6 h", "半闭合",
         "靶可以反复辐照，但 99Mo 本身无法再生；这是全球核医学最脆弱的一环"),
        ("钨–铼", "186W + n → 187W →(β−) 188W →(β−) 188Re", "186W（天然 28.4%）", "188Re",
         "69 d / 17 h", "半闭合", "188W/188Re 发生器让无加速器医院也能用铼治疗"),
        ("铋–钋", "209Bi + n → 210Bi →(β−) 210Po", "209Bi（天然 100%）", "210Po",
         "138 d", "半闭合", "α 源与静电消除器的经典路线；产物剧毒，流通量以克计"),
        ("镭–锕–镭", "226Ra + n → 227Ra → 227Ac → 227Th → 223Ra", "226Ra（铀矿）", "223Ra",
         "21.8 a / 18.7 d", "闭合",
         "靶的比活度决定 227Ac 产量；这是 225Ac 与 223Ra 供应的共同上游"),
        ("硅–磷核掺杂", "30Si + n → 31P", "30Si（需离心富集）", "31P",
         "在线", "闭合", "晶格级均匀掺杂，且掺杂原子可被中子「重写」"),
        ("铀–钚增殖", "238U + n → 239U → 239Np → 239Pu", "238U（天然 99.3%）", "239Pu",
         "数周", "闭合（受政治约束）", "物理上闭合，制度上被 NPT 与保障监督重重限制"),
        ("氚–氦三", "3H →(β−) 3He", "3H", "3He", "12.3 a", "单向",
         "产物 3He 无法回到氚；这是「有半衰期但没有回路」的典型"),
        ("裂变产物", "235U 裂变 → 137Cs / 90Sr / 99Mo / 131I …", "乏燃料", "多种",
         "随堆运行持续产出", "不可再生",
         "只能等下一批乏燃料；可获得性完全绑定后处理能力，而不是核素本身的性质"),
    ]
    df = pd.DataFrame(rows, columns=["闭环", "核反应链", "输入（靶/母体）", "产物",
                                     "再生周期", "闭合性", "要点"])
    widths = [14, 36, 20, 8, 16, 10, 56]
    end = write_table(ws, df, 5, widths, wrap_cols=[2, 3, 7])
    for r in range(6, end + 1):
        ws.row_dimensions[r].height = 40
        v = ws.cell(row=r, column=6).value
        color = {"闭合": "1B5E20", "半闭合": "7CB342", "单向": "E58E7B",
                 "不可再生": "9B2226"}.get(v, "999999")
        c = ws.cell(row=r, column=6)
        c.fill = PatternFill("solid", fgColor=color)
        c.font = Font(name="微软雅黑", size=9, bold=True, color="FFFFFF")
    ws.auto_filter.ref = f"A5:G{end}"
    ws.freeze_panes = "C6"

    r = end + 2
    section(ws, r, "一个推论", 7)
    note_row(ws, r + 1,
             "如果把「可及性」拆成「一次性获得」与「持续获得」两个分量，那么闭合循环里的核素"
             "（233U、3H、238Pu、60Co）的长期成本应该按「维持费」而不是「采购价」来算。"
             "这也解释了为什么 238Pu 的稀缺不是因为难做，而是因为能做它的反应堆与 237Np 库存有限。",
             7, size=10)
    note_row(ws, r + 3,
             "本页是人工策展的**工艺路线**（反应堆/加速器）；由核数据算出来的**衰变链与发生器**"
             "（母体比子体长寿 10 倍以上的对）见 16_衰变链与发生器 —— 两者互补：一个有工程，一个有物理。",
             7, size=9.5)


def sheet_scenarios(wb: Workbook) -> None:
    ws = wb.create_sheet("10_场景推演")
    title_block(ws, "10 · 场景推演", "把可及性维度放进真实的技术路线里看", 7)
    rows = [
        ("NV 色心金刚石", "12C ≥ 99.9%；13C 越少越好；N 杂质单独控制",
         "12C、13C、14N、15N",
         "12C 评分约 55（B）；13C 更高成本；15N 属 T3",
         "低温蒸馏 CO → 甲烷 → CVD；富集气体成本占了材料成本的大头",
         "同位素纯度是 NV 相干时间的一票否决项；Si 基量子比特同理"),
        ("硅基量子比特", "28Si ≥ 99.9%，29Si 残余决定退相干",
         "28Si、29Si、30Si、31P",
         "28Si 评分约 55（B），公斤级可购",
         "SiF4 气体离心 + 区熔；与半导体级硅纯化叠加",
         "同位素纯硅已商业化，但价格仍是天然硅的几十倍"),
        ("离子阱量子计算", "171Yb+ / 87Sr+ / 40Ca+，需要高丰度单核素",
         "171Yb、87Sr、40Ca",
         "171Yb 约 30（D），87Sr 约 32（D）",
         "电磁分离 / 激光分离；克级",
         "Yb 与 Sr 的富集是离子阱路线里最容易被忽略的供应链瓶颈"),
        ("超极化惰性气体", "129Xe（自旋 1/2）、3He",
         "129Xe、3He",
         "129Xe 约 58（B）；3He 约 15（E）",
         "低温蒸馏（Xe）；3He 只能靠氚衰变",
         "3He 的短缺曾经直接威胁中子探测器供应，是「可及性」影响科技的经典案例"),
        ("靶向 α 治疗", "225Ac / 211At / 212Pb，半衰期以天计",
         "225Ac、211At、223Ra、212Pb",
         "225Ac 约 14（E），211At 约 12（E）",
         "232Th 散裂或 227Ac 衰变；211At 需 209Bi(α,2n)",
         "疗效极强但全球年产量以毫居计；这是「核素本身可及」决定产业规模的领域"),
        ("核医学发生器", "99mTc、68Ga、90Y，医院现场洗脱",
         "99Mo→99mTc、68Ge→68Ga、90Sr→90Y",
         "99mTc 约 30（D），但其母体 99Mo 决定一切",
         "研究堆裂变 + 发生器制造",
         "供应链是单点结构：一座研究堆检修，全球影像科排队"),
        ("无中微子双 β 衰变", "76Ge、136Xe、130Te、82Se、48Ca、150Nd",
         "76Ge、136Xe、130Te",
         "76Ge 约 25（D），136Xe 约 22（E）",
         "GeF4/TeF6 离心，氙低温蒸馏",
         "这类实验的本质是「买同位素」，富集成本常常超过探测器本身"),
        ("聚变燃料", "D、T、6Li、7Li、11B",
         "2H、3H、6Li、7Li、11B",
         "2H 约 80（A）；3H 约 32（D）；6Li 约 45（C）",
         "重水化学交换；6Li 化学交换；3H 靠堆内增殖",
         "氚自持是聚变工程的第一道门槛，而它本质上是 6Li 的可及性问题"),
        ("核钟与精密测量", "229Th（229mTh 约 8 eV 核跃迁）",
         "229Th、229mTh",
         "229Th 约 12（E），毫克级",
         "233U 衰变链 / 反应堆",
         "整条链路依赖 233U 的可得性，是「可及性决定基础物理能做什么」的例子"),
        ("中子俘获治疗", "157Gd、10B",
         "157Gd、10B",
         "157Gd 约 44（C）；10B 约 47（C）",
         "离子交换色谱（Gd）；低温蒸馏（B）",
         "157Gd 的热中子俘获截面是全部稳定核素中最高，但天然只有 15.7%"),
        ("钍基核能", "232Th → 233U，需要连续后处理",
         "232Th、233U、233Pa",
         "232Th 约 78（A）；233U 约 18（E）",
         "钍矿开采；233U 需增殖与后处理",
         "「燃料易得、产物难得」的典型：资源不是瓶颈，233U 的制造与防护才是"),
    ]
    df = pd.DataFrame(rows, columns=["场景", "对同位素的要求", "关键核素",
                                     "当前可及性判读", "获取路线", "判读要点"])
    widths = [16, 30, 22, 26, 30, 44]
    end = write_table(ws, df, 4, widths, wrap_cols=[2, 3, 4, 5, 6])
    for r in range(5, end + 1):
        ws.row_dimensions[r].height = 56
    ws.freeze_panes = "B5"

    r = end + 2
    section(ws, r, "反过来读这张表", 6)
    note_row(ws, r + 1,
             "把每一行倒过来看，就得到一张「哪些技术先被卡住」的清单：不是被原理卡住，而是被某个"
             "评分只有 15 的核素卡住。TUIA 的用处不在于给元素排座次，而在于提前指出"
             "「哪一格是红的、而你的技术正好压在上面」。", 6, size=10)


def sheet_sources(wb: Workbook) -> None:
    ws = wb.create_sheet("11_数据源")
    title_block(ws, "11 · 数据源与置信度", "每个字段是从哪来的，可信到什么程度", 7)
    rows = [
        ("原子序数 / 元素符号 / 名称", "NIST + 人工整理", "NIST Atomic Weights and Isotopic Compositions",
         "权威", "118 元素全覆盖"),
        ("质量数 A、原子质量", "**AME2020**（直接读评估表原文件）",
         "IAEA AMDC mass_1.mas20.txt；Chin. Phys. C 45, 030002/030003 (2021)", "权威",
         "2 550 条；与 NIST 转发值为 143 个核素差异超过 1e-4 u（3 页附对账）"),
        ("质量过剩 / 每核子结合能", "**AME2020**", "同上", "权威", "表中以前没有这两列"),
        ("天然丰度", "NIST Isotopic Composition",
         "同上", "权威", "288 个核素有丰度值（稳定 + 原生放射性）"),
        ("半衰期", "Wikipedia「Isotopes of <element>」＋ **NUBASE2020 逐条核对**",
         "en.wikipedia.org/wiki/Isotopes_of_<element>；nubase_4.mas20.txt",
         "汇编 + 评估值核对", "基态 3 099 条可比、94.6% 一致；激发态 1 823/2 050 一致（见 15 页）"),
        ("衰变模式与分支强度", "**NUBASE2020**（BR 列）",
         "IAEA AMDC nubase_4.mas20.txt", "权威（评估表）",
         "含分支百分比（如 40K 的 β− 89.28% / β+ 10.72%）；IS（丰度）不计入衰变模式"),
        ("自旋 I（Jpi）", "**NUBASE2020**（评估值）",
         "IAEA AMDC，Chin. Phys. C 45, 030001 (2021)", "权威（评估表）",
         "NUBASE 未收录的核素才回落到维基；NUBASE 的 `#`（系统性估计）标记保留"),
        ("同位素纯度上限", "工艺经验值", "本工作簿 07_评分模型", "估计", "按工艺类别给出，非具体产品规格"),
        ("成本层级 T0–T4", "量级判断", "本工作簿 07_评分模型", "估计（±1 个数量级）",
         "不构成报价；真实价格随档期与合同波动"),
        ("可得量级", "量级判断 + 公开产能", "本工作簿 06_可及性目录", "估计", "混用质量与活度口径"),
        ("管制负担", "法规分类", "IAEA 放射性源分类 / NPT 保障监督", "定性",
         "仅用于相对比较，不能替代法规判断"),
        ("用途标签", "人工策展", "本工作簿 06_可及性目录", "定性", "127 个标签，可自行扩充"),
    ]
    df = pd.DataFrame(rows, columns=["字段", "来源", "具体出处", "置信度", "备注"])
    widths = [26, 22, 48, 18, 40]
    end = write_table(ws, df, 4, widths, wrap_cols=[3, 5])
    for r in range(5, end + 1):
        ws.row_dimensions[r].height = 34
        conf = ws.cell(row=r, column=4).value or ""
        if conf.startswith("权威"):
            ws.cell(row=r, column=4).fill = PatternFill("solid", fgColor="C8E6C9")
        elif conf.startswith("估计"):
            ws.cell(row=r, column=4).fill = PatternFill("solid", fgColor="FFE0B2")
        else:
            ws.cell(row=r, column=4).fill = PatternFill("solid", fgColor="FFF9C4")

    r = end + 2
    section(ws, r, "如果要做到「可发布级」精度，下一步应该接这些源", 5)
    up = [
        "NUBASE2020 全表 — 已接入：半衰期已逐条对账（15 页），自旋与衰变分支已换成评估值",
        "AME2020 质量表 — 已接入：原子质量、质量过剩、每核子结合能（2 550 条）",
        "ENDF/B-VIII.0 或 JENDL-5（中子截面、分离能、反应道）— 做「再生闭环」定量必须有，尚未接入",
        "IAEA 同位素价格与产能调查（成本层级从估计升级为实测）",
        "IUPAC IPTEI 官方图表（仅作版式参考；本工作簿与其中图形均独立绘制）",
    ]
    for i, t in enumerate(up, start=1):
        note_row(ws, r + i, f"{i}. {t}", 5, size=9.5)


def sheet_limits(wb: Workbook) -> None:
    ws = wb.create_sheet("12_使用与局限")
    title_block(ws, "12 · 使用与局限", "这一版能做什么、不能做什么", 6)
    for col, w in zip("ABCDEF", [4, 26, 80, 20, 14, 3]):
        ws.column_dimensions[col].width = w

    section(ws, 4, "能做的", 5)
    can = [
        "横向比较：同一元素的不同同位素、同一用途的不同候选核素，谁更「拿得到」。",
        "供应链定位：一个技术路线压在哪几个红色格子上，替代品在哪里。",
        "教学用途：把「同位素」从抽象的图表变成有价格、有货期、有许可的工程对象。",
        "扩展模板：新增核素只需在 06 目录里加一行，评分自动生成。",
    ]
    for i, t in enumerate(can, start=1):
        note_row(ws, 5 + i, f"· {t}", 4, size=10)

    section(ws, 11, "不能做的（务必别误用）", 5)
    cannot = [
        "不能当报价单：成本层级是数量级，误差可以达到 ±1 个数量级，且不随时间更新。",
        "不能当核数据表：质量（AME2020）、半衰期（已对账）、自旋与衰变分支（NUBASE）都已是评估值，"
        "但中子截面、衰变子体能级、分离能仍未接入；做计算前请以 NUBASE2020 / AME2020 / ENDF 原件为准。",
        "不能覆盖全部核素：约 3200 个核素的可及性评分是推定的，只有 227 条经过人工策展。",
        "不能替代法规判断：管制负担只是相对分值，真实许可取决于国家法规与用途。",
        "不评价「该不该做」：本表只描述获得难度，不涉及伦理、扩散与出口管制合规。",
        "不是 IUPAC 官方发布物：IPTEI 只作为编排思路的参考，本工作簿与其中图形均独立绘制，"
        "与 IUPAC 无隶属关系。",
    ]
    for i, t in enumerate(cannot, start=1):
        note_row(ws, 12 + i, f"· {t}", 4, size=10)

    section(ws, 19, "如何扩展", 5)
    steps = [
        "① 在 tools/curation.py 的 CURATION 里加一行：(符号, 质量数, 标签, 路线, 成本层级, 量级, 要点)。",
        "② 运行 python tools/build_dataset.py 重新生成三张 CSV。",
        "③ 运行 python tools/build_workbook.py 重新生成本工作簿。",
        "④ 若要替换核物理数据源，只需让 data/processed/nist_all.csv 与 isotopes_wiki.csv 保持同样的列名。",
    ]
    for i, t in enumerate(steps, start=1):
        note_row(ws, 20 + i, t, 4, size=10)

    section(ws, 26, "字段字典（06_可及性目录）", 5)
    header_row(ws, 27, ["", "字段", "含义", "取值范围"], [4, 26, 80, 20])
    fields = [
        ("核素", "质量数 + 元素符号，如 12C", "A + symbol"),
        ("用途标签", "该核素被什么领域使用，可多选", "· 分隔"),
        ("主流获取路线", "实际工业/实验室里怎么拿到它", "文本"),
        ("成本", "T0–T4 数量级分层", "T0–T4"),
        ("可得量级", "全球年可供应批量（质量或活度）", "吨/公斤/克/毫克/微克/居里"),
        ("纯度上限", "可达到的同位素纯度", "文本"),
        ("可及性评分", "七维加权 × 短板折损", "0–100"),
        ("再生性", "消耗后能否回炉再生", "4 类"),
    ]
    for i, (a, b, c) in enumerate(fields, start=1):
        for j, v in enumerate(("", a, b, c), start=1):
            cell = ws.cell(row=27 + i, column=j, value=v)
            cell.font = Font(name="微软雅黑", size=9.5)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=(j == 3))
            if i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=CREAM)


def sheet_supply(wb: Workbook) -> None:
    ws = wb.create_sheet("13_供应格局")
    title_block(ws, "13 · 分离产业格局",
                "哪些国家手里真的有这条分离产线 —— 只算稳定同位素分离，不含反应堆/加速器产物", 9)
    df = pd.read_csv(PROC / "tuia_supply.csv")
    cols = ["Z", "元素", "中文", "供应国数", "供应国", "国家码", "置信度",
            "主流分离工艺", "说明"]
    df = df[cols].copy()
    widths = [5, 7, 8, 9, 30, 26, 8, 22, 70]
    end = write_table(ws, df, 4, widths, wrap_cols=[5, 6, 8, 9], score_cols=[4])
    for r in range(5, end + 1):
        conf = ws.cell(row=r, column=7).value
        fill = {"高": "C8E6C9", "中": "FFE0B2", "低": "FFCDD2"}.get(conf, "FFFFFF")
        ws.cell(row=r, column=7).fill = PatternFill("solid", fgColor=fill)
        ws.row_dimensions[r].height = 30
    ws.auto_filter.ref = f"A4:I{end}"
    ws.freeze_panes = "C5"

    r = end + 2
    section(ws, r, "口径（务必先读）", 9)
    notes = [
        "① 只统计「同位素分离/富集」产业：低温蒸馏、气体离心、化学交换、离子交换、电磁分离、激光分离。"
        "反应堆活化产物（如 60Co、99Mo、177Lu）与加速器产物（如 18F、211At）不在此列 —— 它们的瓶颈是堆和加速器，不是分离。",
        "② 单同位素元素（Be、F、Na、Al、P、Sc、Mn、Co、As、Y、Nb、Rh、I、Cs、Pr、Tb、Ho、Tm、Au、Bi、Th）"
        "没有同位素富集产业，故不在表中 —— 这正是它们的「可及性」很高的原因。",
        "③ 未列出 ≠ 无能力。本表只收公开可查的商业/半工业供应商所在国，是下限；"
        "军用、试验性、未公开的设施一律不计。",
        "④ 置信度：高 = 多家公开供应商或在运工厂；中 = 有明确产品线但供应商少；低 = 仅零星公开记录或依赖研究机构少量制备。",
        "⑤ 国别不等于产能。同一个「US」，可能是一家工厂的几条产线，也可能是十个实验室的合计 —— 具体批量见 06_可及性目录。",
    ]
    for i, t in enumerate(notes, start=1):
        note_row(ws, r + i, t, 9, size=9.5)
        ws.row_dimensions[r + i].height = 34

    r2 = r + len(notes) + 2
    section(ws, r2, "一句话结论", 9)
    note_row(ws, r2 + 1,
             "把整张表按国别计数，会发现一件很直接的事：全球稳定同位素分离产业基本收敛到「俄罗斯 + 美国」两处，"
             "轻元素（H/C/N/O/B/Li/Si）才多出中国与日本，而铀是唯一形成全球商业市场的例外。"
             "碳-12 富集之所以贵，不是化学难，而是这条产线只在四个国家里。", 9, size=10)


def sheet_isomers(wb: Workbook) -> None:
    ws = wb.create_sheet("14_同质异能态")
    title_block(ws, "14 · 同质异能态",
                "同一个质量数、不同的能级 —— 核医学与精密测量真正依赖的那一类核素", 11)
    df = pd.read_csv(PROC / "tuia_isomers.csv").sort_values(["z", "A", "meta"])

    from curation import ISOMERS
    # 说明必须按（元素, 质量数, 能级标记）挂：只按质量数挂会把 178m2Hf 的话
    # 一并贴到 4.0 s 的 178m1Hf 上，也会把 66 h（基态 99Mo）贴到微秒级的 99m1Mo 上。
    note_by = {(s, a, m): n for s, a, m, _t, _r, _c, _q, n in ISOMERS}
    df["说明"] = [note_by.get((s, int(a), str(m)), "")
                 for s, a, m in zip(df["sym"], df["A"], df["meta"])]

    # NUBASE：激发能（只在能级编号对得上时填）+ 半衰期核对结果
    chk = pd.read_csv(PROC / "nubase_vs_isomers.csv").set_index("核素")
    mark = {"一致": "✓", "一致≈": "✓≈", "近似": "≈", "近似≈": "≈",
            "差异": "差异", "差异≈": "差异≈", "NUBASE 无": "NUBASE 无",
            "缺值": ""}
    df["激发能_keV"] = [chk.at[i, "NUBASE激发能_keV"] if i in chk.index else None
                     for i in df["isotope"]]
    df["核对"] = [mark.get(chk.at[i, "判定"], "") if i in chk.index else ""
                 for i in df["isotope"]]

    cols = ["z", "sym", "isotope", "A", "meta", "激发能_keV", "半衰期",
            "decay_modes", "spin", "核对", "说明"]
    view = df[cols].copy()
    view.columns = ["Z", "元素", "同质异能态", "A", "能级标记", "激发能 keV",
                    "半衰期", "衰变模式", "自旋 I", "NUBASE 核对", "说明"]
    widths = [5, 6, 13, 5, 8, 11, 17, 30, 10, 12, 58]
    end = write_table(ws, view, 4, widths, wrap_cols=[8, 11])
    for r in range(5, end + 1):
        if ws.cell(row=r, column=11).value:
            for c in range(1, 12):
                ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor="FFF3CD")
        v = str(ws.cell(row=r, column=10).value or "")
        if v.startswith("差异"):
            ws.cell(row=r, column=10).fill = PatternFill("solid", fgColor="FFCDD2")
        elif v.startswith("="):
            ws.cell(row=r, column=10).fill = PatternFill("solid", fgColor="FFE0B2")
    ws.auto_filter.ref = f"A4:K{end}"
    ws.freeze_panes = "D5"

    r = end + 2
    section(ws, r, "口径", 11)
    notes = [
        "① 05_同位素全景 只收**基态**核素；本表是同一批质量数上的激发态（m、m1、m2…）。"
        "核医学里最重要的一批核素全部属于这一类：99mTc（6.01 h）、111mIn（7.7 min）、137m1Ba（2.55 min）。",
        "② 数据来自 Wikipedia 逐元素同位素表的全量提取，共 2050 条；激发能与核对列来自 NUBASE2020。"
        "两边收录范围不同（NUBASE 非基态 2285 条：1841 同质异能态 + 243 能级 + 186 IAS + 11 共振），"
        "做计算一律以 NUBASE2020 为准。",
        "③ 「NUBASE 核对」列：✓ = 半衰期与 NUBASE 同能级一致（±5%）；✓≈ / ≈ = 能级编号对不上，"
        "按同质量数里最接近的激发态比；差异 = 差超过 2 倍；NUBASE 无 = 评估表里没有这个能级。",
        "④ 黄色行是人工加过说明的，且说明**按能级**挂：178m2Hf（31 a）与 178m1Hf（4.0 s）不是一回事，"
        "110m2Ag（250 d）与 110m1Ag（660 ns）也不是；111mIn 的 7.7 min 与基态 111In 的 2.80 d 同理。",
        "⑤ 同质异能态的「可及性」与基态完全不同：99mTc 由 99Mo 发生器洗脱，"
        "而不是像 99Tc 那样从乏燃料里提取 —— 见 06_可及性目录。",
    ]
    for i, t in enumerate(notes, start=1):
        note_row(ws, r + i, t, 11, size=9.5)
        ws.row_dimensions[r + i].height = 36


def sheet_chains(wb: Workbook) -> None:
    """16_衰变链与发生器：用 NUBASE 的分支算子体，找「母体远长于子体」的发生器对。"""
    ws = wb.create_sheet("16_衰变链与发生器")
    title_block(ws, "16 · 衰变链与发生器",
                "子体不是手写的：按 NUBASE2020 的分支逐条推出来，再筛「母体远长于子体」的对", 7)

    def fmt_t(s) -> str:
        if s is None or pd.isna(s) or s <= 0:
            return "—"
        for unit, v in (("a", 31557600), ("d", 86400), ("h", 3600), ("min", 60),
                        ("s", 1), ("ms", 1e-3), ("µs", 1e-6), ("ns", 1e-9),
                        ("ps", 1e-12), ("fs", 1e-15)):
            if s >= v:
                return f"{s / v:.3g} {unit}"
        return f"{s:.2e} s"

    ch = pd.read_csv(PROC / "decay_chains.csv")
    gen = ch[ch["发生器候选"] == "是"].copy()

    section(ws, 4, f"一、发生器候选（{len(gen)} 对，按母/子半衰期比排序）", 7)
    note_row(ws, 5, "判据：子体半衰期 1 min – 30 d（洗脱出来能用）、母体 1 d – 200 a（能长期供货）、"
                    "母/子 ≥ 10（否则子体跟不上、取不到活度）。", 7, size=9)
    gen_tbl = pd.DataFrame({
        "母体": gen["核素"],
        "子体": gen["子体"],
        "母体半衰期": [fmt_t(x) for x in gen["半衰期_s"]],
        "子体半衰期": [fmt_t(x) for x in gen["子体半衰期_s"]],
        "母/子": [f"{x:,.0f}" for x in gen["母/子半衰期比"]],
        "平衡类型": gen["平衡类型"],
        "子体在 06 目录": gen["子体已策展"].fillna(""),
    })
    end = write_table(ws, gen_tbl, 6, [10, 10, 12, 12, 10, 11, 12], wrap_cols=[])
    for r in range(7, end + 1):
        if ws.cell(row=r, column=7).value:
            for c in range(1, 8):
                ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor="FFF3CD")
    ws.auto_filter.ref = f"A6:G{end}"
    ws.freeze_panes = "C7"

    # ---- 二、BR 看不出来的：馈入同质异能态 ----
    from curation import ISOMER_GENERATORS
    r = end + 3
    section(ws, r, "二、BR 列看不出来的：馈入「同质异能态」的发生器（人工补）", 7)
    note_row(ws, r + 1, "NUBASE 的分支只写 B-=100，不区分落到基态还是同质异能态，"
                        "所以 99Mo→99mTc 这类关系算不出来，只能人工列。", 7, size=9)
    iso_tbl = pd.DataFrame(ISOMER_GENERATORS,
                           columns=["母体", "子体（激发态）", "母体半衰期", "子体半衰期", "用途"])
    end2 = write_table(ws, iso_tbl, r + 2, [10, 14, 12, 12, 70], wrap_cols=[5])

    # ---- 三、最长的链 ----
    r2 = end2 + 3
    section(ws, r2, "三、最长的衰变链（只走主导分支，遇稳定核素停）", 7)
    top = ch.sort_values(["链长", "半衰期_s"], ascending=[False, False]).head(24)
    chain_tbl = pd.DataFrame({
        "核素": top["核素"],
        "半衰期": [fmt_t(x) for x in top["半衰期_s"]],
        "链长": top["链长"],
        "链": top["链"],
    })
    end3 = write_table(ws, chain_tbl, r2 + 1, [10, 12, 6, 150], wrap_cols=[4])
    for rr in range(r2 + 2, end3 + 1):
        ws.row_dimensions[rr].height = 22

    # ---- 四、口径 ----
    r3 = end3 + 3
    section(ws, r3, "口径与局限", 7)
    notes = [
        "① 子体按核电荷与质量数守恒推：β− → Z+1；β+/EC → Z−1；α → Z−2、A−4；"
        "β−n → Z+1、A−1；p → Z−1、A−1；簇放射（¹⁴C、²⁴Ne…）按簇减去 Z 与 A；IT 不换核素、SF 碎片不唯一，都不连边。",
        "② 只走**主导分支**（分支比最大的那一条）：真实核素常有 2–3 条并行分支，"
        "完整的分支树见 `decay_graph.csv`（6588 条边）。",
        "③ 同质异能态没有当作独立节点：99mTc 的边记在 99Tc 上，落到基态即止。"
        "这也是「99Mo→99mTc」必须人工补的原因。",
        "④ 「平衡类型」只按半衰期比粗分：≥100 记长期平衡（子体随时在库），否则瞬时平衡。"
        "真实洗脱活度还要看分支比、发生器装柱量与淋洗效率。",
        "⑤ 09_再生闭环 里那张表是**人工策展的工艺路线**（反应堆/加速器路径），"
        "本页是**由核数据算出来的衰变关系**，两者互补：一个有工程，一个有物理。",
    ]
    for i, t in enumerate(notes, start=1):
        note_row(ws, r3 + i, t, 7, size=9.5)
        ws.row_dimensions[r3 + i].height = 32


def sheet_nubase_qa(wb: Workbook) -> None:
    """15_数据对账：把现有（维基来源）基态数据与 NUBASE2020 逐条比半衰期。"""
    ws = wb.create_sheet("15_NUBASE对账")
    title_block(ws, "15 · 与 NUBASE2020 对账",
                "半衰期是我们最怕出错的一列 —— 拿 IAEA/AMDC 的评估表逐条校一遍", 10)

    cmp = pd.read_csv(PROC / "nubase_vs_wiki.csv")
    nb = pd.read_csv(PROC / "nubase2020.csv")
    n_all, n_gs = len(nb), int((nb["idx"] == 0).sum())
    n_nong = n_all - n_gs
    vc = cmp["判定"].value_counts()
    n_cmp = len(cmp)
    n_same = int(vc.get("一致", 0))
    n_diff = int(vc.get("有差异", 0))
    n_big = int(vc.get("显著分歧", 0))

    section(ws, 4, "一、对账结果", 10)
    stats = [
        ("NUBASE2020 行数", f"{n_all}", "含基态、同质异能态、能级、共振、IAS"),
        ("其中基态", f"{n_gs}", "用来和 05_同位素全景 逐条比"),
        ("其中非基态", f"{n_nong}", "1841 同质异能态 + 243 能级 + 186 IAS + 11 共振"),
        ("两边都有（基态）", f"{n_cmp if n_cmp else 0}", "按 (Z, A) 连接后的可比半衰期条数"),
        ("半衰期一致（±5%）", f"{n_same}（{n_same / max(n_cmp, 1):.1%}）", "|Δlog10| ≤ 0.02"),
        ("有差异（5%–2×）", f"{n_diff}", "多半是四舍五入或评估更新"),
        ("显著分歧（>2×）", f"{n_big}", "见下表，需人工复核"),
    ]
    header_row(ws, 5, ["指标", "数值", "说明"], [30, 22, 78])
    for i, (k, v, note) in enumerate(stats, start=1):
        for j, val in enumerate((k, v, note), start=1):
            cell = ws.cell(row=5 + i, column=j, value=val)
            cell.font = Font(name="微软雅黑", size=9.5, bold=(j == 1), color=INK)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=(j == 3))
            if i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=CREAM)

    rows = []
    for _, r in cmp.iterrows():
        rows.append({
            "Z": int(r["Z"]), "元素": r["元素"], "核素": r["核素"],
            "维基半衰期": r["维基半衰期"],
            "维基_秒": r["维基_秒"], "NUBASE_秒": r["NUBASE_秒"],
            "比值": round(float(r["比值"]), 4) if pd.notna(r["比值"]) else None,
            "log10差": round(float(r["log10差"]), 3) if pd.notna(r["log10差"]) else None,
            "判定": r["判定"],
        })
    df = pd.DataFrame(rows).sort_values("log10差", key=lambda s: s.abs(),
                                        ascending=False)
    widths = [5, 7, 13, 26, 14, 14, 10, 9, 11]
    end = write_table(ws, df, 14, widths, wrap_cols=[4], score_cols=[])
    for r_ in range(15, end + 1):
        j = ws.cell(row=r_, column=9).value
        if j and j != "一致":
            ws.cell(row=r_, column=9).fill = PatternFill(
                "solid", fgColor="FFCDD2" if j == "显著分歧" else "FFE0B2")
    ws.auto_filter.ref = f"A14:I{end}"
    ws.freeze_panes = "C15"

    # 激发态（m 态）对账
    iso_cmp = pd.read_csv(PROC / "nubase_vs_isomers.csv")
    vci = iso_cmp["判定"].value_counts()
    n_iso_same = int(vci.get("一致", 0) + vci.get("一致≈", 0))
    rs = end + 3
    section(ws, rs, "二、激发态（m 态）对账", 10)
    header_row(ws, rs + 1, ["指标", "数值", "说明"], [30, 22, 78])
    iso_stats = [
        ("维基 m 态条数", f"{len(iso_cmp)}", "14_同质异能态 的全量"),
        ("NUBASE 非基态", "2285", "1841 同质异能态 + 243 能级 + 186 IAS + 11 共振"),
        ("半衰期与同能级一致（±5%）", f"{n_iso_same}（{n_iso_same / max(len(iso_cmp), 1):.1%}）",
         "按能级编号配对，含「≈」的近似配对"),
        ("差异（>2 倍）", f"{int(vci.get('差异', 0) + vci.get('差异≈', 0))}",
         "多数是维基给的是上限值（如 <0.1 µs）或能级排序不同"),
        ("NUBASE 里没有这个能级", f"{int(vci.get('NUBASE 无', 0))}",
         "维基报过、评估表未收，属于「文献值」而非「评估值」"),
        ("有一侧没给半衰期", f"{int(vci.get('缺值', 0))}", "无法比较，不强行给结论"),
    ]
    for i, (k, v, note) in enumerate(iso_stats, start=1):
        for j, val in enumerate((k, v, note), start=1):
            cell = ws.cell(row=rs + 1 + i, column=j, value=val)
            cell.font = Font(name="微软雅黑", size=9.5, bold=(j == 1), color=INK)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=(j == 3))
            if i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=CREAM)

    r = rs + len(iso_stats) + 3
    section(ws, r, "三、原子质量对账（AME2020 原表 vs NIST 转发值）", 10)
    ame = pd.read_csv(PROC / "ame_vs_nist.csv")
    vca = ame["判定"].value_counts()
    ame_stats = [
        ("可比条数", f"{len(ame)}", "NIST 与 AME2020 都收录的核素"),
        ("完全一致", f"{int(vca.get('一致', 0))}", "差 = 0 u"),
        ("舍入级差异", f"{int(vca.get('舍入级差异', 0))}", "相差 1e-6 u 以内，即 NIST 只保留 6 位小数"),
        ("显著差异（>1e-4 u）", f"{int(vca.get('显著差异', 0))}",
         "最大 2.86e-3 u（21B，约 2.7 MeV）—— NIST 那一份对中子滴附近的核素已经过时"),
        ("差额中位数 / 最大值", f"{ame['差_u'].abs().median():.1e} u / {ame['差_u'].abs().max():.2e} u",
         "1 u = 931 494.10242 keV"),
    ]
    header_row(ws, r + 1, ["指标", "数值", "说明"], [30, 22, 78])
    for i, (k, v, note) in enumerate(ame_stats, start=1):
        for j, val in enumerate((k, v, note), start=1):
            cell = ws.cell(row=r + 1 + i, column=j, value=val)
            cell.font = Font(name="微软雅黑", size=9.5, bold=(j == 1), color=INK)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=(j == 3))
            if i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=CREAM)

    r = r + len(ame_stats) + 3
    section(ws, r, "口径", 10)
    notes = [
        "① 基态按 (Z, A) 直接连；激发态按能级编号配对（维基 m/m1/m2 ↔ NUBASE idx 1/2/3），"
        "能级排序对不上时退一步在同质量数里找最接近的，并标「≈」。",
        "② 「一致」= |log10(维基/NUBASE)| ≤ 0.02（约 5%）；5%–2 倍记「有差异」；超过 2 倍记「显著分歧」。",
        "③ 用比值而不是差：半衰期跨 30 个数量级，只有比值才有可比性。",
        "④ 显著分歧里有相当一部分是 NUBASE 的「系统性估计」（文件名里带 # 的数），"
        "这类值本就只是量级参考，不能当成测量值。",
        "⑤ 05_同位素全景 里已换成评估值的有：自旋（NUBASE Jpi）、衰变模式与分支（NUBASE BR）、"
        "原子质量与质量过剩（AME2020）；只剩 NUBASE 未收录的那几十个核素仍为维基口径。",
    ]
    for i, t in enumerate(notes, start=1):
        note_row(ws, r + i, t, 10, size=9.5)
        ws.row_dimensions[r + i].height = 30


# ------------------------------------------------------------------ 主流程

def main() -> None:
    nuclides = pd.read_csv(PROC / "tuia_nuclides.csv")
    focus = pd.read_csv(PROC / "tuia_focus.csv")
    elems = pd.read_csv(PROC / "tuia_elements.csv")

    wb = Workbook()
    sheet_cover(wb, nuclides, focus, elems)
    sheet_readme(wb)
    sheet_periodic_image(wb)
    sheet_periodic(wb, elems)
    sheet_elements(wb, elems)
    sheet_iptei(wb, elems, focus)
    sheet_nuclides(wb, nuclides)
    sheet_focus(wb, focus)
    sheet_model(wb)
    sheet_routes(wb)
    sheet_loops(wb)
    sheet_scenarios(wb)
    sheet_sources(wb)
    sheet_limits(wb)
    sheet_supply(wb)
    sheet_isomers(wb)
    sheet_nubase_qa(wb)
    sheet_chains(wb)

    for ws in wb.worksheets:
        ws.sheet_properties.tabColor = NAVY
    wb["02_周衍图"].sheet_properties.tabColor = GOLD
    wb["06_可及性目录"].sheet_properties.tabColor = GOLD

    DIST.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print("saved", OUT, f"({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
