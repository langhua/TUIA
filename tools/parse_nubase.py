"""解析 NUBASE2020 的 ASCII 表（`nubase_4.mas20.txt`）为结构化 CSV。

数据来源：IAEA AMDC，https://www-nds.iaea.org/amdc/ame2020/nubase_4.mas20.txt
引用要求：F.G. Kondev, M. Wang, W.J. Huang, S. Naimi, G. Audi,
          Chin. Phys. C 45, 030001 (2021)。

输出：data/processed/nubase2020.csv

列（源自文件头注释的固定宽度定义，1-based 闭区间）：
  1: 3  A / 5: 8 ZZZi / 12:16 A El / 17 s(态字母) / 19:31 质量过剩 / 32:42 其误差
  43:54 激发能 / 55:65 其误差 / 66:67 Orig / 68 Isom.Unc / 69 Isom.Inv
  70:78 T / 79:80 unit / 82:88 dT / 89:102 Jpi / 103:104 ENSDF 年 / 115:118 发现年
  120:209 BR（衰变模式与强度，IS=同位素丰度）
"""

from __future__ import annotations

import pathlib
import re

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "amdc" / "nubase_4.mas20.txt"
OUT = ROOT / "data" / "processed" / "nubase2020.csv"

# 1 秒 = 多少；年用儒略年
UNIT_S = {
    "ys": 1e-24, "zs": 1e-21, "as": 1e-18, "fs": 1e-15, "ps": 1e-12,
    "ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0, "m": 60.0, "h": 3600.0,
    "d": 86400.0, "y": 31557600.0,
}
_Y = 31557600.0
for _p, _f in (("k", 1e3), ("M", 1e6), ("G", 1e9), ("T", 1e12),
               ("P", 1e15), ("E", 1e18), ("Z", 1e21), ("Y", 1e24)):
    UNIT_S[_p + "y"] = _Y * _f

KIND = {"0": "基态", "1": "同质异能态", "2": "同质异能态",
        "3": "能级", "4": "能级", "5": "共振", "8": "IAS", "9": "IAS"}


def _num(text: str):
    """' 8071.3181  ' -> 8071.3181；带 '#' 表示外推，返回 (值, 是否外推)。"""
    t = text.strip()
    if not t:
        return None, False
    est = "#" in t
    t = t.replace("#", "")
    try:
        return float(t), est
    except ValueError:
        m = re.match(r"[-+]?\d*\.?\d+", t)
        return (float(m.group()) if m else None), est


def parse_tl(t_text: str, unit: str):
    """返回 (秒, 类型)；类型 ∈ 定量/稳定/粒子不稳定/未给。"""
    t = t_text.strip()
    if not t:
        return None, "未给"
    if t == "stbl":
        return None, "稳定"
    if t.startswith("p-unst"):
        return None, "粒子不稳定"
    fac = UNIT_S.get(unit.strip())
    val, _est = _num(t)
    if fac is None or val is None:
        return None, "未给"
    return val * fac, "定量"


def main() -> None:
    rows = []
    for line in SRC.read_text(encoding="latin-1").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        line = line.ljust(209)
        a = line[0:3].strip()
        zzi = line[4:8].strip()
        ael = line[11:16].strip()
        if not (a.isdigit() and zzi.isdigit() and ael):
            continue
        z = int(zzi[:3])
        idx = int(zzi[3])
        sym = re.sub(r"^\d+", "", ael)
        state = line[16:17]
        mass, mass_est = _num(line[18:31])
        dmass, _ = _num(line[31:42])
        exc, _ = _num(line[42:54])
        dexc, _ = _num(line[54:65])
        t_text = line[69:78].strip()
        unit = line[78:80].strip()
        tl_s, tl_kind = parse_tl(t_text, unit)
        jpi = line[88:102].strip()
        rows.append({
            "z": z,
            "sym": sym,
            "A": int(a),
            "idx": idx,
            "态": KIND.get(str(idx), f"其他({idx})"),
            "核素": f"{a}{sym}" if idx == 0 else f"{a}m{idx}{sym}",
            "态字母": state,
            "质量过剩_keV": mass,
            "质量过剩误差_keV": dmass,
            "质量外推": "是" if mass_est else "",
            "激发能_keV": exc,
            "激发能误差_keV": dexc,
            "T": t_text,
            "单位": unit,
            "半衰期_s": tl_s,
            "半衰期类型": tl_kind,
            "Jpi": jpi,
            "ENSDF年": line[102:104].strip(),
            "发现年": line[114:118].strip(),
            "衰变与丰度": line[119:].strip(),
        })
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    gs = (df["idx"] == 0).sum()
    print(f"rows={len(df)}  基态={gs}  激发态/能级/共振={len(df) - gs}")
    print(df["态"].value_counts().to_string())
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
