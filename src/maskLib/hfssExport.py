#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GDS -> HFSS geometry bridge.

Reads real fabricated metal polygons directly out of a chip's GDS, for HFSS
driven-modal geometry construction (see Hairpin_Filter/Hairpin_Filter_HFSS.py).
This deliberately avoids scripting AEDT's own GDS/DXF import
(oEditor.Import(...)), whose option-block syntax is version-dependent and
was never verified against a working example - reading the polygons
ourselves and building solids from draw_polyline (closed=True auto-covers
into a sheet) + sweep_along_vector (both confirmed pyEPR HfssModeler
methods - verified against the actual installed pyEPR-quantum package
source, not guessed) keeps every step to primitives that are either
verifiable locally (this module, no Ansys needed) or confirmed against
pyEPR's real source.

Two extraction paths, matching maskLib's two real metal-drawing
conventions (see SNAIL/SNAIL.py's docstring, which explicitly contrasts
them):

  extract_xor_derived_metal() - for chips using maskLib's XOR-gap CPW
    convention (gaps drawn on a dedicated layer, boolean-subtracted from a
    flood fill - see CLAUDE.md). Use this, NOT extract_metal_polygons()
    pointed at a fill_basemetal_from_xor BASEMETAL layer - that flood
    layer is an intermediate result, not the final metal (see that
    function's docstring for how this was confirmed and why it matters).

  extract_metal_polygons() - for chips that draw positive metal directly
    (e.g. SNAIL.py's FlagPads/JJ_chain/flux_transformer), where the target
    layer already holds the true final metal with no further boolean
    needed.

GDS carries no layer-name field - KLayout drops LayerInfo.name on GDS
write (verified empirically: a layer explicitly created with
kdb.LayerInfo(name='BASEMETAL') in fill_basemetal_from_xor comes back with
name='' after a round trip through a written .gds), so a layer is always
identified by its (layer, datatype) number pair, and that pair is NOT
reliably predictable from wafer.layerNums - fill_basemetal_from_xor creates
BASEMETAL via a name-only kdb.LayerInfo(), so its GDS number comes from
KLayout's own DXF-read auto-assignment, not the explicit numbering
gdsExport.dxf_to_gds uses elsewhere. Always call list_layers() first and
pick the layer by shape count/content rather than assuming a number.
"""

from collections import namedtuple

MetalPolygon = namedtuple('MetalPolygon', ['hull', 'holes'])


def list_layers(gds_path):
    '''
    Inspect a GDS file's (layer, datatype) pairs and shape counts, since
    GDS carries no layer names (see module docstring) - use this to
    identify the right layer for extract_metal_polygons() rather than
    guessing a number. Layers with zero shapes anywhere are omitted.

    Returns a list of dicts: {'layer', 'datatype', 'shape_count'}.
    '''
    import klayout.db as kdb   # deferred: maskLib itself must not require klayout

    layout = kdb.Layout()
    layout.read(gds_path)

    out = []
    for i in layout.layer_indexes():
        info = layout.get_info(i)
        count = sum(cell.shapes(i).size() for cell in layout.each_cell())
        if count:
            out.append({'layer': info.layer, 'datatype': info.datatype,
                         'shape_count': count})
    return out


def extract_xor_derived_metal(gds_path, gap_layer, gap_datatype=0, cell_name=None):
    '''
    True final conductor for a chip built with maskLib's XOR-gap CPW
    convention (see CLAUDE.md: "CPW gap geometry uses an XOR layer
    strategy: gaps are drawn on a dedicated layer and boolean-subtracted
    in KLayout"), derived directly from the raw gap layer - NOT from a
    gdsExport.fill_basemetal_from_xor BASEMETAL layer, even if one exists
    in the file.

    This matters: fill_basemetal_from_xor's BASEMETAL output is
    documented as an intermediate flood fill, NOT the final metal - "the
    actual BASEMETAL XOR XOR-layer boolean... still needs to happen
    afterward" (see gdsExport.py). That final boolean isn't scripted
    anywhere else in this codebase (grepped for it - it's a manual
    KLayout step in the existing fab workflow). Confirmed empirically on
    Hairpin_Filter's own output: the flood BASEMETAL layer measures 540um
    wide at a cross-section where the true conductor (line_width=500,
    verified via the XOR below) is exactly 500um - the flood includes the
    two 20um gap strips as solid metal, which would short the CPW gap in
    an HFSS model built from it.

    Also deliberately does NOT reuse fill_basemetal_from_xor's own
    smoothed() BASEMETAL output even when re-deriving correctly from it
    (e.g. flood ^ raw_gap) - that 5um smoothing pass exists for KLayout
    viewer/fab cleanliness, and introduces small alignment slivers against
    the unsmoothed gap layer (48 polygons instead of 4 in testing,
    mostly sub-um-scale artifacts). Recomputing hulls()/XOR straight from
    the raw gap layer both ways avoids that entirely and matches
    CLAUDE.md's "preserve exact dimensions" rule - see module docstring
    for why this uses klayout's own Region boolean engine rather than
    hand-rolled polygon math.

    Returns a list of MetalPolygon(hull, holes), same format as
    extract_metal_polygons().
    '''
    import klayout.db as kdb   # deferred: maskLib itself must not require klayout

    layout = kdb.Layout()
    layout.read(gds_path)
    dbu = layout.dbu

    li = None
    for i in layout.layer_indexes():
        info = layout.get_info(i)
        if info.layer == gap_layer and info.datatype == gap_datatype:
            li = i
            break
    if li is None:
        raise ValueError('no layer %d/%d in %s - see list_layers()' %
                          (gap_layer, gap_datatype, gds_path))

    if cell_name is not None:
        cell = layout.cell(cell_name)
        if cell is None:
            raise ValueError('no cell named %r in %s' % (cell_name, gds_path))
    else:
        candidates = [c for c in layout.each_cell() if not c.shapes(li).is_empty()]
        if len(candidates) != 1:
            raise ValueError(
                'layer %d/%d has shapes on %d cells (%s) - pass cell_name '
                'explicitly' % (gap_layer, gap_datatype, len(candidates),
                                 [c.name for c in candidates]))
        cell = candidates[0]

    gap_region = kdb.Region(cell.shapes(li))
    gap_region.merge()
    flood = gap_region.hulls()
    conductor = flood ^ gap_region
    conductor.merge()

    polygons = []
    for poly in conductor.each_merged():
        dpoly = poly.to_dtype(dbu)
        hull = [(p.x, p.y) for p in dpoly.each_point_hull()]
        holes = [[(p.x, p.y) for p in dpoly.each_point_hole(h)]
                 for h in range(dpoly.holes())]
        polygons.append(MetalPolygon(hull=hull, holes=holes))
    return polygons


def extract_metal_polygons(gds_path, layer, datatype=0, cell_name=None):
    '''
    Read every polygon on (layer, datatype) out of a GDS file, in microns.

    cell_name -- restrict to one cell; if None, auto-detect the single
                 cell that actually holds shapes on this layer (the usual
                 case for a maskLib single-chip GDS, where the shapes are
                 defined once on a child cell and instanced into TOP - see
                 Chip.save's drawCopyDXF). Raises ValueError if that's
                 ambiguous (shapes on more than one cell), so a bad guess
                 fails loudly instead of silently double-counting.

    Returns a list of MetalPolygon(hull, holes): hull is a list of (x, y)
    tuples in microns (no repeated closing vertex); holes is a list of
    such point lists, one per interior ring. holes is always empty for
    chips built via fill_basemetal_from_xor (its hulls() step removes
    every interior hole by construction - see gdsExport.py), but can be
    non-empty for chips that draw ground-plane-with-cutout metal directly
    (e.g. SNAIL.py's FlagPads/flux_transformer, which skip that XOR fill
    step) - handled here rather than assumed away, since this module is
    meant to work for any maskLib chip, not just hairpin-filter-shaped
    ones.
    '''
    import klayout.db as kdb   # deferred: maskLib itself must not require klayout

    layout = kdb.Layout()
    layout.read(gds_path)
    dbu = layout.dbu

    li = None
    for i in layout.layer_indexes():
        info = layout.get_info(i)
        if info.layer == layer and info.datatype == datatype:
            li = i
            break
    if li is None:
        raise ValueError('no layer %d/%d in %s - see list_layers()' %
                          (layer, datatype, gds_path))

    if cell_name is not None:
        cell = layout.cell(cell_name)
        if cell is None:
            raise ValueError('no cell named %r in %s' % (cell_name, gds_path))
    else:
        candidates = [c for c in layout.each_cell() if not c.shapes(li).is_empty()]
        if len(candidates) != 1:
            raise ValueError(
                'layer %d/%d has shapes on %d cells (%s) - pass cell_name '
                'explicitly' % (layer, datatype, len(candidates),
                                 [c.name for c in candidates]))
        cell = candidates[0]

    polygons = []
    for shape in cell.shapes(li).each():
        poly = shape.polygon
        if poly is None:
            continue   # ignore non-polygon shapes (paths, text, etc.)
        dpoly = poly.to_dtype(dbu)
        hull = [(p.x, p.y) for p in dpoly.each_point_hull()]
        holes = [[(p.x, p.y) for p in dpoly.each_point_hole(h)]
                 for h in range(dpoly.holes())]
        polygons.append(MetalPolygon(hull=hull, holes=holes))
    return polygons
