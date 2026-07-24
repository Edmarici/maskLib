#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 regression check for the GDS->HFSS geometry bridge
(maskLib.hfssExport): confirms the TRUE final conductor polygons (derived
from the raw XOR/gap layer via extract_xor_derived_metal - NOT the
fill_basemetal_from_xor flood layer, which is only an intermediate result,
see hairpin_filter_geometry.py) match what we independently know is true
about Hairpin_Filter.py's design: the coordinate-traced port positions and
the fact that line_width=500um should be the real conductor width at both
port cut planes. Entirely local, no Ansys/pyEPR needed. Run after
regenerating Hairpin_Filter/DXF/Hairpin_Filter_CHIP_HAIRPINBPF.gds (run
Hairpin_Filter.py first if it doesn't exist yet).
"""

import sys

sys.path.insert(0, r'c:\Users\epm114\Desktop\Masklib\src')
from maskLib.hfssExport import list_layers, extract_xor_derived_metal

from hairpin_filter_geometry import (
    GDS_PATH, GDS_GAP_LAYER, GDS_GAP_DATATYPE,
    PORT1_POS_UM, PORT2_POS_UM,
)

EXPECTED_BBOX = (315.34, 15070.6, 6184.66, 29300.0)   # (xmin, ymin, xmax, ymax), true-conductor union bbox
EXPECTED_N_POLYGONS = 4   # one per electrically-continuous trace run (3 coupling gaps split the n=4 array)
TRUE_CONDUCTOR_WIDTH_UM = 500.0   # line_width - NOT the 540um CPW envelope (conductor + 2*gap)


def bbox_of(polygons):
    xs = [x for p in polygons for x, y in p.hull]
    ys = [y for p in polygons for x, y in p.hull]
    return min(xs), min(ys), max(xs), max(ys)


def x_crossings_at_y(polygon, y_cut):
    '''x-coordinates where polygon's hull boundary crosses the horizontal line y=y_cut.'''
    pts = polygon.hull
    n = len(pts)
    xs = []
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if y1 == y2:
            continue
        if (y1 <= y_cut <= y2) or (y2 <= y_cut <= y1):
            t = (y_cut - y1) / (y2 - y1)
            xs.append(x1 + t * (x2 - x1))
    return sorted(set(round(x, 3) for x in xs))


def check_port(name, polygons, pos_um):
    x0, y0 = pos_um
    expected = (round(x0 - TRUE_CONDUCTOR_WIDTH_UM / 2, 3), round(x0 + TRUE_CONDUCTOR_WIDTH_UM / 2, 3))
    hits = []
    for poly in polygons:
        xs = x_crossings_at_y(poly, y0)
        if xs:
            hits.extend(xs)
    hits = sorted(set(hits))
    ok = tuple(hits) == expected
    print('%s: y=%.1f true conductor edges at x=%s (expected %s, width=%.1fum) -> %s'
          % (name, y0, hits, expected, TRUE_CONDUCTOR_WIDTH_UM, 'OK' if ok else 'MISMATCH'))
    return ok


def main():
    print('Layers in %s:' % GDS_PATH)
    for l in list_layers(GDS_PATH):
        print('  layer=%(layer)d datatype=%(datatype)d shapes=%(shape_count)d' % l)

    polygons = extract_xor_derived_metal(GDS_PATH, GDS_GAP_LAYER, GDS_GAP_DATATYPE)
    print('\nExtracted %d true-conductor polygon(s) from gap layer %d/%d' %
          (len(polygons), GDS_GAP_LAYER, GDS_GAP_DATATYPE))
    for i, p in enumerate(polygons):
        xs = [x for x, y in p.hull]
        ys = [y for x, y in p.hull]
        print('  [%d] hull_pts=%d holes=%d bbox=(%.2f,%.2f)-(%.2f,%.2f)'
              % (i, len(p.hull), len(p.holes), min(xs), min(ys), max(xs), max(ys)))

    ok = True
    ok &= len(polygons) == EXPECTED_N_POLYGONS
    print('\npolygon count: %d (expected %d) -> %s'
          % (len(polygons), EXPECTED_N_POLYGONS, 'OK' if len(polygons) == EXPECTED_N_POLYGONS else 'MISMATCH'))

    ok &= all(len(p.holes) == 0 for p in polygons)
    print('holes: %s -> %s' % ([len(p.holes) for p in polygons],
                                'OK' if all(len(p.holes) == 0 for p in polygons) else 'MISMATCH'))

    real_bbox = bbox_of(polygons)
    bbox_ok = all(abs(a - b) < 0.01 for a, b in zip(real_bbox, EXPECTED_BBOX))
    ok &= bbox_ok
    print('union bbox: %s (expected %s) -> %s'
          % (tuple(round(v, 2) for v in real_bbox), EXPECTED_BBOX, 'OK' if bbox_ok else 'MISMATCH'))

    ok &= check_port('Port1 (input)', polygons, PORT1_POS_UM)
    ok &= check_port('Port2 (output)', polygons, PORT2_POS_UM)

    print('\n' + ('ALL CHECKS PASSED' if ok else 'CHECKS FAILED'))
    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
