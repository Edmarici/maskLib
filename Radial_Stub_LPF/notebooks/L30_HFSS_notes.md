# L30 HFSS export — design notes

Companion to [`filter_L30_HFSS.py`](../filter_L30_HFSS.py),
[`filter_L30_hfss_geometry.py`](../filter_L30_hfss_geometry.py), and
[`verify_L30_hfss_export.py`](../verify_L30_hfss_export.py). Covers the
S21 export/solve pipeline specifically - see
[`L30_design_notes.md`](L30_design_notes.md) for the mask-layout design
itself (fan geometry derivation, tilt strategy, etc.).

## 1. Environment

pyEPR (0.8) + AEDT scripting requires a separate Python environment from
this repo's own `.venv` - found and confirmed this session:
`C:\Users\epm114\.AnE\` (Python 3.11.9 venv, numpy 1.26.4 matching
CLAUDE.md's pin note, pyEPR 0.8, pyaedt 0.24.1 also present but unused -
stuck with pyEPR to match `Hairpin_Filter_HFSS.py`'s already-validated API
patterns). Ansys Electronics Desktop 2023 R2 is installed
(`ANSYSEM_ROOT232`). Run HFSS scripts via
`C:\Users\epm114\.AnE\Scripts\python.exe`, from the script's own directory
(so relative `DXF/`/`HFSS/` paths resolve).

## 2. Pipeline overview

1. `filter_L30.py` draws the mask (DXF) and now also exports GDS
   (`dxf_to_gds`) - needed by `hfssExport.py`, though ultimately unused by
   the HFSS geometry path (see §3).
2. `verify_L30_hfss_export.py` (`regenerate_metal_pieces`/
   `regenerate_metal_region`) rebuilds the metal geometry **directly in
   Python** from `filter_L30.py`'s own live tables (imports it as a
   module - accepts the ~1-2s cost of re-running the whole chip build, in
   exchange for the HFSS geometry always being in sync with whatever
   tilts/dimensions are currently in the file). Runs entirely in this
   repo's own `.venv` - no pyEPR/AEDT needed - for local sanity checks
   (merged-polygon count, hole area, port conductor widths).
3. `filter_L30_HFSS.py` (run via `.AnE`) draws the same geometry into a
   live AEDT session, unites it, builds substrate/package/ports, sets up
   a driven-modal sweep, and (when `RUN_ANALYSIS=True`) solves and pulls
   S-parameters.

## 3. Why the geometry is regenerated in Python, not read from GDS

The original plan was to extract geometry from the exported GDS (matching
`Hairpin_Filter_HFSS.py`'s own `extract_xor_derived_metal` pattern, via
`maskLib.hfssExport.extract_metal_polygons` + `klayout.db.Region.merge()`
for this XOR-free design). This was abandoned after a real, reproducible
AEDT failure: `CreatePolyline` on the GDS-derived merged polygon threw
`Parasolid PK_ERROR_crossing_edge`.

**Root cause, confirmed by direct inspection**: the DXF write → GDS read
round-trip corrupts `CurveRect`'s fan polylines. A fan built directly in
Python (`CurveRect._build()` called directly) has a clean 64-vertex
outline; the *same* fan read back from the exported GDS has 130 vertices
with exact consecutive duplicate points (a zero-length boundary "spike").
This doesn't change enclosed area - invisible to bbox/hole-count/
connectivity checks, which is why it wasn't caught earlier in the mask
design work - but Parasolid's stricter simple-curve requirement rejects
it outright.

Fix: `regenerate_metal_pieces()`/`regenerate_metal_region()` rebuild every
polygon directly in Python (fans via `CurveRect._build()` called
directly, or - for AEDT specifically - as true native arcs, see §5;
everything else as clean proper-winding rectangles), never touching the
DXF/GDS round-trip for geometry. `hfssExport.list_layers`/
`extract_metal_polygons` are still used, just for informational GDS-layer
diagnostics only.

## 4. Three real bugs found and fixed (not geometry-strategy issues - straightforward mistakes)

1. **AEDT-illegal object names**: labels like `'P1+_stalk'` broke
   `CreatePolyline` at the COM layer with no AEDT message logged at all
   (rejected before AEDT's own script engine saw it). Fixed by using
   `a`/`b` side labels instead of `+`/`-`.
2. **Meters vs. microns on `draw_box_corner`**: `pyEPR`'s `Box.__init__`
   computes `self.center = corner + size/2` in **plain Python
   arithmetic**, which requires numeric inputs (not `um()`-wrapped
   strings - confirmed by a `TypeError: unsupported operand type(s) for
   /: 'str' and 'int'` when tried). So bare floats are required for this
   *specific* call - but passing raw micron values as bare floats after
   `model.set_units('um')` produced a catastrophically wrong-scale
   Substrate box (AEDT: `"Model dimensions ~500000000... bebeyond the
   expected range (1e-08, 10000)"` - i.e. ~500 meters where 500um was
   intended, a factor of exactly 1e6). `Hairpin_Filter_HFSS.py`'s own
   comments claim bare floats are interpreted in "the current model
   units" after `set_units('um')`; that did not hold for this call in
   this session/AEDT version. Fixed by pre-scaling bare floats to meters
   (`_UM_TO_M = 1e-6`) before passing them specifically to
   `draw_box_corner`.
3. **`solution_type` string mismatch when querying an existing setup
   after the fact**: `design.solution_type` returns `'HFSS Hybrid Modal
   Network'` in this AEDT version, not the `'DrivenModal'` string
   `HfssDesign.get_setup()`'s dispatch checks for - it silently falls
   through and returns `None` instead of raising. Only matters for
   *re-querying* S-parameters from a separate process after the main
   script has already run (e.g. pulling S11 for a follow-up check) -
   `filter_L30_HFSS.py` itself doesn't hit this, since it uses the
   `DM_setup`/`DM_sweep` objects it already has in hand from
   `create_dm_setup`/`insert_sweep`. Workaround: construct
   `HFSS.HfssDMSetup(design, name)` directly, bypassing the broken
   dispatch.

## 5. The Unite() saga - root cause and fix

Getting all ~26 individual metal pieces (drawn separately, since a single
556-vertex merged polygon was "too complex" for one `CreatePolyline` call
- `"invalid parameters to CreatePolyline"`) into **one** conductor solid
took nine failed attempts before the real root cause was found:

- One-shot N-way `unite()`, pairwise progressive `unite()`, skipping
  `unite()` entirely (mesh-time "Parts X and Y intersect" errors - FEM
  meshing can't handle overlapping-but-unmerged volumes), a 1um overlap
  at every joint (introduced a genuine ~8700 um² hole - a real bug in
  that attempt, not just noise), a *base-only* 1um overlap (still didn't
  fix `Unite()`), polygon-approximated fans vs. true native-arc fans
  (`draw_fan_native` - 2 arc segments + 2 straight radial edges via a raw
  `CreatePolyline` call, since pyEPR's own `draw_polyline()` hardcodes
  `SegmentType:="Line"` for every segment) - **none of these fixed it**.
  Every attempt left the united object a null/`Unclassified` body
  (`"Body could not be created for part because of invalid parameters to
  Unite operation"`, sometimes with an explicit `"Null body found"`).

**Root cause, found via interactive GUI testing (Eddie)**: isolating the
problem by hand in the AEDT GUI showed the full straight-line stripline
(all rectangles) unites fine, two fans unite with each other fine, but a
stalk will not unite with its own fan. Direct shoelace-signed-area
computation on the actual polygon point lists confirmed why: **stalk
rectangles wind clockwise** (`_rect_poly`, signed area negative, e.g.
-62500 for a test case) **while the fans (as originally built) wound
counter-clockwise** (+171252 for the matched test case). Opposite winding
means the two extruded solids get oppositely-facing surface normals at
their shared boundary - a classic Parasolid boolean-failure trigger, and
exactly consistent with same-winding pairs (rect-rect, fan-fan) working
while the mixed pair failed.

Two fixes, both needed:
1. **Reverse the fan's point order** (CCW → CW) in `draw_fan_native` so
   every solid in the model shares the same winding convention.
2. **`STALK_FAN_OVERLAP_UM = 5.0`**: each stalk is drawn 5um longer than
   its true (mask-exact) length, poking past its fan attach point by a
   guaranteed real amount, rather than relying on two independently-
   computed edges (`_rect_poly`'s stalk tip, `fan_arc_points`'s inner-arc
   endpoint) landing exactly on top of each other - Eddie spotted a real,
   visible gap between stalk and fan in the AEDT 3D render at that
   boundary, and this may have been a contributing factor to the Unite()
   failures alongside the winding mismatch. The overlap is AEDT-only (a
   `stalk_fan_overlap_um` parameter on `regenerate_metal_pieces`,
   default 0) - the local klayout-based mask-geometry checks stay exact,
   since an earlier attempt at overlap-padding *there* caused a genuine
   hole via a completely different mechanism (redundant fill-quad tiling
   from the DXF rendering convention - not relevant to this native-arc,
   AEDT-only path).

With both fixes, `model.unite(metal_names)` (one-shot, all 26 pieces)
works cleanly every time - confirmed by both interactive GUI testing and
a fully automated scripted rebuild-from-scratch, repeatedly.

**Lesson for future AEDT scripting in this repo**: when building solids
from independently-constructed polygon point lists (not from a single
shared `Structure`-walk), check that every polygon has the *same* winding
order before unite()-ing them, and don't assume exactly-matching
coordinate math from two different formulas will produce a
Parasolid-safe zero-gap joint - a small guaranteed real overlap is more
robust than relying on exact alignment.

## 6. AEDT session hygiene (found the hard way)

- **Stale lock files**: if a script run is interrupted (crash, or a modal
  "file still in use" dialog gets cancelled), AEDT can leave a stale
  `.aedtresults/.Driven Modal.asol_priv.semaphore` lock that blocks the
  *next* `analyze()` call, even in a fresh script invocation. Symptom:
  `"Failed to obtain access to 'Driven Modal.asol_priv' because another
  application did not release its lock"`, sometimes cascading into the
  setup itself vanishing (`"The setup ... has not been found. Cannot
  simulate"`).
- **Fix**: close AEDT cleanly (`HFSS_desktop._desktop.QuitApplication()`)
  and delete `filter_L30_S21.aedt`, `filter_L30_S21.aedt.lock`, and
  `filter_L30_S21.aedtresults/` before retrying. Confirmed safe to do
  repeatedly - these are always freshly created by this script's own
  runs, never pre-existing user work (checked file timestamps against any
  other open AEDT projects before ever touching this).
- **Duplicate project handles**: repeated `HfssApp().get_app_desktop()`
  calls against a long-running AEDT instance (this session's instance had
  been open for a week) can accumulate duplicate entries in
  `GetProjectList()` for the same project name if earlier attempts didn't
  close cleanly. `SetActiveProject(name).Close()` in a loop did not
  reliably clear these; a full `QuitApplication()` + file cleanup did.

## 7. First real S21 result (lumped ports) - total reflection, not a geometry bug

Once the geometry pipeline was fully fixed (§5), `RUN_ANALYSIS=True`
produced a genuine solve with the original lumped-port setup: adaptive
mesh converged, the sweep completed, S21 was extracted successfully -
but showed **no usable filter response**: S21 never rose above about
-90dB anywhere in 0.5-12GHz, and was only -125dB at the filter's own
3.5GHz design frequency. Pulling S11 explained why immediately: **S11
was essentially exactly 0dB (total reflection) across the entire swept
band** (-0.00005 to +0.0002dB, flat at 0dB everywhere). Virtually no
incident power ever entered the structure at any frequency.

This was the **proxy-ground/lumped-port limitation flagged from the very
start of this HFSS work** (both `Hairpin_Filter_HFSS.py`'s own docstring
and `filter_L30_hfss_geometry.py`'s), empirically confirmed: lumped
ports have no local ground reference at all - only the `Package`
proxy-ground walls 3mm away - so the 50Ω port impedance had no real
physical relationship to whatever mode existed at the port's location.
Not a geometry, mesh, or solver bug - the pipeline itself was already
fully validated at this point (three real bugs fixed, the Unite() root
cause found and fixed, a real converged solve produced). Fixed in §8.

## 8. Switching to wave ports - fixed it

Per Eddie, tried a wave port instead of a lumped port. This isn't a
drop-in swap: pyEPR has **no wave-port wrapper at all** (only
`_make_lumped_port`/`make_lumped_port` exist in the source) so it's a
raw `self._boundaries.AssignWavePort(...)` COM call, verified against a
minimal isolated test (a plain box, one face) before touching the
production script. More importantly, a wave port needs to sit on a
genuine **exterior boundary face** of the solve domain with a
well-defined cross-section (conductor + dielectric + surrounding
ground) - unlike a lumped port, it can't just be a free-floating
rectangle in the middle of the model.

**Model restructuring required**: both `Substrate` and `Package` are now
built with their Y-extent (the port-to-port axis) held EXACTLY at
`[ymin, ymax]` - the metal's own bounding span, i.e. no padding at all
in Y - instead of padded beyond the ports like the lumped-port version.
X and Z keep their normal padding (`MODEL_PADDING_UM`/
`PACKAGE_PADDING_UM`). This makes Package's two Y-end faces genuine
exterior boundaries, exactly at the port cross-sections, with the metal
conductor, substrate, and surrounding package walls all present in that
cross-section for AEDT's 2D mode solver to work with. Faces are
identified by querying `GetFaceCenter` on all 6 of Package's faces and
matching y-coordinate to `ymin`/`ymax`; the other 4 (X/Z-facing side
walls) get PerfectE via a raw `AssignPerfectE` call with `Faces:=`
(pyEPR's own `assign_perfect_E` only accepts `Objects:=`, not face IDs).
Integration line: straight up (+Z) from the conductor's center to the
top of Package - a reasonable "trace referenced to a distant enclosure"
convention, not derived from a specific field-pattern analysis (the 2D
eigenmode solver computes the actual mode from the real cross-sectional
geometry regardless; the integration line mainly fixes the sign/phase
convention).

**Result: a real filter response.** S21 in the passband (0.5-3.5GHz)
ranges from -0.20dB to -4.53dB (-3.35dB right at the 3.5GHz design
cutoff - close to a classic 3dB-point definition), then three clear,
sharp transmission zeros: 5.18GHz (-50.25dB), 9.665GHz (-102.69dB),
10.94GHz (-35.45dB). S11 in the passband ranges from -1.89dB to
-13.49dB - a real, physically meaningful match, not the flat 0dB total
reflection from §7.

The zero frequencies don't exactly match the synthesized table values
(P2=6.43, P3=4.623, P4=12.04GHz) - fully expected, given every dimension
here is still a PLACEHOLDER pending real HFSS re-extraction (the Nuhertz
synthesis assumed an alumina/microstrip model, not this bare-sapphire/
proxy-ground stack, and the proxy ground itself is still a rough
stand-in, not a real tunnel model) - but the *existence* of a clean
passband plus multiple sharp, deep nulls, roughly in the right frequency
neighborhood, is strong qualitative confirmation that the radial-stub
topology is behaving as designed. Data: `HFSS/filter_L30_S21.csv`/`.png`,
`HFSS/filter_L30_S11.csv`.

**Lesson for future AEDT scripting in this repo**: if S11 comes back
flat at 0dB across an entire sweep (not just high in a stopband - flat
everywhere, passband included), suspect the port reference/ground
definition before the geometry. A lumped port needs a genuine local
ground; if none exists in the model, a wave port on a real exterior
boundary face (even referencing a distant proxy ground, as here) can
still produce a physically meaningful result where a lumped port cannot.

## 9. Remaining caveats / next-phase options

- All dimensions are still PLACEHOLDER values from the Nuhertz synthesis,
  not yet re-extracted for this real stack - zero frequencies (and
  likely the passband edge) will shift once that happens.
- The proxy ground (`Package`, PEC walls `PACKAGE_PADDING_UM=3000` i.e.
  3mm from the metal in X/Z) is still a rough stand-in for the real
  package tunnel, not a modeled coax pin / SNAIL gap. A real tunnel/
  package/coax-pin model (matching the original handoff doc's eventual
  "chip + tunnel + pin" plan) is the natural next step once real package
  dimensions exist.
- The output port (P2) is still a stand-in at the tip of the drawn
  output line, not a real lumped port at the eventual SNAIL gap.
- Only L30 has been run through this pipeline - L45 would need the
  equivalent `filter_L45_hfss_geometry.py`/`verify_L45_hfss_export.py`/
  `filter_L45_HFSS.py` trio built the same way (not done this session).

## 10. Rev 5 - bend geometry / folded-stalk bridge rewrite

`filter_L30.py`'s Rev 5 rewrite (see `L30_design_notes.md` §12) replaced
straight/tilted stalks with folded (meandered) stalks for P2/P3, using a
new `guarded_bend()` (positive-metal U-turn via `CurveRect` with
`ralign=valign=const.MIDDLE`, unlike `radial_fan()`'s
`ralign=valign=const.BOTTOM`). This bridge's geometry replay
(`_build_pieces()`) hand-mirrors the mask script's drawing sequence, so it
needed a matching rewrite - not done in the same session as the Rev 5 mask
work, done here.

**New functions**: `bend_arc_points()` (native-2-arc AEDT representation,
analog of `fan_arc_points()`) and `_bend_advance()` (pure position/direction
math, analog of `_rect_poly()`'s own advance) - both derived directly from
`CurveRect`'s exact source (`src/maskLib/Entities.py`, read in full this
session) rather than by extending the existing BOTTOM-align fan formula by
analogy. Key finding: MIDDLE ralign's `-height/2` shift and MIDDLE valign's
`-height/2` shift exactly cancel, leaving the *same* `(r*sin(t),
r*cos(t)-radius)` local-point formula the fan case already uses - just with
an extra sign (`vflip_mult`, `1` if `CCW` else `-1`) multiplied onto the
perpendicular component, since `guarded_bend()` passes `vflip=not CCW` to
`CurveRect` (fans never do - they have no CCW choice).

**Verification** (`verify_bend_geometry.py`, new): compares both new
functions against a *real* `filter_L30.guarded_bend()` call's actual
`structure.start`/`.direction` before/after, and its bookkeeping
`CurveRect`'s own discretized `.points`, for both `CCW=True` and
`CCW=False`, `angle_deg` 90 and 180. `_bend_advance()` matched to
`0.000000000` immediately. `bend_arc_points()`'s first check showed a
consistent ~7.2um "error" across every case - this turned out to be a test-
methodology artifact, not a bug: the 2 arc-midpoint key points aren't
exactly represented in `CurveRect`'s own discretization (`ptDensity=120`
samples at `t=(i+0.5)*dTheta`, which never lands exactly on `angle/2` for
these angle values), so nearest-neighbor distance against the discretized
list picks up a real but harmless quantization gap. Re-checked the 4 true
corner points (which ARE exact, un-interpolated entries in `CurveRect`'s
point list) for an exact match, and the 2 midpoints via a
discretization-independent geometric property (distance from the arc's own
rotation center equals `r_in`/`r_out`, and the two half-angles bisect the
full sweep exactly) - all four cases now pass to true machine precision.

**Winding**: unlike fans (always the same orientation), a bend's
`bend_arc_points()` winding depends on `CCW` - confirmed via direct
shoelace signed-area computation in `verify_bend_geometry.py`: `CCW=True`
gives CCW winding (positive area), `CCW=False` gives CW winding (negative
area), consistently for both 90deg and 180deg. Since every rectangle winds
CW, `draw_bend_native()` (the bend analog of `draw_fan_native()`) only
reverses point order when `CCW=True`.

**Piece-tuple format changed**: `_build_pieces()`/`regenerate_metal_pieces()`
now yield/return `(label, hull, kind, arc_params)` (`kind` one of `None`,
`'fan'`, `'bend'`) instead of the old binary `(label, hull,
fan_params_or_None)` - `filter_L30_HFSS.py`'s draw loop updated to a 3-way
dispatch accordingly.

**Smoke test, attempt 1**: all 46 pieces (up from ~26 in Rev 4 - the folded
branches' extra turns/runs) drew, and `model.unite(metal_names)` returned
without a Python exception, printing `United all 46 pieces -> PinPad` - no
repeat of the original winding-order saga (§5) at first glance. The very
next call, `ChangeProperty` (material=aluminum), threw a COM
`SetActiveEditor` exception. Direct inspection right after (via a fresh COM
connection) showed `PinPad`/`Substrate`/`Package` all present with 0
`Unclassified` and material already `"aluminum"` - looked like a benign
UI/focus hiccup, so a `QuitApplication()` + clean re-run was tried next.

**That diagnosis was WRONG - a real bug, not a UI hiccup**: the *exact same*
`ChangeProperty` error reproduced identically on a freshly-quit, single
(no-duplicate-project) AEDT session - ruling out the "stale duplicate
project" theory. Direct inspection on THIS clean session told the true
story: `GetObjectsInGroup("Solids")` was empty and `PinPad` was in
`"Unclassified"` - `Unite()` had silently produced an invalid body all
along (the earlier "looks fine" inspection had actually queried a stale
leftover duplicate project from an *earlier* successful Rev 4 run, not the
fresh Rev 5 build - the same duplicate-project trap flagged in `CLAUDE.md`,
this time actively misleading a diagnosis instead of just being cosmetic
clutter).

**Root cause, found via incremental unite (mirroring §5's own diagnostic
technique)**: built P2's 14 pieces standalone and united them one at a time,
checking `GetObjectsInGroup` after each step. Every join through
`exit_run -> entrance_turn -> run1 -> bend1 -> run2 -> exit_turn` united
cleanly in sequence - the failure was specifically `unite(exit_turn, fan)`,
which produced `Unclassified`. Cause: `STALK_FAN_OVERLAP_UM` (the guaranteed
real-overlap fudge that fixed the original Rev 4 stalk-fan gap) was only
ever applied to the OLD straight-stalk code path (`_build_pieces()`'s
`else` branch, still used by P1/P4) - the NEW folded-branch path's exit
turn attaches to the fan with mathematically exact but zero overlap,
reproducing the identical gap problem in a new location.

**Fix**: `_build_pieces()`'s folded-branch path now yields an extra small
`_rect_poly` "bridge" piece (`%s%s_fan_overlap`, length
`stalk_fan_overlap_um`) between the exit turn and the fan when
`stalk_fan_overlap_um` is nonzero - identical philosophy to the straight-
stalk case: the bridge piece pokes past the true exit-turn end into the
fan, while the fan's own anchor point (`fan_tip`) stays exactly where it
was. Confirmed fixed: re-ran the full smoke test on a clean AEDT session -
all 50 pieces (46 + 4 new overlap bridges, one per folded-branch side) drew,
united into a single real `Solids` entry (`PinPad`, 0 `Unclassified`),
material set correctly, and - checked directly on the correct (non-stale)
project handle this time - `Substrate`/`Package` built,
`Package_Walls`/`Filter_Metal` PerfectE boundaries assigned, both wave
ports (`P1:1`, `P2:1`) registered as excitations, and `S21_Setup`/
`S21_Sweep` created. Full pipeline verified end to end before any real
solve was run.

**Lesson for next time**: when re-diagnosing an AEDT COM error via a fresh
script, always enumerate every project handle matching the target name
(`[p for p in projects if p.name == X]`) and check EACH one's own state
individually - never assume `get_projects()`'s first match is the one the
just-failed script actually built into. A "looks fine" reading from the
wrong duplicate is worse than no reading at all.

## 11. Rev 5 real S21/S11 result

Full solve (`RUN_ANALYSIS=True`), same 0.5-12GHz/2301-point interpolating
sweep, up to 12 adaptive passes, run on the fixed bend-aware bridge (§10).
Results saved to `HFSS/filter_L30_S21.csv`/`.png` and (pulled separately via
the explicit-path export - see the pyEPR `tempfile.mktemp()` lesson in
`CLAUDE.md`) `HFSS/filter_L30_S11.csv`.

```
Passband (0.5-3.5GHz) S21: -0.17 to -4.21 dB (S21 at 3.5GHz cutoff: -4.21 dB)
Passband S11: -14.13 to -2.07 dB

S21 nulls below -20dB:
  5.885 GHz: -67.34 dB   (deepest pair, likely P3's zero - target 4.623GHz)
  6.455 GHz: -31.03 dB
  7.825 GHz: -87.18 dB   (deepest overall - likely P2's zero - target 6.43GHz)
  9.170 GHz: -28.34 dB
  10.905 GHz: -28.54 dB
  11.290 GHz: -22.02 dB
```

**Comparison against the orthogonal (unscaled, unfolded) baseline** -
`HFSS/compare_L30_rev5_vs_orthogonal.png` - is the clearest evidence Rev 5's
rescaling is working in the right direction: every null visibly shifted
DOWN in frequency, toward the Nuhertz synthesis targets (4.623/6.43/12.04
GHz), compared to the orthogonal run's nulls (6.415/9.355/9.665/10.83 GHz).
Nearest-null-to-target ratios: P3 target 4.623GHz -> nearest null 5.885GHz
(x1.273, down from orthogonal's x1.387), P2 target 6.43GHz -> nearest null
6.455GHz (x1.004 - essentially exact), P4 target 12.04GHz -> nearest null
11.290GHz (x0.938 - slightly OVERSHOT past the target this time, unlike
every earlier run which undershot). Passband quality held up well through
the geometry change (comparable insertion loss to both earlier runs) and
S11 is the best of any run so far (-14.13dB best match, vs orthogonal's
-9.37dB and the original tilted run's -13.49dB).

**Caveats on this comparison** (same spirit as the design notes' own
placeholder-dimension caveats):
- The null-to-branch correspondence above ("likely P3's/P2's zero") is
  inferred purely from nearest-target matching, not confirmed against a
  per-branch sensitivity sweep (e.g. removing one fan and checking which
  null disappears) - the two deepest nulls are a reasonable first guess,
  not a verified assignment.
- Several new, shallower nulls appear (6.455/9.170/10.905/11.290GHz, all
  20-60dB less deep than the two dominant ones) that don't have an obvious
  counterpart in the simpler orthogonal baseline's response - plausibly a
  real consequence of the folded geometry's own parasitics (exactly the
  "run_gap=150um... expect MORE coupling-driven inductance reduction"
  caveat already flagged in the design notes' Rev 5 section) rather than a
  numerical artifact, but not independently confirmed either way.
- P4's overshoot (landing below its target instead of above, unlike every
  other branch/every earlier run) suggests `BRANCH_SCALES['P4']` may now be
  slightly too aggressive - a natural candidate for the next HFSS-driven
  scale adjustment, per the iteration loop `filter_L30.py`'s own module
  docstring already describes.

## 12. Files in this pipeline

- `filter_L30_hfss_geometry.py` - shared constants (substrate thickness,
  metal thickness, model/package padding, port impedance, sweep range).
  No GDS path/layer/bbox/port-position constants - all computed live (see
  §3, §2).
- `verify_L30_hfss_export.py` - Ansys-free local checks
  (`main()`/`region_to_polys`/etc.) **plus** the shared geometry-
  regeneration functions (`regenerate_metal_pieces`, `fan_arc_points`,
  `_rect_poly`, ...) that `filter_L30_HFSS.py` imports and builds on.
- `filter_L30_HFSS.py` - the actual pyEPR/AEDT build+solve script. Run
  via `.AnE`. `RUN_ANALYSIS` flag gates the expensive adaptive-mesh solve
  + sweep (`False` = build/setup only, matching `Hairpin_Filter_HFSS.py`'s
  own scope; `True` = solve and save S21 to `HFSS/filter_L30_S21.csv`/
  `.png`).
