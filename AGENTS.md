# TUIA 开发规则（本仓的「必须照着做 / 不能做」）

本仓 = **同位素可及性数据流水线 + 交付物**，不是软件库：

| 目录 | 管什么 |
|---|---|
| `data/processed/*.csv` | **生成物**（14 个 CSV，见 `data/README.md` 索引与复现命令） |
| `docs/figs/` | 图（SVG 是源，PNG/PDF 是渲染物） |
| `dist/*.xlsx` | 21 张表的工作簿（生成物） |
| `tools/` | 生成链：fetch → parse → 评分 → 建表 → 出图 → 渲染 |
| `docs/methodology.md` | 方法与局限 —— **口径有疑问先查这里** |

详细内容见 `README.md` 与 `docs/methodology.md`；进度与已知开口见 `docs/roadmap.md`。

---

## 1. 怎么跑

```bash
# 完整重生成（顺序不能换：parse 依赖 fetch 的原始文件）
python tools/fetch_nist.py && python tools/fetch_wiki.py all
python tools/fetch_nubase.py && python tools/parse_nubase.py && python tools/parse_ame.py
python tools/build_dataset.py          # → tuia_*.csv
python tools/extract_isomers.py && python tools/qa_nubase.py && python tools/qa_ame.py
python tools/decay_chains.py
python tools/fetch_xs.py && python tools/parse_xs.py && python tools/xs_index.py && python tools/xs_spectrum.py
python tools/fetch_prices.py && python tools/parse_prices.py && python tools/price_check.py
python tools/make_figure.py && python tools/render_png.py
python tools/build_workbook.py
```

- `data/raw/` 不入库，随时可用 fetch 脚本重抓。
- **改了数据就必须重跑到 `dist/`**，否则仓库里的工作簿与 CSV 不一致。
- 图的重渲染依赖 **Microsoft YaHei**（Windows）。在别的系统上渲出来的 PNG/PDF 字形会变，
  **渲染后必须人看过再提交**，不要放进自动化流水线。
- **PDF 走浏览器打印，不走 cairosvg**：cairo 子集化微软雅黑（TTC `msyhbd.ttc`）会失败，
  出来的 PDF 中文全是乱码（2026-10 交付物事故）。`render_png.py` 里 PNG 用 cairosvg、
  PDF 用本机 Edge/Chrome 无头打印，两条路不要合并。
- 重渲 PDF 时**别用阅读器开着那个文件**：Windows 独占锁会让浏览器写失败并**静默保留旧文件**。
  `render_png.py` 已改成先打临时目录再拷回来，拷不进去会直接报错。
- **PDF 的字节不可复现**（Chromium 每次写新的创建时间与字体子集标签）：重跑后 `git status`
  显示两个 PDF 改动是正常的，**别为这个单独提交**。判定是否真的变了要比像素：
  用 pypdfium2 把 HEAD 版与工作区版各渲一张、`ImageChops.difference(...).getbbox() is None`
  —— 一致就 `git checkout -- docs/figs/*.pdf` 还原（2026-10-19 实测 periodic/heatmap 都像素一致）。

## 2. 闸门数字（这些一旦变化，必须在提交说明里单独交代原因）

| 数字 | 现值 | 出处 |
|---|---|---|
| 核素总数 | 3 600 | NIST 全表条目 |
| 人工策展 | 234 | `tools/curation.py` |
| 元素 / 供应国 | 118 / 59 | `tuia_elements.csv` / `tuia_supply.csv` |
| 等级分布 | S 19 · A 77 · B 90 · C 98 · D 2 260 · E 1 056 | `tuia_nuclides.csv` |
| 半衰期对账（基态） | 3 099 可比，2 932 一致（94.6%），60 显著分歧 | `nubase_vs_wiki.csv` |
| 单位换算 | 1 kgU = **2.5998** lb U3O8 | `parse_prices.py`（由原子量算） |
| 分离功校验 | 4.5% / 0.25% 尾料 = **6.87** SWU/kgU | `prices_derived.csv` |
| 截面校验 | ¹⁹⁷Au 2200 m/s 俘获 = **98.68 b**（手册 98.65） | `xs_thermal.csv` |
| 算例自校验 | ¹⁸O = **63.1** 分（07 页逐项可复算） | `tuia_nuclides.csv` |
| T 层级标定 | 4 个锚点中 3 个落在 ±1 个量级内 | `price_vs_tier.csv` |

## 3. 不能做的事

1. **不 push。** 提交由本 agent 做，推送由仓主做。要推之前先确认工作区干净。
2. **不手改生成物。** `data/processed/*.csv`、`dist/*.xlsx`、`docs/figs/*.png|pdf` 一律由脚本生成；
   要改就改 `tools/` 后重跑。
3. **不为「看起来合理」改模型。** 不许给单个核素加特例、不许调权重去凑某个分数。
   评分模型改动必须同时更新：`07_评分模型` 的算例（会自动跟着算）、`docs/methodology.md §二`。
   单点不满意先问「是哪一维的取值错了」（去改数据），再问「映射表是不是分得太粗」（去改类别）。
4. **不编价格。** 核素级没有公开报价（NIDC / Sigma / 经销商全是询价制，已逐条核查在
   `price_sources.csv`）；唯一可用的实测价是 EIA 燃料循环侧。**³H 只有 2003 年二手文献值
   （$30 000/g）**，不得据此改它的策展等级 —— 要改先拿到当期报价。
5. **不把「没做」写成「已完成」。** 未接入的项（分离能、衰变子体能级、能群结构共振参数）
   只能在文档里写「未接入」，见 `docs/roadmap.md`。
6. **不混淆三种统计口径**：稳定 / 原生放射性（⁴⁰K、⁸⁷Rb 这类）/ 人工放射性。
   04、05 两表的计数口径不同但都正确，改动前先读 `methodology` 的说明。
7. **工作簿里的文字不用 markdown 反引号**（Excel 不渲染，会显示成 `` ` ``）。

## 4. 改完必做的自检

```bash
python -m compileall -q tools          # 语法
python tools/qa_nubase.py              # 半衰期对账率是否仍 94.6%
python tools/qa_ame.py                 # 质量对账（一致/舍入/显著）
python tools/price_check.py            # T 层级：4 锚点 / 3 命中
python tools/build_workbook.py         # 21 张表，无异常
```

再看一眼 `git status --porcelain`：**改动应只包含你打算改的那几个文件**。
生成物一起变了是对的（数据变了），但若某个无关 CSV 也变了，说明有副作用没查清。

## 5. 措辞

- 给用户报结论时直接说「哪条命令 / 哪个参数 / 哪一行、什么现象、下一步做什么」，
  不用「抓到了」「真凶」这类修辞。
- 数据疑误按「核素名 + 看到的数值 + 依据的出处」三件套记，便于逐条核。
- 引用价格必须带年份（EIA 成交年度 / 文献年份）。
