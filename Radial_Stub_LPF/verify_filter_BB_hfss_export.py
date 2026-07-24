#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 regression check for filter_BB.py's HFSS geometry bridge - entirely
local, no Ansys/pyEPR needed (runs in this repo's own .venv). Sibling of
verify_L60_hfss_export.py (same role, same structure - see that file's own
module docstring for the full history of why geometry is regenerated
directly in Python rather than round-tripped through DXF/GDS). This file
duplicates the filter-agnostic geometry-math helpers (_rect_poly,
fan_arc_points, bend_arc_points, _bend_advance) fresh rather than importing
them, matching the established convention in this file family
(verify_L30_orthogonal_hfss_export.py duplicated rather than imported from
verify_L30_hfss_export.py; verify_L60_hfss_export.py does the same).

GEOMETRY SOURCE: regenerate_metal_pieces_bb() rebuilds filter_BB.py's metal
directly from its own live tables (STUBS, SERIES_SECTIONS, D_PERP_UM, the
pin-pad/taper/output constants) by importing filter_BB as a module and
calling its own filter-specific pure functions directly where they exist
(_prepare_stub() - exactly the same "call the loaded module's own helper,
don't duplicate it" choice verify_L60_hfss_export.py makes for
fl60._apply_scales()). Never touches the exported DXF/GDS.

STRUCTURAL DIFFERENCE FROM filter_L60's BRIDGE (the one thing that isn't a
mechanical copy): filter_BB's folded_stub() is SINGLE-SIDED (one branch per
stub, spawned via cloneAlong at the main line's current point - no mirrored
+/-y pair) and has NO EXIT TURN before the fan (filter_L60's
folded_branch_pair() always turns the fan back to TRANSVERSE via a
deliberate exit turn; filter_BB's fans are AXIAL by design - see that
file's own module docstring). Concretely: turn_arc_len uses (n_bends + 0.5)
here, not L60's (n_bends + 1) - one fewer 90deg turn's worth of arc.

guarded_taper()'s real draw footprint (per its own body: a taper of the
requested length PLUS a trailing straight run of 2x that length at the
output width) is bigger than the envelope corners it returns - filter_BB.py
duplicates this quirk verbatim from filter_L60.py (self-contained-file
convention). Replayed here as two separate pieces (Taper + TaperStraight)
for both the input and output tapers, exactly like L60's own bridge already
does - see that file's own comment on this.

guarded_fan_taper() (used before every fan terminator) draws a degenerate
"taper" (w0==w1 always in filter_BB - no Rev7-style flare) plus a straight
run totaling run_len = retreat + 20um, then retreats the structure position
backward by `retreat` (sagitta + 20um) - net forward advance is just the
20um overlap buffer. Since w0==w1 throughout, the taper+run combination is
geometrically just one rectangle of length run_len - replayed as such, then
the tracked position is retreated by `retreat` before computing the fan's
own tip, matching guarded_fan_taper()'s real net effect exactly.

Prior GDS-round-trip klayout check (notebooks/BB_design_notes.md sec 5,
same technique, run against the real exported GDS in an earlier session):
merged polygon count 1, 0 holes (largest area 0.0 um^2) - the axial-fan-
reaching-over-its-own-fold's-open-mouth risk flagged in this file's own
docstring did NOT materialize, confirmed not just assumed. Same expectations
asserted here, now against the from-Python-tables regeneration instead of
the DXF/GDS output.
"""
import contextlib
import importlib.util
import io
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dxfwrite import const  # noqa: E402
from maskLib.Entities import CurveRect  # noqa: E402

EXPECTED_N_MERGED_POLYGONS = 1   # everything fuses into one connected trace
MAX_HOLE_AREA_UM2 = 10.0         # exact-touching joints should give 0 real holes; small
                                  # threshold (not strict 0) just absorbs float noise


def _load_filter_BB():
    """Import filter_BB.py as a module for its live tables (STUBS,
    SERIES_SECTIONS, D_PERP_UM, pad/taper/output constants, _prepare_stub())
    - re-runs the whole script (chip build, print block, DXF/GDS save) as a
    side effect, so its own stdout is suppressed here."""
    spec = importlib.util.spec_from_file_location(
        'filter_BB', os.path.join(os.path.dirname(__file__), 'filter_BB.py'))
    module = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(module)
    return module


# ===============================================================================
# filter-agnostic geometry math - duplicated verbatim from
# verify_L60_hfss_export.py (see that file's own docstrings for the
# derivation/verification story - not re-derived here)
# ===============================================================================

def _rect_poly(start, direction_deg, length, w0, w1):
    """Proper-winding (simple, non-self-intersecting) quad for a straight or
    tapered metal segment."""
    d = math.radians(direction_deg)
    fwd = (math.cos(d), math.sin(d))
    perp = (math.cos(d + math.pi / 2), math.sin(d + math.pi / 2))
    end = (start[0] + length * fwd[0], start[1] + length * fwd[1])
    pts = [
        (start[0] + (w0 / 2) * perp[0], start[1] + (w0 / 2) * perp[1]),
        (end[0] + (w1 / 2) * perp[0], end[1] + (w1 / 2) * perp[1]),
        (end[0] - (w1 / 2) * perp[0], end[1] - (w1 / 2) * perp[1]),
        (start[0] - (w0 / 2) * perp[0], start[1] - (w0 / 2) * perp[1]),
    ]
    return pts, end


def _fan_poly(tip, direction_deg, r_out, r_in, fan_angle_deg, attach_width):
    """One fan's outline, via the same CurveRect the production drawing
    code uses. Discretized (ptDensity=120) - used for the local klayout-based
    checks below. fan_arc_points() is the 6-point native-arc analog for AEDT."""
    perp = (math.cos(math.radians(direction_deg + 90)), math.sin(math.radians(direction_deg + 90)))
    insert = (tip[0] + (attach_width / 2) * perp[0], tip[1] + (attach_width / 2) * perp[1])
    rotation = direction_deg + fan_angle_deg / 2 - 90
    cr = CurveRect(insert, height=r_out - r_in, radius=r_in, angle=fan_angle_deg, rotation=rotation,
                    ralign=const.BOTTOM, ptDensity=120)
    cr._build()
    return list(cr.points)


def fan_arc_points(tip, direction_deg, r_out, r_in, fan_angle_deg, attach_width):
    """The 6 points needed to draw one fan as 2 TRUE native arcs + 2 straight
    radial edges - identical formula to verify_L60_hfss_export.py's own
    (pure, filter-agnostic geometry math)."""
    perp_deg = direction_deg + 90
    perp = (math.cos(math.radians(perp_deg)), math.sin(math.radians(perp_deg)))
    insert = (tip[0] + (attach_width / 2) * perp[0], tip[1] + (attach_width / 2) * perp[1])
    rotation = math.radians(direction_deg + fan_angle_deg / 2 - 90)
    angle = math.radians(fan_angle_deg)

    def gpt(t, r):
        lx, ly = r * math.sin(t), r * math.cos(t) - r_in
        gx = insert[0] + lx * math.cos(rotation) - ly * math.sin(rotation)
        gy = insert[1] + lx * math.sin(rotation) + ly * math.cos(rotation)
        return (gx, gy)

    return [
        gpt(0, r_in), gpt(angle / 2, r_in), gpt(angle, r_in),
        gpt(angle, r_out), gpt(angle / 2, r_out), gpt(0, r_out),
    ]


def _bend_poly(tip, direction_deg, angle_deg, CCW, w, radius):
    """One guarded_bend()/Strip_bend() U-turn's outline, via the same
    CurveRect the production drawing code uses. Discretized (ptDensity=120)."""
    cr = CurveRect(tip, w, radius, angle=angle_deg, ptDensity=120,
                    ralign=const.MIDDLE, valign=const.MIDDLE,
                    rotation=direction_deg, vflip=not CCW)
    cr._build()
    return list(cr.points)


def bend_arc_points(tip, direction_deg, angle_deg, CCW, w, radius):
    """The 6 points needed to draw one guarded_bend()/Strip_bend() U-turn as
    2 TRUE native arcs + 2 straight radial edges - identical formula to
    verify_L60_hfss_export.py's own."""
    rotation = math.radians(direction_deg)
    r_in, r_out = radius - w / 2, radius + w / 2
    angle = math.radians(angle_deg)
    vflip_mult = 1 if CCW else -1

    def gpt(t, r):
        lx = r * math.sin(t)
        ly = (r * math.cos(t) - radius) * vflip_mult
        gx = tip[0] + lx * math.cos(rotation) - ly * math.sin(rotation)
        gy = tip[1] + lx * math.sin(rotation) + ly * math.cos(rotation)
        return (gx, gy)

    return [
        gpt(0, r_in), gpt(angle / 2, r_in), gpt(angle, r_in),
        gpt(angle, r_out), gpt(angle / 2, r_out), gpt(0, r_out),
    ]


def _bend_advance(pos, direction_deg, angle_deg, CCW, radius):
    """Pure position/direction advance for a bend - mirrors Strip_bend's own
    structure.updatePos(...) call exactly. Identical formula to
    verify_L60_hfss_export.py's own."""
    angle = math.radians(angle_deg)
    d = math.radians(direction_deg)
    local_dx = radius * math.sin(angle)
    local_dy = (1 if CCW else -1) * radius * (math.cos(angle) - 1)
    fwd = (math.cos(d), math.sin(d))
    perp = (math.cos(d + math.pi / 2), math.sin(d + math.pi / 2))
    new_pos = (pos[0] + local_dx * fwd[0] + local_dy * perp[0],
               pos[1] + local_dx * fwd[1] + local_dy * perp[1])
    new_direction = direction_deg - angle_deg if CCW else direction_deg + angle_deg
    return new_pos, new_direction


# ===============================================================================
# filter_BB-specific replay
# ===============================================================================

def _build_pieces(fbb):
    """Yields (label, hull_points, kind, arc_params) for every individual
    metal primitive - UNMERGED. `kind` is None for a plain rectangle, 'fan'
    for a radial_fan() piece, or 'bend' for a guarded_bend() U-turn piece;
    `arc_params` is the matching fan_arc_points()/bend_arc_points() argument
    tuple (None for rectangles). Also yields port1_pos/port2_pos markers.

    Replays filter_BB.py's CURRENT drawing sequence: pin pad -> input taper
    (+ its trailing straight run, see module docstring) -> [folded_stub() +
    series section] per STUBS entry, in table order -> output taper (+
    trailing straight) -> output line. Calls fbb._prepare_stub() directly
    on the loaded module (same "use the filter's own live pure function,
    don't duplicate it" choice verify_L60_hfss_export.py makes for
    fl60._apply_scales()) - only the DRAWING side (folded_stub()'s own
    position-tracking, which has real side effects via chip.add()) is
    reimplemented here.
    """
    x0 = fbb.chip.width / 2
    pos = (x0, fbb.chip.height - fbb.PAD_EDGE_MARGIN)
    direction = -90.0
    yield 'port1_pos', pos, None, None   # pin pad's OUTER edge - the actual port 1 location

    pts, pos = _rect_poly(pos, direction, fbb.PIN_PAD_LENGTH, fbb.PIN_PAD_WIDTH, fbb.PIN_PAD_WIDTH)
    yield 'PinPad', pts, None, None
    pts, pos = _rect_poly(pos, direction, fbb.INOUT_TAPER_LEN, fbb.PIN_PAD_WIDTH, fbb.W_MAIN)
    yield 'InputTaper', pts, None, None
    # guarded_taper() also draws a straight run of length 2*taper_length at
    # the taper's output width right after the taper itself - mirror that
    # here too (see module docstring; same pattern as L60's own bridge).
    pts, pos = _rect_poly(pos, direction, 2 * fbb.INOUT_TAPER_LEN, fbb.W_MAIN, fbb.W_MAIN)
    yield 'InputTaperStraight', pts, None, None

    prepared_stubs = [fbb._prepare_stub(spec) for spec in fbb.STUBS]
    next_fold_dir = {+1: +1, -1: +1}  # per-side-group alternation - mirrors fbb's own __init__ state

    for spec, section in zip(prepared_stubs, fbb.SERIES_SECTIONS):
        label = '%.1fGHz' % spec['f']
        w = spec['w']
        run_gap = max(4 * w, fbb._MIN_RUN_GAP_UM)
        fold_dir = next_fold_dir[spec['side']]
        next_fold_dir[spec['side']] *= -1
        CCW = fold_dir > 0

        bend_radius = (run_gap + w) / 2
        n_par_runs = spec['n_par_runs']
        n_bends = n_par_runs - 1
        # NO exit turn (see module docstring) -> (n_bends + 0.5) turn-lengths'
        # worth of arc, not L60's (n_bends + 1).
        turn_arc_len = math.pi * bend_radius * (n_bends + 0.5)
        run_length = (spec['target_length'] - fbb.D_PERP_UM - turn_arc_len) / n_par_runs

        b_dir = direction + spec['side'] * 90
        b_pos = pos  # branch spawns from the main line's CURRENT point (zero-offset clone) - main pos untouched

        pts, b_pos = _rect_poly(b_pos, b_dir, fbb.D_PERP_UM, w, w)
        yield '%s_exit' % label, pts, None, None

        turn_CCW = CCW
        arc_params = (b_pos, b_dir, 90, turn_CCW, w, bend_radius)
        yield '%s_entrance' % label, _bend_poly(*arc_params), 'bend', arc_params
        b_pos, b_dir = _bend_advance(b_pos, b_dir, 90, turn_CCW, bend_radius)

        pts, b_pos = _rect_poly(b_pos, b_dir, run_length, w, w)
        yield '%s_run1' % label, pts, None, None

        for i in range(n_bends):
            turn_CCW = not turn_CCW
            arc_params = (b_pos, b_dir, 180, turn_CCW, w, bend_radius)
            yield '%s_bend%d' % (label, i + 1), _bend_poly(*arc_params), 'bend', arc_params
            b_pos, b_dir = _bend_advance(b_pos, b_dir, 180, turn_CCW, bend_radius)
            pts, b_pos = _rect_poly(b_pos, b_dir, run_length, w, w)
            yield '%s_run%d' % (label, i + 2), pts, None, None

        # No exit turn - fan (if any) attaches AXIALLY, continuing b_dir as-is.
        if spec['fan_term'] > 0:
            fan_rin = spec['fan_term_rin']
            sagitta = fan_rin * (1 - math.cos(math.radians(90.0) / 2))
            retreat = sagitta + 20.0  # _FAN_TAPER_OVERLAP_BUFFER_UM
            run_len_ft = retreat + 20.0  # guarded_fan_taper()'s own run_len

            # guarded_fan_taper()'s taper+straight-run combine into one rect
            # since w0==w1==w always here (no flare) - see module docstring.
            pts, fan_taper_end = _rect_poly(b_pos, b_dir, run_len_ft, w, w)
            yield '%s_fan_taper' % label, pts, None, None
            # then retreat backward by `retreat` (guarded_fan_taper()'s own
            # structure.translatePos(vector=(-retreat, 0)) call).
            d_rad = math.radians(b_dir)
            fan_tip = (fan_taper_end[0] - retreat * math.cos(d_rad),
                       fan_taper_end[1] - retreat * math.sin(d_rad))

            fan_params = (fan_tip, b_dir, spec['fan_term'], fan_rin, 90.0, w)
            yield '%s_fan' % label, _fan_poly(*fan_params), 'fan', fan_params
        # else: plain open end - the last drawn run's own tip is the stub's end.

        pts, pos = _rect_poly(pos, direction, section['length'], fbb.W_MAIN, fbb.W_MAIN)
        yield 'Line_after_%s' % label, pts, None, None

    pts, pos = _rect_poly(pos, direction, fbb.INOUT_TAPER_LEN, fbb.W_MAIN, fbb.OUTPUT_LINE_WIDTH)
    yield 'OutputTaper', pts, None, None
    pts, pos = _rect_poly(pos, direction, 2 * fbb.INOUT_TAPER_LEN, fbb.OUTPUT_LINE_WIDTH, fbb.OUTPUT_LINE_WIDTH)
    yield 'OutputTaperStraight', pts, None, None
    run_len = pos[1] - (fbb.SNAIL_KEEPOUT_CY + fbb.SNAIL_KEEPOUT_H / 2 + fbb.KEEPOUT_CLEARANCE)
    pts, pos = _rect_poly(pos, direction, run_len, fbb.OUTPUT_LINE_WIDTH, fbb.OUTPUT_LINE_WIDTH)
    yield 'OutputLine', pts, None, None
    yield 'port2_pos', pos, None, None   # tip of the drawn output line - the actual port 2 location


def regenerate_metal_pieces_bb(stalk_fan_overlap_um=0.0):
    """Rebuilds filter_BB's BASEMETAL geometry directly (see module
    docstring) as a list of (label, hull_points, kind, arc_params) -
    deliberately UNMERGED, same shape as verify_L60_hfss_export.py's own
    regenerate_metal_pieces(). stalk_fan_overlap_um is accepted for
    signature parity with L60's version but unused here - filter_BB's own
    guarded_fan_taper() already guarantees a real overlap into the fan
    (the `retreat` mechanism, see module docstring), so no extra bridge
    piece is needed the way L60's exit-turn-to-fan joint needed one."""
    fbb = _load_filter_BB()
    pieces = []
    ports = {}
    for label, data, kind, arc_params in _build_pieces(fbb):
        if label in ('port1_pos', 'port2_pos'):
            ports[label] = data
        else:
            pieces.append((label, data, kind, arc_params))
    return {
        'pieces': pieces,
        'port1_pos': ports['port1_pos'], 'port1_width': fbb.PIN_PAD_WIDTH,
        'port2_pos': ports['port2_pos'], 'port2_width': fbb.OUTPUT_LINE_WIDTH,
        'bore_diameter_um': fbb.PACKAGE_BORE_DIAMETER_UM,
        'snail_keepout_center': (fbb.chip.width / 2, fbb.SNAIL_KEEPOUT_CY),
        'snail_keepout_w': fbb.SNAIL_KEEPOUT_W, 'snail_keepout_h': fbb.SNAIL_KEEPOUT_H,
        'w_main': fbb.W_MAIN, 'pin_pad_length': fbb.PIN_PAD_LENGTH,
    }


def regenerate_metal_region_bb():
    """Same geometry as regenerate_metal_pieces_bb(), merged into a single
    klayout.db.Region - used for the local Ansys-free sanity checks below."""
    import klayout.db as kdb  # deferred, matches hfssExport.py's own convention

    geom = regenerate_metal_pieces_bb()
    dbu = 0.001
    region = kdb.Region()
    for _label, pts, _kind, _arc_params in geom['pieces']:
        region.insert(kdb.DPolygon([kdb.DPoint(x, y) for x, y in pts]).to_itype(dbu))
    region.merge()
    geom['region'] = region
    return geom


def region_to_polys(region, dbu=0.001):
    merged = []
    for poly in region.each_merged():
        dpoly = poly.to_dtype(dbu)
        hull = [(pt.x, pt.y) for pt in dpoly.each_point_hull()]
        holes = [[(pt.x, pt.y) for pt in dpoly.each_point_hole(h)]
                 for h in range(dpoly.holes())]
        merged.append((hull, holes))
    return merged


def bbox_of(polys):
    xs = [x for hull, _ in polys for x, y in hull]
    ys = [y for hull, _ in polys for x, y in hull]
    return min(xs), min(ys), max(xs), max(ys)


def x_crossings_at_y(hull, y_target):
    crossings = []
    n = len(hull)
    for i in range(n):
        x1, y1 = hull[i]
        x2, y2 = hull[(i + 1) % n]
        if (y1 <= y_target < y2) or (y2 <= y_target < y1):
            t = (y_target - y1) / (y2 - y1)
            crossings.append(x1 + t * (x2 - x1))
    return sorted(crossings)


def check_conductor_width_at(polys, y_target, expected_width, label):
    for hull, _holes in polys:
        crossings = x_crossings_at_y(hull, y_target)
        if len(crossings) >= 2:
            width = crossings[-1] - crossings[0]
            ok = abs(width - expected_width) < 1.0
            print('  %s: found width %.2f um at y=%.1f (expected %.1f)%s'
                  % (label, width, y_target, expected_width, '' if ok else '  <<< MISMATCH'))
            return ok
    print('  %s: no boundary crossings found at y=%.1f  <<< MISMATCH' % (label, y_target))
    return False


def main():
    print('=' * 70)
    print('verify_filter_BB_hfss_export - Stage 1 (local, no Ansys/pyEPR)')
    print('=' * 70)

    geom = regenerate_metal_region_bb()
    port1_pos, port2_pos = geom['port1_pos'], geom['port2_pos']
    polys = region_to_polys(geom['region'])
    ok = True

    print('Raw (unmerged) piece count: %d' % len(geom['pieces']))

    n_polys = len(polys)
    print('\nMerged polygon count: %d (expected %d)' % (n_polys, EXPECTED_N_MERGED_POLYGONS))
    ok &= (n_polys == EXPECTED_N_MERGED_POLYGONS)

    def _shoelace_area(pts):
        return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2

    hole_areas = [_shoelace_area(h) for _hull, holes in polys for h in holes]
    max_hole_area = max(hole_areas) if hole_areas else 0.0
    print('Total holes: %d, largest area %.4f um^2 (threshold %.1f um^2)'
          % (len(hole_areas), max_hole_area, MAX_HOLE_AREA_UM2))
    ok &= (max_hole_area <= MAX_HOLE_AREA_UM2)

    if polys:
        xmin, ymin, xmax, ymax = bbox_of(polys)
        print('Bounding box: x[%.1f, %.1f]  y[%.1f, %.1f]  (width %.1f)' %
              (xmin, xmax, ymin, ymax, xmax - xmin))

        print('\nPort cut-plane conductor widths:')
        ok &= check_conductor_width_at(polys, port1_pos[1] - 5, geom['port1_width'], 'Port 1 (pin pad, near y-max)')
        ok &= check_conductor_width_at(polys, port2_pos[1] + 5, geom['port2_width'], 'Port 2 (output line, near y-min)')

    print('\nSNAIL keep-out center (for Stage A placeholder pad placement): %s'
          % (geom['snail_keepout_center'],))
    print('Bore diameter (live from filter_BB.py): %.1f um' % geom['bore_diameter_um'])

    print('=' * 70)
    if ok:
        print('ALL CHECKS PASSED')
    else:
        print('CHECKS FAILED')
        sys.exit(1)


if __name__ == '__main__':
    main()
