#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 5 2026

@author: Agrim, with Claude (Claude Code)

DXF -> GDS conversion using the KLayout Python module ('pip install
klayout') -- the same engine as the KLayout GUI, so results match a manual
conversion exactly, but with one crucial improvement: the GDS layer
numbers are set EXPLICITLY from the wafer layer table instead of relying
on KLayout's automatic assignment. That guarantees the GDS numbering
always matches the .ldt dose table (see maskLib.layerDoseTable).

Only layers that contain shapes exist in a GDS file (GDS has no layer
table), so empty layers -- e.g. base layers of swept dose families --
vanish in conversion automatically.
"""


def dxf_to_gds(dxf_path, gds_path, gds_layer_numbers, keep_layers=None):
    '''
    Convert a DXF file to GDS, renumbering layers by name.

    dxf_path          -- input DXF
    gds_path          -- output GDS
    gds_layer_numbers -- {layer_name: gds_layer_number}; for a maskLib
                         wafer build it as
                         {name: gds_layer_number(wafer, name)
                          for name in wafer.layerNames}
    keep_layers       -- optional set of layer names; if given, every other
                         layer is dropped from the GDS. Use to split one
                         DXF into per-mask GDS files (e.g. one per
                         photolithography step).

    Layer names found in the DXF but missing from the mapping are left to
    KLayout's automatic numbering, with a loud warning -- their numbers
    are NOT guaranteed to match the .ldt. Returns gds_path.
    '''
    import klayout.db as kdb   # deferred: maskLib itself must not require klayout

    layout = kdb.Layout()
    layout.read(dxf_path)

    if keep_layers is not None:
        keep = set(keep_layers)
        for i in list(layout.layer_indexes()):
            if layout.get_info(i).name not in keep:
                layout.delete_layer(i)

    unmapped = []
    for i in layout.layer_indexes():
        info = layout.get_info(i)
        if not info.name:
            continue   # already numeric (e.g. DXF layer '0' comes in as 0/0)
        if info.name in gds_layer_numbers:
            layout.set_info(i, kdb.LayerInfo(gds_layer_numbers[info.name], 0,
                                             info.name))
        elif any(not cell.shapes(i).is_empty() for cell in layout.each_cell()):
            # only shape-holding layers matter: empty ones (e.g. dxfwrite's
            # VIEWPORTS bookkeeping layer) never reach the GDS at all
            unmapped.append(info.name)
    if unmapped:
        print('\x1b[31mWARNING: DXF layers not in the mapping, GDS numbers '
              'NOT guaranteed to match the .ldt: %s\x1b[0m'
              % ', '.join(unmapped))

    layout.write(gds_path)
    return gds_path


def fill_basemetal_from_xor(dxf_path, out_path, smooth_tolerance_um=5,
                             xor_layer='XOR', basemetal_layer='BASEMETAL'):
    '''
    Derive a BASEMETAL fill from the XOR (CPW gap) layer:

    1. merge() the raw XOR shapes (xor_layer is ~1700+ separately-drawn,
       edge-abutting rectangles/arcs - a fresh pair per CPW_straight/
       CPW_bend/CPW_tee/etc. call - not pre-consolidated polygons) into
       one polygon per electrically-continuous trace run. Each such
       polygon has a hole where its own center conductor is (the two gap
       rails form a ring around it).
    2. hulls() fills every one of those holes exactly - a topological
       "drop the hole" operation with no distance-based offsetting at
       all, so it cannot introduce any faceting/jaggedness regardless of
       how wide the conductor is.
    3. smoothed(smooth_tolerance_um, keep_hv=True) strips the redundant
       vertex density every curved edge inherits from the underlying arc
       approximation (CPW_bend etc. draw arcs as many short straight
       segments - on this chip, merge()+hulls() alone still leaves almost
       half of all boundary points on edges under 5um long, which read as
       a fuzzy/jagged boundary in KLayout even with no individual sharp
       spike). keep_hv=True protects genuinely straight/rectangular edges
       (the actual trace envelope) from being rounded off.

    Deliberately does NOT bridge the remaining gaps between separate
    polygons (e.g. the coupling gaps between adjacent hairpin
    resonators): those resonators are electrically distinct, coupled to
    each other only through the fringing field across that gap, not a
    galvanic connection - and unlike the interior hole (which the later
    BASEMETAL XOR XOR-layer boolean correctly resolves to just the
    conductor regardless of how it's filled), any metal added in a
    coupling gap has no corresponding XOR shape to cancel it back out,
    so it would remain in the final metal as a real short between
    resonators. An earlier version of this function did bridge these
    gaps with a small Size pass and produced exactly that short - fixed
    by removing the bridging step entirely and leaving each
    electrically-isolated trace run as its own separate BASEMETAL
    polygon.

    Whatever currently occupies basemetal_layer in each cell is replaced
    with the derived fill - this is meant to be the sole source of
    BASEMETAL for a chip built entirely from XOR-layer CPW calls, not
    merged with other, independently-drawn BASEMETAL shapes. out_path may
    equal dxf_path to overwrite in place (matching format is inferred from
    each path's extension, e.g. .dxf or .gds). Returns out_path.

    The result is a flood BASEMETAL that hugs the actual trace footprint
    (unlike a hand-computed bounding rectangle) but is NOT yet the final
    metal - the actual BASEMETAL XOR XOR-layer boolean (see
    Wafer.setupXORlayer) still needs to happen afterward, same as always.
    '''
    import klayout.db as kdb   # deferred: maskLib itself must not require klayout

    layout = kdb.Layout()
    layout.read(dxf_path)

    def layer_index(name, create=False):
        for i in layout.layer_indexes():
            if layout.get_info(i).name == name:
                return i
        if create:
            return layout.layer(kdb.LayerInfo(name=name))
        return None

    xor_li = layer_index(xor_layer)
    if xor_li is None:
        raise ValueError('layer %r not found in %s' % (xor_layer, dxf_path))
    basemetal_li = layer_index(basemetal_layer, create=True)

    smooth_dbu = int(round(smooth_tolerance_um / layout.dbu))

    for cell in layout.each_cell():
        xor_region = kdb.Region(cell.shapes(xor_li))
        if xor_region.is_empty():
            continue
        xor_region.merge()
        filled = xor_region.hulls()
        smoothed = filled.smoothed(smooth_dbu, True)
        smoothed.merge()
        cell.shapes(basemetal_li).clear()
        for poly in smoothed.each():
            cell.shapes(basemetal_li).insert(poly)

    layout.write(out_path)
    return out_path
