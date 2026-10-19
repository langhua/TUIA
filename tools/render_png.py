"""把 docs/figs 下的 SVG 渲染成 PNG 与 PDF。

每个 SVG 出三份：
- 常规版（`tuia-periodic.png` / `tuia-heatmap.png`）：嵌进工作簿用；
- 加宽版（`tuia-periodic@4k.png` / `tuia-heatmap@2x.png`）：给网页首屏、截图、印刷 ——
  图里最小字号（同位素标签 8.2px、图例 12.5px）只有全宽才读得出来；
- 矢量 PDF（同名 `.pdf`）：字号随便放大都不模糊，给投稿与印刷。

依赖：cairosvg（pip install cairosvg）。Windows 下需要系统字体可用。

注意：SVG 里的 font-family 是 CSS 字体栈，cairosvg 不解析字体栈，
因此渲染前先替换成单一 CJK 字体名，否则中文会画成方框。
"""

from __future__ import annotations

import pathlib
import sys

import cairosvg

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIGS = ROOT / "docs" / "figs"

FONT_STACK = "'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif"
CJK_FONT = "Microsoft YaHei"

# (源 SVG, 输出名, 像素宽)
JOBS = [
    ("tuia-periodic.svg", "tuia-periodic.png", 2400),
    ("tuia-periodic.svg", "tuia-periodic@4k.png", 3840),
    ("tuia-heatmap.svg", "tuia-heatmap.png", 1400),
    ("tuia-heatmap.svg", "tuia-heatmap@2x.png", 2800),
]


def render(name: str, out_name: str, width: int,
           cjk_font: str = CJK_FONT) -> tuple[pathlib.Path, pathlib.Path | None]:
    svg = (FIGS / name).read_text(encoding="utf-8")
    svg = svg.replace(FONT_STACK, cjk_font)
    out = FIGS / out_name
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(out),
                     output_width=width)
    if "@" in out_name:
        return out, None          # 加宽版与常规版是同一张矢量图，PDF 只出一份
    pdf = out.with_suffix(".pdf")
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(pdf))
    return out, pdf


def main() -> None:
    font = sys.argv[1] if len(sys.argv) > 1 else CJK_FONT
    for name, out_name, width in JOBS:
        p, pdf = render(name, out_name, width, font)
        extra = f"   + {pdf.name} {pdf.stat().st_size / 1024:.0f} KB" if pdf else ""
        print(f"{p.name:26s} {p.stat().st_size / 1024:8.0f} KB{extra}")


if __name__ == "__main__":
    main()
