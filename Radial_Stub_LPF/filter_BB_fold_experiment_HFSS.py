#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 17 B2: controlled fold-geometry experiment on ONE stub, isolated on a
through-line in the real bore. Tests the fold-cancellation hypothesis: in a
groundless bore the field around a 70um trace extends millimetres, so a 400um
meander gap could make adjacent antiparallel runs cancel and destroy the
quarter-wave resonance past some fold depth.

WHY THIS IS RUN AS AN ISOLATION TEST, AND WHY V-FOLD-CURRENT GOES FIRST:
the Rev 17 handoff's own premise ("S1 and S7 fail because they're the two
LONGEST stubs, hence deepest-folded") does NOT hold against the live drawn
geometry - ranked by actual realized centerline length, the two failures are
the 2nd and 4th longest, interleaved with successes, and S2 (the LONGEST stub
in the design, same n_par_runs=3 as S1) notches correctly at 4.760GHz.
Nothing in {length, fold count, fan presence} separates the failures from the
successes. What DOES separate them: S1 is the FIRST stub in the array and S7
is the LAST (tee y=30000 and y=15000 - the handoff's claim that S7 "sits
mid-structure" is incorrect, it was appended below S6), so both failures are
END stubs - a cascade/position mechanism, not a fold mechanism.

Hence the ordering here: a SINGLE V-fold-current stub, alone on a matched
through-line, at S1's retargeted 4.5GHz length. If it notches cleanly, fold
cancellation is refuted outright (the geometry works fine in isolation) and
the mechanism must be cascade-level - one cheap solve kills the hypothesis and
the other three variants become unnecessary. Only if it FAILS in isolation is
the fold matrix worth running.

VARIANTS - all at an IDENTICAL total centerline length (STUB_TOTAL_LEN_UM),
so fold geometry is the only variable:
  V-fold-current : d_perp 1000, 3 parallel runs, run_gap 400um (S1's present
                   serpentine)
  V-fold-wide    : d_perp 1000, 2 parallel runs, run_gap 1000um (tests whether
                   opening the gap alone suffices)
  V-L            : one 90deg bend - 2500um perpendicular standoff, then the
                   remainder axial alongside the main line (orthogonal
                   segments don't cancel)
  V-straight     : perpendicular, no folds. REQUIRES A WIDENED BORE and is
                   therefore NOT numerically comparable to the others - see
                   BORE FEASIBILITY below. Supplementary control only.

BORE FEASIBILITY (checked by arithmetic, not assumed): the real bore is radius
3500um and the main line sits on its axis, so maximum perpendicular reach is
~3500um. V-fold-current (~1940um), V-fold-wide (~2070um) and V-L (~2735um) all
fit the REAL bore. V-straight at 6988um perpendicular overshoots it by ~3.5mm
and cannot be built in this package at all. Running it needs a widened bore,
and this repo has already MEASURED that bore width is not a benign knob:
oval_bore_branch_stub_HFSS.py's own docstring records an oversized bore (14mm
vs the real ~7mm) moving a stub's null to ~11.6GHz against a 4.752GHz target -
a 2.4x distortion - which is exactly why the bore widths there were tightened
to the minimum that fits. So V-straight's absolute frequency is not
comparable to the real-bore variants; it can only answer the qualitative
question "does an unfolded stub of this length resonate at all".

HARNESS: follows oval_bore_branch_stub_HFSS.py's proven single-branch-on-a-
through-line pattern (through-line along +Y, stub tee'd at mid-length, lumped
ports at both ends, PerfectE everywhere, anisotropic sapphire, no radiation
boundaries) but uses a CYLINDRICAL bore (the real package shape, per
filter_BB_firstlight_HFSS.py/filter_BB_S1_diagnostics_HFSS.py) rather than
that file's stadium profile, since the oval study's stadium was specific to
its own aspect-ratio sweep. Geometry helpers (bend_arc_points, draw_bend_native
pattern) are reused from the existing files rather than re-derived.

RUN VIA THE SEPARATE PYEPR ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe filter_BB_fold_experiment_HFSS.py
Run from THIS file's own directory.
"""
import csv
import math
import os
import sys

import numpy as np
from pyEPR import ansys as HFSS

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from verify_filter_BB_hfss_export import bend_arc_points  # noqa: E402
from filter_L30_hfss_geometry import (  # noqa: E402
    SAPPHIRE_THICKNESS_UM, METAL_THICKNESS_UM, um,
)
from filter_BB_firstlight_HFSS import find_all_notches  # noqa: E402

RUN_ANALYSIS = True

# Rev 17 Step 1: V-fold-current ran first and DID NOT notch at 4.5GHz - its
# only null sits at 6.830GHz, i.e. 1.518x its own bare quarter-wave frequency
# (k_eff = 4.500/6.830 = 0.659). So the fold penalty is REAL and confirmed in
# isolation, where no cascade effect can be responsible - but note the
# resonance does NOT "cease to exist" as the Rev 17 handoff's stated mechanism
# predicted; it SHIFTS UP by ~52%. Independent corroboration: applying that
# same k_eff to S2 (the design's only other 3-run fold, drawn 9776.09um)
# predicts 4.882GHz against its real measured 4.760GHz - agreement to 2.5%.
# That also explains S1's "missing" notch: at v2 (8610.10um, 3-run) k_eff puts
# its real resonance near 5.54GHz, which is OUTSIDE the dashboard's own
# +-30%-of-target search window around 4.2GHz ([2.94, 5.46]) - and the v2+S7
# solve did have unexplained deep nulls at 5.815/5.845GHz, one of which
# vanished under Track A's +3% S1 lengthening. Nothing was ever missing; the
# search window could not see it.
# Now running the remaining variants to find which geometry gives k_eff ~ 1.
VARIANTS_TO_RUN = ['V-L', 'V-fold-wide', 'V-straight']

PROJECT_NAME = 'filter_BB_fold_experiment'

# S1's retargeted length (Rev 17 D2): 4.5GHz, unterminated, so the bare
# quarter-wave length applies with no fan correction.
# 2.998e5/(4*4.5*sqrt(5.681)) = 6987.7um
EPS_EFF = 5.681
STUB_TARGET_GHZ = 4.5
STUB_TOTAL_LEN_UM = 2.998e5 / (4 * STUB_TARGET_GHZ * math.sqrt(EPS_EFF))

W_MAIN = 70.0
W_STUB = 70.0

REAL_BORE_DIAMETER_UM = 7000.0
# V-straight only - must clear 6988um of perpendicular reach plus margin.
WIDE_BORE_DIAMETER_UM = 16000.0

THROUGH_LINE_LENGTH_UM = 12000.0
BORE_AXIAL_MARGIN_UM = 3000.0
SUBSTRATE_WIDTH_FRAC = 0.985  # substrate slightly narrower than the bore, same as the real chip-in-bore convention

SAPPHIRE_ANISO_NAME = 'sapphire_aniso_foldexp'
Z0_PORT = '70ohm'
_UM_TO_M = 1e-6
METAL_MESH_MAX_LENGTH_UM = 35.0

COARSE_START_GHZ = 0.5
COARSE_STOP_GHZ = 14.0
COARSE_COUNT = 2701
DISCRETE_START_GHZ = 3.5
DISCRETE_STOP_GHZ = 5.5
DISCRETE_STEP_GHZ = 0.01
DISCRETE_COUNT = int(round((DISCRETE_STOP_GHZ - DISCRETE_START_GHZ) / DISCRETE_STEP_GHZ)) + 1
ADAPTIVE_FREQ_GHZ = 4.5  # solve the mesh at the frequency of interest

OUT_DIR = os.path.join(os.path.dirname(__file__), 'HFSS')


# ===============================================================================
# per-variant stub geometry - all at STUB_TOTAL_LEN_UM total centerline length
# ===============================================================================

def variant_spec(name):
    """Returns a dict describing one variant's geometry, with every derived
    length computed so the TOTAL centerline length equals STUB_TOTAL_LEN_UM
    exactly (asserted below, not assumed)."""
    L = STUB_TOTAL_LEN_UM
    if name == 'V-fold-current':
        d_perp, n_par_runs, run_gap = 1000.0, 3, 400.0
    elif name == 'V-fold-wide':
        d_perp, n_par_runs, run_gap = 1000.0, 2, 1000.0
    elif name == 'V-L':
        # one 90deg bend: 2500um perpendicular standoff, remainder axial
        bend_radius = (400.0 + W_STUB) / 2.0
        arc = math.pi * bend_radius / 2.0
        d_perp = 2500.0
        axial = L - d_perp - arc
        assert axial > 0, 'V-L axial run came out negative'
        return dict(name=name, kind='L', d_perp=d_perp, axial=axial,
                     bend_radius=bend_radius, bore_diameter_um=REAL_BORE_DIAMETER_UM,
                     total_check=d_perp + arc + axial,
                     transverse_reach=d_perp + bend_radius)
    elif name == 'V-straight':
        return dict(name=name, kind='straight', d_perp=L,
                     bore_diameter_um=WIDE_BORE_DIAMETER_UM,
                     total_check=L, transverse_reach=L)
    else:
        raise ValueError('unknown variant %r' % name)

    return fold_spec(name, L, d_perp, n_par_runs, run_gap)


def fold_spec(name, total_len_um, d_perp, n_par_runs, run_gap):
    """The fold arithmetic, factored out so other experiments can reuse it
    rather than re-deriving it. Rev 20 B2 (the split-pair gap sweep) calls
    this directly - DESIGN_NOTES sec 12's standing lesson is that a
    re-implemented build loop drifts silently, so there is one copy."""
    bend_radius = (run_gap + W_STUB) / 2.0
    n_bends = n_par_runs - 1
    # entrance 90deg turn + n_bends internal 180deg turns, no exit turn -
    # identical formula to filter_BB.py's own folded_stub()
    turn_arc_len = math.pi * bend_radius * (n_bends + 0.5)
    run_length = (total_len_um - d_perp - turn_arc_len) / n_par_runs
    assert run_length > 0, '%s: run_length came out negative' % name
    return dict(name=name, kind='fold', d_perp=d_perp, n_par_runs=n_par_runs,
                 run_gap=run_gap, bend_radius=bend_radius, run_length=run_length,
                 bore_diameter_um=REAL_BORE_DIAMETER_UM,
                 total_check=d_perp + turn_arc_len + n_par_runs * run_length,
                 transverse_reach=d_perp + (n_par_runs - 1) * (run_gap + W_STUB) + W_STUB)


def _rect_pts(start, direction_deg, length, w):
    d = math.radians(direction_deg)
    fwd = (math.cos(d), math.sin(d))
    perp = (math.cos(d + math.pi / 2), math.sin(d + math.pi / 2))
    end = (start[0] + length * fwd[0], start[1] + length * fwd[1])
    return [
        (start[0] + (w / 2) * perp[0], start[1] + (w / 2) * perp[1]),
        (end[0] + (w / 2) * perp[0], end[1] + (w / 2) * perp[1]),
        (end[0] - (w / 2) * perp[0], end[1] - (w / 2) * perp[1]),
        (start[0] - (w / 2) * perp[0], start[1] - (w / 2) * perp[1]),
    ], end


def _bend_advance(pos, direction_deg, angle_deg, CCW, radius):
    angle = math.radians(angle_deg)
    d = math.radians(direction_deg)
    local_dx = radius * math.sin(angle)
    local_dy = (1 if CCW else -1) * radius * (math.cos(angle) - 1)
    fwd = (math.cos(d), math.sin(d))
    perp = (math.cos(d + math.pi / 2), math.sin(d + math.pi / 2))
    return ((pos[0] + local_dx * fwd[0] + local_dy * perp[0],
             pos[1] + local_dx * fwd[1] + local_dy * perp[1]),
            direction_deg - angle_deg if CCW else direction_deg + angle_deg)


def draw_bend_native(model, label, bend_arc_params):
    """Native-arc bend polyline - same recipe as
    filter_BB_S1_diagnostics_HFSS.py's own draw_bend_native()."""
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
    return model._modeler.CreatePolyline(
        ['NAME:PolylineParameters', 'IsPolylineCovered:=', True, 'IsPolylineClosed:=', True,
         pointsStr, segStr],
        model._attributes_array(name=label))


def build_stub(model, spec, tee_pos, metal_names):
    """Draws one variant's stub off tee_pos, branching toward +X (direction 0).
    Mirrors filter_BB.py's folded_stub() turn schedule exactly for the fold
    variants (entrance 90deg, then alternating 180deg bends, no exit turn)."""
    pos, direction = tee_pos, 0.0
    i = 0

    if spec['kind'] == 'straight':
        pts, _end = _rect_pts(pos, direction, spec['d_perp'], W_STUB)
        model.draw_polyline([[um(x), um(y), '0um'] for x, y in pts], closed=True, name='Stub_straight')
        metal_names.append('Stub_straight')
        return

    if spec['kind'] == 'L':
        pts, pos = _rect_pts(pos, direction, spec['d_perp'], W_STUB)
        model.draw_polyline([[um(x), um(y), '0um'] for x, y in pts], closed=True, name='Stub_perp')
        metal_names.append('Stub_perp')
        # turn toward +Y (axial, alongside the main line)
        arc_params = (pos, direction, 90.0, True, W_STUB, spec['bend_radius'])
        metal_names.append(str(draw_bend_native(model, 'Stub_bend', arc_params)))
        pos, direction = _bend_advance(pos, direction, 90.0, True, spec['bend_radius'])
        pts, pos = _rect_pts(pos, direction, spec['axial'], W_STUB)
        model.draw_polyline([[um(x), um(y), '0um'] for x, y in pts], closed=True, name='Stub_axial')
        metal_names.append('Stub_axial')
        return

    # fold variants
    pts, pos = _rect_pts(pos, direction, spec['d_perp'], W_STUB)
    model.draw_polyline([[um(x), um(y), '0um'] for x, y in pts], closed=True, name='Stub_exit')
    metal_names.append('Stub_exit')

    turn_CCW = True
    arc_params = (pos, direction, 90.0, turn_CCW, W_STUB, spec['bend_radius'])
    metal_names.append(str(draw_bend_native(model, 'Stub_entrance', arc_params)))
    pos, direction = _bend_advance(pos, direction, 90.0, turn_CCW, spec['bend_radius'])

    pts, pos = _rect_pts(pos, direction, spec['run_length'], W_STUB)
    model.draw_polyline([[um(x), um(y), '0um'] for x, y in pts], closed=True, name='Stub_run1')
    metal_names.append('Stub_run1')

    for i in range(spec['n_par_runs'] - 1):
        turn_CCW = not turn_CCW
        arc_params = (pos, direction, 180.0, turn_CCW, W_STUB, spec['bend_radius'])
        metal_names.append(str(draw_bend_native(model, 'Stub_bend%d' % (i + 1), arc_params)))
        pos, direction = _bend_advance(pos, direction, 180.0, turn_CCW, spec['bend_radius'])
        pts, pos = _rect_pts(pos, direction, spec['run_length'], W_STUB)
        model.draw_polyline([[um(x), um(y), '0um'] for x, y in pts], closed=True,
                             name='Stub_run%d' % (i + 2))
        metal_names.append('Stub_run%d' % (i + 2))


def ensure_sapphire(project):
    defmgr = project._project.GetDefinitionManager()
    if SAPPHIRE_ANISO_NAME in list(defmgr.GetProjectMaterialNames()):
        return
    defmgr.AddMaterial([
        'NAME:' + SAPPHIRE_ANISO_NAME, 'CoordinateSystemType:=', 'Cartesian',
        'BulkOrSurfaceType:=', 1,
        ['NAME:PhysicsTypes', 'set:=', ['Electromagnetic']],
        ['NAME:permittivity', 'property_type:=', 'AnisoProperty', 'unit:=', '',
         'component1:=', '9.4', 'component2:=', '9.4', 'component3:=', '11.6'],
    ])


def build_design(project, design_name, spec):
    existing = [d.name for d in project.get_designs()]
    if design_name in existing:
        project._project.DeleteDesign(design_name)
        project.save()
    design = project.new_dm_design(design_name)
    model = design.modeler
    model.set_units('um')
    ensure_sapphire(project)

    bore_r = spec['bore_diameter_um'] / 2.0
    bore_len = THROUGH_LINE_LENGTH_UM + 2 * BORE_AXIAL_MARGIN_UM
    bore_z = -SAPPHIRE_THICKNESS_UM / 2.0
    x0, y0 = 0.0, BORE_AXIAL_MARGIN_UM
    tee_y = y0 + THROUGH_LINE_LENGTH_UM / 2.0

    # feasibility guard - a real check, not an assumption (see module docstring)
    clearance = bore_r - spec['transverse_reach']
    assert clearance > 300.0, (
        '%s: transverse reach %.1fum leaves only %.1fum to the %.0fum-diameter bore wall - '
        'this variant does NOT fit; widen the bore for it explicitly (and note the '
        'non-comparability caveat) rather than silently clipping geometry.'
        % (spec['name'], spec['transverse_reach'], clearance, spec['bore_diameter_um']))

    model._modeler.CreateCylinder(
        ['NAME:CylinderParameters', 'XCenter:=', um(x0), 'YCenter:=', um(0.0), 'ZCenter:=', um(bore_z),
         'Radius:=', um(bore_r), 'Height:=', um(bore_len), 'WhichAxis:=', 'Y', 'NumSides:=', 0],
        model._attributes_array(name='BoreVacuum', material='vacuum'))
    sub_w = spec['bore_diameter_um'] * SUBSTRATE_WIDTH_FRAC
    model.draw_box_corner(
        [(x0 - sub_w / 2) * _UM_TO_M, 0.0, -SAPPHIRE_THICKNESS_UM * _UM_TO_M],
        [sub_w * _UM_TO_M, bore_len * _UM_TO_M, SAPPHIRE_THICKNESS_UM * _UM_TO_M],
        material=SAPPHIRE_ANISO_NAME, name='Substrate')
    model.assign_perfect_E(['BoreVacuum'], name='Package_Walls')

    metal_names = ['MainLine']
    model.draw_polyline(
        [[um(x0 - W_MAIN / 2), um(y0), '0um'], [um(x0 - W_MAIN / 2), um(y0 + THROUGH_LINE_LENGTH_UM), '0um'],
         [um(x0 + W_MAIN / 2), um(y0 + THROUGH_LINE_LENGTH_UM), '0um'], [um(x0 + W_MAIN / 2), um(y0), '0um']],
        closed=True, name='MainLine')
    build_stub(model, spec, (x0, tee_y), metal_names)

    for name in metal_names:
        model.sweep_along_vector([name], ['0um', '0um', um(METAL_THICKNESS_UM)])
    metal_obj = model.unite(metal_names)
    model.assign_perfect_E([metal_obj], name='Filter_Metal')
    model.mesh_length('MetalMesh', [metal_obj], MaxLength='%fum' % METAL_MESH_MAX_LENGTH_UM)

    def make_port(name, y_pos):
        z_bot, z_top = 0.0, bore_z + bore_r
        rect = model._modeler.CreateRectangle(
            ['NAME:RectangleParameters', 'XStart:=', um(x0 - W_MAIN / 2), 'YStart:=', um(y_pos),
             'ZStart:=', um(z_bot), 'Width:=', um(z_top - z_bot), 'Height:=', um(W_MAIN),
             'WhichAxis:=', 'Y'],
            ['NAME:Attributes', 'Name:=', name + '_face', 'Flags:=', '', 'Color:=', '(132 132 193)',
             'Transparency:=', 0.9, 'PartCoordinateSystem:=', 'Global', 'UDMId:=', '',
             'MaterialValue:=', '"vacuum"', 'SolveInside:=', True])
        model._make_lumped_port([um(x0), um(y_pos), um(METAL_THICKNESS_UM / 2)],
                                 [um(x0), um(y_pos), um(z_top)],
                                 ['Objects:=', [rect]], z0=Z0_PORT, name=name)

    make_port('P1', y0)
    make_port('P2', y0 + THROUGH_LINE_LENGTH_UM)

    print('  bore dia=%.0fum, transverse reach=%.1fum, wall clearance=%.1fum'
          % (spec['bore_diameter_um'], spec['transverse_reach'], clearance))
    print('  boundaries: %s' % list(design._boundaries.GetBoundaries()))
    print('  excitations: %s' % list(design._boundaries.GetExcitations()))

    setup = design.create_dm_setup(
        freq_ghz=ADAPTIVE_FREQ_GHZ, name='FoldExp_Setup', max_delta_s=0.02, max_passes=12,
        min_passes=3, min_converged=2, pct_refinement=30, basis_order=1)
    coarse = setup.insert_sweep(start_ghz=COARSE_START_GHZ, stop_ghz=COARSE_STOP_GHZ,
                                 count=COARSE_COUNT, step_ghz=None, name='Coarse', type='Interpolating')
    discrete = setup.insert_sweep(start_ghz=DISCRETE_START_GHZ, stop_ghz=DISCRETE_STOP_GHZ,
                                   count=DISCRETE_COUNT, step_ghz=None, name='Discrete', type='Discrete')
    project.save()
    return design, setup, coarse, discrete


def _pull(sweep, label):
    report = sweep.create_report('Temp_%s' % label, 'dB(S(P2,P1))')
    tmp = os.path.join(OUT_DIR, '_tmp_fold_%s.csv' % label)
    report.export_to_file(tmp)
    f, v = np.loadtxt(tmp, skiprows=1, delimiter=',').transpose()
    os.remove(tmp)
    return f, v


def minus3db_width(freqs, vals, f0):
    """-3dB width relative to the LOCAL baseline (mean over +-0.25..0.5GHz,
    excluding the notch itself) - same convention used for the Rev 15/16
    bandwidth comparisons, so numbers stay comparable."""
    base_mask = (((freqs >= f0 - 0.5) & (freqs <= f0 - 0.25)) |
                 ((freqs >= f0 + 0.25) & (freqs <= f0 + 0.5)))
    if not np.any(base_mask):
        return None, None, None
    baseline = float(np.mean(vals[base_mask]))
    thresh = baseline - 3.0
    ci = int(np.argmin(np.abs(freqs - f0)))
    lo, hi = ci, ci
    while lo > 0 and vals[lo] <= thresh:
        lo -= 1
    while hi < len(freqs) - 1 and vals[hi] <= thresh:
        hi += 1
    return freqs[hi] - freqs[lo], freqs[lo], freqs[hi]


def connect_project():
    full_path = os.path.join(os.getcwd(), PROJECT_NAME + '.aedt')
    desktop = HFSS.HfssApp().get_app_desktop()
    existing = [p for p in desktop.get_projects() if p.name == PROJECT_NAME]
    if existing:
        project = existing[0]
        project.make_active()
        return project
    try:
        project = desktop.open_project(full_path)
        project.make_active()
    except Exception:
        project = desktop.new_project()
        project.save(full_path)
    return project


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    project = connect_project()
    print('=' * 70)
    print('Rev 17 B2 fold experiment - single stub, total centerline length %.1fum (%.2fGHz bare)'
          % (STUB_TOTAL_LEN_UM, STUB_TARGET_GHZ))
    print('=' * 70)

    rows = []
    for vname in VARIANTS_TO_RUN:
        spec = variant_spec(vname)
        assert abs(spec['total_check'] - STUB_TOTAL_LEN_UM) < 1e-6, \
            '%s total length %.6f != %.6f' % (vname, spec['total_check'], STUB_TOTAL_LEN_UM)
        print('--- %s ---' % vname)
        print('  spec: %s' % {k: (round(v, 2) if isinstance(v, float) else v)
                               for k, v in spec.items() if k != 'name'})
        design_name = 'Fold_' + vname.replace('-', '_')
        design, setup, coarse, discrete = build_design(project, design_name, spec)
        if not RUN_ANALYSIS:
            print('  RUN_ANALYSIS=False - built only.')
            continue
        setup.analyze()
        f_c, v_c = _pull(coarse, '%s_coarse' % design_name)
        f_d, v_d = _pull(discrete, '%s_discrete' % design_name)
        with open(os.path.join(OUT_DIR, 'foldexp_%s_S21.csv' % design_name), 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['freq_GHz', 'S21_dB', 'sweep'])
            w.writerows([(a, b, 'coarse') for a, b in zip(f_c, v_c)])
            w.writerows([(a, b, 'discrete') for a, b in zip(f_d, v_d)])

        nulls_all = find_all_notches(f_c, v_c)
        nulls_win = find_all_notches(f_d, v_d)
        in_band = [n for n in nulls_win if DISCRETE_START_GHZ <= n[0] <= DISCRETE_STOP_GHZ]
        print('  real nulls, full 0.5-14GHz coarse: %s'
              % ['%.3fGHz(%.1fdB)' % n for n in nulls_all])
        print('  real nulls in the 3.5-5.5GHz discrete window: %s'
              % ['%.3fGHz(%.1fdB)' % n for n in in_band])
        if in_band:
            f0, depth = min(in_band, key=lambda n: n[1])
            width, wlo, whi = minus3db_width(f_d, v_d, f0)
            delta = 100.0 * (f0 - STUB_TARGET_GHZ) / STUB_TARGET_GHZ
            print('  NOTCH PRESENT: %.4fGHz (%.1fdB), delta vs %.2fGHz target = %+.2f%%, '
                  '-3dB width=%s' % (f0, depth, STUB_TARGET_GHZ, delta,
                                      ('%.4fGHz (%.3f-%.3f)' % (width, wlo, whi)) if width else 'n/a'))
            rows.append(dict(variant=vname, notch='YES', f0_ghz=f0, depth_db=depth,
                              delta_pct=delta, width_ghz=width,
                              bore_diameter_um=spec['bore_diameter_um']))
        else:
            print('  NO NOTCH FOUND in 3.5-5.5GHz - this variant does NOT resonate in isolation.')
            rows.append(dict(variant=vname, notch='NO', f0_ghz=None, depth_db=None,
                              delta_pct=None, width_ghz=None,
                              bore_diameter_um=spec['bore_diameter_um']))

    if rows:
        out = os.path.join(OUT_DIR, 'foldexp_results.csv')
        with open(out, 'w', newline='') as fh:
            wr = csv.DictWriter(fh, fieldnames=['variant', 'notch', 'f0_ghz', 'depth_db',
                                                  'delta_pct', 'width_ghz', 'bore_diameter_um'])
            wr.writeheader()
            wr.writerows(rows)
        print('=' * 70)
        print('Results -> %s' % out)
        vfc = next((r for r in rows if r['variant'] == 'V-fold-current'), None)
        if vfc is not None:
            if vfc['notch'] == 'YES':
                print('VERDICT: V-fold-current NOTCHES in isolation (%.4fGHz, %.1fdB). Fold-cancellation '
                      'is REFUTED for this geometry - S1\'s failure in the full filter is NOT caused by '
                      'its fold geometry, so the mechanism is cascade-level (consistent with both '
                      'failures being END stubs). The other fold variants are unnecessary.'
                      % (vfc['f0_ghz'], vfc['depth_db']))
            else:
                print('VERDICT: V-fold-current does NOT notch even in isolation - fold-cancellation '
                      'remains viable. Run the remaining variants (set VARIANTS_TO_RUN to the full '
                      'list) to find which geometry restores the resonance.')
        print('=' * 70)


if __name__ == '__main__':
    main()
