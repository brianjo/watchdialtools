# Watch Dial Tools – Inkscape Extensions

**Watch Dial Tools** is a small open-source toolkit of Inkscape extensions for designing real, production-ready mechanical watch dials.

It provides three generators:

- 🕒 **Watch Dial Generator** – hour markers, minute ticks, numbers or symbols (CSV driven)
- 🎨 **Dial Pattern Generator** – guilloché, sunburst, concentric, crosshatch, and multi-layer “auto complex” textures
- ⚙️ **Blank Dial / Movement Template Generator** – NH35, ST36 layout templates (holes, date window, feet, sub-dial)
  
---

## Features

### Watch Dial Generator
- Arabic, Roman (IV or IIII), or custom CSV labels
- Emoji / symbol support (vector-safe fonts)
- Date-window omission helper
- Hour markers + minute ticks with alignment control
- Precise millimeter sizing (document-unit aware)
- Rotation modes (upright, tangent, radial, readable tangent)

### Dial Pattern Generator
- Pattern types:
  - Guilloché (rosette)
  - Concentric rings
  - Sunburst
  - Crosshatch
- Stroke width / opacity control
- Automatic circular clipping
- **Auto-complex mode**:
  - Multi-layer stacked patterns
  - Presets: Breguet-ish, modern, pocketwatch, rosette stack
  - Deterministic random seed

### Blank Dial Generator
- Movement presets:
  - NH35 / NH36
  - ST36 / 6497 style
- Center hole
- Hand holes
- Date window
- Sub-dial
- Dial feet markers
- Outline compensation

---

## Requirements

- Inkscape **1.1+** (1.2 / 1.3 recommended)
- Python (bundled with Inkscape)

Works on:
- Windows
- macOS
- Linux

---

## Installation

### 1. Download

Download or clone this repository:

```bash
git clone https://github.com/brianjo/watch-dial-tools.git
```

Or use GitHub’s **Download ZIP** button.

---

### 2. Locate your Inkscape user extensions folder

#### Windows
```
C:\Users\<your-username>\AppData\Roaming\inkscape\extensions
```

Quick way:
- Press `Win + R`
- Paste:
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

---

### 3. Copy the extension files

Copy all `.inx` and `.py` files into the extensions folder:

```
watch_dial_generator.inx
watch_dial_generator.py

watch_dial_pattern_generator.inx
watch_dial_pattern_generator.py

watch_dial_blank_generator.inx
watch_dial_blank_generator.py
```

---

### 4. Restart Inkscape

After restarting, you will find the tools here:

```
Extensions → Watch Dial Tools
```

---

## Usage

Each tool opens as a dialog window with tabs:

- Adjust parameters
- Click **Apply**
- A new grouped SVG layer is created at the document center

All generated elements remain fully editable in Inkscape.

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

Enjoy designing dials 🛠️⌚
