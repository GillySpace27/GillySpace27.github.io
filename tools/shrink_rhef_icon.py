#!/usr/bin/env python3
"""Shrink the RHEF icon's white squircle and its imagery about the centre so more violet ground shows.

  python3 tools/shrink_rhef_icon.py <before-1024.png> <factor> <out-1024.png>

On 2026-11-03 Gilly asked for more of the purple ground to show, and the icon was made with
  git show 5aba92f:assets/sw/rhef-1024.png > before.png
  python3 tools/shrink_rhef_icon.py before.png 0.88 assets/sw/rhef-1024.png
and assets/sw/rhef.png is that file resized to 160 px with Pillow's LANCZOS (as the old one was).
Always start from the 2026-11-02 master (5aba92f), never from a shrunk one. At factor 1.0 the
script returns that master unchanged (checked pixel for pixel). Needs numpy and Pillow.

The tile's own outline (its alpha) stays as it is. Inside it, everything within the white
squircle's outer edge (a superellipse, exponent 5, half-width 451 px: measured on row 512 of the
2026-11-02 master, white from x=61), and the slider bar that runs past it, is scaled by <factor>
about the centre and laid on the family ground, #2F2263 to #15102A top to bottom.
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw

S, SS, N, HALF = 1024, 4, 5, 455.5   # 4.5 px past the white edge, to take its antialiasing
BAR_X0, BAR_X1, BAR_Y0, BAR_Y1 = 503, 522, 20, 1005   # the white slider bar, measured on the same master
TOP, BOT = np.array((47, 34, 99), float), np.array((21, 16, 42), float)


def superellipse(half):
    c, h = S * SS / 2, half * SS
    pts = []
    for i in range(4800):
        t = 2 * math.pi * i / 4800
        ct, st = math.cos(t), math.sin(t)
        pts.append((c + h * math.copysign(abs(ct) ** (2 / N), ct), c + h * math.copysign(abs(st) ** (2 / N), st)))
    m = Image.new("L", (S * SS, S * SS), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return np.array(m.resize((S, S), Image.BOX)).astype(float) / 255


def scale(arr, f):
    """arr (H, W, C) float scaled by f about the centre into a zero canvas of the same size."""
    n = round(S * f)
    o = (S - n) // 2
    out = np.zeros_like(arr)
    for k in range(arr.shape[2]):
        ch = Image.fromarray(arr[..., k].astype(np.float32), "F").resize((n, n), Image.LANCZOS)
        out[o:o + n, o:o + n, k] = np.array(ch)
    return out


src, f, dst = sys.argv[1], float(sys.argv[2]), sys.argv[3]
im = np.array(Image.open(src).convert("RGBA")).astype(float)
m = superellipse(HALF)
m[BAR_Y0:BAR_Y1, BAR_X0:BAR_X1] = 1       # the slider bar runs past the squircle, top and bottom
m = m[..., None]
inner = scale(np.concatenate([im[..., :3] * m, m], axis=2), f)
ms = np.clip(inner[..., 3:], 0, 1)
t = np.linspace(0, 1, S)[:, None, None]
ground = TOP * (1 - t) + BOT * t
rgb = np.clip(ground * (1 - ms) + np.clip(inner[..., :3], 0, 255), 0, 255)
out = np.concatenate([rgb, im[..., 3:]], axis=2).round().astype(np.uint8)
Image.fromarray(out, "RGBA").save(dst)
