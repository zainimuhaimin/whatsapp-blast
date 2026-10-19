#!/usr/bin/env python3
"""Generate PWA PNG icons deterministically (Pillow).

Source of truth for the WA Blast product mark:
dark-green rounded square, white chat bubble, green paper plane.
Idempotent: skips files that already exist (pass --force to redraw).

Used by frontend/Dockerfile so the PNG binaries don't need to live in git
(the GitHub snapshot-push mechanism only accepts UTF-8 text files).
"""
import sys
from pathlib import Path

GREEN_DARK = "#0d5c2e"
GREEN = "#159a4c"
WHITE = "#ffffff"

OUT = Path(__file__).resolve().parent


def draw_mark(draw, s, cx, cy, bubble_w):
    """Draw bubble + plane centered at (cx, cy), scaled to size s (canvas px)."""
    from PIL import ImageDraw  # noqa
    bw, bh = bubble_w, int(bubble_w * 0.72)
    x0, y0 = cx - bw / 2, cy - bh / 2
    x1, y1 = cx + bw / 2, cy + bh / 2
    r = int(bw * 0.16)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=WHITE)
    # tail
    tx = x0 + bw * 0.16
    draw.polygon([(tx, y1 - r * 0.4), (tx - bw * 0.10, y1 + bh * 0.26), (tx + bw * 0.16, y1 - 2)], fill=WHITE)
    # paper plane
    pw = bw * 0.62
    px, py = cx, cy - bh * 0.02
    draw.polygon(
        [
            (px - pw * 0.42, py - pw * 0.10),
            (px + pw * 0.50, py - pw * 0.22),
            (px - pw * 0.05, py + pw * 0.30),
            (px - pw * 0.12, py + pw * 0.02),
        ],
        fill=GREEN,
    )


def make_icon(size, *, maskable=False, force=False):
    from PIL import Image, ImageDraw

    name = {192: "icon-192.png", 512: "icon-512.png"}.get(size, f"icon-{size}.png")
    if maskable:
        name = "maskable-512.png"
    if size == 180:
        name = "apple-touch-icon.png"
    target = OUT / name
    if target.exists() and not force:
        return False

    s = 512  # draw big, downscale
    img = Image.new("RGBA", (s, s), GREEN_DARK)
    d = ImageDraw.Draw(img)
    if not maskable:
        # rounded-square app icon look on transparent canvas
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, s, s], radius=int(s * 0.22), fill=GREEN_DARK)
        draw_mark(d, s, s / 2, s * 0.48, s * 0.60)
    else:
        # full-bleed, mark smaller (safe zone)
        draw_mark(d, s, s / 2, s / 2, s * 0.46)

    img = img.convert("RGB")
    if size != s:
        img = img.resize((size, size), Image.LANCZOS)
    img.save(target)
    return True


def main():
    try:
        from PIL import Image  # noqa  (dependency check)
    except ImportError:
        print("generate-icons: Pillow not installed, skipping (icons optional for build)")
        return 0
    force = "--force" in sys.argv
    made = [n for n, ok in [
        ("icon-192.png", make_icon(192, force=force)),
        ("icon-512.png", make_icon(512, force=force)),
        ("maskable-512.png", make_icon(512, maskable=True, force=force)),
        ("apple-touch-icon.png", make_icon(180, force=force)),
    ] if ok]
    print("generate-icons:", "regenerated " + ", ".join(made) if made else "all icons present, skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
