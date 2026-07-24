#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone SNAIL device test chip: asymmetric pad pair -> 3-big-JJ + 1-small-JJ
loop -> flux-transformer coupler, via the new SNAIL() function in qubitLib.py
(see that function's docstring for the full Ansys -> mask parameter mapping).

Out of scope: wiring the flux transformer into a pump-line feed (see
SNAIL_Pump_Filter/SNAIL_Pump_Filter.py's placeholder keep-out box) - this
chip verifies the SNAIL device geometry in isolation first.

No XOR/BASEMETAL fill step: FlagPads/JJ_chain/smallJJ/flux_transformer draw
positive metal directly (SolidPline/dxf.rectangle), not the XOR-gap CPW
convention used elsewhere in this codebase, so fill_basemetal_from_xor does
not apply here.
"""
import maskLib.MaskLib as m
from maskLib.qubitLib import SNAIL

# ===============================================================================
# wafer setup
# ===============================================================================

w = m.Wafer('SNAIL', 'DXF/', 12000, 10000, padding=1000,
            waferDiameter=m.waferDiameters['3in'], sawWidth=200,
            frame=1, solid=1, multiLayer=1, singleChipColumn=True)

w.SetupLayers([
    ['SNAILMON', 4],
    ['FT', 6],
])
w.init()
w.DicingBorder()


class SnailChip(m.Chip):
    def __init__(self, wafer, chipID, layer):
        m.Chip.__init__(self, wafer, chipID, layer, centerChip=False)

        # startpoint chosen with room above for the longer pad
        # (leadh+flagh=4750), below for the shorter one
        # (padseparation+leadh2+flagh2=2950), and to the right for the flux
        # transformer's large rectangle (~5565 from startpoint) - sized from
        # the first render's actual bbox overflow, not guessed blind.
        startpoint = (2500, 3800)

        SNAIL(self, startpoint=startpoint, pads=True, snail=True, FT=True,
              layer='SNAILMON')

        print('=' * 70)
        print('Standalone SNAIL device')
        print('=' * 70)
        print('Chip: %d x %d um' % (self.width, self.height))
        print('startpoint: %s' % (startpoint,))
        print('=' * 70)


chip = SnailChip(w, 'SNAIL', 'SNAILMON')
chip.save(w, drawCopyDXF=True, dicingBorder=False, center=True)

w.setDefaultChip(chip)
w.populate()
w.save()
