# L30 orthogonal (perpendicular-fan) variant — design notes

Companion to `L30_design_notes.md`, which has the full derivation of the L30
filter's geometry. This doc only covers what's different in
`filter_L30_orthogonal.py` and why, plus (once run) the HFSS comparison
result against `filter_L30.py`.

## What changed vs. filter_L30.py

`filter_L30.py` hand-tilts three of its four shunt branch pairs off
perpendicular (`BRANCH_PAIRS[i]['tilt']`: P1=0, P2=20, P3=`TILT_DEG`=55,
P4=0) purely to shrink the transverse footprint enough to fit a 7mm-wide
chip. Per that file's own design notes (`L30_design_notes.md` §5), the
as-synthesized transverse envelope at `tilt=0` is **~9.01mm**, vs. ~5.17mm
realized at 55°. That tilt is a mask-layout space-saving choice layered on
top of the Nuhertz-synthesized electrical dimensions — it rotates each
stalk+fan rigidly but changes no stalk length/width, fan radius/angle, or
`attach_width`.

`filter_L30_orthogonal.py` is the same filter with:
- Every `BRANCH_PAIRS[i]['tilt']` set to `0.0` (all fans mounted exactly
  perpendicular to the main line — the as-synthesized orientation, no
  mechanical lean).
- Chip width raised from 7000um to **13000um** (`m.Wafer(...)` `chipWidth`
  arg) — comfortably above the 9.01mm as-synthesized envelope estimate, to
  leave room for each fan's actual arc footprint (which extends beyond the
  simple projected envelope near P2/P3's larger radii).
- `WIDTH_BUDGET_UM` raised from 6500 to 12000 to match, so the built-in
  over-budget warning stays meaningful rather than firing spuriously.
- Chip ID `'L30_ORTHO'` / wafer name `'filter_L30_orthogonal'`, so DXF/GDS
  output doesn't collide with `filter_L30.py`'s.
- Chip height (40000um) left unchanged — axial spacing between branches is
  governed by `SERIES_SECTIONS` lengths, not by tilt, so no reason to expect
  it needed to grow (confirmed at build time, see Results below).

`SERIES_SECTIONS`, all `BRANCH_PAIRS` stalk/fan electrical dimensions, pad/
taper/output-line constants, and the drawing helper functions
(`radial_fan`, `branch_pair`, `guarded_straight`, `guarded_taper`) are
byte-for-byte identical to `filter_L30.py` — this file changes tilt and
chip size only.

## Why

To see what `filter_L30.py`'s tilt-based space optimization cost (or didn't
cost) electrically, by building the filter exactly as Nuhertz synthesized it
(no mechanical rotation) and running it through the same HFSS wave-port S21
pipeline validated for `filter_L30.py` this session, then comparing.

## Build-time geometry check (repo `.venv`, no Ansys)

`filter_L30_orthogonal.py`'s own printed report, first run:
- Realized transverse bounding box: **8890.1 um**, under the 12000um budget
  (vs. filter_L30.py's 9.01mm as-synthesized *envelope* estimate — 8890.1um
  realized is consistent with that, actual fan footprint included).
- Per-pair transverse width: P1 1315.4um, P2 6100.2um, P3 8890.1um (the
  overall max), P4 3030.5um.
- Per-pair nearest-neighbor clearance (vertex-to-vertex approximation): P1↔P2
  1123.4um, P2↔P3 2871.1um, P3↔P4 2717.3um — all well above the 500um
  "confirm visually" flag threshold, no warnings raised.
- No `attach_width` mismatch warnings from any `radial_fan()` call.
- Chip height unchanged (40000um) — no axial clearance issue introduced by
  removing tilt.

Note: filter_L30.py has a previously-flagged, still-unfixed P1 fan
self-overlap/fan-vs-mainline overlap bug (found via klayout Region analysis,
not visible to the vertex-distance/bbox checks above). P1 has `tilt=0` in
both files, so it was a real risk this would reappear here too - checked via
`verify_L30_orthogonal_hfss_export.py`'s klayout Region merge/hole-count
gate (the same kind of check that originally caught it): **passed cleanly**
- 1 merged polygon, 0 holes, both port cut-plane widths exactly correct.
Whatever that earlier finding was, it isn't visible as a real geometric
defect in this design's merged-region accounting.

## HFSS build result (AEDT, wave-port pipeline)

`RUN_ANALYSIS=False` smoke test passed cleanly first: all 26 pieces drew and
`Unite()`'d into a single solid, confirmed directly against the live AEDT
session (`GetObjectsInGroup("Unclassified")` empty; exactly 3 solids -
`PinPad` (the united metal, material=aluminum), `Substrate`, `Package`).
The perpendicular stalk/fan joints unite fine with the same
`STALK_FAN_OVERLAP_UM=5.0` value tuned for `filter_L30.py`'s tilted joints -
no rework needed there.

The real solve (`RUN_ANALYSIS=True`) also completed successfully - full
12-pass adaptive mesh, 2301-point interpolating sweep, confirmed by real
per-pass solution data (`SD1`-`SD12` files) in the `.aedtresults` folder -
but pyEPR's `HfssFrequencySweep.get_report_arrays()` failed with a
`FileNotFoundError`: it exports the report via `tempfile.mktemp()` and
immediately reads it back, and AEDT's `ExportToFile` COM call silently
didn't produce a file at that particular temp path (no exception raised at
the COM layer - the file just never appeared). Confirmed this wasn't a
failed/missing solve by manually re-running the same `CreateReport`/
`ExportToFile` sequence against an explicit path inside this repo's own
`HFSS/` folder, which worked immediately and returned the full, real 2301
point sweep. `filter_L30_orthogonal_HFSS.py` now does this explicit-path
export itself (see its `_pull()` helper) rather than relying on pyEPR's
default tempfile-based helper - documented in `CLAUDE.md`'s HFSS section as
a general pyEPR 0.8 lesson, since `filter_L30_HFSS.py` uses the same
default helper and could hit this on some future re-run.

## HFSS comparison result

Full numeric comparison in `Radial_Stub_LPF/HFSS/compare_L30_variants.py`'s
own printed output; overlay plot at
`Radial_Stub_LPF/HFSS/compare_L30_variants.png`.

| | filter_L30 (tilted, 7mm chip) | filter_L30_orthogonal (perpendicular, 13mm chip) |
|---|---|---|
| Passband (0.5-3.5GHz) S21 | -0.20 to -4.53 dB | -0.53 to -4.31 dB |
| S21 at 3.5GHz cutoff | -3.35 dB | -4.31 dB |
| Passband S11 | -1.89 to -13.49 dB | -2.01 to -9.37 dB |
| S21 nulls below -20dB | 5.180 GHz (-50.25dB), 9.665 GHz (-102.69dB), 10.940 GHz (-35.45dB) | 6.415 GHz (-67.34dB), 9.355 GHz (-107.52dB), 9.665 GHz (-66.92dB), 10.830 GHz (-35.97dB) |

**Takeaway**: the two designs are electrically very close in the passband -
both give a low-loss 0.5-3.5GHz band with a broadly similar equiripple
shape and comparable ~3-4.5dB insertion loss at the 3.5GHz cutoff. The
tilt-based space optimization (7mm vs 13mm chip) does **not** come with an
obvious passband electrical penalty.

Where they genuinely differ is the stopband null placement: the orthogonal
(perpendicular) version's first deep null sits noticeably higher
(6.415GHz vs. 5.180GHz for the tilted version), and it shows an extra
resolved null near 9.355GHz that isn't distinctly separated from the
9.665GHz null in the tilted version's response. Since every stalk/fan
*electrical* dimension (length, radius, angle, `attach_width`) is
byte-for-byte identical between the two files, this shift is a real
electromagnetic effect of the mechanical tilt itself - most likely because
tilting changes each fan's physical proximity/parasitic coupling to the
main line and to its neighboring branch pairs, which a simple
transmission-line synthesis model doesn't capture. In other words: tilt is
not electrically "free" - it re-shapes the stopband null pattern even
though it doesn't touch the passband much. This is exactly the kind of
effect the original handoff doc's own dimensions (both files' - all still
PLACEHOLDER pending real HFSS re-extraction) would need to account for in
a final, tuned design.
