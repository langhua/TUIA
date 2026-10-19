"""合并 NIST + Wikipedia + 策展层，产出三张分析用数据表。

输出
----
data/processed/tuia_nuclides.csv   全部核素（约 3500 行，含推定评分）
data/processed/tuia_focus.csv      焦点目录（策展 200+ 核素，含完整评分）
data/processed/tuia_elements.csv   118 元素汇总
"""

from __future__ import annotations

import pathlib
import re
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from curation import CURATION, ISOMERS  # noqa: E402
from elements import BY_SYM, ELEMENTS  # noqa: E402
from supply import COUNTRIES, SUPPLY  # noqa: E402
from scoring import (METHOD_SCORE, TIER_SCORE, abundance_score, composite,  # noqa: E402
                     grade_of, method_from_route, method_from_text, quantity_score,
                     regen_class, regulatory_score, supply_score)

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT_ALL = PROC / "tuia_nuclides.csv"
OUT_FOCUS = PROC / "tuia_focus.csv"
OUT_ELEM = PROC / "tuia_elements.csv"
OUT_SUPPLY = PROC / "tuia_supply.csv"


def clean_jpi(text: str) -> str:
    """NUBASE 的 Jpi -> 表里的自旋。

    只做三件事：去掉尾部的 T=（同位旋）项、去掉 `*`（直接测量，属常态）、
    把 ASCII 负号换成真正的减号；`#`（系统性估计）**保留** —— 那是例外情况，
    抹掉就分不出「量过」和「估的」了。
    """
    t = str(text or "").strip()
    if not t or t.lower() in {"nan", "none"}:
        return ""
    t = t.split("T=")[0].strip()
    t = t.replace("*", "")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\(([^)]*?),\s+", r"(\1,", t)      # "(1−, 2−)" -> "(1−,2−)"
    return t.replace("-", "\u2212").strip()


def load_nubase_jpi() -> dict[tuple[int, int], str]:
    """基态 (z, A) -> NUBASE2020 的 Jpi。文件不存在时返回空表（降级到维基自旋）。"""
    path = PROC / "nubase2020.csv"
    if not path.exists():
        return {}
    nb = pd.read_csv(path, encoding="utf-8-sig")
    gs = nb[nb["idx"] == 0]
    return {(int(z), int(a)): clean_jpi(j)
            for z, a, j in zip(gs["z"], gs["A"], gs["Jpi"])}


# NUBASE 的衰变模式代码 -> 表里的写法
DECAY_MAP = {
    "B-": "β−", "B+": "β+", "B": "β", "EC": "EC", "EC+B+": "EC+β+",
    "A": "α", "IT": "IT", "SF": "SF", "n": "n", "p": "p",
    "2n": "2n", "3n": "3n", "2p": "2p", "3p": "3p", "d": "d", "t": "t", "e+": "e+",
    "B-n": "β−n", "B-2n": "β−2n", "B-3n": "β−3n", "B-4n": "β−4n",
    "B+p": "β+p", "B+2p": "β+2p", "B+3p": "β+3p", "B-p": "β−p",
    "B+A": "β−α", "B-A": "β−α", "B+SF": "β+SF", "B-SF": "β−SF",
    "B+pA": "β+pα", "B-d": "β−d", "B-t": "β−t",
    "2B-": "2β−", "2B+": "2β+",
}
# 重核簇放射：14C、24Ne、28Mg …
_CLUSTER = re.compile(r"^(\d{1,2})([A-Z][a-z]?)$")


def nubase_decay_modes(br) -> str:
    """NUBASE 的 BR 字段 -> 表里的衰变模式文本。

    源格式：“B-=100”、“A=97.5 3;B-=2.5 3”、“B- ?”、“A~7.7e-9#”、
    “B+p ?”、“IS=99.9855 78”。IS 是同位素丰度，不属于衰变模式，跳过。
    强度 ≥ 99.9% 的不写百分比（与维基口径的写法一致），其余照抄原值。
    """
    parts = []
    for seg in str(br or "").split(";"):
        seg = seg.strip()
        if not seg or seg.startswith("IS="):
            continue
        m = re.match(r"^([A-Za-z0-9+\-]+)\s*(.*)$", seg)
        if not m:
            continue
        code, rest = m.group(1), m.group(2).strip()
        sym = DECAY_MAP.get(code)
        if sym is None:
            cm = _CLUSTER.match(code)
            sym = f"{cm.group(1)}{cm.group(2)}" if cm else code
        rest = rest.lstrip("=~ ").strip()
        if not rest or rest.startswith("?"):
            parts.append(f"{sym} ?")
            continue
        val = rest.split()[0]
        if val in {"100", "100.0", "~100"}:
            parts.append(sym)
        else:
            parts.append(f"{sym} ({val}%)")
    return "; ".join(parts)


def load_nubase_decay() -> dict[tuple[int, int], str]:
    """基态 (z, A) -> NUBASE 的衰变模式文本；转换不出内容的条目不入表。"""
    path = PROC / "nubase2020.csv"
    if not path.exists():
        return {}
    nb = pd.read_csv(path, encoding="utf-8-sig")
    gs = nb[nb["idx"] == 0]
    out = {}
    for z, a, br in zip(gs["z"], gs["A"], gs["衰变与丰度"]):
        txt = nubase_decay_modes(br)
        if txt:
            out[(int(z), int(a))] = txt
    return out


def load_ame() -> dict[tuple[int, int], tuple]:
    """(z, A) -> (原子质量 u, 质量过剩 keV, 每核子结合能 keV)。"""
    path = PROC / "ame2020.csv"
    if not path.exists():
        return {}
    ame = pd.read_csv(path, encoding="utf-8-sig")
    return {(int(z), int(a)): (u, me, be)
            for z, a, u, me, be in zip(ame["z"], ame["A"], ame["原子质量_u"],
                                       ame["质量过剩_keV"], ame["每核子结合能_keV"])}


def fix_exponent(text: str) -> str:
    """'5.70×103 y' -> '5.70×10^3 y'，并清理不可见空格与脚注标记。"""
    t = str(text or "").replace("\u00a0", " ")
    t = re.sub(r"\[\s*n\s*\d+\s*\]|\[\d+\]", "", t)
    t = re.sub(r"[×x]10(\d+)", r"×10^\1", t)
    return re.sub(r"\s+", " ", t).strip()


def clean_chain(text) -> str:
    """衰变模式/子体文字清理：去脚注、去 Stable 占位。"""
    if not isinstance(text, str):
        return ""
    t = re.sub(r"\[\s*n\s*\d+\s*\]|\[\d+\]", "", text)
    parts = [p.strip() for p in t.split(";")]
    parts = [p for p in parts if p and p.lower() != "stable"]
    return "; ".join(parts)


def stability_of(kind: str, frac: float | None, hl_s: float | None) -> str:
    if kind == "stable":
        return "稳定"
    if frac is not None and frac > 0:
        return "原生放射性"
    if hl_s and hl_s > 3.15e7 * 1e8:
        return "长寿命放射性"
    return "放射性"


def score_row(row: dict) -> dict:
    z = row["z"]
    frac = row.get("abundance_frac")
    hl_kind = row.get("half_life_kind") or "unknown"
    stable = hl_kind == "stable"

    # ---- 工艺类别
    route = row.get("route")
    route = route if isinstance(route, str) else ""
    enrich_text = row.get("enrich_text")
    enrich_text = enrich_text if isinstance(enrich_text, str) else ""
    method = method_from_route(route) or method_from_text(enrich_text)
    if stable and not route:
        method = method_from_text(enrich_text)
    # 天然占比 ≥90% 的核素，推定行默认「无需富集」（策展行按其写明路线为准）
    if (not route and frac is not None and not pd.isna(frac) and frac >= 0.90
            and method != "无需富集"):
        method = "无需富集"

    a2, a7, purity_ceiling = METHOD_SCORE.get(method, (60, 80, "—"))

    # ---- 成本 / 量级
    tier = row.get("tier")
    if pd.isna(tier):
        if frac is None or pd.isna(frac):
            tier = 4                      # 人工核素：只按活度计
        elif frac >= 0.5:
            tier = 1                      # 天然主成分，按工业品买
        elif frac >= 0.01:
            tier = 2                      # 需中等富集
        elif frac >= 1e-4:
            tier = 3                      # 需大幅富集
        else:
            tier = 4
    tier = int(tier)

    qty = row.get("qty")
    if not isinstance(qty, str):
        if z >= 104:
            qty = "原子级"             # 超重元素：单原子合成，从来不是「可称量的物质」
        elif frac is None or pd.isna(frac):
            qty = "微克级"
        elif frac > 0.01:
            qty = "吨级"
        elif frac > 1e-4:
            qty = "公斤级"
        else:
            qty = "克级"

    subs = {
        "A1": round(abundance_score(frac), 1),
        "A2": a2,
        "A3": TIER_SCORE.get(tier, 20),
        "A4": quantity_score(qty),
        "A5": supply_score(qty, tier),
        "A6": regulatory_score(z, frac, tier),
        "A7": a7,
    }
    score = composite(subs)
    grade, grade_label = grade_of(score)
    out = dict(subs)
    out.update({
        "可及性评分": score,
        "可及性等级": grade,
        "等级含义": grade_label,
        "工艺类别": method,
        "纯度上限": purity_ceiling,
        "成本等级": tier,
        "可得量级": qty,
    })
    return out


def main() -> None:
    nist = pd.read_csv(PROC / "nist_all.csv")
    wiki = pd.read_csv(PROC / "isotopes_wiki.csv")
    wiki = wiki.rename(columns={"A": "A"})
    df = nist.merge(
        wiki[["z", "A", "half_life_text", "half_life_s", "half_life_kind",
              "decay_modes", "daughters", "spin", "mass_text"]],
        on=["z", "A"], how="outer",
    )
    df["sym"] = [ELEMENTS[int(z) - 1].sym for z in df.z]
    df["en"] = [ELEMENTS[int(z) - 1].en for z in df.z]
    df["cn"] = [ELEMENTS[int(z) - 1].cn for z in df.z]
    df["cat"] = [ELEMENTS[int(z) - 1].cat for z in df.z]
    df["enrich_text"] = [ELEMENTS[int(z) - 1].enrich for z in df.z]
    df["N"] = df["A"] - df["z"]
    df["isotope"] = df["A"].astype(int).astype(str) + df["sym"]

    # 策展层并表
    focus = pd.DataFrame(CURATION, columns=["sym", "A", "tags", "route", "tier", "qty", "note"])
    focus = focus.merge(
        pd.DataFrame([(e.sym, e.z, e.en, e.cn, e.cat, e.enrich) for e in ELEMENTS],
                    columns=["sym", "z", "en", "cn", "cat", "enrich_text"]),
        on="sym", how="left")
    focus["key"] = focus["sym"] + "-" + focus["A"].astype(int).astype(str)
    cur = focus.set_index("key")

    df["_key"] = df["sym"] + "-" + df["A"].astype(int).astype(str)
    df = df.merge(
        cur[["tags", "route", "tier", "qty", "note"]],
        left_on="_key", right_index=True, how="left",
    )
    df["策展"] = df["tags"].notna()

    # 逐行评分
    scored = [score_row(r) for r in df.to_dict("records")]
    df = pd.concat([df.reset_index(drop=True), pd.DataFrame(scored)], axis=1)

    df["稳定性"] = [
        stability_of(r.get("half_life_kind") or "unknown", r.get("abundance_frac"),
                     r.get("half_life_s"))
        for r in df.to_dict("records")
    ]
    df["再生性"] = [regen_class(r if isinstance(r, str) else "", s == "稳定")
                    for r, s in zip(df["route"], df["稳定性"])]

    df["半衰期"] = [
        "稳定" if k == "stable" else (fix_exponent(t) if isinstance(t, str) and t else "—")
        for t, k in zip(df["half_life_text"], df["half_life_kind"])
    ]
    df["天然丰度%"] = [None if pd.isna(f) else round(float(f) * 100, 6)
                       for f in df["abundance_frac"]]
    df["自旋.I"] = df["spin"].fillna("").replace({"nan": ""})
    # 自旋优先用 NUBASE2020 的 Jpi（评估值）；NUBASE 没收录的核素才回落到维基口径。
    jpi = load_nubase_jpi()
    df["自旋.I"] = [jpi.get((int(z), int(a))) or s
                 for z, a, s in zip(df["z"], df["A"], df["自旋.I"])]
    df["decay_modes"] = [clean_chain(t) for t in df["decay_modes"]]
    df["daughters"] = [clean_chain(t) for t in df["daughters"]]
    # 衰变模式（含分支强度）改用 NUBASE2020 的 BR 列；转不出内容的才保留维基口径。
    decay = load_nubase_decay()
    df["decay_modes"] = [decay.get((int(z), int(a))) or d
                        for z, a, d in zip(df["z"], df["A"], df["decay_modes"])]

    # 原子质量改用 AME2020（NIST 转发的那份对其中的 143 个核素已经过时），
    # 并补上质量过剩与每核子结合能 —— 这两个是新信息，表里以前没有。
    ame = load_ame()
    df["质量过剩_keV"] = [ame.get((int(z), int(a)), (None, None, None))[1]
                      for z, a in zip(df["z"], df["A"])]
    df["结合能每核子_keV"] = [ame.get((int(z), int(a)), (None, None, None))[2]
                        for z, a in zip(df["z"], df["A"])]
    df["mass_u"] = [ame[(int(z), int(a))][0] if ame.get((int(z), int(a)))
                    and ame[(int(z), int(a))][0] is not None else m
                    for z, a, m in zip(df["z"], df["A"], df["mass_u"])]

    # 自旋为零的标记（NV / 量子相关应用的关键判据）
    df["自旋"] = [
        "0（偶偶核，无核自旋）" if (int(z) % 2 == 0 and (int(a) - int(z)) % 2 == 0)
        else (s if isinstance(s, str) and s and s != "nan" else "—")
        for z, a, s in zip(df["z"], df["A"], df["自旋.I"])
    ]

    all_cols = [
        "z", "sym", "cn", "en", "cat", "isotope", "A", "N",
        "天然丰度%", "mass_u", "质量过剩_keV", "结合能每核子_keV",
        "半衰期", "half_life_s", "decay_modes", "daughters",
        "自旋", "稳定性", "再生性",
        "A1", "A2", "A3", "A4", "A5", "A6", "A7",
        "可及性评分", "可及性等级", "等级含义", "工艺类别", "纯度上限", "成本等级",
        "可得量级", "策展", "tags", "route", "note",
    ]
    allview = df[all_cols].sort_values(["z", "A"]).reset_index(drop=True)
    allview.to_csv(OUT_ALL, index=False, encoding="utf-8-sig")

    focus_out = allview[allview["策展"]].copy()
    focus_out = focus_out.sort_values(["z", "A"]).reset_index(drop=True)
    focus_out.to_csv(OUT_FOCUS, index=False, encoding="utf-8-sig")

    # ---------------- 元素汇总 ----------------
    rows = []
    for e in ELEMENTS:
        sub = allview[allview["z"] == e.z]
        stable = sub[sub["稳定性"] == "稳定"]
        radio = sub[sub["稳定性"] != "稳定"]
        best = None
        if len(sub):
            cand = sub.sort_values(["可及性评分", "策展", "A"],
                                   ascending=[False, False, False])
            best = cand.iloc[0]
        longest = None
        if len(radio):
            cand = radio.dropna(subset=["half_life_s"])
            if len(cand):
                longest = cand.sort_values("half_life_s", ascending=False).iloc[0]
        fracs = sub["天然丰度%"].dropna()
        rows.append({
            "Z": e.z, "元素": e.sym, "中文": e.cn, "英文": e.en, "类别": e.cat,
            "已知核素数": len(sub),
            "稳定同位素数": len(stable),
            "天然丰度范围%": (f"{fracs.min():.4g} – {fracs.max():.4g}" if len(fracs) else "—"),
            "最长寿命同位素": (longest["isotope"] if longest is not None else "—"),
            "最长寿命": (longest["半衰期"] if longest is not None else "—"),
            "最佳可及同位素": (best["isotope"] if best is not None else "—"),
            "最佳可及来源": ("策展" if best is not None and bool(best["策展"]) else "推定"),
            "元素可及性评分": (best["可及性评分"] if best is not None else 0),
            "元素可及性等级": (best["可及性等级"] if best is not None else "E"),
            "可及性跨度": (round(sub["可及性评分"].max() - sub["可及性评分"].min(), 1)
                           if len(sub) else 0),
            "主流富集工艺": e.enrich,
        })
    pd.DataFrame(rows).to_csv(OUT_ELEM, index=False, encoding="utf-8-sig")

    # ---------------- 分离产业国 ----------------
    sup_rows = []
    for sym, (codes, level, note) in SUPPLY.items():
        e = BY_SYM[sym]
        sup_rows.append({
            "Z": e.z, "元素": sym, "中文": e.cn, "英文": e.en,
            "供应国数": len(codes),
            "供应国": "、".join(COUNTRIES.get(c, c) for c in codes),
            "国家码": " ".join(codes),
            "置信度": level,
            "主流分离工艺": e.enrich,
            "说明": note,
        })
    pd.DataFrame(sup_rows).sort_values("Z").to_csv(
        OUT_SUPPLY, index=False, encoding="utf-8-sig")

    print(f"nuclides={len(allview)} focus={len(focus_out)} elements={len(rows)} "
          f"supply={len(sup_rows)}")
    print(allview["可及性等级"].value_counts().to_string())


if __name__ == "__main__":
    main()
