#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 12 Phase 2: filter_BB "quick-look" first-light sim - fast real-package
read on whether the width-collapsed, all-70um six-stub filter_BB.py (Rev 12
Phase 1) behaves like the quarter-wave length synthesis predicts, BEFORE
committing to the much heavier Stage A pin+SNAIL machinery
(filter_BB_stageA_HFSS.py, already built, gated RUN_ANALYSIS=False).

GEOMETRY SOURCE, STATED PER THE HANDOFF'S OWN INSTRUCTION TO SAY WHICH WAS
USED: this file rebuilds real filter metal via `regenerate_metal_pieces_bb()`
(verify_filter_BB_hfss_export.py) - the live-Python-table rebuild already
proven in filter_BB_stageA_HFSS.py - NOT a DXF import and NOT a re-parse of
Phase 1's new `HFSS/filter_BB_dims.json`. That JSON is read here only for
its per-stub `f_target_ghz`/`predicted_f_zero_ghz`/`target_length_um`
fields (the dashboard's target/predicted columns, and the escalation path's
dl_um perturbation size) - it is the human/dashboard-facing dimensions
record, not the HFSS geometry source, exactly as flagged in filter_BB.py's
own dims-export comment.

NO PIN THIS RUN: both ports are LUMPED, trace-end straight up to the bore
wall (filter_L60_package_HFSS.py's own proven make_port() pattern, applied
to filter_BB's port1=pin-pad-outer-edge and port2=output-line-tip), NOT
Stage A's real pin coupler + SNAIL placeholder pads. This is explicitly not
the real embedding - fine for the shape question this pass asks (does the
composite response land near the length-predicted zeros with deep-enough
valleys), not for acceptance-quality Re[Z]/kappa numbers (Stage A's job).

RENORMALIZATION: Z0_FIRSTLIGHT = "70ohm" (a LOCAL override, not the shared
filter_L30_hfss_geometry.Z0_PORT="50ohm" default) - the handoff's own
"70-ohm renormalization (the measured line Z)" instruction, matching
DESIGN_NOTES Sec. 9's measured |Zpi|~69.7ohm.

SWEEP STRATEGY: one Driven Modal setup, TWO sweeps - `Coarse_Sweep`
(Interpolating, 0.5-13GHz) for the passband/recovery-region reads, and
`Discrete_Window` (Discrete, 4.0-8.5GHz @ 10MHz) for real solved points
across the whole protected band, since interpolation can smear/miss sharp
notches (same "discrete windows, not interpolation smoothing" principle
already established for zero-finding in Rev 11). `firstlight_S21.csv` is
the MERGE of the two: coarse data everywhere outside [4.0,8.5]GHz, real
discrete points inside it (never interpolated points in that range).
insert_sweep()'s `step_ghz=` path has a known pyEPR unit bug (confirmed in
Rev 11 - "RangeStep:=" gets no unit suffix, so e.g. 0.01 is read as
0.01Hz) - the discrete sweep uses `count=` instead (451 points over
4.0-8.5GHz @ 10MHz), matching the documented workaround.

DASHBOARD DELTA BASIS: the pass/fail `delta_pct` column is landed-vs-
TARGET (spec['f']), not landed-vs-predicted-from-bare-length. The bare
quarter-wave formula applied to a fan-terminated stub's REALIZED length is
NOT a neutral prediction - the terminator's ~0.6*Rout length correction
deliberately shortens the stub below its bare-formula length (see
filter_BB.py's `_prepare_stub()`), so re-predicting from that shortened
realized length via the bare formula recovers a frequency ABOVE target BY
CONSTRUCTION (~3% for this design's 300um terminators), even if HFSS lands
the stub exactly on target - that's the fan doing its job, not an error.
Using it as the pass/fail basis would manufacture a false failure out of
correct physics. `delta_pct_vs_predicted` is kept as a DIAGNOSTIC column
instead: S1/S6 (unterminated, fan_term=0) have NO such correction, so
their bare-formula prediction is clean - if S1/S6 land within ~1% of
predicted while S2-S5 sit systematically off by roughly the fan
correction's own size, that reads as "eps_eff/fold-length calibration
good, fan correction needs a tweak" (actionable), not "something's wrong."

AMBIGUITY ESCALATION (deliverable 2's own explicit "one extra solve max"
budget): if a stub's own landed-zero search window has a runner-up local
minimum within ~3dB of the primary, or the primary sits at the window
edge, ONE additional narrow discrete-window solve is run with that one
stub's own `dl_um` bumped +2% (on a freshly-reloaded `filter_BB` module
object, mutated directly - `_load_filter_BB()`/`_build_pieces()`, the same
private helpers `regenerate_metal_pieces_bb()` itself uses internally, so
no edit to verify_filter_BB_hfss_export.py is needed) to confirm the null
shifts in the expected direction (longer physical length -> lower
frequency). Only the FIRST ambiguous stub found is escalated this pass,
per the handoff's own budget - flagged if more than one stub is ambiguous.

ADAPTIVE MESH FREQUENCY: the adaptive solve runs at ADAPTIVE_FREQ_GHZ=3.0
(passband), NOT the sweep's own midpoint (~6.75GHz). A single-frequency
adaptive solve deep in the designed stopband would have fields decaying
evanescently past the first stub or two, so mesh refinement (energy-driven)
would concentrate near the input and leave the downstream half of the
filter under-resolved for the WHOLE sweep, including the higher-frequency
stub nulls. 3GHz sits below every stub's target (4.2-8.0GHz) where fields
propagate the full device length, giving a uniformly-resolved mesh instead.
Used for every build_design() call, including the escalation path - the
escalation model is still the full 6-stub geometry, just reported over a
narrow window, so the same reasoning applies there too.

KNOWN SIMPLIFICATIONS/CAVEATS (also printed into firstlight_summary.txt so
they're on the record, not just here):
  - Bore diameter is filter_BB.py's own PACKAGE_BORE_DIAMETER_UM=7000um
    (matching Stage A/filter_L60_package_HFSS.py's own established
    convention), not the 6985um figure used elsewhere in this repo's
    history (e.g. Rev 11's reference bore) - a pre-existing ~0.2% tension,
    irrelevant to this feel run but worth reconciling before Stage A,
    where the wall distance actually matters for Re[Z]/kappa.
  - Chip modeled at SAPPHIRE_WIDTH_UM=6900um inside the 7000um bore with
    NO pocket (floats with a gap on each side), whereas the real package
    has chip (7.000mm) >= bore (6.985mm), held in pockets - a different
    edge boundary condition than reality. Correct simplification for the
    shape question this pass asks; on the record for when O1 (real pocket
    geometry) lands.
  - 10MHz discrete steps will UNDERESTIMATE null depths (real nulls are
    sharp - filter_L60 sims showed -100dB-class spikes at fine resolution).
    Doesn't affect the verdict (its criteria are valley floors and zero
    locations, both broad features) - just don't read this pass's own
    per-null depth numbers as physically accurate.
  - `build_filter_metal()` seeds a 35um mesh length on the filter metal
    (~half the 70um trace width) as a first defense against under-
    resolving the thin traces. If landed zeros come back offset
    systematically (all high or all low by a few percent, not just one
    outlier), suspect mesh resolution before eps_eff - tighten this seed
    or re-run at max_delta_s=0.01 before doubting the calibration.

STAGING: RUN_ANALYSIS starts False (build geometry/ports/audit, print for
manual AEDT inspection, stop) - matching every prior HFSS script in this
repo and CLAUDE.md's duplicate-AEDT-project caution. `connect_project()`
uses the same attach-if-open pattern as filter_BB_stageA_HFSS.py.

RUN VIA THE SEPARATE PYEPR ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe filter_BB_firstlight_HFSS.py
Run from THIS file's own directory (Phase 1's filter_BB.py must have been
run first, so HFSS/filter_BB_dims.json exists).
"""
import csv
import json
import os
import sys

import numpy as np
from pyEPR import ansys as HFSS

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from verify_filter_BB_hfss_export import (  # noqa: E402
    regenerate_metal_pieces_bb, fan_arc_points, bend_arc_points,
    _load_filter_BB, _build_pieces,
)
from filter_L30_hfss_geometry import (  # noqa: E402
    SAPPHIRE_THICKNESS_UM, METAL_THICKNESS_UM, um,
)

RUN_ANALYSIS = True
RUN_AMBIGUITY_ESCALATION = True

PROJECT_NAME = 'filter_BB_firstlight'

BORE_AXIAL_MARGIN_UM = 5000.0
SAPPHIRE_WIDTH_UM = 6900.0  # matches filter_BB.py's own chip width (bore-width, no pocket - see module docstring)

SWEEP_START_GHZ = 0.5
SWEEP_STOP_GHZ = 13.0
SWEEP_COUNT = 2501  # ~5MHz resolution, matches this family's established density

DISCRETE_START_GHZ = 4.0
DISCRETE_STOP_GHZ = 8.5
DISCRETE_STEP_GHZ = 0.01
DISCRETE_COUNT = int(round((DISCRETE_STOP_GHZ - DISCRETE_START_GHZ) / DISCRETE_STEP_GHZ)) + 1  # 451

# Passband, not the sweep midpoint - see module docstring's "ADAPTIVE MESH
# FREQUENCY" section for why (fields propagate the full device length here,
# unlike deep in the stopband where mesh refinement would starve the
# downstream half of the filter).
ADAPTIVE_FREQ_GHZ = 3.0

# Half the 70um trace width - a first defense against under-resolving the
# thin traces (see module docstring's caveats section).
FILTER_METAL_MESH_MAX_LENGTH_UM = 35.0

PASSBAND_FREQS_GHZ = [0.5, 1.0, 2.0, 3.0, 3.3, 3.5]
VALLEY_BAND_GHZ = (4.2, 8.0)
NEEDLE_BAND_GHZ = (8.0, 13.0)
NEEDLE_THRESHOLD_DB = -30.0
SPOT_FREQ_GHZ = 4.5

Z0_FIRSTLIGHT = "70ohm"
SAPPHIRE_ANISO_NAME = 'sapphire_aniso_bb_firstlight'
_UM_TO_M = 1e-6

DIMS_JSON_PATH = os.path.join(os.path.dirname(__file__), 'HFSS', 'filter_BB_dims.json')


def _load_dims():
    if not os.path.exists(DIMS_JSON_PATH):
        raise FileNotFoundError(
            '%s not found - run filter_BB.py (Rev 12 Phase 1) first to generate it.' % DIMS_JSON_PATH)
    with open(DIMS_JSON_PATH) as f:
        return json.load(f)


def _load_geometry():
    geom = regenerate_metal_pieces_bb()
    print('Regenerated %d filter_BB metal piece(s) directly from filter_BB.py (no DXF/GDS round-trip)'
          % len(geom['pieces']))
    return geom


def _safe_name(label):
    """AEDT object names allow only letters/numbers/underscores - see
    filter_BB_stageA_HFSS.py's own docstring for the empirical confirmation."""
    return label.replace('.', 'p').replace('+', 'plus').replace('-', 'minus')


# ===============================================================================
# anisotropic sapphire (raw COM - pyEPR has no material-definition wrapper),
# duplicated from filter_BB_stageA_HFSS.py
# ===============================================================================

def ensure_anisotropic_sapphire(project):
    defmgr = project._project.GetDefinitionManager()
    if SAPPHIRE_ANISO_NAME in list(defmgr.GetProjectMaterialNames()):
        return
    defmgr.AddMaterial([
        'NAME:' + SAPPHIRE_ANISO_NAME,
        'CoordinateSystemType:=', 'Cartesian',
        'BulkOrSurfaceType:=', 1,
        ['NAME:PhysicsTypes', 'set:=', ['Electromagnetic']],
        ['NAME:permittivity', 'property_type:=', 'AnisoProperty', 'unit:=', '',
         'component1:=', '9.4', 'component2:=', '9.4', 'component3:=', '11.6'],
    ])
    print('Created anisotropic material %r (9.4, 9.4, 11.6)' % SAPPHIRE_ANISO_NAME)


def verify_anisotropic_sapphire(project):
    defmgr = project._project.GetDefinitionManager()
    exists = bool(defmgr.DoesMaterialExist(SAPPHIRE_ANISO_NAME))
    print('Material %r exists in project: %s (tensor value NOT auto-verified - '
          'check AnisoProperty 9.4/9.4/11.6 by eye in AEDT\'s Materials editor)'
          % (SAPPHIRE_ANISO_NAME, exists))
    return exists


# ===============================================================================
# filter metal - draw_fan_native/draw_bend_native + build_filter_metal
# duplicated verbatim from filter_BB_stageA_HFSS.py
# ===============================================================================

def draw_fan_native(model, label, fan_params):
    tip, direction_deg, r_out, r_in, fan_angle_deg, attach_width = fan_params
    p_in0, p_inmid, p_inend, p_outend, p_outmid, p_out0 = fan_arc_points(
        tip, direction_deg, r_out, r_in, fan_angle_deg, attach_width)
    pts = [p_out0, p_outmid, p_outend, p_inend, p_inmid, p_in0, p_out0]

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
        pts = [p_out0, p_outmid, p_outend, p_inend, p_inmid, p_in0, p_out0]

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


def build_filter_metal(model, geom):
    """Vacuum bulk + PerfectE only (not a lossy conductor) - same
    losslessness rationale as filter_BB_stageA_HFSS.py's own version."""
    metal_names = []
    for label, hull, kind, arc_params in geom['pieces']:
        label = _safe_name(label)
        if kind == 'fan':
            sheet = draw_fan_native(model, label, arc_params)
        elif kind == 'bend':
            sheet = draw_bend_native(model, label, arc_params)
        else:
            points_3d = [[um(x), um(y), '0um'] for x, y in hull]
            sheet = model.draw_polyline(points_3d, closed=True, name=label)
        model.sweep_along_vector([str(sheet)], ['0um', '0um', um(METAL_THICKNESS_UM)])
        metal_names.append(str(sheet))
    metal_obj_name = model.unite(metal_names)
    model.assign_perfect_E([metal_obj_name], name='Filter_Metal_PerfectE')
    model.mesh_length('FilterMetalMesh', [metal_obj_name], MaxLength='%fum' % FILTER_METAL_MESH_MAX_LENGTH_UM)
    return metal_obj_name


# ===============================================================================
# package (bore + substrate) - duplicated from filter_BB_stageA_HFSS.py
# ===============================================================================

def build_package(model, geom):
    bore_radius_um = geom['bore_diameter_um'] / 2.0
    bore_center_x = geom['port1_pos'][0]
    assert abs(geom['port2_pos'][0] - bore_center_x) < 1.0, \
        'port1/port2 X positions disagree - main line is not straight?'

    all_ys = [y for _label, hull, _kind, _ap in geom['pieces'] for x, y in hull]
    ymin, ymax = min(all_ys), max(all_ys)
    bore_len_um = (ymax - ymin) + 2 * BORE_AXIAL_MARGIN_UM
    bore_y0_edge_um = ymin - BORE_AXIAL_MARGIN_UM
    bore_axis_z_um = -SAPPHIRE_THICKNESS_UM / 2.0  # chip mid-thickness; Z=0 is chip-top/metal surface

    bore_name = model._modeler.CreateCylinder(
        ['NAME:CylinderParameters',
         'XCenter:=', um(bore_center_x), 'YCenter:=', um(bore_y0_edge_um), 'ZCenter:=', um(bore_axis_z_um),
         'Radius:=', um(bore_radius_um), 'Height:=', um(bore_len_um), 'WhichAxis:=', 'Y', 'NumSides:=', 0],
        model._attributes_array(name='BoreVacuum', material='vacuum'))
    print('Bore cylinder: radius %.1fum, axial length %.1fum (Y %.1f..%.1f), axis Z=%.1fum'
          % (bore_radius_um, bore_len_um, bore_y0_edge_um, bore_y0_edge_um + bore_len_um, bore_axis_z_um))

    sub_x0 = bore_center_x - SAPPHIRE_WIDTH_UM / 2.0
    model.draw_box_corner(
        [sub_x0 * _UM_TO_M, bore_y0_edge_um * _UM_TO_M, -SAPPHIRE_THICKNESS_UM * _UM_TO_M],
        [SAPPHIRE_WIDTH_UM * _UM_TO_M, bore_len_um * _UM_TO_M, SAPPHIRE_THICKNESS_UM * _UM_TO_M],
        material=SAPPHIRE_ANISO_NAME, name='Substrate')

    model.assign_perfect_E([bore_name], name='Package_Walls')

    return dict(bore_name=bore_name, bore_radius_um=bore_radius_um, bore_center_x=bore_center_x,
                bore_axis_z_um=bore_axis_z_um, bore_y0_edge_um=bore_y0_edge_um, bore_len_um=bore_len_um)


# ===============================================================================
# lumped ports, trace-end to bore wall - adapted from
# filter_L60_package_HFSS.py's own make_port() (explicit params instead of
# closures, matching filter_BB_stageA_HFSS.py's more modular style)
# ===============================================================================

def make_port(model, pkg, name, port_pos, width_um, z0=Z0_FIRSTLIGHT):
    x0, y0 = port_pos
    z_bot = 0.0  # chip top surface / substrate top
    z_top = pkg['bore_axis_z_um'] + pkg['bore_radius_um']  # straight up to the bore wall
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
    model._make_lumped_port(start, end, ['Objects:=', [rect_name]], z0=z0, name=name)
    print('  port %s: face X=%.1f..%.1f Z=%.1f..%.1f @ Y=%.1f, line Z %.1f -> %.1f, z0=%s'
          % (name, pos[0], pos[0] + width_um, z_bot, z_top, y0, z_mid, z_top, z0))
    return rect_name


# ===============================================================================
# losslessness audit - duplicated from filter_BB_stageA_HFSS.py
# ===============================================================================

def losslessness_audit(project, design):
    print('Losslessness audit:')
    ok_sapphire = verify_anisotropic_sapphire(project)
    boundary_names = list(design._boundaries.GetBoundaries())
    print('  boundaries defined: %s' % boundary_names)
    radiation_like = [b for b in boundary_names if 'rad' in b.lower() or 'absorb' in b.lower()]
    print('  radiation/absorbing boundaries found: %s (expect NONE)' % (radiation_like or 'none'))
    excitations = list(design._boundaries.GetExcitations())
    print('  excitations (ports) defined: %s' % excitations)
    return dict(sapphire_ok=ok_sapphire, boundaries=boundary_names,
                radiation_like=radiation_like, excitations=excitations)


# ===============================================================================
# connection + design build - same attach-if-open pattern as
# filter_BB_stageA_HFSS.py (CLAUDE.md duplicate-AEDT-project fix)
# ===============================================================================

def connect_project():
    HFSS_path = os.getcwd()
    full_path = os.path.join(HFSS_path, PROJECT_NAME + '.aedt')

    HFSS_app = HFSS.HfssApp()
    HFSS_desktop = HFSS_app.get_app_desktop()

    existing = [p for p in HFSS_desktop.get_projects() if p.name == PROJECT_NAME]
    if existing:
        project = existing[0]
        project.make_active()
    else:
        try:
            project = HFSS_desktop.open_project(full_path)
            project.make_active()
        except Exception:
            project = HFSS_desktop.new_project()
            project.save(full_path)
    return project


def build_design(project, design_name, geom, sweep_specs, overwrite=True):
    """sweep_specs: list of dict(name, type, start, stop, count) - one
    Driven Modal setup, one insert_sweep() call per spec. Reused for both
    the main (coarse+discrete) build and the one-off ambiguity-escalation
    build (a single narrow discrete window)."""
    existing_design_names = [d.name for d in project.get_designs()]
    if design_name in existing_design_names:
        if overwrite:
            project._project.DeleteDesign(design_name)
            project.save()
            design = project.new_dm_design(design_name)
        else:
            design = project.get_design(design_name)
    else:
        design = project.new_dm_design(design_name)

    model = design.modeler
    model.set_units('um')

    ensure_anisotropic_sapphire(project)

    build_filter_metal(model, geom)
    pkg = build_package(model, geom)

    make_port(model, pkg, 'P1', geom['port1_pos'], geom['port1_width'])
    make_port(model, pkg, 'P2', geom['port2_pos'], geom['port2_width'])

    audit = losslessness_audit(project, design)

    # ADAPTIVE_FREQ_GHZ (passband), not the sweep's own midpoint - see
    # module docstring's "ADAPTIVE MESH FREQUENCY" section.
    setup = design.create_dm_setup(
        freq_ghz=ADAPTIVE_FREQ_GHZ, name='FirstLight_Setup',
        max_delta_s=0.02, max_passes=12, min_passes=3, min_converged=2,
        pct_refinement=30, basis_order=1,
    )
    sweeps = {}
    for spec in sweep_specs:
        # count= not step_ghz= for Discrete sweeps - insert_sweep()'s
        # step_ghz path has a real pyEPR unit bug (RangeStep:= gets no GHz
        # suffix) - see module docstring.
        sweeps[spec['name']] = setup.insert_sweep(
            start_ghz=spec['start'], stop_ghz=spec['stop'], count=spec['count'],
            step_ghz=None, name=spec['name'], type=spec['type'],
        )
    project.save()

    print('Design %r built (sweeps: %s). Audit: %s' % (design_name, list(sweeps.keys()), audit))
    return design, setup, sweeps


# ===============================================================================
# post-processing
# ===============================================================================

def _pull(sweep, expr, label, out_dir):
    report = sweep.create_report('Temp_%s' % label, expr)
    tmp_path = os.path.join(out_dir, '_tmp_%s_export.csv' % label)
    report.export_to_file(tmp_path)
    freqs_, vals_ = np.loadtxt(tmp_path, skiprows=1, delimiter=',').transpose()
    os.remove(tmp_path)
    return freqs_, vals_


def pull_sweep(sweep, out_dir, suffix):
    freqs, s21 = _pull(sweep, 'dB(S(P2,P1))', 'S21' + suffix, out_dir)
    _, s11 = _pull(sweep, 'dB(S(P1,P1))', 'S11' + suffix, out_dir)
    return freqs, s21, s11


def merge_sweep_data(freqs_coarse, vals_coarse, freqs_discrete, vals_discrete, window):
    """Coarse (interpolated) data everywhere OUTSIDE window, real discrete
    solved points everywhere INSIDE it - never interpolated points inside
    the window (see module docstring)."""
    lo, hi = window
    mask_outside = (freqs_coarse < lo) | (freqs_coarse > hi)
    merged_f = np.concatenate([freqs_coarse[mask_outside], freqs_discrete])
    merged_v = np.concatenate([vals_coarse[mask_outside], vals_discrete])
    order = np.argsort(merged_f)
    return merged_f[order], merged_v[order]


def find_landed_zero(freqs, vals_db, target_ghz, half_width_frac=0.15):
    """Deepest local minimum of vals_db within target_ghz*[1-frac,1+frac].
    Also reports the runner-up local minimum (excluding a +-50MHz
    neighborhood of the primary) and flags ambiguity (runner-up within
    ~3dB of primary, or primary sits at the search window's own edge)."""
    lo, hi = target_ghz * (1 - half_width_frac), target_ghz * (1 + half_width_frac)
    mask = (freqs >= lo) & (freqs <= hi)
    idxs = np.where(mask)[0]
    if len(idxs) == 0:
        raise ValueError('No merged-sweep data in [%.3f, %.3f]GHz for target %.3fGHz' % (lo, hi, target_ghz))
    sub_f, sub_v = freqs[idxs], vals_db[idxs]
    primary_idx = int(np.argmin(sub_v))
    primary_f, primary_v = float(sub_f[primary_idx]), float(sub_v[primary_idx])

    excl = np.abs(sub_f - primary_f) > 0.05
    if np.any(excl):
        masked_v = np.where(excl, sub_v, np.inf)
        runner_idx = int(np.argmin(masked_v))
        runner_f, runner_v = float(sub_f[runner_idx]), float(sub_v[runner_idx])
    else:
        runner_f = runner_v = None

    at_edge = primary_idx <= 1 or primary_idx >= len(sub_f) - 2
    close_runner = runner_v is not None and abs(runner_v - primary_v) < 3.0
    ambiguous = bool(at_edge or close_runner)
    return dict(landed_f_ghz=primary_f, depth_db=primary_v, runner_f_ghz=runner_f,
                runner_depth_db=runner_v, at_edge=at_edge, ambiguous=ambiguous)


def build_dashboard(merged_f, merged_s21, dims):
    """delta_pct (PASS/FAIL basis) is landed-vs-TARGET, not landed-vs-
    predicted-from-bare-length - see module docstring's "DASHBOARD DELTA
    BASIS" section for why the bare-length re-prediction is contaminated
    for fan-terminated stubs (S2-S5) and would manufacture a false failure.
    delta_pct_vs_predicted is kept as a diagnostic-only column - clean for
    S1/S6 (fan_term=0), expected to run systematically high for S2-S5."""
    rows = []
    for stub in dims['stubs']:
        result = find_landed_zero(merged_f, merged_s21, stub['f_target_ghz'])
        target = stub['f_target_ghz']
        predicted = stub['predicted_f_zero_ghz']
        landed = result['landed_f_ghz']
        rows.append(dict(
            label=stub['label'], target_f_ghz=target, predicted_f_ghz=predicted, landed_f_ghz=landed,
            delta_pct=100.0 * (landed - target) / target,
            delta_pct_vs_predicted=100.0 * (landed - predicted) / predicted,
            fan_terminated=stub['fan_term_rout_um'] > 0,
            depth_db=result['depth_db'], ambiguous=result['ambiguous'],
            target_length_um=stub['target_length_um'],
            escalation_perturbed_f_ghz='', escalation_shifted_as_expected='',
        ))
    return rows


def escalate_ambiguous_stub(project, row, out_dir):
    """ONE extra narrow discrete-window solve (see module docstring) -
    bumps this stub's own dl_um by +2% on a freshly-reloaded filter_BB
    module object and confirms the null shifts to a LOWER frequency
    (longer physical length -> lower f_zero)."""
    label = row['label']
    extra_dl_um = 0.02 * row['target_length_um']
    fbb = _load_filter_BB()
    target_spec = next(spec for spec in fbb.STUBS if ('%.1fGHz' % spec['f']) == label)
    target_spec['dl_um'] = extra_dl_um

    pieces, ports = [], {}
    for lbl, data, kind, arc_params in _build_pieces(fbb):
        if lbl in ('port1_pos', 'port2_pos'):
            ports[lbl] = data
        else:
            pieces.append((lbl, data, kind, arc_params))
    geom_p = dict(pieces=pieces, port1_pos=ports['port1_pos'], port1_width=fbb.PIN_PAD_WIDTH,
                  port2_pos=ports['port2_pos'], port2_width=fbb.OUTPUT_LINE_WIDTH,
                  bore_diameter_um=fbb.PACKAGE_BORE_DIAMETER_UM, w_main=fbb.W_MAIN,
                  pin_pad_length=fbb.PIN_PAD_LENGTH)

    lo, hi = row['target_f_ghz'] * 0.85, row['target_f_ghz'] * 1.15
    count = int(round((hi - lo) / 0.01)) + 1
    design_name = 'FirstLight_Perturb_%s' % _safe_name(label)
    print('Ambiguity escalation for stub %s: dl_um +%.2fum (2%% of target_length), window [%.3f,%.3f]GHz'
          % (label, extra_dl_um, lo, hi))

    design_p, setup_p, sweeps_p = build_design(
        project, design_name, geom_p,
        [dict(name='Escalation_Window', type='Discrete', start=lo, stop=hi, count=count)])
    setup_p.analyze()
    freqs_p, s21_p, _ = pull_sweep(sweeps_p['Escalation_Window'], out_dir, '_esc_%s' % _safe_name(label))

    idx = int(np.argmin(s21_p))
    new_f = float(freqs_p[idx])
    shifted_as_expected = new_f < row['landed_f_ghz']
    print('  perturbed null @ %.4fGHz (original %.4fGHz) - shifted lower as expected: %s'
          % (new_f, row['landed_f_ghz'], shifted_as_expected))

    row['escalation_perturbed_f_ghz'] = new_f
    row['escalation_shifted_as_expected'] = shifted_as_expected
    return row


def compute_valleys(dashboard_rows, freqs, vals, band=VALLEY_BAND_GHZ):
    zero_freqs = sorted(r['landed_f_ghz'] for r in dashboard_rows)
    edges = sorted(set([band[0]] + zero_freqs + [band[1]]))
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (freqs >= lo) & (freqs <= hi)
        if not np.any(mask):
            continue
        sub_f, sub_v = freqs[mask], vals[mask]
        idx = int(np.argmax(sub_v))
        rows.append(dict(lo_ghz=lo, hi_ghz=hi, worst_s21_db=float(sub_v[idx]), worst_freq_ghz=float(sub_f[idx])))
    return rows


def compute_passband(freqs, vals, freqs_list=PASSBAND_FREQS_GHZ):
    rows = []
    for f in freqs_list:
        idx = int(np.argmin(np.abs(freqs - f)))
        rows.append(dict(freq_ghz=f, s21_db=float(vals[idx])))
    return rows


def compute_needles(freqs, vals, band=NEEDLE_BAND_GHZ, threshold=NEEDLE_THRESHOLD_DB):
    lo, hi = band
    mask = (freqs >= lo) & (freqs <= hi)
    f, v = freqs[mask], vals[mask]
    needles = []
    for i in range(1, len(f) - 1):
        if v[i] > threshold and v[i] >= v[i - 1] and v[i] >= v[i + 1]:
            needles.append(dict(freq_ghz=float(f[i]), s21_db=float(v[i])))
    return needles


def compute_verdict(dashboard_rows, valley_rows, passband_rows):
    max_delta = max(abs(r['delta_pct']) for r in dashboard_rows)
    zeros_ok = max_delta <= 5.0
    worst_valley = max((r['worst_s21_db'] for r in valley_rows), default=float('nan'))
    valleys_ok = worst_valley <= -30.0
    pb_vals = [r['s21_db'] for r in passband_rows if r['freq_ghz'] <= 3.3]
    pb_spread = (max(pb_vals) - min(pb_vals)) if pb_vals else float('nan')
    passband_ok = pb_spread <= 2.0
    lines = [
        'Zeros within ~5%% of target design frequency: %s (max |delta|=%.2f%%)'
        % ('PASS' if zeros_ok else 'FAIL', max_delta),
        'Every inter-zero valley (4.2-8.0GHz) <=-30dB pre-trim: %s (worst=%.2fdB)'
        % ('PASS' if valleys_ok else 'FAIL', worst_valley),
        'Passband 0.5-3.3GHz within ~2dB of flat: %s (spread=%.2fdB)'
        % ('PASS' if passband_ok else 'FAIL', pb_spread),
    ]
    return '\n'.join(lines)


# ===============================================================================
# main
# ===============================================================================

def main():
    project = connect_project()
    geom = _load_geometry()
    dims = _load_dims()

    # Insurance against a stale JSON (written by Phase 1's filter_BB.py run,
    # consumed here potentially much later) - reload filter_BB.py fresh and
    # cross-check stub count + EPS_EFF.
    fbb_check = _load_filter_BB()
    assert len(dims['stubs']) == len(fbb_check.STUBS), (
        'dims JSON stub count (%d) != live filter_BB.py STUBS (%d) - stale JSON, re-run filter_BB.py first'
        % (len(dims['stubs']), len(fbb_check.STUBS)))
    assert abs(dims['eps_eff'] - fbb_check.EPS_EFF) < 1e-9, (
        'dims JSON eps_eff (%.6f) != live filter_BB.py EPS_EFF (%.6f) - stale JSON, re-run filter_BB.py first'
        % (dims['eps_eff'], fbb_check.EPS_EFF))

    out_dir = os.path.join(os.path.dirname(__file__), 'HFSS')
    os.makedirs(out_dir, exist_ok=True)

    main_sweep_specs = [
        dict(name='Coarse_Sweep', type='Interpolating', start=SWEEP_START_GHZ, stop=SWEEP_STOP_GHZ,
             count=SWEEP_COUNT),
        dict(name='Discrete_Window', type='Discrete', start=DISCRETE_START_GHZ, stop=DISCRETE_STOP_GHZ,
             count=DISCRETE_COUNT),
    ]
    design, setup, sweeps = build_design(project, 'FirstLight', geom, main_sweep_specs)

    if not RUN_ANALYSIS:
        print('Setup complete (RUN_ANALYSIS=False). Inspect in AEDT via a FRESH COM '
              'connection, enumerating every project handle named %r individually '
              '(CLAUDE.md duplicate-AEDT-project lesson) - confirm: filter metal is '
              'one united solid, BoreVacuum+Substrate present with no intersections, '
              'P1/P2 lumped ports both assigned at z0=%s, losslessness audit printed '
              'clean above. Then set RUN_ANALYSIS=True and re-run.' % (PROJECT_NAME, Z0_FIRSTLIGHT))
        return

    print('RUN_ANALYSIS=True: solving FirstLight (max_passes=12, tol=0.02)...')
    setup.analyze()
    print('Convergence:', setup.get_convergence())

    freqs_c, s21_c, s11_c = pull_sweep(sweeps['Coarse_Sweep'], out_dir, '_coarse')
    freqs_d, s21_d, s11_d = pull_sweep(sweeps['Discrete_Window'], out_dir, '_discrete')
    window = (DISCRETE_START_GHZ, DISCRETE_STOP_GHZ)
    merged_f, merged_s21 = merge_sweep_data(freqs_c, s21_c, freqs_d, s21_d, window)
    _, merged_s11 = merge_sweep_data(freqs_c, s11_c, freqs_d, s11_d, window)

    # --- deliverable 1: merged S21/S11 CSV + plot ---
    s21_csv_path = os.path.join(out_dir, 'firstlight_S21.csv')
    with open(s21_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_GHz', 'S21_dB', 'S11_dB'])
        writer.writerows(zip(merged_f, merged_s21, merged_s11))
    print('Merged S21/S11 saved -> %s' % s21_csv_path)

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(merged_f, merged_s21, label='S21')
        ax.plot(merged_f, merged_s11, label='S11', alpha=0.6)
        ax.axvspan(DISCRETE_START_GHZ, DISCRETE_STOP_GHZ, alpha=0.08, color='C2', label='discrete window')
        ax.set_xlabel('Frequency (GHz)')
        ax.set_ylabel('dB')
        ax.set_title('filter_BB first light - merged S21/S11 (70ohm lumped ports, no pin)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        png_path = os.path.join(out_dir, 'firstlight_S21.png')
        fig.savefig(png_path, dpi=150, bbox_inches='tight')
        print('Plot saved -> %s' % png_path)
    except ImportError:
        print('matplotlib not available - CSV saved, plot skipped.')

    # --- deliverable 2: dashboard ---
    dashboard_rows = build_dashboard(merged_f, merged_s21, dims)
    ambiguous_rows = [r for r in dashboard_rows if r['ambiguous']]
    if ambiguous_rows:
        print('%d stub(s) flagged ambiguous: %s' % (len(ambiguous_rows), [r['label'] for r in ambiguous_rows]))
        if RUN_AMBIGUITY_ESCALATION:
            if len(ambiguous_rows) > 1:
                print('  only escalating the first (handoff budget: one extra solve max this pass) - '
                      'remaining ambiguous stubs: %s' % [r['label'] for r in ambiguous_rows[1:]])
            escalate_ambiguous_stub(project, ambiguous_rows[0], out_dir)

    dashboard_path = os.path.join(out_dir, 'firstlight_dashboard.csv')
    with open(dashboard_path, 'w', newline='') as f:
        fieldnames = ['label', 'target_f_ghz', 'predicted_f_ghz', 'landed_f_ghz', 'delta_pct',
                      'delta_pct_vs_predicted', 'fan_terminated', 'depth_db', 'ambiguous',
                      'escalation_perturbed_f_ghz', 'escalation_shifted_as_expected']
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(dashboard_rows)
    print('Dashboard saved -> %s' % dashboard_path)

    # --- deliverable 3: composite-floor readout ---
    valley_rows = compute_valleys(dashboard_rows, merged_f, merged_s21)
    valleys_path = os.path.join(out_dir, 'firstlight_valleys.csv')
    with open(valleys_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['lo_ghz', 'hi_ghz', 'worst_s21_db', 'worst_freq_ghz'])
        writer.writeheader()
        writer.writerows(valley_rows)
    spot_idx = int(np.argmin(np.abs(merged_f - SPOT_FREQ_GHZ)))
    spot_s21 = float(merged_s21[spot_idx])
    print('Valleys saved -> %s; S21@%.1fGHz = %.2fdB' % (valleys_path, SPOT_FREQ_GHZ, spot_s21))

    # --- deliverable 4: passband readout ---
    passband_rows = compute_passband(merged_f, merged_s21)
    passband_path = os.path.join(out_dir, 'firstlight_passband.csv')
    with open(passband_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['freq_ghz', 's21_db'])
        writer.writeheader()
        writer.writerows(passband_rows)
    sag_db = passband_rows[-1]['s21_db'] - passband_rows[-2]['s21_db']  # 3.5GHz - 3.3GHz
    sag_note = ''
    if sag_db < -1.0:
        sag_note = ('  *** %.2fdB sag at the 3.3-3.5GHz edge %s the S1-zero-raise escalation trigger '
                     '(1-2dB) - flagged, NOT implemented this pass ***'
                     % (sag_db, 'EXCEEDS' if sag_db < -2.0 else 'approaches'))
    print('Passband saved -> %s; 3.3->3.5GHz sag = %.2fdB%s' % (passband_path, sag_db, sag_note))

    # --- deliverable 5: 8-13GHz recovery scan ---
    needle_rows = compute_needles(merged_f, merged_s21)
    needles_path = os.path.join(out_dir, 'firstlight_needles.csv')
    with open(needles_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['freq_ghz', 's21_db'])
        writer.writeheader()
        writer.writerows(needle_rows)
    print('Needles (%d found above %.0fdB in %.1f-%.1fGHz) saved -> %s'
          % (len(needle_rows), NEEDLE_THRESHOLD_DB, NEEDLE_BAND_GHZ[0], NEEDLE_BAND_GHZ[1], needles_path))

    # --- deliverable 6: verdict ---
    verdict_text = compute_verdict(dashboard_rows, valley_rows, passband_rows)
    summary_lines = [
        '=' * 70, 'filter_BB first light - Rev 12 Phase 2 summary', '=' * 70,
        'CAVEATS (see script docstring for full detail):',
        '  - bore modeled at 7000um (filter_BB.py convention) vs the 6985um figure used',
        '    elsewhere in this repo\'s history - ~0.2% tension, reconcile before Stage A',
        '  - chip modeled at 6900um wide inside the 7000um bore, no pocket (floats with a',
        '    gap) - real package has chip(7.000mm) >= bore(6.985mm), held in pockets',
        '  - 10MHz discrete steps UNDERESTIMATE null depths (real nulls are much sharper) -',
        '    valley/zero-location criteria are unaffected, but do not read depths as physical',
        '-' * 70,
        'Dashboard (target | predicted-from-bare-length | landed | delta%-vs-target | '
        'delta%-vs-predicted):',
        '  delta%-vs-target is the PASS/FAIL basis. delta%-vs-predicted is diagnostic ONLY -',
        '  for fan-terminated stubs (S2-S5) it is EXPECTED to run high by ~the fan length',
        '  correction (~3% here), by construction, not an error. S1/S6 (unterminated) are',
        '  the clean eps_eff/fold-length check: if they land near predicted while S2-S5 sit',
        '  systematically off by roughly the fan correction, that reads as "calibration',
        '  good, fan correction needs a tweak," not "something is wrong."',
    ]
    for r in dashboard_rows:
        summary_lines.append('  %-8s %6.3f | %6.3f | %6.3f GHz | %+6.2f%% | %+6.2f%%  (%s, depth %.1fdB)%s'
                              % (r['label'], r['target_f_ghz'], r['predicted_f_ghz'], r['landed_f_ghz'],
                                 r['delta_pct'], r['delta_pct_vs_predicted'],
                                 'fan-terminated' if r['fan_terminated'] else 'UNTERMINATED-clean-check',
                                 r['depth_db'], '  <<AMBIGUOUS' if r['ambiguous'] else ''))
    summary_lines.append('-' * 70)
    summary_lines.append('Inter-zero valleys (4.2-8.0GHz):')
    for r in valley_rows:
        summary_lines.append('  [%.3f, %.3f]GHz: worst=%.2fdB @ %.3fGHz'
                              % (r['lo_ghz'], r['hi_ghz'], r['worst_s21_db'], r['worst_freq_ghz']))
    summary_lines.append('S21@%.1fGHz = %.2fdB' % (SPOT_FREQ_GHZ, spot_s21))
    summary_lines.append('-' * 70)
    summary_lines.append('Passband:')
    for r in passband_rows:
        summary_lines.append('  %.1fGHz: %.2fdB' % (r['freq_ghz'], r['s21_db']))
    summary_lines.append('3.3->3.5GHz sag = %.2fdB%s' % (sag_db, sag_note))
    summary_lines.append('-' * 70)
    summary_lines.append('8-13GHz needles (>%.0fdB): %s'
                          % (NEEDLE_THRESHOLD_DB,
                             ['%.3fGHz(%.1fdB)' % (n['freq_ghz'], n['s21_db']) for n in needle_rows] or 'none'))
    summary_lines.append('=' * 70)
    summary_lines.append('VERDICT:')
    summary_lines.append(verdict_text)
    summary_lines.append('=' * 70)
    summary_text = '\n'.join(summary_lines)
    print(summary_text)
    with open(os.path.join(out_dir, 'firstlight_summary.txt'), 'w') as f:
        f.write(summary_text + '\n')


if __name__ == '__main__':
    main()
