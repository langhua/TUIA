"""把 docs/figs 下的 SVG 渲染成 PNG 与 PDF。

每个 SVG 出三份：
- 常规版（`tuia-periodic.png` / `tuia-heatmap.png`）：嵌进工作簿用；
- 加宽版（`tuia-periodic@4k.png` / `tuia-heatmap@2x.png`）：给网页首屏、截图、印刷 ——
  图里最小字号（同位素标签 8.2px、图例 12.5px）只有全宽才读得出来；
- 矢量 PDF（同名 `.pdf`）：字号随便放大都不模糊，给投稿与印刷。

两条渲染路径，**不要合并**：

| 输出 | 引擎 | 原因 |
|---|---|---|
| PNG | cairosvg | 快、可控；字重与位置按雅黑调过 |
| PDF | **Chromium / Edge 无头打印** | cairosvg 走 cairo 的 toy font API，PDF 后端要子集化字体；**微软雅黑是 TTC（msyhbd.ttc），cairo 子集化失败 → 中文全变乱码**。浏览器会正确嵌入字体 |

踩过的坑（2026-10）：
1. cairosvg 产出的 PDF 里中文乱码／错位，英文正常 —— 就是上面那条 TTC 子集化问题。
   换 SimHei 能显示中文，但 **SimHei 缺 Unicode 上标**（1²³⁰⁶⁹ᵐ 全变方框）；
   DengXian 比雅黑窄 15%，会把标签挤位 —— 都不合适，**改用浏览器打印**。
2. CSS 字体栈（`\'Segoe UI\', \'Microsoft YaHei\', sans-serif`）cairo 不解析，
   所以 PNG 路径仍要先替换成单一字体名；PDF 交给浏览器，字体栈原样保留。
3. 图的「痕量」行上标已改成 tspan 小字（见 `make_figure.py` 的 TRACE），
   不依赖字体里有没有 U+2070 / U+2079。

依赖：cairosvg（PNG）、本机 Edge 或 Chrome（PDF）。
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

import cairosvg

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIGS = ROOT / "docs" / "figs"

FONT_STACK = "'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif"
CJK_FONT = "Microsoft YaHei"

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# (源 SVG, 输出名, 像素宽)
JOBS = [
    ("tuia-periodic.svg", "tuia-periodic.png", 2400),
    ("tuia-periodic.svg", "tuia-periodic@4k.png", 3840),
    ("tuia-heatmap.svg", "tuia-heatmap.png", 1400),
    ("tuia-heatmap.svg", "tuia-heatmap@2x.png", 2800),
]


def _browser() -> str | None:
    for p in BROWSERS:
        if pathlib.Path(p).exists():
            return p
    return shutil.which("msedge") or shutil.which("chrome")


def render_png(name: str, out_name: str, width: int,
               cjk_font: str = CJK_FONT) -> pathlib.Path:
    svg = (FIGS / name).read_text(encoding="utf-8")
    svg = svg.replace(FONT_STACK, cjk_font)      # cairo 不解析字体栈
    out = FIGS / out_name
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(out),
                     output_width=width)
    return out


def render_pdf(name: str, out_name: str, retries: int = 5) -> pathlib.Path | None:
    """用浏览器打印成 PDF（字体按 CSS 栈解析并正确嵌入）。

    ★ 先打到临时目录，再拷到 docs/figs：浏览器写**已存在的**目标文件时，
    若那个文件正被 PDF 阅读器打开（Windows 独占锁），它会静默失败并把旧文件留在原处
    —— 于是你会看到一个「看起来更新了」的旧 PDF（2026-10 就是被这个坑过：
    检查时误以为新文件只有一种字体，其实是旧的 cairosvg 产物没被覆盖）。
    """
    exe = _browser()
    if not exe:
        print(f"  ! 找不到 Edge/Chrome，跳过 {name} 的 PDF（cairosvg 出的中文会是乱码）")
        return None

    svg = (FIGS / name).read_text(encoding="utf-8")
    m = re.search(r'<svg[^>]*\swidth="([\d.]+)"[^>]*\sheight="([\d.]+)"', svg)
    if not m:
        raise ValueError(f"{name}: 读不到 width/height")
    w, h = float(m.group(1)), float(m.group(2))
    svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)   # 内联进 HTML 前去掉 XML 声明

    out = (FIGS / out_name).with_suffix(".pdf")
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        html = tmp / "page.html"
        fresh = tmp / "fresh.pdf"
        html.write_text(
            '<!doctype html><html><head><meta charset="utf-8"><style>\n'
            f"@page {{ size: {w * 0.75:.2f}pt {h * 0.75:.2f}pt; margin: 0; }}\n"
            "html,body{margin:0;padding:0;background:#fff;}\n"
            f"svg{{display:block;width:{w}px;height:{h}px;}}\n"
            "</style></head><body>" + svg + "</body></html>",
            encoding="utf-8")
        cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run",
               "--no-default-browser-check", "--no-pdf-header-footer",
               "--print-to-pdf-no-header",
               f"--user-data-dir={tmp / 'profile'}",
               f"--print-to-pdf={fresh.resolve()}", html.resolve().as_uri()]
        r = subprocess.run(cmd, capture_output=True, timeout=300)
        if not fresh.exists() or fresh.stat().st_size < 20_000:
            tail = r.stderr.decode("utf-8", "replace")[-400:]
            raise RuntimeError(f"{name}: 浏览器没写出 PDF（rc={r.returncode}）{tail}")

        last: Exception | None = None
        for _ in range(retries):
            try:
                shutil.copyfile(fresh, out)          # 目标被占用会在这里抛，旧文件仍完整
                break
            except PermissionError as e:             # 多半是 PDF 阅读器开着
                last = e
                time.sleep(1.0)
        else:
            raise RuntimeError(
                f"{out.name} 被其它程序占用，拷不进去（{last}）。"
                f"先关掉 PDF 阅读器再重跑 tools/render_png.py") from last
    return out


def main() -> None:
    font = sys.argv[1] if len(sys.argv) > 1 else CJK_FONT
    for name, out_name, width in JOBS:
        p = render_png(name, out_name, width, font)
        extra = ""
        if "@" not in out_name:            # 加宽版与常规版是同一张矢量图，PDF 只出一份
            pdf = render_pdf(name, out_name)
            if pdf:
                extra = f"   + {pdf.name} {pdf.stat().st_size / 1024:.0f} KB"
        print(f"{p.name:26s} {p.stat().st_size / 1024:8.0f} KB{extra}")


if __name__ == "__main__":
    main()
