#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 9 EXPERIMENT: scripted HFSS eps_eff/Z0 extraction for a strip in the
real 7.0mm package bore - the calibration number that gates filter_BB.py's
EPS_EFF=5.5 placeholder (see that file's own module docstring, "GATING
ITEM", and notebooks/BB_design_notes.md sec 6).

Physics (see the handoff for the full derivation): a wave port on the
FULL bore cross-section makes HFSS solve the 2D eigenmodes of that loaded
cross-section directly and report each mode's complex propagation
constant Gamma = alpha + j*beta and characteristic impedance - no 3D
field solve or S-parameters needed in principle (a "solve ports only"
setup makes this fast; this pass does a normal driven-modal solve
instead - see SCOPE note below - which still computes and reports the
same per-mode Gamma/Zo, just via a full 3D solve instead of the cheaper
port-only shortcut).

SCOPE OF THIS PASS (narrowed live, per Eddie): geometry + a real solve for
BOTH strip widths (W_STRIP_UM=70 and 125 - set via the WIDTHS_TO_RUN list
below, one project per width), modes=3 (needed for real mode verification -
see sec below), an adaptive solve at SOLVE_FREQ_GHZ (6GHz) for mode
verification PLUS a discrete sweep (SWEEP_START/STOP/STEP_GHZ, 1-12GHz in
1GHz steps, matching the handoff's own spec) for the dispersion check and
CSV export - NOT yet the "Solve Ports Only" setup option (deferred, a
normal solve still populates the same per-mode Gamma/Zo, just via a full
3D solve at every sweep point instead of the cheaper port-only shortcut).

Real bore diameter used: 7000um, NOT the handoff's stated 6985um - matches
filter_L60_package_HFSS.py's own already-Eddie-confirmed revision (6985
was an earlier, superseded number - see that file's own module
docstring). Chip width is 6900um, NOT literally equal to the bore diameter
despite the handoff's own "make chip width = bore diameter" simplification
instruction - see CHIP_WIDTH_UM's own comment for why that instruction is
geometrically invalid as stated.

MODE VERIFICATION (mandatory per the handoff): the empty bore is large
relative to the loaded region, so it has multiple eigenmodes near 6GHz -
most are the empty bore's own bulk modes below their ~25GHz cutoff (real
Gamma, zero beta - non-physical eps_eff), competing with the strip's own
bound quasi-TEM mode. modes=3 on both ports, eps_eff computed from EACH
mode's Gamma, keeping only the physically sane one(s) (eps_eff in
[1, SAPPHIRE_EPS_ZZ]). Confirmed empirically this session: mode ORDERING
is NOT consistent between the two otherwise-symmetric ports (P2's own
"mode 1" matched P1's "mode 2" instead) - both ports' first 3 modes are
checked, not just P1's. eps_eff is computed HERE directly from Gamma
(eps_eff = (beta/k0)^2, beta = Gamma's REAL part in this AEDT version -
confirmed empirically, NOT the imaginary part as the alpha+j*beta
convention would suggest), NOT from AEDT's own 'Epsilon()' report
quantity - that quantity returned exactly 0.0 for every mode tested this
session regardless of physical validity, so it isn't trustworthy here.
A field plot of the winning mode's E-field on the port cross-section
(see plot_epseff_mode.py, run separately after this script) is the
additional mandatory visual check - confirmed for the w70 case: field
concentrates tightly at the strip and decays toward the bore wall, the
expected bound-mode signature.

IMPEDANCE (Zpi/Zpv/Zvi): this AEDT version's Modal Solution Data report
system does NOT expose Zpi()/Zpv()/Zvi() as separately-addressable report
quantities at all (confirmed empirically - only 'Zo(P1:N)' exists, under
the "Port Zo" quantities category). With the default renormalize=True
(ports renormalized to a fixed 50ohm reference), Zo(P1:N) reports exactly
50.0 for EVERY mode regardless of the mode's own real impedance - it's
echoing the renormalization TARGET, not a computed value. Fix:
renormalize=False on both ports, so Zo(P1:N) reports the mode's true
natural impedance in the convention chosen at port creation
(characteristic_impedance='Zpi', matching the handoff's own stated
preference for strip-like lines - "Zpi is the convention for strip-like
lines"). Getting Zpv/Zvi as SEPARATE, simultaneous numbers for the same
physical mode would need re-defining the port's own characteristic_impedance
per case and re-solving - not done this pass (Zpi alone is what actually
gates the filter_BB.py stub design; Zpv/Zvi were framed by the handoff as
a supplementary quasi-TEM-ness diagnostic, not a hard requirement).

Uses pyaedt (NOT this repo's established raw-win32com-via-pyEPR pattern -
see filter_L60_HFSS.py/filter_L60_package_HFSS.py) - first use of pyaedt
in this repo. Chosen because this task's genuinely NEW pieces (anisotropic
material, multi-mode wave ports, port-eigenmode post-processing) have
clear first-class pyaedt support. Connection handling follows this repo's
own hard-won conventions where they apply. NOTE: pyaedt's own
new_desktop=False project-attachment logic proved unreliable this session
(repeatedly spawned duplicate/new AEDT processes instead of attaching to
an existing one, matching - and extending to pyaedt - the duplicate-AEDT-
project lesson CLAUDE.md already documents for the raw-COM scripts) -
if this script hangs or a "file in use" dialog appears, check for and
manually close duplicate same-named AEDT processes/projects before
re-running.

RUN VIA THE SEPARATE PYEPR/PYAEDT ENVIRONMENT, NOT THIS REPO'S OWN .venv:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe extract_epseff.py
"""
import math
import os

from pyaedt import Hfss

# ===============================================================================
# geometry parameters (all at the top, per the handoff's own deliverable
# requirement #4 - "geometry parameters at the top of the script")
# ===============================================================================

WIDTHS_TO_RUN = [70.0, 125.0]  # um - both handoff-specified strip widths

BORE_DIAMETER_UM = 7000.0    # real package bore (see module docstring - not
                              # the handoff's stale 6985um)
BORE_LENGTH_UM = 4000.0      # axial length of the modeled bore section
CHIP_THICKNESS_UM = 500.0    # sapphire thickness

# NOT literally BORE_DIAMETER_UM, despite the handoff's own "make the chip
# width = bore diameter" simplification instruction - that combination is
# geometrically invalid: a chip of nonzero thickness whose width exactly
# equals the bore diameter has its corners sticking OUTSIDE the circular
# cross-section (corner distance from axis = sqrt((W/2)^2+(T/2)^2) >
# W/2 = bore_radius whenever T>0 - confirmed by the numbers here:
# sqrt(3500^2+250^2)=3508.9um > 3500um bore radius, ~9um over). Uses
# 6900um instead - the SAME already-validated real chip width from
# filter_L60_package_HFSS.py's own corner-clearance check (40.7um
# clearance in a 7000um bore) - still satisfies the handoff's own stated
# reasoning for the simplification ("edge details are irrelevant here,
# fields concentrate near the strip") just as well as an exact-diameter
# width would, without the invalid geometry.
CHIP_WIDTH_UM = 6900.0

# Anisotropic c-plane sapphire: (9.4, 9.4, 11.6), 11.6 on the axis NORMAL to
# the chip face. Chip face normal is Z (thickness axis) in this model's
# axis=X-along-strip convention - see module docstring.
SAPPHIRE_EPS_XX = 9.4
SAPPHIRE_EPS_YY = 9.4
SAPPHIRE_EPS_ZZ = 11.6

SOLVE_FREQ_GHZ = 6.0
MODES = 3  # see module docstring's MODE VERIFICATION section

# Discrete sweep for the dispersion check (handoff's own "1-12 GHz in 1 GHz
# steps"). Mode verification (which mode index is the real strip mode)
# happens at SOLVE_FREQ_GHZ only, on the adaptive LastAdaptive solution -
# the winning mode's index is then TRUSTED across the sweep, not re-
# verified at every point (the handoff's own "mode swapping is a known
# HFSS behavior" caveat means this trust isn't absolute - the sweep
# results include a per-point sanity check, eps_eff in [1, eps_zz], as a
# cheap guard against a silent mode swap at some other frequency; a full
# per-frequency field-plot re-verification is NOT done this pass).
SWEEP_START_GHZ = 1.0
SWEEP_STOP_GHZ = 12.0
SWEEP_STEP_GHZ = 1.0


def um(val):
    return '%.6fum' % val


def run_extraction(width_um):
    """Build + solve + extract eps_eff/Zo for one strip width - a fresh
    project per width (PROJECT_NAME depends on width_um), so the two
    cases never collide."""
    project_name = 'extract_epseff_w%d' % round(width_um)
    design_name = 'eps_eff_extraction'

    print('=' * 70)
    print('WIDTH = %.1fum -> project=%r' % (width_um, project_name))
    print('=' * 70)

    hfss = Hfss(
        project=os.path.join(os.getcwd(), project_name),
        design=design_name,
        solution_type='DrivenModal',
        new_desktop=False,
        non_graphical=False,
    )
    hfss.modeler.model_units = 'um'

    # Re-runnable from scratch (deliverable requirement: "re-runs clean
    # from scratch, same numbers") - if this design already has geometry
    # (e.g. a prior failed attempt), delete it and start over.
    if hfss.modeler.object_list:
        print('Existing geometry found (%d objects) - clearing for a clean rebuild.'
              % len(hfss.modeler.object_list))
        hfss.modeler.delete(hfss.modeler.object_list)
    for setup_name in list(hfss.setup_names):
        hfss.delete_setup(setup_name)

    # --- anisotropic sapphire material ---
    mat_name = 'sapphire_aniso'
    if mat_name in hfss.materials.material_keys:
        sapphire = hfss.materials[mat_name]
    else:
        sapphire = hfss.materials.add_material(mat_name)
    sapphire.permittivity.value = [SAPPHIRE_EPS_XX, SAPPHIRE_EPS_YY, SAPPHIRE_EPS_ZZ]
    print('sapphire_aniso permittivity set to %r' % (sapphire.permittivity.value,))

    # --- bore cylinder (vacuum interior) - axis = X (per the handoff) ---
    bore_radius_um = BORE_DIAMETER_UM / 2.0
    hfss.modeler.create_cylinder(
        orientation='X', origin=[0, 0, 0], radius=um(bore_radius_um), height=um(BORE_LENGTH_UM),
        name='BoreVacuum', material='vacuum',
    )
    print('Bore cylinder created: radius=%.1fum length=%.1fum axis=X' % (bore_radius_um, BORE_LENGTH_UM))

    # --- chip substrate, mid-thickness on the bore axis ---
    hfss.modeler.create_box(
        origin=[0, -CHIP_WIDTH_UM / 2.0, -CHIP_THICKNESS_UM / 2.0],
        sizes=[BORE_LENGTH_UM, CHIP_WIDTH_UM, CHIP_THICKNESS_UM],
        name='Substrate', material=mat_name,
    )
    print('Substrate box created: %.1f(X) x %.1f(Y) x %.1f(Z) um, material=%s'
          % (BORE_LENGTH_UM, CHIP_WIDTH_UM, CHIP_THICKNESS_UM, mat_name))

    # BoreVacuum and Substrate were originally left as two independent
    # solids occupying the SAME space - AEDT validation correctly
    # rejected this. Fix: subtract the substrate's volume OUT of the
    # vacuum cylinder first (keep_originals=True keeps Substrate as its
    # own solid with its own material after the cut).
    hfss.modeler.subtract(blank_list=['BoreVacuum'], tool_list=['Substrate'], keep_originals=True)
    print('Subtracted Substrate from BoreVacuum (keep_originals=True)')

    bore = hfss.modeler['BoreVacuum']
    curved_faces = [f for f in bore.faces if not f.is_planar]
    assert len(curved_faces) == 1, 'expected 1 curved face on BoreVacuum post-subtract, got %d' % len(curved_faces)
    hfss.assign_perfect_e(assignment=[curved_faces[0].id], name='Package_Walls')
    print('PerfectE assigned to bore curved wall only (face id=%d)' % curved_faces[0].id)

    # --- strip (PerfectE sheet), full model length, chip top face ---
    strip_z = CHIP_THICKNESS_UM / 2.0
    strip = hfss.modeler.create_rectangle(
        orientation='Z', origin=[0, -width_um / 2.0, strip_z], sizes=[BORE_LENGTH_UM, width_um],
        name='Strip_W%d' % round(width_um),
    )
    hfss.assign_perfect_e(assignment=[strip.name], name='Strip_PerfectE')
    print('Strip created: width=%.1fum, full length=%.1fum, Z=%.1fum, PerfectE assigned'
          % (width_um, BORE_LENGTH_UM, strip_z))

    # --- wave ports - independent circular SHEET objects at each end
    # (not the solids' own end faces, which are only PARTIAL disks after
    # the subtract) - integration line from the strip edge midpoint
    # vertically (+Z) to the nearest point on the bore wall.
    # renormalize=False so Zo(P:N) reports the mode's TRUE natural
    # impedance (see module docstring's IMPEDANCE section) rather than
    # echoing a fixed 50ohm renormalization target.
    def bore_wall_z_at_y(y_um):
        return math.sqrt(bore_radius_um ** 2 - y_um ** 2)

    strip_edge_y = width_um / 2.0
    wall_z = bore_wall_z_at_y(strip_edge_y)
    print('Integration line: Y=%.3fum, Z %.3f -> %.3f (strip edge -> bore wall, vertical)'
          % (strip_edge_y, strip_z, wall_z))

    for i, x_port in enumerate([0.0, BORE_LENGTH_UM], start=1):
        sheet = hfss.modeler.create_circle(
            orientation='YZ', origin=[x_port, 0, 0], radius=um(bore_radius_um), name='PortSheet%d' % i,
        )
        start_pt = [um(x_port), um(strip_edge_y), um(strip_z)]
        end_pt = [um(x_port), um(strip_edge_y), um(wall_z)]
        hfss.wave_port(
            assignment=sheet.name, modes=MODES, integration_line=[start_pt, end_pt],
            characteristic_impedance='Zpi', renormalize=False, name='P%d' % i,
        )
        print('  wave port P%d assigned on independent port sheet at X=%.1fum' % (i, x_port))

    # --- setup - adaptive mesh at SOLVE_FREQ_GHZ, plus a discrete sweep
    # covering the handoff's own 1-12GHz range (SWEEP_START/STOP/STEP_GHZ)
    # for the dispersion check. ---
    setup = hfss.create_setup(name='EpsEffSetup', Frequency='%.1fGHz' % SOLVE_FREQ_GHZ,
                               MaximumPasses=8, MinimumConvergedPasses=2)
    print('Setup created: %s @ %.1fGHz' % (setup.name, SOLVE_FREQ_GHZ))

    sweep = hfss.create_linear_step_sweep(
        setup=setup.name, unit='GHz', start_frequency=SWEEP_START_GHZ, stop_frequency=SWEEP_STOP_GHZ,
        step_size=SWEEP_STEP_GHZ, name='FreqSweep', save_fields=True, sweep_type='Discrete',
    )
    print('Discrete sweep created: %s, %.1f-%.1fGHz step %.1fGHz'
          % (sweep.name, SWEEP_START_GHZ, SWEEP_STOP_GHZ, SWEEP_STEP_GHZ))

    hfss.save_project()
    print('Project saved.')

    print('GEOMETRY + SETUP COMPLETE. Running analyze()...')
    analyze_ok = hfss.analyze_setup(setup.name)
    print('analyze_setup() returned: %r' % analyze_ok)

    result = dict(width_um=width_um, project_name=project_name, solved=analyze_ok, modes={})

    if not analyze_ok:
        print('SOLVE DID NOT SUCCEED - stopping before post-processing.')
        # Pull the real error via THIS SAME already-connected hfss object -
        # a fresh connection for diagnosis is unreliable (duplicate-project
        # instability confirmed repeatedly this session with pyaedt's own
        # new_desktop=False attachment logic), but this object is already
        # attached to the exact project/design that just failed.
        try:
            msgs = hfss.odesktop.GetMessages(hfss.project_name, hfss.design_name, 0)
            print('Real AEDT error messages:')
            for m in msgs:
                print('  ', m)
        except Exception as e:
            print('Could not pull messages: %r' % e)
        print('Project left open/saved at %s for manual inspection.' % project_name)
        result['recommended'] = None
        hfss.release_desktop(close_projects=False, close_desktop=False)
        return result

    print('SOLVE SUCCEEDED. Pulling Gamma/Zo for each of the %d modes on BOTH ports...' % MODES)
    k0 = 2 * math.pi * (SOLVE_FREQ_GHZ * 1e9) / 2.998e8  # rad/m

    print('%-8s %14s %10s %12s   %s' % ('mode', 'Re(Gamma)=beta', 'eps_eff', 'Zo(ohm)', 'sane?'))
    for port_name in ['P1', 'P2']:
        for mode_idx in range(1, MODES + 1):
            lbl = '%s:%d' % (port_name, mode_idx)
            try:
                data = hfss.post.get_solution_data(expressions=['Gamma(%s)' % lbl, 'Zo(%s)' % lbl])
                _, gamma_re = data.get_expression_data('Gamma(%s)' % lbl)
                beta = gamma_re[0]
                eps_eff = (beta / k0) ** 2
                # Zo(P:N) is COMPLEX (confirmed empirically: get_expression_data()
                # only surfaces one component - the SMALL one here, ~0.4ohm,
                # looked non-physical until full_matrix_real_imag() revealed a
                # much larger second component, ~70ohm, in a physically sane
                # strip-line range). Same real/imaginary mislabeling pattern
                # already found for Gamma - report the magnitude, which is
                # robust regardless of exactly which component AEDT calls
                # "real" vs "imaginary" here.
                real_d, imag_d = data.full_matrix_real_imag
                zo_re = real_d['Zo(%s)' % lbl][0][1]
                zo_im = imag_d['Zo(%s)' % lbl][0][1]
                zo_mag = math.hypot(zo_re, zo_im)
                sane = 1.0 <= eps_eff <= SAPPHIRE_EPS_ZZ
                print('%-8s %14.4f %10.4f %12.4f   %s' % (lbl, beta, eps_eff, zo_mag, 'YES' if sane else 'no'))
                result['modes'][lbl] = dict(beta=beta, eps_eff=eps_eff, zo_re=zo_re, zo_im=zo_im,
                                             zo_mag=zo_mag, sane=sane)
            except Exception as e:
                print('%-8s FAILED: %r' % (lbl, e))

    sane_modes = [lbl for lbl, r in result['modes'].items() if r['sane']]
    print()
    if sane_modes:
        best = sane_modes[0]
        r = result['modes'][best]
        print('RECOMMENDED for W=%.1fum: mode %s, eps_eff=%.4f, |Zo(Zpi)|=%.4f ohm '
              '(components %.4f, %.4f) at %.1fGHz'
              % (width_um, best, r['eps_eff'], r['zo_mag'], r['zo_re'], r['zo_im'], SOLVE_FREQ_GHZ))
        result['recommended'] = best
    else:
        print('NO mode came back physically sane for W=%.1fum - a real, unresolved problem.' % width_um)
        result['recommended'] = None
        hfss.release_desktop(close_projects=False, close_desktop=False)
        return result

    # --- pull the winning mode across the full 1-12GHz sweep ---
    print()
    print('Pulling %s across the %.1f-%.1fGHz sweep...' % (best, SWEEP_START_GHZ, SWEEP_STOP_GHZ))
    sweep_data = hfss.post.get_solution_data(
        expressions=['Gamma(%s)' % best, 'Zo(%s)' % best],
        setup_sweep_name='%s : FreqSweep' % setup.name,
    )
    freqs, gamma_re_arr = sweep_data.get_expression_data('Gamma(%s)' % best)
    real_d, imag_d = sweep_data.full_matrix_real_imag
    zo_re_arr = real_d['Zo(%s)' % best][:, 1]
    zo_im_arr = imag_d['Zo(%s)' % best][:, 1]

    sweep_rows = []
    print('%-8s %10s %10s %12s   %s' % ('f_GHz', 'beta', 'eps_eff', '|Zo|(ohm)', 'sane?'))
    for f_ghz, beta_f, zre, zim in zip(freqs, gamma_re_arr, zo_re_arr, zo_im_arr):
        k0_f = 2 * math.pi * (f_ghz * 1e9) / 2.998e8
        eps_f = (beta_f / k0_f) ** 2
        zo_mag_f = math.hypot(zre, zim)
        sane_f = 1.0 <= eps_f <= SAPPHIRE_EPS_ZZ
        print('%-8.2f %10.4f %10.4f %12.4f   %s' % (f_ghz, beta_f, eps_f, zo_mag_f, 'YES' if sane_f else 'no'))
        sweep_rows.append(dict(f_ghz=f_ghz, beta=beta_f, eps_eff=eps_f, zo_mag=zo_mag_f, sane=sane_f))
    result['sweep'] = sweep_rows

    # dispersion across 4-8GHz (handoff's own explicit requirement)
    band = [r['eps_eff'] for r in sweep_rows if 4.0 <= r['f_ghz'] <= 8.0 and r['sane']]
    if band:
        disp_pct = 100.0 * (max(band) - min(band)) / (sum(band) / len(band))
        print('Dispersion across 4-8GHz: %.3f%% (min=%.4f, max=%.4f)' % (disp_pct, min(band), max(band)))
        result['dispersion_pct_4_8ghz'] = disp_pct
    else:
        print('WARNING: no sane points in 4-8GHz band - cannot compute dispersion.')
        result['dispersion_pct_4_8ghz'] = None

    # CSV export (handoff deliverable #1)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HFSS')
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, 'epseff_w%d.csv' % round(width_um))
    with open(csv_path, 'w', newline='') as f:
        import csv as csv_mod
        writer = csv_mod.writer(f)
        writer.writerow(['f_GHz', 'beta_rad_per_m', 'eps_eff', 'Zpi_ohm'])
        for r in sweep_rows:
            writer.writerow([r['f_ghz'], r['beta'], r['eps_eff'], r['zo_mag']])
    print('CSV saved -> %s' % csv_path)
    result['csv_path'] = csv_path

    hfss.release_desktop(close_projects=False, close_desktop=False)
    return result


if __name__ == '__main__':
    all_results = [run_extraction(w) for w in WIDTHS_TO_RUN]

    print()
    print('=' * 70)
    print('FINAL SUMMARY')
    print('=' * 70)
    for res in all_results:
        if res['recommended']:
            r = res['modes'][res['recommended']]
            disp = res.get('dispersion_pct_4_8ghz')
            print('W=%.1fum: eps_eff(%.1fGHz)=%.4f, |Zo(Zpi)|=%.4f ohm, dispersion(4-8GHz)=%s, csv=%s'
                  % (res['width_um'], SOLVE_FREQ_GHZ, r['eps_eff'], r['zo_mag'],
                     ('%.3f%%' % disp) if disp is not None else 'N/A', res.get('csv_path')))
        else:
            print('W=%.1fum: NO physically sane mode found (project %s)' % (res['width_um'], res['project_name']))
