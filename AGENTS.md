# AGENTS.md

## What this repository is

`sub-iconfont` is a **2013-era design asset release**, not a software package. It ships a
generated icon font (41 glyphs, 22 icons) for the SUB Göttingen library catalogue, together
with the Illustrator working files and the design guidelines the set was built under.

There is **no build system, no test suite, no CI, no linter, and no source code to refactor.**
The only "code" is one IcoMoon-generated stylesheet, one generated demo page, and a small
generated IE7 shim. If you were expecting a conventional Node/JS project, you should read
this section twice before touching anything.

Practical consequences:

- Most files are **binary** (`.ai`, `.indd`, `.ttf`, `.woff`, `.eot`, `.pdf`, `.png`, `.jpg`).
  Diffing them is noise. Never let a formatter, minifier, or "cleanup" pass reach them.
- The repository is ~50 MB, of which ~37 MB is `Workfiles/` history. Diffs are large and
  unreviewable. **Get explicit confirmation before staging or committing `.ai` files.**
- `package.json` exists only so the release is installable from npm/yarn. It has
  **no `dependencies`, no `scripts`, and `"main": "index.js"` points at a file that does not
  exist.** Do not treat it as a project manifest or try to "fix" it as one.

## Layout

```
ReadMe.md                  Package overview and usage notes (consumer-facing)
Character_Map.md           Codepoint → icon name table (documentation)
Icons_and_Guidelines.pdf   Published guidelines: icon overview + design principles
License.txt                MIT

SUB-Icon-Font/             ← THE DISTRIBUTABLE. Everything else is source/history.
  fonts/subicons.{eot,woff2,woff,ttf,svg}   Compiled font binaries
  fonts/subicons.dev.svg                    IcoMoon round-trip file — THE EDITABLE SOURCE
  svg/subicon-*.svg                         One standalone SVG per glyph (41 files)
  style.css                                 Generated @font-face + .subicon-* class rules
  index.html                                Generated glyph/demo page
  lte-ie7.js                                Generated IcoMoon IE≤7 :before shim
  Read Me.txt                               IcoMoon note about editing subicons.dev.svg

tools/
  build-woff2.py             Derives subicons.woff2 from subicons.ttf, then verifies it
  build-svg.py               Derives svg/*.svg from subicons.ttf, then verifies them

Workfiles/                 Illustrator sources and exports. Never shipped to consumers.
  sub-iconfont_<icon>/      One folder per icon, holds all its .ai versions
    _refs/                 Optional source photos/screenshots
  _exports/SVG-exports_<YYYY-MM-DD>_<HH.MM>/
                           Flattened, Illustrator-generated SVG per layer
  _misc/                   Splash image
  Icons & Guidelines.{ai,indd}   Source of the guidelines PDF
```

## Sources of truth, in precedence order

When two files disagree, believe the higher one and fix the lower one.

1. **`SUB-Icon-Font/fonts/subicons.dev.svg`** — glyph outlines *and* the
   `unicode` → `data-tags` mapping. This is the single authoritative artifact.
2. **`SUB-Icon-Font/style.css`** — must be exactly derivable from (1).
3. **`SUB-Icon-Font/index.html`** — must be exactly derivable from (1).
4. **`SUB-Icon-Font/fonts/subicons.{eot,woff,ttf,svg}`** — derived binaries, must match (1).
5. **`Character_Map.md`** — human-readable documentation, derived. **Currently out of
   sync with (1); see "Known inconsistencies".**
6. **`ReadMe.md` / `Icons_and_Guidelines.pdf`** — prose and design rules, hand-maintained.

You can dump the authoritative mapping at any time with:

```bash
python3 - <<'EOF'
import re
s = open('SUB-Icon-Font/fonts/subicons.dev.svg', encoding='utf-8').read()
pairs = sorted(re.findall(r'unicode="&#x([0-9a-f]+);"[^>]*?data-tags="([^"]+)"', s),
               key=lambda p: int(p[0], 16))
for cp, tag in pairs:
    print(f"U+{cp}  subicon-{tag}")
EOF
```

## The API contract — what must never change

The font is consumed by third-party library systems that hard-code these values. These are
**published, frozen identifiers**. Changing any of them is a breaking change and requires a
major version bump plus a changelog entry — it is not a refactor.

### Codepoints are assigned in the Unicode Private Use Area

| Range | Contents |
|---|---|
| `U+E000`–`U+E023` | 18 two-layer icons × (bg, fg), **even = `_bg` dark, odd = `_fg` light** |
| `U+E024`–`U+E050` | **Reserved / deliberately unassigned.** Leave empty. |
| `U+E051`–`U+E053` | Single-layer UI arrows (no `_bg`/`_fg` suffix) |
| `U+E054`–`U+E055` | UI loupe (bg, fg) |
| `U+F000` | IcoMoon sentinel glyph, `class="hidden"`. Required; do not remove. |
| `U+0020` | IcoMoon-injected space advance. Required for `dev.svg` to re-import. |

Hard rules:

- **Never renumber or reorder existing glyphs.** Add new icons *after* `U+E055`.
- **Never reuse `U+E024`–`U+E050`.**
- **The even/odd bg/fg pairing is structural.** For every two-layer icon, `_bg` is the lower
  (even) codepoint and `_fg` is the higher (odd) codepoint. The even glyph is always the
  dark background layer.
- Codepoints are written `U+E0xx` in prose and `\e0xx` in CSS `content:` values.

### Two-layer architecture

Each media-type icon is **two separate glyphs** meant to be stacked with CSS:

- `_bg` is the dark structural outline/shadow mass; `_fg` is the lighter accent layer.
- Layer order in the DOM does not matter — the artwork never overlaps.
- **Consumers must colour background layers darker than foreground layers**, otherwise the
  icon renders wrong. This is why they are split rather than baked into one glyph. Do not
  "simplify" by merging the two layers into a single outline; that destroys the entire
  colour-customisation capability.

Single-layer icons (the three UI arrows) intentionally have no `_bg`/`_fg` variant.

### Class naming

`subicon-<workfiles-folder-name>[_bg|_fg]`, e.g. `subicon-book_bg`, `subicon-video_fg`,
`subicon-ui-arrow-prev-page`. The `subicon-` prefix is added by IcoMoon's CSS generator;
`data-tags` in `dev.svg` stores the name *without* the prefix.

The suffix comes from the Illustrator filename, so **the `Workfiles/sub-iconfont_*` folder name
is part of the public CSS API.** Renaming a folder changes published class names.

### Font metrics

Grid `24`, `units-per-em 768`, ascent `736`, descent `-32`, `horiz-adv-x 768`. The Illustrator
exports are on a `960 × 960` viewBox (`24 × 40`). Keep the grid and metrics unchanged — the
antialiasing was tuned by hand against them (see the `nudged-to-fix-antialias` files).

### Outline flavours differ per format — this is normal, do not "fix" it

The shipped binaries were produced by FontForge and IcoMoon and do **not** use one outline
flavour throughout:

| File | Flavour | Notes |
|---|---|---|
| `subicons.ttf`, `subicons.eot` | TrueType `glyf` | integer coordinates |
| `subicons.woff` | CFF / `OTTO` | fractional coordinates, different curve subdivision |
| `subicons.woff2` | TrueType `glyf` | derived from `subicons.ttf`, not from the WOFF |

All three carry the same 41 glyphs, the same 42 codepoints and the same metrics. Measured
outlines agree to ≤ 2.25 font units (0.047 px at a 16 px font size), which is CFF rounding.
The practical consequence: `ttf` and `woff2` render **pixel-identically**, while the CFF
`woff` differs from them in edge antialiasing (~6 % of pixels at 64 px). That is a
pre-existing property of the 2013 export, not a regression — do not re-encode the WOFF.

Two further WOFF2 artefacts are expected and harmless:

- `glyf`, `loca` and `head` are re-encoded (the WOFF2 glyf transform, plus a recomputed
  `checkSumAdjustment`). Compare them semantically, never byte-for-byte.
- `head.flags` bit 11 gets set by **every** WOFF2 encoder — verified against six unrelated
  system fonts, not just this one. It is a legacy rasteriser hint; this font ships no
  TrueType hinting instructions at all, so it cannot affect rendering.

### Which file is the WOFF2 built from

`subicons.woff2` is derived from **`subicons.ttf`**, not from the Illustrator masters and not
from `subicons.woff`. That is deliberate: a container repack cannot introduce glyph drift, so
the WOFF2 can never disagree with the TTF about which glyph a codepoint means.

## The standalone SVGs (`SUB-Icon-Font/svg/`)

41 files, one per **glyph**, generated by `tools/build-svg.py` from `subicons.ttf`.

**One file per glyph, never one per icon.** Each media-type icon is two glyphs (`_bg` + `_fg`)
that consumers stack themselves. Merging them into a single SVG would bake the layers together
and destroy the colour-customisation contract that the whole two-layer design exists to provide.
19 two-layer icons produce 38 files; the 3 UI arrows produce 3 single-layer files. 41 total.

Invariants — all enforced by `build-svg.py --check`:

- **Filename = CSS class = `data-tags` value.** `svg/subicon-book_bg.svg` corresponds to
  `.subicon-book_bg` in `style.css` and `data-tags="book_bg"` in `dev.svg`. These three must
  never drift apart; a rename here is a breaking API change, exactly like a font rename.
- **One `<path>` per file**, carrying `id` **and** `class` set to that same name, so a layer can
  be targeted individually or referenced by id.
- **`viewBox="0 0 768 768"`** — the font's em box (ascent 736 + descent 32 = a 24 px grid at 32
  units/px). Not the `960` used by the old Illustrator exports; 768 needs no scaling and
  therefore keeps the SVG pixel-for-pixel consistent with what the font renders.
- **Outlines are baked y-down.** Fonts point up, SVG points down, so the generator applies
  `y_svg = 736 - y_font` into the path data. The files therefore carry no `transform`
  attribute. Do not "simplify" this by shipping a transform or by flipping again.
- **`fill="currentColor"`**, so a referenced file renders black and an inlined one inherits
  `color`.
- **The `U+F000` sentinel is deliberately absent** — it has zero advance width, carries
  `class="hidden"`, and is not an icon. Its absence is asserted, not incidental.

Output is deterministic: two runs are byte-identical, and there are no timestamps or ordering
dependencies.

Note that `subicons.dev.svg` stores **cubic** curves while `subicons.ttf` stores **quadratic**
ones, because TrueType has no cubic Bézier. The two agree geometrically to 2.94 font units
(0.06 px at 16 px) with identical contour counts. The SVGs are generated from the TTF so they
match exactly what the WOFF2 serves; do not generate them from `dev.svg` instead.

## Regenerating the font

The pipeline is **IcoMoon (https://icomoon.io/app) + Adobe Illustrator**, both GUI tools.
There is no CLI equivalent for the AI half.

1. Edit the relevant `.ai` file in `Workfiles/sub-iconfont_<name>/`. The current version is the
   **highest `vNNN`** in that folder (see naming rules below).
2. Export the layer(s) as SVG into a new `Workfiles/_exports/SVG-exports_<date>_<time>/`.
3. Open `SUB-Icon-Font/fonts/subicons.dev.svg` in IcoMoon. It re-imports glyph outlines,
   `unicode` values, and `data-tags` class names.
4. In IcoMoon, replace the affected glyph's artwork, confirm the codepoint and `data-tags`
   are **unchanged**, then export with: font name `subicons`, grid `24`, formats
   `eot/woff/ttf/svg`, **Legacy class names / per-glyph classes**, prefix `subicon`.
5. IcoMoon regenerates `style.css`, `index.html`, `lte-ie7.js` and `fonts/subicons.*`.
   Replace all of them together — they are generated artefacts and must stay in lockstep.
6. **IcoMoon cannot emit WOFF2 or standalone SVGs**, so step 5 deletes both and drops the
   `woff2` entry from the `@font-face` `src` list. Restore them:
   ```bash
   python3 tools/build-woff2.py          # needs: pip install fonttools brotli
   python3 tools/build-svg.py            # needs: pip install fonttools
   ```
   `build-woff2.py --check` / `build-svg.py --check` verify without writing (exit 1 on drift).
   The woff2 build prefers `woff2_compress` (Google's reference encoder) and falls back to
   pure-Python fontTools; both are byte-reproducible. The SVG build has no external encoder.
7. Update `Character_Map.md` if any name or codepoint changed.

**Verification** (there is no test runner; this is the substitute):

- `python3 tools/build-woff2.py --check` — 31 assertions covering table integrity, all 45
  outlines, `cmap`, the reserved `U+E024`–`U+E050` range, the even/odd layer pairing,
  metrics, and that `style.css` lists `woff2` first. Run after any font change.
- `python3 tools/build-svg.py --check` — 14 assertions covering file inventory against
  `dev.svg` `data-tags`, XML validity, viewBox, one path per file, the `_bg`/`_fg` pairing
  (19 pairs), the single-layer arrows, exclusion of the `U+F000` sentinel, an independent
  re-parse round-trip of every path against the font, and that nothing is clipped.
- Re-extract the mapping with the snippet above and confirm it differs from the committed one
  only in the icons you touched.
- `grep -c 'data-icon=' SUB-Icon-Font/index.html` → must be **41** (one per glyph).
- `grep -c 'subicon-' SUB-Icon-Font/index.html` in the "Class Names" section → must be 41.
- Open `SUB-Icon-Font/index.html` in a browser and eyeball every glyph against
  `Icons_and_Guidelines.pdf`. **Open the PDF and read it before judging a rendering** —
  it contains the design principles and the icon overview, and it is not viewable as text
  by some tooling (`pdftotext Icons_and_Guidelines.pdf -` works if installed).
- Render an icon **stacked** (bg + fg overlapping) at small sizes. The demo page does *not*
  stack the layers, so it will not catch a broken icon.

## Design principles (extracted from `Icons_and_Guidelines.pdf`)

Binding for any new or modified icon:

- **Base/structural outlines:** straight or slanted, prominent, **fixed width**. Must define a
  primitive shape (rectangular, square, round). May be less prominent where correctness demands
  it (e.g. manuscript/quill).
- **Distinct shadows:** **ideally just one.** Mass should balance, not dominate.
- **Inner shapes / accent details:** variable widths and proportions are fine. Must **not
  exceed 1/3 of the total symbol**, and must stay visually intact when zoomed out.
- **Curves** only when clearly needed for intelligibility, never by default.
- **Layers/colour:** every icon has a dark background layer and a light foreground layer;
  background must stay darker than foreground.

## Workfiles conventions

- One folder per icon: `Workfiles/sub-iconfont_<name>/`, `<name>` matching the CSS name stem.
- Versions are `sub-iconfont_<name>_vNNN.ai`, `vNNN` incrementing from `v100`.
- Descriptive suffixes are appended to the version, e.g.
  `sub-iconfont_map_v111-highlight-test.ai`, `sub-iconfont_file_v102-nudged-to-fix-antialias-2.ai`.
- **`-old-guides` means "drawn before the current design principles were settled".** Those files
  are historical only — never treat them as current, and do not delete them.
- **Highest `vNNN` is not always current.** `sub-iconfont_file_v102.ai` is superseded by
  `sub-iconfont_file_v102-nudged-to-fix-antialias-2.ai`. Read the version list before picking
  a file to edit.
- Keep every prior version. Do not overwrite or garbage-collect `.ai` files; the history is
  the only record of how each icon converged.

## Known inconsistencies (pre-existing — confirm before "fixing")

These are latent bugs, not intentional design. Raise before changing any of them, since they
are visible to existing consumers.

1. **`Character_Map.md` "CSS Class" column does not match `style.css`.** It lists abbreviated
   pseudo-classes instead of the real ones. Codepoints are correct; names are not.

   | `Character_Map.md` | actual CSS class stem |
   |---|---|
   | `multivolume` | `multivolume-work` |
   | `electronic` | `file` |
   | `data` | `research-data` |
   | `audio-visual` *(Video)* | `video` |
   | `recording` | `audio` |
   | `music-score` | `music` |
   | `microform` | `microfiche` |
   | `website` | `web-resource` |
   | `multiple` | `multiple-mediatypes` |
   | `magnifier` | `ui-loupe` |
   | `previous` / `next` / `?` | `ui-arrow-prev-page` / `ui-arrow-next-page` / `ui-arrow-go-to-result` |

2. **`Character_Map.md` names `U+E010/11` "Video" with class `audio-visual`**, which is where
   the "audio-visual" row above comes from; `U+E012/13` is named "Recording" but is really
   **Audio**. `Icons_and_Guidelines.pdf` lists *Audio* and *Video* as separate icons, confirming
   the codepoints are right and the names are wrong.

3. **`Read Me.txt` claims class names are stored in `subicons.dev.svg`.** They are, but in
   `data-tags` attributes, not as `class` or `id` — `class` is used only for the `U+F000`
   sentinel. Wording is misleading but not functionally wrong.

4. **`package.json` `"main": "index.js"`** points at a nonexistent file.

## Working rules

- Do not add a build system, test framework, bundler, or dependency to this repo. If a task
  appears to need one, that is a signal the task is aimed at the wrong repository. The only
  permitted exceptions are `tools/build-woff2.py` and `tools/build-svg.py` (and their
  `fonttools`/`brotli` requirement), which exist only because IcoMoon can emit neither
  WOFF2 nor standalone SVGs.
- Never hand-edit `SUB-Icon-Font/fonts/subicons.{eot,woff2,woff,ttf,svg}`,
  `SUB-Icon-Font/svg/*.svg`, `style.css`, `index.html`, or `lte-ie7.js` to "fix" something.
  They are generated; the fix belongs in the `.ai` file or in IcoMoon, followed by a full
  re-export and then the two `tools/build-*.py` scripts.
- **The one sanctioned hand-edit to `style.css`** is adding the `woff2` line to the
  `@font-face` `src` list, immediately after the `embedded-opentype` entry. IcoMoon removes it
  again on the next regeneration, which is exactly why the build script exists. Do not
  reorder, reformat, or otherwise tidy the block.
- **Never edit files in `SUB-Icon-Font/svg/` by hand, and never add, merge, or delete one.**
  They are generated from the font; the set is defined by `dev.svg`'s `data-tags`. Adding a
  hand-drawn SVG would silently diverge from the font, and merging a `_bg`/`_fg` pair into one
  file would break the layering contract.
- Never reformat, minify, or normalise `style.css`/`index.html`/`svg/*.svg` — the tabs and the
  IcoMoon selector order are upstream output and churn against regenerated files.
- Do not convert `.ai` → `.svg` and commit the conversion as a substitute for the real file.
  The `.ai` masters are the source of truth.
- Attribution must be preserved: design by **Henrik Cederblad, Cederblad Design**;
  commissioned 2013 by **SUB Göttingen** (Georg-August-Universität Niedersächsische Staats- und
  Universitätsbibliothek). MIT license, `License.txt`. Keep both in any new documentation.
- Version state: `package.json` is `1.0.0` and git tag `1.0.0` exists on `master`. Any change
  to a codepoint, class name, or font metric requires `2.0.0`, not `1.0.1`.

## Reference

- Design/usage documentation: https://icomoon.io/#docs/font-face
- Upstream: https://github.com/subugoe/sub-iconfont
- Commissioning body: http://www.sub.uni-goettingen.de