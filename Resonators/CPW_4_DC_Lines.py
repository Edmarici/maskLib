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
from maskLib.microwaveLib import Strip_bend, Strip_straight, waffle
from maskLib.resonatorLib import JellyfishResonator
from maskLib.utilities import cornerRound, doMirrored, rotate_2d

# ===============================================================================
# wafer setup
# ===============================================================================

w = m.Wafer(
    "CPW_4_DC_Lines",
    "DXF/",
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
            4200,
            4200,
            4200,
            4200,
            4200,
            4200,
        ],  # total cpw length (sets the resonator frequency) (lo to high freq)
        seps=[15] * 6,  # resonator distance to cpw (sets each resonator's coupling)
        indices=[
            2,
            0,
            5,
            3,
            1,
            4,
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
            # move away from edge of chip
            s.shiftPos(340)

        start = (2169.5, 4611)  # starting position in microns
        steps = [
            (0, 100),  # up
            (100, 0),  # left
            (0, -46),  # down
            (-10, 0),  # left
            (0, -8),  # up
            (10, 0),  # right
            (0, -46),  # down
            (-39.5, 0),  # left
            (0, 10),  # down
            (-20, 0),  # right
            (0, -10),  # down
            (-39.5, 0),
        ]
        doMirrored(MarkerCross, w, (15000, 15000), linewidth=5, layer="MARKERS3")
        points = [start]
        current = start
        for dx, dy in steps:
            current = (current[0] + dx, current[1] + dy)
            points.append(current)

        self.add(
            SolidPline(
                insert=(0, 0),
                points=points,
                layer="BASEMETAL",
                bgcolor=self.bg("BASEMETAL"),
                solidFillQuads=True,  # required to support subtraction
            )
        )

        half_trace = self.defaults["w"] / 2 + self.defaults["s"]

        # CPW_launcher(
        #     self, 0, padw=250, pads=80, r_ins=30, r_out=30, l_taper=400, layer="BUSMAIN"
        # )
        # CPW_launcher(
        #     self, 5, padw=250, pads=80, r_ins=30, r_out=30, l_taper=400, layer="BUSMAIN"
        # )

        # =================== Adding the tiny rectangle for the TTG sample in a separate layer=============

        start = (2189, 4657)  # starting position in microns

        # # Define steps: (dx, dy)
        # # Each tuple represents a move in a cardinal direction
        # # For example: (100, 0) = right 100 µm, (0, -200) = down 200 µm
        steps = [
            (0, 8),  # up
            (60, 0),  # left
            (0, -8),  # down
            (-60, 0),  # left
        ]

        # Convert steps into absolute points
        points = [start]
        current = start
        for dx, dy in steps:
            current = (current[0] + dx, current[1] + dy)
            points.append(current)

        # Create and close the polygon
        poly = dxf.polyline(points=points, flags=1, layer="Tiny_rectangle")
        poly.close()

        # Add it to the chip
        self.add(poly)

        CPW_launcher(
            self,
            0,
            padw=250,
            pads=80,
            r_ins=30,
            r_out=30,
            l_taper=400,
            layer="BASEMETAL",
        )
        CPW_launcher(
            self,
            5,
            padw=250,
            pads=80,
            r_ins=30,
            r_out=30,
            l_taper=400,
            layer="BASEMETAL",
        )
        # calculate separation between the two structures

        # xdist = self.structures[5].start[0] - self.structures[0].start[0]
        # CPW_straight(self, 0, xdist, layer="BUSMAIN")

        xdist = self.structures[5].start[0] - self.structures[0].start[0]
        CPW_straight(self, 0, xdist, layer="BASEMETAL")
        # make local copy of s0
        s0 = self.structures[0]

        # CPW resonator parameters
        coupler_length = 180  # length of inductive coupler overlap
        straight_length = 62  # length of straight cpw before meanders start
        straight_length2 = 94  # length of straight cpw after meanders
        pincer_tee_r = 5

        # inductively coupled lambda/4 cpw resonators
        for i in range(1, 5, 4):  # jump 2 for resonator in middle
            s1 = s0.cloneAlongLast(
                (
                    xdist / 2
                    + res_spacing * (-1 + indices[i] // 2)
                    - coupler_length / 2,
                    pow(-1, indices[i]) * (half_trace + seps[i] + half_trace),
                )
            )
            s1.defaults["s"] = 10
            s1.defaults["radius"] = 50
            s1.defaults["r_ins"] = 10
            s1.defaults["r_out"] = 20

            CPW_stub_round(self, s1, flipped=True)
            CPW_straight(self, s1, coupler_length)
            CPW_bend(self, s1, CCW=indices[i] % 2)
            CPW_straight(self, s1, straight_length)
            CPW_bend(self, s1, CCW=indices[i] % 2)
            CPW_straight(self, s1, coupler_length / 2)  # unsure the length here
            CPW_wiggles(
                self,
                s1,
                length=total_lengths[i]
                - 1.5 * coupler_length
                - straight_length
                - straight_length2
                - np.pi * s1.defaults["radius"],
                nTurns=4,
                start_bend=False,
                CCW=indices[i] % 2,
            )
            if i == 1:
                CPW_straight(
                    self, s1, straight_length2 - pincer_tee_r - 45
                )  # example: shorten by 50 µm
            else:
                CPW_straight(self, s1, straight_length2 - pincer_tee_r)

        # drawing the second resonator on the opposite side
        cpw_pos = self.centered((1390, -1200))  # (700,2850)

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
        CPW_straight(self, p1, 180)
        CPW_bend(self, p1, CCW=True)
        CPW_straight(self, p1, 62)
        CPW_bend(self, p1, CCW=True)
        CPW_straight(self, p1, 235.734)
        CPW_bend(self, p1, angle=180, CCW=False)

        for i in range(1, 4):
            CPW_straight(self, p1, 291.468)
            CPW_bend(self, p1, angle=180, CCW=True)

            CPW_straight(self, p1, 291.468)
            CPW_bend(self, p1, angle=180, CCW=False)

        CPW_straight(self, p1, 291.468)
        CPW_bend(self, p1, angle=180, CCW=True)
        CPW_straight(self, p1, 95.734)
        CPW_bend(self, p1, angle=90, CCW=False)
        CPW_straight(self, p1, 89)

        # -------------------- Redesigned gate structure --------------------
        launcher_pos = self.centered((2000, 2850))  # (700,2850)

        s3 = m.Structure(
            self,
            launcher_pos,
            direction=270,
            defaults={
                "w": 5,
                "s": 2.5,
                "radius": 300,
                "r_out": 2,
                "r_ins": 2,
                "curve_pts": 30,
            },
        )

        # CPW_launcher(
        #     self,
        #     s3,
        #     padw=250,
        #     pads=80,
        #     r_ins=30,
        #     r_out=30,
        #     l_taper=400,
        #     layer="BUSMAIN",
        # )

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

        # Continue from launcher: vertical straight line downward
        s2 = s3.cloneAlongLast(distance=400, newDirection=0)  # down

        # vertical chargeline
        CPW_straight(self, s2, 949)

        # Bend leftward
        CPW_bend(self, s2, CCW=True, radius=10)

        # ========================INDUCTOR 1 ==============================
        # CPW_straight(self, s2, 200)
        # st_len = 480
        # b_rad = 4
        # l_w = 5

        # Strip_straight(
        #     self,
        #     s2,
        #     10,
        #     layer="inductor",
        #     linewidth=l_w,
        # )
        # Strip_bend(
        #     self,
        #     s2,
        #     angle=90,
        #     CCW=True,
        #     radius=b_rad,
        #     layer="inductor",
        #     linewidth=l_w,
        # )
        # Strip_straight(
        #     self,
        #     s2,
        #     240,
        #     layer="inductor",
        #     linewidth=l_w,
        # )
        # Strip_bend(self, s2, 180, False, radius=b_rad, layer="inductor", linewidth=l_w)

        # for i in range(28):

        #     Strip_straight(
        #         self,
        #         s2,
        #         st_len,
        #         layer="inductor",
        #         linewidth=l_w,
        #     )
        #     Strip_bend(
        #         self, s2, 180, True, radius=b_rad, layer="inductor", linewidth=l_w
        #     )
        #     Strip_straight(
        #         self,
        #         s2,
        #         st_len,
        #         layer="inductor",
        #         linewidth=l_w,
        #     )

        #     Strip_bend(
        #         self, s2, 180, False, radius=b_rad, layer="inductor", linewidth=l_w
        #     )

        # # ======== End of the inductor, making the bend=========
        # Strip_straight(
        #     self,
        #     s2,
        #     480,
        #     layer="inductor",
        #     linewidth=l_w,
        # )
        # Strip_bend(self, s2, 180, True, radius=b_rad, layer="inductor", linewidth=l_w)
        # Strip_straight(
        #     self,
        #     s2,
        #     232,
        #     layer="inductor",
        #     linewidth=l_w,
        # )

        # Strip_bend(self, s2, 90, False, radius=b_rad, layer="inductor", linewidth=l_w)
        # Strip_straight(
        #     self,
        #     s2,
        #     10,
        #     layer="inductor",
        #     linewidth=l_w,
        # )
        # print("first inductor ends at ", s2.getPos())

        # # ========================INDUCTOR 2 ==============================
        # Strip_straight(
        #     self,
        #     s2,
        #     510,
        #     layer="inductor",
        #     linewidth=l_w,
        # )

        # Strip_bend(
        #     self,
        #     s2,
        #     angle=90,
        #     CCW=True,
        #     radius=b_rad,
        #     layer="inductor",
        #     linewidth=l_w,
        # )
        # Strip_straight(
        #     self,
        #     s2,
        #     240,
        #     layer="inductor",
        #     linewidth=l_w,
        # )
        # Strip_bend(self, s2, 180, False, radius=b_rad, layer="inductor", linewidth=l_w)

        # for i in range(40):

        #     Strip_straight(
        #         self,
        #         s2,
        #         st_len,
        #         layer="inductor",
        #         linewidth=l_w,
        #     )
        #     Strip_bend(
        #         self, s2, 180, True, radius=b_rad, layer="inductor", linewidth=l_w
        #     )
        #     Strip_straight(
        #         self,
        #         s2,
        #         st_len,
        #         layer="inductor",
        #         linewidth=l_w,
        #     )

        #     Strip_bend(
        #         self, s2, 180, False, radius=b_rad, layer="inductor", linewidth=l_w
        #     )
        # # ======== End of the inductor, making the bend=========
        # Strip_straight(
        #     self,
        #     s2,
        #     480,
        #     layer="inductor",
        #     linewidth=l_w,
        # )
        # Strip_bend(self, s2, 180, True, radius=b_rad, layer="inductor", linewidth=l_w)
        # Strip_straight(
        #     self,
        #     s2,
        #     232,
        #     layer="inductor",
        #     linewidth=l_w,
        # )

        # Strip_bend(self, s2, 90, False, radius=b_rad, layer="inductor", linewidth=l_w)
        # Strip_straight(
        #     self,
        #     s2,
        #     10,
        #     layer="inductor",
        #     linewidth=l_w,
        # )
        # print("second inductor ends at ", s2.getPos())
        # # Strip_straight(
        # #     self,
        # #     s2,
        # #     1400.5,
        # #     layer="inductor",
        # #     linewidth=l_w,
        # # )

        # # ================= RECTANGLE FOR INDUCTOR 1 ======================
        # start2 = (5290, 4666)

        # steps2 = [
        #     (0, 250),  # up
        #     (-492, 0),  # left
        #     (0, -245),  # down
        #     (0, -260),
        #     (492, 0),
        # ]

        # # Convert steps into absolute points
        # points2 = [start2]
        # current2 = start2
        # for dx2, dy2 in steps2:
        #     current2 = (current2[0] + dx2, current2[1] + dy2)
        #     points2.append(current2)

        # # Create and close the polygon
        # self.add(
        #     SolidPline(
        #         insert=(0, 0),
        #         points=points2,
        #         layer="BASEMETAL",
        #         bgcolor=self.bg("BASEMETAL"),
        #         solidFillQuads=True,  # required to support subtraction
        #     )
        # )

        # # ================= RECTANGLE FOR INDUCTOR 2 =======================
        # start2 = (4298, 4666)

        # steps2 = [
        #     (0, 250),  # up
        #     (-684, 0),  # left
        #     (0, -245),  # down
        #     (0, -260),
        #     (684, 0),
        # ]

        # # Convert steps into absolute points
        # points2 = [start2]
        # current2 = start2
        # for dx2, dy2 in steps2:
        #     current2 = (current2[0] + dx2, current2[1] + dy2)
        #     points2.append(current2)

        # # Create and close the polygon
        # self.add(
        #     SolidPline(
        #         insert=(0, 0),
        #         points=points2,
        #         layer="BASEMETAL",
        #         bgcolor=self.bg("BASEMETAL"),
        #         solidFillQuads=True,  # required to support subtraction
        #     )
        # )
        # # ========================CAPACITOR 1 ==============================
        # cap1_pos = self.centered((1298, 1166))

        # c1 = m.Structure(
        #     self,
        #     cap1_pos,
        #     direction=180,
        # )
        # st_len = 235
        # l_w = 5
        # b_rad = 5

        # # upper half of the capacitor
        # Strip_straight(
        #     self,
        #     c1,
        #     20,
        #     w=5,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(
        #     self,
        #     c1,
        #     angle=90,
        #     CCW=True,
        #     radius=b_rad,
        #     layer="BASEMETAL",
        #     w=l_w,
        # )
        # Strip_straight(
        #     self,
        #     c1,
        #     st_len,
        #     l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)

        # for i in range(22):
        #     Strip_straight(
        #         self,
        #         c1,
        #         st_len,
        #         l_w,
        #         layer="BASEMETAL",
        #     )
        #     Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)
        #     Strip_straight(
        #         self,
        #         c1,
        #         st_len,
        #         l_w,
        #         layer="BASEMETAL",
        #     )
        #     Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)

        # Strip_straight(
        #     self,
        #     c1,
        #     st_len,
        #     l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(self, c1, 90, True, radius=b_rad, layer="BASEMETAL", w=l_w)
        # Strip_straight(
        #     self,
        #     c1,
        #     20,
        #     w=5,
        #     layer="BASEMETAL",
        # )

        # # lower half of the capacitor
        # cap1_pos = self.centered((1298, 1156))

        # c1 = m.Structure(
        #     self,
        #     cap1_pos,
        #     direction=180,
        # )
        # st_len = 235
        # l_w = 5
        # b_rad = 5
        # Strip_straight(
        #     self,
        #     c1,
        #     20,
        #     w=5,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(
        #     self,
        #     c1,
        #     angle=90,
        #     CCW=False,
        #     radius=b_rad,
        #     layer="BASEMETAL",
        #     w=l_w,
        # )
        # Strip_straight(
        #     self,
        #     c1,
        #     st_len,
        #     l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)

        # for i in range(22):
        #     Strip_straight(
        #         self,
        #         c1,
        #         st_len,
        #         l_w,
        #         layer="BASEMETAL",
        #     )
        #     Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)
        #     Strip_straight(
        #         self,
        #         c1,
        #         st_len,
        #         l_w,
        #         layer="BASEMETAL",
        #     )
        #     Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)

        # Strip_straight(
        #     self,
        #     c1,
        #     st_len,
        #     l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(self, c1, 90, False, radius=b_rad, layer="BASEMETAL", w=l_w)
        # Strip_straight(
        #     self,
        #     c1,
        #     20,
        #     w=5,
        #     layer="BASEMETAL",
        # )
        # print("capacitor 1 ends at ", c1.getPos())
        # # ========================CAPACITOR 2 ==============================
        # cap2_pos = self.centered((114, 1166))

        # c1 = m.Structure(
        #     self,
        #     cap2_pos,
        #     direction=180,
        # )
        # st_len = 235
        # l_w = 2
        # b_rad = 6

        # # upper half of the capacitor
        # Strip_straight(
        #     self,
        #     c1,
        #     20,
        #     w=l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(
        #     self,
        #     c1,
        #     angle=90,
        #     CCW=True,
        #     radius=b_rad,
        #     layer="BASEMETAL",
        #     w=l_w,
        # )
        # Strip_straight(
        #     self,
        #     c1,
        #     st_len,
        #     l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)

        # for i in range(45):
        #     Strip_straight(
        #         self,
        #         c1,
        #         st_len,
        #         l_w,
        #         layer="BASEMETAL",
        #     )
        #     Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)
        #     Strip_straight(
        #         self,
        #         c1,
        #         st_len,
        #         l_w,
        #         layer="BASEMETAL",
        #     )
        #     Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)

        # Strip_straight(
        #     self,
        #     c1,
        #     st_len,
        #     l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(self, c1, 90, True, radius=b_rad, layer="BASEMETAL", w=l_w)
        # Strip_straight(
        #     self,
        #     c1,
        #     20,
        #     w=l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_straight(
        #     self,
        #     c1,
        #     200.5,
        #     w=l_w,
        #     layer="BASEMETAL",
        # )

        # # lower half of the capacitor
        # cap2_pos = self.centered((114, 1156))

        # c1 = m.Structure(
        #     self,
        #     cap2_pos,
        #     direction=180,
        # )
        # st_len = 235
        # l_w = 2
        # b_rad = 6
        # Strip_straight(
        #     self,
        #     c1,
        #     20,
        #     w=l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(
        #     self,
        #     c1,
        #     angle=90,
        #     CCW=False,
        #     radius=b_rad,
        #     layer="BASEMETAL",
        #     w=l_w,
        # )
        # Strip_straight(
        #     self,
        #     c1,
        #     st_len,
        #     l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)

        # for i in range(45):
        #     Strip_straight(
        #         self,
        #         c1,
        #         st_len,
        #         l_w,
        #         layer="BASEMETAL",
        #     )
        #     Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)
        #     Strip_straight(
        #         self,
        #         c1,
        #         st_len,
        #         l_w,
        #         layer="BASEMETAL",
        #     )
        #     Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)

        # Strip_straight(
        #     self,
        #     c1,
        #     st_len,
        #     l_w,
        #     layer="BASEMETAL",
        # )
        # Strip_bend(self, c1, 90, False, radius=b_rad, layer="BASEMETAL", w=l_w)
        # Strip_straight(
        #     self,
        #     c1,
        #     20,
        #     w=l_w,
        #     layer="BASEMETAL",
        # )
        # print("capacitor 2 ends at ", c1.getPos())
        # Strip_straight(
        #     self,
        #     c1,
        #     200.5,
        #     w=l_w,
        #     layer="BASEMETAL",
        # )
        # # =================================================================================

        # # resistance bars
        # ResistanceBarNegative(self, m.Structure(self, self.centered((0, -3000))))

        # Add markers
        length = 200
        linewidth = 10
        CrossAlignMark(self, (6000, 6000), length, linewidth, layer="MARKERS_CHIP2")
        CrossAlignMark(self, (1000, 1000), length, linewidth, layer="MARKERS_CHIP2")
        CrossAlignMark(self, (1000, 6000), length, linewidth, layer="MARKERS_CHIP2")
        CrossAlignMark(self, (6000, 1000), length, linewidth, layer="MARKERS_CHIP2")

        # Add smaller markers
        length2 = 18
        linewidth2 = 2
        CrossAlignMark(self, (2160.5, 4720), length2, linewidth2, layer="MARKERS_CHIP2")
        CrossAlignMark(self, (2160.5, 4602), length2, linewidth2, layer="MARKERS_CHIP2")
        CrossAlignMark(self, (2278.5, 4602), length2, linewidth2, layer="MARKERS_CHIP2")
        CrossAlignMark(self, (2278.5, 4720), length2, linewidth2, layer="MARKERS_CHIP2")
        waffle(self, 171.3, width=20, bleedRadius=1, padx=700, layer="MARKERS")


ResonatorChip = ResonatorChip6(w, "RESONATORS", "BASEMETAL")

ResonatorChip.save(w, drawCopyDXF=True, dicingBorder=False, center=True)


print(len(w.chips))
for k, chip in enumerate(w.chips):
    # for i in range(0, len(w.chips)):

    ResonatorChip = ResonatorChip6(
        w,
        f"RESONATORS_{k}",
        "BASEMETAL",
    )
    chipnum = str(k + 1)
    label = chipnum
    print(label)
    ResonatorChip.add_chip_label(
        label, (991, 850), height=75, layer="CHIP_LABEL"
    )  # Add label to the chip's block

    w.setChipBuffer(ResonatorChip.save(w), k)
# write all chips
doMirrored(MarkerCross, w, (15000, 15000), linewidth=5, layer="MARKERS3")
print(w.fileName, w.path)

w.populate()

w.save()
