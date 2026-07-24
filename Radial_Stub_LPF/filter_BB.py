#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
filter_BB: quarter-wave open-stub band-block filter for the SNAIL
beamsplitter pump/drive line's on-chip protection filtering - Rev 8 DESIGN
PIVOT (Option A) away from the L30/L45/L60 lumped-LC ladder family.

PRINCIPLE: an open-circuited stub of length l shorts the main line at
f = c/(4*l*sqrt(eps_eff)) (quarter-wave interference null) and again at
3f, 5f, ... The zero depends ONLY on length and eps_eff - not on any
capacitance to ground - so the package cannot starve it, unlike
filter_L60.py's fan-capacitance zeros, which this session's own Phase 2
package sim confirmed can't reach: the 7.0mm bore keeps all ground >3mm
away, so fan capacitance is fringing-only and scaling the fans is a losing
fight (4.5GHz attenuation came back at ~0dB - see notebooks/
L60_design_notes.md sec 11). Staggered stub lengths blanket the protection
band with overlapping notches. This is a band-BLOCK, not a lowpass -
transmission recovers above the highest-frequency stub, so 8-12GHz is
checked explicitly (HFSS, out of scope this pass - see below).
Architectural precedent: Hajr et al., PRX 14, 041049 (2024) - multi-stub
band-block on a SNAIL pump line, stub lengths tuned in HFSS.

NEW FILE - filter_L30.py/filter_L45.py/filter_L60.py are untouched (L60
stays the fallback/comparison design). Self-contained (deliberately
duplicated helpers - _corners/guarded_straight/guarded_taper/guarded_bend/
radial_fan/guarded_fan_taper/_flush_attach_width are verbatim copies from
filter_L60.py), same convention as that whole file family.

CHIP WIDTH: 6.9mm (not the handoff's literal "7x40mm" line) - matches
filter_L60.py's own just-revised real chip width for the same 7.0mm-bore
package (confirmed with Eddie this session; the handoff's own stated
6000um width budget only comes out exact - 2*(7000/2-500)=6000 - using the
revised 7.0mm bore, supporting evidence this carries over here too).

SCOPE OF THIS PASS: LAYOUT ONLY (mask + DXF/GDS + Heidelberg-safety checks
+ runtime report), matching the handoff's own deliverable framing. The
handoff's "HFSS plan" GATING ITEM has now been run once (Radial_Stub_LPF/
extract_epseff.py - bare 70um/125um strip on sapphire (9.4,9.4,11.6) in the
real 7.0mm bore, wave-port eigenmode extraction, pyaedt/AEDT 2023 R2) -
see EPS_EFF below. Only the single 6GHz mid-band point is trusted; the
script's own 1-12GHz swept extraction produced non-physical dispersion
(mode index didn't track the same physical mode across frequency - beta
collapsing to 0 near 12GHz, ~130% apparent "dispersion") and is NOT used
here. Per-stub dl_um trimming and the full-band dispersion question stay
open, Eddie-side follow-up items - not attempted this pass.

GEOMETRY DESIGN NOTES (decisions made implementing this handoff):

  - No positive-metal tee primitive exists anywhere in maskLib (checked
    microwaveLib.py - only CPW_tee, XOR-gap-only). Same hand-built-overlap
    T-junction convention filter_L60.py already uses (branch spawned via
    Structure.cloneAlong() at the main line's CURRENT point, natural root
    overlap - CLAUDE.md's FlagPads/JJ_chain pattern) - just single-sided
    here (one stub per junction, not a mirrored pair).

  - "Reuse the Rev 5 folded-branch generator verbatim" means
    filter_L30.py's folded_branch_pair() exact-length-by-construction
    solve (a byte-identical copy already lives in filter_L60.py) - NOT
    maskLib.microwaveLib.wiggle_calc()/CPW_wiggles/Strip_wiggles, a
    different (more general) meander-length solver that also exists in
    this codebase but belongs to the CPW/XOR family and isn't what "Rev 5"
    refers to in this repo's own terminology.

  - folded_stub() (below) is NEW, not a copy: filter_L60.py's
    folded_branch_pair() always draws a MIRRORED PAIR ending in a
    TRANSVERSE fan (via a deliberate exit turn, per Eddie's own L60 Rev7
    correction). This handoff wants the OPPOSITE fan orientation - "fan
    terminators oriented axially at meander ends" - so folded_stub()
    combines folded_branch_pair()'s entrance-turn/n_bends-internal-turns
    machinery with l_bend_branch_pair()'s "no exit turn" idea (generalized
    from l_bend's single turn to n_bends turns), and is single-sided (one
    stub per call, no mirror-handedness-flip needed since there's nothing
    to mirror). See folded_stub()'s own docstring for the turn-arc-length
    formula this implies.

  - fan_term's Rin is DERIVED (not specified by the handoff) so the 90deg
    terminating fan attaches FLUSH to the stub width (w = 2*r_in*sin(45deg)
    -> r_in = w/(2*sin(45deg))) - no Rev7-style deliberate flare, since
    nothing here asks for one. For w=125um this works out to r_in=88.39um
    - not a coincidence: it's the same value filter_L60.py's own P2-P5
    fans used before Rev7's FAN_ANGLE=115 change, a useful cross-check
    that this derivation is principled.

  - run_gap = max(4*w, _MIN_RUN_GAP_UM) reproduces the handoff's stated
    500um (125um stubs)/400um (70um stubs) exactly from one general rule
    (same self-coupling-margin-floor concept as filter_L60.py's own
    _MIN_RUN_GAP_UM), rather than hardcoding per-stub run_gap values.

  - fold_dir alternates per SIDE GROUP, not per adjacent list entry - the
    v1 STUBS table already alternates side on every entry, so there are no
    list-adjacent same-side pairs; "same-side neighbors" means the
    nearest OTHER stub sharing that side (three stubs each on +1/-1).

KNOWN RISK, explicitly verified (not just assumed) after building: axial-
oriented terminal fans reaching back over a fold's own open "mouth" can
enclose a real hole - the same mechanism documented in CLAUDE.md and
L60_design_notes.md sec 10.2 for L30/L60's own axial-fan history.
fan_term's Rout here (300um) is far smaller than L60's synthesized fans
(1100-2000um), lowering but not eliminating the risk - see the klayout
check this file's own build/verification session ran against the real
exported GDS (notebooks/BB_design_notes.md).
"""
import json
import math
import os

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

# Extracted 6GHz value from Radial_Stub_LPF/extract_epseff.py (wave-port
# eigenmode solve, bare strip on anisotropic sapphire (9.4,9.4,11.6) in the
# real 7.0mm bore, 70um/125um both solved and field-plot-verified as the
# true strip mode - not a bulk cavity mode): eps_eff = 5.6795 (w=70um),
# 5.6826 (w=125um) at 6GHz - matching Zpi ~= 69.7 ohm both widths. The two
# widths agree to <0.1%, so one global constant (not per-width/per-stub) is
# justified; using the average. Only this single mid-band point is trusted
# - see module docstring re: the 1-12GHz sweep's non-physical dispersion
# (open follow-up, not resolved). Every stub length below is a pure
# function of this constant - update it and every length recomputes
# automatically, same "derived, not hardcoded" discipline as
# filter_L60.py's WIDTH_BUDGET_UM.
EPS_EFF = 5.681  # HFSS-extracted @ 6GHz (was 5.5 placeholder)

W_MAIN = 70.0  # um, main line width (carried over from L60 Rev 7's W_HIZ)

# f_zero_GHz, width_um, side (+1/-1), fold n_par_runs, fan_term Rout_um
# (0 = plain open end), dl_um (per-stub HFSS length trim, default 0 -
# present in the table for future iteration, not exercised this pass).
STUBS = [
    dict(f=4.2, w=70.0, side=+1, n_par_runs=3, fan_term=0.0, dl_um=0.0),
    dict(f=4.7, w=70.0, side=-1, n_par_runs=3, fan_term=300.0, dl_um=0.0),
    dict(f=5.3, w=70.0, side=+1, n_par_runs=2, fan_term=300.0, dl_um=0.0),
    dict(f=6.1, w=70.0, side=-1, n_par_runs=2, fan_term=300.0, dl_um=0.0),
    dict(f=7.0, w=70.0, side=+1, n_par_runs=2, fan_term=300.0, dl_um=0.0),
    dict(f=8.0, w=70.0, side=-1, n_par_runs=2, fan_term=0.0, dl_um=0.0),
]

# um, default series-section length between stub junctions - "parameterize
# per-section" per the handoff: override individual entries below if a
# future pass needs non-uniform spacing (classic multi-stub band-stop
# theory prefers ~lambda/4 at band center, ~5.8mm, for maximally flat
# composite rejection, but that costs ~30mm of line; starting compact and
# letting HFSS shape the composite response via these lengths instead).
SERIES_SECTION_LENGTH_UM = 2500.0
SERIES_SECTIONS = [{'length': SERIES_SECTION_LENGTH_UM} for _ in STUBS]
assert len(SERIES_SECTIONS) == len(STUBS)

# um - fold geometry, per the handoff ("d_perp 1000um, run_gap 400/500um").
D_PERP_UM = 1000.0

DWL_MIN_LEN = 0.5  # um - see _MIN_LEN below (DWL 66+ degenerate-path guard)
_MIN_LEN = DWL_MIN_LEN
_MIN_RADIUS_UM = 5.0  # um, apex/bend-radius guard (fan r_in, bend radius)
_MIN_RUN_GAP_UM = 400.0  # um, self-coupling-margin floor (see run_gap derivation above)

# um - real package bore, matches filter_L60.py's own revised value
# (Step 0, this session) - 500um wall clearance is still an ASSUMPTION
# pending the real package drawing (handoff item O1).
PACKAGE_BORE_DIAMETER_UM = 7000.0
PACKAGE_WALL_CLEARANCE_UM = 500.0
WIDTH_BUDGET_UM = 2 * (PACKAGE_BORE_DIAMETER_UM / 2 - PACKAGE_WALL_CLEARANCE_UM)

METAL_LAYER = 'BASEMETAL'
MARKER_LAYER = 'MARKERS'

# Same values as filter_L60.py - "all conventions unchanged" per the handoff.
PIN_PAD_WIDTH = 1000.0
PIN_PAD_LENGTH = 1500.0
PAD_EDGE_MARGIN = 5000.0
INOUT_TAPER_LEN = 500.0
OUTPUT_LINE_WIDTH = 200.0
KEEPOUT_CLEARANCE = 1000.0

SNAIL_KEEPOUT_W = 3000.0
SNAIL_KEEPOUT_H = 5000.0
SNAIL_KEEPOUT_CY = 4000.0

DEFAULTS = {'w': W_MAIN, 'radius': 300.0}


# ===============================================================================
# local helpers - verbatim copies from filter_L60.py (self-contained-file
# convention, see module docstring)
# ===============================================================================

def _corners(start, direction_deg, length, w0, w1):
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
    if length is None or length < _MIN_LEN:
        raise ValueError('%s: degenerate length %r um (DWL 66+ forbids zero-length paths)' % (label, length))
    pts = _corners(structure.start, structure.direction, length, w, w)
    Strip_straight(chip, structure, length, w=w, layer=layer)
    return pts


def guarded_taper(chip, structure, length, w0, w1, layer, label=''):
    if length is None or length < _MIN_LEN:
        raise ValueError('%s: degenerate length %r um (DWL 66+ forbids zero-length paths)' % (label, length))
    pts = _corners(structure.start, structure.direction, length, w0, w1)
    Strip_taper(chip, structure, length=length, w0=w0, w1=w1, layer=layer)
    Strip_straight(chip, structure, length=2 * length, w=w1, layer=layer)
    return pts


_FAN_TAPER_STEP_LEN = 25.0
_FAN_TAPER_OVERLAP_BUFFER_UM = 20.0


def guarded_fan_taper(chip, structure, w0, w1, r_in, fan_angle_deg, layer, label=''):
    """See filter_L60.py's own guarded_fan_taper() docstring for the full
    derivation (sagitta retreat + taper-must-finish-before-the-retreated-
    tip fix). Here w0 always equals w1 (stub width - no Rev7-style flare),
    so the "taper" degenerates to a same-width connector; still reused
    verbatim since the sagitta-overlap logic is independent of whether the
    width actually changes."""
    sagitta = r_in * (1 - math.cos(math.radians(fan_angle_deg) / 2))
    retreat = sagitta + _FAN_TAPER_OVERLAP_BUFFER_UM
    run_len = retreat + _FAN_TAPER_OVERLAP_BUFFER_UM

    taper_len = min(_FAN_TAPER_STEP_LEN, run_len, _FAN_TAPER_OVERLAP_BUFFER_UM - 2.0)
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


def _flush_attach_width(r_in, angle_deg):
    return 2 * r_in * math.sin(math.radians(angle_deg) / 2)


def radial_fan(chip, structure, r_out, r_in, fan_angle_deg, attach_width, layer, label=''):
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
    cr._build()
    return list(cr.points)


# ===============================================================================
# stub length calculation
# ===============================================================================

def stub_quarter_wave_length_um(f_ghz, eps_eff):
    """l = c / (4*f*sqrt(eps_eff)) - the quarter-wave open-stub null
    frequency's own length, in um for f in GHz (c = 2.998e5 um*GHz).
    Matches the handoff's own reference table exactly (4.2GHz/eps=5.5 ->
    7609um vs. its stated 7.61mm) - NOTE (Rev 12): that handoff table is
    itself computed at the OLD eps=5.5 placeholder, not the live
    EPS_EFF=5.681 below - at 5.681, 4.2GHz -> 7487um (7.49mm), not 7.61mm,
    same ~1.6% offset at every stub. EPS_EFF=5.681 is the real HFSS-measured
    value (see module docstring / DESIGN_NOTES Sec. 9) and is correct as
    live; the Rev 12 handoff's own "expected" table is stale, carried over
    unedited from the original Rev 8 handoff - flagging here rather than
    silently matching it."""
    return 2.998e5 / (4 * f_ghz * math.sqrt(eps_eff))


def predicted_f_zero_ghz(length_um, eps_eff):
    """Inverse of stub_quarter_wave_length_um() - the quarter-wave null
    frequency a REALIZED length actually predicts, in GHz. Used by the
    runtime report (target f vs. predicted-from-realized-length f) and by
    Rev 12's dims JSON export, so the HFSS first-light dashboard has a
    single, already-computed source of truth rather than recomputing this
    independently in the HFSS driver script."""
    return 2.998e5 / (4 * length_um * math.sqrt(eps_eff))


def _fan_term_rin(w):
    """Derives the terminating fan's r_in so a 90deg fan attaches FLUSH to
    the stub width w (no Rev7-style deliberate flare - nothing here asks
    for one): w = 2*r_in*sin(45deg) -> r_in = w/(2*sin(45deg))."""
    return w / (2 * math.sin(math.radians(45.0)))


def _prepare_stub(spec):
    """Builds the derived fields (nominal/corrected/target length, fan
    r_in) for one STUBS entry - the ONLY place this math happens, base
    STUBS table stays verbatim as the reference (same discipline as
    filter_L60.py's _apply_scales())."""
    s = dict(spec)
    s['nominal_length'] = stub_quarter_wave_length_um(spec['f'], EPS_EFF)
    if spec['fan_term'] > 0:
        # First-order length reduction for capacitive end-loading - per
        # the handoff, a starting guess; HFSS trims via dl_um later.
        s['corrected_length'] = s['nominal_length'] - 0.6 * spec['fan_term']
        s['fan_term_rin'] = _fan_term_rin(spec['w'])
    else:
        s['corrected_length'] = s['nominal_length']
        s['fan_term_rin'] = None
    s['target_length'] = s['corrected_length'] + spec['dl_um']
    return s


# ===============================================================================
# stub geometry - NEW (single-sided, axial-fan-terminated) - see module
# docstring for why this differs from filter_L60.py's folded_branch_pair()
# ===============================================================================

def folded_stub(chip, s_main, spec, fold_params, layer, label=''):
    """
    Draws ONE open-circuited stub off s_main's CURRENT position (single-
    sided - unlike filter_L60.py's folded_branch_pair(), which always
    draws a mirrored +y/-y pair): perpendicular exit run (d_perp) -> 90deg
    entrance turn (into axial) -> alternating 180deg internal bends+runs
    -> NO exit turn -> fan terminator (fan_term>0) or a plain open end.

    The missing exit turn is deliberate: filter_L60.py's own exit turn
    exists specifically to rotate the fan back to TRANSVERSE (Eddie's own
    Rev7 correction there) - this handoff wants fan terminators AXIAL, so
    the terminal run's own direction is left as-is (l_bend_branch_pair()'s
    single-turn precedent, generalized to n_bends turns).

    Does NOT mutate s_main (spawns via cloneAlong). Returns (verts,
    run_length, bend_radius, realized_length_um) - the last is exact by
    construction but computed/returned explicitly for the runtime report's
    target-vs-realized check, per the handoff's own requirement.
    """
    d_perp = fold_params['d_perp']
    n_par_runs = fold_params['n_par_runs']
    run_gap = fold_params['run_gap']
    if run_gap < _MIN_RUN_GAP_UM:
        raise ValueError('%s: run_gap %.2f um below the %.1fum self-coupling margin floor'
                          % (label, run_gap, _MIN_RUN_GAP_UM))
    CCW = fold_params['fold_dir'] > 0
    w = spec['w']
    bend_radius = (run_gap + w) / 2
    if bend_radius < _MIN_RADIUS_UM:
        raise ValueError('%s: bend radius %.2f um below the %.1fum apex guard'
                          % (label, bend_radius, _MIN_RADIUS_UM))

    n_bends = n_par_runs - 1
    # Entrance turn (90deg) + n_bends internal 180deg turns, NO exit turn =
    # (n_bends + 0.5) full 180deg-turn-lengths' worth of arc (vs.
    # folded_branch_pair()'s (n_bends+1), which includes the exit turn).
    turn_arc_len = math.pi * bend_radius * (n_bends + 0.5)
    run_length = (spec['target_length'] - d_perp - turn_arc_len) / n_par_runs
    if run_length < _MIN_LEN:
        raise ValueError('%s: folded stub run length %.2f um is degenerate/negative - d_perp too large '
                          'or too many parallel runs for this target_length=%.1fum'
                          % (label, run_length, spec['target_length']))

    s_b = s_main.cloneAlong(vector=(0, 0), newDirection=spec['side'] * 90)
    pts = guarded_straight(chip, s_b, d_perp, w, layer, label='%s exit' % label)
    turn_CCW = CCW
    pts += guarded_bend(chip, s_b, 90, turn_CCW, w, bend_radius, layer, label='%s entrance turn' % label)
    pts += guarded_straight(chip, s_b, run_length, w, layer, label='%s run1' % label)
    for i in range(n_bends):
        turn_CCW = not turn_CCW
        pts += guarded_bend(chip, s_b, 180, turn_CCW, w, bend_radius, layer, label='%s bend%d' % (label, i + 1))
        pts += guarded_straight(chip, s_b, run_length, w, layer, label='%s run%d' % (label, i + 2))

    realized_length_um = d_perp + turn_arc_len + n_par_runs * run_length

    if spec['fan_term'] > 0:
        fan_rin = spec['fan_term_rin']
        pts += guarded_fan_taper(chip, s_b, w, w, fan_rin, 90.0, layer, label='%s fan_taper' % label)
        pts += radial_fan(chip, s_b, spec['fan_term'], fan_rin, 90.0, w, layer, label='%s fan' % label)

    return pts, run_length, bend_radius, realized_length_um


def straight_stub(chip, s_main, spec, layer, label=''):
    """Unfolded counterpart to folded_stub() - single-sided analog of
    filter_L60.py's branch_pair(). Not exercised by the v1 STUBS table
    (every entry specifies n_par_runs, so all six fold), kept for
    family-consistency with L60's own straight+folded dual precedent."""
    w = spec['w']
    s_b = s_main.cloneAlong(vector=(0, 0), newDirection=spec['side'] * 90)
    pts = guarded_straight(chip, s_b, spec['target_length'], w, layer, label='%s stub' % label)
    realized_length_um = spec['target_length']
    if spec['fan_term'] > 0:
        fan_rin = spec['fan_term_rin']
        pts += guarded_fan_taper(chip, s_b, w, w, fan_rin, 90.0, layer, label='%s fan_taper' % label)
        pts += radial_fan(chip, s_b, spec['fan_term'], fan_rin, 90.0, w, layer, label='%s fan' % label)
    return pts, realized_length_um


def _nearest_vertex_distance(pts_a, pts_b):
    return min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in pts_a for b in pts_b)


# ===============================================================================
# wafer setup
# ===============================================================================

w = m.Wafer('filter_BB', 'DXF/', 6900, 40000, padding=1500,
            waferDiameter=m.waferDiameters['3in'], sawWidth=200,
            frame=1, solid=1, multiLayer=1, singleChipColumn=True)

w.SetupLayers([
    ['BASEMETAL', 4],
    ['MARKERS', 2],
])
w.init()
w.DicingBorder()


class FilterBBChip(m.Chip):
    def __init__(self, wafer, chipID, layer):
        # centerChip=False: same grid-snap/origin_offset rationale as
        # filter_L60.py's own class docstring - non-square chip using
        # SolidPline-family shapes (CurveRect fans).
        m.Chip.__init__(self, wafer, chipID, layer, defaults=DEFAULTS, centerChip=False)

        envelope_pts = []
        stub_vertex_sets = []  # ordered [(label, verts), ...]

        # --- SNAIL + pad keep-out (dummy placeholder marker) ---
        snail_cx, snail_cy = self.width / 2, SNAIL_KEEPOUT_CY
        self.add(dxf.rectangle((snail_cx - SNAIL_KEEPOUT_W / 2, snail_cy - SNAIL_KEEPOUT_H / 2),
                                SNAIL_KEEPOUT_W, SNAIL_KEEPOUT_H, layer=wafer.lyr(MARKER_LAYER), linetype='DASHED'))

        # --- main line ---
        x0 = self.width / 2
        y0 = self.height - PAD_EDGE_MARGIN
        s_main = m.Structure(self, start=(x0, y0), direction=-90, defaults=DEFAULTS)

        # --- input: pin pad -> taper to the main line's width ---
        envelope_pts += guarded_straight(self, s_main, PIN_PAD_LENGTH, PIN_PAD_WIDTH, METAL_LAYER, label='pin pad')
        envelope_pts += guarded_taper(self, s_main, INOUT_TAPER_LEN, PIN_PAD_WIDTH, W_MAIN,
                                       METAL_LAYER, label='input taper')

        # --- main line: stubs + series sections, in table order ---
        prepared_stubs = [_prepare_stub(spec) for spec in STUBS]
        next_fold_dir = {+1: +1, -1: +1}  # per-side-group alternation (see module docstring)
        stub_report = []  # (label, spec, run_length, bend_radius, d_perp_clearance)

        for spec, section in zip(prepared_stubs, SERIES_SECTIONS):
            label = '%.1fGHz' % spec['f']
            d_perp_clearance = D_PERP_UM - W_MAIN / 2 - spec['w'] / 2
            if d_perp_clearance < 500.0:
                raise ValueError('%s: d_perp=%.1fum gives only %.1fum clearance to the main line '
                                  '(need >=500um) - increase d_perp' % (label, D_PERP_UM, d_perp_clearance))

            run_gap = max(4 * spec['w'], _MIN_RUN_GAP_UM)
            fold_dir = next_fold_dir[spec['side']]
            next_fold_dir[spec['side']] *= -1
            fold_params = dict(d_perp=D_PERP_UM, n_par_runs=spec['n_par_runs'],
                                run_gap=run_gap, fold_dir=fold_dir)

            tee_pos = s_main.start  # main line position where this stub branches off (before the call below)
            verts, run_length, bend_radius, realized_length_um = folded_stub(
                self, s_main, spec, fold_params, METAL_LAYER, label=label)
            predicted_f_zero = predicted_f_zero_ghz(realized_length_um, EPS_EFF)
            stub_report.append((label, spec, run_length, bend_radius, d_perp_clearance,
                                 realized_length_um, fold_dir, tee_pos, predicted_f_zero))
            stub_vertex_sets.append((label, verts))
            envelope_pts += verts
            envelope_pts += guarded_straight(self, s_main, section['length'], W_MAIN, METAL_LAYER,
                                              label='main line (after %s)' % label)

        # --- output: taper to a 200um line, stop 1mm short of the SNAIL keep-out ---
        envelope_pts += guarded_taper(self, s_main, INOUT_TAPER_LEN, W_MAIN,
                                       OUTPUT_LINE_WIDTH, METAL_LAYER, label='output taper')
        run_len = s_main.start[1] - (snail_cy + SNAIL_KEEPOUT_H / 2 + KEEPOUT_CLEARANCE)
        envelope_pts += guarded_straight(self, s_main, run_len, OUTPUT_LINE_WIDTH, METAL_LAYER, label='output line')

        # --- bounding box / clearance summary ---
        xs = [p[0] for p in envelope_pts]
        ys = [p[1] for p in envelope_pts]
        transverse_width = max(xs) - min(xs)
        total_length = max(ys) - min(ys)

        print('=' * 70)
        print('filter_BB: quarter-wave open-stub band-block filter (Rev 8 pivot)')
        print('eps_eff=%.3f (HFSS-extracted @ 6GHz, bare-strip-in-bore) - single mid-band point only, see docstring' % EPS_EFF)
        print('=' * 70)
        print('Substrate: 500um c-plane sapphire, NO ground plane, NO backside metal (ground = tunnel walls)')
        print('Metal: 120nm Al (single positive-draw layer, no XOR)')
        print('Chip: %d x %d um (usable %d x %d)' % (wafer.chipX, wafer.chipY, self.width, self.height))
        print('-' * 70)
        print('Stub table (single-sided, axial fan terminators):')
        for (label, spec, run_length, bend_radius, d_perp_clearance, realized_length_um,
             fold_dir, tee_pos, predicted_f_zero) in stub_report:
            fan_str = ('fan Rout=%.1fum (r_in=%.2fum, flush)' % (spec['fan_term'], spec['fan_term_rin'])
                       if spec['fan_term'] > 0 else 'open end')
            print('  %s: side=%+d w=%.1fum n_par_runs=%d %s  tee=(%.1f, %.1f)'
                  % (label, spec['side'], spec['w'], spec['n_par_runs'], fan_str, tee_pos[0], tee_pos[1]))
            print('      length: nominal=%.2fum -> fan-corrected=%.2fum -> +dl_um(%.1f) -> target=%.2fum'
                  % (spec['nominal_length'], spec['corrected_length'], spec['dl_um'], spec['target_length']))
            print('      realized centerline length=%.2fum (target-realized delta=%.4fum) '
                  '[d_perp=%.1fum clearance=%.1fum, run_gap=%.1fum -> bend_radius=%.1fum, run_length=%.2fum, fold_dir=%+d]'
                  % (realized_length_um, spec['target_length'] - realized_length_um, D_PERP_UM, d_perp_clearance,
                     max(4 * spec['w'], _MIN_RUN_GAP_UM), bend_radius, run_length, fold_dir))
            print('      f_zero: target=%.3fGHz -> predicted-from-realized-length=%.3fGHz (delta=%.2f%%)'
                  % (spec['f'], predicted_f_zero, 100.0 * (predicted_f_zero - spec['f']) / spec['f']))
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
        print('Per-stub transverse width:')
        for label, verts in stub_vertex_sets:
            pxs = [p[0] for p in verts]
            print('  %s: %.1f um' % (label, max(pxs) - min(pxs)))
        print('Per-stub nearest-neighbor clearance (vertex-to-vertex approximation - confirm visually in KLayout):')
        for i in range(len(stub_vertex_sets) - 1):
            name_a, verts_a = stub_vertex_sets[i]
            name_b, verts_b = stub_vertex_sets[i + 1]
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

        # --- Rev 12 Phase 1 deliverable: machine-readable dims for the HFSS
        # quick-look sim (filter_BB_firstlight_HFSS.py). This is the
        # human/dashboard-facing dimensions record, NOT the HFSS geometry
        # source - the HFSS driver rebuilds real geometry (bends/fans) via
        # verify_filter_BB_hfss_export.regenerate_metal_pieces_bb() instead
        # (already proven in filter_BB_stageA_HFSS.py), since that replays
        # exact geometry rather than re-deriving it from a flat dims list.
        dims = dict(
            eps_eff=EPS_EFF, w_main=W_MAIN, d_perp_um=D_PERP_UM,
            series_section_length_um=SERIES_SECTION_LENGTH_UM,
            bore_diameter_um=PACKAGE_BORE_DIAMETER_UM,
            transverse_width_um=transverse_width, total_length_um=total_length,
            width_budget_um=WIDTH_BUDGET_UM,
            stubs=[
                dict(label=label, f_target_ghz=spec['f'], w_um=spec['w'], side=spec['side'],
                     n_par_runs=spec['n_par_runs'], fan_term_rout_um=spec['fan_term'],
                     fan_term_rin_um=spec['fan_term_rin'], dl_um=spec['dl_um'],
                     nominal_length_um=spec['nominal_length'], corrected_length_um=spec['corrected_length'],
                     target_length_um=spec['target_length'], realized_length_um=realized_length_um,
                     predicted_f_zero_ghz=predicted_f_zero, run_length_um=run_length,
                     bend_radius_um=bend_radius, fold_dir=fold_dir, tee_pos_um=list(tee_pos))
                for (label, spec, run_length, bend_radius, d_perp_clearance, realized_length_um,
                     fold_dir, tee_pos, predicted_f_zero) in stub_report
            ],
        )
        dims_dir = os.path.join(os.path.dirname(__file__), 'HFSS')
        os.makedirs(dims_dir, exist_ok=True)
        dims_path = os.path.join(dims_dir, 'filter_BB_dims.json')
        with open(dims_path, 'w') as f:
            json.dump(dims, f, indent=2)
        print('Dims JSON written -> %s' % dims_path)


chip = FilterBBChip(w, 'BB', METAL_LAYER)
chip.save(w, drawCopyDXF=True, dicingBorder=False, center=True)

w.setDefaultChip(chip)
w.populate()
w.save()

chip_dxf_path = w.path + w.fileName + '_' + chip.ID + '.dxf'
chip_gds_path = w.path + w.fileName + '_' + chip.ID + '.gds'
dxf_to_gds(chip_dxf_path, chip_gds_path,
           {name: gds_layer_number(w, name) for name in w.layerNames})
print('GDS exported -> %s' % chip_gds_path)
