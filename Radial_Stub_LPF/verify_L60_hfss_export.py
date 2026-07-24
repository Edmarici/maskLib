#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 regression check for filter_L60.py's HFSS geometry bridge -
entirely local, no Ansys/pyEPR needed (runs in this repo's own .venv).
Sibling of verify_L30_hfss_export.py (same role/pattern - see that file's
own module docstring for the full history of why geometry is regenerated
directly in Python rather than round-tripped through DXF/GDS, the Rev 5
folded-stalk replay rewrite, and the bend_arc_points()/_bend_advance()
derivation+verification). This file duplicates that logic fresh rather than
importing it - matches the established convention this session
(verify_L30_orthogonal_hfss_export.py duplicated the same functions rather
than importing from verify_L30_hfss_export.py, mirroring the mask scripts'
own self-contained convention).

GEOMETRY SOURCE: regenerate_metal_region() below rebuilds filter_L60.py's
metal directly from its own live tables/position-tracking (importing
filter_L60 as a module), never touching the exported DXF/GDS - same
DXF/GDS-round-trip-corruption rationale as verify_L30_hfss_export.py.

SCOPE: filter_L60.py's CURRENT geometry only uses two branch kinds -
straight (branch_pair(), P1/P5) and folded meander (folded_branch_pair(),
P2/P3/P4) - confirmed via its BRANCH_FOLDS (no l_bend=True entries; P5's
L-bend was tried and reverted earlier this session, see notebooks/
L60_design_notes.md sec 6). This bridge replays only those two kinds - it
does NOT add L-bend replay support speculatively (filter_L60.py's own
l_bend_branch_pair() stays defined-but-unused there, and nothing here
would exercise a bridge-side L-bend replay to verify it against). If P5's
L-bend is ever reactivated, this file's _build_pieces() needs a matching
third branch (mirroring l_bend_branch_pair()'s single-turn, no-exit-turn
sequence) before any HFSS run against that configuration.

The exit-turn-to-fan joint-overlap fix (see filter_L30_HFSS.py's own
docstring for the full diagnostic story - a real Unite() failure, silently
producing an Unclassified body, found via incremental unite on filter_L30's
own folded branches) is baked into _build_pieces() below from the start,
not re-discovered.
"""
import contextlib
import importlib.util
import io
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from maskLib.hfssExport import list_layers, extract_metal_polygons  # noqa: E402
from maskLib.Entities import CurveRect  # noqa: E402
from dxfwrite import const  # noqa: E402

GDS_PATH = os.path.join(os.path.dirname(__file__), 'DXF', 'filter_L60_CHIP_L60.gds')
GDS_METAL_LAYER = 2      # BASEMETAL - confirmed via gds_layer_number(wafer, 'BASEMETAL')
GDS_METAL_DATATYPE = 0

# Expectations, same rationale as filter_L30's own bridge:
EXPECTED_N_MERGED_POLYGONS = 1   # everything fuses into one connected trace
MAX_HOLE_AREA_UM2 = 10.0   # exact-touching joints should give 0 real holes; small
                           # threshold (not strict 0) just absorbs float noise


def _load_filter_L60():
    """Import filter_L60.py as a module for its live tables (SERIES_SECTIONS,
    BRANCH_PAIRS, BRANCH_FOLDS, pad/taper/output constants) - re-runs the
    whole script (chip build, print block, DXF/GDS save) as a side effect,
    so its own stdout is suppressed here."""
    spec = importlib.util.spec_from_file_location(
        'filter_L60', os.path.join(os.path.dirname(__file__), 'filter_L60.py'))
    module = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(module)
    return module


def _rect_poly(start, direction_deg, length, w0, w1):
    """Proper-winding (simple, non-self-intersecting) quad for a straight or
    tapered metal segment - unlike filter_L60.py's own `_corners()` (which
    deliberately returns a non-loop-ordered point set, fine for its
    bbox-only bookkeeping use but not a valid polygon for HFSS)."""
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
    code uses (same insert/rotation formulas as filter_L60.radial_fan) -
    called directly, no DXF/GDS round-trip. Discretized (ptDensity=120) -
    used for the local klayout-based checks below. filter_L60_HFSS.py uses
    fan_arc_points() instead (6 points, 2 native AEDT arc segments)."""
    perp = (math.cos(math.radians(direction_deg + 90)), math.sin(math.radians(direction_deg + 90)))
    insert = (tip[0] + (attach_width / 2) * perp[0], tip[1] + (attach_width / 2) * perp[1])
    rotation = direction_deg + fan_angle_deg / 2 - 90
    cr = CurveRect(insert, height=r_out - r_in, radius=r_in, angle=fan_angle_deg, rotation=rotation,
                    ralign=const.BOTTOM, ptDensity=120)
    cr._build()
    return list(cr.points)


def fan_arc_points(tip, direction_deg, r_out, r_in, fan_angle_deg, attach_width):
    """The 6 points needed to draw one fan as 2 TRUE native arcs + 2
    straight radial edges (inner_0, inner_mid, inner_end, outer_end,
    outer_mid, outer_0) - instead of the ~64-point polygon approximation
    _fan_poly()/CurveRect use for the 2D DXF/GDS mask output. Identical
    formula to verify_L30_hfss_export.py's own (pure, filter-agnostic
    geometry math - already verified this session, see that file's own
    docstring). AEDT's native CreatePolyline Arc segment format needs a
    3-point (start, on-arc, end) definition per arc - the *_mid points here
    are exactly that "on-arc" point, at the arc's true angular midpoint."""
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
    CurveRect the production drawing code uses (ralign=valign=const.MIDDLE,
    vflip=not CCW - see filter_L60.guarded_bend). Discretized
    (ptDensity=120) - used for the local klayout-based checks below,
    mirroring _fan_poly()'s role. bend_arc_points() below is the 6-point
    native-arc analog for AEDT."""
    cr = CurveRect(tip, w, radius, angle=angle_deg, ptDensity=120,
                    ralign=const.MIDDLE, valign=const.MIDDLE,
                    rotation=direction_deg, vflip=not CCW)
    cr._build()
    return list(cr.points)


def bend_arc_points(tip, direction_deg, angle_deg, CCW, w, radius):
    """The 6 points needed to draw one guarded_bend()/Strip_bend() U-turn as
    2 TRUE native arcs + 2 straight radial edges - identical formula to
    verify_L30_hfss_export.py's own (pure, filter-agnostic geometry math -
    derived directly from CurveRect's source and independently verified to
    machine precision against real guarded_bend() output this session, see
    that file's own docstring / verify_bend_geometry.py / notebooks/
    L30_HFSS_notes.md Rev 5 section - not re-derived or re-verified here,
    same formula applies regardless of which filter's bends it's fed)."""
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
    structure.updatePos(...) call exactly, so _build_pieces() below can
    track a bare (pos, direction) tuple through a folded branch's turns the
    same way _rect_poly() already tracks straight/tapered segments, without
    needing a real m.Structure. Identical formula to
    verify_L30_hfss_export.py's own - already verified to machine precision
    this session (verify_bend_geometry.py)."""
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


def _build_pieces(fl60, stalk_fan_overlap_um=0.0):
    """Yields (label, hull_points, kind, arc_params) for every individual
    metal primitive (pad, tapers, main-line segments, folded/straight
    branches, fan outlines) - UNMERGED. `kind` is None for a plain
    rectangle, 'fan' for a radial_fan() piece, or 'bend' for a
    guarded_bend() U-turn piece; `arc_params` is the matching
    fan_arc_points()/bend_arc_points() argument tuple (None for
    rectangles). Also yields port1_pos/port2_pos markers at the right
    points in the sequence.

    Replays filter_L60.py's CURRENT drawing sequence - scaled tables via
    fl60._apply_scales(), and per-branch dispatch on
    fl60.BRANCH_FOLDS[name]['fold'] between the straight-stalk replay
    (P1/P5 in the current build) and the folded-branch replay (P2/P3/P4),
    mirroring fl60.folded_branch_pair()'s exact turn sequence (exit run,
    entrance turn, alternating internal 180-deg bends + runs, exit turn,
    fan). Does NOT handle fl60.l_bend_branch_pair()'s sequence - no branch
    in the current filter_L60.py build uses it (see module docstring).

    stalk_fan_overlap_um: if nonzero, a small guaranteed-overlap bridge
    piece is inserted right before EVERY fan (both the straight branches'
    stalk-extension, and the folded branches' exit-turn-to-fan bridge) -
    AEDT's Unite() needs this (confirmed empirically for filter_L30.py's
    own folded branches via incremental unite - see
    verify_L30_hfss_export.py's own docstring for the full story). Default
    0 (exact, no overlap) - used by the local klayout checks below;
    filter_L60_HFSS.py opts in via a nonzero value.
    """
    scaled_branches, scaled_sections = fl60._apply_scales()
    x0 = fl60.chip.width / 2
    pos = (x0, fl60.chip.height - fl60.PAD_EDGE_MARGIN)
    direction = -90.0
    yield 'port1_pos', pos, None, None   # pin pad's OUTER (chip-edge-facing) edge - the actual port 1 location

    pts, pos = _rect_poly(pos, direction, fl60.PIN_PAD_LENGTH, fl60.PIN_PAD_WIDTH, fl60.PIN_PAD_WIDTH)
    yield 'PinPad', pts, None, None
    pts, pos = _rect_poly(pos, direction, fl60.INOUT_TAPER_LEN, fl60.PIN_PAD_WIDTH,
                                   scaled_sections[0]['width'])
    yield 'InputTaper', pts, None, None
    # guarded_taper() also draws a straight run of length 2*taper_length at
    # the taper's output width right after the taper itself - mirror that
    # here too (reimplements guarded_taper's position-tracking rather than
    # calling it directly, so it must be kept in sync by hand).
    w1 = scaled_sections[0]['width']
    pts, pos = _rect_poly(pos, direction, 2 * fl60.INOUT_TAPER_LEN, w1, w1)
    yield 'InputTaperStraight', pts, None, None

    for branch, section in zip(scaled_branches, scaled_sections):
        # side labels avoid '+'/'-' - not valid characters in AEDT object
        # names (confirmed empirically this session for filter_L30.py).
        fold_params = fl60.BRANCH_FOLDS[branch['name']]
        if fold_params.get('fold'):
            d_perp = fold_params['d_perp']
            n_par_runs = fold_params['n_par_runs']
            run_gap = fold_params['run_gap']
            CCW_base = fold_params['fold_dir'] > 0
            w = branch['stalk_width']
            bend_radius = (run_gap + w) / 2
            n_bends = n_par_runs - 1
            turn_arc_len = math.pi * bend_radius * (n_bends + 1)
            run_length = (branch['stalk_length'] - d_perp - turn_arc_len) / n_par_runs

            for sign, side in ((+1, 'a'), (-1, 'b')):
                side_CCW = CCW_base if sign > 0 else not CCW_base
                b_dir = direction + sign * 90  # tilt retired - always perpendicular exit
                b_pos = pos

                pts, b_pos = _rect_poly(b_pos, b_dir, d_perp, w, w)
                yield '%s%s_exit' % (branch['name'], side), pts, None, None

                turn_CCW = side_CCW
                arc_params = (b_pos, b_dir, 90, turn_CCW, w, bend_radius)
                yield '%s%s_entrance' % (branch['name'], side), _bend_poly(*arc_params), 'bend', arc_params
                b_pos, b_dir = _bend_advance(b_pos, b_dir, 90, turn_CCW, bend_radius)

                pts, b_pos = _rect_poly(b_pos, b_dir, run_length, w, w)
                yield '%s%s_run1' % (branch['name'], side), pts, None, None

                for i in range(n_bends):
                    turn_CCW = not turn_CCW
                    arc_params = (b_pos, b_dir, 180, turn_CCW, w, bend_radius)
                    yield ('%s%s_bend%d' % (branch['name'], side, i + 1),
                           _bend_poly(*arc_params), 'bend', arc_params)
                    b_pos, b_dir = _bend_advance(b_pos, b_dir, 180, turn_CCW, bend_radius)
                    pts, b_pos = _rect_poly(b_pos, b_dir, run_length, w, w)
                    yield '%s%s_run%d' % (branch['name'], side, i + 2), pts, None, None

                turn_CCW = not turn_CCW
                arc_params = (b_pos, b_dir, 90, turn_CCW, w, bend_radius)
                yield '%s%s_exitturn' % (branch['name'], side), _bend_poly(*arc_params), 'bend', arc_params
                b_pos, b_dir = _bend_advance(b_pos, b_dir, 90, turn_CCW, bend_radius)

                # fan_tip = the TRUE (un-extended) exit-turn end - what the
                # fan attaches to. AEDT's Unite() needs a guaranteed real
                # overlap here (see module docstring) - a small extra
                # straight "bridge" run pokes stalk_fan_overlap_um past the
                # true end; the fan's own anchor (fan_tip) is unaffected.
                fan_tip = b_pos
                if stalk_fan_overlap_um:
                    overlap_pts, _ = _rect_poly(b_pos, b_dir, stalk_fan_overlap_um, w, w)
                    yield '%s%s_fan_overlap' % (branch['name'], side), overlap_pts, None, None

                fan_params = (fan_tip, b_dir, branch['fan_rout'], branch['fan_rin'],
                              branch['fan_angle'], branch['attach_width'])
                yield '%s%s_fan' % (branch['name'], side), _fan_poly(*fan_params), 'fan', fan_params
        else:
            for sign, side in ((+1, 'a'), (-1, 'b')):
                b_dir = direction + sign * 90  # tilt retired - always perpendicular exit
                # tip = the TRUE (un-extended) stalk end - what the fan attaches
                # to. stalk_pts is drawn stalk_fan_overlap_um longer so it pokes
                # past that point into the fan; the fan's own position never
                # uses the extended length.
                stalk_pts, tip = _rect_poly(pos, b_dir, branch['stalk_length'] + stalk_fan_overlap_um,
                                                           branch['stalk_width'], branch['stalk_width'])
                if stalk_fan_overlap_um:
                    _, tip = _rect_poly(pos, b_dir, branch['stalk_length'],
                                         branch['stalk_width'], branch['stalk_width'])
                yield '%s%s_stalk' % (branch['name'], side), stalk_pts, None, None
                fan_params = (tip, b_dir, branch['fan_rout'], branch['fan_rin'],
                              branch['fan_angle'], branch['attach_width'])
                yield '%s%s_fan' % (branch['name'], side), _fan_poly(*fan_params), 'fan', fan_params
        pts, pos = _rect_poly(pos, direction, section['length'], section['width'], section['width'])
        yield 'Line_after_%s' % branch['name'], pts, None, None

    pts, pos = _rect_poly(pos, direction, fl60.INOUT_TAPER_LEN, scaled_sections[-1]['width'],
                                   fl60.OUTPUT_LINE_WIDTH)
    yield 'OutputTaper', pts, None, None
    pts, pos = _rect_poly(pos, direction, 2 * fl60.INOUT_TAPER_LEN,
                                   fl60.OUTPUT_LINE_WIDTH, fl60.OUTPUT_LINE_WIDTH)
    yield 'OutputTaperStraight', pts, None, None
    run_len = pos[1] - (fl60.SNAIL_KEEPOUT_CY + fl60.SNAIL_KEEPOUT_H / 2 + fl60.KEEPOUT_CLEARANCE)
    pts, pos = _rect_poly(pos, direction, run_len, fl60.OUTPUT_LINE_WIDTH, fl60.OUTPUT_LINE_WIDTH)
    yield 'OutputLine', pts, None, None
    yield 'port2_pos', pos, None, None   # tip of the drawn output line - the actual port 2 location


def regenerate_metal_pieces(stalk_fan_overlap_um=0.0):
    """Rebuilds filter_L60's BASEMETAL geometry directly (see module
    docstring) as a list of (label, hull_points, kind, arc_params) -
    deliberately UNMERGED. This is what filter_L60_HFSS.py actually draws
    into AEDT: drawing each simple piece separately (then unite()d) avoids
    AEDT's CreatePolyline choking on an overly complex single polygon (the
    same issue confirmed for filter_L30.py this session). See
    _build_pieces() for stalk_fan_overlap_um and the kind/arc_params
    piece-tuple shape ('fan'/'bend'/None)."""
    fl60 = _load_filter_L60()
    pieces = []
    ports = {}
    for label, data, kind, arc_params in _build_pieces(fl60, stalk_fan_overlap_um=stalk_fan_overlap_um):
        if label in ('port1_pos', 'port2_pos'):
            ports[label] = data
        else:
            pieces.append((label, data, kind, arc_params))
    return {
        'pieces': pieces,
        'port1_pos': ports['port1_pos'], 'port1_width': fl60.PIN_PAD_WIDTH,
        'port2_pos': ports['port2_pos'], 'port2_width': fl60.OUTPUT_LINE_WIDTH,
        # Live, not hardcoded - same rationale as everything else here (see
        # module docstring): filter_L60_package_HFSS.py's cavity bore needs
        # this to stay in sync with filter_L60.py's own real-package
        # constant rather than duplicating a number that could drift stale.
        'bore_diameter_um': fl60.PACKAGE_BORE_DIAMETER_UM,
    }


def regenerate_metal_region():
    """Same geometry as regenerate_metal_pieces(), merged into a single
    klayout.db.Region - used for the local Ansys-free sanity checks below
    (bbox/hole/connectivity/port-width), not for driving AEDT directly."""
    import klayout.db as kdb  # deferred, matches hfssExport.py's own convention

    geom = regenerate_metal_pieces()
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
    """x-coordinates where the hull's boundary crosses the horizontal line
    y=y_target (same technique as Hairpin_Filter/verify_hfss_export.py)."""
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
    print('verify_L60_hfss_export - Stage 1 (local, no Ansys/pyEPR)')
    print('=' * 70)
    print('GDS layers found (informational only - not the geometry source, see module docstring):')
    for layer_info in list_layers(GDS_PATH):
        print('  ', layer_info)
    print('(raw unmerged BASEMETAL shape count via extract_metal_polygons: %d)'
          % len(extract_metal_polygons(GDS_PATH, GDS_METAL_LAYER, GDS_METAL_DATATYPE)))

    geom = regenerate_metal_region()
    port1_pos, port2_pos = geom['port1_pos'], geom['port2_pos']
    polys = region_to_polys(geom['region'])
    ok = True

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

    print('=' * 70)
    if ok:
        print('ALL CHECKS PASSED')
    else:
        print('CHECKS FAILED')
        sys.exit(1)


if __name__ == '__main__':
    main()
