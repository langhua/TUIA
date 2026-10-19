"""把 TUIA 现有（维基来源）的基态核素数据与 NUBASE2020 对账。

产出：
- data/processed/nubase_vs_wiki.csv  逐条对照（基态，按 (Z, A) 连接）
- 控制台摘要：覆盖率、半衰期一致率、分歧最大者

口径：
- 只比基态（NUBASE idx=0）；激发态在两边的收录范围不同（维基 2050 条 vs NUBASE 1841 条），
  不能一一对应，故只统计条数，不做逐条比对。
- 半衰期比值用 log10 差；|Δlog10| ≤ 0.02（≈5%）记为"一致"。
"""

from __future__ import annotations

import math
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    wiki = pd.read_csv(PROC / "tuia_nuclides.csv", encoding="utf-8-sig")
    nb = pd.read_csv(PROC / "nubase2020.csv", encoding="utf-8-sig")
    iso = pd.read_csv(PROC / "tuia_isomers.csv", encoding="utf-8-sig")

    gs = nb[nb["idx"] == 0][["z", "A", "核素", "半衰期_s", "半衰期类型", "Jpi",
                             "激发能_keV", "衰变与丰度", "质量外推"]].rename(
        columns={"核素": "NUBASE核素", "半衰期_s": "NUBASE半衰期_s",
                 "半衰期类型": "NUBASE半衰期类型", "Jpi": "NUBASE_Jpi",
                 "激发能_keV": "NUBASE激发能_keV",
                 "衰变与丰度": "NUBASE衰变与丰度", "质量外推": "NUBASE质量外推"})
    m = wiki.merge(gs, on=["z", "A"], how="outer", indicator=True)

    both = m[m["_merge"] == "both"]
    only_wiki = m[m["_merge"] == "left_only"]
    only_nb = m[m["_merge"] == "right_only"]

    cmp = both.dropna(subset=["half_life_s", "NUBASE半衰期_s"]).copy()
    cmp["比值"] = cmp["half_life_s"] / cmp["NUBASE半衰期_s"]
    cmp["log10差"] = cmp["比值"].apply(lambda x: math.log10(x) if x and x > 0 else None)
    cmp["判定"] = "一致"
    cmp.loc[cmp["log10差"].abs() > 0.02, "判定"] = "有差异"
    cmp.loc[cmp["log10差"].abs() > 0.3, "判定"] = "显著分歧"

    out = cmp[["z", "sym", "A", "NUBASE核素", "半衰期", "half_life_s",
               "NUBASE半衰期_s", "比值", "log10差", "判定"]].copy()
    out.columns = ["Z", "元素", "A", "核素", "维基半衰期", "维基_秒",
                   "NUBASE_秒", "比值", "log10差", "判定"]
    out = out.sort_values("log10差", key=lambda s: s.abs(), ascending=False)
    out.to_csv(PROC / "nubase_vs_wiki.csv", index=False, encoding="utf-8-sig")

    n = len(cmp)
    print(f"维基基态 {len(wiki)} 条 / NUBASE 基态 {len(gs)} 条 / 双方都有 {len(both)} 条")
    print(f"仅维基 {len(only_wiki)} 条，仅 NUBASE {len(only_nb)} 条")
    print(f"可比半衰期 {n} 条：" + " / ".join(
        f"{k} {v}" for k, v in cmp["判定"].value_counts().items()))
    print(f"激发态条数：维基 {len(iso)} vs NUBASE {(nb['idx'] > 0).sum()}")
    print("NUBASE 激发态构成：" + " / ".join(
        f"{k} {v}" for k, v in nb.loc[nb["idx"] > 0, "态"].value_counts().items()))
    print("\n分歧最大 10 条：")
    print(out.head(10).to_string(index=False))
    print(f"\n-> {PROC / 'nubase_vs_wiki.csv'}")


if __name__ == "__main__":
    main()
