#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 11 Models B+C: bore-flattening parametric study - zero frequency of an
UNFOLDED L60-style branch pair (Model B) and an UNFOLDED filter_BB-style
stub (Model C) vs. bore_h. Companion to oval_bore_epseff_HFSS.py (Model A,
pyaedt) - this file is pyEPR/raw win32com, matching filter_L60_HFSS.py/
filter_L60_package_HFSS.py's own established convention for standard
2-port driven-modal S21 extraction (Rev 9's pyaedt choice was specifically
for multi-mode wave-port eigenmode work that doesn't apply here).

GEOMETRY SOURCE - dimensions resolved against the handoff's own stated
numbers before writing code (same discipline as every prior Rev in this
session):
  - Model B (branch): handoff says "P4 dims from the Rev 6 table: stalk
    3.137mm x 125um -> use 70um per width-collapse lesson if preferred;
    fan Rout 1.229mm, Rin 88.39um, 90deg." Checked filter_L60.py's live
    BRANCH_PAIRS table directly - stalk_length=3137.0 and fan Rout/Rin
    match exactly, but W_HIZ (stalk width) is ALREADY 70um (the handoff's
    own fallback is the current real value, no ambiguity) and FAN_ANGLE
    is 115deg (Rev7), not 90. Using the REAL current P4 geometry (70um,
    115deg) - the whole point is testing whether the ACTUAL as-built
    branch (target 4.752GHz) reaches it, not a stale 90deg geometry.
  - Model C (stub): handoff's own explicit standalone numbers (6.03mm x
    70um, no terminator) don't match filter_BB.py's CURRENT live STUBS
    table entry for f=5.3 (w=125um, fan_term=300um present) - using the
    handoff's own numbers as given (a deliberately simplified
    representative stub for isolating the eps_eff/length effect, not a
    byte-exact replica of the real folded+terminated design).
  Both UNFOLDED (straight stalks, no folded_stub()/folded_branch_pair()
  machinery) per the handoff's own explicit instruction.

BORE GEOMETRY - A DELIBERATELY DIFFERENT bore_w THAN MODEL A, NOT A BUG:
Model A's bore_w (~7mm) matches the REAL package width. An UNFOLDED P4
branch pair does NOT fit inside that width - direct calculation: one
branch's own reach from centerline = stalk_length + (fan_rout - fan_rin)
= 3137 + (1229-88.39) = 4277.6um, and a MIRRORED PAIR needs that on BOTH
sides = ~8555um total, exceeding even Model A's own widened 7185um bore_w.
Model C's single-sided 6030um stub reach is comparably large. Since the
handoff's own "UNFOLDED" instruction is a deliberate simplification for
isolating physics (not meant to fit a real package), this file uses
SEPARATE, PER-MODEL bore widths (BORE_W_B_UM=10mm, BORE_W_C_UM=13mm) -
each the tightest comfortable fit for that model's own reach, not one
shared oversized value (an earlier 14mm-for-both version measurably
distorted Model B's own result - see the "MEASURED CONSEQUENCE" paragraph
below) - while sweeping bore_h (the actual variable under test) over the
SAME values as Model A. This means Model B/C's own "bore_h=6.985
(reference)" point is NOT a true circle here (bore_w != bore_h at either
model's own width) - just the least-flattened stadium in the sweep, which
is still a valid baseline for comparison purposes (Models B/C have no
pre-existing Rev9-style calibration value to reproduce the way Model A
does, so there's no regression-check reason to force a true
circle). Every bore_h in the sweep uses the SAME stadium construction -
no reference/circle special-case needed at all, unlike Model A.

MEASURED CONSEQUENCE of bore_w choice (why it was tightened from an
original, more generous 14mm-for-both): a live test of Model B at the
reference bore_h with BORE_W_UM=14000 found its S21 null at ~11.6GHz -
2.4x the real P4 design's own 4.752GHz target - confirmed (via a widened
0.5-12GHz coarse sweep, still the global minimum, no competing dip near
4.752GHz anywhere) that this is real, not a sweep-range artifact. Plausible
explanation: a 14mm test bore is ~2x the real ~7mm package, giving the fan
even less shunt capacitance than the already capacitance-starved real
design, pushing the LC resonance higher. Tightening bore_w per-model to the
smallest comfortable fit (still confirmed >270um clearance at every swept
bore_h, including the smallest) reduces but does NOT eliminate this offset
- Model C's own reach (6030um) exceeds the real package's ~3492.5um half-
width regardless of bore_w choice, so its own absolute f_zero values stay
offset from anything a real (folded, real-package) design would show. The
TREND vs bore_h (this study's actual question) is the trustworthy signal
either way; treat absolute f_zero-vs-target comparisons as approximate.

WALL BOUNDARY: reuses filter_L60_package_HFSS.py's own simpler convention
(assign_perfect_E to the WHOLE bore object, not per-face) rather than
Model A's own per-face wall-vs-notch discrimination (which needed a real
fix there - pyaedt's `f.is_planar`/`f.center` face properties aren't
available via pyEPR/raw win32com anyway). If this causes an "intersecting
solids" validation error the way it would for a boolean-subtracted bore,
that will surface directly in the first live build and gets fixed then
- not speculatively engineered around here.

RUN VIA THE SEPARATE PYEPR ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe oval_bore_branch_stub_HFSS.py
Run from THIS file's own directory.
"""
import csv
import math
import os
import sys

import numpy as np
from pyEPR import ansys as HFSS

sys.path.insert(0, os.path.dirname(__file__))
from filter_L30_hfss_geometry import SAPPHIRE_THICKNESS_UM, METAL_THICKNESS_UM, Z0_PORT, um  # noqa: E402

PROJECT_NAME = 'oval_branch_stub'

# --- bore geometry: SAME bore_h sweep as Model A, SEPARATE (larger) bore_w
# per model, MINIMIZED to the tightest comfortable fit rather than one
# generously-oversized value shared by both (see module docstring) - a
# live test found Model B's own null at ~11.6GHz vs the real P4 design's
# 4.752GHz target, and confirmed (widened 0.5-12GHz sweep, still the
# global minimum) this isn't a sweep-range artifact; a plausible physical
# explanation is that the ORIGINAL bore_w=14000 (chosen only for "does it
# fit") is ~2x the real ~7000um package, giving the fan even less shunt
# capacitance than the (already capacitance-starved) real design and
# pushing its LC resonance higher. Tightened both bore widths to the
# smallest value that still comfortably fits each model's own UNFOLDED
# reach (direct calculation, see notebooks-style comment at each
# constant), to get as close to real package scale as the "UNFOLDED"
# instruction physically allows.
BORE_H_TO_RUN_UM = [6985.0, 4000.0, 3000.0, 2000.0, 1500.0, 1000.0]

# Model B: mirrored-pair reach per side = stalk_length + (fan_rout-fan_rin)
# = 3137 + (1229-88.39) = 4277.6um; mirrored total = 8555.2um. 10000um
# gives 722um clearance per side (comfortable margin for the fan's own
# 115deg angular spread, not just its straight-ahead reach) while staying
# far closer to the real ~7000um package than the original 14000um guess.
BORE_W_B_UM = 10000.0

# Model C: single-sided stub reach = 6030um (the handoff's own literal
# spec) - this ALONE already exceeds the real package's own ~3492.5um
# half-width, regardless of any folding/mirroring choice, so it can't be
# brought to real scale without violating the handoff's explicit stub
# length. 13000um gives 470um clearance - a modest tightening from the
# original 14000um, at the practical minimum for this model's own geometry.
BORE_W_C_UM = 13000.0

THROUGH_LINE_LENGTH_UM = 10000.0
BORE_AXIAL_MARGIN_UM = 1000.0
BORE_LENGTH_UM = THROUGH_LINE_LENGTH_UM + 2 * BORE_AXIAL_MARGIN_UM
SUBSTRATE_WIDTH_B_UM = 9200.0  # margin inside BORE_W_B_UM
SUBSTRATE_WIDTH_C_UM = 12000.0  # margin inside BORE_W_C_UM

SAPPHIRE_EPS_XX = 9.4
SAPPHIRE_EPS_YY = 9.4
SAPPHIRE_EPS_ZZ = 11.6
SAPPHIRE_ANISO_NAME = 'sapphire_aniso_oval'

W_MAIN = 70.0  # main through-line width

# Model B: P4's REAL current geometry (Rev7) - see module docstring
STALK_WIDTH_B_UM = 70.0
STALK_LENGTH_B_UM = 3137.0
FAN_ROUT_B_UM = 1229.0
FAN_RIN_B_UM = 88.39
FAN_ANGLE_B_DEG = 115.0
BRANCH_SIDES_B = [+1, -1]  # mirrored butterfly pair

# Model C: handoff's own explicit stub numbers - see module docstring
STALK_WIDTH_C_UM = 70.0
STALK_LENGTH_C_UM = 6030.0
BRANCH_SIDES_C = [+1]  # single-sided, no terminator

# Coarse-then-discrete zero-finding (acceptance checklist: "discrete
# windows, not interpolation smoothing"). START widened down to 0.5GHz
# (from an original 2.0GHz) - Model B's first live test found its only
# null at 11.55GHz, right at the edge of a 2-12GHz window and 2.4x above
# the real P4 design's own 4.752GHz target; widening down checks whether
# the true fundamental was hiding below the old 2GHz floor before trusting
# 11.55GHz as the answer.
COARSE_SWEEP_START_GHZ = 0.5
COARSE_SWEEP_STOP_GHZ = 12.0
COARSE_SWEEP_COUNT = 575  # keep ~20MHz resolution over the wider range
DISCRETE_WINDOW_HALF_GHZ = 0.3
DISCRETE_STEP_GHZ = 0.01


def _flush_attach_width(r_in, angle_deg):
    return 2 * r_in * math.sin(math.radians(angle_deg) / 2)


def fan_arc_points(tip, direction_deg, r_out, r_in, fan_angle_deg, attach_width):
    """Filter-agnostic fan-outline math, duplicated verbatim from
    verify_L60_hfss_export.py / filter_L60_HFSS.py (same formula, already
    verified there) - see those files' own docstrings for the derivation."""
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


def draw_fan_native(model, label, fan_params):
    """Verbatim from filter_L60_HFSS.py/filter_L60_package_HFSS.py - 2
    native arcs + 2 lines via a raw CreatePolyline call, already proven."""
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


def _stadium_profile_points_xz(bore_w_um, bore_h_um):
    """6 vertices (pt0..pt5) of a stadium cross-section in the LOCAL X-Z
    plane (major axis X, minor axis Z) - for a raw 4-segment
    Line/Arc/Line/Arc CreatePolyline, matching draw_fan_native's own
    2-arc-native-polyline convention. Same derivation as
    oval_bore_epseff_HFSS.py's own _stadium_profile_points() - duplicated,
    not imported (self-contained-file convention, and that file's version
    is pyaedt-flavored while this needs a bare point list for the raw COM
    call below)."""
    r = bore_h_um / 2.0
    flat_half_w = (bore_w_um - bore_h_um) / 2.0
    assert flat_half_w > 0, 'bore_h must be < bore_w for the stadium profile'
    return [
        (-flat_half_w, r), (flat_half_w, r), (flat_half_w + r, 0.0),
        (flat_half_w, -r), (-flat_half_w, -r), (-flat_half_w - r, 0.0),
    ]


def build_stadium_bore(model, bore_w_um, bore_h_um, bore_y0_um, bore_length_um, bore_z_center_um, name):
    """Stadium bore as a solid: 2D covered/closed profile (Line/Arc/Line/Arc,
    matching draw_fan_native's proven native-arc CreatePolyline pattern) in
    the local X-Z plane at Y=bore_y0_um, swept along +Y into a solid."""
    pts_local = _stadium_profile_points_xz(bore_w_um, bore_h_um)
    pointsStr = ['NAME:PolylinePoints']
    for x, z in pts_local:
        pointsStr.append(['NAME:PLPoint', 'X:=', um(x), 'Y:=', um(bore_y0_um), 'Z:=', um(bore_z_center_um + z)])
    segStr = ['NAME:PolylineSegments',
              ['NAME:PLSegment', 'SegmentType:=', 'Line', 'StartIndex:=', 0, 'NoOfPoints:=', 2],
              ['NAME:PLSegment', 'SegmentType:=', 'Arc', 'StartIndex:=', 1, 'NoOfPoints:=', 3],
              ['NAME:PLSegment', 'SegmentType:=', 'Line', 'StartIndex:=', 3, 'NoOfPoints:=', 2],
              ['NAME:PLSegment', 'SegmentType:=', 'Arc', 'StartIndex:=', 4, 'NoOfPoints:=', 3]]
    model._modeler.CreatePolyline(
        ['NAME:PolylineParameters', 'IsPolylineCovered:=', True, 'IsPolylineClosed:=', True,
         pointsStr, segStr],
        model._attributes_array(name=name, material='vacuum'))
    model.sweep_along_vector([name], ['0um', um(bore_length_um), '0um'])
    return name


# ===============================================================================
# branch/stub geometry - straight (unfolded) stalk + optional fan, T-junction
# overlap onto the main through-line (same hand-built-overlap convention as
# everywhere else in this repo)
# ===============================================================================

def build_branch_or_stub(model, layer_pieces, main_x0_um, branch_y_um, stalk_width_um, stalk_length_um,
                          side, fan_params=None, label_prefix=''):
    """Draws one branch/stub: a straight stalk from the main line's
    centerline (main_x0_um, branch_y_um) outward along +-X (side=+1/-1),
    then an optional fan (fan_params = (fan_rout, fan_rin, fan_angle_deg)
    or None for a plain open end, matching Model C's own "no terminator").
    Appends (name, kind, params) tuples to layer_pieces for the caller's
    own sweep_along_vector + unite loop."""
    direction_deg = 0 if side > 0 else 180
    x0 = main_x0_um
    x_tip = main_x0_um + side * stalk_length_um

    stalk_name = '%sStalk%s' % (label_prefix, 'P' if side > 0 else 'M')
    pts = [
        [um(x0), um(branch_y_um - stalk_width_um / 2), '0um'],
        [um(x_tip), um(branch_y_um - stalk_width_um / 2), '0um'],
        [um(x_tip), um(branch_y_um + stalk_width_um / 2), '0um'],
        [um(x0), um(branch_y_um + stalk_width_um / 2), '0um'],
    ]
    model.draw_polyline(pts, closed=True, name=stalk_name)
    layer_pieces.append(stalk_name)

    if fan_params is not None:
        fan_rout, fan_rin, fan_angle_deg = fan_params
        attach_width = _flush_attach_width(fan_rin, fan_angle_deg)
        fan_name = '%sFan%s' % (label_prefix, 'P' if side > 0 else 'M')
        fan_p = ((x_tip, branch_y_um), direction_deg, fan_rout, fan_rin, fan_angle_deg, attach_width)
        draw_fan_native(model, fan_name, fan_p)
        layer_pieces.append(fan_name)


def build_design(project, design_name, bore_h_um, model_kind, overwrite=True):
    """model_kind: 'B' (P4 branch, mirrored pair, real Rev7 geometry) or
    'C' (filter_BB-style stub, single-sided, handoff's own numbers)."""
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

    mat_name = SAPPHIRE_ANISO_NAME
    defmgr = project._project.GetDefinitionManager()
    if mat_name not in list(defmgr.GetProjectMaterialNames()):
        defmgr.AddMaterial([
            'NAME:' + mat_name,
            'CoordinateSystemType:=', 'Cartesian',
            'BulkOrSurfaceType:=', 1,
            ['NAME:PhysicsTypes', 'set:=', ['Electromagnetic']],
            ['NAME:permittivity', 'property_type:=', 'AnisoProperty', 'unit:=', '',
             'component1:=', '9.4', 'component2:=', '9.4', 'component3:=', '11.6'],
        ])

    bore_w_um = BORE_W_B_UM if model_kind == 'B' else BORE_W_C_UM
    substrate_width_um = SUBSTRATE_WIDTH_B_UM if model_kind == 'B' else SUBSTRATE_WIDTH_C_UM

    x0 = 0.0  # main line's transverse (X) centerline
    y0 = BORE_AXIAL_MARGIN_UM  # main line's own axial start
    branch_y = y0 + THROUGH_LINE_LENGTH_UM / 2.0
    bore_z_center = -SAPPHIRE_THICKNESS_UM / 2.0  # chip mid-thickness on the bore axis, Z=0 at chip top

    build_stadium_bore(model, bore_w_um, bore_h_um, 0.0, BORE_LENGTH_UM, bore_z_center, 'BoreVacuum')
    model.draw_box_corner(
        [(x0 - substrate_width_um / 2.0) * 1e-6, 0.0, -SAPPHIRE_THICKNESS_UM * 1e-6],
        [substrate_width_um * 1e-6, BORE_LENGTH_UM * 1e-6, SAPPHIRE_THICKNESS_UM * 1e-6],
        material=mat_name, name='Substrate',
    )
    model.assign_perfect_E(['BoreVacuum'], name='Package_Walls')

    metal_names = ['MainLine']
    model.draw_polyline(
        [[um(x0 - W_MAIN / 2), um(y0), '0um'], [um(x0 - W_MAIN / 2), um(y0 + THROUGH_LINE_LENGTH_UM), '0um'],
         [um(x0 + W_MAIN / 2), um(y0 + THROUGH_LINE_LENGTH_UM), '0um'], [um(x0 + W_MAIN / 2), um(y0), '0um']],
        closed=True, name='MainLine',
    )

    if model_kind == 'B':
        for side in BRANCH_SIDES_B:
            build_branch_or_stub(model, metal_names, x0, branch_y, STALK_WIDTH_B_UM, STALK_LENGTH_B_UM,
                                  side, fan_params=(FAN_ROUT_B_UM, FAN_RIN_B_UM, FAN_ANGLE_B_DEG), label_prefix='B_')
    else:
        for side in BRANCH_SIDES_C:
            build_branch_or_stub(model, metal_names, x0, branch_y, STALK_WIDTH_C_UM, STALK_LENGTH_C_UM,
                                  side, fan_params=None, label_prefix='C_')

    for name in metal_names:
        model.sweep_along_vector([name], ['0um', '0um', um(METAL_THICKNESS_UM)])
    metal_obj = model.unite(metal_names) if len(metal_names) > 1 else metal_names[0]
    model.assign_perfect_E([metal_obj], name='Filter_Metal')

    def make_port(name, y_pos):
        z_bot, z_top = 0.0, bore_z_center + bore_h_um / 2.0
        pos = [x0 - W_MAIN / 2, y_pos, z_bot]
        size = [W_MAIN, 0, z_top - z_bot]
        rect_name = model._modeler.CreateRectangle(
            ['NAME:RectangleParameters',
             'XStart:=', um(pos[0]), 'YStart:=', um(pos[1]), 'ZStart:=', um(pos[2]),
             'Width:=', um(size[2]), 'Height:=', um(size[0]), 'WhichAxis:=', 'Y'],
            ['NAME:Attributes', 'Name:=', name + '_face', 'Flags:=', '',
             'Color:=', '(132 132 193)', 'Transparency:=', 0.9,
             'PartCoordinateSystem:=', 'Global', 'UDMId:=', '',
             'MaterialValue:=', '"vacuum"', 'SolveInside:=', True])
        z_mid = METAL_THICKNESS_UM / 2.0
        start = [um(x0), um(y_pos), um(z_mid)]
        end = [um(x0), um(y_pos), um(z_top)]
        model._make_lumped_port(start, end, ['Objects:=', [rect_name]], z0=Z0_PORT, name=name)

    make_port('P1', y0)
    make_port('P2', y0 + THROUGH_LINE_LENGTH_UM)

    setup = design.create_dm_setup(
        freq_ghz=(COARSE_SWEEP_START_GHZ + COARSE_SWEEP_STOP_GHZ) / 2, name='S21_Setup',
        max_delta_s=0.02, max_passes=12, min_passes=3, min_converged=2, pct_refinement=30, basis_order=1,
    )
    coarse_sweep = setup.insert_sweep(
        start_ghz=COARSE_SWEEP_START_GHZ, stop_ghz=COARSE_SWEEP_STOP_GHZ, count=COARSE_SWEEP_COUNT,
        step_ghz=None, name='CoarseSweep', type='Interpolating',
    )
    project.save()
    return design, setup, coarse_sweep


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


def find_zero(project, setup, sweep, out_dir, design_name):
    """Coarse Interpolating sweep -> argmin(S21) -> discrete window around
    it -> refined argmin from the DISCRETE data only (acceptance
    checklist: "zero locations from discrete windows, not interpolation
    smoothing")."""
    report = sweep.create_report('Temp_S21_coarse', 'dB(S(P2,P1))')
    tmp_path = os.path.join(out_dir, '_tmp_%s_coarse.csv' % design_name)
    report.export_to_file(tmp_path)
    freqs, s21_db = np.loadtxt(tmp_path, skiprows=1, delimiter=',').transpose()
    os.remove(tmp_path)
    coarse_f0 = freqs[int(np.argmin(s21_db))]
    print('  coarse argmin(S21) @ %.3fGHz (%.2fdB)' % (coarse_f0, s21_db.min()))

    discrete_start = max(COARSE_SWEEP_START_GHZ, coarse_f0 - DISCRETE_WINDOW_HALF_GHZ)
    discrete_stop = min(COARSE_SWEEP_STOP_GHZ, coarse_f0 + DISCRETE_WINDOW_HALF_GHZ)
    # insert_sweep()'s own step_ghz path has a real bug (confirmed
    # empirically): it passes "RangeStep:=", step_ghz as a BARE float with
    # no unit suffix (unlike RangeStart/RangeEnd, which correctly get
    # "GHz" appended) - AEDT then interprets 0.01 as 0.01Hz, not 0.01GHz,
    # producing a ~60-BILLION-point sweep and failing with "can not have
    # over 25000 points". Worked around by using count= instead (that
    # code path IS unit-safe - RangeCount is dimensionless).
    discrete_count = int(round((discrete_stop - discrete_start) / DISCRETE_STEP_GHZ)) + 1
    discrete_sweep = setup.insert_sweep(
        start_ghz=discrete_start, stop_ghz=discrete_stop, count=discrete_count, step_ghz=None,
        name='DiscreteWindow', type='Discrete',
    )
    project.save()
    setup.analyze()
    report2 = discrete_sweep.create_report('Temp_S21_discrete', 'dB(S(P2,P1))')
    tmp_path2 = os.path.join(out_dir, '_tmp_%s_discrete.csv' % design_name)
    report2.export_to_file(tmp_path2)
    freqs2, s21_db2 = np.loadtxt(tmp_path2, skiprows=1, delimiter=',').transpose()
    os.remove(tmp_path2)
    f_zero = freqs2[int(np.argmin(s21_db2))]
    print('  refined (discrete) argmin(S21) @ %.4fGHz (%.2fdB)' % (f_zero, s21_db2.min()))
    return f_zero


def run_one(bore_h_um, model_kind):
    gap_um = bore_h_um / 2.0 - SAPPHIRE_THICKNESS_UM / 2.0
    design_name = 'Model%s_h%d' % (model_kind, round(bore_h_um))
    print('=' * 70)
    print('bore_h=%.1fum (gap=%.2fum) model=%s -> design=%r' % (bore_h_um, gap_um, model_kind, design_name))
    print('=' * 70)

    project = connect_project()
    design, setup, coarse_sweep = build_design(project, design_name, bore_h_um, model_kind)

    print('  Solving %s (coarse interpolating sweep)...' % design_name)
    # setup.analyze()'s own return value is NOT a reliable success signal
    # here (confirmed empirically: returned False for a solve whose own
    # message log showed "Interpolating frequency sweep complete.
    # Converged" / "Normal completion of simulation") - matching
    # filter_L60_package_HFSS.py's own established convention of not
    # checking it at all. A real failure surfaces naturally as an
    # exception from the report pull in find_zero() below instead.
    setup.analyze()

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HFSS')
    os.makedirs(out_dir, exist_ok=True)
    try:
        f_zero = find_zero(project, setup, coarse_sweep, out_dir, design_name)
    except Exception as e:
        print('  find_zero FAILED for %s: %r' % (design_name, e))
        try:
            app = HFSS.HfssApp()
            desktop = app.get_app_desktop()
            msgs = desktop._desktop.GetMessages(PROJECT_NAME, design_name, 0)
            for m in msgs:
                print('   ', m)
        except Exception as e2:
            print('  could not pull messages: %r' % e2)
        return None
    return dict(bore_h_um=bore_h_um, gap_um=gap_um, model=model_kind, f_zero_ghz=f_zero)


def _already_done(bore_h_um, model_kind, csv_path):
    if not os.path.exists(csv_path):
        return False
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if row['model'] == model_kind and abs(float(row['bore_h_um']) - bore_h_um) < 1.0:
                return True
    return False


def _append_csv(row, csv_path):
    file_exists = os.path.exists(csv_path)
    with open(csv_path, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['bore_h_um', 'gap_um', 'model', 'f_zero_ghz'])
        writer.writerow([row['bore_h_um'], row['gap_um'], row['model'], row['f_zero_ghz']])


if __name__ == '__main__':
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HFSS')
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, 'oval_branch_stub_raw.csv')

    for model_kind in ('B', 'C'):
        for bore_h_um in BORE_H_TO_RUN_UM:
            if _already_done(bore_h_um, model_kind, csv_path):
                print('model=%s bore_h=%.1fum already done - skipping.' % (model_kind, bore_h_um))
                continue
            res = run_one(bore_h_um, model_kind)
            if res is not None:
                _append_csv(res, csv_path)
                print('Appended -> %s' % csv_path)

    print()
    print('=' * 70)
    print('DONE. Raw data -> %s' % csv_path)
    print('=' * 70)
