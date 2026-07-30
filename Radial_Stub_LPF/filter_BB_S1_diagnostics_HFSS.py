#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 14 T1/T2: filter_BB S1 diagnostic campaign - is S1 alive, and does
perturbing it move any real null? See DESIGN_NOTES Sec. 9/11/12 and the
Rev 14 handoff for the full analysis. T0 (layout audit) and T4 (dashboard
hardening) were completed directly against live code/data with NO solve -
see filter_BB_firstlight_HFSS.py's own find_all_notches()/build_dashboard()
docstrings for T4's story (a real, two-part bug: a flat depth threshold too
shallow to reject passband ripple, AND a target-order-greedy matcher that
cascades once one stub is genuinely absent). This file is T1 (field plots)
+ T2 (single-stub perturbation), Rung 2 of the handoff's own fallback
framing - T3 (overtone attribution) is explicitly deferred.

BASELINE GEOMETRY (Rev14-D2, NOT Rev13-D2 - see DESIGN_NOTES/plan for the
naming collision): S1 reverted to NOMINAL length (dl_um=0, undoing passes
1-3's cumulative +27.4% growth - the kinematic disproof shows that growth
was chasing a misidentified feature, not S1's own resonance: length grew
+27.4% while the tracked frequency only moved -8.4%, a ~0.31 sensitivity
ratio where a real quarter-wave resonance should show ~1.0). S2-S6 stay at
their pass-3 (converged) lengths, read live from the current
HFSS/filter_BB_dims.json - this is the new REFERENCE geometry both T1 and
T2 build from.

GEOMETRY/PACKAGE/PORT BUILDING: duplicated verbatim from
filter_BB_firstlight_HFSS.py (draw_fan_native/draw_bend_native/
build_filter_metal/build_package/make_port/ensure_anisotropic_sapphire/
losslessness_audit/connect_project) - same "no cross-import, duplicate the
orchestration" convention this whole file family uses. ONE deliberate
EXCEPTION: find_all_notches() (T2's own null-survey) IS imported directly
from filter_BB_firstlight_HFSS.py rather than duplicated - it's pure
Python post-processing with no AEDT dependency, and T2 needs the EXACT
same, just-hardened notion of "real transmission zero" T4 built, not a
second copy that could silently drift out of sync.

FIELD PLOTS (T1): surface current density (Mag_Jsurf - the correct AEDT
quantity for a PerfectE-bounded object, not Mag_E/vacuum field) via raw
COM CreateFieldPlot + ExportFieldPlot + manual PyVista render, translating
Rev 11's proven pyaedt recipe (oval_bore_epseff_HFSS.py's own
render_field_plot_manual(), which used hfss.post.create_fieldplot_surface/
export_field_plot) to this file family's pyEPR/raw-COM convention since
Rev 12. pyEPR itself has no field-plot wrapper (checked installed source -
design._fields_calc only exposes the Fields CALCULATOR sub-API
(CalcStack/ClearAllNamedExpr), not field-plot creation/export, even though
it's bound to the same "FieldsReporter" COM module CreateFieldPlot/
ExportFieldPlot also live on). The exact CreateFieldPlot param block below
is RECALLED AEDT scripting syntax, not verified against this specific
install - same epistemic status as filter_BB_firstlight_HFSS.py's own
multi-freq-adaptive attempt, which failed cleanly and had a working
fallback ready. There is no clean fallback for a field plot (it's the
whole point of T1), so the recipe is tested FIRST against S2 (known-good
positive control, already converged in pass 3) before trusting whatever it
shows for S1 - if it doesn't even work for S2, it needs fixing before S1's
own result means anything either way.

PERTURBATION SWEEP (T2): 0.5-14GHz (wider than this family's usual
13GHz ceiling - S1's own predicted 3rd harmonic sits ~12.6GHz nominal and
the window must safely contain it). Fold-count-boundary guard from the
handoff's own T2 spec CHECKED against this codebase's actual
implementation and found NOT APPLICABLE (see
build_geometry_with_overrides()'s own docstring) - n_par_runs is a fixed,
manually-set STUBS table field here, never auto-derived from length.

STAGING: RUN_ANALYSIS starts False (build every design/setup, stop before
any analyze() call, for manual AEDT inspection) - matching every prior
HFSS script in this repo. `connect_project()` uses the same attach-if-open
pattern as filter_BB_firstlight_HFSS.py.

RUN VIA THE SEPARATE PYEPR ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe filter_BB_S1_diagnostics_HFSS.py
Run from THIS file's own directory (filter_BB.py's pass-3 run must already
have produced HFSS/filter_BB_dims.json and
HFSS/firstlight2_quickscan_pass3_dashboard.csv).
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
    fan_arc_points, bend_arc_points, _load_filter_BB, _build_pieces,
)
from filter_L30_hfss_geometry import (  # noqa: E402
    SAPPHIRE_THICKNESS_UM, METAL_THICKNESS_UM, um,
)
from filter_BB_firstlight_HFSS import find_all_notches  # noqa: E402 - see module docstring's one deliberate exception

RUN_ANALYSIS = True
RUN_T1 = False  # Rev 16: field plots stay broken (new TypeError this session,
                 # CreateFieldPlot() arg-count mismatch - a real, fixable bug,
                 # just not this run's job) - Track A only needs the null survey.
RUN_T2 = True

# Rev 16 Track A: +3% S1 perturbation FROM THE V2+S7 BASELINE (not the old
# Rev 14 T2 "S1 reverted to nominal" baseline this file used to build) -
# separate, throwaway designs, per Rev 15 D5/Rev 16 D5 ("must never touch
# the v2/S7 baseline"). RUN_TRACK_A gates main() below; the old Rev 14
# T1/T2 functions (build_baseline_overrides/build_perturbed_overrides,
# S1_Nominal_Baseline/S1_Plus15pct) stay in this file as historical
# reference/pattern but are not called by main() anymore - that campaign
# is complete and already reported.
RUN_TRACK_A = True

PROJECT_NAME = 'filter_BB_s1_diagnostics'
BASELINE_DESIGN_NAME = 'S1_Nominal_Baseline'
PERTURBED_DESIGN_NAME = 'S1_Plus15pct'
TRACKA_BASELINE_DESIGN_NAME = 'TrackA_V2S7_Baseline'
TRACKA_PERTURBED_DESIGN_NAME = 'TrackA_S1_Plus3pct'

BORE_AXIAL_MARGIN_UM = 5000.0
SAPPHIRE_WIDTH_UM = 6900.0  # matches filter_BB.py's own chip width (bore-width, no pocket)

Z0_DIAG = "70ohm"
SAPPHIRE_ANISO_NAME = 'sapphire_aniso_bb_s1diag'
_UM_TO_M = 1e-6

FILTER_METAL_MESH_MAX_LENGTH_UM = 35.0

S1_LABEL = '4.2GHz'
S2_LABEL = '4.7GHz'
S1_NOMINAL_GHZ = 4.2  # T1's own S1 field-plot frequency (S1's nominal/target)

T2_PERTURB_FRAC = 0.15
T2_SWEEP_START_GHZ = 0.5
T2_SWEEP_STOP_GHZ = 14.0
T2_SWEEP_COUNT = 2701  # ~5MHz resolution over the wider range
SWEEP_ADAPTIVE_FREQ_GHZ = 3.0  # passband - same "mesh at a propagating frequency" reasoning as Rev 12/13

T2_NULL_MATCH_MAX_GHZ = 0.4  # generous - this is a diagnostic survey, not a per-stub landing measurement

# Rev 16 Track A (Rev 15 A1): from the v2+S7 baseline (S1 already at
# nominal*1.15), lengthen S1 by a FURTHER 3% of NOMINAL (not 3% of the v2
# length) - matches T2's own established convention of measuring every
# perturbation as a fraction of NOMINAL length, so response ratios stay
# comparable across different perturbation magnitudes. Total S1 dl_um
# fraction for the perturbed design is therefore 0.15+0.03=0.18 of nominal.
TRACKA_PERTURB_FRAC = 0.03
TRACKA_TOTAL_FRAC = 0.15 + TRACKA_PERTURB_FRAC
TRACKA_NULL_MATCH_MAX_GHZ = 0.4

OUT_DIR = os.path.join(os.path.dirname(__file__), 'HFSS')


def _load_dims():
    with open(os.path.join(OUT_DIR, 'filter_BB_dims.json')) as f:
        return json.load(f)


def _load_pass3_dashboard():
    out = {}
    with open(os.path.join(OUT_DIR, 'firstlight2_quickscan_pass3_dashboard.csv'), newline='') as f:
        for row in csv.DictReader(f):
            out[row['label']] = row
    return out


def _safe_name(label):
    return label.replace('.', 'p').replace('+', 'plus').replace('-', 'minus')


# ===============================================================================
# anisotropic sapphire (raw COM) - duplicated from filter_BB_firstlight_HFSS.py
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
    print('Material %r exists in project: %s' % (SAPPHIRE_ANISO_NAME, exists))
    return exists


# ===============================================================================
# filter metal / package / ports - duplicated from filter_BB_firstlight_HFSS.py
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
    """Vacuum bulk + PerfectE only - same losslessness rationale as
    filter_BB_firstlight_HFSS.py's own version. Returns the united solid's
    name (needed here for the field plot's own geometry assignment)."""
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


def build_package(model, geom):
    bore_radius_um = geom['bore_diameter_um'] / 2.0
    bore_center_x = geom['port1_pos'][0]
    assert abs(geom['port2_pos'][0] - bore_center_x) < 1.0, \
        'port1/port2 X positions disagree - main line is not straight?'

    all_ys = [y for _label, hull, _kind, _ap in geom['pieces'] for x, y in hull]
    ymin, ymax = min(all_ys), max(all_ys)
    bore_len_um = (ymax - ymin) + 2 * BORE_AXIAL_MARGIN_UM
    bore_y0_edge_um = ymin - BORE_AXIAL_MARGIN_UM
    bore_axis_z_um = -SAPPHIRE_THICKNESS_UM / 2.0

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


def make_port(model, pkg, name, port_pos, width_um, z0=Z0_DIAG):
    x0, y0 = port_pos
    z_bot = 0.0
    z_top = pkg['bore_axis_z_um'] + pkg['bore_radius_um']
    z_mid = METAL_THICKNESS_UM / 2.0

    pos = [x0 - width_um / 2, y0, z_bot]
    size = [width_um, 0, z_top - z_bot]
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
    print('  port %s: face X=%.1f..%.1f Z=%.1f..%.1f @ Y=%.1f, z0=%s'
          % (name, pos[0], pos[0] + width_um, z_bot, z_top, y0, z0))
    return rect_name


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


# ===============================================================================
# geometry with per-stub overrides - generalizes
# filter_BB_firstlight_HFSS.py's own escalate_ambiguous_stub() pattern
# ===============================================================================

def build_geometry_with_overrides(overrides):
    """overrides: {label: {field: value}} - mutates matching STUBS entries
    on a FRESHLY-RELOADED filter_BB module object before replaying
    geometry (same _load_filter_BB()/_build_pieces() private-helper reuse
    as filter_BB_firstlight_HFSS.py's own escalate_ambiguous_stub() - no
    edit to verify_filter_BB_hfss_export.py needed).

    Fold-count-boundary note (the Rev 14 T2 spec's own explicit caution,
    checked against this codebase's actual implementation, not assumed
    safe): n_par_runs is a FIXED, manually-set STUBS table field here,
    never auto-derived from target_length - folded_stub() always uses
    whatever n_par_runs the table specifies, and run_length scales
    continuously with length (only a too-SHORT guard exists, via
    _MIN_LEN - no too-long constraint). A length INCREASE (T2's own +15%
    on S1) cannot silently cross a fold-count boundary in THIS
    implementation - verified by reading folded_stub()/_prepare_stub()
    directly."""
    fbb = _load_filter_BB()
    for spec in fbb.STUBS:
        label = '%.1fGHz' % spec['f']
        if label in overrides:
            spec.update(overrides[label])

    pieces, ports = [], {}
    for lbl, data, kind, arc_params in _build_pieces(fbb):
        if lbl in ('port1_pos', 'port2_pos'):
            ports[lbl] = data
        else:
            pieces.append((lbl, data, kind, arc_params))
    return dict(pieces=pieces, port1_pos=ports['port1_pos'], port1_width=fbb.PIN_PAD_WIDTH,
                port2_pos=ports['port2_pos'], port2_width=fbb.OUTPUT_LINE_WIDTH,
                bore_diameter_um=fbb.PACKAGE_BORE_DIAMETER_UM, w_main=fbb.W_MAIN,
                pin_pad_length=fbb.PIN_PAD_LENGTH)


def build_baseline_overrides():
    """Rev14-D2: S1 reverted to NOMINAL length (dl_um=0, undoing passes
    1-3's cumulative +27.4% growth). S2-S6 are left untouched (no override
    entry) - _prepare_stub() will seed THEIR OWN dl_um from the current
    PREVIOUS_PASS_DIMS_JSON/DASHBOARD_CSV exactly as filter_BB.py's own
    normal pass-N flow does, landing them at their pass-3 converged
    lengths automatically."""
    return {S1_LABEL: dict(dl_um=0.0)}


def build_perturbed_overrides(dims, frac):
    """S1 lengthened by `frac` beyond its own NOMINAL length (not beyond
    wherever pass 3 left it) - T2's own perturbation, from the Rev14-D2
    reverted baseline."""
    s1 = next(s for s in dims['stubs'] if s['label'] == S1_LABEL)
    extra_dl_um = frac * s1['nominal_length_um']
    return {S1_LABEL: dict(dl_um=extra_dl_um)}


def build_track_a_perturbed_overrides(dims, total_frac=TRACKA_TOTAL_FRAC):
    """Rev 16 Track A: S1's dl_um set to `total_frac` of NOMINAL (0.18 =
    0.15 v2-freeze + 0.03 Track A perturbation) - everything else (S2-S7)
    stays exactly as the CURRENT live filter_BB.py table has it (no
    override entry), i.e. the just-solved v2+S7 baseline. The baseline
    design itself needs NO overrides at all - build_geometry_with_overrides({})
    replays the live table verbatim."""
    s1 = next(s for s in dims['stubs'] if s['label'] == S1_LABEL)
    return {S1_LABEL: dict(dl_um=total_frac * s1['nominal_length_um'])}


# ===============================================================================
# design build - geometry/package/ports only; setups added separately so one
# geometry build can host multiple independent solves (T1's baseline design
# gets two single-freq setups + a sweep setup; T2's perturbed design gets
# just its own sweep setup)
# ===============================================================================

def build_base_design(project, design_name, geom, overwrite=True):
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
    metal_obj_name = build_filter_metal(model, geom)
    pkg = build_package(model, geom)
    make_port(model, pkg, 'P1', geom['port1_pos'], geom['port1_width'])
    make_port(model, pkg, 'P2', geom['port2_pos'], geom['port2_width'])
    audit = losslessness_audit(project, design)
    project.save()
    print('Design %r geometry built (metal=%r). Audit: %s' % (design_name, metal_obj_name, audit))
    return design, metal_obj_name


def add_single_freq_setup(design, setup_name, freq_ghz):
    return design.create_dm_setup(
        freq_ghz=freq_ghz, name=setup_name,
        max_delta_s=0.02, max_passes=12, min_passes=3, min_converged=2,
        pct_refinement=30, basis_order=1,
    )


def add_sweep_setup(design, setup_name, adaptive_freq_ghz, sweep_name, start_ghz, stop_ghz, count):
    setup = design.create_dm_setup(
        freq_ghz=adaptive_freq_ghz, name=setup_name,
        max_delta_s=0.02, max_passes=12, min_passes=3, min_converged=2,
        pct_refinement=30, basis_order=1,
    )
    sweep = setup.insert_sweep(
        start_ghz=start_ghz, stop_ghz=stop_ghz, count=count,
        step_ghz=None, name=sweep_name, type='Interpolating',
    )
    return setup, sweep


def _pull(sweep, expr, label, out_dir):
    report = sweep.create_report('Temp_%s' % label, expr)
    tmp_path = os.path.join(out_dir, '_tmp_%s_export.csv' % label)
    report.export_to_file(tmp_path)
    freqs_, vals_ = np.loadtxt(tmp_path, skiprows=1, delimiter=',').transpose()
    os.remove(tmp_path)
    return freqs_, vals_


# ===============================================================================
# T1 field plot - raw COM CreateFieldPlot + ExportFieldPlot + manual PyVista
# (see module docstring for the recall-vs-verified caveat)
# ===============================================================================

def render_current_field_plot(design, setup_sweep_name, metal_obj_name, freq_ghz, export_path, plot_name):
    """Surface current density (Mag_Jsurf) on the filter metal's own
    surface, at freq_ghz, from setup_sweep_name's own LastAdaptive
    solution."""
    import pyvista as pv

    plot_name = _safe_name(plot_name)
    fields_module = design._fields_calc
    fields_module.CreateFieldPlot(
        ['NAME:' + plot_name,
         'SolutionName:=', setup_sweep_name,
         'QuantityName:=', 'Mag_Jsurf',
         'PlotFolder:=', 'Currents',
         'UserSpecifyName:=', 0,
         'UserSpecifyFolder:=', 0,
         'IntrinsicVar:=', "Freq='%gGHz'" % freq_ghz,
         'PlotGeomInfo:=', [1, 'Surface', 'ObjList', 1, metal_obj_name],
         'FilterBoxes:=', [0],
         'PlotOnSurfaceOnly:=', True],
        'Field')

    tmp_case = os.path.join(OUT_DIR, '_tmp_%s.case' % plot_name)
    fields_module.ExportFieldPlot(plot_name, False, tmp_case)

    pv.OFF_SCREEN = True
    reader = pv.get_reader(tmp_case)
    mesh = reader.read()
    block = mesh[0]
    plotter = pv.Plotter(off_screen=True, window_size=[1400, 1000])
    plotter.add_mesh(block, scalars='Mag_Jsurf', cmap='inferno', show_edges=False,
                      scalar_bar_args={'title': 'Mag_Jsurf (A/m)'})
    plotter.view_xy()
    plotter.camera.parallel_projection = True
    plotter.screenshot(export_path)
    print('  field plot saved -> %s' % export_path)


# ===============================================================================
# T2 null survey - before/after comparison via find_all_notches() (imported,
# see module docstring)
# ===============================================================================

def match_nulls(nulls_before, nulls_after, max_shift_ghz=T2_NULL_MATCH_MAX_GHZ):
    """Best-pair-first greedy match (same principle as
    filter_BB_firstlight_HFSS.py's own build_dashboard() fix) between two
    null lists, by absolute frequency shift - avoids the same target-order
    cascading failure mode T4 fixed for the per-stub dashboard."""
    candidates = []
    for bi, (bf, _bd) in enumerate(nulls_before):
        for ai, (af, _ad) in enumerate(nulls_after):
            shift = af - bf
            if abs(shift) <= max_shift_ghz:
                candidates.append((abs(shift), bi, ai, shift))
    candidates.sort(key=lambda c: c[0])

    matched_before, matched_after = set(), set()
    rows = []
    for _abs_shift, bi, ai, shift in candidates:
        if bi in matched_before or ai in matched_after:
            continue
        matched_before.add(bi)
        matched_after.add(ai)
        bf, bd = nulls_before[bi]
        af, ad = nulls_after[ai]
        rows.append(dict(before_ghz=bf, before_db=bd, after_ghz=af, after_db=ad,
                          shift_ghz=shift, shift_pct=100.0 * shift / bf))
    for bi, (bf, bd) in enumerate(nulls_before):
        if bi not in matched_before:
            rows.append(dict(before_ghz=bf, before_db=bd, after_ghz=None, after_db=None,
                              shift_ghz=None, shift_pct=None))
    for ai, (af, ad) in enumerate(nulls_after):
        if ai not in matched_after:
            rows.append(dict(before_ghz=None, before_db=None, after_ghz=af, after_db=ad,
                              shift_ghz=None, shift_pct=None))
    rows.sort(key=lambda r: r['before_ghz'] if r['before_ghz'] is not None else r['after_ghz'])
    return rows


# ===============================================================================
# main
# ===============================================================================

def main_track_a():
    """Rev 16 Track A (Rev 15 A1): from the just-solved v2+S7 baseline,
    lengthen S1 alone by a further 3% of nominal (total 18% of nominal),
    coarse 0.5-14GHz sweep, match nulls before/after, report the response
    ratio r=(delta_f/f)/(delta_l/l). Separate throwaway designs
    (TrackA_V2S7_Baseline/TrackA_S1_Plus3pct) - the live filter_BB.py
    table (and its own committed HFSS/filter_BB_dims.json) are never
    touched by this script."""
    project = connect_project()
    dims = _load_dims()
    s1 = next(s for s in dims['stubs'] if s['label'] == S1_LABEL)
    baseline_dl_um = s1['dl_um']
    print('Track A baseline: v2+S7, S1 dl_um=%.2fum (=%.4f x nominal %.2fum) - LIVE table, no overrides.'
          % (baseline_dl_um, baseline_dl_um / s1['nominal_length_um'], s1['nominal_length_um']))

    baseline_geom = build_geometry_with_overrides({})
    design, _metal_obj_name = build_base_design(project, TRACKA_BASELINE_DESIGN_NAME, baseline_geom)
    setup_sweep_before, sweep_before = add_sweep_setup(
        design, 'Setup_Sweep', SWEEP_ADAPTIVE_FREQ_GHZ, 'Sweep_0p5_14',
        T2_SWEEP_START_GHZ, T2_SWEEP_STOP_GHZ, T2_SWEEP_COUNT)

    perturbed_overrides = build_track_a_perturbed_overrides(dims)
    s1_perturbed_dl_um = perturbed_overrides[S1_LABEL]['dl_um']
    print('Track A perturbed: S1 dl_um=%.2fum (=%.4f x nominal, total frac=%.2f) - S2-S7 unchanged.'
          % (s1_perturbed_dl_um, TRACKA_TOTAL_FRAC, TRACKA_TOTAL_FRAC))
    perturbed_geom = build_geometry_with_overrides(perturbed_overrides)
    design_p, _metal_obj_name_p = build_base_design(project, TRACKA_PERTURBED_DESIGN_NAME, perturbed_geom)
    setup_sweep_after, sweep_after = add_sweep_setup(
        design_p, 'Setup_Sweep', SWEEP_ADAPTIVE_FREQ_GHZ, 'Sweep_0p5_14',
        T2_SWEEP_START_GHZ, T2_SWEEP_STOP_GHZ, T2_SWEEP_COUNT)

    if not RUN_ANALYSIS:
        print('Setup complete (RUN_ANALYSIS=False). Inspect in AEDT, then set RUN_ANALYSIS=True and re-run.')
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    summary_lines = ['=' * 70, 'filter_BB Track A: +3%% S1 perturbation from the v2+S7 baseline (Rev 16)', '=' * 70]

    print('--- Track A: v2+S7 baseline sweep ---')
    setup_sweep_before.analyze()
    freqs_before, s21_before = _pull(sweep_before, 'dB(S(P2,P1))', 'TrackA_before', OUT_DIR)
    with open(os.path.join(OUT_DIR, 'tracka_baseline_sweep.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_GHz', 'S21_dB'])
        writer.writerows(zip(freqs_before, s21_before))

    print('--- Track A: +3%% perturbed sweep ---')
    setup_sweep_after.analyze()
    freqs_after, s21_after = _pull(sweep_after, 'dB(S(P2,P1))', 'TrackA_after', OUT_DIR)
    with open(os.path.join(OUT_DIR, 'tracka_perturbed_sweep.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_GHz', 'S21_dB'])
        writer.writerows(zip(freqs_after, s21_after))

    nulls_before = find_all_notches(freqs_before, s21_before)
    nulls_after = find_all_notches(freqs_after, s21_after)
    comparison = match_nulls(nulls_before, nulls_after, max_shift_ghz=TRACKA_NULL_MATCH_MAX_GHZ)

    comparison_path = os.path.join(OUT_DIR, 'tracka_null_comparison.csv')
    with open(comparison_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['before_ghz', 'before_db', 'after_ghz', 'after_db',
                                                 'shift_ghz', 'shift_pct'])
        writer.writeheader()
        writer.writerows(comparison)

    frac_dl_over_l = TRACKA_PERTURB_FRAC * s1['nominal_length_um'] / baseline_dl_um_len(s1, baseline_dl_um)
    summary_lines.append('-' * 70)
    summary_lines.append('Null survey before (v2+S7) vs. after (+%.0f%% of nominal further on S1, '
                          'fractional length change on S1 itself = %.4f):'
                          % (100 * TRACKA_PERTURB_FRAC, frac_dl_over_l))
    best_ratio_row = None
    for r in comparison:
        if r['before_ghz'] is not None and r['after_ghz'] is not None:
            r_val = (r['shift_pct'] / 100.0) / frac_dl_over_l
            summary_lines.append('  %.3fGHz(%.1fdB) -> %.3fGHz(%.1fdB)  shift=%+.3fGHz (%+.2f%%)  r=%+.3f'
                                  % (r['before_ghz'], r['before_db'], r['after_ghz'], r['after_db'],
                                     r['shift_ghz'], r['shift_pct'], r_val))
            if best_ratio_row is None or abs(r_val - (-1.0)) < abs(best_ratio_row[1] - (-1.0)):
                best_ratio_row = (r, r_val)
        elif r['before_ghz'] is not None:
            summary_lines.append('  %.3fGHz(%.1fdB) -> [null disappeared]' % (r['before_ghz'], r['before_db']))
        else:
            summary_lines.append('  [new null] -> %.3fGHz(%.1fdB)' % (r['after_ghz'], r['after_db']))

    summary_lines.append('-' * 70)
    if best_ratio_row is not None:
        r_row, r_val = best_ratio_row
        if -1.3 <= r_val <= -0.7:
            case = 'r~0.85-1.0 case: S1 is a normal quarter-wave stub whose zero sits high - pure attribution issue.'
        elif -0.35 <= r_val <= -0.25:
            case = 'r~0.25-0.35 case: S1 alive but responds at ~1/4 the ideal rate - consistent with the fold-penalty hypothesis (D4).'
        else:
            case = 'r does not cleanly match either named A2 case - report as-is, do not force a label.'
        summary_lines.append('TRACK A VERDICT: closest candidate %.3fGHz -> %.3fGHz, r=%+.3f. %s'
                              % (r_row['before_ghz'], r_row['after_ghz'], r_val, case))
    else:
        summary_lines.append('TRACK A VERDICT: no null tracked with a fractional shift matching S1\'s own '
                              '%.4f fractional length change - no null attributable to S1 at this step size either.'
                              % frac_dl_over_l)

    summary_lines.append('=' * 70)
    summary_text = '\n'.join(summary_lines)
    print(summary_text)
    with open(os.path.join(OUT_DIR, 'tracka_summary.txt'), 'w') as f:
        f.write(summary_text + '\n')


def baseline_dl_um_len(s1, baseline_dl_um):
    """S1's TOTAL realized length in the v2+S7 baseline (nominal + its
    frozen dl_um) - the correct denominator for Track A's own fractional
    length change (delta_l/l), not the bare nominal length."""
    return s1['nominal_length_um'] + baseline_dl_um


def main():
    if RUN_TRACK_A:
        main_track_a()
        return
    raise RuntimeError('RUN_TRACK_A=False and no other entry point is wired up in this Rev 16 revision - '
                        'the old Rev 14 T1/T2 campaign (build_baseline_overrides/build_perturbed_overrides, '
                        'S1_Nominal_Baseline/S1_Plus15pct) is complete and already reported; its functions '
                        'stay in this file as reference but main() no longer calls them automatically.')


if __name__ == '__main__':
    main()
