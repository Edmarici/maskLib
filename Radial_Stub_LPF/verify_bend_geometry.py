#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 0 regression check for verify_L30_hfss_export.py's bend_arc_points()/
_bend_advance() - entirely local, no Ansys/pyEPR needed (runs in this repo's
own .venv). Compares those two pure-math functions (freshly derived this
session from CurveRect's source, see their own docstrings) against a REAL
filter_L30.guarded_bend() call's actual output (its bookkeeping CurveRect's
discretized .points, and the real m.Structure's start/direction before and
after) - to machine precision - for both CCW=True and CCW=False. Also
computes the bend's winding (shoelace signed area) for both CCW cases, to
settle filter_L30_HFSS.py's draw_bend_native() point order ahead of time
(same technique that found/fixed the original stalk/fan winding mismatch -
see notebooks/L30_HFSS_notes.md).

Run before trusting bend_arc_points()/_bend_advance() in the HFSS bridge -
mirrors how fan_arc_points() was originally verified "to 0.000000um" against
real CurveRect output before use.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import maskLib.MaskLib as m  # noqa: E402
from verify_L30_hfss_export import bend_arc_points, _bend_advance  # noqa: E402

import filter_L30 as fl  # noqa: E402  (side effect: builds+saves the real chip once)


def _shoelace(pts):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1])) / 2


def check_case(angle_deg, CCW, w, radius, label):
    print('-' * 70)
    print('%s: angle=%d CCW=%s w=%.1f radius=%.1f' % (label, angle_deg, CCW, w, radius))

    tip = (1234.5, -678.9)
    direction_deg = 37.0  # arbitrary non-axis-aligned direction, deliberately not 0/90/180

    s = m.Structure(fl.chip, start=tip, direction=direction_deg, defaults=fl.DEFAULTS)
    real_pts = fl.guarded_bend(fl.chip, s, angle_deg, CCW, w, radius, 'BASEMETAL', label=label)
    real_end_pos, real_end_dir = s.start, s.direction

    calc_end_pos, calc_end_dir = _bend_advance(tip, direction_deg, angle_deg, CCW, radius)

    dpos = math.hypot(real_end_pos[0] - calc_end_pos[0], real_end_pos[1] - calc_end_pos[1])
    ddir = abs((real_end_dir - calc_end_dir + 180) % 360 - 180)
    print('  position/direction advance: real=%s dir=%.6f  calc=%s dir=%.6f'
          % (real_end_pos, real_end_dir, calc_end_pos, calc_end_dir))
    print('  |pos error|=%.9f um   |dir error|=%.9f deg' % (dpos, ddir))
    ok_advance = dpos < 1e-6 and ddir < 1e-9

    arc_pts = bend_arc_points(tip, direction_deg, angle_deg, CCW, w, radius)
    inner_0, inner_mid, inner_end, outer_end, outer_mid, outer_0 = arc_pts

    # 4 of the 6 key points (the true corners: inner_0, inner_end, outer_end,
    # outer_0) are EXACTLY represented, un-interpolated, in CurveRect's own
    # discretized point list (indices 0, segments+1, segments+2, and -1 - see
    # Entities.py's _calc_points rmin>0 branch) - check those against nearest-
    # neighbor distance for a genuine to-the-last-bit match. The other 2 (the
    # arc MIDPOINTS) are legitimately NOT exact discretized samples unless
    # ptDensity happens to divide evenly into angle/2 - Entities.py samples at
    # t=(i+0.5)*dTheta, which for angle=90/180 with ptDensity=120 never lands
    # exactly on angle/2 - so nearest-point distance against them is a real,
    # harmless quantization gap (~7.2um here), NOT a bug: verified separately
    # below via a discretization-independent geometric property instead
    # (distance from the arc's own rotation center equals r_in/r_out exactly).
    corner_pts = [inner_0, inner_end, outer_end, outer_0]
    max_corner_err = 0.0
    for p in corner_pts:
        nearest = min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in real_pts)
        max_corner_err = max(max_corner_err, nearest)
    print('  4 EXACT corner points vs real CurveRect.points: max nearest-point error = %.9f um' % max_corner_err)

    # rotation center = gpt(t, r=0) for any t (constant, since lx=r*sin(t)=0
    # and ly=(0*cos(t)-radius)*vflip_mult=-radius*vflip_mult don't depend on t)
    vflip_mult = 1 if CCW else -1
    rot = math.radians(direction_deg)
    center = (tip[0] + radius * vflip_mult * math.sin(rot),
              tip[1] - radius * vflip_mult * math.cos(rot))
    r_in, r_out = radius - w / 2, radius + w / 2

    def dist(p, q):
        return math.hypot(p[0] - q[0], p[1] - q[1])

    mid_radius_err = max(abs(dist(inner_mid, center) - r_in), abs(dist(outer_mid, center) - r_out))
    # also confirm the midpoints sit at exactly half the angular sweep
    # between their matching exact endpoints (not just "somewhere on the
    # right circle") - angle at center between inner_0->center->inner_mid
    # should equal angle_deg/2, same for inner_mid->inner_end.
    def angle_at_center(p, q):
        v1 = (p[0] - center[0], p[1] - center[1])
        v2 = (q[0] - center[0], q[1] - center[1])
        cos_a = (v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))
        return math.degrees(math.acos(max(-1.0, min(1.0, cos_a))))

    half1 = angle_at_center(inner_0, inner_mid)
    half2 = angle_at_center(inner_mid, inner_end)
    bisect_err = max(abs(half1 - angle_deg / 2), abs(half2 - angle_deg / 2))

    print('  2 MID points: |radius error|=%.9f um   |bisection error|=%.9f deg (half1=%.6f half2=%.6f)'
          % (mid_radius_err, bisect_err, half1, half2))
    ok_points = (max_corner_err < 1e-6) and (mid_radius_err < 1e-6) and (bisect_err < 1e-6)

    area = _shoelace(arc_pts)
    print('  bend_arc_points shoelace signed area = %.3f (%s)' % (area, 'CW' if area < 0 else 'CCW'))

    ok = ok_advance and ok_points
    print('  %s' % ('PASS' if ok else 'FAIL <<<'))
    return ok, area


def main():
    print('=' * 70)
    print('verify_bend_geometry - Stage 0 (local, no Ansys/pyEPR)')
    print('=' * 70)
    ok = True
    areas = {}
    for angle_deg in (90, 180):
        for CCW in (True, False):
            case_ok, area = check_case(angle_deg, CCW, w=125.0, radius=212.5,
                                        label='angle%d_CCW%s' % (angle_deg, CCW))
            ok &= case_ok
            areas[(angle_deg, CCW)] = area

    print('=' * 70)
    print('Winding summary (for draw_bend_native() point-order decision):')
    for (angle_deg, CCW), area in areas.items():
        print('  angle=%d CCW=%s -> %s (area=%.1f)' % (angle_deg, CCW, 'CW' if area < 0 else 'CCW', area))
    print('=' * 70)
    if ok:
        print('ALL CHECKS PASSED')
    else:
        print('CHECKS FAILED')
        sys.exit(1)


if __name__ == '__main__':
    main()
