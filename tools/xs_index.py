"""用热中子截面算三个「增殖/嬗变」指标。

输入：data/processed/xs_thermal.csv（tools/parse_xs.py 产出）
输出：data/processed/xs_index.csv

三个指标（都明确是**单群、2200 m/s、无共振自屏、无泄漏**的近似值）：

1. **α = σγ / σf**（裂变核）
   每吸收一个中子里「白耗」的比例。α 越小，中子经济越好。
2. **热谱单群转换比 CR = σc(增殖核) / (σf + σγ)(裂变核)**
   CR > 1 才是增殖。这是最简单的一群估计，只用来判断「热谱能不能增殖」，
   **不是**反应堆的增殖比（后者要按能谱做输运计算）。
3. **嬗变时间常数 τ = 1 / (σc · φ)**
   取热中子通量 φ = 3×10¹⁴ n·cm⁻²·s⁻¹（研究堆/压水堆的典型量级）。
   τ 与核素自身半衰期差多少倍，就是「烧掉它」比「等它衰变」快多少。
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = PROC / "xs_index.csv"

FLUX = 3.0e14          # n/cm²/s
SEC_PER_YEAR = 3.15576e7

# 嬗变靶（长寿命裂变产物 / 次锕系之外的难处理核素）
TRANSMUTE = ["99Tc", "129I", "135Cs", "93Zr", "107Pd", "79Se"]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    xs = pd.read_csv(PROC / "xs_thermal.csv", encoding="utf-8-sig")
    nuc = pd.read_csv(PROC / "tuia_nuclides.csv", encoding="utf-8-sig")
    half = dict(zip(nuc["isotope"], nuc["half_life_s"]))

    def sig(name: str, mt: int):
        r = xs[(xs["核素"] == name) & (xs["MT"] == mt)]
        return float(r["σ_热_barn"].iloc[0]) if len(r) else None

    rows = []

    # —— 1. 裂变核的 α ——
    for name in ("233U", "235U", "239Pu", "241Pu"):
        sf, sc = sig(name, 18), sig(name, 102)
        if sf and sc:
            rows.append({
                "指标": "α=σγ/σf", "对象": name,
                "值": round(sc / sf, 4),
                "说明": f"σγ={sc:.1f} b / σf={sf:.1f} b",
            })

    # —— 2. 热谱单群转换比 ——
    for fertile, fissile in (("232Th", "233U"), ("238U", "239Pu")):
        sc = sig(fertile, 102)
        sf, sg = sig(fissile, 18), sig(fissile, 102)
        if sc and sf and sg:
            rows.append({
                "指标": "热谱转换比", "对象": f"{fertile} → {fissile}",
                "值": round(sc / (sf + sg), 5),
                "说明": f"σc({fertile})={sc:.2f} b / [σf+σγ]({fissile})={sf + sg:.1f} b",
            })

    # —— 3. 嬗变时间 ——
    for name in TRANSMUTE:
        sc = sig(name, 102)
        if not sc:
            continue
        tau_s = 1.0 / (sc * 1e-24 * FLUX)
        t_half = half.get(name)
        ratio = (t_half / tau_s) if pd.notna(t_half) and t_half else None
        rows.append({
            "指标": "嬗变时间 τ", "对象": name,
            "值": round(tau_s / SEC_PER_YEAR, 3),
            "说明": (f"σc={sc:.2f} b、φ=3e14；半衰期 {t_half / SEC_PER_YEAR:,.3g} a，"
                     f"比 τ 长 {ratio:,.3g} 倍" if ratio else f"σc={sc:.2f} b、φ=3e14"),
        })

    # —— 4. 中子毒物 / 氚增殖 ——
    li, b10, he3 = sig("6Li", 105), sig("10B", 107), sig("3He", 103)
    rows.append({
        "指标": "氚增殖 vs 中子毒物", "对象": "6Li / 10B",
        "值": round(li / b10, 3),
        "说明": f"⁶Li(n,t)={li:.0f} b、¹⁰B(n,α)={b10:.0f} b、³He(n,p)={he3:.0f} b",
    })

    # —— 5. 金标准校验 ——
    au = sig("197Au", 102)
    rows.append({
        "指标": "校验 197Au(n,γ)", "对象": "197Au",
        "值": round(au, 2),
        "说明": "手册值为 98.65 b（中子通量监测的经典基准），差 %.2f%%"
                % (abs(au - 98.65) / 98.65 * 100),
    })

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(df.to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
