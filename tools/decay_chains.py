"""用 NUBASE2020 的衰变分支推出**子体**，再拼成衰变链与「发生器」对。

为什么值得单独做：
- 06_可及性目录 里讲的「99Mo/99mTc 发生器」「68Ge/68Ga」「82Sr/82Rb」本质上是
  **母体半衰期远长于子体**的一条衰变边；这层关系在表里以前只有人工写的一句话，
  现在可以由 BR 列算出来，并可批量筛查还有哪些核素具备同样的条件。
- 09_再生闭环 的「回炉」判断也能用真实子体核对，而不是只看路线文字。

子体规则（只按核反应守恒记账，不涉及分支竞争）：
    β−       → Z+1, A 不变        β+ / EC  → Z−1, A 不变
    α        → Z−2, A−4         IT       → 同核素落基态（不算换核素）
    β−n      → Z+1, A−1        β+ p     → Z−2, A−1
    n        → Z,   A−1        p        → Z−1, A−1
    2β−      → Z+2, A 不变      2n       → Z,   A−2
    簇放射   → 减去该簇（¹⁴C → Z−6, A−14；²⁴Ne → Z−10, A−24 …）
    SF       → 分裂碎片不唯一，不连边

输出：data/processed/decay_chains.csv（每个核素的主导边 + 链长）
      data/processed/decay_graph.csv（逐条边：母体 → 子体）
"""

from __future__ import annotations

import pathlib
import re
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from elements import BY_Z  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT_EDGES = PROC / "decay_graph.csv"
OUT_CHAINS = PROC / "decay_chains.csv"

# 模式代码 -> (dZ, dA, 中文标签)；None 表示不连边
DELTA: dict[str, tuple[int, int, str] | None] = {
    "B-": (1, 0, "β−"), "B+": (-1, 0, "β+"), "EC": (-1, 0, "EC"),
    "EC+B+": (-1, 0, "EC+β+"), "e+": (-1, 0, "e+"),
    "A": (-2, -4, "α"), "IT": None, "SF": None,
    "n": (0, -1, "n"), "2n": (0, -2, "2n"), "3n": (0, -3, "3n"),
    "p": (-1, -1, "p"), "2p": (-2, -2, "2p"), "3p": (-3, -3, "3p"),
    "d": (-1, -2, "d"), "t": (-1, -3, "t"),
    "B-n": (1, -1, "β−n"), "B-2n": (1, -2, "β−2n"), "B-3n": (1, -3, "β−3n"),
    "B-4n": (1, -4, "β−4n"), "B+p": (-2, -1, "β+p"), "B+2p": (-3, -2, "β+2p"),
    "B+3p": (-4, -3, "β+3p"), "B-p": (0, -1, "β−p"),
    "B+A": (0, -4, "β−α"), "B-A": (0, -4, "β−α"),
    "B+SF": None, "B-SF": None, "B+pA": (-2, -5, "β+pα"),
    "B-d": (0, -2, "β−d"), "B-t": (0, -3, "β−t"),
    "2B-": (2, 0, "2β−"), "2B+": (-2, 0, "2β+"),
}
_CLUSTER = re.compile(r"^(\d{1,2})([A-Z][a-z]?)$")


def _cluster_delta(code: str) -> tuple[int, int, str] | None:
    m = _CLUSTER.match(code)
    if not m:
        return None
    a, sym = int(m.group(1)), m.group(2)
    z = next((e.z for e in BY_Z.values() if e.sym == sym), None)
    if z is None:
        return None
    return -z, -a, f"{a}{sym}"


def parse_branches(br: str) -> list[tuple[str, float | None, float | None]]:
    """BR -> [(模式标签, 分支百分比, dZ, dA)]；不连边的模式（IT/SF）也返回，便于统计。"""
    out = []
    for seg in str(br or "").split(";"):
        seg = seg.strip()
        if not seg or seg.startswith("IS="):
            continue
        m = re.match(r"^([A-Za-z0-9+\-]+)\s*(.*)$", seg)
        if not m:
            continue
        code, rest = m.group(1), m.group(2).strip().lstrip("=~ ").strip()
        pct = None
        if rest and not rest.startswith("?"):
            try:
                pct = float(rest.split()[0].replace("#", ""))
            except ValueError:
                pct = None
        d = DELTA.get(code, "missing")
        if d == "missing":
            d = _cluster_delta(code)
            if d is None:
                out.append((code, pct, None, None))
                continue
        if d is None:
            out.append((code, pct, None, None))     # IT / SF：不连边
        else:
            out.append((d[2], pct, d[0], d[1]))
    return out


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    nb = pd.read_csv(PROC / "nubase2020.csv", encoding="utf-8-sig")
    nb["核素"] = nb["核素"].astype(str)

    # 索引：基态 (z, A) -> 行（用 dict，避免 itertuples 把中文列名搞乱）
    gs_by_key = {(int(r["z"]), int(r["A"])): r
                 for r in nb[nb["idx"] == 0].to_dict("records")}

    edges = []
    for r in nb.to_dict("records"):
        for label, pct, dz, da in parse_branches(r["衰变与丰度"]):
            if dz is None:
                continue
            tz, ta = int(r["z"]) + dz, int(r["A"]) + da
            if ta < 1:
                continue
            tgt = gs_by_key.get((tz, ta))
            edges.append({
                "母体": r["核素"], "母体Z": int(r["z"]), "母体A": int(r["A"]),
                "母体半衰期_s": r["半衰期_s"],
                "模式": label, "分支%": pct,
                "子体Z": tz, "子体A": ta,
                "子体": tgt["核素"] if tgt is not None
                        else (f"{ta}{BY_Z[tz].sym}" if tz in BY_Z else ""),
                "子体在表中": "是" if tgt is not None else "否",
                "子体半衰期_s": tgt["半衰期_s"] if tgt is not None else None,
            })
    ed = pd.DataFrame(edges)
    ed.to_csv(OUT_EDGES, index=False, encoding="utf-8-sig")

    # 主导边：取分支最大的那条（没有百分比时按出现顺序）
    ed["_pct"] = ed["分支%"].fillna(0)
    main_edge = (ed.sort_values("_pct", ascending=False)
                   .drop_duplicates(subset=["母体"]))

    # 沿主导边走后继，算链长与链尾；遇到稳定核素或回头路就停
    nxt = {r["母体"]: r["子体"] for r in main_edge.to_dict("records") if r["子体"]}
    stable = {r["核素"] for r in nb.to_dict("records")
              if r["半衰期类型"] == "稳定"}

    def walk(node: str, limit: int = 20) -> tuple[int, list[str]]:
        seen, chain = {node}, [node]
        while len(chain) < limit and chain[-1] not in stable:
            n = nxt.get(chain[-1])
            if not n or n in seen:
                break
            seen.add(n)
            chain.append(n)
        return len(chain), chain

    # 06_可及性目录 里策展过的核素（用来判断子体“有没有用途”）
    curated = set(pd.read_csv(PROC / "tuia_focus.csv")["isotope"].astype(str)) \
        if (PROC / "tuia_focus.csv").exists() else set()

    rows = []
    for r in main_edge.to_dict("records"):
        ln, chain = walk(r["母体"])
        rows.append({
            "核素": r["母体"], "Z": r["母体Z"], "A": r["母体A"],
            "半衰期_s": r["母体半衰期_s"], "主导模式": r["模式"], "分支%": r["分支%"],
            "子体": r["子体"], "子体半衰期_s": r["子体半衰期_s"], "链长": ln,
            "链": " → ".join(chain),
            "子体已策展": "是" if r["子体"] in curated else "",
            "发生器候选": "", "母/子半衰期比": None, "平衡类型": "",
        })
    ch = pd.DataFrame(rows)

    # 「发生器」判据（不是只要母体比子体长寿就算）：
    #   ① 子体半衰期在 60 s – 30 d，即「洗脱出来能用」的窗口
    #   ② 母体半衰期在 1 d – 200 a，即「能长期供货」的窗口
    #   ③ 母/子半衰期比 ≥ 10（否则子体跟不上衰变、取不到活度）
    # 不筛的话排名会被 8Li→4Li（子体存活 9e-23 s）这种无意义对占据。
    D_MIN, D_MAX = 60.0, 30 * 86400.0
    P_MIN, P_MAX = 86400.0, 200 * 31557600.0
    for i, r in ch.iterrows():
        p, d = r["半衰期_s"], r["子体半衰期_s"]
        if pd.isna(p) or pd.isna(d) or d <= 0:
            continue
        ratio = p / d
        ch.at[i, "母/子半衰期比"] = round(ratio, 1)
        if D_MIN <= d <= D_MAX and P_MIN <= p <= P_MAX and ratio >= 10:
            ch.at[i, "发生器候选"] = "是"
            ch.at[i, "平衡类型"] = "长期平衡" if ratio >= 100 else "瞬时平衡"
    ch = ch.sort_values(["发生器候选", "母/子半衰期比"], ascending=[False, False])
    ch.to_csv(OUT_CHAINS, index=False, encoding="utf-8-sig")

    n_gen = int((ch["发生器候选"] == "是").sum())
    gen = ch[ch["发生器候选"] == "是"]
    long_chain = ch[ch["链长"] >= 5]
    print(f"衰变边 {len(ed)} 条（可确定子体）；核素 {len(ch)} 个有过继边")
    print(f"链长 ≥5 的核素 {len(long_chain)} 个；发生器候选 {n_gen} 个")
    print("\n链最长的 6 条：")
    print(long_chain.sort_values("链长", ascending=False)
          .head(6)[["核素", "半衰期_s", "链长", "链"]].to_string(index=False))
    print("\n发生器候选（按母/子半衰期比）：")
    print(gen.head(20)[["核素", "子体", "子体已策展", "半衰期_s", "子体半衰期_s",
                        "母/子半衰期比", "平衡类型"]].to_string(index=False))
    print(f"\n-> {OUT_EDGES}\n-> {OUT_CHAINS}")


if __name__ == "__main__":
    main()
