#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone radial-stub Chebyshev-II lowpass filter (L30: 8th order, fc=3.5GHz,
stopband from 3.999GHz, 30dB equiripple floor), for the SNAIL beamsplinter
pump/drive line's on-chip protection filtering. Dimensions transcribed
verbatim from a Nuhertz Filter Solutions synthesis (microstrip/alumina model,
Zo 84.29ohm/125um main line) - see notebooks/L30_design_notes.md for the full
derivation of the geometry below and the design decisions made translating
the synthesized dimensions into mask layout.

7mm x 40mm bare (no backside metal) c-plane sapphire chip, 120nm Al, NO
ground plane on-chip at all (ground reference = the package tunnel walls
around the chip, not modeled here). This is therefore a positive-metal-draw
design (filled polygons = aluminum directly) - NOT the CPW/XOR-gap
convention used by Hairpin_Filter.py/SNAIL_Pump_Filter.py elsewhere in this
repo. The closest structural precedent is SNAIL/SNAIL.py + FlagPads/
JJ_chain (junctionLib.py/fluxoniumLib.py), which draw positive metal
directly for the same no-ground-plane reason. No XOR layer, no
fill_basemetal_from_xor step.

Every electrical dimension here is a PLACEHOLDER pending HFSS re-extraction
in the real (bare-sapphire, tunnel-grounded) environment - same caveat as
Hairpin_Filter.py/SNAIL_Pump_Filter.py. Branch-pair interpretation (butterfly
up/down at one junction) and the P1 matching-branch stalk Zo are unverified
against the original Nuhertz netlist (see notebooks/L30_design_notes.md,
items V1/V2).

REV 5 (this pass): the first real HFSS wave-port S21 result (this session,
on filter_L30_orthogonal.py's untilted geometry - see notebooks/
L30_HFSS_notes.md) showed the whole response ~1.4x high in frequency vs the
Nuhertz synthesis targets (no ground plane -> collapsed fan capacitance +
lower eps_eff). Fixed here with two additive mechanisms, both layered on top
of the still-verbatim Rev 4 base tables (SERIES_SECTIONS/BRANCH_PAIRS):
(A) SCALE_SERIES/BRANCH_SCALES - per-branch dimensionless multipliers so
further HFSS-driven iteration is a constants edit, not a layout rewrite (see
_apply_scales()); (B) BRANCH_FOLDS - folds P2/P3's now-longer stalks into
hairpin-style meanders (guarded_bend()/folded_branch_pair(), reusing
maskLib.microwaveLib.Strip_bend - the positive-metal analog of the CPW_bend
Hairpin_Filter.py's own tapped_hairpin_filter() uses) so the extra length
fits inside WIDTH_BUDGET_UM. Rev 4's per-branch 'tilt' mechanism is retired -
folding supersedes it; every branch now exits exactly perpendicular to the
main line. See notebooks/L30_design_notes.md's "Rev 5" section for the full
derivation, physics rationale, and as-built results.

NOTE: the HFSS bridge scripts built for Rev 4 (verify_L30_hfss_export.py /
filter_L30_HFSS.py) hand-replay this file's OLD straight/tilted drawing
sequence and are now STALE against this folded geometry - they need a
matching rewrite before any future HFSS run against this revision (not done
this session; further HFSS iteration and the resulting BRANCH_SCALES
adjustments are expected future work, not blocking this layout pass).

Companion file: filter_L45.py (12th order, 45dB floor) - deliberately
self-contained, no shared parameterization module yet (this is intentional,
not an oversight - see notebooks/L30_design_notes.md). Not touched this
session - gets the same Rev 5 treatment once L30 converges in HFSS.
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

# --- HFSS iteration knobs (Rev 5) - dimensionless multipliers on the Rev 4
# base tables below (SERIES_SECTIONS/BRANCH_PAIRS), which stay verbatim as
# the reference - tuning lives here, the base numbers are never overwritten.
# Widths (stalk/line width, fan Rin, attach_width) are NOT scaled.
#
# First HFSS pass (this session, on filter_L30_orthogonal.py's untilted
# geometry - used specifically because it isolates the pure no-ground-plane
# physics from tilt's own separate fan-to-line coupling shift, see
# notebooks/L30_HFSS_notes.md) showed the whole response ~1.4x high in
# frequency vs the Nuhertz synthesis targets: no ground plane -> fan
# capacitance collapsed (bigger effect) + eps_eff dropped -> electrical
# lengths effectively shrank (smaller effect).
#
# Physics: zero freq ~ 1/sqrt(L*C); L ~ stalk length (linear); C ~ fan
# Rout^alpha, alpha in [1 (fringing-dominated, no ground plane), 2
# (area-dominated)]. For a uniform scale s applied to both L and C
# dimensions: LC ~ s^3 if alpha=2 (s~1.24-1.28 suffices), LC ~ s^2 if
# alpha=1 (s~1.38-1.45 needed). Values below start at the alpha~1
# (conservative/larger) end - expect 2-3 more HFSS iterations per branch,
# adjusting stalk scale for fine moves and fan scale for coarse moves.
# Branches converge to DIFFERENT scales (P2 shifted x1.454, P3 x1.384 in
# the first pass) - hence per-branch, not global.
SCALE_SERIES = 1.40
BRANCH_SCALES = {
    # pair: (stalk_len_scale, fan_rout_scale)
    'P1': (1.40, 1.40),  # matching pair - scale with the rest until told otherwise
    'P2': (1.40, 1.40),
    'P3': (1.35, 1.35),
    'P4': (1.40, 1.40),
}

# Folded (meandered) stalk geometry - REPLACES Rev 4's tilt mechanism
# entirely (tilt is retired: branches now always exit perpendicular to the
# main line; folding, not leaning, is how the post-scaling extra stalk
# length fits inside WIDTH_BUDGET_UM). fold=False keeps a straight stalk -
# P1/P4 stay short enough even after scaling that they don't need it.
# See folded_branch_pair() below for the construction.
BRANCH_FOLDS = {
    # pair: dict(fold, d_perp, n_par_runs, run_gap, fold_dir).
    #
    # d_perp=625um is the practical floor, not an arbitrary choice: the
    # handoff's own rule is "any meander segment to the main line >= 500um"
    # - with both the main line and every folded stalk at 125um wide, that's
    # d_perp - 125/2 - 125/2 >= 500 -> d_perp >= 625um exactly. Shortening
    # further would violate that clearance rule.
    #
    # fold_dir's sign -> axial direction is empirical (see guarded_bend/
    # folded_branch_pair's own docstring for the full derivation), and - now
    # that folded_branch_pair() ends with an explicit 90-degree exit turn -
    # only affects which of the internal parallel runs initially goes
    # upstream vs downstream; it no longer affects the FAN's final direction
    # at all (the exit turn always returns to the same transverse/outward
    # heading regardless of fold_dir - confirmed by direct trace this
    # session). P2 uses +1 specifically so its FIRST run (the one nearest
    # the main line, i.e. nearest P1) goes downstream (away from P1) instead
    # of upstream toward P1's fan - confirmed via a segment-by-segment trace
    # that the earlier -1 choice sent run1 toward P1 (y 30056->30695, well
    # into P1's own fan's y-range) even though the fan itself (unaffected by
    # this, thanks to the exit turn) already pointed safely away. P3 keeps
    # -1 (no equivalent nearby-upstream-neighbor constraint).
    'P1': dict(fold=False),
    'P2': dict(fold=True, d_perp=625.0, n_par_runs=2, run_gap=300.0, fold_dir=+1),
    # P3 was originally 3 parallel runs (matching its longer stalk_length),
    # but at run_gap=300 that pushed the realized transverse width to
    # 7013.8um (513.8um over WIDTH_BUDGET_UM) - P3 was the binding
    # constraint. Dropped to 2 runs (per Eddie's call) to fit back under
    # budget at the wider, less-cramped run_gap - run_length grows
    # correspondingly to absorb the same stalk_length target (see
    # folded_branch_pair's solve).
    'P3': dict(fold=True, d_perp=625.0, n_par_runs=2, run_gap=300.0, fold_dir=-1),
    'P4': dict(fold=False),
}

# DWL 66+ rejects single-vertex/zero-length PATH elements (CLAUDE.md). Every
# length in the tables below is real/nonzero, so this should never actually
# fire - it's a guard against future edits introducing a degenerate segment,
# not a live code path.
_MIN_LEN = 0.5  # um

# Apex/bend-radius Heidelberg-safety guard (Rev 5) - analogous to _MIN_LEN
# but for radii (fan_rin, folded-stalk bend radius) rather than lengths.
# Today's values (fan_rin >= 88um, bend radius = (run_gap+w)/2 >= ~312um)
# clear this easily - the guard exists to catch a future bad edit, not
# today's numbers.
_MIN_RADIUS_UM = 5.0  # um

WIDTH_BUDGET_UM = 6500.0  # transverse hard budget (handoff doc, unchanged in Rev 5)

METAL_LAYER = 'BASEMETAL'
MARKER_LAYER = 'MARKERS'

# ===============================================================================
# dimension tables - transcribed verbatim (Nuhertz Filter Solutions synthesis,
# 8th order Chebyshev II, fc=3.500 GHz, stopband from 3.999 GHz, 30dB floor)
# ===============================================================================

# Main-line series sections, input -> output. All Zo=84.29ohm/125um in the
# as-synthesized (alumina microstrip) model.
SERIES_SECTIONS = [
    {'length': 1487.0, 'width': 125.0, 'zo': 84.29},   # S1
    {'length': 4202.0, 'width': 125.0, 'zo': 84.29},   # S2
    {'length': 3190.0, 'width': 125.0, 'zo': 84.29},   # S3
    {'length': 138.3, 'width': 125.0, 'zo': 84.29},    # S4
]

# Shunt branch pairs (each row = one butterfly pair: two mirrored branches,
# +y and -y off the main line at that junction). P1 sits before S1; Pn sits
# between S(n-1) and Sn. attach_width is the fan's inner-arc chord width (see
# radial_fan below) - it is numerically equal to stalk_width in every row
# here, but is a geometrically distinct quantity (see notebooks/
# L30_design_notes.md, "attach_width vs stalk_width"). These are the Rev 4
# Nuhertz-synthesized electrical dimensions, unchanged - Rev 5's per-branch
# HFSS scale factors (BRANCH_SCALES) and fold geometry (BRANCH_FOLDS) are
# applied on top of these at build time (_apply_scales()), never by editing
# this table directly.
#
# Rev 4 had a 'tilt' field here (per-branch lean off perpendicular, a
# mask-layout space-saving choice). Retired in Rev 5 - folding (BRANCH_FOLDS)
# supersedes it, so every branch now exits exactly perpendicular to the main
# line (see branch_pair()/folded_branch_pair()).
BRANCH_PAIRS = [
    {'name': 'P1', 'stalk_length': 200.0, 'stalk_width': 250.0, 'stalk_zo': 66.55,
     'fan_rout': 582.9, 'fan_rin': 176.8, 'fan_angle': 90.0, 'attach_width': 250.0,
     'zero_label': 'matching element, ~1.05 THz'},
    {'name': 'P2', 'stalk_length': 1980.0, 'stalk_width': 125.0, 'stalk_zo': None,
     'fan_rout': 1133.0, 'fan_rin': 88.39, 'fan_angle': 90.0, 'attach_width': 125.0,
     'zero_label': '6.43 GHz'},
    {'name': 'P3', 'stalk_length': 3271.0, 'stalk_width': 125.0, 'stalk_zo': None,
     'fan_rout': 1237.0, 'fan_rin': 88.39, 'fan_angle': 90.0, 'attach_width': 125.0,
     'zero_label': '4.623 GHz'},
    {'name': 'P4', 'stalk_length': 585.4, 'stalk_width': 125.0, 'stalk_zo': None,
     'fan_rout': 992.7, 'fan_rin': 88.39, 'fan_angle': 90.0, 'attach_width': 125.0,
     'zero_label': '12.04 GHz'},
]

assert len(BRANCH_PAIRS) == len(SERIES_SECTIONS), 'one branch pair per series section, by construction'

# Input pin pad (Axline-style capacitive pin above an on-chip pad). "1000 x
# 1500 um" per the handoff doc, read as width(transverse) x length(axial) to
# match the chip's own "7mm x 40mm" width x height convention - PROVISIONAL,
# not derived from a package drawing (see notebooks/L30_design_notes.md).
PIN_PAD_WIDTH = 1000.0
PIN_PAD_LENGTH = 1500.0
PAD_EDGE_MARGIN = 5000.0    # um, pad's outer (chip-edge-facing) edge from the input edge
INOUT_TAPER_LEN = 500.0     # um, standard taper length (both ends)
OUTPUT_LINE_WIDTH = 200.0   # um
KEEPOUT_CLEARANCE = 1000.0  # um, output line stops 1mm short of the SNAIL keep-out

# SNAIL + capacitive-pad keep-out (dummy marker, not real geometry). Orientation
# (3mm transverse x 5mm axial) matches SNAIL_Pump_Filter.py's precedent exactly;
# the handoff doc's "5 x 3mm" prose is ambiguous on which axis is which - see
# notebooks/L30_design_notes.md.
SNAIL_KEEPOUT_W = 3000.0
SNAIL_KEEPOUT_H = 5000.0
SNAIL_KEEPOUT_CY = 4000.0

DEFAULTS = {'w': 125.0, 'radius': 300.0}


# ===============================================================================
# local helpers - deliberately duplicated in filter_L45.py (no shared
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
    Strip_straight(chip,structure,length=2*length, w=w1, layer=layer)
    return pts


def guarded_bend(chip, structure, angle, CCW, w, radius, layer, label=''):
    """Strip_bend (positive-metal U-turn via CurveRect, ralign=valign=MIDDLE -
    i.e. `radius` is the trace CENTERLINE radius, `w` is the trace width) -
    the positive-metal analog of CPW_bend (Hairpin_Filter.py's
    tapped_hairpin_filter() uses CPW_bend for its own folds, but that whole
    path is CPW/XOR-gap, not usable directly on this file's no-ground-plane
    convention - Strip_bend is the correct, already-proven reuse target, see
    notebooks/L30_design_notes.md Rev 5 section).

    Calls the real Strip_bend for drawing + structure position/direction
    update (true reuse, not reimplemented - Strip_bend itself returns
    nothing though), and separately builds an un-added CurveRect with
    IDENTICAL parameters purely to extract its discretized .points for
    envelope/clearance bookkeeping - same point-capture idiom radial_fan()
    already uses for the fans (cr._build() is a pure fn of ctor args, safe
    to call without chip.add()).

    Guarded against DWL 66+ degenerate (near-zero) radius, same _MIN_LEN-
    style philosophy as guarded_straight/guarded_taper, plus the Rev 5
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
    tip of `structure`, angularly centered on structure.direction.

    CurveRect's own `insert` point is NOT the fan's geometric center - it's
    one corner of the fan's inner arc (see notebooks/L30_design_notes.md for
    the full derivation). So for the fan to come out centered on, and flush
    against, the stalk's tip edge:
        rotation = S + fan_angle/2 - 90        (centers the angular sweep on S)
        insert   = tip + (attach_width/2)*perp  (one tip-edge corner, not the
                                                   tip centerline point)
    This only produces a seamless (zero-gap, zero-overlap) joint when
    attach_width == 2*r_in*sin(fan_angle/2). Not enforced - fan_angle and
    attach_width are free to be tuned independently (e.g. by hand, while
    iterating on layout) - a mismatch just means the fan won't sit perfectly
    flush against the stalk tip; printed as a heads-up, not an error.
    """
    expected_attach = 2 * r_in * math.sin(math.radians(fan_angle_deg) / 2)
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
    radial fan) off s_main's CURRENT position: both branches start at the
    same point on the main line's centerline, exactly perpendicular on each
    side (s_main.direction +/- 90 - tilt is retired in Rev 5, see
    BRANCH_FOLDS/folded_branch_pair() for the folded alternative used by
    branches that need more length than a straight stalk can fit
    transversely). Does NOT mutate s_main (spawns via cloneAlong). The
    stalk's near half necessarily overlaps the already-drawn main-line
    rectangle at the junction - fusing visually with no gap, no boolean op
    needed (same overlapping-filled-polygon composition FlagPads/JJ_chain
    already use elsewhere in this repo for positive metal).

    Returns {'+': [...], '-': [...]}, the global vertex lists (stalk corners
    + fan polygon) for each side, for the bbox/clearance summary.
    """
    if abs(spec['stalk_width'] - spec['attach_width']) > 1e-6:
        raise ValueError('%s: stalk_width (%.3f) != attach_width (%.3f) - branch_pair assumes '
                          'these coincide (see notebooks/L30_design_notes.md)'
                          % (label, spec['stalk_width'], spec['attach_width']))
    verts = {}
    for sign, key in ((+1, '+'), (-1, '-')):
        s_b = s_main.cloneAlong(vector=(0, 0), newDirection=sign * 90)
        stalk_pts = guarded_straight(chip, s_b, spec['stalk_length'], spec['stalk_width'], layer,
                                      label='%s%s stalk' % (label, key))
        fan_pts = radial_fan(chip, s_b, spec['fan_rout'], spec['fan_rin'], spec['fan_angle'],
                              spec['attach_width'], layer, label='%s%s fan' % (label, key))
        verts[key] = stalk_pts + fan_pts
    return verts


def folded_branch_pair(chip, s_main, spec, fold_params, layer, label=''):
    """
    Draws one symmetric butterfly pair of FOLDED (meandered) shunt branches:
    perpendicular exit run (fold_params['d_perp']) -> a 90-degree turn into
    the AXIAL direction (parallel to the main line) -> a meander of
    fold_params['n_par_runs'] axial parallel runs connected by ALTERNATING-
    handedness 180-degree guarded_bend() U-turns (each 180-degree bend steps
    the meander further away from the main line, TRANSVERSELY) -> a 90-degree
    exit turn back to perpendicular/transverse -> a radial fan at the free
    end, pointing away from the main line. Rev 5's replacement for
    branch_pair()'s straight stalk, used for branches whose scaled
    stalk_length (see _apply_scales()) would otherwise blow the transverse
    WIDTH_BUDGET_UM if drawn straight. Tilt is retired - the initial exit is
    always exactly perpendicular, same as branch_pair().

    IMPORTANT (two bugs found and fixed via rendered-DXF review - see
    notebooks/L30_design_notes.md Rev 5 section for the full story):
      1. The parallel runs must run axially (parallel to the main line,
         matching e.g. Fast_Flux's hairpin inductor precedent) - NOT
         transversely. An early version omitted the 90-degree turn after the
         exit run entirely, so the "parallel runs" stayed transverse the
         whole time and the 180-degree bends (which step perpendicular to
         the CURRENT direction) stepped AXIALLY instead - exactly backwards.
      2. Every 180-degree bend's handedness must ALTERNATE (not CCW, CCW,
         not CCW, ...), not repeat the same value - repeating the same CCW
         spirals the path into a closed loop/circle (each 180 bend curling
         the same way as the last) instead of zigzagging back and forth in
         a straight line of parallel runs. A final 90-degree exit turn
         (continuing the SAME alternation one more step, just at half the
         angle) brings the direction back to perpendicular/transverse so
         the fan ends up pointing away from the main line, not along the
         chip axis.

    Geometry:
      - bend_radius = (run_gap + stalk_width) / 2 (centerline radius that
        gives exactly run_gap edge-to-edge clearance between adjacent
        parallel runs, given guarded_bend's ralign=MIDDLE convention). Used
        for the 90-degree entrance/exit turns and every 180-degree internal
        bend alike.
      - run_length is SOLVED from the target scaled stalk_length, never
        hardcoded: d_perp + (n_bends+1)*pi*bend_radius [the entrance + exit
        90s together cost one 180-equivalent arc, plus n_bends true 180s] +
        n_par_runs*run_length == spec['stalk_length'].
      - `turn_CCW` alternates via a running variable: starts at `side_CCW`
        for the entrance turn, flips (`not turn_CCW`) before every
        subsequent turn (each internal 180, and the final 90 exit turn) -
        this one running/flipping variable produces the correct alternating
        zigzag with no separate parity-tracking logic needed.
      - fold_params['fold_dir'] (+1/-1) sets the entrance turn's initial
        handedness (`CCW = fold_dir > 0`), which in turn sets which axial
        direction (toward the input vs toward the output) the meander body
        extends in. In this design P2 and P3 both use fold_dir=-1
        (downstream) - not because they interleave with each other, but
        because P2 sits close upstream of P1 and must point away from it;
        confirmed empirically (see design notes) that fold_dir=-1 points
        downstream at this main-line orientation.
      - CCW is FLIPPED per side (side '-' uses `not CCW`) for EVERY turn
        (entrance, every internal 180, and the exit turn): mirroring about
        the main line's vertical axis already flips direction correctly via
        cloneAlong's sign*90 (confirmed: '+'/'-' x-ranges do come out
        mirrored about x0), but a mirror reflection also inverts handedness
        - using the SAME CCW on both sides instead gives 180-degree
        ROTATIONAL (point) symmetry about the junction, not a mirror image,
        which was caught empirically: both sides' Y-extents differed (one
        side's meander swung toward the neighboring branch upstream, eating
        into its clearance) when they should be identical (a reflection
        about a vertical axis cannot change Y-extent at all). Flipping CCW
        per side fixes this - both sides then get the identical Y-extent,
        differing only in X (correctly mirrored).
      - The fan is attached by calling radial_fan() unchanged after the
        exit turn, so it points along whatever direction the exit turn left
        the structure facing - transverse/away from the main line, per the
        handoff's "facing away from the microstripline" requirement.

    Returns {'+': [...], '-': [...]}, the global vertex lists (every drawn
    sub-piece's points: exit run, entrance turn, every parallel run, every
    180-degree bend's discretized arc, fan) for each side - denser than
    branch_pair()'s straight-stalk points, so the existing envelope/
    clearance bookkeeping (_nearest_vertex_distance et al.) automatically
    covers the full folded
    envelope, not just the fan.
    """
    if abs(spec['stalk_width'] - spec['attach_width']) > 1e-6:
        raise ValueError('%s: stalk_width (%.3f) != attach_width (%.3f) - folded_branch_pair assumes '
                          'these coincide (see notebooks/L30_design_notes.md)'
                          % (label, spec['stalk_width'], spec['attach_width']))
    d_perp = fold_params['d_perp']
    n_par_runs = fold_params['n_par_runs']
    run_gap = fold_params['run_gap']
    CCW = fold_params['fold_dir'] > 0
    w = spec['stalk_width']
    bend_radius = (run_gap + w) / 2
    if bend_radius < _MIN_RADIUS_UM:
        raise ValueError('%s: bend radius %.2f um below the %.1fum apex guard'
                          % (label, bend_radius, _MIN_RADIUS_UM))

    n_bends = n_par_runs - 1
    # Two 90-deg turns (entrance: perpendicular->axial, exit: axial->perpendicular
    # again) plus n_bends 180-deg turns, all at the same centerline bend_radius.
    # The two 90s together cost exactly one 180-equivalent arc length (pi*radius).
    turn_arc_len = math.pi * bend_radius * (n_bends + 1)
    run_length = (spec['stalk_length'] - d_perp - turn_arc_len) / n_par_runs
    if run_length < _MIN_LEN:
        raise ValueError('%s: folded run length %.2f um is degenerate/negative - d_perp too large '
                          'or too many parallel runs for this (scaled) stalk_length=%.1fum'
                          % (label, run_length, spec['stalk_length']))

    verts = {}
    for sign, key in ((+1, '+'), (-1, '-')):
        side_CCW = CCW if sign > 0 else not CCW  # mirror reflection flips handedness - see docstring
        s_b = s_main.cloneAlong(vector=(0, 0), newDirection=sign * 90)  # tilt retired - always perpendicular exit
        pts = guarded_straight(chip, s_b, d_perp, w, layer, label='%s%s exit' % (label, key))
        # turn from perpendicular (transverse, away from the main line) into axial
        # (parallel to the main line) - the parallel runs below must run axially,
        # not transversely (see folded_branch_pair's docstring/design-notes fix).
        turn_CCW = side_CCW
        pts += guarded_bend(chip, s_b, 90, turn_CCW, w, bend_radius, layer,
                             label='%s%s entrance turn' % (label, key))
        pts += guarded_straight(chip, s_b, run_length, w, layer, label='%s%s run1' % (label, key))
        # ALTERNATE each 180-deg bend's handedness (not just repeat the same
        # one) - repeating the same CCW every time spirals the path into a
        # closed loop/circle instead of zigzagging back and forth in a
        # straight line of parallel runs (caught from a rendered DXF review -
        # see notebooks/L30_design_notes.md Rev 5 section, bug #4). Mirrors
        # Strip_wiggles' own alternating not-CCW/CCW/not-CCW/... pattern.
        for i in range(n_bends):
            turn_CCW = not turn_CCW
            pts += guarded_bend(chip, s_b, 180, turn_CCW, w, bend_radius, layer,
                                 label='%s%s bend%d' % (label, key, i + 1))
            pts += guarded_straight(chip, s_b, run_length, w, layer,
                                     label='%s%s run%d' % (label, key, i + 2))
        # exit turn: one more alternation step (90 deg instead of 180) - turns
        # back from axial to perpendicular/transverse, so the fan ends up
        # pointing AWAY from the main line (outward), not along the chip axis.
        turn_CCW = not turn_CCW
        pts += guarded_bend(chip, s_b, 90, turn_CCW, w, bend_radius, layer,
                             label='%s%s exit turn' % (label, key))
        fan_pts = radial_fan(chip, s_b, spec['fan_rout'], spec['fan_rin'], spec['fan_angle'],
                              spec['attach_width'], layer, label='%s%s fan' % (label, key))
        verts[key] = pts + fan_pts
    return verts, run_length, bend_radius


def _apply_scales():
    """Builds the Rev 5 scaled series/branch tables from the Rev 4 base
    tables (SERIES_SECTIONS/BRANCH_PAIRS) + the SCALE_SERIES/BRANCH_SCALES
    multipliers - the ONLY place scaling is applied; the base tables
    themselves are never mutated. fan_rin/attach_width/stalk_width are
    deliberately left out of the per-branch override, i.e. unscaled (Rev 5's
    rule: only stalk_length and fan_rout scale, all widths stay fixed)."""
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

w = m.Wafer('filter_L30', 'DXF/', 7000, 40000, padding=1500,
            waferDiameter=m.waferDiameters['3in'], sawWidth=200,
            frame=1, solid=1, multiLayer=1, singleChipColumn=True)

w.SetupLayers([
    ['BASEMETAL', 4],
    ['MARKERS', 2],
])
w.init()
w.DicingBorder()


class FilterL30Chip(m.Chip):
    def __init__(self, wafer, chipID, layer):
        # centerChip=False: Chip.add()'s grid-snap applies origin_offset to
        # SolidPline-family shapes (CurveRect radial fans, Strip_taper's
        # SkewRect trapezoids) before their own insert/rotation transform is
        # later applied lazily at DXF-serialization time - same rationale as
        # Hairpin_Filter.py's class docstring. This chip is non-square
        # (7mm x 40mm), so disable centering rather than touch shared code.
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
        # Rev 5: iterate the SCALED tables (_apply_scales()), never the Rev 4
        # base tables directly, and dispatch each branch to
        # folded_branch_pair() or branch_pair() per BRANCH_FOLDS[name]['fold']. ---
        scaled_branches, scaled_sections = _apply_scales()
        fold_report = {}  # name -> (fold_params, run_length, bend_radius, d_perp_clearance)
        for branch, section in zip(scaled_branches, scaled_sections):
            fold_params = BRANCH_FOLDS[branch['name']]
            if fold_params.get('fold'):
                d_perp = fold_params['d_perp']
                d_perp_clearance = d_perp - section['width'] / 2 - branch['stalk_width'] / 2
                if d_perp_clearance < 500.0:
                    raise ValueError('%s: d_perp=%.1fum gives only %.1fum clearance to the main line '
                                      '(need >=500um) - increase d_perp' % (branch['name'], d_perp, d_perp_clearance))
                verts, run_length, bend_radius = folded_branch_pair(self, s_main, branch, fold_params,
                                                                     METAL_LAYER, label=branch['name'])
                fold_report[branch['name']] = (fold_params, run_length, bend_radius, d_perp_clearance)
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
        transverse_width = max(xs) - min(xs)

        print('=' * 70)
        print('L30 radial-stub Chebyshev-II lowpass filter (8th order, 30dB floor)')
        print('Rev 5: HFSS-driven rescale (SCALE_SERIES=%.2f) + folded stalks (tilt retired)' % SCALE_SERIES)
        print('PLACEHOLDER dimensions pending further HFSS re-extraction - see notebooks/L30_design_notes.md')
        print('=' * 70)
        print('Substrate: 500um c-plane sapphire, NO ground plane, NO backside metal (ground = tunnel walls)')
        print('Metal: 120nm Al (single positive-draw layer, no XOR)')
        print('Chip: %d x %d um (usable %d x %d)' % (wafer.chipX, wafer.chipY, self.width, self.height))
        print('-' * 70)
        print('Main line series sections (Zo=84.29ohm, w=125um) - base -> x%.2f -> scaled:' % SCALE_SERIES)
        for i, (base, scaled) in enumerate(zip(SERIES_SECTIONS, scaled_sections), 1):
            print('  S%d: %.1f um -> %.1f um' % (i, base['length'], scaled['length']))
        print('-' * 70)
        print('Shunt branch pairs (butterfly, always perpendicular - tilt retired in Rev 5):')
        for base, scaled in zip(BRANCH_PAIRS, scaled_branches):
            print('  %s: stalk_length %.1f um -> x%.2f -> %.1f um; fan_rout %.1f um -> x%.2f -> %.1f um '
                  '(fan_rin %.1f um, attach_width %.1f um - both unscaled); zero=%s'
                  % (base['name'], base['stalk_length'], scaled['_stalk_scale'], scaled['stalk_length'],
                     base['fan_rout'], scaled['_fan_scale'], scaled['fan_rout'],
                     scaled['fan_rin'], scaled['attach_width'], scaled['zero_label']))
            if base['name'] in fold_report:
                fp, run_length, bend_radius, d_perp_clearance = fold_report[base['name']]
                print('      FOLDED: d_perp=%.1fum (main-line clearance %.1fum), n_par_runs=%d, '
                      'run_gap=%.1fum -> bend_radius=%.1fum, solved run_length=%.1fum, fold_dir=%+d'
                      % (fp['d_perp'], d_perp_clearance, fp['n_par_runs'], fp['run_gap'],
                         bend_radius, run_length, fp['fold_dir']))
        print('-' * 70)
        over_budget = transverse_width > WIDTH_BUDGET_UM
        print('Realized transverse bounding box: %.1f um (budget %.1f um)%s'
              % (transverse_width, WIDTH_BUDGET_UM, '  *** OVER BUDGET ***' if over_budget else ''))
        if over_budget:
            print('\x1b[31m!! WARNING: realized transverse width %.1f um exceeds %.1f um budget !!\x1b[0m'
                  % (transverse_width, WIDTH_BUDGET_UM))
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


chip = FilterL30Chip(w, 'L30', METAL_LAYER)
chip.save(w, drawCopyDXF=True, dicingBorder=False, center=True)

w.setDefaultChip(chip)
w.populate()
w.save()

# GDS export (needed downstream by the HFSS bridge - see
# src/maskLib/hfssExport.py / filter_L30_HFSS.py - this positive-metal
# design has no XOR layer, so unlike Hairpin_Filter.py's
# fill_basemetal_from_xor step, this is a plain DXF->GDS conversion with no
# boolean fill involved).
chip_dxf_path = w.path + w.fileName + '_' + chip.ID + '.dxf'
chip_gds_path = w.path + w.fileName + '_' + chip.ID + '.gds'
dxf_to_gds(chip_dxf_path, chip_gds_path,
           {name: gds_layer_number(w, name) for name in w.layerNames})
print('GDS exported -> %s' % chip_gds_path)
