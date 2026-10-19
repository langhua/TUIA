"""抓 NUBASE2020 / AME2020 的 ASCII 原始表到 data/raw/amdc/。

来源：IAEA AMDC（https://www-nds.iaea.org/amdc/，AME2020 目录）
- nubase_4.mas20.txt : NUBASE2020 全表（质量、激发能、半衰期、自旋、衰变模式与分支）
- mass_1.mas20.txt   : AME2020 实验/外推原子质量

引用要求：使用者须引用 Chin. Phys. C 45 (2021) 030001（NUBASE2020）
与 030002/030003（AME2020），不得只引用电子文件。
"""
from __future__ import annotations

import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "amdc"
BASE = "https://www-nds.iaea.org/amdc/ame2020/"
FILES = ["nubase_4.mas20.txt", "mass_1.mas20.txt"]
UA = {"User-Agent": "Mozilla/5.0 (TUIA/0.1; research use)"}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = RAW / name
        if dest.exists() and dest.stat().st_size > 10_000:
            print(f"cached  {name} ({dest.stat().st_size} B)")
            continue
        req = urllib.request.Request(BASE + name, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        dest.write_bytes(data)
        print(f"fetched {name} ({len(data)} B)")


if __name__ == "__main__":
    main()
