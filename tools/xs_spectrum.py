"""谱平均截面与共振自屏（NR 近似）。

输入：data/raw/endf8/*.json（tools/fetch_xs.py）
输出：
- data/processed/xs_spec.csv     各谱下的单群截面
- data/processed/xs_shield.csv   共振自屏后的有效俘获截面与 f 因子

两块计算：

**一、谱平均**   σ̄ = ∫σ(E)·χ(E)dE / ∫χ(E)dE
- Maxwell 谱（温度 T 可扫）：χ ∝ E·exp(-E/kT)。T=300 K 就是热谱；
  T 扫到几十–几百 keV 就是「谱逐渐变硬」，用来找「转换比什么时候过 1」。
- Watt 裂变谱（²³⁵U 热裂变的标准形状）：χ ∝ exp(-E/a)·sinh(√(bE))，a=0.988 MeV、b=2.249 MeV⁻¹。

**二、共振自屏（窄共振近似 NR）**
在含吸收体的均匀介质里，给定背景截面 σb，中子通量按
    φ(E) ∝ 1 / [σb + σt(E)]
被吸收峰压下去（σt 取弹性 + 俘获 + 裂变之和），于是
    σ_eff(σb) = ∫σγ·φ dE/E ÷ ∫φ dE/E      定义域取 0.5 eV – 100 keV
σb → ∞ 即无限稀释（无自屏）；f = σ_eff / σ_eff(∞) 就是自屏因子。
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "endf8"
PROC = ROOT / "data" / "processed"
OUT_SPEC = PROC / "xs_spec.csv"
OUT_SHIELD = PROC / "xs_shield.csv"

K_EV = 8.617333262e-5          # eV/K
WATT_A, WATT_B = 0.988e6, 2.249e-6   # eV, 1/eV（U-235 热裂变）

SHIELD_LO, SHIELD_HI = 0.5, 1.0e5    # eV，自屏积分定义域
SIGMA_B = [1e6, 1000.0, 100.0, 50.0, 20.0, 10.0]


def load(sym: str, a: int, mt: int):
    p = RAW / f"{sym}_{a}_n_{mt}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return [float(v) for v in d["energy"]], [float(v) for v in d["cross section"]]


def interp_loglog(x: list[float], y: list[float], x0: float) -> float:
    """在 (ln x, ln y) 上插值；越界返回 0（低能端之外按 0 处理，避免外推）。"""
    if not x or x0 < x[0] or x0 > x[-1]:
        return 0.0
    lo, hi = 0, len(x) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if x[mid] <= x0:
            lo = mid
        else:
            hi = mid
    x1, x2, y1, y2 = x[lo], x[hi], y[lo], y[hi]
    if y1 <= 0 and y2 <= 0:
        return 0.0
    if y1 <= 0:
        y1 = y2
    if y2 <= 0:
        y2 = y1
    if x2 <= x1:
        return y2
    t = (math.log(x0) - math.log(x1)) / (math.log(x2) - math.log(x1))
    return math.exp(math.log(y1) + t * (math.log(y2) - math.log(y1)))


def maxwell(e: float, kt: float, cut: float = 0.0) -> float:
    if e < cut:
        return 0.0
    return e * math.exp(-e / kt)


def watt(e: float) -> float:
    return math.exp(-e / WATT_A) * math.sinh(math.sqrt(WATT_B * e))


def average(x: list[float], y: list[float], w) -> float:
    """∫σ·w dE / ∫w dE（梯形）。"""
    num = den = 0.0
    for i in range(1, len(x)):
        e1, e2 = x[i - 1], x[i]
        if e2 <= 0:
            continue
        w1, w2 = w(e1), w(e2)
        num += 0.5 * (y[i - 1] * w1 + y[i] * w2) * (e2 - e1)
        den += 0.5 * (w1 + w2) * (e2 - e1)
    return num / den if den > 0 else 0.0


def shielded(xg: list[float], sc: list[float], st: list[float], sb: float):
    """NR 近似下的有效俘获截面：σ_eff = ∫σγ/(σb+σt) dE/E ÷ ∫1/(σb+σt) dE/E。"""
    num = den = 0.0
    for i in range(1, len(xg)):
        e1, e2 = xg[i - 1], xg[i]
        if e2 <= SHIELD_LO or e1 >= SHIELD_HI:
            continue
        a, b = max(e1, SHIELD_LO), min(e2, SHIELD_HI)
        if b <= a:
            continue
        for e in (a, b):
            pass
        p1 = sc[i - 1] / (sb + st[i - 1])
        p2 = sc[i] / (sb + st[i])
        dln = math.log(b / a)
        num += 0.5 * (p1 + p2) * dln
        q1 = 1.0 / (sb + st[i - 1])
        q2 = 1.0 / (sb + st[i])
        den += 0.5 * (q1 + q2) * dln
    return num / den if den > 0 else 0.0


# 参与谱平均的核素：有俘获的 + 有裂变的
NUCLIDES = [
    ("Th", 232), ("U", 238), ("U", 234), ("U", 236), ("U", 233),
    ("Pu", 239), ("Pu", 240), ("Pu", 241), ("Pu", 242),
    ("Np", 237), ("Am", 241), ("Cm", 244), ("Th", 230), ("U", 235),
]
# 谱：名字 -> 权重函数
#
# 快谱档用「Maxwell 形 + 10 keV 以下截止」的**示意性软化谱**：
# 不截止的话，Maxwell 的低能尾巴会把 ²³⁸U 在 1–10 keV 的巨大共振吃进来，
# 算出的转换比会虚假掉到 0.8 左右（真实快谱低能通量很低，但也确实不是 0，
# 所以这只是示意，不是任何真实堆芯的谱）。硬端参考用 Watt 裂变谱。
SPECTRA = {
    "热 Maxwell 300 K": lambda e: maxwell(e, 300 * K_EV),
    "Watt 裂变谱（硬）": watt,
}
for t_kev in (50, 100, 200, 400):
    # kT 直接是 t_kev 千电子伏 → eV（不要再乘 K_EV：那是 K → eV 的换算，
    # 乘上去会把 50 keV 变成 4.3 eV，配上 10 keV 截止就整段权重为 0）
    SPECTRA[f"软化快谱 kT={t_kev} keV"] = (
        lambda e, kt=t_kev * 1e3: maxwell(e, kt, cut=1.0e4))


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    cache: dict[tuple[str, int, int], tuple | None] = {}
    rows = []
    for sym, a in NUCLIDES:
        for mt, kind in ((102, "σγ"), (18, "σf")):
            key = (sym, a, mt)
            if key not in cache:
                cache[key] = load(*key)
            if cache[key] is None:
                continue
            x, y = cache[key]
            for sname, w in SPECTRA.items():
                rows.append({
                    "核素": f"{a}{sym}", "反应道": kind, "谱": sname,
                    "σ̄_barn": average(x, y, w),
                })
    spec = pd.DataFrame(rows)
    spec.to_csv(OUT_SPEC, index=False, encoding="utf-8-sig")

    # —— 自屏 ——
    sh_rows = []
    for sym, a in (("U", 238), ("Th", 232), ("Pu", 239), ("Pu", 240)):
        e2 = load(sym, a, 2)
        c102 = load(sym, a, 102)
        c18 = load(sym, a, 18)
        if not e2 or not c102:
            continue
        xg, sc = c102[0], c102[1]
        st = [interp_loglog(e2[0], e2[1], e) + sc[i]
              + (interp_loglog(c18[0], c18[1], e) if c18 else 0.0)
              for i, e in enumerate(xg)]
        base = shielded(xg, sc, st, 1e9)
        for sb in SIGMA_B:
            val = shielded(xg, sc, st, sb)
            sh_rows.append({
                "核素": f"{a}{sym}", "背景截面σb_b": sb,
                "σ_eff_barn": val, "f": val / base if base else None,
            })
    sh = pd.DataFrame(sh_rows)
    sh.to_csv(OUT_SHIELD, index=False, encoding="utf-8-sig")

    # —— 转换比随谱变硬 ——
    def sig(name, kind, sname):
        r = spec[(spec["核素"] == name) & (spec["反应道"] == kind)
                 & (spec["谱"] == sname)]
        return float(r["σ̄_barn"].iloc[0]) if len(r) else None

    print("== 转换比随谱变化（CR = σc(fertile)/[σf+σγ](fissile)）==")
    out = []
    for sname in SPECTRA:
        line = [f"{sname:<18}"]
        for fertile, fissile in (("232Th", "233U"), ("238U", "239Pu")):
            sc = sig(fertile, "σγ", sname)
            sf, sg = sig(fissile, "σf", sname), sig(fissile, "σγ", sname)
            if sc and sf and sg:
                line.append(f"{fertile}→{fissile}: {sc / (sf + sg):.4f}")
        out.append("  ".join(line))
    print("\n".join(out))

    print("\n== 共振自屏 f 因子（σb = 1000 → 10 b）==")
    for name in sh["核素"].unique():
        sub = sh[sh["核素"] == name]
        vals = " ".join(f"σb={r['背景截面σb_b']:>6.0f}b: f={r['f']:.3f}"
                        for _, r in sub.iterrows() if r["背景截面σb_b"] <= 1000)
        base = sub[sub["背景截面σb_b"] > 1e5]["σ_eff_barn"].iloc[0]
        print(f"  {name:>6}  无限稀释 {base:9.3f} b | {vals}")

    print(f"\n-> {OUT_SPEC}\n-> {OUT_SHIELD}")


if __name__ == "__main__":
    main()
