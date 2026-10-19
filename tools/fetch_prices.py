"""抓 EIA 铀市场年报的原始 XLSX —— 本仓唯一能拿到的「实测成交价」。

来源：U.S. EIA，Uranium Marketing Annual Report（Form EIA-858，每年 7 月发布）
    https://www.eia.gov/uranium/marketing/

取三个表：
    Table S1b  2003–2025 年 U3O8e 加权平均价（含现货 / 长协分列）
    Table S2   2003–2025 年浓缩服务价（US$ / SWU）
    Table 4    2025 年按物料形态（U3O8 / 天然 UF6 / 浓缩 UF6）分列的加权平均价

为什么用它：这是**采购方申报的成交价**，不是供应商报价单，也不是估算；
公开、逐年更新、能机器解析。核素级的报价单（NIDC/Sigma/BuyIsotope/Trace Sciences）
全部是「询价制」，页面上没有价（见 tools/price_check.py 的 SOURCES 核查记录）。

用法：python tools/fetch_prices.py
输出：data/raw/eia/*.xlsx（data/raw/ 不入库，可随时重抓）
"""

from __future__ import annotations

import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "eia"
BASE = "https://www.eia.gov/uranium/marketing/xls/"
UA = {"User-Agent": "Mozilla/5.0 (TUIA research)"}

FILES = [
    ("umartableS1bfigureS2.xlsx", "U3O8e 加权平均价 2003–2025"),
    ("umartableS2figuresS3n4.xlsx", "浓缩服务 US$/SWU 2003–2025"),
    ("umartable4figure6.xlsx", "2025 年按物料形态的成交价"),
]


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, what in FILES:
        dest = RAW / name
        if dest.exists() and dest.stat().st_size > 5000:
            print(f"  已缓存 {name}  ({dest.stat().st_size / 1024:.0f} KB)")
            continue
        req = urllib.request.Request(BASE + name, headers=UA)
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
        dest.write_bytes(data)
        print(f"  {what}\n    -> {name}  {len(data) / 1024:.0f} KB")
    print(f"完成 -> {RAW}")


if __name__ == "__main__":
    main()
