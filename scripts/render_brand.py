"""Render the bundled Apache-licensed mdi:rodent SVG; development-only CairoSVG."""

from pathlib import Path

import cairosvg

BRAND = Path(__file__).resolve().parents[1] / "custom_components/mousetrap_manager/brand"
svg = (BRAND / "rodent.svg").read_text()
for prefix, color in (("", "#365f83"), ("dark_", "#a9d5f3")):
    colored = svg.replace("<path ", f'<path fill="{color}" ')
    for suffix, size in (("", 256), ("@2x", 512)):
        cairosvg.svg2png(
            bytestring=colored.encode(),
            output_width=size,
            output_height=size,
            write_to=str(BRAND / f"{prefix}icon{suffix}.png"),
        )
