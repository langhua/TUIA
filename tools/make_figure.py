"""生成 README / 交付用的 SVG 配图（不依赖绘图库，直接写 SVG）。

输出
----
docs/figs/tuia-periodic.svg   IPTEI 式元素方框（名称 / 符号 / 原子序数 / 原子量 /
                              同位素组成饼图）+ TUIA 可及性徽标
docs/figs/tuia-heatmap.svg    可及性热力格（与工作簿 02_周衍图 同构）
docs/figs/tuia-focus-bars.svg 焦点核素评分条形图
"""

from __future__ import annotations

import math
import pathlib
import re
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from elements import ELEMENTS, GRID  # noqa: E402
from supply import SHORT, SUPPLY  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIGS = ROOT / "docs" / "figs"

NAVY = "#0F2740"
GOLD = "#C9A227"
INK = "#1B1B1B"
MUTED = "#6B6B6B"
BG = "#FAF7F0"
FONT = "'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif"

GRADE_FILL = {"S": "#1B5E20", "A": "#2E7D32", "B": "#7CB342",
              "C": "#F2C14E", "D": "#E58E7B", "E": "#9B2226"}
GRADE_TEXT = {"S": "#FFFFFF", "A": "#FFFFFF", "B": "#1B1B1B",
              "C": "#1B1B1B", "D": "#FFFFFF", "E": "#FFFFFF"}

# IPTEI 风：按元素类别上色（稀有气体取截图中的粉色）
CAT_FILL = {
    "碱金属": "#E3C6F2",
    "碱土金属": "#FFD8A8",
    "过渡金属": "#BFCBE8",
    "后过渡金属": "#A9D6D0",
    "类金属": "#E3DFA0",
    "非金属": "#93C87D",
    "稀有气体": "#F7B3C9",
    "镧系": "#F0DCC8",
    "锕系": "#E8C4C4",
}

# 同位素饼图配色：最丰的一种固定深蓝（与 IPTEI 截图一致）
SLICE_COLORS = ["#2B4B8F", "#5BC0BE", "#9C6BA8", "#D9A441", "#7A9E7E",
                "#C05A5A", "#4A6FA5", "#D98B5F", "#6B8E9F", "#A8763E"]

# IUPAC 2021 常规原子量（仅用于给出区间的那 13 个元素）
CONVENTIONAL = {
    1: "1.008", 3: "6.94", 5: "10.81", 6: "12.011", 7: "14.007",
    8: "15.999", 12: "24.305", 14: "28.085", 16: "32.06", 17: "35.45",
    18: "39.95", 35: "79.904", 81: "204.38",
}


# IUPAC 2021 标准原子量表：给出区间的元素（常规值, 下限, 上限）
IUPAC_INTERVALS = {
    1: ("1.008", "1.00784", "1.00811"),
    3: ("6.94", "6.938", "6.997"),
    5: ("10.81", "10.806", "10.821"),
    6: ("12.011", "12.0096", "12.0116"),
    7: ("14.007", "14.00643", "14.00728"),
    8: ("15.999", "15.99903", "15.99977"),
    12: ("24.305", "24.304", "24.307"),
    14: ("28.085", "28.084", "28.086"),
    16: ("32.06", "32.059", "32.076"),
    17: ("35.45", "35.446", "35.457"),
    18: ("39.95", "39.792", "39.963"),
    35: ("79.904", "79.901", "79.907"),
    81: ("204.38", "204.382", "204.385"),
}


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ------------------------------------------------------------------ 小工具

def _pt(cx: float, cy: float, r: float, ang: float) -> tuple[float, float]:
    a = math.radians(ang)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def slice_path(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    x0, y0 = _pt(cx, cy, r, a0)
    x1, y1 = _pt(cx, cy, r, a1)
    large = 1 if (a1 - a0) > 180 else 0
    return (f"M{cx:.2f},{cy:.2f} L{x0:.2f},{y0:.2f} "
            f"A{r},{r} 0 {large},1 {x1:.2f},{y1:.2f} Z")


def fmt_weight(raw, z: int) -> tuple[str, str]:
    """标准原子量 -> (白字主值, 黑字区间)。优先用 IUPAC 2021 的区间值。"""
    if z in IUPAC_INTERVALS:
        conv, lo, hi = IUPAC_INTERVALS[z]
        return (conv, f"[{lo}, {hi}]")
    if not isinstance(raw, str) or not raw.strip():
        return ("—", "")
    s = raw.strip().replace("\u00a0", " ")
    if s in {"&nbsp;", "", "nan", "None"}:
        return ("—", "")
    m = re.match(r"^\[([\d.]+)\s*,\s*([\d.]+)\]$", s)
    if m:
        lo, hi = m.group(1), m.group(2)
        return (CONVENTIONAL.get(z, ""), f"[{lo}, {hi}]")
    if s.startswith("[") and s.endswith("]"):
        return (s, "")
    v = re.sub(r"\([^)]*\)", "", s).strip()
    try:
        txt = f"{float(v):.4f}".rstrip("0").rstrip(".")
    except ValueError:
        txt = v
    return (txt, "")


# 自然界存在、但天然丰度低到无法在饼图上占一个扇区的核素（NIST 无丰度值）
TRACE = {
    1: "痕量 ³H",
    4: "痕量 ¹⁰Be",
    6: "痕量 ¹⁴C",
    13: "痕量 ²⁶Al",
    17: "痕量 ³⁶Cl",
    53: "痕量 ¹²⁹I",
}


def est_text_width(s: str, fs: float) -> float:
    """粗略估算文本宽度（CJK 按 1em，ASCII 按 0.52em）。"""
    w = 0.0
    for ch in s:
        w += fs * (1.0 if ord(ch) > 0x2E80 else 0.52)
    return w


def fmt_pct(frac: float) -> str:
    """丰度 -> 百分比文本（4 位有效数字，极小值用阈值表示）。"""
    p = frac * 100.0
    if p < 0.01:
        return "<0.01%"
    s = f"{p:.4g}"
    if "e" in s.lower():
        return "<0.01%"
    return s + "%"


def element_box(z: int, sym: str, name: str, cat: str, score: float, grade: str,
                std_weight: str, isotopes: list[tuple[int, float]],
                x: float, y: float, bw: float, bh: float,
                fallback_a: int | None = None, source: str = "策展") -> list[str]:
    """一个 IPTEI 式元素方框。"""
    out: list[str] = [f'<g transform="translate({x:.1f},{y:.1f})">']
    out.append(f'<rect x="0" y="0" width="{bw}" height="{bh}" fill="{CAT_FILL.get(cat, "#DDD")}" '
               f'stroke="{INK}" stroke-width="1.6"/>')

    # 元素名（小写，左上）
    out.append(f'<text x="9" y="21" font-size="12.5" font-weight="700" '
               f'fill="{INK}">{esc(name.lower())}</text>')

    # 可及性徽标（右上）：实心 = 人工策展，空心 = 模型推定
    bx, by, bwid, bhei = bw - 42, 6, 36, 17
    if source == "策展":
        out.append(f'<rect x="{bx}" y="{by}" width="{bwid}" height="{bhei}" rx="3" '
                   f'fill="{GRADE_FILL[grade]}"/>')
        badge_fill = GRADE_TEXT[grade]
    else:
        out.append(f'<rect x="{bx}" y="{by}" width="{bwid}" height="{bhei}" rx="3" '
                   f'fill="#FFFFFF" stroke="{GRADE_FILL[grade]}" stroke-width="1.4"/>')
        badge_fill = INK
    out.append(f'<text x="{bx + bwid / 2}" y="{by + 12.6}" font-size="10.5" '
               f'font-weight="700" fill="{badge_fill}" text-anchor="middle" '
               f'font-family="{FONT}">{grade}{score:.0f}</text>')

    # 符号 + 原子序数
    out.append(f'<text x="8" y="64" font-size="42" font-weight="700" '
               f'fill="{INK}">{esc(sym)}</text>')
    out.append(f'<text x="9" y="93" font-size="22" font-weight="700" '
               f'fill="{INK}">{z}</text>')
    if z in TRACE:
        out.append(f'<text x="9" y="110" font-size="9" fill="#4A4A4A" '
                   f'font-family="{FONT}">{esc(TRACE[z])}</text>')

    # 同位素组成饼图（偏左，给右侧标签留出一整列宽位置）
    cx, cy, r = bw - 105, 100, 30
    total_ab = sum(a for _, a in isotopes if a > 0)
    if not isotopes or total_ab <= 0:
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#8A8A8A"/>')
        mark = str(fallback_a) if fallback_a else "—"
        out.append(f'<text x="{cx}" y="{cy + 5.5}" font-size="14" font-weight="700" '
                   f'fill="#FFFFFF" text-anchor="middle" font-family="{FONT}">{mark}</text>')
    else:
        items = sorted(isotopes, key=lambda t: t[0])          # 按质量数递增绘制
        rank = {a: i for i, (a, _) in enumerate(sorted(isotopes, key=lambda t: -t[1]))}
        total = total_ab
        ang = 0.0                                             # 从 12 点开始顺时针
        right: list[list] = []
        left: list[list] = []
        # 扇区与圆内文字必须分两趟画：文字夹在循环里时，后面画的扇区会盖掉
        # 先前画好的文字（Sb 的“121 / 57.21%”就被 123 的扇区盖成了“21 / ?21%”）。
        slices: list[str] = []
        centre: list[str] = []
        for a, frac in items:
            span = 360.0 * frac / total
            a0, a1 = ang, ang + span
            colour = SLICE_COLORS[rank[a] % len(SLICE_COLORS)]
            if span >= 359.5:
                slices.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colour}"/>')
            else:
                slices.append(f'<path d="{slice_path(cx, cy, r, a0, a1)}" fill="{colour}" '
                              f'stroke="#FFFFFF" stroke-width="0.4"/>')
            mid = a0 + span / 2
            ang = a1
            if frac >= 0.5:      # 主同位素：标在圆内（质量数 + 百分比）
                centre.append(f'<text x="{cx:.1f}" y="{cy - 1:.1f}" font-size="13.5" '
                              f'font-weight="700" fill="#FFFFFF" text-anchor="middle" '
                              f'font-family="{FONT}">{a}</text>')
                centre.append(f'<text x="{cx:.1f}" y="{cy + 10.5:.1f}" font-size="8.2" '
                              f'fill="#FFFFFF" text-anchor="middle" '
                              f'font-family="{FONT}">{esc(fmt_pct(frac))}</text>')
            else:
                ex, ey = _pt(cx, cy, r + 1.5, mid)
                sin_mid = math.sin(math.radians(mid))
                pct = fmt_pct(frac)
                if sin_mid > 0.15:
                    right.append([a, ex, ey, mid, pct])
                elif sin_mid < -0.15:
                    left.append([a, ex, ey, mid, pct])
                elif math.cos(math.radians(mid)) > 0:
                    right.append([a, ex, ey, mid, pct])   # 正上方 → 右上
                else:
                    left.append([a, ex, ey, mid, pct])    # 正下方 → 左下
        out += slices
        out += centre

        # 左右两侧标签：单行「质量数 百分比」。
        # ① 必须单行 —— 两行（质量数 / 百分比）在 9–10 个同位素的元素（Sn、Te、Xe）上
        #    会两两相叠，百分比根本读不出；单行能把同样的高度装下约两倍条目。
        # ② 左侧列的 y 下限必须压到 Z（y=93）与「痕量」行（y=110）以下，
        #    否则标签会压在元素符号上（Sn 就是这样重叠过）。
        for group, sign, lo, hi in ((right, 1, 34, cy + 62),
                                    (left, -1, 128, cy + 62)):
            if not group:
                continue
            group.sort(key=lambda t: t[2])
            ys = [g[2] for g in group]
            for i in range(1, len(ys)):
                if ys[i] - ys[i - 1] < 13.0:
                    ys[i] = ys[i - 1] + 13.0
            span = ys[-1] - ys[0]
            room = hi - lo
            if len(ys) > 1 and span > room:      # 标签太多，均匀压缩
                step = room / (len(ys) - 1)
                ys = [lo + i * step for i in range(len(ys))]
            else:                                 # 否则整块平移进区间
                if ys[0] < lo:
                    ys = [v + (lo - ys[0]) for v in ys]
                if ys[-1] > hi:
                    ys = [v - (ys[-1] - hi) for v in ys]
            for (a, ex, ey, mid, pct), ty in zip(group, ys):
                label = f"{a} {pct}"
                tw = est_text_width(label, 8.2)
                if sign > 0:
                    tx = bw - 7
                    lend = tx - tw - 3
                else:
                    tx = cx - r - 8
                    lend = tx + 3
                kx, ky = _pt(cx, cy, r + 10, mid)         # 先径向快出圈
                # 折线走「径向 → 竖直 → 水平」：直接斜着连到标签会从饼图上穿过，
                # 多同位素元素上一堆斜线会盖住扇区、也读不清连的是哪块。
                out.append(f'<polyline points="{ex:.1f},{ey:.1f} {kx:.1f},{ky:.1f} '
                           f'{kx:.1f},{ty - 2.6:.1f} {lend:.1f},{ty - 2.6:.1f}" '
                           f'fill="none" stroke="{INK}" stroke-width="0.65"/>')
                out.append(f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="8.2" '
                           f'font-weight="600" fill="{INK}" text-anchor="end" '
                           f'font-family="{FONT}">{esc(label)}</text>')

    # 原子量（白字，IPTEI 版式）。无标准原子量时写 [A]（A = 最长寿核素的质量数），
    # 比一个破折号有用，也和灰圆里的数字对得上。
    if not str(std_weight or "").strip() and fallback_a:
        std_weight = f"[{fallback_a}]"
    main, interval = fmt_weight(std_weight, z)
    if not main and interval:
        out.append(f'<text x="9" y="{bh - 40}" font-size="15" font-weight="700" '
                   f'fill="#FFFFFF" font-family="{FONT}">—</text>')
        out.append(f'<text x="9" y="{bh - 22}" font-size="12" font-weight="700" '
                   f'fill="{INK}" font-family="{FONT}">{esc(interval)}</text>')
    else:
        out.append(f'<text x="9" y="{bh - 40}" font-size="15.5" font-weight="700" '
                   f'fill="#FFFFFF" font-family="{FONT}">{esc(main)}</text>')
        if interval:
            out.append(f'<text x="9" y="{bh - 22}" font-size="11.5" font-weight="700" '
                       f'fill="{INK}" font-family="{FONT}">{esc(interval)}</text>')

    # 分离产业国（粗粒度，仅稳定同位素分离）：用中文简称，宽度不够时自动缩小字号
    if sym in SUPPLY:
        codes, level, _note = SUPPLY[sym]
        text = "分离 " + "、".join(SHORT.get(c, c) for c in codes)
        fs = 8.6
        avail = bw - 12
        while fs > 6.0 and est_text_width(text, fs) > avail:
            fs -= 0.2
        fill = MUTED if level != "低" else "#8C8C8C"
        out.append(f'<text x="9" y="{bh - 6}" font-size="{fs:.1f}" fill="{fill}" '
                   f'font-family="{FONT}">{esc(text)}</text>')
    out.append("</g>")
    return out


def iptei_svg(elems: pd.DataFrame, nist: pd.DataFrame, nuclides: pd.DataFrame) -> str:
    bw, bh, gap = 205, 232, 6
    mx, top = 40, 208
    w = mx * 2 + 18 * (bw + gap) - gap
    h = top + 10 * (bh + gap) + 250

    by_z = elems.set_index("Z")
    cur = ELEMENTS
    std_by_z: dict[int, str] = {}
    iso_by_z: dict[int, list[tuple[int, float]]] = {}
    for z, grp in nist.groupby("z"):
        std_by_z[int(z)] = str(grp["std_atomic_weight"].dropna().iloc[0]) \
            if grp["std_atomic_weight"].notna().any() else ""
        lst = []
        for a, f in zip(grp["A"], grp["abundance_frac"]):
            if pd.notna(f) and f > 0:
                lst.append((int(a), float(f)))
        iso_by_z[int(z)] = sorted(lst)

    # 无天然丰度的元素：取半衰期最长的那一个核素作饼心标记
    longest: dict[int, int] = {}
    for z, grp in nuclides.groupby("z"):
        cand = grp.dropna(subset=["half_life_s"])
        if len(cand):
            longest[int(z)] = int(cand.sort_values("half_life_s").iloc[-1]["A"])

    def bracket_a(raw: str) -> int | None:
        """从 NIST 的 "[98]" 取质量数。"""
        m = re.match(r"^\s*\[(\d+)\]\s*$", str(raw or "").strip())
        return int(m.group(1)) if m else None

    def no_weight_marks(z: int) -> int | None:
        """无标准原子量的元素该标哪个质量数：优先 NIST 的方括号值，
        否则取表中最长寿核素 —— 灰圆中心与原子量处必须用同一个数，
        否则像 Tc 会出现「圆里写 97、原子量写 [98]」的自相矛盾。"""
        return bracket_a(std_by_z.get(z, "")) or longest.get(z)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}" font-family="{FONT}">',
           f'<rect width="{w}" height="{h}" fill="{BG}"/>',
           f'<text x="{w / 2:.0f}" y="68" font-size="52" font-weight="700" fill="{NAVY}" '
           f'text-anchor="middle">周衍图：同位素可及性视角下的周期表全景扩展</text>',
           f'<text x="{w / 2:.0f}" y="102" font-size="19" font-weight="600" fill="{GOLD}" '
           f'text-anchor="middle" letter-spacing="2">TUIA · The Universal Isotope Atlas</text>',
           f'<rect x="{w / 2 - 90:.0f}" y="116" width="180" height="2" fill="{GOLD}"/>',
           f'<text x="{w / 2:.0f}" y="146" font-size="15.5" font-weight="600" fill="{INK}" '
           f'text-anchor="middle">'
           f'每个方框是一个元素的同位素组成：扇区大小按天然丰度，旁标「质量数 丰度%」</text>',
           f'<text x="{w / 2:.0f}" y="169" font-size="13" fill="{MUTED}" text-anchor="middle">'
           f'灰色圆 = 无天然同位素（圆心数字为最长寿核素的质量数）；方括号如 [98] = 无标准原子量，'
           f'括号内同样是最长寿核素的质量数（IUPAC 2021 惯例）；左侧「痕量」行 = 天然存在但丰度低到画不出扇区</text>',
           f'<text x="{w / 2:.0f}" y="190" font-size="13" fill="{MUTED}" text-anchor="middle">'
           f'右上角徽标 = 可及性等级与评分；底部「分离」行 = 稳定同位素分离产业所在国；'
           f'数据来自 NIST / IUPAC 2021 / Wikipedia + NUBASE2020 核对，模型见 tools/scoring.py</text>']

    for z, (col, row) in GRID.items():
        e = cur[z - 1]
        rec = by_z.loc[z]
        x = mx + (col - 1) * (bw + gap)
        y = top + (row - 1) * (bh + gap)
        out += element_box(
            z=z, sym=e.sym, name=e.en, cat=e.cat,
            score=float(rec["元素可及性评分"]), grade=str(rec["元素可及性等级"]),
            std_weight=std_by_z.get(z, ""),
            isotopes=iso_by_z.get(z, []),
            x=x, y=y, bw=bw, bh=bh,
            fallback_a=no_weight_marks(z),
            source=str(rec.get("最佳可及来源", "推定")),
        )

    # 镧系/锕系引导标记
    lab_y = top + 8 * (bh + gap)
    out.append(f'<text x="{mx + 4}" y="{lab_y - 6}" font-size="10" fill="{MUTED}">'
               f'镧系 / 锕系（57–71、89–103）</text>')

    # 图例一：元素类别
    ly = top + 10 * (bh + gap) + 40
    out.append(f'<text x="{mx}" y="{ly}" font-size="13" font-weight="700" '
               f'fill="{NAVY}">元素类别</text>')
    for i, (cat, colour) in enumerate(CAT_FILL.items()):
        x = mx + 84 + i * 168
        out.append(f'<rect x="{x}" y="{ly - 11}" width="15" height="15" fill="{colour}" '
                   f'stroke="{INK}" stroke-width="0.8"/>')
        out.append(f'<text x="{x + 21}" y="{ly + 1}" font-size="12.5" fill="{INK}">'
                   f'{esc(cat)}</text>')

    # 图例二：可及性等级
    ly2 = ly + 36
    out.append(f'<text x="{mx}" y="{ly2}" font-size="13" font-weight="700" '
               f'fill="{NAVY}">可及性等级</text>')
    gname = [("S", "随手可得"), ("A", "常规采购"), ("B", "需专门渠道"),
             ("C", "稀缺/受限"), ("D", "实验室级别"), ("E", "仅少数机构可产")]
    for i, (g, label) in enumerate(gname):
        x = mx + 84 + i * 168
        out.append(f'<rect x="{x}" y="{ly2 - 11}" width="30" height="15" rx="2" '
                   f'fill="{GRADE_FILL[g]}"/>')
        out.append(f'<text x="{x + 15}" y="{ly2 + 0.5}" font-size="10" font-weight="700" '
                   f'fill="{GRADE_TEXT[g]}" text-anchor="middle">{g}</text>')
        out.append(f'<text x="{x + 37}" y="{ly2 + 1}" font-size="12.5" fill="{INK}">'
                   f'{esc(label)}</text>')

    # 图例二之二：实心 = 策展，空心 = 推定
    n_cur = sum(1 for zz in GRID if str(by_z.loc[zz].get("最佳可及来源", "")) == "策展")
    lx = mx + 84 + len(gname) * 168 + 26
    out.append(f'<rect x="{lx}" y="{ly2 - 11}" width="34" height="15" rx="2" '
               f'fill="{NAVY}"/>')
    out.append(f'<text x="{lx + 17}" y="{ly2 + 0.5}" font-size="10" font-weight="700" '
               f'fill="#FFFFFF" text-anchor="middle">S</text>')
    out.append(f'<text x="{lx + 41}" y="{ly2 + 1}" font-size="12.5" fill="{INK}">'
               f'实心 = 策展（{n_cur} 格，人工读过路线与量级）</text>')
    lx2 = lx + 372
    out.append(f'<rect x="{lx2}" y="{ly2 - 11}" width="34" height="15" rx="2" '
               f'fill="#FFFFFF" stroke="{NAVY}" stroke-width="1.4"/>')
    out.append(f'<text x="{lx2 + 17}" y="{ly2 + 0.5}" font-size="10" font-weight="700" '
               f'fill="{NAVY}" text-anchor="middle">S</text>')
    out.append(f'<text x="{lx2 + 41}" y="{ly2 + 1}" font-size="12.5" fill="{INK}">'
               f'空心 = 推定（{118 - n_cur} 格，模型推算）</text>')

    # 图例三：分离产业国
    ly3 = ly2 + 32
    out.append(f'<text x="{mx}" y="{ly3}" font-size="13" font-weight="700" '
               f'fill="{NAVY}">分离产业国</text>')
    out.append(f'<text x="{mx + 84}" y="{ly3 + 1}" font-size="12.5" fill="{INK}">'
               f'方框底部一行「分离 美、俄、中」= 公开可查的稳定同位素分离产业所在国；'
               f'单同位素元素无此产业，故不标。粗粒度判断，未列 ≠ 无能力。</text>')

    # 图例四：饼图与质量数标记（回应「灰色圆圈 / [98] 是什么」这类疑问）
    ly4 = ly3 + 32
    out.append(f'<text x="{mx}" y="{ly4}" font-size="13" font-weight="700" '
               f'fill="{NAVY}">饼图标记</text>')
    gy = ly4 - 11
    out.append(f'<circle cx="{mx + 100}" cy="{gy + 8}" r="11" fill="#8A8A8A"/>')
    out.append(f'<text x="{mx + 100}" y="{gy + 11.5}" font-size="9.5" font-weight="700" '
               f'fill="#FFFFFF" text-anchor="middle">98</text>')
    out.append(f'<text x="{mx + 120}" y="{ly4 + 1}" font-size="12.5" fill="{INK}">'
               f'灰圆 = 无天然同位素（Tc、Pm、Np 以后全部元素），圆心数字 = 最长寿核素的质量数；'
               f'原子量处写 [98] 同理：无标准原子量，方括号内为该质量数</text>')

    out.append(f'<text x="{mx}" y="{h - 56}" font-size="12.5" fill="{MUTED}">'
               f'读法示例：碳的饼图里 12 98.93% 与 13 1.07%，徽标 B56，分离 美、俄、中、日 —— '
               f'「碳」很便宜，但「碳-12 富集到 99.9%」只在这四个国家里做。</text>')
    out.append(f'<text x="{mx}" y="{h - 36}" font-size="12.5" fill="{MUTED}">'
               f'方框底色只表示元素类别；可及性只用右上角徽标表示，两者互不干扰。</text>')
    out.append(f'<text x="{mx}" y="{h - 14}" font-size="10.5" fill="{MUTED}">'
               f'本图为 TUIA 项目独立绘制（数据自 NIST / IUPAC 2021 汇总后自行计算），'
               f'编排思路参考 IUPAC IPTEI；不是 IUPAC 官方发布物，与 IUPAC 无隶属关系。</text>')
    out.append("</svg>")
    return "\n".join(out)


def heatmap_svg(elems: pd.DataFrame) -> str:
    cw, ch, gap = 90, 80, 5
    x0, y0 = 34, 96
    spacer = 26

    def row_y(r: int) -> float:
        if r <= 7:
            return y0 + (r - 1) * (ch + gap)
        return y0 + 7 * (ch + gap) + spacer + (r - 9) * (ch + gap)

    grid_bottom = row_y(10) + ch
    w = x0 + 18 * (cw + gap) + 24
    h = grid_bottom + 84
    by_z = elems.set_index("Z")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}" font-family="{FONT}">',
           f'<rect width="{w}" height="{h}" fill="{BG}"/>',
           f'<text x="{x0}" y="42" font-size="28" font-weight="700" fill="{NAVY}">'
           f'周衍图 · 可及性热力格</text>',
           f'<text x="{x0}" y="66" font-size="12" fill="{MUTED}">'
           f'每格 = 元素 / 原子序数 / 最佳可及同位素的可及性评分（0–100）；'
           f'底部一行 = 稳定同位素分离产业所在国</text>',
           f'<text x="{x0}" y="84" font-size="11" fill="{MUTED}">'
           f'底色代表可及性等级；虚线内框 = 可及性为模型推定；'
           f'单同位素元素（Be、Al、P、I…）无同位素富集产业，故无国别行</text>']

    for g in range(1, 19):
        x = x0 + (g - 1) * (cw + gap) + cw / 2
        out.append(f'<text x="{x}" y="{y0 - 6}" font-size="8" fill="{MUTED}" '
                   f'text-anchor="middle">{g}</text>')

    for z, (col, row) in GRID.items():
        rec = by_z.loc[z]
        g = rec["元素可及性等级"]
        sym = str(rec["元素"])
        x = x0 + (col - 1) * (cw + gap)
        y = row_y(row)
        out.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="5" '
                   f'fill="{GRADE_FILL[g]}"/>')
        if str(rec.get("最佳可及来源", "推定")) != "策展":
            out.append(f'<rect x="{x + 2.5:.1f}" y="{y + 2.5:.1f}" '
                       f'width="{cw - 5}" height="{ch - 5}" rx="4" fill="none" '
                       f'stroke="{GRADE_TEXT[g]}" stroke-opacity="0.55" '
                       f'stroke-width="0.9" stroke-dasharray="3 2.5"/>')
        out.append(f'<text x="{x + cw / 2}" y="{y + 14}" font-size="7.5" '
                   f'fill="{GRADE_TEXT[g]}" fill-opacity="0.85" text-anchor="middle">'
                   f'{z}</text>')
        out.append(f'<text x="{x + cw / 2}" y="{y + 38}" font-size="18" '
                   f'font-weight="700" fill="{GRADE_TEXT[g]}" text-anchor="middle">'
                   f'{esc(sym)}</text>')
        out.append(f'<text x="{x + cw / 2}" y="{y + 55}" font-size="10" '
                   f'font-weight="600" fill="{GRADE_TEXT[g]}" text-anchor="middle">'
                   f'{rec["元素可及性评分"]:.0f}</text>')

        if sym in SUPPLY:
            codes = [SHORT.get(c, c) for c in SUPPLY[sym][0]]
            fs, maxw = 6.5, cw - 10
            lines: list[str] = []
            cur = ""
            for c in codes:
                piece = c if not cur else "、" + c
                if cur and est_text_width(cur + piece, fs) > maxw:
                    lines.append(cur)
                    cur = c
                else:
                    cur += piece
            if cur:
                lines.append(cur)
            if len(lines) > 2:
                lines = lines[:2]
                lines[1] = lines[1] + "…"
            for i, ln in enumerate(lines):
                out.append(f'<text x="{x + cw / 2}" y="{y + 66 + i * 9}" '
                           f'font-size="{fs}" fill="{GRADE_TEXT[g]}" fill-opacity="0.8" '
                           f'text-anchor="middle" font-family="{FONT}">{esc(ln)}</text>')

    ly = grid_bottom + 24
    for i, (lab, g) in enumerate([("S 随手可得", "S"), ("A 常规采购", "A"),
                                  ("B 需专门渠道", "B"), ("C 稀缺受限", "C"),
                                  ("D 实验室级别", "D"), ("E 少数机构可产", "E")]):
        x = x0 + i * 132
        out.append(f'<rect x="{x}" y="{ly}" width="16" height="16" rx="3" '
                   f'fill="{GRADE_FILL[g]}"/>')
        out.append(f'<text x="{x + 22}" y="{ly + 12}" font-size="10" '
                   f'fill="{INK}">{esc(lab)}</text>')
    out.append(f'<text x="{x0}" y="{ly + 40}" font-size="9.5" fill="{MUTED}">'
               f'数据：NIST + Wikipedia 汇编 {len(GRID)} 个元素；评分为七维加权×短板折损的合成值；'
               f'国别为公开可查的稳定同位素分离产业，粗粒度，未列 ≠ 无能力。</text>')
    out.append("</svg>")
    return "\n".join(out)


def bars_svg(focus: pd.DataFrame, picks: list[str]) -> str:
    sub = focus[focus["isotope"].isin(picks)].copy()
    sub["order"] = sub["isotope"].map({k: i for i, k in enumerate(picks)})
    sub = sub.sort_values("order", ascending=False)

    row_h, top, left, right = 26, 92, 96, 240
    w = 900
    h = top + row_h * len(sub) + 60
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}" font-family="{FONT}">',
           f'<rect width="{w}" height="{h}" fill="{BG}"/>',
           f'<text x="28" y="42" font-size="22" font-weight="700" fill="{NAVY}">'
           f'可及性不是元素的属性，而是同位素的属性</text>',
           f'<text x="28" y="66" font-size="11.5" fill="{MUTED}">'
           f'同一元素内的两端可以差 50 分以上：碳、硅、氦都是这样</text>']

    bar_max = w - left - right
    for i, (_, r) in enumerate(sub.iterrows()):
        y = top + i * row_h
        score = float(r["可及性评分"])
        g = r["可及性等级"]
        bw = bar_max * score / 100.0
        out.append(f'<text x="{left - 12}" y="{y + 15}" font-size="12.5" '
                   f'font-weight="600" fill="{INK}" text-anchor="end">'
                   f'{esc(r["isotope"])}</text>')
        out.append(f'<rect x="{left}" y="{y + 4}" width="{bar_max}" height="15" '
                   f'rx="3" fill="#E7E1D4"/>')
        out.append(f'<rect x="{left}" y="{y + 4}" width="{bw:.1f}" height="15" '
                   f'rx="3" fill="{GRADE_FILL[g]}"/>')
        out.append(f'<text x="{left + bw + 8}" y="{y + 16}" font-size="11" '
                   f'fill="{INK}">{score:.0f} · {esc(g)}</text>')
        out.append(f'<text x="{left + bar_max + 42}" y="{y + 15}" font-size="9.5" '
                   f'fill="{MUTED}">{esc(str(r["tags"]).split("·")[0])[:16]}</text>')
    out.append(f'<text x="28" y="{h - 16}" font-size="9" fill="{MUTED}">'
               f'注：评分 = 七维加权平均 × (0.60 + 0.40 × 最差子维度/100)，见 07_评分模型</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    elems = pd.read_csv(PROC / "tuia_elements.csv")
    focus = pd.read_csv(PROC / "tuia_focus.csv")
    nist = pd.read_csv(PROC / "nist_all.csv")
    nuclides = pd.read_csv(PROC / "tuia_nuclides.csv")
    FIGS.mkdir(parents=True, exist_ok=True)

    (FIGS / "tuia-periodic.svg").write_text(
        iptei_svg(elems, nist, nuclides), encoding="utf-8")
    (FIGS / "tuia-heatmap.svg").write_text(heatmap_svg(elems), encoding="utf-8")

    picks = ["1H", "2H", "3H", "3He", "4He", "6Li", "10B", "12C", "13C",
             "14N", "15N", "18O", "28Si", "29Si", "157Gd", "171Yb",
             "235U", "238Pu", "252Cf", "225Ac", "211At", "10Be"]
    (FIGS / "tuia-focus-bars.svg").write_text(bars_svg(focus, picks), encoding="utf-8")
    print("figures written:", sorted(p.name for p in FIGS.glob("*.svg")))


if __name__ == "__main__":
    main()
