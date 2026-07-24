#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared geometry constants for the hairpin filter's HFSS export
(Hairpin_Filter_HFSS.py) and its local, Ansys-free verification
(verify_hfss_export.py) - split out so both can import the same numbers
instead of duplicating them. Deliberately has NO pyEPR import: pyEPR lives
in a separate environment (see CLAUDE.md), so anything importing pyEPR
can't run in this repo's .venv, and verify_hfss_export.py needs to.

GDS_GAP_LAYER=2 is the raw XOR (CPW gap) layer, NOT the fill_basemetal_from_xor
BASEMETAL flood layer (which was layer 3 in an earlier version of this
file) - confirmed via hfssExport.list_layers() by shape count (~1700
individually-drawn gap rectangles/arcs, matching gdsExport.py's own
description). Metal geometry must go through
hfssExport.extract_xor_derived_metal(), not extract_metal_polygons() on
the BASEMETAL layer directly: the flood layer is only an intermediate
result (its own docstring says so - "the actual BASEMETAL XOR XOR-layer
boolean... still needs to happen afterward"), and that final boolean
isn't scripted anywhere else in this codebase. This was caught empirically
while building the HFSS export: the flood layer measured 540um wide at
the port cut planes below (500um conductor + both 20um gaps included as
solid metal - it would short the CPW gap), while the properly-XORed
metal measures exactly 500um, matching line_width.

Port positions were extracted directly from Hairpin_Filter.py's actual
drawn coordinates (coordinate-tracer script, not estimated), then
independently cross-checked against extract_xor_derived_metal()'s real
polygon edges at each port's cut plane - see verify_hfss_export.py.

PORT1/2_WIDTH_UM=540 is the CPW envelope (line_width + 2*gap) at each
port's reference plane, i.e. how far the port face should span past the
conductor edges to cover both gaps - NOT a claim that all 540um is metal
(the conductor itself is only the center 500um). This chip has no on-chip
ground plane at all (tapped_hairpin_filter's docstring: "package-grounded"
- ground return comes from the physical package enclosing the chip, not
modeled here), so what the port should actually reference as "ground" at
its outer 20um edges is an open question, not yet resolved - flagged
separately, not baked into this number.
"""

import os

GDS_PATH = os.path.join(os.path.dirname(__file__), 'DXF',
                         'Hairpin_Filter_CHIP_HAIRPINBPF.gds')
GDS_GAP_LAYER = 2            # XOR (CPW gap) layer - see module docstring
GDS_GAP_DATATYPE = 0

CHIP_W_UM = 6500.0
CHIP_L_UM = 30000.0
SAPPHIRE_THICKNESS_UM = 550.0

# Fattened well past the real 120nm Al film thickness, deliberately - the
# metal is assigned PerfectE (see Hairpin_Filter_HFSS.py), which is a
# surface boundary condition: current flows on the surface, and the
# solver ignores the metal's actual volume/thickness entirely, so this
# has ZERO effect on the EM solve. What it does affect is Parasolid's
# numerical robustness: at the real 120nm, the model spanned a ~25,000:1
# dynamic range between the metal thickness and the ~3mm package padding,
# which is what caused "Parasolid Error: transformation would result in
# body lying outside the size box" errors when inspecting the built model
# in the AEDT GUI. 5um keeps that ratio down near ~1000:1 while staying
# visually/geometrically "thin trace" relative to the 500um line width.
METAL_THICKNESS_UM = 5.0

PORT1_POS_UM = (4755.0, 27020.0)     # input, direction=+Y
PORT1_WIDTH_UM = 540.0               # 500 (conductor) + 2*20 (gaps) - see module docstring
PORT2_POS_UM = (2285.0, 17350.6)     # output, direction=-Y
PORT2_WIDTH_UM = 540.0

Z0_PORT = "50ohm"
SWEEP_START_GHZ = 2.0
SWEEP_STOP_GHZ = 8.0
SWEEP_COUNT = 2001


def um(val):
    return '%.6fum' % val
