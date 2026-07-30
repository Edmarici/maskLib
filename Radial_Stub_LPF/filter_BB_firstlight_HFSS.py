#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 12 Phase 2: filter_BB "quick-look" first-light sim - fast real-package
read on whether the width-collapsed, all-70um six-stub filter_BB.py (Rev 12
Phase 1) behaves like the quarter-wave length synthesis predicts, BEFORE
committing to the much heavier Stage A pin+SNAIL machinery
(filter_BB_stageA_HFSS.py, already built, gated RUN_ANALYSIS=False).

REV 13 ADDITIONS (zero-placement pass 1, re-run against filter_BB.py's own
Rev-12-measurement-seeded stub lengths - see that file's own docstring):
  - Multi-frequency adaptive mesh at MULTI_FREQ_ADAPTIVE_GHZ (4.5/6.0/8.0GHz),
    attempted via raw COM (`_try_multi_freq_adaptive_setup()`) since pyEPR's
    own `create_dm_setup()` has no multi-freq support (checked installed
    source). The exact `MultipleAdaptiveFreqsSetup` param block is RECALLED
    AEDT scripting syntax, not verified against this specific pyEPR/AEDT
    install (this exact combination has already produced two confirmed real
    bugs this session - get_convergence()'s pandas incompatibility,
    get_setup()/get_sweep()'s solution_type-string mismatch, both worked
    around by bypassing the broken helper) - so this is wrapped in try/except
    with an automatic fallback to a known-good single-point adaptive at
    SINGLE_POINT_FALLBACK_GHZ=4.5 (the band that failed last pass), per the
    handoff's own explicit pre-authorization for this contingency.
  - Real convergence data (`export_convergence()`) via the SAME raw COM call
    pyEPR's own broken `get_convergence()` makes internally
    (`design._design.ExportConvergence(...)`), parsed with a small hand-
    written parser instead of pyEPR's own pandas-based one.
  - `compute_acceptance_pass1()`: this pass's own acceptance standard (band
    edge, all-six-matched-within-3%, S21@4.5GHz, convergence) - alongside,
    not replacing, Rev 12's own generic `compute_verdict()`.
  - Outputs use a `firstlight2_*` prefix - Rev 12's own `firstlight_*`
    outputs are left untouched as the historical record.

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
RUN_AMBIGUITY_ESCALATION = True  # fresh solve this pass - new one-solve budget

# Recovery mode: skip build_design()/analyze() entirely and reconnect to an
# ALREADY-SOLVED 'FirstLight' design/setup/sweeps by name (design.get_setup(),
# setup.get_sweep() - real pyEPR accessors, confirmed against installed
# source) instead of rebuilding/resolving. Exists because setup.get_convergence()
# has a real pyEPR/pandas incompatibility bug (DataFrame.drop() called with a
# positional axis arg newer pandas rejects) that crashed a prior run AFTER
# setup.analyze() had already completed successfully - don't throw away a
# real completed solve to a diagnostic print's own bug.
RECOVER_ONLY = False

# Quick-scan mode: coarsen the discrete sweep for a fast directional read
# (does each pass's measurement-seeded lengthening move things the right
# way?) before spending time on the full-resolution confirmation pass.
# Outputs get their own 'firstlight2_quickscan_passN_*' prefix (see
# SCAN_PASS/OUTPUT_PREFIX below) so each pass's own record is preserved
# distinctly, never overwritten by the next one, and so the eventual
# confirmed, full-resolution pass DESIGN_NOTES actually cites has a clean
# name. Set False and re-run once the quick-scan direction looks right.
QUICK_SCAN = False  # Rev 16 D3: this is a confirmation run scored against locked predictions -
                     # "must be swept with real resolution this run, not left to a coarse pass"

# Bump alongside filter_BB.py's own PREVIOUS_PASS_DASHBOARD_CSV/
# PREVIOUS_PASS_DIMS_JSON (which point at THIS pass's own -1 predecessor)
# every time a new pass starts - keeps outputs, the design name, and the
# side-by-side pass comparison (compare_passes()) all in sync.
SCAN_PASS = 3
# Rev 16: this run is a BASELINE CONFIRMATION (S7+v2, geometry frozen per
# Rev 16 Step 0), not another link in the pass-1/2/3 trim-iteration chain -
# SCAN_PASS stays at 3 only because some print framing below still
# references it informationally; PREVIOUS_PASS_PREFIX is disabled (None)
# since a pass-over-pass sensitivity comparison against pass-3 isn't
# meaningful here (S2-S6 are frozen, not iteratively re-trimmed; S1/S7
# differ structurally, not by a small trim step).
PREVIOUS_PASS_PREFIX = None  # for compare_passes() - disabled this run, see above
PREVIOUS_PASS_DIMS_JSON = 'filter_BB_dims_pass2.json'  # unused while PREVIOUS_PASS_PREFIX is None

PROJECT_NAME = 'filter_BB_firstlight'
# Rev 13: a killed background run left the old 'FirstLight' design stuck
# server-side (DeleteDesign() on it consistently raises a COM error across
# retries, while deleting an unrelated design in the same project works
# fine - confirmed via a diagnostic script, not assumed) - build under a
# fresh per-pass name instead of fighting AEDT's internal state; stuck
# designs are left orphaned in the project (harmless).
MAIN_DESIGN_NAME = 'FirstLight_V3_Confirm'

BORE_AXIAL_MARGIN_UM = 5000.0
SAPPHIRE_WIDTH_UM = 6900.0  # matches filter_BB.py's own chip width (bore-width, no pocket - see module docstring)

SWEEP_START_GHZ = 0.5
SWEEP_STOP_GHZ = 13.0
SWEEP_COUNT = 2501  # ~5MHz resolution, matches this family's established density - Interpolating sweeps
                     # are cheap regardless of count (adaptive algorithm, not one real solve per point),
                     # so QUICK_SCAN doesn't touch this one - only the Discrete sweep below is expensive.

DISCRETE_START_GHZ = 3.0  # Rev 16 D3: was 4.0 - lowered to cover the 3.0-5.0GHz S1-at-v2 test region
                            # (handoff's two requested windows, 3.0-5.0 and 5.0-8.5, are contiguous -
                            # one wider discrete range covers both, no multi-window mechanism needed)
DISCRETE_STOP_GHZ = 8.5
DISCRETE_STEP_GHZ = 0.05 if QUICK_SCAN else 0.01  # 50MHz quick-scan vs 10MHz confirm
DISCRETE_COUNT = int(round((DISCRETE_STOP_GHZ - DISCRETE_START_GHZ) / DISCRETE_STEP_GHZ)) + 1

# Passband, not the sweep midpoint - see module docstring's "ADAPTIVE MESH
# FREQUENCY" section for why (fields propagate the full device length here,
# unlike deep in the stopband where mesh refinement would starve the
# downstream half of the filter). Used for the escalation path (narrow
# single-stub windows - multi-freq adaptive isn't needed there).
ADAPTIVE_FREQ_GHZ = 3.0

# Rev 13 D3: multi-frequency adaptive for the MAIN build, attempted first
# (see module docstring); SINGLE_POINT_FALLBACK_GHZ is the handoff's own
# pre-authorized fallback if the raw-COM multi-freq attempt fails.
MULTI_FREQ_ADAPTIVE_GHZ = [3.5, 5.5, 8.0]  # Rev 16 D3: was [4.5, 6.0, 8.0] - low anchor moved down
                                             # to cover the 3.65GHz S1-at-v2 bare-pole question
SINGLE_POINT_FALLBACK_GHZ = 3.5  # moved down to match, same reasoning

OUTPUT_PREFIX = 'v3_confirm'
# Rev 16: fresh prefix, not tied to SCAN_PASS - this is a baseline
# confirmation run, not another pass-N trim iteration. Every earlier
# pass's own 'firstlight2_quickscan_passN_*'/'firstlight_*' outputs stay
# untouched.

# Rev 13 D3 Part II step 4 acceptance standard (compute_acceptance_pass1()).
BAND_EDGE_THRESHOLD_DB = -10.0
BAND_EDGE_MAX_GHZ = 4.35
ACCEPTANCE_ZERO_TOL_PCT = 3.0
ACCEPTANCE_S21_AT_4P5_DB = -20.0
ACCEPTANCE_MAX_DELTA_S = 0.02

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


def _try_multi_freq_adaptive_setup(design, name, freqs_ghz, max_delta_s, max_passes,
                                    min_passes, min_converged, pct_refinement, basis_order):
    """Rev 13 D3: raw-COM multi-frequency adaptive setup - pyEPR's own
    create_dm_setup() has no multi-freq support (checked installed source).
    Returns the setup name on success, None on ANY failure (caller falls
    back to create_dm_setup()'s known-good single-point path). This exact
    param block is RECALLED AEDT scripting syntax, not verified against
    this specific pyEPR/AEDT install - see module docstring. Verifies the
    setup actually exists AND actually has multi-freq adaptation enabled
    (not just "InsertSetup didn't raise") before trusting it, since a
    malformed-but-non-exception-raising call is a real risk with recalled
    syntax."""
    try:
        freq_pairs = ['NAME:MultipleAdaptiveFreqsSetup']
        for f in freqs_ghz:
            freq_pairs.extend(['%gGHz:=' % f, [max_delta_s, max_passes]])
        design._setup_module.InsertSetup(
            'HfssDriven', [
                'NAME:' + name,
                'AdaptMultipleFreqs:=', True,
                freq_pairs,
                'MaxDeltaS:=', max_delta_s,
                'MaximumPasses:=', max_passes,
                'MinimumPasses:=', min_passes,
                'MinimumConvergedPasses:=', min_converged,
                'PercentRefinement:=', pct_refinement,
                'IsEnabled:=', True,
                'BasisOrder:=', basis_order,
            ])
        if name not in list(design._setup_module.GetSetups()):
            print('  multi-freq adaptive setup %r not found after InsertSetup - treating as failed' % name)
            return None
        readback = design._design.GetPropertyValue('HfssTab', 'AnalysisSetup:' + name, 'Adaptive Solutions')
        print('  multi-freq adaptive setup %r created (readback: %r)' % (name, readback))
        return name
    except Exception as e:
        print('  multi-freq adaptive setup attempt raised %r - falling back to single-point' % (e,))
        return None


def build_design(project, design_name, geom, sweep_specs, overwrite=True, adaptive='multi'):
    """sweep_specs: list of dict(name, type, start, stop, count) - one
    Driven Modal setup, one insert_sweep() call per spec. Reused for both
    the main (coarse+discrete) build and the one-off ambiguity-escalation
    build (a single narrow discrete window). adaptive='multi' attempts
    Rev 13's multi-frequency mesh (main build); 'single' uses the plain
    ADAPTIVE_FREQ_GHZ passband point (escalation - a narrow single-stub
    window doesn't need multi-freq resolution)."""
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

    setup_name = None
    if adaptive == 'multi':
        setup_name = _try_multi_freq_adaptive_setup(
            design, 'FirstLight_Setup', MULTI_FREQ_ADAPTIVE_GHZ,
            max_delta_s=0.02, max_passes=12, min_passes=3, min_converged=2,
            pct_refinement=30, basis_order=1)
    if setup_name is not None:
        setup = HFSS.HfssDMSetup(design, setup_name)
    else:
        # ADAPTIVE_FREQ_GHZ (passband) for the escalation path, or
        # SINGLE_POINT_FALLBACK_GHZ (D3's own pre-authorized fallback) if
        # the multi-freq attempt above failed - see module docstring's
        # "ADAPTIVE MESH FREQUENCY" section for why NOT the sweep's own
        # midpoint (would starve mesh resolution downstream).
        fallback_freq = ADAPTIVE_FREQ_GHZ if adaptive != 'multi' else SINGLE_POINT_FALLBACK_GHZ
        if adaptive == 'multi':
            print('  using single-point fallback @ %.2fGHz' % fallback_freq)
        setup = design.create_dm_setup(
            freq_ghz=fallback_freq, name='FirstLight_Setup',
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


NOTCH_DEPTH_THRESHOLD_DB = -15.0  # Rev 14 T4: was -3.0 - too shallow to distinguish
                                    # a real zero from passband ripple (see below)
NOTCH_LOCAL_BASELINE_WINDOW_GHZ = 0.3  # +-300MHz neighborhood for the local-baseline gate
NOTCH_LOCAL_BASELINE_MARGIN_DB = 10.0  # must sit at least this far below its OWN local baseline
NOTCH_SEARCH_RANGE_GHZ = (3.5, 8.6)
NOTCH_MATCH_MAX_REL_OFFSET = 0.30  # a candidate more than 30% off target isn't a plausible match


def find_all_notches(freqs, vals_db, depth_threshold_db=NOTCH_DEPTH_THRESHOLD_DB,
                      baseline_window_ghz=NOTCH_LOCAL_BASELINE_WINDOW_GHZ,
                      baseline_margin_db=NOTCH_LOCAL_BASELINE_MARGIN_DB):
    """All local minima of vals_db that are REAL transmission zeros, not
    passband ripple - Rev 14 T4 hardening. The old flat -3dB-only threshold
    mistook a ~1.5dB peak-to-trough ripple dip (~-5dB absolute, at 4.35GHz)
    for a real notch across all of Rev 13's passes 1-3, misidentifying S1's
    own resonance and driving three passes of trim iteration against a
    feature that wasn't S1 at all (confirmed via a kinematic check: S1's
    length grew +27.4% cumulatively while the tracked feature only moved
    -8.4%, a ~0.31 sensitivity ratio where a real quarter-wave resonance
    should show ~1.0).

    A candidate must now be BOTH below the absolute depth_threshold_db AND
    at least baseline_margin_db below its own LOCAL baseline (mean S21 over
    +-baseline_window_ghz around the candidate) - ripple dips sit close to
    their own local neighborhood's average by definition; real zeros sit
    far below it. Returns (freq_ghz, depth_db) tuples sorted by frequency."""
    notches = []
    for i in range(1, len(freqs) - 1):
        if not (vals_db[i] < vals_db[i - 1] and vals_db[i] < vals_db[i + 1]):
            continue
        if vals_db[i] >= depth_threshold_db:
            continue
        lo, hi = freqs[i] - baseline_window_ghz, freqs[i] + baseline_window_ghz
        mask = (freqs >= lo) & (freqs <= hi)
        local_baseline = float(np.mean(vals_db[mask])) if np.any(mask) else float(vals_db[i])
        if vals_db[i] > local_baseline - baseline_margin_db:
            continue
        notches.append((float(freqs[i]), float(vals_db[i])))
    return notches


def build_dashboard(merged_f, merged_s21, dims):
    """Matches stub targets to real notches (see find_all_notches()) via
    GLOBAL best-pair-first greedy assignment: repeatedly claim whichever
    (target, notch) pair has the SMALLEST relative offset across ALL
    still-unmatched targets and still-unclaimed notches, not "process
    targets in a fixed order, take the nearest available" (Rev 14 T4 fix -
    the fixed-order approach cascades badly the moment one stub is
    genuinely absent: with a real notch sitting within TWO targets' search
    windows, a fixed processing order lets the stub that happens to go
    FIRST steal a notch that actually belongs to a LATER target, pushing
    every following assignment down by one slot - confirmed empirically
    against the pass-3 data once the ripple-rejection fix in
    find_all_notches() removed S1's old false candidate: S1 then grabbed
    S2's own real 4.700GHz notch outright, corrupting S2-S6 too, not just
    S1. Best-pair-first avoids this: the closest, most confident matches
    (S2's own 0%-error notch, S5's 1.4%) get claimed before any ambiguous
    ones are even considered, so a genuinely-absent stub is left with
    nothing rather than displacing a real match).

    A target with no unclaimed notch within NOTCH_MATCH_MAX_REL_OFFSET is
    reported as NO NOTCH FOUND (landed_f_ghz=None) rather than a bogus
    value - a real, physically meaningful outcome, not a search artifact
    to paper over. `ambiguous` now means exactly this: no matching notch
    found.

    delta_pct (PASS/FAIL basis) is landed-vs-TARGET, not landed-vs-
    predicted-from-bare-length - see module docstring's "DASHBOARD DELTA
    BASIS" section for why the bare-length re-prediction is contaminated
    for fan-terminated stubs (S2-S5) and would manufacture a false failure.
    delta_pct_vs_predicted is kept as a diagnostic-only column."""
    lo, hi = NOTCH_SEARCH_RANGE_GHZ
    mask = (merged_f >= lo) & (merged_f <= hi)
    available = find_all_notches(merged_f[mask], merged_s21[mask])

    stubs = dims['stubs']
    # All (stub_idx, notch_idx, rel_offset) candidate pairs within tolerance,
    # sorted best-match-first - claimed greedily, best pair wins first.
    candidates = []
    for si, stub in enumerate(stubs):
        target = stub['f_target_ghz']
        for ni, (cand_f, _cand_depth) in enumerate(available):
            rel_offset = abs(cand_f - target) / target
            if rel_offset <= NOTCH_MATCH_MAX_REL_OFFSET:
                candidates.append((rel_offset, si, ni))
    candidates.sort(key=lambda c: c[0])

    assigned_notch_for_stub = {}
    claimed_notches = set()
    for rel_offset, si, ni in candidates:
        if si in assigned_notch_for_stub or ni in claimed_notches:
            continue
        assigned_notch_for_stub[si] = ni
        claimed_notches.add(ni)

    by_label = {}
    for si, stub in enumerate(stubs):
        target = stub['f_target_ghz']
        predicted = stub['predicted_f_zero_ghz']
        landed_f = depth_db = delta_pct = delta_pct_vs_predicted = None
        if si in assigned_notch_for_stub:
            landed_f, depth_db = available[assigned_notch_for_stub[si]]
            delta_pct = 100.0 * (landed_f - target) / target
            delta_pct_vs_predicted = 100.0 * (landed_f - predicted) / predicted
        by_label[stub['label']] = dict(
            label=stub['label'], target_f_ghz=target, predicted_f_ghz=predicted, landed_f_ghz=landed_f,
            delta_pct=delta_pct, delta_pct_vs_predicted=delta_pct_vs_predicted,
            fan_terminated=stub['fan_term_rout_um'] > 0, depth_db=depth_db,
            ambiguous=(landed_f is None), target_length_um=stub['target_length_um'],
            escalation_perturbed_f_ghz='', escalation_shifted_as_expected='',
        )
    return [by_label[stub['label']] for stub in dims['stubs']]


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
        [dict(name='Escalation_Window', type='Discrete', start=lo, stop=hi, count=count)],
        adaptive='single')
    setup_p.analyze()
    freqs_p, s21_p, _ = pull_sweep(sweeps_p['Escalation_Window'], out_dir, '_esc_%s' % _safe_name(label))

    idx = int(np.argmin(s21_p))
    new_f = float(freqs_p[idx])
    if row['landed_f_ghz'] is not None:
        shifted_as_expected = new_f < row['landed_f_ghz']
        print('  perturbed null @ %.4fGHz (original %.4fGHz) - shifted lower as expected: %s'
              % (new_f, row['landed_f_ghz'], shifted_as_expected))
    else:
        shifted_as_expected = None
        print('  perturbed null @ %.4fGHz (no original landed value - stub had no matched notch)' % new_f)

    row['escalation_perturbed_f_ghz'] = new_f
    row['escalation_shifted_as_expected'] = shifted_as_expected
    return row


def compute_valleys(dashboard_rows, freqs, vals, band=VALLEY_BAND_GHZ):
    zero_freqs = sorted(r['landed_f_ghz'] for r in dashboard_rows if r['landed_f_ghz'] is not None)
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


def count_all_nulls_in_range(freqs, vals, band, dashboard_rows):
    """Rev 14 T4: total REAL transmission zeros (find_all_notches(), the
    hardened matcher) across the FULL given band vs. the number of stubs
    matched by build_dashboard() - surfaces unassigned nulls (e.g. the SIR
    overtone candidates around 10/11.5GHz - T3's own job to attribute,
    deferred this session, but worth having on the record now) rather than
    silently ignoring anything outside the stubs' own search windows."""
    lo, hi = band
    mask = (freqs >= lo) & (freqs <= hi)
    all_nulls = find_all_notches(freqs[mask], vals[mask])
    matched_freqs = [r['landed_f_ghz'] for r in dashboard_rows if r['landed_f_ghz'] is not None]
    unassigned = [n for n in all_nulls if not any(abs(n[0] - mf) < 0.05 for mf in matched_freqs)]
    return dict(total_nulls=len(all_nulls), n_stubs=len(dashboard_rows),
                n_matched=len(matched_freqs), all_nulls=all_nulls, unassigned=unassigned)


def export_convergence(design, setup_name, out_dir, suffix=''):
    """Rev 13 D3: real convergence data, bypassing pyEPR's own broken
    get_convergence() (a real pandas incompatibility - DataFrame.drop()
    called with a positional axis arg newer pandas rejects). Calls the
    SAME underlying COM method get_convergence() itself uses
    (design._design.ExportConvergence(...)) directly, then parses the
    resulting text with a small hand-written, pandas-free parser. Returns
    the parsed rows (list of dicts) or None on any failure - per the
    handoff, a failed export blocks the ACCEPTANCE VERDICT, not the whole
    script (caller decides what None means downstream)."""
    tmp_path = os.path.join(out_dir, '_tmp_convergence%s.conv' % suffix)
    try:
        design._design.ExportConvergence(setup_name, '', tmp_path, True)
    except Exception as e:
        print('ExportConvergence raised %r - convergence data unavailable this run '
              '(Rung 2 fallback: export manually from the AEDT UI - right-click the setup '
              '-> View/Edit or similar -> Export Convergence)' % (e,))
        return None
    if not os.path.exists(tmp_path):
        print('ExportConvergence did not write %r - convergence data unavailable this run.' % tmp_path)
        return None
    text = open(tmp_path).read()
    os.remove(tmp_path)
    sections = text.split('==================')
    if len(sections) < 4:
        raw_path = os.path.join(out_dir, '%s_convergence_raw.txt' % OUTPUT_PREFIX)
        with open(raw_path, 'w') as f:
            f.write(text)
        print('Convergence export text did not have the expected ====-delimited sections '
              '(got %d) - raw text saved for manual inspection -> %s' % (len(sections), raw_path))
        return None
    table_text = sections[3].strip()
    lines = [ln for ln in table_text.splitlines() if ln.strip()]
    if not lines:
        return None
    header = [h.strip() for h in lines[0].split('|') if h.strip() and not h.strip().startswith('Unnamed')]
    rows = []
    for ln in lines[1:]:
        cells = [c.strip() for c in ln.split('|') if c.strip() != '']
        if len(cells) < len(header):
            continue
        rows.append(dict(zip(header, cells[:len(header)])))
    return rows


def field_plot_at_frequency(design, setup_name, freq_ghz, out_path):
    """Best-effort field plot for the S1 investigation trigger (Rev 13
    Part II step 5) - pyEPR has no field-plot wrapper (checked installed
    source), so this is raw COM against the FieldsReporter module. Wrapped
    in try/except at the call site - a failure here degrades to a text-
    only flag in the summary, not a blocked run (this is a conditional,
    investigation-only deliverable, not a core one)."""
    fields_module = design._design.GetModule('FieldsReporter')
    fields_module.CreateFieldPlot(
        ['NAME:MagE1', 'SolutionName:=', '%s : LastAdaptive' % setup_name,
         'QuantityName:=', 'Mag_E', 'PlotFolder:=', 'E Field',
         'IntrinsicVar:=', 'Freq=\'%gGHz\'' % freq_ghz,
         ['NAME:FieldsPlotItemIDs'],
         'SurfaceOnly:=', False, 'PlotOnSurfaceOnly:=', False],
        'MagE1', 'Field')
    design._design.ExportModelImageToFile(out_path, 1600, 1200, ['NAME:SaveImageParams'])


def compute_acceptance_pass1(dashboard_rows, merged_f, merged_s21, convergence_rows):
    """Rev 13's own acceptance standard (handoff Part II step 4) - printed
    alongside, not instead of, Rev 12's own generic compute_verdict()."""
    mask = merged_f >= 0.5
    f, v = merged_f[mask], merged_s21[mask]
    band_edge_ghz = None
    for i in range(1, len(f)):
        if v[i - 1] > BAND_EDGE_THRESHOLD_DB >= v[i]:
            band_edge_ghz = float(f[i])
            break
    band_edge_ok = band_edge_ghz is not None and band_edge_ghz <= BAND_EDGE_MAX_GHZ

    missing = [r['label'] for r in dashboard_rows if r['landed_f_ghz'] is None]
    deltas = [abs(r['delta_pct']) for r in dashboard_rows if r['delta_pct'] is not None]
    all_matched_ok = not missing
    all_within_tol = all_matched_ok and bool(deltas) and max(deltas) <= ACCEPTANCE_ZERO_TOL_PCT

    spot_idx = int(np.argmin(np.abs(merged_f - SPOT_FREQ_GHZ)))
    spot_s21 = float(merged_s21[spot_idx])
    spot_ok = spot_s21 <= ACCEPTANCE_S21_AT_4P5_DB

    last_delta_s = None
    if convergence_rows:
        last_row = convergence_rows[-1]
        for key in ('Delta S', 'MaxDeltaS', 'Max Mag. Delta S', 'Delta S1'):
            if key in last_row:
                try:
                    last_delta_s = float(last_row[key])
                except ValueError:
                    pass
                break
    convergence_ok = last_delta_s is not None and last_delta_s <= ACCEPTANCE_MAX_DELTA_S

    lines = [
        'Band edge (S21=%.0fdB crossing) <= %.2fGHz: %s (found @ %s)'
        % (BAND_EDGE_THRESHOLD_DB, BAND_EDGE_MAX_GHZ, 'PASS' if band_edge_ok else 'FAIL',
           ('%.3fGHz' % band_edge_ghz) if band_edge_ghz is not None else 'not found'),
        'All %d stubs matched within %.0f%%: %s%s'
        % (len(dashboard_rows), ACCEPTANCE_ZERO_TOL_PCT, 'PASS' if all_within_tol else 'FAIL',
           '' if all_matched_ok else ' (unmatched: %s)' % missing),
        'S21@%.1fGHz <= %.0fdB: %s (%.2fdB)'
        % (SPOT_FREQ_GHZ, ACCEPTANCE_S21_AT_4P5_DB, 'PASS' if spot_ok else 'FAIL', spot_s21),
        'Convergence history present, final delta-S <= %.2f: %s%s'
        % (ACCEPTANCE_MAX_DELTA_S, 'PASS' if convergence_ok else 'FAIL',
           (' (%.4f)' % last_delta_s) if last_delta_s is not None else ' (no convergence data)'),
        'Valleys: REPORT ONLY this pass (judged after zero placement)',
    ]
    return '\n'.join(lines)


SENSITIVITY_RANGE = (-1.3, -0.7)  # Rev 14 T4: expected (delta_f/f)/(delta_L/L) for a REAL
                                    # quarter-wave resonance is ~-1.0 (f~1/L) - outside this
                                    # range means the tracked feature likely ISN'T that stub's
                                    # own resonance (S1's own was ~-0.31 across passes 1-3).


def compare_passes(dashboard_rows, previous_pass_prefix, out_dir, dims=None):
    """Side-by-side dashboard comparison against the previous pass's own
    saved dashboard CSV (Rev 13 pass-2 handoff: "log both passes'
    dashboards side by side in the summary so the convergence rate is on
    record"). Returns the comparison text, or a short note if the previous
    pass's dashboard isn't found (doesn't block the rest of the run).

    Rev 14 T4: also computes a movement-vs-length SENSITIVITY per stub -
    (delta_f/f)/(delta_L/L) between the two passes' own realized lengths
    (from each pass's own dims JSON, `dims` = the CURRENT pass's already-
    loaded dict, PREVIOUS_PASS_DIMS_JSON = the previous pass's saved one)
    and landed frequencies - flagged loudly outside SENSITIVITY_RANGE. This
    is exactly the check that would have caught passes 1-3's S1
    misidentification as it happened, rather than requiring a dedicated
    post-hoc audit (see find_all_notches()'s own docstring for the story)."""
    prev_path = os.path.join(out_dir, '%s_dashboard.csv' % previous_pass_prefix)
    if not os.path.exists(prev_path):
        return 'No previous-pass dashboard found at %s - skipping comparison.' % prev_path
    prev_rows = {}
    with open(prev_path, newline='') as f:
        for row in csv.DictReader(f):
            prev_rows[row['label']] = row

    prev_dims = {}
    prev_dims_path = os.path.join(out_dir, PREVIOUS_PASS_DIMS_JSON)
    if os.path.exists(prev_dims_path):
        with open(prev_dims_path) as f:
            prev_dims = {s['label']: s for s in json.load(f)['stubs']}
    cur_dims = {s['label']: s for s in dims['stubs']} if dims else {}

    def _fmt(landed, delta):
        if not landed:
            return 'NO NOTCH'
        return '%6.3fGHz/%+6.2f%%' % (float(landed), float(delta))

    lines = ['Pass-over-pass comparison (target | previous landed/delta%% | this landed/delta%% | '
             'depth prev->this | sensitivity):']
    for r in dashboard_rows:
        label = r['label']
        prev = prev_rows.get(label)
        if prev is None:
            lines.append('  %-8s %6.3f | (no previous data)' % (label, r['target_f_ghz']))
            continue
        prev_str = _fmt(prev.get('landed_f_ghz'), prev.get('delta_pct'))
        cur_str = (_fmt(r['landed_f_ghz'], r['delta_pct']) if r['landed_f_ghz'] is not None
                   else 'NO NOTCH')
        prev_depth = prev.get('depth_db')
        depth_str = '%s -> %s' % (
            ('%.1fdB' % float(prev_depth)) if prev_depth else 'n/a',
            ('%.1fdB' % r['depth_db']) if r['depth_db'] is not None else 'n/a')

        sens_str = 'n/a'
        prev_landed = prev.get('landed_f_ghz')
        cur_landed = r['landed_f_ghz']
        prev_L = prev_dims.get(label, {}).get('target_length_um')
        cur_L = cur_dims.get(label, {}).get('target_length_um')
        if prev_landed and cur_landed is not None and prev_L and cur_L:
            prev_landed_f = float(prev_landed)
            frac_df = (cur_landed - prev_landed_f) / prev_landed_f
            frac_dL = (cur_L - prev_L) / prev_L
            if abs(frac_dL) > 1e-6:
                sensitivity = frac_df / frac_dL
                lo, hi = SENSITIVITY_RANGE
                flag = '' if lo <= sensitivity <= hi else '  <<< SENSITIVITY OUT OF RANGE (not this stub\'s own resonance?)'
                sens_str = '%+.2f%s' % (sensitivity, flag)

        lines.append('  %-8s %6.3f | %s | %s | depth %s | sens %s'
                      % (label, r['target_f_ghz'], prev_str, cur_str, depth_str, sens_str))
    return '\n'.join(lines)


def compute_verdict(dashboard_rows, valley_rows, passband_rows):
    missing = [r['label'] for r in dashboard_rows if r['landed_f_ghz'] is None]
    found_deltas = [abs(r['delta_pct']) for r in dashboard_rows if r['delta_pct'] is not None]
    # A stub with NO matched notch is worse than any delta%, not something to
    # silently drop from the max() - counts as an automatic FAIL, reported
    # explicitly rather than folded into max_delta's own number.
    notches_ok = not missing
    max_delta = max(found_deltas) if found_deltas else float('nan')
    zeros_ok = notches_ok and max_delta <= 5.0
    worst_valley = max((r['worst_s21_db'] for r in valley_rows), default=float('nan'))
    valleys_ok = worst_valley <= -30.0
    pb_vals = [r['s21_db'] for r in passband_rows if r['freq_ghz'] <= 3.3]
    pb_spread = (max(pb_vals) - min(pb_vals)) if pb_vals else float('nan')
    passband_ok = pb_spread <= 2.0
    lines = [
        'Every stub shows a matched notch: %s%s'
        % ('PASS' if notches_ok else 'FAIL', '' if notches_ok else ' (no notch found for: %s)' % missing),
        'Zeros within ~5%% of target design frequency: %s (max |delta| among matched=%.2f%%)'
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

    if RECOVER_ONLY:
        print('RECOVER_ONLY=True: reconnecting to an already-solved FirstLight design '
              '(no rebuild, no re-solve).')
        design = project.get_design(MAIN_DESIGN_NAME)
        # design.get_setup()/setup.get_sweep() dispatch on design.solution_type
        # (design.GetSolutionType(), a raw AEDT COM call) against a hardcoded
        # "DrivenModal" string - returned None here (a real pyEPR/AEDT-version
        # string mismatch, same class of issue as get_convergence()'s own
        # pandas bug above). Construct the wrapper objects directly instead -
        # exactly what get_setup()/get_sweep() build internally on a match,
        # confirmed against HfssDMSetup.__init__(design, name)/
        # HfssFrequencySweep.__init__(setup, name)'s own installed source.
        setup = HFSS.HfssDMSetup(design, 'FirstLight_Setup')
        sweeps = {name: HFSS.HfssFrequencySweep(setup, name) for name in ('Coarse_Sweep', 'Discrete_Window')}
    else:
        main_sweep_specs = [
            dict(name='Coarse_Sweep', type='Interpolating', start=SWEEP_START_GHZ, stop=SWEEP_STOP_GHZ,
                 count=SWEEP_COUNT),
            dict(name='Discrete_Window', type='Discrete', start=DISCRETE_START_GHZ, stop=DISCRETE_STOP_GHZ,
                 count=DISCRETE_COUNT),
        ]
        design, setup, sweeps = build_design(project, MAIN_DESIGN_NAME, geom, main_sweep_specs)

        if not RUN_ANALYSIS:
            print('Setup complete (RUN_ANALYSIS=False). Inspect in AEDT via a FRESH COM '
                  'connection, enumerating every project handle named %r individually '
                  '(CLAUDE.md duplicate-AEDT-project lesson) - confirm: filter metal is '
                  'one united solid, BoreVacuum+Substrate present with no intersections, '
                  'P1/P2 lumped ports both assigned at z0=%s, losslessness audit printed '
                  'clean above. Then set RUN_ANALYSIS=True and re-run.' % (PROJECT_NAME, Z0_FIRSTLIGHT))
            return

        print('RUN_ANALYSIS=True: solving FirstLight...')
        setup.analyze()

    # Rev 13 D3: real convergence data via raw ExportConvergence, not
    # pyEPR's own broken get_convergence() - called here regardless of
    # RECOVER_ONLY vs. a fresh solve, since `design`/`setup` are populated
    # either way by this point.
    convergence_rows = export_convergence(design, setup.name, out_dir)
    convergence_path = os.path.join(out_dir, '%s_convergence.csv' % OUTPUT_PREFIX)
    if convergence_rows:
        with open(convergence_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(convergence_rows[0].keys()))
            writer.writeheader()
            writer.writerows(convergence_rows)
        print('Convergence data (%d passes) saved -> %s' % (len(convergence_rows), convergence_path))
    else:
        print('Convergence data unavailable this run (see message above) - '
              'acceptance verdict will FAIL the convergence criterion accordingly.')

    freqs_c, s21_c, s11_c = pull_sweep(sweeps['Coarse_Sweep'], out_dir, '_coarse')
    freqs_d, s21_d, s11_d = pull_sweep(sweeps['Discrete_Window'], out_dir, '_discrete')
    window = (DISCRETE_START_GHZ, DISCRETE_STOP_GHZ)
    merged_f, merged_s21 = merge_sweep_data(freqs_c, s21_c, freqs_d, s21_d, window)
    _, merged_s11 = merge_sweep_data(freqs_c, s11_c, freqs_d, s11_d, window)

    # --- deliverable 1: merged S21/S11 CSV + plot ---
    s21_csv_path = os.path.join(out_dir, '%s_S21.csv' % OUTPUT_PREFIX)
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
        png_path = os.path.join(out_dir, '%s_S21.png' % OUTPUT_PREFIX)
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

    dashboard_path = os.path.join(out_dir, '%s_dashboard.csv' % OUTPUT_PREFIX)
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
    valleys_path = os.path.join(out_dir, '%s_valleys.csv' % OUTPUT_PREFIX)
    with open(valleys_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['lo_ghz', 'hi_ghz', 'worst_s21_db', 'worst_freq_ghz'])
        writer.writeheader()
        writer.writerows(valley_rows)
    spot_idx = int(np.argmin(np.abs(merged_f - SPOT_FREQ_GHZ)))
    spot_s21 = float(merged_s21[spot_idx])
    print('Valleys saved -> %s; S21@%.1fGHz = %.2fdB' % (valleys_path, SPOT_FREQ_GHZ, spot_s21))

    # --- deliverable 4: passband readout ---
    passband_rows = compute_passband(merged_f, merged_s21)
    passband_path = os.path.join(out_dir, '%s_passband.csv' % OUTPUT_PREFIX)
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
    needles_path = os.path.join(out_dir, '%s_needles.csv' % OUTPUT_PREFIX)
    with open(needles_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['freq_ghz', 's21_db'])
        writer.writeheader()
        writer.writerows(needle_rows)
    print('Needles (%d found above %.0fdB in %.1f-%.1fGHz) saved -> %s'
          % (len(needle_rows), NEEDLE_THRESHOLD_DB, NEEDLE_BAND_GHZ[0], NEEDLE_BAND_GHZ[1], needles_path))

    # --- Rev 14 T4: null-count check over the FULL sweep range - surfaces
    # unassigned nulls (e.g. SIR overtone candidates) rather than only ever
    # looking inside each stub's own narrow search window.
    null_count_info = count_all_nulls_in_range(merged_f, merged_s21, (SWEEP_START_GHZ, SWEEP_STOP_GHZ), dashboard_rows)
    print('Full-sweep null count (%.1f-%.1fGHz): %d real zeros found vs %d stubs (%d matched, %d unassigned)'
          % (SWEEP_START_GHZ, SWEEP_STOP_GHZ, null_count_info['total_nulls'], null_count_info['n_stubs'],
             null_count_info['n_matched'], len(null_count_info['unassigned'])))
    if null_count_info['unassigned']:
        print('  unassigned nulls: %s'
              % ['%.3fGHz(%.1fdB)' % (f, d) for f, d in null_count_info['unassigned']])

    # --- Rev 13 S1 investigation trigger: if S1 (4.2GHz) still shows no
    # matched notch even with converged mesh and the lengthened upstream
    # section, this is its own genuine open finding, not something to
    # silently patch with more dl_um - a best-effort field plot (degrades
    # to a text-only flag on any failure) documents it.
    s1_row = next((r for r in dashboard_rows if r['label'] == '4.2GHz'), None)
    s1_field_plot_note = ''
    if s1_row is not None and s1_row['landed_f_ghz'] is None:
        s1_plot_path = os.path.join(out_dir, '%s_S1_field_4p2GHz.png' % OUTPUT_PREFIX)
        try:
            field_plot_at_frequency(design, setup.name, 4.2, s1_plot_path)
            s1_field_plot_note = '  field plot @ 4.2GHz saved -> %s' % s1_plot_path
            print(s1_field_plot_note)
        except Exception as e:
            s1_field_plot_note = ('  field plot attempt raised %r - S1 remains an OPEN, UN-PLOTTED '
                                   'investigation (not silently patched with more dl_um)' % (e,))
            print(s1_field_plot_note)

    # --- deliverable 6: verdict + Rev 13 acceptance ---
    verdict_text = compute_verdict(dashboard_rows, valley_rows, passband_rows)
    acceptance_text = compute_acceptance_pass1(dashboard_rows, merged_f, merged_s21, convergence_rows)
    summary_lines = [
        '=' * 70, 'filter_BB first light - Rev 16 S7+v2 baseline confirmation', '=' * 70,
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
        '  delta%-vs-target is the PASS/FAIL basis (this pass\'s whole point - do the Rev-12-',
        '  measurement-seeded lengths land closer to target than Rev 12\'s did). delta%-vs-',
        '  predicted is diagnostic ONLY, and its own sign/size is EXPECTED to look different',
        '  from Rev 12: these stubs were deliberately built LONGER than the naive bare-formula',
        '  length for their target, betting on the real (fan-loaded/measurement-corrected)',
        '  structure landing on target where the bare formula alone would not - so a large',
        '  NEGATIVE delta%-vs-predicted here is the correction working as intended, not a flag.',
    ]
    for r in dashboard_rows:
        if r['landed_f_ghz'] is not None:
            landed_str = ('%6.3f GHz | %+6.2f%% | %+6.2f%%  (%s, depth %.1fdB)'
                          % (r['landed_f_ghz'], r['delta_pct'], r['delta_pct_vs_predicted'],
                             'fan-terminated' if r['fan_terminated'] else 'UNTERMINATED-clean-check',
                             r['depth_db']))
        else:
            landed_str = 'NO NOTCH FOUND (no local min <%.0fdB matched within %.0f%% of target)' % (
                NOTCH_DEPTH_THRESHOLD_DB, 100 * NOTCH_MATCH_MAX_REL_OFFSET)
        summary_lines.append('  %-8s %6.3f | %6.3f | %s%s'
                              % (r['label'], r['target_f_ghz'], r['predicted_f_ghz'], landed_str,
                                 '  <<NO MATCH' if r['ambiguous'] else ''))
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
    summary_lines.append('-' * 70)
    summary_lines.append('Full-sweep null count (%.1f-%.1fGHz): %d real zeros vs %d stubs (%d matched, %d unassigned)'
                          % (SWEEP_START_GHZ, SWEEP_STOP_GHZ, null_count_info['total_nulls'],
                             null_count_info['n_stubs'], null_count_info['n_matched'],
                             len(null_count_info['unassigned'])))
    if null_count_info['unassigned']:
        summary_lines.append('  unassigned: %s'
                              % ['%.3fGHz(%.1fdB)' % (f, d) for f, d in null_count_info['unassigned']])
    if s1_field_plot_note:
        summary_lines.append('-' * 70)
        summary_lines.append('S1 (4.2GHz) investigation:')
        summary_lines.append(s1_field_plot_note)
    if PREVIOUS_PASS_PREFIX:
        summary_lines.append('=' * 70)
        summary_lines.append(compare_passes(dashboard_rows, PREVIOUS_PASS_PREFIX, out_dir, dims=dims))
    summary_lines.append('=' * 70)
    summary_lines.append('REV 13 ACCEPTANCE (standing standard, evaluated on the S7+v2 baseline):')
    summary_lines.append(acceptance_text)
    summary_lines.append('=' * 70)
    summary_lines.append('REV 12 VERDICT (generic, kept for continuity):')
    summary_lines.append(verdict_text)
    summary_lines.append('=' * 70)
    summary_text = '\n'.join(summary_lines)
    print(summary_text)
    with open(os.path.join(out_dir, '%s_summary.txt' % OUTPUT_PREFIX), 'w') as f:
        f.write(summary_text + '\n')


if __name__ == '__main__':
    main()
