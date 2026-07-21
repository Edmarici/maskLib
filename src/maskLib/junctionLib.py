# -*- coding: utf-8 -*-
"""
Created on Fri Mar 27 13:02:59 2020

@author: sasha
Edited by Agrim, 2026 (added tab_shift_x to Transmon3DWithShunt)

Library for drawing standard junctions and other relevant components (contact tabs, etc)
"""

import maskLib.MaskLib as m
from dxfwrite import DXFEngine as dxf
from dxfwrite import const

from dxfwrite.vector2d import vadd
from dxfwrite.algebra import rotate_2d

from maskLib.Entities import SolidPline, CurveRect, RoundRect, InsideCurve
from maskLib.microwaveLib import Strip_straight, Strip_taper, Strip_pad

from maskLib.utilities import curveAB, kwargStrip, cornerRound
from maskLib.point_logger import log_point, log_points

import math
import ezdxf
from ezdxf.math import Vec2
from ezdxf.addons import geo

# ===============================================================================
# global functions to setup global variables in an arbitrary wafer object
# these can 
# ===============================================================================

def setupJunctionLayers(wafer,JLAYER='JUNCTION',jcolor=1,ULAYER='UNDERCUT',ucolor=2,bandaid=False,BLAYER='BANDAID',bcolor=3):
    #add correct layers to wafer, and cache layer
    wafer.addLayer(JLAYER,jcolor)
    wafer.JLAYER=JLAYER
    wafer.addLayer(ULAYER,ucolor)
    wafer.ULAYER=ULAYER
    if bandaid:
        wafer.addLayer(BLAYER,bcolor)
        wafer.BLAYER=BLAYER

def setupJunctionAngles(wafer,JANGLES=[0,90]):
    '''
    Angles are defined as the angle in degrees *from which the evaporation is coming*.
    For example, if the first evaporation comes from the East, and the second from the north,
    the angles would be [0,90]. Add more angles to the list as needed.
    '''
    wafer.JANGLES = [angle % 360 for angle in JANGLES]
    
def setupManhattanJAngles(wafer,JANGLE1=0,flip=False):
    '''
    Sets up angles specifically for manhattan junction (Angle 2 is 90 deg CW or CCW from angle 1)
    '''
    JANGLE2 = JANGLE1 + 90
    if flip:
        JANGLE2 = JANGLE1 - 90
    setupJunctionAngles(wafer,[JANGLE1 % 360,JANGLE2 % 360])

# ===============================================================================
# contact pad functions (for ground plane)
# ===============================================================================
                                #stemw=3,steml=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5
def JcalcTabDims(chip,structure,gapw=3,gapl=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5,absoluteDimensions=False,stemw=None,steml=None,**kwargs):
    if stemw is not None:
        gapw = stemw
    if steml is not None:
        gapl = steml
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,start=structure,direction=0)
        else:
            return chip.structure(structure)
    if r_out is None:
        try:
            r_out = struct().defaults['r_out']
        except KeyError:
            #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            r_out = 0
    if r_ins is None:
        try:
            r_ins = struct().defaults['r_ins']
        except KeyError:
            #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            r_ins = 0
    #determine stem and tab lengths
    if absoluteDimensions:
        if gapl >= 2*r_out:
            gapl = gapl-2*r_out
        if tabl >= 2*r_ins:
            tabl = tabl-2*r_ins
            
    #returns length, half width
    return 2*r_out+gapl+taboffs+2*r_ins+tabl,(gapw/2+r_out+tabw+r_ins)
    
                                                                    #stemw=3,steml=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5
# def JContact_slot(chip,structure,rotation=0,absoluteDimensions=False,gapw=3,gapl=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5,hflip=False,bgcolor=None,debug=False,**kwargs):
#     '''
#     Creates shapes forming a negative space puzzle piece slot (tab) with rounded corners, and adjustable angles. 
#     No overlap : XOR mode compatible
#     Centered on outside midpoint of gap
    
#     gap: {width (gapw),height (gapl),r_out}
#     tab: {slot width, (tabw),height (tabl), height offset (taboffs),r_ins}
    
#     by default, absolute dimensions are off, so gap / tab lengths are determined by radii. gapl and tabl will then determine extra space between rounded corners.
#     if absolute dimensions are on, then tab / gap lengths are determined only by gapl and tabl.
    
#     set r_ins or r_out to None to inherit defaults from chip/structure
#     '''
#     def struct():
#         if isinstance(structure,m.Structure):
#             return structure
#         elif isinstance(structure,tuple):
#             return m.Structure(chip,start=structure,direction=rotation)
#         else:
#             return chip.structure(structure)
#     if r_out is None:
#         try:
#             r_out = struct().defaults['r_out']
#         except KeyError:
#             #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
#             r_out = 0
#     if r_ins is None:
#         try:
#             r_ins = struct().defaults['r_ins']
#         except KeyError:
#             #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
#             r_ins = 0
#     if bgcolor is None:
#         bgcolor = chip.wafer.bg()
    
#     tot_length,half_width = JcalcTabDims(chip,structure,gapw,gapl,tabw,tabl,taboffs,r_out,r_ins,absoluteDimensions)
#     #determine stem and tab lengths
#     if absoluteDimensions:
#         if gapl >= 2*r_out:
#             gapl = gapl-2*r_out
#         else:
#             print('\x1b[33mWarning:\x1b[0m gap too short in ',chip.chipID,'!')
#         if tabl >= 2*r_ins:
#             tabl = tabl-2*r_ins
#         else:
#             print('\x1b[33mWarning:\x1b[0m tab too short in ',chip.chipID,'!')
    
#     if hflip:
#         struct().shiftPos(tot_length,angle=180)
    
#     if taboffs==0:
#         theta=90
#     else:
#         theta = math.degrees(math.atan2(
#             (r_ins + r_out)*(taboffs + r_ins + r_out)+ abs(tabw)*math.sqrt(max(tabw**2 + taboffs*(taboffs + 2*(r_ins + r_out)),0)),
#             tabw*(-r_ins - r_out)+(taboffs + r_ins + r_out)*math.sqrt(max(tabw**2 + taboffs*(taboffs + 2*(r_ins + r_out)),0))*abs(tabw)/tabw))
#     inside_ptx = tot_length-tabl-r_ins*(1+math.sin(math.radians(theta))- (1- math.cos(math.radians(theta)))/math.tan(math.radians(theta)))
    
#     chip.add(SolidPline(struct().getPos(),rotation=struct().direction,points=[(gapl+r_out,gapw/2+r_out),
#                                                                               (gapl+r_out*(1+math.sin(math.radians(theta))),gapw/2+r_out*(1-math.cos(math.radians(theta)))),
#                                                                               (inside_ptx,half_width),(0,half_width),(0,gapw/2+r_out)],bgcolor=bgcolor,**kwargs))
#     chip.add(SolidPline(struct().getPos(),rotation=struct().direction,points=[(gapl+r_out,-gapw/2-r_out),
#                                                                               (gapl+r_out*(1+math.sin(math.radians(theta))),-gapw/2-r_out*(1-math.cos(math.radians(theta)))),
#                                                                               (inside_ptx,-half_width),(0,-half_width),(0,-gapw/2-r_out)],bgcolor=bgcolor,**kwargs))
    
#     if r_out>0:
#         if debug:
#             chip.add(dxf.circle(r_out,struct().getPos((r_out+gapl,gapw/2+r_out)),layer='FRAME',**kwargs))
#             chip.add(dxf.circle(r_out,struct().getPos((r_out+gapl,-gapw/2-r_out)),layer='FRAME',**kwargs))
#         chip.add(CurveRect(struct().getPos((r_out,gapw/2+r_out)), r_out, r_out,ralign=const.TOP,hflip=True,vflip=True,rotation=struct().direction,bgcolor=bgcolor, **kwargs))
#         chip.add(CurveRect(struct().getPos((r_out,-gapw/2-r_out)), r_out, r_out,ralign=const.TOP,hflip=True,rotation=struct().direction,bgcolor=bgcolor, **kwargs))
#         if gapl > 0:
#             chip.add(dxf.rectangle(struct().getPos((r_out,gapw/2)),gapl,r_out,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
#             chip.add(dxf.rectangle(struct().getPos((r_out,-gapw/2)),gapl,-r_out,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
#         chip.add(CurveRect(struct().getPos((r_out+gapl,gapw/2+r_out)), r_out, r_out,ralign=const.TOP,angle=theta,vflip=True,rotation=struct().direction,bgcolor=bgcolor, **kwargs))
#         chip.add(CurveRect(struct().getPos((r_out+gapl,-gapw/2-r_out)), r_out, r_out,ralign=const.TOP,angle=theta,rotation=struct().direction,bgcolor=bgcolor, **kwargs))
    
#     if r_ins>0:
#         if debug:
#             chip.add(dxf.circle(r_ins,struct().getPos((tot_length-r_ins-tabl,half_width-r_ins)),layer='FRAME',**kwargs))
#             chip.add(dxf.circle(r_ins,struct().getPos((tot_length-r_ins-tabl,-half_width+r_ins)),layer='FRAME',**kwargs))
#         chip.add(InsideCurve(struct().getPos((tot_length,half_width)), r_ins, rotation=struct().direction,bgcolor=bgcolor,**kwargs))
#         chip.add(InsideCurve(struct().getPos((tot_length,-half_width)), r_ins, vflip=True,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
        
#         chip.add(InsideCurve(struct().getPos((inside_ptx,half_width)), r_ins,angle=180-theta,hflip=True, rotation=struct().direction,bgcolor=bgcolor,**kwargs))
#         chip.add(InsideCurve(struct().getPos((inside_ptx,-half_width)), r_ins,angle=180-theta,hflip=True, vflip=True,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
    
#     if hflip:
#         struct().shiftPos(tot_length,angle=180)
#     else:
#         struct().shiftPos(tot_length)
def JContact_slot(chip,structure,rotation=0,absoluteDimensions=False,gapw=3,gapl=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5,hflip=False,bgcolor=None,debug=False,**kwargs):
    '''
    Creates shapes forming a negative space puzzle piece slot (tab) with rounded corners, and adjustable angles.
    This version creates two unified polygons for the top and bottom halves to prevent grid-snapping issues.
    No overlap : XOR mode compatible
    Centered on outside midpoint of gap

    gap: {width (gapw),height (gapl),r_out}
    tab: {slot width, (tabw),height (tabl), height offset (taboffs),r_ins}

    by default, absolute dimensions are off, so gap / tab lengths are determined by radii. gapl and tabl will then determine extra space between rounded corners.
    if absolute dimensions are on, then tab / gap lengths are determined only by gapl and tabl.

    set r_ins or r_out to None to inherit defaults from chip/structure
    '''
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,start=structure,direction=rotation)
        else:
            return chip.structure(structure)
            
    # Helper function to generate points for a circular arc
    def _arc(center, radius, start_deg, end_deg, segments=20):
        points = []
        start_rad = math.radians(start_deg)
        end_rad = math.radians(end_deg)
        angle_range = end_rad - start_rad
        for i in range(1, segments + 1): # Start from 1 to not duplicate start point
            angle = start_rad + angle_range * i / segments
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            points.append((x, y))
        return points

    if r_out is None:
        try:
            r_out = struct().defaults['r_out']
        except KeyError:
            r_out = 0
    if r_ins is None:
        try:
            r_ins = struct().defaults['r_ins']
        except KeyError:
            r_ins = 0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()

    tot_length,half_width = JcalcTabDims(chip,structure,gapw,gapl,tabw,tabl,taboffs,r_out,r_ins,absoluteDimensions)

    if absoluteDimensions:
        if gapl >= 2*r_out:
            gapl = gapl-2*r_out
        else:
            print('\x1b[33mWarning:\x1b[0m gap too short in ',chip.chipID,'!')
        if tabl >= 2*r_ins:
            tabl = tabl-2*r_ins
        else:
            print('\x1b[33mWarning:\x1b[0m tab too short in ',chip.chipID,'!')

    if hflip:
        struct().shiftPos(tot_length,angle=180)

    if taboffs==0:
        theta=90
    else:
        theta = math.degrees(math.atan2(
            (r_ins + r_out)*(taboffs + r_ins + r_out)+ abs(tabw)*math.sqrt(max(tabw**2 + taboffs*(taboffs + 2*(r_ins + r_out)),0)),
            tabw*(-r_ins - r_out)+(taboffs + r_ins + r_out)*math.sqrt(max(tabw**2 + taboffs*(taboffs + 2*(r_ins + r_out)),0))*abs(tabw)/tabw))

    # Define key points on the perimeter
    shoulder_pt_top = (gapl + r_out * (1 + math.sin(math.radians(theta))), gapw / 2 + r_out * (1 - math.cos(math.radians(theta))))
    shoulder_pt_bot = (gapl + r_out * (1 + math.sin(math.radians(theta))), -gapw / 2 - r_out * (1 - math.cos(math.radians(theta))))
    inside_ptx = tot_length-tabl-r_ins*(1+math.sin(math.radians(theta))- (1- math.cos(math.radians(theta)))/math.tan(math.radians(theta)))

    # --- Unified Top Half ---
    top_points = []
    top_points.append((0, half_width))
    top_points.append((inside_ptx, half_width))

    if r_ins > 0:
        # This generates the smooth concave lobe from the original's two InsideCurves
        top_points.extend(curveAB(top_points[-1], shoulder_pt_top, clockwise=False, angleDeg=180-theta))
    top_points.append(shoulder_pt_top)

    if r_out > 0:
        # Convex curve on the shoulder
        top_points.extend(curveAB(top_points[-1], (r_out+gapl, gapw/2), clockwise=True, angleDeg=theta))
    if gapl > 0:
        top_points.append((r_out+gapl, gapw/2))
        top_points.append((r_out, gapw/2))
    
    if r_out > 0:
        # Convex curve on the stem
        top_points.extend(curveAB((r_out, gapw/2), (0, gapw/2+r_out), clockwise=True, angleDeg=90))
    top_points.append((0, gapw/2+r_out))
    top_points.append((0, half_width)) # Close path
    chip.add(SolidPline(struct().getPos(), rotation=struct().direction, points=top_points, bgcolor=bgcolor, **kwargStrip(kwargs)))

    # --- Unified Bottom Half ---
    bot_points = []
    bot_points.append((0, -half_width))
    bot_points.append((inside_ptx, -half_width))

    if r_ins > 0:
        # Concave lobe for the bottom half
        bot_points.extend(curveAB(bot_points[-1], shoulder_pt_bot, clockwise=True, angleDeg=180-theta))
    bot_points.append(shoulder_pt_bot)
    
    if r_out > 0:
        # Convex curve on the shoulder
        bot_points.extend(curveAB(bot_points[-1], (r_out+gapl, -gapw/2), clockwise=False, angleDeg=theta))
    if gapl > 0:
        bot_points.append((r_out+gapl, -gapw/2))
        bot_points.append((r_out, -gapw/2))

    if r_out > 0:
        # Convex curve on the stem
        bot_points.extend(curveAB((r_out, -gapw/2), (0, -gapw/2-r_out), clockwise=False, angleDeg=90))
    bot_points.append((0, -gapw/2-r_out))
    bot_points.append((0, -half_width)) # Close path
    chip.add(SolidPline(struct().getPos(), rotation=struct().direction, points=bot_points, bgcolor=bgcolor, **kwargStrip(kwargs)))
    
    if debug:
        # Optional: draw circles to show key radii centers if needed
        pass

    if hflip:
        struct().shiftPos(tot_length,angle=180)
    else:
        struct().shiftPos(tot_length)
# def JContact_slot(chip,structure,rotation=0,absoluteDimensions=False,gapw=3,gapl=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5,hflip=False,bgcolor=None,debug=False,**kwargs):
#     '''
#     Creates shapes forming a negative space puzzle piece slot (tab) with rounded corners, and adjustable angles.
#     This version creates two unified polygons for the top and bottom halves to prevent grid-snapping issues.
#     No overlap : XOR mode compatible
#     Centered on outside midpoint of gap

#     gap: {width (gapw),height (gapl),r_out}
#     tab: {slot width, (tabw),height (tabl), height offset (taboffs),r_ins}

#     by default, absolute dimensions are off, so gap / tab lengths are determined by radii. gapl and tabl will then determine extra space between rounded corners.
#     if absolute dimensions are on, then tab / gap lengths are determined only by gapl and tabl.

#     set r_ins or r_out to None to inherit defaults from chip/structure
#     '''
#     def struct():
#         if isinstance(structure,m.Structure):
#             return structure
#         elif isinstance(structure,tuple):
#             return m.Structure(chip,start=structure,direction=rotation)
#         else:
#             return chip.structure(structure)
#     if r_out is None:
#         try:
#             r_out = struct().defaults['r_out']
#         except KeyError:
#             #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
#             r_out = 0
#     if r_ins is None:
#         try:
#             r_ins = struct().defaults['r_ins']
#         except KeyError:
#             #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
#             r_ins = 0
#     if bgcolor is None:
#         bgcolor = chip.wafer.bg()

#     tot_length,half_width = JcalcTabDims(chip,structure,gapw,gapl,tabw,tabl,taboffs,r_out,r_ins,absoluteDimensions)
#     #determine stem and tab lengths
#     if absoluteDimensions:
#         if gapl >= 2*r_out:
#             gapl = gapl-2*r_out
#         else:
#             print('\x1b[33mWarning:\x1b[0m gap too short in ',chip.chipID,'!')
#         if tabl >= 2*r_ins:
#             tabl = tabl-2*r_ins
#         else:
#             print('\x1b[33mWarning:\x1b[0m tab too short in ',chip.chipID,'!')

#     if hflip:
#         struct().shiftPos(tot_length,angle=180)

#     if taboffs==0:
#         theta=90
#     else:
#         theta = math.degrees(math.atan2(
#             (r_ins + r_out)*(taboffs + r_ins + r_out)+ abs(tabw)*math.sqrt(max(tabw**2 + taboffs*(taboffs + 2*(r_ins + r_out)),0)),
#             tabw*(-r_ins - r_out)+(taboffs + r_ins + r_out)*math.sqrt(max(tabw**2 + taboffs*(taboffs + 2*(r_ins + r_out)),0))*abs(tabw)/tabw))
#     inside_ptx = tot_length-tabl-r_ins*(1+math.sin(math.radians(theta))- (1- math.cos(math.radians(theta)))/math.tan(math.radians(theta)))

#     # --- Unified Top Half ---
#     top_points = []
#     # Start at top-left and trace clockwise
#     top_points.append((0, half_width))
#     top_points.append((inside_ptx, half_width))
#     if r_ins > 0:
#         # Inner corner at the far right
#         top_points.extend(curveAB((inside_ptx, half_width), (tot_length, half_width-r_ins), clockwise=False, angleDeg=90))
#         # Inner corner transitioning to the shoulder
#         top_points.extend(curveAB((tot_length, half_width-r_ins), (gapl+r_out*(1+math.sin(math.radians(theta))),gapw/2+r_out*(1-math.cos(math.radians(theta)))), clockwise=False, angleDeg=180-theta))
#     else:
#         top_points.append((tot_length, half_width))
#         top_points.append((gapl+r_out*(1+math.sin(math.radians(theta))),gapw/2+r_out*(1-math.cos(math.radians(theta)))))

#     # Outer corner on the shoulder
#     if r_out > 0:
#         top_points.extend(curveAB((gapl+r_out*(1+math.sin(math.radians(theta))),gapw/2+r_out*(1-math.cos(math.radians(theta)))), (r_out+gapl, gapw/2), clockwise=True, angleDeg=theta))
#     top_points.append((r_out+gapl, gapw/2))
#     if gapl > 0:
#         top_points.append((r_out, gapw/2))
#     # Outer corner on the stem
#     if r_out > 0:
#         top_points.extend(curveAB((r_out, gapw/2), (0,gapw/2+r_out), clockwise=True, angleDeg=90))
#     top_points.append((0,gapw/2+r_out))
#     top_points.append((0, half_width)) # Close path
#     chip.add(SolidPline(struct().getPos(), rotation=struct().direction, points=top_points, bgcolor=bgcolor, **kwargs))

#     # --- Unified Bottom Half ---
#     bot_points = []
#     # Start at bottom-left and trace clockwise
#     bot_points.append((0, -half_width))
#     bot_points.append((0, -gapw/2-r_out))
#     # Outer corner on the stem
#     if r_out > 0:
#         bot_points.extend(curveAB((0, -gapw/2-r_out), (r_out, -gapw/2), clockwise=True, angleDeg=90))
#     if gapl > 0:
#         bot_points.append((r_out, -gapw/2))
#     bot_points.append((r_out+gapl, -gapw/2))
#     # Outer corner on the shoulder
#     if r_out > 0:
#         bot_points.extend(curveAB((r_out+gapl, -gapw/2), (gapl+r_out*(1+math.sin(math.radians(theta))),-gapw/2-r_out*(1-math.cos(math.radians(theta)))), clockwise=True, angleDeg=theta))

#     if r_ins > 0:
#         # Inner corner transitioning to the shoulder
#         bot_points.extend(curveAB((gapl+r_out*(1+math.sin(math.radians(theta))),-gapw/2-r_out*(1-math.cos(math.radians(theta)))), (tot_length, -half_width+r_ins), clockwise=False, angleDeg=180-theta))
#         # Inner corner at the far right
#         bot_points.extend(curveAB((tot_length, -half_width+r_ins), (inside_ptx, -half_width), clockwise=False, angleDeg=90))
#     else:
#         bot_points.append((gapl+r_out*(1+math.sin(math.radians(theta))),-gapw/2-r_out*(1-math.cos(math.radians(theta)))))
#         bot_points.append((tot_length, -half_width))

#     bot_points.append((inside_ptx, -half_width))
#     bot_points.append((0, -half_width)) # Close path
#     chip.add(SolidPline(struct().getPos(), rotation=struct().direction, points=bot_points, bgcolor=bgcolor, **kwargs))

#     if hflip:
#         struct().shiftPos(tot_length,angle=180)
#     else:
#         struct().shiftPos(tot_length)


    
def JContact_tab(chip,structure,rotation=0,absoluteDimensions=False,stemw=3,steml=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5,hflip=False,bgcolor=None,debug=False,**kwargs):
    '''
    Creates shapes forming a puzzle piece tab with rounded corners, and adjustable angles. 
    No overlap : XOR mode compatible
    Centered on bottom midpoint of stem
    
    stem: {width (stemw),height (steml),r_out}
    tab: {slot width, (tabw),height (tabl), height offset (taboffs),r_ins}
    
    by default, absolute dimensions are off, so stem / tab lengths are determined by radii. steml and tabl will then determine extra space between rounded corners.
    if absolute dimensions are on, then tab / stem lengths are determined only by steml and tabl.
    
    set r_ins or r_out to None to inherit defaults from chip/structure
    '''
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,start=structure,direction=rotation)
        else:
            return chip.structure(structure)
    if r_out is None:
        try:
            r_out = struct().defaults['r_out']
        except KeyError:
            #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            r_out = 0
    if r_ins is None:
        try:
            r_ins = struct().defaults['r_ins']
        except KeyError:
            #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            r_ins = 0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    
    tot_length,half_width = JcalcTabDims(chip,structure,stemw,steml,tabw,tabl,taboffs,r_out,r_ins,absoluteDimensions)
    #determine stem and tab lengths
    if absoluteDimensions:
        if steml >= 2*r_ins:
            steml = steml-2*r_ins
        else:
            print('\x1b[33mWarning:\x1b[0m stem too short in ',chip.chipID,'!')
        if tabl >= 2*r_out:
            tabl = tabl-2*r_out
        else:
            print('\x1b[33mWarning:\x1b[0m tab too short in ',chip.chipID,'!')
    
    if hflip:
        struct().shiftPos(tot_length,angle=180)
    
    if taboffs==0:
        theta=90
    else:
        theta = math.degrees(math.atan2(
            (r_out + r_ins)*(taboffs + r_out + r_ins)+ abs(tabw)*math.sqrt(tabw**2 + taboffs*(taboffs + 2*(r_out + r_ins))),
            tabw*(-r_out - r_ins)+(taboffs + r_out + r_ins)*math.sqrt(tabw**2 + taboffs*(taboffs + 2*(r_out + r_ins)))*abs(tabw)/tabw))
    inside_ptx = r_ins + steml + r_ins*(math.sin(math.radians(theta))- (1- math.cos(math.radians(theta)))/math.tan(math.radians(theta)))
    
    chip.add(SolidPline(struct().getPos(),rotation=struct().direction,points=[(tot_length-tabl-r_out,half_width-r_out),
                                                                              (tot_length-tabl-r_out*(1+math.sin(math.radians(theta))),half_width-r_out*(1-math.cos(math.radians(theta)))),
                                                                              (inside_ptx,stemw/2),(tot_length,stemw/2),(tot_length,half_width-r_out)],bgcolor=bgcolor,**kwargs))
    chip.add(SolidPline(struct().getPos(),rotation=struct().direction,points=[(tot_length-tabl-r_out,-half_width+r_out),
                                                                              (tot_length-tabl-r_out*(1+math.sin(math.radians(theta))),-half_width+r_out*(1-math.cos(math.radians(theta)))),
                                                                              (inside_ptx,-stemw/2),(tot_length,-stemw/2),(tot_length,-half_width+r_out)],bgcolor=bgcolor,**kwargs))
    
    chip.add(dxf.rectangle(struct().getPos(),tot_length,stemw,valign=const.MIDDLE,bgcolor=bgcolor,rotation=struct().direction,**kwargStrip(kwargs)))
    
    if r_out>0:
        if debug:
            chip.add(dxf.circle(r_out,struct().getPos((tot_length-r_out-tabl,half_width-r_out)),layer='FRAME',**kwargs))
            chip.add(dxf.circle(r_out,struct().getPos((tot_length-r_out-tabl,-half_width+r_out)),layer='FRAME',**kwargs))
            
        chip.add(CurveRect(struct().getPos((tot_length-r_out,half_width-r_out)), r_out, r_out,ralign=const.TOP,rotation=struct().direction,bgcolor=bgcolor, **kwargs))
        chip.add(CurveRect(struct().getPos((tot_length-r_out,-half_width+r_out)), r_out, r_out,ralign=const.TOP,vflip=True,rotation=struct().direction,bgcolor=bgcolor, **kwargs))
        if tabl > 0:
            chip.add(dxf.rectangle(struct().getPos((tot_length-r_out,half_width-r_out)),-tabl,r_out,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
            chip.add(dxf.rectangle(struct().getPos((tot_length-r_out,-half_width+r_out)),-tabl,-r_out,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
        chip.add(CurveRect(struct().getPos((2*r_ins + steml + taboffs + r_out,half_width-r_out)), r_out, r_out,ralign=const.TOP,angle=theta,hflip=True,rotation=struct().direction,bgcolor=bgcolor, **kwargs))
        chip.add(CurveRect(struct().getPos((2*r_ins + steml + taboffs + r_out,-half_width+r_out)), r_out, r_out,ralign=const.TOP,angle=theta,hflip=True,vflip=True,rotation=struct().direction,bgcolor=bgcolor, **kwargs))
        
        
    if r_ins>0:
        if debug:
            chip.add(dxf.circle(r_ins,struct().getPos((r_ins+steml,stemw/2+r_ins)),layer='FRAME',**kwargs))
            chip.add(dxf.circle(r_ins,struct().getPos((r_ins+steml,-stemw/2-r_ins)),layer='FRAME',**kwargs))
        chip.add(InsideCurve(struct().getPos((0,stemw/2)), r_ins, hflip=True,vflip=True,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
        chip.add(InsideCurve(struct().getPos((0,-stemw/2)), r_ins, hflip=True,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
        
        chip.add(InsideCurve(struct().getPos((inside_ptx,stemw/2)), r_ins, angle=180-theta,vflip=True,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
        chip.add(InsideCurve(struct().getPos((inside_ptx,-stemw/2)), r_ins, angle=180-theta,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
    
    if hflip:
        struct().shiftPos(0,angle=180)
    else:
        struct().shiftPos(tot_length)
        
    
def JSingleProbePad(chip,pos,padwidth=250,padheight=None,padradius=25,tab=False,tabShoulder = False,tabShoulderWidth=30,tabShoulderLength=80,tabShoulderRadius=None,flipped=False,rotation=0,bgcolor=None,**kwargs):
    '''
    Creates a rectangular pad with rounded corners, and a JContactTab on one end (defaults to right)
    No overlap : XOR mode compatible
    
    Optionally set tabShoulder to True to extend a thinner lead from the main contact pad.
    '''
    def struct():
        if isinstance(pos,m.Structure):
            return pos
        elif isinstance(pos,tuple):
            return m.Structure(chip,start=pos,direction=rotation)
        else:
            return chip.structure(pos)
    if tabShoulderRadius is None:
        try:
            tabShoulderRadius = struct().defaults['r_out']
        except KeyError:
            #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            tabShoulderRadius = 0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    
    if padheight is None:
        padheight=padwidth
        
    if padradius is None:
        try:
            padradius = struct().defaults['r_out']
        except KeyError:
            #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            padradius = 0
    
    tablength,tabhwidth = JcalcTabDims(chip,pos,**kwargs)    
    
    if tab:
        #positive tab
        if not flipped:
            chip.add(RoundRect(struct().start,padwidth,padheight,padradius,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=padwidth)
            if tabShoulder:
                chip.add(RoundRect(struct().start,tabShoulderLength,tabShoulderWidth,tabShoulderRadius,roundCorners=[0,1,1,0],valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=tabShoulderLength)
        JContact_tab(chip,struct(),hflip = flipped,**kwargs)
        if flipped:
            if tabShoulder:
                chip.add(RoundRect(struct().start,tabShoulderLength,tabShoulderWidth,tabShoulderRadius,roundCorners=[1,0,0,1],valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=tabShoulderLength)
            chip.add(RoundRect(struct().start,padwidth,padheight,padradius,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
    else:
        #slot
        if not flipped:
            if tabShoulder:
                chip.add(RoundRect(struct().start,padwidth,padheight,padradius,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=padwidth)
                chip.add(RoundRect(struct().getPos((0,tabhwidth)),tabShoulderLength,tabShoulderWidth/2 - tabhwidth,min(tabShoulderRadius,(tabShoulderWidth/2 - tabhwidth)/2),roundCorners=[0,0,1,0],rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(RoundRect(struct().getPos((0,-tabhwidth)),tabShoulderLength,tabShoulderWidth/2 - tabhwidth,min(tabShoulderRadius,(tabShoulderWidth/2 - tabhwidth)/2),roundCorners=[0,1,0,0],valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(dxf.rectangle(struct().start,tabShoulderLength-tablength,2*tabhwidth,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct(),length=tabShoulderLength-tablength)
            else:
                chip.add(RoundRect(struct().getPos((0,tabhwidth)),padwidth,padheight/2 - tabhwidth,padradius,roundCorners=[0,0,1,1],rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(RoundRect(struct().getPos((0,-tabhwidth)),padwidth,padheight/2 - tabhwidth,padradius,roundCorners=[1,1,0,0],valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(dxf.rectangle(struct().start,padwidth-tablength,2*tabhwidth,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct(),length=padwidth-tablength)
        JContact_slot(chip,struct(),hflip = not flipped,**kwargs)
        if flipped:
            if tabShoulder:
                chip.add(RoundRect(struct().getPos((-tablength,tabhwidth)),tabShoulderLength,tabShoulderWidth/2 - tabhwidth,min(tabShoulderRadius,(tabShoulderWidth/2 - tabhwidth)/2),roundCorners=[0,0,0,1],rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(RoundRect(struct().getPos((-tablength,-tabhwidth)),tabShoulderLength,tabShoulderWidth/2 - tabhwidth,min(tabShoulderRadius,(tabShoulderWidth/2 - tabhwidth)/2),roundCorners=[1,0,0,0],valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(dxf.rectangle(struct().start,tabShoulderLength-tablength,2*tabhwidth,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct(),length=tabShoulderLength-tablength)
                chip.add(RoundRect(struct().start,padwidth,padheight,padradius,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=padwidth)
            else:
                chip.add(RoundRect(struct().getPos((-tablength,tabhwidth)),padwidth,padheight/2 - tabhwidth,padradius,roundCorners=[0,0,1,1],rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(RoundRect(struct().getPos((-tablength,-tabhwidth)),padwidth,padheight/2 - tabhwidth,padradius,roundCorners=[1,1,0,0],valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(dxf.rectangle(struct().start,padwidth-tablength,2*tabhwidth,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
            

def JSingleProbePadLeads(chip,pos,padwidth=250,padheight=None,padradius=25,tab=False,tabShoulder = False,tabShoulderWidth=30,tabShoulderLength=80,tabShoulderRadius=None,flipped=False,rotation=0,bgcolor=None,**kwargs):
    '''
    Creates just a set of leads with rounded corners, and a JContactTab on one end (defaults to right)
    No overlap : XOR mode compatible
    
    Optionally set tabShoulder to True to extend a thinner lead from the main contact pad.
    '''
    def struct():
        if isinstance(pos,m.Structure):
            return pos
        elif isinstance(pos,tuple):
            return m.Structure(chip,start=pos,direction=rotation)
        else:
            return chip.structure(pos)
    if tabShoulderRadius is None:
        try:
            tabShoulderRadius = struct().defaults['r_out']
        except KeyError:
            #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            tabShoulderRadius = 0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    
    if padheight is None:
        padheight=padwidth
        
    if padradius is None:
        try:
            padradius = struct().defaults['r_out']
        except KeyError:
            #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            padradius = 0
    
    tablength,tabhwidth = JcalcTabDims(chip,pos,**kwargs)    
    
    if tab:
        #positive tab
        if not flipped:
            #chip.add(RoundRect(struct().start,padwidth,padheight,padradius,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=padwidth)
            if tabShoulder:
                chip.add(RoundRect(struct().start,tabShoulderLength,tabShoulderWidth,tabShoulderRadius,roundCorners=[0,1,1,0],valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=tabShoulderLength)
        JContact_tab(chip,struct(),hflip = flipped,**kwargs)
        if flipped:
            if tabShoulder:
                chip.add(RoundRect(struct().start,tabShoulderLength,tabShoulderWidth,tabShoulderRadius,roundCorners=[1,0,0,1],valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=tabShoulderLength)
            #chip.add(RoundRect(struct().start,padwidth,padheight,padradius,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
    else:
        #slot
        if not flipped:
            if tabShoulder:
                #chip.add(RoundRect(struct().start,padwidth,padheight,padradius,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=padwidth)
                chip.add(RoundRect(struct().getPos((0,tabhwidth)),tabShoulderLength,tabShoulderWidth/2 - tabhwidth,min(tabShoulderRadius,(tabShoulderWidth/2 - tabhwidth)/2),roundCorners=[0,0,1,0],rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(RoundRect(struct().getPos((0,-tabhwidth)),tabShoulderLength,tabShoulderWidth/2 - tabhwidth,min(tabShoulderRadius,(tabShoulderWidth/2 - tabhwidth)/2),roundCorners=[0,1,0,0],valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(dxf.rectangle(struct().start,tabShoulderLength-tablength,2*tabhwidth,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct(),length=tabShoulderLength-tablength)
            else:
                chip.add(RoundRect(struct().getPos((0,tabhwidth)),padwidth,padheight/2 - tabhwidth,padradius,roundCorners=[0,0,1,1],rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(RoundRect(struct().getPos((0,-tabhwidth)),padwidth,padheight/2 - tabhwidth,padradius,roundCorners=[1,1,0,0],valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                #chip.add(dxf.rectangle(struct().start,padwidth-tablength,2*tabhwidth,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct(),length=padwidth-tablength)
        JContact_slot(chip,struct(),hflip = not flipped,**kwargs)
        if flipped:
            if tabShoulder:
                chip.add(RoundRect(struct().getPos((-tablength,tabhwidth)),tabShoulderLength,tabShoulderWidth/2 - tabhwidth,min(tabShoulderRadius,(tabShoulderWidth/2 - tabhwidth)/2),roundCorners=[0,0,0,1],rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(RoundRect(struct().getPos((-tablength,-tabhwidth)),tabShoulderLength,tabShoulderWidth/2 - tabhwidth,min(tabShoulderRadius,(tabShoulderWidth/2 - tabhwidth)/2),roundCorners=[1,0,0,0],valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(dxf.rectangle(struct().start,tabShoulderLength-tablength,2*tabhwidth,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct(),length=tabShoulderLength-tablength)
                #chip.add(RoundRect(struct().start,padwidth,padheight,padradius,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=struct(),length=padwidth)
            else:
                chip.add(RoundRect(struct().getPos((-tablength,tabhwidth)),padwidth,padheight/2 - tabhwidth,padradius,roundCorners=[0,0,1,1],rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                chip.add(RoundRect(struct().getPos((-tablength,-tabhwidth)),padwidth,padheight/2 - tabhwidth,padradius,roundCorners=[1,1,0,0],valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
                #chip.add(dxf.rectangle(struct().start,padwidth-tablength,2*tabhwidth,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
        

def FlagPads(chip, pos, flagw=1500, flagh=750, flagw2=None, flagh2=None, leadw=100, leadw2=None, leadh=2000, leadh2=None, separation=200, padradius=25,
             tab=False, tabShoulder=False, tabShoulderWidth=30, tabShoulderLength=80, tabShoulderRadius=None,
             flipped=False, rotation=0, bgcolor=None, shunt=False, shunt_width=10, shunt_dist=150, shunt_length=400, shunt_side='left',
             flag_offset=0, flag_offset2=None, **kwargs):
    '''
    Creates a pair of flag-shaped pad with rounded corners, and a JContactTab on one end (defaults to right)
    No overlap : XOR mode compatible

    Optionally set tabShoulder to True to extend a thinner lead from the main contact pad.
    Optionally add a shunt between the pads.

    flag_offset / flag_offset2 : shift the "flag" (wide pad) sideways (um) relative to
        its default flush-left position with the lead, for the top/bottom pad
        respectively (flag_offset2 defaults to flag_offset). 0 (the default) reproduces
        the original flush-left geometry exactly. Not supported together with shunt=True.
    '''
    def struct():
        if isinstance(pos, m.Structure):
            return pos
        elif isinstance(pos, tuple):
            return m.Structure(chip, start=pos, direction=rotation)
        else:
            return chip.structure(pos)

    flagstart = struct().start

    # Ensure default values for flagw2, flagh2, leadw2, and leadh2
    if flagw2 is None:
        flagw2 = flagw
    if flagh2 is None:
        flagh2 = flagh
    if leadw2 is None:
        leadw2 = leadw
    if leadh2 is None:
        leadh2 = leadh

    flagwdiff = flagw2 - flagw
    flaghdiff = flagh2 - flagh
    leadwdiff = leadw2 - leadw
    leadhdiff = leadh2 - leadh

    if flag_offset2 is None:
        flag_offset2 = flag_offset
    if shunt and (flag_offset != 0 or flag_offset2 != 0):
        raise ValueError('FlagPads: flag_offset/flag_offset2 with shunt=True is not implemented')

    if flipped:
        if flag_offset == 0:
            topflag = [
                flagstart,
                (flagstart[0] + leadw, flagstart[1]),
                (flagstart[0] + leadw, flagstart[1] + leadh),
                (flagstart[0] + flagw, flagstart[1] + leadh),
                (flagstart[0] + flagw, flagstart[1] + flagh + leadh),
                (flagstart[0], flagstart[1] + flagh + leadh),
                flagstart
            ]
        else:
            # flag shifted sideways from the lead's flush-left default: needs
            # two extra vertices (lead top-left / flag bottom-left) to trace
            # the step between the (unshifted) lead and the (shifted) flag -
            # at flag_offset==0 those two points coincide, which is why this
            # is a separate branch rather than always-on (a duplicate vertex
            # there would be degenerate geometry).
            topflag = [
                flagstart,
                (flagstart[0] + leadw, flagstart[1]),
                (flagstart[0] + leadw, flagstart[1] + leadh),
                (flagstart[0] + flagw + flag_offset, flagstart[1] + leadh),
                (flagstart[0] + flagw + flag_offset, flagstart[1] + flagh + leadh),
                (flagstart[0] + flag_offset, flagstart[1] + flagh + leadh),
                (flagstart[0] + flag_offset, flagstart[1] + leadh),
                (flagstart[0], flagstart[1] + leadh),
                flagstart
            ]

        if flag_offset2 == 0:
            botflag = [
                (flagstart[0], flagstart[1] - separation),
                (flagstart[0], flagstart[1] - separation - flagh2 - leadh2),
                (flagstart[0] + flagw2, flagstart[1] - separation - flagh2 - leadh2),
                (flagstart[0] + flagw2, flagstart[1] - separation - leadh2),
                (flagstart[0] + leadw2, flagstart[1] - separation - leadh2),
                (flagstart[0] + leadw2, flagstart[1] - separation),
                (flagstart[0], flagstart[1] - separation)
            ]
        else:
            botflag = [
                (flagstart[0], flagstart[1] - separation),
                (flagstart[0], flagstart[1] - separation - leadh2),
                (flagstart[0] + flag_offset2, flagstart[1] - separation - leadh2),
                (flagstart[0] + flag_offset2, flagstart[1] - separation - flagh2 - leadh2),
                (flagstart[0] + flagw2 + flag_offset2, flagstart[1] - separation - flagh2 - leadh2),
                (flagstart[0] + flagw2 + flag_offset2, flagstart[1] - separation - leadh2),
                (flagstart[0] + leadw2, flagstart[1] - separation - leadh2),
                (flagstart[0] + leadw2, flagstart[1] - separation),
                (flagstart[0], flagstart[1] - separation)
            ]

        # Fillet the corners of the top flag
        radius = 20
        if flag_offset == 0:
            p1_top = cornerRound(topflag[0], 3, radius)
            p2_top = cornerRound(topflag[1], 4, radius)
            p3_top = cornerRound(topflag[2], 2, radius, clockwise=False)
            p4_top = cornerRound(topflag[3], 4, radius)
            p5_top = cornerRound(topflag[4], 1, radius)
            p6_top = cornerRound(topflag[5], 2, radius)

            topflag_fillet = p6_top + p5_top + p4_top + p3_top + p2_top + p1_top
        else:
            p1_top = cornerRound(topflag[0], 3, radius)
            p2_top = cornerRound(topflag[1], 4, radius)
            p3_top = cornerRound(topflag[2], 2, radius, clockwise=False)
            p4_top = cornerRound(topflag[3], 4, radius)
            p5_top = cornerRound(topflag[4], 1, radius)
            p6_top = cornerRound(topflag[5], 2, radius)
            p7_top = cornerRound(topflag[6], 3, radius)
            p8_top = cornerRound(topflag[7], 1, radius, clockwise=False)

            topflag_fillet = p8_top + p7_top + p6_top + p5_top + p4_top + p3_top + p2_top + p1_top


        # Fillet the corners of the bottom flag
        if flag_offset2 == 0:
            p1_bot = cornerRound(botflag[0], 2, radius)
            p2_bot = cornerRound(botflag[1], 3, radius)
            p3_bot = cornerRound(botflag[2], 4, radius)
            p4_bot = cornerRound(botflag[3], 1, radius)
            p5_bot = cornerRound(botflag[4], 3, radius, clockwise=False)
            p6_bot = cornerRound(botflag[5], 1, radius)

            botflag_fillet = p6_bot + p5_bot + p4_bot + p3_bot + p2_bot + p1_bot
        else:
            p1_bot = cornerRound(botflag[0], 2, radius)
            p2_bot = cornerRound(botflag[1], 4, radius, clockwise=False)
            p3_bot = cornerRound(botflag[2], 2, radius)
            p4_bot = cornerRound(botflag[3], 3, radius)
            p5_bot = cornerRound(botflag[4], 4, radius)
            p6_bot = cornerRound(botflag[5], 1, radius)
            p7_bot = cornerRound(botflag[6], 3, radius, clockwise=False)
            p8_bot = cornerRound(botflag[7], 1, radius)

            botflag_fillet = p8_bot + p7_bot + p6_bot + p5_bot + p4_bot + p3_bot + p2_bot + p1_bot


        if shunt:
            if shunt_side == 'left':
                shunt_start_x = flagstart[0]
            else:
                shunt_start_x = flagstart[0] + flagw

            shunt_start = (shunt_start_x, flagstart[1] - separation / 2 - shunt_length / 2)
            shunt_end = (shunt_start_x, flagstart[1] - separation / 2 + shunt_length / 2)
     
            shunt_points_inner = [
                shunt_end,
                (shunt_start[0], shunt_end[1]),
                (shunt_start[0]-shunt_dist, shunt_end[1]),
                (shunt_start[0]-shunt_dist, shunt_start[1]),
                shunt_start
            ]
       
            shunt_points_outer = [
                (shunt_start[0], shunt_start[1]-shunt_width),
                (shunt_start[0]-shunt_dist-shunt_width, shunt_start[1]-shunt_width),
                (shunt_end[0]-shunt_dist-shunt_width, shunt_end[1]+shunt_width),
                (shunt_end[0], shunt_end[1]+shunt_width)
            ]

            if tab:
                slotposadjust = JcalcTabDims(chip,struct(),gapw=3,gapl=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5,absoluteDimensions=False,stemw=None,steml=None,**kwargs)
                topslotpos = (flagstart[0] + leadw/2, flagstart[1]+slotposadjust[1])
                slot_points_top = [
                    (flagstart[0] + leadw/2 + slotposadjust[0], flagstart[1]),
                    (flagstart[0] + leadw/2 + slotposadjust[0], flagstart[1]+slotposadjust[1]),
                    (flagstart[0] + leadw/2 - slotposadjust[0], flagstart[1]+slotposadjust[1]),
                    (flagstart[0] + leadw/2 - slotposadjust[0], flagstart[1])
                    ]
                botslotpos = (flagstart[0] + leadw2/2, flagstart[1] - separation)
                slot_points_bot = [
                    (flagstart[0] + leadw2/2 - slotposadjust[0], flagstart[1] - separation),
                    (flagstart[0] + leadw2/2 - slotposadjust[0], flagstart[1] - separation - slotposadjust[1]),
                    (flagstart[0] + leadw2/2 + slotposadjust[0], flagstart[1] - separation - slotposadjust[1]),
                    (flagstart[0] + leadw2/2 + slotposadjust[0], flagstart[1] - separation)
                    ]
                combined_flag = p1_top + shunt_points_inner + p1_bot + slot_points_bot + p6_bot + p5_bot + p4_bot + p3_bot + p2_bot + shunt_points_outer + p6_top + p5_top + p4_top + p3_top + p2_top + slot_points_top
            else:
                combined_flag = p1_top + shunt_points_inner + p1_bot + p6_bot + p5_bot + p4_bot + p3_bot + p2_bot + shunt_points_outer + p6_top + p5_top + p4_top + p3_top + p2_top
    
            chip.add(SolidPline((0, 0), points=combined_flag))
        else:
            if tab:
                slotposadjust = JcalcTabDims(chip,struct(),gapw=3,gapl=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5,absoluteDimensions=False,stemw=None,steml=None,**kwargs)
                topslotpos = (flagstart[0] + leadw/2, flagstart[1]+slotposadjust[1])
                slot_points_top = [
                    (flagstart[0] + leadw/2 + slotposadjust[0], flagstart[1]),
                    (flagstart[0] + leadw/2 + slotposadjust[0], flagstart[1]+slotposadjust[1]),
                    (flagstart[0] + leadw/2 - slotposadjust[0], flagstart[1]+slotposadjust[1]),
                    (flagstart[0] + leadw/2 - slotposadjust[0], flagstart[1])
                    ]
                botslotpos = (flagstart[0] + leadw2/2, flagstart[1] - separation)
                slot_points_bot = [
                    (flagstart[0] + leadw2/2 - slotposadjust[0], flagstart[1] - separation),
                    (flagstart[0] + leadw2/2 - slotposadjust[0], flagstart[1] - separation - slotposadjust[1]),
                    (flagstart[0] + leadw2/2 + slotposadjust[0], flagstart[1] - separation - slotposadjust[1]),
                    (flagstart[0] + leadw2/2 + slotposadjust[0], flagstart[1] - separation)
                    ]
                # combined_flag = p1_top  + p1_bot + slot_points_bot + p6_bot + p5_bot + p4_bot + p3_bot + p2_bot  + p6_top + p5_top + p4_top + p3_top + p2_top + slot_points_top

                # on the top pad the slot points need to be drawn before the last fillet
                if flag_offset == 0:
                    top_flag_pad_points = p6_top + p5_top + p4_top + p3_top + p2_top + slot_points_top + p1_top
                else:
                    top_flag_pad_points = p8_top + p7_top + p6_top + p5_top + p4_top + p3_top + p2_top + slot_points_top + p1_top
                # on the bottom pad the slot points are drawn last
                if flag_offset2 == 0:
                    bot_flag_pad_points = p6_bot + p5_bot + p4_bot + p3_bot + p2_bot + p1_bot + slot_points_bot
                else:
                    bot_flag_pad_points = p8_bot + p7_bot + p6_bot + p5_bot + p4_bot + p3_bot + p2_bot + p1_bot + slot_points_bot
                
            else:
            #     combined_flag = p1_top  + p1_bot + p6_bot + p5_bot + p4_bot + p3_bot + p2_bot  + p6_top + p5_top + p4_top + p3_top + p2_top
                top_flag_pad_points = topflag_fillet
                bot_flag_pad_points = botflag_fillet

            # chip.add(SolidPline((0, 0), points=combined_flag))
            # chip.add(SolidPline((0, 0), points=topflag_fillet))
            # chip.add(SolidPline((0, 0), points=botflag_fillet))

            # if shunt=False then the flag pads need to be drawn separately. Otherwise there will be a connecting line
            chip.add(SolidPline((0, 0), points=top_flag_pad_points))
            chip.add(SolidPline((0, 0), points=bot_flag_pad_points))
        
        if tab:
            # print(struct().getPos((flagw, flagh / 2)))
            # print(flagstart)
            # print(slotpos)
            # testing top/botslotpos assignment
            slotposadjust = JcalcTabDims(chip,struct(),gapw=3,gapl=0.5,tabw=2,tabl=0.5,taboffs=-0.5,r_out=1.5,r_ins=1.5,absoluteDimensions=False,stemw=None,steml=None,**kwargs)
            topslotpos = (flagstart[0] + leadw/2, flagstart[1]+slotposadjust[1])
            botslotpos = (flagstart[0] + leadw2/2, flagstart[1] - separation)
            
            JContact_slot(chip, m.Structure(chip, start=topslotpos, direction=rotation-90), hflip=flipped, rotation=0, **kwargs)
            JContact_slot(chip, m.Structure(chip, start=botslotpos, direction=rotation-90), hflip=not flipped, rotation=0, **kwargs)



            if tabShoulder: #note that this is broken
                chip.add(RoundRect(struct().getPos((-tabShoulderLength, tabShoulderWidth / 2)), tabShoulderLength, tabShoulderWidth / 2, min(tabShoulderRadius, (tabShoulderWidth / 2) / 2), roundCorners=[0, 0, 0, 1], rotation=struct().direction, bgcolor=bgcolor, **kwargs))
                chip.add(RoundRect(struct().getPos((-tabShoulderLength, -tabShoulderWidth / 2)), tabShoulderLength, tabShoulderWidth / 2, min(tabShoulderRadius, (tabShoulderWidth / 2) / 2), roundCorners=[1, 0, 0, 0], valign=const.TOP, rotation=struct().direction, bgcolor=bgcolor, **kwargs))


    else:
        print('You chose not flipped. This is not yet written, sorry.')


def TPads(chip, pos, flagw=1500, flagh=750, flagw2=None, flagh2=None, leadw=100, leadw2=None, leadh=2000, leadh2=None, separation=200,
             flag_offset=0, flag_offset2=None, padradius=20,
             tab=False, tabShoulder=False,
             rotation=0, bgcolor=None, **kwargs):
    '''
    Creates a pair of T-shaped pads with filleted corners, using the same robust
    methodology as the FlagPads function.

    If tab=True, a rectangular notch is cut from the lead and the corresponding
    JContact_slot is created. The geometry is constructed as a single, continuous
    polygon for each pad, with filleted corners on the main body.

    Args:
        chip: The chip object.
        pos: The starting position, can be a tuple or a Structure.
        flagw (float): Width of the top bar of the 'T'.
        flagh (float): Height of the top bar of the 'T'.
        leadw (float): Width of the vertical lead of the 'T'.
        leadh (float): Length of the vertical lead of the 'T'.
        separation (float): The distance between the two pads' leads.
        flag_offset (float): Horizontal offset of the 'T' bar from the lead center.
        padradius (float): Radius for the filleted corners. If 0 or None, corners will be sharp.
        tab (bool): If True, creates a notch for a JContact connection.
        tabShoulder (bool): If True, enables a shoulder feature (currently not implemented).
        rotation (float): Rotation of the entire component in degrees.
        bgcolor: The background color.
        **kwargs: Additional arguments passed to JcalcTabDims for tab sizing.
    '''
    def struct():
        if isinstance(pos, m.Structure):
            return pos
        elif isinstance(pos, tuple):
            return m.Structure(chip, start=pos, direction=rotation)
        else:
            return chip.structure(pos)

    padstart = struct().start

    # Set default values for the second pad to match the first
    if flagw2 is None: flagw2 = flagw
    if flagh2 is None: flagh2 = flagh
    if leadw2 is None: leadw2 = leadw
    if leadh2 is None: leadh2 = leadh
    if flag_offset2 is None: flag_offset2 = flag_offset

    # --- TOP PAD ---
    flag_left_x = padstart[0] + flag_offset - flagw / 2
    flag_right_x = padstart[0] + flag_offset + flagw / 2
    lead_left_x = padstart[0] - leadw / 2
    lead_right_x = padstart[0] + leadw / 2
    lead_bottom_y = padstart[1] + separation / 2
    flag_bottom_y = lead_bottom_y + leadh
    flag_top_y = flag_bottom_y + flagh

    # Define the 8 primary vertices for the T-shape (clockwise from lead bottom-left)
    toppad_verts = [
        (lead_left_x, lead_bottom_y),    # 0
        (lead_right_x, lead_bottom_y),   # 1
        (lead_right_x, flag_bottom_y),   # 2 (Inner corner)
        (flag_right_x, flag_bottom_y),   # 3
        (flag_right_x, flag_top_y),      # 4
        (flag_left_x, flag_top_y),       # 5
        (flag_left_x, flag_bottom_y),    # 6
        (lead_left_x, flag_bottom_y),    # 7 (Inner corner)
    ]

    if padradius and padradius > 0:
        # --- FILLETS ENABLED ---
        if tab:
            slot_len, slot_half_w = JcalcTabDims(chip, struct(), **kwargs)
            notch_width = min(leadw, 2 * slot_half_w)
            
            # Notch vertices ordered to trace the cutout from right to left
            notch_points = [
                (padstart[0] + notch_width/2, lead_bottom_y),      # bottom-right
                (padstart[0] + notch_width/2, lead_bottom_y + slot_len), # top-right
                (padstart[0] - notch_width/2, lead_bottom_y + slot_len), # top-left
                (padstart[0] - notch_width/2, lead_bottom_y),      # bottom-left
            ]
            
            p0 = cornerRound(toppad_verts[0], 3, padradius)
            p1 = cornerRound(toppad_verts[1], 4, padradius)
            p2 = cornerRound(toppad_verts[2], 2, padradius, clockwise=False) # Inner corner
            p3 = cornerRound(toppad_verts[3], 4, padradius)
            p4 = cornerRound(toppad_verts[4], 1, padradius)
            p5 = cornerRound(toppad_verts[5], 2, padradius)
            p6 = cornerRound(toppad_verts[6], 3, padradius)
            p7 = cornerRound(toppad_verts[7], 1, padradius, clockwise=False) # Inner corner

            
            toppad_path = (p7 + p6 + p5 + p4 + p3 + p2 + p1 + notch_points + p0)
            chip.add(SolidPline((0, 0), points=toppad_path, bgcolor=bgcolor, **kwargs))
            JContact_slot(chip, m.Structure(chip, start=(padstart[0], lead_bottom_y), direction=rotation+90), hflip=False, rotation=0, **kwargs)

        else: # No tab, fillet all 8 corners
            p0 = cornerRound(toppad_verts[0], 3, padradius)
            p1 = cornerRound(toppad_verts[1], 4, padradius)
            p2 = cornerRound(toppad_verts[2], 2, padradius, clockwise=False) # Inner corner
            p3 = cornerRound(toppad_verts[3], 4, padradius)
            p4 = cornerRound(toppad_verts[4], 1, padradius)
            p5 = cornerRound(toppad_verts[5], 2, padradius)
            p6 = cornerRound(toppad_verts[6], 3, padradius)
            p7 = cornerRound(toppad_verts[7], 1, padradius, clockwise=False) # Inner corner

            toppad_fillet = p0 + p7 + p6 + p5 + p4 + p3 + p2 + p1
            chip.add(SolidPline((0, 0), points=toppad_fillet, bgcolor=bgcolor, **kwargs))
    else:
        # --- SHARP CORNERS ---
        if tab:
            slot_len, slot_half_w = JcalcTabDims(chip, struct(), **kwargs)
            notch_width = min(leadw, 2 * slot_half_w)
            notch_points = [
                (padstart[0] + notch_width/2, lead_bottom_y),
                (padstart[0] + notch_width/2, lead_bottom_y + slot_len),
                (padstart[0] - notch_width/2, lead_bottom_y + slot_len),
                (padstart[0] - notch_width/2, lead_bottom_y),
            ]
            toppad_path = [toppad_verts[7], toppad_verts[6], toppad_verts[5], toppad_verts[4],
                           toppad_verts[3], toppad_verts[2], toppad_verts[1]] + notch_points + [toppad_verts[0]]
            chip.add(SolidPline((0, 0), points=toppad_path, bgcolor=bgcolor, **kwargs))
            JContact_slot(chip, m.Structure(chip, start=(padstart[0], lead_bottom_y), direction=rotation+90), hflip=True, rotation=0, **kwargs)
        else: # No tab
            chip.add(SolidPline((0, 0), points=toppad_verts, bgcolor=bgcolor, **kwargs))


    # --- BOTTOM PAD ---
    flag_left_x2 = padstart[0] + flag_offset2 - flagw2 / 2
    flag_right_x2 = padstart[0] + flag_offset2 + flagw2 / 2
    lead_left_x2 = padstart[0] - leadw2 / 2
    lead_right_x2 = padstart[0] + leadw2 / 2
    lead_top_y2 = padstart[1] - separation / 2
    flag_top_y2 = lead_top_y2 - leadh2
    flag_bottom_y2 = flag_top_y2 - flagh2

    botpad_verts = [
        (lead_left_x2, lead_top_y2),      # 0
        (lead_right_x2, lead_top_y2),     # 1
        (lead_right_x2, flag_top_y2),     # 2 (Inner corner)
        (flag_right_x2, flag_top_y2),     # 3
        (flag_right_x2, flag_bottom_y2),  # 4
        (flag_left_x2, flag_bottom_y2),   # 5
        (flag_left_x2, flag_top_y2),      # 6
        (lead_left_x2, flag_top_y2),      # 7 (Inner corner)
    ]

    if padradius and padradius > 0:
        # --- FILLETS ENABLED ---
        if tab:
            slot_len, slot_half_w = JcalcTabDims(chip, struct(), **kwargs)
            notch_width = min(leadw2, 2 * slot_half_w)
            
            # Notch vertices ordered to trace the cutout from left to right
            notch_points = [
                (padstart[0] - notch_width/2, lead_top_y2), # top-left
                (padstart[0] - notch_width/2, lead_top_y2 - slot_len), # bottom-left
                (padstart[0] + notch_width/2, lead_top_y2 - slot_len), # bottom-right
                (padstart[0] + notch_width/2, lead_top_y2), # top-right
            ]

            p0 = cornerRound(botpad_verts[0], 2, padradius, clockwise=False)
            p1 = cornerRound(botpad_verts[1], 1, padradius, clockwise=False)
            p2 = cornerRound(botpad_verts[2], 3, padradius)
            p3 = cornerRound(botpad_verts[3], 1, padradius, clockwise=False)
            p4 = cornerRound(botpad_verts[4], 4, padradius, clockwise=False)
            p5 = cornerRound(botpad_verts[5], 3, padradius, clockwise=False)
            p6 = cornerRound(botpad_verts[6], 2, padradius, clockwise=False)
            p7 = cornerRound(botpad_verts[7], 4, padradius)

            botpad_path = (p7 + p6 + p5 + p4 + p3 + p2 + p1 + list(reversed(notch_points)) + p0)
            chip.add(SolidPline((0, 0), points=botpad_path, bgcolor=bgcolor, **kwargs))
            JContact_slot(chip, m.Structure(chip, start=(padstart[0], lead_top_y2), direction=rotation-90), hflip=False, rotation=0, **kwargs)

        else: # No tab
            p0 = cornerRound(botpad_verts[0], 2, padradius, clockwise=False)
            p1 = cornerRound(botpad_verts[1], 1, padradius, clockwise=False)
            p2 = cornerRound(botpad_verts[2], 3, padradius)
            p3 = cornerRound(botpad_verts[3], 1, padradius, clockwise=False)
            p4 = cornerRound(botpad_verts[4], 4, padradius, clockwise=False)
            p5 = cornerRound(botpad_verts[5], 3, padradius, clockwise=False)
            p6 = cornerRound(botpad_verts[6], 2, padradius, clockwise=False)
            p7 = cornerRound(botpad_verts[7], 4, padradius)

            botpad_fillet = p0 + p7 + p6 + p5 + p4 + p3 + p2 + p1
            chip.add(SolidPline((0, 0), points=botpad_fillet, bgcolor=bgcolor, **kwargs))
    else:
        # --- SHARP CORNERS ---
        if tab:
            slot_len, slot_half_w = JcalcTabDims(chip, struct(), **kwargs)
            notch_width = min(leadw2, 2 * slot_half_w)
            notch_points = [
                (padstart[0] - notch_width/2, lead_top_y2),
                (padstart[0] - notch_width/2, lead_top_y2 - slot_len),
                (padstart[0] + notch_width/2, lead_top_y2 - slot_len),
                (padstart[0] + notch_width/2, lead_top_y2),
            ]
            botpad_path = [botpad_verts[7], botpad_verts[6], botpad_verts[5], botpad_verts[4],
                           botpad_verts[3], botpad_verts[2], botpad_verts[1]] + list(reversed(notch_points)) + [botpad_verts[0]]
            chip.add(SolidPline((0, 0), points=botpad_path, bgcolor=bgcolor, **kwargs))
            JContact_slot(chip, m.Structure(chip, start=(padstart[0], lead_top_y2), direction=rotation-90), hflip=False, rotation=0, **kwargs)
        else: # No tab
            chip.add(SolidPline((0, 0), points=botpad_verts, bgcolor=bgcolor, **kwargs))
        
    if tabShoulder:
        print("\x1b[33mWarning:\x1b[0m tabShoulder functionality is not implemented for TPads.")








# def Transmon3DWithShunt(chip, pos, padw=1500, padh=750, padw2=None, padh2=None, leadw=100, leadw2=None, leadh=2000, leadh2=None, separation=200, padradius=20,
#                         tab=False, tabShoulder=False, tabShoulderWidth=30, tabShoulderLength=80, tabShoulderRadius=None,
#                         flipped=False, rotation=0, bgcolor=None, shunt=False, shunt_width=10, shunt_dist=150, shunt_length=400, shunt_side='left', **kwargs):
#     '''
#     Creates a pair of Transmon3D pads with rounded corners, and a JContactTab on one end (defaults to right)
#     No overlap : XOR mode compatible
    
#     Optionally set tabShoulder to True to extend a thinner lead from the main contact pad.
#     Optionally add a shunt between the pads.
#     '''
#     def struct():
#         if isinstance(pos, m.Structure):
#             return pos
#         elif isinstance(pos, tuple):
#             return m.Structure(chip, start=pos, direction=rotation)
#         else:
#             return chip.structure(pos)

#     padstart = struct().start

#     # Ensure default values for padw2, padh2, leadw2, and leadh2
#     if padw2 is None:
#         padw2 = padw
#     if padh2 is None:
#         padh2 = padh
#     if leadw2 is None:
#         leadw2 = leadw
#     if leadh2 is None:
#         leadh2 = leadh

#     if flipped:
#         toppad = [
#             padstart,
#             (padstart[0] + padw, padstart[1]),
#             (padstart[0] + padw, padstart[1] + padh),
#             (padstart[0], padstart[1] + padh),
#             padstart
#         ]

#         botpad = [
#             (padstart[0], padstart[1] - separation),
#             (padstart[0], padstart[1] - separation - padh2),
#             (padstart[0] + padw2, padstart[1] - separation - padh2),
#             (padstart[0] + padw2, padstart[1] - separation),
#             (padstart[0], padstart[1] - separation)
#         ]

#         # Fillet the corners of the top pad
#         radius = padradius
#         p1_top = cornerRound(toppad[0], 3, radius)
#         p2_top = cornerRound(toppad[1], 4, radius)
#         p3_top = cornerRound(toppad[2], 1, radius)#, clockwise=False)
#         p4_top = cornerRound(toppad[3], 2, radius)

#         toppad_fillet = p4_top + p3_top + p2_top + p1_top

#         # Fillet the corners of the bottom pad
#         p1_bot = cornerRound(botpad[0], 2, radius)
#         p2_bot = cornerRound(botpad[1], 3, radius)
#         p3_bot = cornerRound(botpad[2], 4, radius)
#         p4_bot = cornerRound(botpad[3], 1, radius)

#         botpad_fillet = p4_bot + p3_bot + p2_bot + p1_bot

#         if shunt:
#             if shunt_side == 'left':
#                 shunt_start_x = padstart[0]
#             else:
#                 shunt_start_x = padstart[0] + padw

#             shunt_start = (shunt_start_x, padstart[1] - separation / 2 - shunt_length / 2)
#             shunt_end = (shunt_start_x, padstart[1] - separation / 2 + shunt_length / 2)
     
#             shunt_points_inner = [
#                 shunt_end,
#                 (shunt_start[0], shunt_end[1]),
#                 (shunt_start[0]-shunt_dist, shunt_end[1]),
#                 (shunt_start[0]-shunt_dist, shunt_start[1]),
#                 shunt_start
#             ]
       
#             shunt_points_outer = [
#                 (shunt_start[0], shunt_start[1]-shunt_width),
#                 (shunt_start[0]-shunt_dist-shunt_width, shunt_start[1]-shunt_width),
#                 (shunt_end[0]-shunt_dist-shunt_width, shunt_end[1]+shunt_width),
#                 (shunt_end[0], shunt_end[1]+shunt_width)
#             ]

#             combined_pad = p1_top + shunt_points_inner + p1_bot + p4_bot + p3_bot + p2_bot + shunt_points_outer + p4_top + p3_top + p2_top
    
#             chip.add(SolidPline((0, 0), points=combined_pad))
#         else:
#             chip.add(SolidPline((0, 0), points=toppad_fillet))
#             chip.add(SolidPline((0, 0), points=botpad_fillet))

#     else:
#         print('You chose not flipped. This is not yet written, sorry.')
def Transmon3DWithShunt(chip, pos, padw=1500, padh=750, padw2=None, padh2=None, leadw=100, leadw2=None, leadh=2000, leadh2=None, separation=200, padradius=20,
                        tab=False, tab_shift_x=0, tabShoulder=False, tabShoulderWidth=30, tabShoulderLength=80, tabShoulderRadius=None,
                        flipped=False, rotation=0, bgcolor=None, shunt=False, shunt_width=10, shunt_dist=150, shunt_length=400, shunt_side='left', **kwargs):
    '''
    Creates a pair of Transmon3D pads with rounded corners, and a JContactTab on one end (defaults to right)
    No overlap : XOR mode compatible

    Optionally set tabShoulder to True to extend a thinner lead from the main contact pad.
    Optionally add a shunt between the pads.
    tab_shift_x moves the contact tabs/slots right of their default position (leadw/2 from the pad left edge),
    e.g. tab_shift_x=padw/2-leadw/2 centers them on the pads.
    '''

    def struct():
        if isinstance(pos, m.Structure):
            return pos
        elif isinstance(pos, tuple):
            return m.Structure(chip, start=pos, direction=rotation)
        else:
            return chip.structure(pos)

    padstart = struct().start

    # Ensure default values for padw2, padh2, leadw2, and leadh2
    if padw2 is None:
        padw2 = padw
    if padh2 is None:
        padh2 = padh
    if leadw2 is None:
        leadw2 = leadw
    if leadh2 is None:
        leadh2 = leadh

    if flipped:
        toppad = [
            padstart,
            (padstart[0] + padw, padstart[1]),
            (padstart[0] + padw, padstart[1] + padh),
            (padstart[0], padstart[1] + padh),
            padstart
        ]

        botpad = [
            (padstart[0], padstart[1] - separation),
            (padstart[0], padstart[1] - separation - padh2),
            (padstart[0] + padw2, padstart[1] - separation - padh2),
            (padstart[0] + padw2, padstart[1] - separation),
            (padstart[0], padstart[1] - separation)
        ]

        # Fillet the corners of the top pad
        radius = padradius
        p1_top = cornerRound(toppad[0], 3, radius)
        p2_top = cornerRound(toppad[1], 4, radius)
        p3_top = cornerRound(toppad[2], 1, radius)
        p4_top = cornerRound(toppad[3], 2, radius)

        toppad_fillet = p4_top + p3_top + p2_top + p1_top

        # Fillet the corners of the bottom pad
        p1_bot = cornerRound(botpad[0], 2, radius)
        p2_bot = cornerRound(botpad[1], 3, radius)
        p3_bot = cornerRound(botpad[2], 4, radius)
        p4_bot = cornerRound(botpad[3], 1, radius)

        botpad_fillet = p4_bot + p3_bot + p2_bot + p1_bot

        if tab:
            slotposadjust = JcalcTabDims(chip, struct(), gapw=3, gapl=0.5, tabw=2, tabl=0.5, taboffs=-0.5, r_out=1.5, r_ins=1.5, absoluteDimensions=False, stemw=None, steml=None, **kwargs)
            topslotx = padstart[0] + leadw/2 + tab_shift_x
            botslotx = padstart[0] + leadw2/2 + tab_shift_x
            topslotpos = (topslotx, padstart[1] + slotposadjust[1])
            slot_points_top = [
                (topslotx + slotposadjust[0], padstart[1]),
                (topslotx + slotposadjust[0], padstart[1] + slotposadjust[1]),
                (topslotx - slotposadjust[0], padstart[1] + slotposadjust[1]),
                (topslotx - slotposadjust[0], padstart[1])
            ]
            botslotpos = (botslotx, padstart[1] - separation)
            slot_points_bot = [
                (botslotx - slotposadjust[0], padstart[1] - separation),
                (botslotx - slotposadjust[0], padstart[1] - separation - slotposadjust[1]),
                (botslotx + slotposadjust[0], padstart[1] - separation - slotposadjust[1]),
                (botslotx + slotposadjust[0], padstart[1] - separation)
            ]

        if shunt:
            if shunt_side == 'left':
                shunt_start_x = padstart[0]
            else:
                shunt_start_x = padstart[0] + padw

            shunt_start = (shunt_start_x, padstart[1] - separation / 2 - shunt_length / 2)
            shunt_end = (shunt_start_x, padstart[1] - separation / 2 + shunt_length / 2)
     
            shunt_points_inner = [
                shunt_end,
                (shunt_start[0], shunt_end[1]),
                (shunt_start[0]-shunt_dist, shunt_end[1]),
                (shunt_start[0]-shunt_dist, shunt_start[1]),
                shunt_start
            ]
       
            shunt_points_outer = [
                (shunt_start[0], shunt_start[1]-shunt_width),
                (shunt_start[0]-shunt_dist-shunt_width, shunt_start[1]-shunt_width),
                (shunt_end[0]-shunt_dist-shunt_width, shunt_end[1]+shunt_width),
                (shunt_end[0], shunt_end[1]+shunt_width)
            ]

            combined_pad = p1_top + shunt_points_inner + p1_bot + p4_bot + p3_bot + p2_bot + shunt_points_outer + p4_top + p3_top + p2_top

            if tab:
                combined_pad = p1_top + shunt_points_inner + p1_bot + slot_points_bot + p4_bot + p3_bot + p2_bot + shunt_points_outer + p4_top + p3_top + p2_top + slot_points_top

    
            chip.add(SolidPline((0, 0), points=combined_pad, **kwargs))
        else:
            if tab:            
                # on the top pad the slot points need to be drawn before the last fillet
                top_pad_points = p4_top + p3_top + p2_top + slot_points_top + p1_top 
                # on the bottom pad the slot points are drawn last
                bot_pad_points = p4_bot + p3_bot + p2_bot + p1_bot + slot_points_bot
                
            else:
                top_pad_points = toppad_fillet
                bot_pad_points = botpad_fillet

            chip.add(SolidPline((0, 0), points=top_pad_points, **kwargs))
            chip.add(SolidPline((0, 0), points=bot_pad_points, **kwargs))

        if tab:
            slotposadjust = JcalcTabDims(chip, struct(), gapw=3, gapl=0.5, tabw=2, tabl=0.5, taboffs=-0.5, r_out=1.5, r_ins=1.5, absoluteDimensions=False, stemw=None, steml=None, **kwargs)
            topslotpos = (padstart[0] + leadw/2 + tab_shift_x, padstart[1] + slotposadjust[1])
            botslotpos = (padstart[0] + leadw2/2 + tab_shift_x, padstart[1] - separation)

            JContact_slot(chip, m.Structure(chip, start=topslotpos, direction=rotation-90), hflip=flipped, rotation=0, **kwargs)
            JContact_slot(chip, m.Structure(chip, start=botslotpos, direction=rotation-90), hflip=not flipped, rotation=0, **kwargs)

            if tabShoulder: #note that this is broken
                chip.add(RoundRect(struct().getPos((-tabShoulderLength, tabShoulderWidth / 2)), tabShoulderLength, tabShoulderWidth / 2, min(tabShoulderRadius, (tabShoulderWidth / 2) / 2), 
                                   roundCorners=[0, 0, 0, 1], rotation=struct().direction, bgcolor=bgcolor, **kwargs))
                chip.add(RoundRect(struct().getPos((-tabShoulderLength, -tabShoulderWidth / 2)), tabShoulderLength, tabShoulderWidth / 2, min(tabShoulderRadius, (tabShoulderWidth / 2) / 2), 
                roundCorners=[1, 0, 0, 0], valign=const.TOP, rotation=struct().direction, bgcolor=bgcolor, **kwargs))

    else:
        print('You chose not flipped. This is not yet written, sorry.')


def JProbePads(chip,structure,padwidth=250,separation=40,rotation=0,**kwargs):
    #cache the structure locally. needed since we call structure methods (shiftPos) on the structure
    thisStructure = None
    if isinstance(structure,tuple):
        thisStructure = m.Structure(chip,start=structure,direction=rotation)
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return thisStructure
        else:
            return chip.structure(structure)
    #cache start
    pos = struct().start
    struct().shiftPos(-separation/2-padwidth)
    JSingleProbePad(chip,struct(),padwidth=padwidth,flipped=False,**kwargs)
    struct().shiftPos(separation)
    JSingleProbePad(chip,struct(),padwidth=padwidth,flipped=True,**kwargs) 
    struct().updatePos(pos) #shift back to where we started        
    
    
def ManhattanJunction(chip,structure,rotation=0,separation=40,jpadw=20,jpadr=2,jpadh=None,jpadOverhang=5,jpadTaper=0,
                      jfingerw=0.13,jfingerl=5.0,jfingerex=1.0,
                      leadw=2.0,leadr=0.5,
                      ucdist=0.6,
                      JANGLE1=None,JANGLE2=None,
                      JLAYER=None,ULAYER=None,bgcolor=None,**kwargs):
    '''
    Set jpadr to None to use chip-wide defaults (r_out).
    '''
    #cache the structure locally. needed since we call structure methods (shiftPos) on the structure
    thisStructure = None
    if isinstance(structure,tuple):
        thisStructure = m.Structure(chip,start=structure,direction=rotation)
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return thisStructure
        else:
            return chip.structure(structure)
    if jpadr is None:
        try:
            jpadr = struct().defaults['r_out']
        except KeyError:
            #print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            jpadr = 0
    if jpadh is None:
        jpadh = jpadw
    if bgcolor is None: #color for junction, not undercut
        bgcolor = chip.wafer.bg()
    #get layers from wafer
    if JLAYER is None:
        try:
            JLAYER = chip.wafer.JLAYER
        except AttributeError:
            setupJunctionLayers(chip.wafer)
            JLAYER = chip.wafer.JLAYER
    if ULAYER is None:
        try:
            ULAYER = chip.wafer.ULAYER
        except AttributeError:
            setupJunctionLayers(chip.wafer)
            ULAYER = chip.wafer.ULAYER
    
    #cache start position and figure out if we're using structures or not
    '''
    if thisStructure is None:
        #using structures
        struct().shiftPos(separation/2)
    '''
    centerPos = struct().start
    
    if JANGLE2 is None:
        if JANGLE1 is None:
            try:
                JANGLE2 = chip.wafer.JANGLES[1] % 360
                JANGLE1 = chip.wafer.JANGLES[0] % 360
                if (JANGLE1 + 90) % 360 != JANGLE2:
                    #switch angle 1 and 2
                    JANGLE2 = JANGLE1
                    JANGLE1 = JANGLE2-90

            except AttributeError:
                setupManhattanJAngles(chip.wafer)
                JANGLE2 = chip.wafer.JANGLES[1] % 360
                JANGLE1 = chip.wafer.JANGLES[0] % 360
        else:
            JANGLE2 = JANGLE1 % 360
            JANGLE1 = JANGLE2-90
    else:
        JANGLE2 = JANGLE2 % 360
        JANGLE1 = JANGLE2-90
    
    # determine angle of structure relative to junction fingers
    angle = (struct().direction - (JANGLE2 - 90)) % 360
    if angle > 180:
        struct().shiftPos(0,angle=180)
        angle = angle % 180
    rot = math.radians(angle)
    #angle should now be between [0,180)
    if angle <= 45:
        left_top = False
        right_top = True
        right_switch = False
    elif angle <= 90:
        left_top = True
        right_top = False
        right_switch = False
    else:
        left_top = True
        right_top = True
        right_switch = True
    
    # adjust overhang to account for taper
    if jpadTaper > 0:
        jpadOverhang = jpadOverhang + jpadTaper
    
    '''
    # ==================== UNDERCUT LAYER ====================
    # do this first so undercut lines don't obscure junction lines
    '''
    if ucdist > 0:
        # -------------------- junction pads -----------------------
        rot0 = min(max(math.radians(angle),0),math.radians(90))
        rot90 = min(max(math.radians(angle)-math.radians(90),0),math.radians(90))
        
        '''
        = = = = = = = = = = = LEFT LEAD = = = = = = = = = = = = =
        '''
        
        jpadUCL=SolidPline(centerPos,rotation=struct().direction,bgcolor=chip.bg(ULAYER),layer=ULAYER,solidFillQuads=True)
        # - - - - - - - hug pad - - - - - - - 
        if angle < 90:
            if jpadTaper > 0:
                jpadUCL.add_vertex((-separation/2+jpadOverhang-jpadTaper,-jpadh/2))
            else: # corner 1
                jpadUCL.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper-jpadr*(1-math.cos(rot)),-jpadh/2+jpadr*(1-math.sin(rot))),
                                             (-separation/2+jpadOverhang-jpadTaper-jpadr,-jpadh/2),
                                             clockwise=True,angleDeg=90-angle))
        if angle < 180: # corner 2
            jpadUCL.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper-jpadw+jpadr*(1-math.sin(rot90)),-jpadh/2+jpadr*(1-math.cos(rot90))),
                                         (-separation/2+jpadOverhang-jpadTaper-jpadw,-jpadh/2+jpadr),
                                         clockwise=True,angleDeg=min(180-angle,90)))
        
        # corner 3 (this one never goes away)
        jpadUCL.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper-jpadw,jpadh/2-jpadr),
                                     (-separation/2+jpadOverhang-jpadTaper-jpadw+jpadr,jpadh/2),
                                     clockwise=True))
        
        # corner 4
        if angle > 0:
            if jpadTaper >0:
                jpadUCL.add_vertex((-separation/2+jpadOverhang-jpadTaper,jpadh/2))
            else:
                jpadUCL.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper-jpadr,jpadh/2),
                                             (-separation/2+jpadOverhang-jpadTaper-jpadr*(1-math.sin(rot0)),jpadh/2-jpadr*(1-math.cos(rot0))),
                                             clockwise=True,angleDeg=min(angle,90)))
        if jpadTaper <=0:
            if angle > 90:
                jpadUCL.add_vertex((-separation/2+jpadOverhang,
                               -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2+ucdist*max(-math.cos(rot),math.sin(rot))))
            # - - - - - - - extend pad - - - - - -
            
            if angle > 90:
                jpadUCL.add_vertex((-separation/2+jpadOverhang-ucdist*math.cos(rot),
                               -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2+ucdist*max(-math.cos(rot),math.sin(rot))))
        # corner 4
        if angle > 0:
            if jpadTaper >0:
                jpadUCL.add_vertex((-separation/2+jpadOverhang-jpadTaper-ucdist*math.cos(rot),jpadh/2 + ucdist* max(math.sin(rot),-math.cos(rot))))
            else:
                jpadUCL.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper-jpadr*(1-math.sin(rot0))-ucdist*math.cos(rot),jpadh/2 -jpadr*(1-math.cos(rot0)) + ucdist* max(math.sin(rot),-math.cos(rot))),
                                             (-separation/2+jpadOverhang-jpadTaper-jpadr-ucdist*math.cos(rot),jpadh/2 + ucdist* max(math.sin(rot),-math.cos(rot))),
                                             clockwise=False,angleDeg=min(angle,90)))
        
        
        # corner 3 (this one never goes away)
        jpadUCL.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper-jpadw+jpadr + (math.cos(rot)>math.sin(rot) and -ucdist*math.cos(rot) or -ucdist*math.sin(rot)),jpadh/2+ucdist*max(math.sin(rot),-math.cos(rot))),
                                     (-separation/2+jpadOverhang-jpadTaper-jpadw -ucdist*max(math.sin(rot),math.cos(rot)),jpadh/2-jpadr + ucdist*math.sin(rot0)),
                                     clockwise=False))
        if angle < 180: # corner 2
            jpadUCL.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper-jpadw-ucdist*max(math.sin(rot),math.cos(rot)),-jpadh/2+jpadr -ucdist*math.cos(rot)),
                                         (-separation/2+jpadOverhang-jpadTaper-jpadw+jpadr*(1-math.sin(rot90))-ucdist*max(math.sin(rot),math.cos(rot)),-jpadh/2+jpadr*(1-math.cos(rot90))-ucdist*math.cos(rot)),
                                         clockwise=False,angleDeg=min(180-angle,90)))
        
        if angle < 90: 
            if jpadTaper > 0:
                jpadUCL.add_vertex((-separation/2+jpadOverhang-jpadTaper-ucdist*math.sin(rot),-jpadh/2-ucdist*math.cos(rot)))
            else: # corner 1
                jpadUCL.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper-jpadr-ucdist*math.sin(rot),-jpadh/2-ucdist*math.cos(rot)),
                                             (-separation/2+jpadOverhang-jpadTaper-jpadr*(1-math.cos(rot))-ucdist*math.sin(rot),-jpadh/2+jpadr*(1-math.sin(rot))-ucdist*math.cos(rot)),
                                             clockwise=False,angleDeg=90-angle))
        chip.add(jpadUCL)
        
        if angle > 90 and jpadTaper <=0:
            jpadUCL2=SolidPline(centerPos,rotation=struct().direction,bgcolor=chip.bg(ULAYER),layer=ULAYER,solidFillQuads=True)
            # - - - - - - - hug pad - - - - - - -
            jpadUCL2.add_vertex((-separation/2+jpadOverhang,
                       -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2))
            # corner 1
            jpadUCL2.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper,-jpadh/2+jpadr),
                                         (-separation/2+jpadOverhang-jpadTaper-jpadr*(1-math.cos(rot90)),-jpadh/2+jpadr*(1-math.sin(rot90))),
                                             clockwise=True,angleDeg=min(angle-90,90)))
            # - - - - - - - extend pad - - - - - - -
            # corner 1
            jpadUCL2.add_vertices(curveAB((-separation/2+jpadOverhang-jpadTaper-jpadr*(1-math.cos(rot90))-ucdist*math.cos(rot),
                                          -jpadh/2+jpadr*(1-math.sin(rot90))+ucdist*math.sin(rot)),
                                         (-separation/2+jpadOverhang-jpadTaper-ucdist*math.cos(rot),-jpadh/2+jpadr+ucdist*math.sin(rot)),
                                             clockwise=False,angleDeg=min(angle-90,90)))
            jpadUCL2.add_vertex((-separation/2+jpadOverhang-ucdist*math.cos(rot),
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2))
            chip.add(jpadUCL2)
        '''
        = = = = = = = = = = = RIGHT LEAD = = = = = = = = = = = = =
        '''
        
        if (angle < 90 and jpadTaper > 0) or (angle < 180 and jpadTaper <= 0): 
            
            jpadUCR=SolidPline(centerPos,rotation=struct().direction,bgcolor=chip.bg(ULAYER),layer=ULAYER,solidFillQuads=True)
            # - - - - - - - hug pad - - - - - - - 
            if angle < 90: # corner 1
                jpadUCR.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper-jpadr*(1-math.cos(rot)),-jpadh/2+jpadr*(1-math.sin(rot))),
                                             (jpadw+separation/2-jpadOverhang+jpadTaper-jpadr,-jpadh/2),
                                             clockwise=True,angleDeg=90-angle))
            if jpadTaper > 0:
                if angle < 90:
                    jpadUCR.add_vertex((jpadw+separation/2-jpadOverhang+jpadTaper-jpadw,-jpadh/2))
            elif angle < 180: # corner 2
                jpadUCR.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper-jpadw+jpadr*(1-math.sin(rot90)),-jpadh/2+jpadr*(1-math.cos(rot90))),
                                             (jpadw+separation/2-jpadOverhang+jpadTaper-jpadw,-jpadh/2+jpadr),
                                             clockwise=True,angleDeg=min(180-angle,90)))
            if jpadTaper <=0:
                if right_top:
                    # j finger stems from top of right lead
                    if not right_switch:
                        # angle is 0-45 deg
                        jpadUCR.add_vertices([(separation/2-jpadOverhang,
                                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),
                                              (separation/2-jpadOverhang-ucdist*math.cos(rot),
                                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2-ucdist*math.cos(rot))])
                    else:
                        # angle is 91-180 deg
                        jpadUCR.add_vertices([
                            (separation/2-jpadOverhang,
                                           (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2),
                            (separation/2-jpadOverhang-ucdist*math.sin(rot),
                                           (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2)
                            ])
                else:
                    # angle is 46-90 deg
                    jpadUCR.add_vertices([(separation/2-jpadOverhang,
                                       (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),
                                          (separation/2-jpadOverhang-ucdist*math.sin(rot),
                                       (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot))
                                          ])
            # - - - - - - - extend pad - - - - - -
            
            if jpadTaper > 0:
                if angle < 90:
                    jpadUCR.add_vertex((jpadw+separation/2-jpadOverhang+jpadTaper-jpadw-ucdist*max(math.sin(rot),math.cos(rot)),-jpadh/2 -ucdist*math.cos(rot)))
            elif angle < 180: # corner 2
                jpadUCR.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper-jpadw-ucdist*max(math.sin(rot),math.cos(rot)),-jpadh/2+jpadr -ucdist*math.cos(rot)),
                                             (jpadw+separation/2-jpadOverhang+jpadTaper-jpadw+jpadr*(1-math.sin(rot90))-ucdist*max(math.sin(rot),math.cos(rot)),-jpadh/2+jpadr*(1-math.cos(rot90))-ucdist*math.cos(rot)),
                                             clockwise=False,angleDeg=min(180-angle,90)))
            
            if angle < 90: # corner 1
                jpadUCR.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper-jpadr-ucdist*math.sin(rot),-jpadh/2-ucdist*math.cos(rot)),
                                             (jpadw+separation/2-jpadOverhang+jpadTaper-jpadr*(1-math.cos(rot))-ucdist*math.sin(rot),-jpadh/2+jpadr*(1-math.sin(rot))-ucdist*math.cos(rot)),
                                             clockwise=False,angleDeg=90-angle))
            chip.add(jpadUCR)
            
        if (jpadTaper > 0 and angle > 0) or jpadTaper <= 0:
            jpadUCR2=SolidPline(centerPos,rotation=struct().direction,bgcolor=chip.bg(ULAYER),layer=ULAYER,solidFillQuads=True)
            # - - - - - - - hug pad - - - - - - - 
            if jpadTaper >0:
                if angle > 0:
                    jpadUCR2.add_vertex((separation/2-jpadOverhang+jpadTaper,jpadh/2))
            else:
                if right_top:
                    # j finger stems from top of right lead
                    if not right_switch:
                        # angle is 0-45 deg
                        jpadUCR2.add_vertex((separation/2-jpadOverhang,
                                           -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)))
                    else:
                        # angle is 91-180 deg
                        jpadUCR2.add_vertex((separation/2-jpadOverhang,
                                           (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2+ucdist*max(math.sin(rot),-math.cos(rot))))
                else:
                    # angle is 46-90 deg
                    jpadUCR2.add_vertex((separation/2-jpadOverhang,
                                       (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)))
                    
                # corner 3 (this one never goes away)
                jpadUCR2.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper-jpadw,jpadh/2-jpadr),
                                             (jpadw+separation/2-jpadOverhang+jpadTaper-jpadw+jpadr,jpadh/2),
                                             clockwise=True))
            
            # corner 4
            if angle > 0:
                jpadUCR2.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper-jpadr,jpadh/2),
                                                 (jpadw+separation/2-jpadOverhang+jpadTaper-jpadr*(1-math.sin(rot0)),jpadh/2-jpadr*(1-math.cos(rot0))),
                                                 clockwise=True,angleDeg=min(angle,90)))
            
            # corner 1
            if angle >90:
                jpadUCR2.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper,-jpadh/2+jpadr),
                                             (jpadw+separation/2-jpadOverhang+jpadTaper-jpadr*(1-math.cos(rot90)),-jpadh/2+jpadr*(1-math.sin(rot90))),
                                                 clockwise=True,angleDeg=min(angle-90,90)))
                # - - - - - - - extend pad - - - - - - -
                # corner 1
                jpadUCR2.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper-jpadr*(1-math.cos(rot90))-ucdist*math.cos(rot),
                                              -jpadh/2+jpadr*(1-math.sin(rot90))+ucdist*math.sin(rot)),
                                             (jpadw+separation/2-jpadOverhang+jpadTaper-ucdist*math.cos(rot),-jpadh/2+jpadr+ucdist*math.sin(rot)),
                                                 clockwise=False,angleDeg=min(angle-90,90)))
            
            # corner 4
            if angle > 0:
                jpadUCR2.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper-jpadr*(1-math.sin(rot0))-ucdist*math.cos(rot),jpadh/2 -jpadr*(1-math.cos(rot0)) + ucdist* max(math.sin(rot),-math.cos(rot))),
                                                 (jpadw+separation/2-jpadOverhang+jpadTaper-jpadr-ucdist*math.cos(rot),jpadh/2 + ucdist* max(math.sin(rot),-math.cos(rot))),
                                                 clockwise=False,angleDeg=min(angle,90)))
            
            
            if jpadTaper >0:
                if angle > 0:
                    jpadUCR2.add_vertex((separation/2-jpadOverhang+jpadTaper+ (math.cos(rot)>math.sin(rot) and -ucdist*math.cos(rot) or -ucdist*math.sin(rot)),jpadh/2+ucdist*max(math.sin(rot),-math.cos(rot))))
            else:
                # corner 3 (this one never goes away)
                jpadUCR2.add_vertices(curveAB((jpadw+separation/2-jpadOverhang+jpadTaper-jpadw+jpadr + (math.cos(rot)>math.sin(rot) and -ucdist*math.cos(rot) or -ucdist*math.sin(rot)),jpadh/2+ucdist*max(math.sin(rot),-math.cos(rot))),
                                             (jpadw+separation/2-jpadOverhang+jpadTaper-jpadw -ucdist*max(math.sin(rot),math.cos(rot)),jpadh/2-jpadr + ucdist*math.sin(rot0)),
                                             clockwise=False))
                if right_top:
                    # j finger stems from top of right lead
                    if not right_switch:
                        # angle is 0-45 deg
                        jpadUCR2.add_vertex((separation/2-jpadOverhang-ucdist*math.cos(rot),
                                           -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)))
                    else:
                        # angle is 91-180 deg
                        jpadUCR2.add_vertex((separation/2-jpadOverhang-ucdist*math.sin(rot),
                                           (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2+ucdist*max(math.sin(rot),-math.cos(rot))))
                else:
                    # angle is 46-90 deg
                    jpadUCR2.add_vertex((separation/2-jpadOverhang-ucdist*math.sin(rot),
                                       (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)))
                    
            chip.add(jpadUCR2)


        # -------------------- junction taper ----------------------
        
        if jpadTaper >0:
            # left taper
            if left_top:
                l_tap_rot_0 = math.atan(jpadTaper/(jpadh/2-(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2))
                l_tap_rot_1 = math.atan(jpadTaper/(jpadh/2+(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2))
                
                if  l_tap_rot_0 > rot: # bottom angle 2
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((-separation/2+jpadOverhang-ucdist*math.sin(rot),
                                   -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang-jpadTaper-ucdist*math.sin(rot),-jpadh/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang-jpadTaper,-jpadh/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                elif angle < 90:
                    # bottom angle 2
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((-separation/2+jpadOverhang-ucdist*math.cos(rot)*math.tan(l_tap_rot_0),
                                   -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                if l_tap_rot_1 > math.pi/2 - rot:
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((-separation/2+jpadOverhang-ucdist*math.cos(rot),
                                   -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2+ucdist*max(math.sin(rot),-math.cos(rot))),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2+ucdist*max(math.sin(rot),-math.cos(rot))),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang-jpadTaper,jpadh/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang-jpadTaper-ucdist*math.cos(rot),jpadh/2+ucdist*max(math.sin(rot),-math.cos(rot))),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                else:
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((-separation/2+jpadOverhang-ucdist*math.sin(rot)*math.tan(l_tap_rot_1),
                                   -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                    
            else:
                l_tap_rot_0 = math.atan(jpadTaper/(jpadh/2+(jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2))
                l_tap_rot_1 = math.atan(jpadTaper/(jpadh/2-(jfingerl-jfingerex)*math.cos(rot)-leadw-jfingerw*math.sin(rot)/2))
                #print('taper angle ',math.degrees(l_tap_rot_1),',@',90-angle)
                if  l_tap_rot_0 > rot: # bottom angle 2
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((-separation/2+jpadOverhang-ucdist*math.sin(rot),
                                   (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang-jpadTaper-ucdist*math.sin(rot),-jpadh/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang-jpadTaper,-jpadh/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))     
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                elif angle < 90:
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((-separation/2+jpadOverhang-ucdist*math.cos(rot)*math.tan(l_tap_rot_0),
                                   (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))     
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                if l_tap_rot_1 > math.pi/2 - rot:
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((-separation/2+jpadOverhang-ucdist*math.cos(rot),
                                   (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang-jpadTaper,jpadh/2),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang-jpadTaper-ucdist*math.cos(rot),jpadh/2+ucdist*math.sin(rot)),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                elif angle > 0:
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((-separation/2+jpadOverhang-ucdist*math.sin(rot)*math.tan(l_tap_rot_1),
                                   (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                        rotate_2d((-separation/2+jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
            
            # right taper
            if right_top:
                if not right_switch:
                    # angle is 0-45 deg
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((separation/2-jpadOverhang,
                               -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang,
                               -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang+jpadTaper,-jpadh/2),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang+jpadTaper-ucdist*math.cos(rot),-jpadh/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang-ucdist*math.cos(rot),
                               -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                    if angle > 0:
                        chip.add(SolidPline(centerPos, points=[
                            rotate_2d((separation/2-jpadOverhang,
                                       -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang,
                                       -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper,jpadh/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper-ucdist*math.cos(rot),jpadh/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang-ucdist*math.cos(rot),
                                       -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction))
                            ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                    else:
                        chip.add(SolidPline(centerPos, points=[
                            rotate_2d((separation/2-jpadOverhang-ucdist*math.cos(rot),
                                       -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang,
                                       -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper,jpadh/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper-ucdist*math.cos(rot),jpadh/2+ucdist*math.sin(rot)),math.radians(struct().direction))
                            ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                else:
                    # angle is 91-180 deg
                    r_tap_rot_0 = math.atan(jpadTaper/(jpadh/2 + (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2))
                    
                    if math.degrees(r_tap_rot_0) + angle < 180 and angle < 180:
                        chip.add(SolidPline(centerPos, points=[
                            rotate_2d((separation/2-jpadOverhang-ucdist*(math.sin(rot)+math.cos(rot)*math.tan(r_tap_rot_0)),
                                       (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang,
                                       (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper,-jpadh/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper-ucdist*math.sin(rot),-jpadh/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                            ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                    if angle < 180:
                        chip.add(SolidPline(centerPos, points=[
                            rotate_2d((separation/2-jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2+ucdist*max(math.sin(rot),-math.cos(rot))),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper,jpadh/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper-ucdist*math.sin(rot),jpadh/2+ucdist*max(math.sin(rot),-math.cos(rot))),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang-ucdist*math.sin(rot),
                               (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2+ucdist*max(math.sin(rot),-math.cos(rot))),math.radians(struct().direction))
                            ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                    else:
                        chip.add(SolidPline(centerPos, points=[
                            rotate_2d((separation/2-jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2+ucdist*max(math.sin(rot),-math.cos(rot))),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper,jpadh/2),math.radians(struct().direction)),
                            rotate_2d((separation/2-jpadOverhang+jpadTaper-ucdist*math.sin(rot),jpadh/2+ucdist*max(math.sin(rot),-math.cos(rot))),math.radians(struct().direction))
                            ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
            else:
                # angle is 46 - 90 deg
                if angle < 90:
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((separation/2-jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang+jpadTaper,-jpadh/2),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang+jpadTaper-ucdist*math.sin(rot),-jpadh/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang-ucdist*math.sin(rot),
                                   (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                else:
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((separation/2-jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang+jpadTaper,-jpadh/2),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang+jpadTaper-ucdist*math.sin(rot),-jpadh/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang-ucdist*math.sin(rot),
                                   (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d((separation/2-jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang+jpadTaper,jpadh/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang+jpadTaper-ucdist*math.sin(rot),jpadh/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang-ucdist*math.sin(rot),
                               (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                    
                    ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                
                
        # -------------------- junction fingers --------------------
        chip.add(dxf.rectangle(vadd(centerPos,rotate_2d((-jfingerex,0),#rotate about center
                                                        math.radians(JANGLE2))), jfingerex<=0 and 2*jfingerex or -ucdist, min(3*jfingerw,2*jfingerex), rotation=JANGLE2,
                               valign=const.MIDDLE,layer=ULAYER,bgcolor=chip.bg(ULAYER),**kwargStrip(kwargs)))
        if jfingerex >0:
            chip.add(dxf.rectangle(vadd(centerPos,rotate_2d((-jfingerex,0),#rotate about center
                                                            math.radians(JANGLE1))), -ucdist, min(3*jfingerw,2*jfingerex), rotation=JANGLE1,
                                   valign=const.MIDDLE,layer=ULAYER,bgcolor=chip.bg(ULAYER),**kwargStrip(kwargs)))
            
        # -------------------- junction leads ---------------------
        if left_top: 
            # j finger stems from top of left lead
            # angle is 46-180 deg
            if angle < 180:
                # ANGLE 1 undercut
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d((-separation/2+jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                    rotate_2d((jfingerl-jfingerex,-jfingerw/2),math.radians(JANGLE1)),
                    rotate_2d((jfingerl-jfingerex-ucdist,-jfingerw/2),math.radians(JANGLE1)),
                    rotate_2d((-separation/2+jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction))
                    ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
            if math.sin(rot) < -math.cos(rot):
                # ANGLE 2 undercut
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d((jfingerl-jfingerex,-jfingerw/2-ucdist),math.radians(JANGLE1)),
                    rotate_2d((jfingerl-jfingerex,-jfingerw/2+ucdist*math.tan(rot)),math.radians(JANGLE1)),
                    rotate_2d((-separation/2+jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                    rotate_2d((-separation/2+jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                    ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
            if angle <90:
                # ANGLE 2 undercut
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d(((jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                    rotate_2d((-separation/2+jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                    rotate_2d((-separation/2+jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                    rotate_2d(((jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2-ucdist*math.sin(rot),
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                    ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
            elif angle > 90:
                # ANGLE 1 undercut
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE1)),
                    rotate_2d((jfingerl-jfingerex-ucdist,jfingerw/2),math.radians(JANGLE1)),
                    rotate_2d(((jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2 - ucdist*math.cos(rot),
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2 + ucdist*math.sin(rot)),math.radians(struct().direction)),
                    rotate_2d(((jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2),math.radians(struct().direction))
                    ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
        else:# angle is 0-45 deg
            # j finger stems from bottom of left lead
            if angle > 0:
                # ANGLE 1 undercut
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d((-separation/2+jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                    rotate_2d((-separation/2+jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                    rotate_2d(((jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2-ucdist*math.cos(rot),
                               (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                    rotate_2d(((jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2,
                               (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction))
                    ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
            # ANGLE 2 undercut
            chip.add(SolidPline(centerPos, points=[
                rotate_2d((-separation/2+jpadOverhang,
                           (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE2)),
                rotate_2d((jfingerl-jfingerex-ucdist,jfingerw/2),math.radians(JANGLE2)),
                rotate_2d((-separation/2+jpadOverhang,
                           (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2- ucdist*math.cos(rot)),math.radians(struct().direction))
                ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
        
        if right_top:
            # j finger stems from top of right lead
            if not right_switch:
                # JANGLE1 is our finger
                # angle is 0-45 deg
                
                # ANGLE 1 undercut
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d((jfingerl-jfingerex-ucdist,-jfingerw/2),math.radians(JANGLE1)),
                    rotate_2d((jfingerl-jfingerex,-jfingerw/2),math.radians(JANGLE1)),
                    rotate_2d(((jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2,
                               -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                    rotate_2d(((jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot),
                               -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction))
                    ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                if angle > 0:
                    # ANGLE 1 undercut
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((jfingerl-jfingerex-ucdist,jfingerw/2),math.radians(JANGLE1)),
                        rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE1)),
                        rotate_2d((separation/2-jpadOverhang,
                               -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang,
                               -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                # ANGLE 2 undercut
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d(((jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                    rotate_2d(((jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2-ucdist*math.sin(rot),
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                    rotate_2d(((jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)*math.tan(rot),
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2+ucdist*math.sin(rot)*math.tan(rot)),math.radians(struct().direction))
                    ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
            else:
                # JANGLE2 is our finger
                # angle is 91-180 deg
                if angle < 180:
                    # ANGLE 2 undercut
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((jfingerl-jfingerex,-jfingerw/2),math.radians(JANGLE2)),
                        rotate_2d((jfingerl-jfingerex-ucdist,-jfingerw/2),math.radians(JANGLE2)),
                        rotate_2d(((jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2-ucdist*math.sin(rot),
                               (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d(((jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2,
                               (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                if angle > 90:
                    # ANGLE 2 undercut
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE2)),
                        rotate_2d((jfingerl-jfingerex-ucdist,jfingerw/2),math.radians(JANGLE2)),
                        rotate_2d((separation/2-jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((separation/2-jpadOverhang,
                                   (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
                if math.sin(rot)>-math.cos(rot):
                    # ANGLE 1 undercut
                    chip.add(SolidPline(centerPos, points=[
                        rotate_2d((separation/2-jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction)),
                        rotate_2d((jfingerl-jfingerex,jfingerw/2-ucdist/math.tan(rot)),math.radians(JANGLE2)),
                        rotate_2d((jfingerl-jfingerex,jfingerw/2+ucdist),math.radians(JANGLE2)),
                        rotate_2d((separation/2-jpadOverhang,
                               (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction))
                        ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
        else:
            # j finger stems from bottom of right lead
            # JANGLE2 is our finger
            # angle is 46-90 deg
            if angle < 90:
                # ANGLE 2 undercut
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d((jfingerl-jfingerex-ucdist,-jfingerw/2),math.radians(JANGLE2)),
                    rotate_2d((jfingerl-jfingerex,-jfingerw/2),math.radians(JANGLE2)),
                    rotate_2d((separation/2-jpadOverhang,
                       (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang,
                       (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                    ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
            # ANGLE 2 undercut
            chip.add(SolidPline(centerPos, points=[
                rotate_2d((jfingerl-jfingerex-ucdist,jfingerw/2),math.radians(JANGLE2)),
                rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE2)),
                rotate_2d(((jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2,
                           (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                rotate_2d(((jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2-ucdist*math.sin(rot),
                           (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)),math.radians(struct().direction))
                ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
            # ANGLE 1 undercut
            chip.add(SolidPline(centerPos, points=[
                rotate_2d(((jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2,
                           (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                rotate_2d((separation/2-jpadOverhang,
                           (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                rotate_2d((separation/2-jpadOverhang,
                           (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                rotate_2d(((jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2-ucdist*math.cos(rot),
                           (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2+ucdist*math.sin(rot)),math.radians(struct().direction)),
                rotate_2d(((jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2-ucdist*math.sin(rot)/math.tan(rot),
                           (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2-ucdist*math.cos(rot)/math.tan(rot)),math.radians(struct().direction))
                ],bgcolor=chip.bg(ULAYER),layer=ULAYER))
        
    '''
    # ==================== JUNCTION LAYER ====================
    '''
    
    # -------------------- junction pads --------------------
    
    chip.add(RoundRect(struct().getPos((-separation/2+jpadOverhang-jpadTaper,0)),jpadw,jpadh,jpadr,roundCorners = (jpadTaper > 0) and [1,0,0,1] or [1,1,1,1],
                       valign=const.MIDDLE,halign=const.RIGHT,rotation=struct().direction,bgcolor=bgcolor,layer=JLAYER,**kwargs))
    chip.add(RoundRect(struct().getPos((separation/2-jpadOverhang+jpadTaper,0)),jpadw,jpadh,jpadr,roundCorners = (jpadTaper > 0) and [0,1,1,0] or [1,1,1,1],
                       valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,layer=JLAYER,**kwargs))
    
    # -------------------- junction fingers --------------------
    
    chip.add(dxf.rectangle(vadd(centerPos,rotate_2d((-jfingerex,0),#rotate about center
                                                    math.radians(JANGLE2))), jfingerl, jfingerw, rotation=JANGLE2,
                           valign=const.MIDDLE,layer=JLAYER,bgcolor=bgcolor,**kwargStrip(kwargs)))
    if jfingerex >0:
        chip.add(dxf.rectangle(vadd(centerPos,rotate_2d((-jfingerex,0),#rotate about center
                                                        math.radians(JANGLE1))), jfingerex-jfingerw/2, jfingerw, rotation = JANGLE1,
                               valign=const.MIDDLE,layer=JLAYER,bgcolor=bgcolor,**kwargStrip(kwargs)))
    chip.add(dxf.rectangle(vadd(centerPos,rotate_2d((max(jfingerw/2,-jfingerex),0),#rotate about center
                                                    math.radians(JANGLE1))), min(jfingerl-jfingerex-jfingerw/2,jfingerl), jfingerw, rotation = JANGLE1,
                           valign=const.MIDDLE,layer=JLAYER,bgcolor=bgcolor,**kwargStrip(kwargs)))
    
    # -------------------- junction leads --------------------    
    if left_top:
        # j finger stems from top of left lead
        chip.add(SolidPline(centerPos, points=[
            rotate_2d((-separation/2+jpadOverhang,
                       -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
            rotate_2d(((jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2,
                       -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
            rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE1)),
            rotate_2d((jfingerl-jfingerex,-jfingerw/2),math.radians(JANGLE1)),
            rotate_2d((-separation/2+jpadOverhang,
                       -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2),math.radians(struct().direction))
            ],bgcolor=bgcolor,layer=JLAYER))
        if jpadTaper > 0:
            chip.add(SolidPline(centerPos, points=[
                rotate_2d((-separation/2+jpadOverhang-jpadTaper,jpadh/2),math.radians(struct().direction)),
                rotate_2d((-separation/2+jpadOverhang-jpadTaper,-jpadh/2),math.radians(struct().direction)),
                rotate_2d((-separation/2+jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw-jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                rotate_2d((-separation/2+jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2),math.radians(struct().direction))
                ],bgcolor=bgcolor,layer=JLAYER))
    else:
        # j finger stems from bottom of left lead
        chip.add(SolidPline(centerPos, points=[
            rotate_2d((-separation/2+jpadOverhang,
                       (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
            rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE2)),
            rotate_2d((jfingerl-jfingerex,-jfingerw/2),math.radians(JANGLE2)),
            rotate_2d(((jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2,
                       (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
            rotate_2d((-separation/2+jpadOverhang,
                       (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction))
            ],bgcolor=bgcolor,layer=JLAYER))
        if jpadTaper > 0:
            chip.add(SolidPline(centerPos, points=[
                rotate_2d((-separation/2+jpadOverhang-jpadTaper,jpadh/2),math.radians(struct().direction)),
                rotate_2d((-separation/2+jpadOverhang-jpadTaper,-jpadh/2),math.radians(struct().direction)),
                rotate_2d((-separation/2+jpadOverhang,
                       (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                rotate_2d((-separation/2+jpadOverhang,
                       (jfingerl-jfingerex)*math.cos(rot)+leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction))
                ],bgcolor=bgcolor,layer=JLAYER))
    
    if right_top:
        # j finger stems from top of right lead
        if not right_switch:
            # JANGLE1 is our finger
            chip.add(SolidPline(centerPos, points=[
                rotate_2d((separation/2-jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                rotate_2d(((jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                rotate_2d((jfingerl-jfingerex,-jfingerw/2),math.radians(JANGLE1)),
                rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE1)),
                rotate_2d((separation/2-jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2),math.radians(struct().direction))
                ],bgcolor=bgcolor,layer=JLAYER))
            if jpadTaper > 0:
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d((separation/2-jpadOverhang+jpadTaper,jpadh/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang+jpadTaper,-jpadh/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)-leadw+jfingerw*math.cos(rot)/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang,
                           -(jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2),math.radians(struct().direction))
                    ],bgcolor=bgcolor,layer=JLAYER))
        else:
            # JANGLE2 is our finger
            chip.add(SolidPline(centerPos, points=[
                rotate_2d((separation/2-jpadOverhang,
                           (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                rotate_2d(((jfingerl-jfingerex)*math.sin(rot)+jfingerw*math.cos(rot)/2,
                           (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                rotate_2d((jfingerl-jfingerex,-jfingerw/2),math.radians(JANGLE2)),
                rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE2)),
                rotate_2d((separation/2-jpadOverhang,
                           (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction))
                ],bgcolor=bgcolor,layer=JLAYER))
            if jpadTaper > 0:
                chip.add(SolidPline(centerPos, points=[
                    rotate_2d((separation/2-jpadOverhang+jpadTaper,jpadh/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang+jpadTaper,-jpadh/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang,
                           (jfingerl-jfingerex)*math.cos(rot)-leadw+jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                    rotate_2d((separation/2-jpadOverhang,
                           (jfingerl-jfingerex)*math.cos(rot)+jfingerw*math.sin(rot)/2),math.radians(struct().direction))
                    ],bgcolor=bgcolor,layer=JLAYER))
    else:
        # j finger stems from bottom of right lead
        # JANGLE2 is our finger
        chip.add(SolidPline(centerPos, points=[
            rotate_2d((separation/2-jpadOverhang,
                       (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
            rotate_2d(((jfingerl-jfingerex)*math.sin(rot)-jfingerw*math.cos(rot)/2,
                       (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
            rotate_2d((jfingerl-jfingerex,jfingerw/2),math.radians(JANGLE2)),
            rotate_2d((jfingerl-jfingerex,-jfingerw/2),math.radians(JANGLE2)),
            rotate_2d((separation/2-jpadOverhang,
                       (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2),math.radians(struct().direction))
            ],bgcolor=bgcolor,layer=JLAYER))
        if jpadTaper > 0:
            chip.add(SolidPline(centerPos, points=[
                rotate_2d((separation/2-jpadOverhang+jpadTaper,jpadh/2),math.radians(struct().direction)),
                rotate_2d((separation/2-jpadOverhang+jpadTaper,-jpadh/2),math.radians(struct().direction)),
                rotate_2d((separation/2-jpadOverhang,
                   (jfingerl-jfingerex)*math.cos(rot)-jfingerw*math.sin(rot)/2),math.radians(struct().direction)),
                rotate_2d((separation/2-jpadOverhang,
                   (jfingerl-jfingerex)*math.cos(rot)+leadw-jfingerw*math.sin(rot)/2),math.radians(struct().direction))
                ],bgcolor=bgcolor,layer=JLAYER))


def DolanJunction(
    chip, structure, junctionl, jfingerw=0.5, rotation=0,
    jarmw=3, jpadw=15, jpadl=20, jpadr=0,jpadoverhang=5, # dimensions for contact tab overlap
    jfingerl=1.36,jtaperl=2-1.36-0.140,jgap=0.140, # fixed for LL
    backward=False, # if True, draw so points toward current structure location
    JANGLE=None, JLAYER=None,ULAYER=None,bgcolor=None,lincolnLabs=False,**kwargs):
    # centered such that taper starts at current position
    # junctionl is the gap distance we wish to cover

    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)

    #get layers from wafer
    if JLAYER is None:
        try:
            JLAYER = chip.wafer.JLAYER
        except AttributeError:
            setupJunctionLayers(chip.wafer)
            JLAYER = chip.wafer.JLAYER
    if ULAYER is None:
        try:
            ULAYER = chip.wafer.ULAYER
        except AttributeError:
            setupJunctionLayers(chip.wafer)
            ULAYER = chip.wafer.ULAYER

    if JANGLE is None:
        try:
            JANGLE = chip.wafer.JANGLES[0] % 360
        except AttributeError:
            setupJunctionAngles(chip.wafer, [struct().direction])
            JANGLE = chip.wafer.JANGLES[0] % 360
    # assert chip.wafer.JANGLES[0] % 180 == struct().direction % 180, 'Need Dolan junction to be in same direction as JANGLE'

    if lincolnLabs and not (0.1 < jfingerw < 3): print('WARNING: fingerw out of range. Recommended 0.150 < jfingerw < 3')

    # Junction layer
    struct().direction += rotation
    if backward: struct().direction += 180
    struct().shiftPos(-junctionl/2-jpadw+jpadoverhang)
    Strip_pad(chip, struct(), jpadw, w=jpadl, r_out=jpadr,layer=JLAYER) # contact pad
    Strip_straight(chip, struct(), length=junctionl/2-jtaperl-jpadoverhang, w=jarmw, layer=JLAYER)
    if lincolnLabs: ucstruct = struct().clone() 
    Strip_taper(chip, struct(), length=jtaperl, w0=jarmw, w1=jfingerw, layer=JLAYER)
    Strip_straight(chip, struct(), length=jfingerl, w=jfingerw, layer=JLAYER)

    if lincolnLabs:
        struct().shiftPos(jgap) # gap
    else:
        Strip_straight(chip, struct(), length=jgap, w=max(jarmw,jfingerw), layer=ULAYER)

    Strip_straight(chip, struct(), length=junctionl/2-jgap-jfingerl-jpadoverhang, w=jarmw, layer=JLAYER)
    Strip_pad(chip, struct(), jpadw, w=jpadl, r_out=jpadr, layer=JLAYER) # contact pad

    # Undercut layer
    if lincolnLabs:
        Strip_taper(chip, ucstruct, length=jtaperl, w0=jarmw, w1=jfingerw, layer=ULAYER)
        Strip_straight(chip, ucstruct, length=jfingerl+jgap, w=jfingerw, layer=ULAYER)

def CrossAlignMark(chip, structure, length=50, linewidth=10, rotation=0, layer=None, **kwargs):
    # Cross alignment mark
    if layer is None:
        try:
            layer = chip.wafer.JLAYER
        except AttributeError:
            setupJunctionLayers(chip.wafer)
            layer = chip.wafer.JLAYER

    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)

    struct().direction += rotation
    Strip_straight(chip, (structure[0]-length/2-linewidth/2,structure[1]), length=length, w=linewidth, layer=layer, **kwargs)
    # struct().direction += 90
    Strip_straight(chip, (structure[0]-linewidth/2,structure[1]), length=linewidth, w=length, layer=layer, **kwargs)
