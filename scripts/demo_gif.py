#!/usr/bin/env python3
"""Turn PNG frames from the demo recording into the GIF shown in the README.

    ffmpeg -i docs/demo/lineage-walkthrough.webm -r 4 frames/%04d.png
    python scripts/demo_gif.py frames docs/demo/lineage-walkthrough.gif

Frames captured at 4 a second play at 6, one and a half times real speed. GitHub plays a GIF in a
README but not a video kept in the repository.
"""

import sys
from pathlib import Path

from PIL import Image

SIZE = (880, 550)
FPS = 6
# The console's own colours get reserved palette entries: the highlighted quote, the accent, the
# ratings and the verified-chain banner cover too few pixels to win a slot on their own.
RESERVED = [
    (255, 241, 184),
    (31, 78, 121),
    (164, 38, 44),
    (138, 90, 0),
    (46, 107, 48),
    (232, 243, 232),
    (238, 243, 248),
    (251, 234, 234),
]


def build(frames_dir: Path, out: Path) -> int:
    paths = sorted(frames_dir.glob("*.png"))
    frames = [Image.open(p).convert("RGB").resize(SIZE, Image.Resampling.LANCZOS) for p in paths]
    sample = frames[::8]
    sheet = Image.new("RGB", (SIZE[0], SIZE[1] * len(sample)))
    for i, frame in enumerate(sample):
        sheet.paste(frame, (0, SIZE[1] * i))
    colours = 256 - len(RESERVED)
    base = sheet.quantize(colors=colours, method=Image.Quantize.MEDIANCUT).getpalette() or []
    palette = Image.new("P", (1, 1))
    palette.putpalette(base[: 3 * colours] + [c for rgb in RESERVED for c in rgb])
    quantized = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    quantized[0].save(
        out,
        save_all=True,
        append_images=quantized[1:],
        duration=1000 // FPS,
        loop=0,
        optimize=True,
    )
    return len(quantized)


if __name__ == "__main__":
    print(build(Path(sys.argv[1]), Path(sys.argv[2])), "frames")
