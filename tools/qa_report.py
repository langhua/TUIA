"""人工复核：把关键切片导出为 UTF-8 文本，便于逐行检查。"""

from __future__ import annotations

import io
import pathlib
import sys

import pandas as pd

PROC = pathlib.Path("data/processed")
buf = io.StringIO()


def w(*args) -> None:
    print(*args, file=buf)
    print(file=buf)


nu = pd.read_csv(PROC / "tuia_nuclides.csv")
fo = pd.read_csv(PROC / "tuia_focus.csv")
el = pd.read_csv(PROC / "tuia_elements.csv")

w("=== 1. 焦点目录 Top 20 ===")
w(fo.head(20)[["isotope", "tags", "成本等级", "可得量级", "可及性评分",
               "可及性等级", "工艺类别"]].to_string(index=False))

w("=== 2. 焦点目录 Bottom 15 ===")
w(fo.tail(15)[["isotope", "tags", "成本等级", "可得量级", "可及性评分",
               "可及性等级", "工艺类别"]].to_string(index=False))

w("=== 3. 指定核素核对 ===")
want = ["12C", "13C", "14N", "15N", "28Si", "29Si", "3He", "4He", "2H", "3H",
        "225Ac", "252Cf", "238Pu", "235U", "238U", "60Co", "177Lu", "157Gd",
        "76Ge", "136Xe", "87Sr", "171Yb", "229Th", "211At"]
sub = fo[fo["isotope"].isin(want)][
    ["isotope", "天然丰度%", "半衰期", "自旋", "稳定性", "A1", "A2", "A3",
     "A4", "A5", "A6", "A7", "可及性评分", "可及性等级", "再生性"]]
w(sub.sort_values("可及性评分", ascending=False).to_string(index=False))

w("=== 4. 元素表抽样 ===")
w(el[el["元素"].isin(["H", "C", "N", "O", "Si", "P", "Fe", "Gd", "U", "Cf", "Og"])].to_string(index=False))

w("=== 5. 缺失与分布检查 ===")
w("焦点行数:", len(fo))
w("评分缺失:", int(fo["可及性评分"].isna().sum()))
w("路线缺失:", int(fo["route"].isna().sum()))
w("等级分布:")
w(fo["可及性等级"].value_counts().to_string())
w("再生性分布（全表）:")
w(nu["再生性"].value_counts().to_string())
w("稳定性分布（全表）:")
w(nu["稳定性"].value_counts().to_string())
w("自旋为零计数:", int((nu["自旋"].astype(str).str.startswith("0")).sum()))
w("全表评分区间:", float(nu["可及性评分"].min()), "-", float(nu["可及性评分"].max()))

w("=== 6. 元素可及性跨度 Top 12 ===")
w(el.sort_values("可及性跨度", ascending=False)
  .head(12)[["元素", "中文", "元素可及性评分", "元素可及性等级", "可及性跨度",
             "最佳可及同位素"]].to_string(index=False))

w("=== 7. 衰变模式抽样（应无 [n x] 与 Stable） ===")
w(nu[nu["isotope"].isin(["1H", "12C", "14C", "235U", "3H", "60Co"])][
    ["isotope", "半衰期", "decay_modes", "daughters"]].to_string(index=False))

pathlib.Path("review.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written review.txt", len(buf.getvalue()))
