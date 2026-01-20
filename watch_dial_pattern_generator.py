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
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Dial Pattern Generator (auto-complex layers)

Adds "Auto complex" mode that generates multiple layered patterns in one click
to achieve rich, watch-like textures without manual duplicating.

Key features:
- Multiple layers (stack) with per-layer variation (lobes/amplitude/rotation/stroke/opacity)
- Presets: rosette stack, Breguet-ish, modern, pocketwatch
- Deterministic randomness via seed
- Still supports single-layer generation when Auto complex is off

Compatibility:
- Uses svg.unittouu("...mm") for correct mm sizing in mm-based docs
- Avoids inkex.utils.random_string; uses uuid4 for ids
"""

import math
import re
import uuid
import random

import inkex
from inkex import Group, Circle

try:
    from inkex import PathElement
except Exception:
    PathElement = None


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


def mm_to_uu(svg, mm: float) -> float:
    try:
        return float(svg.unittouu(f"{mm}mm"))
    except Exception:
        return mm * 96.0 / 25.4


def get_doc_center(svg):
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


def new_path(d: str):
    if PathElement is not None:
        p = PathElement()
    else:
        p = inkex.etree.Element(inkex.addNS('path', 'svg'))
    p.set('d', d)
    return p


def set_style(el, style_dict):
    if hasattr(el, 'style'):
        el.style = style_dict
    else:
        el.set('style', inkex.Style(style_dict))


def polar(cx, cy, r, ang_deg_clockwise_from_12):
    a = math.radians(ang_deg_clockwise_from_12)
    return (cx + r * math.sin(a), cy - r * math.cos(a))


def clip_group_to_circle(svg, group, cx, cy, r, clip_id):
    defs = ensure_defs(svg)
    clip = inkex.etree.Element(inkex.addNS('clipPath', 'svg'))
    clip.set('id', clip_id)

    c = inkex.etree.Element(inkex.addNS('circle', 'svg'))
    c.set('cx', str(cx))
    c.set('cy', str(cy))
    c.set('r', str(r))
    clip.append(c)
    defs.append(clip)

    group.set('clip-path', f'url(#{clip_id})')


def pattern_concentric(svg, g, cx, cy, r_outer, r_inner, spacing, stroke_w, stroke_color, opacity):
    r = max(0.0, r_inner)
    while r <= r_outer + 1e-9:
        c = Circle()
        c.set('cx', str(cx))
        c.set('cy', str(cy))
        c.set('r', str(r))
        set_style(c, {
            "fill": "none",
            "stroke": stroke_color,
            "stroke-width": str(stroke_w),
            "stroke-opacity": str(opacity),
        })
        g.add(c)
        r += spacing


def pattern_sunburst(svg, g, cx, cy, r_outer, r_inner, rays, stroke_w, stroke_color, opacity):
    rays = max(4, int(rays))
    step = 360.0 / rays
    for i in range(rays):
        ang = i * step
        x1, y1 = polar(cx, cy, r_inner, ang)
        x2, y2 = polar(cx, cy, r_outer, ang)
        d = f"M {x1:.6f},{y1:.6f} L {x2:.6f},{y2:.6f}"
        p = new_path(d)
        set_style(p, {
            "fill": "none",
            "stroke": stroke_color,
            "stroke-width": str(stroke_w),
            "stroke-opacity": str(opacity),
            "stroke-linecap": "round",
        })
        g.add(p) if hasattr(g, 'add') else g.append(p)


def pattern_crosshatch(svg, g, cx, cy, r_outer, spacing, angle_deg, double, stroke_w, stroke_color, opacity):
    size = r_outer * 2.2
    half = size / 2.0

    def add_set(theta_deg):
        theta = math.radians(theta_deg)
        ux, uy = math.cos(theta), math.sin(theta)
        vx, vy = -uy, ux

        count = int((size / spacing)) + 3
        start = -count // 2
        end = count // 2 + 1
        for i in range(start, end):
            off = i * spacing
            px = cx + off * vx
            py = cy + off * vy
            x1 = px - half * ux
            y1 = py - half * uy
            x2 = px + half * ux
            y2 = py + half * uy
            d = f"M {x1:.6f},{y1:.6f} L {x2:.6f},{y2:.6f}"
            p = new_path(d)
            set_style(p, {
                "fill": "none",
                "stroke": stroke_color,
                "stroke-width": str(stroke_w),
                "stroke-opacity": str(opacity),
                "stroke-linecap": "round",
            })
            g.add(p) if hasattr(g, 'add') else g.append(p)

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
        ang_deg = math.degrees(t)
        x, y = polar(cx, cy, r, ang_deg)
        pts.append((x, y))

    d = f"M {pts[0][0]:.6f},{pts[0][1]:.6f} " + " ".join([f"L {x:.6f},{y:.6f}" for x, y in pts[1:]])
    p = new_path(d)
    set_style(p, {
        "fill": "none",
        "stroke": stroke_color,
        "stroke-width": str(stroke_w),
        "stroke-opacity": str(opacity),
        "stroke-linejoin": "round",
    })
    g.add(p) if hasattr(g, 'add') else g.append(p)


class DialPatternGenerator(inkex.EffectExtension):
    def add_arguments(self, pars):
        # Inkscape notebook tab selector (ignored)
        pars.add_argument("--ui", type=str, default="pattern")

        pars.add_argument("--dial_diameter_mm", type=float, default=28.5)

        pars.add_argument("--draw_outline", type=inkex.Boolean, default=True)
        pars.add_argument("--outline_stroke_mm", type=float, default=0.12)
        pars.add_argument("--outline_compensate_stroke", type=inkex.Boolean, default=True)

        pars.add_argument("--clip_to_circle", type=inkex.Boolean, default=True)
        pars.add_argument("--inner_radius_mm", type=float, default=0.0)

        pars.add_argument("--pattern_type", type=str, default="guilloche",
                          choices=["guilloche", "concentric", "sunburst", "crosshatch"])

        pars.add_argument("--stroke_mm", type=float, default=0.10)
        pars.add_argument("--stroke_color", type=str, default="#000000")
        pars.add_argument("--stroke_opacity", type=float, default=0.35)

        # Concentric
        pars.add_argument("--ring_spacing_mm", type=float, default=0.6)

        # Sunburst
        pars.add_argument("--rays", type=int, default=120)

        # Guilloche
        pars.add_argument("--lobes", type=int, default=12)
        pars.add_argument("--amplitude_mm", type=float, default=1.2)
        pars.add_argument("--points", type=int, default=1200)

        # Crosshatch
        pars.add_argument("--hatch_spacing_mm", type=float, default=0.7)
        pars.add_argument("--hatch_angle_deg", type=float, default=35.0)
        pars.add_argument("--hatch_double", type=inkex.Boolean, default=True)

        # Auto-complex
        pars.add_argument("--auto_complex", type=inkex.Boolean, default=False)
        pars.add_argument("--complex_preset", type=str, default="rosette_stack",
                          choices=["rosette_stack", "breguet", "modern", "pocketwatch"])
        pars.add_argument("--layers", type=int, default=4)
        pars.add_argument("--seed", type=int, default=1)
        pars.add_argument("--rotate_jitter_deg", type=float, default=6.0)
        pars.add_argument("--opacity_decay", type=float, default=0.75)
        pars.add_argument("--stroke_decay", type=float, default=0.85)
        pars.add_argument("--lobe_jitter", type=int, default=10)
        # amplitude per layer will be multiplied by amp_decay^k
        pars.add_argument("--amp_decay", type=float, default=0.70)

        pars.add_argument("--group_name", type=str, default="dial-pattern")

    def _draw_one(self, svg, layer_g, cx, cy, r_outer, r_inner, ptype, stroke_w, stroke_color, opacity, overrides):
        # overrides dict may include: ring_spacing, rays, lobes, amplitude, points, hatch_spacing, hatch_angle, hatch_double
        if ptype == "concentric":
            spacing = overrides.get("ring_spacing", mm_to_uu(svg, self.options.ring_spacing_mm))
            pattern_concentric(svg, layer_g, cx, cy, r_outer, r_inner, spacing, stroke_w, stroke_color, opacity)
        elif ptype == "sunburst":
            rays = overrides.get("rays", self.options.rays)
            pattern_sunburst(svg, layer_g, cx, cy, r_outer, r_inner, rays, stroke_w, stroke_color, opacity)
        elif ptype == "crosshatch":
            hs = overrides.get("hatch_spacing", mm_to_uu(svg, self.options.hatch_spacing_mm))
            ha = overrides.get("hatch_angle", self.options.hatch_angle_deg)
            hd = overrides.get("hatch_double", bool(self.options.hatch_double))
            pattern_crosshatch(svg, layer_g, cx, cy, r_outer, hs, ha, hd, stroke_w, stroke_color, opacity)
        else:
            lobes = overrides.get("lobes", self.options.lobes)
            amp = overrides.get("amplitude", mm_to_uu(svg, self.options.amplitude_mm))
            pts = overrides.get("points", self.options.points)
            pattern_guilloche(svg, layer_g, cx, cy, r_outer, lobes, amp, pts, stroke_w, stroke_color, opacity)

    def effect(self):
        svg = self.document.getroot()
        cx, cy = get_doc_center(svg)

        # Radii
        outline_w_mm = self.options.outline_stroke_mm
        dial_r_mm = (self.options.dial_diameter_mm - (outline_w_mm if self.options.outline_compensate_stroke else 0.0)) / 2.0
        r_outer = mm_to_uu(svg, dial_r_mm)
        r_inner = mm_to_uu(svg, max(0.0, self.options.inner_radius_mm))

        # Root group
        g = Group()
        g.label = self.options.group_name or "dial-pattern"
        g.set("id", self.options.group_name or "dial-pattern")
        svg.add(g)

        # Pattern group (clipped)
        pattern_g = Group()
        pattern_g.label = "pattern"
        pattern_g.set("id", (g.get("id") + "-pattern"))
        g.add(pattern_g)

        if self.options.clip_to_circle:
            clip_id = (g.get("id") + "-clip-" + uuid.uuid4().hex[:6])
            clip_group_to_circle(svg, pattern_g, cx, cy, r_outer, clip_id)

        base_stroke = mm_to_uu(svg, self.options.stroke_mm)
        base_opacity = float(self.options.stroke_opacity)
        stroke_color = self.options.stroke_color

        rnd = random.Random(int(self.options.seed))

        if not self.options.auto_complex:
            # Single-layer (existing behavior)
            self._draw_one(
                svg, pattern_g, cx, cy, r_outer, r_inner,
                self.options.pattern_type,
                base_stroke, stroke_color, base_opacity,
                {}
            )
        else:
            # Multi-layer presets
            layers = max(1, int(self.options.layers))
            preset = (self.options.complex_preset or "rosette_stack").strip().lower()

            # helper to create a layer group with optional rotation
            def make_layer(idx, rotate_deg):
                lg = Group()
                lg.label = f"layer-{idx+1}"
                lg.set("id", f"{pattern_g.get('id')}-layer-{idx+1}")
                if abs(rotate_deg) > 1e-9:
                    lg.set("transform", f"rotate({rotate_deg:.6f},{cx},{cy})")
                pattern_g.add(lg)
                return lg

            # Preset definitions as a list of (ptype, overrides_fn(idx)->dict)
            plan = []

            if preset == "breguet":
                # subtle rings + rosette + faint sunburst + fine rosette
                plan = [
                    ("concentric", lambda i: {"ring_spacing": mm_to_uu(svg, 0.45)}),
                    ("guilloche",  lambda i: {"lobes": 12 + rnd.randint(-2, 2), "amplitude": mm_to_uu(svg, 1.0), "points": max(1600, int(self.options.points))}),
                    ("sunburst",   lambda i: {"rays": 240}),
                    ("guilloche",  lambda i: {"lobes": 36 + rnd.randint(-6, 6), "amplitude": mm_to_uu(svg, 0.28), "points": max(2400, int(self.options.points))}),
                ]
                layers = max(layers, 4)
            elif preset == "modern":
                # sunburst shimmer + crosshatch texture + rosette structure + fine rosette
                plan = [
                    ("sunburst",   lambda i: {"rays": 300}),
                    ("crosshatch", lambda i: {"hatch_spacing": mm_to_uu(svg, 0.6), "hatch_angle": 35.0, "hatch_double": True}),
                    ("guilloche",  lambda i: {"lobes": 18 + rnd.randint(-3, 3), "amplitude": mm_to_uu(svg, 0.75), "points": max(2000, int(self.options.points))}),
                    ("guilloche",  lambda i: {"lobes": 48 + rnd.randint(-8, 8), "amplitude": mm_to_uu(svg, 0.22), "points": max(3000, int(self.options.points))}),
                ]
                layers = max(layers, 4)
            elif preset == "pocketwatch":
                # lots of rosettes with alternating lobes and tiny amplitudes
                plan = [("guilloche", lambda i: {})] * layers
            else:
                # rosette_stack
                plan = [("guilloche", lambda i: {})] * layers

            for i in range(layers):
                # pick pattern type / overrides
                ptype, ofn = plan[i % len(plan)]
                overrides = ofn(i) if callable(ofn) else {}

                # vary rosette parameters if not explicitly set by preset
                if ptype == "guilloche":
                    base_lobes = overrides.get("lobes", int(self.options.lobes))
                    base_amp = overrides.get("amplitude", mm_to_uu(svg, self.options.amplitude_mm))
                    # jitter lobes unless preset already tightly set via overrides
                    if "lobes" not in overrides:
                        base_lobes = max(2, base_lobes + rnd.randint(-int(self.options.lobe_jitter), int(self.options.lobe_jitter)))
                        overrides["lobes"] = base_lobes
                    if "amplitude" not in overrides:
                        overrides["amplitude"] = base_amp * (float(self.options.amp_decay) ** i)
                    if "points" not in overrides:
                        # more points on top layers reads as "engraving-grade"
                        p0 = int(self.options.points)
                        overrides["points"] = max(800, int(p0 * (1.0 + 0.10 * i)))

                # vary crosshatch angle/spacing a little when used repeatedly
                if ptype == "crosshatch":
                    if "hatch_angle" not in overrides:
                        overrides["hatch_angle"] = float(self.options.hatch_angle_deg) + rnd.uniform(-5.0, 5.0)

                # compute per-layer stroke/opacity
                sw = base_stroke * (float(self.options.stroke_decay) ** i)
                op = base_opacity * (float(self.options.opacity_decay) ** i)
                op = max(0.02, min(1.0, op))

                # rotation jitter
                rot = rnd.uniform(-float(self.options.rotate_jitter_deg), float(self.options.rotate_jitter_deg))
                lg = make_layer(i, rot)

                self._draw_one(svg, lg, cx, cy, r_outer, r_inner, ptype, sw, stroke_color, op, overrides)

        # Outline on top
        if self.options.draw_outline:
            stroke_outline = mm_to_uu(svg, outline_w_mm)
            c = Circle()
            c.set('cx', str(cx))
            c.set('cy', str(cy))
            c.set('r', str(r_outer))
            set_style(c, {
                "fill": "none",
                "stroke": "#000000",
                "stroke-width": str(stroke_outline),
            })
            g.add(c)


if __name__ == "__main__":
    DialPatternGenerator().run()