"""下载并解析 NIST "Atomic Weights and Isotopic Compositions"（全元素、含放射性核素）。

权威来源：NIST Physics Laboratory
  https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=&ascii=ascii2&isotype=all
本表给出：质量数、相对原子质量（AME2020 汇编）、同位素丰度、标准原子量。

输出：data/processed/nist_all.csv
"""

from __future__ import annotations

import pathlib
import re
import ssl
import sys
import urllib.request

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from elements import ELEMENTS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nist_all.html"
OUT = ROOT / "data" / "processed" / "nist_all.csv"
URL = ("https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl"
       "?ele=&ascii=ascii2&isotype=all")
CTX = ssl._create_unverified_context()


def fetch() -> str:
    if RAW.exists() and RAW.stat().st_size > 100000:
        return RAW.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180, context=CTX) as resp:
        html = resp.read().decode("utf-8", "replace")
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(html, encoding="utf-8")
    return html


def num(text: str) -> float | None:
    """'1.00782503223(9)' -> 1.00782503223；'[1.00784,1.00811]' -> None"""
    t = (text or "").strip()
    if not t or t.startswith("["):
        return None
    t = re.sub(r"\([^)]*\)$", "", t)
    try:
        return float(t)
    except ValueError:
        return None


def main() -> None:
    html = fetch()
    pre = re.findall(r"<pre>(.*?)</pre>", html, re.S)
    if not pre:
        raise SystemExit("找不到 <pre> 数据块")
    body = re.sub(r"<[^>]+>", "", pre[0])

    rows = []
    for block in body.split("Atomic Number = ")[1:]:
        rec = {}
        for line in ("Atomic Number = " + block).splitlines():
            if " = " in line:
                k, _, v = line.partition(" = ")
                rec[k.strip()] = v.strip()
        z = rec.get("Atomic Number", "")
        if not z.isdigit():
            continue
        z = int(z)
        sym_raw = rec.get("Atomic Symbol", "")
        a_raw = rec.get("Mass Number", "")
        if not a_raw.isdigit():
            continue
        sym = ELEMENTS[z - 1].sym  # D / T 归一到 H
        rows.append({
            "z": z,
            "sym": sym,
            "A": int(a_raw),
            "mass_u": num(rec.get("Relative Atomic Mass", "")),
            "abundance_frac": num(rec.get("Isotopic Composition", "")),
            "std_atomic_weight": rec.get("Standard Atomic Weight", ""),
            "nist_notes": rec.get("Notes", ""),
            "nist_symbol": sym_raw,
        })

    df = pd.DataFrame(rows).drop_duplicates(subset=["z", "A"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"rows={len(df)} elements={df.z.nunique()} -> {OUT}")
    print("abundance 非空:", df.abundance_frac.notna().sum(),
          "| mass 非空:", df.mass_u.notna().sum())


if __name__ == "__main__":
    main()
