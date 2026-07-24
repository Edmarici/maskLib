#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 21 18:29:41 2022

@author: sasha

Generating file for a wafer of
"""
import math

import numpy as np
from dxfwrite import DXFEngine as dxf
from dxfwrite import const
from dxfwrite.vector2d import vadd, vmul_scalar, vsub

import maskLib.MaskLib as m
from maskLib.dcLib import ResistanceBarNegative
from maskLib.Entities import CurveRect, InsideCurve, SolidPline
from maskLib.junctionLib import CrossAlignMark
from maskLib.markerLib import MarkerCross, MarkerCross_global, MarkerSquare
from maskLib.microwaveLib import *
from maskLib.microwaveLib import (
    LC_Filter_cap1,
    LC_Filter_cap2,
    LC_Filter_ind1,
    LC_Filter_ind2,
    LC_Filter_ind_rects1,
    LC_Filter_ind_rects2,
    Strip_bend,
    Strip_straight,
    waffle,
)
from maskLib.resonatorLib import JellyfishResonator
from maskLib.utilities import cornerRound, doMirrored, rotate_2d

# ===============================================================================
# wafer setup
# ===============================================================================

w = m.Wafer(
    "CPW_2_res_driven_modal",
    "DXF/Resonator/",
    7000,
    7000,
    padding=2500,
    waferDiameter=m.waferDiameters["2in"],
    sawWidth=200,
    frame=1,
    solid=0,
    multiLayer=1,
)


w.SetupLayers([["BASEMETAL", 4], ["BUSMAIN", 3], ["MARKERS", 2], ["inductor", 5]])

# initialize the wafer
w.init()

# write the dicing border
w.DicingBorder()


class ResonatorChip6(m.Chip7mm):
    def __init__(
        self,
        wafer,
        chipID,
        layer,
        total_lengths=[
            5382,
            5382,
            5382,
            5382,
            5382,
            5382,
        ],  # total cpw length (sets the resonator frequency) (lo to high freq)
        seps=[15] * 6,  # resonator distance to cpw (sets each resonator's coupling)
        indices=[
            1,
            2,
            3,
            4,
            5,
            6,
        ],  # these indices are chosen so no two adjacent resonators are close in frequency (to limit crosstalk)
        res_spacing=1300,
        res_spacing2=1000,  # how far apart the resonators are
    ):
        m.Chip7mm.__init__(
            self,
            wafer,
            chipID,
            layer,
            defaults={
                "w": 20,
                "s": 10,
                "radius": 300,
                "r_out": 10,
                "r_ins": 10,
                "curve_pts": 30,
            },
        )
        for s in self.structures:
            s.shiftPos(340)

        launcher_pos = self.centered(
            (-2660, -2350)
        )  # (-2660,-2550) centre of the left launcher

        s3 = m.Structure(
            self,
            launcher_pos,
            direction=0,
            defaults={
                "w": 5,
                "s": 2.5,
                "radius": 300,
                "r_out": 2,
                "r_ins": 2,
                "curve_pts": 30,
            },
        )

        CPW_launcher(
            self,
            s3,
            padw=250,
            pads=80,
            r_ins=30,
            r_out=30,
            l_taper=400,
            layer="BASEMETAL",
        )
        CPW_straight(self, s3, 3860)

        # Continue from straight line
        s2 = s3.cloneAlongLast(distance=4590, newDirection=180)  # down

        CPW_launcher(
            self,
            s2,
            padw=250,
            pads=80,
            r_ins=30,
            r_out=30,
            l_taper=400,
            layer="BASEMETAL",
        )
        ## drawing the test resonator ~7GHz
        cpw_pos = self.centered((1530, -2305))  # (1390,-2310)

        p1 = m.Structure(
            self,
            cpw_pos,
            direction=0,
        )
        p1.defaults["s"] = 10
        p1.defaults["radius"] = 50
        p1.defaults["r_ins"] = 10
        p1.defaults["r_out"] = 20

        CPW_stub_round(self, p1, flipped=True)
        CPW_straight(self, p1, 250)
        CPW_bend(self, p1, CCW=False)
        CPW_straight(self, p1, 62)
        CPW_bend(self, p1, CCW=False)
        CPW_straight(self, p1, 235.734)
        CPW_bend(self, p1, angle=180, CCW=True)

        for i in range(1, 4):
            CPW_straight(self, p1, 291.468)
            CPW_bend(self, p1, angle=180, CCW=False)

            CPW_straight(self, p1, 291.468)
            CPW_bend(self, p1, angle=180, CCW=True)

        CPW_straight(self, p1, 291.468)
        CPW_bend(self, p1, angle=180, CCW=False)
        CPW_straight(self, p1, 95.734)
        CPW_bend(self, p1, angle=90, CCW=True)
        CPW_straight(self, p1, 29)

        # drawing the graphene resonator ~6GHz
        cpw_pos = self.centered((-1760, -2320))  # (-1391, -2310)

        p1 = m.Structure(
            self,
            cpw_pos,
            direction=0,
        )
        p1.defaults["s"] = 10
        p1.defaults["radius"] = 50
        p1.defaults["r_ins"] = 10
        p1.defaults["r_out"] = 20

        CPW_stub_round(self, p1, flipped=True)
        CPW_straight(self, p1, 250)
        CPW_bend(self, p1, CCW=False)
        CPW_straight(self, p1, 62)
        CPW_bend(self, p1, CCW=False)
        CPW_straight(self, p1, 309.609)
        CPW_bend(self, p1, angle=180, CCW=True)

        for i in range(1, 4):
            CPW_straight(self, p1, 439.218)
            CPW_bend(self, p1, angle=180, CCW=False)

            CPW_straight(self, p1, 439.218)
            CPW_bend(self, p1, angle=180, CCW=True)

        CPW_straight(self, p1, 439.218)
        CPW_bend(self, p1, angle=180, CCW=False)
        CPW_straight(self, p1, 99.609)
        CPW_bend(self, p1, angle=90, CCW=True)
        CPW_straight(self, p1, 44)

        # # Add markers
        # length = 200
        # linewidth = 10
        # CrossAlignMark(self, (6000, 6000), length, linewidth, layer="MARKERS_CHIP2")
        # CrossAlignMark(self, (1000, 1000), length, linewidth, layer="MARKERS_CHIP2")
        # CrossAlignMark(self, (1000, 6000), length, linewidth, layer="MARKERS_CHIP2")
        # CrossAlignMark(self, (6000, 1000), length, linewidth, layer="MARKERS_CHIP2")

        # # Add smaller markers
        # length2 = 18
        # linewidth2 = 2
        # CrossAlignMark(self, (2160.5, 4720), length2, linewidth2, layer="MARKERS_CHIP2")
        # CrossAlignMark(self, (2160.5, 4602), length2, linewidth2, layer="MARKERS_CHIP2")
        # CrossAlignMark(self, (2278.5, 4602), length2, linewidth2, layer="MARKERS_CHIP2")
        # CrossAlignMark(self, (2278.5, 4720), length2, linewidth2, layer="MARKERS_CHIP2")
        # waffle(self, 171.3, width=20, bleedRadius=1, padx=700, layer="MARKERS")


ResonatorChip = ResonatorChip6(w, "RESONATORS", "BASEMETAL")

ResonatorChip.save(w, drawCopyDXF=True, dicingBorder=False, center=True)


# print(len(w.chips))
# for k, chip in enumerate(w.chips):
#     # for i in range(0, len(w.chips)):

#     ResonatorChip = ResonatorChip6(
#         w,
#         f"RESONATORS_{k}",
#         "BASEMETAL",
#     )
#     chipnum = str(k + 1)
#     label = chipnum
#     # print(label)
#     ResonatorChip.add_chip_label(
#         label, (700, 700), height=75, layer="CHIP_LABEL"
#     )  # Add label to the chip's block

#     w.setChipBuffer(ResonatorChip.save(w), k)
# # write all chips
# doMirrored(MarkerCross, w, (15000, 15000), linewidth=5, layer="MARKERS3")
print(w.fileName, w.path)

w.populate()

w.save()
