#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 24 14:48:45 2020

@author: sasha
Edited by Agrim, 2026 (fixed dose-array indexing/broadcast bugs in add_dose_array)
"""
import numpy as np
import maskLib.MaskLib as m
from dxfwrite import DXFEngine as dxf
from dxfwrite import const
from dxfwrite.vector2d import midpoint, vadd, vsub, distance

#import maskLib.junctionLib as j
from maskLib.Entities import RoundRect, InsideCurve, CurveRect, SolidPline  
from maskLib.microwaveLib import CPW_stub_open, CPW_straight, Strip_straight, Strip_contact, Strip_bend, Strip_taper, CPW_launcher, CPW_taper, Strip_stub_open
from maskLib.junctionLib import DolanJunction, JContact_tab, ManhattanJunction, JcalcTabDims, JContact_slot, JContact_tab, JSingleProbePad, JProbePads, JSingleProbePadLeads, Transmon3DWithShunt, FlagPads
from maskLib.fluxoniumLib import smallJJ, JJ_chain, half_loop_leads, flux_transformer, half_loop_leads2, leads_for_tmon_dosearray_custom #no_loop_leads, 
from maskLib.utilities import kwargStrip, cornerRound



# NOTE: the deprecated module-level setupXORlayer() was removed in 2026 --
# use wafer.setupXORlayer() instead (the old version is preserved in
# qubitLib_old.py).

# ===============================================================================
# 3D transmon qubit functions (composite entities)
# ===============================================================================

qubit_defaults= {'sharp_jContactTab':{'r_out':0,'r_ins':0,'taboffs':3,'gapl':0,'tabl':0,'gapw':3,'tabw':2},
                 'sharp_junction':{'jpadr':0}}

def TransmonPad(chip,pos,padwidth=250,padheight=None,padradius=25,tab=False,tabShoulder = False,tabShoulderWidth=30,tabShoulderLength=80,tabShoulderRadius=None,flipped=False,rotation=0,bgcolor=None,**kwargs):
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



def Transmon3D(chip,pos,rotation=0,bgcolor=None,padh=200,padh2=200,padw=3000,padw2=3000,
               taperw=0,taperw2=0,leadw=85,leadw2=85,leadh=20,leadh2=20,separation=20,
               r_out=0.75,r_ins=0.75,taboffs=-0.05,steml=1.5,gapl=1.5,tabl=2,stemw=3,gapw=3,tabw=0.5,
               jpadTaper=10,jpadw=25,jpadh=16,jpadSeparation=28,jfingerl=4.5,jfingerex=1.5,jleadw=1,
               junctionClass=ManhattanJunction,**kwargs): 
    '''
    Generates transmon paddles with a manhattan junction at the center. 
    Junction and contact tab parameters are monkey patched to Junction function through kwargs.
    
    padh, padh2: left,right transmon pad height
    padw, padw2: left,right  transmon pad width (or length)
    taperw, taperw2: left,right taper length from pad to lead
    leadw, leadw2: left,right lead width
    leadh, leadh2: left,right lead height
    separation: separation between leads (where junction goes)
    junctionClass: if None, no junction is drawn. Otherwise, a junction of the specified class is drawn, e.g. ManhattanJunction, DolanJunction, etc.

    '''
    thisStructure = None
    if isinstance(pos,tuple):
        thisStructure = m.Structure(chip,start=pos,direction=rotation)
        
    def struct():
        if isinstance(pos,m.Structure):
            return pos
        elif isinstance(pos,tuple):
            return thisStructure
        else:
            return chip.structure(pos)
     
    if bgcolor is None: #color for junction, not undercut
        bgcolor = chip.wafer.bg()
    
    j_struct = struct().start
        
    #start where the junction is, move left to where left pad starts
    struct().shiftPos(-separation/2-leadw-padw)
    JSingleProbePad(chip,struct(),padwidth=padw,padheight=padh,tabShoulder=True,tabShoulderWidth=leadh,tabShoulderLength=leadw,flipped=False,padradius=None,
                      r_out=r_out,r_ins=r_ins,taboffs=taboffs,gapl=gapl,tabl=tabl,gapw=gapw,tabw=tabw,absoluteDimensions=True,**kwargs)
    struct().shiftPos(separation)
    JSingleProbePad(chip,struct(),padwidth=padw2,padheight=padh2,tabShoulder=True,tabShoulderWidth=leadh2,tabShoulderLength=leadw2,flipped=True,padradius=None,
                      r_out=r_out,r_ins=r_ins,taboffs=taboffs,gapl=gapl,tabl=tabl,gapw=gapw,tabw=tabw,absoluteDimensions=True,**kwargs)
                    #r_out=0,r_ins=0,taboffs=3,gapl=0,tabl=0,gapw=gapw,tabw=2,absoluteDimensions=True,**kwargs)
    
    #write the junction. The "None" option allows for creation of pads only, in case one wants to draw a SNAILmon, fluxonium-mon, etc.
    if junctionClass != None:
        junctionClass(chip, j_struct,rotation=struct().direction,jpadTaper=jpadTaper,jpadw=jpadw,jpadh=jpadh,separation=jpadSeparation+jpadTaper,jfingerl=jfingerl,jfingerex=jfingerex,leadw=jleadw,**kwargs)
    
def Transmon3D_leads(chip,pos,rotation=0,bgcolor=None,padh=200,padh2=200,padw=3000,padw2=3000,
               taperw=0,taperw2=0,leadw=85,leadw2=85,leadh=20,leadh2=20,separation=20,
               r_out=0.75,r_ins=0.75,taboffs=-0.05,steml=1.5,gapl=1.5,tabl=2,stemw=3,gapw=3,tabw=0.5,
               jpadTaper=10,jpadw=25,jpadh=16,jpadSeparation=28,jfingerl=4.5,jfingerex=1.5,jleadw=1,
               junctionClass=None,**kwargs):
    '''
    Generates just the leads of a 3D transmon, with the option of including a junction (which is off by default). 
    Junction and contact tab parameters are monkey patched to Junction function through kwargs.
    
    padh, padh2: left,right transmon pad height
    padw, padw2: left,right  transmon pad width (or length)
    taperw, taperw2: left,right taper length from pad to lead
    leadw, leadw2: left,right lead width
    leadh, leadh2: left,right lead height
    separation: separation between leads (where junction goes)

    '''
    thisStructure = None
    if isinstance(pos,tuple):
        thisStructure = m.Structure(chip,start=pos,direction=rotation)
        
    def struct():
        if isinstance(pos,m.Structure):
            return pos
        elif isinstance(pos,tuple):
            return thisStructure
        else:
            return chip.structure(pos)
     
    if bgcolor is None: #color for junction, not undercut
        bgcolor = chip.wafer.bg()
    
    j_struct = struct().start
        
    #start where the junction is, move left to where left pad starts
    struct().shiftPos(-separation/2-leadw-padw)
    JSingleProbePadLeads(chip,struct(),padwidth=padw,padheight=padh,tabShoulder=True,tabShoulderWidth=leadh,tabShoulderLength=leadw,flipped=False,padradius=None,
                      r_out=r_out,r_ins=r_ins,taboffs=taboffs,gapl=gapl,tabl=tabl,gapw=gapw,tabw=tabw,absoluteDimensions=True,**kwargs)
    struct().shiftPos(separation)
    JSingleProbePadLeads(chip,struct(),padwidth=padw2,padheight=padh2,tabShoulder=True,tabShoulderWidth=leadh2,tabShoulderLength=leadw2,flipped=True,padradius=None,
                      r_out=r_out,r_ins=r_ins,taboffs=taboffs,gapl=gapl,tabl=tabl,gapw=gapw,tabw=tabw,absoluteDimensions=True,**kwargs)
                    #r_out=0,r_ins=0,taboffs=3,gapl=0,tabl=0,gapw=gapw,tabw=2,absoluteDimensions=True,**kwargs)
    
    #write the junction.
    if junctionClass != None:
        junctionClass(chip, j_struct,rotation=struct().direction,jpadTaper=jpadTaper,jpadw=jpadw,jpadh=jpadh,separation=jpadSeparation+jpadTaper,jfingerl=jfingerl,jfingerex=jfingerex,leadw=jleadw,**kwargs)




# ===============================================================================
# Planar (2D) qubit functions (composite entities)
# ===============================================================================

def Hamburgermon(chip,pos,rotation=0,
                   qwidth=1120,qheight=795,qr_out=200, minQbunToGnd=100,
                   qbunwidth=960,qbunthick=0,qbunr=60,qbunseparation=69.3751,
                   qccap_padw=40,qccap_padl=170,qccap_padr_out=10,qccap_padr_ins=4.5,qccap_gap=30,
                   qccapl=210,qccapw=0,qccapr_ins=30,qccapr_out=15,
                   qccap_steml=70,qccap_stemw=None,
                   XLAYER=None,bgcolor=None,**kwargs):
    '''
    Generates a hamburger shaped qubit. Needs XOR layers to define base metal layer. 
    Junction and contact tab parameters are monkey patched to Junction function through kwargs.
    '''
    thisStructure = None
    if isinstance(pos,tuple):
        thisStructure = m.Structure(chip,start=pos,direction=rotation)
        
    def struct():
        if isinstance(pos,m.Structure):
            return pos
        elif isinstance(pos,tuple):
            return thisStructure
        else:
            return chip.structure(pos)
        
    if bgcolor is None: #color for junction, not undercut
        bgcolor = chip.wafer.bg()
    
    #get layers from wafer
    if XLAYER is None:
        try:
            XLAYER = chip.wafer.XLAYER
        except AttributeError:
            chip.wafer.setupXORlayer()
            XLAYER = chip.wafer.XLAYER
            
    if qccap_stemw is None:
        try:
            qccap_stemw = struct().defaults['w']
        except KeyError:
            print('\x1b[33mw not defined in ',chip.chipID,'!\x1b[0m')
            qccap_stemw = 6
    
    #increase thicknesses if radii are too large
    qccapw = max(qccapw,2*qccapr_out)
    qbunthick = max(qbunthick,2*qbunr)
    qccap_padw = max(qccap_padw,2*qccap_padr_out)
    qccap_padl = max(qccap_padl,2*qccap_padr_out)
    
    #increase qubit width and height if buns are too close to ground
    qwidth = max(qwidth,qbunwidth+2*minQbunToGnd)
    qheight = max(qheight,max(qccap_steml+qccap_padl,qccap_gap+qccapl)+2*max(2*qbunr,qbunthick)+qbunseparation+minQbunToGnd)
    
    #cache junction position and figure out if we're using structures or not
    jxpos = qccap_steml+qccap_padl+qccap_gap+qbunthick+qbunseparation/2
    if thisStructure is not None:
        #not using structures
        struct().shiftPos(-jxpos)
    centerPos = struct().getPos((jxpos,0))
    
    #hole in basemetal (negative)
    chip.add(RoundRect(struct().start,qheight,qwidth,qr_out,valign=const.MIDDLE,rotation=struct().direction,bgcolor=bgcolor,**kwargs))
    
    #xor defined qubit (positive)
    if qccap_padr_ins >0 and qccap_stemw+2*qccap_padr_ins < qccap_padw - 2*qccap_padr_out:
        chip.add(InsideCurve(struct().getPos((qccap_steml,qccap_stemw/2)),qccap_padr_ins,vflip=True,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs))
        chip.add(InsideCurve(struct().getPos((qccap_steml,-qccap_stemw/2)),qccap_padr_ins,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs))
        
    chip.add(dxf.rectangle(struct().start,qccap_steml,qccap_stemw,valign=const.MIDDLE,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargStrip(kwargs)))
    chip.add(RoundRect(struct().getPos((qccap_steml,0)),qccap_padl,qccap_padw,qccap_padr_out,valign=const.MIDDLE,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs))
    
    if qccapr_ins > 0:
        chip.add(InsideCurve(struct().getPos((jxpos-qbunseparation/2-qbunthick,qccap_padw/2+qccap_gap)),qccapr_ins,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs))
        chip.add(InsideCurve(struct().getPos((jxpos-qbunseparation/2-qbunthick,qccap_padw/2+qccap_gap+qccapw)),qccapr_ins,vflip=True,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs))
        
        chip.add(InsideCurve(struct().getPos((jxpos-qbunseparation/2-qbunthick,-qccap_padw/2-qccap_gap)),qccapr_ins,vflip=True,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs))
        chip.add(InsideCurve(struct().getPos((jxpos-qbunseparation/2-qbunthick,-qccap_padw/2-qccap_gap-qccapw)),qccapr_ins,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs))
        
    chip.add(RoundRect(struct().getPos((jxpos-qbunseparation/2-qbunthick,qccap_padw/2+qccap_gap)),qccapl,qccapw,qccapr_out,roundCorners=[1,0,0,1],halign=const.RIGHT,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs))
    chip.add(RoundRect(struct().getPos((jxpos-qbunseparation/2-qbunthick,-qccap_padw/2-qccap_gap)),qccapl,qccapw,qccapr_out,roundCorners=[1,0,0,1],halign=const.RIGHT,vflip=True,rotation=struct().direction,layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs))
    
    JProbePads(chip, centerPos,rotation=struct().direction,padwidth=qbunthick,padheight=qbunwidth,padradius=qbunr,separation=qbunseparation,
                 layer=XLAYER,bgcolor=chip.bg(XLAYER),**kwargs)
    
    ManhattanJunction(chip, centerPos, rotation=struct().direction,separation=qbunseparation, **kwargs)
    
    return centerPos,struct().direction
    
def Elephantmon(
    chip, structure, rotation=0, totalw=0, totall=0,
    tpad_width=200, tpad_height=300, tpad_gap_gnd=50,
    tpad_gap=100, rpad=10, **kwargs):

    """
    Generates an Elephantmon, which is similar to the Hamburgermon but does NOT use
    an XOR layer and uses a Dolan junction. Additional params can be passed to
    junctions used kwargs.
    If totalw, totall are specified to be non-zero, tpad_width and tpad_height are
        re-calculated based on tpad_gap and tpad_gap_gnd.
    """
    s = structure.clone()
    s.direction += rotation

    if totalw > 0:
        tpad_width = totalw-2*tpad_gap_gnd
    if totall > 0:
        tpad_height = (totall-2*tpad_gap_gnd-tpad_gap)/2
    

    s.shiftPos(tpad_width/2+tpad_gap_gnd)

    s_right = s.clone()
    s_right.direction += 90
    CPW_stub_open(chip, s_right, tpad_gap/2, r_ins=rpad, w=tpad_width, s=tpad_gap_gnd, flipped=True, **kwargs)
    JContact_tab(chip, s_right, **kwargs)

    s_right = s.cloneAlongLast()
    s_right.shiftPos(tpad_gap_gnd/2)
    s_right.direction += 90
    s_right.shiftPos(tpad_gap/2)
    Strip_straight(chip, s_right, length=tpad_height-rpad, w=tpad_gap_gnd, **kwargs)
    Strip_bend(chip, s_right, CCW=True, w=tpad_gap_gnd, radius=rpad+tpad_gap_gnd/2, **kwargs)
    Strip_straight(chip, s_right, length=tpad_width-2*rpad, w=tpad_gap_gnd, **kwargs)
    Strip_bend(chip, s_right, CCW=True, w=tpad_gap_gnd, radius=rpad+tpad_gap_gnd/2, **kwargs)
    Strip_straight(chip, s_right, length=tpad_height-rpad, w=tpad_gap_gnd, **kwargs)

    s_left = s.clone()
    s_left.direction -= 90
    CPW_stub_open(chip, s_left, tpad_gap/2, r_ins=rpad, w=tpad_width, s=tpad_gap_gnd, flipped=True, **kwargs)
    JContact_tab(chip, s_left, **kwargs)

    s_left = s.cloneAlongLast()
    s_left.shiftPos(tpad_gap_gnd/2)
    s_left.direction -= 90
    s_left.shiftPos(tpad_gap/2)
    Strip_straight(chip, s_left, length=tpad_height-rpad, w=tpad_gap_gnd, **kwargs)
    Strip_bend(chip, s_left, CCW=False, w=tpad_gap_gnd, radius=rpad+tpad_gap_gnd/2, **kwargs)
    Strip_straight(chip, s_left, length=tpad_width-2*rpad, w=tpad_gap_gnd, **kwargs)
    Strip_bend(chip, s_left, CCW=False, w=tpad_gap_gnd, radius=rpad+tpad_gap_gnd/2, **kwargs)
    Strip_straight(chip, s_left, length=tpad_height-rpad, w=tpad_gap_gnd, **kwargs)

    s.direction -= 90
    DolanJunction(chip, s, junctionl=tpad_gap, **kwargs)

def Xmon(
    chip, structure, rotation=0,
    xmonw=25, xmonl=150, xmon_gapw=20, xmon_gapl=30,
    r_out=None, r_ins=None, r_arm5=None,
    jj_loc=6, jj_reverse=False, junctionClass=ManhattanJunction,**kwargs):

    """
    Generates an Xmon (does NOT use an XOR layer) with a junction method specified by junctionClass.
    Additional params can be passed to junctions used kwargs.
    jj_loc in [0, 11] decides the location on the cross to place the junction:
        end of every arm and midway along every arm, counting clockwise
        from the start.
    xmonw, xmonl, xmon_gapw, and xmon_gapl can be either number or array. If array, uses those values
        for the corresponding arm (indexed clockwise 0 starting from the bottom arm)
    By default, draws the junction pointing toward ground. If jj_reverse, draws pointing toward
        pad at the specified location.
    """
    def struct():
        if isinstance(structure,m.Structure):
            return structure
        elif isinstance(structure,tuple):
            return m.Structure(chip,structure)
        else:
            return chip.structure(structure)
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
    
    if np.isscalar(xmonl): xmonl = [xmonl]*4
    if np.isscalar(xmonw): xmonw = [xmonw]*4
    if np.isscalar(xmon_gapl): xmon_gapl = [xmon_gapl]*4
    if np.isscalar(xmon_gapw): xmon_gapw = [xmon_gapw]*4

    for i in range(4):
        right = (i+1)%4
        left = (i-1)%4
        across = (i+2)%4
        min_length = max(xmonw[right]/2+xmon_gapw[right], xmonw[left]/2+xmon_gapw[left])
        if xmonl[i] < min_length:
            xmonl[i] = min_length
            xmon_gapw[i] = xmonw[across] + xmonw[across]/2
            xmonw[i] = 0
            xmon_gapl[i] = 0
    assert len(xmonl) == len(xmonw) == len(xmon_gapw) == len(xmon_gapl)

    add_arm = False
    if len(xmonl) == 5:
        add_arm = True
        # Add arm capability is very limited in cases where gap widths are not all equal

    s_start = struct().clone()
    s = struct().cloneAlong(distance=xmon_gapl[0]+xmonl[0], newDirection=rotation) # start in center of X
    s_jj_locs = [None]*12
    s_jj_ls = [0]*12

    center_to_start_arm_ud = max(xmonw[1]/2+xmon_gapw[1], xmonw[3]/2+xmon_gapw[3])
    center_to_start_arm_lr = max(xmonw[0]/2+xmon_gapw[0], xmonw[2]/2+xmon_gapw[2])

    cur = 2
    l = (cur-1)%4
    r = (cur+1)%4
    s_up = s.cloneAlong(newDirection=0)
    # fill left corner
    s_temp = s_up.cloneAlong(vector=(xmonw[l]/2, center_to_start_arm_lr/2+xmonw[cur]/4))
    Strip_straight(chip, s_temp, length=xmon_gapw[l], w=center_to_start_arm_lr-xmonw[cur]/2, **kwargs)
    s_temp = s_up.cloneAlong(vector=(xmonw[l]/2+xmon_gapw[l], (xmon_gapw[cur]+xmonw[cur])/2))
    Strip_straight(chip, s_temp, length=center_to_start_arm_ud-(xmonw[l]/2+xmon_gapw[l]), w=xmon_gapw[cur], **kwargs)
    # fill right corner
    center_to_start_arm = center_to_start_arm_lr
    if add_arm: center_to_start_arm += xmonw[4]/np.sqrt(2)
    s_temp = s_up.cloneAlong(vector=(xmonw[r]/2, -(center_to_start_arm/2+xmonw[cur]/4)))
    Strip_straight(chip, s_temp, length=xmon_gapw[r], w=center_to_start_arm-xmonw[cur]/2, **kwargs)
    s_temp = s_up.cloneAlong(vector=(xmonw[r]/2+xmon_gapw[r], -(xmon_gapw[cur]+xmonw[cur])/2))
    Strip_straight(chip, s_temp, length=center_to_start_arm_ud-(xmonw[r]/2+xmon_gapw[r]), w=xmon_gapw[cur], **kwargs)

    s_up.shiftPos(center_to_start_arm_ud)
    if xmonl[cur]-center_to_start_arm_ud > 0 and xmon_gapl[cur] > 0:
        CPW_straight(chip, s_up, length=xmonl[cur]-center_to_start_arm_ud, w=xmonw[cur], s=xmon_gapw[cur], **kwargs)
        CPW_stub_open(chip, s_up, length=xmon_gapl[cur], r_out=r_out, r_ins=r_ins, w=xmonw[cur], s=xmon_gapw[cur], **kwargs)
        s_jj_locs[6] = s_up.cloneAlongLast()
        s_jj_locs[5] = s_up.cloneAlongLast(vector=(-(xmonl[cur]-center_to_start_arm_ud)/2, xmonw[cur]/2), newDirection=90)
        s_jj_locs[7] = s_up.cloneAlongLast(vector=(-(xmonl[cur]-center_to_start_arm_ud)/2, -xmonw[cur]/2), newDirection=-90)
        s_jj_ls[6] = xmon_gapl[cur]
        s_jj_ls[5] = s_jj_ls[7] = xmon_gapw[cur]
    else:
        s_jj_locs[6] = s.cloneAlong(vector=(max(xmonw[l]/2, xmonw[r]/2), 0), newDirection=s_up.direction-s.direction)
        s_jj_ls[6] = max(xmon_gapw[l], xmon_gapw[r])

    cur = 0
    l = (cur-1)%4
    r = (cur+1)%4
    s_down = s.cloneAlong(newDirection=180)
    # fill left corner
    if not add_arm:
        s_temp = s_down.cloneAlong(vector=(xmonw[l]/2, center_to_start_arm_lr/2+xmonw[cur]/4))
        Strip_straight(chip, s_temp, length=xmon_gapw[l], w=center_to_start_arm_lr-xmonw[cur]/2, **kwargs)
        s_temp = s_down.cloneAlong(vector=(xmonw[l]/2+xmon_gapw[l], (xmon_gapw[cur]+xmonw[cur])/2))
        Strip_straight(chip, s_temp, length=center_to_start_arm_ud-(xmonw[l]/2+xmon_gapw[l]), w=xmon_gapw[cur], **kwargs)
    else: # add 5th arm
        assert xmon_gapw[l] == xmon_gapw[cur], 'Currently unsupported'
        s_temp = s_down.cloneAlong(vector=(xmonw[l]/2, xmonw[cur]/2), newDirection=45)
        s_temp.shiftPos(xmonw[4]/2 + xmon_gapw[cur]/np.sqrt(2))

        s_temp.shiftPos(xmon_gapw[cur]/np.sqrt(2) + xmon_gapw[4])
        s_temp_temp = s_temp.cloneAlong(newDirection=180)
        CPW_taper(chip, s_temp_temp, length=xmon_gapw[4], w0=xmonw[4], s0=xmon_gapw[4], w1=xmonw[4], s1=0, **kwargs)

        # inner rounded triangles
        if r_arm5 == None:
            r_arm5 = xmon_gapw[l]/4
        s_temp_l = s_temp_temp.cloneAlong(newDirection=-90)
        s_temp_l.shiftPos(xmonw[4]/2)
        s_temp_l.direction += 45
        s_temp_l = s_temp_l.cloneAlong(vector=(xmon_gapw[l]-r_arm5,0), newDirection=135)
        sub_tri_height = xmon_gapw[l]-r_arm5
        Strip_taper(chip, s_temp_l, length=(sub_tri_height)/np.sqrt(2), w0=0, w1=sub_tri_height*np.sqrt(2), **kwargs)
        s_temp_l = s_temp_l.cloneAlongLast(newDirection=-45)
        s_temp_l = s_temp_l.cloneAlongLast(vector=(0,-r_arm5/2))
        Strip_straight(chip, s_temp_l, sub_tri_height-r_arm5, w=r_arm5, **kwargs)
        s_temp_l = s_temp_l.cloneAlong(vector=(0,r_arm5/2), newDirection=-45)
        chip.add(CurveRect(s_temp_l.getPos(), height=r_arm5, radius=r_arm5, ralign=const.TOP,angle=90,rotation=0, **kwargs))

        s_temp_r = s_temp_temp.cloneAlong(newDirection=90)
        s_temp_r.shiftPos(xmonw[4]/2)
        s_temp_r.direction -= 45
        s_temp_r = s_temp_r.cloneAlong(vector=(xmon_gapw[cur]-r_arm5,0), newDirection=-135)
        sub_tri_height = xmon_gapw[cur]-r_arm5
        Strip_taper(chip, s_temp_r, length=(sub_tri_height)/np.sqrt(2), w0=0, w1=sub_tri_height*np.sqrt(2), **kwargs)
        s_temp_r = s_temp_r.cloneAlongLast(newDirection=45)
        s_temp_r = s_temp_r.cloneAlongLast(vector=(0,r_arm5/2))
        Strip_straight(chip, s_temp_r, sub_tri_height-r_arm5, w=r_arm5, **kwargs)
        s_temp_r = s_temp_r.cloneAlong(vector=(0,-r_arm5/2), newDirection=45)
        chip.add(CurveRect(s_temp_r.getPos(), height=r_arm5, radius=r_arm5, ralign=const.TOP, angle=90, rotation=0, **kwargs))

        # fill in outer triangles
        s_temp_r = s_temp.cloneAlong(vector=(0,-xmonw[4]/2-xmon_gapw[4]))
        chip.add(InsideCurve(s_temp_r.getPos(), height=r_arm5, radius=r_arm5, ralign=const.TOP, angle=45, rotation=0, **kwargs))
        s_temp_l = s_temp.cloneAlong(vector=(0,xmonw[4]/2+xmon_gapw[4]))
        chip.add(InsideCurve(s_temp_l.getPos(), height=r_arm5, radius=r_arm5, ralign=const.TOP, angle=45, rotation=45, **kwargs))

        # fill in actual arm of arm
        CPW_straight(chip, s_temp, length=xmonl[4]-distance(s_temp.getPos(), s.getPos()), w=xmonw[4], s=xmon_gapw[4], **kwargs)
        CPW_stub_open(chip, s_temp, length=xmon_gapl[4], r_out=r_out, r_ins=r_ins, w=xmonw[4], s=xmon_gapw[4], **kwargs)

        # fill in the leftover corners that would have been filled in here if there was no arm
        s_temp = s_down.cloneAlong(vector=(xmonw[l]/2+xmon_gapw[l]+xmonw[4]/np.sqrt(2), (xmon_gapw[cur]+xmonw[cur])/2))
        Strip_straight(chip, s_temp, length=center_to_start_arm_ud-(xmonw[l]/2+xmon_gapw[l]), w=xmon_gapw[cur], **kwargs)

    # fill right corner
    center_to_start_arm = center_to_start_arm_ud
    if add_arm: center_to_start_arm += xmonw[4]/np.sqrt(2)
    s_temp = s_down.cloneAlong(vector=(xmonw[r]/2, -(center_to_start_arm_lr/2+xmonw[cur]/4)))
    Strip_straight(chip, s_temp, length=xmon_gapw[r], w=center_to_start_arm_lr-xmonw[cur]/2, **kwargs)
    s_temp = s_down.cloneAlong(vector=(xmonw[r]/2+xmon_gapw[r], -(xmon_gapw[cur]+xmonw[cur])/2))
    Strip_straight(chip, s_temp, length=center_to_start_arm-(xmonw[r]/2+xmon_gapw[r]), w=xmon_gapw[cur], **kwargs)

    s_down.shiftPos(center_to_start_arm)
    if xmonl[cur]-center_to_start_arm > 0 and xmon_gapl[cur] > 0:
        CPW_straight(chip, s_down, length=xmonl[cur]-center_to_start_arm, w=xmonw[cur], s=xmon_gapw[cur], **kwargs)
        CPW_stub_open(chip, s_down, length=xmon_gapl[cur], r_out=r_out, r_ins=r_ins, w=xmonw[cur], s=xmon_gapw[cur], **kwargs)
        s_jj_locs[0] = s_down.cloneAlongLast()
        s_jj_locs[11] = s_down.cloneAlongLast(vector=(-(xmonl[cur]-center_to_start_arm)/2, xmonw[cur]/2), newDirection=90)
        s_jj_locs[1] = s_down.cloneAlongLast(vector=(-(xmonl[cur]-center_to_start_arm)/2, -xmonw[cur]/2), newDirection=-90)
        s_jj_ls[0] = xmon_gapl[cur]
        s_jj_ls[1] = s_jj_ls[11] = xmon_gapw[cur]
    else:
        s_jj_locs[0] = s.cloneAlong(vector=(-max(xmonw[l]/2, xmonw[r]/2), 0), newDirection=s_down.direction-s.direction)
        s_jj_ls[0] = max(xmon_gapw[l], xmon_gapw[r])

    cur = 1
    l = (cur-1)%4
    r = (cur+1)%4
    s_left = s.cloneAlong(newDirection=90)
    s_left.shiftPos(center_to_start_arm_lr)
    if xmonl[cur]-center_to_start_arm_lr > 0 and xmon_gapl[cur] > 0:
        CPW_straight(chip, s_left, length=xmonl[cur]-center_to_start_arm_lr, w=xmonw[cur], s=xmon_gapw[cur], **kwargs)
        CPW_stub_open(chip, s_left, length=xmon_gapl[cur], r_out=r_out, r_ins=r_ins, w=xmonw[cur], s=xmon_gapw[cur], **kwargs)
        s_jj_locs[3] = s_left.cloneAlongLast()
        s_jj_locs[2] = s_left.cloneAlongLast(vector=(-(xmonl[cur]-center_to_start_arm_lr)/2, xmonw[cur]/2), newDirection=90)
        s_jj_locs[4] = s_left.cloneAlongLast(vector=(-(xmonl[cur]-center_to_start_arm_lr)/2, -xmonw[cur]/2), newDirection=-90)
        s_jj_ls[3] = xmon_gapl[cur]
        s_jj_ls[2] = s_jj_ls[4] = xmon_gapw[cur]
    else:
        s_jj_locs[3] = s.cloneAlong(vector=(0, max(xmonw[l]/2, xmonw[r]/2)), newDirection=s_left.direction-s.direction)
        s_jj_ls[3] = max(xmon_gapw[l], xmon_gapw[r])

    cur = 3
    l = (cur-1)%4
    r = (cur+1)%4
    s_right = s.cloneAlong(newDirection=-90)
    center_to_start_arm = center_to_start_arm_lr
    if add_arm: center_to_start_arm += xmonw[4]/np.sqrt(2)
    s_right.shiftPos(center_to_start_arm)
    if xmonl[cur]-center_to_start_arm > 0 and xmon_gapl[cur] > 0:
        CPW_straight(chip, s_right, length=xmonl[cur]-center_to_start_arm, w=xmonw[cur], s=xmon_gapw[cur], **kwargs)
        CPW_stub_open(chip, s_right, length=xmon_gapl[cur], r_out=r_out, r_ins=r_ins, w=xmonw[cur], s=xmon_gapw[cur], **kwargs)
        s_jj_locs[9] = s_right.cloneAlongLast()
        s_jj_locs[8] = s_right.cloneAlongLast(vector=(-(xmonl[cur]-center_to_start_arm)/2, xmonw[cur]/2), newDirection=90)
        s_jj_locs[10] = s_right.cloneAlongLast(vector=(-(xmonl[cur]-center_to_start_arm)/2, -xmonw[cur]/2), newDirection=-90)
        s_jj_ls[9] = xmon_gapl[cur]
        s_jj_ls[8] = s_jj_ls[10] = xmon_gapw[cur]
    else:
        s_jj_locs[9] = s.cloneAlong(vector=(0, -max(xmonw[l]/2, xmonw[r]/2)), newDirection=s_right.direction-s.direction)
        s_jj_ls[8] = max(xmon_gapw[l], xmon_gapw[r])

    for i in range(len(s_jj_locs)): # Lincoln labs requires placing junctions on 5x5 nm grid
        s_jj = s_jj_locs[jj_loc]
        s_jj.updatePos(np.around(s_jj.getPos(), 2))

    s_jj = s_jj_locs[jj_loc]
    junctionl = s_jj_ls[jj_loc]
    JContact_tab(chip, s_jj.cloneAlong(newDirection=180), **kwargs)
    #keep junction method general
    junctionClass(chip,s_jj.cloneAlong(distance=junctionl/2), junctionl=junctionl, backward=jj_reverse, separation=junctionl,**kwargs)
    JContact_tab(chip, s_jj.cloneAlong(distance=junctionl), **kwargs)

    struct().updatePos(s_start.getPos()) # initial starting position
    return s # center of xmon


def Snailmon3D(chip, 
                startpoint = (1500, 2350), 
                pads=True, 
                snail=True, 
                FT=False, 
                dosearray=True, 
                alignstrip=True,
                # small_JJ=False,
                # big_JJ_chain=True,
                **kwargs):
    # Set default values for layers if not provided in kwargs
    layer = kwargs.get('layer', 'SNAILMON')
    LJlayer = kwargs.get('LJlayer', 'LJJLAYER')
    LUlayer = kwargs.get('LUlayer', 'LULAYER')
    SJJlayer = kwargs.get('SJJlayer', 'SJJLAYER')
    SUlayer = kwargs.get('SUlayer', 'SULAYER')
    gap = kwargs.get('gap', 0.48)
    bridgewidth = kwargs.get('bridgewidth', 1.78)
    bigfingerW = kwargs.get('bigfinger_width', 0.41)
    smallfingerW = kwargs.get('smallfingerwidth', 0.21)
    bridgeW = kwargs.get('bridge_width', 0.91)
    bridgeL = kwargs.get('bridgeL', 0.48)
    largebridgeL = kwargs.get('largebridgeL', 0.4)
    undercut = kwargs.get('undercut', 0.2)
    leads_contactpads_dose = kwargs.get('leads_contactpads_dose', 1)
    smallfinger_dose = kwargs.get('smallfinger_dose', 1)
    bigfinger_dose = kwargs.get('bigfinger_dose', 1)
    big_JJ_finger_dose = kwargs.get('big_JJ_finger_dose', 1)


    bridgedose = kwargs.get('bridgedose', 1)
    bridge_dose = kwargs.get('bridge_dose', 1)
    shift_dose = kwargs.get('shift_dose', 1)
    undercut_dose = kwargs.get('undercut_dose', 1)
    label_dose = kwargs.get('label_dose', 1)
    homeplates = kwargs.get('homeplates', True)
    n_junc = kwargs.get('n_junc', 3)
    # JJlength = kwargs.get('JJlength', 1.5)
    # JJwidth = kwargs.get('JJwidth', 1.08)
    padseparation = kwargs.get('padseparation', 200)

    big_JJ_chain = kwargs.get('big_JJ_chain', True)
    small_JJ = kwargs.get('small_JJ', True)

    big_JJ_finger_width = kwargs.get('big_JJ_finger_width', 0.41)
    big_JJ_finger_length = kwargs.get('big_JJ_finger_length', 2.2)

    # print("")
    
    #locals().update(kwargs)


    # Define the chip-mounting alignment strip
    if alignstrip:
        Strip_straight(chip, 
                    (34750, 3350), 
                    100, 
                    w=6700
                    )


    if pads:
        FlagPads(chip, 
                startpoint, 
                leadh=3250, 
                leadh2=1250,
                # flagw=750, 
                # flagh=750, 
                flipped=True, 
                separation=padseparation,
                shunt=True, 
                shunt_width=10, 
                shunt_dist=150, 
                shunt_length=400, 
                shunt_side='left',
                tab=True,
                tabShoulder=False,
                layer=layer
                )

    # Draw the SNAIL JJ's using updated fluxoniumLib
    if snail:
        if big_JJ_chain:
            print('drawing chain of big JJs')
            # print('bigfinger_width', big_JJ_finger_width)
            JJlength = float(big_JJ_finger_length)
            JJwidth = float(big_JJ_finger_width)
            yoffset=padseparation/2+n_junc/2*JJlength+largebridgeL
            JJ_chain(chip, m.Structure(chip, 
                #start=(startpoint[0]+50-17/2+1/2, startpoint[1]-100-5.3/2),direction=90), 
                start=(startpoint[0]+42, startpoint[1]-yoffset),direction=90), 
                n_junc_array=[n_junc],
                JJlength=JJlength,
                JJwidth=JJwidth, 
                w=1.5, 
                s=1.78, 
                bridgewidth=bridgewidth, 
                gap=0.4, 
                bgcolor=None, 
                CW=True, 
                finalpiece=False, 
                Jlayer='BIGJJFINGER_'+str(float(big_JJ_finger_dose)), 
                Ulayer='BIGJJUNDERCUT_'+str(float(undercut_dose)),
                bridgelayer='BIGJJBRIDGE_'+str(float(bridge_dose)),
                padseparation=padseparation
                )
        if small_JJ:
            print('drawing small JJ')
            # print('smallfinger_width', float(smallfingerW))
            smallJJ(chip, 
                m.Structure(chip, start=(startpoint[0]+58.5, startpoint[1]-100),direction=90), 
                Jlayer=SJJlayer,
                # Ulayer=SUlayer,
                Ulayer='SMALLJJUNDERCUT_'+str(float(undercut_dose)),
                gap=gap, 
                leadW = 1, 
                fingerL=1.5, 
                bigfingerW=float(bigfingerW), 
                smallfingerW=(float(smallfingerW)), 
                bridgeW=bridgeW, 
                bridgeL=bridgeL, 
                undercut=undercut,
                smallfingerlayer='SMALLJJSMALLFINGER_'+str(float(smallfinger_dose)), 
                bigfingerlayer='SMALLJJBIGFINGER_'+str(float(bigfinger_dose)), 
                Undercutlayer='SMALLJJUNDERCUT_'+str(float(undercut_dose)), 
                shiftlayer = 'SMALLJJSHIFT_'+str(float(shift_dose)), 
                bridgelayer='SMALLJJBRIDGE_'+str(float(bridge_dose)),
                )
        if small_JJ and big_JJ_chain:
            print('drawing full snail')

        # Draw the half loop leads
        # half_loop_leads(chip, 
        #             m.Structure(chip, start=startpoint,direction=0),
        #             start=(50,-100),
        #             leadL=103, 
        #             leadW=1, 
        #             loopW=15, 
        #             looplength_R=(17-3.48)/2, 
        #             looplength_L=17/2-5.3/2, 
        #             contactpads=homeplates, 
        #             contactL=11.5, 
        #             contactW=23, 
        #             shift=True, 
        #             layer='LOOP'
        #             )       
        # half_loop_leads(chip, 
        #             m.Structure(chip, start=startpoint, direction=0), 
        #             start=(50,-100), 
        #             yflip=True,
        #             leadL=103, 
        #             leadW=1, 
        #             loopW=15, 
        #             looplength_R=(17-3.48)/2, 
        #             looplength_L=17/2-5.3/2, 
        #             contactpads=homeplates, 
        #             contactL=11.5, 
        #             contactW=23, 
        #             layer='LOOP'
        #             )
         
        # draw half-loop leads adjusted for large JJs, per Prathu's code
        loopW = 15
        loopLength=17
        bridge_length=largebridgeL
        bigJJfinger_length=2.2
        smallJJ_finger_length=1.5
        smallJJ_bridge_length=bridgeL
        looplength_R = (loopLength - 2*smallJJ_finger_length - smallJJ_bridge_length)/2
        looplength_L = (loopLength - 3*bigJJfinger_length - 2*bridge_length)/2
        leadW = 1
        if small_JJ:
            loopleads_dose = smallfinger_dose
        elif big_JJ_chain:
            loopleads_dose = big_JJ_finger_dose
        elif (small_JJ and big_JJ_chain):
            loopleads_dose = smallfinger_dose
        half_loop_leads2(
                    chip, 
                    m.Structure(chip, start=(startpoint[0], startpoint[1]), direction=0), 
                    start=(50,-100), 
                    yflip=False,
                    # leadL=103, 
                    # leadW=1, 
                    # loopW=15, 
                    # looplength_R=(17-3.48)/2, 
                    # looplength_L=17/2-5.3/2, 
                    # contactpads=None, 
                    # contactL=11.5, 
                    # contactW=23, 
                    # layer='LOOP'
                    leadL=100, leadW=leadW, loopW=loopW, looplength_R=looplength_R, looplength_L=looplength_L,
                        contactpads=homeplates, contactW=20, contactL=10, wedgeL=10, shift=True, shiftW=0.5, 
                        layer='LOOP_'+str(loopleads_dose),
                        contact_to_probe_leads=True, contact_to_probe_leads_Length=130,homeplates=homeplates
                    )
        half_loop_leads2(
                    chip, 
                    m.Structure(chip, start=startpoint, direction=0), 
                    start=(50,-100), 
                    yflip=True,
                    # leadL=103, 
                    # leadW=1, 
                    # loopW=15, 
                    # looplength_R=(17-3.48)/2, 
                    # looplength_L=17/2-5.3/2, 
                    # contactpads=None, 
                    # contactL=11.5, 
                    # contactW=23, 
                    # layer='LOOP'
                    leadL=100, leadW=leadW, loopW=loopW, looplength_R=looplength_R, looplength_L=looplength_L,
                        contactpads=homeplates, contactW=20, contactL=10, wedgeL=10, shift=True, shiftW=0.5, 
                        layer='LOOP_'+str(loopleads_dose),
                        contact_to_probe_leads=True, contact_to_probe_leads_Length=130
                    )
        # # top one.
        # half_loop_leads2(chip, 
        #                 m.Structure(chip, start=startpoint, direction=0),
        #                 direction=0),
        #                 start=(0,0),
        #                 yflip=False,
        #                 leadL=100, leadW=leadW, loopW=loopW, looplength_R=looplength_R, looplength_L=5,
        #                 contactpads=True, contactW=20, contactL=10, wedgeL=10, shift=True, shiftW=0.5, layer='LOOP',
        #                 contact_to_probe_leads=True, contact_to_probe_leads_Length=130)
        # # bottom one.
        # half_loop_leads2(self,
        #                 m.Structure(self, start=(params['startpoint'][0]+i*arrayspacing_x+padw/2, params['startpoint'][1]+j*arrayspacing_y+100-separation/2),
        #                 direction=0),
        #                 start=(0,0),
        #                 yflip=True,
        #                 leadL=100, leadW=leadW, loopW=loopW, looplength_R=looplength_R, looplength_L=5,
        #                 contactpads=True, contactW=20, contactL=10, wedgeL=10, shift=True, shiftW=0.5, layer='LOOP',
        #                 contact_to_probe_leads=True, contact_to_probe_leads_Length=130)
        


    if FT:
    # draw the flux transformer
        flux_transformer(chip,
            startpoint=(1565,2200),
            large_rect_length=5000,
            large_rect_width=2250,
            small_rect_length=2500,
            small_rect_width=100,
            conductor_width=10,
            Y_offset=0,
            X_offset=0,
            outer_radius=20,
            inner_radius=10,
            layer='FT'
            )
    if dosearray:
    # draw the dose array--need to add the slot at least
        add_dose_array(chip,
                    startpoint=(35950,1450),
                    arraydims=(6,2), 
                    arrayspacing=1000, 
                    doses=None, 
                    basedose=1000,
                    printdose=False,
                    qubit='Transmon',
                    dummyFT=False,
                    #layer='DOSEARRAY'
                    )
        add_dose_array(chip,
                    startpoint=(35950,4000),
                    arraydims=(6,2),
                    arrayspacing=1000,
                    doses=None,
                    basedose=1000,
                    printdose=False,
                    qubit='SNAIL',
                    #layer='DOSEARRAY'
                    )

def SNAIL(chip,
          startpoint=(1500, 2350),
          pads=True,
          snail=True,
          FT=True,
          leadw=200, leadh=4000, leadh2=2000,
          flagw=1500, flagh=750, flagh2=None,
          flag_offset=700, flag_offset2=None,
          padseparation=200, padradius=25,
          FT_startpoint=None,
          FT_large_rect_length=5000, FT_large_rect_width=1000,
          FT_small_rect_length=500, FT_small_rect_width=30,
          FT_conductor_width=2, FT_X_offset=-450, FT_Y_offset=0,
          FT_outer_radius=20, FT_inner_radius=10, FT_rotation=0,
          n_junc=3, big_JJ_chain=True, small_JJ=True,
          **kwargs):
    '''
    Standalone SNAIL device: an asymmetric pad pair (via FlagPads) feeding a
    3-big-JJ + 1-small-JJ loop (via JJ_chain/smallJJ/half_loop_leads2, at
    Snailmon3D's existing realistic sub-micron fab scale), plus an optional
    nearby flux-transformer inductive coupler loop (flux_transformer).

    This is the same underlying composition as Snailmon3D (see that
    function), but with the pad and flux-transformer dimensions exposed as
    top-level parameters instead of hardcoded, so a specific real design
    (e.g. one already simulated in Ansys HFSS/Q3D) can be reproduced
    directly. The defaults here come from translating one such design:

    leadw/leadh/leadh2 : the two pads' narrow "wire" sections (width/length)
        - an asymmetric pair by design (leadh != leadh2).
    flagw/flagh/flagh2 : the big capacitor pad ("flag") at the far end of
        each wire. flagh2 defaults to flagh (symmetric).
    flag_offset/flag_offset2 : how far the big pad is shifted sideways from
        the wire's own centerline (perpendicular to the pad axis), passed
        through to FlagPads' flag_offset/flag_offset2 after converting from
        "shift from the wire's centerline" to FlagPads' own "shift from its
        flush-left default" convention: -(flagw-leadw)/2 + flag_offset.
        flag_offset2 defaults to flag_offset.
    padseparation : gap between the two wires' inner ends, where the actual
        junction chain and loop leads sit (independent of leadw/flagw).
    FT_* : flux_transformer dimensions (see that function). FT_startpoint
        defaults to startpoint plus the same relative offset Snailmon3D
        uses for its own (fixed-dimension) FT call - this is a reasonable
        starting position, not a verified one; re-check against the real
        coupling geometry (FT_dist/ftcouplerL in the source design) once
        rendered.
    n_junc/big_JJ_chain/small_JJ : junction-chain composition, passed
        through with JJ_chain/smallJJ's own existing defaults for the
        junction fab geometry itself (JJlength/JJwidth/bridgewidth/gap/...) -
        override via **kwargs the same way Snailmon3D does, if needed.
    '''
    if flagh2 is None:
        flagh2 = flagh
    if flag_offset2 is None:
        flag_offset2 = flag_offset
    if FT_startpoint is None:
        FT_startpoint = (startpoint[0] + 65, startpoint[1] - 150)

    layer = kwargs.get('layer', 'SNAILMON')
    bigfingerW = kwargs.get('bigfinger_width', 0.41)
    smallfingerW = kwargs.get('smallfingerwidth', 0.21)
    bridgewidth = kwargs.get('bridgewidth', 1.78)
    bridgeW = kwargs.get('bridge_width', 0.91)
    bridgeL = kwargs.get('bridgeL', 0.48)
    largebridgeL = kwargs.get('largebridgeL', 0.4)
    undercut = kwargs.get('undercut', 0.2)
    gap = kwargs.get('gap', 0.48)
    bridge_dose = kwargs.get('bridge_dose', 1)
    undercut_dose = kwargs.get('undercut_dose', 1)
    smallfinger_dose = kwargs.get('smallfinger_dose', 1)
    bigfinger_dose = kwargs.get('bigfinger_dose', 1)
    big_JJ_finger_dose = kwargs.get('big_JJ_finger_dose', 1)
    big_JJ_finger_width = kwargs.get('big_JJ_finger_width', 0.41)
    big_JJ_finger_length = kwargs.get('big_JJ_finger_length', 2.2)
    homeplates = kwargs.get('homeplates', True)

    # (flagw - leadw)/2 centers the flag on the wire by default; FlagPads'
    # own flag_offset is a shift from ITS flush-left default (see that
    # function), so subtracting that centering term converts our
    # "shift from the wire's centerline" convention into FlagPads' own.
    fp_flag_offset = flag_offset - (flagw - leadw) / 2
    fp_flag_offset2 = flag_offset2 - (flagw - leadw) / 2

    if pads:
        FlagPads(chip,
                 startpoint,
                 leadw=leadw, leadh=leadh, leadh2=leadh2,
                 flagw=flagw, flagh=flagh, flagh2=flagh2,
                 flag_offset=fp_flag_offset, flag_offset2=fp_flag_offset2,
                 flipped=True,
                 separation=padseparation,
                 padradius=padradius,
                 shunt=False,
                 tab=True,
                 tabShoulder=False,
                 layer=layer
                 )

    if snail:
        if big_JJ_chain:
            JJlength = float(big_JJ_finger_length)
            JJwidth = float(big_JJ_finger_width)
            yoffset = padseparation / 2 + n_junc / 2 * JJlength + largebridgeL
            JJ_chain(chip, m.Structure(chip,
                     start=(startpoint[0] + 42, startpoint[1] - yoffset), direction=90),
                     n_junc_array=[n_junc],
                     JJlength=JJlength,
                     JJwidth=JJwidth,
                     w=1.5,
                     s=1.78,
                     bridgewidth=bridgewidth,
                     gap=0.4,
                     bgcolor=None,
                     CW=True,
                     finalpiece=False,
                     Jlayer='BIGJJFINGER_' + str(float(big_JJ_finger_dose)),
                     Ulayer='BIGJJUNDERCUT_' + str(float(undercut_dose)),
                     bridgelayer='BIGJJBRIDGE_' + str(float(bridge_dose)),
                     padseparation=padseparation
                     )
        if small_JJ:
            smallJJ(chip,
                    m.Structure(chip, start=(startpoint[0] + 58.5, startpoint[1] - 100), direction=90),
                    Jlayer='SJJLAYER',
                    Ulayer='SMALLJJUNDERCUT_' + str(float(undercut_dose)),
                    gap=gap,
                    leadW=1,
                    fingerL=1.5,
                    bigfingerW=float(bigfingerW),
                    smallfingerW=float(smallfingerW),
                    bridgeW=bridgeW,
                    bridgeL=bridgeL,
                    undercut=undercut,
                    smallfingerlayer='SMALLJJSMALLFINGER_' + str(float(smallfinger_dose)),
                    bigfingerlayer='SMALLJJBIGFINGER_' + str(float(bigfinger_dose)),
                    Undercutlayer='SMALLJJUNDERCUT_' + str(float(undercut_dose)),
                    shiftlayer='SMALLJJSHIFT_' + str(float(kwargs.get('shift_dose', 1))),
                    bridgelayer='SMALLJJBRIDGE_' + str(float(bridge_dose)),
                    )

        loopW = 15
        loopLength = 17
        bridge_length = largebridgeL
        bigJJfinger_length = 2.2
        smallJJ_finger_length = 1.5
        smallJJ_bridge_length = bridgeL
        looplength_R = (loopLength - 2 * smallJJ_finger_length - smallJJ_bridge_length) / 2
        looplength_L = (loopLength - 3 * bigJJfinger_length - 2 * bridge_length) / 2
        leadW = 1
        loopleads_dose = smallfinger_dose if small_JJ else big_JJ_finger_dose
        half_loop_leads2(chip,
                          m.Structure(chip, start=startpoint, direction=0),
                          start=(50, -100),
                          yflip=False,
                          leadL=100, leadW=leadW, loopW=loopW, looplength_R=looplength_R, looplength_L=looplength_L,
                          contactpads=homeplates, contactW=20, contactL=10, wedgeL=10, shift=True, shiftW=0.5,
                          layer='LOOP_' + str(loopleads_dose),
                          contact_to_probe_leads=True, contact_to_probe_leads_Length=130, homeplates=homeplates
                          )
        half_loop_leads2(chip,
                          m.Structure(chip, start=startpoint, direction=0),
                          start=(50, -100),
                          yflip=True,
                          leadL=100, leadW=leadW, loopW=loopW, looplength_R=looplength_R, looplength_L=looplength_L,
                          contactpads=homeplates, contactW=20, contactL=10, wedgeL=10, shift=True, shiftW=0.5,
                          layer='LOOP_' + str(loopleads_dose),
                          contact_to_probe_leads=True, contact_to_probe_leads_Length=130
                          )

    if FT:
        flux_transformer(chip,
                          startpoint=FT_startpoint,
                          large_rect_length=FT_large_rect_length,
                          large_rect_width=FT_large_rect_width,
                          small_rect_length=FT_small_rect_length,
                          small_rect_width=FT_small_rect_width,
                          conductor_width=FT_conductor_width,
                          Y_offset=FT_Y_offset,
                          X_offset=FT_X_offset,
                          outer_radius=FT_outer_radius,
                          inner_radius=FT_inner_radius,
                          rotation=FT_rotation,
                          layer='FT'
                          )


def SQUIDCoupler(chip, structure, pad_width=800, pad_height=1400, pad_separation=200,
                  loop_width=30, junction_kwargs=None, bgcolor=None, **kwargs):
    '''
    PLACEHOLDER two-junction (symmetric DC SQUID) coupler, matching the general
    two-pad layout of arXiv:2503.13953 Fig. 10(b). There is no existing SQUID
    (two-junction-in-parallel) pattern elsewhere in this codebase to adapt, so
    this topology (two parallel junction arms forming a flux-threading loop
    between two pads) was authored fresh.

    Uses DolanJunction (shadow-evaporation style, built from plain Strip_pad/
    Strip_straight/Strip_taper calls) for each arm rather than ManhattanJunction:
    ManhattanJunction has an unrelated pre-existing origin_offset placement bug
    (it draws via eager SolidPline calls affected by Chip.add()'s centering
    shift, the same mechanism that broke Double_Y_balun's star and CPS_taper
    before those were fixed) that hasn't been patched yet.

    NOT CALIBRATED:
    - Junction dimensions default to DolanJunction's own library defaults,
      which have NOT been checked against this lab's actual dose/evaporation
      calibration for a target critical current - override via
      junction_kwargs (e.g. jfingerw, jgap, jpadw) once real numbers exist.
    - loop_width/pad_separation set the loop's geometric size, but the
      resulting inductance has not been simulated (the reference paper tunes
      this via ANSYS HFSS) - treat these as a starting layout to refine.

    Parameters
    ----------
    pad_width, pad_height : each of the two capacitor pads (rectangles)
    pad_separation         : gap between the inner edges of the two pads,
                              spanned by each DolanJunction arm
    loop_width             : vertical separation between the two parallel
                              junction arms (sets the loop's enclosed area)
    junction_kwargs        : extra kwargs forwarded to both DolanJunction
                              calls (e.g. jfingerw, jgap, jpadw) - both arms
                              always get identical values, for a symmetric SQUID
    '''
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if bgcolor is None:
        bgcolor = chip.wafer.bg()
    if junction_kwargs is None:
        junction_kwargs = {}

    direction = struct().direction
    half_gap = pad_separation / 2
    half_loop = loop_width / 2

    # Two big capacitor pads, straddling the gap where the SQUID loop/junctions sit
    chip.add(dxf.rectangle(struct().getPos((-half_gap - pad_width, -pad_height/2)), pad_width, pad_height,
                            rotation=direction, bgcolor=bgcolor, **kwargStrip(kwargs)))
    chip.add(dxf.rectangle(struct().getPos((half_gap, -pad_height/2)), pad_width, pad_height,
                            rotation=direction, bgcolor=bgcolor, **kwargStrip(kwargs)))

    # Two parallel Dolan-bridge junction arms, symmetric (equal Ic) - together
    # enclosing the flux-threading loop between the two pads
    for sign in (+1, -1):
        y = sign * half_loop
        j_structure = m.Structure(chip, struct().getPos((0, y)), direction=direction)
        DolanJunction(chip, j_structure, junctionl=pad_separation, bgcolor=bgcolor, **junction_kwargs)

def ESDShortingLines(chip, structure, pad_width=800, pad_height=1400, pad_separation=200,
                      line_width=10, line_length=1000, bar_width=None, bgcolor=None, **kwargs):
    '''
    ESD protection shorting lines matching arXiv:2503.13953 Fig. 10(c): thin
    traces connecting each of SQUIDCoupler's two pads down to a common
    grounding bar, shorting the SQUID pads together during fabrication and
    handling to protect the junctions from electrostatic discharge. This only
    draws the geometry - it doesn't implement any particular removal/dicing
    step for later disconnecting the short, which is process-specific.

    Call with the SAME structure/pad_width/pad_height/pad_separation used for
    the matching SQUIDCoupler call so the lines start at the correct pads.

    Parameters
    ----------
    line_length : distance from each pad down to the grounding bar
    line_width  : width of each shorting line trace
    bar_width   : width (length) of the grounding bar itself (defaults to
                  spanning both pads plus some margin)
    '''
    def struct():
        if isinstance(structure, m.Structure):
            return structure
        elif isinstance(structure, tuple):
            return m.Structure(chip, structure)
        else:
            return chip.structure(structure)

    if bgcolor is None:
        bgcolor = chip.wafer.bg()

    direction = struct().direction
    half_gap = pad_separation / 2
    pad_centers = [-half_gap - pad_width/2, half_gap + pad_width/2]

    if bar_width is None:
        bar_width = pad_separation + 2*pad_width + 200

    # Grounding bar, centered below the coupler
    chip.add(dxf.rectangle(struct().getPos((-bar_width/2, -pad_height/2 - line_length - line_width)),
                            bar_width, line_width, rotation=direction, bgcolor=bgcolor, **kwargStrip(kwargs)))

    # One thin line from each pad down to the bar
    for x in pad_centers:
        chip.add(dxf.rectangle(struct().getPos((x - line_width/2, -pad_height/2 - line_length)),
                                line_width, line_length, rotation=direction, bgcolor=bgcolor, **kwargStrip(kwargs)))

def Fluxonium3D(chip,
                startpoint = (1500, 2350), 
                addFlagPads=True, 
                addLoop=True, 
                FT=False, 
                dosearray=False, 
                alignstrip=True,
                small_JJ=True,
                straight_JJ_chain=True,
                **kwargs):
    # Set default values for layers if not provided in kwargs
    layer = kwargs.get('layer', 'SNAILMON')
    LJlayer = kwargs.get('LJlayer', 'LJJLAYER')
    LUlayer = kwargs.get('LUlayer', 'LULAYER')
    SJJlayer = kwargs.get('SJJlayer', 'SJJLAYER')
    SUlayer = kwargs.get('SUlayer', 'SULAYER')
    gap = kwargs.get('gap', 0.48)
    bridgewidth = kwargs.get('bridgewidth', 1.78)
    bigfingerW = kwargs.get('bigfinger_width', 0.41)
    smallfingerW = kwargs.get('smallfingerwidth', 0.21)
    bridgeW = kwargs.get('bridge_width', 0.91)
    bridgeL = kwargs.get('bridgeL', 0.48)
    largebridgeL = kwargs.get('largebridgeL', 0.4)
    undercut = kwargs.get('undercut', 0.2)
    leads_contactpads_dose = kwargs.get('leads_contactpads_dose', 1)
    smallfinger_dose = kwargs.get('smallfinger_dose', 1)
    bigfinger_dose = kwargs.get('bigfinger_dose', 1)
    bridgedose = kwargs.get('bridgedose', 1)
    bridge_dose = kwargs.get('bridge_dose', 1)
    shift_dose = kwargs.get('shift_dose', 1)
    undercut_dose = kwargs.get('undercut_dose', 1)
    label_dose = kwargs.get('label_dose', 1)
    homeplates = kwargs.get('homeplates', True)
    n_junc = kwargs.get('n_junc', 3)
    JJlength = kwargs.get('JJlength', 1.5)
    JJwidth = kwargs.get('JJwidth', 1.08)
    padseparation = kwargs.get('padseparation', 200)
    loopW = kwargs.get('loopW',15)
    loopLength = kwargs.get('loopLength', 17)
    bridge_length = kwargs.get('bridge_length', largebridgeL)
    finger_length = kwargs.get('finger_length', JJlength)
    smallJJ_finger_length = kwargs.get('smallJJ_finger_length', 1.5)
    smallJJ_bridge_length = kwargs.get('smallJJ_bridge_length', bridgeL)

    # Define the chip-mounting alignment strip
    if alignstrip:
        Strip_straight(chip, 
                    (34750, 3350), 
                    100, 
                    w=6700
                    )


    if addFlagPads:
        FlagPads(chip, 
                startpoint, 
                leadh=3250, 
                leadh2=1250,
                # flagw=750, 
                # flagh=750, 
                flipped=True, 
                separation=padseparation,
                shunt=True, 
                shunt_width=10, 
                shunt_dist=150, 
                shunt_length=400, 
                shunt_side='left',
                tab=True,
                tabShoulder=False,
                layer=layer
                )

    # Draw the SNAIL JJ's using updated fluxoniumLib
    if addLoop:
        if straight_JJ_chain:
        # print(JJlength,"snailmon3d")
            #loopLength = 17 - (n_junc*finger_length + (n_junc-1)*bridge_length)/2#34 - n_junc*finger_length - (n_junc-1)*bridge_length)/2
            yoffset=padseparation/2+n_junc/2*JJlength+(n_junc-1)*largebridgeL/2
            JJ_chain(chip, m.Structure(chip, 
                #start=(startpoint[0]+50-17/2+1/2, startpoint[1]-100-5.3/2),direction=90), 
                start=(startpoint[0]+42, startpoint[1]-yoffset),direction=90), 
                n_junc=n_junc,
                JJlength=JJlength,
                JJwidth=JJwidth, 
                w=1.5, 
                s=1.78, 
                bridgewidth=bridgewidth, 
                gap=0.4, 
                bgcolor=None, 
                CW=True, 
                finalpiece=False, 
                Jlayer='LARGEJJFINGER_'+str(bigfinger_dose), 
                Ulayer='UNDERCUT_'+str(undercut_dose),
                bridgelayer='BRIDGE_'+str(bridge_dose),
                padseparation=padseparation
                )
            print(n_junc, "JJ_chain")
        
        if small_JJ:
            smallJJ(chip, 
                m.Structure(chip, start=(startpoint[0]+58.5, startpoint[1]-100),direction=90), 
                Jlayer=SJJlayer,
                Ulayer=SUlayer,
                gap=gap, 
                leadW = 1, 
                fingerL=1.5, 
                bigfingerW=bigfingerW, 
                smallfingerW=smallfingerW, 
                bridgeW=bridgeW, 
                bridgeL=bridgeL, 
                undercut=undercut,
                smallfingerlayer='SMALLFINGER_'+str(smallfinger_dose), 
                bigfingerlayer='BIGFINGER_'+str(bigfinger_dose), 
                Undercutlayer='UNDERCUT_'+str(undercut_dose), 
                shiftlayer = 'SHIFT_'+str(shift_dose), 
                bridgelayer='BRIDGE_'+str(bridge_dose),
                )

        # Draw the half loop leads
        # half_loop_leads(chip, 
        #             m.Structure(chip, start=startpoint,direction=0),
        #             start=(50,-100),
        #             leadL=103, 
        #             leadW=1, 
        #             loopW=15, 
        #             looplength_R=(17-3.48)/2, 
        #             looplength_L=17/2-5.3/2, 
        #             contactpads=homeplates, 
        #             contactL=11.5, 
        #             contactW=23, 
        #             shift=True, 
        #             layer='LOOP'
        #             )       
        # half_loop_leads(chip, 
        #             m.Structure(chip, start=startpoint, direction=0), 
        #             start=(50,-100), 
        #             yflip=True,
        #             leadL=103, 
        #             leadW=1, 
        #             loopW=15, 
        #             looplength_R=(17-3.48)/2, 
        #             looplength_L=17/2-5.3/2, 
        #             contactpads=homeplates, 
        #             contactL=11.5, 
        #             contactW=23, 
        #             layer='LOOP'
        #             )
         
        # draw half-loop leads adjusted for large JJs, per Prathu's code

        looplength_R = (loopLength - 2*smallJJ_finger_length - smallJJ_bridge_length)/2
        looplength_L = (loopLength - n_junc*finger_length - (n_junc-1)*bridge_length)/2
        leadW = 1
        half_loop_leads2( #top half of the loop/leads
                    chip, 
                    m.Structure(chip, start=startpoint, direction=0), 
                    start=(50,-108.5+loopLength/2), 
                    yflip=False,
                    leadL=100, 
                    leadW=leadW, 
                    loopW=loopW, 
                    loopLength = loopLength,
                    looplength_R=looplength_R, 
                    looplength_L=looplength_L,
                    contactpads=homeplates, 
                    contactW=20, 
                    contactL=10, 
                    wedgeL=10, 
                    shift=True, 
                    shiftW=0.5, 
                    layer='LOOP',
                    contact_to_probe_leads=True, 
                    contact_to_probe_leads_Length=130,
                    homeplates=homeplates
                    )
        half_loop_leads2( #bottom half of the loop/leads
                    chip, 
                    m.Structure(chip, start=startpoint, direction=0), 
                    start=(50,-91.5-loopLength/2), 
                    yflip=True,
                    leadL=100, 
                    leadW=leadW, 
                    loopW=loopW, 
                    loopLength = loopLength,
                    looplength_R=looplength_R, 
                    looplength_L=looplength_L,
                    contactpads=homeplates, 
                    contactW=20, 
                    contactL=10, 
                    wedgeL=10, 
                    shift=True, 
                    shiftW=0.5, 
                    layer='LOOP',
                    contact_to_probe_leads=True, 
                    contact_to_probe_leads_Length=130,
                    homeplates=homeplates
                    )
        # top one.
        # half_loop_leads2(chip, 
        #                 m.Structure(chip, start=startpoint, direction=0),
        #                 direction=0),
        #                 start=(0,0),
        #                 yflip=False,
        #                 leadL=100, leadW=leadW, loopW=loopW, looplength_R=looplength_R, looplength_L=5,
        #                 contactpads=True, contactW=20, contactL=10, wedgeL=10, shift=True, shiftW=0.5, layer='LOOP',
        #                 contact_to_probe_leads=True, contact_to_probe_leads_Length=130)
        # # bottom one.
        # half_loop_leads2(self,
        #                 m.Structure(self, start=(params['startpoint'][0]+i*arrayspacing_x+padw/2, params['startpoint'][1]+j*arrayspacing_y+100-separation/2),
        #                 direction=0),
        #                 start=(0,0),
        #                 yflip=True,
        #                 leadL=100, leadW=leadW, loopW=loopW, looplength_R=looplength_R, looplength_L=5,
        #                 contactpads=True, contactW=20, contactL=10, wedgeL=10, shift=True, shiftW=0.5, layer='LOOP',
        #                 contact_to_probe_leads=True, contact_to_probe_leads_Length=130)
        


    if FT:
    # draw the flux transformer
        flux_transformer(chip,
            startpoint=(1565,2200),
            large_rect_length=5000,
            large_rect_width=2250,
            small_rect_length=2500,
            small_rect_width=100,
            conductor_width=10,
            Y_offset=0,
            X_offset=0,
            outer_radius=20,
            inner_radius=10,
            layer='FT'
            )
    if dosearray:
    # draw the dose array--need to add the slot at least
        add_dose_array(chip,
                    startpoint=(35950,1450),
                    arraydims=(6,2), 
                    arrayspacing=1000, 
                    doses=None, 
                    basedose=1000,
                    printdose=False,
                    qubit='Transmon',
                    dummyFT=False,
                    #layer='DOSEARRAY'
                    )
        add_dose_array(chip,
                    startpoint=(35950,4000),
                    arraydims=(6,2), 
                    arrayspacing=1000, 
                    doses=None, 
                    basedose=1000,
                    printdose=False,
                    qubit='SNAIL',
                    #layer='DOSEARRAY'
                    )





# dose arrays by Tom. Todo: make qubit modular? Fix slot in pads. General improvements.
def add_dose_array(chip, 
                   startpoint=(0,0), 
                   arraydims=(5,5), 
                   arrayspacing=500, 
                   doses=None, 
                   basedose=1000,
                   printdose=False,
                   dummyFT=True,
                   qubit=None, #can be 'Transmon' or 'SNAIL'
                   probepads=True,
                   transmon_number_label=True,
                   JJparams_label=True,
                   Doselabels=True,
                   homeplates=True,
                   **kwargs
                   ):
    '''
    Draw a dose-test array of junctions (one per grid point). qubit selects the
    style: 'Transmon' (bare smallJJ + leads), 'SNAIL', 'Fluxonium', or 'Shunt'.

    Array-valued kwargs and how they are indexed per field (i,j):
      indexed [i]    (1D, length arraydims[0]): smallfingerWs, bigfingerWs, bigJJfingerWs
      indexed [j]    (1D, length arraydims[1]): bridgedoses
      indexed [i][j] (2D, shape arraydims):     smallfingerdoses, bigfingerdoses, bigJJfingerdoses
    Scalars are broadcast automatically.

    NOTE: for transmon probe arrays consider the sweep system in
    'junction array.py' (field_params/JunctionWithLeads) instead -- it
    generates dose layers, field labels, and a parameter CSV automatically.
    '''
    # Add a dose array to the chip
    if doses is None:
        doses = np.ones(arraydims)*basedose
    for i in range(arraydims[0]):
        for j in range(arraydims[1]):
            # params for "FT" and transmon 3D pads
            params = {
                'startpoint': startpoint,
                'large_rect_length': 0,
                'large_rect_width': 0,
                'small_rect_length': 500,
                'small_rect_width': 100,
                'conductor_width': 10,
                'Y-offset': 0,  # smallrect offset from the +Y side of the largerect
                'X-offset': 0,  # offset of the +Y largerect line from the +X end of the small rectangle
                'outer_radius': 20,
                'inner_radius': 10
            }


            if dummyFT:
                
                FT_start = (params['startpoint'][0] + 75, params['startpoint'][1] - 0.5*params['small_rect_width'])
                # Generate dummy FT coordinates using params variables. The dummy FT is just a filleted rectangle.
                dummy_FT_pts_outer = [
                    FT_start,
                    (FT_start[0] + 500, FT_start[1]),
                    (FT_start[0] + 500, FT_start[1] - params['small_rect_width']),
                    (FT_start[0], FT_start[1] - params['small_rect_width']),
                    FT_start
                ]
                dummy_FT_quadrants_outer = [2,1,4,3]
                dummy_FT_clockwises_outer = [True, True, True, True]
                filleted_points_outer = []
                for point, quadrant, clockwise in zip(dummy_FT_pts_outer, dummy_FT_quadrants_outer, dummy_FT_clockwises_outer):
                    radius = params['inner_radius'] if not clockwise else params['outer_radius']
                    filleted_points_outer.extend(cornerRound(point, quadrant, radius, clockwise=clockwise))
                chip.add(SolidPline((i*arrayspacing,j*arrayspacing), points=filleted_points_outer, layer='ARRAYFT'))
                

                dummy_FT_pts_inner = [
                    (FT_start[0] + 10, FT_start[1] - 10),
                    (FT_start[0] + 490, FT_start[1] - 10),
                    (FT_start[0] + 490, FT_start[1] - params['small_rect_width'] + 10),
                    (FT_start[0] + 10, FT_start[1] - params['small_rect_width'] + 10),
                    (FT_start[0] + 10, FT_start[1] - 10)
                ]
                dummy_FT_quadrants_inner = dummy_FT_quadrants_outer
                dummy_FT_clockwises_inner = dummy_FT_clockwises_outer
                filleted_points_inner = []
                for point, quadrant, clockwise in zip(dummy_FT_pts_inner, dummy_FT_quadrants_inner, dummy_FT_clockwises_inner):
                    radius = params['outer_radius'] if not clockwise else params['inner_radius']
                    filleted_points_inner.extend(cornerRound(point, quadrant, radius, clockwise=clockwise))
                chip.add(SolidPline((i*arrayspacing,j*arrayspacing), points=filleted_points_inner, layer='ARRAYFT'))

            #still need to make this take arguments from the kwargs or at least somewhere up higher
            if qubit=='Transmon':
                w = 90-1.74 if 'w' not in kwargs else kwargs['w']
                # finger width varies along i; scalar is broadcast, default
                # matches smallJJ's own default (0.21 um)
                smallfingerWs = kwargs.get('smallfingerWs', 0.21)
                if np.isscalar(smallfingerWs):
                    smallfingerWs = np.full(arraydims[0], smallfingerWs)
                smallJJ(chip,
                        m.Structure(chip, start=(startpoint[0]+50.5+i*arrayspacing, startpoint[1]-100+j*arrayspacing),direction=90),
                        bridgelayer=f'BRIDGE_{j}', smallfingerwidth=smallfingerWs[i],
                        bridgeW=0.91, bridgeL=0.48
                        )
                Strip_contact(chip,
                              m.Structure(chip, start=(startpoint[0]+49.5+i*arrayspacing, startpoint[1]-98.26+j*arrayspacing)),
                              1,
                              w=w,
                              layer='LEADS'+str(i)+str(j),
                              contactW=23,
                              contactL=11.5)
                Strip_contact(chip,
                              m.Structure(chip, start=(startpoint[0]+49.5+i*arrayspacing, startpoint[1]-101.74+j*arrayspacing)),
                              1,
                              w=-w,
                              layer='LEADS'+str(i)+str(j),
                              contactW=23,
                              contactL=11.5) #maybe fix the pad shape, it's a bit weird
            
            if qubit=='SNAIL':
                starterpoint=(startpoint[0]+i*arrayspacing, startpoint[1]+j*arrayspacing)
                smallfingerWs=kwargs.get('smallfingerWs', 1)
                bridgedoses=kwargs.get('bridgedoses', 1000)

                n_junc = kwargs.get('n_junc', 3)

                small_finger_doses = kwargs.get('smallfingerdoses', np.ones(arraydims))
                big_finger_doses = kwargs.get('bigfingerdoses', np.ones(arraydims))


                big_JJ_finger_doses = kwargs.get('bigJJfingerdoses', np.ones(arraydims))

                big_JJ_finger_widths  = kwargs.get('bigJJfingerWs', 0.41)
                big_JJ_finger_length = kwargs.get('big_JJ_finger_length', 2.2)

                snailTF = kwargs.get('snailTF', True)
                big_JJ_chainTF = kwargs.get('big_JJ_chainTF', False)
                small_JJTF = kwargs.get('small_JJTF', True)

                # broadcast scalars to arrays shaped for how each is indexed
                # below: [i] -> length arraydims[0], [j] -> length arraydims[1],
                # [i][j] -> full 2D arraydims
                if np.isscalar(smallfingerWs):
                    smallfingerWs = np.full(arraydims[0], smallfingerWs)
                if np.isscalar(big_JJ_finger_widths):
                    big_JJ_finger_widths = np.full(arraydims[0], big_JJ_finger_widths)
                if np.isscalar(bridgedoses):
                    bridgedoses = np.full(arraydims[1], bridgedoses)
                if np.isscalar(small_finger_doses):
                    small_finger_doses = np.full(arraydims, small_finger_doses)
                if np.isscalar(big_finger_doses):
                    big_finger_doses = np.full(arraydims, big_finger_doses)
                if np.isscalar(big_JJ_finger_doses):
                    big_JJ_finger_doses = np.full(arraydims, big_JJ_finger_doses)

                # print(smallfingerWs, "smallfingerWs")
                # print(small_finger_doses, "small_finger_doses")
                # print(big_finger_doses, "big_finger_doses")
                # print(big_JJ_finger_doses, "big_JJ_finger_doses")
                # print(big_JJ_finger_widths, "big_JJ_finger_widths")
                # print(bridgedoses, "bridgedoses")

                # print(smallfingerWs)
                # print(big_JJ_finger_doses, "big_JJ_finger_doses")
                Snailmon3D(chip, 
                            startpoint=starterpoint, 
                            pads=False, 
                            snail=snailTF, 
                            small_JJ=small_JJTF,
                            big_JJ_chain=big_JJ_chainTF,
                            FT=False, 
                            dosearray=False, 
                            alignstrip=False,
                            homeplates=homeplates,

                            smallfinger_dose = small_finger_doses[i][j],
                            bigfinger_dose = big_finger_doses[i][j],
                            smallfingerwidth=smallfingerWs[i],
                            smallfingerW=smallfingerWs[i],
                            #bridge_width=bridgeWs[j],

                            bridge_dose=bridgedoses[j],

                            n_junc = n_junc,
                            big_JJ_finger_length = big_JJ_finger_length,
                            big_JJ_finger_width = big_JJ_finger_widths[i],
                            big_JJ_finger_dose = big_JJ_finger_doses[i][j],
                           ) 



            if qubit == 'Fluxonium':
                starterpoint = (startpoint[0] + i*arrayspacing,
                                startpoint[1] + j*arrayspacing)

                # --- dose arrays / parameters ---
                n_junc = kwargs.get('n_junc', 3)

                small_finger_doses = kwargs.get('smallfingerdoses', np.ones(arraydims))
                big_finger_doses   = kwargs.get('bigfingerdoses', np.ones(arraydims))

                smallfingerWs = kwargs.get('smallfingerWs', 1)
                bigfingerWs   = kwargs.get('bigfingerWs', 0.41)

                bridge_doses  = kwargs.get('bridgedoses', np.ones(arraydims))

                # scalar -> array safety; widths are indexed [i] below, so
                # they must be 1D of length arraydims[0] (not 2D)
                if np.isscalar(smallfingerWs):
                    smallfingerWs = np.full(arraydims[0], smallfingerWs)
                if np.isscalar(bigfingerWs):
                    bigfingerWs = np.full(arraydims[0], bigfingerWs)
                if np.isscalar(bridge_doses):
                    bridge_doses = np.full(arraydims, bridge_doses)

                # --- call Fluxonium generator ---
                Fluxonium3D(
                    chip,
                    startpoint=starterpoint,
                    addFlagPads=False,      # dose array → no large pads
                    addLoop=True,
                    FT=False,
                    dosearray=False,
                    alignstrip=False,

                    n_junc=n_junc,

                    smallfinger_dose=small_finger_doses[i][j],
                    bigfinger_dose=big_finger_doses[i][j],

                    smallfingerwidth=smallfingerWs[i],
                    bigfinger_width=bigfingerWs[i],

                    bridge_dose=bridge_doses[i][j],

                    homeplates=homeplates,
                )




            if qubit=='Shunt':
                no_loop_leads(chip, 
                              m.Structure(chip, start=(startpoint[0]+i*arrayspacing, startpoint[1]+j*arrayspacing)), 
                              start=(50,-100),           
                              leadL=100, 
                              leadW=1, 
                              contactpads=True, 
                              contactL=11.5, 
                              contactW=23, 
                              layer='LEAD', 
                              startshifty=1.5
                              )







            # Draw transmon 3D pads with shunt
            if probepads:
                probe_pad_start = (params['startpoint'][0]+i*arrayspacing+3500, params['startpoint'][1]+j*arrayspacing+3500)
                # print("probe pads startpoint: ", probe_pad_start)
                Transmon3DWithShunt(chip, 
                                    # (params['startpoint'][0]+i*arrayspacing, params['startpoint'][1]+j*arrayspacing) , 
                                    probe_pad_start,
                                    padw=100, padh=100, leadw=100, leadh=2000, 
                                    separation=200, tab=False, shunt=True, shunt_width=10, shunt_dist=150, shunt_length=300, shunt_side='left', flipped=True)

            # labels
            arrayspacing_x = arrayspacing
            arrayspacing_y = arrayspacing
            padw = 200#1500
            padh = 200# 750

            fontsize=20
            xpos = params['startpoint'][0]+i*arrayspacing_x+padw
            ypos = params['startpoint'][1]+j*arrayspacing_y+padh

            
            #extract the JJ parameters from kwargs
            finger_length = kwargs.get('finger_length', 1.5)
            finger_width = kwargs.get('finger_width', 1)
            bigfinger_length = kwargs.get('bigfinger_length', 1.5)
            bigfinger_width = kwargs.get('bigfinger_width', 0.41)
            bridge_length = kwargs.get('bridge_length', 0.48)
            bridge_width = kwargs.get('bridge_width', 0.91)

            #extract the dose parameters from kwargs
            leads_contactpads_dose = kwargs.get('leads_contactpads_dose', 1)
            bridge_dose = kwargs.get('bridge_dose', 'Bridge dose ' + str(i) + ',' + str(j))
            bigfinger_dose = kwargs.get('bigfinger_dose', 1)
            smallfinger_dose = kwargs.get('smallfinger_dose', 1)
            undercut_dose = kwargs.get('undercut_dose', 1)
            shift_dose = kwargs.get('shift_dose', 1)
            label_dose = kwargs.get('label_dose', 1)

            separation = 25



            if transmon_number_label == True:
                chip.add_chip_label('JJ ('+str(i)+','+str(j)+')', layer='LABEL', 
                                    position=(xpos, params['startpoint'][1]+j*arrayspacing_y+padh-150), height=fontsize
                                    )            
            if JJparams_label == True:
                ypos = ypos-fontsize-15
                label_list =               [finger_length,  finger_width,   bigfinger_length, bigfinger_width, bridge_length , bridge_width]
                for ii,label in enumerate(['SmallFingerL', 'SmallFingerW', 'BigfingerL',     'BigFingerW',    'BridgeL',      'BridgeW' ]):
                    chip.add_chip_label(label+ ' = ' + str(round(label_list[ii], 3)), 
                                    layer='LABEL', 
                                    position=(xpos, ypos), height=fontsize
                                    )
                    ypos-=fontsize+10
            if Doselabels == True:
                ypos = params['startpoint'][1]+j*arrayspacing_y-separation
                label_list = [leads_contactpads_dose, bridge_dose, bigfinger_dose, smallfinger_dose, undercut_dose, shift_dose, label_dose]
                for ii, label in enumerate(['leads_contactpads_dose', 'bridge_dose', 'bigfinger_dose', 'smallfinger_dose', 'undercut_dose', 
                                            'shift_dose', 'label_dose']):
                    if label == 'leads_contactpads_dose':
                        xpos+=70
                    # (was `type(x) == (float or int)`, which only ever
                    # checked float -- `(float or int)` evaluates to float)
                    if isinstance(label_list[ii], (int, float)):
                        chip.add_chip_label(label+ ' = ' + str(round(label_list[ii], 3)),
                                    layer='LABEL',
                                    position=(xpos, ypos), height=fontsize
                                    )
                    else:
                        chip.add_chip_label(label+ ' = ' + str(label_list[ii]),
                                    layer='LABEL',
                                    position=(xpos, ypos), height=fontsize
                                    )
                    ypos-=fontsize+10
                




def add_JJ_dose_array(chip,
                   startpoint=(0,0),
                   arraydims=(5,5),
                   arrayspacing=500,
                   doses=None,
                   basedose=1000,
                   printdose=False,
                   optlayer='OPTICAL',
                   JJlayer='JJ',
                   FT=False):
    '''
    LEGACY: draws a grid of shunted transmon pads (plus optional dummy FT
    rectangles) with no junctions. Nothing in this repo calls it -- for real
    dose arrays see add_dose_array or the sweep system in 'junction array.py'.
    '''
    # Add a dose array to the chip
    if doses is None:
        doses = np.ones(arraydims)*basedose
    for i in range(arraydims[0]):
        for j in range(arraydims[1]):                
            params = {
                'startpoint': startpoint,
                'large_rect_length': 0,
                'large_rect_width': 0,
                'small_rect_length': 500,
                'small_rect_width': 100,
                'conductor_width': 10,
                'Y-offset': 0,  # smallrect offset from the +Y side of the largerect
                'X-offset': 0,  # offset of the +Y largerect line from the +X end of the small rectangle
                'outer_radius': 20,
                'inner_radius': 10
            }
            if FT: # params for "FT" and transmon 3D pads
                FT_start = (params['startpoint'][0] + 75, params['startpoint'][1] - 0.5*params['small_rect_width'])
                # Generate dummy FT coordinates using params variables. The dummy FT is just a filleted rectangle.
                dummy_FT_pts_outer = [
                    FT_start,
                    (FT_start[0] + 500, FT_start[1]),
                    (FT_start[0] + 500, FT_start[1] - params['small_rect_width']),
                    (FT_start[0], FT_start[1] - params['small_rect_width']),
                    FT_start
                ]
                dummy_FT_quadrants_outer = [2,1,4,3]
                dummy_FT_clockwises_outer = [True, True, True, True]
                filleted_points_outer = []
                for point, quadrant, clockwise in zip(dummy_FT_pts_outer, dummy_FT_quadrants_outer, dummy_FT_clockwises_outer):
                    radius = params['inner_radius'] if not clockwise else params['outer_radius']
                    filleted_points_outer.extend(cornerRound(point, quadrant, radius, clockwise=clockwise))
                chip.add(SolidPline((i*arrayspacing,j*arrayspacing), points=filleted_points_outer, layer=optlayer))
                

                dummy_FT_pts_inner = [
                    (FT_start[0] + 10, FT_start[1] - 10),
                    (FT_start[0] + 490, FT_start[1] - 10),
                    (FT_start[0] + 490, FT_start[1] - params['small_rect_width'] + 10),
                    (FT_start[0] + 10, FT_start[1] - params['small_rect_width'] + 10),
                    (FT_start[0] + 10, FT_start[1] - 10)
                ]
                dummy_FT_quadrants_inner = dummy_FT_quadrants_outer
                dummy_FT_clockwises_inner = dummy_FT_clockwises_outer
                filleted_points_inner = []
                for point, quadrant, clockwise in zip(dummy_FT_pts_inner, dummy_FT_quadrants_inner, dummy_FT_clockwises_inner):
                    radius = params['outer_radius'] if not clockwise else params['inner_radius']
                    filleted_points_inner.extend(cornerRound(point, quadrant, radius, clockwise=clockwise))
                chip.add(SolidPline((i*arrayspacing,j*arrayspacing), points=filleted_points_inner, layer=optlayer))

            # Draw a transmon 3D with shunt
            Transmon3DWithShunt(chip, (params['startpoint'][0]+i*arrayspacing, params['startpoint'][1]+j*arrayspacing) , padw=100, padh=300, leadw=100, leadh=2000, separation=200, shunt=True, shunt_width=10, shunt_dist=150, shunt_length=400, shunt_side='left', flipped=True,layer='DOSEARRAY')
