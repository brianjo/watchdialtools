#!/usr/bin/env python3
"""
Repopulate the "Font (installed)" dropdown in watch_dial_tools.inx with the
fonts installed on THIS machine. Cross-platform (Windows / macOS / Linux),
pure standard library -- no GUI, no external tools, no third-party packages.

Inkscape extension dialogs (.inx) are static XML, so the font list cannot be
built at runtime. Run this once after installing the extension on a new machine
(and again whenever you install new fonts):

    python3 regen_fonts.py            # rewrites ./watch_dial_tools.inx
    python3 regen_fonts.py --inx /path/to/watch_dial_tools.inx
    python3 regen_fonts.py --dry-run  # show font count, write nothing

Font family names are read directly from the .ttf/.otf/.ttc/.otc files found in
the platform's standard font directories (the sfnt 'name' table). Only the
<param name="wd_font_preset"> block is rewritten; everything else is untouched.
"Times New Roman" stays the default if present (otherwise the first font is the
default), and a trailing "Custom (type below)" option is always added.
"""

import argparse
import os
import re
import struct
import sys
from xml.sax.saxutils import escape


# ---------------------------------------------------------------------------
# Locate font files for the current platform
# ---------------------------------------------------------------------------

def font_dirs():
    home = os.path.expanduser("~")
    dirs = []
    if sys.platform.startswith("win"):
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs += [
            os.path.join(windir, "Fonts"),
            os.path.join(os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local")),
                         "Microsoft", "Windows", "Fonts"),
        ]
    elif sys.platform == "darwin":
        dirs += [
            "/System/Library/Fonts",
            "/System/Library/Fonts/Supplemental",
            "/Library/Fonts",
            os.path.join(home, "Library", "Fonts"),
        ]
    else:  # Linux / *BSD
        xdg = os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share"))
        dirs += [
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            "/run/host/fonts",  # Flatpak sandbox passthrough
            os.path.join(xdg, "fonts"),
            os.path.join(home, ".fonts"),
        ]
    seen = set()
    out = []
    for d in dirs:
        d = os.path.abspath(d)
        if d not in seen and os.path.isdir(d):
            seen.add(d)
            out.append(d)
    return out


FONT_EXTS = (".ttf", ".otf", ".ttc", ".otc")


def font_files():
    for d in font_dirs():
        for root, _dirs, files in os.walk(d):
            for f in files:
                if f.lower().endswith(FONT_EXTS):
                    yield os.path.join(root, f)


# ---------------------------------------------------------------------------
# Minimal sfnt 'name' table reader (TrueType / OpenType / collections)
# ---------------------------------------------------------------------------

def _decode_name(raw, platform_id):
    try:
        if platform_id in (0, 3):       # Unicode / Microsoft -> UTF-16BE
            return raw.decode("utf-16-be").strip("\x00").strip()
        if platform_id == 1:            # Macintosh -> Mac Roman
            return raw.decode("mac_roman").strip()
        return raw.decode("latin-1").strip()
    except Exception:
        return None


def _read_family_from_offset(data, base):
    """Return the family name(s) of the font whose table directory starts at `base`.

    Collects both the legacy/GDI family (nameID 1) and the typographic family
    (nameID 16). Keeping nameID 1 preserves genuinely distinct families such as
    "Arial Narrow" and "Arial Black" that nameID 16 would otherwise fold into
    their base family -- both are valid CSS font-family names.
    """
    try:
        num_tables = struct.unpack_from(">H", data, base + 4)[0]
        name_off = None
        rec = base + 12
        for _ in range(num_tables):
            tag = data[rec:rec + 4]
            if tag == b"name":
                name_off = struct.unpack_from(">I", data, rec + 8)[0]
                break
            rec += 16
        if name_off is None:
            return set()

        _fmt, count, string_off = struct.unpack_from(">HHH", data, name_off)
        storage = name_off + string_off

        # Per nameID, keep the best-scoring decoded value (English Windows wins).
        best = {1: (-1, None), 16: (-1, None)}
        for i in range(count):
            r = name_off + 6 + i * 12
            platform_id, _enc_id, lang_id, name_id, length, off = struct.unpack_from(">HHHHHH", data, r)
            if name_id not in best:  # 1 = family, 16 = typographic family
                continue
            raw = data[storage + off: storage + off + length]
            value = _decode_name(raw, platform_id)
            if not value:
                continue
            score = 0
            if platform_id == 3 and lang_id == 0x0409:
                score += 3
            elif platform_id == 3:
                score += 2
            elif platform_id == 0:
                score += 1
            if score > best[name_id][0]:
                best[name_id] = (score, value)

        return {v for _s, v in best.values() if v}
    except Exception:
        return set()


def family_names():
    names = set()
    for path in font_files():
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except Exception:
            continue
        if len(data) < 12:
            continue
        try:
            if data[:4] == b"ttcf":                       # font collection
                num_fonts = struct.unpack_from(">I", data, 8)[0]
                for j in range(num_fonts):
                    base = struct.unpack_from(">I", data, 12 + j * 4)[0]
                    names.update(_read_family_from_offset(data, base))
            else:                                         # single font
                names.update(_read_family_from_offset(data, 0))
        except Exception:
            continue
    # Drop blanks; sort case-insensitively for a stable, readable dropdown.
    return sorted((n for n in names if n.strip()), key=lambda s: s.lower())


# ---------------------------------------------------------------------------
# Build and splice the <param> block
# ---------------------------------------------------------------------------

def build_block(families):
    has_times = "Times New Roman" in families
    lines = ['<param name="wd_font_preset" type="optiongroup" appearance="combo" gui-text="Font (installed)">']
    for f in families:
        esc = escape(f)
        is_default = (f == "Times New Roman" and has_times) or (not has_times and f == families[0])
        if is_default:
            lines.append(f'        <option value="{esc}" default="true">{esc}</option>')
        else:
            lines.append(f'        <option value="{esc}">{esc}</option>')
    lines.append('        <option value="Custom">Custom (type below)</option>')
    lines.append('      </param>')
    return "\n".join(lines)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Rebuild the font dropdown in watch_dial_tools.inx from local fonts.")
    ap.add_argument("--inx", default=os.path.join(here, "watch_dial_tools.inx"),
                    help="Path to watch_dial_tools.inx (default: next to this script).")
    ap.add_argument("--dry-run", action="store_true", help="Report the font count without writing.")
    args = ap.parse_args()

    families = family_names()
    if not families:
        print("ERROR: no fonts were found on this system; aborting so the .inx is not left empty.",
              file=sys.stderr)
        return 2
    print(f"Found {len(families)} font families.")

    if args.dry_run:
        for f in families:
            print("  " + f)
        return 0

    if not os.path.isfile(args.inx):
        print(f"ERROR: INX file not found: {args.inx}", file=sys.stderr)
        return 2

    with open(args.inx, "r", encoding="utf-8") as fh:
        content = fh.read()

    pattern = re.compile(r'<param name="wd_font_preset".*?</param>', re.DOTALL)
    if not pattern.search(content):
        print(f"ERROR: could not find the wd_font_preset <param> block in {args.inx}", file=sys.stderr)
        return 2

    block = build_block(families)
    # Function replacement avoids backreference interpretation of '\' or '$' in names.
    updated = pattern.sub(lambda m: block, content, count=1)

    with open(args.inx, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(updated)

    # Validate the result is still well-formed XML.
    try:
        import xml.dom.minidom as minidom
        minidom.parse(args.inx)
    except Exception as exc:
        print(f"ERROR: rewrote {args.inx} but it is no longer valid XML: {exc}", file=sys.stderr)
        return 3

    print(f"Updated {args.inx} with {len(families)} installed fonts.")
    print("Restart Inkscape (or reload extensions) to see the new font list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
