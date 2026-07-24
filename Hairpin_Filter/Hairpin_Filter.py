#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone n=4 Nuhertz-synthesized tapped CPW hairpin bandpass filter
(~4.5 GHz), launcher-to-launcher, with no stepped-impedance lowpass and no
SNAIL keep-out - a clean two-port test structure for the bandpass filter
alone, on a 6.5mm x 30mm bare (no backside metal) c-plane sapphire chip with
120nm Al (sized for the HFSS S12 export - see Hairpin_Filter_HFSS.py -
not the filter's own footprint, which only needs ~7mm x 17mm; the rest of
the substrate is intentionally empty). Same bandpass parameters and
floorplan conventions as
SNAIL_Pump_Filter/SNAIL_Pump_Filter.py; see that script and the docstring
on tapped_hairpin_filter for the full derivation/caveats.

Every electrical dimension here is a PLACEHOLDER pending HFSS
re-extraction in the real (CPW, package-grounded) environment.

Out of scope: HFSS retuning, open-stub notches, the final BASEMETAL XOR
XOR-layer boolean (still downstream in KLayout, same as always - only the
BASEMETAL *fill* is scripted here, via KLayout's own engine through the
klayout.db Python module, not a Python-side polygon boolean - see
fill_basemetal_from_xor).
"""
import maskLib.MaskLib as m
from maskLib.microwaveLib import CPW_launcher, CPW_straight, CPW_taper, tapped_hairpin_filter
from maskLib.gdsExport import fill_basemetal_from_xor

# Fills BASEMETAL from the XOR layer after the chip DXF is saved (see
# fill_basemetal_from_xor) - requires `pip install klayout`. Set False to
# skip (leaves BASEMETAL empty). Each resonator's own trace fills exactly
# via hulls() (no sizing, so no faceting risk); the coupling gaps between
# adjacent resonators are deliberately left unbridged - they're
# electrically distinct, only fringe-field-coupled, not wired together.
FILL_BASEMETAL_FROM_XOR = True

# ===============================================================================
# wafer setup
# ===============================================================================

w = m.Wafer('Hairpin_Filter', 'DXF/', 6500, 30000, padding=1500,
            waferDiameter=m.waferDiameters['3in'], sawWidth=200,
            frame=1, solid=1, multiLayer=1, singleChipColumn=True)

w.setupXORlayer()
w.SetupLayers([
    ['BASEMETAL', 4],
])
w.init()
w.DicingBorder()

defaults = {'w': 500, 's': 20, 'radius': 300, 'r_out': 100, 'r_ins': 100}

# ===============================================================================
# n=4 tapped hairpin bandpass (Nuhertz Filter Solutions synthesis,
# microstrip/Si/500um - see SNAIL_Pump_Filter.py caveats). PLACEHOLDER
# pending HFSS.
# ===============================================================================

N_POLES = 4
ARM_LENGTH = 4330                  # um - Nuhertz raw value (Si microstrip);
                                    # no backside metal here (confirmed), so
                                    # this is actually CPW - re-extract in HFSS
HAIRPIN_WIDTH = 2000               # um, outer edge-to-edge extent
LINE_WIDTH = 500                   # um
GAP = 20                           # um - placeholder CPW gap, NOT from Nuhertz
                                    # (microstrip has no gap concept). HFSS
                                    # must retune gap/tap_point/tap_width/
                                    # line_width jointly for a real ~50ohm
                                    # target, not just gap alone
COUPLING_GAPS = (333.8, 461.8, 333.8)   # um, edge-to-edge
# Nuhertz's raw tap_point (486.1um) does not clear the tap tee junction's
# own footprint: CPW_tee's corner fillets are keyed off line_width
# regardless of the branch's own width, so tapped_hairpin_filter always
# branches the tee at line_width (500um) and tapers to TAP_WIDTH
# afterward - which needs >= ~540um of room (2*(gap+line_width/2)) no
# matter how small gap gets. Bumped up from Nuhertz's value for clean,
# artifact-free geometry; re-derive properly in HFSS.
TAP_POINT = 700                    # um from the U-bend ("joint")
TAP_WIDTH = 399.6                  # um


class HairpinFilterChip(m.Chip):
    def __init__(self, wafer, chipID, layer):
        # centerChip=False: Chip.add()'s grid-snap applies origin_offset to
        # SolidPline-family shapes (RoundRect/CurveRect, used by CPW_bend/
        # CPW_stub_open/CPW_tee) before their own insert/rotation transform
        # is later applied lazily at DXF-serialization time. On a non-square
        # chip with centerChip=True, any shape drawn at a rotated structure
        # direction gets origin_offset's cross-axis component rotated into
        # its final coordinates (invisible on a square chip, where
        # width/2==height/2, which is why this hasn't shown up in other
        # scripts). This filter's arms run at direction=0 (and the U-bends/
        # taps hit +/-90) throughout, so disable centering here rather than
        # touch the shared Chip.add() logic.
        m.Chip.__init__(self, wafer, chipID, layer, defaults=defaults, centerChip=False)

        # --- bandpass filter: hairpin arms run ACROSS the width
        #     (direction=0), the 4-resonator array stacks DOWN the length.
        #     Centered in x, starting near the top so the array (which
        #     grows toward -y) leaves room above for the input launcher,
        #     and enough room below for the mirrored output launcher (no
        #     LPF/SNAIL downstream on this chip). The chip is much taller
        #     than this compact filter+launcher footprint needs (see
        #     module docstring) - both launcher feeds stay a fixed, short
        #     length (not stretched to reach the chip edges), leaving the
        #     rest of the substrate empty. ---
        bend_radius = (HAIRPIN_WIDTH - LINE_WIDTH) / 2
        # -270um: the launcher pads sit off-center from the arm span itself
        # (the tap tee's LEFT/RIGHT branch choice, not symmetric around the
        # array), so naively centering just ARM_LENGTH left the actual
        # drawn footprint (launcher pads included) only ~25um from the
        # right edge at width=6500 - measured directly from a real render,
        # not derived analytically. This shift rebalances it to comfortable
        # margin on both sides; re-check if ARM_LENGTH or the tap geometry
        # changes.
        array_x0 = (self.width - ARM_LENGTH) / 2 - 270
        array_y0 = self.height - 3500

        s_filt = m.Structure(self, start=(array_x0, array_y0), direction=0, defaults=defaults)
        tap_in, tap_out = tapped_hairpin_filter(self, s_filt, n_poles=N_POLES,
                                                 arm_length=ARM_LENGTH, hairpin_width=HAIRPIN_WIDTH,
                                                 line_width=LINE_WIDTH, gap=GAP,
                                                 coupling_gaps=COUPLING_GAPS,
                                                 tap_point=TAP_POINT, tap_width=TAP_WIDTH,
                                                 layer='XOR')

        # --- input feed: tap_in already faces toward the top edge. Taper the
        #     tap conductor back to the main line_width, then run to a
        #     coupling-pin capacitive pad launcher (no backside metal / no
        #     wirebond - a big open pad the package pin presses against) ---
        edge_margin = 700
        CPW_taper(self, tap_in, length=100, w0=TAP_WIDTH, s0=GAP, w1=LINE_WIDTH, s1=GAP, layer='XOR')
        launch_len_in = (self.height - edge_margin) - tap_in.start[1]
        CPW_straight(self, tap_in, launch_len_in, w=LINE_WIDTH, s=GAP, layer='XOR')
        # l_pad must be nonzero: CPW_launcher's default (0) draws a
        # zero-length CPW_straight pad segment, a genuinely degenerate
        # rectangle. padw/pads set well above line_width/gap so the pad
        # reads as a distinct wide coupling area, not just a taper.
        CPW_launcher(self, tap_in, l_taper=400, l_pad=50, padw=900, pads=150,
                     r_ins=40, r_out=40, layer='XOR')

        # --- output: tap_out is resonator (N_POLES-1)'s arm-B tap, the
        #     literal mirror image of tap_in (resonator 0's arm-A tap) -
        #     see tapped_hairpin_filter's docstring. It already faces
        #     further down the chip, away from the entire array, with no
        #     extra clearance run needed. Mirror the input launcher onto
        #     this end exactly (instead of continuing to an LPF/SNAIL),
        #     making this a symmetric two-port test structure. Reuses
        #     launch_len_in rather than stretching to the (now much
        #     farther away) bottom edge - see the class docstring comment
        #     above on chip vs. filter footprint. ---
        CPW_taper(self, tap_out, length=100, w0=TAP_WIDTH, s0=GAP, w1=LINE_WIDTH, s1=GAP, layer='XOR')
        launch_len_out = launch_len_in
        CPW_straight(self, tap_out, launch_len_out, w=LINE_WIDTH, s=GAP, layer='XOR')
        CPW_launcher(self, tap_out, l_taper=400, l_pad=50, padw=900, pads=150,
                     r_ins=40, r_out=40, layer='XOR')

        # BASEMETAL is filled from the XOR layer as a post-processing step
        # (see FILL_BASEMETAL_FROM_XOR below, after chip.save()) rather than
        # drawn here.

        # --- parameter table for traceability ---
        print('=' * 70)
        print('Standalone hairpin bandpass filter - parameter table')
        print('=' * 70)
        print('Substrate: 550um c-plane sapphire, NO backside metal (CPW, not microstrip)')
        print('Metal: 120nm Al (single layer)')
        print('Chip: %d x %d um' % (self.width, self.height))
        print('-' * 70)
        print('Bandpass (n=%d hairpin, Nuhertz Si-microstrip synthesis):' % N_POLES)
        print('  arm_length      = %.1f um' % ARM_LENGTH)
        print('  hairpin_width   = %.1f um  (bend radius = %.1f um)' % (HAIRPIN_WIDTH, bend_radius))
        print('  line_width      = %.1f um' % LINE_WIDTH)
        print('  gap             = %.1f um  (narrow placeholder, not impedance-matched)' % GAP)
        print('  coupling_gaps   = %s um' % (COUPLING_GAPS,))
        print('  tap_point       = %.1f um from U-bend' % TAP_POINT)
        print('  tap_width       = %.1f um' % TAP_WIDTH)
        print('=' * 70)


chip = HairpinFilterChip(w, 'HAIRPINBPF', 'BASEMETAL')
chip.save(w, drawCopyDXF=True, dicingBorder=False, center=True)

if FILL_BASEMETAL_FROM_XOR:
    # drawCopyDXF above wrote the standalone single-chip DXF at this path
    # (see Chip.save: fileName = wafer.fileName + '_' + chip.ID). Output
    # goes to GDS, not back into the DXF - GDS is the intended final fab
    # format anyway (see gdsExport.py) and uses the same integer
    # database-unit representation klayout.db computes in natively, no
    # ASCII-decimal round-trip. klayout.db.Layout.write() picks the
    # format from the extension.
    chip_dxf_path = w.path + w.fileName + '_' + chip.ID + '.dxf'
    chip_gds_path = w.path + w.fileName + '_' + chip.ID + '.gds'
    fill_basemetal_from_xor(chip_dxf_path, chip_gds_path)
    print('BASEMETAL filled from XOR -> %s' % chip_gds_path)

w.setDefaultChip(chip)
w.populate()
w.save()
