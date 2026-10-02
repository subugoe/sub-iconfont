#!/usr/bin/env python3
"""
build-svg.py - emit one standalone SVG per glyph from subicons.ttf, then verify them.

WHY THIS EXISTS
---------------
The only per-glyph SVGs in the repository are the Illustrator exports under
`Workfiles/_exports/SVG-exports_2013-09-12_17.04/`. Those are editor output: a
960x960 viewBox, Adobe `<switch>`/`<foreignObject>`/`i:pgfRef` wrappers and
ENTITY declarations, roughly an order of magnitude larger than the artwork they
carry, and they are source history rather than something to ship.

This script produces clean, distribution-ready files in `SUB-Icon-Font/svg/`,
derived from the shipped `subicons.ttf` so they are guaranteed to match what a
browser gets from the WOFF2.

ONE FILE PER GLYPH, NOT PER ICON
--------------------------------
Every media-type icon is TWO glyphs (a dark `_bg` and a light `_fg` layer) that
consumers stack themselves - see AGENTS.md. Emitting one merged SVG per icon
would bake the two layers together and destroy the colour-customisation
contract, so this emits one file per *glyph*, named after its CSS class.

The IcoMoon sentinel `U+F000` is deliberately excluded: it has zero advance
width, carries `class="hidden"`, and is not an icon.

USAGE
-----
    python3 tools/build-svg.py           # (re)generate SUB-Icon-Font/svg/
    python3 tools/build-svg.py --check   # verify only, write nothing

REQUIRES: fonttools >= 4.x  (pip install fonttools)
Exit codes: 0 = ok, 1 = drift, 2 = missing dependency.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONTS = REPO / "SUB-Icon-Font" / "fonts"
TTF = FONTS / "subicons.ttf"
DEV_SVG = FONTS / "subicons.dev.svg"
OUT = REPO / "SUB-Icon-Font" / "svg"

SENTINEL = 0xF000
RESERVED = range(0xE024, 0xE051)
EXPECTED = ([c for c in range(0xE000, 0xE024)]
            + [0xE051, 0xE052, 0xE053, 0xE054, 0xE055])

# The em box of the font: ascent 736 + |descent 32| = 768 units (a 24px grid at
# 32 units per pixel). SVG's y axis points down, fonts point up, so outlines are
# baked through  y_svg = 736 - y_font  on the way out. No runtime transform.
VIEWBOX = 768
ASCENT = 736


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        self.checks += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" -> {detail}" if detail else ""))
        if not ok:
            self.failures.append(label)
        return ok


def glyph_map() -> dict[int, str]:
    """codepoint -> CSS class name, read from the authoritative dev.svg."""
    if not DEV_SVG.is_file():
        sys.exit(f"missing {DEV_SVG}")
    src = DEV_SVG.read_text(encoding="utf-8")
    out: dict[int, str] = {}
    for attrs in re.findall(r"<glyph\s[^>]*>", src, re.S):
        u = re.search(r'unicode="&#x([0-9a-fA-F]+);"', attrs)
        t = re.search(r'data-tags="([^"]+)"', attrs)
        if u and t:
            out[int(u.group(1), 16)] = "subicon-" + t.group(1)
    return out


def build() -> int:
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.misc.transform import Transform
    from fontTools.ttLib import TTFont

    names = glyph_map()
    font = TTFont(str(TTF))
    cmap = font.getBestCmap()
    # y-down flip, baked into the path data so the files need no transform attr.
    flip = Transform(1, 0, 0, -1, 0, ASCENT)

    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for cp in sorted(names):
        if cp == SENTINEL:
            continue
        glyph = cmap.get(cp)
        if glyph is None:
            continue
        pen = SVGPathPen(glyphSet=font.getGlyphSet(), ntos=lambda v: f"{v:g}")
        font.getGlyphSet()[glyph].draw(TransformPen(pen, flip))
        cls = names[cp]
        path = pen.getCommands()
        (OUT / f"{cls}.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb} {vb}"'
            ' width="{n}" height="{n}" role="img" aria-hidden="true">\n'
            '\t<path id="{cls}" class="{cls}" fill="currentColor" d="{d}"/>\n'
            '</svg>\n'.format(vb=VIEWBOX, n=VIEWBOX, cls=cls, d=path),
            encoding="utf-8")
        written += 1
    return written


def _flattened(font, glyphname: str, steps: int = 48) -> list[tuple]:
    """Flatten to a polyline so differing point counts can be compared by shape."""
    from fontTools.misc.bezierTools import splitCubicAtT
    from fontTools.pens.basePen import BasePen

    class Flat(BasePen):
        def __init__(s, gs):
            super().__init__(gs)
            s.steps, s.pts = steps, []

        def _moveTo(s, p): s.pts.append(p)
        def _lineTo(s, p): s.pts.append(p)

        def _curveToOne(s, p1, p2, p3):
            p0 = s._getCurrentPoint()
            for i in range(1, s.steps + 1):
                s.pts.append(splitCubicAtT(p0, p1, p2, p3, i / s.steps)[0][-1])

        def _qCurveToOne(s, p1, p2):
            p0 = s._getCurrentPoint()
            if p1 is None:
                p1 = p0
            if p2 is None:
                s._qCurveToOne(p1, p1)
                return
            c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
            c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
            for i in range(1, s.steps + 1):
                s.pts.append(splitCubicAtT(p0, c1, c2, p2, i / s.steps)[0][-1])

        def _closePath(s): pass
        def _endPath(s): pass

    pen = Flat(font.getGlyphSet())
    font.getGlyphSet()[glyphname].draw(pen)
    return pen.pts


def _deviation(a: list[tuple], b: list[tuple]) -> float:
    grid: dict[tuple, list] = {}
    for p in b:
        grid.setdefault((round(p[0] * 4), round(p[1] * 4)), []).append(p)
    worst = 0.0
    for p in a:
        best = math.inf
        kx, ky = round(p[0] * 4), round(p[1] * 4)
        for dx in range(-8, 9):
            for dy in range(-8, 9):
                for q in grid.get((kx + dx, ky + dy), ()):
                    best = min(best, math.dist(p, q))
        if best is not math.inf:
            worst = max(worst, best)
    return worst


def verify() -> Report:
    import xml.etree.ElementTree as ET
    from fontTools.svgLib.path.parser import parse_path
    from fontTools.pens.basePen import BasePen
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.ttLib import TTFont

    r = Report()
    names = glyph_map()
    font = TTFont(str(TTF))
    cmap = font.getBestCmap()

    expected_files = {f"{names[c]}.svg" for c in names if c != SENTINEL}

    print("1) Inventory")
    r.check(OUT.is_dir(), "svg/ directory exists", str(OUT.relative_to(REPO)))
    if not OUT.is_dir():
        return r
    on_disk = {p.name for p in OUT.glob("*.svg")}
    r.check(len(expected_files) == 41, "41 glyphs expected",
            f"{len(expected_files)} (36 media layers + 3 arrows + 2 loupe)")
    r.check(on_disk == expected_files,
            "file set matches dev.svg data-tags exactly",
            f"unexpected={sorted(on_disk - expected_files)[:4]} "
            f"missing={sorted(expected_files - on_disk)[:4]}")

    print("\n2) Per-file structure")
    bad_xml, bad_view, bad_class, empty = [], [], [], []
    for fname in sorted(expected_files):
        f = OUT / fname
        if not f.is_file():
            continue
        try:
            root = ET.fromstring(f.read_text(encoding="utf-8"))
        except ET.ParseError as e:
            bad_xml.append(f"{fname}: {e}")
            continue
        if root.get("viewBox") != f"0 0 {VIEWBOX} {VIEWBOX}":
            bad_view.append(fname)
        paths = root.findall(".//{http://www.w3.org/2000/svg}path")
        if len(paths) != 1:
            bad_class.append(f"{fname}: {len(paths)} paths")
            continue
        p = paths[0]
        if p.get("class") != fname[:-4] or p.get("id") != fname[:-4]:
            bad_class.append(fname)
        if not (p.get("d") or "").strip():
            empty.append(fname)
    r.check(not bad_xml, "every file is well-formed XML", "; ".join(bad_xml[:2]))
    r.check(not bad_view, f"every viewBox is 0 0 {VIEWBOX} {VIEWBOX}", str(bad_view[:3]))
    r.check(not bad_class, "one path per file, class+id match the filename", str(bad_class[:3]))
    r.check(not empty, "no empty path data", str(empty[:3]))

    print("\n3) Published contract - codepoints, layers, sentinel")
    r.check(not any(f.startswith("subicon-hidden") or "f000" in f for f in on_disk),
            "U+F000 sentinel not shipped as an icon")
    r.check(not any(f"{n}.svg" in on_disk for n in
                    (f"subicon-reserved_{c:x}" for c in RESERVED)),
            "reserved range U+E024-U+E050 has no files")
    two_layer = sorted(f for f in on_disk if f.endswith(("_bg.svg", "_fg.svg")))
    bgs = {f[:-7] for f in two_layer if f.endswith("_bg.svg")}
    fgs = {f[:-7] for f in two_layer if f.endswith("_fg.svg")}
    # 18 media-type icons plus the UI loupe are two-layer; the 3 arrows are not.
    r.check(len(two_layer) == 38 and bgs == fgs and len(bgs) == 19,
            "every two-layer glyph has both a _bg and a _fg file",
            f"{len(two_layer)} layer files = {len(bgs)} complete pairs "
            f"(18 media types + UI loupe); unbalanced={sorted(bgs ^ fgs)}")
    arrows = [f for f in on_disk if f.startswith("subicon-ui-arrow")]
    r.check(len(arrows) == 3, "3 single-layer UI arrows have no _bg/_fg", str(len(arrows)))

    print("\n4) Round-trip: re-parse each SVG and compare to the font")
    worst = 0.0
    checked = 0
    for cp, cls in sorted(names.items()):
        if cp == SENTINEL:
            continue
        f = OUT / f"{cls}.svg"
        if not f.is_file():
            continue
        root = ET.fromstring(f.read_text(encoding="utf-8"))
        d = root.find(".//{http://www.w3.org/2000/svg}path").get("d")

        class Shim(BasePen):
            def __init__(s, gs):
                super().__init__(gs)
                s.pts = []

            def _moveTo(s, p): s.pts.append(p)
            def _lineTo(s, p): s.pts.append(p)

            def _curveToOne(s, p1, p2, p3):
                p0 = s._getCurrentPoint()
                for i in range(1, 49):
                    from fontTools.misc.bezierTools import splitCubicAtT
                    s.pts.append(splitCubicAtT(p0, p1, p2, p3, i / 48.0)[0][-1])

            def _qCurveToOne(s, p1, p2):
                p0 = s._getCurrentPoint()
                if p1 is None:
                    p1 = p0
                if p2 is None:
                    s._qCurveToOne(p1, p1)
                    return
                c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
                c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
                for i in range(1, 49):
                    from fontTools.misc.bezierTools import splitCubicAtT
                    s.pts.append(splitCubicAtT(p0, c1, c2, p2, i / 48.0)[0][-1])

            def _closePath(s): pass
            def _endPath(s): pass

        shim = Shim(font.getGlyphSet())
        parse_path(d, shim)
        glyph = cmap[cp]
        expected = _flattened(font, glyph)
        # SVG was written y-down; the font is y-up. Flip the SVG points back.
        flipped = [(x, ASCENT - y) for x, y in shim.pts]
        worst = max(worst, _deviation(flipped, expected), _deviation(expected, flipped))
        checked += 1
    r.check(checked == 41, "all 41 files round-tripped", f"{checked} checked")
    r.check(worst <= 0.5, "every SVG draws the same shape as the font glyph",
            f"max deviation {worst:.6f} font units (path-data rounding only)")

    print("\n5) Not clipped by its own viewBox")
    outside = []
    for cp, cls in sorted(names.items()):
        if cp == SENTINEL:
            continue
        f = OUT / f"{cls}.svg"
        if not f.is_file():
            continue
        root = ET.fromstring(f.read_text(encoding="utf-8"))
        d = root.find(".//{http://www.w3.org/2000/svg}path").get("d")
        rec = RecordingPen()
        parse_path(d, rec)
        for op, args in rec.value:
            if op not in ("moveTo", "lineTo", "curveTo", "qCurveTo"):
                continue
            # args is a tuple of points; qCurveTo may encode an implied
            # on-curve point as None, which has no coordinates to check.
            for pt in (p for p in args if p is not None):
                x, y = pt[0], pt[1]
                if not (-0.5 <= x <= VIEWBOX + 0.5 and -0.5 <= y <= VIEWBOX + 0.5):
                    outside.append(f"{cls}({x:.0f},{y:.0f})")
    r.check(not outside, "all geometry inside the viewBox", str(outside[:4]))

    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    args = ap.parse_args()

    try:
        import fontTools  # noqa: F401
    except ImportError:
        sys.exit("missing dependency: pip install fonttools")

    if not args.check:
        n = build()
        size = sum(p.stat().st_size for p in OUT.glob("*.svg"))
        print(f"Generated {n} SVG files into {OUT.relative_to(REPO)}/ ({size:,} B total)")

    rep = verify()
    print("\n" + "=" * 62)
    if rep.failures:
        print(f"RESULT: FAILED - {len(rep.failures)}/{rep.checks} checks failed")
        for f in rep.failures:
            print(f"  - {f}")
        print("=" * 62)
        return 1
    print(f"RESULT: OK - all {rep.checks} checks passed")
    print("every SVG is a faithful, self-contained rendition of its font glyph")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())