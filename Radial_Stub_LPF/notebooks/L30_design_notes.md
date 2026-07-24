# L30 radial-stub lowpass filter — design notes

Companion to [`filter_L30.py`](../filter_L30.py). This records *why* the
mask geometry looks the way it does, not just what it looks like — see
[`L45_design_notes.md`](L45_design_notes.md) for the 12th-order sibling
(same methodology, different synthesized numbers; the two files are kept
separate rather than sharing a "methodology" doc, to match the `.py` files'
own "two self-contained files, no shared module yet" convention this
session).

## 1. Provenance

All dimensions below are transcribed **verbatim** from a Nuhertz Filter
Solutions synthesis: 8th order Chebyshev-II distributed lowpass, fc=3.500
GHz, stopband from 3.999 GHz (ratio 1.142), 30 dB equiripple floor,
microstrip/alumina model (εr=9.80, h=500um, t=300nm, main line Zo=84.29Ω /
125um). Zero-crossing frequencies are carried through the code as comments
only — they document *why* each branch exists, they are not used in the
geometry.

Nuhertz source/netlist files have not been provided directly; the tables
here were transcribed from screenshots of the synthesis output. This is
**item V1/V2 below** — flagged, not yet independently verified.

## 2. Topology

A main transmission line (constant 125um width / 84.29Ω throughout — no
impedance step between series sections in this design) with four shunt
branch pairs hanging off it at the section boundaries. Each branch pair is
a **butterfly**: two mirror-image branches (one to either side of the main
line) at the same junction point, each branch being a narrow series stalk
(the branch inductor) feeding a 90° radial fan (the branch capacitor). The
stalk+fan's own series-LC resonance produces the transmission zero — the
fans are electrically small compared to a quarter-wave resonator at their
zero frequency, they are not resonant cavities in their own right.

Branch/section ordering: P1 sits before S1 (closest to the input), P2
between S1/S2, P3 between S2/S3, P4 between S3/S4 (closest to the output).

## 3. Positive-metal-draw convention (why this differs from the rest of the repo)

This chip has **no ground plane at all** — the design is bare c-plane
sapphire with a single 120nm Al layer, and the ground reference is the
package's tunnel walls, not anything drawn on-chip. That means there's no
CPW gap to draw, so this filter does **not** use the CPW/XOR-gap convention
documented in the top-level `CLAUDE.md` ("CPW gap geometry uses an XOR
layer strategy...") and used by `Hairpin_Filter.py`/`SNAIL_Pump_Filter.py`
elsewhere in this repo. Every polygon drawn here (main line, stalks, fans,
pad, taper) *is* the aluminum, directly.

The real precedent for this pattern in the repo is `SNAIL/SNAIL.py` +
`FlagPads`/`JJ_chain` (`src/maskLib/junctionLib.py`,
`src/maskLib/fluxoniumLib.py`) and `qubitLib.SNAIL()` — those draw positive
metal directly for the same no-ground-plane reason, and explicitly skip the
XOR/`fill_basemetal_from_xor` post-processing step. This filter does the
same: no `w.setupXORlayer()`, no XOR layer, no BASEMETAL-fill step.

The primitives used are `Strip_straight`/`Strip_taper`
(`src/maskLib/microwaveLib.py:198,273`) for the main line, stalks, pad, and
tapers — these already draw plain filled rectangles/trapezoids (via
`dxf.rectangle`/`SkewRect` with `bgcolor` set) despite their misleading
"note: uses CPW conventions" comment; read the function bodies directly,
not the comment. `CurveRect` (`src/maskLib/Entities.py:182-303`) draws the
radial fans — see §4.

## 4. Radial fan geometry derivation

No radial-fan-specific primitive existed in this repo before this session
(confirmed by search). But `CurveRect` already draws a filled **annular
sector** whenever its computed `rmin > 0` (the `_build_solid_quad` branch in
`_build()`) — every fan here has `r_in` in the 88-177um range, well above
the degenerate-pie-wedge threshold, so this is exactly the primitive we
need with no modification.

With `ralign=const.BOTTOM, roffset=0`: `rmin = radius`, `rmax = radius +
height`. Setting `radius = r_in`, `height = r_out - r_in` gives the correct
radial extent directly.

The nontrivial part is `insert`/`rotation`. **`CurveRect`'s `insert` point
is not the fan's geometric center** — tracing `_calc_points`/
`_transform_points`, the first polygon vertex (local angle 0, r=rmin) lands
*exactly at* `insert` after the rotate+translate transform. Requiring the
fan's angular bisector to point along the stalk's outward direction `S`,
and requiring the fan's two inner-arc endpoints to exactly coincide with
the stalk's own tip-edge corners (so stalk and fan meet with literally zero
gap and zero overlap), solves to:

```
rotation = S + fan_angle/2 - 90
insert   = tip + (attach_width/2) * (cos(S+90), sin(S+90))
```

i.e. `insert` is **one corner of the stalk's tip edge**, not its centerline
point. This was re-derived by hand from `CurveRect._calc_points` (not just
read off), and independently confirmed by actually building the DXF and
checking that all 288 BASEMETAL shapes in the rendered `filter_L30.dxf`
merge into a **single connected polygon** (`klayout.db.Region.merge()` →
count 1) — i.e. every stalk/fan/main-line joint is genuinely seamless in
the real output, not just on paper.

This seamless-joint property only holds when
`attach_width == 2 * r_in * sin(fan_angle/2)`. Checked against every row in
the table: `2*88.39*sin(45°) = 125.00` (table: 125), `2*176.8*sin(45°) =
250.03` (table: 250) — holds to the tables' own rounding. `radial_fan()`
asserts this at draw time (tolerance 0.5um) so a future edit that breaks
the relationship fails loudly instead of silently drawing a gapped joint.

### `attach_width` vs `stalk_width`

Numerically identical in every row of this table, but **not** the same
concept: `stalk_width` is the stalk rectangle's cross-section;
`attach_width` is the fan's inner-arc chord length. They only coincide
because Nuhertz (or the transcription) chose `r_in` specifically so the
stalk's flat tip edge is an exact chord of the fan's inner arc. Both fields
are kept in the table (traceability + a runtime consistency assert in
`branch_pair()`), even though today one could be derived from the other.

## 5. Tilt / butterfly geometry

Per-branch direction is set via `m.Structure.cloneAlong(vector=(0,0),
newDirection=sign*(90+TILT_DEG))` off the main line's *current* structure
— `cloneAlong` adds `newDirection` to the *current* direction rather than
setting an absolute one, so with the main line running at `direction=-90`
(straight down the chip, input at high y / output at low y), the two
branch directions come out to `-90 + (90+55) = 55°` and
`-90 - (90+55) = -235° ≡ 125°` — both of which lean toward +y, i.e. **back
toward the input**, matching the handoff doc's "sweep back toward the
input" width-reduction strategy. `TILT_DEG = 55` is a fixed top-of-file
constant (not derived in this file) chosen per the handoff doc's own
tilt-vs-width table (0°→9.01mm, 50°→5.80mm, 55°→5.17mm, 60°→4.51mm
*as-synthesized*; realized numbers here differ because they include the
fan's actual footprint, not just the as-synthesized envelope — see §8).

`cloneAlong` does not mutate the main line's own `Structure`, so both
branches of a pair, and the continuing main line, all originate from the
same unperturbed junction point.

## 6. T-junction strategy

There is no generic positive-metal T-junction primitive in this repo
(`CPW_tee` is XOR/gap-based and doesn't apply here). The approach taken:
the main line is drawn as one continuous, unbroken `Strip_straight` chain;
each branch stalk starts at the exact same centerline point and extends
outward, so its near half necessarily overlaps the already-drawn main-line
rectangle. Separately-drawn overlapping filled polygons fuse visually with
no boolean operation needed — the same composition pattern `FlagPads`/
`JJ_chain` already use elsewhere in this repo for positive metal. Confirmed
empirically (see §4) that the full drawn geometry merges into one connected
region.

One consequence: P1's stalk (250um) is wider than the main line at that
point (125um) — expected/normal (P1's Zo=66.55Ω differs from the main
line's 84.29Ω by synthesis), the wider stalk simply overlaps more of the
main line polygon near that junction. No special-casing needed.

## 7. Bounding-box / clearance methodology

**Overall transverse width**: every drawn element's global vertices are
accumulated into one list as the chip is built; `max(x) - min(x)` at the
end. For the fans specifically, the *actual* rendered polygon vertices are
used (`CurveRect._build()` is called once right after `chip.add()` — a pure
function of the constructor args, confirmed idempotent, so calling it early
for bookkeeping doesn't affect the later real DXF serialization), not a
hand-approximated envelope.

**Per-pair nearest-neighbor clearance**: vertex-to-vertex nearest distance
between consecutive branch pairs' combined vertex sets. This is a
deliberate approximation — true polygon-polygon minimum separation can
occur mid-edge, not just at a vertex, so it can *undercount* the real
clearance in some geometries. A 1-D "project onto the main-line axis"
check was considered and rejected: because branches tilt 145° from the
forward direction, a later pair's y-extent can fully engulf an earlier
pair's y-extent while the two are actually far apart in x — that check
would false-positive constantly here. Any reported clearance under ~500um
is flagged (`<< CHECK`) for visual confirmation in KLayout rather than
trusted blindly.

## 8. Results (as-built, from the actual rendered `filter_L30.dxf`)

Usable chip: 6800 x 39800um (7000x40000 minus 200um saw width), main line
centered at x=3400 (chip-local) / x=3400 (BASEMETAL-layer origin as saved).

| Pair | Realized transverse width | Notes |
|---|---|---|
| P1 | 1234.1 um | |
| P2 | 4431.2 um | |
| P3 | **6117.1 um** | tightest pair — 383um under the 6500um budget |
| P4 | 2555.1 um | |

**Overall realized transverse bounding box: 6117.1 um** (budget 6500um,
383um margin) — confirmed both by the script's own printed report and by
directly measuring the rendered DXF's BASEMETAL layer bbox in KLayout
(6117.053um, matching to floating-point noise).

Per-pair nearest-neighbor clearance: P1↔P2 **467.5um** (flagged, under
500um — visually confirm in KLayout before fab), P2↔P3 1606.5um, P3↔P4
1744.5um.

DXF validation performed this session (via `klayout.db`, not just eyeballing):
- 288 BASEMETAL shapes, **0 degenerate (<3-vertex) polygons** (DWL 66+
  requirement, `CLAUDE.md`).
- All 288 shapes merge into **exactly 1 connected polygon** — every
  stalk/fan/main-line/taper/pad joint is genuinely seamless, not just
  visually close.

## 9. Open verification items (carried from the handoff doc)

- **V1**: branch-pair interpretation (butterfly up/down at one junction,
  vs. two separate junctions) is assumed correct per the handoff doc but
  not yet cross-checked against the original Nuhertz 3D layout view.
- **V2**: P1's stalk Zo (66.55Ω / 250um wide, differing from all other
  branches) is read from the transcription as given; not independently
  re-derived.
- **V3**: first real DXF now exists and has been checked programmatically
  (connectivity, degenerate-geometry) — a KLayout XOR/visual pass by a
  human, and converter acceptance on real hardware, are still open.

## 10. HFSS-pending caveats

Every electrical dimension in `filter_L30.py` is a **PLACEHOLDER** pending
HFSS re-extraction in the real (bare-sapphire, tunnel-grounded, no ground
plane) environment — same caveat already carried by
`Hairpin_Filter.py`/`SNAIL_Pump_Filter.py`'s own docstrings for their
filters. The Nuhertz synthesis assumed an alumina microstrip model (εr=9.80,
h=500um, with an implicit ground plane) that does not match this chip's
actual bare-sapphire/tunnel-ground stack — expect stalk lengths and fan
radii to shift once re-extracted (handoff doc estimates +10-40% growth is
plausible; at +30% growth, L45 at 55° tilt would exceed budget and need 60°
+ possibly the reserve L-bend stalk option — not needed for L30 at the
current numbers, but worth tracking if growth applies here too).

## 11. Known risks carried into implementation

1. **P3 is the tightest pair** (6117.1um vs 6500um budget, 383um margin) —
   any future dimension change should re-check this first.
2. **P1↔P2 clearance (467.5um) is under the 500um visual-check threshold**
   — confirm in KLayout before committing to fab.
3. Pin pad placement ("5mm from the chip edge") and SNAIL keep-out
   orientation (3mm transverse x 5mm axial, per `SNAIL_Pump_Filter.py`'s
   precedent — the handoff doc's own "5 x 3mm" prose is ambiguous on which
   axis is which) are both provisional assumptions, not directly specified.
   Neither affects real filter geometry (pad position is a simple offset;
   keep-out is a dummy marker), but both should be confirmed against the
   actual package drawing once it exists.
4. S4 (138.3um) is the shortest main-line segment in this filter — well
   above the DWL degenerate-length threshold, and since branch tilt always
   leans backward (toward input), no branch geometry can reach forward into
   it; still worth a first-render glance (done this session, looks fine).

## 12. Rev 5 — HFSS-driven rescale + folded stalks

### 12.1 Motivation

First real HFSS wave-port S21 result (this session, run on
`filter_L30_orthogonal.py`'s untilted geometry specifically — chosen because
it isolates the pure no-ground-plane physics from tilt's own separate
fan-to-line coupling shift, see `L30_HFSS_notes.md`) showed the whole
response landing ~1.4x high in frequency vs. the Nuhertz synthesis targets:

| Branch pair | Designed zero | Realized zero | Shift | Required LC growth (=shift²) |
|---|---|---|---|---|
| P3 (stalk 3.271mm, fan 1.237mm) | 4.623 GHz | ~6.40 GHz | x1.384 | x1.92 |
| P2 (stalk 1.980mm, fan 1.133mm) | 6.43 GHz | ~9.35 GHz | x1.454 | x2.11 |
| P4 (stalk 585.4um, fan 992.7um) | 12.04 GHz | ~17 GHz (est., off sweep) | ~x1.45 | ~x2.1 |
| Cutoff | 3.94 GHz | ~5.5-6 GHz | ~x1.45 | - |

Cause (expected, budgeted for from the start — see §10): no ground plane ->
fan capacitance collapsed (bigger effect) + eps_eff dropped -> stalk/series
electrical lengths shrank (smaller effect). The in-band mismatch ripple vs.
50-ohm ports and the ~9.6GHz parasitic spike noted in the handoff are HFSS/
port-model questions, not layout — out of scope for this pass.

### 12.2 Scaling mechanism (`SCALE_SERIES`/`BRANCH_SCALES`, `_apply_scales()`)

The Rev 4 base tables (`SERIES_SECTIONS`/`BRANCH_PAIRS`) stay verbatim as the
permanent reference; `_apply_scales()` builds a scaled copy at build time and
everything downstream (drawing, envelope/clearance bookkeeping, the printed
report) consumes only the scaled copy. Only `stalk_length` (all branches) and
`fan_rout` (all branches) scale — `fan_rin`, `attach_width`, and every
line/stalk *width* stay fixed at their Rev 4 values, per the handoff's
explicit rule.

Physics: zero freq ~ 1/√(LC); L ~ stalk length (linear); C ~ fan Rout^α, α
between 1 (fringing-dominated, no ground plane) and 2 (area-dominated). A
uniform scale *s* on both gives LC ~ s³ (α=2, s~1.24-1.28 suffices) to LC ~
s² (α=1, s~1.38-1.45 needed). `SCALE_SERIES=1.40`, `BRANCH_SCALES` start at
the α~1 (larger/conservative) end; P3 gets a smaller scale (1.35) than
P2/P4/P1 (1.40) per its smaller measured shift (x1.384 vs x1.454). Expect
2-3 more HFSS-driven edits per branch as this converges — this is exactly
what the mechanism is for.

### 12.3 Folded-stalk geometry (`BRANCH_FOLDS`, `guarded_bend()`, `folded_branch_pair()`)

Rev 4's `tilt` mechanism (leaning branches back to shrink transverse
footprint) is **retired** — every branch now exits exactly perpendicular to
the main line. Growth from scaling (P2 stalk 1980->2772um, P3 3271->4416um)
would blow the 6500um transverse budget if drawn straight, so P2/P3 fold
into hairpin-style meanders instead (P1/P4 stay straight — short enough even
scaled).

**Reuse target**: `maskLib.microwaveLib.Strip_bend` — the positive-metal
analog of `CPW_bend` (which `Hairpin_Filter.py`'s own `tapped_hairpin_filter`
uses for its own folds, but that whole path is CPW/XOR-gap and not usable
directly on this file's no-ground-plane convention). `Strip_bend` with
`ralign=valign=MIDDLE` draws one filled `CurveRect` half-annulus — `radius`
is the trace *centerline* radius, `height`=`w` is the trace width — exactly
a U-turn between two parallel strips. `guarded_bend()` wraps it (mirroring
`guarded_straight`/`guarded_taper`'s existing pattern): calls the real
`Strip_bend` for drawing + structure position/direction update, and
separately builds an un-added `CurveRect` with identical params purely to
extract `.points` for envelope bookkeeping (same idiom `radial_fan()`
already uses for the fans). `Strip_wiggles`/`wiggle_calc` (the library's own
full meander composite) weren't used directly — their parameterization
(auto-fit turn count to a width budget) doesn't match the handoff's explicit
knobs (`d_perp` independent of run length, `n_par_runs` fixed by hand,
`run_gap` explicit) — instead `folded_branch_pair()` hand-rolls the fold
loop with `Strip_straight`/`guarded_bend`, mirroring `Strip_wiggles`'s own
internal loop shape.

**Run length is always solved, never hardcoded**: given `d_perp`,
`n_par_runs`, and `run_gap` (-> `bend_radius = (run_gap+w)/2`), each parallel
run's length solves from `spec['stalk_length'] (scaled) = d_perp +
(pi/2)*bend_radius [90° entrance arc] + n_par_runs*run_length +
(n_par_runs-1)*(pi*bend_radius) [180° arcs]`.

**Bug #1 found and fixed — mirror vs. rotational symmetry**: the initial
implementation used the SAME `CCW` value for both the '+' and '-' side, on
the (wrong) assumption that the two sides' already-mirrored local frames
(`main_dir±90`) would automatically produce a true mirror image. Caught via
the printed clearance report: P1<->P2 clearance came back at 252.1um (well
under the 500um floor) on the first build. Diagnosis (numerically comparing
both sides' point-set Y-ranges) showed the two sides' meanders had
*different* Y-extents — impossible for a true reflection about the main
line's vertical axis (a vertical-axis mirror cannot change Y-extent at all)
— i.e. the same-CCW construction was actually giving 180°-*rotational*
(point) symmetry about the junction, not a mirror image. Fix: flip `CCW` on
the '-' side (`not CCW`) for every bend, entrance turn included — a mirror
reflection inverts handedness. Re-verified numerically (identical Y-ranges,
correctly-mirrored X-ranges for both P2's 2-run and P3's 3-run fold).

**Bug #2 found and fixed — parallel runs were transverse, not axial**:
caught by Eddie from a rendered DXF review, compared directly against a
folded-inductor reference image (and the Fast_Flux hairpin filter precedent)
— the fold's long axis came out oriented *transverse* to the main line
instead of parallel to it. Root cause: the first implementation went
straight from the perpendicular exit run into the "parallel runs" with NO
turn in between, so those runs stayed in the transverse direction the whole
time; the 180° bends (which step *perpendicular to the current direction*)
then stepped the meander *axially* instead of transversely — exactly
backwards. Fixed by inserting an explicit 90° `guarded_bend()` between the
exit run and the first parallel run, turning the direction from
perpendicular into axial before the meander starts (mirroring
`Strip_wiggles`'s own `start_bend=True` branch, which does exactly this).
Confirmed via re-rendered DXF: parallel runs now run parallel to the main
line, matching the reference geometry, with each 180° bend correctly
stepping the meander transversely (away from the main line) as intended.

**Bug #3 found and fixed — `fold_dir` needed to avoid P1, not just interleave
P2/P3**: after fixing bug #2, the fan (which now correctly points axially,
along whichever direction the last parallel run travels) pointed P2's fan
*upstream*, straight at P1's own fan — collapsing P1<->P2 clearance to
300um and creating two new small enclosed holes between them. P1 sits close
upstream of P2 (short, 2082um-scaled S1 gap), so P2's fold needs to point
*downstream* (away from P1) regardless of P3's own direction — the original
"opposite fold_dir interleaves P2/P3" framing turned out not to be the
binding constraint here. Fixed by setting `BRANCH_FOLDS['P2']['fold_dir']`
to `-1` (matching P3's, not opposite) — confirmed empirically (this sign
convention is otherwise unlabeled/empirical, see `guarded_bend`'s own
docstring) that `-1` points the meander downstream for both branches at this
main-line orientation.

**Bug #4 found and fixed — repeated (not alternating) bend handedness spirals
into a closed loop**: caught by Eddie from a rendered DXF review against a
folded-inductor reference image — the meander came out as a closed
racetrack/oval loop instead of a zigzag. Root cause: every 180° internal
bend reused the SAME `side_CCW` value, so each turn curled the SAME
rotational way as the last, spiraling the path back on itself instead of
alternating side to side. Fixed with a running `turn_CCW` variable that
flips (`not turn_CCW`) before every turn (each 180° internal bend, in
sequence) — mirrors `Strip_wiggles`' own alternating not-CCW/CCW/not-CCW/...
pattern (re-read directly from its source this session to get this right).

**Bug #5 found and fixed — fan orientation**: the original design (§ above,
now superseded) assumed the fan should point *axially* (no turn after the
last run) to minimize transverse extent. Eddie corrected this directly: the
fan needs to point *away from the main line* (transverse), matching "facing
away from the microstripline." Fixed by adding a final 90° exit turn after
the last parallel run (continuing the SAME alternating `turn_CCW` sequence
one more step, just at half the angle) before calling `radial_fan()`
unchanged. This costs meaningfully more transverse budget than the axial
orientation did (the fan's full `Rout` now projects transversely instead of
mostly axially) — see § 12.4.

### 12.4 As-built results (after all five fixes, this session)

Fixing fan orientation (bug #5) pushed the transverse bounding box from
~5.4mm to 9363.8um — 44% over the 6500um budget, since the fan's full
`fan_rout` (1586-1670um) now projects directly into the transverse
direction. Per Eddie's direction, closed the gap by tightening `d_perp`/
`run_gap` (not by relaxing the budget or shrinking `fan_rout`, which would
drift from the HFSS-measured scale targets) — iterated down from
`d_perp=1200/run_gap=500` to `d_perp=630/run_gap=150` for both P2 and P3:

```
Main line series sections - base -> x1.40 -> scaled:
  S1: 1487.0 -> 2081.8um   S2: 4202.0 -> 5882.8um
  S3: 3190.0 -> 4466.0um   S4: 138.3 -> 193.6um

P1: stalk 200.0->280.0um (x1.40), fan_rout 582.9->816.1um (x1.40) - straight
P2: stalk 1980.0->2772.0um (x1.40), fan_rout 1133.0->1586.2um (x1.40)
    FOLDED: d_perp=630um, n_par_runs=2, run_gap=150um -> bend_radius=137.5um,
    solved run_length=639.0um, fold_dir=-1
P3: stalk 3271.0->4415.9um (x1.35), fan_rout 1237.0->1670.0um (x1.35)
    FOLDED: d_perp=630um, n_par_runs=3, run_gap=150um -> bend_radius=137.5um,
    solved run_length=830.0um, fold_dir=-1
P4: stalk 585.4->819.6um (x1.40), fan_rout 992.7->1389.8um (x1.40) - straight

Realized transverse bounding box: 6123.8um (budget 6500um, margin 376.2um)
Per-pair clearances: P1<->P2 548.5um, P2<->P3 2497.8um, P3<->P4 3463.8um
(all above the 500um visual-check threshold; P1<->P2 is the tightest -
worth a KLayout visual confirm before fab)
```

### 12.5 Second tuning round — wider run_gap, P1 proximity, width re-fit

Eddie reviewed a rendered DXF of the `run_gap=150` version and asked for
three changes: shorten `d_perp` further, widen `run_gap` back toward the
handoff's original 300-500um guideline (less antiparallel-run coupling),
and let `run_length` grow to absorb both (already automatic via the
existing solve - no code change needed for that part).

**`d_perp` cannot shorten below 625um** without violating the handoff's own
"any meander segment to the main line >= 500um" rule (`d_perp - 125/2 -
125/2 >= 500` given 125um-wide traces on both sides) - the prior 630um value
was already only 5um above this floor. Set to the exact floor, 625um, for
both P2 and P3 - as short as the rule allows.

**`run_gap` widened 150um -> 300um** for both P2 and P3 (bend_radius
137.5um -> 212.5um) - still short of the original 500um guideline, but a
real improvement; `run_length` grows automatically to absorb the larger
turn-arc cost against the same `stalk_length` target (see the width re-fit
below for P3's actual resulting `run_length`, which also changed its
`n_par_runs`).

**Bug #6 found and fixed — P1<->P2 proximity was from `run1`, not the
fan**: traced P2's segments individually (structure position/direction
after each drawn piece) and found `run1` (the parallel run nearest the main
line) ran from y=30056 to y=30695 - *into* P1's own fan's y-range
(P1's fan spans down to ~y=31423) - even though the fan (unaffected, at the
far end) already pointed safely downstream. Root cause: `fold_dir=-1`'s
entrance-turn handedness sent the FIRST run upstream before the internal
180 bend flipped it back downstream for `run2`. Confirmed algebraically and
via the trace that flipping `fold_dir` (now `+1` for P2) swaps which run
goes upstream vs downstream first, WITHOUT changing the fan's final
direction at all - the exit turn (bug #5's fix) always returns to the same
transverse-outward heading regardless of `fold_dir`'s sign, so this fix is
fully decoupled from the earlier fan-orientation fix and can't undo it.
P1<->P2 clearance: 548.5um -> 1445.6um.

**Width re-fit**: `run_gap=300` alone (before any n_par_runs change) pushed
the transverse bbox to 7013.8um (513.8um over budget) - P3, still at 3
parallel runs, was the binding constraint. Per Eddie's call, dropped P3 to
2 parallel runs (matching P2) rather than relaxing `WIDTH_BUDGET_UM` or
re-splitting `run_gap` - `run_length` grows to 1227.8um to absorb the same
`stalk_length` target with one fewer bend.

```
P2: FOLDED: d_perp=625um, n_par_runs=2, run_gap=300um -> bend_radius=212.5um,
    solved run_length=405.9um, fold_dir=+1
P3: FOLDED: d_perp=625um, n_par_runs=2, run_gap=300um -> bend_radius=212.5um,
    solved run_length=1227.8um, fold_dir=-1

Realized transverse bounding box: 6163.8um (budget 6500um, margin 336.2um)
Per-pair clearances: P1<->P2 1445.6um, P2<->P3 3274.2um, P3<->P4 2455.6um
(all comfortably above the 500um threshold; single merged polygon, 0 holes)
```

P3 is now 2 parallel runs rather than the originally-requested 3 - a direct
trade against the wider `run_gap`, made explicitly by Eddie once the
width conflict surfaced. If a future HFSS pass frees up width budget
elsewhere (e.g. a smaller required `BRANCH_SCALES` correction), reverting
P3 to 3 runs (and shrinking `run_gap` back down somewhat) is the natural
first knob to revisit.

Visually re-rendered and confirmed: clean alternating zigzag matching the
reference image, fans pointing away from the main line, single merged
polygon, **0 holes**. (An earlier axial-fan version of this geometry had
found 6 real, sizeable enclosed holes — each fold's fan was large enough to
sweep back over its own meander body and seal a pocket of bare sapphire.
With the fan now pointing transversely/outward instead, it no longer
reaches back over the fold at all, so that mechanism no longer applies -
resolved as a side effect of bug #5's fix, not a separate fix.)

**Real caveat worth flagging**: `run_gap=150um` (1.2x the 125um line width)
is well below the handoff's own original guideline of `run_gap>=500um (=4x
line width)`, chosen specifically to keep antiparallel-run coupling's
inductance-reducing effect small. At this tighter spacing, expect MORE
coupling-driven inductance reduction than a straight stalk of the same
length would have — i.e. the next HFSS iteration's realized zero frequency
for P2/P3 will likely need a bigger `BRANCH_SCALES` correction than an
equivalent straight or loosely-folded stalk, on top of the no-ground-plane
correction already being tracked. Not quantifiable without re-running HFSS
(out of this session's scope) - flagged here so it isn't mistaken for a
plain re-measurement of the same physics when the next HFSS pass comes back
different from a straight-stalk extrapolation.

(Separately confirmed, and no longer applicable now that fans point
transverse rather than axial: the individual zero-length "degenerate" edges
klayout reports elsewhere in the merged region are a **pre-existing**
`CurveRect` fill-quad/triangle rendering characteristic — same check run
against `filter_L30_orthogonal`'s already-shipped GDS, fans only, no bends,
shows the same pattern. Not a Rev 5 regression, not a real PATH-degeneracy
issue — every real `guarded_straight`/`guarded_taper`/`guarded_bend` call in
this file still raises `ValueError` on an actually-degenerate length/radius
before it can reach the DXF.)

### 12.6 Scope notes

- **`verify_L30_hfss_export.py`/`filter_L30_HFSS.py` were stale against this
  geometry as of the layout-only pass above** (their `_build_pieces()` still
  hand-replayed the OLD straight/tilted drawing sequence) — **rewritten and
  re-run in a follow-up session** (see `notebooks/L30_HFSS_notes.md` §10-11
  for the bend-geometry derivation, the exit-turn-to-fan `Unite()` fix, and
  the real S21/S11 result: every null shifted toward the Nuhertz targets
  vs. the unscaled orthogonal baseline, `HFSS/compare_L30_rev5_vs_orthogonal.png`).
- **`filter_L30_orthogonal.py` is untouched** — still reflects Rev 4
  dimensions (unscaled, untilted). Purely a historical tilt-comparison
  artifact now; not part of the Rev 5 lineage.
- **`filter_L45.py` is untouched** this session, per the handoff — gets the
  same Rev 5 treatment once L30 converges in HFSS.
- The handoff's deliverables list mentions "KLayout XOR solid fill" —
  this contradicts this file's explicit, repeatedly-confirmed positive-metal
  (no XOR) convention (own module docstring, `CLAUDE.md`). Treated as
  boilerplate carried over from a Hairpin-derived deliverables checklist;
  XOR was NOT implemented. Flagging in case this reading is wrong.
