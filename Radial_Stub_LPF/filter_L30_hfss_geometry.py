#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared geometry constants for filter_L30's HFSS export (filter_L30_HFSS.py)
and its local, Ansys-free verification (verify_L30_hfss_export.py) - split
out so both can import the same numbers instead of duplicating them. Same
role as Hairpin_Filter/hairpin_filter_geometry.py. Deliberately has NO
pyEPR import: pyEPR lives in a separate environment (C:\\Users\\epm114\\.AnE\\,
confirmed this session - see CLAUDE.md), so anything importing pyEPR can't
run in this repo's .venv, and verify_L30_hfss_export.py needs to.

Unlike Hairpin_Filter's geometry file, this one does NOT hardcode a GDS
path/layer, metal bounding box, or port positions - those are all computed
LIVE by verify_L30_hfss_export.regenerate_metal_region() every time it
runs, by importing filter_L30.py directly and replaying its own
position-tracking. Two reasons: (1) filter_L30.py's branch tilts were being
actively hand-tuned this session, so any hardcoded bbox/port snapshot would
go stale almost immediately; (2) round-tripping fan geometry through the
exported DXF/GDS turned out to silently corrupt it - a fan's outline
polyline gains extra, exactly-duplicated vertices somewhere in the DXF
write / GDS read pipeline (a clean 64-vertex CurveRect outline comes back
as 130 vertices with consecutive duplicates). This doesn't change the
enclosed area (invisible to bbox/connectivity/hole-count checks - klayout
still reports a clean single polygon), but Ansys's Parasolid kernel
rejects it outright: CreatePolyline -> PK_ERROR_crossing_edge, confirmed
directly against a real AEDT session this session. Fix: regenerate_metal_
region() rebuilds every polygon (fans via CurveRect._build() called
directly, everything else as clean proper-winding rectangles) purely in
Python, never touching the DXF/GDS round-trip at all. See that function's
own docstring in verify_L30_hfss_export.py for the full story.

No on-chip ground reference exists anywhere on this chip (ground = package
tunnel walls, not modeled here) - same open question already flagged in
Hairpin_Filter's own hairpin_filter_geometry.py, worse here since this
design doesn't even have CPW ground-adjacent gaps. PACKAGE_PADDING_UM below
builds a simple proxy-ground PEC box around the modeled region (confirmed
with Eddie: first-pass approximation, not a real tunnel model - "next
phase" per the original handoff doc).

MODEL_PADDING_UM: unlike Hairpin_Filter_HFSS.py (which draws the substrate
at the chip's FULL dimensions, 6.5x30mm, even though its own metal occupies
only a fraction), this filter's substrate/package region is cropped to the
metal's own bounding box (computed live) plus this padding - a deliberate
deviation, because this design has ~70x more geometric complexity than
Hairpin's and a full 7x40mm domain would make meshing/solving impractically
slow for a first-pass sanity check.
"""

SAPPHIRE_THICKNESS_UM = 500.0   # filter_L30.py's own substrate spec

# Fattened past the real 120nm Al film thickness, same rationale as
# Hairpin_Filter's own METAL_THICKNESS_UM: the metal gets assign_perfect_E
# (a surface boundary condition - thickness doesn't affect the EM solve),
# so this exists purely to keep Parasolid's dynamic range sane relative to
# the package padding.
METAL_THICKNESS_UM = 5.0

MODEL_PADDING_UM = 1500.0       # substrate/package region = metal bbox + this, on all sides
PACKAGE_PADDING_UM = 3000.0     # proxy-ground box padding around the modeled region (see docstring)

Z0_PORT = "50ohm"

SWEEP_START_GHZ = 0.5
SWEEP_STOP_GHZ = 12.0           # covers the full 0.5-3.5GHz passband plus every
                                 # branch zero (up to 12.04GHz) - matches the
                                 # original handoff doc's "HFSS plan" item 1
SWEEP_COUNT = 2301              # ~5MHz resolution; cheap for an Interpolating sweep


def um(val):
    return '%.6fum' % val
