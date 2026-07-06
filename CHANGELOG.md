# Changelog

All notable changes to Watch Dial Tools are documented here.

## [Unreleased]

### Added
- **Shapes tool** — new tab for adding centered geometric shapes: circle, rectangle (with corner radius and rotation), and annulus (ring). Configurable stroke, fill color, and fill opacity.
- More example output files in `Examples/` (bjjred, dive base, mondwatch, simple-grad, finished dial photo).

### Changed
- "Text radial offset" label renamed to "Text radial offset / fine-tune" for clarity.
- "Forum" font added to the installed-fonts dropdown.

---

## [2.0.0] — 2026-06-19

### Added
- Unified `watch_dial_tools` extension consolidating all three v1 extensions into a single tabbed dialog.
- **Dial** tab: outline, center hole, hour markers, minute ticks, Arabic/Roman/custom numerals, font picker, orientation controls.
- **Blank Template** tab: movement layout for NH35/NH36 and ST36 movements (hand holes, date window, subdial, dial feet).
- **Classic Patterns** tab: guilloché (rosette / filled field), concentric rings, sunburst, crosshatch, multi-layer auto-complex engraving presets.
- **Rose Engine** tab: rose-engine rosettes (sine, square/engine-turned, epicycloid) with multi-ring twist/taper.
- **Perlage** tab: perlage / côtes spots in staggered, grid, spiral, and radial-ring layouts.
- **Modern Patterns** tab: Mondrian blocks, 60s Op-Art waves, psychedelic spiral stripes, paper texture, linen weave.
- `regen_fonts.py` utility script to refresh the font dropdown from system-installed fonts.
- All generated elements are concentric and fully editable in Inkscape.

### Changed
- v1 files moved to `V1/` for reference.

---

## [1.1.0] — 2026-01-21

### Added
- Fill dial option in the pattern generator.

### Fixed
- Dial fill was not rendering correctly; corrected fill behavior in `watch_dial_pattern_generator.py`.

---

## [1.0.0] — 2026-01-19

### Added
- Initial release with three separate Inkscape extensions:
  - `watch_dial_generator` — dial outline, hour markers, minute ticks, numerals.
  - `watch_dial_blank_generator` — movement blank templates (NH35/NH36, ST36).
  - `watch_dial_pattern_generator` — guilloché and decorative pattern fills.
