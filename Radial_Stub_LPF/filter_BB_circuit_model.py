#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
filter_BB_circuit_model: ABCD transmission-line/circuit model of the
filter_BB stub cascade - Rev 15 Track B item B3, extended in Rev 16 to a
locked forward-prediction instrument for the S7+v2 baseline.

GEOMETRY SOURCES:
  - Pass-3 regression/calibration: HFSS/filter_BB_dims_pass3.json +
    firstlight2_quickscan_pass3_S21.csv (six stubs, real measured data -
    used ONLY to calibrate fan capacitances and sanity-check the matching
    fix below, never to "predict" anything that's already measured).
  - S7+v2 prediction: HFSS/filter_BB_dims.json (seven stubs, live from
    filter_BB.py - Rev 16 Step 0 froze S1 at the v2 baseline and S2-S6 at
    their exact pass-3 lengths, and added S7 at 4.4GHz). No measured data
    exists for this geometry yet - that's the whole point (Rev 16 D1:
    predict before solving).

IMPEDANCE CONVENTION: every line/stub segment uses Z0=ZPI (measured this
session via raw-COM AssignWavePort port recreation + re-solve, matches the
already-saved epseff_w70.csv value to 4 decimal places). Ports modeled at
PORT_Z0=70.0ohm, matching the real HFSS lumped-port setup.

FAN MODELING: a lumped shunt capacitance at each fan-terminated stub's open
end, calibrated per-stub against pass-3's own real measured landed
frequency (solve_fan_capacitance_pf() - see its own docstring for why the
"equivalent length" approach was tried first and rejected: it missed real
measured nulls by up to 50%). S7 (new, Rev 16, no measured data of its own)
reuses S2's calibrated fan_c_pf - the nearest by target frequency among the
stubs with a real calibration (S1 is excluded as a source: it's the
anomalous stub Track A is independently investigating). S1/S6 (fan_term=0)
need no calibration - bare open stubs.

REV 16 D2 FIX: the null-to-stub matching used to be a per-label
`min(nulls, key=nearest)` search, which can double-assign the SAME model
null to two different labels (confirmed: S3 and S4 both matched
5.633GHz in the pass-3 regression - S3's own intended pole isn't
distinguishable as a separate cascade minimum, S4's search fell through to
it). Replaced with the SAME global best-pair-first greedy matching already
proven in filter_BB_firstlight_HFSS.py's build_dashboard() (Rev 14 T4 fix)
- see match_nulls_global() below.

PREDICTION DEFINITION (Rev 16 Step 2): each stub's "predicted null
frequency" and "predicted -3dB width" are computed from that stub's OWN
ISOLATED admittance function (find_pole_ghz/find_isolated_3db_width_ghz),
not read off the cascade's own distinct-null list. This is deliberate: the
cascade's minima can shift or merge under neighbor loading (exactly what
caused the D2 bug), so attributing a specific cascade dip to a specific
stub is not well-defined pre-solve. The isolated-stub numbers ARE
well-defined and reproducible - the price is that they don't include
neighbor-loading effects, which is expected and stated, not hidden. The
cascade's own distinct-pole list is reported separately as supplementary
context (and is what should be compared, informally, against the real
measured trace's overall shape).
"""
import json
import os

import matplotlib.pyplot as plt
import numpy as np

EPS_EFF = 5.681
C_UM_GHZ = 2.998e5          # um*GHz, matches filter_BB.py's own convention
Z0 = 69.7066                 # ohm, Zpi measured this session (matches saved epseff_w70.csv @6GHz)
PORT_Z0 = 70.0                # ohm, matches the real HFSS lumped-port setup

HFSS_DIR = os.path.join(os.path.dirname(__file__), 'HFSS')
PASS3_DIMS_PATH = os.path.join(HFSS_DIR, 'filter_BB_dims_pass3.json')
PASS3_S21_PATH = os.path.join(HFSS_DIR, 'firstlight2_quickscan_pass3_S21.csv')
S7V2_DIMS_PATH = os.path.join(HFSS_DIR, 'filter_BB_dims.json')

# Real matched landed frequencies from the Rev 14 T4-hardened pass-3
# dashboard (firstlight2_quickscan_pass3_dashboard_hardened.csv) - S1 has
# no real notch (Track A, still open), so no calibration target for it.
PASS3_MEASURED_LANDED_GHZ = {
    '4.7GHz': 4.700,
    '5.3GHz': 5.100,
    '6.1GHz': 5.650,
    '7.0GHz': 6.900,
    '8.0GHz': 8.150,
}

PORT1_Y_UM = 35000.0   # chip height(40000) - PAD_EDGE_MARGIN(5000), matches filter_BB.py
PORT2_Y_UM = 7500.0    # SNAIL_KEEPOUT_CY(4000) + SNAIL_KEEPOUT_H/2(2500) + KEEPOUT_CLEARANCE(1000)


def beta_l(f_ghz, l_um):
    return 2 * np.pi * f_ghz * np.sqrt(EPS_EFF) * l_um / C_UM_GHZ


def abcd_line(f_ghz, l_um, z0=Z0):
    bl = beta_l(f_ghz, l_um)
    return np.array([[np.cos(bl), 1j * z0 * np.sin(bl)],
                      [1j * np.sin(bl) / z0, np.cos(bl)]], dtype=complex)


def abcd_shunt_admittance(y):
    return np.array([[1, 0], [y, 1]], dtype=complex)


def open_stub_admittance(f_ghz, l_um, z0=Z0, fan_c_pf=0.0):
    """Open-circuited stub input admittance, optionally loaded with a
    lumped shunt capacitance (fan_c_pf, in picofarads) at its open end -
    see module docstring for why this is needed for fan-terminated stubs."""
    bl = beta_l(f_ghz, l_um)
    y0 = 1.0 / z0
    if fan_c_pf <= 0.0:
        return 1j * y0 * np.tan(bl)
    omega = 2 * np.pi * f_ghz * 1e9
    y_c = 1j * omega * (fan_c_pf * 1e-12)
    tan_bl = np.tan(bl)
    return y0 * (y_c + 1j * y0 * tan_bl) / (y0 + 1j * y_c * tan_bl)


def solve_fan_capacitance_pf(l_um, f_target_ghz, z0=Z0):
    """Calibrate ONE stub's lumped fan capacitance so its own ISOLATED
    admittance pole sits exactly at f_target_ghz (the real measured landed
    frequency) - see module docstring. Derivation: Y_in's denominator
    (y0 + j*y_c*tan(bl)) vanishes (pole) when tan(beta*l) = 1/(Z0*omega*C),
    i.e. C = 1/(Z0*omega*tan(beta(f_target)*l))."""
    bl = beta_l(f_target_ghz, l_um)
    omega = 2 * np.pi * f_target_ghz * 1e9
    c_farad = 1.0 / (z0 * omega * np.tan(bl))
    return c_farad * 1e12


def find_pole_ghz(l_um, fan_c_pf, f_lo, f_hi, z0=Z0, n_scan=400, n_bisect=60):
    """Isolated-stub admittance pole within [f_lo, f_hi] - pure bisection,
    no scipy dependency (not in this repo's own .venv). Bare stubs use
    cos(beta*l)'s zero-crossing (smooth, no branch-cut issue); fan-loaded
    stubs use tan(beta*l) - 1/(Z0*omega*C)'s zero-crossing (the same
    condition solve_fan_capacitance_pf() inverts the other way). Returns
    None if no sign change is found in the bracket (caller's bracket was
    wrong - a real error to surface, not silently swallow)."""
    def g(f_ghz):
        if fan_c_pf <= 0.0:
            return np.cos(beta_l(f_ghz, l_um))
        omega = 2 * np.pi * f_ghz * 1e9
        return np.tan(beta_l(f_ghz, l_um)) - 1.0 / (z0 * omega * (fan_c_pf * 1e-12))

    fs = np.linspace(f_lo, f_hi, n_scan)
    gs = np.array([g(f) for f in fs])
    sign_changes = np.where(np.diff(np.sign(gs)) < 0)[0]  # pole approached from below (g: -inf-ish -> +inf-ish is the tan branch jump, not a root; a true ROOT of a continuously-increasing g crosses - to +)
    # tan(x)-const is increasing right up to the pole, so a genuine root is a - to + crossing;
    # the branch-cut jump (+inf to -inf) shows as a + to - crossing - explicitly excluded above.
    if len(sign_changes) == 0:
        return None
    i = sign_changes[0]
    a, b = fs[i], fs[i + 1]
    for _ in range(n_bisect):
        m = 0.5 * (a + b)
        if np.sign(g(a)) == np.sign(g(m)):
            a = m
        else:
            b = m
    return 0.5 * (a + b)


def find_isolated_3db_width_ghz(l_um, fan_c_pf, f0_ghz, z0=Z0, half_span_ghz=1.2, n_scan=4001, _depth=0):
    """-3dB width of ONE isolated shunt stub on an otherwise-matched line,
    via the standard |S21|^2 = 4/(4+B^2) result (B = normalized shunt
    susceptance = Im(Y_in)*Z0 for a lossless shunt admittance) - same
    formula already trusted in this project's own Part I analysis text.
    -3dB edges are where |B|=2. ADAPTIVE span: if |B|>=2 all the way to
    either edge of the search window, that edge is a CLIPPED result, not a
    real crossing - double the span and retry (bounded) rather than
    silently report a truncated width (a real bug caught before this file's
    earlier version locked several predictions at exactly 2x their search
    half-span - e.g. 2.4000GHz for a 1.2GHz half-span, verbatim across four
    different stubs, which is what exposed the clipping in the first
    place)."""
    fs = np.linspace(f0_ghz - half_span_ghz, f0_ghz + half_span_ghz, n_scan)
    B = np.array([open_stub_admittance(f, l_um, z0, fan_c_pf).imag * z0 for f in fs])
    center_i = int(np.argmin(np.abs(fs - f0_ghz)))
    lo_i, hi_i = center_i, center_i
    while lo_i > 0 and abs(B[lo_i]) >= 2.0:
        lo_i -= 1
    while hi_i < len(fs) - 1 and abs(B[hi_i]) >= 2.0:
        hi_i += 1
    clipped_lo = (lo_i == 0 and abs(B[0]) >= 2.0)
    clipped_hi = (hi_i == len(fs) - 1 and abs(B[-1]) >= 2.0)
    if (clipped_lo or clipped_hi) and half_span_ghz < 6.0:
        return find_isolated_3db_width_ghz(l_um, fan_c_pf, f0_ghz, z0, half_span_ghz * 2, n_scan, _depth + 1)
    if clipped_lo or clipped_hi:
        print('  WARNING: -3dB width search did not converge within +-6GHz for f0=%.3fGHz - '
              'reporting the clipped bound, treat as a lower limit not an exact width.' % f0_ghz)
    return fs[hi_i] - fs[lo_i], fs[lo_i], fs[hi_i]


def load_dims(path):
    with open(path) as f:
        return json.load(f)


def s21_of_f(f_ghz, stub_models, z0=Z0, port_z0=PORT_Z0):
    M = np.eye(2, dtype=complex)
    prev_y = PORT1_Y_UM
    for sm in stub_models:
        section_len = prev_y - sm['tee_y']
        M = M @ abcd_line(f_ghz, section_len, z0)
        y_stub = open_stub_admittance(f_ghz, sm['l_um'], z0, sm['fan_c_pf'])
        M = M @ abcd_shunt_admittance(y_stub)
        prev_y = sm['tee_y']
    M = M @ abcd_line(f_ghz, prev_y - PORT2_Y_UM, z0)
    A, B, C, D = M[0, 0], M[0, 1], M[1, 0], M[1, 1]
    denom = A + B / port_z0 + C * port_z0 + D
    return 2.0 / denom


def find_local_minima_ghz(freqs, vals_db, depth_threshold_db=-10.0):
    out = []
    for i in range(1, len(freqs) - 1):
        if vals_db[i] < vals_db[i - 1] and vals_db[i] < vals_db[i + 1] and vals_db[i] < depth_threshold_db:
            out.append((float(freqs[i]), float(vals_db[i])))
    return out


def match_nulls_global(model_nulls, targets, max_rel_offset=0.30):
    """Global best-pair-first greedy matching (Rev 16 D2 fix) - identical
    algorithm to filter_BB_firstlight_HFSS.py's build_dashboard() (Rev 14
    T4): build every (label, null) candidate pair within tolerance, sort by
    relative offset ascending, claim greedily (best match first) so one
    null can never be double-assigned to two labels. targets: {label:
    f_target_ghz}. Returns {label: (null_f, null_depth_db, rel_pct) or
    None}."""
    labels = list(targets.keys())
    candidates = []
    for li, label in enumerate(labels):
        target = targets[label]
        for ni, (nf, nd) in enumerate(model_nulls):
            rel_offset = abs(nf - target) / target
            if rel_offset <= max_rel_offset:
                candidates.append((rel_offset, li, ni))
    candidates.sort(key=lambda c: c[0])
    assigned, claimed = {}, set()
    for rel_offset, li, ni in candidates:
        if li in assigned or ni in claimed:
            continue
        assigned[li] = ni
        claimed.add(ni)
    result = {}
    for li, label in enumerate(labels):
        if li in assigned:
            nf, nd = model_nulls[assigned[li]]
            result[label] = (nf, nd, 100.0 * (nf - targets[label]) / targets[label])
        else:
            result[label] = None
    return result


def calibrate_pass3_fan_capacitances():
    """Returns {label: fan_c_pf} for S2-S5, calibrated against pass-3's own
    real measured landed frequencies."""
    dims = load_dims(PASS3_DIMS_PATH)
    fan_c = {}
    for s in dims['stubs']:
        if s['fan_term_rout_um'] > 0 and s['label'] in PASS3_MEASURED_LANDED_GHZ:
            fan_c[s['label']] = solve_fan_capacitance_pf(s['realized_length_um'], PASS3_MEASURED_LANDED_GHZ[s['label']])
    return fan_c


def run_pass3_regression(fan_c_pf_by_label):
    print('=' * 70)
    print('STEP 1 REGRESSION: pass-3 six-stub geometry, hardened matching')
    print('=' * 70)
    dims = load_dims(PASS3_DIMS_PATH)
    stub_models = []
    for s in dims['stubs']:
        fan_c_pf = fan_c_pf_by_label.get(s['label'], 0.0)
        stub_models.append(dict(label=s['label'], l_um=s['realized_length_um'], fan_c_pf=fan_c_pf,
                                 tee_y=s['tee_pos_um'][1], has_fan=s['fan_term_rout_um'] > 0))
    freqs = np.linspace(0.5, 13.0, 6001)
    s21_db = 20 * np.log10(np.abs([s21_of_f(f, stub_models) for f in freqs]))
    model_nulls = find_local_minima_ghz(freqs, s21_db)
    print('Distinct cascade-model poles (depth < -10dB), label-independent:')
    for f, d in model_nulls:
        print('  %.3fGHz  (%.1fdB)' % (f, d))
    print('-' * 70)
    print('Null-position agreement (global best-pair-first matching, Rev 16 D2 fix):')
    matched = match_nulls_global(model_nulls, PASS3_MEASURED_LANDED_GHZ)
    for label, f_meas in PASS3_MEASURED_LANDED_GHZ.items():
        m = matched[label]
        if m is None:
            print('  %-8s measured=%.3fGHz -> NO MODEL NULL FOUND' % (label, f_meas))
        else:
            nf, nd, rel = m
            flag = '' if abs(rel) <= 5.0 else '  <<< DISAGREES (>5%)'
            print('  %-8s measured=%.3fGHz  model=%.3fGHz  delta=%+.2f%%%s' % (label, f_meas, nf, rel, flag))
    print('-' * 70)
    print('(S3 vs S4 double-assignment check: under the OLD per-label nearest-search both')
    print(' matched 5.633GHz identically - see if that collision is gone above.)')
    print('=' * 70)
    return dims, stub_models, freqs, s21_db


def run_s7v2_predictions(fan_c_pf_by_label):
    print()
    print('=' * 70)
    print('STEP 2: S7+v2 LOCKED PRE-SOLVE PREDICTIONS (no measured data used)')
    print('=' * 70)
    dims = load_dims(S7V2_DIMS_PATH)
    stub_models = []
    rows = []
    for s in dims['stubs']:
        label = s['label']
        l_um = s['realized_length_um']
        has_fan = s['fan_term_rout_um'] > 0
        if label in fan_c_pf_by_label:
            fan_c_pf = fan_c_pf_by_label[label]
            fan_note = 'own pass-3 calibration'
        elif has_fan:
            # S7: no measured data of its own - borrow the nearest-by-target-frequency
            # calibrated neighbor (excludes S1, the anomalous/uncalibrated stub).
            target = s['f_target_ghz']
            nearest_label = min(fan_c_pf_by_label, key=lambda lbl: abs(float(lbl.replace('GHz', '')) - target))
            fan_c_pf = fan_c_pf_by_label[nearest_label]
            fan_note = 'borrowed from %s (nearest calibrated neighbor)' % nearest_label
        else:
            fan_c_pf = 0.0
            fan_note = 'bare (no fan)'
        stub_models.append(dict(label=label, l_um=l_um, fan_c_pf=fan_c_pf, tee_y=s['tee_pos_um'][1], has_fan=has_fan))

        # isolated per-stub prediction (see module docstring for why isolated, not cascade-read)
        f_search_center = s['f_target_ghz'] if not has_fan else s['f_target_ghz']
        f_pole = find_pole_ghz(l_um, fan_c_pf, max(0.3, f_search_center - 2.0), f_search_center + 2.0)
        if f_pole is None:
            print('  WARNING: %s isolated pole not found in search bracket - widening' % label)
            f_pole = find_pole_ghz(l_um, fan_c_pf, 0.3, 13.0)
        width_ghz, w_lo, w_hi = find_isolated_3db_width_ghz(l_um, fan_c_pf, f_pole)
        rows.append(dict(label=label, l_um=l_um, fan_treatment=fan_note,
                          predicted_null_ghz=f_pole, predicted_width_ghz=width_ghz,
                          width_lo_ghz=w_lo, width_hi_ghz=w_hi))

    print('Per-stub isolated predictions (drawn length | fan treatment | predicted null | predicted -3dB width):')
    for r in rows:
        print('  %-8s l=%8.2fum  %-42s  f0=%.4fGHz  width=%.4fGHz (%.3f-%.3f)'
              % (r['label'], r['l_um'], r['fan_treatment'], r['predicted_null_ghz'],
                 r['predicted_width_ghz'], r['width_lo_ghz'], r['width_hi_ghz']))

    freqs = np.linspace(0.5, 14.0, 6501)
    s21_db = 20 * np.log10(np.abs([s21_of_f(f, stub_models) for f in freqs]))
    cascade_nulls = find_local_minima_ghz(freqs, s21_db)
    print('-' * 70)
    print('Cascade-model distinct poles (supplementary context, label-independent):')
    for f, d in cascade_nulls:
        print('  %.3fGHz  (%.1fdB)' % (f, d))
    print('=' * 70)

    import csv
    out_path = os.path.join(HFSS_DIR, 's7v2_predictions.csv')
    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['label', 'l_um', 'fan_treatment', 'predicted_null_ghz',
                                                 'predicted_width_ghz', 'width_lo_ghz', 'width_hi_ghz'])
        writer.writeheader()
        writer.writerows(rows)
    print('Predictions written -> %s' % out_path)

    with open(os.path.join(HFSS_DIR, 's7v2_predictions_distinct_poles.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['freq_ghz', 'depth_db'])
        writer.writerows(cascade_nulls)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(freqs, s21_db, color='C1', linewidth=1.0)
    for r in rows:
        ax.axvline(r['predicted_null_ghz'], color='C3', linestyle='--', alpha=0.5, linewidth=0.8)
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('S21 (dB)')
    ax.set_title('filter_BB S7+v2 circuit-model PREDICTION (pre-solve) - Zpi=%.2fohm' % Z0)
    ax.set_ylim(-80, 5)
    out_png = os.path.join(HFSS_DIR, 's7v2_predictions_plot.png')
    fig.savefig(out_png, dpi=150, bbox_inches='tight')
    print('Prediction plot saved -> %s' % out_png)
    return rows


def main():
    fan_c_pf_by_label = calibrate_pass3_fan_capacitances()
    print('Pass-3-calibrated fan capacitances (per-stub, against real measured landed freq):')
    for label, c in fan_c_pf_by_label.items():
        print('  %-8s fan_c=%.4fpF' % (label, c))

    dims3, models3, freqs3, s21_db3 = run_pass3_regression(fan_c_pf_by_label)

    # overlay plot against the real pass-3 measurement (regression sanity check)
    meas_freqs, meas_s21_db, _ = np.loadtxt(PASS3_S21_PATH, delimiter=',', skiprows=1, unpack=True)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(meas_freqs, meas_s21_db, label='Measured (pass-3 HFSS)', color='C0', linewidth=1.2)
    ax.plot(freqs3, s21_db3, label='Circuit model (Zpi=%.2fohm)' % Z0, color='C1', linewidth=1.0, alpha=0.85)
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('S21 (dB)')
    ax.set_title('filter_BB circuit model vs. real pass-3 HFSS measurement (regression)')
    ax.legend()
    ax.set_ylim(-80, 5)
    out_png = os.path.join(HFSS_DIR, 'filter_BB_circuit_model_overlay.png')
    fig.savefig(out_png, dpi=150, bbox_inches='tight')
    print('Regression overlay plot saved -> %s' % out_png)

    run_s7v2_predictions(fan_c_pf_by_label)


if __name__ == '__main__':
    main()
