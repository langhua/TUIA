"""抓取并解析 Wikipedia "Isotopes of <element>" 页面，产出核素级基础数据。

输出：data/processed/isotopes_wiki.csv
列：z, sym, A, nuclide, half_life_text, half_life_s, decay_modes, daughters,
    spin, abundance_note, da_mass

数据来源：English Wikipedia, "Isotopes of <element>"（逐元素 118 页）
注意：Wikipedia 数据为二次汇编，权威原始来源为 NUBASE2020 / AME2020 / ENDF。
本脚本只做"抓取 + 结构化"，不做科学判断。
"""

from __future__ import annotations

import io
import pathlib
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from elements import ELEMENTS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "wiki"
OUT = ROOT / "data" / "processed" / "isotopes_wiki.csv"
CTX = ssl._create_unverified_context()
UA = {"User-Agent": "Mozilla/5.0 (TUIA dataset build; contact: local)"}

# ---------------------------------------------------------------- 半衰期解析

_TIME_UNITS = {
    "ys": 1e-24, "zs": 1e-21, "as": 1e-18, "fs": 1e-15, "ps": 1e-12,
    "ns": 1e-9, "us": 1e-6, "µs": 1e-6, "μs": 1e-6, "ms": 1e-3,
    "s": 1.0, "min": 60.0, "h": 3600.0, "d": 86400.0,
    "y": 3.155693e7, "a": 3.155693e7, "ky": 3.155693e10, "Ma": 3.155693e13,
    "Ga": 3.155693e16, "ka": 3.155693e10,
    "Ty": 3.155693e19, "Py": 3.155693e22, "Ey": 3.155693e25,
    "Zy": 3.155693e28, "Yy": 3.155693e31,
}


def parse_half_life(text: str) -> tuple[float | None, str]:
    """把 "5.70(3)×103 y" / "126.5(9) ms" / "Stable" / "< 30 ns" 解析成秒。

    返回 (秒, 归一化种类)。种类 ∈ {"stable", "value", "limit", "unknown"}。
    """
    if text is None:
        return None, "unknown"
    t = str(text).strip()
    if not t or t.lower() in {"nan", "—", "-"}:
        return None, "unknown"
    if "stable" in t.lower():
        return None, "stable"
    t = t.replace("\u00a0", " ").replace("\u2212", "-").replace("−", "-")
    # 去掉脚注 [n 3]、上标引用 [1]
    t = re.sub(r"\[[^\]]*\]", "", t)
    # 去掉不确定度括号。要**反复**剥：76Ge 写作
    # "2.022(0.018 (stat), 0.038 (sys))×1021 y"，一次替换会留下残渣，
    # 导致后面的 ×10^21 匹配不上（曾把 6.4e28 s 静默算成 6.4e7 s）。
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"\([^()]*\)", "", t)
    t = t.strip()
    # “2 ms#”“67 s?”：尾随的 # 是「由系统性估得」，? 是「待定」；
    # 不剔掉会让单位正则匹配失败、退回默认的 s —— 于是 2 ms 静默变成 2 s（差 1000 倍）。
    t = t.replace("#", " ").replace("?", " ").strip()
    limit = bool(re.match(r"^[<≤>≥]", t))
    t = t.lstrip("<≤>≥~≈ ").strip()

    m = re.search(r"([0-9]*\.?[0-9]+)", t)
    if not m:
        return None, "unknown"
    value = float(m.group(1))
    # 指数形式：×10 后面直接跟指数数字（HTML 上标被压平），可与系数分开出现
    exp = re.search(r"[×x]\s*10\s*\^?\s*(-?\d+)", t)
    if exp:
        value *= 10.0 ** int(exp.group(1))
    munit = re.search(r"([a-zA-Zµμ]+)\s*$", t)
    unit = munit.group(1) if munit else "s"
    if unit in _TIME_UNITS:
        value *= _TIME_UNITS[unit]
    elif unit.rstrip("s") in _TIME_UNITS:
        value *= _TIME_UNITS[unit.rstrip("s")]
    else:
        return None, "unknown"
    return value, ("limit" if limit else "value")


_NUC_CLEAN = re.compile(r"\[\s*n[^\]]*\]|\[[0-9]+\]|\s+")


def clean_nuclide(text: str) -> tuple[int, str, bool] | None:
    """'11 C[n 8]' -> (11, 'C', False)；'235m U' -> (235, 'U', True)"""
    if text is None:
        return None
    t = _NUC_CLEAN.sub("", str(text))
    m = re.match(r"^(\d+)m?([A-Za-z]{1,2})$", t)
    if not m:
        return None
    return int(m.group(1)), m.group(2), bool(re.match(r"^\d+m", t))


def norm_sym(sym: str, z: int) -> str:
    return ELEMENTS[z - 1].sym


# ---------------------------------------------------------------- 抓取

def fetch(page: str) -> str:
    path = CACHE / (page.replace(" ", "_") + ".html")
    rest = CACHE / (page.replace(" ", "_") + ".rest.html")
    if rest.exists() and rest.stat().st_size > 20000:
        return rest.read_text(encoding="utf-8", errors="replace")
    if path.exists() and path.stat().st_size > 20000:
        return path.read_text(encoding="utf-8", errors="replace")
    url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(page.replace(" ", "_"))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90, context=CTX) as resp:
        html = resp.read().decode("utf-8", "replace")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    time.sleep(0.4)
    return html


def flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [" | ".join(str(y) for y in c) if isinstance(c, tuple) else str(c)
                  for c in df.columns]
    return df


def pick_col(cols: list[str], *keys: str) -> str | None:
    for c in cols:
        low = c.lower()
        if all(k.lower() in low for k in keys):
            return c
    return None


def parse_element(el) -> list[dict]:
    try:
        html = fetch(f"Isotopes of {el.en.lower()}")
    except Exception as exc:  # noqa: BLE001
        print(f"  !! fetch failed {el.sym}: {exc}")
        return []
    # 个别页面（如 Np）存在 rowspan=3" 这类残缺属性，先做无害修补
    html = re.sub(r'((?:row|col)span)\s*=\s*(\d{1,3})"', r'\1="\2"', html)

    tables = None
    for flavor in ("lxml", "html5lib", "bs4"):
        try:
            tables = pd.read_html(io.StringIO(html), flavor=flavor) if flavor != "bs4" \
                else pd.read_html(io.StringIO(html))
            break
        except Exception:  # noqa: BLE001
            continue
    if tables is None:
        # 最后兜底：去掉所有 rowspan / colspan（合并单元格展开成重复值，对本用途无害）
        html2 = re.sub(r"""(?:row|col)span\s*=\s*["']?\d{1,3}[^"\s>]*""", "", html)
        try:
            tables = pd.read_html(io.StringIO(html2), flavor="lxml")
        except Exception:  # noqa: BLE001
            tables = None
    if tables is None:
        print(f"  !! parse failed {el.sym}")
        return []

    target = None
    for tab in tables:
        tab = flatten_cols(tab)
        if pick_col(list(tab.columns), "nuclide") and pick_col(list(tab.columns), "half-life"):
            target = tab
            break
    if target is None:
        print(f"  !! no isotope table {el.sym}")
        return []

    cols = list(target.columns)
    c_nuc = pick_col(cols, "nuclide")
    c_hl = pick_col(cols, "half-life")
    c_mode = pick_col(cols, "decay")
    c_dau = pick_col(cols, "daughter")
    c_spin = pick_col(cols, "spin")
    c_ab = pick_col(cols, "normal proportion")
    c_mass = pick_col(cols, "isotopic mass")

    recs: dict[int, dict] = {}
    for _, row in target.iterrows():
        parsed = clean_nuclide(row.get(c_nuc))
        if not parsed:
            continue
        a, sym, is_meta = parsed
        if a < el.z or a > 3 * el.z + 10:
            continue
        if is_meta and a in recs:
            continue  # 同质异能态：只保留基态（表中基态在前）
        hl_text = str(row.get(c_hl, "")).strip()
        hl_s, hl_kind = parse_half_life(hl_text)
        mode = "" if pd.isna(row.get(c_mode)) else str(row.get(c_mode)).strip()
        dau = "" if c_dau is None or pd.isna(row.get(c_dau)) else str(row.get(c_dau)).strip()
        spin = "" if c_spin is None or pd.isna(row.get(c_spin)) else str(row.get(c_spin)).strip()
        ab = "" if c_ab is None or pd.isna(row.get(c_ab)) else str(row.get(c_ab)).strip()
        mass = "" if c_mass is None or pd.isna(row.get(c_mass)) else str(row.get(c_mass)).strip()

        cur = recs.get(a)
        if cur is None:
            recs[a] = {
                "z": el.z, "sym": el.sym, "A": a, "nuclide": f"{a}{el.sym}",
                "half_life_text": hl_text if hl_kind != "unknown" else "",
                "half_life_s": hl_s, "half_life_kind": hl_kind,
                "decay_modes": [mode] if mode else [],
                "daughters": [dau] if dau else [],
                "spin": spin, "abundance_note": ab, "mass_text": mass,
            }
        else:
            if mode and mode not in cur["decay_modes"]:
                cur["decay_modes"].append(mode)
            if dau and dau not in cur["daughters"]:
                cur["daughters"].append(dau)
            if not cur["spin"] and spin:
                cur["spin"] = spin
            if not cur["abundance_note"] and ab:
                cur["abundance_note"] = ab
            if not cur["half_life_text"] and hl_kind != "unknown":
                cur["half_life_text"] = hl_text
                cur["half_life_s"] = hl_s
                cur["half_life_kind"] = hl_kind

    out = []
    for a in sorted(recs):
        r = recs[a]
        r["decay_modes"] = "; ".join(x for x in r["decay_modes"] if x)
        r["daughters"] = "; ".join(sorted({x for x in r["daughters"] if x}))
        out.append(r)
    return out


def main() -> None:
    todo = list(ELEMENTS)
    if len(sys.argv) > 1 and sys.argv[1] != "all":
        wanted = {int(x) for x in sys.argv[1].split(",")}
        todo = [e for e in ELEMENTS if e.z in wanted]
    rows: list[dict] = []
    for el in todo:
        got = parse_element(el)
        rows.extend(got)
        print(f"{el.z:3d} {el.sym:3s} {len(got):3d} nuclides")
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        print("!! no rows parsed, keep old file")
        return
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\nrows={len(df)} -> {OUT}")
    print(df["half_life_kind"].value_counts().to_string())


if __name__ == "__main__":
    main()
