"""下载 ENDF/B-VIII.0 的逐点中子截面（JSON 镜像）。

数据来源：ENDF/B-VIII.0（NNDC），JSON 转录见
https://github.com/openmc-data-storage/ENDF-B-VIII.0-NNDC-json
（原始文件由 NNDC 发布；本仓只取做「增殖/嬗变」判断所需的那几个反应道）

每个文件形如 `U_238_ENDFB-8.0_n_102_294K.json`，字段：
    energy (eV) / cross section (barn) / MT reaction number / ...

MT 含义：2 弹性、16 (n,2n)、18 裂变、102 (n,γ)、103 (n,p)、105 (n,t)、107 (n,α)
（注意：⁶Li(n,α)³H 在 ENDF-6 里用的是 MT=105）

输出：data/raw/endf8/<Element>_<A>_n_<MT>.json（不入库）
"""

from __future__ import annotations

import pathlib
import ssl
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "endf8"
BASE = ("https://raw.githubusercontent.com/openmc-data-storage/"
        "ENDF-B-VIII.0-NNDC-json/main/json_files/")
UA = {"User-Agent": "Mozilla/5.0 (TUIA research)"}
CTX = ssl._create_unverified_context()

# (元素符号, 质量数, MT)
TARGETS: list[tuple[str, int, int]] = [
    # —— 增殖/转换链的上游（(n,γ)）——
    ("Th", 232, 102), ("Th", 230, 102),
    ("U", 234, 102), ("U", 236, 102), ("U", 238, 102),
    ("Np", 237, 102), ("Pu", 240, 102), ("Pu", 242, 102), ("Am", 241, 102),
    ("Cm", 244, 102),
    # —— 裂变核 ——（同时取裂变与俘获，才能算 α = σγ/σf）
    ("U", 233, 18), ("U", 235, 18), ("U", 238, 18),
    ("Pu", 239, 18), ("Pu", 241, 18),
    ("U", 233, 102), ("U", 235, 102), ("Pu", 239, 102), ("Pu", 241, 102),
    # —— 氚增殖与中子吸收 ——
    # 注意：⁶Li(n,α)³H 在 ENDF-6 里记在 **MT=105（n,t）**，不是 MT=107（该核素没有 107）。
    ("Li", 6, 105), ("B", 10, 107), ("He", 3, 103),
    ("Cd", 113, 102), ("Hf", 176, 102), ("Dy", 164, 102),
    # —— 嬗变靶（长寿命裂变产物）——
    ("Tc", 99, 102), ("I", 129, 102), ("Cs", 135, 102),
    ("Zr", 93, 102), ("Pd", 107, 102), ("Se", 79, 102),
    # —— 辐照源/工业 ——
    ("Co", 59, 102), ("Bi", 209, 102), ("W", 186, 102),
    # —— 校验用金标准：197Au 的 2200 m/s 俘获截面 = 98.65 b（中子通量监测的经典基准）——
    ("Au", 197, 102),
]


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    ok = skip = fail = 0
    for sym, a, mt in TARGETS:
        dest = RAW / f"{sym}_{a}_n_{mt}.json"
        if dest.exists() and dest.stat().st_size > 1000:
            skip += 1
            continue
        name = f"{sym}_{a}_ENDFB-8.0_n_{mt}_294K.json"
        try:
            req = urllib.request.Request(BASE + name, headers=UA)
            with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
                data = r.read()
            dest.write_bytes(data)
            ok += 1
            print(f"  {sym}-{a} MT={mt:3d}  {len(data) / 1024:8.0f} KB")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  {sym}-{a} MT={mt:3d}  失败 {type(e).__name__}: {str(e)[:60]}")
    print(f"下载 {ok}，已缓存 {skip}，失败 {fail} -> {RAW}")


if __name__ == "__main__":
    main()
