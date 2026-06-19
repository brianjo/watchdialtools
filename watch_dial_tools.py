#!/usr/bin/env python3
# Copyright (C) 2026 Brian Johnson
# https://github.com/brianjo
# brianjo@gmail.com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

"""
Watch Dial Tools — unified watch-dial design extension.

Combines six previously separate Inkscape extensions into a single dialog with a
master "Tool" selector:

  * dial    -- Watch Dial Generator (outline, center hole, hour markers,
               minute ticks, Arabic/Roman/custom numerals).
  * blank   -- Blank Movement Template (NH35 / ST36 hand holes, date window,
               subdial, dial feet).
  * classic -- Classic / old-world patterns (guilloche, concentric, sunburst,
               crosshatch, plus multi-layer "auto-complex" presets).
  * rose    -- Rose-engine guilloche (sine / square / epicycloid, multi-ring).
  * perlage -- Perlage spots (grid / staggered / spiral / radial).
  * modern  -- Modern / new-world patterns (Mondrian, Op-Art waves, spiral
               stripes, paper texture, linen texture).

High-accuracy alignment: every tool resolves the same document center via
get_doc_center(), so stacked layers land perfectly concentric regardless of the
tool used.
"""

import math
import csv
import re
import uuid
import random

import inkex
from inkex import Circle, Rectangle, TextElement, Group

try:
    from inkex import PathElement
except Exception:  # pragma: no cover - very old inkex
    PathElement = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def mm_to_uu(svg, mm: float) -> float:
    """Convert millimeters to the document's user units."""
    try:
        return float(svg.unittouu(f"{mm}mm"))
    except Exception:
        # Fallback to px @ 96dpi
        return mm * 96.0 / 25.4


def get_doc_center(svg):
    """Robust document-center detection (no viewbox dependency required)."""
    vb = svg.get("viewBox") or svg.get("viewbox")
    if vb:
        parts = [p for p in re.split(r"[ ,]+", vb.strip()) if p]
        if len(parts) == 4:
            minx, miny, w, h = [float(p) for p in parts]
            return (minx + w / 2.0, miny + h / 2.0)
    try:
        w = svg.unittouu(svg.get("width") or "0")
        h = svg.unittouu(svg.get("height") or "0")
        if w and h:
            return (w / 2.0, h / 2.0)
    except Exception:
        pass
    return (0.0, 0.0)


def add_root_group(svg, label, gid):
    """Create a root group on the current layer (falls back to root)."""
    g = Group()
    g.label = label
    if gid:
        g.set("id", gid)
    try:
        svg.get_current_layer().add(g)
    except Exception:
        svg.add(g)
    return g


def new_path(d: str):
    if PathElement is not None:
        p = PathElement()
    else:
        p = inkex.etree.Element(inkex.addNS('path', 'svg'))
    p.set('d', d)
    return p


def new_rect(x, y, w, h):
    if Rectangle is not None:
        r = Rectangle()
    else:
        r = inkex.etree.Element(inkex.addNS('rect', 'svg'))
    r.set('x', str(x)); r.set('y', str(y))
    r.set('width', str(w)); r.set('height', str(h))
    return r


def set_style(el, style_dict):
    """Set style on both inkex elements and raw lxml elements."""
    try:
        if hasattr(el, "style"):
            el.style = style_dict
            return
    except Exception:
        pass
    el.set("style", str(inkex.Style(style_dict)))


def set_rect_geom(rect, x, y, w, h):
    rect.set("x", str(x))
    rect.set("y", str(y))
    rect.set("width", str(w))
    rect.set("height", str(h))


def ensure_defs(svg):
    try:
        defs = svg.defs
        if defs is not None:
            return defs
    except Exception:
        pass
    defs_list = svg.xpath('//svg:defs', namespaces=inkex.NSS)
    if defs_list:
        return defs_list[0]
    defs = inkex.etree.Element(inkex.addNS('defs', 'svg'))
    svg.insert(0, defs)
    return defs


def clip_group_to_circle(svg, group, cx, cy, r, clip_id):
    defs = ensure_defs(svg)
    clip = inkex.etree.Element(inkex.addNS('clipPath', 'svg'))
    clip.set('id', clip_id)
    c = inkex.etree.Element(inkex.addNS('circle', 'svg'))
    c.set('cx', str(cx)); c.set('cy', str(cy)); c.set('r', str(r))
    clip.append(c)
    defs.append(clip)
    group.set('clip-path', f'url(#{clip_id})')


def normalize_color(c):
    """Normalize various Inkscape color formats to #RRGGBB."""
    if c is None:
        return "#000000"
    c = str(c).strip()
    if c == "" or c.lower() in ("none", "transparent"):
        return "#000000"

    m = re.fullmatch(r"#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?", c)
    if m:
        return "#" + m.group(1)

    m = re.fullmatch(r"rgba?\(([^)]+)\)", c.replace(" ", ""))
    if m:
        parts = m.group(1).split(",")
        if len(parts) >= 3:
            def chan(v):
                if v.endswith("%"):
                    return max(0, min(255, round(float(v[:-1]) * 2.55)))
                return max(0, min(255, int(round(float(v)))))
            r = chan(parts[0]); g = chan(parts[1]); b = chan(parts[2])
            if len(parts) >= 4:
                try:
                    a = float(parts[3])
                    if a <= 0.001:
                        return "#000000"
                except Exception:
                    pass
            return "#{:02X}{:02X}{:02X}".format(r, g, b)

    if re.fullmatch(r"-?\d+", c):
        try:
            n = int(c) & 0xFFFFFFFF
            r = (n >> 16) & 0xFF
            g = (n >> 8) & 0xFF
            b = n & 0xFF
            return "#{:02X}{:02X}{:02X}".format(r, g, b)
        except Exception:
            return "#000000"

    return c


def polar(cx, cy, r, ang_deg_clockwise_from_12):
    """Clock convention: 0 deg = 12 o'clock, positive = clockwise."""
    a = math.radians(ang_deg_clockwise_from_12)
    return (cx + r * math.sin(a), cy - r * math.cos(a))


def rotate_point(x, y, angle_rad):
    ca = math.cos(angle_rad)
    sa = math.sin(angle_rad)
    return x * ca - y * sa, x * sa + y * ca


# ---------------------------------------------------------------------------
# Dial generator helpers (numbers / markers)
# ---------------------------------------------------------------------------

def rotation_for_number(mode: str, angle_clock_deg: float) -> float:
    mode = (mode or "upright").strip().lower()
    if mode == "upright":
        return 0.0
    if mode == "tangent":
        return angle_clock_deg
    if mode == "radial":
        return angle_clock_deg + 90.0
    if mode == "tangent_readable":
        r = angle_clock_deg % 360.0
        if 90.0 < r < 270.0:
            r += 180.0
        return r
    return 0.0


def read_labels_from_csv(csv_text: str):
    if not csv_text:
        return []
    s = csv_text.strip()
    if not s:
        return []
    if "\n" not in s and ";" not in s:
        parts = [p.strip() for p in s.split(",")]
        return [p for p in parts if p]
    out = []
    for row in csv.reader(s.splitlines()):
        for cell in row:
            cell = cell.strip()
            if cell:
                out.append(cell)
    return out


def aligned_radius(r: float, h: float, align: str) -> float:
    a = (align or "outer").strip().lower()
    if a == "outer":
        return r - h / 2.0
    if a == "inner":
        return r + h / 2.0
    return r


# Fraction of the font size from the alphabetic baseline up to a lining digit's
# optical center (~ half the cap height). Used by the "optical" baseline mode.
OPTICAL_DIGIT_CENTER = 0.35

ARABIC_12_FIRST = ["12", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
ROMAN_12_FIRST_IV = ["XII", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
ROMAN_12_FIRST_IIII = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]


# ---------------------------------------------------------------------------
# Classic / old-world pattern primitives
# ---------------------------------------------------------------------------

def pattern_concentric(svg, g, cx, cy, r_outer, r_inner, spacing, stroke_w, stroke_color, opacity):
    r = max(0.0, r_inner)
    while r <= r_outer + 1e-9:
        c = Circle()
        c.set('cx', str(cx)); c.set('cy', str(cy)); c.set('r', str(r))
        set_style(c, {"fill": "none", "stroke": stroke_color,
                      "stroke-width": str(stroke_w), "stroke-opacity": str(opacity)})
        g.add(c)
        r += spacing


def pattern_sunburst(svg, g, cx, cy, r_outer, r_inner, rays, stroke_w, stroke_color, opacity):
    rays = max(4, int(rays))
    step = 360.0 / rays
    for i in range(rays):
        ang = i * step
        x1, y1 = polar(cx, cy, r_inner, ang)
        x2, y2 = polar(cx, cy, r_outer, ang)
        p = new_path(f"M {x1:.6f},{y1:.6f} L {x2:.6f},{y2:.6f}")
        set_style(p, {"fill": "none", "stroke": stroke_color, "stroke-width": str(stroke_w),
                      "stroke-opacity": str(opacity), "stroke-linecap": "round"})
        g.add(p)


def pattern_crosshatch(svg, g, cx, cy, r_outer, spacing, angle_deg, double, stroke_w, stroke_color, opacity):
    size = r_outer * 2.2
    half = size / 2.0

    def add_set(theta_deg):
        theta = math.radians(theta_deg)
        ux, uy = math.cos(theta), math.sin(theta)
        vx, vy = -uy, ux
        count = int((size / spacing)) + 3
        for i in range(-count // 2, count // 2 + 1):
            off = i * spacing
            px = cx + off * vx
            py = cy + off * vy
            x1 = px - half * ux; y1 = py - half * uy
            x2 = px + half * ux; y2 = py + half * uy
            p = new_path(f"M {x1:.6f},{y1:.6f} L {x2:.6f},{y2:.6f}")
            set_style(p, {"fill": "none", "stroke": stroke_color, "stroke-width": str(stroke_w),
                          "stroke-opacity": str(opacity), "stroke-linecap": "round"})
            g.add(p)

    add_set(angle_deg)
    if double:
        add_set(angle_deg + 90.0)


def pattern_guilloche(svg, g, cx, cy, r_outer, lobes, amplitude, points, stroke_w, stroke_color, opacity):
    lobes = max(2, int(lobes))
    points = max(200, int(points))
    base = max(0.0, r_outer - amplitude)
    pts = []
    for i in range(points + 1):
        t = (2.0 * math.pi) * (i / points)
        r = base + amplitude * math.cos(lobes * t)
        x, y = polar(cx, cy, r, math.degrees(t))
        pts.append((x, y))
    d = f"M {pts[0][0]:.6f},{pts[0][1]:.6f} " + " ".join([f"L {x:.6f},{y:.6f}" for x, y in pts[1:]])
    p = new_path(d)
    set_style(p, {"fill": "none", "stroke": stroke_color, "stroke-width": str(stroke_w),
                  "stroke-opacity": str(opacity), "stroke-linejoin": "round"})
    g.add(p)


def pattern_guilloche_field(svg, g, cx, cy, r_outer, r_inner, lobes, amplitude, points,
                            stroke_w, stroke_color, opacity, band_spacing):
    lobes = max(2, int(lobes))
    points = max(200, int(points))
    band_spacing = max(0.1, float(band_spacing))
    r = max(0.0, float(r_inner)) + amplitude
    bands = 0
    max_bands = 600
    while r <= r_outer + 1e-9 and bands < max_bands:
        base = r
        pts = []
        for i in range(points + 1):
            t = (2.0 * math.pi) * (i / points)
            rr = base + amplitude * math.cos(lobes * t)
            x, y = polar(cx, cy, rr, math.degrees(t))
            pts.append((x, y))
        d = f"M {pts[0][0]:.6f},{pts[0][1]:.6f} " + " ".join([f"L {x:.6f},{y:.6f}" for x, y in pts[1:]])
        p = new_path(d)
        set_style(p, {"fill": "none", "stroke": stroke_color, "stroke-width": str(stroke_w),
                      "stroke-opacity": str(opacity), "stroke-linejoin": "round"})
        g.add(p)
        r += band_spacing
        bands += 1


# ---------------------------------------------------------------------------
# Modern / new-world pattern primitives
# ---------------------------------------------------------------------------

def mondrian_split_rects(rnd, rects, min_size):
    rects_sorted = sorted(rects, key=lambda t: t[2] * t[3], reverse=True)
    for (x, y, w, h) in rects_sorted[: max(1, len(rects_sorted) // 2)]:
        if w < 2 * min_size and h < 2 * min_size:
            continue
        if w > h * 1.15:
            direction = "v"
        elif h > w * 1.15:
            direction = "h"
        else:
            direction = "v" if rnd.random() < 0.5 else "h"
        if direction == "v" and w >= 2 * min_size:
            cut = x + rnd.uniform(min_size, w - min_size)
            rects.remove((x, y, w, h))
            rects.extend([(x, y, cut - x, h), (cut, y, x + w - cut, h)])
            return True
        if direction == "h" and h >= 2 * min_size:
            cut = y + rnd.uniform(min_size, h - min_size)
            rects.remove((x, y, w, h))
            rects.extend([(x, y, w, cut - y), (x, cut, w, y + h - cut)])
            return True
    return False


def pattern_mondrian(svg, g, cx, cy, r_outer, rnd, density, line_w, palette_mode, fill_opacity=1.0):
    size = r_outer * 2.0
    x0 = cx - r_outer
    y0 = cy - r_outer
    min_size = size / max(6.0, min(30.0, density * 3.5))
    rects = [(x0, y0, size, size)]
    splits = int(10 + density * 22)
    for _ in range(splits):
        if not mondrian_split_rects(rnd, rects, min_size):
            break

    if palette_mode == "classic":
        colors = ["#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#F2C400", "#D13B2F", "#1E4ED8"]
    elif palette_mode == "pastel":
        colors = ["#FFFFFF", "#F8F1E5", "#E9F2FF", "#FCE4EC", "#FFF9C4", "#E8F5E9"]
    else:
        colors = ["#FFFFFF", "#111111", "#FF3B30", "#FFCC00", "#34C759", "#007AFF", "#AF52DE"]

    for (x, y, w, h) in rects:
        fill = rnd.choice(colors)
        r = new_rect(x, y, w, h)
        set_style(r, {"fill": fill, "fill-opacity": str(fill_opacity), "stroke": "none"})
        g.add(r)

    xs = set([x0, x0 + size]); ys = set([y0, y0 + size])
    for (x, y, w, h) in rects:
        xs.add(x); xs.add(x + w); ys.add(y); ys.add(y + h)
    xs = sorted(xs); ys = sorted(ys)

    for x in xs[1:-1]:
        if rnd.random() < 0.65:
            p = new_path(f"M {x:.6f},{y0:.6f} L {x:.6f},{(y0 + size):.6f}")
            set_style(p, {"fill": "none", "stroke": "#000000", "stroke-width": str(line_w)})
            g.add(p)
    for y in ys[1:-1]:
        if rnd.random() < 0.65:
            p = new_path(f"M {x0:.6f},{y:.6f} L {(x0 + size):.6f},{y:.6f}")
            set_style(p, {"fill": "none", "stroke": "#000000", "stroke-width": str(line_w)})
            g.add(p)


def pattern_op_waves(svg, g, cx, cy, r_outer, r_inner, rnd, spacing, stroke_w, color, opacity,
                     warp_strength, warp_freq, rotate_deg):
    size = r_outer * 2.2
    half = size / 2
    x0 = cx - half; x1 = cx + half
    y0 = cy - half; y1 = cy + half
    if abs(rotate_deg) > 1e-6:
        g.set("transform", f"rotate({rotate_deg},{cx},{cy})")
    steps = max(200, int(r_outer))
    phase = rnd.uniform(0, math.tau)
    x = x0
    while x <= x1:
        pts = []
        for i in range(steps + 1):
            t = i / steps
            y = y0 + (y1 - y0) * t
            rr = math.hypot(x - cx, y - cy)
            falloff = 0 if rr < r_inner else min(1, (rr - r_inner) / max(1, (r_outer - r_inner)))
            w = warp_strength * falloff * math.sin((warp_freq * (y - cy) / max(1, r_outer)) * math.tau + phase)
            pts.append((x + w, y))
        d = "M " + " ".join([f"{px:.3f},{py:.3f}" if i == 0 else f"L {px:.3f},{py:.3f}" for i, (px, py) in enumerate(pts)])
        p = new_path(d)
        set_style(p, {"fill": "none", "stroke": color, "stroke-width": str(stroke_w), "stroke-opacity": str(opacity)})
        g.add(p)
        x += spacing


def pattern_spiral_stripes(svg, g, cx, cy, r_outer, r_inner, turns, stripe_w, stroke_w, color, opacity):
    steps = max(1200, int(r_outer * 2))
    base = []
    for i in range(steps + 1):
        t = i / steps
        r = r_inner + (r_outer - r_inner) * t
        ang = turns * 360 * t
        base.append(polar(cx, cy, r, ang))
    n = min(80, max(1, int((r_outer - r_inner) / stripe_w)))
    for k in range(n):
        off = (k - (n - 1) / 2) * stripe_w
        pts = []
        for (x, y) in base:
            dx = x - cx; dy = y - cy; rr = math.hypot(dx, dy)
            if rr > 0:
                pts.append((x + dx / rr * off, y + dy / rr * off))
            else:
                pts.append((x, y))
        d = "M " + " ".join([f"{px:.3f},{py:.3f}" if i == 0 else f"L {px:.3f},{py:.3f}" for i, (px, py) in enumerate(pts)])
        p = new_path(d)
        set_style(p, {"fill": "none", "stroke": color, "stroke-width": str(stroke_w), "stroke-opacity": str(opacity)})
        g.add(p)


def pattern_paper_texture(svg, g, cx, cy, r_outer, r_inner, rnd,
                          speckle_density, speckle_radius_mm, fiber_count,
                          fiber_length_mm, fiber_jitter_mm, color, opacity):
    speck_r = mm_to_uu(svg, max(0.01, speckle_radius_mm))
    fib_len = mm_to_uu(svg, max(0.05, fiber_length_mm))
    fib_jit = mm_to_uu(svg, max(0.0, fiber_jitter_mm))
    uu_per_mm = mm_to_uu(svg, 1.0)
    area_mm2 = math.pi * ((r_outer / uu_per_mm) ** 2 - (r_inner / uu_per_mm) ** 2)
    n_speckles = int(max(0, min(20000, area_mm2 * max(0.0, speckle_density))))
    n_fibers = int(max(0, min(6000, fiber_count)))

    for _ in range(n_speckles):
        rr = math.sqrt(rnd.random() * (r_outer ** 2 - r_inner ** 2) + r_inner ** 2)
        ang = rnd.random() * 360.0
        x, y = polar(cx, cy, rr, ang)
        c = inkex.etree.Element(inkex.addNS('circle', 'svg'))
        c.set('cx', f"{x:.6f}"); c.set('cy', f"{y:.6f}")
        rj = speck_r * (0.6 + 0.8 * rnd.random())
        c.set('r', f"{rj:.6f}")
        set_style(c, {"fill": color, "fill-opacity": str(opacity * (0.35 + 0.65 * rnd.random())), "stroke": "none"})
        g.add(c)

    for _ in range(n_fibers):
        rr = math.sqrt(rnd.random() * (r_outer ** 2 - r_inner ** 2) + r_inner ** 2)
        ang = rnd.random() * 360.0
        x, y = polar(cx, cy, rr, ang)
        theta = rnd.random() * math.tau
        dx = math.cos(theta) * fib_len * 0.5
        dy = math.sin(theta) * fib_len * 0.5
        jx1 = (rnd.random() - 0.5) * 2.0 * fib_jit
        jy1 = (rnd.random() - 0.5) * 2.0 * fib_jit
        jx2 = (rnd.random() - 0.5) * 2.0 * fib_jit
        jy2 = (rnd.random() - 0.5) * 2.0 * fib_jit
        x1 = x - dx + jx1; y1 = y - dy + jy1
        x2 = x + dx + jx2; y2 = y + dy + jy2
        p = new_path(f"M {x1:.6f},{y1:.6f} L {x2:.6f},{y2:.6f}")
        set_style(p, {
            "fill": "none", "stroke": color,
            "stroke-width": str(mm_to_uu(svg, 0.03 + 0.05 * rnd.random())),
            "stroke-opacity": str(opacity * (0.25 + 0.55 * rnd.random())),
            "stroke-linecap": "round", "stroke-linejoin": "round"})
        g.add(p)


def pattern_linen_texture(svg, g, cx, cy, r_outer, r_inner, rnd,
                          thread_spacing_mm, waviness_mm, waviness_freq,
                          rotate_deg, color, opacity, stroke_mm):
    spacing = mm_to_uu(svg, max(0.05, thread_spacing_mm))
    wav = mm_to_uu(svg, max(0.0, waviness_mm))
    freq = max(0.5, float(waviness_freq))
    size = r_outer * 2.2
    half = size / 2.0
    x0 = cx - half; y0 = cy - half; x1 = cx + half; y1 = cy + half
    if abs(rotate_deg) > 1e-9:
        g.set("transform", f"rotate({rotate_deg:.6f},{cx},{cy})")
    steps = max(120, int(r_outer * 0.6))
    stroke_w = mm_to_uu(svg, max(0.01, stroke_mm))

    phase_v = rnd.random() * math.tau
    x = x0
    while x <= x1 + 1e-6:
        pts = []
        for i in range(steps + 1):
            t = i / steps
            y = y0 + (y1 - y0) * t
            w = wav * math.sin((freq * (y - cy) / max(1.0, r_outer)) * math.tau + phase_v + (x - cx) * 0.002)
            pts.append((x + w, y))
        d = f"M {pts[0][0]:.6f},{pts[0][1]:.6f} " + " ".join([f"L {px:.6f},{py:.6f}" for px, py in pts[1:]])
        p = new_path(d)
        set_style(p, {"fill": "none", "stroke": color, "stroke-width": str(stroke_w),
                      "stroke-opacity": str(opacity * (0.55 + 0.35 * rnd.random())),
                      "stroke-linecap": "round", "stroke-linejoin": "round"})
        g.add(p)
        x += spacing

    phase_h = rnd.random() * math.tau
    y = y0
    while y <= y1 + 1e-6:
        pts = []
        for i in range(steps + 1):
            t = i / steps
            x = x0 + (x1 - x0) * t
            w = wav * math.sin((freq * (x - cx) / max(1.0, r_outer)) * math.tau + phase_h + (y - cy) * 0.002)
            pts.append((x, y + w))
        d = f"M {pts[0][0]:.6f},{pts[0][1]:.6f} " + " ".join([f"L {px:.6f},{py:.6f}" for px, py in pts[1:]])
        p = new_path(d)
        set_style(p, {"fill": "none", "stroke": color, "stroke-width": str(stroke_w * (0.95 + 0.25 * rnd.random())),
                      "stroke-opacity": str(opacity * (0.45 + 0.35 * rnd.random())),
                      "stroke-linecap": "round", "stroke-linejoin": "round"})
        g.add(p)
        y += spacing


# ---------------------------------------------------------------------------
# Blank movement-template presets
# ---------------------------------------------------------------------------

BLANK_PRESETS = {
    "nh35": {
        "dial": 28.5, "center": 2.05,
        "hands": (1.5, 0.9, 0.2),
        "date": (2.9, 2.0, 12.0),
        "feet": [(9.672, -8.667), (-9.466, 8.93)],
    },
    "st36": {
        "dial": 36.6, "center": 2.0,
        "hands": (1.7, 1.0, 0.3),
        "sub": (10.25, 13.404),
    },
}


# ---------------------------------------------------------------------------
# Unified extension
# ---------------------------------------------------------------------------

class WatchDialTools(inkex.EffectExtension):
    def add_arguments(self, pars):
        # The notebook's value is the name of the currently-open tab, which we
        # use directly as the active-tool selector: Apply/Preview run whichever
        # tool's tab is showing.
        pars.add_argument("--ui", type=str, default="dial")

        # ---- Watch Dial Generator (wd_) ----
        pars.add_argument("--wd_dial_diameter_mm", type=float, default=28.5)
        pars.add_argument("--wd_draw_dial_outline", type=inkex.Boolean, default=True)
        pars.add_argument("--wd_dial_outline_stroke_mm", type=float, default=0.12)
        pars.add_argument("--wd_outline_compensate_stroke", type=inkex.Boolean, default=True)
        pars.add_argument("--wd_draw_center_hole", type=inkex.Boolean, default=True)
        pars.add_argument("--wd_center_hole_mm", type=float, default=1.5)
        pars.add_argument("--wd_start_angle_deg", type=float, default=0.0)
        pars.add_argument("--wd_clockwise", type=inkex.Boolean, default=True)
        pars.add_argument("--wd_text_mode", type=str, default="arabic",
                          choices=["arabic", "roman", "custom"])
        pars.add_argument("--wd_labels_csv", type=str, default="")
        pars.add_argument("--wd_roman_four_style", type=str, default="IV", choices=["IV", "IIII"])
        pars.add_argument("--wd_omit_three", type=inkex.Boolean, default=False)
        pars.add_argument("--wd_text_radius_mm", type=float, default=11.5)
        pars.add_argument("--wd_text_radial_offset_mm", type=float, default=0.0)
        pars.add_argument("--wd_text_angle_offset_deg", type=float, default=0.0)
        pars.add_argument("--wd_font_family", type=str, default="Times New Roman")
        pars.add_argument("--wd_font_preset", type=str, default="Times New Roman")
        pars.add_argument("--wd_font_custom", type=str, default="")
        pars.add_argument("--wd_font_size_mm", type=float, default=2.6)
        pars.add_argument("--wd_text_baseline", type=str, default="optical",
                          choices=["optical", "alphabetic", "central", "middle", "hanging"])
        pars.add_argument("--wd_number_orientation", type=str, default="upright",
                          choices=["upright", "tangent", "radial", "tangent_readable"])
        pars.add_argument("--wd_show_hour_markers", type=inkex.Boolean, default=True)
        pars.add_argument("--wd_hour_marker_radius_mm", type=float, default=12.8)
        pars.add_argument("--wd_hour_marker_w_mm", type=float, default=0.7)
        pars.add_argument("--wd_hour_marker_h_mm", type=float, default=1.8)
        pars.add_argument("--wd_hour_marker_align", type=str, default="outer",
                          choices=["outer", "center", "inner"])
        pars.add_argument("--wd_show_minute_ticks", type=inkex.Boolean, default=True)
        pars.add_argument("--wd_minute_tick_radius_mm", type=float, default=13.6)
        pars.add_argument("--wd_minute_tick_w_mm", type=float, default=0.25)
        pars.add_argument("--wd_minute_tick_h_mm", type=float, default=1.0)
        pars.add_argument("--wd_five_minute_scale", type=float, default=1.7)
        pars.add_argument("--wd_minute_tick_align", type=str, default="outer",
                          choices=["outer", "center", "inner"])
        pars.add_argument("--wd_group_name", type=str, default="watch-dial")

        # ---- Blank Movement Template (bk_) ----
        pars.add_argument("--bk_movement_preset", type=str, default="nh35")
        pars.add_argument("--bk_draw_outline", type=inkex.Boolean, default=True)
        pars.add_argument("--bk_outline_stroke_mm", type=float, default=0.12)
        pars.add_argument("--bk_compensate_outline", type=inkex.Boolean, default=True)
        pars.add_argument("--bk_draw_center_hole", type=inkex.Boolean, default=True)
        pars.add_argument("--bk_draw_hand_holes", type=inkex.Boolean, default=True)
        pars.add_argument("--bk_draw_date_window", type=inkex.Boolean, default=True)
        pars.add_argument("--bk_draw_subdial", type=inkex.Boolean, default=True)
        pars.add_argument("--bk_draw_dial_feet", type=inkex.Boolean, default=True)
        pars.add_argument("--bk_group_name", type=str, default="dial-template")

        # ---- Classic / old-world patterns (cp_) ----
        pars.add_argument("--cp_dial_diameter_mm", type=float, default=28.5)
        pars.add_argument("--cp_draw_outline", type=inkex.Boolean, default=True)
        pars.add_argument("--cp_outline_stroke_mm", type=float, default=0.12)
        pars.add_argument("--cp_outline_compensate_stroke", type=inkex.Boolean, default=True)
        pars.add_argument("--cp_clip_to_circle", type=inkex.Boolean, default=True)
        pars.add_argument("--cp_inner_radius_mm", type=float, default=0.0)
        pars.add_argument("--cp_pattern_type", type=str, default="guilloche",
                          choices=["guilloche", "concentric", "sunburst", "crosshatch"])
        pars.add_argument("--cp_stroke_mm", type=float, default=0.10)
        pars.add_argument("--cp_stroke_color", type=str, default="#000000")
        pars.add_argument("--cp_stroke_opacity", type=float, default=0.35)
        pars.add_argument("--cp_ring_spacing_mm", type=float, default=0.6)
        pars.add_argument("--cp_rays", type=int, default=120)
        pars.add_argument("--cp_lobes", type=int, default=12)
        pars.add_argument("--cp_amplitude_mm", type=float, default=1.2)
        pars.add_argument("--cp_points", type=int, default=1200)
        pars.add_argument("--cp_guilloche_fill", type=inkex.Boolean, default=False)
        pars.add_argument("--cp_band_spacing_mm", type=float, default=0.35)
        pars.add_argument("--cp_hatch_spacing_mm", type=float, default=0.7)
        pars.add_argument("--cp_hatch_angle_deg", type=float, default=35.0)
        pars.add_argument("--cp_hatch_double", type=inkex.Boolean, default=True)
        pars.add_argument("--cp_auto_complex", type=inkex.Boolean, default=False)
        pars.add_argument("--cp_complex_preset", type=str, default="rosette_stack",
                          choices=["rosette_stack", "breguet", "modern", "pocketwatch"])
        pars.add_argument("--cp_layers", type=int, default=4)
        pars.add_argument("--cp_seed", type=int, default=1)
        pars.add_argument("--cp_rotate_jitter_deg", type=float, default=6.0)
        pars.add_argument("--cp_opacity_decay", type=float, default=0.75)
        pars.add_argument("--cp_stroke_decay", type=float, default=0.85)
        pars.add_argument("--cp_lobe_jitter", type=int, default=10)
        pars.add_argument("--cp_amp_decay", type=float, default=0.70)
        pars.add_argument("--cp_group_name", type=str, default="dial-pattern")

        # ---- Rose Engine (re_) ----
        pars.add_argument("--re_preset_mode", type=str, default="custom")
        pars.add_argument("--re_preset", type=str, default="sine")
        pars.add_argument("--re_lobes", type=int, default=18)
        pars.add_argument("--re_amplitude", type=float, default=1.2)
        pars.add_argument("--re_radius", type=float, default=12.5)
        pars.add_argument("--re_multiply", type=inkex.Boolean, default=True)
        pars.add_argument("--re_copies", type=int, default=15)
        pars.add_argument("--re_spacing", type=float, default=0.4)
        pars.add_argument("--re_twist", type=float, default=1.0)
        pars.add_argument("--re_softness", type=float, default=0.1)
        pars.add_argument("--re_taper", type=float, default=0.0)
        pars.add_argument("--re_group_name", type=str, default="rose-engine")

        # ---- Perlage (pg_) ----
        pars.add_argument("--pg_pattern", type=str, default="staggered")
        pars.add_argument("--pg_outer_diameter", type=float, default=29.0)
        pars.add_argument("--pg_center_hole_diameter", type=float, default=0.0)
        pars.add_argument("--pg_spot_diameter", type=float, default=0.35)
        pars.add_argument("--pg_spacing_x", type=float, default=0.75)
        pars.add_argument("--pg_spacing_y", type=float, default=0.75)
        pars.add_argument("--pg_rotation_deg", type=float, default=0.0)
        pars.add_argument("--pg_jitter_xy", type=float, default=0.0)
        pars.add_argument("--pg_skip_percent", type=float, default=0.0)
        pars.add_argument("--pg_seed", type=int, default=7)
        pars.add_argument("--pg_draw_guides", type=inkex.Boolean, default=True)
        pars.add_argument("--pg_guide_stroke_width", type=float, default=0.05)
        pars.add_argument("--pg_group_name", type=str, default="perlage")

        # ---- Modern / new-world patterns (mp_) ----
        pars.add_argument("--mp_dial_diameter_mm", type=float, default=28.5)
        pars.add_argument("--mp_inner_radius_mm", type=float, default=0.0)
        pars.add_argument("--mp_clip_to_circle", type=inkex.Boolean, default=True)
        pars.add_argument("--mp_draw_outline", type=inkex.Boolean, default=False)
        pars.add_argument("--mp_outline_stroke_mm", type=float, default=0.12)
        pars.add_argument("--mp_pattern_type", type=str, default="mondrian")
        pars.add_argument("--mp_seed", type=int, default=1)
        pars.add_argument("--mp_stroke_mm", type=float, default=0.10)
        pars.add_argument("--mp_stroke_color", type=str, default="#000000")
        pars.add_argument("--mp_stroke_opacity", type=float, default=0.35)
        pars.add_argument("--mp_mondrian_density", type=float, default=0.6)
        pars.add_argument("--mp_mondrian_line_mm", type=float, default=0.35)
        pars.add_argument("--mp_mondrian_palette", type=str, default="classic")
        pars.add_argument("--mp_mondrian_fill_opacity", type=float, default=1.0)
        pars.add_argument("--mp_op_line_spacing_mm", type=float, default=0.35)
        pars.add_argument("--mp_op_warp_strength_mm", type=float, default=0.70)
        pars.add_argument("--mp_op_warp_frequency", type=float, default=6.0)
        pars.add_argument("--mp_op_rotate_deg", type=float, default=0.0)
        pars.add_argument("--mp_spiral_turns", type=float, default=5.0)
        pars.add_argument("--mp_spiral_stripe_width_mm", type=float, default=0.35)
        pars.add_argument("--mp_paper_speckle_density", type=float, default=18.0)
        pars.add_argument("--mp_paper_speckle_radius_mm", type=float, default=0.06)
        pars.add_argument("--mp_paper_fiber_count", type=int, default=1200)
        pars.add_argument("--mp_paper_fiber_length_mm", type=float, default=0.55)
        pars.add_argument("--mp_paper_fiber_jitter_mm", type=float, default=0.12)
        pars.add_argument("--mp_paper_color", type=str, default="#000000")
        pars.add_argument("--mp_paper_opacity", type=float, default=0.10)
        pars.add_argument("--mp_linen_thread_spacing_mm", type=float, default=0.35)
        pars.add_argument("--mp_linen_waviness_mm", type=float, default=0.10)
        pars.add_argument("--mp_linen_waviness_freq", type=float, default=7.0)
        pars.add_argument("--mp_linen_rotate_deg", type=float, default=0.0)
        pars.add_argument("--mp_linen_color", type=str, default="#000000")
        pars.add_argument("--mp_linen_opacity", type=float, default=0.18)
        pars.add_argument("--mp_group_name", type=str, default="modern-dial-pattern")

    # ------------------------------------------------------------------
    def effect(self):
        # self.options.ui is the name of the open notebook tab (one tab per tool).
        tool = (self.options.ui or "dial").strip().lower()
        dispatch = {
            "dial": self.tool_dial,
            "blank": self.tool_blank,
            "classic": self.tool_classic,
            "rose": self.tool_rose,
            "perlage": self.tool_perlage,
            "modern": self.tool_modern,
        }
        handler = dispatch.get(tool, self.tool_dial)
        handler()

    # ------------------------------------------------------------------
    # Tool: Watch Dial Generator
    # ------------------------------------------------------------------
    def tool_dial(self):
        o = self.options
        svg = self.document.getroot()
        cx, cy = get_doc_center(svg)

        g = add_root_group(svg, o.wd_group_name or "watch-dial", o.wd_group_name or "watch-dial")

        stroke_w_mm = o.wd_dial_outline_stroke_mm
        stroke_w = str(mm_to_uu(svg, stroke_w_mm))

        comp = stroke_w_mm if o.wd_outline_compensate_stroke else 0.0
        dial_r_mm = (o.wd_dial_diameter_mm - comp) / 2.0
        center_r_mm = (o.wd_center_hole_mm - comp) / 2.0

        if o.wd_draw_dial_outline:
            c = Circle()
            c.set("cx", str(cx)); c.set("cy", str(cy)); c.set("r", str(mm_to_uu(svg, dial_r_mm)))
            c.style = {"fill": "none", "stroke": "#000", "stroke-width": stroke_w}
            g.add(c)

        if o.wd_draw_center_hole:
            h = Circle()
            h.set("cx", str(cx)); h.set("cy", str(cy)); h.set("r", str(mm_to_uu(svg, max(0.0, center_r_mm))))
            h.style = {"fill": "none", "stroke": "#000", "stroke-width": stroke_w}
            g.add(h)

        if o.wd_show_hour_markers:
            r_base = mm_to_uu(svg, o.wd_hour_marker_radius_mm)
            w = mm_to_uu(svg, o.wd_hour_marker_w_mm)
            hh = mm_to_uu(svg, o.wd_hour_marker_h_mm)
            r = aligned_radius(r_base, hh, o.wd_hour_marker_align)
            for i in range(12):
                ang = (o.wd_start_angle_deg + i * 30.0) % 360.0
                if not o.wd_clockwise:
                    ang = (-ang) % 360.0
                x, y = polar(cx, cy, r, ang)
                rect = Rectangle()
                rect.style = {"fill": "#000", "stroke": "none"}
                set_rect_geom(rect, x - w / 2.0, y - hh / 2.0, w, hh)
                rect.set("transform", f"rotate({ang},{x},{y})")
                g.add(rect)

        if o.wd_show_minute_ticks:
            r_base = mm_to_uu(svg, o.wd_minute_tick_radius_mm)
            w = mm_to_uu(svg, o.wd_minute_tick_w_mm)
            h0 = mm_to_uu(svg, o.wd_minute_tick_h_mm)
            for i in range(60):
                ang = (o.wd_start_angle_deg + i * 6.0) % 360.0
                if not o.wd_clockwise:
                    ang = (-ang) % 360.0
                scale = o.wd_five_minute_scale if (i % 5 == 0) else 1.0
                hh = h0 * scale
                r = aligned_radius(r_base, hh, o.wd_minute_tick_align)
                x, y = polar(cx, cy, r, ang)
                rect = Rectangle()
                rect.style = {"fill": "#000", "stroke": "none"}
                set_rect_geom(rect, x - w / 2.0, y - hh / 2.0, w, hh)
                rect.set("transform", f"rotate({ang},{x},{y})")
                g.add(rect)

        if o.wd_text_mode == "arabic":
            labels = list(ARABIC_12_FIRST)
        elif o.wd_text_mode == "roman":
            labels = list(ROMAN_12_FIRST_IIII if (o.wd_roman_four_style == "IIII") else ROMAN_12_FIRST_IV)
        else:
            labels = read_labels_from_csv(o.wd_labels_csv)

        if labels:
            r = mm_to_uu(svg, o.wd_text_radius_mm + o.wd_text_radial_offset_mm)
            font_uu = mm_to_uu(svg, o.wd_font_size_mm)

            preset = (o.wd_font_preset or '').strip()
            custom = (o.wd_font_custom or '').strip()
            base = (o.wd_font_family or '').strip() or 'Times New Roman'
            if preset and preset.lower() != 'custom':
                font_family_used = preset
            elif custom:
                font_family_used = custom
            else:
                font_family_used = base

            n = len(labels)
            step = 30.0 if n == 12 else 360.0 / float(n)
            for i, label in enumerate(labels):
                if n == 12 and o.wd_omit_three and i == 3:
                    continue
                ang = (o.wd_start_angle_deg + o.wd_text_angle_offset_deg + i * step) % 360.0
                if not o.wd_clockwise:
                    ang = (-ang) % 360.0
                x, y = polar(cx, cy, r, ang)
                t = TextElement()
                t.text = label
                style = {
                    "font-family": font_family_used,
                    "font-size": str(font_uu),
                    "text-anchor": "middle",
                }
                if o.wd_text_baseline == "optical":
                    # No SVG baseline centers a digit (they follow font metrics,
                    # not the glyph's visual center). Anchor on the alphabetic
                    # baseline and nudge down by ~half the cap height so the
                    # numeral centers exactly on (x, y) -- font/renderer agnostic.
                    style["dominant-baseline"] = "alphabetic"
                    t.set("dy", str(OPTICAL_DIGIT_CENTER * font_uu))
                else:
                    style["dominant-baseline"] = o.wd_text_baseline
                t.style = style
                t.set("x", str(x)); t.set("y", str(y))
                rot = rotation_for_number(o.wd_number_orientation, ang)
                if rot != 0.0:
                    t.set("transform", f"rotate({rot},{x},{y})")
                g.add(t)

    # ------------------------------------------------------------------
    # Tool: Blank Movement Template
    # ------------------------------------------------------------------
    def tool_blank(self):
        o = self.options
        svg = self.svg
        cx, cy = get_doc_center(svg)
        preset_name = o.bk_movement_preset
        preset = BLANK_PRESETS.get(preset_name)
        g = add_root_group(svg, o.bk_group_name or "dial-template", o.bk_group_name or "dial-template")

        if preset is None:
            self.msg("Custom movement preset selected: no template geometry to draw. "
                     "Use the Watch Dial tool for a custom blank.")
            return

        def mm(v):
            return mm_to_uu(svg, v)

        if o.bk_draw_outline:
            r = preset["dial"] / 2
            if o.bk_compensate_outline:
                r -= o.bk_outline_stroke_mm / 2
            c = Circle(); c.center = (cx, cy); c.radius = mm(r)
            c.style = {"fill": "none", "stroke": "#777", "stroke-width": str(mm(o.bk_outline_stroke_mm))}
            g.add(c)

        if o.bk_draw_center_hole:
            c = Circle(); c.center = (cx, cy); c.radius = mm(preset["center"] / 2)
            c.style = {"fill": "none", "stroke": "#777", "stroke-width": str(mm(0.1))}
            g.add(c)

        if o.bk_draw_hand_holes:
            # Hand-bore reference circles (hour / minute / second hubs). They are
            # small and concentric -- nested inside the larger center hole -- so
            # give each a distinct color and label to make it visible/identifiable.
            hand_colors = ["#e8000b", "#1f77b4", "#2ca02c", "#ff7f0e"]
            hand_names = ["hour", "minute", "second", "hand"]
            for i, d in enumerate(preset["hands"]):
                c = Circle(); c.center = (cx, cy); c.radius = mm(d / 2)
                c.label = f"hand-hole-{hand_names[i] if i < len(hand_names) else i + 1}"
                c.style = {"fill": "none",
                           "stroke": hand_colors[i % len(hand_colors)],
                           "stroke-width": str(mm(0.08))}
                g.add(c)

        if preset_name == "nh35" and o.bk_draw_date_window and "date" in preset:
            w, h, r = preset["date"]
            rect = Rectangle()
            rect.set("x", str(cx + mm(r) - mm(w / 2)))
            rect.set("y", str(cy - mm(h / 2)))
            rect.set("width", str(mm(w)))
            rect.set("height", str(mm(h)))
            rect.style = {"fill": "none", "stroke": "#777", "stroke-width": str(mm(0.1))}
            g.add(rect)

        if preset_name == "st36" and o.bk_draw_subdial and "sub" in preset:
            x, y = preset["sub"]
            c = Circle(); c.center = (cx - mm(x), cy); c.radius = mm(6.0)
            c.style = {"fill": "none", "stroke": "#777", "stroke-width": str(mm(0.1))}
            g.add(c)

        if o.bk_draw_dial_feet and "feet" in preset:
            for x, y in preset["feet"]:
                c = Circle(); c.center = (cx + mm(x), cy + mm(y)); c.radius = mm(0.5)
                c.style = {"fill": "none", "stroke": "#aaa", "stroke-width": str(mm(0.08))}
                g.add(c)

    # ------------------------------------------------------------------
    # Tool: Classic / old-world patterns
    # ------------------------------------------------------------------
    def _classic_draw_one(self, svg, layer_g, cx, cy, r_outer, r_inner, ptype,
                          stroke_w, stroke_color, opacity, overrides):
        o = self.options
        if ptype == "concentric":
            spacing = overrides.get("ring_spacing", mm_to_uu(svg, o.cp_ring_spacing_mm))
            pattern_concentric(svg, layer_g, cx, cy, r_outer, r_inner, spacing, stroke_w, stroke_color, opacity)
        elif ptype == "sunburst":
            rays = overrides.get("rays", o.cp_rays)
            pattern_sunburst(svg, layer_g, cx, cy, r_outer, r_inner, rays, stroke_w, stroke_color, opacity)
        elif ptype == "crosshatch":
            hs = overrides.get("hatch_spacing", mm_to_uu(svg, o.cp_hatch_spacing_mm))
            ha = overrides.get("hatch_angle", o.cp_hatch_angle_deg)
            hd = overrides.get("hatch_double", bool(o.cp_hatch_double))
            pattern_crosshatch(svg, layer_g, cx, cy, r_outer, hs, ha, hd, stroke_w, stroke_color, opacity)
        else:
            lobes = overrides.get("lobes", o.cp_lobes)
            amp = overrides.get("amplitude", mm_to_uu(svg, o.cp_amplitude_mm))
            pts = overrides.get("points", o.cp_points)
            if bool(o.cp_guilloche_fill):
                bs = mm_to_uu(svg, float(o.cp_band_spacing_mm))
                pattern_guilloche_field(svg, layer_g, cx, cy, r_outer, r_inner, lobes, amp, pts,
                                        stroke_w, stroke_color, opacity, bs)
            else:
                pattern_guilloche(svg, layer_g, cx, cy, r_outer, lobes, amp, pts, stroke_w, stroke_color, opacity)

    def tool_classic(self):
        o = self.options
        svg = self.document.getroot()
        cx, cy = get_doc_center(svg)

        outline_w_mm = o.cp_outline_stroke_mm
        dial_r_mm = (o.cp_dial_diameter_mm - (outline_w_mm if o.cp_outline_compensate_stroke else 0.0)) / 2.0
        r_outer = mm_to_uu(svg, dial_r_mm)
        r_inner = mm_to_uu(svg, max(0.0, o.cp_inner_radius_mm))

        gid = o.cp_group_name or "dial-pattern"
        g = add_root_group(svg, gid, gid)

        pattern_g = Group()
        pattern_g.label = "pattern"
        pattern_g.set("id", gid + "-pattern")
        g.add(pattern_g)

        if o.cp_clip_to_circle:
            clip_id = gid + "-clip-" + uuid.uuid4().hex[:6]
            clip_group_to_circle(svg, pattern_g, cx, cy, r_outer, clip_id)

        base_stroke = mm_to_uu(svg, o.cp_stroke_mm)
        base_opacity = float(o.cp_stroke_opacity)
        stroke_color = normalize_color(o.cp_stroke_color)
        rnd = random.Random(int(o.cp_seed))

        if not o.cp_auto_complex:
            self._classic_draw_one(svg, pattern_g, cx, cy, r_outer, r_inner,
                                   o.cp_pattern_type, base_stroke, stroke_color, base_opacity, {})
        else:
            layers = max(1, int(o.cp_layers))
            preset = (o.cp_complex_preset or "rosette_stack").strip().lower()

            def make_layer(idx, rotate_deg):
                lg = Group()
                lg.label = f"layer-{idx + 1}"
                lg.set("id", f"{pattern_g.get('id')}-layer-{idx + 1}")
                if abs(rotate_deg) > 1e-9:
                    lg.set("transform", f"rotate({rotate_deg:.6f},{cx},{cy})")
                pattern_g.add(lg)
                return lg

            if preset == "breguet":
                plan = [
                    ("concentric", lambda i: {"ring_spacing": mm_to_uu(svg, 0.45)}),
                    ("guilloche", lambda i: {"lobes": 12 + rnd.randint(-2, 2), "amplitude": mm_to_uu(svg, 1.0), "points": max(1600, int(o.cp_points))}),
                    ("sunburst", lambda i: {"rays": 240}),
                    ("guilloche", lambda i: {"lobes": 36 + rnd.randint(-6, 6), "amplitude": mm_to_uu(svg, 0.28), "points": max(2400, int(o.cp_points))}),
                ]
                layers = max(layers, 4)
            elif preset == "modern":
                plan = [
                    ("sunburst", lambda i: {"rays": 300}),
                    ("crosshatch", lambda i: {"hatch_spacing": mm_to_uu(svg, 0.6), "hatch_angle": 35.0, "hatch_double": True}),
                    ("guilloche", lambda i: {"lobes": 18 + rnd.randint(-3, 3), "amplitude": mm_to_uu(svg, 0.75), "points": max(2000, int(o.cp_points))}),
                    ("guilloche", lambda i: {"lobes": 48 + rnd.randint(-8, 8), "amplitude": mm_to_uu(svg, 0.22), "points": max(3000, int(o.cp_points))}),
                ]
                layers = max(layers, 4)
            elif preset == "pocketwatch":
                plan = [("guilloche", lambda i: {})] * layers
            else:
                plan = [("guilloche", lambda i: {})] * layers

            for i in range(layers):
                ptype, ofn = plan[i % len(plan)]
                overrides = ofn(i) if callable(ofn) else {}

                if ptype == "guilloche":
                    base_lobes = overrides.get("lobes", int(o.cp_lobes))
                    base_amp = overrides.get("amplitude", mm_to_uu(svg, o.cp_amplitude_mm))
                    if "lobes" not in overrides:
                        base_lobes = max(2, base_lobes + rnd.randint(-int(o.cp_lobe_jitter), int(o.cp_lobe_jitter)))
                        overrides["lobes"] = base_lobes
                    if "amplitude" not in overrides:
                        overrides["amplitude"] = base_amp * (float(o.cp_amp_decay) ** i)
                    if "points" not in overrides:
                        p0 = int(o.cp_points)
                        overrides["points"] = max(800, int(p0 * (1.0 + 0.10 * i)))

                if ptype == "crosshatch":
                    if "hatch_angle" not in overrides:
                        overrides["hatch_angle"] = float(o.cp_hatch_angle_deg) + rnd.uniform(-5.0, 5.0)

                sw = base_stroke * (float(o.cp_stroke_decay) ** i)
                op = base_opacity * (float(o.cp_opacity_decay) ** i)
                op = max(0.02, min(1.0, op))
                rot = rnd.uniform(-float(o.cp_rotate_jitter_deg), float(o.cp_rotate_jitter_deg))
                lg = make_layer(i, rot)
                self._classic_draw_one(svg, lg, cx, cy, r_outer, r_inner, ptype, sw, stroke_color, op, overrides)

        if o.cp_draw_outline:
            stroke_outline = mm_to_uu(svg, outline_w_mm)
            c = Circle()
            c.set('cx', str(cx)); c.set('cy', str(cy)); c.set('r', str(r_outer))
            set_style(c, {"fill": "none", "stroke": "#000000", "stroke-width": str(stroke_outline)})
            g.add(c)

    # ------------------------------------------------------------------
    # Tool: Rose Engine
    # ------------------------------------------------------------------
    def tool_rose(self):
        o = self.options
        svg = self.document.getroot()
        cx, cy = get_doc_center(svg)

        if o.re_preset_mode == "default_25":
            p, l, a, r, m, c, s, t, soft, taper = "sine", 18, 1.2, 12.5, True, 15, 0.4, 1.0, 0.1, 0.0
        elif o.re_preset_mode == "small_cog":
            p, l, a, r, m, c, s, t, soft, taper = "square", 12, 0.8, 5.0, False, 1, 0.5, 0.0, 0.05, 0.0
        else:
            p, l, a, r, m, c, s, t, soft, taper = (o.re_preset, o.re_lobes, o.re_amplitude, o.re_radius,
                                                   o.re_multiply, o.re_copies, o.re_spacing, o.re_twist,
                                                   o.re_softness, o.re_taper)

        # Rose-engine radii are authored in mm; convert to user units for sizing.
        a_uu = mm_to_uu(svg, a)
        r_uu = mm_to_uu(svg, r)
        s_uu = mm_to_uu(svg, s)
        stroke_uu = mm_to_uu(svg, 0.1)

        gid = o.re_group_name or "rose-engine"
        container = add_root_group(svg, gid, gid)
        iterations = c if m else 1

        # Samples per ring: keep density high even for large lobe counts
        # (>= ~40 samples per lobe) so curves don't facet.
        samples = max(1000, int(max(int(l), 1) * 40))

        for ring_idx in range(iterations):
            points = []
            curr_r = r_uu - (ring_idx * s_uu)
            if curr_r < 0:
                break
            # A fixed rosette has constant throw; taper toward the center is an
            # optional artistic control (default 0 = mechanically faithful).
            current_amplitude = a_uu * (1.0 - (taper * (ring_idx / max(1, iterations - 1))))
            curr_ph = ring_idx * math.radians(t)

            # range(samples + 1) makes the final point land exactly on theta=2*pi
            # (coincident with the start) so the closed loop has no chord seam.
            for i in range(samples + 1):
                theta = (i / samples) * 2 * math.pi
                if p == "sine":
                    wave_r = curr_r + current_amplitude * math.sin(l * theta + curr_ph)
                elif p == "square":
                    sharpness = 1.0 / max(0.001, soft)
                    wave_r = curr_r + current_amplitude * math.tanh(math.sin(l * theta + curr_ph) * sharpness)
                elif p == "epicycloid":
                    # Cusp count is set by the lobe count (like a geometric chuck's
                    # gear ratio) and held constant across passes; only the figure
                    # size and phase change per ring. Scale so the epicycloid's
                    # outer radius matches this pass's base radius.
                    k = max(1, int(l))
                    scale_a = curr_r / (k + 1)
                    ang = theta + curr_ph
                    points.append(f"{cx + scale_a * ((k + 1) * math.cos(ang) - math.cos((k + 1) * ang))},"
                                  f"{cy + scale_a * ((k + 1) * math.sin(ang) - math.sin((k + 1) * ang))}")
                    continue
                points.append(f"{cx + wave_r * math.cos(theta)},{cy + wave_r * math.sin(theta)}")

            # Close the loop ('Z') so the line returns to its start -- real
            # guilloche lines are continuous closed curves (removes ~0.16mm seam).
            path = new_path("M " + " L ".join(points) + " Z")
            set_style(path, {"stroke": "#000", "fill": "none", "stroke-width": str(stroke_uu)})
            container.add(path)

    # ------------------------------------------------------------------
    # Tool: Perlage
    # ------------------------------------------------------------------
    def tool_perlage(self):
        o = self.options
        svg = self.svg
        cx, cy = get_doc_center(svg)

        outer_r = max(0.01, o.pg_outer_diameter) / 2.0
        inner_r = max(0.0, o.pg_center_hole_diameter) / 2.0
        spacing_x = max(0.01, o.pg_spacing_x)
        spacing_y = max(0.01, o.pg_spacing_y)
        spot_d = max(0.01, o.pg_spot_diameter)
        rot = math.radians(o.pg_rotation_deg)
        skip_prob = min(100.0, max(0.0, o.pg_skip_percent)) / 100.0
        jitter = max(0.0, o.pg_jitter_xy)
        rng = random.Random(o.pg_seed)
        pattern = (o.pg_pattern or 'staggered').strip().lower()

        gid = o.pg_group_name or "perlage"
        group = add_root_group(svg, gid, gid)

        def mm(v):
            return mm_to_uu(svg, v)

        outer_r_uu = mm(outer_r)
        inner_r_uu = mm(inner_r)
        spot_r_uu = mm(spot_d / 2.0)
        guide_sw = mm(o.pg_guide_stroke_width)

        def add_circle(x_px, y_px, r_px, style):
            c = Circle()
            c.set('cx', str(x_px)); c.set('cy', str(y_px)); c.set('r', str(r_px))
            c.set('style', str(inkex.Style(style)))
            group.add(c)

        spot_style = {'fill': 'none', 'stroke': '#000000', 'stroke-width': str(mm(0.03))}
        guide_style = {
            'fill': 'none', 'stroke': '#0000ff', 'stroke-width': str(guide_sw),
            'stroke-dasharray': f'{guide_sw * 4},{guide_sw * 2}',
        }

        spots = []

        def maybe_add_spot(x_mm, y_mm):
            if rng.random() < skip_prob:
                return
            if jitter > 0:
                x_mm += rng.uniform(-jitter, jitter)
                y_mm += rng.uniform(-jitter, jitter)
            rr = math.hypot(x_mm, y_mm)
            if rr > outer_r:
                return
            if inner_r > 0 and rr < inner_r:
                return
            xr, yr = rotate_point(x_mm, y_mm, rot)
            spots.append((cx + mm(xr), cy + mm(yr)))

        if pattern in ('grid', 'staggered'):
            y = -outer_r
            row = 0
            while y <= outer_r + 1e-9:
                x_offset = (spacing_x / 2.0) if (pattern == 'staggered' and row % 2 == 1) else 0.0
                x = -outer_r + x_offset
                while x <= outer_r + 1e-9:
                    maybe_add_spot(x, y)
                    x += spacing_x
                y += spacing_y
                row += 1
        elif pattern == 'spiral':
            pitch = max(0.05, spacing_x)
            theta = 0.0
            dtheta = 0.18
            last = None
            while True:
                r = pitch * theta / (2.0 * math.pi)
                if r > outer_r:
                    break
                x = r * math.cos(theta)
                y = r * math.sin(theta)
                if inner_r == 0 or r >= inner_r:
                    if last is None or math.hypot(x - last[0], y - last[1]) >= min(spacing_x, spacing_y) * 0.85:
                        maybe_add_spot(x, y)
                        last = (x, y)
                theta += dtheta
        elif pattern == 'radial':
            ring_step = max(0.05, spacing_y)
            r = inner_r if inner_r > 0 else 0.0
            ring_index = 0
            while r <= outer_r + 1e-9:
                if ring_index == 0 and r == 0:
                    maybe_add_spot(0.0, 0.0)
                else:
                    circumference = max(0.01, 2.0 * math.pi * max(r, ring_step))
                    count = max(6, int(round(circumference / max(0.05, spacing_x))))
                    phase = 0.5 if ring_index % 2 else 0.0
                    for i in range(count):
                        a = 2.0 * math.pi * ((i + phase) / count)
                        maybe_add_spot(r * math.cos(a), r * math.sin(a))
                r += ring_step
                ring_index += 1
        else:
            raise inkex.AbortExtension(f'Unsupported perlage pattern: {pattern}')

        for x_px, y_px in spots:
            add_circle(x_px, y_px, spot_r_uu, spot_style)

        if o.pg_draw_guides:
            add_circle(cx, cy, outer_r_uu, guide_style)
            if inner_r > 0:
                add_circle(cx, cy, inner_r_uu, guide_style)

        self.msg(f'Created {len(spots)} perlage spots.')

    # ------------------------------------------------------------------
    # Tool: Modern / new-world patterns
    # ------------------------------------------------------------------
    def tool_modern(self):
        o = self.options
        svg = self.document.getroot()
        cx, cy = get_doc_center(svg)
        r_outer = mm_to_uu(svg, o.mp_dial_diameter_mm / 2)
        r_inner = mm_to_uu(svg, max(0, o.mp_inner_radius_mm))
        rnd = random.Random(int(o.mp_seed))

        gid = o.mp_group_name or "modern-dial-pattern"
        g = add_root_group(svg, gid, gid)

        pg = Group()
        g.add(pg)

        if o.mp_clip_to_circle:
            clip_group_to_circle(svg, pg, cx, cy, r_outer, f"clip-{uuid.uuid4().hex[:6]}")

        stroke_w = mm_to_uu(svg, o.mp_stroke_mm)
        ptype = o.mp_pattern_type

        if ptype == "mondrian":
            pattern_mondrian(svg, pg, cx, cy, r_outer, rnd,
                             o.mp_mondrian_density, mm_to_uu(svg, o.mp_mondrian_line_mm),
                             o.mp_mondrian_palette, o.mp_mondrian_fill_opacity)
        elif ptype == "op_waves":
            pattern_op_waves(svg, pg, cx, cy, r_outer, r_inner, rnd,
                             mm_to_uu(svg, o.mp_op_line_spacing_mm), stroke_w,
                             normalize_color(o.mp_stroke_color), o.mp_stroke_opacity,
                             mm_to_uu(svg, o.mp_op_warp_strength_mm), o.mp_op_warp_frequency,
                             o.mp_op_rotate_deg)
        elif ptype == "paper_texture":
            pattern_paper_texture(svg, pg, cx, cy, r_outer, r_inner, rnd,
                                  o.mp_paper_speckle_density, o.mp_paper_speckle_radius_mm,
                                  o.mp_paper_fiber_count, o.mp_paper_fiber_length_mm,
                                  o.mp_paper_fiber_jitter_mm, normalize_color(o.mp_paper_color),
                                  o.mp_paper_opacity)
        elif ptype == "linen_texture":
            pattern_linen_texture(svg, pg, cx, cy, r_outer, r_inner, rnd,
                                  o.mp_linen_thread_spacing_mm, o.mp_linen_waviness_mm,
                                  o.mp_linen_waviness_freq, o.mp_linen_rotate_deg,
                                  normalize_color(o.mp_linen_color), o.mp_linen_opacity, o.mp_stroke_mm)
        else:
            pattern_spiral_stripes(svg, pg, cx, cy, r_outer, r_inner, o.mp_spiral_turns,
                                   mm_to_uu(svg, o.mp_spiral_stripe_width_mm), stroke_w,
                                   normalize_color(o.mp_stroke_color), o.mp_stroke_opacity)

        if o.mp_draw_outline:
            c = Circle()
            c.set('cx', str(cx)); c.set('cy', str(cy)); c.set('r', str(r_outer))
            set_style(c, {"fill": "none", "stroke": "#000000",
                          "stroke-width": str(mm_to_uu(svg, o.mp_outline_stroke_mm))})
            g.add(c)


if __name__ == "__main__":
    WatchDialTools().run()
