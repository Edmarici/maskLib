#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HFSS Driven Modal S21 setup (and, when RUN_ANALYSIS=True, solve + S21/S11
extraction) for the L60 10th-order elliptic lowpass filter
(Radial_Stub_LPF/filter_L60.py -> DXF/filter_L60_CHIP_L60.gds).

Sibling of filter_L30_HFSS.py - built to run the exact same wave-port S21
pipeline against filter_L60.py's geometry. Every low-level pyEPR 0.8 API
workaround, the Unite() winding-order fix (for both fans AND bends), the
exit-turn-to-fan joint-overlap fix, and the wave-port restructuring are
unchanged copies of filter_L30_HFSS.py's own (hand-verified against the
real installed pyEPR/AEDT across two separate sessions) - see that file's
own docstring for the full rationale on each point. Only the project/output
naming and the geometry-source import differ - PLUS one real fix baked in
from the start here rather than left as a known bug: S21/S11 are pulled via
an explicit export path (report.export_to_file(<path>) read back directly),
NOT pyEPR's default HfssFrequencySweep.get_report_arrays()/
HfssReport.get_arrays(), which relies on tempfile.mktemp() and can fail with
FileNotFoundError even after a fully successful solve (confirmed this
session on filter_L30_HFSS.py itself - see CLAUDE.md's HFSS section and
notebooks/L30_HFSS_notes.md sec 8). filter_L30_HFSS.py itself still uses
the buggy default (worked when last run, but not fixed there) and doesn't
pull S11 at all (a separate ad-hoc follow-up script did, this session) -
both fixed here from the start instead of being left for a future session
to rediscover.

RUN VIA THE SEPARATE PYEPR ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe filter_L60_HFSS.py
Run from THIS file's own directory (so the relative DXF/GDS paths in
filter_L30_hfss_geometry.py resolve).

WHAT'S DIFFERENT FROM filter_L30_HFSS.py:

  GEOMETRY SOURCE - imports regenerate_metal_pieces/fan_arc_points/
    bend_arc_points from verify_L60_hfss_export instead, which replays
    filter_L60.py's own tables (5 branches: P1/P5 straight, P2/P3/P4
    folded meanders, all n_par_runs=2 - no L-bend branches active in the
    current filter_L60.py build, see that file's own BRANCH_FOLDS).

  DIFFERENT CROPPED MODEL DOMAIN - the live metal bounding box here
    reflects L60's own 5-branch geometry (6265.0um transverse, per
    filter_L60.py's own printed report) - the cropped Substrate/Package
    region (metal bbox + MODEL_PADDING_UM/PACKAGE_PADDING_UM, unchanged
    constants) scales automatically, no code change needed.

  EXPLICIT-PATH S21/S11 EXPORT - see module docstring above. Both S21 and
    S11 pulled this way from the start (filter_L30_HFSS.py only pulls S21,
    via the buggy default helper).

  PROJECT/OUTPUT NAMING ONLY otherwise - project_name, and the S21/S11
    CSV/PNG basenames, are renamed to filter_L60_orthogonal_* -> actually
    filter_L60_* so results don't collide with filter_L30.py's own
    HFSS/filter_L30_S21.csv etc.

Everything else (proxy-ground Package construction, wave-port face
selection + AssignWavePort, DM setup/sweep, RUN_ANALYSIS staging) is an
unchanged copy of filter_L30_HFSS.py - see that file's own docstring for
the PROXY GROUND / WAVE PORTS / OUTPUT PORT IS A STAND-IN sections, which
apply identically here (same no-ground-plane chip, same stand-in output
port at the drawn line's tip).
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
    SAPPHIRE_THICKNESS_UM, METAL_THICKNESS_UM, MODEL_PADDING_UM,
    PACKAGE_PADDING_UM, Z0_PORT, SWEEP_START_GHZ, SWEEP_STOP_GHZ, SWEEP_COUNT, um,
)

# Gates the actual adaptive-mesh solve + S21/S11 pull (see module docstring).
# False: build geometry/ports/boundaries/sweep setup and stop. True:
# additionally call DM_setup.analyze() and save S21/S11 to CSV + PNG plots.
# Starts False - new geometry scale/schema (5 branches, different bbox)
# never solved before, even though the underlying bend/fan primitives are
# already proven - smoke test first, same staged pattern used for every
# HFSS build this session.
RUN_ANALYSIS = True


# ===============================================================================
# connection + Driven Modal design setup (verbatim pattern from
# filter_L30_HFSS.py / Hairpin_Filter_HFSS.py)
# ===============================================================================

project_name = 'filter_L60_S21'
design_name = 'Driven Modal'
overwrite = True

HFSS_path = os.getcwd()
full_path = os.path.join(HFSS_path, project_name + '.aedt')

HFSS_app = HFSS.HfssApp()
HFSS_desktop = HFSS_app.get_app_desktop()

# Real bug found+fixed this session: calling open_project(full_path)
# unconditionally (the pattern filter_L30_HFSS.py itself still uses) spawns
# a SECOND duplicate project handle when one of this name is already open
# in the persistent AEDT desktop (confirmed here - a smoke-test run left
# filter_L60_S21 open, and the next run's open_project() call created a
# distinct empty duplicate instead of attaching to it; this script's own
# DM_setup/DM_sweep objects ended up bound to the NEW empty duplicate, so
# post-solve S21/S11 export silently found no data - see CLAUDE.md's HFSS
# section for the general duplicate-project lesson this confirms). Fix:
# check get_projects() for an existing same-name handle first and attach
# to it rather than blindly opening/creating another.
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
# filter metal geometry - see filter_L30_HFSS.py's own module docstring for
# the full Unite()-winding-order story; draw_fan_native/draw_bend_native/
# STALK_FAN_OVERLAP_UM below are unchanged copies of that fix (including the
# exit-turn-to-fan joint-overlap fix, baked into verify_L60_hfss_export's
# _build_pieces() from the start - see that file's own docstring).
# ===============================================================================

def draw_fan_native(model, label, fan_params):
    """Draws one fan as 2 native AEDT arc segments + 2 straight radial
    edges - identical to filter_L30_HFSS.py's own draw_fan_native() (see
    that file's docstring for the winding-order rationale)."""
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
    """Draws one guarded_bend()/Strip_bend() U-turn as 2 native AEDT arc
    segments + 2 straight radial edges - identical to filter_L30_HFSS.py's
    own draw_bend_native() (see that file's docstring for the CCW-dependent
    winding-order rationale, verified this session in verify_bend_geometry.py)."""
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


# STALK_FAN_OVERLAP_UM: same value/rationale as filter_L30_HFSS.py - a
# guaranteed real overlap right before every fan (straight-branch stalk
# extension AND folded-branch exit-turn-to-fan bridge - see
# verify_L60_hfss_export._build_pieces()'s own docstring), needed for
# AEDT's Unite() to succeed.
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
# substrate + package (proxy ground enclosure), cropped to the metal's own
# bounding box + MODEL_PADDING_UM - see filter_L30_HFSS.py's own docstring
# (CROPPED MODEL DOMAIN, WAVE PORTS sections) for the full rationale. Y-extent
# held exactly [ymin, ymax] (no padding) so Package's Y-end faces are true
# exterior boundaries at the port cross-sections, required for wave ports.
# ===============================================================================

all_xs = [x for _label, hull, _kind, _arc_params in pieces for x, y in hull]
all_ys = [y for _label, hull, _kind, _arc_params in pieces for x, y in hull]
xmin, ymin, xmax, ymax = min(all_xs), min(all_ys), max(all_xs), max(all_ys)

# See filter_L30_HFSS.py's own docstring: pyEPR's Box.__init__ needs bare
# numeric inputs (not um()-wrapped strings), but bare floats after
# model.set_units('um') were empirically interpreted as METERS in this AEDT
# version - pre-scale to meters here, same fix.
_UM_TO_M = 1e-6

sub_x0 = xmin - MODEL_PADDING_UM
sub_w = (xmax - xmin) + 2 * MODEL_PADDING_UM
substrate = model.draw_box_corner(
    [sub_x0 * _UM_TO_M, ymin * _UM_TO_M, -SAPPHIRE_THICKNESS_UM * _UM_TO_M],
    [sub_w * _UM_TO_M, (ymax - ymin) * _UM_TO_M, SAPPHIRE_THICKNESS_UM * _UM_TO_M],
    material='sapphire',
    name='Substrate',
)

pkg_x0 = sub_x0 - PACKAGE_PADDING_UM
pkg_w = sub_w + 2 * PACKAGE_PADDING_UM
pkg_z0 = -SAPPHIRE_THICKNESS_UM - PACKAGE_PADDING_UM
pkg_h = SAPPHIRE_THICKNESS_UM + METAL_THICKNESS_UM + 2 * PACKAGE_PADDING_UM
package = model.draw_box_corner(
    [pkg_x0 * _UM_TO_M, ymin * _UM_TO_M, pkg_z0 * _UM_TO_M],
    [pkg_w * _UM_TO_M, (ymax - ymin) * _UM_TO_M, pkg_h * _UM_TO_M],
    material='vacuum',
    name='Package',
)

face_ids = [int(f) for f in model.get_face_ids(str(package))]
face_y = {fid: float(model._modeler.GetFaceCenter(fid)[1]) for fid in face_ids}
port1_face = min(face_ids, key=lambda fid: abs(face_y[fid] - ymax))  # input, high y
port2_face = min(face_ids, key=lambda fid: abs(face_y[fid] - ymin))  # output, low y
wall_faces = [fid for fid in face_ids if fid not in (port1_face, port2_face)]

model._boundaries.AssignPerfectE(
    ['NAME:Package_Walls', 'Faces:=', wall_faces, 'InfGroundPlane:=', False])

model.assign_perfect_E([METAL_OBJ_NAME], name='Filter_Metal')


# ===============================================================================
# wave ports - unchanged from filter_L30_HFSS.py (raw AssignWavePort COM
# call, integration line straight up from the conductor to the Package top).
# ===============================================================================

def make_wave_port(name, face_id, center_x_um):
    z_top = pkg_z0 + pkg_h
    start = [um(center_x_um), um(face_y[face_id]), um(0.0)]
    end = [um(center_x_um), um(face_y[face_id]), um(z_top)]
    params = ['NAME:' + name,
              'Faces:=', [face_id],
              'NumModes:=', 1,
              'UseLineModeAlignment:=', False,
              'DoDeembed:=', False,
              'RenormalizeAllTerminals:=', True,
              ['NAME:Modes',
               ['NAME:Mode1',
                'ModeNum:=', 1,
                'UseIntLine:=', True,
                ['NAME:IntLine', 'Start:=', start, 'End:=', end],
                'AlignmentGroup:=', 0,
                'CharImp:=', 'Zpi',
                'RenormImp:=', Z0_PORT]],
              'ShowReporterFilter:=', False,
              'ReporterFilter:=', [True]]
    model._boundaries.AssignWavePort(params)


make_wave_port('P1', port1_face, geom['port1_pos'][0])
make_wave_port('P2', port2_face, geom['port2_pos'][0])


# ===============================================================================
# Driven Modal analysis setup + frequency sweep (always built - cheap);
# the actual solve is gated behind RUN_ANALYSIS (see module docstring)
# ===============================================================================

DM_setup = DM_design.create_dm_setup(
    freq_ghz=(SWEEP_START_GHZ + SWEEP_STOP_GHZ) / 2,
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
    stop_ghz=SWEEP_STOP_GHZ,
    count=SWEEP_COUNT,
    step_ghz=None,
    name='S21_Sweep',
    type='Interpolating',
)

project.save()

if not RUN_ANALYSIS:
    print('Setup complete (RUN_ANALYSIS=False). Inspect the model in AEDT '
          '(confirm Unite() succeeded - METAL_OBJ_NAME should be a single '
          'solid, not null/Unclassified - check via a FRESH COM connection, '
          'enumerating every project handle matching the name and checking '
          'each individually, not just the first match - see CLAUDE.md\'s '
          'HFSS section), then set RUN_ANALYSIS=True and re-run to solve + '
          'pull S21/S11.')
else:
    print('RUN_ANALYSIS=True: running DM_setup.analyze() - this can take a '
          'while (adaptive mesh over the metal sheet + package enclosure, '
          'up to 12 passes, %d-point interpolating sweep).' % SWEEP_COUNT)
    DM_setup.analyze()

    # Explicit-path export (see module docstring) - NOT pyEPR's default
    # get_report_arrays()/get_arrays(), which relies on tempfile.mktemp()
    # and can fail with FileNotFoundError even after a fully successful
    # solve (confirmed this session on filter_L30_HFSS.py itself).
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

    s21_csv_path = os.path.join(out_dir, 'filter_L60_S21.csv')
    with open(s21_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_GHz', 'S21_dB'])
        writer.writerows(zip(freqs, s21_db))
    print('S21 data saved -> %s' % s21_csv_path)

    s11_csv_path = os.path.join(out_dir, 'filter_L60_S11.csv')
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
        ax.set_title('filter_L60 - S21/S11 (PLACEHOLDER geometry, proxy ground)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        png_path = os.path.join(out_dir, 'filter_L60_S21.png')
        fig.savefig(png_path, dpi=150, bbox_inches='tight')
        print('S21/S11 plot saved -> %s' % png_path)
    except ImportError:
        print('matplotlib not available in this environment - CSV saved, plot skipped.')
