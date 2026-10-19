"""解析 EIA 铀市场年报 → 燃料循环成交价 + 由成交价推出的同位素成本。

输入：data/raw/eia/*.xlsx（tools/fetch_prices.py 抓的）
输出（data/processed/）：
    prices_fuelcycle.csv   逐年：U3O8 加权/现货/长协价（$/lb U3O8e）、SWU 价（$/SWU）、U3O8 折 $/kgU
    prices_material2025.csv 2025 年按物料形态（U3O8 / 天然 UF6 / 浓缩 UF6）的成交量与成交价
    prices_derived.csv     4.5% / 19.75% / 90% 三档丰度的进料量与分离功、$\\mathrm{kgU}$、
                           每克 ²³⁵U 的隐含成本

几处必须说清楚的口径（都写进 CSVs 与工作表）：
1. EIA 的原材料价格单位是 **$/lb U3O8e**（U3O8 当量），换算 $/kgU 用
   1 lb U3O8 = 0.45359237 kg × (3×238.02891)/(3×238.02891+8×15.9994)
             = 0.384641 kgU，故 1 kgU = 2.5998 lb U3O8。
   （写错成 0.41628 会让所有 $/kgU 低 8%——这个数只能由原子量算，不能靠记。）
2. Table 4 的表注写明：天然 UF6 与浓缩 UF6 的价格**只含铀组分（U3O8 当量）、不含转化与
   浓缩服务费**。所以「天然 UF6 价 − U3O8 价」不等于转化费，本脚本**不去拆它**。
3. SWU 价是浓缩服务价；分离功公式用标准值函数 V(x)。

用法：python tools/parse_prices.py
"""

from __future__ import annotations

import pathlib

import openpyxl
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "eia"
PROC = ROOT / "data" / "processed"

# ---- 换算常数（都从原子量算，不写死结果）----
A_U = 238.02891        # ²³⁸U 原子质量（u），天然铀按它算 U3O8 的铀质量分数
A_O = 15.9994
LB = 0.45359237        # kg per lb
U_FRAC_U3O8 = 3 * A_U / (3 * A_U + 8 * A_O)          # 0.84799
LB_U3O8_PER_KG_U = 1.0 / (LB * U_FRAC_U3O8)          # 2.5998
CNY_PER_USD = 7.1      # 只用于把 $/g 折成 元/g；汇率变了 T 层级判断不变（差一个数量级才换档）

XF = 0.00711           # 天然铀 ²³⁵U 丰度
XW = 0.0025            # 尾料丰度（典型离心厂的贫化尾料）

# (产品丰度, 名称)
ASSAYS = [
    (0.045, "LEU 4.5%（压水堆燃料）"),
    (0.1975, "HALEU 19.75%（研究堆 / 先进堆）"),
    (0.90, "HEU 90%（武器级）"),
]


def _num(v):
    """EIA 用 'W'（保密）与 '- -' / '-' 表示缺数，一律返回 None。"""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        t = v.strip().replace(",", "")
        try:
            return float(t)
        except ValueError:
            return None
    return None


def _rows(path: pathlib.Path):
    wb = openpyxl.load_workbook(path, data_only=True)
    return [[c for c in r] for r in wb.worksheets[0].iter_rows(values_only=True)]


def _find_col(header: list, *keys: str) -> int | None:
    for i, c in enumerate(header):
        if isinstance(c, str) and all(k.lower() in c.lower() for k in keys):
            return i
    return None


def parse_uranium(path: pathlib.Path) -> pd.DataFrame:
    rows = _rows(path)
    hdr_i = next(i for i, r in enumerate(rows)
                 if isinstance(r[0], str) and r[0].strip() == "Delivery year")
    hdr = rows[hdr_i]
    c_tot = _find_col(hdr, "Total purchased")
    c_spot = _find_col(hdr, "Spot contracts")
    c_long = _find_col(hdr, "Long-term contracts")
    out = []
    for r in rows[hdr_i + 1:]:
        y = r[0]
        if not isinstance(y, int):
            continue
        tot = _num(r[c_tot])
        out.append({
            "年份": y,
            "U3O8e加权价_usd_per_lb": tot,
            "U3O8e现货价_usd_per_lb": _num(r[c_spot]),
            "U3O8e长协价_usd_per_lb": _num(r[c_long]),
            "U3O8e加权价_usd_per_kgU": round(tot * LB_U3O8_PER_KG_U, 1) if tot else None,
        })
    return pd.DataFrame(out)


def parse_swu(path: pathlib.Path) -> pd.DataFrame:
    rows = _rows(path)
    hdr_i = next(i for i, r in enumerate(rows)
                 if isinstance(r[0], str) and r[0].strip() == "Year")
    c_swu = _find_col(rows[hdr_i], "Average price")
    out = []
    for r in rows[hdr_i + 1:]:
        y = r[0]
        if not isinstance(y, int):
            continue
        out.append({"年份": y, "SWU价_usd_per_SWU": _num(r[c_swu])})
    return pd.DataFrame(out)


MATERIAL_CN = {
    "Uranium concentrate": "铀氧化物精矿（U3O8）",
    "Natural UF6": "天然 UF6",
    "Enriched UF6": "浓缩 UF6",
    "Total": "合计",
}


def parse_material(path: pathlib.Path) -> pd.DataFrame:
    rows = _rows(path)
    hdr_i = next(i for i, r in enumerate(rows)
                 if r and isinstance(r[0], str) and r[0].strip() == "Deliveries")
    hdr = rows[hdr_i]
    cols = []
    for key in ("Uranium concentrate", "Natural UF6", "Enriched UF6", "Total"):
        i = _find_col(hdr, key)
        if i is not None:
            cols.append((i, key))
    # 同一列名出现两次时（"Natural UF6 and Enriched UF6" 含 "Natural UF6"），只认精确匹配
    exact = []
    for key in ("Uranium concentrate", "Natural UF6", "Enriched UF6", "Total"):
        for i, c in enumerate(hdr):
            if isinstance(c, str) and c.strip() == key:
                exact.append((i, key))
                break
    cols = exact or cols

    # 取最后一段（Total）里的 Purchases 与 Weighted-average price。
    # 注意：表注那一行以 "Notes: ... Weighted-average prices ..." 开头，用 in 会误命中
    # （踩过：整列变成 None），所以这里必须做 == 精确比较。
    qty_row = price_row = None
    for r in rows[hdr_i + 1:]:
        if isinstance(r[0], str) and r[0].strip().startswith("Purchases"):
            qty_row = r
        elif isinstance(r[0], str) and r[0].strip() == "Weighted-average price":
            price_row = r            # 反复覆盖 → 停在最后一段（Total）
    out = []
    for i, key in cols:
        q = _num(qty_row[i]) if qty_row else None
        p = _num(price_row[i]) if price_row else None
        out.append({"物料形态": MATERIAL_CN.get(key, key),
                    "采购量_千lb_U3O8e": q,
                    "加权平均价_usd_per_lb_U3O8e": p})
    return pd.DataFrame(out)


def v(x: float) -> float:
    """分离功价值函数 V(x) = (1-2x)·ln((1-x)/x)。"""
    return (1 - 2 * x) * __import__("math").log((1 - x) / x)


def derive(c_u3o8_per_kg_u: float, c_swu: float) -> pd.DataFrame:
    """由「天然铀 $/kgU」与「$SWU」推出各丰度产品的单位成本。

    成本只含两项（EIA 有实测的两项）：进料铀 + 分离功。
    转化与元件制造 EIA 不发布价格，本表不计（见工作表口径）。
    """
    out = []
    for xp, name in ASSAYS:
        feed = (xp - XW) / (XF - XW)                       # kg 天然铀 / kg 产品
        swu = v(xp) + (feed - 1) * v(XW) - feed * v(XF)    # SWU / kg 产品
        c_feed = feed * c_u3o8_per_kg_u
        c_sep = swu * c_swu
        total = c_feed + c_sep
        g235 = xp * 1000.0                                 # g ²³⁵U / kg 产品
        out.append({
            "产品": name,
            "²³⁵U丰度": xp,
            "进料量_kg天然U_per_kg产品": round(feed, 3),
            "分离功_SWU_per_kg产品": round(swu, 2),
            "进料成本_usd_per_kgU": round(c_feed, 0),
            "分离成本_usd_per_kgU": round(c_sep, 0),
            "合计_usd_per_kgU": round(total, 0),
            "²³⁵U含量_g_per_kgU": round(g235, 1),
            "每克²³⁵U_usd": round(total / g235, 1),
            "每克²³⁵U_元": round(total / g235 * CNY_PER_USD, 1),
            "每公斤铀_元": round(total * CNY_PER_USD, 0),
        })
    return pd.DataFrame(out)


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    ur = parse_uranium(RAW / "umartableS1bfigureS2.xlsx")
    swu = parse_swu(RAW / "umartableS2figuresS3n4.xlsx")
    mat = parse_material(RAW / "umartable4figure6.xlsx")

    fu = ur.merge(swu, on="年份", how="outer").sort_values("年份")
    fu.to_csv(PROC / "prices_fuelcycle.csv", index=False, encoding="utf-8-sig")
    mat.to_csv(PROC / "prices_material2025.csv", index=False, encoding="utf-8-sig")

    last = fu.dropna(subset=["U3O8e加权价_usd_per_kgU"]).iloc[-1]
    yr = int(last["年份"])
    c_u = float(last["U3O8e加权价_usd_per_kgU"])
    c_swu = float(fu.dropna(subset=["SWU价_usd_per_SWU"]).iloc[-1]["SWU价_usd_per_SWU"])
    der = derive(c_u, c_swu)
    der.insert(0, "基准年", yr)
    der.insert(1, "天然铀_usd_per_kgU", round(c_u, 1))
    der.insert(2, "SWU价_usd_per_SWU", c_swu)
    der.to_csv(PROC / "prices_derived.csv", index=False, encoding="utf-8-sig")

    print(f"1 lb U3O8 = {LB * U_FRAC_U3O8:.6f} kgU -> 1 kgU = {LB_U3O8_PER_KG_U:.4f} lb U3O8")
    print(f"\n{yr} 年基准：天然铀 {c_u:.1f} $/kgU，SWU {c_swu:.2f} $/SWU")
    print(der[["产品", "进料量_kg天然U_per_kg产品", "分离功_SWU_per_kg产品",
               "合计_usd_per_kgU", "每克²³⁵U_usd", "每克²³⁵U_元"]].to_string(index=False))
    print("\n2025 按物料形态：")
    print(mat.to_string(index=False))
    print("\n价格波动（U3O8e 加权价，$/lb）：2003 "
          f"{ur.iloc[0]['U3O8e加权价_usd_per_lb']:.2f} / 峰值 "
          f"{ur['U3O8e加权价_usd_per_lb'].max():.2f}（{int(ur.loc[ur['U3O8e加权价_usd_per_lb'].idxmax(),'年份'])}）"
          f" / {yr} {float(last['U3O8e加权价_usd_per_lb']):.2f}")
    print(f"写出 -> {PROC}")


if __name__ == "__main__":
    main()
