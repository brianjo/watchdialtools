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
Watch Dial Generator (fix mm scaling to match document units)

Problem:
- If the document's user units are already mm (common in modern Inkscape templates),
  converting mm->px using 96dpi makes everything ~3.78x too large (28.5mm -> ~108mm).

Fix:
- Convert mm to *document user units* using svg.unittouu(f"{mm}mm").
  This adapts correctly whether the document uses px, mm, etc.

Keeps:
- 12-at-top ordering
- Roman IV/IIII option
- Omit 3 for date window
- Tuning options (offsets, baseline, orientation)
- Marker/tick alignment options
- Robust center detection (no svg.viewbox dependency)
"""

import math
import csv
import re

import inkex
from inkex import Circle, Rectangle, TextElement, Group


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


def mm_to_uu(svg, mm: float) -> float:
    """Convert millimeters to the document's user units."""
    try:
        return float(svg.unittouu(f"{mm}mm"))
    except Exception:
        # Fallback to px @ 96dpi
        return mm * 96.0 / 25.4


def polar_to_xy(cx, cy, r, angle_deg_clockwise_from_12):
    a = math.radians(angle_deg_clockwise_from_12)
    return (cx + r * math.sin(a), cy - r * math.cos(a))


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


def set_rect_geom(rect: Rectangle, x: float, y: float, w: float, h: float):
    rect.set("x", str(x))
    rect.set("y", str(y))
    rect.set("width", str(w))
    rect.set("height", str(h))


def aligned_radius(r: float, h: float, align: str) -> float:
    a = (align or "outer").strip().lower()
    if a == "outer":
        return r - h / 2.0
    if a == "inner":
        return r + h / 2.0
    return r


ARABIC_12_FIRST = ["12", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
ROMAN_12_FIRST_IV  = ["XII", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
ROMAN_12_FIRST_IIII = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]


class WatchDialGenerator(inkex.EffectExtension):
    def add_arguments(self, pars):
        # Inkscape notebook tab selector (ignored)
        pars.add_argument("--ui", type=str, default="dial")

        # Dial
        pars.add_argument("--dial_diameter_mm", type=float, default=28.5)
        pars.add_argument("--draw_dial_outline", type=inkex.Boolean, default=True)
        pars.add_argument("--dial_outline_stroke_mm", type=float, default=0.12)
        pars.add_argument("--outline_compensate_stroke", type=inkex.Boolean, default=True)

        # Center hole
        pars.add_argument("--draw_center_hole", type=inkex.Boolean, default=True)
        pars.add_argument("--center_hole_mm", type=float, default=1.5)

        # Angle system
        pars.add_argument("--start_angle_deg", type=float, default=0.0)
        pars.add_argument("--clockwise", type=inkex.Boolean, default=True)

        # Text labels
        pars.add_argument("--text_mode", type=str, default="arabic",
                          choices=["arabic", "roman", "custom"])
        pars.add_argument("--labels_csv", type=str, default="")

        # Roman-specific
        pars.add_argument("--roman_four_style", type=str, default="IV",
                          choices=["IV", "IIII"])

        # Date-window helper
        pars.add_argument("--omit_three", type=inkex.Boolean, default=False)

        # Text placement
        pars.add_argument("--text_radius_mm", type=float, default=11.5)
        pars.add_argument("--text_radial_offset_mm", type=float, default=0.0)
        pars.add_argument("--text_angle_offset_deg", type=float, default=0.0)

        # Font
        pars.add_argument("--font_family", type=str, default="Times New Roman")
        pars.add_argument("--font_size_mm", type=float, default=2.6)
        pars.add_argument("--text_baseline", type=str, default="central",
                          choices=["alphabetic", "central", "middle", "hanging"])

        # Orientation
        pars.add_argument("--number_orientation", type=str, default="upright",
                          choices=["upright", "tangent", "radial", "tangent_readable"])

        # Hour markers
        pars.add_argument("--show_hour_markers", type=inkex.Boolean, default=True)
        pars.add_argument("--hour_marker_radius_mm", type=float, default=12.8)
        pars.add_argument("--hour_marker_w_mm", type=float, default=0.7)
        pars.add_argument("--hour_marker_h_mm", type=float, default=1.8)
        pars.add_argument("--hour_marker_align", type=str, default="outer",
                          choices=["outer", "center", "inner"])

        # Minute ticks
        pars.add_argument("--show_minute_ticks", type=inkex.Boolean, default=True)
        pars.add_argument("--minute_tick_radius_mm", type=float, default=13.6)
        pars.add_argument("--minute_tick_w_mm", type=float, default=0.25)
        pars.add_argument("--minute_tick_h_mm", type=float, default=1.0)
        pars.add_argument("--five_minute_scale", type=float, default=1.7)
        pars.add_argument("--minute_tick_align", type=str, default="outer",
                          choices=["outer", "center", "inner"])

        # Output
        pars.add_argument("--group_name", type=str, default="watch-dial")

    def effect(self):
        svg = self.document.getroot()
        cx, cy = get_doc_center(svg)

        g = Group()
        g.label = (self.options.group_name or "watch-dial")
        g.set("id", (self.options.group_name or "watch-dial"))
        svg.add(g)

        stroke_w_mm = self.options.dial_outline_stroke_mm
        stroke_w = str(mm_to_uu(svg, stroke_w_mm))

        dial_r_mm = (self.options.dial_diameter_mm - (stroke_w_mm if self.options.outline_compensate_stroke else 0.0)) / 2.0
        center_r_mm = (self.options.center_hole_mm - (stroke_w_mm if self.options.outline_compensate_stroke else 0.0)) / 2.0

        # Outline
        if self.options.draw_dial_outline:
            c = Circle()
            c.set("cx", str(cx))
            c.set("cy", str(cy))
            c.set("r", str(mm_to_uu(svg, dial_r_mm)))
            c.style = {"fill": "none", "stroke": "#000", "stroke-width": stroke_w}
            g.add(c)

        # Center hole
        if self.options.draw_center_hole:
            h = Circle()
            h.set("cx", str(cx))
            h.set("cy", str(cy))
            h.set("r", str(mm_to_uu(svg, max(0.0, center_r_mm))))
            h.style = {"fill": "none", "stroke": "#000", "stroke-width": stroke_w}
            g.add(h)

        # Hour markers
        if self.options.show_hour_markers:
            r_base = mm_to_uu(svg, self.options.hour_marker_radius_mm)
            w = mm_to_uu(svg, self.options.hour_marker_w_mm)
            hh = mm_to_uu(svg, self.options.hour_marker_h_mm)
            r = aligned_radius(r_base, hh, self.options.hour_marker_align)

            for i in range(12):
                ang = (self.options.start_angle_deg + i * 30.0) % 360.0
                if not self.options.clockwise:
                    ang = (-ang) % 360.0
                x, y = polar_to_xy(cx, cy, r, ang)

                rect = Rectangle()
                rect.style = {"fill": "#000", "stroke": "none"}
                set_rect_geom(rect, x - w / 2.0, y - hh / 2.0, w, hh)
                rect.set("transform", f"rotate({ang},{x},{y})")
                g.add(rect)

        # Minute ticks
        if self.options.show_minute_ticks:
            r_base = mm_to_uu(svg, self.options.minute_tick_radius_mm)
            w = mm_to_uu(svg, self.options.minute_tick_w_mm)
            h0 = mm_to_uu(svg, self.options.minute_tick_h_mm)

            for i in range(60):
                ang = (self.options.start_angle_deg + i * 6.0) % 360.0
                if not self.options.clockwise:
                    ang = (-ang) % 360.0

                scale = self.options.five_minute_scale if (i % 5 == 0) else 1.0
                hh = h0 * scale
                r = aligned_radius(r_base, hh, self.options.minute_tick_align)

                x, y = polar_to_xy(cx, cy, r, ang)

                rect = Rectangle()
                rect.style = {"fill": "#000", "stroke": "none"}
                set_rect_geom(rect, x - w / 2.0, y - hh / 2.0, w, hh)
                rect.set("transform", f"rotate({ang},{x},{y})")
                g.add(rect)

        # Labels
        if self.options.text_mode == "arabic":
            labels = list(ARABIC_12_FIRST)
        elif self.options.text_mode == "roman":
            labels = list(ROMAN_12_FIRST_IIII if (self.options.roman_four_style == "IIII") else ROMAN_12_FIRST_IV)
        else:
            labels = read_labels_from_csv(self.options.labels_csv)

        if labels:
            r = mm_to_uu(svg, self.options.text_radius_mm + self.options.text_radial_offset_mm)
            font_uu = mm_to_uu(svg, self.options.font_size_mm)

            if len(labels) == 12:
                for i, label in enumerate(labels):
                    if self.options.omit_three and i == 3:
                        continue

                    ang = (self.options.start_angle_deg + self.options.text_angle_offset_deg + i * 30.0) % 360.0
                    if not self.options.clockwise:
                        ang = (-ang) % 360.0

                    x, y = polar_to_xy(cx, cy, r, ang)

                    t = TextElement()
                    t.text = label
                    t.style = {
                        "font-family": self.options.font_family,
                        "font-size": str(font_uu),
                        "text-anchor": "middle",
                        "dominant-baseline": self.options.text_baseline,
                    }
                    t.set("x", str(x))
                    t.set("y", str(y))

                    rot = rotation_for_number(self.options.number_orientation, ang)
                    if rot != 0.0:
                        t.set("transform", f"rotate({rot},{x},{y})")

                    g.add(t)
            else:
                n = len(labels)
                step = 360.0 / float(n)
                for i, label in enumerate(labels):
                    ang = (self.options.start_angle_deg + self.options.text_angle_offset_deg + i * step) % 360.0
                    if not self.options.clockwise:
                        ang = (-ang) % 360.0

                    x, y = polar_to_xy(cx, cy, r, ang)

                    t = TextElement()
                    t.text = label
                    t.style = {
                        "font-family": self.options.font_family,
                        "font-size": str(font_uu),
                        "text-anchor": "middle",
                        "dominant-baseline": self.options.text_baseline,
                    }
                    t.set("x", str(x))
                    t.set("y", str(y))

                    rot = rotation_for_number(self.options.number_orientation, ang)
                    if rot != 0.0:
                        t.set("transform", f"rotate({rot},{x},{y})")

                    g.add(t)


if __name__ == "__main__":
    WatchDialGenerator().run()