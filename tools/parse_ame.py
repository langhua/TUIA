"""解析 AME2020 的原子质量表（`mass_1.mas20.txt`）为 CSV。

数据来源：IAEA AMDC，https://www-nds.iaea.org/amdc/ame2020/mass_1.mas20.txt
引用要求：W.J. Huang et al., Chin. Phys. C 45, 030002 (2021)（AME2020-I）
         与 M. Wang et al., Chin. Phys. C 45, 030003 (2021)（AME2020-II）。

文件头给出的固定宽度格式（1-based 闭区间）：
    1      cc      a1
    2: 4   NZ      i3
    5: 9   N       i5
   10:14   Z       i5
   15:19   A       i5
   21:23   el      a3
   24:27   orig    a4
   29:42   mass excess   f14.6  (keV)
   43:54   其误差        f12.6
   55:67   binding/A     f13.5  (keV)
   69:78   B (Beta)      f10.5  (keV)
   80:81   beta 类型     a2
   82:94   beta 能量     f13.5  (keV)
   95:105  其误差        f11.5
  111:123  原子质量      f13.6  (micro-u，整数部分用空格分隔千位)
  124:135  其误差        f12.6

注意：原子质量在文件里写成 `1 007825.031898` —— **整数部分与小数部分是两段字段**
（`[106:109]` 是整数，`[110:123]` 是小数），只取后一段会得到 0.0078 u。

`#` 表示非实验值（由系统性外推），`*` 表示不可计算。

输出：data/processed/ame2020.csv
"""

from __future__ import annotations

import pathlib
import re

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "amdc" / "mass_1.mas20.txt"
OUT = ROOT / "data" / "processed" / "ame2020.csv"

U_KEV = 931494.10242          # 1 u = 931.49410242 MeV


def _f(text: str):
    """'#8071.31' -> (8071.31, 是否外推)；'*' / 空 -> (None, False)。"""
    t = text.strip()
    if not t or t == "*":
        return None, False
    est = "#" in t
    t = t.replace("#", "").replace(" ", "")
    try:
        return float(t), est
    except ValueError:
        return None, est


def main() -> None:
    rows = []
    for line in SRC.read_text(encoding="latin-1").splitlines():
        if len(line) < 130 or line[0] not in "01 " or not line[9:14].strip():
            continue
        try:
            z = int(line[9:14])
            a = int(line[14:19])
        except ValueError:
            continue

        el = line[20:23].strip()
        if not el.isalpha():
            continue

        mass_exc, est_mass = _f(line[28:42])
        dmass_exc, _ = _f(line[42:54])
        bind_a, _ = _f(line[54:67])
        beta_e, _ = _f(line[81:94])
        beta_kind = line[79:81].strip()

        raw_atom = line[106:109].strip() + line[110:123].strip()
        atom_u, _ = _f(raw_atom)
        atom_u = atom_u / 1e6 if atom_u is not None else None
        datom_u, _ = _f(line[123:135])

        if atom_u is None and mass_exc is not None:
            atom_u = a + mass_exc / U_KEV        # 兜底：由质量过剩换算

        rows.append({
            "z": z, "sym": el, "A": a,
            "质量过剩_keV": mass_exc, "质量过剩误差_keV": dmass_exc,
            "每核子结合能_keV": bind_a,
            "beta衰变能_keV": beta_e, "beta类型": beta_kind,
            "原子质量_u": atom_u,
            "原子质量误差_u": datom_u / 1e6 if datom_u is not None else None,
            "非实验值": "是" if est_mass else "",
        })

    df = pd.DataFrame(rows).drop_duplicates(subset=["z", "A"], keep="first")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    n_est = int((df["非实验值"] == "是").sum())
    print(f"rows={len(df)}  元素={df['sym'].nunique()}  其中外推值={n_est}")
    for name in ("1H", "12C", "56Fe", "208Pb", "238U"):
        r = df[(df["sym"] == re.sub(r"^\d+", "", name)) & (df["A"] == int(re.sub(r"\D", "", name)))]
        if len(r):
            x = r.iloc[0]
            print(f"  {name:>6}  质量过剩={x['质量过剩_keV']:>12.6f} keV   原子质量={x['原子质量_u']:.9f} u")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
