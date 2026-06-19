# Watch Dial Tools – Inkscape Extensions

**Watch Dial Tools** is a small open-source toolkit of Inkscape extensions for designing real, production-ready mechanical watch dials.

I have a rough demo video you can watch [here](https://youtu.be/5oQK36zGMQM). I've alsp added some simple example output to the Examples folder in the repo.

If you use these tools to make anything, I would love to hear from you! (https://www.instagram.com/brianjophoto/)

> **v2 note:** The three separate v1 extensions have been merged into a single unified extension (`watch_dial_tools`). The original files are preserved in `V1/` for reference.

---

## Tools

The extension opens as a single dialog. Each tab is a tool — click a tab, set its options, and click **Apply**. Everything is centered on the document center, so layers stack perfectly concentric.

| Tool | What it makes | Style |
|------|---------------|-------|
| **Dial** | Outline, center hole, hour markers, minute ticks, Arabic/Roman/custom numerals, fonts, orientation | foundation |
| **Blank Template** | Movement layout (NH35/NH36, ST36): hand holes, date window, subdial, dial feet | foundation |
| **Classic Patterns** | Guilloché (rosette / filled field), concentric rings, sunburst, crosshatch, plus multi-layer auto-complex engraving presets | old world |
| **Rose Engine** | Rose-engine rosettes: sine, square (engine-turned), epicycloid, with multi-ring twist/taper | old world |
| **Perlage** | Perlage / côtes spots: staggered, grid, spiral, radial-ring layouts | old world |
| **Modern Patterns** | Mondrian blocks, 60s Op-Art waves, psychedelic spiral stripes, paper texture, linen weave | new world |

---

## Usage

1. Open the extension: **Extensions → Watch Dial Tools**
2. Click the tab for the tool you want and set its options
3. Click **Apply** (or enable **Live preview**)
4. The result is added to a named group on the current layer
5. Switch tabs and Apply again to add more aligned layers on top

Only the open tab's tool runs on each Apply.

All generated elements remain fully editable in Inkscape.

---

## Requirements

- Inkscape **1.0+** (1.2 / 1.3 recommended)
- Python (bundled with Inkscape)

Works on Windows, macOS, and Linux.

---

## Installation

### 1. Download

Download or clone this repository:

```bash
git clone https://github.com/brianjo/watch-dial-tools.git
```

Or use GitHub's **Download ZIP** button.

### 2. Locate your Inkscape user extensions folder

#### Windows
```
%APPDATA%\inkscape\extensions
```

#### macOS
```
~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions
```

#### Linux
```
~/.config/inkscape/extensions
```

### 3. Copy the extension files

Copy these two files into the extensions folder:

```
watch_dial_tools.inx
watch_dial_tools.py
```

### 4. Restart Inkscape

After restarting, find the tools under:

```
Extensions → Watch Dial Tools
```

---

## Font Picker

The *Font (installed)* dropdown in the Dial tool is baked into the `.inx` file from the machine where it was generated. To refresh it with fonts installed on your system, run the included `regen_fonts.py` script using the Python that ships with Inkscape — no extra packages needed:

```sh
# Run from the folder containing watch_dial_tools.inx
python3 regen_fonts.py    # macOS / Linux
py regen_fonts.py         # Windows
```

Useful flags: `--dry-run` (list fonts, write nothing) and `--inx <path>` (point at a specific `.inx` file).

The script reads font family names from your platform's standard font folders, rewrites only the font dropdown in `watch_dial_tools.inx`, and validates the result is still well-formed XML. It is safe to run repeatedly. Restart Inkscape after running it.

---

## Recommended Fonts for Symbols

For vector-safe symbol / emoji dials on Windows:

```
Segoe UI Symbol
```

Backup:

```
DejaVu Sans
```

Avoid color emoji fonts (they export as bitmaps).

---

## License

GNU General Public License v2 or later (GPL-2.0+)

Copyright (C) 2026  
Brian Johnson  
https://github.com/brianjo

---

## Contributing

Pull requests, feature ideas, and improvements are welcome.

Interesting future ideas:

- More movement templates (ETA 2824, 2892, Miyota, etc.)
- Dial preset packs (Breguet, Flieger, Diver, Sector)
- Multi-depth engraving layers
- Lume mask generation
- Export helpers for CAM workflows

---

## Disclaimer

These tools generate geometry only. Always validate dimensions and tolerances before manufacturing real watch components.

Use at your own risk.

---

Enjoy designing dials ⌚
