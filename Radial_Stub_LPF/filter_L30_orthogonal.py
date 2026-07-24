#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
As-synthesized sibling of filter_L30.py: same radial-stub Chebyshev-II
lowpass filter (L30: 8th order, fc=3.5GHz, stopband from 3.999GHz, 30dB
equiripple floor), same Nuhertz-synthesized electrical dimensions, but with
every shunt-branch fan mounted perpendicular to the main line (tilt=0
everywhere) instead of filter_L30.py's hand-tuned backward lean. filter_L30.py
tilts three of its four branch pairs purely to shrink the transverse
footprint into a 7mm-wide chip (its own design notes' tilt-vs-width table:
0deg->9.01mm, 55deg->5.17mm as-synthesized) - that tilt is a mask-layout
space-saving choice layered on top of the synthesized dimensions, it does not
change any stalk/fan electrical dimension.

This script exists purely as a comparison point: build the filter exactly as
Nuhertz synthesized it (no mechanical rotation) on a chip wide enough to fit
it (13mm, comfortably above the 9.01mm as-synthesized envelope), run it
through the same HFSS wave-port S21 pipeline used for filter_L30.py, and
compare the two results to see what filter_L30.py's tilt-based space
optimization cost (or didn't cost) electrically. See
notebooks/L30_orthogonal_design_notes.md.

13mm x 40mm bare (no backside metal) c-plane sapphire chip, 120nm Al, NO
ground plane on-chip at all (ground reference = the package tunnel walls
around the chip, not modeled here) - same positive-metal-draw convention as
filter_L30.py (filled polygons = aluminum directly, no XOR layer, no
fill_basemetal_from_xor step).

Every electrical dimension here is a PLACEHOLDER pending HFSS re-extraction,
same caveat as filter_L30.py - see notebooks/L30_design_notes.md for the
full derivation (this file only changes tilt + chip width, not any
electrical dimension).

Deliberately self-contained/duplicated from filter_L30.py rather than
parameterized - matches this project's existing filter_L30.py/filter_L45.py
precedent of no shared dimension-table module.
"""
import math

from dxfwrite import const
from dxfwrite import DXFEngine as dxf

import maskLib.MaskLib as m
from maskLib.microwaveLib import Strip_straight, Strip_taper
from maskLib.Entities import CurveRect
from maskLib.gdsExport import dxf_to_gds
from maskLib.layerDoseTable import gds_layer_number

# ===============================================================================
# tunable constants
# ===============================================================================

# All branches perpendicular to the main line (0 = perpendicular, no lean) -
# this script reproduces the as-synthesized Nuhertz geometry with no
# mechanical tilt, unlike filter_L30.py's hand-tuned per-branch leans. Kept
# as a named constant (rather than removed) so BRANCH_PAIRS below keeps the
# same 'tilt' key/shape as filter_L30.py's table for the HFSS bridge's
# geometry-replay logic to stay schema-compatible.
TILT_DEG = 0.0

# DWL 66+ rejects single-vertex/zero-length PATH elements (CLAUDE.md). Every
# length in the tables below is real/nonzero, so this should never actually
# fire - it's a guard against future edits introducing a degenerate segment,
# not a live code path.
_MIN_LEN = 0.5  # um

# Raised from filter_L30.py's 6500um budget to match this chip's wider
# 13000um width - at tilt=0 the as-synthesized transverse envelope is
# ~9.01mm (see module docstring / notebooks/L30_design_notes.md), so this
# budget just keeps the over-budget warning meaningful for the new chip
# rather than firing spuriously.
WIDTH_BUDGET_UM = 12000.0

METAL_LAYER = 'BASEMETAL'
MARKER_LAYER = 'MARKERS'

# ===============================================================================
# dimension tables - transcribed verbatim (Nuhertz Filter Solutions synthesis,
# 8th order Chebyshev II, fc=3.500 GHz, stopband from 3.999 GHz, 30dB floor)
# Identical to filter_L30.py except every 'tilt' is 0.0 (perpendicular) - see
# module docstring.
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
# L30_design_notes.md, "attach_width vs stalk_width").
#
# 'tilt': all 0.0 (perpendicular, no lean) - this script's whole point is
# the as-synthesized geometry with no mechanical rotation, unlike
# filter_L30.py which overrides this per-branch to shrink the transverse
# footprint (see that file's own BRANCH_PAIRS comment). Electrical
# dimensions (stalk_length/width, fan_rout/rin/angle, attach_width) are
# otherwise identical to filter_L30.py's table.
BRANCH_PAIRS = [
    {'name': 'P1', 'stalk_length': 200.0, 'stalk_width': 250.0, 'stalk_zo': 66.55,
     'fan_rout': 582.9, 'fan_rin': 176.8, 'fan_angle': 90.0, 'attach_width': 250.0,
     'tilt': 0.0, 'zero_label': 'matching element, ~1.05 THz'},
    {'name': 'P2', 'stalk_length': 1980.0, 'stalk_width': 125.0, 'stalk_zo': None,
     'fan_rout': 1133.0, 'fan_rin': 88.39, 'fan_angle': 90.0, 'attach_width': 125.0,
     'tilt': 0.0, 'zero_label': '6.43 GHz'},
    {'name': 'P3', 'stalk_length': 3271.0, 'stalk_width': 125.0, 'stalk_zo': None,
     'fan_rout': 1237.0, 'fan_rin': 88.39, 'fan_angle': 90.0, 'attach_width': 125.0,
     'tilt': 0.0, 'zero_label': '4.623 GHz'},
    {'name': 'P4', 'stalk_length': 585.4, 'stalk_width': 125.0, 'stalk_zo': None,
     'fan_rout': 992.7, 'fan_rin': 88.39, 'fan_angle': 90.0, 'attach_width': 125.0,
     'tilt': 0.0, 'zero_label': '12.04 GHz'},
]

assert len(BRANCH_PAIRS) == len(SERIES_SECTIONS), 'one branch pair per series section, by construction'

# Input pin pad (Axline-style capacitive pin above an on-chip pad). "1000 x
# 1500 um" per the handoff doc, read as width(transverse) x length(axial) to
# match the chip's own width x height convention - PROVISIONAL, not derived
# from a package drawing (see notebooks/L30_design_notes.md).
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
# local helpers - identical to filter_L30.py (deliberately duplicated, no
# shared parameterization module yet; see module docstring)
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
    Draws one symmetric butterfly pair of shunt branches (stalk + radial fan)
    off s_main's CURRENT position: both branches start at the same point on
    the main line's centerline, tilted spec['tilt'] degrees back from
    perpendicular toward the input on each side (s_main.direction +/-
    (90+spec['tilt'])) - spec['tilt']=0 means perpendicular, no lean. Does
    NOT mutate s_main (spawns via cloneAlong). The stalk's near half
    necessarily overlaps the already-drawn main-line rectangle at the
    junction - fusing visually with no gap, no boolean op needed (same
    overlapping-filled-polygon composition FlagPads/JJ_chain already use
    elsewhere in this repo for positive metal).

    Returns {'+': [...], '-': [...]}, the global vertex lists (stalk corners
    + fan polygon) for each side, for the bbox/clearance summary.
    """
    if abs(spec['stalk_width'] - spec['attach_width']) > 1e-6:
        raise ValueError('%s: stalk_width (%.3f) != attach_width (%.3f) - branch_pair assumes '
                          'these coincide (see notebooks/L30_design_notes.md)'
                          % (label, spec['stalk_width'], spec['attach_width']))
    tilt_deg = spec['tilt']
    verts = {}
    for sign, key in ((+1, '+'), (-1, '-')):
        s_b = s_main.cloneAlong(vector=(0, 0), newDirection=sign * (90 + tilt_deg))
        stalk_pts = guarded_straight(chip, s_b, spec['stalk_length'], spec['stalk_width'], layer,
                                      label='%s%s stalk' % (label, key))
        fan_pts = radial_fan(chip, s_b, spec['fan_rout'], spec['fan_rin'], spec['fan_angle'],
                              spec['attach_width'], layer, label='%s%s fan' % (label, key))
        verts[key] = stalk_pts + fan_pts
    return verts


def _nearest_vertex_distance(pts_a, pts_b):
    """Vertex-to-vertex nearest distance - a cheap approximation of true
    polygon-polygon minimum separation (documented limitation: can undercount
    a true mid-edge minimum). Good enough for a design-time sanity check;
    confirm any reported value under ~500um visually in KLayout."""
    return min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in pts_a for b in pts_b)


# ===============================================================================
# wafer setup
# ===============================================================================

w = m.Wafer('filter_L30_orthogonal', 'DXF/', 13000, 40000, padding=1500,
            waferDiameter=m.waferDiameters['3in'], sawWidth=200,
            frame=1, solid=1, multiLayer=1, singleChipColumn=True)

w.SetupLayers([
    ['BASEMETAL', 4],
    ['MARKERS', 2],
])
w.init()
w.DicingBorder()


class FilterL30OrthogonalChip(m.Chip):
    def __init__(self, wafer, chipID, layer):
        # centerChip=False: Chip.add()'s grid-snap applies origin_offset to
        # SolidPline-family shapes (CurveRect radial fans, Strip_taper's
        # SkewRect trapezoids) before their own insert/rotation transform is
        # later applied lazily at DXF-serialization time - same rationale as
        # Hairpin_Filter.py's class docstring. This chip is non-square
        # (13mm x 40mm), so disable centering rather than touch shared code.
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

        # --- main line: branch pairs + series sections, in synthesis order ---
        for branch, section in zip(BRANCH_PAIRS, SERIES_SECTIONS):
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
        print('ORTHOGONAL variant: all fans perpendicular (tilt=0), 13mm chip -')
        print('comparison sibling of filter_L30.py - see notebooks/L30_orthogonal_design_notes.md')
        print('PLACEHOLDER dimensions pending HFSS re-extraction - see notebooks/L30_design_notes.md')
        print('=' * 70)
        print('Substrate: 500um c-plane sapphire, NO ground plane, NO backside metal (ground = tunnel walls)')
        print('Metal: 120nm Al (single positive-draw layer, no XOR)')
        print('Chip: %d x %d um (usable %d x %d)' % (wafer.chipX, wafer.chipY, self.width, self.height))
        print('-' * 70)
        print('Main line series sections (Zo=84.29ohm, w=125um):')
        for i, s in enumerate(SERIES_SECTIONS, 1):
            print('  S%d: length=%.1f um' % (i, s['length']))
        print('-' * 70)
        print('Shunt branch pairs (butterfly, tilt = deg off perpendicular, backward toward input):')
        for b in BRANCH_PAIRS:
            print('  %s: stalk %.1fx%.1fum, fan Rout=%.1f Rin=%.1f angle=%.0fdeg, tilt=%.1fdeg, zero=%s'
                  % (b['name'], b['stalk_length'], b['stalk_width'], b['fan_rout'], b['fan_rin'],
                     b['fan_angle'], b['tilt'], b['zero_label']))
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


chip = FilterL30OrthogonalChip(w, 'L30_ORTHO', METAL_LAYER)
chip.save(w, drawCopyDXF=True, dicingBorder=False, center=True)

w.setDefaultChip(chip)
w.populate()
w.save()

# GDS export (needed downstream by the HFSS bridge - see
# src/maskLib/hfssExport.py / filter_L30_orthogonal_HFSS.py - this
# positive-metal design has no XOR layer, so unlike Hairpin_Filter.py's
# fill_basemetal_from_xor step, this is a plain DXF->GDS conversion with no
# boolean fill involved).
chip_dxf_path = w.path + w.fileName + '_' + chip.ID + '.dxf'
chip_gds_path = w.path + w.fileName + '_' + chip.ID + '.gds'
dxf_to_gds(chip_dxf_path, chip_gds_path,
           {name: gds_layer_number(w, name) for name in w.layerNames})
print('GDS exported -> %s' % chip_gds_path)
