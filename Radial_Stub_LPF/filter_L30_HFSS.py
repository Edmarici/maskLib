#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HFSS Driven Modal S21 setup (and, when RUN_ANALYSIS=True, solve + S21
extraction) for the L30 radial-stub lowpass filter
(Radial_Stub_LPF/filter_L30.py -> DXF/filter_L30_CHIP_L30.gds).

Structure and every low-level pyEPR 0.8 API workaround below (connection
pattern, draw_polyline/sweep_along_vector instead of a nonexistent
thicken_sheet, the material ChangeProperty call, draw_region's quoting
requirements, the CreateRectangle-instead-of-draw_rect_corner port
workaround, make_lumped_port's hardcoded-mm bypass, create_dm_setup's
kwargs) are copied directly from Hairpin_Filter/Hairpin_Filter_HFSS.py,
which hand-verified all of it against the actual installed pyEPR-quantum
0.8 source (not guessed) - see that file's own docstring for the full
rationale on each point. Only the geometry-extraction and geometry-scope
differences below are new to this file.

RUN VIA THE SEPARATE PYEPR ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe filter_L30_HFSS.py
(found and confirmed this session: pyEPR 0.8, numpy 1.26.4 - matches
CLAUDE.md's pin note - and klayout, all present; matplotlib checked lazily
below only if RUN_ANALYSIS=True). Run from THIS file's own directory (so
the relative DXF/GDS paths in filter_L30_hfss_geometry.py resolve) - same
convention as every other script in this repo, see the repo-wide
.vscode/tasks.json fix made earlier this session.

REV 5 UPDATE (this session): filter_L30.py's mask geometry changed from
straight/tilted stalks to HFSS-rescaled, folded (meandered) stalks for
P2/P3 (see filter_L30.py's own module docstring / notebooks/
L30_design_notes.md Rev 5 section) - this file's geometry-replay dependency
(verify_L30_hfss_export.regenerate_metal_pieces()) was rewritten to match,
adding draw_bend_native() (the U-turn analog of draw_fan_native() below,
using the newly-derived+verified bend_arc_points()) and a 3-way piece-kind
dispatch ('fan'/'bend'/None) in the draw loop. Substrate/package/wave-port/
sweep logic below is UNCHANGED - all generic against the live metal bbox
regardless of how the pieces were generated.

WHAT'S DIFFERENT FROM Hairpin_Filter_HFSS.py:

  REGENERATED GEOMETRY, NOT GDS-EXTRACTED - filter_L30.py is a positive-
    metal-draw design (no XOR/ground plane) that draws its BASEMETAL layer
    as ~290 separate overlapping shapes (pad, tapers, main-line segments,
    8 stalks, 8 fans - each fan is a CurveRect polyline + ~31 fill quads).
    An earlier version of this file extracted+merged those via
    maskLib.hfssExport.extract_metal_polygons() + klayout.db.Region.merge()
    - that collapsed cleanly to 1 polygon in klayout's own accounting, but
    CreatePolyline on it threw a real Parasolid PK_ERROR_crossing_edge in
    AEDT (confirmed empirically this session). Root cause: the DXF write ->
    GDS read round-trip corrupts CurveRect's fan outlines - a fan built
    directly in Python has a clean 64-vertex boundary, the same fan read
    back from GDS has 130 vertices with exact consecutive duplicates (a
    zero-length boundary "spike"). This doesn't change enclosed area (so
    klayout's bbox/hole/connectivity checks never caught it), but Parasolid
    rejects it. Fix: verify_L30_hfss_export.regenerate_metal_region()
    (imported below - same function the Ansys-free verify script uses, so
    both stay consistent) rebuilds every polygon directly in Python - fans
    via CurveRect._build() called directly, everything else as clean
    proper-winding rectangles - never touching the DXF/GDS round-trip. That
    also means port positions/widths come back from the same call (position-
    tracking replayed live from filter_L30.py's own tables), not from a
    separately-hardcoded snapshot that could go stale.

  PROXY GROUND - same situation as Hairpin_Filter (no on-chip ground plane
    - here it's even more total: not even CPW ground-adjacent gaps exist,
    this is bare positive metal on bare sapphire, ground = package tunnel
    walls per the original design intent, not modeled here). Confirmed
    with Eddie this session: use a proxy-ground PEC box (Package) as a
    first-pass approximation, not a real tunnel/coax/SNAIL model (that's
    explicitly "next phase" per the original handoff doc). NOT built via
    draw_region() (which pads uniformly in all 6 directions) - see WAVE
    PORTS below for why.

  WAVE PORTS, NOT LUMPED PORTS - the first real solve with lumped ports
    (see notebooks/L30_HFSS_notes.md sec 7) showed S11 flat at ~0dB
    (total reflection) across the ENTIRE swept band - lumped ports need a
    genuine local ground reference, which doesn't exist here (only the
    proxy Package walls, far away). Switched to wave ports per Eddie -
    pyEPR has no wave-port wrapper at all, so this is a raw
    self._boundaries.AssignWavePort(...) COM call. Wave ports need to sit
    on a genuine EXTERIOR boundary face with a well-defined cross-section,
    so Substrate and Package are both built with their Y-extent (the
    port-to-port axis) held EXACTLY at [ymin, ymax] - no padding at all -
    instead of padded beyond the ports like the lumped-port version, so
    Package's two Y-end faces become true exterior boundaries exactly at
    the port cross-sections. This is what fixed the port-matching problem
    - see notebooks/L30_HFSS_notes.md sec 8 for the full result.

  CROPPED MODEL DOMAIN - Hairpin_Filter_HFSS.py draws its substrate at the
    chip's FULL dimensions (6.5x30mm) even though its own metal occupies
    only a fraction. This file instead crops the substrate/package region
    to the metal's own bounding box (computed live from the regenerated
    pieces, not hardcoded) plus MODEL_PADDING_UM - a deliberate, flagged deviation:
    this filter's geometry has ~70x more shape complexity than Hairpin's
    (290 vs ~4), so a full 7x40mm domain would make meshing/solving
    impractically slow for a first-pass sanity check. If a later pass needs
    the true drawn-metal envelope relative to the whole chip (e.g. once
    real package/tunnel geometry gets added), revisit this.

  OUTPUT PORT IS A STAND-IN - port 2 sits at the tip of the drawn 200um
    output line, 1mm before the SNAIL keep-out marker (no real SNAIL
    device exists yet - this was a deliberate choice, confirmed with
    Eddie, standing in for the eventual "lumped port at the SNAIL gap"
    from the original handoff doc's HFSS plan).

  STAGED RUN_ANALYSIS FLAG - Hairpin_Filter_HFSS.py stops after building
    setup and prints manual follow-up instructions. This file goes one
    step further (actually calls .analyze() and pulls/saves S21) but only
    when RUN_ANALYSIS=True, since a full adaptive-mesh solve over a
    556-vertex sheet + package enclosure could run for a long time and
    consumes a real Ansys license seat - not something to trigger silently.
"""

import csv
import os
import sys

from pyEPR import ansys as HFSS

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from verify_L30_hfss_export import regenerate_metal_pieces, fan_arc_points, bend_arc_points  # noqa: E402

from filter_L30_hfss_geometry import (  # noqa: E402
    SAPPHIRE_THICKNESS_UM, METAL_THICKNESS_UM, MODEL_PADDING_UM,
    PACKAGE_PADDING_UM, Z0_PORT, SWEEP_START_GHZ, SWEEP_STOP_GHZ, SWEEP_COUNT, um,
)

# Gates the actual adaptive-mesh solve + S21 pull (see module docstring).
# False: build geometry/ports/boundaries/sweep setup and stop (same scope
# Hairpin_Filter_HFSS.py stops at). True: additionally call
# DM_setup.analyze() and save S21 to CSV + a PNG plot.
# Smoke test passed clean on a freshly-quit AEDT session (single Solids
# entry, 0 Unclassified, both wave ports + setup/sweep confirmed via direct
# COM inspection - see notebooks/L30_HFSS_notes.md Rev 5 section) after
# fixing the exit-turn-to-fan Unite() gap. Flipped to True per Eddie's
# go-ahead to run the real solve.
RUN_ANALYSIS = True


# ===============================================================================
# connection + Driven Modal design setup (verbatim pattern from
# Hairpin_Filter_HFSS.py - see that file's docstring for the full
# per-line pyEPR 0.8 rationale)
# ===============================================================================

project_name = 'filter_L30_S21'
design_name = 'Driven Modal'
overwrite = True

HFSS_path = os.getcwd()
full_path = os.path.join(HFSS_path, project_name + '.aedt')

HFSS_app = HFSS.HfssApp()
HFSS_desktop = HFSS_app.get_app_desktop()

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
# filter metal geometry - drawn as ~26 individual simple pieces, exact-
# touching (matching the true 2D mask geometry exactly - no artificial
# joint overlap), and deliberately NOT united. Rectangles (pad/tapers/
# main-line/stalks) are plain draw_polyline (4 straight segments); fans
# are drawn as TRUE native AEDT arcs (2 arc segments + 2 straight radial
# edges, 6 points total - see draw_fan_native() below), not the ~64-point
# polygon approximation _fan_poly()/CurveRect use for the 2D DXF/GDS mask
# output - confirmed this session that the 6-point arc construction's
# corner points match CurveRect's own discretized output to 0.000000um,
# so this describes the identical physical shape, just as a true analytic
# curve instead of a polygon approximation.
#
# unite() ROOT CAUSE FOUND AND FIXED (this session): nine earlier attempts
# (one-shot N-way, pairwise progressive, with/without joint overlap
# padding, polygon vs. native-arc fans) all left the merged object a
# null/Unclassified body. Eddie isolated it interactively in the AEDT GUI:
# the straight-line stripline (all rectangles) united fine, two fans
# united with each other fine, but a stalk would NOT unite with its own
# fan. Root cause: opposite polygon winding (stalks CW via _rect_poly,
# fans CCW as originally built) giving the two solids oppositely-facing
# surface normals at their shared boundary - confirmed by direct
# shoelace-signed-area computation (stalk -62500, fan +171252) - plus a
# real, visually-confirmed gap between stalk and fan edges in the AEDT
# render. Fixed by reversing the fan's winding to CW (draw_fan_native,
# above) and giving each stalk a small guaranteed real overlap into its
# fan (STALK_FAN_OVERLAP_UM, below) instead of relying on two
# independently-computed edges landing exactly on top of each other.
# Confirmed working: Eddie united all 26 pieces manually in the GUI after
# both fixes landed. The one-shot N-way unite() below reproduces that
# automatically.
# ===============================================================================

def draw_fan_native(model, label, fan_params):
    """Draws one fan as 2 native AEDT arc segments + 2 straight radial
    edges (6 points + 1 duplicate closing point), via a raw CreatePolyline
    COM call - pyEPR's own draw_polyline() hardcodes SegmentType:="Line"
    for every segment (checked source), so arcs need the raw call. AEDT's
    3-point (start, on-arc, end) arc segment format is a standard,
    documented CreatePolyline convention.

    WINDING ORDER MATTERS: fan_arc_points() returns points in CCW order,
    but _rect_poly() (used for every stalk/rect) winds CW - confirmed by
    direct shoelace-signed-area computation this session (stalk: -62500,
    fan: +171252 for a matched test case). Isolated interactively in the
    AEDT GUI: the full straight-line stripline unites fine (all CW, mutually
    consistent), two fans unite with each other fine (both CCW, mutually
    consistent), but a stalk+its own fan will NOT unite ("invalid parameters
    to Unite operation", body deleted) - exactly the signature of opposite-
    winding solids getting opposite-facing surface normals after extrusion,
    which is a classic Parasolid boolean-failure trigger. Reversing the fan's
    point order (CCW -> CW) below fixes this at the source, matching every
    rectangle's winding convention."""
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
    segments + 2 straight radial edges, via the same raw CreatePolyline
    pattern as draw_fan_native() above - the bend analog, for Rev 5's
    folded stalks (P2/P3).

    WINDING ORDER: bend_arc_points() output's winding DEPENDS on the CCW
    parameter (fans never had this choice - they're always drawn the same
    way) - confirmed via direct shoelace computation this session
    (verify_bend_geometry.py): CCW=True -> CCW winding (positive signed
    area), CCW=False -> CW winding (negative signed area) in every case
    tested (angle=90 and angle=180). Since every rectangle
    (_rect_poly/model.draw_polyline) winds CW, only the CCW=True case needs
    reversing to match; CCW=False already comes out CW and is used as-is.
    """
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


# STALK_FAN_OVERLAP_UM: each stalk is drawn this much longer than its true
# (mask-exact) length, poking past its fan attach point by a guaranteed
# real amount - see regenerate_metal_pieces'/​_build_pieces' own docstring
# in verify_L30_hfss_export.py. Fixes a real, visually-confirmed gap
# between stalks and fans in the AEDT render (Eddie spotted it directly in
# the 3D view this session) and may also be implicated in the stalk-fan
# Unite() failures, alongside the winding-order fix in draw_fan_native().
STALK_FAN_OVERLAP_UM = 5.0

geom = regenerate_metal_pieces(stalk_fan_overlap_um=STALK_FAN_OVERLAP_UM)
pieces = geom['pieces']
print('Regenerated %d metal piece(s) directly from filter_L30.py (no DXF/GDS round-trip)' % len(pieces))

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
# bounding box + MODEL_PADDING_UM (see module docstring re: CROPPED MODEL
# DOMAIN - a deliberate deviation from the Hairpin precedent's full-chip box)
#
# WAVE PORTS (this session's change from lumped ports): a wave port needs
# to sit on a genuine EXTERIOR boundary face of the solve domain, with a
# well-defined cross-section (conductor + surrounding dielectric/vacuum +
# enclosing ground) at that plane - unlike a lumped port, it isn't just a
# free-floating rectangle anywhere in the model. So unlike the lumped-port
# version of this file, BOTH Substrate and Package are built with their
# Y-extent EXACTLY [ymin, ymax] (the port-to-port span, no padding at
# all) instead of padded beyond the ports - this makes the two Y-end
# faces of Package genuine exterior boundaries, at exactly the port
# cross-sections, with the metal conductor, substrate, and surrounding
# package walls all visible in that cross-section for the 2D mode solver.
# X and Z keep their padding as before (MODEL_PADDING_UM / PACKAGE_PADDING_UM).
# ===============================================================================

all_xs = [x for _label, hull, _kind, _arc_params in pieces for x, y in hull]
all_ys = [y for _label, hull, _kind, _arc_params in pieces for x, y in hull]
xmin, ymin, xmax, ymax = min(all_xs), min(all_ys), max(all_xs), max(all_ys)

# pyEPR's Box.__init__ (ansys.py) computes self.center = corner + size/2 in
# PLAIN PYTHON ARITHMETIC - it needs numeric inputs, not um()-wrapped
# strings (confirmed empirically: passing strings here raised "unsupported
# operand type(s) for /: 'str' and 'int'"). So bare floats are required,
# matching Hairpin_Filter_HFSS.py's own approach - BUT its claim that
# "AEDT interprets bare numbers in the current model units" (i.e. um, after
# model.set_units('um')) did NOT hold in this session/AEDT version:
# passing raw micron values as bare floats produced a catastrophically
# wrong-scale Substrate box (AEDT reported "Model dimensions ~500000000 ...
# beyond the expected range (1e-08, 10000)" - i.e. ~500 meters where 500um
# was intended, a factor of exactly 1e6 = 1 meter/1um). Fix: pre-scale
# bare floats to meters (AEDT's actual apparent default for this call
# path) before passing them, rather than assuming um.
_UM_TO_M = 1e-6

sub_x0 = xmin - MODEL_PADDING_UM
sub_w = (xmax - xmin) + 2 * MODEL_PADDING_UM
substrate = model.draw_box_corner(
    [sub_x0 * _UM_TO_M, ymin * _UM_TO_M, -SAPPHIRE_THICKNESS_UM * _UM_TO_M],
    [sub_w * _UM_TO_M, (ymax - ymin) * _UM_TO_M, SAPPHIRE_THICKNESS_UM * _UM_TO_M],
    material='sapphire',
    name='Substrate',
)

# PROXY GROUND / PACKAGE - see module docstring. PACKAGE_PADDING_UM=3000
# matches Hairpin_Filter_HFSS.py's own PADDING_UM guess, not derived from
# any real package dimension. Built manually (not via draw_region, which
# pads all 6 directions uniformly around whatever's already in the model)
# so the Y-extent can be held exactly at [ymin, ymax] while X/Z still get
# padded beyond the substrate.
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

# Identify Package's 6 faces by their center coordinates: the two whose
# center y matches ymin/ymax are the port cross-sections (wave ports go
# there, see below); the other 4 (the box's X/Z-facing side walls) get
# PerfectE as the proxy ground enclosure.
face_ids = [int(f) for f in model.get_face_ids(str(package))]
face_y = {fid: float(model._modeler.GetFaceCenter(fid)[1]) for fid in face_ids}
port1_face = min(face_ids, key=lambda fid: abs(face_y[fid] - ymax))  # input, high y
port2_face = min(face_ids, key=lambda fid: abs(face_y[fid] - ymin))  # output, low y
wall_faces = [fid for fid in face_ids if fid not in (port1_face, port2_face)]

model._boundaries.AssignPerfectE(
    ['NAME:Package_Walls', 'Faces:=', wall_faces, 'InfGroundPlane:=', False])

model.assign_perfect_E([METAL_OBJ_NAME], name='Filter_Metal')


# ===============================================================================
# wave ports (this session's change from lumped ports - see module
# docstring). pyEPR has no wave-port wrapper at all (checked source - only
# _make_lumped_port/make_lumped_port exist), so this is a raw
# self._boundaries.AssignWavePort COM call, following AEDT's standard
# scripting syntax for a face-based wave port (Faces:=[face_id], one mode,
# an IntLine for the impedance/phase reference) - verified against a
# minimal isolated test (a plain box, one face) before use here.
#
# Integration line: straight up (+Z) from the conductor's center at the
# port cross-section to the top of the Package enclosure - a reasonable
# "trace referenced to a distant enclosure" convention, NOT derived from
# any specific field-pattern analysis. The 2D eigenmode solver computes
# the actual mode shape from the real cross-sectional geometry regardless
# (conductor + substrate + surrounding vacuum + the 4 PerfectE side
# walls) - the integration line mainly fixes the sign/phase convention
# and helps the impedance renormalization converge to something physical,
# it doesn't define the mode itself. Revisit if results look sign-flipped
# or the computed port impedance looks unphysical.
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
    print('Setup complete (RUN_ANALYSIS=False, matching the same scope '
          "Hairpin_Filter_HFSS.py stops at). Inspect the model in AEDT, "
          'then set RUN_ANALYSIS=True and re-run to solve + pull S21.')
else:
    print('RUN_ANALYSIS=True: running DM_setup.analyze() - this can take a '
          'while (adaptive mesh over a 556-vertex sheet + package '
          'enclosure, up to 12 passes, %d-point interpolating sweep).' % SWEEP_COUNT)
    DM_setup.analyze()

    freqs, s21_db = DM_sweep.get_report_arrays(expr='dB(S(P2,P1))')

    out_dir = os.path.join(os.path.dirname(__file__), 'HFSS')
    os.makedirs(out_dir, exist_ok=True)

    csv_path = os.path.join(out_dir, 'filter_L30_S21.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_GHz', 'S21_dB'])
        writer.writerows(zip(freqs, s21_db))
    print('S21 data saved -> %s' % csv_path)

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(freqs, s21_db)
        ax.set_xlabel('Frequency (GHz)')
        ax.set_ylabel('S21 (dB)')
        ax.set_title('filter_L30 - S21 (PLACEHOLDER geometry, proxy ground)')
        ax.grid(True, alpha=0.3)
        png_path = os.path.join(out_dir, 'filter_L30_S21.png')
        fig.savefig(png_path, dpi=150, bbox_inches='tight')
        print('S21 plot saved -> %s' % png_path)
    except ImportError:
        print('matplotlib not available in this environment - CSV saved, plot skipped.')
