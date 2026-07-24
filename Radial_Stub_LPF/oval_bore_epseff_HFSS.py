#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 11 Model A: bore-flattening parametric study - eps_eff/Zpi of a bare
70um strip vs. bore_h (stadium/oval bore minor axis), major axis bore_w
fixed at 6.985mm. Tests whether flattening the package bore (bringing
machined ground planes close above/below the chip) meaningfully changes
eps_eff, and produces the CSV this study's Model B/C length predictions
and the overall verdict depend on. See DESIGN_NOTES_snail_filter.md Sec. 5
for why this question matters (the round bore's lack of a parallel-plate
shunt-C term is what killed the L60 fan-ladder) and Sec. 9 for the
ports-only/no-sweep calibration methodology this file inherits from
extract_epseff.py (Rev 9) - same physics, same pyaedt approach, same
mode-verification discipline, adapted for a swept bore_h instead of a
swept strip width.

BORE CROSS-SECTION: a "stadium" (rectangle + 2 semicircular end caps), NOT
a true ellipse - closer to what a split-block mill produces (flat parallel
walls), per the handoff's own preference. Built as ONE closed, covered
polyline (2 native 180deg arcs + 2 straight lines) in the local X-Z plane
at each axial (Y) location needed, then swept along Y into a solid for the
bore itself (`sweep_along_vector`) - reuses the exact 2-arc+2-line native-
polyline technique already proven in this repo's pyEPR-side scripts
(filter_L60_HFSS.py's draw_fan_native/draw_bend_native), translated to
pyaedt's own `create_polyline(segment_type=[...])` API instead of a raw
win32com PLSegment array (first use of that specific pyaedt call in this
repo - if it misbehaves, the raw `hfss.modeler.oeditor.CreatePolyline`
escape hatch is the proven fallback, same array shape as the pyEPR-side
scripts already use).

**THE REFERENCE POINT (bore_h = bore_w = 6.985mm) DOES NOT USE THE STADIUM
CODE AT ALL** - at that value the stadium is mathematically a true circle
(flat_half_w = 0), but degenerate zero-length "flat" line segments in a
compound polyline are exactly the kind of edge case this codebase's own
DWL/Heidelberg-safety discipline is built to avoid (CLAUDE.md), and there's
no need to risk it: the reference point is built with the SAME plain
`create_cylinder` circular bore extract_epseff.py already uses and already
validated (eps_eff~5.68). This also directly serves the acceptance
checklist's own regression requirement using code already proven to pass
it, not new code exercised at a degenerate corner.

WALL-CLEARANCE SIMPLIFICATION: bore_w stays FIXED (6.985mm) through the
whole sweep - only bore_h shrinks. The strip sits centered, half-width
~35um, always deep inside the stadium's flat central region
(flat_half_w = (bore_w-bore_h)/2, minimum 2.99mm even at the smallest
swept bore_h=1.0mm) - so "straight up from the strip edge to the wall" is
simply Z = bore_h/2 (flat-topped) for every swept bore_h, no curved-cap
trigonometry needed anywhere in this file (unlike a real ellipse, where
the wall height would depend on X).

STANDING RULE (DESIGN_NOTES Sec. 9, Rev 9's own hard-won lesson): ports-
only quantities use N independent SINGLE-FREQUENCY setups, NEVER a swept
setup - a swept port-only solve was confirmed this session to evaluate a
frozen mode solution across the whole sweep, producing non-physical
eps_eff(f). This file creates 3 separate setups per bore_h (3/6/9GHz),
each solved and its own LastAdaptive mode data pulled independently.

RUN VIA THE SEPARATE PYEPR/PYAEDT ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe oval_bore_epseff_HFSS.py
"""
import csv
import math
import os

from pyaedt import Hfss

# ===============================================================================
# geometry parameters
# ===============================================================================

REFERENCE_BORE_H_UM = 6985.0  # true circle at the ORIGINAL diameter, special-cased (see module docstring)
BORE_H_TO_RUN_UM = [REFERENCE_BORE_H_UM, 4000.0, 3000.0, 2000.0, 1500.0, 1000.0]  # minor axis sweep

# Major axis for the STADIUM cases only - widened +0.1mm on the semi-major
# axis (i.e. +0.2mm on the full diameter: 6985 -> 7185) vs. the reference
# circle's own diameter. Needed because the chip's own corner
# (Y=+-CHIP_WIDTH_UM/2, Z=+-CHIP_THICKNESS_UM/2) pokes OUTSIDE the
# stadium's curved end cap at small bore_h if the major axis stays at
# 6985: confirmed by direct calculation (cap center at
# Y=(BORE_W_UM-bore_h)/2, radius=bore_h/2) - bore_h=1000 overshoots the
# cap boundary by 21um, bore_h=1500 by 0.4um (both real intersections, not
# noise). +0.2mm on the major axis gives >60um clearance at every swept
# bore_h. Deliberately NOT applied to the reference circle (still exactly
# REFERENCE_BORE_H_UM, unwidened) - that case already has 33um corner
# clearance at its own original diameter and is the already-validated
# Rev9-matching calibration point; widening it would change what
# "reference" means without need.
BORE_W_UM = REFERENCE_BORE_H_UM + 200.0

BORE_LENGTH_UM = 4000.0
CHIP_THICKNESS_UM = 500.0
CHIP_WIDTH_UM = 6900.0  # same corner-clearance-safe value as extract_epseff.py/filter_L60_package_HFSS.py

STRIP_WIDTH_UM = 70.0  # fixed - this study sweeps bore_h, not strip width (that was Rev 9's own study)

SAPPHIRE_EPS_XX = 9.4
SAPPHIRE_EPS_YY = 9.4
SAPPHIRE_EPS_ZZ = 11.6

SOLVE_FREQS_GHZ = [3.0, 6.0, 9.0]  # 3 independent single-frequency setups, never a sweep (see module docstring)
MODES = 5  # bumped from 3 - 3GHz found no sane candidate at all among the first 3 modes at the reference point

FIELD_PLOT_BORE_H_UM = [min(BORE_H_TO_RUN_UM), max(BORE_H_TO_RUN_UM)]  # mandatory visual check, scoped to 2 of 6


def um(val):
    return '%.6fum' % val


def gap_um(bore_h_um):
    """Metal-to-lid gap = bore_h/2 - chip_half_thickness, matching the
    handoff's own stated gap sequence (3.24/1.75/1.25/0.75/0.50/0.25mm)."""
    return bore_h_um / 2.0 - CHIP_THICKNESS_UM / 2.0


def _stadium_profile_points(bore_h_um):
    """The 6 vertices (pt0..pt5) of a stadium cross-section (major axis
    BORE_W_UM along local x, minor axis bore_h_um along local z), for use
    with create_polyline(segment_type=['Line','Arc','Line','Arc'],
    close_surface=True). See module docstring for the derivation - 2
    straight edges (length BORE_W_UM - bore_h_um) + 2 semicircular caps
    (radius bore_h_um/2)."""
    r = bore_h_um / 2.0
    flat_half_w = (BORE_W_UM - bore_h_um) / 2.0
    assert flat_half_w > 0, 'bore_h must be < BORE_W_UM for the stadium code path (reference point is special-cased)'
    return [
        (-flat_half_w, r),              # pt0: top-left
        (flat_half_w, r),               # pt1: top-right (Line pt0->pt1)
        (flat_half_w + r, 0.0),         # pt2: rightmost (Arc mid pt1->pt2->pt3)
        (flat_half_w, -r),              # pt3: bottom-right
        (-flat_half_w, -r),             # pt4: bottom-left (Line pt3->pt4)
        (-flat_half_w - r, 0.0),        # pt5: leftmost (Arc mid pt4->pt5->pt0, closing)
    ]


def build_bore(hfss, bore_h_um, name='BoreVacuum'):
    """Builds the vacuum bore as a solid - a plain circle/cylinder at the
    reference point, a stadium (native polyline + sweep) otherwise. Returns
    the bore's NAME (a plain string), not the Object3d reference - matches
    extract_epseff.py's own convention of always re-looking-up objects by
    their fixed name string after a boolean op, never trusting a cached
    Object3d reference across one (confirmed empirically this session:
    `hfss.modeler[str(obj)]` returned None after `subtract()` even though
    the object's NAME was unchanged - the cached reference itself doesn't
    survive the boolean op cleanly, the name-based lookup does)."""
    if bore_h_um == REFERENCE_BORE_H_UM:
        radius_um = REFERENCE_BORE_H_UM / 2.0  # NOT BORE_W_UM - the reference circle stays at its own original diameter, unwidened
        hfss.modeler.create_cylinder(
            orientation='X', origin=[0, 0, 0], radius=um(radius_um), height=um(BORE_LENGTH_UM),
            name=name, material='vacuum',
        )
        print('  Reference bore: plain circle, radius=%.1fum (bore_h==REFERENCE_BORE_H_UM, stadium code path skipped)'
              % radius_um)
        return name

    pts_local = _stadium_profile_points(bore_h_um)
    points_3d = [[um(0.0), um(x), um(z)] for x, z in pts_local]  # cross-section at X=0 (axial start)
    profile = hfss.modeler.create_polyline(
        points=points_3d, segment_type=['Line', 'Arc', 'Line', 'Arc'],
        cover_surface=True, close_surface=True, name=name,
    )
    profile.material_name = 'vacuum'
    hfss.modeler.sweep_along_vector(assignment=name, sweep_vector=[um(BORE_LENGTH_UM), 0, 0])
    print('  Stadium bore: bore_w=%.1fum bore_h=%.1fum (flat_half_w=%.2fum, r=%.2fum)'
          % (BORE_W_UM, bore_h_um, (BORE_W_UM - bore_h_um) / 2.0, bore_h_um / 2.0))
    return name


def build_port_sheet(hfss, bore_h_um, x_pos_um, name):
    """Same profile-building code as build_bore(), but flat (not swept) -
    used for the wave-port sheets at each axial end, matching
    extract_epseff.py's own independent-sheet-not-solid's-own-face
    convention (avoids any post-boolean partial-face ambiguity)."""
    if bore_h_um == REFERENCE_BORE_H_UM:
        radius_um = REFERENCE_BORE_H_UM / 2.0  # NOT BORE_W_UM - see build_bore()'s own comment
        return hfss.modeler.create_circle(
            orientation='YZ', origin=[x_pos_um, 0, 0], radius=um(radius_um), name=name,
        )
    pts_local = _stadium_profile_points(bore_h_um)
    points_3d = [[um(x_pos_um), um(x), um(z)] for x, z in pts_local]
    return hfss.modeler.create_polyline(
        points=points_3d, segment_type=['Line', 'Arc', 'Line', 'Arc'],
        cover_surface=True, close_surface=True, name=name,
    )


def render_field_plot_manual(hfss, setup_sweep_name, export_path, quantity='Mag_E', assignment=None,
                              intrinsics=None):
    """Manual replacement for hfss.post.plot_field(), which fails
    unconditionally in this environment ("<format> file format is not
    supported for this plot", for BOTH 'case' and 'fldplt') - confirmed
    empirically that the failure is isolated to plot_field_from_fieldplot()'s
    own internal PyVista-rendering step, NOT the underlying field export:
    create_fieldplot_surface() and export_field_plot() both work fine
    called directly, producing a real, loadable .case file with genuine
    per-point Mag_E data (confirmed: N Arrays=1, 'Mag_E' in point_data).
    This function does the same two proven-working steps, then loads the
    .case file with PyVista directly (bypassing pyaedt's own broken
    wrapper entirely) and renders+saves the image itself."""
    import pyvista as pv

    if assignment is None:
        assignment = ['PortSheet1']
    if intrinsics is None:
        # 'Setup_6GHz : LastAdaptive' -> '6GHz'
        intrinsics = {'Freq': setup_sweep_name.split(':')[0].strip().replace('Setup_', '')}

    plotf = hfss.post.create_fieldplot_surface(assignment, quantity, setup_sweep_name, intrinsics)
    if not plotf:
        raise RuntimeError('create_fieldplot_surface returned False/None')
    case_path = hfss.post.export_field_plot(plotf.name, hfss.working_directory, plotf.name, file_format='case')
    if not case_path:
        raise RuntimeError('export_field_plot returned False/None')

    pv.OFF_SCREEN = True
    reader = pv.get_reader(str(case_path))
    mesh = reader.read()
    block = mesh[0]

    plotter = pv.Plotter(off_screen=True, window_size=[1400, 1000])
    plotter.add_mesh(block, scalars=quantity, cmap='inferno', show_edges=False,
                      scalar_bar_args={'title': quantity})
    plotter.view_yz()
    plotter.camera.parallel_projection = True
    plotter.screenshot(export_path)


def run_extraction(bore_h_um):
    gap = gap_um(bore_h_um)
    project_name = 'oval_epseff_h%d' % round(bore_h_um)
    design_name = 'eps_eff_extraction'

    print('=' * 70)
    print('BORE_H = %.1fum (gap=%.2fum) -> project=%r' % (bore_h_um, gap, project_name))
    print('=' * 70)

    hfss = Hfss(
        project=os.path.join(os.getcwd(), project_name), design=design_name,
        solution_type='DrivenModal', new_desktop=False, non_graphical=False,
    )
    hfss.modeler.model_units = 'um'

    if hfss.modeler.object_list:
        hfss.modeler.delete(hfss.modeler.object_list)
    for setup_name in list(hfss.setup_names):
        hfss.delete_setup(setup_name)

    mat_name = 'sapphire_aniso'
    if mat_name in hfss.materials.material_keys:
        sapphire = hfss.materials[mat_name]
    else:
        sapphire = hfss.materials.add_material(mat_name)
    sapphire.permittivity.value = [SAPPHIRE_EPS_XX, SAPPHIRE_EPS_YY, SAPPHIRE_EPS_ZZ]

    bore = build_bore(hfss, bore_h_um)

    hfss.modeler.create_box(
        origin=[0, -CHIP_WIDTH_UM / 2.0, -CHIP_THICKNESS_UM / 2.0],
        sizes=[BORE_LENGTH_UM, CHIP_WIDTH_UM, CHIP_THICKNESS_UM],
        name='Substrate', material=mat_name,
    )
    hfss.modeler.subtract(blank_list=[bore], tool_list=['Substrate'], keep_originals=True)
    # pyaedt's own object cache doesn't auto-refresh after a raw boolean op
    # (confirmed empirically: hfss.modeler[bore] returned None post-subtract
    # even though the object's own NAME was unchanged) - refresh_all_ids()
    # resyncs it with AEDT's actual state before the name-based lookup below.
    hfss.modeler.refresh_all_ids()

    bore_obj = hfss.modeler[bore]

    def _is_wall_face(f):
        """True wall face (curved cap, or - stadium only - flat top/bottom
        at exactly Z=+-bore_h/2), NOT one of the substrate notch's own
        internal flat faces (at exactly Z=+-CHIP_THICKNESS_UM/2, always a
        different value from +-bore_h/2 for every bore_h in this sweep).
        A first version assigned PerfectE to "every face except the 2 end
        caps", which silently included the notch's own faces too -
        confirmed empirically as the cause of a 13-minute solve failure
        (an internally-shorted, ill-posed structure) at the reference
        point. Curved faces are never planar, so `not f.is_planar` alone
        already correctly isolates them (the notch, a rectangular box cut,
        never introduces a curved face) - the Z-match check only matters
        for the stadium's own flat top/bottom walls."""
        if not f.is_planar:
            return True
        return abs(abs(f.center[2]) - bore_h_um / 2.0) < 1.0

    end_cap_faces = [f.id for f in bore_obj.faces if abs(f.center[0]) < 1.0 or abs(f.center[0] - BORE_LENGTH_UM) < 1.0]
    wall_faces = [f.id for f in bore_obj.faces if f.id not in end_cap_faces and _is_wall_face(f)]
    hfss.assign_perfect_e(assignment=wall_faces, name='Package_Walls')
    print('  Bore faces: %d wall (PerfectE), %d end-cap (reserved for ports)'
          % (len(wall_faces), len(end_cap_faces)))

    strip_z = CHIP_THICKNESS_UM / 2.0
    strip = hfss.modeler.create_rectangle(
        orientation='Z', origin=[0, -STRIP_WIDTH_UM / 2.0, strip_z], sizes=[BORE_LENGTH_UM, STRIP_WIDTH_UM],
        name='Strip',
    )
    hfss.assign_perfect_e(assignment=[strip.name], name='Strip_PerfectE')

    # Integration line: strip edge straight up to the wall. The flat-
    # topped Z=bore_h/2 simplification (module docstring) applies ONLY to
    # the stadium cases - the REFERENCE point is a TRUE CIRCLE (no flat
    # region at all), where the wall height genuinely varies with Y even
    # for small Y. Using the flat-topped value there put the integration
    # line's endpoint ~0.175um outside the port disk's true boundary
    # (sqrt(r^2-y^2) ~ 3492.32um vs the flat r=3492.5um at y=35um) -
    # confirmed empirically as the cause of a same-class-as-Rev10
    # "must lie on the port" solve failure (message unavailable this time -
    # GetMessages/gRPC + win32com both failed to return it live - but the
    # geometry math confirms it directly).
    strip_edge_y = STRIP_WIDTH_UM / 2.0
    if bore_h_um == REFERENCE_BORE_H_UM:
        radius_um = REFERENCE_BORE_H_UM / 2.0  # NOT BORE_W_UM - see build_bore()'s own comment
        wall_z = math.sqrt(radius_um ** 2 - strip_edge_y ** 2)
    else:
        wall_z = bore_h_um / 2.0

    port_names = []
    for i, x_port in enumerate([0.0, BORE_LENGTH_UM], start=1):
        sheet = build_port_sheet(hfss, bore_h_um, x_port, name='PortSheet%d' % i)
        start_pt = [um(x_port), um(strip_edge_y), um(strip_z)]
        end_pt = [um(x_port), um(strip_edge_y), um(wall_z)]
        pname = 'P%d' % i
        hfss.wave_port(
            assignment=sheet.name, modes=MODES, integration_line=[start_pt, end_pt],
            characteristic_impedance='Zpi', renormalize=False, name=pname,
        )
        port_names.append(pname)
        print('  wave port %s @ X=%.1fum (wall Z=%.2fum)' % (pname, x_port, wall_z))

    for f_ghz in SOLVE_FREQS_GHZ:
        hfss.create_setup(name='Setup_%dGHz' % round(f_ghz), Frequency='%.1fGHz' % f_ghz,
                           MaximumPasses=8, MinimumConvergedPasses=2)

    hfss.save_project()

    result = dict(bore_h_um=bore_h_um, gap_um=gap, project_name=project_name, rows=[])

    k0_of = lambda f_ghz: 2 * math.pi * (f_ghz * 1e9) / 2.998e8

    # Process 6GHz FIRST (matches extract_epseff.py's own calibration
    # frequency) to establish a per-bore_h eps_eff "anchor" - the OTHER
    # frequencies then pick the sane candidate CLOSEST to that anchor,
    # not just the highest-eps_eff one. Confirmed empirically this
    # matters: at the reference point, "highest among sane" correctly
    # picked 6GHz's true mode (5.56, the lowest of 2 sane candidates) but
    # OVERSHOT at 9GHz (picked 7.19 over two much-closer-to-5.68
    # candidates at 5.65/5.66) - a fixed global target (e.g. 5.68) would
    # be wrong for non-reference bore_h values where eps_eff is EXPECTED
    # to shift (that's the whole point of this study), so the anchor is
    # taken from THIS bore_h's own 6GHz result, not a hardcoded constant.
    freqs_ordered = sorted(SOLVE_FREQS_GHZ, key=lambda f: (f != 6.0, f))
    anchor_eps_eff = [None]

    for f_ghz in freqs_ordered:
        setup_name = 'Setup_%dGHz' % round(f_ghz)
        print('Solving %s...' % setup_name)
        analyze_ok = hfss.analyze_setup(setup_name)
        if not analyze_ok:
            print('  SOLVE FAILED for %s - skipping this frequency.' % setup_name)
            try:
                msgs = hfss.odesktop.GetMessages(hfss.project_name, hfss.design_name, 0)
                for m in msgs:
                    print('   ', m)
            except Exception as e:
                print('  could not pull messages: %r' % e)
            continue

        k0 = k0_of(f_ghz)
        modes_found = {}
        for port_name in port_names:
            for mode_idx in range(1, MODES + 1):
                lbl = '%s:%d' % (port_name, mode_idx)
                try:
                    # Explicit setup_sweep_name is required with 3
                    # coexisting setups - without it, get_solution_data()
                    # defaults ambiguously (confirmed empirically: it
                    # silently queried whichever setup wasn't-yet-solved
                    # for 2 of 3 frequencies, only working for the LAST
                    # one solved - "Solution Data failed to load" for
                    # Setup_3GHz/Setup_6GHz, fine for Setup_9GHz).
                    data = hfss.post.get_solution_data(
                        expressions=['Gamma(%s)' % lbl, 'Zo(%s)' % lbl],
                        setup_sweep_name='%s : LastAdaptive' % setup_name,
                    )
                    _, gamma_re = data.get_expression_data('Gamma(%s)' % lbl)
                    beta = gamma_re[0]
                    eps_eff = (beta / k0) ** 2
                    real_d, imag_d = data.full_matrix_real_imag
                    zo_re = real_d['Zo(%s)' % lbl][0][1]
                    zo_im = imag_d['Zo(%s)' % lbl][0][1]
                    zo_mag = math.hypot(zo_re, zo_im)
                    sane = 1.0 <= eps_eff <= SAPPHIRE_EPS_ZZ
                    modes_found[lbl] = dict(beta=beta, eps_eff=eps_eff, zo_mag=zo_mag, sane=sane)
                except Exception as e:
                    print('  %s FAILED: %r' % (lbl, e))

        print('  %s: all mode candidates:' % setup_name)
        for lbl, r in modes_found.items():
            print('    %-6s eps_eff=%8.4f |Zpi|=%8.2f ohm  sane=%s' % (lbl, r['eps_eff'], r['zo_mag'], r['sane']))

        # Mode selection: for the FIRST frequency processed (6GHz), no
        # anchor exists yet - fall back to "highest eps_eff among sane"
        # (a bulk/vacuum-adjacent spurious mode has LOW eps_eff, close to
        # 1 - the true substrate-dominated strip mode should be the
        # highest of the sane candidates at a frequency with no other
        # info available). Once 6GHz has set an anchor, later frequencies
        # instead pick the sane candidate CLOSEST to that anchor - a
        # physical mode shouldn't jump far in eps_eff between adjacent
        # solve frequencies (confirmed this matters: "highest among sane"
        # alone picked the wrong candidate at 9GHz, 7.19 over two
        # candidates within 0.1 of the 6GHz anchor).
        sane_modes = [lbl for lbl, r in modes_found.items() if r['sane']]
        if sane_modes:
            if anchor_eps_eff[0] is None:
                best = max(sane_modes, key=lambda lbl: modes_found[lbl]['eps_eff'])
                reason = 'highest eps_eff among sane candidates - no anchor yet'
            else:
                best = min(sane_modes, key=lambda lbl: abs(modes_found[lbl]['eps_eff'] - anchor_eps_eff[0]))
                reason = 'closest to anchor eps_eff=%.4f' % anchor_eps_eff[0]
            r = modes_found[best]
            anchor_eps_eff[0] = r['eps_eff'] if anchor_eps_eff[0] is None else anchor_eps_eff[0]
            print('  %s: SELECTED mode %s eps_eff=%.4f |Zpi|=%.4f ohm (%s)'
                  % (setup_name, best, r['eps_eff'], r['zo_mag'], reason))
            result['rows'].append(dict(freq_ghz=f_ghz, eps_eff=r['eps_eff'], zpi_ohm=r['zo_mag']))
        else:
            print('  %s: NO physically sane mode found.' % setup_name)

    if bore_h_um in FIELD_PLOT_BORE_H_UM:
        # Render BOTH 6GHz and 9GHz here (not just 6GHz) - the mode
        # selection at 6GHz and 9GHz can disagree substantially at
        # flattened bore_h (confirmed: 6GHz picks a spurious wall-hugging
        # mode there), so both need visual comparison. Done from THIS
        # live, already-solved hfss connection deliberately - a FRESH
        # reconnection to the saved project hit a real async-loading race
        # (setup_names/object_list stayed empty even after explicit
        # polling, "Parsing...File correctly loaded" only appears AFTER
        # the failing call) that a live in-process connection doesn't hit.
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HFSS')
        os.makedirs(out_dir, exist_ok=True)
        for plot_f_ghz in (6.0, 9.0):
            try:
                export_path = os.path.join(
                    out_dir, 'oval_epseff_h%d_%dGHz_mode_field.png' % (round(bore_h_um), round(plot_f_ghz)))
                render_field_plot_manual(hfss, 'Setup_%dGHz : LastAdaptive' % round(plot_f_ghz), export_path,
                                          intrinsics={'Freq': '%dGHz' % round(plot_f_ghz)})
                print('  field plot saved -> %s' % export_path)
            except Exception as e:
                print('  field plot @ %.0fGHz FAILED (non-fatal): %r' % (plot_f_ghz, e))

    hfss.release_desktop(close_projects=False, close_desktop=False)
    return result


def _append_csv(rows, csv_path):
    file_exists = os.path.exists(csv_path)
    with open(csv_path, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['bore_h_um', 'gap_um', 'freq_ghz', 'eps_eff', 'zpi_ohm'])
        for row in rows:
            writer.writerow([row['bore_h_um'], row['gap_um'], row['freq_ghz'], row['eps_eff'], row['zpi_ohm']])


def _already_done(bore_h_um, csv_path):
    """Incremental execution (per the plan) - skip a bore_h already fully
    present in the CSV (all 3 frequencies) so a re-run only does the
    remaining work."""
    if not os.path.exists(csv_path):
        return False
    done_freqs = set()
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if abs(float(row['bore_h_um']) - bore_h_um) < 1.0:
                done_freqs.add(round(float(row['freq_ghz'])))
    return done_freqs >= set(round(f) for f in SOLVE_FREQS_GHZ)


if __name__ == '__main__':
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HFSS')
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, 'oval_epseff_raw.csv')

    for bore_h_um in BORE_H_TO_RUN_UM:
        if _already_done(bore_h_um, csv_path):
            print('bore_h=%.1fum already complete in %s - skipping.' % (bore_h_um, csv_path))
            continue
        res = run_extraction(bore_h_um)
        for row in res['rows']:
            row['bore_h_um'] = bore_h_um
            row['gap_um'] = res['gap_um']
        _append_csv(res['rows'], csv_path)
        print('Appended %d row(s) to %s' % (len(res['rows']), csv_path))

    print()
    print('=' * 70)
    print('DONE. Raw data -> %s' % csv_path)
    print('=' * 70)
