# Watch Dial Tools (Inkscape extension)

A single Inkscape extension that combines six previously separate watch-dial
tools into one dialog, for designing watch dials with high-accuracy alignment
and both old-world and new-world decoration.

Every tool centers its output on the **document center**, so anything you
generate stacks perfectly concentric — design a blank, drop a guilloché field
on it, add perlage, then place numerals and markers, all aligned.

## Tools (the "Active tool" selector on the **Tool** tab)

| Tool | What it makes | Style |
|------|---------------|-------|
| **Dial** | Outline, center hole, hour markers, minute ticks, Arabic/Roman/custom numerals, fonts, orientation | foundation |
| **Blank Template** | Movement layout (Seiko NH35/NH36, Seagull ST36): hand holes, date window, subdial, dial feet | foundation |
| **Classic Patterns** | Guilloché (rosette / filled field), concentric rings, sunburst, crosshatch, plus multi-layer "auto-complex" engraving presets | old world |
| **Rose Engine** | Rose-engine rosettes: sine, square (engine-turned), epicycloid (guilloché), with multi-ring twist/taper | old world |
| **Perlage** | Perlage / côtes spots: staggered, grid, spiral, radial-ring layouts | old world |
| **Modern Patterns** | Mondrian blocks, 60s Op-Art waves, psychedelic spiral stripes, paper texture, linen weave | new world |

## How to use

The dialog has **one tab per tool** (Dial, Blank Template, Classic Patterns,
Rose Engine, Perlage, Modern Patterns) — the tabs are the navigation.

1. Open the extension: **Extensions → Watch Dial Tools**.
2. Click the tab for the tool you want; set its options.
3. Click **Apply** (or turn on **Live preview**). **The tool whose tab is
   open is the one that runs** — there's no separate selector.
4. The result is added to a named group on the current layer.
5. Switch to another tab and Apply again to add another aligned layer on top.

> Only the open tab's tool runs on each Apply. With Live preview on, switching
> tabs re-renders using that tab's tool.

## Installation

Requires **Inkscape 1.0 or newer** (the dialog uses the `hbox`/`vbox` two-column
layout introduced in 1.0).

Copy these two files into your Inkscape user extensions folder:

- `watch_dial_tools.inx`
- `watch_dial_tools.py`

Extensions folder locations:

- **Windows:** `%APPDATA%\inkscape\extensions\`
- **macOS:** `~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/`
- **Linux:** `~/.config/inkscape/extensions/`

Then restart Inkscape. Find it under **Extensions → Watch Dial Tools**.

### Make the font picker match this machine

The *Font (installed)* dropdown is baked into the `.inx`, so on a new machine
(or after installing new fonts) regenerate it from your local system fonts.

Run `regen_fonts.py` with the Python that ships with Inkscape — no extra
packages needed:

```sh
# Run from the folder containing watch_dial_tools.inx
python3 regen_fonts.py          # macOS / Linux
py regen_fonts.py               # Windows
```

Useful flags: `--dry-run` (list fonts, write nothing) and
`--inx <path>` (point at a specific `watch_dial_tools.inx`).

`regen_fonts.py` reads font family names directly from the `.ttf`/`.otf`/`.ttc`
files in your platform's standard font folders (Windows, macOS, and Linux paths
are all handled), then rewrites **only** the font dropdown in
`watch_dial_tools.inx` — keeping "Times New Roman" as the default (or the first
font if it's absent) and a trailing "Custom (type below)" option. It validates
the result is still well-formed XML and leaves everything else untouched. It is
safe to run repeatedly. Run it on the same machine where you'll use Inkscape so
the list reflects that machine's fonts, then restart Inkscape.

## Notes

- **Font picker (Dial tool, "Dial: Text" tab):** the *Font (installed)* dropdown
  is populated with the fonts installed on the machine where the `.inx` was
  generated, so you can pick a font instead of typing its name. To use a font
  not in the list, choose **Custom (type below)** and enter the exact family
  name in *Custom font family*. Note: because the list is baked into the `.inx`,
  it reflects this machine's fonts; regenerate the dropdown if you install new
  fonts or move to another computer.
- All dimensions are in millimeters and converted to the document's user units
  via `svg.unittouu`, so sizing is correct in mm-based and px-based documents.
- Tip: start from an mm document whose page is centered on your dial for the
  most intuitive alignment.
- The original six extensions are kept unchanged in `original/` for reference.
