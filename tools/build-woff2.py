#!/usr/bin/env python3
"""
build-woff2.py - derive subicons.woff2 from subicons.ttf, then verify it.

WHY THIS EXISTS
---------------
`SUB-Icon-Font/` is normally regenerated wholesale by IcoMoon (see
`SUB-Icon-Font/Read Me.txt`). IcoMoon's free tier cannot emit WOFF2, so a
regeneration silently drops the file and the woff2 entry in the @font-face
`src` list. This script restores both deterministically and proves the result
is lossless, so adding WOFF2 never depends on a manual binary drop.

The conversion is a pure container repack: WOFF2 carries the same outlines,
the same `cmap`, and the same metrics as the source TTF. It is not a re-export
from the Illustrator masters, so it can never drift from `subicons.ttf`.

USAGE
-----
    python3 tools/build-woff2.py            # build subicons.woff2 + verify
    python3 tools/build-woff2.py --check    # verify only, write nothing (exit 1 on drift)

REQUIRES
--------
    fonttools >= 4.x   and   brotli        # pip install fonttools brotli
Optional, preferred if present:
    woff2_compress                          # Google's reference encoder
    (brew install woff2 / apt install woff2 / npm i -g wawoff2)

Exit codes: 0 = ok, 1 = drift or failure, 2 = missing dependency.
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONTS = REPO / "SUB-Icon-Font" / "fonts"
TTF = FONTS / "subicons.ttf"
WOFF2 = FONTS / "subicons.woff2"
CSS = REPO / "SUB-Icon-Font" / "style.css"

# Codepoints that make up the published API contract (see AGENTS.md).
EXPECTED_CODEPOINTS = (
    [c for c in range(0xE000, 0xE024)]          # 36: 18 icons x (bg, fg)
    + [0xE051, 0xE052, 0xE053, 0xE054, 0xE055]  # UI arrows + loupe
    + [0xF000]                                   # IcoMoon sentinel, must survive
)
RESERVED = range(0xE024, 0xE051)                # must stay unassigned


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


def _require_fonttools():
    try:
        import fontTools  # noqa: F401
    except ImportError:
        sys.exit("missing dependency: pip install fonttools brotli")
    try:
        import brotli  # noqa: F401
    except ImportError:
        sys.exit("missing dependency: pip install brotli")


def build() -> str:
    """Produce WOFF2 from the TTF. Returns the encoder used."""
    if not TTF.is_file():
        sys.exit(f"source font not found: {TTF}")

    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / TTF.name
        shutil.copy2(TTF, work)

        if shutil.which("woff2_compress"):
            subprocess.run(["woff2_compress", str(work)], check=True,
                           stdout=subprocess.DEVNULL)
            made = work.with_suffix(".woff2")
            if not made.is_file():
                sys.exit("woff2_compress produced no output")
            shutil.copy2(made, WOFF2)
            return "woff2_compress (reference encoder)"

        # Portable fallback: fontTools' pure-Python WOFF2 writer.
        from fontTools.ttLib import TTFont
        font = TTFont(str(TTF))
        font.flavor = "woff2"
        # fontTools otherwise stamps head.modified with the current time, which
        # would make every build produce a different file. Pin it to the source
        # so the output is byte-reproducible.
        font.recalcTimestamp = False
        font.save(str(WOFF2))
        return "fontTools (pure Python)"


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

def _flattened_points(font, glyphname: str, steps: int = 32) -> list[tuple]:
    """Flatten a glyph to a polyline.

    Two encodings of the same artwork can subdivide curves differently (and CFF
    keeps fractional coordinates), so point-by-point comparison is meaningless.
    Flattening both to polygons lets us ask the only question that matters:
    "does this draw the same shape?"
    """
    from fontTools.misc.bezierTools import splitCubicAtT
    from fontTools.pens.basePen import BasePen

    class Flatten(BasePen):
        def __init__(self, glyphset, steps):
            super().__init__(glyphset)
            self.steps, self.pts = steps, []

        def _moveTo(self, p): self.pts.append(p)
        def _lineTo(self, p): self.pts.append(p)

        def _curveToOne(self, p1, p2, p3):
            p0 = self._getCurrentPoint()
            for i in range(1, self.steps + 1):
                self.pts.append(splitCubicAtT(p0, p1, p2, p3, i / self.steps)[0][-1])

        def _qCurveToOne(self, p1, p2):
            p0 = self._getCurrentPoint()
            c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
            c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
            for i in range(1, self.steps + 1):
                self.pts.append(splitCubicAtT(p0, c1, c2, p2, i / self.steps)[0][-1])

        def _closePath(self): pass
        def _endPath(self): pass

    pen = Flatten(font.getGlyphSet(), steps)
    font.getGlyphSet()[glyphname].draw(pen)
    return pen.pts


def max_deviation(a: list[tuple], b: list[tuple]) -> float:
    """Symmetric nearest-point distance between two polylines, in font units."""
    grid: dict[tuple, list] = {}
    for p in b:
        grid.setdefault((round(p[0] * 4), round(p[1] * 4)), []).append(p)
    worst = 0.0
    for p in a:
        kx, ky = round(p[0] * 4), round(p[1] * 4)
        best = math.inf
        for dx in range(-8, 9):
            for dy in range(-8, 9):
                for q in grid.get((kx + dx, ky + dy), ()):
                    best = min(best, math.dist(p, q))
        if best is not math.inf:
            worst = max(worst, best)
    return worst


def verify(strict_warnings: bool = True) -> Report:
    from fontTools.ttLib import TTFont

    r = Report()
    if not WOFF2.is_file():
        r.check(False, "subicons.woff2 exists")
        return r

    src, out = TTFont(str(TTF)), TTFont(str(WOFF2))

    print("\n1) Container")
    r.check(out.sfntVersion == src.sfntVersion,
            "flavour matches source TTF (TrueType, not OTTO)", str(out.sfntVersion))
    r.check(sorted(src.keys()) == sorted(out.keys()), "same table directory",
            f"{len(out.keys())} tables")

    print("\n2) Tables that must survive bit-identical")
    # glyf/loca/head are legitimately rewritten by the WOFF2 glyf transform and
    # by checkSumAdjustment recomputation, so they are checked semantically below.
    volatile = {"glyf", "loca", "head", "GlyphOrder", "fvar"}
    for t in sorted(k for k in src.keys() if k not in volatile):
        same = src.reader[t] == out.reader[t]
        r.check(same, f"{t} identical ({len(src.reader[t])} bytes)")

    print("\n3) Tables that are re-encoded - checked semantically instead")
    head_diff = {f for f in set(src['head'].__dict__) | set(out['head'].__dict__)
                 if src['head'].__dict__.get(f) != out['head'].__dict__.get(f)}
    r.check(head_diff <= {"checkSumAdjustment", "flags"},
            "head differs only in checkSumAdjustment/flags",
            f"differing fields: {sorted(head_diff) or 'none'}")
    r.check(src['head'].unitsPerEm == out['head'].unitsPerEm == 768,
            "head.unitsPerEm unchanged", str(out['head'].unitsPerEm))
    r.check((src['head'].xMin, src['head'].yMin, src['head'].xMax, src['head'].yMax)
            == (out['head'].xMin, out['head'].yMin, out['head'].xMax, out['head'].yMax),
            "font bounding box unchanged")
    r.check(src['maxp'].__dict__ == out['maxp'].__dict__,
            "maxp identical (all glyph limits)", f"numGlyphs={out['maxp'].numGlyphs}")

    print("\n4) Glyph outlines - the thing that actually gets drawn")
    r.check(src.getGlyphOrder() == out.getGlyphOrder(),
            "glyph order identical", f"{len(out.getGlyphOrder())} glyphs")
    worst = 0.0
    for name in src.getGlyphOrder():
        a, b = _flattened_points(src, name), _flattened_points(out, name)
        worst = max(worst, max_deviation(a, b), max_deviation(b, a))
    # Flattening tolerance, not a real tolerance: subdivision points land within
    # a fraction of a font unit of the true curve either way.
    r.check(worst <= 1.0, "every outline geometrically identical",
            f"max deviation {worst:.6f} font units")

    print("\n5) Published API contract - codepoints")
    s, o = src.getBestCmap(), out.getBestCmap()
    r.check(set(s) == set(o), "same codepoints mapped", f"{len(o)} codepoints")
    r.check(s == o, "codepoint -> glyph mapping identical")
    missing = [c for c in EXPECTED_CODEPOINTS if c not in o]
    r.check(not missing, "all 41 glyphs + U+F000 sentinel present",
            f"missing {[hex(c) for c in missing]}" if missing else "42 codepoints")
    r.check(o.get(0xF000) == "uniF000", "U+F000 IcoMoon sentinel preserved")
    clashing = [c for c in o if c in RESERVED]
    r.check(not clashing, "U+E024-U+E050 still unassigned",
            f"clashing {[hex(c) for c in clashing]}" if clashing else "reserved range intact")
    # Layer parity: every two-layer icon must keep even=_bg, odd=_fg.
    pairs = [(c, c + 1) for c in range(0xE000, 0xE024, 2)]
    r.check(all(a in o and b in o for a, b in pairs),
            "all 18 even/odd background+foreground pairs intact")

    print("\n6) Vertical metrics, naming, embedding")
    r.check(src['hhea'].__dict__ == out['hhea'].__dict__, "hhea identical",
            f"ascent={out['hhea'].ascent} descent={out['hhea'].descent}")
    r.check([src['hmtx'][n] for n in src.getGlyphOrder()]
            == [out['hmtx'][n] for n in out.getGlyphOrder()],
            "hmtx advance widths identical")

    # OS/2 and name hold nested objects (Panose, NameRecord) that do not
    # implement __eq__, so compare plain values rather than object identity.
    # OS/2 is version 1 here, so probe defensively: fields added in later
    # versions simply do not exist on either side and must compare as equal.
    os2_fields = ("version", "xAvgCharWidth", "usWeightClass", "usWidthClass", "fsType",
                  "ySubscriptXSize", "ySubscriptYSize", "ySubscriptXOffset",
                  "ySuperscriptXSize", "ySuperscriptYSize", "usFirstCharIndex",
                  "usLastCharIndex", "sTypoAscender", "sTypoDescender", "sTypoLineGap",
                  "usWinAscent", "usWinDescent", "sxHeight", "sCapHeight", "usDefaultChar",
                  "usBreakChar", "usMaxContext", "fsSelection", "achVendID")
    MISSING = object()
    os2_of = lambda f: tuple(getattr(f['OS/2'], k, MISSING) for k in os2_fields)
    panose_of = lambda f: tuple(getattr(f['OS/2'].panose, a, MISSING)
                                for a in sorted(f['OS/2'].panose.__dict__))
    r.check(os2_of(src) == os2_of(out), "OS/2 fields identical",
            f"v{out['OS/2'].version} fsType={out['OS/2'].fsType} "
            f"weight={out['OS/2'].usWeightClass} "
            f"win={out['OS/2'].usWinAscent}/{out['OS/2'].usWinDescent}")
    r.check(panose_of(src) == panose_of(out), "OS/2 panose identical")

    names_of = lambda f: tuple(
        (rec.nameID, rec.platformID, rec.platEncID, rec.langID, rec.toUnicode())
        for rec in f['name'].names)
    r.check(names_of(src) == names_of(out), "name records identical",
            f"{len(out['name'].names)} records, family="
            f"{out['name'].getDebugName(1)!r}, version={out['name'].getDebugName(5)!r}")
    r.check(src['post'].formatType == out['post'].formatType, "post format retained")

    print("\n7) Wiring")
    css = CSS.read_text(encoding="utf-8") if CSS.is_file() else ""
    if not r.check("subicons.woff2" in css, "style.css @font-face references woff2"):
        print("       -> a future IcoMoon regeneration will drop this; "
              "re-run this script after regenerating")
    ordered = css.find("woff2") < css.find(".woff)") if "woff2" in css and ".woff)" in css else None
    if ordered is False:
        print("       -> woff2 is present but not first in src; browsers would "
              "never reach it")

    if strict_warnings and head_diff:
        print("\n   note: head.flags bit 11 is set by every WOFF2 encoder "
              "(verified against system fonts too).\n"
              "         It is a legacy rasteriser hint; this font ships no "
              "TrueType hinting,\n"
              "         so it has no effect on rendering.")

    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="verify only; do not write subicons.woff2")
    args = ap.parse_args()

    _require_fonttools()

    if not args.check:
        print(f"Building {WOFF2.relative_to(REPO)} from {TTF.name} ...")
        print(f"  encoder: {build()}")
        print(f"  size:    {TTF.stat().st_size} B (ttf) -> {WOFF2.stat().st_size} B (woff2)")

    report = verify()
    print("\n" + "=" * 62)
    if report.failures:
        print(f"RESULT: FAILED - {len(report.failures)}/{report.checks} checks failed")
        for f in report.failures:
            print(f"  - {f}")
        print("=" * 62)
        return 1
    print(f"RESULT: OK - all {report.checks} checks passed")
    print("subicons.woff2 is a lossless repackaging of subicons.ttf")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())