# L60 radial-stub lowpass filter — design notes

Companion to [`filter_L60.py`](../filter_L60.py) - the third filter in this
family, built directly on [`filter_L30.py`](../filter_L30.py)'s Rev 5
pattern (HFSS scale-factor hooks, folded/meandered stalks, envelope
clearance checks, runtime dimension report - see
[`L30_design_notes.md`](L30_design_notes.md) sec 12 for that pattern's own
derivation). This doc only covers what's specific to L60: its own dimension
tables, the new L-bend fold variant P5 needed, and the as-built iteration
results - not a re-derivation of the shared geometry math (fan
insert/rotation, bend winding, mirror-symmetry CCW-flip rule, etc.), which
is unchanged and already fully documented in `L30_design_notes.md`.

## 1. Provenance

10th order elliptic (equiripple in BOTH passband and stopband, unlike
L30/L45's Chebyshev-II - a real filter-type change, not just "more
sections") lowpass, synthesized 2026-07-19: fc=3.500GHz/0.01dB passband
ripple, stopband from 3.917GHz (ratio 1.119), 60dB equiripple floor.
Microstrip/alumina model (eps_r=9.80, h=500um, conductor 100nm - closer to
our 120nm Al than L30/L45's prior 300nm assumption, no layout consequence),
main line Zo=84.28ohm/125um. As-synthesized (untilted/unfolded):
19.02mm x 9.825mm total envelope.

Nuhertz source/netlist not provided directly - tables transcribed from
screenshots, same caveat as L30/L45 (item **V1** below).

## 2. Topology

Same butterfly-pair structure as L30: a 125um/84.28ohm main line with 5
shunt branch pairs (P1-P5) at the section boundaries, P1 before S1, Pn
between S(n-1)/Sn. Branch ordering along the line, and the P1 matching
branch's distinct stalk width/Zo (250um/66.54ohm vs 125um for P2-P5), are
both **unverified** against the Nuhertz layout picture (items **V2**/**V3**).

Elliptic-specific note (HFSS/circuit-side, no layout implication): the
zero clustering just above cutoff (P3 4.471GHz, P4 4.752GHz, P2 5.491GHz)
is what buys the steep 3.5->3.917GHz skirt at 60dB - tighter than L30's
more spread-out zeros. P1's matching fan (1.108mm as-synthesized) is
notably larger than L30/L45's (~0.4-0.6mm) - a real consequence of the
elliptic synthesis, not a transcription error.

## 3. Dimension tables (base, unscaled - see sec 5 for scaling)

```
Main line series sections (Zo=84.28ohm, 125um):
  S1: 3934.0um   S2: 3322.0um   S3: 2941.0um   S4: 4122.0um   S5: 1948.0um

Shunt branch pairs:
  P1 (match): stalk 200.0x250.0um (Zo=66.54ohm), fan Rout=1108.0 Rin=176.8 angle=90deg
  P2: stalk 2010.0x125.0um, fan Rout=1398.0 Rin=88.39 angle=90deg, zero=5.491GHz
  P3: stalk 3781.0x125.0um, fan Rout=1132.0 Rin=88.39 angle=90deg, zero=4.471GHz
  P4: stalk 3137.0x125.0um, fan Rout=1229.0 Rin=88.39 angle=90deg, zero=4.752GHz
  P5: stalk 808.3x125.0um, fan Rout=1474.0 Rin=88.39 angle=90deg, zero=7.679GHz
```

Sanity check from the handoff doc, confirmed consistent with the butterfly
reading: worst branch P3 = 3.781+1.132 = 4.91mm/side; x2 = 9.83mm matches
Nuhertz's own "Total Height" (9.825mm).

## 4. Scaling (unchanged mechanism from L30 Rev 5 - see `L30_design_notes.md` sec 12.2)

`SCALE_SERIES=1.40`, every `BRANCH_SCALES` entry `(1.40, 1.40)` -
**uniform, not per-branch-differentiated**. The handoff for this file asked
to seed from "filter_L30.py's converged HFSS scales," but `filter_L30.py`
has had exactly one real HFSS pass so far (see `L30_HFSS_notes.md` sec 11)
and is explicitly NOT converged (P4 there is already flagged as likely
needing a further correction). Per the handoff's own stated fallback ("fall
back to 1.40/1.40 if L30 has not converged"), every L60 branch starts at
1.40/1.40 uniformly - there's no valid physical reason to map L60's 5
branches onto L30's 4 by index, they're different branches on a different
filter. This is a starting guess pending L60's own future HFSS pass, same
as every dimension in this file.

## 5. New fold variant: the single L-bend (P5)

P2/P3/P4 reuse `folded_branch_pair()` verbatim (byte-identical copy from
`filter_L30.py` - see `L30_design_notes.md` sec 12.3 for its full
derivation and the two bugs found/fixed there, both already baked into this
copy). P5 (short stalk, unusually large fan - 1474um Rout as-synthesized,
the biggest of any branch pair in this filter) needed something new: the
handoff explicitly wanted its fan "oriented along the chip axis
(outboard-axial)" - a DIFFERENT orientation than P2/P3/P4's meander, which
deliberately points its fan TRANSVERSE (away from the main line, per
Eddie's own correction to `filter_L30.py`'s design - see
`L30_design_notes.md` sec 12.3, bug #5).

**`l_bend_branch_pair()`** (new, `filter_L60.py` only): perpendicular exit
run (`d_perp`) -> ONE 90-degree `guarded_bend()` turn -> one run -> fan,
attached DIRECTLY with no exit turn. Since there's no exit turn to rotate
back to transverse, the fan naturally inherits the single run's AXIAL
direction - exactly the orientation requested, achieved by *omitting* a
step from `folded_branch_pair()`'s sequence rather than adding one.
`run_length` is solved the same way (`stalk_length - d_perp -
(pi/2)*bend_radius`), and the same mirror-symmetry CCW-flip-per-side rule
applies (`side_CCW = CCW if sign>0 else not CCW` - a mirror reflection
inverts handedness, same reasoning as `folded_branch_pair()`'s own
already-empirically-confirmed rule, applied here from the start rather than
re-discovered the hard way).

Since a single L-bend has no second parallel run to space against, it takes
`bend_radius` directly in `BRANCH_FOLDS['P5']` rather than
`run_gap`/`n_par_runs` - not specified by the handoff, started at 212.5um
(matching `filter_L30.py`'s own actually-converged bend radius at
`run_gap=300,w=125`).

**P5 was reverted to a plain straight branch after the first build** (per
Eddie, once P2/P3/P4's own width tuning - sec 6 - freed up enough margin to
afford it, matching the handoff's own explicitly-allowed fallback: "already
fits under budget... inside hard budget but over target"). `filter_L60.py`
keeps `l_bend_branch_pair()` defined and verified-working (not deleted) in
case a future width squeeze makes P5's L-bend worth revisiting - see sec 6
for the actual as-built comparison between the two.

## 6. As-built iteration (this session)

The handoff's own suggested starting `d_perp=1200um`/`run_gap=500um`
**failed immediately** - P2's scaled stalk_length (2814um) can't fit
`d_perp=1200` plus the 2-turn arc cost at `run_gap=500`'s
`bend_radius=312.5um` (degenerate negative run length), the exact same
failure `filter_L30.py` hit with ITS OWN original starting values. Started
over directly from `filter_L30.py`'s actual battle-tested values instead
(`d_perp=625um` - the true main-line-clearance floor - `run_gap=300um`) -
rather than re-discovering the same failure mode from scratch.

Three rounds of width-budget tuning followed (5 branches share the same
unchanged 6500um budget L30 used for 4, so more pressure was expected):

```
Round 1 (d_perp=625, run_gap=300, P2/P3/P4 all n_par_runs=3, P5 l_bend):
  Transverse width: 7115.0um *** OVER BUDGET *** (P4 binding: 7115.0um)
Round 2 (P4 -> n_par_runs=2):
  Transverse width: 6843.5um *** OVER BUDGET *** (P3 binding: 6843.5um)
Round 3 (P3 -> n_par_runs=2):
  Transverse width: 6738.1um *** OVER BUDGET *** (P2 binding: 6738.1um)
Round 4 (P2 -> run_gap=150, already at n_par_runs=2):
  Transverse width: 6265.0um - UNDER BUDGET (235.0um margin)
```

Final `BRANCH_FOLDS`:
```
P1: straight (280.0um scaled - short enough as-is)
P2: FOLDED, d_perp=625um, n_par_runs=2, run_gap=150um -> bend_radius=137.5um,
    run_length=662.5um, fold_dir=+1
P3: FOLDED, d_perp=625um, n_par_runs=2, run_gap=300um -> bend_radius=212.5um,
    run_length=1666.6um, fold_dir=-1
P4: FOLDED, d_perp=625um, n_par_runs=2, run_gap=300um -> bend_radius=212.5um,
    run_length=1215.8um, fold_dir=+1
P5: L-BEND, d_perp=625um, bend_radius=212.5um, run_length=172.8um, fold_dir=+1
    (fan axial, not transverse - see sec 5)

Realized transverse bounding box: 6265.0um (budget 6500um, margin 235.0um)
Realized axial (length) extent: 27500.0um (informational, no hard budget - 40mm chip)
Per-pair clearances: P1<->P2 3272.7um, P2<->P3 1502.4um, P3<->P4 1782.7um,
                      P4<->P5 4024.8um (all comfortably above the 500um threshold)
```

**Round 5 (P5 L-bend -> plain straight, per Eddie)**: with the L-bend, P5's
own transverse width was 4593.4um (comfortably below P4's 6265.0um, so not
the binding constraint) - reverting it to a straight `branch_pair()`
brought P5's own width up to 6264.0um (just barely under P4's, still not
binding). Net effect: **transverse bounding box unchanged at 6265.0um**
(P4 stays the binding constraint either way), clearances shift slightly
(P4<->P5: 4024.8um -> 2965.3um) but stay comfortable. Final per-pair
clearances: P1<->P2 3272.7um, P2<->P3 1502.4um, P3<->P4 1782.7um, P4<->P5
2965.3um.

P5's `fold_dir=+1` (from the L-bend attempt) was never re-checked against a
neighbor-proximity issue the way L30's P2 needed (see `L30_design_notes.md`
sec 12.5, bug #6) - P4<->P5 clearance came out comfortable on the first try
either way, so no segment-trace diagnostic was needed - now moot with P5
straight, but would matter again if the L-bend is revisited later.

**margin note**: 235um is a real but not generous margin - about the same
tightness level L30 landed at after its own tuning. The first knob to
revisit if a future HFSS pass grows any branch's `stalk_length` is
`run_gap` (P3/P4 are still at 300um, one step above P2's 150um - room to
tighten there before touching `n_par_runs` or `d_perp` again, or
reintroducing P5's L-bend for more margin).

## 7. Build-time / Heidelberg-safety checks (this session)

Printed report (repo `.venv`, no Ansys): no `ValueError` from any guard
(degenerate length/radius, d_perp main-line clearance, folded/L-bend
run-length degeneracy); transverse width under budget; every adjacent-pair
clearance above 500um (see sec 6's table).

Visual render (matplotlib + klayout Region, same technique as L30's own
iteration), both configurations checked:
- **With P5 as an L-bend** (first build): confirmed clean butterfly
  symmetry throughout, P2/P3/P4's meanders correctly transverse-oriented,
  and P5's L-bend clearly visible with its fan correctly pointing axially
  (up the chip, toward P4) rather than transversely - the intended,
  distinct orientation for that variant. klayout check: 1 merged polygon,
  **2 real holes** (~480,000 um^2 each, at P5's turn region,
  y~10856-11891) - same mechanism already documented for L30's earlier
  axial-fan-orientation version (`L30_design_notes.md` sec 12.4-12.5): P5's
  own large fan (2063.6um scaled Rout), pointing axially, physically
  reached back far enough to seal the open channel at its own turn,
  enclosing a pocket of bare sapphire. Not a Heidelberg/DWL rejection risk
  (a polygon with a hole is a normal GDS/DXF construct), just flagged.
- **With P5 reverted to straight** (final build, this session): same clean
  butterfly symmetry, P5 now a simple stalk+fan pair matching P1's style.
  klayout check: 1 merged polygon, **0 holes** (P5's fan no longer reaches
  back over anything, since there's no turn left to reach back over).

**130 degenerate (zero-length) edges** reported in the raw unmerged shapes
(both configurations) - confirmed via the same check run against L30's own
GDS earlier this session that this is a **pre-existing `CurveRect`
fill-quad/triangle rendering characteristic** (present in L30's fan-only
baseline too, not a new issue here), not a real PATH-degeneracy problem -
every `guarded_straight`/`guarded_taper`/`guarded_bend` call in this file
still raises `ValueError` on an actually-degenerate length/radius before it
reaches the DXF. Higher count than L30's (130 vs ~50-80) simply tracks L60
having more curved pieces (5 branches x up to 2 turns each + 5 fans, vs
L30's 4 branches).

## 8. Open verification items (carried from the handoff doc)

- **V1**: dimension tables transcribed from Nuhertz synthesis screenshots,
  not the original netlist/export file - not independently re-verified.
- **V2**: branch ordering along the main line (P1 before S1, P2 between
  S1/S2, etc.) assumed to match L30/L45's precedent - not confirmed against
  L60's own Nuhertz layout picture.
- **V3**: P1's stalk Zo (66.54ohm) and width (250um, vs 125um for P2-P5)
  read directly from the handoff table - flagged as the one branch that
  differs from the others, worth double-checking against the source.

## 9. Known risks / caveats carried into implementation

*(This section is Rev 6's own snapshot - P5 is no longer an L-bend and the
width margin is no longer 235um under budget; see sec 10 for Rev 7's
current state and its own risk list.)*

- Every electrical dimension is PLACEHOLDER pending HFSS re-extraction in
  the real bare-sapphire/tunnel-ground stack - same caveat as L30/L45, now
  compounded by the fact that scales are seeded from L30's own UNCONVERGED
  first-pass values (sec 4), not real L60 sim data.
- P5's `bend_radius=212.5um` is an unvalidated starting guess (sec 5) -
  no L-bend-specific HFSS data exists yet to confirm this radius doesn't
  introduce more parasitic coupling than expected (same general caveat
  `L30_design_notes.md` sec 12.5 raised for its own tight `run_gap` values).
- The 235um width-budget margin (sec 6) is real but not generous - the
  first thing a future HFSS-driven `BRANCH_SCALES` increase would threaten.
- No HFSS bridge exists for this file yet (out of scope this session,
  matching the handoff's own deliverables list and L30's own Rev 5
  layout-only precedent) - would need the equivalent of
  `verify_L30_hfss_export.py`/`filter_L30_HFSS.py`, including a
  `bend_arc_points()`-style native-arc representation AND a matching
  `l_bend_branch_pair()` replay (new geometry, not yet built for any HFSS
  bridge) before any real S21 sweep is possible for L60.
- `filter_L30.py`/`filter_L45.py` untouched this session, per the handoff.

## 10. Rev 7: impedance-contrast + real package bore (Phase 1 of a two-phase handoff)

**Motivation**: HFSS diagnostics on the Rev 6 sim identified the 10.23GHz
stopband peak as the first overtone of the P3 branch pair (a
stepped-impedance resonator whose overtone-to-fundamental ratio grows with
stalk/fan impedance contrast). Raising that contrast - narrower high-Z
lines (`W_HIZ=70um`, main line + P2-P5 stalks; P1 keeps its distinct
`W_P1_STALK=250um` matching-branch role unchanged) and a wider fan angle
(`FAN_ANGLE=115deg`, all 5 branches) - shortens branches and pushes the
overtone above ~11.5GHz, out of the protection band. PHASE 2 (adding the
real aluminum cavity package to the HFSS sim) is Eddie-side, out of scope
here.

### 10.1 Flared stalk-to-fan junction

At the wider fan angle, `radial_fan()`'s own flush attach chord
(`2*r_in*sin(angle/2)`) no longer equals the (now narrower) stalk width -
`fan_rin` stays exactly as synthesized (unchanged per the handoff),
`attach_width` is recomputed to the fan's true flush chord instead
(`_flush_attach_width()`), so the stalk deliberately flares/steps into the
wider fan root. `branch_pair()`/`folded_branch_pair()`'s old
`stalk_width==attach_width` assertion was dropped accordingly - a
deliberate design decision confirmed with Eddie before implementation (not
a silently-picked default), since the alternative (shrinking `fan_rin` to
preserve a flush stalk-width match) would have violated the handoff's
explicit "Fan Rin... unchanged" instruction.

### 10.2 Dead end #1: axial fans / L-bend under the WRONG width budget

The handoff stated the package bore was 5.5mm, giving `WIDTH_BUDGET_UM
=4500` (down from Rev 6's 6500). Under that budget, every large-fan
branch's own transverse bulge alone dominated the budget regardless of
fold geometry - this led to two bad detours, both later reverted per
Eddie's direct, live correction:

1. Dropped `folded_branch_pair()`'s exit turn so fans pointed AXIALLY
   instead of perpendicular to the microstrip (misreading the handoff's
   width-budget language as overriding the established perpendicular-fan
   convention). **Wrong**: fans must stay perpendicular to the
   microstrip - the exit turn is not optional. Also produced a visually
   collapsed "circle" rather than a genuine back-and-forth zigzag ("the
   same mistake as before" - Eddie).
2. Switched to `l_bend_branch_pair()` (single turn, no exit turn - same
   axial-fan problem as #1) with `d_perp`/`bend_radius` pushed to their
   physical floors. Even at the theoretical minimum overhead, P5 alone
   (`fan_rout=2063.6um` scaled, the largest fan) came out ~200um over the
   4500um budget - a confirmed, numbers-backed infeasibility, not a
   tuning failure - given `fan_rout`/`FAN_ANGLE`/`BRANCH_SCALES` are all
   fixed inputs Phase 1 isn't authorized to touch.

Both issues turned out to share one root cause: **the handoff's own bore
figure was wrong**. Eddie corrected it mid-session to 6.985mm (not
5.5mm) - `WIDTH_BUDGET_UM` is now derived from `PACKAGE_BORE_DIAMETER_UM`/
`PACKAGE_WALL_CLEARANCE_UM` (not hardcoded) and comes out to 5985um,
close to Rev 6's own 6500um and comfortably resolving dead end #2's
infeasibility. Both `folded_branch_pair()`'s exit turn and the
straight-branch fallback were reverted to their perpendicular-fan form.

### 10.3 Dead end #2: the stalk-to-fan gap wasn't actually closed by a longer reach

Once fans were back to perpendicular, a visual render showed the stalk
NOT touching the fan at all - a real gap, not the intended flared
T-junction. Root cause: `radial_fan()`'s `CurveRect` annular sector has a
CURVED inner boundary (radius `fan_rin`), not the flat chord
`attach_width` matches - the arc bulges away from that chord by a real
sagitta (`r_in*(1-cos(angle/2))`, ~41-82um depending on branch), zero at
the sweep's two corners, maximum at the center.

Two fix attempts failed for the SAME underlying reason, only understood
after the second: extending the connecting taper/run's own drawn LENGTH
(first: sagitta+20um margin; then, when a visual check still showed the
rect "starting on the outside" of the fan - Eddie - a much larger `r_in`-
based reach) had **zero measurable effect** on the resulting gap/hole
(confirmed via klayout: identical hole area to 4+ decimal places across
both attempts). The sagitta gap is INTRINSIC to `radial_fan()`'s own
construction relative to wherever `structure.start` sits when it's
called - pushing that reference point further away via a longer preceding
run just moves the whole fan (and its own unchanged internal sagitta gap)
further away too, never closing it. A separate width-overshoot attempt
(widening the connector beyond `attach_width`) was also tried and later
reverted per Eddie's request for the taper to end at the fan's own
*correct* (not arbitrarily wide) end width.

**The actual fix** (`guarded_fan_taper()`): draw a short connector (taper
+ straight run, exactly `attach_width` wide) for a clean visual
transition, then RETREAT the structure's own position backward
(`Structure.translatePos()`, no drawing) by the sagitta plus a small
buffer, so `radial_fan()`'s own `tip` reference lands INSIDE the metal
already drawn, guaranteeing real overlap with the fan's near-boundary
instead of an ever-receding tangent point. Verified via klayout: 3
disconnected fragments + large holes (up to ~5.7 million um^2) -> 1 fully
connected polygon, 0 holes.

**Follow-up bug (found by Eddie visually, after the above was already
merged/hole-free): the taper was still measurably narrower than the fan
right at the seam corners.** Root cause: the retreated `tip` always lands
exactly `_FAN_TAPER_OVERLAP_BUFFER_UM` (20um) past the connector's own
start, independent of sagitta (`run_len - retreat == buffer` by
construction) - but `_FAN_TAPER_STEP_LEN` (the taper's own length, 25um)
was *longer* than that 20um buffer, so the fan's corners (which need the
full `attach_width` exactly at the tip) landed 5um inside the still-
narrowing taper, 5 um short of full width per branch (~7.9um short in
half-width terms at the 115deg/149um-attach-width branches). Didn't show
up as a klayout hole/disconnect (the notch wasn't big enough to break
polygon merging) - only visible as a boundary irregularity on close visual
inspection, exactly what Eddie flagged. Fixed by clamping `taper_len =
min(_FAN_TAPER_STEP_LEN, run_len, _FAN_TAPER_OVERLAP_BUFFER_UM - 2.0)` -
structurally guarantees (not just via the nominal constant) that the
taper reaches full `attach_width` at least 2um before the tip, for every
branch (checked analytically for all 5: P1 sagitta 81.8um, P2-P5 sagitta
40.9um, all landing at taper_len=18um vs tip_u=20um). Re-verified after
the fix: klayout still reports 1 merged polygon, 0 holes.

### 10.4 Final per-branch fold treatment (KLayout-verified clean)

```
P1: straight (branch_pair()) - short stalk, fits without folding
P2: FOLDED, n_par_runs=1 (single elongated run), d_perp=575um,
    run_gap=400um -> bend_radius=235um, fold_dir=-1 (flipped + elongated
    per Eddie - cuts one bend_radius of turn overhead vs a 2-run meander;
    was the widest branch (6969.8um) before this fix, now 5948.1um)
P3: FOLDED, n_par_runs=2, d_perp=575um, run_gap=400um -> bend_radius=235um,
    fold_dir=-1 (flipped per Eddie - also improved its own clearance to
    P4 from 316.5um to 1331.7um)
P4: FOLDED, n_par_runs=2, d_perp=575um, run_gap=400um -> bend_radius=235um,
    fold_dir=-1
P5: straight (branch_pair()) - CANNOT fold at all under _MIN_RUN_GAP_UM
    =400: even one U-turn's own arc cost (pi*bend_radius=738.3um) plus
    the d_perp clearance floor (~570um) exceeds its own scaled
    stalk_length (1131.6um) - confirmed via a real ValueError (negative
    run_length), not a preference

Realized transverse bounding box: 6415.0um (budget 5985.0um) - 430um/7.2% OVER
Per-pair clearances: P1<->P2 1101.9um, P2<->P3 2526.3um, P3<->P4 1331.7um,
                      P4<->P5 2586.9um (all comfortable)
KLayout check: 1 merged polygon, 0 real holes - ALL CHECKS PASSED
```

P3/P4 specifically cannot both use the single-elongated-run form
(`n_par_runs=1`) without enclosing a real hole between their folds and the
main line, confirmed via klayout across several `fold_dir`/`d_perp`
combinations (tried: both n_par_runs=1 with various direction pairings -
holes ranging 3-17 million um^2 every time; one branch at n_par_runs=1
with the other at 2 - still enclosed a hole). Only both at `n_par_runs=2`
passed cleanly. Unlike P2, which elongates cleanly against ITS neighbors
(P1 straight, P3 folded) - the specific combination of P3's long base
`stalk_length` (3781um, the largest of the 5) and its proximity to P4
seems to be what makes the single-run form risky specifically for this
pair, not a general rule against elongation.

**Remaining gap**: 430um (7.2%) over budget, driven by P3/P4's wider
2-run form. Closing it further would require either touching
`fan_rout`/`BRANCH_SCALES`/`FAN_ANGLE` (none of which Phase 1 is
authorized to change unilaterally - see Rev 6/7's own scope notes) or
accepting a real (klayout-confirmed) hole between P3 and P4 - geometric
correctness was prioritized over closing this last margin. Revisit if
Eddie wants to spend some of `BRANCH_SCALES`' pre-package headroom here,
or once Phase 2's real package model re-converges the scales anyway.

### 10.5 Build-time / Heidelberg-safety checks (this session)

Same technique as Rev 6 (klayout `Region` merge + hole-area report), run
directly against the real exported `DXF/filter_L60_CHIP_L60.gds` this
time (not a Python-side replay) - **note the GDS layer number for
BASEMETAL is 2**, not the `4` passed to `w.SetupLayers([['BASEMETAL',
4],...])` (that argument is an internal maskLib index; `gds_layer_number()`
remaps it - confirmed by cross-checking against `filter_L30.py`'s own GDS,
which shows the identical layer-2 mapping). Final build: 1 merged
polygon, 0 holes (threshold ~10um^2 noise floor), matching the printed
runtime report's own clearance table.

### 10.6 Known risks / caveats (Rev 7, supersedes sec 9 for current state)

- 430um/7.2% over `WIDTH_BUDGET_UM` (sec 10.4) - a real, open gap, not
  resolved this session. `PACKAGE_WALL_CLEARANCE_UM=500um` is still an
  ASSUMPTION pending the real package drawing (handoff open item O1) - if
  the real clearance is smaller, the budget (and this gap) improves for
  free; if larger, it gets worse.
- `SERIES_SECTIONS`' `zo` values (84.28ohm) are now STALE - synthesized at
  the old 125um width, not recomputed for the new `W_HIZ=70um` - real
  impedance re-derivation is Phase 2 (HFSS + package), same PLACEHOLDER
  caveat as every other electrical dimension here.
- P2's single-elongated-run form (n_par_runs=1) vs P3/P4's 2-run meander
  is an ASYMMETRIC fold topology across the filter - not yet checked
  whether this asymmetry has any electrical consequence (e.g. differing
  parasitic coupling profiles) beyond the geometric footprint difference
  it was chosen to solve; flag for Phase 2's HFSS pass.
- `BRANCH_SCALES`/`SCALE_SERIES` remain untouched pre-package placeholders
  (sec 10) - Phase 2's cavity walls will shift the whole response and
  re-converge these from scratch, so nothing about Rev 7's own geometry
  (including the open width-budget gap) should be read as tuned against
  real EM data yet.
- No HFSS bridge exists for L60 yet (same as Rev 6's own note) - would
  additionally need n_par_runs=1 replay support if built now (the
  existing single-run/2-run fold-kind dispatch pattern from
  `folded_branch_pair()` itself generalizes over `n_par_runs` already, so
  this is likely a non-issue, but unverified since no bridge exists to
  test it against).
- `filter_L30.py`/`filter_L45.py` untouched this session, per Phase 1's
  scope.

## 11. Rev 8 (2026-07-20): taper/fan seam fix, Phase 1 HFSS sanity run, bore/chip-width revision

**Taper/fan seam bug fixed** (Eddie flagged visually - the taper still
looked measurably narrower than the fan right at the seam corners, after
sec 10.3's sagitta-retreat fix already closed the gap at the fan's
*center*). Root cause and fix are documented in `guarded_fan_taper()`'s own
docstring (`filter_L60.py`) - short version: the retreated tip always lands
exactly `_FAN_TAPER_OVERLAP_BUFFER_UM` (20um) past the connector's own
start, independent of sagitta, but `_FAN_TAPER_STEP_LEN` (25um) was longer
than that buffer, so the fan's corners landed 5um inside the still-
narrowing taper. Fixed by clamping `taper_len` to finish at least 2um
before the tip, checked analytically for all 5 branches (P1 sagitta
81.8um, P2-P5 sagitta 40.9um, all landing at taper_len=18um vs tip_u=20um).
Re-verified via klayout: still 1 merged polygon, 0 holes.

**First real HFSS solve for L60** (`filter_L60_HFSS.py`, open-sim-volume
proxy-ground model, RUN_ANALYSIS=True): ran clean end to end after the
taper fix and after clearing two stale/duplicate `ansysedt.exe` desktop
processes left over from an earlier interrupted session (same class of
issue as the duplicate-*project* problem CLAUDE.md documents, one level up
- two whole separate desktop instances, not just two project handles
within one). Response is NOT yet a converged 3.5GHz-cutoff/60dB-floor
filter (deep S11 nulls near 2.8/5.4GHz, S21 rolloff from ~6.7GHz, stopband
bottoming near -73dB at 7.4GHz then rising back to roughly -25 to -40dB by
10-12GHz) - expected, since `BRANCH_SCALES`/`SCALE_SERIES` are still the
pre-package 1.40 placeholder (sec 4/10.6). This run's purpose was only to
confirm the corrected geometry solves cleanly, which it did - not a tuning
result, don't read cutoff/floor numbers from it.

**Bore diameter and chip width revised** (Eddie, ahead of Phase 2
planning): `PACKAGE_BORE_DIAMETER_UM` 6.985mm -> 7.0mm (a clean round
number), paired with the chip's own usable width narrowing 7.0mm -> 6.9mm
(`m.Wafer(...)` call). Deliberate pairing, not independent tweaks: a
6.9mm-wide, mid-thickness-centered 500um-thick chip has corner-to-bore-axis
distance `sqrt(3450^2 + 250^2) = 3459.3um`, just inside the new 3500um bore
radius (40.7um clearance at the corners - the binding point for a
rectangle inscribed near a circle, since corners are always a rectangle's
farthest points from center). **This means the chip's cross-section now
fits entirely inside the round bore with no mounting pocket needed** -
removes handoff item O1's pocket-geometry dependency from the Phase 2
*simulation* specifically (the real mechanical mounting/slot question may
still be physically open, but the sim no longer needs to model a wall
cutout for it). `WIDTH_BUDGET_UM` is derived (not hardcoded), so this
propagated automatically to 6000um (was 5985um) - realized transverse
width is still 6415um, so the sec 10.4 over-budget gap is essentially
unchanged (~415um now vs ~430um before) and still open, not reopened by
this revision. Re-verified: `filter_L60.py` runs clean (chip now
7100x40200um, usable 6900x40000um), klayout still reports 1 merged
polygon / 0 holes.

**Phase 2 (Al cavity package HFSS model) built and solved** - see
`filter_L60_package_HFSS.py` (new file, sibling to `filter_L60_HFSS.py`,
not an in-place edit). Cylindrical bore (radius 3500um, PEC walls via one
whole-object PerfectE assignment), chip mid-thickness on the bore axis, NO
mounting pocket (see Context above - the 6.9mm/7.0mm pairing makes this
unnecessary), lumped ports from each trace vertically to the bore wall
(handoff option (a), ~3.25mm integration line - flagged as not the
final-fidelity answer, see the script's own docstring). Geometry-only
smoke test passed cleanly first (fresh COM connection confirmed: 3 real
solids - metal/BoreVacuum/Substrate, 0 Unclassified; 2 PerfectE
boundaries; 2 Lumped Port excitations, `P1:1`/`P2:1`) before committing to
the real solve.

**Results (0.5-13GHz sweep, `HFSS/filter_L60_package_S21.csv`/`.png`)**:
solve completed cleanly, but the response is NOT yet a converged
3.5GHz-cutoff/60dB-floor filter - fully expected, exactly per the doc's
own prediction ("walls at ~3.5mm are a much closer ground reference...
the whole response shifts... do not chase pre-package tuning targets").
Specifics, checked against the doc's own acceptance/logging items:
- **4.5GHz attenuation: -0.07dB** (essentially none - still in-passband
  behavior at this frequency in the real-package environment).
- **Passband (0.5-3.917GHz) is rough**, not flat: worst insertion loss
  -5.32dB at 3.32GHz, first -3dB crossing at just 0.785GHz then recovering
  (non-monotonic ripple) - a symptom of the pre-package placeholder scales
  meeting walls 3.5mm away, not a new bug.
- **P3 overtone**: a sharp, deep null at 11.44GHz (-81.2dB) - close to,
  just under, the ~11.5GHz target the impedance-contrast change (sec 10)
  was aiming for. But the response climbs right back to -13.6dB by
  11.91GHz and stays around -14dB through 12.6GHz - the overtone notch
  itself may have moved to roughly the right place, but the surrounding
  8-12GHz region does NOT meet the doc's "-30dB floor" protection-budget
  target (worst point: 11.91GHz at -13.56dB).
- **5.9GHz / 10.9GHz "needles"**: neither shows up as a sharp isolated
  feature in this run (5.9GHz: -0.52dB, still near-passband; 10.9GHz:
  -35.34dB, reasonably suppressed) - but this can't be read as a clean
  "vanished vs. persisted" verdict against the doc's own reference, since
  no CSV/data from THAT original pre-Rev-7 diagnostic run exists to compare
  against directly (only this session's own two runs are on hand: the
  open-volume proxy-ground sim from earlier tonight showed -4.90dB /
  -38.85dB at the same two points respectively - similarly unremarkable,
  no sharp needle in either sim at either frequency).
- Other nulls found: 7.63GHz (-76.7dB), 9.52GHz (-99.5dB, the deepest).

**Bottom line**: Phase 2's package model itself is complete and verified
(geometry correct, solve clean, results extracted) - the results confirm
the doc's own prediction that `BRANCH_SCALES`/`SCALE_SERIES` need a real
re-convergence pass against the package now. That re-convergence is
explicitly NOT attempted here (would need real iteration, likely several
HFSS passes) - next step, pending Eddie's direction.
