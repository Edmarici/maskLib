#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
filter_BB: quarter-wave open-stub band-block filter for the SNAIL
beamsplitter pump/drive line's on-chip protection filtering - Rev 8 DESIGN
PIVOT (Option A) away from the L30/L45/L60 lumped-LC ladder family.

REV 13 (zero-placement, iterative): stub lengths are no longer pure
synthesis theory - fan_length_correction_um()/_iterative_dl_um_seed()
re-derive each stub's target length from the PREVIOUS PASS's own real HFSS
first-light measurement (PREVIOUS_PASS_DASHBOARD_CSV/PREVIOUS_PASS_DIMS_JSON,
currently pass 1's: Radial_Stub_LPF/HFSS/firstlight2_quickscan_pass1_*),
since Rev 12 showed the whole composite response landing meaningfully high
in frequency. Pass 1 seeded from Rev 12 directly (a one-time transition off
the old flat fan correction, _rev12_dl_um_seed() in git history); every
pass from 2 onward just projects off the immediately-preceding pass,
uniformly, via simple f~1/L scaling. See fan_length_correction_um()/
_iterative_dl_um_seed()'s own docstrings and DESIGN_NOTES Sec. 9-10 for the
full derivation, including a sign inversion caught against an earlier draft
of the fan-correction formula before implementing (pass 1 only).

PRINCIPLE: an open-circuited stub of length l shorts the main line at
f = c/(4*l*sqrt(eps_eff)) (quarter-wave interference null) and again at
3f, 5f, ... The zero depends ONLY on length and eps_eff - not on any
capacitance to ground - so the package cannot starve it, unlike
filter_L60.py's fan-capacitance zeros, which this session's own Phase 2
package sim confirmed can't reach: the 7.0mm bore keeps all ground >3mm
away, so fan capacitance is fringing-only and scaling the fans is a losing
fight (4.5GHz attenuation came back at ~0dB - see notebooks/
L60_design_notes.md sec 11). Staggered stub lengths blanket the protection
band with overlapping notches. This is a band-BLOCK, not a lowpass -
transmission recovers above the highest-frequency stub, so 8-12GHz is
checked explicitly (HFSS, out of scope this pass - see below).
Architectural precedent: Hajr et al., PRX 14, 041049 (2024) - multi-stub
band-block on a SNAIL pump line, stub lengths tuned in HFSS.

NEW FILE - filter_L30.py/filter_L45.py/filter_L60.py are untouched (L60
stays the fallback/comparison design). Self-contained (deliberately
duplicated helpers - _corners/guarded_straight/guarded_taper/guarded_bend/
radial_fan/guarded_fan_taper/_flush_attach_width are verbatim copies from
filter_L60.py), same convention as that whole file family.

CHIP WIDTH: 6.9mm (not the handoff's literal "7x40mm" line) - matches
filter_L60.py's own just-revised real chip width for the same 7.0mm-bore
package (confirmed with Eddie this session; the handoff's own stated
6000um width budget only comes out exact - 2*(7000/2-500)=6000 - using the
revised 7.0mm bore, supporting evidence this carries over here too).

SCOPE OF THIS PASS: LAYOUT ONLY (mask + DXF/GDS + Heidelberg-safety checks
+ runtime report), matching the handoff's own deliverable framing. The
handoff's "HFSS plan" GATING ITEM has now been run once (Radial_Stub_LPF/
extract_epseff.py - bare 70um/125um strip on sapphire (9.4,9.4,11.6) in the
real 7.0mm bore, wave-port eigenmode extraction, pyaedt/AEDT 2023 R2) -
see EPS_EFF below. Only the single 6GHz mid-band point is trusted; the
script's own 1-12GHz swept extraction produced non-physical dispersion
(mode index didn't track the same physical mode across frequency - beta
collapsing to 0 near 12GHz, ~130% apparent "dispersion") and is NOT used
here. Per-stub dl_um trimming and the full-band dispersion question stay
open, Eddie-side follow-up items - not attempted this pass.

GEOMETRY DESIGN NOTES (decisions made implementing this handoff):

  - No positive-metal tee primitive exists anywhere in maskLib (checked
    microwaveLib.py - only CPW_tee, XOR-gap-only). Same hand-built-overlap
    T-junction convention filter_L60.py already uses (branch spawned via
    Structure.cloneAlong() at the main line's CURRENT point, natural root
    overlap - CLAUDE.md's FlagPads/JJ_chain pattern) - just single-sided
    here (one stub per junction, not a mirrored pair).

  - "Reuse the Rev 5 folded-branch generator verbatim" means
    filter_L30.py's folded_branch_pair() exact-length-by-construction
    solve (a byte-identical copy already lives in filter_L60.py) - NOT
    maskLib.microwaveLib.wiggle_calc()/CPW_wiggles/Strip_wiggles, a
    different (more general) meander-length solver that also exists in
    this codebase but belongs to the CPW/XOR family and isn't what "Rev 5"
    refers to in this repo's own terminology.

  - folded_stub() (below) is NEW, not a copy: filter_L60.py's
    folded_branch_pair() always draws a MIRRORED PAIR ending in a
    TRANSVERSE fan (via a deliberate exit turn, per Eddie's own L60 Rev7
    correction). This handoff wants the OPPOSITE fan orientation - "fan
    terminators oriented axially at meander ends" - so folded_stub()
    combines folded_branch_pair()'s entrance-turn/n_bends-internal-turns
    machinery with l_bend_branch_pair()'s "no exit turn" idea (generalized
    from l_bend's single turn to n_bends turns), and is single-sided (one
    stub per call, no mirror-handedness-flip needed since there's nothing
    to mirror). See folded_stub()'s own docstring for the turn-arc-length
    formula this implies.

  - fan_term's Rin is DERIVED (not specified by the handoff) so the 90deg
    terminating fan attaches FLUSH to the stub width (w = 2*r_in*sin(45deg)
    -> r_in = w/(2*sin(45deg))) - no Rev7-style deliberate flare, since
    nothing here asks for one. For w=125um this works out to r_in=88.39um
    - not a coincidence: it's the same value filter_L60.py's own P2-P5
    fans used before Rev7's FAN_ANGLE=115 change, a useful cross-check
    that this derivation is principled.

  - run_gap = max(4*w, _MIN_RUN_GAP_UM) reproduces the handoff's stated
    500um (125um stubs)/400um (70um stubs) exactly from one general rule
    (same self-coupling-margin-floor concept as filter_L60.py's own
    _MIN_RUN_GAP_UM), rather than hardcoding per-stub run_gap values.

  - fold_dir alternates per SIDE GROUP, not per adjacent list entry - the
    v1 STUBS table already alternates side on every entry, so there are no
    list-adjacent same-side pairs; "same-side neighbors" means the
    nearest OTHER stub sharing that side (three stubs each on +1/-1).

KNOWN RISK, explicitly verified (not just assumed) after building: axial-
oriented terminal fans reaching back over a fold's own open "mouth" can
enclose a real hole - the same mechanism documented in CLAUDE.md and
L60_design_notes.md sec 10.2 for L30/L60's own axial-fan history.
fan_term's Rout here (300um) is far smaller than L60's synthesized fans
(1100-2000um), lowering but not eliminating the risk - see the klayout
check this file's own build/verification session ran against the real
exported GDS (notebooks/BB_design_notes.md).
"""
import csv
import json
import math
import os

from dxfwrite import const
from dxfwrite import DXFEngine as dxf

import maskLib.MaskLib as m
from maskLib.microwaveLib import Strip_straight, Strip_taper, Strip_bend
from maskLib.Entities import CurveRect
from maskLib.gdsExport import dxf_to_gds
from maskLib.layerDoseTable import gds_layer_number

# ===============================================================================
# tunable constants
# ===============================================================================

# Extracted 6GHz value from Radial_Stub_LPF/extract_epseff.py (wave-port
# eigenmode solve, bare strip on anisotropic sapphire (9.4,9.4,11.6) in the
# real 7.0mm bore, 70um/125um both solved and field-plot-verified as the
# true strip mode - not a bulk cavity mode): eps_eff = 5.6795 (w=70um),
# 5.6826 (w=125um) at 6GHz - matching Zpi ~= 69.7 ohm both widths. The two
# widths agree to <0.1%, so one global constant (not per-width/per-stub) is
# justified; using the average. Only this single mid-band point is trusted
# - see module docstring re: the 1-12GHz sweep's non-physical dispersion
# (open follow-up, not resolved). Every stub length below is a pure
# function of this constant - update it and every length recomputes
# automatically, same "derived, not hardcoded" discipline as
# filter_L60.py's WIDTH_BUDGET_UM.
EPS_EFF = 5.681  # HFSS-extracted @ 6GHz (was 5.5 placeholder)

W_MAIN = 70.0  # um, main line width (carried over from L60 Rev 7's W_HIZ)

# ===============================================================================
# Rev 13 zero-placement (iterative): re-derive stub lengths from the most
# recent real HFSS first-light measurement of THIS EXACT geometry, not from
# synthesis theory alone. Each pass reads the PREVIOUS pass's own dims JSON
# (what was actually built) + dashboard CSV (what it actually measured) and
# projects a new length via simple f~1/L scaling - see
# _iterative_dl_um_seed() below. DESIGN_NOTES Sec. 9-10 has the full write-up.
# ===============================================================================

# K_FAN_UM/F_REF_GHZ are the ONE-TIME pass-1 anchor (Rev12->pass1 transition
# only) - fan_length_correction_um() stays fixed at these values for every
# LATER pass too (D1 in the Rev 13 pass-2 handoff: "don't re-tune the model
# constants mid-iteration" - dl_um residual seeding, not the formula itself,
# absorbs each pass's own remaining error, both signs, automatically).
K_FAN_UM = 0.6
F_REF_GHZ = 7.0  # anchor: S5 (7.0GHz) landed closest to prediction under the old flat correction (+2.4%)

INPUT_SECTION_EXTRA_UM = 2000.0  # D2: lengthens the line between the input taper and S1's own tee

# Points at the PREVIOUS pass's own outputs - bump these two names together
# when starting a new pass (this pass reads pass 1's; a hypothetical pass 3
# would read pass 2's, etc.).
#
# Rev 16 Step 0 FIX: Rev 15 bumped these to pass-3's own (hardened) output
# intending "S1 frozen at v2, S2-S6 unchanged from pass-3" - but pointing
# _iterative_dl_um_seed() at pass-3's own dashboard doesn't FREEZE S2-S6,
# it projects ANOTHER f~1/L correction step from pass-3's own non-zero
# landed-vs-target deltas (like seeding a hypothetical pass 4). Confirmed
# by diff against filter_BB_dims_pass3.json: S3 target_length silently
# drifted 7395.29um -> 7116.23um (S2's own pass-3 delta was exactly 0%, so
# it happened to be a no-op there, masking the bug for that one stub).
# Fix: point at nonexistent files so EVERY stub's seed defaults to 0 (see
# _load_previous_pass_dashboard()/_load_previous_pass_dims()'s own
# graceful-empty-dict handling) - every one of the 7 stubs is now a frozen
# constant via its own manual dl_um in STUBS below, matching what
# "baseline" actually means. Real pass-3 seeding data still lives in
# filter_BB_dims_pass3.json/firstlight2_quickscan_pass3_dashboard_hardened.csv
# on disk for reference - just no longer wired up as a live input.
PREVIOUS_PASS_DIMS_JSON = 'NONE_frozen_v2_baseline_dims.json'
PREVIOUS_PASS_DASHBOARD_CSV = 'NONE_frozen_v2_baseline_dashboard.csv'


def _load_previous_pass_dashboard():
    """Previous pass's own HFSS-measured dashboard - target_f_ghz/landed_f_ghz
    per stub label. Returns {} with a loud warning if missing, so filter_BB.py
    still runs standalone (dl_um seeds fall back to 0) without a prior run."""
    path = os.path.join(os.path.dirname(__file__), 'HFSS', PREVIOUS_PASS_DASHBOARD_CSV)
    if not os.path.exists(path):
        print('\x1b[33mWARNING: %s not found - dl_um seeds default to 0 for every stub '
              '(need the previous pass\'s own first-light dashboard as input)\x1b[0m' % path)
        return {}
    out = {}
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            out[row['label']] = row
    return out


def _load_previous_pass_dims():
    """Previous pass's own dims JSON - what was ACTUALLY BUILT (realized
    target_length_um) per stub label, keyed the same way. Needed alongside
    the dashboard because the iterative seed projects from the REAL built
    length, not from any re-derivation of an older baseline (see
    _iterative_dl_um_seed()'s own docstring)."""
    path = os.path.join(os.path.dirname(__file__), 'HFSS', PREVIOUS_PASS_DIMS_JSON)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    return {s['label']: s for s in data['stubs']}


_PREV_DASHBOARD = _load_previous_pass_dashboard()
_PREV_DIMS = _load_previous_pass_dims()

# f_zero_GHz, width_um, side (+1/-1), fold n_par_runs, fan_term Rout_um
# (0 = plain open end), dl_um (per-stub HFSS length trim, default 0 -
# present in the table for future iteration, not exercised this pass).
STUBS = [
    # Rev 17 D2: S1 RETARGETED 4.2 -> 4.5GHz, and its accumulated dl_um RESET
    # to zero. With S7 deleted (D1) S1 is the only element that can cover the
    # SNAIL band, so it belongs ON the acceptance frequency rather than
    # 300MHz below it. Three effects at once: (1) S1 gets SHORTER
    # (8610.10 -> 6987.90um at dl_um=0, since it's unterminated so no fan
    # correction applies); (2) less passband loading at the band edge (at
    # 3.5GHz a 4.5GHz stub sits at theta~70deg, B~2.8, vs theta~75deg,
    # B~3.7 for a 4.2GHz stub - roughly 2dB less shunt loading, for free);
    # (3) the S21@4.5GHz criterion becomes directly addressable by one
    # element. The dl_um reset is deliberate: that 1123.06um was accumulated
    # against a feature Rev 14 showed was never S1's own resonance, so it
    # carries no information worth keeping.
    # Rev 17 B2: S1 uses the L geometry (geom='L', see l_stub()) - measured
    # k_eff 0.891 vs 0.659 for the 3-run serpentine it used to have, i.e. far
    # less fold cancellation. dl_um carries that geometry's OWN measured
    # residual: V-L at a 6987.90um drawn length landed at 5.050GHz instead of
    # its bare 4.500GHz (ratio 1.1222), so landing ON 4.5GHz needs
    # 6987.90 * 1.1222 = 7841.97um -> dl_um = 7841.97 - 6987.90 = 854.07.
    # This is an empirical correction from a real solve, deliberately NOT a
    # theory value - the residual's own cause (eps_eff for a stub vs. the
    # bare through-line it was extracted from, and/or tee loading) is a real
    # open question, logged rather than chased.
    # ---------------- Rev 18: S1 is now a WIDE-GAP SINGLE FOLD ----------------
    # Replaces Rev 17's L geometry. Motive: in v3 the L stub's open end (a
    # voltage antinode) came to rest 783um from S3's fan (also an antinode) -
    # the tightest pair in the whole design - and S3's own -66dB notch
    # disappeared from the v3 sweep. Rev 16's Track A had already seen the
    # coupling (perturbing S1 moved the 5.355GHz S3 notch harder than anything
    # else). Folding S1 back on itself keeps the length while pulling its
    # far end away from S3.
    #
    # Geometry: 2 runs at a 1000um gap (-> bend_radius (1000+70)/2 = 535um),
    # the fold experiment's measured-best serpentine (k_eff 0.792). Landing on
    # 4.5GHz therefore needs 6987.90/0.792254 = 8820.28um drawn, so
    # dl_um = 8820.28 - 6987.90 = 1832.38. CAVEAT: k_eff 0.792 was measured on
    # a 6987.90um piece and is being applied 26.2% beyond it (the L case
    # extrapolated only 12%) - if the null lands well off 4.5GHz, suspect this
    # extrapolation before suspecting the geometry.
    #
    # fold_dir=-1 folds NORTH, away from S3, which is the whole point. The
    # handoff assumed a southward fold that turns back before reaching S3's
    # latitude; that is geometrically impossible here - swept d_perp over
    # 600..4200um for both fold handednesses and NO southward configuration
    # satisfies the standoff, S1-S3 separation, transverse and bore
    # constraints simultaneously (the U-turn apex cannot get far enough from
    # S3 without pushing the return run through the 6950um bore wall).
    # Folding north makes S1's southernmost metal its own exit segment at
    # y=29965, i.e. 4915um clear of S3's top - nearly 2x the requirement -
    # at zero cost. d_perp=1200um then keeps the return run 1665um off the
    # main line and the outer run 660um inside the bore wall, with the fold
    # apex at y~33085, 1915um short of the y=35000 port plane (the failure
    # mode that killed a +y L stub in Rev 17 - checked explicitly here).
    # ---------------- Rev 20 B1: S1 TRIMMED 70.56um (8820.28 -> 8749.72) ----------------
    # Moves S1's null 4.340 -> 4.375GHz, i.e. from 10MHz BELOW buffer 1's
    # scored window ([4.350, 4.650]) to 25MHz inside it. S1 is buffer 1's
    # primary protection - deleting it cost 13.6dB there - and the window's low
    # edge falls off sharply, so the target is 4.375 and deliberately not
    # higher.
    #
    # WHICH MEASUREMENT THE TRIM IS BUILT ON, because they disagree: S1's null
    # has read 4.310 (census), 4.325 (Rev 18 probe) and 4.340 (Rev 19 B3/B4).
    # The Rev 20 handoff's 100.8um comes from 4.325 (k_eff 0.8243). 4.340 is
    # used here instead because B3/B4 read it off REAL DISCRETE SOLVED POINTS
    # (the 10MHz Discrete_Window), while every other value comes from an
    # Interpolating sweep's rational reconstruction, which misplaces sharp
    # minima. Rev 20's own probe baseline measured that bias directly: its
    # interpolated nulls sit a mean 14MHz (worst 35MHz) below the discrete
    # ones, in the same direction, at every one of seven nulls. So the spread
    # is a sweep-type artifact, not mesh noise, and the discrete number is the
    # one to trim against.
    #
    # Scaling is exact and needs no k_eff: null frequency goes as 1/length at
    # fixed geometry, so L_new = 8820.2836 * 4.340/4.375 = 8749.7214um and
    # dl_um drops by 70.5623. Each of the two parallel runs shortens 35.28um;
    # the fold apex moves 35um FURTHER from the y=35000 port plane, so every
    # Rev 18 clearance gets marginally better, none worse.
    dict(f=4.5, w=70.0, side=+1, n_par_runs=2, fan_term=0.0,
         dl_um=1761.8205974802, run_gap=1000.0, d_perp=1200.0, fold_dir=-1),
    # Rev 16 Step 0: S2-S6 FROZEN at their exact pass-3 realized lengths -
    # each dl_um below is copied verbatim from that stub's own recorded
    # dl_um_seed in filter_BB_dims_pass3.json (S2's pass-3 delta was exactly
    # 0%, so this reproduces its length exactly; S3-S6 had nonzero deltas,
    # which is exactly what was silently drifting before this fix - see the
    # PREVIOUS_PASS_* comment above). NOT live-reseeded - same "frozen
    # baseline" discipline as S1's own dl_um above.
    dict(f=4.7, w=70.0, side=-1, n_par_runs=3, fan_term=300.0, dl_um=3206.40664222529),
    dict(f=5.3, w=70.0, side=+1, n_par_runs=2, fan_term=300.0, dl_um=1598.4552595998848, fold_dir=+1),  # Rev13: overrides
        # auto -1 - at Rev13's much-longer length, -1 swung S3's fold up into S1's own territory (75um
        # clearance, confirmed via direct pairwise vertex-distance calc); +1 clears it (2806um) instead
    dict(f=6.1, w=70.0, side=-1, n_par_runs=2, fan_term=300.0, dl_um=583.162019879448),
    dict(f=7.0, w=70.0, side=+1, n_par_runs=2, fan_term=300.0, dl_um=-4.414055730569999),
    # ------- Rev 19 B2: S6 RETARGETED 8.0 -> 5.98GHz (was frozen since Rev 16) -------
    # WHY IT WAS FREE TO MOVE: the Rev 19 full-range census (0.5-14GHz, the
    # first sweep in this campaign wide enough to see them) found 12 nulls,
    # not the 5 the Rev 18 probe's 3.5-9.0GHz window reported. Assigning one
    # null per stub gives a k_eff sequence consistent with the fold
    # experiment's independently measured values - notably S2 at 0.664
    # against a measured 0.659 for a 3-run/400um fold - and puts S6's own
    # null at 9.970GHz. That is ABOVE the 8.001GHz top of the mode comb, so
    # S6 was contributing nothing to the acceptance spec; storage 7 (8.001)
    # is covered by S5's 8.125 null, not by S6.
    #
    # WHERE IT GOES: the only remaining FLAG is storage 1 (5.792GHz, ~-18.1dB),
    # caused by the 1.410GHz gap between S3's 5.480 and S4's 6.890 nulls.
    # 5.98GHz is the midpoint of the two comb modes stranded in that gap
    # (5.792 and 6.160), putting each ~185MHz from a null rather than
    # bullseyeing one and leaving the other exposed. Resulting null spacings
    # 0.500 and 0.910GHz, both inside the <=1.0GHz valley rule.
    #
    # LENGTH: S6's own measured k_eff = bare 8.1447 / null 9.970 = 0.81692, so
    # landing 5.98GHz needs 6436.90um drawn. dl_um = 6436.90 - 5258.45
    # (quarter-wave at 5.98GHz) = 1178.45. This is S6's OWN measured ratio,
    # not an extrapolation from another stub's geometry - the mistake that
    # put S1 3.9% low in Rev 18.
    #
    # NOT YET PROVEN: S6's ownership of 9.970 is inferred from k_eff
    # consistency, not confirmed by deletion the way S1 (4.310) and S4
    # (6.890) were. This edit doubles as that test - if 9.970 disappears and
    # a null appears near 5.98, the assignment was right.
    # fold_dir=-1 overrides the automatic +1 this stub would otherwise get.
    # At its old 3861um length S6's runs were short enough that folding north
    # was harmless; at 6437um they are not. Auto +1 folds S6 north while S4
    # (side=-1, fold_dir=-1) folds south, so the two U-turns approach head-on
    # over an identical x span (both side=-1 with the same d_perp/run_gap) and
    # close to 88.5um - a hard fail against the 800um floor, and at that
    # spacing in a groundless bore they would hybridise violently rather than
    # act as two independent stubs. -1 turns S6 south into the empty run above
    # the output taper instead. Same override, same reason, as S3's own
    # Rev 13 fix. Caught by the all-pairs clearance check, not by inspection.
    # ---- Rev 20 B3: S6 LENGTHENED 6436.90 -> 7379.32um to land storage 1 ----
    # Rev 19 B4 established by DELETION that S6 owns TWO nulls, 6.640 and
    # 7.580GHz - not the one null every earlier inference assumed. This move
    # puts the LOWER of them on storage 1 (5.792GHz), the design's only flag:
    #
    #   L = 6436.9032 * 6.640/5.792 = 7379.3227um   (+942.42, +14.64%)
    #
    # No k_eff appears in that arithmetic on purpose. Rev 20 B1 confirmed pure
    # 1/length scaling on a real solve - S1's null moved +30MHz against +35MHz
    # predicted, agreement one sweep grid point - so a length edit needs only
    # the measured null and the ratio of frequencies. Every k_eff round trip
    # this campaign attempted (Rev 18's S1, Rev 19 B2's S6) landed several
    # percent off.
    #
    # f=5.98 is left alone deliberately: it is now only a LABEL (the piece
    # prefix '6.0GHz' that the deletion tests filter on). This stub has not
    # resonated at its nominal target since Rev 19 B2, and renaming it would
    # break the attribution machinery for no gain. The number that means
    # anything is realized_length_um.
    #
    # WHAT B2 REMOVED FROM THE MENU: the handoff's candidate (b) was this same
    # move with the run gap widened to retune the pair's span. Rev 20 B2 ran
    # S6's exact topology (2 runs, 400um gap, this length) alone in the real
    # bore and got ONE null at 6.780GHz, not a pair - so there is no measured
    # gap-to-span law to apply, and (b) cannot be specified. Note 6.780 sits
    # only 2.06% from the cascade's LOWER null but 4.64% from the pair centre:
    # the lower null is S6's own resonance lightly pulled by neighbour loading,
    # and the upper null exists only in the cascade. Mechanism still unknown -
    # see DESIGN_NOTES sec 15.
    #
    # RISK, stated before the solve (HFSS/v6_prediction_locked.md): S6's
    # 7.580GHz null is currently worth +3.7dB to storage 6 and +4.1dB to
    # storage 7. Moving it to 6.612 should push both toward their measured
    # S6-ABSENT values (-20.09 and -19.76), so this may trade storage 1's
    # -4.2dB flag for a ~-0.2dB one at storage 7.
    dict(f=5.98, w=70.0, side=-1, n_par_runs=2, fan_term=0.0, dl_um=2120.8689,
         fold_dir=-1),
    # Rev 17 D1: S7 (4.4GHz) DELETED outright. Rev 16's real solve found it
    # produced NO notch at all, while still costing ~2.5mm of line length and
    # adding a passband shunt susceptance - so it was pure cost. Removing it
    # shortens the filter and should improve passband ripple (confirmed or
    # refuted by the v3 solve's own ripple-vs-v2+S7 comparison). Deleted
    # rather than disabled/zero-lengthed, per D1, so nothing downstream can
    # accidentally resurrect it.
]

# um, default series-section length between stub junctions - "parameterize
# per-section" per the handoff: override individual entries below if a
# future pass needs non-uniform spacing (classic multi-stub band-stop
# theory prefers ~lambda/4 at band center, ~5.8mm, for maximally flat
# composite rejection, but that costs ~30mm of line; starting compact and
# letting HFSS shape the composite response via these lengths instead).
SERIES_SECTION_LENGTH_UM = 2500.0
SERIES_SECTIONS = [{'length': SERIES_SECTION_LENGTH_UM} for _ in STUBS]
assert len(SERIES_SECTIONS) == len(STUBS)

# um - fold geometry, per the handoff ("d_perp 1000um, run_gap 400/500um").
D_PERP_UM = 1000.0

# Rev 17 B2: L-stub geometry (geom='L' in STUBS), measured to have the mildest
# fold penalty of any real-bore geometry tested. See l_stub() and the S1 entry.
L_STUB_D_PERP_UM = 2500.0      # perpendicular standoff before the single 90deg turn
L_STUB_BEND_RADIUS_UM = 235.0  # same radius the fold variants use (run_gap 400 equivalent)

DWL_MIN_LEN = 0.5  # um - see _MIN_LEN below (DWL 66+ degenerate-path guard)
_MIN_LEN = DWL_MIN_LEN
_MIN_RADIUS_UM = 5.0  # um, apex/bend-radius guard (fan r_in, bend radius)
_MIN_RUN_GAP_UM = 400.0  # um, self-coupling-margin floor (see run_gap derivation above)

# um - real package bore, matches filter_L60.py's own revised value
# (Step 0, this session) - 500um wall clearance is still an ASSUMPTION
# pending the real package drawing (handoff item O1).
PACKAGE_BORE_DIAMETER_UM = 7000.0
PACKAGE_WALL_CLEARANCE_UM = 500.0
WIDTH_BUDGET_UM = 2 * (PACKAGE_BORE_DIAMETER_UM / 2 - PACKAGE_WALL_CLEARANCE_UM)

METAL_LAYER = 'BASEMETAL'
MARKER_LAYER = 'MARKERS'

# Same values as filter_L60.py - "all conventions unchanged" per the handoff.
PIN_PAD_WIDTH = 1000.0
PIN_PAD_LENGTH = 1500.0
PAD_EDGE_MARGIN = 5000.0
INOUT_TAPER_LEN = 500.0
OUTPUT_LINE_WIDTH = 200.0
KEEPOUT_CLEARANCE = 1000.0

SNAIL_KEEPOUT_W = 3000.0
SNAIL_KEEPOUT_H = 5000.0
SNAIL_KEEPOUT_CY = 4000.0

DEFAULTS = {'w': W_MAIN, 'radius': 300.0}


# ===============================================================================
# local helpers - verbatim copies from filter_L60.py (self-contained-file
# convention, see module docstring)
# ===============================================================================

def _corners(start, direction_deg, length, w0, w1):
    d = math.radians(direction_deg)
    fwd = (math.cos(d), math.sin(d))
    perp = (math.cos(d + math.pi / 2), math.sin(d + math.pi / 2))
    end = (start[0] + length * fwd[0], start[1] + length * fwd[1])
    return [
        (start[0] + (w0 / 2) * perp[0], start[1] + (w0 / 2) * perp[1]),
        (start[0] - (w0 / 2) * perp[0], start[1] - (w0 / 2) * perp[1]),
        (end[0] + (w1 / 2) * perp[0], end[1] + (w1 / 2) * perp[1]),
        (end[0] - (w1 / 2) * perp[0], end[1] - (w1 / 2) * perp[1]),
    ]


def guarded_straight(chip, structure, length, w, layer, label=''):
    if length is None or length < _MIN_LEN:
        raise ValueError('%s: degenerate length %r um (DWL 66+ forbids zero-length paths)' % (label, length))
    pts = _corners(structure.start, structure.direction, length, w, w)
    Strip_straight(chip, structure, length, w=w, layer=layer)
    return pts


def guarded_taper(chip, structure, length, w0, w1, layer, label=''):
    if length is None or length < _MIN_LEN:
        raise ValueError('%s: degenerate length %r um (DWL 66+ forbids zero-length paths)' % (label, length))
    pts = _corners(structure.start, structure.direction, length, w0, w1)
    Strip_taper(chip, structure, length=length, w0=w0, w1=w1, layer=layer)
    Strip_straight(chip, structure, length=2 * length, w=w1, layer=layer)
    return pts


_FAN_TAPER_STEP_LEN = 25.0
_FAN_TAPER_OVERLAP_BUFFER_UM = 20.0


def guarded_fan_taper(chip, structure, w0, w1, r_in, fan_angle_deg, layer, label=''):
    """See filter_L60.py's own guarded_fan_taper() docstring for the full
    derivation (sagitta retreat + taper-must-finish-before-the-retreated-
    tip fix). Here w0 always equals w1 (stub width - no Rev7-style flare),
    so the "taper" degenerates to a same-width connector; still reused
    verbatim since the sagitta-overlap logic is independent of whether the
    width actually changes."""
    sagitta = r_in * (1 - math.cos(math.radians(fan_angle_deg) / 2))
    retreat = sagitta + _FAN_TAPER_OVERLAP_BUFFER_UM
    run_len = retreat + _FAN_TAPER_OVERLAP_BUFFER_UM

    taper_len = min(_FAN_TAPER_STEP_LEN, run_len, _FAN_TAPER_OVERLAP_BUFFER_UM - 2.0)
    if taper_len < _MIN_LEN:
        raise ValueError('%s: degenerate fan-taper length %r um' % (label, taper_len))
    pts = _corners(structure.start, structure.direction, taper_len, w0, w1)
    Strip_taper(chip, structure, length=taper_len, w0=w0, w1=w1, layer=layer)
    remaining = run_len - taper_len
    if remaining >= _MIN_LEN:
        pts += guarded_straight(chip, structure, remaining, w1, layer,
                                 label='%s fan_taper_run' % label)
    structure.translatePos(vector=(-retreat, 0))
    return pts


def guarded_bend(chip, structure, angle, CCW, w, radius, layer, label=''):
    if radius is None or radius < _MIN_RADIUS_UM:
        raise ValueError('%s: bend radius %r um below the %.1fum apex guard (DWL 66+/Heidelberg safety)'
                          % (label, radius, _MIN_RADIUS_UM))
    bookkeeping = CurveRect(structure.start, w, radius, angle=angle, ptDensity=120,
                             ralign=const.MIDDLE, valign=const.MIDDLE,
                             rotation=structure.direction, vflip=not CCW)
    bookkeeping._build()
    pts = list(bookkeeping.points)
    Strip_bend(chip, structure, angle=angle, CCW=CCW, w=w, radius=radius, ptDensity=120, layer=layer)
    return pts


def _flush_attach_width(r_in, angle_deg):
    return 2 * r_in * math.sin(math.radians(angle_deg) / 2)


def radial_fan(chip, structure, r_out, r_in, fan_angle_deg, attach_width, layer, label=''):
    if r_in < _MIN_RADIUS_UM:
        raise ValueError('%s: fan r_in %.2f um below the %.1fum apex guard (DWL 66+/Heidelberg safety)'
                          % (label, r_in, _MIN_RADIUS_UM))
    expected_attach = _flush_attach_width(r_in, fan_angle_deg)
    if abs(expected_attach - attach_width) > 0.5:
        print('\x1b[33m%s: attach_width %.2f does not match 2*r_in*sin(angle/2)=%.2f '
              '(fan will not sit perfectly flush against the stalk)\x1b[0m'
              % (label, attach_width, expected_attach))
    S = structure.direction
    tip = structure.start
    perp = (math.cos(math.radians(S + 90)), math.sin(math.radians(S + 90)))
    insert = (tip[0] + (attach_width / 2) * perp[0], tip[1] + (attach_width / 2) * perp[1])
    rotation = S + fan_angle_deg / 2 - 90
    cr = CurveRect(insert, height=r_out - r_in, radius=r_in, angle=fan_angle_deg, rotation=rotation,
                    ralign=const.BOTTOM, ptDensity=120, bgcolor=chip.wafer.bg(), layer=layer)
    chip.add(cr)
    cr._build()
    return list(cr.points)


# ===============================================================================
# stub length calculation
# ===============================================================================

def stub_quarter_wave_length_um(f_ghz, eps_eff):
    """l = c / (4*f*sqrt(eps_eff)) - the quarter-wave open-stub null
    frequency's own length, in um for f in GHz (c = 2.998e5 um*GHz).
    Matches the handoff's own reference table exactly (4.2GHz/eps=5.5 ->
    7609um vs. its stated 7.61mm) - NOTE (Rev 12): that handoff table is
    itself computed at the OLD eps=5.5 placeholder, not the live
    EPS_EFF=5.681 below - at 5.681, 4.2GHz -> 7487um (7.49mm), not 7.61mm,
    same ~1.6% offset at every stub. EPS_EFF=5.681 is the real HFSS-measured
    value (see module docstring / DESIGN_NOTES Sec. 9) and is correct as
    live; the Rev 12 handoff's own "expected" table is stale, carried over
    unedited from the original Rev 8 handoff - flagging here rather than
    silently matching it."""
    return 2.998e5 / (4 * f_ghz * math.sqrt(eps_eff))


def predicted_f_zero_ghz(length_um, eps_eff):
    """Inverse of stub_quarter_wave_length_um() - the quarter-wave null
    frequency a REALIZED length actually predicts, in GHz. Used by the
    runtime report (target f vs. predicted-from-realized-length f) and by
    Rev 12's dims JSON export, so the HFSS first-light dashboard has a
    single, already-computed source of truth rather than recomputing this
    independently in the HFSS driver script."""
    return 2.998e5 / (4 * length_um * math.sqrt(eps_eff))


def _fan_term_rin(w):
    """Derives the terminating fan's r_in so a 90deg fan attaches FLUSH to
    the stub width w (no Rev7-style deliberate flare - nothing here asks
    for one): w = 2*r_in*sin(45deg) -> r_in = w/(2*sin(45deg))."""
    return w / (2 * math.sin(math.radians(45.0)))


def fan_length_correction_um(f_ghz, rout_um):
    """Rev 13 D4: frequency-scaled fan-termination length correction,
    replacing Rev 12's flat K_FAN_UM*Rout. Modeled as a fixed FRACTION of
    guided wavelength (SMALLER absolute correction, i.e. a LONGER stub
    kept, at low frequency) rather than a fixed absolute length - matching
    the Rev 12 data: every fan-terminated stub landed ABOVE its target
    under the flat correction, and a resonator landing high needs MORE
    length, not less (f~1/L). NOTE: an earlier draft of this formula used
    (F_REF_GHZ/f_ghz) - the OPPOSITE direction, which would make low-
    frequency stubs SHORTER, not longer - caught and inverted against the
    Rev 12 measurements before implementing (see git history/DESIGN_NOTES
    Sec. 9 for the sign-check). Anchored at F_REF_GHZ (S5) so the
    correction there stays ~unchanged from Rev 12's own flat value."""
    return K_FAN_UM * rout_um * (f_ghz / F_REF_GHZ)


def _iterative_dl_um_seed(spec, nominal_length_um, fan_correction_um):
    """Rev 13 (iterative, pass 2+): this stub's own dl_um SEED, derived
    directly from the PREVIOUS pass's own real HFSS measurement of the
    ACTUAL geometry that was built and solved - NOT re-derived from any
    older/stale baseline (pass 1's own _rev12_dl_um_seed() special-cased
    the one-time Rev12-flat-correction transition; from pass 2 onward,
    every pass just projects off the immediately-preceding one, uniformly).

    f~1/L (same D1 principle as pass 1, applied iteratively): if the
    previous pass's built length L_prev landed at f_prev instead of this
    stub's own target, the new length that should land on target (by the
    same local linear scaling) is L_new = L_prev * (f_prev / target_f).
    Sign-symmetric by construction - a stub that landed LOW gets LESS
    length, not just stubs landing HIGH (confirmed both signs occurred in
    pass 1's own quick-scan: S1-S4 landed above target, S5/S6 landed at-or-
    slightly-below - both directions flow through this one formula with no
    special-casing). Returns 0 (no seed change) if no previous measurement
    exists for this stub (S1 no longer needs pass 1's own baseline stand-in
    - it found a real notch in pass 1, so it now uses this same real-
    measurement path as every other stub)."""
    label = '%.1fGHz' % spec['f']
    target_f = spec['f']
    prev_dash = _PREV_DASHBOARD.get(label)
    prev_dims = _PREV_DIMS.get(label)
    if prev_dash is None or not prev_dash.get('landed_f_ghz') or prev_dims is None:
        return 0.0
    landed_f = float(prev_dash['landed_f_ghz'])
    l_prev_realized = float(prev_dims['target_length_um'])
    l_new = l_prev_realized * (landed_f / target_f)
    corrected_length_um = nominal_length_um - fan_correction_um
    return l_new - corrected_length_um


def _prepare_stub(spec):
    """Builds the derived fields (nominal/corrected/target length, fan
    r_in) for one STUBS entry - the ONLY place this math happens, base
    STUBS table stays verbatim as the reference (same discipline as
    filter_L60.py's _apply_scales()). Rev 13: target_length now includes
    the previous-pass-seeded dl_um trim (see _iterative_dl_um_seed()) ON
    TOP OF the table's own dl_um (currently 0 for every entry - kept as
    the manual fine-trim knob per the table's own original design intent)."""
    s = dict(spec)
    s['nominal_length'] = stub_quarter_wave_length_um(spec['f'], EPS_EFF)
    if spec['fan_term'] > 0:
        s['fan_correction_um'] = fan_length_correction_um(spec['f'], spec['fan_term'])
        s['corrected_length'] = s['nominal_length'] - s['fan_correction_um']
        s['fan_term_rin'] = _fan_term_rin(spec['w'])
    else:
        s['fan_correction_um'] = 0.0
        s['corrected_length'] = s['nominal_length']
        s['fan_term_rin'] = None
    s['dl_um_seed'] = _iterative_dl_um_seed(spec, s['nominal_length'], s['fan_correction_um'])
    s['dl_um_total'] = spec['dl_um'] + s['dl_um_seed']
    s['target_length'] = s['corrected_length'] + s['dl_um_total']
    return s


# ===============================================================================
# stub geometry - NEW (single-sided, axial-fan-terminated) - see module
# docstring for why this differs from filter_L60.py's folded_branch_pair()
# ===============================================================================

def folded_stub(chip, s_main, spec, fold_params, layer, label=''):
    """
    Draws ONE open-circuited stub off s_main's CURRENT position (single-
    sided - unlike filter_L60.py's folded_branch_pair(), which always
    draws a mirrored +y/-y pair): perpendicular exit run (d_perp) -> 90deg
    entrance turn (into axial) -> alternating 180deg internal bends+runs
    -> NO exit turn -> fan terminator (fan_term>0) or a plain open end.

    The missing exit turn is deliberate: filter_L60.py's own exit turn
    exists specifically to rotate the fan back to TRANSVERSE (Eddie's own
    Rev7 correction there) - this handoff wants fan terminators AXIAL, so
    the terminal run's own direction is left as-is (l_bend_branch_pair()'s
    single-turn precedent, generalized to n_bends turns).

    Does NOT mutate s_main (spawns via cloneAlong). Returns (verts,
    run_length, bend_radius, realized_length_um) - the last is exact by
    construction but computed/returned explicitly for the runtime report's
    target-vs-realized check, per the handoff's own requirement.
    """
    d_perp = fold_params['d_perp']
    n_par_runs = fold_params['n_par_runs']
    run_gap = fold_params['run_gap']
    if run_gap < _MIN_RUN_GAP_UM:
        raise ValueError('%s: run_gap %.2f um below the %.1fum self-coupling margin floor'
                          % (label, run_gap, _MIN_RUN_GAP_UM))
    CCW = fold_params['fold_dir'] > 0
    w = spec['w']
    bend_radius = (run_gap + w) / 2
    if bend_radius < _MIN_RADIUS_UM:
        raise ValueError('%s: bend radius %.2f um below the %.1fum apex guard'
                          % (label, bend_radius, _MIN_RADIUS_UM))

    n_bends = n_par_runs - 1
    # Entrance turn (90deg) + n_bends internal 180deg turns, NO exit turn =
    # (n_bends + 0.5) full 180deg-turn-lengths' worth of arc (vs.
    # folded_branch_pair()'s (n_bends+1), which includes the exit turn).
    turn_arc_len = math.pi * bend_radius * (n_bends + 0.5)
    run_length = (spec['target_length'] - d_perp - turn_arc_len) / n_par_runs
    if run_length < _MIN_LEN:
        raise ValueError('%s: folded stub run length %.2f um is degenerate/negative - d_perp too large '
                          'or too many parallel runs for this target_length=%.1fum'
                          % (label, run_length, spec['target_length']))

    s_b = s_main.cloneAlong(vector=(0, 0), newDirection=spec['side'] * 90)
    pts = guarded_straight(chip, s_b, d_perp, w, layer, label='%s exit' % label)
    turn_CCW = CCW
    pts += guarded_bend(chip, s_b, 90, turn_CCW, w, bend_radius, layer, label='%s entrance turn' % label)
    pts += guarded_straight(chip, s_b, run_length, w, layer, label='%s run1' % label)
    for i in range(n_bends):
        turn_CCW = not turn_CCW
        pts += guarded_bend(chip, s_b, 180, turn_CCW, w, bend_radius, layer, label='%s bend%d' % (label, i + 1))
        pts += guarded_straight(chip, s_b, run_length, w, layer, label='%s run%d' % (label, i + 2))

    realized_length_um = d_perp + turn_arc_len + n_par_runs * run_length

    if spec['fan_term'] > 0:
        fan_rin = spec['fan_term_rin']
        pts += guarded_fan_taper(chip, s_b, w, w, fan_rin, 90.0, layer, label='%s fan_taper' % label)
        pts += radial_fan(chip, s_b, spec['fan_term'], fan_rin, 90.0, w, layer, label='%s fan' % label)

    return pts, run_length, bend_radius, realized_length_um


def l_stub(chip, s_main, spec, l_params, layer, label=''):
    """
    Rev 17 B2: SINGLE-BEND "L" stub - perpendicular standoff, one 90deg turn,
    then the remaining length axially (parallel to the main line). NEW in
    Rev 17, and the measured-best real-bore geometry.

    WHY THIS EXISTS: filter_BB's own serpentine folds carry a large,
    quantified electrical-length penalty in this groundless bore. Measured
    directly (filter_BB_fold_experiment_HFSS.py, one stub alone on a matched
    through-line, four geometries at an IDENTICAL 6987.9um drawn length, all
    in the real 7000um bore):

        3 parallel runs, 400um gap  -> null 6.830GHz, k_eff = 0.659
        2 parallel runs, 1000um gap -> null 5.680GHz, k_eff = 0.792
        L (this function)           -> null 5.050GHz, k_eff = 0.891

    (k_eff = bare-quarter-wave frequency / measured null frequency; 1.0 would
    mean the drawn length resonates where lambda/4 theory says.) The trend is
    monotonic in both fold count and run gap - antiparallel adjacent runs
    cancel, shortening the effective electrical length and pushing the
    resonance UP. Note the resonance does NOT disappear at any fold depth
    tested; it shifts, which is why several stubs' "missing" notches in
    earlier passes were really notches sitting outside the dashboard's own
    +-30%-of-target search window.

    Even this geometry lands 12.2% high, so its own measured ratio is applied
    as an explicit length correction at the call site (see S1's dl_um) rather
    than pretended away. A 4th variant (fully straight, no bend) could not be
    tested comparably - 6988um of perpendicular reach does not fit inside the
    3500um-radius bore at all, and widening the bore to fit it changes the
    effective permittivity enough (implied eps_eff 3.87 vs 5.681) to make its
    number non-comparable.

    Does NOT mutate s_main (spawns via cloneAlong). Returns the same 4-tuple
    shape as folded_stub() so the caller's loop is geometry-agnostic.
    """
    d_perp = l_params['d_perp']
    bend_radius = l_params['bend_radius']
    if bend_radius < _MIN_RADIUS_UM:
        raise ValueError('%s: bend radius %.2f um below the %.1fum apex guard' % (label, bend_radius, _MIN_RADIUS_UM))
    CCW = l_params['fold_dir'] > 0
    w = spec['w']

    arc_len = math.pi * bend_radius / 2.0
    axial_len = spec['target_length'] - d_perp - arc_len
    if axial_len < _MIN_LEN:
        raise ValueError('%s: L-stub axial run %.2f um is degenerate/negative - d_perp too large for '
                          'this target_length=%.1fum' % (label, axial_len, spec['target_length']))

    s_b = s_main.cloneAlong(vector=(0, 0), newDirection=spec['side'] * 90)
    pts = guarded_straight(chip, s_b, d_perp, w, layer, label='%s perp' % label)
    pts += guarded_bend(chip, s_b, 90, CCW, w, bend_radius, layer, label='%s bend' % label)
    pts += guarded_straight(chip, s_b, axial_len, w, layer, label='%s axial' % label)

    realized_length_um = d_perp + arc_len + axial_len

    if spec['fan_term'] > 0:
        fan_rin = spec['fan_term_rin']
        pts += guarded_fan_taper(chip, s_b, w, w, fan_rin, 90.0, layer, label='%s fan_taper' % label)
        pts += radial_fan(chip, s_b, spec['fan_term'], fan_rin, 90.0, w, layer, label='%s fan' % label)

    return pts, axial_len, bend_radius, realized_length_um


def straight_stub(chip, s_main, spec, layer, label=''):
    """Unfolded counterpart to folded_stub() - single-sided analog of
    filter_L60.py's branch_pair(). Not exercised by the v1 STUBS table
    (every entry specifies n_par_runs, so all six fold), kept for
    family-consistency with L60's own straight+folded dual precedent."""
    w = spec['w']
    s_b = s_main.cloneAlong(vector=(0, 0), newDirection=spec['side'] * 90)
    pts = guarded_straight(chip, s_b, spec['target_length'], w, layer, label='%s stub' % label)
    realized_length_um = spec['target_length']
    if spec['fan_term'] > 0:
        fan_rin = spec['fan_term_rin']
        pts += guarded_fan_taper(chip, s_b, w, w, fan_rin, 90.0, layer, label='%s fan_taper' % label)
        pts += radial_fan(chip, s_b, spec['fan_term'], fan_rin, 90.0, w, layer, label='%s fan' % label)
    return pts, realized_length_um


def _nearest_vertex_distance(pts_a, pts_b):
    return min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in pts_a for b in pts_b)


# ===============================================================================
# wafer setup
# ===============================================================================

w = m.Wafer('filter_BB', 'DXF/', 6900, 40000, padding=1500,
            waferDiameter=m.waferDiameters['3in'], sawWidth=200,
            frame=1, solid=1, multiLayer=1, singleChipColumn=True)

w.SetupLayers([
    ['BASEMETAL', 4],
    ['MARKERS', 2],
])
w.init()
w.DicingBorder()


class FilterBBChip(m.Chip):
    def __init__(self, wafer, chipID, layer):
        # centerChip=False: same grid-snap/origin_offset rationale as
        # filter_L60.py's own class docstring - non-square chip using
        # SolidPline-family shapes (CurveRect fans).
        m.Chip.__init__(self, wafer, chipID, layer, defaults=DEFAULTS, centerChip=False)

        envelope_pts = []
        stub_vertex_sets = []  # ordered [(label, verts), ...]

        # --- SNAIL + pad keep-out (dummy placeholder marker) ---
        snail_cx, snail_cy = self.width / 2, SNAIL_KEEPOUT_CY
        self.add(dxf.rectangle((snail_cx - SNAIL_KEEPOUT_W / 2, snail_cy - SNAIL_KEEPOUT_H / 2),
                                SNAIL_KEEPOUT_W, SNAIL_KEEPOUT_H, layer=wafer.lyr(MARKER_LAYER), linetype='DASHED'))

        # --- main line ---
        x0 = self.width / 2
        y0 = self.height - PAD_EDGE_MARGIN
        s_main = m.Structure(self, start=(x0, y0), direction=-90, defaults=DEFAULTS)

        # --- input: pin pad -> taper to the main line's width ---
        envelope_pts += guarded_straight(self, s_main, PIN_PAD_LENGTH, PIN_PAD_WIDTH, METAL_LAYER, label='pin pad')
        envelope_pts += guarded_taper(self, s_main, INOUT_TAPER_LEN, PIN_PAD_WIDTH, W_MAIN,
                                       METAL_LAYER, label='input taper')

        # --- Rev 13 D2: lengthen the input section before S1's own tee -
        # gives S1 matched line upstream, cheaply ruling out "input taper
        # not yet settled" as a contributor to S1's missing Rev 12 notch.
        envelope_pts += guarded_straight(self, s_main, INPUT_SECTION_EXTRA_UM, W_MAIN, METAL_LAYER,
                                          label='input section extension')

        # --- main line: stubs + series sections, in table order ---
        prepared_stubs = [_prepare_stub(spec) for spec in STUBS]
        next_fold_dir = {+1: +1, -1: +1}  # per-side-group alternation (see module docstring)
        stub_report = []  # (label, spec, run_length, bend_radius, d_perp_clearance, ..., d_perp_um, run_gap)

        for spec, section in zip(prepared_stubs, SERIES_SECTIONS):
            label = '%.1fGHz' % spec['f']
            # Rev 18: d_perp and run_gap are per-stub overridable (defaulting to
            # the globals) so ONE stub can carry a different fold geometry
            # without disturbing the others. S1 needs both: a 1000um run gap
            # (the fold experiment's measured-best serpentine, k_eff 0.792 vs
            # 0.659 for the stock 400um gap) and a longer standoff, because the
            # wide 535um-radius U-turn pushes its return run 1070um further out
            # than a stock fold's would.
            d_perp_um = spec.get('d_perp') if spec.get('d_perp') is not None else D_PERP_UM
            d_perp_clearance = d_perp_um - W_MAIN / 2 - spec['w'] / 2
            if d_perp_clearance < 500.0:
                raise ValueError('%s: d_perp=%.1fum gives only %.1fum clearance to the main line '
                                  '(need >=500um) - increase d_perp' % (label, d_perp_um, d_perp_clearance))

            run_gap = (spec.get('run_gap') if spec.get('run_gap') is not None
                       else max(4 * spec['w'], _MIN_RUN_GAP_UM))
            # spec['fold_dir'] (optional, default None) overrides the automatic
            # per-side-group alternation for ONE stub, when a same-side non-
            # adjacent-in-table pair needs a specific fold direction to clear
            # (the alternation only guarantees ADJACENT-in-table same-side
            # stubs differ, not that either one points safely away from a
            # same-side stub further down the table - see Rev 13 clearance fix).
            # The automatic schedule still advances regardless, so any LATER
            # stub without its own override still gets what the schedule would
            # have given it anyway.
            auto_fold_dir = next_fold_dir[spec['side']]
            next_fold_dir[spec['side']] *= -1
            fold_dir = spec.get('fold_dir') if spec.get('fold_dir') is not None else auto_fold_dir
            fold_params = dict(d_perp=d_perp_um, n_par_runs=spec['n_par_runs'],
                                run_gap=run_gap, fold_dir=fold_dir)

            tee_pos = s_main.start  # main line position where this stub branches off (before the call below)
            # Rev 17: geom='L' selects the single-bend L stub (see l_stub()'s
            # own docstring for the measured fold-penalty comparison that
            # motivated it); everything else keeps the serpentine.
            if spec.get('geom') == 'L':
                l_params = dict(d_perp=L_STUB_D_PERP_UM, bend_radius=L_STUB_BEND_RADIUS_UM,
                                 fold_dir=fold_dir)
                verts, run_length, bend_radius, realized_length_um = l_stub(
                    self, s_main, spec, l_params, METAL_LAYER, label=label)
            else:
                verts, run_length, bend_radius, realized_length_um = folded_stub(
                    self, s_main, spec, fold_params, METAL_LAYER, label=label)
            predicted_f_zero = predicted_f_zero_ghz(realized_length_um, EPS_EFF)
            # Rev 19: d_perp_um/run_gap are carried through this tuple, NOT re-derived
            # at the print site. They used to be re-read from the module globals there,
            # so a per-stub override printed as the default - S1 reported
            # d_perp=1000um/run_gap=400um while actually drawn at 1200/1000. Report-only,
            # but the same bug class as the Rev 8 fold_dir loop-variable leak and just as
            # able to send a later reader down the wrong path.
            stub_report.append((label, spec, run_length, bend_radius, d_perp_clearance,
                                 realized_length_um, fold_dir, tee_pos, predicted_f_zero,
                                 d_perp_um, run_gap))
            stub_vertex_sets.append((label, verts))
            envelope_pts += verts
            envelope_pts += guarded_straight(self, s_main, section['length'], W_MAIN, METAL_LAYER,
                                              label='main line (after %s)' % label)

        # --- output: taper to a 200um line, stop 1mm short of the SNAIL keep-out ---
        envelope_pts += guarded_taper(self, s_main, INOUT_TAPER_LEN, W_MAIN,
                                       OUTPUT_LINE_WIDTH, METAL_LAYER, label='output taper')
        run_len = s_main.start[1] - (snail_cy + SNAIL_KEEPOUT_H / 2 + KEEPOUT_CLEARANCE)
        envelope_pts += guarded_straight(self, s_main, run_len, OUTPUT_LINE_WIDTH, METAL_LAYER, label='output line')

        # --- bounding box / clearance summary ---
        xs = [p[0] for p in envelope_pts]
        ys = [p[1] for p in envelope_pts]
        transverse_width = max(xs) - min(xs)
        total_length = max(ys) - min(ys)

        print('=' * 70)
        print('filter_BB: quarter-wave open-stub band-block filter (Rev 8 pivot)')
        print('eps_eff=%.3f (HFSS-extracted @ 6GHz, bare-strip-in-bore) - single mid-band point only, see docstring' % EPS_EFF)
        print('=' * 70)
        print('Substrate: 500um c-plane sapphire, NO ground plane, NO backside metal (ground = tunnel walls)')
        print('Metal: 120nm Al (single positive-draw layer, no XOR)')
        print('Chip: %d x %d um (usable %d x %d)' % (wafer.chipX, wafer.chipY, self.width, self.height))
        print('-' * 70)
        print('Stub table (single-sided, axial fan terminators):')
        for (label, spec, run_length, bend_radius, d_perp_clearance, realized_length_um,
             fold_dir, tee_pos, predicted_f_zero, d_perp_um_r, run_gap_r) in stub_report:
            fan_str = ('fan Rout=%.1fum (r_in=%.2fum, flush)' % (spec['fan_term'], spec['fan_term_rin'])
                       if spec['fan_term'] > 0 else 'open end')
            print('  %s: side=%+d w=%.1fum n_par_runs=%d %s  tee=(%.1f, %.1f)'
                  % (label, spec['side'], spec['w'], spec['n_par_runs'], fan_str, tee_pos[0], tee_pos[1]))
            if spec['fan_term'] > 0:
                print('      fan correction: old(flat,Rev12-built)=%.1fum -> new(freq-scaled)=%.1fum '
                      '(recovered=%+.1fum)'
                      % (K_FAN_UM * spec['fan_term'], spec['fan_correction_um'],
                         K_FAN_UM * spec['fan_term'] - spec['fan_correction_um']))
            print('      length: nominal=%.2fum -> fan-corrected=%.2fum -> dl_um: table(%.1f) + '
                  'prev-pass-seed(%+.1f) = %+.1f -> target=%.2fum'
                  % (spec['nominal_length'], spec['corrected_length'], spec['dl_um'],
                     spec['dl_um_seed'], spec['dl_um_total'], spec['target_length']))
            print('      realized centerline length=%.2fum (target-realized delta=%.4fum) '
                  '[d_perp=%.1fum clearance=%.1fum, run_gap=%.1fum -> bend_radius=%.1fum, run_length=%.2fum, fold_dir=%+d]'
                  % (realized_length_um, spec['target_length'] - realized_length_um, d_perp_um_r, d_perp_clearance,
                     run_gap_r, bend_radius, run_length, fold_dir))
            print('      f_zero: target=%.3fGHz -> predicted-from-realized-length=%.3fGHz (delta=%.2f%%)'
                  % (spec['f'], predicted_f_zero, 100.0 * (predicted_f_zero - spec['f']) / spec['f']))
        print('-' * 70)
        over_budget = transverse_width > WIDTH_BUDGET_UM
        print('Realized transverse bounding box: %.1f um (budget %.1f um)%s'
              % (transverse_width, WIDTH_BUDGET_UM, '  *** OVER BUDGET ***' if over_budget else ''))
        if over_budget:
            print('\x1b[31m!! WARNING: realized transverse width %.1f um exceeds %.1f um budget !!\x1b[0m'
                  % (transverse_width, WIDTH_BUDGET_UM))
        bore_half_width = PACKAGE_BORE_DIAMETER_UM / 2 - PACKAGE_WALL_CLEARANCE_UM
        print('Package bore margin (chip centered, ASSUMED %.0fum wall clearance pending O1): '
              'realized half-width %.1fum vs bore usable half-width %.1fum (bore dia %.0fum)'
              % (PACKAGE_WALL_CLEARANCE_UM, transverse_width / 2, bore_half_width, PACKAGE_BORE_DIAMETER_UM))
        print('Realized axial (length) extent: %.1f um (informational - no hard budget, 40mm chip)' % total_length)
        print('Per-stub transverse width:')
        for label, verts in stub_vertex_sets:
            pxs = [p[0] for p in verts]
            print('  %s: %.1f um' % (label, max(pxs) - min(pxs)))
        print('Per-stub nearest-neighbor clearance (vertex-to-vertex approximation - confirm visually in KLayout):')
        for i in range(len(stub_vertex_sets) - 1):
            name_a, verts_a = stub_vertex_sets[i]
            name_b, verts_b = stub_vertex_sets[i + 1]
            d = _nearest_vertex_distance(verts_a, verts_b)
            print('  %s <-> %s: %.1f um%s' % (name_a, name_b, d, '  << CHECK' if d < 500 else ''))
        print('-' * 70)
        print('Pin pad: %.1f x %.1f um, outer edge %.1f um from input edge' %
              (PIN_PAD_WIDTH, PIN_PAD_LENGTH, PAD_EDGE_MARGIN))
        print('Output line: %.1f um wide, stops %.1f um short of SNAIL keep-out' %
              (OUTPUT_LINE_WIDTH, KEEPOUT_CLEARANCE))
        print('SNAIL keep-out: %.0f x %.0f um, centered at x=%.1f y=%.1f' %
              (SNAIL_KEEPOUT_W, SNAIL_KEEPOUT_H, snail_cx, snail_cy))
        print('=' * 70)

        # --- Rev 12 Phase 1 deliverable: machine-readable dims for the HFSS
        # quick-look sim (filter_BB_firstlight_HFSS.py). This is the
        # human/dashboard-facing dimensions record, NOT the HFSS geometry
        # source - the HFSS driver rebuilds real geometry (bends/fans) via
        # verify_filter_BB_hfss_export.regenerate_metal_pieces_bb() instead
        # (already proven in filter_BB_stageA_HFSS.py), since that replays
        # exact geometry rather than re-deriving it from a flat dims list.
        dims = dict(
            eps_eff=EPS_EFF, w_main=W_MAIN, d_perp_um=D_PERP_UM,
            series_section_length_um=SERIES_SECTION_LENGTH_UM,
            bore_diameter_um=PACKAGE_BORE_DIAMETER_UM,
            transverse_width_um=transverse_width, total_length_um=total_length,
            width_budget_um=WIDTH_BUDGET_UM,
            stubs=[
                dict(label=label, f_target_ghz=spec['f'], w_um=spec['w'], side=spec['side'],
                     n_par_runs=spec['n_par_runs'], fan_term_rout_um=spec['fan_term'],
                     fan_term_rin_um=spec['fan_term_rin'], dl_um=spec['dl_um'],
                     fan_correction_um=spec['fan_correction_um'], dl_um_seed=spec['dl_um_seed'],
                     dl_um_total=spec['dl_um_total'],
                     nominal_length_um=spec['nominal_length'], corrected_length_um=spec['corrected_length'],
                     target_length_um=spec['target_length'], realized_length_um=realized_length_um,
                     predicted_f_zero_ghz=predicted_f_zero, run_length_um=run_length,
                     bend_radius_um=bend_radius, fold_dir=fold_dir, tee_pos_um=list(tee_pos),
                     d_perp_um=d_perp_um_r, run_gap_um=run_gap_r)
                for (label, spec, run_length, bend_radius, d_perp_clearance, realized_length_um,
                     fold_dir, tee_pos, predicted_f_zero, d_perp_um_r, run_gap_r) in stub_report
            ],
        )
        dims_dir = os.path.join(os.path.dirname(__file__), 'HFSS')
        os.makedirs(dims_dir, exist_ok=True)
        dims_path = os.path.join(dims_dir, 'filter_BB_dims.json')
        with open(dims_path, 'w') as f:
            json.dump(dims, f, indent=2)
        print('Dims JSON written -> %s' % dims_path)


chip = FilterBBChip(w, 'BB', METAL_LAYER)
chip.save(w, drawCopyDXF=True, dicingBorder=False, center=True)

w.setDefaultChip(chip)
w.populate()
w.save()

chip_dxf_path = w.path + w.fileName + '_' + chip.ID + '.dxf'
chip_gds_path = w.path + w.fileName + '_' + chip.ID + '.gds'
dxf_to_gds(chip_dxf_path, chip_gds_path,
           {name: gds_layer_number(w, name) for name in w.layerNames})
print('GDS exported -> %s' % chip_gds_path)
