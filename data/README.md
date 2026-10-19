# 数据目录索引

`data/processed/` 下的 CSV 都是**可从公开数据源重新生成**的中间产物，已入库，
方便不开脚本也能核数。`data/raw/` 是抓下来的原始文件（不进版本库，用 fetch 脚本重抓）。

每个文件都是 UTF-8 with BOM（Excel 直接打开不乱码），第一行是表头。

## 基础核数据

| 文件 | 行数 | 内容 | 来源 | 生成脚本 |
|---|---|---|---|---|
| `nist_all.csv` | ~3 600 | 原子序数、质量数、原子质量、天然丰度 | NIST Atomic Weights and Isotopic Compositions | `fetch_nist.py` |
| `isotopes_wiki.csv` | ~3 500 | 半衰期、衰变模式、子体、自旋 | Wikipedia「Isotopes of *X*」118 页 | `fetch_wiki.py` |
| `nubase2020.csv` | 5 843 | NUBASE2020 全表（含 2 285 条激发态）：质量过剩、激发能、半衰期、Jpi、衰变分支 | IAEA/AMDC `nubase_4.mas20.txt` | `fetch_nubase.py` + `parse_nubase.py` |
| `ame2020.csv` | 2 550 | AME2020 原子质量、质量过剩、每核子结合能 | IAEA/AMDC `mass_1.mas20.txt` | `fetch_nubase.py` + `parse_ame.py` |

## 合并与评分

| 文件 | 行数 | 内容 |
|---|---|---|
| `tuia_nuclides.csv` | 3 600 | **全库主表**：核数据 + 七维评分（A1–A7）+ 可及性评分/等级 + 成本层级 + 可得量级 + 再生性 + 策展标记 |
| `tuia_focus.csv` | 234 | 人工策展目录（用途标签、路线、成本、量级、要点） |
| `tuia_elements.csv` | 118 | 元素级汇总：核素数、稳定数、原生放射性数、最佳可及核素、可及性跨度 |
| `tuia_supply.csv` | 59 | 稳定同位素分离产业所在国与置信度 |
| `tuia_isomers.csv` | 2 050 | 同质异能态单表（半衰期、衰变模式、自旋、能级标记） |

## 对账（QA）

| 文件 | 行数 | 内容 |
|---|---|---|
| `nubase_vs_wiki.csv` | 3 099 | 基态半衰期逐条对账（一致 2 932 / 有差异 107 / 显著分歧 60） |
| `nubase_vs_isomers.csv` | 2 050 | 激发态逐条对账（一致 1 823 / 差异 56 / NUBASE 无 35 / 缺值 104） |
| `ame_vs_nist.csv` | 2 537 | 原子质量对账（完全一致 1 348 / 舍入级 1 046 / 显著 143） |

## 衰变链

| 文件 | 行数 | 内容 |
|---|---|---|
| `decay_graph.csv` | 6 588 | 逐条衰变边（母体、模式、分支%、子体） |
| `decay_chains.csv` | 4 156 | 每个核素的主导边 + 走到稳定的整条链 + 发生器候选标记 |

## 中子截面（ENDF/B-VIII.0）

| 文件 | 行数 | 内容 |
|---|---|---|
| `xs_thermal.csv` | 35 | 2200 m/s 截面、共振积分、共振峰 |
| `xs_index.csv` | 35 | α = σγ/σf、单位原子数转换比、嬗变时间、¹⁹⁷Au 校验 |
| `xs_spec.csv` | 114 | 6 个谱（热 Maxwell / Watt / 软化快谱 4 档）下的谱平均截面 |
| `xs_shield.csv` | 24 | 窄共振近似（NR）自屏后的有效俘获截面与 f 因子 |

## 价格（EIA Form EIA-858）

| 文件 | 行数 | 内容 |
|---|---|---|
| `prices_fuelcycle.csv` | 23 | 2003–2025：U3O8 加权/现货/长协价（$/lb U3O8e）、折 $/kgU、SWU 价 |
| `prices_material2025.csv` | 4 | 2025 年按物料形态（U3O8 / 天然 UF6 / 浓缩 UF6）的成交量与成交价 |
| `prices_derived.csv` | 3 | 4.5% / 19.75% / 90% 三档丰度的进料量、分离功、$/kgU、每克 ²³⁵U 成本 |
| `price_vs_tier.csv` | 5 | 价格锚点 → 元/g → 实测 T 层级 vs 策展层级（含来源·时间戳） |
| `price_sources.csv` | 6 | 6 个候选价格来源的逐条核查（页面原话、能不能拿到价） |

---

## 复现

```bash
python tools/fetch_nist.py && python tools/fetch_wiki.py all
python tools/fetch_nubase.py && python tools/parse_nubase.py && python tools/parse_ame.py
python tools/build_dataset.py          # → tuia_*.csv
python tools/extract_isomers.py && python tools/qa_nubase.py && python tools/qa_ame.py
python tools/decay_chains.py
python tools/fetch_xs.py && python tools/parse_xs.py && python tools/xs_index.py && python tools/xs_spectrum.py
python tools/fetch_prices.py && python tools/parse_prices.py && python tools/price_check.py
```

依赖见仓库根目录 `requirements.txt`。原始文件缓存在 `data/raw/`（.gitignore 已排除）。
