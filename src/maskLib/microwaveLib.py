# -*- coding: utf-8 -*-
"""
Created on Fri Oct  4 17:29:02 2019

@author: Sasha

Library for drawing standard microwave components (CPW parts, inductors, capacitors etc)

Only standard composite components (inductors, launchers) are included here- complicated / application specific composites
go in sub-libraries
"""

import maskLib.MaskLib as m
from dxfwrite import DXFEngine as dxf
from dxfwrite import const
from dxfwrite.entities import Polyline
from dxfwrite.vector2d import vadd, midpoint ,vsub, vector2angle, magnitude, distance
from dxfwrite.algebra import rotate_2d

from maskLib.Entities import SolidPline, SkewRect, CurveRect, RoundRect, InsideCurve
from maskLib.utilities import kwargStrip, curveAB
from maskLib.point_logger import log_points 
from copy import deepcopy
from matplotlib.path import Path
from matplotlib.transforms import Bbox
import math
from copy import copy

# ===============================================================================
# perforate the ground plane with a grid of squares, which avoid any polylines 
# ===============================================================================
#TODO move to MaskLib


def waffle(chip, grid_x, grid_y=None,width=10,height=None,exclude=None,padx=0,pady=None,bleedRadius=1,layer='0'):
    radius = max(int(bleedRadius),0)
    
    if exclude is None:
        exclude = ['FRAME']
    else:
        exclude.append('FRAME')
        
    if grid_y is None:
        grid_y = grid_x
    
    if height is None:
        height = width
        
    if pady is None:
        pady=padx
        
    nx, ny = list(map(int, [(chip.width) / grid_x, (chip.height) / grid_y]))
    occupied = [[False]*ny for i in range(nx)]
    for i in range(nx):
        occupied[i][0] = True
        occupied[i][-1] = True
    for i in range(ny):
        occupied[0][i] = True
        occupied[-1][i] = True
    
    for e in chip.chipBlock.get_data():
        if isinstance(e.__dxftags__()[0], Polyline):
            if e.layer not in exclude:
                o_x_list = []
                o_y_list = []
                plinePts = [v.__getitem__('location').__getitem__('xy') for v in e.__dxftags__()[0].get_data()]
                plinePts.append(plinePts[0])
                for p in plinePts:
                    o_x, o_y = list(map(int, (p[0] / grid_x, p[1] / grid_y)))
                    if 0 <= o_x < nx and 0 <= o_y < ny:
                        o_x_list.append(o_x)
                        o_y_list.append(o_y)
                        
                        #this will however ignore a rectangle with corners outside the chip...
                if o_x_list:
                    path = Path([[pt[0]/grid_x,pt[1]/grid_y] for pt in plinePts],closed=True)
                    for x in range(min(o_x_list)-1, max(o_x_list)+2):
                        for y in range(min(o_y_list)-1, max(o_y_list)+2):
                            try:
                                if path.contains_point([x+.5,y+.5]):
                                    occupied[x][y]=True
                                elif path.intersects_bbox(Bbox.from_bounds(x,y,1.,1.),filled=True):
                                    occupied[x][y]=True
                            except IndexError:
                                pass
       

    second_pass = deepcopy(occupied)
    for r in range(radius):
        for i in range(nx):
            for j in range(ny):
                if occupied[i][j]:
                    for ip, jp in [(i+1,j), (i-1,j), (i,j+1), (i,j-1)]:
                        try:
                            second_pass[ip][jp] = True
                        except IndexError:
                            pass
        second_pass = deepcopy(second_pass)
   
    for i in range(int(padx/grid_x),nx-int(padx/grid_x)):
        for j in range(int(pady/grid_y),ny-int(pady/grid_y)):
            if not second_pass[i][j]:
                pos = i*grid_x + grid_x/2., j*grid_y + grid_y/2.
                chip.add(dxf.rectangle(pos,width,height,bgcolor=chip.wafer.bg(layer),halign=const.CENTER,valign=const.MIDDLE,layer=layer) )   
                
    return chip

def waffle_bumpbond(chip, grid_x, grid_y=None, width=10, height=None, exclude=None, padx=0, pady=None, bleedRadius=1, layer1='140_IUBM',
                    layer2='40_UBM', layer3='45_BUMP', num_bumps=1):
    radius = max(int(bleedRadius), 0)

    if exclude is None:
        exclude = ['FRAME', '703_ChipEdge', '101_IPOST', '103_IPOSTCLEAN', '12_DELBUMP']
    else:
        exclude.append('FRAME')

    if grid_y is None:
        grid_y = grid_x

    if height is None:
        height = width

    if pady is None:
        pady = padx

    nx, ny = list(map(int, [(chip.width) / grid_x, (chip.height) / grid_y]))
    occupied = [[False] * ny for i in range(nx)]
    for i in range(nx):
        occupied[i][0] = True
        occupied[i][-1] = True
    for i in range(ny):
        occupied[0][i] = True
        occupied[-1][i] = True

    for e in chip.chipBlock.get_data():
        if isinstance(e.__dxftags__()[0], Polyline):
            if e.layer not in exclude:
                o_x_list = []
                o_y_list = []
                plinePts = [v.__getitem__('location').__getitem__('xy') for v in e.__dxftags__()[0].get_data()]
                plinePts.append(plinePts[0])
                for p in plinePts:
                    o_x, o_y = list(map(int, (p[0] / grid_x, p[1] / grid_y)))
                    if 0 <= o_x < nx and 0 <= o_y < ny:
                        o_x_list.append(o_x)
                        o_y_list.append(o_y)

                        # this will however ignore a rectangle with corners outside the chip...
                if o_x_list:
                    path = Path([[pt[0] / grid_x, pt[1] / grid_y] for pt in plinePts], closed=True)
                    for x in range(min(o_x_list) - 1, max(o_x_list) + 2):
                        for y in range(min(o_y_list) - 1, max(o_y_list) + 2):
                            try:
                                if path.contains_point([x + .5, y + .5]):
                                    occupied[x][y] = True
                                elif path.intersects_bbox(Bbox.from_bounds(x, y, 1., 1.), filled=True):
                                    occupied[x][y] = True
                            except IndexError:
                                pass

    second_pass = deepcopy(occupied)
    for r in range(radius):
        for i in range(nx):
            for j in range(ny):
                if occupied[i][j]:
                    for ip, jp in [(i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)]:
                        try:
                            second_pass[ip][jp] = True
                        except IndexError:
                            pass
        second_pass = deepcopy(second_pass)

    for i in range(int(padx / grid_x), nx - int(padx / grid_x)):
        for j in range(int(pady / grid_y), ny - int(pady / grid_y)):
            if not second_pass[i][j]:
                pos = i * grid_x + grid_x / 2., j * grid_y + grid_y / 2.
                create_bumpbond(chip=chip, pos=pos, width=width, height=height, radius=7.5, layer1=layer1, layer2=layer2, layer3=layer3, num_bumps=num_bumps)
    return chip

def create_bumpbond(chip, pos, width, height, radius, layer1, layer2, layer3, num_bumps=1):
    chip.add(dxf.rectangle(pos, width, height, bgcolor=chip.wafer.bg(), halign=const.CENTER, valign=const.MIDDLE,
                      layer=layer1))
    chip.add(dxf.rectangle(pos, width, height, bgcolor=chip.wafer.bg(), halign=const.CENTER, valign=const.MIDDLE,
                      layer=layer2))
    #Unable to use, because circle only creates a polyline with 32 sides, while LL requires the polyline to have 40-50 sides
    # chip.add(dxf.circle(radius=7.5, center=pos, bgcolor=chip.wafer.bg(), layer=layer3))
    initial_pos = pos
    for i in range(num_bumps):
        pos = (initial_pos[0] - radius - (20+2*radius)*(i-math.floor(num_bumps/2)), initial_pos[1] - radius)
        chip.add(RoundRect(pos, height=radius*2, radius=radius, width=radius*2, roundCorners=[1, 1, 1, 1],
                  rotation=0, ptDensity=45, layer=layer3))


# ===============================================================================
# basic POSITIVE microstrip function definitions
# ===============================================================================

def Strip_straight(chip,structure,length,w=None,bgcolor=None,**kwargs): #note: uses CPW conventions
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    
    # Calculate rectangle corners for logging
    x0, y0 = struct().start
    angle_rad = math.radians(struct().direction)
    dx = length * math.cos(angle_rad)
    dy = length * math.sin(angle_rad)
    wx = (w/2) * math.sin(angle_rad)
    wy = (w/2) * math.cos(angle_rad)
    corners = [
        (x0 - wx, y0 + wy),
        (x0 + dx - wx, y0 + dy + wy),
        (x0 + dx + wx, y0 + dy - wy),
        (x0 + wx, y0 - wy),
    ]
    log_points(corners)

    chip.add(dxf.rectangle(struct().start,length,w,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=structure,length=length)

#straights strip with contact pads for ease of use. unfinished*** finished hastily by Tom
def Strip_contact(chip,structure,length,contactTop=True,contactBot=True,w=None,bgcolor=None,**kwargs): #note: uses CPW conventions
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    
    chip.add(dxf.rectangle(struct().start,length,w,valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=structure,length=length)
   
    contactW=20 if 'contactW' not in kwargs else kwargs['contactW']
    contactL=10 if 'contactL' not in kwargs else kwargs['contactL']
    wedgeL=10 if 'wedgeL' not in kwargs else kwargs['wedgeL']

    # Adjust the sign of contactL and wedgeL based on the sign of w
    contactL = math.copysign(contactL, w)
    wedgeL = math.copysign(wedgeL, w)

    drawstart=(struct().start[0]-0.5,struct().start[1]+w+contactL+wedgeL)
    contact_points=[
                (drawstart[0] + contactW/2, drawstart[1]),
                (drawstart[0] + contactW/2, drawstart[1] - wedgeL),
                (drawstart[0] + length/2, drawstart[1] - contactL - wedgeL),
                (drawstart[0] - length/2, drawstart[1] - contactL -wedgeL),
                (drawstart[0] - contactW/2, drawstart[1] - wedgeL),
                (drawstart[0] - contactW/2, drawstart[1])
            ]
    contact = dxf.polyline(points=contact_points,**kwargStrip(kwargs))
    contact.close()
    
    chip.add(contact)


def Strip_taper(chip,structure,length=None,w0=None,w1=None,bgcolor=None,offset=(0,0),**kwargs): #note: uses CPW conventions
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w0 is None:
        try:
            w0 = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if w1 is None:
        try:
            w1 = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    #if undefined, make outer angle 30 degrees
    if length is None:
        length = math.sqrt(3)*abs(w0/2-w1/2)
    
    chip.add(SkewRect(_originCompensatedInsert(chip, struct().start, struct().direction),length,w0,offset,w1,rotation=struct().direction,valign=const.MIDDLE,edgeAlign=const.MIDDLE,bgcolor=bgcolor,**kwargs),structure=structure,offsetVector=vadd((length,0),offset))

def Strip_bend(chip,structure,angle=90,CCW=True,w=None,radius=None,ptDensity=120,bgcolor=None,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID)
    if radius is None:
        try:
            radius = struct().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ',chip.chipID,'!\x1b[0m')
            return
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
        
    while angle < 0:
        angle = angle + 360
    angle = angle%360
        
    chip.add(CurveRect(struct().start,w,radius,angle=angle,ptDensity=ptDensity,ralign=const.MIDDLE,valign=const.MIDDLE,rotation=struct().direction,vflip=not CCW,bgcolor=bgcolor,**kwargs))
    struct().updatePos(newStart=struct().getPos((radius*math.sin(math.radians(angle)),(CCW and 1 or -1)*radius*(math.cos(math.radians(angle))-1))),angle=CCW and -angle or angle)


def Strip_stub_open(chip,structure,flipped=False,curve_out=True,r_out=None,w=None,allow_oversize=True,length=None,bgcolor=None,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if r_out is None:
        try:
            if allow_oversize:
                r_out = struct().defaults['r_out']
            else:
                r_out = min(struct().defaults['r_out'],w/2)
        except KeyError:
            print('r_out not defined in ',chip.chipID,'!\x1b[0m')
            r_out=0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    
    
    if r_out > 0:
        dx = 0.
        if flipped:
            if allow_oversize:
                dx = r_out
            else:
                dx = min(w/2,r_out)
        
        if allow_oversize:
            l=r_out
        else:
            l=min(w/2,r_out)
        
        if length is None: length=0

        chip.add(RoundRect(struct().getPos((dx,0)),max(length,l),w,l,roundCorners=[0,curve_out,curve_out,0],hflip=flipped,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=structure,length=l)
    else:
        if length is not None:
            if allow_oversize:
                l=length
            else:
                l=min(w/2,length)
        else:
            l=w/2
        Strip_straight(chip,structure,l,w=w,bgcolor=bgcolor,**kwargs)

def Strip_stub_short(chip,structure,r_ins=None,w=None,flipped=False,extra_straight_section=False,bgcolor=None,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID,'!\x1b[0m')
    if r_ins is None:
        try:
            r_ins = struct().defaults['r_ins']
        except KeyError:
            #print('r_ins not defined in ',chip.chipID,'!\x1b[0m')
            r_ins=0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    
    if r_ins > 0:
        if extra_straight_section and not flipped:
            Strip_straight(chip, struct(), r_ins, w=w,rotation=struct().direction,bgcolor=bgcolor,**kwargs)
        chip.add(InsideCurve(struct().getPos((0,w/2)),r_ins,rotation=struct().direction,hflip=flipped,bgcolor=bgcolor,**kwargs))
        chip.add(InsideCurve(struct().getPos((0,-w/2)),r_ins,rotation=struct().direction,hflip=flipped,vflip=True,bgcolor=bgcolor,**kwargs))
        if extra_straight_section and flipped:
                Strip_straight(chip, struct(), r_ins, w=w,rotation=struct().direction,bgcolor=bgcolor,**kwargs)

def Strip_pad(chip,structure,length,r_out=None,w=None,bgcolor=None,**kwargs):
    '''
    Draw a pad with all rounded corners (similar to strip_stub_open + strip_straight + strip_stub_open but only one shape)

    '''
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if r_out is None:
        try:
            r_out = min(struct().defaults['r_out'],w/2)
        except KeyError:
            print('r_out not defined in ',chip.chipID,'!\x1b[0m')
            r_out=0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    
    
    if r_out > 0:
        chip.add(RoundRect(struct().getPos((0,0)),length,w,r_out,roundCorners=[1,1,1,1],valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=structure,length=length)
    else:
        Strip_straight(chip,structure,length,w=w,bgcolor=bgcolor,**kwargs)

# ===============================================================================
# basic NEGATIVE CPW function definitions
# ===============================================================================


def CPW_straight(chip,structure,length,w=None,s=None,bondwires=False,bond_pitch=70,incl_end_bond=True,bgcolor=None,**kwargs): #note: uses CPW conventions
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')

    if bondwires: # bond parameters patched through kwargs
        num_bonds = int(length/bond_pitch)
        this_struct = struct().clone()
        this_struct.shiftPos(bond_pitch)
        if not incl_end_bond: num_bonds -= 1
        for i in range(num_bonds):
            Airbridge(chip, this_struct, **kwargs)
            this_struct.shiftPos(bond_pitch)
    
    chip.add(dxf.rectangle(struct().getPos((0,-w/2)),length,-s,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
    chip.add(dxf.rectangle(struct().getPos((0,w/2)),length,s,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=structure,length=length)
        
def CPW_taper(chip,structure,length=None,w0=None,s0=None,w1=None,s1=None,bgcolor=None,offset=(0,0),**kwargs): #note: uses CPW conventions
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w0 is None:
        try:
            w0 = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if s0 is None:
        try:
            s0 = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if w1 is None:
        try:
            w1 = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if s1 is None:
        try:
            s1 = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    #if undefined, make outer angle 30 degrees
    if length is None:
        length = math.sqrt(3)*abs(w0/2+s0-w1/2-s1)
    
    chip.add(SkewRect(struct().getPos((0,-w0/2)),length,s0,(offset[0],w0/2-w1/2+offset[1]),s1,rotation=struct().direction,valign=const.TOP,edgeAlign=const.TOP,bgcolor=bgcolor,**kwargs))
    chip.add(SkewRect(struct().getPos((0,w0/2)),length,s0,(offset[0],w1/2-w0/2+offset[1]),s1,rotation=struct().direction,valign=const.BOTTOM,edgeAlign=const.BOTTOM,bgcolor=bgcolor,**kwargs),structure=structure,offsetVector=(length+offset[0],offset[1]))
    
def CPW_stub_short(chip,structure,flipped=False,curve_ins=True,curve_out=True,r_out=None,w=None,s=None,length=None,bgcolor=None,**kwargs):
    allow_oversize = (curve_ins != curve_out)
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if r_out is None:
        try:
            if allow_oversize:
                r_out = struct().defaults['r_out']
            else:
                r_out = min(struct().defaults['r_out'],s/2)
        except KeyError:
            print('r_out not defined in ',chip.chipID,'!\x1b[0m')
            r_out=0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    
    
    if r_out > 0:
        
        dx = 0.
        if flipped:
            if allow_oversize:
                dx = r_out
            else:
                dx = min(s/2,r_out)
        
        if allow_oversize:
            l=r_out
        else:
            l=min(s/2,r_out)

        chip.add(RoundRect(struct().getPos((dx,w/2)),l,s,l,roundCorners=[0,curve_ins,curve_out,0],hflip=flipped,valign=const.BOTTOM,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
        chip.add(RoundRect(struct().getPos((dx,-w/2)),l,s,l,roundCorners=[0,curve_out,curve_ins,0],hflip=flipped,valign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=structure,length=l)
    else:
        if length is not None:
            if allow_oversize:
                l=length
            else:
                l=min(s/2,length)
        else:
            l=s/2
        CPW_straight(chip,structure,l,w=w,s=s,bgcolor=bgcolor,**kwargs)
        
def CPW_stub_open(chip,structure,length=0,r_out=None,r_ins=None,w=None,s=None,flipped=False,extra_straight_section=False,bgcolor=None,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID,'!\x1b[0m')
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if length==0:
        length = max(length,s)
    if r_out is None:
        try:
            r_out = struct().defaults['r_out']
        except KeyError:
            print('\x1b[33mr_out not defined in ',chip.chipID,'!\x1b[0m')
            r_out=0
    if r_ins is None:
        try:
            r_ins = struct().defaults['r_ins']
        except KeyError:
            #print('r_ins not defined in ',chip.chipID,'!\x1b[0m')
            r_ins=0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    
    dx = 0.
    if flipped:
        dx = length

    if r_ins > 0:
        if extra_straight_section and not flipped:
            CPW_straight(chip, struct(), r_ins, w=w,s=s,rotation=struct().direction,bgcolor=bgcolor,**kwargs)
        chip.add(InsideCurve(struct().getPos((dx,w/2)),r_ins,rotation=struct().direction,hflip=flipped,bgcolor=bgcolor,**kwargs))
        chip.add(InsideCurve(struct().getPos((dx,-w/2)),r_ins,rotation=struct().direction,hflip=flipped,vflip=True,bgcolor=bgcolor,**kwargs))

    chip.add(RoundRect(struct().getPos((dx,0)),length,w+2*s,min(r_out,length),roundCorners=[0,1,1,0],hflip=flipped,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs),structure=structure,length=length)
    if extra_straight_section and flipped:
        CPW_straight(chip, struct(), r_ins, w=w,s=s,rotation=struct().direction,bgcolor=bgcolor,**kwargs)

def CPW_cap(chip,structure,gap,r_ins=None,w=None,s=None,bgcolor=None,angle=90,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID,'!\x1b[0m')
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if r_ins is None:
        try:
            r_ins = struct().defaults['r_ins']
        except KeyError:
            #print('r_ins not defined in ',chip.chipID,'!\x1b[0m')
            r_ins=0
    if bgcolor is None:
        bgcolor = chip.wafer.bg()

    if r_ins > 0:
        chip.add(InsideCurve(struct().getPos((0,w/2)),r_ins,rotation=struct().direction + 90,vflip=True,angle=angle,bgcolor=bgcolor,**kwargs))
        chip.add(InsideCurve(struct().getPos((0,-w/2)),r_ins,rotation=struct().direction - 90,angle=angle,bgcolor=bgcolor,**kwargs))
        # chip.add(InsideCurve(struct().getPos((gap,w/2)),r_ins,rotation=struct().direction + 90,angle=angle,bgcolor=bgcolor,**kwargs))
        # chip.add(InsideCurve(struct().getPos((gap,-w/2)),r_ins,rotation=struct().direction - 90,vflip=True,angle=angle,bgcolor=bgcolor,**kwargs))

    chip.add(dxf.rectangle(struct().start,gap,w+2*s,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=structure,length=gap)

        
def CPW_stub_round(chip,structure,w=None,s=None,round_left=True,round_right=True,flipped=False,bgcolor=None,**kwargs):
    #same as stub_open, but preserves gap width along turn (so radii are nominally defined by w, s)
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID)
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    
    dx = 0.
    if flipped:
        dx = s+w/2

    if False:#round_left and round_right:
        chip.add(CurveRect(struct().getPos((dx,w/2)),s,w/2,angle=180,ralign=const.BOTTOM,rotation=struct().direction,hflip=flipped,bgcolor=bgcolor,**kwargs),structure=structure,length=s+w/2)
    else:
        if round_left:
            chip.add(CurveRect(struct().getPos((dx,w/2)),s,w/2,angle=90,ralign=const.BOTTOM,rotation=struct().direction,hflip=flipped,bgcolor=bgcolor,**kwargs))
        else:
            chip.add(dxf.rectangle(struct().getPos((0,w/2)),s+w/2,s,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
            chip.add(InsideCurve(struct().getPos((flipped and s or w/2,w/2)),w/2,rotation=struct().direction,hflip=flipped,bgcolor=bgcolor,**kwargs))
            chip.add(dxf.rectangle(struct().getPos((s+w/2-dx,w/2)),-s,-w/2,rotation=struct().direction,halign = flipped and const.RIGHT or const.LEFT, bgcolor=bgcolor,**kwargStrip(kwargs)))
        if round_right:
            chip.add(CurveRect(struct().getPos((dx,-w/2)),s,w/2,angle=90,ralign=const.BOTTOM,rotation=struct().direction,hflip=flipped,vflip=True,bgcolor=bgcolor,**kwargs),structure=structure,length=s+w/2)
        else:
            chip.add(dxf.rectangle(struct().getPos((0,-w/2)),s+w/2,-s,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
            chip.add(InsideCurve(struct().getPos((flipped and s or w/2,-w/2)),w/2,rotation=struct().direction,hflip=flipped,vflip=True,bgcolor=bgcolor,**kwargs))
            chip.add(dxf.rectangle(struct().getPos((s+w/2-dx,-w/2)),-s,w/2,rotation=struct().direction,halign = flipped and const.RIGHT or const.LEFT, bgcolor=bgcolor,**kwargStrip(kwargs)),structure=structure,length=s+w/2)
    
def CPW_bend(chip,structure,angle=90,CCW=True,w=None,s=None,radius=None,ptDensity=120,bondwires=False,incl_end_bond=True,bond_pitch=70,bgcolor=None,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID)
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID)
    if radius is None:
        try:
            radius = struct().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ',chip.chipID,'!\x1b[0m')
            return
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
        
    while angle < 0:
        angle = angle + 360
    angle = angle%360
    angleRadians = math.radians(angle)

    startstruct = struct().clone()
        
    chip.add(CurveRect(struct().start,s,radius,angle=angle,ptDensity=ptDensity,roffset=w/2,ralign=const.BOTTOM,rotation=struct().direction,vflip=not CCW,bgcolor=bgcolor,**kwargs))
    chip.add(CurveRect(struct().start,s,radius,angle=angle,ptDensity=ptDensity,roffset=-w/2,ralign=const.TOP,valign=const.TOP,rotation=struct().direction,vflip=not CCW,bgcolor=bgcolor,**kwargs))
    struct().updatePos(newStart=struct().getPos((radius*math.sin(angleRadians),(CCW and 1 or -1)*radius*(math.cos(angleRadians)-1))),angle=CCW and -angle or angle)

    if bondwires: # bond parameters patched through kwargs
        bond_angle_density = 8
        if 'lincolnLabs' in kwargs and kwargs['lincolnLabs']: bond_angle_density = int((2*math.pi*radius)/bond_pitch)
        clockwise = 1 if CCW else -1
        bond_points = curveAB(startstruct.start, struct().start, clockwise=clockwise, angleDeg=angle, ptDensity=bond_angle_density)
        if not incl_end_bond: bond_points = bond_points[:-1]
        for i, bond_point in enumerate(bond_points[1:], start=1):
            this_struct = m.Structure(chip, start=bond_point, direction=startstruct.direction-clockwise*i*360/bond_angle_density)
            Airbridge(chip, this_struct, br_radius=radius, clockwise=clockwise, **kwargs)


def CPW_tee(chip,structure,w=None,s=None,radius=None,r_ins=None,w1=None,s1=None,bgcolor=None,hflip=False,branch_off=const.CENTER,**kwargs):
    
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID)
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID)
    if radius is None:
        try:
            radius = 2*struct().defaults['s']
        except KeyError:
            print('\x1b[33mradius not defined in ',chip.chipID,'!\x1b[0m')
            return
    if r_ins is None: #check if r_ins is defined in the defaults
        try:
            r_ins = struct().defaults['r_ins']
        except KeyError: # quiet catch
            r_ins = None   
    
    #default to left and right branches identical to original structure
    if w1 is None:
        w1 = w
    if s1 is None:
        s1 = s
        
    #clone structure defaults
    defaults1 = copy(struct().defaults)
    #update new defaults if defined
    defaults1.update({'w':w1})
    defaults1.update({'s':s1})
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
        
    #long curves not allowed if gaps differ
    if s!=s1:
        radius = min(abs(radius),min(s,s1))
    
    #assign a inside curve radius if not defined
    if r_ins is None:
        r_ins = radius
    
    s_rad = max(radius,s1)
    
    #figure out if tee is centered, or offset
    if branch_off == const.LEFT:
        struct().translatePos((s_rad+w1/2 - 2*hflip*(s_rad+w1/2),w/2+max(radius,s)),angle=-90)
    elif branch_off == const.RIGHT:
        struct().translatePos((s_rad+w1/2 - 2*hflip*(s_rad+w1/2),-w/2-max(radius,s)),angle=90)

    chip.add(dxf.rectangle(struct().getPos((s_rad+w1 - 2*hflip*(s_rad+w1),0)),hflip and -s1 or s1,2*max(radius,s)+w,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
    if s==s1:
        chip.add(CurveRect(struct().getPos((0,-w/2-s)),s,radius,hflip=hflip,ralign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
        chip.add(CurveRect(struct().getPos((0,w/2+s)),s,radius,hflip=hflip,vflip=True,ralign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
    else:
        if s1>s:
            chip.add(dxf.rectangle(struct().getPos((0,-w/2)),hflip and s-s1 or s1-s,-s,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
            chip.add(dxf.rectangle(struct().getPos((0,w/2)),hflip and s-s1 or s1-s,s,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
            chip.add(CurveRect(struct().getPos((hflip and s-s1 or s1-s,-w/2-s)),radius,radius,hflip=hflip,ralign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
            chip.add(CurveRect(struct().getPos((hflip and s-s1 or s1-s,w/2+s)),radius,radius,hflip=hflip,vflip=True,ralign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
        else:#s1<s
            chip.add(CurveRect(struct().getPos((0,-w/2-radius)),radius,radius,hflip=hflip,ralign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
            chip.add(CurveRect(struct().getPos((0,w/2+radius)),radius,radius,hflip=hflip,vflip=True,ralign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
            chip.add(dxf.rectangle(struct().getPos((0,-w/2-radius)),hflip and -radius or radius,-(s-s1),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
            chip.add(dxf.rectangle(struct().getPos((0,w/2+radius)),hflip and -radius or radius,(s-s1),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
    if radius <= min(s,s1) and r_ins > 0:
        #inside edges are square
        chip.add(InsideCurve(struct().getPos((0,w/2+s)),r_ins,hflip=hflip,vflip=True,ralign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
        chip.add(InsideCurve(struct().getPos((0,-w/2-s)),r_ins,hflip=hflip,vflip=False,ralign=const.TOP,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
    
    
    if branch_off == const.CENTER:  
        s_l = struct().cloneAlong((s_rad+w1/2 - 2*hflip*(s_rad+w1/2),w/2+max(radius,s)),newDirection=90,defaults=defaults1)
        s_r = struct().cloneAlong((s_rad+w1/2 - 2*hflip*(s_rad+w1/2),-w/2-max(radius,s)),newDirection=-90,defaults=defaults1)
    
        return s_l,s_r
    elif branch_off == const.LEFT:
        s_l = struct().cloneAlong((0,0),newDirection=180)
        struct().translatePos((w/2+max(radius,s),s_rad+w1/2 - 2*hflip*(s_rad+w1/2)),angle=90)
        return s_l
    elif branch_off == const.RIGHT:
        s_r = struct().cloneAlong((0,0),newDirection=180)
        struct().translatePos((w/2+max(radius,s),-s_rad-w1/2 + 2*hflip*(s_rad+w1/2)),angle=-90)
        return s_r

# ===============================================================================
# basic NEGATIVE TwoPinCPW function definitions
# ===============================================================================

def TwoPinCPW_straight(chip,structure,length,w=None,s_ins=None,s_out=None,Width=None,s=None,bgcolor=None,**kwargs): #note: uses CPW conventions
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if s is not None:
        #s overridden somewhere above
        if s_ins is None:
            s_ins = s
        if s_out is None:
            s_out = s
    if s_ins is None:
        try:
            s_ins = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if s_out is None:
        if Width is not None:
            s_out = Width - w - s_ins/2
        else:
            try:
                s_out = struct().defaults['s']
            except KeyError:
                print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    
    
    chip.add(dxf.rectangle(struct().getPos((0,-s_ins/2-w)),length,-s_out,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
    chip.add(dxf.rectangle(struct().getPos((0,-s_ins/2)),length,s_ins,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
    chip.add(dxf.rectangle(struct().getPos((0,s_ins/2+w)),length,s_out,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=structure,length=length)

# ===============================================================================
#  NEGATIVE wire/stripline function definitions
# ===============================================================================

def Wire_bend(chip,structure,angle=90,CCW=True,w=None,radius=None,bgcolor=None,**kwargs):
    #only defined for 90 degree bends
    if angle%90 != 0:
        return
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID)
    if radius is None:
        try:
            radius = struct().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ',chip.chipID,'!\x1b[0m')
            return
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
        
    while angle < 0:
        angle = angle + 360
    angle = angle%360
        
    if radius-w/2 > 0:
        chip.add(CurveRect(struct().start,radius-w/2,radius,angle=angle,roffset=-w/2,ralign=const.TOP,valign=const.TOP,rotation=struct().direction,vflip=not CCW,bgcolor=bgcolor,**kwargs))
    for i in range(angle//90):
        chip.add(InsideCurve(struct().getPos(vadd(rotate_2d((radius+w/2,(CCW and 1 or -1)*(radius+w/2)),(CCW and -1 or 1)*math.radians(i*90)),(0,CCW and -radius or radius))),radius+w/2,rotation=struct().direction+(CCW and -1 or 1)*i*90,bgcolor=bgcolor,vflip=not CCW,**kwargs))
    struct().updatePos(newStart=struct().getPos((radius*math.sin(math.radians(angle)),(CCW and 1 or -1)*radius*(math.cos(math.radians(angle))-1))),angle=CCW and -angle or angle)

# ===============================================================================
# composite CPW function definitions
# ===============================================================================
def CPW_pad(chip,struct,l_pad=0,l_gap=0,padw=300,pads=50,l_lead=None,w=None,s=None,r_ins=None,r_out=None,bgcolor=None,**kwargs):
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            w=0
            print('\x1b[33mw not defined in ',chip.chipID)
    CPW_stub_open(chip,struct,length=max(l_gap,pads),r_out=r_out,r_ins=r_ins,w=padw,s=pads,flipped=True,**kwargs)
    CPW_straight(chip,struct,max(l_pad,padw),w=padw,s=pads,**kwargs)
    if l_lead is None:
        l_lead = max(l_gap,pads)
    CPW_stub_short(chip,struct,length=l_lead,r_out=r_out,r_ins=r_ins,w=w,s=pads+padw/2-w/2,flipped=False,curve_ins=False,**kwargs)


def CPW_launcher(chip,struct,l_taper=None,l_pad=0,l_gap=0,padw=300,pads=160,w=None,s=None,r_ins=0,r_out=0,bgcolor=None,**kwargs):
    CPW_stub_open(chip,struct,length=max(l_gap,pads),r_out=r_out,r_ins=r_ins,w=padw,s=pads,flipped=True,**kwargs)
    CPW_straight(chip,struct,l_pad,w=padw,s=pads,**kwargs)
    CPW_taper(chip,struct,length=l_taper,w0=padw,s0=pads,**kwargs)

def CPW_taper_cap(chip,structure,gap,width,l_straight=0,l_taper=None,s1=None,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if s1 is None:
        try:
            s = struct().defaults['s']
            w = struct().defaults['w']
            s1 = width*s/w
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID)
            print('\x1b[33ms not defined in ',chip.chipID)
    if l_taper is None:
        l_taper = 3*width
    if l_straight<=0:
        try:
            tap_angle = math.degrees(math.atan(2*l_taper/(width-struct().defaults['w'])))
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID)
            tap_angle = 90
    else:
        tap_angle = 90
        
    CPW_taper(chip,structure,length=l_taper,w1=width,s1=s1,**kwargs)
    if l_straight > 0 :
        CPW_straight(chip,structure,length=l_straight,w=width,s=s1,**kwargs)
    CPW_cap(chip, structure, gap, w=width, s=s1, angle=tap_angle, **kwargs)
    if l_straight > 0 :
        CPW_straight(chip,structure,length=l_straight,w=width,s=s1,**kwargs)
    CPW_taper(chip,structure,length=l_taper,w0=width,s0=s1,**kwargs)
    
def CPW_directTo(chip,from_structure,to_structure,to_flipped=True,w=None,s=None,radius=None,CW1_override=None,CW2_override=None,flip_angle=False,debug=False,**kwargs):
    def struct1():
        if isinstance(from_structure,m.Structure):
            return from_structure
        else:
            return chip.structure(from_structure)
    if radius is None:
        try:
            radius = struct1().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ',chip.chipID,'!\x1b[0m')
            return
    #struct2 is only a local copy
    struct2 = isinstance(to_structure,m.Structure) and to_structure or chip.structure(to_structure)
    if to_flipped:
        struct2.direction=(struct2.direction+180.)%360
    
    CW1 = vector2angle(struct1().getGlobalPos(struct2.start)) < 0
    CW2 = vector2angle(struct2.getGlobalPos(struct1().start)) < 0

    target1 = struct1().getPos((0,CW1 and -2*radius or 2*radius))
    target2 = struct2.getPos((0,CW2 and -2*radius or 2*radius))
    
    #reevaluate based on center positions
    
    CW1 = vector2angle(struct1().getGlobalPos(target2)) < 0
    CW2 = vector2angle(struct2.getGlobalPos(target1)) < 0
    
    if CW1_override is not None:
        CW1 = CW1_override
    if CW2_override is not None:
        CW2 = CW2_override

    center1 = struct1().getPos((0,CW1 and -radius or radius))
    center2 = struct2.getPos((0,CW2 and -radius or radius))
    
    if debug:
        chip.add(dxf.line(struct1().getPos((-3000,0)),struct1().getPos((3000,0)),layer='FRAME'))
        chip.add(dxf.line(struct2.getPos((-3000,0)),struct2.getPos((3000,0)),layer='FRAME'))
        chip.add(dxf.circle(center=center1,radius=radius,layer='FRAME'))
        chip.add(dxf.circle(center=center2,radius=radius,layer='FRAME'))
    
    correction_angle=math.asin(abs(2*radius*(CW1 - CW2)/distance(center2,center1)))
    angle1 = abs(struct1().direction - math.degrees(vector2angle(vsub(center2,center1)))) + math.degrees(correction_angle)
    if flip_angle:
        angle1 = 360-abs(struct1().direction - math.degrees(vector2angle(vsub(center2,center1)))) + math.degrees(correction_angle)
    
    if debug:
        print(CW1,CW2,angle1,math.degrees(correction_angle))
    
    if angle1 > 270:
        if debug:
            print('adjusting to shorter angle')
        angle1 = min(angle1,abs(360-angle1))
    '''
    if CW1 - CW2 == 0 and abs(angle1)>100:
        if abs((struct1().getGlobalPos(struct2.start))[1]) < 2*radius:
            print('adjusting angle')
            angle1 = angle1 + math.degrees(math.asin(abs(2*radius/distance(center2,center1))))
            '''
    CPW_bend(chip,from_structure,angle=angle1,w=w,s=s,radius=radius, CCW=CW1,**kwargs)
    CPW_straight(chip,from_structure,distance(center2,center1)*math.cos(correction_angle),w=w,s=s,**kwargs)
    
    angle2 = abs(struct1().direction-struct2.direction)
    if angle2 > 270:
        angle2 = min(angle2,abs(360-angle2))
    CPW_bend(chip,from_structure,angle=angle2,w=w,s=s,radius=radius,CCW=CW2,**kwargs)

#Various wiggles (meander) definitions 

def wiggle_calc(chip,structure,length=None,nTurns=None,maxWidth=None,Width=None,start_bend = True,stop_bend=True,w=None,s=None,radius=None,debug=False,**kwargs):
    #figure out 
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if radius is None:
        try:
            radius = struct().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ',chip.chipID,'!\x1b[0m')
            return
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID,'!\x1b[0m')
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            s = 0
    #prevent dumb entries
    if nTurns is None:
        nTurns = 1
    elif nTurns < 1:
        nTurns = 1
    
    #debug
    if debug:
        print('w=',w,' s=',s,' nTurns=',nTurns,' length=',length,' Width=',Width,' maxWidth=',maxWidth)
    
    #is length constrained?
    if length is not None:
        if nTurns is None:
            nTurns = 1
        h = (length - nTurns*2*math.pi*radius - (start_bend+stop_bend)*(math.pi/2-1)*radius)/(4*nTurns)

        #is width constrained?
        if Width is not None or maxWidth is not None:
            #maxWidth corresponds to the wiggle width, while Width corresponds to the total width filled
            if maxWidth is not None:
                if Width is None:
                    Width = maxWidth
                else:
                    maxWidth = min(maxWidth,Width)
            else:
                maxWidth = Width
            while h+radius+w/2+s/2>maxWidth:
                nTurns = nTurns+1
                h = (length - nTurns*2*math.pi*radius - (start_bend+stop_bend)*(math.pi/2-1)*radius)/(4*nTurns)
    else: #length is not contrained
        h= maxWidth-radius-w/2-s
    if h<radius:
        print("WARNING: straight segment is shorter than the radius, possible bad CPW resonator")
    # h = max(h,radius)
    # Commented out by CD on 4/14/2025 - not sure why the straight segment needs to be longer than the curved segment,
    # likely for a microwave engineering reason. But I think the alternative is significantly worse, because it just
    # gives the wrong resonator length if n_turns is too large.

    return {'nTurns':nTurns,'h':h,'length':length,'maxWidth':maxWidth,'Width':Width}

def CPW_wiggles(chip,structure,length=None,nTurns=None,maxWidth=None,CCW=True,start_bend = True,stop_bend=True,w=None,s=None,radius=None,bgcolor=None,debug=False,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if radius is None:
        try:
            radius = struct().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ',chip.chipID,'!\x1b[0m')
            return
    
    params = wiggle_calc(chip,structure,length,nTurns,maxWidth,None,start_bend,stop_bend,w,s,radius,**kwargs)
    [nTurns,h,length,maxWidth]=[params[key] for key in ['nTurns','h','length','maxWidth']]
    if (length is None) or (h is None) or (nTurns is None):
        print('not enough params specified for CPW_wiggles!')
        return
    if debug:
        chip.add(dxf.rectangle(struct().start,(nTurns*4 + start_bend + stop_bend)*radius,2*h,valign=const.MIDDLE,rotation=struct().direction,layer='FRAME'))
        chip.add(dxf.rectangle(struct().start,(nTurns*4 + start_bend + stop_bend)*radius,2*maxWidth,valign=const.MIDDLE,rotation=struct().direction,layer='FRAME'))
    if start_bend:
        CPW_bend(chip,structure,angle=90,CCW=CCW,w=w,s=s,radius=radius,bgcolor=bgcolor,**kwargs)
        if h > radius:
            CPW_straight(chip,structure,h-radius,w=w,s=s,bgcolor=bgcolor,**kwargs)
    else:
        CPW_straight(chip,structure,h,w=w,s=s,bgcolor=bgcolor,**kwargs)
    CPW_bend(chip,structure,angle=180,CCW=not CCW,w=w,s=s,radius=radius,bgcolor=bgcolor,**kwargs)
    CPW_straight(chip,structure,h+radius,w=w,s=s,bgcolor=bgcolor,**kwargs)
    if h > radius:
        CPW_straight(chip,structure,h-radius,w=w,s=s,bgcolor=bgcolor,**kwargs)
    CPW_bend(chip,structure,angle=180,CCW=CCW,w=w,s=s,radius=radius,bgcolor=bgcolor,**kwargs)
    if h > radius:
        CPW_straight(chip,structure,h-radius,w=w,s=s,bgcolor=bgcolor,**kwargs)
    for n in range(nTurns-1):
        CPW_straight(chip,structure,h+radius,w=w,s=s,bgcolor=bgcolor,**kwargs)
        CPW_bend(chip,structure,angle=180,CCW=not CCW,w=w,s=s,radius=radius,bgcolor=bgcolor,**kwargs)
        CPW_straight(chip,structure,h+radius,w=w,s=s,bgcolor=bgcolor,**kwargs)
        if h > radius:
            CPW_straight(chip,structure,h-radius,w=w,s=s,bgcolor=bgcolor,**kwargs)
        CPW_bend(chip,structure,angle=180,CCW=CCW,w=w,s=s,radius=radius,bgcolor=bgcolor,**kwargs)
        if h > radius:
            CPW_straight(chip,structure,h-radius,w=w,s=s,bgcolor=bgcolor,**kwargs)
    if stop_bend:
        CPW_bend(chip,structure,angle=90,CCW=not CCW,w=w,s=s,radius=radius,bgcolor=bgcolor,**kwargs)
    else:
        CPW_straight(chip,structure,radius,w=w,s=s,bgcolor=bgcolor,**kwargs)

def Strip_wiggles(chip,structure,length=None,nTurns=None,maxWidth=None,CCW=True,start_bend = True,stop_bend=True,w=None,radius=None,bgcolor=None,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if radius is None:
        try:
            radius = struct().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ',chip.chipID,'!\x1b[0m')
            return
    
    params = wiggle_calc(chip,structure,length,nTurns,maxWidth,None,start_bend,stop_bend,w,0,radius,**kwargs)
    [nTurns,h,length,maxWidth]=[params[key] for key in ['nTurns','h','length','maxWidth']]
    if (h is None) or (nTurns is None):
        print('not enough params specified for Microstrip_wiggles!')
        return

    if start_bend:
        Strip_bend(chip,structure,angle=90,CCW=CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
        if h > radius:
            Strip_straight(chip,structure,h-radius,w=w,bgcolor=bgcolor,**kwargs)
    else:
        Strip_straight(chip,structure,h,w=w,bgcolor=bgcolor,**kwargs)
    Strip_bend(chip,structure,angle=180,CCW=not CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
    Strip_straight(chip,structure,h+radius,w=w,bgcolor=bgcolor,**kwargs)
    if h > radius:
        Strip_straight(chip,structure,h-radius,w=w,bgcolor=bgcolor,**kwargs)
    Strip_bend(chip,structure,angle=180,CCW=CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
    if h > radius:
        Strip_straight(chip,structure,h-radius,w=w,bgcolor=bgcolor,**kwargs)
    for n in range(nTurns-1):
        Strip_straight(chip,structure,h+radius,w=w,bgcolor=bgcolor,**kwargs)
        Strip_bend(chip,structure,angle=180,CCW=not CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
        Strip_straight(chip,structure,h+radius,w=w,bgcolor=bgcolor,**kwargs)
        if h > radius:
            Strip_straight(chip,structure,h-radius,w=w,bgcolor=bgcolor,**kwargs)
        Strip_bend(chip,structure,angle=180,CCW=CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
        if h > radius:
            Strip_straight(chip,structure,h-radius,w=w,bgcolor=bgcolor,**kwargs)
    if stop_bend:
        Strip_bend(chip,structure,angle=90,CCW=not CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
    else:
        Strip_straight(chip,structure,radius,w=w,bgcolor=bgcolor,**kwargs)

def Inductor_wiggles(chip,structure,length=None,nTurns=None,maxWidth=None,Width=None,CCW=True,start_bend = True,stop_bend=True,pad_to_width=None,w=None,s=None,radius=None,bgcolor=None,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if radius is None:
        try:
            radius = struct().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ',chip.chipID,'!\x1b[0m')
            return
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID,'!\x1b[0m')
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')

    if pad_to_width is None and Width is not None:
        pad_to_width = True
    params = wiggle_calc(chip,structure,length,nTurns,maxWidth,Width,start_bend,stop_bend,w,0,radius,**kwargs)
    [nTurns,h,length,maxWidth,Width]=[params[key] for key in ['nTurns','h','length','maxWidth','Width']]
    if (h is None) or (nTurns is None):
        print('not enough params specified for CPW_wiggles!')
        return
    
    pm = (CCW - 0.5)*2
    
    #put rectangles on either side to line up with max width
    if pad_to_width:
        if Width is None:
            print('\x1b[33mERROR:\x1b[0m cannot pad to width with Width undefined!')
            return
        if start_bend:
            chip.add(dxf.rectangle(struct().getPos((0,h+radius+w/2)),(2*radius)+(nTurns)*4*radius,Width-(h+radius+w/2),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
            chip.add(dxf.rectangle(struct().getPos((0,-h-radius-w/2)),(stop_bend)*(radius+w/2)+(nTurns)*4*radius + radius-w/2,(h+radius+w/2)-Width,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
        else:
            chip.add(dxf.rectangle(struct().getPos((-h-radius-w/2,w/2)),(h+radius+w/2)-Width,(radius-w/2)+(nTurns)*4*radius,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
            chip.add(dxf.rectangle(struct().getPos((h+radius+w/2,-radius)),Width-(h+radius+w/2),(stop_bend)*(radius+w/2)+(nTurns)*4*radius + w/2,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
    #begin wiggles
    if start_bend:
        chip.add(dxf.rectangle(struct().getPos((0,pm*w/2)),radius+w/2,pm*(h+radius),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
        Wire_bend(chip,structure,angle=90,CCW=CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
        if h > radius:
            chip.add(dxf.rectangle(struct().getPos((0,-pm*w/2)),h+w/2,pm*(radius-w/2),valign=const.BOTTOM,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct(),length=h-radius)
        else:
            chip.add(dxf.rectangle(struct().getPos((0,-pm*w/2)),radius+w/2,pm*(radius-w/2),valign=const.BOTTOM,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
    else:
        chip.add(dxf.rectangle(struct().getPos((0,-pm*w/2)),2*radius+w/2,pm*(radius-w/2),valign=const.BOTTOM,rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct(),length=radius)
        #struct().shiftPos(h)
    chip.add(dxf.rectangle(struct().getPos((0,pm*w/2)),-h-max(h,radius)-radius-w/2,pm*(2*radius-w),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
    Wire_bend(chip,structure,angle=180,CCW=not CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
    struct().shiftPos(h+radius)
    if h > radius:
        struct().shiftPos(h-radius)
    chip.add(dxf.rectangle(struct().getPos((0,-pm*w/2)),-h-max(h,radius)-radius-w/2,pm*(-2*radius+w),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
    Wire_bend(chip,structure,angle=180,CCW=CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
    if h > radius:
        struct().shiftPos(h-radius)
    for n in range(nTurns-1):
        struct().shiftPos(h+radius)
        chip.add(dxf.rectangle(struct().getPos((0,pm*w/2)),-h-max(h,radius)-radius-w/2,pm*(2*radius-w),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
        Wire_bend(chip,structure,angle=180,CCW=not CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
        struct().shiftPos(2*h)
        chip.add(dxf.rectangle(struct().getPos((0,-pm*w/2)),-h-max(h,radius)-radius-w/2,pm*(-2*radius+w),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
        Wire_bend(chip,structure,angle=180,CCW=CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
        struct().shiftPos(h-radius)
    chip.add(dxf.rectangle(struct().getLastPos((-radius-w/2,pm*w/2)),w/2+h,pm*(radius-w/2),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct())
    if stop_bend:
        chip.add(dxf.rectangle(struct().getPos((radius+w/2,-pm*w/2)),h+radius,pm*(radius+w/2),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)))
        Wire_bend(chip,structure,angle=90,CCW=not CCW,w=w,radius=radius,bgcolor=bgcolor,**kwargs)
    else:
        #CPW_straight(chip,structure,radius,w=w,s=s,bgcolor=bgcolor)
        chip.add(dxf.rectangle(struct().getPos((0,pm*w/2)),radius,pm*(radius-w/2),rotation=struct().direction,bgcolor=bgcolor,**kwargStrip(kwargs)),structure=struct(),length=radius)
        
def TwoPinCPW_wiggles(chip,structure,w=None,s_ins=None,s_out=None,s=None,Width=None,maxWidth=None,**kwargs):
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if s is not None:
        #s overridden somewhere above
        if s_ins is None:
            s_ins = s
        if s_out is None:
            s_out = s
    if s_ins is None:
        try:
            s_ins = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if s_out is None:
        if Width is not None:
            s_out = Width - w - s_ins/2
        else:
            try:
                s_out = struct().defaults['s']
            except KeyError:
                print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
                
    s0 = struct().clone()
    maxWidth = wiggle_calc(chip,struct(),Width=Width,maxWidth=maxWidth,w=s_ins+2*w,s=0,**kwargs)['maxWidth']
    Inductor_wiggles(chip, s0, w=s_ins+2*w,Width=Width,maxWidth=maxWidth,**kwargs)
    Strip_wiggles(chip, struct(), w=s_ins,maxWidth=maxWidth-w,**kwargs)

def CPW_pincer(chip,structure,pincer_w,pincer_l,pincer_padw,pincer_tee_r=0,pad_r=None,w=None,s=None,pincer_flipped=False,bgcolor=None,**kwargs):
    '''
    pincer_w :      
    pincer_l :      length of pincer arms
    pincer_padw :   pincer pad trace width
    pincer_tee_r :  radius of tee
    pad_r:          inside radius of pincer bends
    w:              original trace width
    s:              pincer trace gap
    pincer_flipped: equivalent to hflip
    '''
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            w=0
            print('\x1b[33mw not defined in ',chip.chipID)
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID,'!\x1b[0m')
    if pad_r is None:
        pincer_r = pincer_padw/2 + s
        pad_r=0
    else:
        pincer_r = pincer_padw/2+s+abs(pad_r)#prevent negative entries
        pad_r = abs(pad_r)
        
    if not pincer_flipped: s_start = struct().clone()
    else:
        struct().shiftPos(pincer_padw+pincer_tee_r+2*s,angle=180)
        #struct().direction += 180
        s_start = struct().clone()

    s_left, s_right = CPW_tee(chip, struct(), w=w, s=s, w1=pincer_padw, s1=s, radius=pincer_tee_r + s, **kwargs)

    CPW_straight(chip, s_left, length=(pincer_w-w-2*s-2*pincer_tee_r)/2-pad_r, **kwargs)
    CPW_straight(chip, s_right, length=(pincer_w-w-2*s-2*pincer_tee_r)/2-pad_r, **kwargs)

    if pincer_l > s:
        CPW_bend(chip, s_left, CCW=True, w=pincer_padw, s=s, radius=pincer_r, **kwargs)
        CPW_straight(chip, s_left, length=pincer_l - s-pad_r, **kwargs)
        CPW_stub_open(chip, s_left, w=pincer_padw, s=s, **kwargs)

        CPW_bend(chip, s_right, CCW=False, w=pincer_padw, s=s, radius=pincer_r, **kwargs)
        CPW_straight(chip, s_right, length=pincer_l - s-pad_r, **kwargs)
        CPW_stub_open(chip, s_right, w=pincer_padw, s=s, **kwargs)
    else:
        s_left = s_left.cloneAlong(vector=(0,pincer_padw/2+s/2))
        Strip_bend(chip, s_left, CCW=True, w=s, radius=pincer_r + pincer_padw/2 - s/2, **kwargs)
        s_left = s_left.cloneAlong(vector=(s/2,s/2), newDirection=-90)
        Strip_straight(chip, s_left, length=pad_r + pincer_padw/2, w=s)

        s_right = s_right.cloneAlong(vector=(0,-pincer_padw/2-s/2))
        Strip_bend(chip, s_right, CCW=False, w=s, radius=pincer_r + pincer_padw/2 - s/2, **kwargs)
        s_right = s_right.cloneAlong(vector=(s/2,-s/2), newDirection=90)
        Strip_straight(chip, s_right, length=pad_r + pincer_padw/2, w=s)



    if not pincer_flipped:
        s_start.shiftPos(pincer_padw+pincer_tee_r+2*s)
        struct().updatePos(s_start.getPos())
    else: 
        struct().updatePos(s_start.getPos(),angle=180)
        #struct.direction = s_start.direction + 180
    
# ===============================================================================
# Airbridges (Lincoln Labs designs)
# ===============================================================================
def setupAirbridgeLayers(wafer:m.Wafer,BRLAYER='BRIDGE',RRLAYER='TETHER',brcolor=41,rrcolor=32,IBRLAYER='BRIDGE',IRRLAYER='TETHER',ibrcolor=41,irrcolor=32):
    #add correct layers to wafer, and cache layer
    wafer.addLayer(BRLAYER,brcolor)
    wafer.BRLAYER=BRLAYER
    wafer.addLayer(RRLAYER,rrcolor)
    wafer.RRLAYER=RRLAYER
    wafer.addLayer(IBRLAYER,ibrcolor)
    wafer.IBRLAYER=IBRLAYER
    wafer.addLayer(IRRLAYER,irrcolor)
    wafer.IRRLAYER=IRRLAYER

def Airbridge(
    chip, structure, cpw_w=None, cpw_s=None, xvr_width=None, xvr_length=None, rr_width=None, rr_length=None,
    rr_br_gap=None, rr_cpw_gap=None, shape_overlap=0, br_radius=0, clockwise=False, lincolnLabs=False, BRLAYER=None,
        RRLAYER=None, IBRLAYER=None, IRRLAYER=None,  layer=None, **kwargs):
    """
    Define either cpw_w and cpw_s (refers to the cpw that the airbridge goes across) or xvr_length.
    xvr_length overrides cpw_w and cpw_s.
    """
    assert lincolnLabs, 'Not implemented for normal usage'
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if cpw_w is None:
        try:
            cpw_w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID)
    if cpw_s is None:
        try:
            cpw_s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID)

    #get layers from wafer
    if layer is None:
        if BRLAYER is None:
            try:
                BRLAYER = chip.wafer.IBRLAYER
            except AttributeError:
                setupAirbridgeLayers(chip.wafer)
                BRLAYER = chip.wafer.IBRLAYER
        if RRLAYER is None:
            try:
                RRLAYER = chip.wafer.IRRLAYER
            except AttributeError:
                setupAirbridgeLayers(chip.wafer)
                RRLAYER = chip.wafer.IRRLAYER
    elif layer=='5_M1':
        if BRLAYER is None:
            try:
                BRLAYER = chip.wafer.BRLAYER
            except AttributeError:
                setupAirbridgeLayers(chip.wafer)
                BRLAYER = chip.wafer.BRLAYER
        if RRLAYER is None:
            try:
                RRLAYER = chip.wafer.RRLAYER
            except AttributeError:
                setupAirbridgeLayers(chip.wafer)
                RRLAYER = chip.wafer.RRLAYER
    elif layer=='105_IM1':
        if IBRLAYER is None:
            try:
                BRLAYER = chip.wafer.IBRLAYER
            except AttributeError:
                setupAirbridgeLayers(chip.wafer)
                BRLAYER = chip.wafer.IBRLAYER
        if IRRLAYER is None:
            try:
                RRLAYER = chip.wafer.IRRLAYER
            except AttributeError:
                setupAirbridgeLayers(chip.wafer)
                RRLAYER = chip.wafer.IRRLAYER

    if lincolnLabs:
        rr_br_gap = 1.5 # RR.BR.E.1
        if rr_cpw_gap is None: rr_cpw_gap = 2 # LL requires >= 0 (RR.E.1)
        else: assert rr_cpw_gap + rr_br_gap >= 1.5 # RR.E.1

        if xvr_length is None:
            xvr_length = cpw_w + 2*cpw_s + 2*(rr_cpw_gap)

        if 5 <= xvr_length <= 16: # BR.W.1, RR.L.1
            xvr_width = 5
            rr_length = 8
        elif 16 < xvr_length <= 27: # BR.W.2, RR.L.2
            xvr_width = 7.5
            rr_length = 10
        elif 27 < xvr_length <= 32: # BR.W.3, RR.L.3
            xvr_width = 10
            rr_length = 14
        rr_width = xvr_width + 3 # RR.W.1
        shape_overlap = 0.1 # LL requires >= 0.1
        delta = 0
        if br_radius > 0:
            r = br_radius - cpw_w/2 - cpw_s
            delta = r*(1-math.sqrt(1-1/r**2*((rr_width + 2*rr_br_gap)/2)**2))
        # this code does not check if your bend is super severe and the necessary delta
        # changes the necessary xvr_widths and rr_lengths, so don't do anything extreme

    if clockwise:
        delta_left = 0
        delta_right = delta
    else:
        delta_right = 0
        delta_left = delta

    s_left = struct().clone()
    s_left.direction += 90
    s_left.shiftPos(-shape_overlap)
    Strip_straight(chip, s_left, length=xvr_length/2+delta_left+2*shape_overlap, w=xvr_width, layer=BRLAYER, **kwargs)
    s_left.shiftPos(-shape_overlap)
    Strip_straight(chip, s_left, length=rr_length + 2*rr_br_gap, w=rr_width + 2*rr_br_gap, layer=BRLAYER, **kwargs)
    s_l = s_left.clone()
    s_left.shiftPos(-rr_length - rr_br_gap)
    Strip_straight(chip, s_left, length=rr_length, w=rr_width, layer=RRLAYER, **kwargs)

    s_right = struct().clone()
    s_right.direction -= 90
    s_right.shiftPos(-shape_overlap)
    Strip_straight(chip, s_right, length=xvr_length/2+delta_right+2*shape_overlap, w=xvr_width, layer=BRLAYER, **kwargs)
    s_right.shiftPos(-shape_overlap)
    Strip_straight(chip, s_right, length=rr_length + 2*rr_br_gap, w=rr_width + 2*rr_br_gap, layer=BRLAYER, **kwargs)
    s_r = s_right.clone()
    s_right.shiftPos(-rr_length - rr_br_gap)
    Strip_straight(chip, s_right, length=rr_length, w=rr_width, layer=RRLAYER, **kwargs)

    return s_l, s_r


def CPW_bridge(chip, structure, xvr_length=None, w=None, s=None, lincolnLabs=False, BRLAYER=None, RRLAYER=None, **kwargs):
    """
    Draws an airbridge to bridge two sections of CPW, as well as the necessary connections.
    w, s are for the CPW we want to connect.
    structure is oriented at the same place as the structure for Airbridge.
    """
    assert lincolnLabs, 'Not implemented for normal usage'
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID)
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ',chip.chipID)

    if lincolnLabs:
        rr_br_gap = 1.5 # RR.BR.E.1
        rr_cpw_gap = 0 # LL requires >= 0 (RR.E.1)
        if xvr_length is None:
            xvr_length = w + 2*s + 2*(rr_cpw_gap)
        if 5 <= xvr_length <= 16:
            xvr_width = 5
            rr_length = 8
        elif 16 < xvr_length <= 27:
            xvr_width = 7.5
            rr_length = 10
        elif 27 < xvr_length <= 32:
            xvr_width = 10
            rr_length = 14
        else:
            assert False, f'xvr_length {xvr_length} is out of range'
        rr_width = xvr_width + 3

    s_left, s_right = Airbridge(chip, struct(), xvr_length=xvr_length, lincolnLabs=lincolnLabs, **kwargs)

    s_left.shiftPos(-rr_length - 2*rr_br_gap - rr_cpw_gap)
    CPW_straight(chip, s_left, length=rr_length + 2*rr_br_gap + rr_cpw_gap, w=rr_width + 2*rr_br_gap, s=s, **kwargs)
    CPW_taper(chip, s_left, length=rr_length + 2*rr_br_gap, w0=rr_width+2*rr_br_gap, s0=s, w1=w, s1=s, **kwargs)

    s_right.shiftPos(-rr_length - 2*rr_br_gap - rr_cpw_gap)
    CPW_straight(chip, s_right, length=rr_length + 2*rr_br_gap + rr_cpw_gap, w=rr_width + 2*rr_br_gap, s=s, **kwargs)
    CPW_taper(chip, s_right, length=rr_length + 2*rr_br_gap, w0=rr_width + 2*rr_br_gap, s0=s, w1=w, s1=s, **kwargs)

    return s_left, s_right

# ===============================================================================
# CPS (coplanar stripline) function definitions — ported from personal work in
# the chakramlab/maskLib clone (uncommitted there), for use in Fast_Flux designs
# ===============================================================================
def Double_Y_balun(chip, structure, arm_length=500, w=2, s=100, cpw_s=2, cpw_w=2, gnd_width=50, rotation=0, bgcolor=None, **kwargs):

    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if bgcolor is None:
        bgcolor = chip.wafer.bg()

    center = struct().start
    base_direction = struct().direction + rotation

    def offset_start(angle_deg, offset):
        angle_rad = math.radians(angle_deg)
        return (center[0] + offset * math.cos(angle_rad),
                center[1] + offset * math.sin(angle_rad))

    gap_offset = w / 2

    # CPS port 1: arms at +30° (open end) and +150° (short end)
    cps1_end   = m.Structure(chip, offset_start(base_direction + 30,  gap_offset), direction=base_direction + 30)
    cps1_short = m.Structure(chip, offset_start(base_direction + 150, gap_offset), direction=base_direction + 150)
    CPS_straight(chip, cps1_end,   arm_length, w=w, s=s)
    CPS_straight(chip, cps1_short, arm_length, w=w, s=s)

    # CPW port: arms at -30° and -150° — drawn as positive metal
    cpw1_end   = m.Structure(chip, offset_start(base_direction - 30,  gap_offset), direction=base_direction - 30)
    cpw1_short = m.Structure(chip, offset_start(base_direction - 150, gap_offset), direction=base_direction - 150)
    CPW_straight_pos(chip, cpw1_end,   arm_length, w=cpw_s, s=cpw_w, gnd_width=gnd_width)
    CPW_straight_pos(chip, cpw1_short, arm_length, w=cpw_s, s=cpw_w, gnd_width=gnd_width)

    # CPW in arm at +90° and CPS out arm at -90°
    cpw_in  = m.Structure(chip, offset_start(base_direction + 90, gap_offset), direction=base_direction + 90)
    cps_out = m.Structure(chip, offset_start(base_direction - 90, gap_offset), direction=base_direction - 90)
    CPW_straight_pos(chip, cpw_in,  arm_length, w=cpw_s, s=cpw_w, gnd_width=gnd_width)
    CPS_straight(chip, cps_out, arm_length, w=w, s=s)

    # CPS Short bridge at tip of cps1_short arm
    tip = offset_start(base_direction + 150, gap_offset + arm_length)
    chip.add(dxf.rectangle(
        tip, s, w + 2*s,
        valign=const.MIDDLE,
        rotation=base_direction + 150,
        bgcolor=bgcolor,
        **kwargStrip(kwargs)))


def CPS_structure(chip, start, direction=0, w=6, strip=10, radius=100):

    s = m.Structure(chip, start, direction)

    s.defaults['w'] = w
    s.defaults['s'] = strip
    s.defaults['radius'] = radius
    return s
def CPS_straight(chip, structure, length, w=None, s=None, bgcolor=None, **kwargs):
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')

    # Draw two metal strips of width s, separated by gap w
    # In CPW, rectangles were drawn at ±w/2 outward (the gaps)
    # In CPS, we draw the conductors at ±w/2 inward (the strips)
    chip.add(dxf.rectangle(struct().getPos((0, -w/2)), length, -s,
             rotation=struct().direction, bgcolor=bgcolor, **kwargStrip(kwargs)))
    chip.add(dxf.rectangle(struct().getPos((0,  w/2)), length,  s,
             rotation=struct().direction, bgcolor=bgcolor, **kwargStrip(kwargs)),
             structure=structure, length=length)

    return struct().getPos()


def CPS_bend(chip, structure, angle=90, CCW=True, w=None, s=None, radius=None,
             ptDensity=120, bgcolor=None, **kwargs):
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID)
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID)
    if radius is None:
        try:
            radius = struct().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ', chip.chipID, '!\x1b[0m')
            return
    if bgcolor is None:
        bgcolor = chip.wafer.bg()

    while angle < 0:
        angle = angle + 360
    angle = angle % 360
    angleRadians = math.radians(angle)

    # Mirror of CPW_bend: CurveRects are drawn at ±w/2 as the metal strips
    # roffset places the inner edge of each strip at the gap boundary (±w/2)
    # ralign=BOTTOM grows outward from the gap edge, matching CPW strip geometry
    chip.add(CurveRect(struct().start, s, radius, angle=angle, ptDensity=ptDensity,
             roffset=w/2,  ralign=const.BOTTOM,
             rotation=struct().direction, vflip=not CCW, bgcolor=bgcolor, **kwargs))
    chip.add(CurveRect(struct().start, s, radius, angle=angle, ptDensity=ptDensity,
             roffset=-w/2, ralign=const.TOP, valign=const.TOP,
             rotation=struct().direction, vflip=not CCW, bgcolor=bgcolor, **kwargs))

    struct().updatePos(
        newStart=struct().getPos((
            radius * math.sin(angleRadians),
            (CCW and 1 or -1) * radius * (math.cos(angleRadians) - 1)
        )),
        angle=CCW and -angle or angle
    )

def _originCompensatedInsert(chip, insert, rotation_deg):
    ''' Chip.add() shifts the .points of eager SolidPline-based shapes (SkewRect, RoundRect,
    Star, ...) by chip.origin_offset while they're still in their local, pre-rotation frame -
    that shift then gets rotated along with the rest of the shape's points, instead of applying
    untransformed to the insert point like it would for a plain dxf.rectangle. Pre-correct the
    insert point here so the shape ends up where callers actually asked for it. '''
    r_oo = rotate_2d(chip.origin_offset, math.radians(rotation_deg))
    return (insert[0] - r_oo[0], insert[1] - r_oo[1])

def CPS_taper(chip, structure, length=None, w0=None, s0=None, w1=None, s1=None, bgcolor=None, offset=(0,0), **kwargs):
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w0 is None:
        try:
            w0 = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
    if s0 is None:
        try:
            s0 = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')
    if w1 is None:
        try:
            w1 = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
    if s1 is None:
        try:
            s1 = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')

    # If undefined, make outer angle 30 degrees (matching CPW convention)
    # In CPS the outer edge is at w/2 + s, same as CPW, so formula is identical
    if length is None:
        length = math.sqrt(3) * abs(w0/2 + s0 - w1/2 - s1)

    # Lower strip: starts at -w0/2 (inner edge), grows downward by s0
    # skews so inner edge tracks -w1/2 at the far end
    chip.add(SkewRect(_originCompensatedInsert(chip, struct().getPos((0, -w0/2)), struct().direction), length, s0,
             (offset[0], w0/2 - w1/2 + offset[1]), s1,
             rotation=struct().direction, valign=const.TOP, edgeAlign=const.TOP,
             bgcolor=bgcolor, **kwargs))
    # Upper strip: starts at +w0/2 (inner edge), grows upward by s0
    # skews so inner edge tracks +w1/2 at the far end
    chip.add(SkewRect(_originCompensatedInsert(chip, struct().getPos((0,  w0/2)), struct().direction), length, s0,
             (offset[0], w1/2 - w0/2 + offset[1]), s1,
             rotation=struct().direction, valign=const.BOTTOM, edgeAlign=const.BOTTOM,
             bgcolor=bgcolor, **kwargs), structure=structure, offsetVector=(length + offset[0], offset[1]))

def CPS_circular_taper(chip, structure, length=None, w0=None, s0=None, w1=None, s1=None,
                        ptDensity=60, bgcolor=None, **kwargs):
    """
    CPS taper where the strip width follows a concave circular profile,
    pinching inward (narrowest at the midpoint) between s0 and s1.

    Parameters
    ----------
    length    : total length of the taper
    w0, w1    : gap width at start and end (usually kept equal for CPS)
    s0, s1    : strip width at start and end
    ptDensity : number of segments to approximate the curve
    """
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w0 is None:
        try:
            w0 = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
    if s0 is None:
        try:
            s0 = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')
    if w1 is None:
        w1 = w0
    if s1 is None:
        s1 = s0
    if length is None:
        length = math.sqrt(3) * abs(w0/2 + s0 - w1/2 - s1)

    # Build circular concave profile for strip width along the taper.
    # The profile is a circular arc that passes through s0 at x=0,
    # dips to a minimum at x=length/2, and returns to s1 at x=length.
    #
    # We define the circular arc by fitting a circle through:
    #   (0, s0), (length/2, s_mid), (length, s1)
    # where s_mid is the minimum strip width (narrowest point).
    # s_mid is derived from the geometry of the circle passing through
    # the endpoints, giving a natural concave curve.
    #
    # For simplicity we use a cosine-approximated circular profile:
    #   s(x) = s_avg - (s_amp)*cos(pi*x/length)
    # where s_avg and s_amp are chosen to match s0 and s1 at endpoints.

    n = ptDensity
    seg_length = length / n

    for i in range(n):
        x0 = i * seg_length
        x1 = (i + 1) * seg_length

        # Normalized positions [0,1]
        t0 = x0 / length
        t1 = x1 / length

        # Concave circular profile using sine:
        # width is s0/s1 at ends, dips to minimum at midpoint
        # sin(pi*t) is 0 at ends, 1 at midpoint — invert for concave
        s_at_t0 = s0 + (s1 - s0) * t0 - min(s0, s1) * math.sin(math.pi * t0)
        s_at_t1 = s0 + (s1 - s0) * t1 - min(s0, s1) * math.sin(math.pi * t1)

        # Gap interpolated linearly
        w_at_t0 = w0 + (w1 - w0) * t0
        w_at_t1 = w0 + (w1 - w0) * t1

        # Draw bottom strip segment: inner edge at -w/2, grows downward
        chip.add(SkewRect(
            _originCompensatedInsert(chip, struct().getPos((x0, -w_at_t0/2)), struct().direction), seg_length, s_at_t0,
            (0, w_at_t0/2 - w_at_t1/2), s_at_t1,
            rotation=struct().direction, valign=const.TOP, edgeAlign=const.TOP,
            bgcolor=bgcolor, **kwargs))

        # Draw top strip segment: inner edge at +w/2, grows upward
        chip.add(SkewRect(
            _originCompensatedInsert(chip, struct().getPos((x0,  w_at_t0/2)), struct().direction), seg_length, s_at_t0,
            (0, w_at_t1/2 - w_at_t0/2), s_at_t1,
            rotation=struct().direction, valign=const.BOTTOM, edgeAlign=const.BOTTOM,
            bgcolor=bgcolor, **kwargs))

    # Advance structure by full length
    struct().updatePos(newStart=struct().getPos((length, 0)), angle=0)

def CPS_capPad(chip, structure, pad_length, pad_width, w=None, bgcolor=None, **kwargs):
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)
    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
            return

    # Lower pad: inner edge at -w/2, grows downward by pad_width
    chip.add(dxf.rectangle(struct().getPos((0, -w/2)), pad_length, -pad_width,
             rotation=struct().direction, bgcolor=bgcolor, **kwargStrip(kwargs)))
    # Upper pad: inner edge at +w/2, grows upward by pad_width
    chip.add(dxf.rectangle(struct().getPos((0,  w/2)), pad_length,  pad_width,
             rotation=struct().direction, bgcolor=bgcolor, **kwargStrip(kwargs)),
             structure=structure, length=pad_length)


def CPS_hairpin_filter(chip, structure, resonators, bgcolor=None, **kwargs):
    """
    Draws a 7th order (or arbitrary order) CPS hairpin filter.
    Starts and ends with a capacitive pad.

    Parameters
    ----------
    resonators : list of dicts, each with keys:
        'straight1'  : length of the first straight section (default 1000)
        'straight2'  : length of the hairpin straight section (default 2200)
        'straight3'  : length of the last straight section (default 1000)
        'taper_in'   : (length, w0, s0, w1, s1) for input taper
        'pad_length' : length of capacitive pad
        'pad_width'  : width of capacitive pad
        'taper_out'  : (length, w0, s0, w1, s1) for output taper
        'w'          : CPS gap width, shared by the capacitive pad and the
                       hairpin meander line (defaults to structure's 'w' default)
        's'          : CPS strip width of the hairpin meander line (defaults to
                       structure's 's' default; the pad's own strip width is
                       set separately via 'pad_width')
    """
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    for i, res in enumerate(resonators):


        straight1 = res.get('straight1', 1500)
        straight2 = res.get('straight2', 3200)
        straight3 = res.get('straight3', 1500)

        taper_in  = res.get('taper_in',  (50, 6, 10, 6, 70))
        taper_out = res.get('taper_out', (50, 6, 70, 6, 10))

        pad_length = res.get('pad_length', 2000)
        pad_width  = res.get('pad_width',  2000)
        w = res.get('w', None)
        s = res.get('s', None)

        # Leading capacitive pad
        CPS_circular_taper(chip, structure, *taper_in)
        CPS_capPad(chip, structure, pad_length, pad_width, w=w)
        CPS_circular_taper(chip, structure, *taper_out)

        # Hairpin shape
        CPS_bend(chip, structure, angle=90,  CCW=False, w=w, s=s)
        CPS_straight(chip, structure, length=straight1, w=w, s=s)
        CPS_bend(chip, structure, angle=180, w=w, s=s)
        CPS_straight(chip, structure, length=straight2, w=w, s=s)
        CPS_bend(chip, structure, angle=180, CCW=False, w=w, s=s)
        CPS_straight(chip, structure, length=straight3, w=w, s=s)
        CPS_bend(chip, structure, angle=90, w=w, s=s)

    # Trailing capacitive pad after the last resonator
    last = resonators[-1]
    taper_in  = last.get('taper_in',  (50, 6, 10, 6, 70))
    taper_out = last.get('taper_out', (50, 6, 70, 6, 10))
    pad_length = last.get('pad_length', 2000)
    pad_width  = last.get('pad_width',  2000)
    w = last.get('w', None)

    CPS_circular_taper(chip, structure, *taper_in)
    CPS_capPad(chip, structure, pad_length, pad_width, w=w)
    CPS_circular_taper(chip, structure, *taper_out)


def CPS_patch_filter(chip, structure, resonators, bgcolor=None, **kwargs):
    """
    Edge-coupled (combline-style) CPS bandpass filter: a chain of rectangular
    resonator patches connected end-to-end by short narrow tabs, instead of
    CPS_hairpin_filter's single continuously-meandering line. Each patch acts
    as its own resonator, coupled to its neighbors mainly through proximity/
    fringing fields at the tab junctions rather than a long shared conductor -
    matching the stacked-patch filter topology in arXiv:2503.13953 Fig. 10(a,d).

    Parameters
    ----------
    resonators : list of dicts, each with keys:
        'patch_length'     : length of the resonator patch along the line (default 2000)
        'patch_width'       : CPS strip width of the patch (default 2000)
        'gap'               : CPS gap width for both the patch and its connector
                              (defaults to structure's 'w' default)
        'connector_length'  : length of the narrow tab to the *next* patch (default 50)
        'connector_width'   : CPS strip width of that connecting tab
                              (defaults to structure's 's' default)
    The last resonator's connector_length/connector_width are ignored (no trailing tab).
    """
    for i, res in enumerate(resonators):
        patch_length = res.get('patch_length', 2000)
        patch_width  = res.get('patch_width', 2000)
        gap = res.get('gap', None)

        CPS_capPad(chip, structure, patch_length, patch_width, w=gap, bgcolor=bgcolor, **kwargs)

        if i < len(resonators) - 1:
            connector_length = res.get('connector_length', 50)
            connector_width  = res.get('connector_width', None)
            CPS_straight(chip, structure, connector_length, w=gap, s=connector_width, bgcolor=bgcolor, **kwargs)


def tapped_hairpin_filter(chip, structure, n_poles=4,
                           arm_length=4330, hairpin_width=2000, line_width=500,
                           gap=None, coupling_gaps=(333.8, 461.8, 333.8),
                           tap_point=486.1, tap_width=399.6,
                           length_trim=0.0, flip_alternate=True,
                           tap_lead=100, tap_taper_length=50, bgcolor=None, **kwargs):
    """
    Parameterized tapped hairpin-line CPW bandpass filter: n_poles folded
    half-wave resonators, edge-coupled side by side, with tapped I/O
    coupling on the first and last resonator (Wong, IEEE Trans. MTT 1979;
    Hong & Lancaster ch. 5 tapped-line design).

    Dimensions (arm_length, hairpin_width, coupling_gaps, tap_point,
    tap_width) are taken directly rather than derived from f0/eps_eff -
    this matches a Nuhertz Filter Solutions synthesis run (microstrip, Si,
    500um) that hands over topology + starting physical dimensions
    directly. Two caveats carried over from that synthesis, both out of
    scope to resolve here:
      - our actual stack has NO backside metal, so this is really a CPW
        structure (center conductor + gap slots on the same top metal
        layer), not microstrip. Nuhertz's output has no equivalent to a
        CPW gap - `gap` must be picked/tuned independently of the
        synthesis.
      - even with a gap chosen, the synthesized lengths/couplings assume a
        microstrip field distribution and will need HFSS re-extraction
        once the real (bare-chip, package-grounded) environment is
        modeled.
    Treat every dimension here as a placeholder pending that HFSS pass.

    structure : positioned/oriented like any other CPW composite call. Its
        `.start` is resonator 0's open tip (arm A) and `.direction`
        defines the arm axis - it may be any angle, not just +/-90 (e.g.
        direction=0 lays the array out with arms along the chip's X axis,
        stacking along Y, matching a "hairpins across the width" layout).
        Successive resonators stack along the perpendicular axis
        (structure's local "direction - 90"), alternating arm-forward/
        arm-backward orientation (see flip_alternate) so adjacent arms
        face each other in the standard hairpin-ladder arrangement.
    n_poles : number of hairpin resonators (poles).
    arm_length : straight length (um) of each hairpin arm.
    hairpin_width : outer edge-to-edge extent (um) of one hairpin's two
        arms (center-to-center arm spacing + line_width). Sets the U-bend
        radius as (hairpin_width - line_width) / 2.
    line_width : CPW center conductor width (um) of the main resonator/
        feed line.
    gap : CPW gap width (um) for the main line. Defaults to structure's
        own 's' default if not given - see the no-backside-metal caveat
        above; this has no Nuhertz equivalent and needs independent
        tuning.
    coupling_gaps : edge-to-edge gap (um) between adjacent hairpins' facing
        arms. Must have length n_poles-1.
    tap_point : distance (um) from the U-bend ("joint") to the I/O tap,
        measured along the arm. Resonator 0 is tapped on arm A (the arm
        ending at the joint, i.e. tap_point measured back from arm A's own
        open tip works out to arm_length - tap_point from that open tip);
        resonator n_poles-1 is tapped on arm B (the arm starting at the
        joint, so tap_point there is measured directly from where the
        U-bend ends). Tapping each end resonator on its OWN outer arm
        (arm A is resonator 0's outer/edge-facing arm; arm B is resonator
        n_poles-1's outer/edge-facing arm - see outward_branch in the
        source) is what makes the two taps literal mirror images of each
        other, each escaping toward its own edge of the array with no
        risk of crossing its sibling arm. Must clear the tee junction's
        own footprint on both sides - see tap_width below; the function
        raises ValueError if it doesn't.
    tap_width : CPW center conductor width (um) of the tap branch itself,
        applied via a short taper immediately after the tee (see
        tap_taper_length) rather than at the tee junction itself.
        CPW_tee's own corner geometry (CurveRect/InsideCurve fillets) is
        keyed off the main line's width regardless of its w1 argument, so
        branching directly at tap_width whenever tap_width != line_width
        leaves a real, visible gap in the gap-boundary polyline (confirmed
        by isolating CPW_tee with generous clearance on all sides - it's
        not a tight-fit artifact). Tapping AFTER the tee avoids ever
        calling CPW_tee with mismatched widths. Because of this, the tee
        itself always has an effective branch width of line_width, so
        tap_point must clear a footprint of 2*(max(gap, gap-at-tee) +
        line_width/2) - for line_width=500 that's >=500um regardless of
        gap, well above Nuhertz's raw 486.1um tap_point; this dimension
        needs to be re-derived in HFSS anyway, so bump it up rather than
        fight the tee.
    length_trim : global fractional length fudge factor for HFSS retuning
        (arm_length *= (1 + length_trim)).
    flip_alternate : standard hairpin ladder (True) alternates each
        resonator's U-bend orientation so adjacent arms face each other.
        False keeps every resonator in the same orientation.
    tap_lead : short straight CPW lead (um) drawn right after each I/O tap
        junction (and after the tap_taper_length transition to tap_width),
        so the returned tap structures sit clear of the tee geometry
        before the caller extends them further.
    tap_taper_length : length (um) of the CPW_taper from line_width down
        to tap_width, immediately after the tee (see tap_width above).

    Returns
    -------
    (tap_in, tap_out) : new Structures at the input/output tap points,
        ready to be extended (e.g. CPW_straight/CPW_bend/CPW_launcher)
        toward the feed launcher and the downstream circuit (e.g. a
        lowpass cleanup section / SNAIL) respectively. tap_in exits
        resonator 0's arm A toward global "D0+90" (away from the rest of
        the array, toward the array's near/start edge); tap_out exits
        resonator n_poles-1's arm B toward global "D0-90" (also away from
        the rest of the array, toward the array's far/growth-direction
        edge) - literal mirror images of each other, each on its own
        resonator's outer arm, each already facing away from the whole
        array with no further redirect needed before continuing on to the
        launcher / downstream circuit.
    """
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    w = line_width
    if gap is None:
        try:
            gap = struct().defaults['s']
        except KeyError:
            print('\x1b[33mgap not defined in ', chip.chipID, '!\x1b[0m')
    s = gap
    if bgcolor is None:
        bgcolor = chip.wafer.bg()

    if len(coupling_gaps) != n_poles - 1:
        raise ValueError('coupling_gaps must have %d entries for n_poles=%d, got %d' %
                          (n_poles - 1, n_poles, len(coupling_gaps)))
    if hairpin_width <= line_width:
        raise ValueError('hairpin_width (%s) must be greater than line_width (%s)' % (hairpin_width, line_width))

    arm_length = arm_length * (1 + length_trim)
    radius = (hairpin_width - line_width) / 2
    tee_radius = s

    # CPW_tee (branch_off=LEFT/RIGHT) leaves the main structure's direction
    # unchanged but silently advances its position along that direction by
    # 2*(max(tee_radius, s) + w1/2) - two internal +/-90 degree rotations
    # that cancel out in direction but not in translation. This was
    # negligible at the old (w=10, s=6) prototype scale but is significant
    # at these Nuhertz-derived dimensions, so it must be subtracted from
    # the straight run between the tee and the U-bend, or the resonator's
    # developed length silently grows. w1=w (not tap_width) here - see the
    # tap_width docstring entry for why the tee itself always branches at
    # line_width.
    tee_extra_length = 2 * (max(tee_radius, s) + w / 2)

    tap_dist_from_open = arm_length - tap_point
    if not (0 < tap_dist_from_open < arm_length):
        raise ValueError('tap_point=%s places the tap outside the resonator arm (arm_length=%.1fum)' %
                          (tap_point, arm_length))
    # Both ends of the array get their tap on whichever arm is that
    # resonator's OWN "outer" arm (arm A - the one drawn first, ending at
    # the U-bend - for resonator 0; arm B - the one drawn after the U-bend -
    # for resonator n_poles-1), so the tee footprint must clear the U-bend
    # on BOTH sides of the tap point, not just the tap_point side: arm A's
    # tee sits between the tap and the joint (needs tap_point >
    # tee_extra_length), arm B's tee sits between the joint and the tap
    # (needs tap_dist_from_open > tee_extra_length, since arm B's pre-tee
    # run is tap_point and its post-tee run to the open tip is
    # tap_dist_from_open - tee_extra_length).
    if tap_point <= tee_extra_length or tap_dist_from_open <= tee_extra_length:
        raise ValueError(
            'tap_point=%s (and its complement %.1fum) is too close to the U-bend to fit '
            'the tap tee junction on both the input and output arms '
            '(tee footprint along the arm is %.1fum, set by gap=%s and line_width=%s - '
            'the tee always branches at line_width, not tap_width, see the tap_width '
            'docstring entry) - increase tap_point (or move it closer to arm_length/2), '
            'or shrink gap/line_width, and re-check in HFSS' %
            (tap_point, tap_dist_from_open, tee_extra_length, s, w))

    D0 = struct().direction

    def outward_branch(forward_i):
        # branch_off=LEFT gives a tap in the current structure's own
        # (direction+90) direction, RIGHT gives (direction-90) - validated
        # empirically against CPW_tee's output. This same rule is reused
        # for both arm A (pre-U-bend, direction D0 if forward_i else
        # D0+180) and arm B (post-U-bend, direction D0+180 if forward_i
        # else D0 - always the OPPOSITE of arm A's, since the 180 degree
        # bend's net global displacement is always toward D0-90 regardless
        # of forward_i, confirmed by extracting drawn geometry) taps. The
        # SAME "LEFT if forward_i else RIGHT" choice therefore lands arm
        # A's tap on global D0+90 and arm B's tap on global D0-90 - each
        # is the direction away from that resonator's OTHER (sibling) arm,
        # so neither ever crosses it. This is what makes the input tap
        # (arm A of resonator 0, escaping D0+90 toward one edge) and the
        # output tap (arm B of resonator n_poles-1, escaping D0-90 toward
        # the other edge) literal mirror images of each other.
        return const.LEFT if forward_i else const.RIGHT

    def draw_tapped_arm(sA, forward_i, dist_to_tap, dist_after_tap, do_tap):
        # Draws one arm's straight run from sA's current position, with an
        # optional I/O tee tap inserted dist_to_tap along it. Shared by
        # both arm A (dist_to_tap=tap_dist_from_open) and arm B
        # (dist_to_tap=tap_point) - see outward_branch above for why the
        # same branch formula is correct for both.
        if not do_tap:
            CPW_straight(chip, sA, dist_to_tap + dist_after_tap, w=w, s=s, bgcolor=bgcolor, **kwargs)
            return None
        CPW_straight(chip, sA, dist_to_tap, w=w, s=s, bgcolor=bgcolor, **kwargs)
        branch = outward_branch(forward_i)
        # w1=w (not tap_width): CPW_tee's corner fillets are keyed off
        # the main line's width regardless of w1, so branching directly
        # at a different tap_width leaves a real gap in the gap-boundary
        # polyline (confirmed by isolating CPW_tee with generous
        # clearance - not a tight-fit artifact). Get to tap_width via a
        # taper immediately after the tee instead.
        tap_struct = CPW_tee(chip, sA, w=w, s=s, w1=w, s1=s, radius=tee_radius,
                              branch_off=branch, bgcolor=bgcolor, **kwargs)
        if tap_taper_length > 0 and tap_width != w:
            CPW_taper(chip, tap_struct, length=tap_taper_length, w0=w, s0=s, w1=tap_width, s1=s,
                      bgcolor=bgcolor, **kwargs)
        if tap_lead > 0:
            CPW_straight(chip, tap_struct, tap_lead, w=tap_width, s=s, bgcolor=bgcolor, **kwargs)
        CPW_straight(chip, sA, dist_after_tap, w=w, s=s, bgcolor=bgcolor, **kwargs)
        return tap_struct

    tap_in = None
    tap_out = None
    cum_pitch = 0.0
    for i in range(n_poles):
        forward_i = True if not flip_alternate else (i % 2 == 0)
        direction_i = D0 if forward_i else D0 + 180
        along_i = 0.0 if forward_i else arm_length
        sA_start = struct().getPos((along_i, -cum_pitch))

        sA = m.Structure(chip, start=sA_start, direction=direction_i, defaults=struct().defaults)
        # length/r_out passed explicitly (r_out < length) rather than left to
        # defaults: RoundRect's corner arc collapses onto the adjacent square
        # corner (a duplicate/zero-length vertex) whenever r_out clamps to
        # exactly equal the stub length - easy to hit with typical defaults.
        CPW_stub_open(chip, sA, flipped=True, w=w, s=s, length=2*s, r_out=s, bgcolor=bgcolor, **kwargs)

        tap_a = draw_tapped_arm(sA, forward_i, tap_dist_from_open,
                                 arm_length - tap_dist_from_open - tee_extra_length,
                                 do_tap=(i == 0))
        if i == 0:
            tap_in = tap_a

        CPW_bend(chip, sA, angle=180, CCW=forward_i, radius=radius, w=w, s=s, bgcolor=bgcolor, **kwargs)

        tap_b = draw_tapped_arm(sA, forward_i, tap_point,
                                 arm_length - tap_point - tee_extra_length,
                                 do_tap=(i == n_poles - 1))
        if i == n_poles - 1:
            tap_out = tap_b

        CPW_stub_open(chip, sA, w=w, s=s, length=2*s, r_out=s, bgcolor=bgcolor, **kwargs)

        if i < n_poles - 1:
            cum_pitch += hairpin_width + coupling_gaps[i]

    return tap_in, tap_out


def stepped_impedance_lpf(chip, structure, n_sections=7,
                           w_hi=100, w_lo=1800, w_feed=500,
                           section_lengths=None, total_length=3500,
                           gap=None, taper_length=20, bgcolor=None, **kwargs):
    """
    Placeholder stepped-impedance lowpass filter: n_sections alternating
    high-Z (narrow, w_hi) / low-Z (wide, w_lo) CPW sections in series,
    starting and ending on a high-Z section (standard stepped-impedance
    LPF topology), short-tapered to/from w_feed at the ports.

    This is UNSYNTHESIZED placeholder geometry - n_sections/w_hi/w_lo and
    especially section_lengths are not yet tied to a real cutoff/
    rejection target. Run a proper stepped-impedance synthesis (Nuhertz or
    Hong & Lancaster tables) for the real cutoff and feed the resulting
    section_lengths back in before trusting this for anything beyond
    floorplanning.

    structure : positioned/oriented like any other CPW composite call;
        mutated in place to sit at the output port, ready for the caller
        to continue (e.g. toward the SNAIL).
    n_sections : number of alternating hi/lo-Z sections (should be odd, so
        the filter starts and ends on a high-Z section).
    w_hi, w_lo : CPW center conductor width (um) of the high-Z (narrow)
        and low-Z (wide) sections.
    w_feed : CPW center conductor width (um) of the line feeding in/out
        (should match the upstream/downstream line, e.g. the bandpass
        filter's line_width).
    section_lengths : list of n_sections lengths (um). If None, splits
        total_length evenly among all sections as a placeholder.
    total_length : total placeholder length (um), used only when
        section_lengths is None.
    gap : CPW gap width (um), held constant across all sections (a real
        design would vary it with width to hold an impedance target -
        out of scope here). Defaults to structure's own 's' if not given.
    taper_length : length (um) of the width transition between adjacent
        sections. Deliberately short and fixed (rather than CPW_taper's
        default ~30-degree auto-sized taper, which would run to ~1.5mm for
        a w_hi/w_lo swing this large) - a "stepped" impedance filter wants
        near-abrupt steps, not long smooth tapers eating into the section
        lengths that actually set the cutoff.

    Returns
    -------
    The (possibly newly-resolved) Structure at the output port, mutated in
    place - use this (rather than the original `structure` argument, which
    may have been a tuple/index) to continue building downstream.
    """
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if gap is None:
        try:
            gap = struct().defaults['s']
        except KeyError:
            print('\x1b[33mgap not defined in ', chip.chipID, '!\x1b[0m')
    s = gap
    if bgcolor is None:
        bgcolor = chip.wafer.bg()

    if section_lengths is None:
        section_lengths = [total_length / n_sections] * n_sections
    if len(section_lengths) != n_sections:
        raise ValueError('section_lengths must have %d entries for n_sections=%d, got %d' %
                          (n_sections, n_sections, len(section_lengths)))

    s_ref = struct()

    CPW_taper(chip, s_ref, length=taper_length, w0=w_feed, s0=s, w1=w_hi, s1=s, bgcolor=bgcolor, **kwargs)
    prev_w = w_hi
    for i, length in enumerate(section_lengths):
        this_w = w_hi if i % 2 == 0 else w_lo
        if this_w != prev_w:
            CPW_taper(chip, s_ref, length=taper_length, w0=prev_w, s0=s, w1=this_w, s1=s, bgcolor=bgcolor, **kwargs)
        CPW_straight(chip, s_ref, length, w=this_w, s=s, bgcolor=bgcolor, **kwargs)
        prev_w = this_w
    CPW_taper(chip, s_ref, length=taper_length, w0=prev_w, s0=s, w1=w_feed, s1=s, bgcolor=bgcolor, **kwargs)

    return s_ref


def CPS_loop(chip, structure, loop_width=None, loop_height=None, w=None, s=None, radius=None, bgcolor=None, **kwargs):
    """
    Splits a CPS line into two symmetric striplines that form a rectangular
    loop and merge back into a single CPS line at the far end.

    Parameters
    ----------
    loop_width  : total width of the loop (distance between the two parallel
                  long sides). Defaults to 500.
    loop_height : length of the long sides of the loop. Defaults to 2000.
    w           : gap between striplines (from defaults['w'])
    s           : strip width (from defaults['s'])
    radius      : bend radius (from defaults['radius'])
    """
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
            return
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')
            return
    if radius is None:
        try:
            radius = struct().defaults['radius']
        except KeyError:
            print('\x1b[33mradius not defined in ', chip.chipID, '!\x1b[0m')
            return
    if loop_width is None:
        loop_width = 500
    if loop_height is None:
        loop_height = 2000

    # The two strips need to diverge by loop_width/2 each side.
    # Account for the radius so the straight sections meet cleanly.
    # Each strip travels: out 90°, straight loop_height, back 90°,
    # straight loop_width - 2*radius, back 90°, straight loop_height,
    # back 90° to merge.

    # We use two independent structures cloned from the current position,
    # one for each strip, then advance the original structure to the end point.

    top_struct    = struct().clone()
    bottom_struct = struct().clone()

    top_struct.translatePos(vector=(0,  -(w/2 + s/2)))
    bottom_struct.translatePos(vector=(0,  w/2 + s/2))

    #top_struct.shiftPos(0, newDir=-90)
   # bottom_struct.shiftPos(0, newDir=-90)
    # --- Top strip (CCW=True, bends upward) ---
    # Each clone only draws one of the two rectangles per CPS call,
    # so we use Strip_ functions for individual line drawing.

    # Diverge outward
    Strip_bend(chip, top_struct,    angle=90, CCW=True,  w=s, radius=radius)
    Strip_bend(chip, bottom_struct, angle=90, CCW=False, w=s, radius=radius)

    # Long sides
    Strip_straight(chip, top_struct,    length=loop_height, w=s)
    Strip_straight(chip, bottom_struct, length=loop_height, w=s)

    # Turn back inward
    Strip_bend(chip, top_struct,    angle=90, CCW=False, w=s, radius=radius)
    Strip_bend(chip, bottom_struct, angle=90, CCW=True,  w=s, radius=radius)

    # Short closing side (loop_width - 2*radius on each strip's path)
    closing_length = loop_width - 2 * radius
    if closing_length > 0:
        Strip_straight(chip, top_struct,    length=closing_length, w=s)
        Strip_straight(chip, bottom_struct, length=closing_length, w=s)

    # Turn to face back toward original direction
    Strip_bend(chip, top_struct,    angle=90, CCW=False, w=s, radius=radius)
    Strip_bend(chip, bottom_struct, angle=90, CCW=True,  w=s, radius=radius)

    # Long sides back
    Strip_straight(chip, top_struct,    length=loop_height+radius+w/2+s/2, w=s)
    Strip_straight(chip, bottom_struct, length=loop_height+radius+w/2+s/2, w=s)


    # Advance the main structure to the end of the loop
    # Total forward advance = loop_width (the two 90° diverge/merge pairs
    # each consume one radius, and the closing straight is loop_width - 2*radius)
    struct().updatePos(newStart=struct().getPos((loop_width, 0)), angle=0)

#Positive CPW Functions


def CPW_straight_pos(chip, structure, length, w=None, s=None, gnd_width=None, bgcolor=None, **kwargs):
    """
    Positive CPW straight — draws metal directly instead of gaps.

    Parameters
    ----------
    length    : length of the CPW section
    w         : center strip width
    s         : gap width between center strip and ground plane
    gnd_width : how far the ground plane extends past the gap edge
    """
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
            return
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')
            return
    if gnd_width is None:
        try:
            gnd_width = struct().defaults['gnd_width']
        except KeyError:
            print('\x1b[33mgnd_width not defined in ', chip.chipID, '!\x1b[0m')
            return

    # Center strip
    chip.add(dxf.rectangle(struct().getPos((0, -w/2)), length,  w,
             rotation=struct().direction, bgcolor=bgcolor, **kwargStrip(kwargs)))

    # Left ground plane: starts at outer edge of left gap (w/2 + s), extends by gnd_width
    chip.add(dxf.rectangle(struct().getPos((0,  w/2 + s)), length,  gnd_width,
             rotation=struct().direction, bgcolor=bgcolor, **kwargStrip(kwargs)))

    # Right ground plane: starts at outer edge of right gap (w/2 + s), extends by gnd_width
    chip.add(dxf.rectangle(struct().getPos((0, -w/2 - s)), length, -gnd_width,
             rotation=struct().direction, bgcolor=bgcolor, **kwargStrip(kwargs)),
             structure=structure, length=length)



def CPW_stub_open_pos(chip, structure, length=0, r_out=None, r_ins=None, w=None, s=None,
                      gnd_width=None, flipped=False, bgcolor=None, **kwargs):
    """
    Positive CPW stub open — draws metal directly instead of gaps.
    Draws center strip + two ground planes with rounded ends.
    """
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')
    if length == 0:
        length = max(length, s)
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
    if gnd_width is None:
        try:
            gnd_width = struct().defaults['gnd_width']
        except KeyError:
            gnd_width = s  # default to gap width if not specified
    if bgcolor is None:
        bgcolor = chip.wafer.bg()

    dx = 0.
    if flipped:
        dx = length

    # Center strip
    chip.add(RoundRect(
        _originCompensatedInsert(chip, struct().getPos((dx, -w/2)), struct().direction), length, w,
        min(r_out, length),
        roundCorners=[0, 1, 1, 0], hflip=flipped,
        valign=const.BOTTOM, rotation=struct().direction,
        bgcolor=bgcolor, **kwargs))

    # Upper ground plane: starts at outer edge of upper gap (w/2 + s)
    chip.add(RoundRect(
        _originCompensatedInsert(chip, struct().getPos((dx, w/2 + s)), struct().direction), length, gnd_width,
        min(r_out, length),
        roundCorners=[0, 1, 1, 0], hflip=flipped,
        valign=const.BOTTOM, rotation=struct().direction,
        bgcolor=bgcolor, **kwargs))

    # Lower ground plane: starts at outer edge of lower gap (w/2 + s)
    chip.add(RoundRect(
        _originCompensatedInsert(chip, struct().getPos((dx, -w/2 - s)), struct().direction), length, -gnd_width,
        min(r_out, length),
        roundCorners=[0, 1, 1, 0], hflip=flipped,
        valign=const.TOP, rotation=struct().direction,
        bgcolor=bgcolor, **kwargs),
        structure=structure, length=length)

def CPW_taper_pos(chip, structure, length=None, w0=None, s0=None, w1=None, s1=None,
                  gnd_width=None, bgcolor=None, offset=(0, 0), **kwargs):
    """
    Positive CPW taper — draws metal directly instead of gaps.
    """
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w0 is None:
        try:
            w0 = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
    if s0 is None:
        try:
            s0 = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')
    if w1 is None:
        try:
            w1 = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
    if s1 is None:
        try:
            s1 = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')
    if gnd_width is None:
        try:
            gnd_width = struct().defaults['gnd_width']
        except KeyError:
            gnd_width = max(s0, s1)
    if length is None:
        length = math.sqrt(3) * abs(w0/2 + s0 - w1/2 - s1)

    # Center strip taper: starts at -w0/2, tapers to w1
    chip.add(SkewRect(
        _originCompensatedInsert(chip, struct().getPos((0, -w0/2)), struct().direction), length, w0,
        (offset[0], (w1 - w0)/2 + offset[1]), w1,
        rotation=struct().direction, valign=const.BOTTOM, edgeAlign=const.BOTTOM,
        bgcolor=bgcolor, **kwargs))

    # Upper ground plane taper: inner edge moves from w0/2+s0 to w1/2+s1
    chip.add(SkewRect(
        _originCompensatedInsert(chip, struct().getPos((0, w0/2 + s0)), struct().direction), length, gnd_width,
        (offset[0], (w1/2 + s1) - (w0/2 + s0) + offset[1]), gnd_width,
        rotation=struct().direction, valign=const.BOTTOM, edgeAlign=const.BOTTOM,
        bgcolor=bgcolor, **kwargs))

    # Lower ground plane taper: inner edge moves from -(w0/2+s0) to -(w1/2+s1)
    chip.add(SkewRect(
        _originCompensatedInsert(chip, struct().getPos((0, -w0/2 - s0)), struct().direction), length, -gnd_width,
        (offset[0], (w0/2 + s0) - (w1/2 + s1) + offset[1]), -gnd_width,
        rotation=struct().direction, valign=const.TOP, edgeAlign=const.TOP,
        bgcolor=bgcolor, **kwargs),
        structure=structure, offsetVector=(length + offset[0], offset[1]))

def CPW_launcher_pos(chip, structure, l_taper=None, l_pad=0, l_gap=0, padw=300, pads=160,
                     gnd_width=None, w=None, s=None, r_ins=0, r_out=0, bgcolor=None, **kwargs):
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if w is None:
        try:
            w = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ', chip.chipID, '!\x1b[0m')
            return
    if s is None:
        try:
            s = struct().defaults['s']
        except KeyError:
            print('\x1b[33ms not defined in ', chip.chipID, '!\x1b[0m')
            return
    if gnd_width is None:
        try:
            gnd_width = struct().defaults['gnd_width']
        except KeyError:
            gnd_width = pads  # default to pad gap width

    CPW_stub_open_pos(chip, structure, length=max(l_gap, pads), r_out=r_out, r_ins=r_ins,
                      w=padw, s=pads, gnd_width=gnd_width, flipped=True, bgcolor=bgcolor, **kwargs)
    CPW_straight_pos(chip, structure, max(l_pad, padw), w=padw, s=pads,
                     gnd_width=gnd_width, bgcolor=bgcolor, **kwargs)
    CPW_taper_pos(chip, structure, length=l_taper, w0=padw, s0=pads, w1=w, s1=s,
                  gnd_width=gnd_width, bgcolor=bgcolor, **kwargs)
    


def LC_Filter_ind1(self, s3):
    # INDUCTOR 1
    CPW_straight(self, s3, 200)
    st_len = 480
    b_rad = 4
    l_w = 5

    Strip_straight(
        self,
        s3,
        10,
        layer="inductor",
        linewidth=l_w,
    )
    Strip_bend(
        self,
        s3,
        angle=90,
        CCW=True,
        radius=b_rad,
        layer="inductor",
        linewidth=l_w,
    )
    Strip_straight(
        self,
        s3,
        240,
        layer="inductor",
        linewidth=l_w,
    )
    Strip_bend(self, s3, 180, False, radius=b_rad, layer="inductor", linewidth=l_w)

    for i in range(28):

        Strip_straight(
            self,
            s3,
            st_len,
            layer="inductor",
            linewidth=l_w,
        )
        Strip_bend(self, s3, 180, True, radius=b_rad, layer="inductor", linewidth=l_w)
        Strip_straight(
            self,
            s3,
            st_len,
            layer="inductor",
            linewidth=l_w,
        )

        Strip_bend(self, s3, 180, False, radius=b_rad, layer="inductor", linewidth=l_w)

    Strip_straight(
        self,
        s3,
        480,
        layer="inductor",
        linewidth=l_w,
    )
    Strip_bend(self, s3, 180, True, radius=b_rad, layer="inductor", linewidth=l_w)
    Strip_straight(
        self,
        s3,
        232,
        layer="inductor",
        linewidth=l_w,
    )

    Strip_bend(self, s3, 90, False, radius=b_rad, layer="inductor", linewidth=l_w)
    Strip_straight(
        self,
        s3,
        10,
        layer="inductor",
        linewidth=l_w,
    )
    # ========================INDUCTOR 2 ==============================


def LC_Filter_ind2(self, s3):
    st_len = 480
    b_rad = 4
    l_w = 5
    Strip_straight(
        self,
        s3,
        510,
        layer="inductor",
        linewidth=l_w,
    )

    Strip_bend(
        self,
        s3,
        angle=90,
        CCW=True,
        radius=b_rad,
        layer="inductor",
        linewidth=l_w,
    )
    Strip_straight(
        self,
        s3,
        240,
        layer="inductor",
        linewidth=l_w,
    )
    Strip_bend(self, s3, 180, False, radius=b_rad, layer="inductor", linewidth=l_w)

    for i in range(40):

        Strip_straight(
            self,
            s3,
            st_len,
            layer="inductor",
            linewidth=l_w,
        )
        Strip_bend(self, s3, 180, True, radius=b_rad, layer="inductor", linewidth=l_w)
        Strip_straight(
            self,
            s3,
            st_len,
            layer="inductor",
            linewidth=l_w,
        )

        Strip_bend(self, s3, 180, False, radius=b_rad, layer="inductor", linewidth=l_w)

    Strip_straight(
        self,
        s3,
        480,
        layer="inductor",
        linewidth=l_w,
    )
    Strip_bend(self, s3, 180, True, radius=b_rad, layer="inductor", linewidth=l_w)
    Strip_straight(
        self,
        s3,
        232,
        layer="inductor",
        linewidth=l_w,
    )

    Strip_bend(self, s3, 90, False, radius=b_rad, layer="inductor", linewidth=l_w)
    Strip_straight(
        self,
        s3,
        10,
        layer="inductor",
        linewidth=l_w,
    )

    # ================= RECTANGLE FOR INDUCTOR 1 ======================


def LC_Filter_ind_rects1(self, x1, y1):
    start2 = (x1, y1)

    steps2 = [
        (0, 250),  # up
        (-492, 0),  # left
        (0, -245),  # down
        (0, -260),
        (492, 0),
    ]

    # Convert steps into absolute points
    points2 = [start2]
    current2 = start2
    for dx2, dy2 in steps2:
        current2 = (current2[0] + dx2, current2[1] + dy2)
        points2.append(current2)

    # Create and close the polygon
    self.add(
        SolidPline(
            insert=(0, 0),
            points=points2,
            layer="BASEMETAL",
            bgcolor=self.bg("BASEMETAL"),
            solidFillQuads=True,  # required to support subtraction
        )
    )

    # ================= RECTANGLE FOR INDUCTOR 2 =======================


def LC_Filter_ind_rects2(self, x2, y2):
    start2 = (x2, y2)

    steps2 = [
        (0, 250),  # up
        (-684, 0),  # left
        (0, -245),  # down
        (0, -260),
        (684, 0),
    ]

    # Convert steps into absolute points
    points2 = [start2]
    current2 = start2
    for dx2, dy2 in steps2:
        current2 = (current2[0] + dx2, current2[1] + dy2)
        points2.append(current2)

    # Create and close the polygon
    self.add(
        SolidPline(
            insert=(0, 0),
            points=points2,
            layer="BASEMETAL",
            bgcolor=self.bg("BASEMETAL"),
            solidFillQuads=True,  # required to support subtraction
        )
    )


# ========================CAPACITOR 1 ==============================


def LC_Filter_cap1(self, x, y):
    cap1_pos = self.centered((x, y))
    c1 = m.Structure(
        self,
        cap1_pos,
        direction=180,
    )
    st_len = 235
    l_w = 5
    b_rad = 5

    # upper half of the capacitor
    Strip_straight(
        self,
        c1,
        20,
        w=5,
        layer="BASEMETAL",
    )
    Strip_bend(
        self,
        c1,
        angle=90,
        CCW=True,
        radius=b_rad,
        layer="BASEMETAL",
        w=l_w,
    )
    Strip_straight(
        self,
        c1,
        st_len,
        l_w,
        layer="BASEMETAL",
    )
    Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)

    for i in range(22):
        Strip_straight(
            self,
            c1,
            st_len,
            l_w,
            layer="BASEMETAL",
        )
        Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)
        Strip_straight(
            self,
            c1,
            st_len,
            l_w,
            layer="BASEMETAL",
        )
        Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)

    Strip_straight(
        self,
        c1,
        st_len,
        l_w,
        layer="BASEMETAL",
    )
    Strip_bend(self, c1, 90, True, radius=b_rad, layer="BASEMETAL", w=l_w)
    Strip_straight(
        self,
        c1,
        20,
        w=5,
        layer="BASEMETAL",
    )

    # lower half of the capacitor
    cap1_pos = self.centered((x, y - 10))

    c1 = m.Structure(
        self,
        cap1_pos,
        direction=180,
    )
    st_len = 235
    l_w = 5
    b_rad = 5
    Strip_straight(
        self,
        c1,
        20,
        w=5,
        layer="BASEMETAL",
    )
    Strip_bend(
        self,
        c1,
        angle=90,
        CCW=False,
        radius=b_rad,
        layer="BASEMETAL",
        w=l_w,
    )
    Strip_straight(
        self,
        c1,
        st_len,
        l_w,
        layer="BASEMETAL",
    )
    Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)

    for i in range(22):
        Strip_straight(
            self,
            c1,
            st_len,
            l_w,
            layer="BASEMETAL",
        )
        Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)
        Strip_straight(
            self,
            c1,
            st_len,
            l_w,
            layer="BASEMETAL",
        )
        Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)

    Strip_straight(
        self,
        c1,
        st_len,
        l_w,
        layer="BASEMETAL",
    )
    Strip_bend(self, c1, 90, False, radius=b_rad, layer="BASEMETAL", w=l_w)
    Strip_straight(
        self,
        c1,
        20,
        w=5,
        layer="BASEMETAL",
    )

    # # ========================CAPACITOR 2 ==============================


def LC_Filter_cap2(self, x, y):
    cap2_pos = self.centered((x, y))

    c1 = m.Structure(
        self,
        cap2_pos,
        direction=180,
    )
    st_len = 235
    l_w = 2
    b_rad = 6

    # upper half of the capacitor
    Strip_straight(
        self,
        c1,
        20,
        w=l_w,
        layer="BASEMETAL",
    )
    Strip_bend(
        self,
        c1,
        angle=90,
        CCW=True,
        radius=b_rad,
        layer="BASEMETAL",
        w=l_w,
    )
    Strip_straight(
        self,
        c1,
        st_len,
        l_w,
        layer="BASEMETAL",
    )
    Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)

    for i in range(45):
        Strip_straight(
            self,
            c1,
            st_len,
            l_w,
            layer="BASEMETAL",
        )
        Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)
        Strip_straight(
            self,
            c1,
            st_len,
            l_w,
            layer="BASEMETAL",
        )
        Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)

    Strip_straight(
        self,
        c1,
        st_len,
        l_w,
        layer="BASEMETAL",
    )
    Strip_bend(self, c1, 90, True, radius=b_rad, layer="BASEMETAL", w=l_w)

    # lower half of the capacitor
    cap2_pos = self.centered((x, y - 10))

    c1 = m.Structure(
        self,
        cap2_pos,
        direction=180,
    )
    st_len = 235
    l_w = 2
    b_rad = 6
    Strip_straight(
        self,
        c1,
        20,
        w=l_w,
        layer="BASEMETAL",
    )
    Strip_bend(
        self,
        c1,
        angle=90,
        CCW=False,
        radius=b_rad,
        layer="BASEMETAL",
        w=l_w,
    )
    Strip_straight(
        self,
        c1,
        st_len,
        l_w,
        layer="BASEMETAL",
    )
    Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)

    for i in range(45):
        Strip_straight(
            self,
            c1,
            st_len,
            l_w,
            layer="BASEMETAL",
        )
        Strip_bend(self, c1, 180, False, radius=b_rad, layer="BASEMETAL", w=l_w)
        Strip_straight(
            self,
            c1,
            st_len,
            l_w,
            layer="BASEMETAL",
        )
        Strip_bend(self, c1, 180, True, radius=b_rad, layer="BASEMETAL", w=l_w)

    Strip_straight(
        self,
        c1,
        st_len,
        l_w,
        layer="BASEMETAL",
    )
    Strip_bend(self, c1, 90, False, radius=b_rad, layer="BASEMETAL", w=l_w)

