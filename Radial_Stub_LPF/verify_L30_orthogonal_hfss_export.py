#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 regression check for filter_L30_orthogonal.py's HFSS geometry bridge
- entirely local, no Ansys/pyEPR needed (runs in this repo's own .venv).
Sibling of verify_L30_hfss_export.py (that file's own docstring has the full
story of why geometry is regenerated directly in Python rather than
round-tripped through DXF/GDS - CurveRect fan polylines get corrupted by the
DXF write/GDS read cycle, invisible to bbox/hole checks but fatal to AEDT's
Parasolid CreatePolyline). This file only retargets the loader at
filter_L30_orthogonal.py instead of filter_L30.py - all geometry-math helpers
below are unchanged copies (topology-generic: same BRANCH_PAIRS/
SERIES_SECTIONS schema, same centered-top-pad/straight-down-main-line layout,
just tilt=0 everywhere and a wider chip).
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

GDS_PATH = os.path.join(os.path.dirname(__file__), 'DXF', 'filter_L30_orthogonal_CHIP_L30_ORTHO.gds')
GDS_METAL_LAYER = 2      # BASEMETAL - confirmed via gds_layer_number(wafer, 'BASEMETAL')
GDS_METAL_DATATYPE = 0

# Expectations - same as filter_L30.py's (see verify_L30_hfss_export.py):
EXPECTED_N_MERGED_POLYGONS = 1   # everything fuses into one connected trace
MAX_HOLE_AREA_UM2 = 10.0   # exact-touching joints should give 0 real holes; small
                           # threshold (not strict 0) just absorbs float noise


def _load_filter_L30_orthogonal():
    """Import filter_L30_orthogonal.py as a module for its live tables
    (SERIES_SECTIONS, BRANCH_PAIRS - all tilt=0.0, pad/taper/output
    constants) - re-runs the whole script (chip build, print block, DXF/GDS
    save) as a side effect, so its own stdout is suppressed here."""
    spec = importlib.util.spec_from_file_location(
        'filter_L30_orthogonal', os.path.join(os.path.dirname(__file__), 'filter_L30_orthogonal.py'))
    module = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(module)
    return module


def _rect_poly(start, direction_deg, length, w0, w1):
    """Proper-winding (simple, non-self-intersecting) quad for a straight or
    tapered metal segment - see verify_L30_hfss_export.py's own docstring."""
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
    code uses - see verify_L30_hfss_export.py's own docstring."""
    perp = (math.cos(math.radians(direction_deg + 90)), math.sin(math.radians(direction_deg + 90)))
    insert = (tip[0] + (attach_width / 2) * perp[0], tip[1] + (attach_width / 2) * perp[1])
    rotation = direction_deg + fan_angle_deg / 2 - 90
    cr = CurveRect(insert, height=r_out - r_in, radius=r_in, angle=fan_angle_deg, rotation=rotation,
                    ralign=const.BOTTOM, ptDensity=120)
    cr._build()
    return list(cr.points)


def fan_arc_points(tip, direction_deg, r_out, r_in, fan_angle_deg, attach_width):
    """The 6 points needed to draw one fan as 2 TRUE native arcs + 2
    straight radial edges - identical formula to verify_L30_hfss_export.py's
    (topology-generic, no filter_L30-specific values) - see that file's own
    docstring for the full derivation/why."""
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


def _build_pieces(fl30o, stalk_fan_overlap_um=0.0):
    """Yields (label, hull_points, fan_params) for every individual metal
    primitive - identical replay logic to verify_L30_hfss_export.py's
    _build_pieces(), just parameterized on the passed-in module (here,
    filter_L30_orthogonal's live tables) instead of filter_L30's. Relies on
    the two files sharing the same BRANCH_PAIRS/SERIES_SECTIONS schema and
    drawing topology (centered top pad, straight-down main line) - true by
    construction, since filter_L30_orthogonal.py only changes tilt/chip
    width, not the drawing sequence itself. See stalk_fan_overlap_um's
    meaning in verify_L30_hfss_export.py's own docstring."""
    x0 = fl30o.chip.width / 2
    pos = (x0, fl30o.chip.height - fl30o.PAD_EDGE_MARGIN)
    direction = -90.0
    yield 'port1_pos', pos, None   # pin pad's OUTER (chip-edge-facing) edge - the actual port 1 location

    pts, pos = _rect_poly(pos, direction, fl30o.PIN_PAD_LENGTH, fl30o.PIN_PAD_WIDTH, fl30o.PIN_PAD_WIDTH)
    yield 'PinPad', pts, None
    pts, pos = _rect_poly(pos, direction, fl30o.INOUT_TAPER_LEN, fl30o.PIN_PAD_WIDTH,
                                   fl30o.SERIES_SECTIONS[0]['width'])
    yield 'InputTaper', pts, None
    w1 = fl30o.SERIES_SECTIONS[0]['width']
    pts, pos = _rect_poly(pos, direction, 2 * fl30o.INOUT_TAPER_LEN, w1, w1)
    yield 'InputTaperStraight', pts, None

    for branch, section in zip(fl30o.BRANCH_PAIRS, fl30o.SERIES_SECTIONS):
        for sign, side in ((+1, 'a'), (-1, 'b')):
            b_dir = direction + sign * (90 + branch['tilt'])
            stalk_pts, tip = _rect_poly(pos, b_dir, branch['stalk_length'] + stalk_fan_overlap_um,
                                                       branch['stalk_width'], branch['stalk_width'])
            if stalk_fan_overlap_um:
                _, tip = _rect_poly(pos, b_dir, branch['stalk_length'],
                                     branch['stalk_width'], branch['stalk_width'])
            yield '%s%s_stalk' % (branch['name'], side), stalk_pts, None
            fan_params = (tip, b_dir, branch['fan_rout'], branch['fan_rin'],
                          branch['fan_angle'], branch['attach_width'])
            yield '%s%s_fan' % (branch['name'], side), _fan_poly(*fan_params), fan_params
        pts, pos = _rect_poly(pos, direction, section['length'], section['width'], section['width'])
        yield 'Line_after_%s' % branch['name'], pts, None

    pts, pos = _rect_poly(pos, direction, fl30o.INOUT_TAPER_LEN, fl30o.SERIES_SECTIONS[-1]['width'],
                                   fl30o.OUTPUT_LINE_WIDTH)
    yield 'OutputTaper', pts, None
    pts, pos = _rect_poly(pos, direction, 2 * fl30o.INOUT_TAPER_LEN,
                                   fl30o.OUTPUT_LINE_WIDTH, fl30o.OUTPUT_LINE_WIDTH)
    yield 'OutputTaperStraight', pts, None
    run_len = pos[1] - (fl30o.SNAIL_KEEPOUT_CY + fl30o.SNAIL_KEEPOUT_H / 2 + fl30o.KEEPOUT_CLEARANCE)
    pts, pos = _rect_poly(pos, direction, run_len, fl30o.OUTPUT_LINE_WIDTH, fl30o.OUTPUT_LINE_WIDTH)
    yield 'OutputLine', pts, None
    yield 'port2_pos', pos, None   # tip of the drawn output line - the actual port 2 location


def regenerate_metal_pieces(stalk_fan_overlap_um=0.0):
    """Rebuilds filter_L30_orthogonal's BASEMETAL geometry directly, as a
    list of (label, hull_points) - deliberately UNMERGED. Mirrors
    verify_L30_hfss_export.py's regenerate_metal_pieces() exactly, just
    against filter_L30_orthogonal's module. See _build_pieces() for
    stalk_fan_overlap_um."""
    fl30o = _load_filter_L30_orthogonal()
    pieces = []
    ports = {}
    for label, data, fan_params in _build_pieces(fl30o, stalk_fan_overlap_um=stalk_fan_overlap_um):
        if label in ('port1_pos', 'port2_pos'):
            ports[label] = data
        else:
            pieces.append((label, data, fan_params))
    return {
        'pieces': pieces,
        'port1_pos': ports['port1_pos'], 'port1_width': fl30o.PIN_PAD_WIDTH,
        'port2_pos': ports['port2_pos'], 'port2_width': fl30o.OUTPUT_LINE_WIDTH,
    }


def regenerate_metal_region():
    """Same geometry as regenerate_metal_pieces(), merged into a single
    klayout.db.Region - used for the local Ansys-free sanity checks below."""
    import klayout.db as kdb  # deferred, matches hfssExport.py's own convention

    geom = regenerate_metal_pieces()
    dbu = 0.001
    region = kdb.Region()
    for _label, pts, _fan_params in geom['pieces']:
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
    print('verify_L30_orthogonal_hfss_export - Stage 1 (local, no Ansys/pyEPR)')
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
