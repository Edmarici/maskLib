#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 10 Stage A: protection-spectrum sim for filter_BB - extends the
regenerated filter_BB geometry (verify_filter_BB_hfss_export.py) with a
real pin coupler (Addition 1) and a SNAIL-side lumped port (Addition 2),
then solves for the actual acceptance-quality figures of merit: Re[Z_snail](f)
(what a protected mode sees looking out through pad->filter->pin->coax) and
coax->SNAIL |S21| (drive delivery), with and without the filter metal, plus
a pin-recess-depth parametric. See DESIGN_NOTES_snail_filter.md secs 2-3, 6,
9, 11-12 (O5) for the physics/requirement this sim answers.

NO PRE-EXISTING BASE MODEL: despite the handoff's framing ("extend the
EXISTING package/drive-chip HFSS model"), no bore+chip+filter_BB HFSS model
existed anywhere in this repo before this file - extract_epseff.py only
ever built a bare strip (no filter, no pin, no SNAIL port). This file
builds the whole package fresh, reusing verify_filter_BB_hfss_export.py's
geometry replay (itself new this session) the same way
filter_L60_package_HFSS.py reuses verify_L60_hfss_export.py's.

pyEPR/raw win32com, NOT pyaedt (unlike extract_epseff.py): that Rev 9
script's pyaedt choice was specifically for multi-mode wave-port eigenmode
post-processing (Gamma/Zo per mode) that pyEPR has no wrapper for at all.
This is a standard driven-modal 2-port S/Z-parameter extraction - exactly
what filter_L60_package_HFSS.py already does well - so this file reuses
that connection/staging boilerplate and its draw_fan_native/draw_bend_native
functions verbatim.

ANISOTROPIC SAPPHIRE VIA RAW COM: pyEPR (0.8, this environment) has no
material-definition wrapper either (checked source - same gap as its
missing wave-port wrapper, which filter_L30_HFSS.py's own make_wave_port()
already works around with a raw AssignWavePort COM call). ensure_
anisotropic_sapphire() below is the same idea applied to
oDefinitionManager.AddMaterial - the AnisoProperty array shape is standard
AEDT scripting syntax but UNEXERCISED via pyEPR/raw win32com in this repo
before now (only ever done via pyaedt, in extract_epseff.py) - verify_
anisotropic_sapphire() reads the definition back via GetData() immediately
after creation, same empirical-verification discipline extract_epseff.py's
own docstring describes for the identical tensor via a different library.
Check this printed readback on the FIRST real run before trusting anything
downstream.

TWO MODEL VARIANTS, ONE SCRIPT: build_design() takes include_filter_metal -
True draws the real regenerated filter_BB metal; False draws a single plain
bar (same width/axial-extent envelope) so port positions and main-line
continuity stay identical between variants (deliverable #3's own "differ
ONLY by filter metal" requirement) - not simply "delete the filter", which
would leave the ports referencing nothing.

Z_SNAIL PORT-INDEX CONVENTION - read before touching the post-processing:
the handoff's own formula is written "Z_snail = Z11 - Z12*Z21/(Z22+50), 50
on the COAX port" - i.e. in THEIR formula, index 1 = SNAIL (the probe) and
index 2 = coax (terminated). This file's own AEDT port NAMES follow this
whole repo's established convention instead (P1 = the input/pin side, P2 =
the output/SNAIL side - matching every other script in this family). So the
same physics, expressed in THIS file's own P1=coax/P2=SNAIL numbering, is
the mirror form: Z_snail = Z22 - Z12*Z21/(Z11+50). compute_z_snail() below
implements exactly that mirrored form - do not paste the handoff's formula
literally without swapping indices, that would silently terminate the wrong
port.

PIN COUPLER / SNAIL PAD DIMENSIONS ARE PROVISIONAL: tube_dia=2.5mm,
pin_dia=0.8mm, pin_recess=1.0mm (pending O1/O3 - real package drawing not
available); SNAIL-side facing pads are 500x500um placeholders with a 200um
gap (pending real SNAIL antenna pad dims - checked SNAIL/SNAIL.py and
SNAIL_Pump_Filter/SNAIL_Pump_Filter.py, neither has finalized pad geometry
either, only qubitLib.SNAIL()'s own default flag pads and a keep-out
placeholder box respectively) - both match the handoff's own explicit
fallback numbers. Flag in DESIGN_NOTES_snail_filter.md sec 11 as load-
bearing assumptions once real numbers exist.

CONVERGENCE AT STOPBAND FREQUENCIES: the handoff wants Re[Z_snail] tracked
across adaptive passes at 4.5/6.0/7.0GHz specifically (default delta-S is
not a reliable proxy this deep in the stopband, where Re[Z] sits orders
below Im[Z]). pyEPR's own get_convergence() exposes the standard per-pass
Max-Delta-S table (used here, and included in the run summary) but NOT
per-pass frequency-resolved Re[Z] - true per-pass Re[Z]-at-spot-frequency
tracking is NOT implemented this pass (flagged, not faked). Mitigated with
a tighter max_delta_s (0.005, vs the L60 package script's 0.02) and
min_converged_passes=3.

STAGING: RUN_ANALYSIS starts False (geometry + ports + losslessness audit
only) - confirm in AEDT (fresh COM connection, enumerate every same-named
project handle individually per CLAUDE.md's duplicate-AEDT-project lesson)
before spending real solve time. RUN_PINDEPTH_SWEEP starts False -
deliverable #4 is the first thing the handoff's own fallback framing says
to trim/defer if runtime bites; core deliverables are 1-3 (transfer + Re[Z],
filter-in and filter-out).

RUN VIA THE SEPARATE PYEPR ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe filter_BB_stageA_HFSS.py
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

from verify_filter_BB_hfss_export import (  # noqa: E402
    regenerate_metal_pieces_bb, fan_arc_points, bend_arc_points,
)
from filter_L30_hfss_geometry import (  # noqa: E402
    SAPPHIRE_THICKNESS_UM, METAL_THICKNESS_UM, Z0_PORT, um,
)

RUN_ANALYSIS = True
RUN_PINDEPTH_SWEEP = False
BUILD_FILTER_OUT_VARIANT = False  # flip on once the filter-in design is confirmed good

PROJECT_NAME = 'filter_BB_stageA'

BORE_AXIAL_MARGIN_UM = 5000.0
SAPPHIRE_WIDTH_UM = 6900.0  # matches filter_BB.py's own chip width

SWEEP_START_GHZ = 0.5
SWEEP_STOP_GHZ = 12.0
SWEEP_COUNT = 2301  # ~5MHz resolution, matches filter_L60_package_HFSS.py's own density

# --- pin coupler (Addition 1) - PROVISIONAL, see module docstring ---
TUBE_DIA_UM = 2500.0
PIN_DIA_UM = 800.0
TUBE_LENGTH_UM = 4000.0
PIN_RECESS_UM = 1000.0  # base-case default; the parametric sweep varies this

# --- SNAIL-side placeholder pads/port (Addition 2) - PROVISIONAL, see module docstring ---
SNAIL_GAP_UM = 200.0
SNAIL_PAD_UM = 500.0

# --- spot frequencies for the attenuation/convergence summary ---
SPOT_FREQS_REZ_GHZ = [4.5, 6.0, 7.0]
SPOT_FREQS_S21_GHZ = [1.0, 3.5]

SAPPHIRE_ANISO_NAME = 'sapphire_aniso_bb'
_UM_TO_M = 1e-6


def _load_geometry():
    geom = regenerate_metal_pieces_bb()
    print('Regenerated %d filter_BB metal piece(s) directly from filter_BB.py (no DXF/GDS round-trip)'
          % len(geom['pieces']))
    return geom


# ===============================================================================
# anisotropic sapphire (raw COM - pyEPR has no material-definition wrapper,
# see module docstring)
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
    """Empirical readback, NOT a rubber-stamp - see module docstring.
    IDefinitionManager has no GetData() (confirmed empirically - that
    method exists on other AEDT COM interfaces, not this one; dir()'d the
    live object this session, no method returns a plain data blob for a
    single material). DoesMaterialExist() is real and used as a minimal
    existence check; the ACTUAL tensor value is NOT re-verified
    automatically this pass (flagged, not faked) - confirm AnisoProperty
    9.4/9.4/11.6 by eye in the AEDT Materials editor before trusting a
    solve, same manual-check fallback the module docstring's convergence-
    tracking caveat already uses for a different unavailable API."""
    defmgr = project._project.GetDefinitionManager()
    exists = bool(defmgr.DoesMaterialExist(SAPPHIRE_ANISO_NAME))
    print('Material %r exists in project: %s (tensor value NOT auto-verified this pass - '
          'check AnisoProperty 9.4/9.4/11.6 by eye in AEDT\'s Materials editor)'
          % (SAPPHIRE_ANISO_NAME, exists))
    return exists


# ===============================================================================
# filter metal - draw_fan_native/draw_bend_native copied verbatim from
# filter_L60_package_HFSS.py (same native-arc CreatePolyline pattern)
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


def _safe_name(label):
    """AEDT object names allow only letters/numbers/underscores (confirmed
    empirically this session - 'Invalid part name' COM error on any of
    filter_BB's own '4.2GHz_...' stub labels; same general issue
    filter_L60_package_HFSS.py's own comment already flags for '+'/'-')."""
    return label.replace('.', 'p').replace('+', 'plus').replace('-', 'minus')


def build_filter_metal(model, geom):
    """Real filter_BB metal, united + assigned PerfectE. Returns the solid's
    name. DELIBERATELY left at vacuum bulk material (NOT reassigned to
    'aluminum', unlike filter_L60_package_HFSS.py's own S21-only script) -
    the losslessness audit's own "ONE dissipative element only: the 50ohm
    coax termination" requirement means a real, lossy bulk conductor here
    would silently contaminate Re[Z_snail] with a second loss channel.
    PerfectE alone (a boundary condition, not a bulk material) makes it
    electromagnetically perfect while staying genuinely lossless."""
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
    return metal_obj_name


def build_filter_out_bar(model, geom):
    """Filter-OUT variant (deliverable #3): a single plain bar spanning the
    SAME axial extent as the real filter's own bbox, at W_MAIN width - keeps
    port positions and main-line continuity identical to the filter-in
    variant, so the two models differ ONLY by the filter's own shaping
    metal (per the handoff's explicit requirement), not by a routing gap."""
    all_ys = [y for _label, hull, _kind, _ap in geom['pieces'] for x, y in hull]
    y0, y1 = min(all_ys), max(all_ys)
    x0 = geom['port1_pos'][0]
    w = geom['w_main']
    pts = [
        [um(x0 - w / 2), um(y0), '0um'], [um(x0 + w / 2), um(y0), '0um'],
        [um(x0 + w / 2), um(y1), '0um'], [um(x0 - w / 2), um(y1), '0um'],
    ]
    sheet = model.draw_polyline(pts, closed=True, name='FilterOutBar')
    model.sweep_along_vector([str(sheet)], ['0um', '0um', um(METAL_THICKNESS_UM)])
    model.assign_perfect_E([str(sheet)], name='FilterOutBar_PerfectE')
    return str(sheet)


# ===============================================================================
# package (bore + substrate) - same pattern as filter_L60_package_HFSS.py
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
# Addition 1: pin coupler - side tube + coax pin + wave port. See module
# docstring for the axis convention (bore axis=Y, pin tube axis=Z, both
# ports at chip-transverse-center so "straight up" is exact, same
# simplification filter_L60_package_HFSS.py's own lumped ports already use).
# ===============================================================================

def build_pin_coupler(model, pkg, tube_pos_y_um, pin_recess_um, port_name='P1'):
    x0 = pkg['bore_center_x']
    z_wall = pkg['bore_axis_z_um'] + pkg['bore_radius_um']
    tube_r = TUBE_DIA_UM / 2.0
    pin_r = PIN_DIA_UM / 2.0
    z_tube_top = z_wall + TUBE_LENGTH_UM
    z_pin_tip = z_wall - pin_recess_um  # recessed INTO the bore from the wall intersection plane

    tube_name = model._modeler.CreateCylinder(
        ['NAME:CylinderParameters',
         'XCenter:=', um(x0), 'YCenter:=', um(tube_pos_y_um), 'ZCenter:=', um(z_wall),
         'Radius:=', um(tube_r), 'Height:=', um(z_tube_top - z_wall), 'WhichAxis:=', 'Z', 'NumSides:=', 0],
        model._attributes_array(name='PinTube', material='vacuum'))

    pin_name = model._modeler.CreateCylinder(
        ['NAME:CylinderParameters',
         'XCenter:=', um(x0), 'YCenter:=', um(tube_pos_y_um), 'ZCenter:=', um(z_pin_tip),
         'Radius:=', um(pin_r), 'Height:=', um(z_tube_top - z_pin_tip), 'WhichAxis:=', 'Z', 'NumSides:=', 0],
        model._attributes_array(name='PinConductor', material='vacuum'))

    # PinConductor overlaps BOTH PinTube (its own vacuum interior) and
    # BoreVacuum (the pin's recessed portion sits below the tube/bore
    # intersection plane) - two independent solids occupying the same
    # space is invalid (confirmed empirically: "Parts PinConductor and
    # PinTube/BoreVacuum intersect"). Same fix as every other
    # vacuum-vs-conductor overlap in this repo (extract_epseff.py's own
    # BoreVacuum/Substrate subtract): carve the conductor's volume OUT of
    # each vacuum region, keeping the conductor itself as its own solid.
    model.subtract(pkg['bore_name'], [pin_name], keep_originals=True)
    model.subtract(tube_name, [pin_name], keep_originals=True)

    model.assign_perfect_E([pin_name], name='Pin_Conductor_PerfectE')

    # Mesh seed on the pin-tip-to-pad gap region - the port coupling funnels
    # entirely through this small volume, same discipline as junction-gap
    # mesh seeding elsewhere in this codebase (CLAUDE.md).
    model.mesh_length('PinGapMesh', [pin_name], MaxLength='%fum' % (pin_recess_um / 10.0))

    # Wave port on an INDEPENDENT circular sheet at the tube's outer end
    # (not the tube solid's own end face) - same convention
    # extract_epseff.py already used for its own bore-cross-section ports,
    # avoiding any post-boolean partial-face ambiguity.
    sheet_name = model._modeler.CreateCircle(
        ['NAME:CircleParameters', 'IsCovered:=', True,
         'XCenter:=', um(x0), 'YCenter:=', um(tube_pos_y_um), 'ZCenter:=', um(z_tube_top),
         'WhichAxis:=', 'Z', 'Radius:=', um(tube_r), 'NumSegments:=', '0'],
        model._attributes_array(name='PinPortSheet', material='vacuum'))
    # int() cast is required - GetFaceIDs' raw COM return type doesn't
    # marshal correctly into AssignWavePort's Faces:=[...] array otherwise
    # (confirmed empirically; matches filter_L30_HFSS.py's own
    # `face_ids = [int(f) for f in model.get_face_ids(...)]` precedent).
    face_id = int(model.get_face_ids(sheet_name)[0])

    # Both endpoints MUST lie ON the port face itself (a flat disk at
    # Z=z_tube_top) - confirmed empirically ("Both endpoints of port lines
    # must lie on the port"). Standard coax integration line: pin conductor's
    # own edge to the tube's outer wall, both at the port's own Z-plane,
    # along a radial direction (+X here).
    start = [um(x0 + pin_r), um(tube_pos_y_um), um(z_tube_top)]
    end = [um(x0 + tube_r), um(tube_pos_y_um), um(z_tube_top)]
    params = ['NAME:' + port_name,
              'Faces:=', [face_id],
              'NumModes:=', 1,
              'UseLineModeAlignment:=', False,
              'DoDeembed:=', False,
              'RenormalizeAllTerminals:=', True,
              ['NAME:Modes',
               ['NAME:Mode1', 'ModeNum:=', 1, 'UseIntLine:=', True,
                ['NAME:IntLine', 'Start:=', start, 'End:=', end],
                'AlignmentGroup:=', 0, 'CharImp:=', 'Zpi', 'RenormImp:=', Z0_PORT]],
              'ShowReporterFilter:=', False, 'ReporterFilter:=', [True]]
    model._boundaries.AssignWavePort(params)
    print('  pin coupler: tube_dia=%.0fum pin_dia=%.0fum pin_recess=%.0fum @ Y=%.1f -> wave port %s'
          % (TUBE_DIA_UM, PIN_DIA_UM, pin_recess_um, tube_pos_y_um, port_name))
    return port_name


# ===============================================================================
# Addition 2: SNAIL-side lumped port - placeholder facing pads + gap (see
# module docstring - no real SNAIL antenna pad dims exist anywhere in this
# repo yet).
# ===============================================================================

def build_snail_port(model, geom, port2_pos_um, port_name='P2'):
    x0, y_line_end = port2_pos_um
    w_main = geom['w_main']
    z_bot, z_top = 0.0, METAL_THICKNESS_UM

    # drive-side pad: continues the output line's own direction (-Y) from
    # where it stops
    pad_a = model.draw_polyline(
        [[um(x0 - SNAIL_PAD_UM / 2), um(y_line_end), '0um'], [um(x0 + SNAIL_PAD_UM / 2), um(y_line_end), '0um'],
         [um(x0 + SNAIL_PAD_UM / 2), um(y_line_end - SNAIL_PAD_UM), '0um'],
         [um(x0 - SNAIL_PAD_UM / 2), um(y_line_end - SNAIL_PAD_UM), '0um']],
        closed=True, name='DrivePad')
    model.sweep_along_vector([str(pad_a)], ['0um', '0um', um(METAL_THICKNESS_UM)])

    y_gap_far = y_line_end - SNAIL_PAD_UM - SNAIL_GAP_UM
    pad_b = model.draw_polyline(
        [[um(x0 - SNAIL_PAD_UM / 2), um(y_gap_far), '0um'], [um(x0 + SNAIL_PAD_UM / 2), um(y_gap_far), '0um'],
         [um(x0 + SNAIL_PAD_UM / 2), um(y_gap_far - SNAIL_PAD_UM), '0um'],
         [um(x0 - SNAIL_PAD_UM / 2), um(y_gap_far - SNAIL_PAD_UM), '0um']],
        closed=True, name='SnailDummyPad')
    model.sweep_along_vector([str(pad_b)], ['0um', '0um', um(METAL_THICKNESS_UM)])

    for name in (str(pad_a), str(pad_b)):
        model.assign_perfect_E([name], name=name + '_PerfectE')

    # Port face fills the REAL gap volume between the two facing pad edges:
    # a thin sheet at constant X=x0 (the pads' shared centerline), spanning
    # Y across the full gap length and Z across the metal thickness -
    # NOT a Y-normal cross-section (that shape doesn't have any Y-extent at
    # all, so an integration line spanning the gap in Y can never lie on
    # it - confirmed empirically, "Both endpoints of port lines must lie on
    # the port" - same conceptual bug the pin coupler's own integration
    # line had, fixed the same way: keep the line INSIDE the port's own
    # plane).
    y_gap_near = y_line_end - SNAIL_PAD_UM  # drive pad's own facing edge
    mid_z = (z_bot + z_top) / 2.0
    face_name = model._modeler.CreateRectangle(
        ['NAME:RectangleParameters',
         'XStart:=', um(x0), 'YStart:=', um(y_gap_far), 'ZStart:=', um(z_bot),
         'Width:=', um(y_gap_near - y_gap_far), 'Height:=', um(z_top - z_bot), 'WhichAxis:=', 'X'],
        ['NAME:Attributes', 'Name:=', port_name + '_face', 'Flags:=', '',
         'Color:=', '(132 132 193)', 'Transparency:=', 0.9,
         'PartCoordinateSystem:=', 'Global', 'UDMId:=', '',
         'MaterialValue:=', '"vacuum"', 'SolveInside:=', True])

    start = [um(x0), um(y_gap_near), um(mid_z)]
    end = [um(x0), um(y_gap_far), um(mid_z)]
    model._make_lumped_port(start, end, ['Objects:=', [face_name]], z0=Z0_PORT, name=port_name)
    print('  SNAIL port: placeholder pads %.0fx%.0fum, gap %.0fum @ Y~%.1f -> lumped port %s'
          % (SNAIL_PAD_UM, SNAIL_PAD_UM, SNAIL_GAP_UM, y_gap_far, port_name))
    return port_name


# ===============================================================================
# losslessness audit (mandatory per handoff) - the ONE dissipative element
# should be the 50ohm coax termination applied in post-processing, not
# anything in the model itself.
# ===============================================================================

def losslessness_audit(project, design):
    print('Losslessness audit:')
    ok_sapphire = verify_anisotropic_sapphire(project)
    boundary_names = list(design._boundaries.GetBoundaries())
    print('  boundaries defined: %s' % boundary_names)
    radiation_like = [b for b in boundary_names if 'rad' in b.lower() or 'absorb' in b.lower()]
    print('  radiation/absorbing boundaries found: %s (expect NONE)' % (radiation_like or 'none'))
    # Ports are EXCITATIONS, not boundaries, in AEDT's own object model
    # (confirmed empirically - GetBoundaries() alone doesn't list P1/P2 at
    # all) - checked separately here so a missing port doesn't slip past
    # this audit silently.
    excitations = list(design._boundaries.GetExcitations())
    print('  excitations (ports) defined: %s' % excitations)
    return dict(sapphire_ok=ok_sapphire, boundaries=boundary_names,
                radiation_like=radiation_like, excitations=excitations)


# ===============================================================================
# connection + one full design build (bore, substrate, filter metal or bar,
# pin coupler, SNAIL port, setup+sweep) - same attach-if-open pattern as
# filter_L60_package_HFSS.py (CLAUDE.md's duplicate-AEDT-project fix already
# applied there, reused verbatim here)
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


def build_design(project, design_name, geom, include_filter_metal=True,
                  pin_recess_um=PIN_RECESS_UM, overwrite=True):
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

    if include_filter_metal:
        build_filter_metal(model, geom)
    else:
        build_filter_out_bar(model, geom)

    pkg = build_package(model, geom)

    tube_pos_y_um = geom['port1_pos'][1] - geom['pin_pad_length'] / 2.0
    build_pin_coupler(model, pkg, tube_pos_y_um, pin_recess_um, port_name='P1')
    build_snail_port(model, geom, geom['port2_pos'], port_name='P2')

    audit = losslessness_audit(project, design)

    setup = design.create_dm_setup(
        freq_ghz=(SWEEP_START_GHZ + SWEEP_STOP_GHZ) / 2, name='StageA_Setup',
        max_delta_s=0.005, max_passes=15, min_passes=3, min_converged=3,
        pct_refinement=30, basis_order=1,
    )
    sweep = setup.insert_sweep(
        start_ghz=SWEEP_START_GHZ, stop_ghz=SWEEP_STOP_GHZ, count=SWEEP_COUNT,
        step_ghz=None, name='StageA_Sweep', type='Interpolating',
    )
    project.save()

    print('Design %r built (include_filter_metal=%s, pin_recess=%.0fum). Audit: %s'
          % (design_name, include_filter_metal, pin_recess_um, audit))
    return design, setup, sweep


# ===============================================================================
# post-processing: S/Z pull + Z_snail computation + CSV export
# ===============================================================================

def _pull(sweep, expr, label, out_dir):
    report = sweep.create_report('Temp_%s' % label, expr)
    tmp_path = os.path.join(out_dir, '_tmp_%s_export.csv' % label)
    report.export_to_file(tmp_path)
    freqs_, vals_ = np.loadtxt(tmp_path, skiprows=1, delimiter=',').transpose()
    os.remove(tmp_path)
    return freqs_, vals_


def compute_z_snail(z11_re, z11_im, z12_re, z12_im, z21_re, z21_im, z22_re, z22_im, z0=50.0):
    """P1=coax (terminated in z0), P2=SNAIL (probe) - per THIS file's own
    port numbering (see module docstring's Z_SNAIL PORT-INDEX CONVENTION
    section for why this is the mirror of the handoff's own literal
    formula, not a copy of it)."""
    z11 = z11_re + 1j * z11_im
    z12 = z12_re + 1j * z12_im
    z21 = z21_re + 1j * z21_im
    z22 = z22_re + 1j * z22_im
    z_snail = z22 - z12 * z21 / (z11 + z0)
    return z_snail.real, z_snail.imag


def pull_and_export(sweep, out_dir, suffix=''):
    """Pulls S21/S11 magnitude+phase and the full Z-matrix, computes
    Z_snail(f), writes stageA_transfer{suffix}.csv / stageA_ReZ{suffix}.csv.
    Returns (freqs, s21_db, re_z_snail, im_z_snail) for the summary."""
    freqs, s21_db = _pull(sweep, 'dB(S(P2,P1))', 'S21dB' + suffix, out_dir)
    _, s21_deg = _pull(sweep, 'ang_deg(S(P2,P1))', 'S21deg' + suffix, out_dir)
    _, s11_db = _pull(sweep, 'dB(S(P1,P1))', 'S11dB' + suffix, out_dir)

    _, z11_re = _pull(sweep, 're(Z(P1,P1))', 'Z11re' + suffix, out_dir)
    _, z11_im = _pull(sweep, 'im(Z(P1,P1))', 'Z11im' + suffix, out_dir)
    _, z12_re = _pull(sweep, 're(Z(P1,P2))', 'Z12re' + suffix, out_dir)
    _, z12_im = _pull(sweep, 'im(Z(P1,P2))', 'Z12im' + suffix, out_dir)
    _, z21_re = _pull(sweep, 're(Z(P2,P1))', 'Z21re' + suffix, out_dir)
    _, z21_im = _pull(sweep, 'im(Z(P2,P1))', 'Z21im' + suffix, out_dir)
    _, z22_re = _pull(sweep, 're(Z(P2,P2))', 'Z22re' + suffix, out_dir)
    _, z22_im = _pull(sweep, 'im(Z(P2,P2))', 'Z22im' + suffix, out_dir)

    re_z_snail, im_z_snail = [], []
    for i in range(len(freqs)):
        re_, im_ = compute_z_snail(z11_re[i], z11_im[i], z12_re[i], z12_im[i],
                                    z21_re[i], z21_im[i], z22_re[i], z22_im[i])
        re_z_snail.append(re_)
        im_z_snail.append(im_)

    transfer_path = os.path.join(out_dir, 'stageA_transfer%s.csv' % suffix)
    with open(transfer_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_GHz', 'S21_dB', 'S21_deg', 'S11_dB'])
        writer.writerows(zip(freqs, s21_db, s21_deg, s11_db))
    print('Transfer data saved -> %s' % transfer_path)

    rez_path = os.path.join(out_dir, 'stageA_ReZ%s.csv' % suffix)
    with open(rez_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_GHz', 'Re_Z_snail_ohm', 'Im_Z_snail_ohm'])
        writer.writerows(zip(freqs, re_z_snail, im_z_snail))
    print('Re[Z_snail] data saved -> %s' % rez_path)

    return np.asarray(freqs), np.asarray(s21_db), np.asarray(re_z_snail), np.asarray(im_z_snail)


def _nearest(freqs, target):
    idx = int(np.argmin(np.abs(freqs - target)))
    return idx


def summarize(freqs_in, s21_in, rez_in, freqs_out, s21_out, rez_out, out_dir):
    lines = []
    lines.append('=' * 70)
    lines.append('Stage A summary: filter-in vs filter-out')
    lines.append('=' * 70)
    for f in SPOT_FREQS_REZ_GHZ:
        i_in, i_out = _nearest(freqs_in, f), _nearest(freqs_out, f)
        atten_db = 10 * math.log10(max(rez_out[i_out], 1e-12) / max(rez_in[i_in], 1e-12))
        lines.append('  %.1fGHz: Re[Z_snail] filter-in=%.4g ohm, filter-out=%.4g ohm, '
                      'realized attenuation=%.1f dB' % (f, rez_in[i_in], rez_out[i_out], atten_db))
    lines.append('-' * 70)
    for f in SPOT_FREQS_S21_GHZ:
        i = _nearest(freqs_in, f)
        lines.append('  |S21| @ %.1fGHz (filter-in, drive delivery): %.2f dB' % (f, s21_in[i]))
    tilt = s21_in[_nearest(freqs_in, 3.5)] - s21_in[_nearest(freqs_in, 0.5)]
    lines.append('  passband tilt (3.5GHz - 0.5GHz): %.2f dB' % tilt)
    lines.append('=' * 70)
    text = '\n'.join(lines)
    print(text)
    with open(os.path.join(out_dir, 'stageA_summary.txt'), 'w') as f:
        f.write(text + '\n')


# ===============================================================================
# main
# ===============================================================================

def main():
    project = connect_project()
    geom = _load_geometry()
    out_dir = os.path.join(os.path.dirname(__file__), 'HFSS')
    os.makedirs(out_dir, exist_ok=True)

    design_in, setup_in, sweep_in = build_design(
        project, 'StageA_FilterIn', geom, include_filter_metal=True)

    design_out = setup_out = sweep_out = None
    if BUILD_FILTER_OUT_VARIANT:
        design_out, setup_out, sweep_out = build_design(
            project, 'StageA_FilterOut', geom, include_filter_metal=False)

    if not RUN_ANALYSIS:
        print('Setup complete (RUN_ANALYSIS=False). Inspect in AEDT via a FRESH COM '
              'connection, enumerating every project handle named %r individually '
              '(CLAUDE.md duplicate-AEDT-project lesson) - confirm: filter metal/bar '
              'is one solid, BoreVacuum+Substrate+PinTube+PinConductor all present, '
              'P1 (wave port) and P2 (lumped port) both assigned, no intersecting '
              'solids, losslessness audit printed clean above. Then set '
              'RUN_ANALYSIS=True and re-run.' % PROJECT_NAME)
        return

    print('RUN_ANALYSIS=True: solving StageA_FilterIn (max_passes=15, tol=0.005)...')
    setup_in.analyze()
    freqs_in, s21_in, rez_in, imz_in = pull_and_export(sweep_in, out_dir, suffix='')
    print('Convergence (StageA_FilterIn):', setup_in.get_convergence())

    if not BUILD_FILTER_OUT_VARIANT:
        print('BUILD_FILTER_OUT_VARIANT=False - filter-in deliverables (1,2) done. '
              'Set BUILD_FILTER_OUT_VARIANT=True and re-run for the filter-out '
              'comparison (deliverable 3) and the attenuation summary.')
        return

    print('Solving StageA_FilterOut...')
    setup_out.analyze()
    freqs_out, s21_out, rez_out, imz_out = pull_and_export(sweep_out, out_dir, suffix='_nofilter')
    print('Convergence (StageA_FilterOut):', setup_out.get_convergence())

    summarize(freqs_in, s21_in, rez_in, freqs_out, s21_out, rez_out, out_dir)

    if not RUN_PINDEPTH_SWEEP:
        print('RUN_PINDEPTH_SWEEP=False - deliverable 4 (pin-depth parametric) skipped '
              'this pass (first thing to trim per the handoff\'s own fallback framing). '
              'Set RUN_PINDEPTH_SWEEP=True and re-run to add it.')
        return

    print('Pin-depth parametric sweep...')
    pindepth_rows = []
    for recess in np.linspace(200.0, 2000.0, 6):
        dname = 'StageA_PinDepth_%04d' % int(recess)
        _, setup_pd, sweep_pd = build_design(project, dname, geom, include_filter_metal=True,
                                              pin_recess_um=float(recess))
        setup_pd.analyze()
        freqs_pd, s21_pd, rez_pd, _ = pull_and_export(sweep_pd, out_dir, suffix='_pd%04d' % int(recess))
        row = dict(pin_recess_um=float(recess))
        for f in SPOT_FREQS_REZ_GHZ:
            row['ReZ_%.1fGHz' % f] = rez_pd[_nearest(freqs_pd, f)]
        for f in SPOT_FREQS_S21_GHZ:
            row['S21dB_%.1fGHz' % f] = s21_pd[_nearest(freqs_pd, f)]
        pindepth_rows.append(row)

    pindepth_path = os.path.join(out_dir, 'stageA_pindepth.csv')
    fieldnames = list(pindepth_rows[0].keys())
    with open(pindepth_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(pindepth_rows)
    print('Pin-depth parametric saved -> %s' % pindepth_path)


if __name__ == '__main__':
    main()
