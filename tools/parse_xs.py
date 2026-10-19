"""从 ENDF/B-VIII.0 的逐点截面里取三个数：热中子截面、共振积分、峰值。

输入：data/raw/endf8/*.json（由 tools/fetch_xs.py 下载）
输出：data/processed/xs_thermal.csv

三个量的定义（都按 ENDF-6 的惯例写清楚，便于复核）：
- **热中子截面 σ₀**：E = 0.0253 eV（2200 m/s）处的截面。
  逐点在 (ln E, ln σ) 上线性插值 —— 截面常常跨 3–6 个数量级，线性能量插值会明显偏低。
- **共振积分 RI**：∫₀.₅eV^20MeV σ(E) dE/E，同样在 ln 网格上做梯形积分。
  这是「超热区吸收能力」的常用指标（严格定义还含 1/v 扣除，这里不减，标为 RI_total）。
- **峰值**：能区内的最大截面与对应能量（113Cd、176Hf 这类全靠共振峰的核素靠它才看得出差别）。
"""

from __future__ import annotations

import json
import math
import pathlib
import re

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "endf8"
OUT = ROOT / "data" / "processed" / "xs_thermal.csv"

E0 = 0.0253            # eV，2200 m/s
RI_LO, RI_HI = 0.5, 2.0e7

MT_NAME = {2: "弹性散射", 16: "(n,2n)", 18: "裂变", 102: "(n,γ) 俘获",
           103: "(n,p)", 105: "(n,t)", 107: "(n,α)"}


def interp_loglog(x: list[float], y: list[float], x0: float) -> float | None:
    """在 (ln x, ln y) 上线性插值；y ≤ 0 的点跳过（截面为零处取 0）。"""
    if not x or x0 < x[0] or x0 > x[-1]:
        return None
    lo, hi = 0, len(x) - 1
    while hi - lo > 1:                      # 二分找区间
        mid = (lo + hi) // 2
        if x[mid] <= x0:
            lo = mid
        else:
            hi = mid
    x1, x2 = x[lo], x[hi]
    y1, y2 = y[lo], y[hi]
    if y1 <= 0 and y2 <= 0:
        return 0.0
    if y1 <= 0:
        y1 = y2
    if y2 <= 0:
        y2 = y1
    if x2 == x1:
        return y2
    t = (math.log(x0) - math.log(x1)) / (math.log(x2) - math.log(x1))
    return math.exp(math.log(y1) + t * (math.log(y2) - math.log(y1)))


def resonance_integral(x: list[float], y: list[float],
                       lo: float = RI_LO, hi: float = RI_HI) -> float:
    """∫σ dE/E，在 ln E 上做梯形积分，只取 [lo, hi] 区间。"""
    total = 0.0
    for i in range(1, len(x)):
        e1, e2 = x[i - 1], x[i]
        if e2 <= lo or e1 >= hi:
            continue
        s1, s2 = y[i - 1], y[i]
        a, b = max(e1, lo), min(e2, hi)
        if b <= a:
            continue
        # 端点在 ln 区间内按比例插值截面（线性于 ln E）
        span = math.log(e2 / e1) if e2 > e1 else 0.0
        if span <= 0:
            continue
        ta = (math.log(a / e1)) / span if a > e1 else 0.0
        tb = (math.log(b / e1)) / span if b < e2 else 1.0
        sa = s1 + (s2 - s1) * ta
        sb = s1 + (s2 - s1) * tb
        # ∫σ d(lnE) 的梯形近似再换成 dE/E
        total += 0.5 * (sa + sb) * (math.log(b / a))
    return total


def main() -> None:
    rows = []
    for f in sorted(RAW.glob("*.json")):
        m = re.match(r"^([A-Za-z]{1,2})_(\d+)_n_(\d+)\.json$", f.name)
        if not m:
            continue
        sym, a, mt = m.group(1), int(m.group(2)), int(m.group(3))
        d = json.loads(f.read_text(encoding="utf-8"))
        x = [float(v) for v in d["energy"]]
        y = [float(v) for v in d["cross section"]]
        if not x:
            continue
        i_max = max(range(len(y)), key=lambda i: y[i])
        # 峰值只在 ≥0.5 eV 找：1/v 核素的最大的截面恒在最底一个能量点上，
        # 那个「峰值」没有信息量；先找超热区里的共振峰。
        cand = [i for i, e in enumerate(x) if e >= RI_LO]
        i_res = max(cand, key=lambda i: y[i]) if cand else i_max
        rows.append({
            "元素": sym, "A": a, "Z": int(d["Proton number"]),
            "MT": mt, "反应道": MT_NAME.get(mt, f"MT={mt}"),
            "σ_热_barn": interp_loglog(x, y, E0),
            "共振积分_barn": resonance_integral(x, y),
            "共振峰截面_barn": y[i_res],
            "共振峰能量_eV": x[i_res],
            "全局最大_barn": y[i_max],
            "数据点数": len(x),
            "能区下限_eV": x[0], "能区上限_eV": x[-1],
        })

    df = pd.DataFrame(rows).sort_values(["Z", "A", "MT"])
    df["核素"] = df["A"].astype(str) + df["元素"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    print(f"{len(df)} 条截面记录 -> {OUT}")
    print(df[["核素", "反应道", "σ_热_barn", "共振积分_barn", "共振峰截面_barn",
              "共振峰能量_eV"]].to_string(index=False))


if __name__ == "__main__":
    main()
