"""把 TUIA 现有（维基来源）的核素数据与 NUBASE2020 对账。

产出：
- data/processed/nubase_vs_wiki.csv      基态逐条对照（按 (Z, A) 连接）
- data/processed/nubase_vs_isomers.csv   激发态（m 态）逐条对照
- 控制台摘要

口径：
- 基态：按 (Z, A) 直接连，比半衰期（log10 比值）。|Δlog10| ≤ 0.02（≈5%）记「一致」。
- 激发态：维基写 m / m1 / m2（第几个激发态），NUBASE 写 idx = 1,2,3…
  所以先按同号配对；NUBASE 的能级排序未必与维基一致，同号配不上时退一步
  在同一 (Z, A) 的激发态里找半衰期最接近的，并把结果记成「≈」。
"""

from __future__ import annotations

import math
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


def _meta_to_idx(meta: str) -> int:
    """维基的 m / m1 / m2 -> NUBASE 的激发态序号 1 / 1 / 2。"""
    m = str(meta).strip()
    if m == "m":
        return 1
    digits = m[1:]
    return int(digits) if digits.isdigit() else 1


def compare_isomers(iso: pd.DataFrame, nb: pd.DataFrame) -> pd.DataFrame:
    """激发态逐条对照；返回逐核素带判定的一行一核素表。"""
    fam: dict[tuple[int, int], list[tuple[int, float, float]]] = {}
    for _, r in nb[nb["idx"] > 0].iterrows():
        fam.setdefault((int(r["z"]), int(r["A"])), []).append(
            (int(r["idx"]), r["半衰期_s"], r["激发能_keV"]))

    rows = []
    for _, r in iso.iterrows():
        want = _meta_to_idx(r["meta"])
        cands = fam.get((int(r["z"]), int(r["A"])), [])
        ours = r["half_life_s"]
        pick = next((c for c in cands if c[0] == want), None)
        approx = ""
        if pick is None and cands:
            usable = [c for c in cands if pd.notna(c[1]) and c[1] > 0]
            if usable and pd.notna(ours) and ours > 0:
                pick = min(usable, key=lambda c: abs(math.log10(ours / c[1])))
            else:
                pick = cands[0]
            approx = "≈"

        if pick is None:
            verdict, theirs, exc = "NUBASE 无", None, None
        else:
            theirs, exc = pick[1], pick[2]
            if pd.isna(ours) or pd.isna(theirs) or ours <= 0 or theirs <= 0:
                verdict = "缺值"
            else:
                d = abs(math.log10(ours / theirs))
                verdict = "一致" if d <= 0.02 else ("近似" if d <= 0.3 else "差异")
                verdict += approx

        rows.append({
            "核素": r["isotope"], "z": int(r["z"]), "sym": r["sym"],
            "A": int(r["A"]), "meta": r["meta"], "idx": want,
            "维基半衰期": r["半衰期"], "维基_秒": ours,
            "NUBASE_秒": theirs, "NUBASE激发能_keV": exc, "判定": verdict,
        })
    return pd.DataFrame(rows)


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

    iso_cmp = compare_isomers(iso, nb)
    iso_cmp.to_csv(PROC / "nubase_vs_isomers.csv", index=False, encoding="utf-8-sig")
    n_iso_ok = int(iso_cmp["判定"].isin(["一致", "一致≈"]).sum())

    n = len(cmp)
    print(f"维基基态 {len(wiki)} 条 / NUBASE 基态 {len(gs)} 条 / 双方都有 {len(both)} 条")
    print(f"仅维基 {len(only_wiki)} 条，仅 NUBASE {len(only_nb)} 条")
    print(f"可比半衰期 {n} 条：" + " / ".join(
        f"{k} {v}" for k, v in cmp["判定"].value_counts().items()))
    print(f"激发态条数：维基 {len(iso)} vs NUBASE {(nb['idx'] > 0).sum()}")
    print("NUBASE 激发态构成：" + " / ".join(
        f"{k} {v}" for k, v in nb.loc[nb["idx"] > 0, "态"].value_counts().items()))
    print("  逐条判定：" + " / ".join(
        f"{k} {v}" for k, v in iso_cmp["判定"].value_counts().items()))
    print(f"  其中完全一致 {n_iso_ok} 条（{n_iso_ok / max(len(iso_cmp), 1):.1%}）")
    bad = iso_cmp[~iso_cmp["判定"].str.startswith(("一致", "缺值", "NUBASE"))]
    print(f"  对不上的 {len(bad)} 条，前 8 条：")
    print(bad.head(8).to_string(index=False))
    print("\n分歧最大 10 条：")
    print(out.head(10).to_string(index=False))
    print(f"\n-> {PROC / 'nubase_vs_wiki.csv'}")


if __name__ == "__main__":
    main()
