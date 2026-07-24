#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HFSS Driven Modal S12 setup for the standalone hairpin bandpass filter
(Hairpin_Filter/Hairpin_Filter.py -> DXF/Hairpin_Filter_CHIP_HAIRPINBPF.gds).

CONFIDENCE LEVELS (read before running):

  CONFIRMED - connection setup, Driven Modal design creation, and every
              HfssModeler call used below (draw_box_corner, draw_region,
              draw_polyline, sweep_along_vector, unite, assign_perfect_E,
              Rect.make_lumped_port, create_dm_setup, insert_sweep) are
              verified two ways: the connection/design/box/mesh/unite/PerfE
              pattern is copied from your own working
              snailcav_bigpads_ProcFix1_2025.ipynb notebook, and everything
              used for the metal geometry, package, and ports was
              additionally checked directly against the actual installed
              pyEPR-quantum package source (ansys.py) - not guessed. See
              maskLib.hfssExport for the (locally-verified, no Ansys
              needed) polygon extraction this depends on.
  PROXY GROUND - this filter has NO on-chip ground plane at all
              (tapped_hairpin_filter's own docstring: "package-grounded" -
              ground return comes from the physical metal package
              enclosing the chip in the real device, not from anything in
              this mask). Since you don't have real package dimensions
              yet, the "substrate + airbox" section below builds a
              draw_region() enclosure and assigns PerfectE to its walls as
              a stand-in package (PADDING_UM=3000 is a GUESS, not a real
              package dimension - tune it once you have one). This also
              replaces the old open-radiation-boundary plan entirely (see
              TODO below) - a closed proxy cavity is both simpler to
              script correctly and a better match for "package-grounded"
              than free space would have been anyway.
  TODO      - none blocking a first run. If you later want an open
              (non-package) boundary instead of the PerfectE proxy: no
              radiation-boundary wrapper exists on pyEPR's HfssModeler
              (checked the source - grepped for "radiat", nothing).
              Likely a raw model._boundaries.AssignRadiation(...) call
              (mirroring how assign_perfect_E calls
              model._boundaries.AssignPerfectE(...) internally), but the
              exact parameter array isn't confirmed.

Geometry reference (extracted directly from Hairpin_Filter.py's actual
drawn coordinates and cross-checked against the real fabricated metal
polygons - see hairpin_filter_geometry.py and
Hairpin_Filter/verify_hfss_export.py):
  Chip: 6500 x 30000 um, sapphire, 550um thick, no backside metal.
  Metal: real Al film is 120nm, drawn here at 5um (PerfectE boundary -
    thickness doesn't affect the EM solve, only Parasolid's numerical
    robustness - see hairpin_filter_geometry.py), single layer, true
    conductor width 500um (NOT the 540um CPW envelope - see
    hairpin_filter_geometry.py for why that distinction matters).
  Port 1 (input):  pos=(4755, 27020) um, direction=90deg  (+Y).
  Port 2 (output): pos=(2285, 17350.6) um, direction=270deg (-Y).
  Both ports sit right after the taper from the coupling-tuned tap_width
  (399.6um) back to the filter's actual 50ohm-designed line_width
  (500um) - upstream of both launcher pads, so S12 characterizes the
  filter itself, not the launcher/pin coupling.
"""

import os
import sys
from pyEPR import ansys as HFSS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from maskLib.hfssExport import extract_xor_derived_metal

from hairpin_filter_geometry import (
    GDS_PATH, GDS_GAP_LAYER, GDS_GAP_DATATYPE,
    CHIP_W_UM, CHIP_L_UM, SAPPHIRE_THICKNESS_UM, METAL_THICKNESS_UM,
    PORT1_POS_UM, PORT1_WIDTH_UM, PORT2_POS_UM, PORT2_WIDTH_UM,
    Z0_PORT, SWEEP_START_GHZ, SWEEP_STOP_GHZ, SWEEP_COUNT, um,
)


# First run: build just one metal polygon and stop (cheap, fails fast -
# confirm draw_polyline/sweep_along_vector behave as expected in your
# AEDT version before committing to the full loop). Set False once that's
# confirmed.
SMOKE_TEST = False


# ===============================================================================
# CONFIRMED: connection + Driven Modal design setup
# (pattern copied from snailcav_bigpads_ProcFix1_2025.ipynb cells 185/323)
# ===============================================================================

project_name = 'Hairpin_Filter_S12'
design_name = 'Driven Modal'
overwrite = True

HFSS_path = os.getcwd()
full_path = os.path.join(HFSS_path, project_name + '.aedt')

HFSS_app = HFSS.HfssApp()
HFSS_desktop = HFSS_app.get_app_desktop()

try:
    # pyEPR's open_project has no exception handling at all - it's a
    # direct passthrough to the native OpenProject COM call, which throws
    # (does NOT return None) when the file doesn't exist yet - verified
    # against the actual pyEPR 0.8 source, not assumed. The notebook's own
    # "if project is None" pattern only ever worked because it always
    # opened an already-existing project; ours is new, so catch instead.
    project = HFSS_desktop.open_project(full_path)
    # only needed when reattaching to an already-open project - a
    # freshly-created one is already active, and calling SetActiveProject
    # on it immediately threw a COM error in testing (exact cause
    # unconfirmed - AEDT-side timing/naming quirk, not a pyEPR API gap).
    project.make_active()
except Exception:
    project = HFSS_desktop.new_project()
    project.save(full_path)

# pyEPR 0.8's HfssProject has neither get_design_names() nor
# delete_design() (checked source - only get_designs(), returning objects
# with a .name attribute) - the notebook's pattern assumed a newer pyEPR.
# delete_design falls back to the raw COM object (project._project) that
# HfssProject wraps internally, same pattern as model._boundaries/
# model.oeditor elsewhere in this script for calls pyEPR doesn't expose.
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

# HfssDesign has no make_active() in pyEPR 0.8 (checked source) - a
# newly-inserted design is already active in AEDT by default, so this was
# never actually needed here. HfssDesign.__init__ also already builds and
# exposes .modeler itself (HfssModeler(self, self._modeler,
# self._boundaries, self._mesh)) - HFSS.HfssModeler(DM_design) was a
# newer-pyEPR calling convention; 0.8's constructor needs all four args,
# which DM_design.modeler already has wired up.
model = DM_design.modeler

# draw_box_corner/draw_rect_corner's Box/Rect wrapper objects compute a
# convenience .center as `corner + size/2` in plain Python (checked
# source), which needs numeric or VariableString inputs. HFSS.var()
# looked like the fix (wraps a string as a VariableString supporting that
# arithmetic) but it round-trips the string through sympy, which
# reformats "6500.000000um" as "6500.0*um" - and AEDT's OWN expression
# parser then rejects THAT ("'um' is not a defined variable name" -
# confirmed via desktop.get_messages(), not guessed). The unit-suffixed
# strings from um() were never the problem (draw_polyline/sweep_along_vector/
# draw_region already use them successfully - those don't do local
# arithmetic on their inputs). Simplest fix: set the model's default
# length unit once, then pass PLAIN FLOATS (no strings, no var()) to
# draw_box_corner/draw_rect_corner specifically - Python arithmetic on
# floats just works, and AEDT interprets bare numbers in the current
# model units.
model.set_units('um')


# ===============================================================================
# CONFIRMED: filter metal geometry, built from real fabricated polygons
#
# draw_polyline(points, closed=True) auto-covers into a filled 2D sheet
# (verified in pyEPR source: closed=True sets IsPolylineCovered:=True
# internally) - no separate "cover" step needed. sweep_along_vector then
# extrudes that sheet into a 3D solid along a vector. There is no
# thicken_sheet/ThickenSheet method on HfssModeler at all (an earlier
# draft of this script assumed one existed - it doesn't; checked against
# the actual pyEPR source, not just the notebook).
#
# Polygons come from extract_xor_derived_metal(), which derives the TRUE
# final conductor directly from the raw XOR/gap layer - NOT from a
# fill_basemetal_from_xor BASEMETAL layer, which is only an intermediate
# flood fill (built from that layer, the port cross-sections measure
# 540um of solid metal - i.e. it fills in the CPW gap itself, which would
# short the transmission line in this model). See
# hairpin_filter_geometry.py and maskLib.hfssExport for the full story.
# ===============================================================================

polygons = extract_xor_derived_metal(GDS_PATH, GDS_GAP_LAYER, GDS_GAP_DATATYPE)
print('Extracted %d metal polygon(s) from %s' % (len(polygons), GDS_PATH))

if SMOKE_TEST:
    polygons = polygons[:1]
    print('SMOKE_TEST=True: building only the first polygon. Set False in '
          'this script once this looks right in AEDT.')

metal_names = []
for i, poly in enumerate(polygons):
    if poly.holes:
        raise NotImplementedError(
            'polygon %d has %d hole(s) - this filter is not expected to '
            'have any (see hfssExport docstring). draw_polyline as used '
            'here does not handle holes; would need the outer loop and '
            'each hole loop drawn as separate polylines and subtracted.'
            % (i, len(poly.holes)))
    points_3d = [[um(x), um(y), '0um'] for x, y in poly.hull]
    sheet = model.draw_polyline(points_3d, closed=True, name='FilterMetal_%d' % i)
    model.sweep_along_vector([str(sheet)], ['0um', '0um', um(METAL_THICKNESS_UM)])
    metal_names.append(str(sheet))
    print('  built solid %d/%d: %s (%d vertices)' % (i + 1, len(polygons), sheet, len(poly.hull)))

METAL_OBJ_NAME = model.unite(metal_names) if len(metal_names) > 1 else metal_names[0]

# material='aluminum' is cosmetic/organizational only - assign_perfect_E
# below overrides the electrical behavior regardless of material. Setting
# it at draw_polyline() time (via its material= kwarg) doesn't stick -
# sweep_along_vector doesn't preserve the sheet's material onto the
# resulting solid (confirmed by testing both ways) - so it has to be set
# here, after sweep+unite, via a direct ChangeProperty call (no pyEPR
# wrapper for changing an existing object's material). Without this the
# object silently inherits AEDT's blank-material default and gets grouped
# under "vacuum" in the tree, confusing to look at (found via a
# screenshot of the actual GUI).
model._modeler.ChangeProperty(
    ['NAME:AllTabs',
     ['NAME:Geometry3DAttributeTab',
      ['NAME:PropServers', METAL_OBJ_NAME],
      ['NAME:ChangedProps', ['NAME:Material', 'Value:=', '"aluminum"']]]])


# ===============================================================================
# CONFIRMED: substrate + package (proxy ground enclosure)
# (draw_box_corner/assign material pattern from the notebook; dimensions
# are ours)
# ===============================================================================

substrate = model.draw_box_corner(
    [0, 0, -SAPPHIRE_THICKNESS_UM],
    [CHIP_W_UM, CHIP_L_UM, SAPPHIRE_THICKNESS_UM],
    material='sapphire',
    name='Substrate',
)

# PROXY GROUND PLANE / PACKAGE: this filter has no on-chip ground plane at
# all - the real device's ground return is the metal package enclosing the
# chip (see module docstring's "PROXY GROUND" note - you chose to proxy it
# rather than model the real package or run without one). draw_region() is
# pyEPR's native "wrap the existing model
# in a padded enclosure" call (CreateRegion under the hood) - confirmed
# from source - rather than a second hand-drawn box like the old Airbox:
# a plain draw_box_corner box here would overlap Substrate in space with
# no boolean between them, which is exactly the ambiguity Region exists
# to avoid (it pads out from the current model's real bounding box and
# nests correctly around what's already there). PADDING_UM=3000 is a
# GUESS standing in for real package clearance (a few mm is typical for
# this kind of device) - tune it if/when real package dimensions are
# available; it is not derived from anything.
#
# Assigning PerfectE to the region's own walls makes it double as both
# the enclosure and the proxy package ground - a closed metal cavity is
# also a more faithful stand-in for "package-grounded" than an open
# radiation boundary would have been, independent of the port question.
PADDING_UM = 3000.0
model.draw_region(
    [[um(PADDING_UM), um(PADDING_UM)],
     [um(PADDING_UM), um(PADDING_UM)],
     [um(PADDING_UM), um(PADDING_UM)]],
    PaddingType='Absolute Offset',
    name='Package',
    # material intentionally omitted: draw_region's MaterialValue:= is
    # parsed as an AEDT expression, not a plain name, so it needs embedded
    # quote characters ('"vacuum"', not 'vacuum') - confirmed via AEDT's
    # own error dialog ("'vacuum' is not a defined variable name") when
    # we passed the unquoted form. The function's own default already has
    # the right quoting and is vacuum anyway, so just don't override it.
)
model.assign_perfect_E(['Package'], name='Package_Walls')

model.assign_perfect_E([METAL_OBJ_NAME], name='Filter_Metal')


# ===============================================================================
# CONFIRMED (method) / WORTH WATCHING (physics): lumped ports
#
# Rect.make_lumped_port(axis, z0, name) is a confirmed real method (see
# module docstring). There's now a ground reference (the Package region's
# PerfectE walls, above) so the 50ohm renormalization has something to
# terminate to, but it's 3mm (PADDING_UM) away, not immediately adjacent
# the way a real on-chip coplanar ground would be at the port cross
# section - the port rectangle's own edges, at the 540um CPW envelope,
# still just end in open vacuum/substrate. That's an honest reflection of
# the actual design (no local ground exists - see the module docstring's
# "PROXY GROUND" note), not a bug, but it does mean the port's field
# won't look like a tightly-confined CPW gap mode. If the first real S12
# run doesn't show a sane bandpass shape near the expected ~4.5GHz, this
# (rather than the geometry) is the first thing to revisit - e.g. a wave
# port instead of lumped, or moving the proxy ground much closer.
# ===============================================================================

def make_port(name, center_xy, width_um):
    x0, y0 = center_xy

    # pyEPR 0.8's draw_rect_corner builds a minimal Attributes array (via
    # _attributes_array) that CreateBox tolerates but CreateRectangle does
    # not, in this AEDT version - confirmed by direct testing: even the
    # simplest possible rectangle (10x10 at the origin, freshly-created
    # empty design) failed with "PK_CURVE_make_wire_body_2"/"invalid
    # parameters to CreateRectangle" through draw_rect_corner, while an
    # identical draw_box_corner call succeeded, and the SAME rectangle
    # succeeded once called with a fuller raw Attributes array (Flags/
    # Color/UDMId/MaterialValue/SolveInside all explicitly present, not
    # just Name/Transparency). Calling CreateRectangle directly here
    # rather than through draw_rect_corner.
    pos = [x0 - width_um / 2, y0, 0]
    size = [width_um, 0, METAL_THICKNESS_UM]  # y_size=0 sentinel -> WhichAxis='Y'
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

    # Rect.make_lumped_port()'s own make_center_line() builds the
    # integration line via self.modeler.eval_expr(), which hardcodes
    # units="mm" with no way to override it through make_lumped_port()'s
    # public signature - since our model is in microns, that silently
    # produced a line ~1000x too large, and AEDT rejected it ("Both
    # endpoints of port lines must lie on the port" - read from
    # desktop.get_messages(), not guessed). Bypassing it entirely: call
    # the lower-level _make_lumped_port directly, with the integration
    # line built ourselves as explicit um()-suffixed strings. fix_units()
    # (inside _make_lumped_port) leaves already-unit-suffixed strings
    # untouched, so these pass through correctly. The line spans the
    # port's full width at mid-thickness (z=METAL_THICKNESS_UM/2), same
    # geometry make_center_line was trying (and failing) to produce.
    z_mid = METAL_THICKNESS_UM / 2
    start = [um(x0 - width_um / 2), um(y0), um(z_mid)]
    end = [um(x0 + width_um / 2), um(y0), um(z_mid)]
    model._make_lumped_port(start, end, ['Objects:=', [rect_name]], z0=Z0_PORT, name=name)
    return rect_name


if not SMOKE_TEST:
    port1 = make_port('P1', PORT1_POS_UM, PORT1_WIDTH_UM)
    port2 = make_port('P2', PORT2_POS_UM, PORT2_WIDTH_UM)
else:
    print('SMOKE_TEST=True: skipping port creation (only one metal polygon '
          'was built, ports need the real geometry). Set SMOKE_TEST=False '
          'and re-run once the metal construction looks right.')


# ===============================================================================
# CONFIRMED: Driven Modal analysis setup + frequency sweep
# (create_dm_setup/insert_sweep pattern from the notebook, cell 345 -
# adapted for a plain linear S-parameter sweep instead of their per-mode
# fine-scan loop)
# ===============================================================================

if not SMOKE_TEST:
    DM_setup = DM_design.create_dm_setup(
        freq_ghz=(SWEEP_START_GHZ + SWEEP_STOP_GHZ) / 2,
        name='S12_Setup',
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
        name='S12_Sweep',
        # pyEPR 0.8 names this kwarg 'type', not 'sweep_type' (checked
        # source) - the notebook's 'sweep_type' assumed a newer pyEPR.
        type='Interpolating',
    )

project.save()

if SMOKE_TEST:
    print('Smoke test built. Check the one solid in AEDT looks like a flat '
          'extruded polygon, then set SMOKE_TEST=False and re-run.')
else:
    print('Setup complete. Run DM_setup.analyze() (or via the GUI) to solve, then')
    print("pull S12 via DM_sweep.get_report_arrays(expr='dB(S(P2,P1))') or similar,")
    print('matching the get_report_arrays(expr=...) pattern used for Y-parameters')
    print('in the notebook (cell 350).')
