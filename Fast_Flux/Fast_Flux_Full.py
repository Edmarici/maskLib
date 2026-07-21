import numpy as np

from dxfwrite import DXFEngine as dxf
from dxfwrite import const

import maskLib.MaskLib as m
from maskLib.microwaveLib import CPS_straight, CPS_bend,CPS_structure, CPS_taper, CPS_capPad, CPS_hairpin_filter, CPS_loop,CPW_launcher_pos, CPW_straight_pos, CPW_stub_open, CPW_stub_open_pos,CPW_taper_pos, CPS_loop,CPW_launcher
from maskLib.junctionLib import setupJunctionLayers

from maskLib.qubitLib import qubit_defaults, Hamburgermon, SQUIDCoupler, ESDShortingLines


from maskLib.markerLib import MarkerSquare, MarkerCross
from maskLib.utilities import doMirrored, kwargStrip
from maskLib.Entities import SolidPline, Star, SkewRect
import math as math

# ===============================================================================
# wafer setup
# ===============================================================================

w = m.Wafer('Fast_Flux_Full','DXF/',43000,6000,padding=2500,waferDiameter=m.waferDiameters['2in'],sawWidth=200,#sawWidth=m.sawWidths['8A'],
                frame=1,solid=1,multiLayer=1,singleChipColumn=True)
#set wafer properties
# w.frame: draw frame layer?
# w.solid: draw things solid?
# w.multiLayer: draw in multiple layers?
# w.singleChipColumn: only make one column of chips?
w.setupXORlayer()
w.SetupLayers([
    ['BASEMETAL', 4],
    ['DICEBORDER', 5],
    ['MARKERS', 3]
])

#setup junction layers
setupJunctionLayers(w)

#initialize the wafer (remember to finalize any wafer properties like layers before initializing!)
w.init()


#do dicing border (by default located on layer 'MARKERS', so let's put it on layer 'DICEBORDER' instead)
w.DicingBorder(layer='DICEBORDER')

#do optical markers
#(note: mirrorX and mirrorY are true by default, but I've exposed them here to demonstrate how they work)
doMirrored(MarkerCross, w, (16000,16000),(200,200), 5,layer='MARKERS',mirrorX=True,mirrorY=True)

#do ebeam markers 
markerpts = [(15000,15000),(14000,14000),(13000,13000),(12000,12000)]
for pt in markerpts:
    #(note: mirrorX and mirrorY are true by default)
    doMirrored(MarkerSquare, w, pt, 80,layer='MARKERS')



def Double_Y_balun(chip, structure, arm_length=500, arm_width=100,
                   w_cps=6, w_cpw=6, s_cps=10, s_cpw=10,
                    rotation=0, bgcolor=None, **kwargs):
    """
    Double-Y balun junction connecting 3 CPS arms and 3 CPW arms.
    Metal drawn on BASEMETAL layer, gaps drawn on XOR layer.
    Both CPW and CPS gaps are straight rectangles.
    CPW gaps extend from center conductor edge to arm tip.
    CPS gaps extend from CPW gap intersection point to arm tip.
    In KLayout, compute BASEMETAL - XOR to get final metal layer.

    Parameters
    ----------
    arm_length  : length of each arm from center
    arm_width   : width of each arm metal rectangle
    w_cps       : CPS gap width
    w_cpw       : CPW gap width (each of the two gaps)
    s_cps       : CPS strip width
    s_cpw       : CPW center strip width
    rotation    : rotation of the whole structure in degrees
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

    center = struct().start
    base_direction = struct().direction + rotation

    # -------------------------------------------------------------------------
    # Step 1: Draw star metal polygon on BASEMETAL
    # -------------------------------------------------------------------------
    def star_vertices(arm_length, arm_width, num_arms=6, rotation=0):
        half_w = arm_width / 2
        angle_step = 2 * math.pi / num_arms

        tips_left = []
        tips_right = []
        notches = []

        for i in range(num_arms+1):
            angle_this = math.radians(rotation) + i * angle_step
            angle_next = angle_this + angle_step
            angle_perp_this = angle_this + math.pi / 2
            angle_perp_next = angle_next + math.pi / 2

            tip = (arm_length * math.cos(angle_this),
                   arm_length * math.sin(angle_this))

            v1 = (tip[0] + half_w * math.cos(angle_perp_this),
                  tip[1] + half_w * math.sin(angle_perp_this))
            v2 = (tip[0] - half_w * math.cos(angle_perp_this),
                  tip[1] - half_w * math.sin(angle_perp_this))

            tips_left.append(v1)
            tips_right.append(v2)

            v2_base = (-half_w * math.cos(angle_perp_this),
                       -half_w * math.sin(angle_perp_this))
            v1_base_next = (half_w * math.cos(angle_perp_next),
                            half_w * math.sin(angle_perp_next))

            d1 = (math.cos(angle_this), math.sin(angle_this))
            d2 = (math.cos(angle_next), math.sin(angle_next))

            dx = v1_base_next[0] - v2_base[0]
            dy = v1_base_next[1] - v2_base[1]

            denom = d1[0]*d2[1] - d1[1]*d2[0]
            if abs(denom) > 1e-10:
                t = (dx*d2[1] - dy*d2[0]) / denom
                notch = (v2_base[0] + t*d1[0],
                         v2_base[1] + t*d1[1])
            else:
                notch = (0, 0)

            notches.append(notch)

        vertices = [(0, 0)]
        for i in range(num_arms+1):
            vertices.append(tips_left[i])
            vertices.append(tips_right[i])
            vertices.append(notches[i])

        return vertices

    star_pts = star_vertices(arm_length, arm_width, rotation=base_direction)
    # SolidPline gets auto-shifted by chip.origin_offset in Chip.add() (it has a
    # .points attribute), unlike the plain dxf.rectangle() arms below which are
    # added as-is - pre-compensate so the star lands in the same space as the arms
    star_center = (center[0] - chip.origin_offset[0], center[1] - chip.origin_offset[1])
    chip.add(SolidPline(star_center, points=star_pts, bgcolor=bgcolor, **kwargStrip(kwargs)))

    # -------------------------------------------------------------------------
 # Step 2: Attach arms outside the star on BASEMETAL
    # -------------------------------------------------------------------------
# CPW 0° — normal CPW arm, connects to launcher
    angle_rad_0 = math.radians(base_direction + 0)
    cpw_connect_start = (center[0] + arm_length * math.cos(angle_rad_0),
                         center[1] + arm_length * math.sin(angle_rad_0))
    cpw_connect = m.Structure(chip, cpw_connect_start, direction=base_direction + 0)
    CPW_straight_pos(chip, cpw_connect, arm_length/4, w=s_cpw, s=w_cpw, gnd_width=(arm_width-s_cpw)/2-w_cpw)

    # CPW 120° — short termination: solid rectangle full arm width
    angle_rad_120 = math.radians(base_direction + 120)
    cpw_short_start = (center[0] + arm_length * math.cos(angle_rad_120),
                       center[1] + arm_length * math.sin(angle_rad_120))
    chip.add(dxf.rectangle(
        cpw_short_start, arm_width/2-arm_width/4, arm_width,
        valign=const.MIDDLE,
        rotation=base_direction + 120,
        bgcolor=bgcolor, **kwargStrip(kwargs)))

    # CPW 240° — open termination:
    # 1. Solid metal rectangle full arm width (ground plane border)
    # 2. XOR cutout removing center conductor
    # 3. Perpendicular end cap rectangle at tip
    angle_rad_240 = math.radians(base_direction + 240)
    cpw_open_start = (center[0] + arm_length * math.cos(angle_rad_240),
                      center[1] + arm_length * math.sin(angle_rad_240))

    # Ground plane border — full arm width solid rectangle
    chip.add(dxf.rectangle(
        cpw_open_start, arm_width/2, arm_width,
        valign=const.MIDDLE,
        rotation=base_direction + 240,
        bgcolor=bgcolor, **kwargStrip(kwargs)))

    # XOR cutout — removes center conductor from ground plane border
    chip.add(dxf.rectangle(
        cpw_open_start, arm_width/2-arm_width/4, (s_cpw +2*w_cpw),
        valign=const.MIDDLE,
        rotation=base_direction + 240,
        layer='XOR',
        bgcolor=bgcolor, **kwargStrip(kwargs)))


    # CPS 180° — normal CPS arm, connects to filter
    angle_rad_180 = math.radians(base_direction + 180)
    cps_connect_start = (center[0] + arm_length * math.cos(angle_rad_180),
                         center[1] + arm_length * math.sin(angle_rad_180))
    cps_connect = m.Structure(chip, cps_connect_start, direction=base_direction + 180)
    CPS_straight(chip, cps_connect, arm_length/4, w=w_cps, s=(arm_width-w_cps)/2)

    # CPS 300° — normal CPS arm, open termination (just ends)
    angle_rad_300 = math.radians(base_direction + 300)
    cps_open_start = (center[0] + arm_length * math.cos(angle_rad_300),
                      center[1] + arm_length * math.sin(angle_rad_300))
    chip.add(dxf.rectangle(
        cps_open_start, arm_length/4, arm_width,
        valign=const.MIDDLE,
        rotation=base_direction + 300,
        bgcolor=bgcolor, **kwargStrip(kwargs)))
    #cps_open = m.Structure(chip, cps_open_start, direction=base_direction + 300)
    #CPS_straight(chip, cps_open, arm_length/4, w=w_cps, s=(arm_width-w_cps)/2)

    # CPS 60° — solid rectangle, no gap (short termination)
    angle_rad_60 = math.radians(base_direction + 60)
    short_start = (center[0] + arm_length * math.cos(angle_rad_60),
                   center[1] + arm_length * math.sin(angle_rad_60))
    #cps_open = m.Structure(chip, short_start, direction=base_direction + 60)
    #CPS_straight(chip, cps_open, arm_length/4, w=w_cps, s=(arm_width-w_cps)/2)
    # -------------------------------------------------------------------------
    # Step 3: Draw gap shapes on XOR layer
    # -------------------------------------------------------------------------

    cps_stop_dist = (s_cpw/2 + w_cpw/2) / math.sin(math.radians(60))

    # CPW gaps at 0°, 120°, 240° — two straight rectangles per arm
    for angle in [0, 120, 240]:
        angle_rad = math.radians(base_direction + angle)
        perp_rad  = angle_rad + math.pi / 2

        for sign in [+1, -1]:
            offset = sign * (s_cpw/2 + w_cpw/2)
            gap_start = (center[0] + offset * math.cos(perp_rad),
                         center[1] + offset * math.sin(perp_rad))
            chip.add(dxf.rectangle(
                gap_start, arm_length, w_cpw,
                valign=const.MIDDLE,
                rotation=base_direction + angle,
                layer='XOR',
                bgcolor=bgcolor, **kwargStrip(kwargs)))

    # CPS gaps at 60°, 180°, 300° — straight rectangles stopping at CPW gap intersection
    for angle in [60, 180, 300]:
        angle_rad = math.radians(base_direction + angle)
        gap_start = (center[0] + cps_stop_dist * math.cos(angle_rad),
                     center[1] + cps_stop_dist * math.sin(angle_rad))
        gap_length = arm_length - cps_stop_dist
        chip.add(dxf.rectangle(
            gap_start, gap_length, w_cps,
            valign=const.MIDDLE,
            rotation=base_direction + angle,
            layer='XOR',
            bgcolor=bgcolor, **kwargStrip(kwargs)))

    # -------------------------------------------------------------------------
    # Step 4: Advance main structure to end of connecting CPS arm (180°)
    # -------------------------------------------------------------------------
    angle_rad_180 = math.radians(base_direction + 180)
    struct().updatePos(
        newStart=(center[0] +  (arm_length/4+arm_length) * math.cos(angle_rad_180),
                  center[1] + (arm_length/4 +arm_length) * math.sin(angle_rad_180)),
        angle=base_direction)
    
    
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
            gnd_width = pads

    # Step 1: Stub open — rounded pad end, flipped so rounded end faces outward
    CPW_stub_open_pos(chip, structure, length=max(l_gap, pads), r_out=r_out, r_ins=r_ins,
                      w=padw, s=pads, gnd_width=gnd_width, flipped=True,
                      bgcolor=bgcolor, **kwargs)

    # Step 2: Straight pad section
    CPW_straight_pos(chip, structure, max(l_pad, padw), w=padw, s=pads,
                     gnd_width=gnd_width, bgcolor=bgcolor, **kwargs)

    # Step 3: Taper from pad dimensions down to CPW line dimensions
    CPW_taper_pos(chip, structure, length=l_taper, w0=padw, s0=pads, w1=w, s1=s,
                  gnd_width=gnd_width, bgcolor=bgcolor, **kwargs)
# ===============================================================================
# chip class definition


# ===============================================================================
class Fast_Flux_Full(m.Chip):
    def __init__(self,wafer,chipID,layer,jfingerw,chip_id_loc=(0,0),defaults=None,**kwargs):
        m.Chip.__init__(self,wafer,chipID,layer,structures=[],defaults={'w':200,'r_out':10,'r_ins':0})
        #self.defaults = {'w':200,'r_out':10,'r_ins':0}
        if defaults is not None:
            for d in defaults:
                self.defaults[d]=defaults[d]
        
        for s in self.structures:
            s.shiftPos(340)
        
        '''
        #by default the corner structures are angled to match the pads
        self.structures[4].shiftPos(0,angle=-45)
        #make a reference to structure #4 so we don't confuse it for a variable
        s4 = self.structures[4]
        '''
        

    
        c4 = CPS_structure(self,self.chipSpace((40000,2900)),direction=180,w=6,strip=10,radius=100)

        cps_w, cps_s = 3, 5

        #define the transmon (transmon pads and manhattan junction)
        #these numbers copied from Kevin's files
        
        #define the alignment mark
        #Strip_straight(self,self.centered((-1300-1600+3808+790+943.75,0)),100,w=2000)
        # Taper from the CPS stripline width (10) up to 100 um, then the pad
        # connects directly to that 100 um taper end - the pad is meant to be
        # much wider than the taper, not smoothly width-matched to it.
        # w/s match the rest of this chip's CPS lines (CPS_structure's own
        # w=6,strip=10 defaults) - shared here as explicit, adjustable
        # parameters rather than relying on the structure's implicit defaults.
        pad_taper = {'taper_in': (50, cps_w, cps_s, cps_w, 100), 'taper_out': (50, cps_w, 100, cps_w, cps_s), 'w': cps_w, 's': cps_s}
        resonators = [
            {'pad_length': 4000, 'pad_width': 2200, **pad_taper},
            {'pad_length': 4000, 'pad_width': 2200, **pad_taper},
            {'pad_length': 4000, 'pad_width': 2200, **pad_taper},
            {'pad_length': 4000, 'pad_width': 2200, **pad_taper},
        ]
       
        
        #CPW_taper_pos(self, c4, length=300, w0=50, s0=10, w1=0, s1=150, gnd_width=100)
        #CPW_stub_open_pos(self, c4, length=150, w=0, s=150, gnd_width=100, flipped=True)
        
        
        Double_Y_balun(self,c4,arm_length=500, arm_width=300,
                   w_cps=cps_w, w_cpw=2, s_cps=100, s_cpw=8,
                    rotation=180,)
        #SlotToCPS_taper(self, c4, offset=20,slot_s1=10)
        CPS_taper(self,c4, length=300, w0=cps_w, s0=(300-6)/2, w1=cps_w, s1=cps_s)
        CPS_straight(self,c4, 2000, w=cps_w, s=cps_s)
        CPS_hairpin_filter(self, c4, resonators)

        # Thinner CPS line approaching the flux loop (was w=6,s=10 to match the
        # filter/pads; narrowed down for the final run into the loop).
        
        CPS_straight(self, c4, 3000, w=cps_w, s=cps_s)

        # Flux bias loop: the two CPS conductors themselves diverge and
        # reconverge to form the loop (CPS_loop), rather than a separate
        # solid-trace shape - this whole chain (launcher/balun/filter) IS the
        # flux-delivery line, terminating here close to (but not galvanically
        # connected to) the SQUID below.
        # loop_height+radius+w/2+s/2 must stay well under squid_pad_separation/2
        # (the SQUID's pad gap half-width) or the loop's diverging arms collide
        # with the SQUID's own pads.
        loop_width, loop_height, loop_radius = 100, 50, 15
        CPS_loop(self, c4, loop_width=loop_width, loop_height=loop_height,
                 w=cps_w, s=cps_s, radius=loop_radius)

        # SQUID coupler (Fig. 10(b,c)) - a separate, independent structure (its
        # capacitive pads couple to the 3D cavity, not to this flux line). Placed
        # just past where the CPS line re-merges after the loop, rotated 90
        # degrees left (CCW) so its pads extend clear of the loop's approach.
        squid_pad_width = 800
        squid_pad_separation = 200
        loop_clearance = 50  # gap left between the loop's far end and the SQUID loop
        squid_structure = m.Structure(self, c4.getPos((loop_clearance, 0)), direction=c4.direction + 90)
        SQUIDCoupler(self, squid_structure, pad_width=squid_pad_width, pad_separation=squid_pad_separation)
        ESDShortingLines(self, squid_structure, pad_width=squid_pad_width, pad_separation=squid_pad_separation)
        
        
        """Hamburgermon(
        self, c4, rotation=0)
        #or to just use primitives, you could use: 
        #self.add(dxf.rectangle(self.centered((-1300-1600+3808+790+943.75,0)),100,2000,valign=const.MIDDLE,bgcolor=wafer.bg()))
        #add chip name to frame layer
        self.add(dxf.text(str(self.chipID),chip_id_loc,height=200,layer='FRAME'))"""
        
        
# ===============================================================================
# generate chips
# ===============================================================================
junc_ws = np.array([175,178,180,180,182,185,190,200,205,215,225,235,105,95,145,155])/1000
        
        
#this will set the default chip for the wafer, filling the chip buffer with this chip
#Let's make this a transmon without rounded edges:

w.setDefaultChip(Fast_Flux_Full(w,'3DMM2_CHIP_DEFAULT',w.defaultLayer,jfingerw=float(junc_ws[0]),defaults={'r_out':0,'r_ins':0},jpadr=0,
                 **qubit_defaults['sharp_jContactTab']))
#this goes through the chip buffer and sets each entry to a new chip we define.
#Note: the CHIPID has to be unique for each chip 
for i in range(1,len(w.chips)):
    w.setChipBuffer(Fast_Flux_Full(w,'_CHIP'+str(i),w.defaultLayer,jfingerw=float(junc_ws[i])).save(w), i)
    #Note: You need to generate the chip, then call chip.save(wafer) to make sure the chip is written to the wafer block list!
    #alternative example:
    #temp_chip = MultimodeTransmon3D(w,'3DMM2_CHIP'+str(i),w.defaultLayer,jfingerw=junc_ws[i])
    #temp_chip.save(w)
    #wafer.chips[i]=temp_chip
    
#Let's also save a dxf of just one of the chips but without the dicing border 
#(this will technically overwrite the block list with itself, so best to do this when you set the chip buffer)
w.chips[1].save(w,drawCopyDXF=True,dicingBorder=False)
    

# Now that all chips are saved in the blocks section, write instances of the chips at the right spots on the wafer
w.populate()
w.save()