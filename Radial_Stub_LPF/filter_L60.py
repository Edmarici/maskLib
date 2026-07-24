#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone radial-stub 10th-order elliptic lowpass filter (L60: fc=3.5GHz
passband edge/0.01dB ripple, stopband from 3.917GHz, 60dB equiripple floor -
equiripple in BOTH passband and stopband, unlike L30/L45's Chebyshev-II),
for the SNAIL beamsplitter pump/drive line's on-chip protection filtering -
third filter in this family, re-synthesized by Eddie for more attenuation
than L30 (8th order/30dB). Dimensions transcribed verbatim from a Nuhertz
Filter Solutions synthesis (microstrip/alumina model, Zo 84.28ohm/125um
main line, conductor 100nm - closer to our 120nm Al than prior syntheses'
300nm, no layout action needed) - see notebooks/L60_design_notes.md for the
full derivation.

REV 6: built directly on filter_L30.py's Rev 5 pattern (HFSS scale-factor
hooks + folded/meandered stalks + envelope clearance checks + runtime
dimension report) - see that file's own module docstring for the Rev 4->5
history this inherits. Self-contained (deliberately duplicated helpers, no
shared parameterization module - same convention as filter_L30.py/
filter_L45.py) - filter_L30.py/filter_L45.py are untouched.

One genuinely new piece vs filter_L30.py: a new "L-bend" fold variant
(l_bend_branch_pair() below) - a single 90-degree turn (exit run -> one
turn -> one run -> fan), NOT the multi-run meander filter_L30.py's P2/P3
use. Unlike the meander (which ends with an explicit exit turn so its fan
points TRANSVERSELY, away from the main line, per Eddie's own correction to
filter_L30.py's original design), the L-bend has NO exit turn, so its fan
ends up pointing AXIALLY (along the chip axis) instead. Built for P5 (short
stalk, unusually large fan) per this filter's own handoff doc, and used
there for the first build this session - then reverted back to a plain
straight branch per Eddie (fits comfortably under budget once P2/P3/P4 were
tuned, see notebooks/L60_design_notes.md sec 6). l_bend_branch_pair() stays
defined and available (verified working, not dead code) in case a future
width-budget squeeze makes it worth revisiting - no BRANCH_FOLDS entry uses
it in the current build.

6.9mm x 40mm bare (no backside metal) c-plane sapphire chip (Phase 2: revised
from 7.0mm so the chip's cross-section fits entirely inside the 7.0mm-
diameter Al cavity bore with no mounting pocket needed - see
PACKAGE_BORE_DIAMETER_UM below), 120nm Al, NO ground plane on-chip at all
(ground reference = the package tunnel walls around the chip, not modeled
here) - same positive-metal-draw convention as filter_L30.py (filled
polygons = aluminum directly, no XOR layer, no fill_basemetal_from_xor
step).

Every electrical dimension here is a PLACEHOLDER pending HFSS re-extraction,
same caveat as filter_L30.py/filter_L45.py. HFSS scale factors below
(SCALE_SERIES/BRANCH_SCALES) are seeded at 1.40/1.40 uniformly - NOT from
"filter_L30.py's converged values" (the handoff for this file asked for
that, but filter_L30.py has had exactly one real HFSS pass so far and is
explicitly not converged yet - see notebooks/L30_HFSS_notes.md sec 11 - so
there is nothing to seed from beyond its own first-pass starting guess).
Branch-pair interpretation (butterfly up/down at one junction), P1's
matching-branch stalk Zo, and branch ordering along the line are all
unverified against the original Nuhertz netlist (see notebooks/
L60_design_notes.md, items V1/V2/V3).

This session's scope is layout-only (mask + DXF/GDS + Heidelberg-safety
check) - no HFSS bridge/run for this file yet, matching filter_L30.py's own
Rev 5 layout-only pass (its HFSS bridge was rewritten in a separate later
session - see notebooks/L30_HFSS_notes.md sec 10-11).

REV 7 (PHASE 1 of a two-phase handoff - PHASE 2, adding the aluminum cavity
package to the HFSS sim, is Eddie-side and out of scope here): HFSS
diagnostics on the Rev 6 sim identified the 10.23GHz stopband peak as the
first overtone of the P3 branch pair (a stepped-impedance resonator whose
overtone-to-fundamental ratio grows with stalk/fan impedance contrast).
Raising that contrast - narrower high-Z lines (125um -> W_HIZ=70um, main
line + P2-P5 stalks; P1's matching stalk stays W_P1_STALK=250um, unchanged
role) and a wider fan angle (90deg -> FAN_ANGLE=115deg, all 5 branches,
P1's revertible independently) - shortens branches (helps the ~1.25x-high
cutoff) and pushes the overtone above ~11.5GHz, out of the protection band.
Separately, the real package bore is 7.0mm (PACKAGE_BORE_DIAMETER_UM - the
handoff's own stated 5.5mm was wrong, corrected live to 6.985mm, then
revised again to a clean 7.0mm alongside the chip's own 6.9mm width - see
that constant's own comment), which sets WIDTH_BUDGET_UM (derived, not
hardcoded - see that constant). One
geometry consequence: at the wider fan angle, the fan's own flush attach
chord (2*r_in*sin(angle/2)) no longer equals the (now narrower) stalk
width - fan_rin stays exactly as synthesized, and attach_width is
recomputed to the fan's true flush chord instead, so the stalk
deliberately flares/steps into the wider fan root (a normal positive-metal
T-junction, not a defect - confirmed visually in KLayout). branch_pair()/
folded_branch_pair()'s old stalk_width==attach_width assertion is gone
accordingly.

Fan orientation: folded branches' fans stay PERPENDICULAR to the main
microstrip line (unchanged from Rev 5/6) - folded_branch_pair() keeps its
90deg exit turn. An earlier pass of this revision tried making these fans
axial instead (misreading the handoff's width-budget language as
overriding this), which produces a visually collapsed loop rather than a
genuine back-and-forth zigzag and was reverted per Eddie's direct
correction. The "high inductance curl" for each branch is a real
multi-run meander (folded_branch_pair(), alternating bend handedness -
same two Rev 5 fixes as filter_L30.py: parallel runs must be axial not
transverse, and bend handedness must alternate or the path spirals into a
closed loop). BRANCH_SCALES/SCALE_SERIES are left at their Rev 6 values
(1.40/1.40 uniformly) - explicitly pre-package; Phase 2's cavity walls will
shift the whole response and re-converge these again, so no new
scale-tuning guesses belong in Phase 1.

Stalk-to-fan junction: at FAN_ANGLE=115deg, radial_fan()'s own CurveRect
annular sector has a CURVED inner boundary (radius fan_rin), not the flat
chord its attach_width matches - the arc bulges away from that chord by a
real sagitta (~41-82um depending on branch), confirmed visually as a
literal gap between the stalk and fan, not just a cosmetic flare.
guarded_fan_taper() draws a short connector at EXACTLY radial_fan()'s own
attach_width (not an arbitrarily widened stand-in), then RETREATS the
structure's position backward by the sagitta (Structure.translatePos(), no
drawing) before the fan attaches - so the fan's own reference point lands
INSIDE metal already drawn, guaranteeing real overlap instead of an
ever-receding tangent (two earlier attempts that only extended the
connector's LENGTH - even by a lot - had zero effect, since the sagitta
gap is intrinsic to the fan's own construction relative to wherever it's
placed, not something a longer approach run can close).

Per-branch fold treatment (final, KLayout-verified clean - 1 merged
polygon, 0 real holes): P1/P5 straight (branch_pair()) - P5's own
stalk_length is too short to fold at all under the _MIN_RUN_GAP_UM=400
floor (confirmed: even one U-turn's own arc cost plus the d_perp clearance
floor exceeds it). P2 uses a single elongated run (n_par_runs=1, flipped
per Eddie) - cuts its own turn overhead by a full bend_radius vs a 2-run
meander, and was the widest branch before this fix. P3 (flipped per Eddie)
and P4 use the standard 2-run meander (n_par_runs=2) - confirmed via
KLayout that this SPECIFIC pair cannot both use the single-run form
without enclosing a real hole between their folds and the main line
(tried multiple fold_dir/d_perp combinations), unlike P2 against its own
neighbors. Realized transverse width 6415.0um vs the (corrected) 5985um
budget - 430um/7.2% over, driven by P3/P4 needing the wider 2-run form -
geometric correctness prioritized over closing this last margin, which
would otherwise require touching fan_rout/BRANCH_SCALES (Phase 1 isn't
authorized to). See notebooks/L60_design_notes.md's Rev 7 section for the
full derivation, the dead-end axial-fan/L-bend/wide-taper attempts, and
the complete iteration log.
"""
import math

from dxfwrite import const
from dxfwrite import DXFEngine as dxf

import maskLib.MaskLib as m
from maskLib.microwaveLib import Strip_straight, Strip_taper, Strip_bend
from maskLib.Entities import CurveRect
from maskLib.gdsExport import dxf_to_gds
from maskLib.layerDoseTable import gds_layer_number

# ===============================================================================
# tunable constants
# ===============================================================================

# --- HFSS iteration knobs - dimensionless multipliers on the base tables
# below (SERIES_SECTIONS/BRANCH_PAIRS), which stay verbatim as the
# reference - tuning lives here, the base numbers are never overwritten.
# Widths (stalk/line width, fan Rin, attach_width) are NOT scaled.
#
# Seeded at 1.40/1.40 uniformly (NOT per-branch-differentiated): the
# handoff for this file asked to seed from "filter_L30.py's converged HFSS
# scales," but filter_L30.py has had exactly one real HFSS pass this
# session and is NOT converged (P4 already flagged there as likely needing
# a further correction - see notebooks/L30_HFSS_notes.md sec 11). Per the
# handoff's own stated fallback ("fall back to 1.40/1.40 if L30 has not
# converged"), every branch here starts at 1.40/1.40 - there's no valid
# physical reason to map L60's 5 branches onto L30's 4 by index, they are
# different branches on a different filter.
#
# Physics (same as filter_L30.py): zero freq ~ 1/sqrt(L*C); L ~ stalk
# length (linear); C ~ fan Rout^alpha, alpha in [1 (fringing-dominated, no
# ground plane), 2 (area-dominated)]. Expect 2-3 HFSS iterations per
# branch once real sim data exists, stalk scale for fine moves, fan scale
# for coarse moves.
#
# REV 7: left unchanged at 1.40/1.40 uniformly - explicitly PRE-PACKAGE
# values. Phase 2 adds the aluminum cavity package (walls at 2.75mm from
# the chip axis, a much closer ground reference than the open sim volume
# these were never even converged against) - that will shift the whole
# response and these scales will need to re-converge again from scratch.
# No new scale-tuning guesses belong here until Phase 2's package model
# exists; these are a Rev 6 carryover, not a Rev 7 result.
SCALE_SERIES = 1.40
BRANCH_SCALES = {
    # pair: (stalk_len_scale, fan_rout_scale)
    'P1': (1.40, 1.40),
    'P2': (1.40, 1.40),
    'P3': (1.40, 1.40),
    'P4': (1.40, 1.40),
    'P5': (1.40, 1.40),
}

# REV 7: impedance-contrast constants (10.23GHz P3-overtone diagnosis - see
# module docstring). W_HIZ replaces the old flat 125um high-Z line width for
# the main-line series sections AND branch stalks P2-P5. P1's matching
# branch keeps its own distinct (unchanged) stalk width - its role is
# passband match, not stopband, so it's not part of the impedance-contrast
# change. FAN_ANGLE replaces the old flat 90deg fan included angle for ALL
# 5 branches (P1 included this time, per the handoff - flagged as
# independently revertible if HFSS shows P1's match degrading).
W_HIZ = 70.0        # um, new high-Z line width (main line + P2-P5 stalks)
W_P1_STALK = 250.0  # um, P1's own distinct matching-branch stalk width (unchanged)
FAN_ANGLE = 115.0   # deg, new fan included angle, all branches (P1 revertible)

# REV 7: the handoff's own bore figure (5.5mm) was WRONG - Eddie corrected
# it mid-session to 6.985mm, then (Phase 2 planning session) revised again
# to a clean 7.0mm - paired with the chip's own usable width narrowing to
# 6.9mm (below) so the chip's cross-section fits entirely inside the round
# bore with no mounting pocket needed (see notebooks/L60_design_notes.md's
# Phase 2 section for the corner-clearance derivation: 40.7um margin at the
# tightest point, the chip corners). WIDTH_BUDGET_UM below is derived from
# PACKAGE_BORE_DIAMETER_UM/PACKAGE_WALL_CLEARANCE_UM (=
# 2*(PACKAGE_BORE_DIAMETER_UM/2 - PACKAGE_WALL_CLEARANCE_UM), see the
# runtime report's bore-margin line) rather than hardcoded, so bore-diameter
# corrections propagate automatically. PACKAGE_WALL_CLEARANCE_UM is still a
# 500um ASSUMPTION pending the real package drawing (handoff open question
# O1) - informational only, not itself a hard check.
PACKAGE_BORE_DIAMETER_UM = 7000.0    # um (revised from 6.985mm to a clean 7.0mm)
PACKAGE_WALL_CLEARANCE_UM = 500.0    # um, ASSUMED pending O1 (package drawing)

# Folded (meandered) / L-bend stalk geometry. fold=False+no l_bend keeps a
# straight stalk (P1 - 280um scaled, short enough as-is). fold=True selects
# the multi-run meander (folded_branch_pair(), unchanged from
# filter_L30.py's Rev 5 - see that function's own docstring for the full
# derivation: perpendicular exit -> 90deg entrance turn -> alternating
# 180deg internal bends+runs -> 90deg exit turn -> fan, fan ends up
# TRANSVERSE/outward). l_bend=True (P5 only) selects the new single-turn
# variant (l_bend_branch_pair() below): perpendicular exit -> ONE 90deg
# turn -> one run -> fan, NO exit turn, so the fan ends up AXIAL (along the
# chip axis) instead - a distinct, deliberate choice for this specific
# short-stalk/big-fan branch, per this filter's own handoff doc ("fan
# oriented along the chip axis... outboard-axial").
#
# d_perp=1200um / run_gap=500um below are the handoff's own suggested
# STARTING values - these are filter_L30.py's ORIGINAL pre-tuning numbers,
# not what filter_L30.py actually converged to after real DXF-rendering
# iteration this session (that ended up at d_perp=625um - the true
# clearance-rule floor - and run_gap=300um, after several empirical
# rounds - see notebooks/L30_design_notes.md sec 12.5). Starting from the
# handoff's given values per its explicit instructions; L30's own
# battle-tested values are the fallback reference if this file's own
# iteration hits the same width-budget pressure L30 did (likely, since 5
# branches now share the same unchanged 6500um budget instead of 4).
#
# P5's bend_radius=212.5um is NOT specified by the handoff (the L-bend has
# no second parallel run to space against, so run_gap/n_par_runs don't
# apply - it needs its own bend_radius directly) - started at 212.5um,
# matching filter_L30.py's own actually-converged bend radius
# (run_gap=300,w=125 -> (300+125)/2=212.5), flagged as a starting guess.
# The handoff explicitly allows falling back to a plain straight P5
# (already fits under budget per its own sanity check) if the L-bend's
# clearances don't work out.
#
# REV 7 dead end (kept as a record, not a live decision): the handoff's own
# stated 4500um budget (from its wrong 5.5mm bore figure) made every
# large-fan branch's transverse bulge alone dominate the budget, which led
# to two bad detours - (1) trying to shrink transverse cost by dropping
# folded_branch_pair()'s exit turn so fans point axially instead of
# perpendicular to the microstrip, and (2) switching to
# l_bend_branch_pair() (single-turn, no exit turn) to minimize overhead
# further. Both were reverted per Eddie's live correction: fans MUST stay
# perpendicular to the microstrip (folded_branch_pair()'s exit turn is not
# optional), and the "curl" needs to be a genuine back-and-forth zigzag,
# not a single compressed turn - see notebooks/L60_design_notes.md's Rev 7
# section for the full story. Eddie also corrected the bore diameter to
# 6.985mm (not 5.5mm) mid-session, which resolves the width pressure that
# motivated the detour in the first place - WIDTH_BUDGET_UM comes out to
# 5985um now, close to Rev 6's own 6500um budget under the OLD (correct)
# transverse-fan convention.
#
# d_perp=625um / run_gap=400um (the _MIN_RUN_GAP_UM floor - narrower
# W_HIZ=70um stalks still need the same self-coupling margin) for P2-P4;
# fold_dir signs carried over from Rev 6's own converged choices (verified
# against a rendered DXF then, not re-guessed here). P5 tried straight
# first (branch_pair()) since a transverse fan's max reach is ~fan_rout
# regardless of FAN_ANGLE (the wider angle mostly adds AXIAL spread, not
# transverse - unlike the axial-fan case) - fits under the corrected
# budget without folding.
BRANCH_FOLDS = {
    'P1': dict(fold=False),
    # P2 flipped (fold_dir -1, away from P1/P3) and elongated (n_par_runs=1
    # - a single longer run instead of two short ones + an internal bend)
    # per Eddie's direct correction - the two-run version's own turn
    # overhead (entrance+internal+exit, 3 bend_radius-scaled turns) was the
    # widest branch in the filter (6969.8um alone); a single run trades
    # that extra turn for more axial length instead, cutting transverse
    # cost by roughly one bend_radius per side.
    'P2': dict(fold=True, d_perp=575.0, n_par_runs=1, run_gap=400.0, fold_dir=-1),
    # P3<->P4 specifically cannot tolerate n_par_runs=1 (a single long run)
    # on EITHER side without enclosing a real hole between them and the
    # main line - confirmed via klayout across several fold_dir/d_perp
    # combinations (both branches must use the shorter n_par_runs=2 runs
    # for a clean, hole-free result here) - unlike P2, which elongates
    # cleanly against its own neighbors. Costs width (P3/P4 end up the
    # widest branches, driving the filter ~430um over budget) but this is
    # the only combination that passed the definitive klayout check (1
    # merged polygon, 0 real holes) - geometric correctness over budget
    # here; see notebooks/L60_design_notes.md for the still-open gap.
    'P3': dict(fold=True, d_perp=575.0, n_par_runs=2, run_gap=400.0, fold_dir=-1),
    'P4': dict(fold=True, d_perp=575.0, n_par_runs=2, run_gap=400.0, fold_dir=-1),
    # P5's own stalk_length (1131.6um scaled) is too short to fold at all
    # under the _MIN_RUN_GAP_UM=400 floor: even a single U-turn's own arc
    # cost (pi*bend_radius=738.3um at bend_radius=235) plus the d_perp
    # clearance floor (~570um) already exceeds 1131.6um before any run
    # length is left - confirmed by a real ValueError (negative run_length)
    # when tried. P5 stays straight (branch_pair()) - not a choice, a
    # structural necessity given the run_gap floor.
    'P5': dict(fold=False),
}

# DWL 66+ rejects single-vertex/zero-length PATH elements (CLAUDE.md). Every
# length in the tables below is real/nonzero, so this should never actually
# fire - it's a guard against future edits introducing a degenerate segment,
# not a live code path.
_MIN_LEN = 0.5  # um

# Apex/bend-radius Heidelberg-safety guard - analogous to _MIN_LEN but for
# radii (fan_rin, folded/L-bend bend radius) rather than lengths.
_MIN_RADIUS_UM = 5.0  # um

# REV 7: explicit run_gap floor for folded branches - narrower W_HIZ=70um
# lines are higher-Z, and mutual coupling between adjacent parallel runs
# matters relatively more even though the line-width-relative rule
# (run_gap >= 4x width) would technically permit run_gap as low as 280um
# now. Enforced in folded_branch_pair(), independent of the 4x-width rule.
_MIN_RUN_GAP_UM = 400.0  # um

# um, transverse hard budget - REV 7: driven by the real package bore (was
# 6500um, an assumption predating the bore spec) - DERIVED from
# PACKAGE_BORE_DIAMETER_UM/PACKAGE_WALL_CLEARANCE_UM above (not hardcoded)
# so a bore-diameter correction propagates automatically - see the runtime
# report's bore-margin line.
WIDTH_BUDGET_UM = 2 * (PACKAGE_BORE_DIAMETER_UM / 2 - PACKAGE_WALL_CLEARANCE_UM)

METAL_LAYER = 'BASEMETAL'
MARKER_LAYER = 'MARKERS'

# ===============================================================================
# dimension tables - transcribed verbatim (Nuhertz Filter Solutions synthesis,
# 2026-07-19, 10th order elliptic, fc=3.500GHz/0.01dB ripple, stopband from
# 3.917GHz, 60dB floor). See notebooks/L60_design_notes.md items V1/V2/V3 for
# open verification items (transcribed from screenshots, ordering/ P1 Zo
# unconfirmed against the original Nuhertz netlist).
# ===============================================================================

# Main-line series sections, input -> output. Zo=84.28ohm was synthesized
# at the original 125um width - REV 7 narrows width to W_HIZ=70um for the
# impedance-contrast change (module docstring); 'zo' below is now STALE
# (the physical impedance at 70um is higher, not yet recomputed) - real
# electrical re-derivation is Phase 2 (HFSS + package), same PLACEHOLDER
# caveat as every other electrical dimension in this file.
SERIES_SECTIONS = [
    {'length': 3934.0, 'width': W_HIZ, 'zo': 84.28},   # S1
    {'length': 3322.0, 'width': W_HIZ, 'zo': 84.28},   # S2
    {'length': 2941.0, 'width': W_HIZ, 'zo': 84.28},   # S3
    {'length': 4122.0, 'width': W_HIZ, 'zo': 84.28},   # S4
    {'length': 1948.0, 'width': W_HIZ, 'zo': 84.28},   # S5
]

def _flush_attach_width(r_in, angle_deg):
    """The fan's own natural flush attach-chord width (2*r_in*sin(angle/2))
    - shared by BRANCH_PAIRS's construction below AND radial_fan()'s own
    consistency check (defined later in this file), so the two can never
    silently drift apart. REV 7: at FAN_ANGLE=115deg (vs the old 90deg),
    this no longer equals any of this file's stalk widths - see module
    docstring's "flared junction" note."""
    return 2 * r_in * math.sin(math.radians(angle_deg) / 2)


# Shunt branch pairs (each row = one butterfly pair: two mirrored branches,
# +y and -y off the main line at that junction). P1 sits before S1; Pn sits
# between S(n-1) and Sn. attach_width is the fan's inner-arc chord width (see
# radial_fan below) - it is numerically equal to stalk_width in every row
# here, but is a geometrically distinct quantity (see filter_L30.py's own
# notebooks/L30_design_notes.md, "attach_width vs stalk_width").
#
# Note the elliptic zero clustering (P3 4.471GHz, P4 4.752GHz, P2 5.491GHz)
# just above the 3.5GHz cutoff - that's what buys the steep 3.5->3.917GHz
# skirt at 60dB (vs. L30's more spread-out zeros). P1's matching fan is
# much larger than L30/L45's (1.108mm vs ~0.4-0.6mm) - not a transcription
# error, don't "simplify" it down.
# REV 7: attach_width is now the fan's own flush chord at FAN_ANGLE=115deg
# (_flush_attach_width() above), NOT the stalk width - stalk_width and
# attach_width deliberately differ now (P1: 250 vs ~298.17; P2-P5: 70 vs
# ~149.07), producing a flared stalk-to-fan junction (module docstring).
# fan_rin/fan_rout are unchanged from Rev 6 (handoff: "Fan Rin... unchanged").
BRANCH_PAIRS = [
    {'name': 'P1', 'stalk_length': 200.0, 'stalk_width': W_P1_STALK, 'stalk_zo': 66.54,
     'fan_rout': 1108.0, 'fan_rin': 176.8, 'fan_angle': FAN_ANGLE,
     'attach_width': _flush_attach_width(176.8, FAN_ANGLE),
     'zero_label': 'matching element, ~456 GHz'},
    {'name': 'P2', 'stalk_length': 2010.0, 'stalk_width': W_HIZ, 'stalk_zo': None,
     'fan_rout': 1398.0, 'fan_rin': 88.39, 'fan_angle': FAN_ANGLE,
     'attach_width': _flush_attach_width(88.39, FAN_ANGLE),
     'zero_label': '5.491 GHz'},
    {'name': 'P3', 'stalk_length': 3781.0, 'stalk_width': W_HIZ, 'stalk_zo': None,
     'fan_rout': 1132.0, 'fan_rin': 88.39, 'fan_angle': FAN_ANGLE,
     'attach_width': _flush_attach_width(88.39, FAN_ANGLE),
     'zero_label': '4.471 GHz'},
    {'name': 'P4', 'stalk_length': 3137.0, 'stalk_width': W_HIZ, 'stalk_zo': None,
     'fan_rout': 1229.0, 'fan_rin': 88.39, 'fan_angle': FAN_ANGLE,
     'attach_width': _flush_attach_width(88.39, FAN_ANGLE),
     'zero_label': '4.752 GHz'},
    {'name': 'P5', 'stalk_length': 808.3, 'stalk_width': W_HIZ, 'stalk_zo': None,
     'fan_rout': 1474.0, 'fan_rin': 88.39, 'fan_angle': FAN_ANGLE,
     'attach_width': _flush_attach_width(88.39, FAN_ANGLE),
     'zero_label': '7.679 GHz'},
]

assert len(BRANCH_PAIRS) == len(SERIES_SECTIONS), 'one branch pair per series section, by construction'

# Input pin pad (Axline-style capacitive pin above an on-chip pad). "1000 x
# 1500 um" per the handoff doc, read as width(transverse) x length(axial) to
# match the chip's own width x height convention - PROVISIONAL, not derived
# from a package drawing (same as filter_L30.py).
PIN_PAD_WIDTH = 1000.0
PIN_PAD_LENGTH = 1500.0
PAD_EDGE_MARGIN = 5000.0    # um, pad's outer (chip-edge-facing) edge from the input edge
INOUT_TAPER_LEN = 500.0     # um, standard taper length (both ends)
OUTPUT_LINE_WIDTH = 200.0   # um
KEEPOUT_CLEARANCE = 1000.0  # um, output line stops 1mm short of the SNAIL keep-out

# SNAIL + capacitive-pad keep-out (dummy marker, not real geometry). Same
# orientation/values as filter_L30.py (3mm transverse x 5mm axial).
SNAIL_KEEPOUT_W = 3000.0
SNAIL_KEEPOUT_H = 5000.0
SNAIL_KEEPOUT_CY = 4000.0

DEFAULTS = {'w': 125.0, 'radius': 300.0}


# ===============================================================================
# local helpers - deliberately duplicated from filter_L30.py (no shared
# parameterization module yet; see module docstring)
# ===============================================================================

def _corners(start, direction_deg, length, w0, w1):
    """Global corners of a (possibly tapered) rectangle, for envelope/clearance
    bookkeeping only - does not draw anything."""
    d = math.radians(direction_deg)
    fwd = (math.cos(d), math.sin(d))
    perp = (math.cos(d + math.pi / 2), math.sin(d + math.pi / 2))
    end = (start[0] + length * fwd[0], start[1] + length * fwd[1])
    return [
        (start[0] + (w0 / 2) * perp[0], start[1] + (w0 / 2) * perp[1]),
        (start[0] - (w0 / 2) * perp[0], start[1] - (w0 / 2) * perp[1]),
        (end[0] + (w1 / 2) * perp[0], end[1] + (w1 / 2) * perp[1]),
        (end[0] - (w1 / 2) * perp[0], end[1] - (w1 / 2) * perp[1]),
    ]


def guarded_straight(chip, structure, length, w, layer, label=''):
    """Strip_straight (positive-metal rectangle), guarded against DWL 66+
    degenerate (near-zero-length) paths. Returns global corner points."""
    if length is None or length < _MIN_LEN:
        raise ValueError('%s: degenerate length %r um (DWL 66+ forbids zero-length paths)' % (label, length))
    pts = _corners(structure.start, structure.direction, length, w, w)
    Strip_straight(chip, structure, length, w=w, layer=layer)
    return pts


def guarded_taper(chip, structure, length, w0, w1, layer, label=''):
    """Strip_taper (positive-metal trapezoid), guarded against DWL 66+
    degenerate (near-zero-length) paths. Returns global corner points."""
    if length is None or length < _MIN_LEN:
        raise ValueError('%s: degenerate length %r um (DWL 66+ forbids zero-length paths)' % (label, length))
    pts = _corners(structure.start, structure.direction, length, w0, w1)
    Strip_taper(chip, structure, length=length, w0=w0, w1=w1, layer=layer)
    Strip_straight(chip, structure, length=2 * length, w=w1, layer=layer)
    return pts


_FAN_TAPER_STEP_LEN = 25.0  # um - see guarded_fan_taper()'s docstring
_FAN_TAPER_OVERLAP_BUFFER_UM = 20.0  # um - see guarded_fan_taper()'s docstring


def guarded_fan_taper(chip, structure, w0, w1, r_in, fan_angle_deg, layer, label=''):
    """REV 7: bridges stalk_width (w0) -> radial_fan()'s attach_width (w1)
    before the fan attaches, AND overlaps the fan's own sagitta gap - the
    gap between a FLAT taper end and radial_fan()'s CURVED inner boundary
    (a CurveRect annular sector's true inner edge is an ARC of radius
    r_in, which bulges AWAY from the flush attach-chord by
    r_in*(1-cos(angle/2)) at the sweep's center, zero at the two corners).

    Two earlier attempts both failed, for the SAME underlying reason once
    understood: extending this function's own drawn LENGTH (even by a lot -
    tried both a small sagitta-based margin and, when that left a small but
    real residual hole confirmed via klayout AND visually - Eddie: "our
    block is... starting on the outside... We want the taper to stop at
    the beginning of the fan and the rect to extend into the fan" - the
    much larger r_in itself) had ZERO effect on the resulting gap, because
    the sagitta offset is INTRINSIC to radial_fan()'s own construction
    RELATIVE TO WHEREVER `structure.start` sits when it's called - pushing
    that reference point further away just moves the whole fan (and its
    own unchanged internal sagitta gap) further away too, never closing it.

    The actual fix: draw a short connector (taper + straight run, ample
    length for a clean visual transition) at EXACTLY w1 (radial_fan()'s own
    attach_width - the fan's real end width, not an arbitrarily widened
    stand-in), then RETREAT the structure's own position backward
    (Structure.translatePos(), no drawing) by the sagitta - a small buffer,
    so radial_fan()'s own `tip` reference lands INSIDE the metal already
    drawn here, guaranteeing real overlap with the fan's near-boundary
    instead of an ever-receding tangent point. The taper's own wide end
    still lands exactly at the fan's own attach point once the run
    completes - this is a connector INTO the fan, not a replacement for
    part of it. Guarded against DWL 66+ degenerate lengths.

    Third bug, found after the sagitta-retreat fix above was already
    visually confirmed closing the arc gap at the fan's CENTER: a residual
    few-um gap remained specifically at the fan's CORNERS (where the near
    boundary is the flat chord, not the arc, and needs the FULL w1 width
    immediately). retreat/run_len are built so the retreated tip always
    lands exactly `_FAN_TAPER_OVERLAP_BUFFER_UM` past this run's own start,
    independent of sagitta (run_len - retreat == buffer, always) - but the
    taper itself was allowed to run up to `_FAN_TAPER_STEP_LEN` (25um),
    longer than that buffer (20um). So the tip (and the fan's corners,
    which sit at that exact position) landed 5um inside the still-
    narrowing taper, before it reached full w1 - the taper was measurably
    narrower than the fan right at the seam. Fixed by capping taper_len to
    finish strictly before the retreat point, not just at its own nominal
    length.
    """
    sagitta = r_in * (1 - math.cos(math.radians(fan_angle_deg)/2))
    retreat = sagitta + _FAN_TAPER_OVERLAP_BUFFER_UM
    run_len = retreat + _FAN_TAPER_OVERLAP_BUFFER_UM  # drawn metal must reach past the retreat point

    # The retreated tip sits at exactly _FAN_TAPER_OVERLAP_BUFFER_UM past
    # this run's own start (run_len - retreat == buffer, always - see above)
    # - the taper MUST reach full w1 at or before that point, or the fan's
    # corners land inside the still-narrowing taper. Clamped here
    # structurally (not just via the nominal _FAN_TAPER_STEP_LEN constant)
    # so a future edit to either constant can't silently reintroduce the gap.
    taper_len = min(_FAN_TAPER_STEP_LEN, run_len, _FAN_TAPER_OVERLAP_BUFFER_UM ) #taken away 2 micron subtraction from overlap buffer
    if taper_len < _MIN_LEN:
        raise ValueError('%s: degenerate fan-taper length %r um' % (label, taper_len))
    pts = _corners(structure.start, structure.direction, taper_len, w0, w1)
    Strip_taper(chip, structure, length=taper_len, w0=w0, w1=w1, layer=layer)
    remaining = run_len - taper_len
    if remaining >= _MIN_LEN:
        pts += guarded_straight(chip, structure, remaining, w1, layer,
                                 label='%s fan_taper_run' % label)
    structure.translatePos(vector=(-retreat, 0))
    return pts


def guarded_bend(chip, structure, angle, CCW, w, radius, layer, label=''):
    """Strip_bend (positive-metal U-turn via CurveRect, ralign=valign=MIDDLE -
    i.e. `radius` is the trace CENTERLINE radius, `w` is the trace width) -
    the positive-metal analog of CPW_bend, unchanged from filter_L30.py's
    Rev 5 (see that file's own docstring for the full derivation/rationale).

    Calls the real Strip_bend for drawing + structure position/direction
    update (true reuse, not reimplemented), and separately builds an
    un-added CurveRect with IDENTICAL parameters purely to extract its
    discretized .points for envelope/clearance bookkeeping - same
    point-capture idiom radial_fan() uses for the fans.

    Guarded against DWL 66+ degenerate (near-zero) radius, plus the
    apex/bend-radius guard (_MIN_RADIUS_UM).
    """
    if radius is None or radius < _MIN_RADIUS_UM:
        raise ValueError('%s: bend radius %r um below the %.1fum apex guard (DWL 66+/Heidelberg safety)'
                          % (label, radius, _MIN_RADIUS_UM))
    bookkeeping = CurveRect(structure.start, w, radius, angle=angle, ptDensity=120,
                             ralign=const.MIDDLE, valign=const.MIDDLE,
                             rotation=structure.direction, vflip=not CCW)
    bookkeeping._build()
    pts = list(bookkeeping.points)
    Strip_bend(chip, structure, angle=angle, CCW=CCW, w=w, radius=radius, ptDensity=120, layer=layer)
    return pts


def radial_fan(chip, structure, r_out, r_in, fan_angle_deg, attach_width, layer, label=''):
    """
    Draws one filled annular-sector fan (CurveRect, rmin=r_in>0 branch) at the
    tip of `structure`, angularly centered on structure.direction. Unchanged
    from filter_L30.py's Rev 5 - see that file's own docstring for the full
    insert/rotation derivation.

    REV 7: added the r_in apex-guard check (previously missing here, unlike
    guarded_bend()'s equivalent radius guard) per the handoff's explicit
    "keep the r_inner >= 5um apex guard" instruction for the wider
    FAN_ANGLE - doesn't fire at this file's current r_in values (88.39/
    176.8um) but is a real guard now, not just a restated comment.
    """
    if r_in < _MIN_RADIUS_UM:
        raise ValueError('%s: fan r_in %.2f um below the %.1fum apex guard (DWL 66+/Heidelberg safety)'
                          % (label, r_in, _MIN_RADIUS_UM))
    expected_attach = _flush_attach_width(r_in, fan_angle_deg)
    if abs(expected_attach - attach_width) > 0.5:
        print('\x1b[33m%s: attach_width %.2f does not match 2*r_in*sin(angle/2)=%.2f '
              '(fan will not sit perfectly flush against the stalk)\x1b[0m'
              % (label, attach_width, expected_attach))
    S = structure.direction
    tip = structure.start
    perp = (math.cos(math.radians(S + 90)), math.sin(math.radians(S + 90)))
    insert = (tip[0] + (attach_width / 2) * perp[0], tip[1] + (attach_width / 2) * perp[1])
    rotation = S + fan_angle_deg / 2 - 90
    cr = CurveRect(insert, height=r_out - r_in, radius=r_in, angle=fan_angle_deg, rotation=rotation,
                    ralign=const.BOTTOM, ptDensity=120, bgcolor=chip.wafer.bg(), layer=layer)
    chip.add(cr)
    cr._build()  # force point computation now (pure fn of ctor args - safe/idempotent) for bookkeeping
    return list(cr.points)


def branch_pair(chip, s_main, spec, layer, label=''):
    """
    Draws one symmetric butterfly pair of STRAIGHT shunt branches (stalk +
    radial fan) off s_main's CURRENT position - unchanged from
    filter_L30.py's Rev 5 branch_pair(). Does NOT mutate s_main (spawns via
    cloneAlong).

    Returns {'+': [...], '-': [...]}, the global vertex lists (stalk corners
    + fan polygon) for each side, for the bbox/clearance summary.

    REV 7: stalk_width no longer needs to equal attach_width (dropped the
    old flush-junction assertion) - at the wider FAN_ANGLE, the fan's own
    flush chord naturally exceeds this file's (now narrower) stalk widths.
    A guarded_fan_taper() bridges stalk_width -> attach_width AND the fan's
    own sagitta gap (see that function's docstring - confirmed visually as
    a real gap, not just a flare, without it) before the fan attaches.
    """
    verts = {}
    for sign, key in ((+1, '+'), (-1, '-')):
        s_b = s_main.cloneAlong(vector=(0, 0), newDirection=sign * 90)
        stalk_pts = guarded_straight(chip, s_b, spec['stalk_length'], spec['stalk_width'], layer,
                                      label='%s%s stalk' % (label, key))
        taper_pts = guarded_fan_taper(chip, s_b, spec['stalk_width'], spec['attach_width'],
                                       spec['fan_rin'], spec['fan_angle'], layer,
                                       label='%s%s fan_taper' % (label, key))
        fan_pts = radial_fan(chip, s_b, spec['fan_rout'], spec['fan_rin'], spec['fan_angle'],
                              spec['attach_width'], layer, label='%s%s fan' % (label, key))
        verts[key] = stalk_pts + taper_pts + fan_pts
    return verts


def folded_branch_pair(chip, s_main, spec, fold_params, layer, label=''):
    """
    Draws one symmetric butterfly pair of FOLDED (meandered) shunt branches:
    perpendicular exit run -> 90deg entrance turn (into axial) -> alternating
    180deg internal bends+runs -> 90deg exit turn (back to transverse) ->
    fan, PERPENDICULAR to the main microstrip line (pointing away from it),
    not axial. Unchanged from filter_L30.py's Rev 5 folded_branch_pair() -
    see that file's own docstring for the full derivation, including the
    two bugs found/fixed there (parallel runs must be axial not transverse,
    or the meander doesn't add length; bend handedness must alternate, not
    repeat, or the path spirals into a closed loop/"circle" instead of a
    genuine back-and-forth zigzag) - both fixes retained here.

    REV 7 correction: an earlier pass of this file's own Rev 7 change
    dropped this exit turn, making fans axial instead, per the impedance-
    contrast handoff's own (mistaken) width-budget reasoning. Eddie
    corrected this live: the fan must stay perpendicular to the microstrip,
    which requires exactly this 90deg turn at the end of the high-Z line -
    reverted back to the original transverse-fan behavior. The exit turn is
    NOT optional for this design. Also enforces _MIN_RUN_GAP_UM
    (independent of the 4x-linewidth rule) - see that constant's own
    comment.

    Returns {'+': [...], '-': [...]}, plus (run_length, bend_radius) for the
    printed report.
    """
    d_perp = fold_params['d_perp']
    n_par_runs = fold_params['n_par_runs']
    run_gap = fold_params['run_gap']
    if run_gap < _MIN_RUN_GAP_UM:
        raise ValueError('%s: run_gap %.2f um below the %.1fum self-coupling margin floor'
                          % (label, run_gap, _MIN_RUN_GAP_UM))
    CCW = fold_params['fold_dir'] > 0
    w = spec['stalk_width']
    bend_radius = (run_gap + w) / 2
    if bend_radius < _MIN_RADIUS_UM:
        raise ValueError('%s: bend radius %.2f um below the %.1fum apex guard'
                          % (label, bend_radius, _MIN_RADIUS_UM))

    n_bends = n_par_runs - 1
    # Entrance turn (90deg) + n_bends internal 180deg turns + exit turn
    # (90deg) = (n_bends+1) full 180deg-turn-lengths' worth of arc.
    turn_arc_len = math.pi * bend_radius * (n_bends + 1)
    run_length = (spec['stalk_length'] - d_perp - turn_arc_len) / n_par_runs
    if run_length < _MIN_LEN:
        raise ValueError('%s: folded run length %.2f um is degenerate/negative - d_perp too large '
                          'or too many parallel runs for this (scaled) stalk_length=%.1fum'
                          % (label, run_length, spec['stalk_length']))

    verts = {}
    for sign, key in ((+1, '+'), (-1, '-')):
        side_CCW = CCW if sign > 0 else not CCW  # mirror reflection flips handedness
        s_b = s_main.cloneAlong(vector=(0, 0), newDirection=sign * 90)
        pts = guarded_straight(chip, s_b, d_perp, w, layer, label='%s%s exit' % (label, key))
        turn_CCW = side_CCW
        pts += guarded_bend(chip, s_b, 90, turn_CCW, w, bend_radius, layer,
                             label='%s%s entrance turn' % (label, key))
        pts += guarded_straight(chip, s_b, run_length, w, layer, label='%s%s run1' % (label, key))
        for i in range(n_bends):
            turn_CCW = not turn_CCW
            pts += guarded_bend(chip, s_b, 180, turn_CCW, w, bend_radius, layer,
                                 label='%s%s bend%d' % (label, key, i + 1))
            pts += guarded_straight(chip, s_b, run_length, w, layer,
                                     label='%s%s run%d' % (label, key, i + 2))
        turn_CCW = not turn_CCW
        pts += guarded_bend(chip, s_b, 90, turn_CCW, w, bend_radius, layer,
                             label='%s%s exit turn' % (label, key))
        # REV 7: bridges stalk_width -> attach_width AND the fan's own
        # sagitta gap - see guarded_fan_taper()'s docstring.
        pts += guarded_fan_taper(chip, s_b, w, spec['attach_width'],
                                  spec['fan_rin'], spec['fan_angle'], layer,
                                  label='%s%s fan_taper' % (label, key))
        fan_pts = radial_fan(chip, s_b, spec['fan_rout'], spec['fan_rin'], spec['fan_angle'],
                              spec['attach_width'], layer, label='%s%s fan' % (label, key))
        verts[key] = pts + fan_pts
    return verts, run_length, bend_radius


def l_bend_branch_pair(chip, s_main, spec, fold_params, layer, label=''):
    """
    Draws one symmetric butterfly pair of SINGLE-L-BEND shunt branches - a
    NEW variant (this file only, not in filter_L30.py): perpendicular exit
    run (fold_params['d_perp']) -> ONE 90-degree guarded_bend() turn (into
    the axial direction) -> one run -> fan, attached DIRECTLY with NO exit
    turn. Designed for P5 (short stalk, unusually large fan) per this
    filter's own handoff doc, which explicitly wants this branch's fan
    pointing AXIALLY (along the chip axis, "outboard-axial") rather than
    the transverse/outward orientation folded_branch_pair()'s meander
    produces. Tried for P5 in this session's first build, then reverted to
    a plain straight branch_pair() per Eddie once the width budget had
    enough margin to afford it (see notebooks/L60_design_notes.md sec 6) -
    no current BRANCH_FOLDS entry uses this function, kept available
    (verified working) rather than deleted, in case a future width squeeze
    makes it worth revisiting - a deliberate, distinct choice for this one
    branch (a single L-shaped
    dogleg costs far less transverse width than either a straight branch
    or a full meander, at the cost of extending the branch's reach along
    the chip's own long axis instead - fine here given the axial length
    budget is ample, per the handoff's own note).

    Geometry:
      - bend_radius comes directly from fold_params['bend_radius'] (unlike
        folded_branch_pair(), there's no second parallel run to space
        against via run_gap, so this variant takes bend_radius directly).
      - run_length is SOLVED from the target scaled stalk_length, never
        hardcoded: d_perp + (pi/2)*bend_radius [one 90-deg arc] +
        run_length == spec['stalk_length'].
      - fold_params['fold_dir'] sets the turn's handedness (CCW =
        fold_dir>0), which sets which axial direction (toward the input vs
        output) the branch's single run - and hence its fan - ends up
        pointing. Same empirical, unlabeled sign convention as
        folded_branch_pair() (see that function's docstring) - verify
        against a rendered DXF, don't assume a sign without checking, same
        lesson filter_L30.py's own P2 fold_dir needed (see notebooks/
        L30_design_notes.md sec 12.5, bug found via segment trace).
      - CCW is FLIPPED per side (side '-' uses `not CCW`) for the same
        mirror-reflection-inverts-handedness reason as
        folded_branch_pair() - using the SAME CCW on both sides would give
        180-degree rotational symmetry instead of a true mirror image (see
        that function's docstring for the full empirical story behind this
        rule - baked in correctly here from the start rather than
        re-discovered).

    Returns {'+': [...], '-': [...]}, plus (run_length, bend_radius) for the
    printed report - same shape as folded_branch_pair()'s return, so the
    caller can treat both uniformly.

    REV 7: dropped the old stalk_width==attach_width assertion and added
    the guarded_fan_taper() gap-bridge before the fan, matching
    branch_pair()/folded_branch_pair() - kept in sync even though this
    function is currently unused. NOTE a real, not-yet-resolved tension:
    this function's fan is inherently AXIAL (no exit turn, by design -
    that's its whole point), but Eddie's live correction this session
    established that fans must stay PERPENDICULAR to the microstrip
    (folded_branch_pair()'s exit turn exists specifically for this). If
    this function is ever reactivated, it would need its own exit turn
    added first - it is NOT currently a valid alternative to
    folded_branch_pair() under that constraint, despite being kept
    "verified working" as a geometry primitive.
    """
    d_perp = fold_params['d_perp']
    bend_radius = fold_params['bend_radius']
    CCW = fold_params['fold_dir'] > 0
    w = spec['stalk_width']
    if bend_radius < _MIN_RADIUS_UM:
        raise ValueError('%s: bend radius %.2f um below the %.1fum apex guard'
                          % (label, bend_radius, _MIN_RADIUS_UM))

    turn_arc_len = (math.pi / 2) * bend_radius
    run_length = spec['stalk_length'] - d_perp - turn_arc_len
    if run_length < _MIN_LEN:
        raise ValueError('%s: L-bend run length %.2f um is degenerate/negative - d_perp too large '
                          'for this (scaled) stalk_length=%.1fum' % (label, run_length, spec['stalk_length']))

    verts = {}
    for sign, key in ((+1, '+'), (-1, '-')):
        side_CCW = CCW if sign > 0 else not CCW  # mirror reflection flips handedness
        s_b = s_main.cloneAlong(vector=(0, 0), newDirection=sign * 90)
        pts = guarded_straight(chip, s_b, d_perp, w, layer, label='%s%s exit' % (label, key))
        pts += guarded_bend(chip, s_b, 90, side_CCW, w, bend_radius, layer,
                             label='%s%s turn' % (label, key))
        pts += guarded_straight(chip, s_b, run_length, w, layer, label='%s%s run' % (label, key))
        # NO exit turn - fan attaches directly, inheriting the run's AXIAL
        # direction (the deliberate width-saving choice for this branch -
        # see this function's own docstring for why that's currently NOT
        # compatible with the perpendicular-fan requirement).
        pts += guarded_fan_taper(chip, s_b, w, spec['attach_width'],
                                  spec['fan_rin'], spec['fan_angle'], layer,
                                  label='%s%s fan_taper' % (label, key))
        fan_pts = radial_fan(chip, s_b, spec['fan_rout'], spec['fan_rin'], spec['fan_angle'],
                              spec['attach_width'], layer, label='%s%s fan' % (label, key))
        verts[key] = pts + fan_pts
    return verts, run_length, bend_radius


def _apply_scales():
    """Builds the scaled series/branch tables from the base tables
    (SERIES_SECTIONS/BRANCH_PAIRS) + the SCALE_SERIES/BRANCH_SCALES
    multipliers - the ONLY place scaling is applied; the base tables
    themselves are never mutated. fan_rin/attach_width/stalk_width are
    deliberately left out of the per-branch override, i.e. unscaled (only
    stalk_length and fan_rout scale, all widths stay fixed) - unchanged
    from filter_L30.py's Rev 5 _apply_scales()."""
    scaled_sections = [dict(s, length=s['length'] * SCALE_SERIES) for s in SERIES_SECTIONS]
    scaled_branches = []
    for b in BRANCH_PAIRS:
        stalk_scale, fan_scale = BRANCH_SCALES[b['name']]
        sb = dict(b)
        sb['stalk_length'] = b['stalk_length'] * stalk_scale
        sb['fan_rout'] = b['fan_rout'] * fan_scale
        sb['_stalk_scale'] = stalk_scale
        sb['_fan_scale'] = fan_scale
        scaled_branches.append(sb)
    return scaled_branches, scaled_sections


def _nearest_vertex_distance(pts_a, pts_b):
    """Vertex-to-vertex nearest distance - a cheap approximation of true
    polygon-polygon minimum separation (documented limitation: can undercount
    a true mid-edge minimum). Good enough for a design-time sanity check;
    confirm any reported value under ~500um visually in KLayout."""
    return min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in pts_a for b in pts_b)


# ===============================================================================
# wafer setup
# ===============================================================================

w = m.Wafer('filter_L60', 'DXF/', 6900, 40000, padding=1500,
            waferDiameter=m.waferDiameters['3in'], sawWidth=200,
            frame=1, solid=1, multiLayer=1, singleChipColumn=True)

w.SetupLayers([
    ['BASEMETAL', 4],
    ['MARKERS', 2],
])
w.init()
w.DicingBorder()


class FilterL60Chip(m.Chip):
    def __init__(self, wafer, chipID, layer):
        # centerChip=False: Chip.add()'s grid-snap applies origin_offset to
        # SolidPline-family shapes (CurveRect radial fans, Strip_taper's
        # SkewRect trapezoids) before their own insert/rotation transform is
        # later applied lazily at DXF-serialization time - same rationale as
        # filter_L30.py's class docstring. This chip is non-square (7mm x
        # 40mm), so disable centering rather than touch shared code.
        m.Chip.__init__(self, wafer, chipID, layer, defaults=DEFAULTS, centerChip=False)

        envelope_pts = []
        pair_vertex_sets = []  # ordered [(name, combined_verts), ...]

        # --- SNAIL + pad keep-out (dummy placeholder marker) ---
        snail_cx, snail_cy = self.width / 2, SNAIL_KEEPOUT_CY
        self.add(dxf.rectangle((snail_cx - SNAIL_KEEPOUT_W / 2, snail_cy - SNAIL_KEEPOUT_H / 2),
                                SNAIL_KEEPOUT_W, SNAIL_KEEPOUT_H, layer=wafer.lyr(MARKER_LAYER), linetype='DASHED'))

        # --- main line: runs straight down the chip (input near the top edge,
        #     output near the bottom toward the SNAIL keep-out), centered in x ---
        x0 = self.width / 2
        y0 = self.height - PAD_EDGE_MARGIN
        s_main = m.Structure(self, start=(x0, y0), direction=-90, defaults=DEFAULTS)

        # --- input: pin pad -> taper to the main line's width ---
        envelope_pts += guarded_straight(self, s_main, PIN_PAD_LENGTH, PIN_PAD_WIDTH, METAL_LAYER, label='pin pad')
        envelope_pts += guarded_taper(self, s_main, INOUT_TAPER_LEN, PIN_PAD_WIDTH, SERIES_SECTIONS[0]['width'],
                                       METAL_LAYER, label='input taper')

        # --- main line: branch pairs + series sections, in synthesis order.
        # Iterate the SCALED tables (_apply_scales()), never the base tables
        # directly, and dispatch each branch to folded_branch_pair(),
        # l_bend_branch_pair(), or branch_pair() per BRANCH_FOLDS[name]. ---
        scaled_branches, scaled_sections = _apply_scales()
        fold_report = {}  # name -> (kind, fold_params, run_length, bend_radius, d_perp_clearance)
        for branch, section in zip(scaled_branches, scaled_sections):
            fold_params = BRANCH_FOLDS[branch['name']]
            if fold_params.get('fold') or fold_params.get('l_bend'):
                d_perp = fold_params['d_perp']
                d_perp_clearance = d_perp - section['width'] / 2 - branch['stalk_width'] / 2
                if d_perp_clearance < 500.0:
                    raise ValueError('%s: d_perp=%.1fum gives only %.1fum clearance to the main line '
                                      '(need >=500um) - increase d_perp' % (branch['name'], d_perp, d_perp_clearance))
                if fold_params.get('fold'):
                    verts, run_length, bend_radius = folded_branch_pair(self, s_main, branch, fold_params,
                                                                         METAL_LAYER, label=branch['name'])
                    kind = 'FOLDED'
                else:
                    verts, run_length, bend_radius = l_bend_branch_pair(self, s_main, branch, fold_params,
                                                                         METAL_LAYER, label=branch['name'])
                    kind = 'L-BEND'
                fold_report[branch['name']] = (kind, fold_params, run_length, bend_radius, d_perp_clearance)
            else:
                verts = branch_pair(self, s_main, branch, METAL_LAYER, label=branch['name'])
            combined = verts['+'] + verts['-']
            pair_vertex_sets.append((branch['name'], combined))
            envelope_pts += combined
            envelope_pts += guarded_straight(self, s_main, section['length'], section['width'], METAL_LAYER,
                                              label='main line (after %s)' % branch['name'])

        # --- output: taper to a 200um line, stop 1mm short of the SNAIL keep-out ---
        envelope_pts += guarded_taper(self, s_main, INOUT_TAPER_LEN, SERIES_SECTIONS[-1]['width'],
                                       OUTPUT_LINE_WIDTH, METAL_LAYER, label='output taper')
        run_len = s_main.start[1] - (snail_cy + SNAIL_KEEPOUT_H / 2 + KEEPOUT_CLEARANCE)
        envelope_pts += guarded_straight(self, s_main, run_len, OUTPUT_LINE_WIDTH, METAL_LAYER, label='output line')

        # --- bounding box / clearance summary ---
        xs = [p[0] for p in envelope_pts]
        ys = [p[1] for p in envelope_pts]
        transverse_width = max(xs) - min(xs)
        total_length = max(ys) - min(ys)

        print('=' * 70)
        print('L60 radial-stub 10th-order elliptic lowpass filter (60dB floor)')
        print('Rev 6: filter_L30.py Rev 5 pattern (SCALE_SERIES=%.2f)' % SCALE_SERIES)
        print('PLACEHOLDER dimensions pending HFSS re-extraction - see notebooks/L60_design_notes.md')
        print('=' * 70)
        print('Substrate: 500um c-plane sapphire, NO ground plane, NO backside metal (ground = tunnel walls)')
        print('Metal: 120nm Al (single positive-draw layer, no XOR)')
        print('Chip: %d x %d um (usable %d x %d)' % (wafer.chipX, wafer.chipY, self.width, self.height))
        print('-' * 70)
        print('Main line series sections (Zo=84.28ohm, w=125um) - base -> x%.2f -> scaled:' % SCALE_SERIES)
        for i, (base, scaled) in enumerate(zip(SERIES_SECTIONS, scaled_sections), 1):
            print('  S%d: %.1f um -> %.1f um' % (i, base['length'], scaled['length']))
        print('-' * 70)
        print('Shunt branch pairs (butterfly, always perpendicular exit):')
        for base, scaled in zip(BRANCH_PAIRS, scaled_branches):
            print('  %s: stalk_length %.1f um -> x%.2f -> %.1f um; fan_rout %.1f um -> x%.2f -> %.1f um '
                  '(fan_rin %.1f um, attach_width %.1f um - both unscaled); zero=%s'
                  % (base['name'], base['stalk_length'], scaled['_stalk_scale'], scaled['stalk_length'],
                     base['fan_rout'], scaled['_fan_scale'], scaled['fan_rout'],
                     scaled['fan_rin'], scaled['attach_width'], scaled['zero_label']))
            if base['name'] in fold_report:
                kind, fp, run_length, bend_radius, d_perp_clearance = fold_report[base['name']]
                if kind == 'FOLDED':
                    print('      FOLDED: d_perp=%.1fum (main-line clearance %.1fum), n_par_runs=%d, '
                          'run_gap=%.1fum -> bend_radius=%.1fum, solved run_length=%.1fum, fold_dir=%+d '
                          '(fan perpendicular to microstrip, via exit turn)'
                          % (fp['d_perp'], d_perp_clearance, fp['n_par_runs'], fp['run_gap'],
                             bend_radius, run_length, fp['fold_dir']))
                else:
                    print('      L-BEND: d_perp=%.1fum (main-line clearance %.1fum), bend_radius=%.1fum, '
                          'solved run_length=%.1fum, fold_dir=%+d (fan axial - NOT currently used, see '
                          'l_bend_branch_pair() docstring)'
                          % (fp['d_perp'], d_perp_clearance, bend_radius, run_length, fp['fold_dir']))
        print('-' * 70)
        over_budget = transverse_width > WIDTH_BUDGET_UM
        print('Realized transverse bounding box: %.1f um (budget %.1f um)%s'
              % (transverse_width, WIDTH_BUDGET_UM, '  *** OVER BUDGET ***' if over_budget else ''))
        if over_budget:
            print('\x1b[31m!! WARNING: realized transverse width %.1f um exceeds %.1f um budget !!\x1b[0m'
                  % (transverse_width, WIDTH_BUDGET_UM))
        bore_half_width = PACKAGE_BORE_DIAMETER_UM / 2 - PACKAGE_WALL_CLEARANCE_UM
        print('Package bore margin (chip centered, ASSUMED %.0fum wall clearance pending O1): '
              'realized half-width %.1fum vs bore usable half-width %.1fum (bore dia %.0fum)'
              % (PACKAGE_WALL_CLEARANCE_UM, transverse_width / 2, bore_half_width, PACKAGE_BORE_DIAMETER_UM))
        print('Realized axial (length) extent: %.1f um (informational - no hard budget, 40mm chip)' % total_length)
        print('Per-pair transverse width:')
        for name, verts in pair_vertex_sets:
            pxs = [p[0] for p in verts]
            print('  %s: %.1f um' % (name, max(pxs) - min(pxs)))
        print('Per-pair nearest-neighbor clearance (vertex-to-vertex approximation - confirm visually in KLayout):')
        for i in range(len(pair_vertex_sets) - 1):
            name_a, verts_a = pair_vertex_sets[i]
            name_b, verts_b = pair_vertex_sets[i + 1]
            d = _nearest_vertex_distance(verts_a, verts_b)
            print('  %s <-> %s: %.1f um%s' % (name_a, name_b, d, '  << CHECK' if d < 500 else ''))
        print('-' * 70)
        print('Pin pad: %.1f x %.1f um, outer edge %.1f um from input edge' %
              (PIN_PAD_WIDTH, PIN_PAD_LENGTH, PAD_EDGE_MARGIN))
        print('Output line: %.1f um wide, stops %.1f um short of SNAIL keep-out' %
              (OUTPUT_LINE_WIDTH, KEEPOUT_CLEARANCE))
        print('SNAIL keep-out: %.0f x %.0f um, centered at x=%.1f y=%.1f' %
              (SNAIL_KEEPOUT_W, SNAIL_KEEPOUT_H, snail_cx, snail_cy))
        print('=' * 70)


chip = FilterL60Chip(w, 'L60', METAL_LAYER)
chip.save(w, drawCopyDXF=True, dicingBorder=False, center=True)

w.setDefaultChip(chip)
w.populate()
w.save()

# GDS export (needed downstream by a future HFSS bridge - see
# src/maskLib/hfssExport.py / filter_L30_HFSS.py's own precedent - this
# positive-metal design has no XOR layer, so unlike Hairpin_Filter.py's
# fill_basemetal_from_xor step, this is a plain DXF->GDS conversion with no
# boolean fill involved). Not consumed by any HFSS bridge this session -
# filter_L60.py's HFSS work is out of scope for this pass, see module
# docstring.
chip_dxf_path = w.path + w.fileName + '_' + chip.ID + '.dxf'
chip_gds_path = w.path + w.fileName + '_' + chip.ID + '.gds'
dxf_to_gds(chip_dxf_path, chip_gds_path,
           {name: gds_layer_number(w, name) for name in w.layerNames})
print('GDS exported -> %s' % chip_gds_path)
