#!/usr/bin/env python3
"""Face-centered square crop for circular avatars.

Reusable helper: turns a portrait/headshot into a square, face-biased crop so an
``object-fit:cover`` circular frame centers the FACE, not the torso. No face
detection dependency — headshots put the face in the upper portion of the frame,
so a top-biased square is a robust heuristic. Fine-tune with --side/--top/--cx.

    python tools/crop_avatar.py photo.jpg photo_avatar.jpg
    python tools/crop_avatar.py in.jpg out.jpg --side 0.62 --top 0.11 --cx 0.52 --out 512
"""
from __future__ import annotations

import argparse

from PIL import Image


def face_square_box(w, h, side_frac, top_frac, cx_frac):
    """(left, top, right, bottom) square box, clamped to the image."""
    side = min(round(h * side_frac), w, h)
    left = round(w * cx_frac - side / 2)
    top = round(h * top_frac)
    left = max(0, min(left, w - side))
    top = max(0, min(top, h - side))
    return (left, top, left + side, top + side)


def crop_avatar(src, dst, side, top, cx, out):
    img = Image.open(src)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    box = face_square_box(img.width, img.height, side, top, cx)
    square = img.crop(box)
    if out > 0:
        square = square.resize((out, out), Image.LANCZOS)
    square.save(dst, quality=90, optimize=True)
    print(f"src {img.width}x{img.height} -> box {box} -> {square.width}x{square.height} -> {dst}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--side", type=float, default=0.62)
    ap.add_argument("--top", type=float, default=0.11)
    ap.add_argument("--cx", type=float, default=0.52)
    ap.add_argument("--out", type=int, default=512)
    a = ap.parse_args()
    crop_avatar(a.src, a.dst, a.side, a.top, a.cx, a.out)


if __name__ == "__main__":
    main()
