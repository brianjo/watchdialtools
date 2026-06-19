#!/usr/bin/env python
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

import inkex, math, re
from inkex import Circle, Rectangle, Group

def mm(svg, v): return svg.unittouu(f"{v}mm")

def center(svg):
    vb = svg.get("viewBox")
    if vb:
        p = list(map(float, re.split(r"[ ,]+", vb)))
        return p[0]+p[2]/2, p[1]+p[3]/2
    return svg.viewport_width/2, svg.viewport_height/2

PRESETS = {
 "nh35": {
   "dial":28.5, "center":2.05,
   "hands":(1.5,0.9,0.2),
   "date":(2.9,2.0,12.0),
   "feet":[(9.672,-8.667),(-9.466,8.93)]
 },
 "st36":{
   "dial":36.6, "center":2.0,
   "hands":(1.7,1.0,0.3),
   "sub":(10.25,13.404),
 }
}

class BlankDial(inkex.EffectExtension):
  def add_arguments(self,p):
    p.add_argument("--movement_preset",default="nh35")
    p.add_argument("--draw_outline",type=inkex.Boolean,default=True)
    p.add_argument("--outline_stroke_mm",type=float,default=0.12)
    p.add_argument("--compensate_outline",type=inkex.Boolean,default=True)
    p.add_argument("--draw_center_hole",type=inkex.Boolean,default=True)
    p.add_argument("--draw_hand_holes",type=inkex.Boolean,default=True)
    p.add_argument("--draw_date_window",type=inkex.Boolean,default=True)
    p.add_argument("--draw_subdial",type=inkex.Boolean,default=True)
    p.add_argument("--draw_dial_feet",type=inkex.Boolean,default=True)
    p.add_argument("--group_name",default="dial-template")

  def effect(self):
    svg=self.svg
    cx,cy=center(svg)
    preset=PRESETS[self.options.movement_preset]
    g=Group(); g.label=self.options.group_name
    svg.get_current_layer().add(g)

    def add(el): g.add(el)

    if self.options.draw_outline:
      r=preset["dial"]/2
      if self.options.compensate_outline:
        r-=self.options.outline_stroke_mm/2
      c=Circle(); c.center=(cx,cy); c.radius=mm(svg,r)
      c.style={"fill":"none","stroke":"#777","stroke-width":str(mm(svg,self.options.outline_stroke_mm))}
      add(c)

    if self.options.draw_center_hole:
      c=Circle(); c.center=(cx,cy); c.radius=mm(svg,preset["center"]/2)
      c.style={"fill":"none","stroke":"#777","stroke-width":str(mm(svg,0.1))}
      add(c)

    if self.options.draw_hand_holes:
      for d in preset["hands"]:
        c=Circle(); c.center=(cx,cy); c.radius=mm(svg,d/2)
        c.style={"fill":"none","stroke":"#999","stroke-width":str(mm(svg,0.08))}
        add(c)

    if self.options.movement_preset=="nh35" and self.options.draw_date_window:
      w,h,r=preset["date"]
      rect=Rectangle()
      rect.set("x",str(cx+mm(svg,r)-mm(svg,w/2)))
      rect.set("y",str(cy-mm(svg,h/2)))
      rect.set("width",str(mm(svg,w)))
      rect.set("height",str(mm(svg,h)))
      rect.style={"fill":"none","stroke":"#777","stroke-width":str(mm(svg,0.1))}
      add(rect)

    if self.options.movement_preset=="st36" and self.options.draw_subdial:
      x,y=preset["sub"]
      c=Circle(); c.center=(cx-mm(svg,x),cy); c.radius=mm(svg,6.0)
      c.style={"fill":"none","stroke":"#777","stroke-width":str(mm(svg,0.1))}
      add(c)

    if self.options.draw_dial_feet and "feet" in preset:
      for x,y in preset["feet"]:
        c=Circle(); c.center=(cx+mm(svg,x),cy+mm(svg,y)); c.radius=mm(svg,0.5)
        c.style={"fill":"none","stroke":"#aaa","stroke-width":str(mm(svg,0.08))}
        add(c)

if __name__=="__main__":
  BlankDial().run()