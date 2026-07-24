#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2 of the L60 impedance-contrast + Al cavity package handoff: HFSS
Driven Modal S21 setup for the REAL superconducting aluminum cavity package
(cylindrical bore, PEC walls) around filter_L60.py's geometry - replaces
Phase 1's open-sim-volume/proxy-ground rectangular box (filter_L60_HFSS.py,
kept unchanged and still valid as its own already-verified sanity run) with
a real model of how the device is actually packaged.

NEW FILE, not an edit to filter_L60_HFSS.py - matches this codebase's
convention of self-contained, purpose-scoped HFSS driver files (see
CLAUDE.md). Reuses filter_L60_HFSS.py's own metal-piece-building loop
(draw_fan_native/draw_bend_native/Unite()) verbatim, and
verify_L60_hfss_export.regenerate_metal_pieces() as the geometry source
(same live-replay-from-filter_L60.py mechanism, so this picks up the taper
fix and the Step-0 bore/chip-width revision below automatically).

PACKAGE NUMBERS (revised this session, Eddie): bore diameter 7.0mm (radius
3.5mm, up from the handoff doc's 6.985mm), chip usable width 6.9mm (down
from 7.0mm) - both are now the real constants in filter_L60.py itself
(PACKAGE_BORE_DIAMETER_UM, the w.Wafer(...) call), not simulation-only
approximations. Deliberate pairing: a 6.9mm-wide, mid-thickness-centered
500um chip has corner-to-bore-axis distance sqrt(3450^2+250^2)=3459.3um,
just inside the 3500um bore radius (40.7um clearance at the corners - the
binding point for a rectangle inscribed near a circle). **This means the
chip's cross-section fits entirely inside the round bore - no mounting
pocket is modeled here.** Handoff item O1 (real pocket/slot geometry) is
still an open question for the actual mechanical package, but the
simulation no longer needs a wall cutout to represent it - this was the
explicit simplification Eddie asked for.

MODELING CHOICES vs. the handoff doc's Phase 2 spec:
  - Chip vertical centering (O2): mid-thickness on the bore axis (the
    doc's own default) - substrate spans Z=-250..+250um relative to the
    bore's own axis-Z; the bore cylinder's center is placed at
    Z=-SAPPHIRE_THICKNESS_UM/2 in filter_L60_HFSS.py's own Z=0-at-chip-top
    convention (substrate [-500,0], metal [0,METAL_THICKNESS_UM]) - this
    achieves the same "chip mid-thickness on the bore axis" relationship
    without needing to translate the metal/substrate after the fact.
  - Bore axial length: metal bbox Y-extent + 2x BORE_AXIAL_MARGIN_UM
    (5000um, per the doc's "filter extent + >=5mm margin each end").
  - End caps: the two flat axial ends of the modeled bore section get
    PerfectE too (one whole-object assign_perfect_E call covers the
    curved wall AND both end caps). ASSUMPTION, not in the doc: no port or
    radiation boundary sits there, and pyEPR has no radiation-boundary
    wrapper anyway (confirmed absent - same gap Hairpin_Filter_HFSS.py's
    own docstring flags). Reasonable given the doc's own margin framing -
    sub-cutoff evanescent decay (bore TE11 cutoff ~25GHz vacuum, well
    above this sweep) makes the exact end treatment immaterial at 5mm.
  - Ports: handoff option (a) - lumped ports from each trace end
    VERTICALLY to the bore wall (fast, doesn't need option (b)'s pin-
    coupler geometry, O3, which isn't available). Both ports sit
    essentially on the bore's own X-center (the main line runs along the
    bore axis), so the wall intersection simplifies to Z = bore_axis_z +
    BORE_RADIUS_UM (straight up to the top of the circle) with no per-port
    trig needed. Port face rectangle + explicit um()-suffixed integration
    line: same CreateRectangle/_make_lumped_port pattern already proven
    working in Hairpin_Filter_HFSS.py (lines ~290-335 there) - bypasses
    Rect.make_lumped_port()'s known mm/um unit bug documented there.
    CAVEAT (flagging, not fixing): the integration line is ~3.25mm long -
    a much longer "ground return" path than a typical on-chip lumped
    port. The doc's own framing ("fast, fine for filter shaping") already
    anticipates this isn't the final-fidelity answer; option (b) (real
    pin couplers) is the documented follow-up once O3 exists.
  - Unit handling for the NEW cylinder/rectangle raw COM calls: passed as
    explicit um()-suffixed strings throughout (never bare Python floats),
    matching the proven-safe pattern this repo already uses for every
    polyline/rectangle vertex (filter_L60_HFSS.py's draw_fan_native/
    draw_bend_native, Hairpin's make_port). Deliberately NOT using pyEPR's
    draw_cylinder_center() convenience wrapper's own var()/height-halving
    arithmetic (untested in this repo, no prior usage found) or bare-float
    inputs to draw_cylinder() (draw_box_corner's own bare-float path is
    the one CLAUDE.md documents silently defaulting to METERS regardless
    of set_units('um') - "got a ~500m box from a 500um input" - the
    substrate box below still uses that ALREADY-proven meters-prescaled
    draw_box_corner() pattern verbatim from filter_L60_HFSS.py; the new
    cylinder avoids the whole class of bug by using unit-suffixed strings
    on a raw CreateCylinder call instead).
  - Sweep range: extended locally to 13.0GHz (doc: "re-run the 9-13GHz
    discrete sweep") - SWEEP_STOP_GHZ from the shared
    filter_L30_hfss_geometry module stays 12.0 for Phase 1's own already-
    validated run; overridden here only. Kept as one Interpolating sweep
    rather than a separate discrete-sweep setup - AEDT's interpolating
    algorithm adaptively refines to its error tolerance, which should
    resolve the doublet features the doc wants checked; flagged as a
    simplification, easy to revisit if it doesn't resolve the P3 doublet
    cleanly.

STAGING (matches every prior HFSS script in this repo): RUN_ANALYSIS starts
False - build geometry (bore, substrate, metal, ports, setup) and stop, so
Unite()/port construction can be confirmed (via a fresh diagnostic
connection - CLAUDE.md's duplicate-AEDT-project lesson: enumerate every
same-named project handle and check each individually, don't trust a first
match) before spending real solve time on genuinely new geometry.

RUN VIA THE SEPARATE PYEPR ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe filter_L60_package_HFSS.py
Run from THIS file's own directory.
"""

import csv
import os
import sys

import numpy as np
from pyEPR import ansys as HFSS

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from verify_L60_hfss_export import regenerate_metal_pieces, fan_arc_points, bend_arc_points  # noqa: E402

from filter_L30_hfss_geometry import (  # noqa: E402
    SAPPHIRE_THICKNESS_UM, METAL_THICKNESS_UM, Z0_PORT, SWEEP_START_GHZ, um,
)

RUN_ANALYSIS = True

# Doc: "filter extent + >=5mm margin each end."
BORE_AXIAL_MARGIN_UM = 5000.0

# Matches filter_L60.py's own w.Wafer(...) usable width (Step 0 revision) -
# duplicated here per this repo's self-contained-file convention (same as
# SAPPHIRE_THICKNESS_UM etc. being duplicated via filter_L30_hfss_geometry.py
# rather than importing filter_L60 directly).
SAPPHIRE_WIDTH_UM = 6900.0

# Doc: "re-run the 9-13GHz discrete sweep" - see module docstring's
# "Sweep range" note for why this stays a single Interpolating sweep.
SWEEP_STOP_GHZ_PKG = 13.0
SWEEP_COUNT_PKG = 2501  # ~5MHz resolution over 0.5-13GHz, matching Phase 1's density

_UM_TO_M = 1e-6  # for draw_box_corner() calls only - see module docstring


# ===============================================================================
# connection + Driven Modal design setup (same duplicate-project-safe
# pattern as filter_L60_HFSS.py - see that file's own docstring for the
# real bug this guards against)
# ===============================================================================

project_name = 'filter_L60_package_S21'
design_name = 'Driven Modal'
overwrite = True

HFSS_path = os.getcwd()
full_path = os.path.join(HFSS_path, project_name + '.aedt')

HFSS_app = HFSS.HfssApp()
HFSS_desktop = HFSS_app.get_app_desktop()

_existing = [p for p in HFSS_desktop.get_projects() if p.name == project_name]
if _existing:
    project = _existing[0]
    project.make_active()
else:
    try:
        project = HFSS_desktop.open_project(full_path)
        project.make_active()
    except Exception:
        project = HFSS_desktop.new_project()
        project.save(full_path)

existing_design_names = [d.name for d in project.get_designs()]
if design_name in existing_design_names:
    if overwrite:
        project._project.DeleteDesign(design_name)
        project.save()
        DM_design = project.new_dm_design(design_name)
    else:
        DM_design = project.get_design(design_name)
else:
    DM_design = project.new_dm_design(design_name)

model = DM_design.modeler
model.set_units('um')


# ===============================================================================
# filter metal geometry - verbatim copy of filter_L60_HFSS.py's own
# draw_fan_native/draw_bend_native/piece-building loop (see that file's
# docstring for the Unite()-winding-order + exit-turn-to-fan overlap fixes
# baked into these). Drawn at Z=0..METAL_THICKNESS_UM, same convention as
# filter_L60_HFSS.py - the package below is what changes, not this.
# ===============================================================================

def draw_fan_native(model, label, fan_params):
    tip, direction_deg, r_out, r_in, fan_angle_deg, attach_width = fan_params
    p_in0, p_inmid, p_inend, p_outend, p_outmid, p_out0 = fan_arc_points(
        tip, direction_deg, r_out, r_in, fan_angle_deg, attach_width)
    pts = [p_out0, p_outmid, p_outend, p_inend, p_inmid, p_in0, p_out0]  # reversed -> CW, closing duplicate

    pointsStr = ['NAME:PolylinePoints']
    for x, y in pts:
        pointsStr.append(['NAME:PLPoint', 'X:=', um(x), 'Y:=', um(y), 'Z:=', '0um'])
    segStr = ['NAME:PolylineSegments',
              ['NAME:PLSegment', 'SegmentType:=', 'Arc', 'StartIndex:=', 0, 'NoOfPoints:=', 3],
              ['NAME:PLSegment', 'SegmentType:=', 'Line', 'StartIndex:=', 2, 'NoOfPoints:=', 2],
              ['NAME:PLSegment', 'SegmentType:=', 'Arc', 'StartIndex:=', 3, 'NoOfPoints:=', 3],
              ['NAME:PLSegment', 'SegmentType:=', 'Line', 'StartIndex:=', 5, 'NoOfPoints:=', 2]]
    name = model._modeler.CreatePolyline(
        ['NAME:PolylineParameters', 'IsPolylineCovered:=', True, 'IsPolylineClosed:=', True,
         pointsStr, segStr],
        model._attributes_array(name=label))
    return name


def draw_bend_native(model, label, bend_arc_params):
    tip, direction_deg, angle_deg, CCW, w, radius = bend_arc_params
    p_in0, p_inmid, p_inend, p_outend, p_outmid, p_out0 = bend_arc_points(
        tip, direction_deg, angle_deg, CCW, w, radius)
    pts = [p_in0, p_inmid, p_inend, p_outend, p_outmid, p_out0, p_in0]
    if CCW:
        pts = [p_out0, p_outmid, p_outend, p_inend, p_inmid, p_in0, p_out0]  # reverse CCW -> CW

    pointsStr = ['NAME:PolylinePoints']
    for x, y in pts:
        pointsStr.append(['NAME:PLPoint', 'X:=', um(x), 'Y:=', um(y), 'Z:=', '0um'])
    segStr = ['NAME:PolylineSegments',
              ['NAME:PLSegment', 'SegmentType:=', 'Arc', 'StartIndex:=', 0, 'NoOfPoints:=', 3],
              ['NAME:PLSegment', 'SegmentType:=', 'Line', 'StartIndex:=', 2, 'NoOfPoints:=', 2],
              ['NAME:PLSegment', 'SegmentType:=', 'Arc', 'StartIndex:=', 3, 'NoOfPoints:=', 3],
              ['NAME:PLSegment', 'SegmentType:=', 'Line', 'StartIndex:=', 5, 'NoOfPoints:=', 2]]
    name = model._modeler.CreatePolyline(
        ['NAME:PolylineParameters', 'IsPolylineCovered:=', True, 'IsPolylineClosed:=', True,
         pointsStr, segStr],
        model._attributes_array(name=label))
    return name


STALK_FAN_OVERLAP_UM = 5.0

geom = regenerate_metal_pieces(stalk_fan_overlap_um=STALK_FAN_OVERLAP_UM)
pieces = geom['pieces']
print('Regenerated %d metal piece(s) directly from filter_L60.py (no DXF/GDS round-trip)' % len(pieces))

metal_names = []
for i, (label, hull, kind, arc_params) in enumerate(pieces):
    if kind == 'fan':
        sheet = draw_fan_native(model, label, arc_params)
    elif kind == 'bend':
        sheet = draw_bend_native(model, label, arc_params)
    else:
        points_3d = [[um(x), um(y), '0um'] for x, y in hull]
        sheet = model.draw_polyline(points_3d, closed=True, name=label)
    model.sweep_along_vector([str(sheet)], ['0um', '0um', um(METAL_THICKNESS_UM)])
    metal_names.append(str(sheet))
    print('  built solid %d/%d: %s (%s)' % (i + 1, len(pieces), sheet,
                                             kind if kind else '%d vertices' % len(hull)))

METAL_OBJ_NAME = model.unite(metal_names)
print('United all %d pieces -> %s' % (len(metal_names), METAL_OBJ_NAME))

model._modeler.ChangeProperty(
    ['NAME:AllTabs',
     ['NAME:Geometry3DAttributeTab',
      ['NAME:PropServers', METAL_OBJ_NAME],
      ['NAME:ChangedProps', ['NAME:Material', 'Value:=', '"aluminum"']]]])


# ===============================================================================
# package: real cylindrical Al cavity bore (PEC walls) + chip substrate -
# see module docstring for the Z-convention and unit-handling rationale.
# ===============================================================================

BORE_RADIUS_UM = geom['bore_diameter_um'] / 2.0  # live from filter_L60.py, not re-derived

bore_center_x = geom['port1_pos'][0]
assert abs(geom['port2_pos'][0] - bore_center_x) < 1.0, \
    'port1/port2 X positions disagree (%r vs %r) - main line is not straight?' % (
        bore_center_x, geom['port2_pos'][0])

all_ys = [y for _label, hull, _kind, _arc_params in pieces for x, y in hull]
ymin, ymax = min(all_ys), max(all_ys)

bore_len_um = (ymax - ymin) + 2 * BORE_AXIAL_MARGIN_UM
bore_y0_edge_um = ymin - BORE_AXIAL_MARGIN_UM  # CreateCylinder's Y is the starting edge, not the true center
bore_axis_z_um = -SAPPHIRE_THICKNESS_UM / 2.0  # chip mid-thickness, under this file's Z=0-at-chip-top convention

bore_name = model._modeler.CreateCylinder(
    ['NAME:CylinderParameters',
     'XCenter:=', um(bore_center_x),
     'YCenter:=', um(bore_y0_edge_um),
     'ZCenter:=', um(bore_axis_z_um),
     'Radius:=', um(BORE_RADIUS_UM),
     'Height:=', um(bore_len_um),
     'WhichAxis:=', 'Y',
     'NumSides:=', 0],
    model._attributes_array(name='BoreVacuum', material='vacuum'))
print('Bore cylinder: radius %.1fum, axial length %.1fum (Y %.1f..%.1f), axis Z=%.1fum'
      % (BORE_RADIUS_UM, bore_len_um, bore_y0_edge_um, bore_y0_edge_um + bore_len_um, bore_axis_z_um))

sub_x0 = bore_center_x - SAPPHIRE_WIDTH_UM / 2.0
substrate = model.draw_box_corner(
    [sub_x0 * _UM_TO_M, bore_y0_edge_um * _UM_TO_M, -SAPPHIRE_THICKNESS_UM * _UM_TO_M],
    [SAPPHIRE_WIDTH_UM * _UM_TO_M, bore_len_um * _UM_TO_M, SAPPHIRE_THICKNESS_UM * _UM_TO_M],
    material='sapphire',
    name='Substrate',
)

# Single whole-object PerfectE call covers the curved wall AND both flat
# axial end caps - see module docstring's "End caps" note.
model.assign_perfect_E([bore_name], name='Package_Walls')
model.assign_perfect_E([METAL_OBJ_NAME], name='Filter_Metal')


# ===============================================================================
# lumped ports (handoff option (a)) - see module docstring's "Ports" note.
# Pattern (raw CreateRectangle + explicit-um() integration line via
# model._make_lumped_port) copied from Hairpin_Filter_HFSS.py's own
# make_port(), adapted for a VERTICAL (trace-to-bore-wall) line instead of
# its horizontal (across-trace-width) one.
# ===============================================================================

def make_port(name, port_pos, width_um):
    x0, y0 = port_pos
    z_bot = 0.0  # chip top surface / substrate top
    z_top = bore_axis_z_um + BORE_RADIUS_UM  # straight up to the bore wall
    z_mid = METAL_THICKNESS_UM / 2.0

    pos = [x0 - width_um / 2, y0, z_bot]
    size = [width_um, 0, z_top - z_bot]  # y_size=0 sentinel -> WhichAxis='Y'
    axis = 'XYZ'[size.index(0)]
    w_idx, h_idx = {'X': (1, 2), 'Y': (2, 0), 'Z': (0, 1)}[axis]
    rect_name = model._modeler.CreateRectangle(
        ['NAME:RectangleParameters',
         'XStart:=', um(pos[0]), 'YStart:=', um(pos[1]), 'ZStart:=', um(pos[2]),
         'Width:=', um(size[w_idx]), 'Height:=', um(size[h_idx]), 'WhichAxis:=', axis],
        ['NAME:Attributes', 'Name:=', name + '_face', 'Flags:=', '',
         'Color:=', '(132 132 193)', 'Transparency:=', 0.9,
         'PartCoordinateSystem:=', 'Global', 'UDMId:=', '',
         'MaterialValue:=', '"vacuum"', 'SolveInside:=', True],
    )

    start = [um(x0), um(y0), um(z_mid)]
    end = [um(x0), um(y0), um(z_top)]
    model._make_lumped_port(start, end, ['Objects:=', [rect_name]], z0=Z0_PORT, name=name)
    print('  port %s: face X=%.1f..%.1f Z=%.1f..%.1f @ Y=%.1f, line Z %.1f -> %.1f'
          % (name, pos[0], pos[0] + width_um, z_bot, z_top, y0, z_mid, z_top))
    return rect_name


port1 = make_port('P1', geom['port1_pos'], geom['port1_width'])
port2 = make_port('P2', geom['port2_pos'], geom['port2_width'])


# ===============================================================================
# Driven Modal analysis setup + frequency sweep (always built - cheap);
# the actual solve is gated behind RUN_ANALYSIS (see module docstring)
# ===============================================================================

DM_setup = DM_design.create_dm_setup(
    freq_ghz=(SWEEP_START_GHZ + SWEEP_STOP_GHZ_PKG) / 2,
    name='S21_Setup',
    max_delta_s=0.02,
    max_passes=12,
    min_passes=3,
    min_converged=2,
    pct_refinement=30,
    basis_order=1,
)

DM_sweep = DM_setup.insert_sweep(
    start_ghz=SWEEP_START_GHZ,
    stop_ghz=SWEEP_STOP_GHZ_PKG,
    count=SWEEP_COUNT_PKG,
    step_ghz=None,
    name='S21_Sweep',
    type='Interpolating',
)

project.save()

if not RUN_ANALYSIS:
    print('Setup complete (RUN_ANALYSIS=False). Inspect the model in AEDT '
          '(confirm Unite() succeeded on the metal - METAL_OBJ_NAME should '
          'be a single solid, not null/Unclassified; confirm BoreVacuum is '
          'a real cylinder and both P1/P2 lumped ports appear in the '
          'boundary list - via a FRESH COM connection, enumerating every '
          'project handle matching the name and checking each individually, '
          'not just the first match - see CLAUDE.md\'s HFSS section), then '
          'set RUN_ANALYSIS=True and re-run to solve + pull S21/S11.')
else:
    print('RUN_ANALYSIS=True: running DM_setup.analyze() - this can take a '
          'while (adaptive mesh over metal + substrate + bore, up to 12 '
          'passes, %d-point interpolating sweep).' % SWEEP_COUNT_PKG)
    DM_setup.analyze()

    out_dir = os.path.join(os.path.dirname(__file__), 'HFSS')
    os.makedirs(out_dir, exist_ok=True)

    def _pull(expr, label):
        report = DM_sweep.create_report('Temp_%s' % label, expr)
        tmp_path = os.path.join(out_dir, '_tmp_%s_export.csv' % label)
        report.export_to_file(tmp_path)
        freqs_, vals_ = np.loadtxt(tmp_path, skiprows=1, delimiter=',').transpose()
        os.remove(tmp_path)
        return freqs_, vals_

    freqs, s21_db = _pull('dB(S(P2,P1))', 'S21')
    _, s11_db = _pull('dB(S(P1,P1))', 'S11')

    s21_csv_path = os.path.join(out_dir, 'filter_L60_package_S21.csv')
    with open(s21_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_GHz', 'S21_dB'])
        writer.writerows(zip(freqs, s21_db))
    print('S21 data saved -> %s' % s21_csv_path)

    s11_csv_path = os.path.join(out_dir, 'filter_L60_package_S11.csv')
    with open(s11_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_GHz', 'S11_dB'])
        writer.writerows(zip(freqs, s11_db))
    print('S11 data saved -> %s' % s11_csv_path)

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(freqs, s21_db, label='S21')
        ax.plot(freqs, s11_db, label='S11')
        ax.set_xlabel('Frequency (GHz)')
        ax.set_ylabel('dB')
        ax.set_title('filter_L60 - S21/S11 (Phase 2: real Al cavity package)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        png_path = os.path.join(out_dir, 'filter_L60_package_S21.png')
        fig.savefig(png_path, dpi=150, bbox_inches='tight')
        print('S21/S11 plot saved -> %s' % png_path)
    except ImportError:
        print('matplotlib not available in this environment - CSV saved, plot skipped.')
