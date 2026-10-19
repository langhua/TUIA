"""把 NIST 汇编的原子质量与 AME2020 原表对账。

产出：
- data/processed/ame_vs_nist.csv   逐条对照（按 (Z, A) 连接）
- 控制台摘要

口径：1 u = 931 494.10242 keV。NIST 的 `mass_u` 是它自己从某版评估表转来的，
对中子滴附近的部分核素已经过时，差别可达几个 MeV；AME2020 是权威原件。
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
U_KEV = 931494.10242


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    nist = pd.read_csv(PROC / "nist_all.csv")
    ame = pd.read_csv(PROC / "ame2020.csv", encoding="utf-8-sig")
    m = nist[["z", "sym", "A", "mass_u"]].merge(
        ame[["z", "A", "原子质量_u", "质量过剩_keV", "非实验值"]], on=["z", "A"],
        how="outer", indicator=True)

    both = m[m["_merge"] == "both"].copy()
    both["差_u"] = both["mass_u"] - both["原子质量_u"]
    both["差_keV"] = both["差_u"] * U_KEV
    both["判定"] = "一致"
    both.loc[both["差_u"].abs() > 1e-6, "判定"] = "舍入级差异"
    both.loc[both["差_u"].abs() > 1e-4, "判定"] = "显著差异"

    out = both[["z", "sym", "A", "mass_u", "原子质量_u", "差_u", "差_keV", "判定"]] \
        .sort_values("差_u", key=lambda s: s.abs(), ascending=False)
    out.columns = ["Z", "元素", "A", "NIST_u", "AME2020_u", "差_u", "差_keV", "判定"]
    out.to_csv(PROC / "ame_vs_nist.csv", index=False, encoding="utf-8-sig")

    vc = both["判定"].value_counts()
    print(f"可比 {len(both)} 条；NIST 独有 {int((m['_merge'] == 'left_only').sum())}，"
          f"AME 独有 {int((m['_merge'] == 'right_only').sum())}")
    print("判定：" + " / ".join(f"{k} {v}" for k, v in vc.items()))
    print(f"差异中位数 {both['差_u'].abs().median():.2e} u，最大 {both['差_u'].abs().max():.3e} u")
    print("\n差异最大的 8 条：")
    print(out.head(8).to_string(index=False))
    print(f"\n-> {PROC / 'ame_vs_nist.csv'}")


if __name__ == "__main__":
    main()
