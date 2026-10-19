"""成本层级 T0–T4 的实测标定 —— 用真实成交价去校验策展的「量级估计」。

两件事：
一、SOURCES：把「哪些来源能拿到价、哪些只是询价制」逐条记下来（都是本次实际打开的页面）。
    结论：核素级报价单**没有公开价**；能机器取到的只有燃料循环侧（EIA Form EIA-858）。
二、ANCHORS：拿到的价格锚点 → 折成 元/g → 按 T 层级的带宽判「实测层级」→ 与
    tools/curation.py 里策展的 tier 对照，输出差几档。

T 层级的带宽（与 docs/methodology.md §四 一致，换成 元/g 更便于换算）：
    T0 < 1                （< 千元/kg，大宗商品）
    T1 [1, 10)            （万元/kg 量级）
    T2 [10, 100)          （十万元/kg 量级）
    T3 [100, 1000)        （百万元/kg 量级）
    T4 ≥ 1000             （十亿元/kg 以上，或只能按活度/原子数计）

用法：python tools/price_check.py
输出：data/processed/price_vs_tier.csv
"""

from __future__ import annotations

import math
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
sys.path.insert(0, str(ROOT / "tools"))

from curation import CURATION  # noqa: E402

CNY_PER_USD = 7.1

# 每档的带宽（元/g）—— 与 methodology §四 的「万元/kg / 十万元/kg / 百万元/kg」对齐
BANDS = [(1.0, 0), (10.0, 1), (100.0, 2), (1000.0, 3)]
BAND_CENTER = {0: 0.3, 1: 3.0, 2: 30.0, 3: 300.0, 4: 3000.0}


def tier_of(cny_per_g: float) -> int:
    for edge, t in BANDS:
        if cny_per_g < edge:
            return t
    return 4


# ---------------------------------------------------------------- 公开价格来源核查
# 全部是本次实际打开的页面；「原话」是页面上的原文，便于复核。
SOURCES = [
    ("NIDC（DOE 同位素计划，isotopes.gov/catalog）", "官方目录",
     "“Elements shown in blue indicate that isotopes are available for quotation… "
     "click on the cart button to complete your quote request”",
     "否，只能询价", "目录页与产品页均不标价；报价按单回复"),
    ("Sigma-Aldrich（CIL 稳定同位素分销，D₂O 99.9 atom %）", "商业目录",
     "“Sign In to View Organizational & Contract Pricing.”",
     "否，需登录", "标价藏在登录墙后，不可抓取/不可引用"),
    ("BuyIsotope（Neonest AB）", "商业目录",
     "入口一律是 “REQUEST STABLE ISOTOPE QUOTE / REQUEST ENRICHED ISOTOPE QUOTE”",
     "否，报价制", "只有清单与工艺说明，无价"),
    ("Trace Sciences International", "商业目录",
     "全站只有一个 “Get A Quote” 入口",
     "否，报价制", "同上"),
    ("IAEA / AMDC（NUBASE2020、AME2020）", "核数据评估",
     "只发布核性质（半衰期、质量、自旋、衰变分支）",
     "不适用", "本仓的核数据来源，但不含任何价格"),
    ("U.S. EIA Form EIA-858（铀市场年报 Table S1b / S2 / Table 4）", "成交量申报",
     "“weighted-average price … 58.46 per pound U3O8e”（2025 年，按品种与来源分列）",
     "**是**，逐年、可机器解析", "燃料循环侧唯一拿到手的实测成交价序列"),
]

# ---------------------------------------------------------------- 价格锚点
# (标签, 对应核素(sym,A) 或 None, 价格_元每g, 来源类型, 年份, 一句话依据)
ANCHORS_RAW = [
    ("天然铀（U3O8 加权成交）", ("U", 238),
     152.0 * CNY_PER_USD / 1000.0, "实测成交（EIA 表 S1b）", 2025,
     "58.46 $/lb U3O8e → 152.0 $/kgU → 1.08 元/g 铀"),
    ("²³⁵U（含在 90% HEU 里，按全成本摊到 ²³⁵U）", ("U", 235),
     58.0 * CNY_PER_USD, "推算（EIA 进料价 + SWU 价）", 2025,
     "进料 194.7 kg天然U/kgU + 208 SWU/kgU → 52 205 $/kgU，除 900 g ²³⁵U"),
    ("²³⁵U（含在 4.5% LEU 里，按全成本摊到 ²³⁵U）", ("U", 235),
     47.7 * CNY_PER_USD, "推算（EIA 进料价 + SWU 价）", 2025,
     "进料 9.22 kg天然U/kgU + 6.87 SWU/kgU → 2 148 $/kgU，除 45 g ²³⁵U"),
    ("³H（氚）", ("H", 3),
     30_000 * CNY_PER_USD, "二手（LANL 2003 报告，经维基转述）", 2003,
     "“the cost is $30,000 per gram ($850,000/oz) or more”；当前需求更高，只会上偏"),
    ("天然铀（2003 年，历史对照）", None,
     28.1 * CNY_PER_USD / 1000.0, "实测成交（EIA 表 S1b）", 2003,
     "10.81 $/lb → 28.1 $/kgU：同一物质二十年间跨了一整档，说明档位是「量级」不是「定价」"),
]

TIER_NAME = {0: "T0 大宗商品", 1: "T1 工业品", 2: "T2 专门品",
             3: "T3 稀缺品", 4: "T4 战略/实验品"}


def curated_tier(sym_a: tuple[str, int] | None) -> int | None:
    if not sym_a:
        return None
    for rec in CURATION:
        if (rec[0], rec[1]) == sym_a:
            return rec[4]
    return None


def main() -> None:
    src = pd.DataFrame(SOURCES, columns=["来源", "类型", "页面原话", "能拿到价吗", "结论"])
    src.to_csv(PROC / "price_sources.csv", index=False, encoding="utf-8-sig")

    curated = {(r[0], r[1]): r[4] for r in CURATION}
    rows = []
    for label, key, cny_g, src, year, basis in ANCHORS_RAW:
        t_meas = tier_of(cny_g)
        t_cur = curated_tier(key)
        mult = ratio = None
        stamp = {"实测成交（EIA 表 S1b）": f"EIA-{year}",
                 "推算（EIA 进料价 + SWU 价）": f"EIA-{year}",
                 "二手（LANL 2003 报告，经维基转述）": "LANL-2003"}.get(src, str(year))
        if t_cur is not None:
            ratio = cny_g / BAND_CENTER[t_cur]
            mult = math.log10(ratio)
        if mult is None:
            verdict = "对照（无策展行）"
        elif abs(mult) <= 1.0:
            verdict = "一致（1 个量级内）"
        elif mult > 0:
            verdict = f"低估 {mult:.1f} 个量级"
        else:
            verdict = f"高估 {abs(mult):.1f} 个量级"
        rows.append({
            "价格锚点": label,
            "对应核素": (f"{key[1]}{key[0]}" if key else "—"),
            "年份": year,
            "价格_元_per_g": round(cny_g, 3),
            "来源·时间": stamp,
            "来源类型": src,
            "依据": basis,
            "实测层级": f"T{t_meas}",
            "策展层级": f"T{t_cur}" if t_cur is not None else "—",
            "实测_策展档中心倍数": (f"{ratio:.1f}×" if ratio else "—"),
            "差数量级": (round(mult, 2) if mult is not None and pd.notna(mult) else None),
            "判定": verdict,
        })
    df = pd.DataFrame(rows)
    df.to_csv(PROC / "price_vs_tier.csv", index=False, encoding="utf-8-sig")

    print("T 层级带宽（元/g）：<1 T0 ｜ 1–10 T1 ｜ 10–100 T2 ｜ 100–1000 T3 ｜ ≥1000 T4")
    print(df[["价格锚点", "来源·时间", "价格_元_per_g", "实测层级", "策展层级",
              "实测_策展档中心倍数", "差数量级", "判定"]]
          .to_string(index=False))
    judged = df[df["差数量级"].notna()]
    ok = (judged["差数量级"].abs() <= 1.0).sum()
    print(f"\n能对照的锚点 {len(judged)} 个，其中 {ok} 个落在 ±1 个数量级内")
    print(f"写出 -> {PROC / 'price_vs_tier.csv'}、{PROC / 'price_sources.csv'}")


if __name__ == "__main__":
    main()
