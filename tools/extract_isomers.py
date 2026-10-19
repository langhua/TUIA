"""从已缓存的 Wikipedia 同位素表里抽出**同质异能态**（m-state）。

主表 05_同位素全景 只含基态核素；核医学与精密测量里最关键的几个核素
（99mTc、229mTh、178m2Hf、111mIn、137mBa…）都是激发态，单独成表。

输出：data/processed/tuia_isomers.csv
"""

from __future__ import annotations

import io
import pathlib
import re
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from elements import ELEMENTS  # noqa: E402
from fetch_wiki import (CACHE, flatten_cols, parse_half_life, pick_col,  # noqa: E402
                        fetch)

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "tuia_isomers.csv"

ISO_RE = re.compile(r"^(\d+)(m\d*)?([A-Za-z]{1,2})$")
CLEAN_RE = re.compile(r"\[\s*n[^\]]*\]|\[[0-9]+\]|\s+")


def parse_cell(text):
    """'99m Tc[n 3]' -> (99, 'm', 'Tc')；非异构体返回 None。"""
    if text is None:
        return None
    t = CLEAN_RE.sub("", str(text))
    m = ISO_RE.match(t)
    if not m:
        return None
    a, meta, sym = m.group(1), m.group(2), m.group(3)
    if not meta:
        return None
    return int(a), meta, sym


def main() -> None:
    rows: list[dict] = []
    for el in ELEMENTS:
        page = f"Isotopes of {el.en.lower()}"
        path = CACHE / (page.replace(" ", "_") + ".rest.html")
        if not path.exists():
            path = CACHE / (page.replace(" ", "_") + ".html")
        if not path.exists():
            continue
        html = fetch(page)
        # 维基的 span 属性偶有畸形（如 rowspan=3"），统一规范化；否则 pandas 会抛错、
        # 落到下面"整段剥掉 span"的兜底分支 —— 那会让 Np 这类表的列整体错位。
        html = re.sub(r'(rowspan|colspan)\s*=\s*["\']?\s*(\d+)\s*["\']?', r'\1="\2"', html)
        try:
            tables = pd.read_html(io.StringIO(html), flavor="lxml")
        except Exception:  # noqa: BLE001
            html2 = re.sub(r"""(?:row|col)span\s*=\s*["']?\d{1,3}[^"\s>]*""", "", html)
            try:
                tables = pd.read_html(io.StringIO(html2), flavor="lxml")
            except Exception:  # noqa: BLE001
                continue

        target = None
        for tab in tables:
            tab = flatten_cols(tab)
            if pick_col(list(tab.columns), "nuclide") and \
                    pick_col(list(tab.columns), "half-life"):
                target = tab
                break
        if target is None:
            continue

        cols = list(target.columns)
        c_nuc = pick_col(cols, "nuclide")
        c_hl = pick_col(cols, "half-life")
        c_mode = pick_col(cols, "decay")
        c_spin = pick_col(cols, "spin")

        agg: dict[tuple[int, str], dict] = {}
        for _, row in target.iterrows():
            parsed = parse_cell(row.get(c_nuc))
            if not parsed:
                continue
            a, meta, _sym = parsed
            if a < el.z or a > 3 * el.z + 10:
                continue
            hl_text = "" if pd.isna(row.get(c_hl)) else str(row.get(c_hl)).strip()
            hl_s, kind = parse_half_life(hl_text)
            mode = "" if pd.isna(row.get(c_mode)) else str(row.get(c_mode)).strip()
            spin = "" if c_spin is None or pd.isna(row.get(c_spin)) else str(row.get(c_spin)).strip()
            key = (a, meta)
            cur = agg.get(key)
            if cur is None:
                agg[key] = {
                    "z": el.z, "sym": el.sym, "cn": el.cn, "A": a, "meta": meta,
                    "isotope": f"{a}{meta}{el.sym}",
                    "half_life_text": hl_text if kind != "unknown" else "",
                    "half_life_s": hl_s, "half_life_kind": kind,
                    "decay_modes": [mode] if mode else [],
                    "spin": spin,
                }
            else:
                if mode and mode not in cur["decay_modes"]:
                    cur["decay_modes"].append(mode)
                if not cur["spin"] and spin:
                    cur["spin"] = spin
                if not cur["half_life_text"] and kind != "unknown":
                    cur["half_life_text"] = hl_text
                    cur["half_life_s"] = hl_s
                    cur["half_life_kind"] = kind

        for key in sorted(agg, key=lambda k: (k[0], k[1])):
            r = agg[key]
            r["decay_modes"] = "; ".join(x for x in r["decay_modes"] if x)
            rows.append(r)

    df = pd.DataFrame(rows).drop_duplicates(subset=["sym", "A", "meta"])
    df["半衰期"] = [
        "稳定" if k == "stable" else (re.sub(r"[×x]10(\d+)", r"×10^\1", str(t)).strip()
                                      if isinstance(t, str) and t else "—")
        for t, k in zip(df["half_life_text"], df["half_life_kind"])
    ]
    df["半衰期"] = [str(x).replace("\u00a0", " ") for x in df["半衰期"]]
    df["decay_modes"] = [str(x).replace("\u00a0", " ") for x in df["decay_modes"]]
    df["decay_modes"] = [("—" if x.strip() in ("", "nan", "None") else x) for x in df["decay_modes"]]
    df["spin"] = [("—" if str(x).strip() in ("", "nan", "None") else str(x)) for x in df["spin"]]
    # 维基单元格里的引用标记（如 “7(1) µs[15]”、“177.25(7) d[4]”）不影响数值，清掉
    cite = re.compile(r"\[(?:[a-z] )?\d+\]")
    for col in ("半衰期", "decay_modes", "spin"):
        df[col] = [cite.sub("", str(x)).strip() for x in df[col]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"isomers={len(df)}  -> {OUT}")
    top = df.dropna(subset=["half_life_s"]).sort_values("half_life_s", ascending=False).head(8)
    print(top[["isotope", "half_life_text", "decay_modes", "spin"]].to_string(index=False))


if __name__ == "__main__":
    main()
