#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 11 post-processing: merges oval_epseff_raw.csv (Model A) and
oval_branch_stub_raw.csv (Models B/C) into oval_study.csv, produces the 4
decision plots, a sensitivity table, and the verdict text - per the
handoff's own deliverables list. Pure Python (numpy/matplotlib only) - no
AEDT/pyEPR/pyaedt needed, but run via .AnE's python since that's where
matplotlib/numpy are already confirmed available (filter_L60_package_
HFSS.py's own prior successful use).

DATA-QUALITY CAVEATS baked into this analysis, not glossed over:

1. Model A's eps_eff at 6GHz and 9GHz DISAGREE substantially away from the
   reference bore_h (6GHz climbs toward the sanity ceiling ~11 as bore_h
   shrinks; 9GHz drops toward ~4, the physically-expected direction) - a
   live field-plot check found BOTH frequencies' selected mode is
   wall-hugging, not strip-hugging, at the smallest bore_h, and the
   plot_field mechanism isn't mode-index-specific enough to resolve which
   (if either) is correct. Both traces are plotted and reported; this
   script does NOT pick a winner.
2. Model B's own absolute f_zero (~11.5-11.8GHz throughout the ENTIRE
   sweep) is far from the real P4 design's 4.752GHz target - confirmed
   (widened sweep, bore_w halved) this isn't a sweep-range or bore-size
   artifact; the branch's null in this UNFOLDED test appears dominated by
   the stalk's own transmission-line resonance rather than fan-capacitance
   loading. The ABSOLUTE value is not comparable to the real design: the
   TREND vs gap (essentially flat, see below) is the trustworthy signal.
3. Model C's own "implied eps_eff" (back-solved from its measured f_zero
   via the same quarter-wave formula, NOT copied from Model A) is used for
   the stub-design-impact criterion - self-consistent for tracking the
   TREND across this model's own sweep, but not directly comparable to
   Model A's own eps_eff (different physical configuration - a T-branch
   stub resonance, not a bare 2-port propagation constant).

RUN VIA THE SEPARATE PYEPR/PYAEDT ENVIRONMENT (matplotlib/numpy live
there, confirmed working) - doesn't touch AEDT itself:
    C:\\Users\\epm114\\.AnE\\Scripts\\python.exe oval_study_analysis.py
"""
import csv
import math
import os

import numpy as np

C_UM_GHZ = 2.998e5  # speed of light, um*GHz (same convention as filter_BB.py)

STUB_LENGTH_C_UM = 6030.0  # Model C's own fixed stub length (handoff's own number)
BRANCH_TARGET_GHZ = 4.752  # P4's real design target (filter_L60.py zero_label)
STUB_NOMINAL_GHZ = 5.3     # nominal frequency of the real 5.3GHz filter_BB stub this model approximates
REFERENCE_EPS_EFF = 5.681  # Model A's own HFSS-calibrated reference (DESIGN_NOTES Sec. 9)

SENSITIVITY_STEP_UM = 50.0  # "MHz per 50um" - the handoff's own tolerance currency

HERE = os.path.dirname(os.path.abspath(__file__))
HFSS_DIR = os.path.join(HERE, 'HFSS')


def load_epseff_raw():
    rows = {}
    path = os.path.join(HFSS_DIR, 'oval_epseff_raw.csv')
    with open(path) as f:
        for row in csv.DictReader(f):
            bore_h = float(row['bore_h_um'])
            freq = round(float(row['freq_ghz']))
            rows.setdefault(bore_h, {})[freq] = dict(
                eps_eff=float(row['eps_eff']), zpi_ohm=float(row['zpi_ohm']), gap_um=float(row['gap_um']))
    return rows


def load_branch_stub_raw():
    rows = {}
    path = os.path.join(HFSS_DIR, 'oval_branch_stub_raw.csv')
    with open(path) as f:
        for row in csv.DictReader(f):
            bore_h = float(row['bore_h_um'])
            model = row['model']
            rows.setdefault(bore_h, {})[model] = dict(
                f_zero_ghz=float(row['f_zero_ghz']), gap_um=float(row['gap_um']))
    return rows


def merge(epseff, branch_stub):
    bore_hs = sorted(set(epseff.keys()) | set(branch_stub.keys()), reverse=True)
    merged = []
    for bh in bore_hs:
        e = epseff.get(bh, {})
        bs = branch_stub.get(bh, {})
        gap_um = (e.get(6, {}) or e.get(9, {}) or bs.get('B', {}) or bs.get('C', {})).get('gap_um')
        row = dict(
            bore_h_um=bh, gap_um=gap_um,
            eps_eff_6ghz=e.get(6, {}).get('eps_eff'), eps_eff_9ghz=e.get(9, {}).get('eps_eff'),
            zpi_6ghz_ohm=e.get(6, {}).get('zpi_ohm'), zpi_9ghz_ohm=e.get(9, {}).get('zpi_ohm'),
            f_zero_branch_ghz=bs.get('B', {}).get('f_zero_ghz'),
            f_zero_stub_ghz=bs.get('C', {}).get('f_zero_ghz'),
        )
        if row['f_zero_stub_ghz']:
            row['stub_implied_eps_eff'] = (C_UM_GHZ / (4 * STUB_LENGTH_C_UM * row['f_zero_stub_ghz'])) ** 2
        else:
            row['stub_implied_eps_eff'] = None
        merged.append(row)
    return merged


def write_csv(merged, path):
    fieldnames = ['bore_h_um', 'gap_um', 'eps_eff_6ghz', 'eps_eff_9ghz', 'zpi_6ghz_ohm', 'zpi_9ghz_ohm',
                  'f_zero_branch_ghz', 'f_zero_stub_ghz', 'stub_implied_eps_eff']
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)


def _series(merged, key):
    gaps, vals = [], []
    for row in merged:
        if row.get(key) is not None and row.get('gap_um') is not None:
            gaps.append(row['gap_um'])
            vals.append(row[key])
    order = np.argsort(gaps)
    return np.array(gaps)[order], np.array(vals)[order]


def make_plots(merged, out_dir):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib not available - skipping plots.')
        return

    # 1. eps_eff vs gap
    fig, ax = plt.subplots(figsize=(8, 5))
    g6, e6 = _series(merged, 'eps_eff_6ghz')
    g9, e9 = _series(merged, 'eps_eff_9ghz')
    ax.plot(g6, e6, 'o-', label='eps_eff @ 6GHz (unresolved trend - see docstring)')
    ax.plot(g9, e9, 's-', label='eps_eff @ 9GHz (unresolved trend - see docstring)')
    ax.axhline(REFERENCE_EPS_EFF, color='gray', linestyle=':', label='Rev9 reference (5.681)')
    ax.set_xlabel('gap (um)')
    ax.set_ylabel('eps_eff')
    ax.set_title('Model A: bare-strip eps_eff vs metal-to-lid gap')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(os.path.join(out_dir, 'oval_eps_eff_vs_gap.png'), dpi=150, bbox_inches='tight')
    plt.close(fig)

    # 2. Zpi vs gap
    fig, ax = plt.subplots(figsize=(8, 5))
    g6z, z6 = _series(merged, 'zpi_6ghz_ohm')
    g9z, z9 = _series(merged, 'zpi_9ghz_ohm')
    ax.plot(g6z, z6, 'o-', label='|Zpi| @ 6GHz')
    ax.plot(g9z, z9, 's-', label='|Zpi| @ 9GHz')
    ax.set_xlabel('gap (um)')
    ax.set_ylabel('|Zpi| (ohm)')
    ax.set_title('Model A: bare-strip |Zpi| vs metal-to-lid gap')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(os.path.join(out_dir, 'oval_zpi_vs_gap.png'), dpi=150, bbox_inches='tight')
    plt.close(fig)

    # 3. f_zero_branch vs gap with target line
    fig, ax = plt.subplots(figsize=(8, 5))
    gb, fb = _series(merged, 'f_zero_branch_ghz')
    ax.plot(gb, fb, 'o-', label='Model B: unfolded P4 branch null')
    ax.axhline(BRANCH_TARGET_GHZ, color='red', linestyle='--', label='real design target (4.752GHz)')
    ax.set_xlabel('gap (um)')
    ax.set_ylabel('f_zero (GHz)')
    ax.set_title('Model B: branch zero vs metal-to-lid gap')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(os.path.join(out_dir, 'oval_f_zero_branch_vs_gap.png'), dpi=150, bbox_inches='tight')
    plt.close(fig)

    # 4. f_zero_stub vs gap with nominal line
    fig, ax = plt.subplots(figsize=(8, 5))
    gs, fs = _series(merged, 'f_zero_stub_ghz')
    ax.plot(gs, fs, 'o-', label='Model C: unfolded filter_BB-style stub null')
    ax.axhline(STUB_NOMINAL_GHZ, color='red', linestyle='--', label='nominal target (5.3GHz)')
    ax.set_xlabel('gap (um)')
    ax.set_ylabel('f_zero (GHz)')
    ax.set_title('Model C: stub zero vs metal-to-lid gap')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(os.path.join(out_dir, 'oval_f_zero_stub_vs_gap.png'), dpi=150, bbox_inches='tight')
    plt.close(fig)

    print('4 plots saved -> %s' % out_dir)


def sensitivity_table(merged):
    lines = []
    for key, label in (('f_zero_branch_ghz', 'f_zero_branch'), ('f_zero_stub_ghz', 'f_zero_stub')):
        gaps, vals = _series(merged, key)
        lines.append('%s local slopes (MHz per %.0fum):' % (label, SENSITIVITY_STEP_UM))
        for i in range(len(gaps) - 1):
            dg = gaps[i + 1] - gaps[i]
            df_mhz = (vals[i + 1] - vals[i]) * 1000.0
            slope = df_mhz / dg * SENSITIVITY_STEP_UM
            lines.append('  gap %.0f -> %.0fum: %.2f MHz per %.0fum' % (gaps[i], gaps[i + 1], slope, SENSITIVITY_STEP_UM))
    return '\n'.join(lines)


def compute_verdict(merged):
    gb, fb = _series(merged, 'f_zero_branch_ghz')
    lines = []
    lines.append('DECISION: FAN-LADDER VIABILITY')
    crosses = np.any((fb[:-1] - BRANCH_TARGET_GHZ) * (fb[1:] - BRANCH_TARGET_GHZ) < 0)
    min_gap_at_crossing = None
    if crosses:
        for i in range(len(fb) - 1):
            if (fb[i] - BRANCH_TARGET_GHZ) * (fb[i + 1] - BRANCH_TARGET_GHZ) < 0:
                min_gap_at_crossing = min(gb[i], gb[i + 1])
    lines.append('  f_zero_branch range across the full sweep: %.3f - %.3f GHz (target %.3fGHz)'
                 % (fb.min(), fb.max(), BRANCH_TARGET_GHZ))
    if crosses and min_gap_at_crossing is not None and min_gap_at_crossing >= 500.0:
        lines.append('  VERDICT: FAN-LADDER VIABLE - target crossed at gap=%.0fum (>=500um)' % min_gap_at_crossing)
    else:
        lines.append('  VERDICT: FAN-LADDER NOT VIABLE in this test - f_zero_branch never crosses '
                      '%.3fGHz at any tested gap (250-3242um). Absolute value is offset from the real '
                      'design for reasons unrelated to gap (see module docstring); the essentially FLAT '
                      'trend across the full gap range (%.2f-%.2fGHz, %.1f%% spread) is itself the finding: '
                      'no evidence flattening meaningfully changes this branch\'s own resonant behavior '
                      'in this test configuration.' % (BRANCH_TARGET_GHZ, fb.min(), fb.max(),
                                                        100 * (fb.max() - fb.min()) / fb.mean()))

    lines.append('')
    lines.append('DECISION: STUB-DESIGN IMPACT')
    gs, fs = _series(merged, 'f_zero_stub_ghz')
    gi, ei = _series(merged, 'stub_implied_eps_eff')
    lines.append('  f_zero_stub range: %.3f - %.3f GHz (%.1f%% spread) as gap shrinks %.0f -> %.0fum'
                 % (fs.min(), fs.max(), 100 * (fs.max() - fs.min()) / fs.mean(), gs.max(), gs.min()))
    lines.append('  stub-implied eps_eff (back-solved from f_zero_stub via the quarter-wave formula, '
                 'self-consistent for THIS model, not directly comparable to Model A): %.3f -> %.3f '
                 'across the same gap range' % (ei[np.argmax(gi)], ei[np.argmin(gi)]))
    growth_factor = math.sqrt(ei[np.argmax(gi)] / ei[np.argmin(gi)])
    lines.append('  implied length growth factor sqrt(eps_eff_wide_gap/eps_eff_narrow_gap) = %.4f' % growth_factor)
    stub_4p2ghz_um = C_UM_GHZ / (4 * 4.2 * math.sqrt(ei[np.argmin(gi)]))
    lines.append('  4.2GHz stub length at the narrowest tested gap, using the stub-implied eps_eff: %.2fmm%s'
                 % (stub_4p2ghz_um / 1000.0, ' - EXCEEDS 10mm fold-budget flag' if stub_4p2ghz_um > 10000 else ''))

    return '\n'.join(lines)


def main():
    os.makedirs(HFSS_DIR, exist_ok=True)
    epseff = load_epseff_raw()
    branch_stub = load_branch_stub_raw()
    merged = merge(epseff, branch_stub)

    csv_path = os.path.join(HFSS_DIR, 'oval_study.csv')
    write_csv(merged, csv_path)
    print('Merged CSV -> %s' % csv_path)

    make_plots(merged, HFSS_DIR)

    sens = sensitivity_table(merged)
    print()
    print('=' * 70)
    print('SENSITIVITY TABLE')
    print('=' * 70)
    print(sens)

    verdict = compute_verdict(merged)
    print()
    print('=' * 70)
    print('VERDICT')
    print('=' * 70)
    print(verdict)

    report_path = os.path.join(HFSS_DIR, 'oval_study_verdict.txt')
    with open(report_path, 'w') as f:
        f.write('SENSITIVITY TABLE\n' + '=' * 70 + '\n' + sens + '\n\n')
        f.write('VERDICT\n' + '=' * 70 + '\n' + verdict + '\n')
    print()
    print('Verdict + sensitivity table saved -> %s' % report_path)


if __name__ == '__main__':
    main()
