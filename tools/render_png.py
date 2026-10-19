"""把 docs/figs 下的 SVG 渲染成 PNG，供工作簿嵌入。

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

JOBS = [
    ("tuia-periodic.svg", 1800),
    ("tuia-heatmap.svg", 1400),
]


def render(name: str, width: int, cjk_font: str = CJK_FONT) -> pathlib.Path:
    svg = (FIGS / name).read_text(encoding="utf-8")
    svg = svg.replace(FONT_STACK, cjk_font)
    out = FIGS / name.replace(".svg", ".png")
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(out),
                     output_width=width)
    return out


def main() -> None:
    font = sys.argv[1] if len(sys.argv) > 1 else CJK_FONT
    for name, width in JOBS:
        p = render(name, width, font)
        print(f"{p.name:28s} {p.stat().st_size/1024:8.0f} KB")


if __name__ == "__main__":
    main()
