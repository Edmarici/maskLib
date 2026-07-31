#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 18 DIRECTIONAL PROBE - S1 wide-gap single fold (variant `v3f_singlefold`).

NOT a characterization run and NOT a scorecard. Deliberately loose: one
interpolating sweep over 3.5-9.0GHz, single-point adaptive mesh, no discrete
windows, no dashboard, no label-assignment, no passband/8-14GHz analysis. The
only question it answers is whether refolding S1 away from S3 moves the
~4.9GHz stopband hole in the right direction, for roughly a quarter of a full
confirmation run's solve time.

Reuses filter_BB_firstlight_HFSS.py's machinery wholesale (connect_project,
_load_geometry, build_design, pull_sweep) rather than duplicating the AEDT
plumbing - that file's package model, port definitions, material tensor and
losslessness audit are the already-validated ones, and reproducing them here
would be exactly the kind of drift that bit the HFSS export replay in Rev 18
(per-stub d_perp/run_gap silently read from stale globals).

DELIBERATE DEVIATION FROM THE HANDOFF: the bore stays at 7000um, not the
handoff's 6.985mm. The whole point of this run is a numerical comparison
against v3, which was solved at 7000um; changing the bore in the same step
would confound the one variable under test. The 7000/6985 tension is a real
open item but it is not this run's business (CLAUDE.md / Rev 17 already
reconciled it in favour of the 7000um filter_BB.py convention).

The max-4-passes cap in the handoff is not enforced separately: the shared
setup builder uses max_delta_s=0.02 with max_passes=12, and v3's own solve
converged in 3 passes at that tolerance, so the cap would not bind. The
convergence history is reported so this can be checked rather than assumed.
"""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filter_BB_firstlight_HFSS as FL  # noqa: E402

DESIGN_NAME = 'v3f_singlefold'
OUT_PREFIX = 'v3f_singlefold'
BASELINE_PREFIX = 'v3_confirm'      # the tagged filter_BB_v3 solve

PROBE_START_GHZ = 3.5
PROBE_STOP_GHZ = 9.0
PROBE_COUNT = 1101                  # ~5MHz
PROBE_ADAPTIVE_GHZ = 4.7            # centre of the region of interest

# v3 reference numbers, from HFSS/v3_confirm_scorecard.txt
V3_S21_AT_4P5 = -33.56
V3_HOLE_WORST = -7.39
V3_HOLE_AT_GHZ = 4.910


def _at(freqs, vals, f0):
    i = int(np.argmin(np.abs(freqs - f0)))
    return float(freqs[i]), float(vals[i])


def _worst_in(freqs, vals, lo, hi):
    m = (freqs >= lo) & (freqs <= hi)
    if not m.any():
        return None, None
    sub_f, sub_v = freqs[m], vals[m]
    i = int(np.argmax(sub_v))
    return float(sub_f[i]), float(sub_v[i])


def _nulls(freqs, vals, lo, hi, depth=-15.0):
    out = []
    for i in range(1, len(freqs) - 1):
        if not (lo <= freqs[i] <= hi):
            continue
        if vals[i] < vals[i - 1] and vals[i] < vals[i + 1] and vals[i] < depth:
            out.append((float(freqs[i]), float(vals[i])))
    return out


def _load_baseline(out_dir):
    path = os.path.join(out_dir, '%s_S21.csv' % BASELINE_PREFIX)
    if not os.path.exists(path):
        return None, None
    f, s = [], []
    with open(path, newline='') as fh:
        rdr = csv.DictReader(fh)
        fcol = next(c for c in rdr.fieldnames if c.lower().startswith('f'))
        scol = next(c for c in rdr.fieldnames if 's21' in c.lower())
        for r in rdr:
            try:
                f.append(float(r[fcol]))
                s.append(float(r[scol]))
            except (TypeError, ValueError):
                continue
    order = np.argsort(np.array(f))
    return np.array(f)[order], np.array(s)[order]


def main():
    project = FL.connect_project()
    # CLAUDE.md: a persistent desktop can hold several same-named project
    # handles, and picking the wrong one has already cost this campaign a real
    # solve. connect_project() attaches to the first match; say how many there
    # were so a wrong-handle result is diagnosable rather than silent.
    desktop = FL.HFSS.HfssApp().get_app_desktop()
    same_named = [p for p in desktop.get_projects() if p.name == FL.PROJECT_NAME]
    print('AEDT handles named %r currently open: %d%s'
          % (FL.PROJECT_NAME, len(same_named),
             '  <== MORE THAN ONE, results may belong to another handle' if len(same_named) > 1 else ''))

    geom = FL._load_geometry()
    dims = FL._load_dims()
    fbb = FL._load_filter_BB()
    assert len(dims['stubs']) == len(fbb.STUBS), 'stale dims JSON - re-run filter_BB.py'
    s1 = dims['stubs'][0]
    print('S1 under test: %s  realized %.4fum  run_length %.4fum  bend_radius %.1fum  fold_dir %+d'
          % (s1['label'], s1['realized_length_um'], s1['run_length_um'],
             s1['bend_radius_um'], s1['fold_dir']))
    assert abs(s1['realized_length_um'] - 8820.283628620473) < 1e-6, (
        'S1 length %.6f is not the Rev 18 single-fold target - wrong geometry loaded'
        % s1['realized_length_um'])

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HFSS')
    os.makedirs(out_dir, exist_ok=True)

    FL.ADAPTIVE_FREQ_GHZ = PROBE_ADAPTIVE_GHZ
    specs = [dict(name='Probe_Sweep', type='Interpolating',
                  start=PROBE_START_GHZ, stop=PROBE_STOP_GHZ, count=PROBE_COUNT)]
    design, setup, sweeps = FL.build_design(project, DESIGN_NAME, geom, specs,
                                             adaptive='single')

    print('solving %s (single-point adaptive @ %.2fGHz, delta_S 0.02)...'
          % (DESIGN_NAME, PROBE_ADAPTIVE_GHZ))
    setup.analyze()

    rows = FL.export_convergence(design, setup.name, out_dir)
    if rows:
        print('convergence: %d passes, final delta-S %s'
              % (len(rows), list(rows[-1].values())[-1]))
    else:
        print('convergence history unavailable (does not invalidate the sweep)')

    freqs, s21, s11 = FL.pull_sweep(sweeps['Probe_Sweep'], out_dir, '_probe')

    csv_path = os.path.join(out_dir, '%s_S21.csv' % OUT_PREFIX)
    with open(csv_path, 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['freq_ghz', 'S21_dB', 'S11_dB'])
        for a, b, c in zip(freqs, s21, s11):
            wr.writerow(['%.6f' % a, '%.6f' % b, '%.6f' % c])
    print('S21 saved -> %s' % csv_path)

    bf, bs = _load_baseline(out_dir)

    print('=' * 70)
    print('Rev 18 directional probe - S1 wide-gap single fold vs v3 L-stub')
    print('  DIRECTIONAL ONLY: looser mesh than v3, interpolated sweep, no')
    print('  discrete window. Do not read these as scorecard numbers.')
    print('=' * 70)

    f45, s45 = _at(freqs, s21, 4.5)
    print('1. S21 @ %.3fGHz            : %+8.2f dB   (v3 %+.2f dB, delta %+.2f dB)'
          % (f45, s45, V3_S21_AT_4P5, s45 - V3_S21_AT_4P5))

    hf, hv = _worst_in(freqs, s21, 4.7, 5.3)
    print('2. worst S21 in 4.7-5.3GHz  : %+8.2f dB @ %.3fGHz   (v3 %+.2f dB @ %.3fGHz, delta %+.2f dB)'
          % (hv, hf, V3_HOLE_WORST, V3_HOLE_AT_GHZ, hv - V3_HOLE_WORST))

    n_lo = _nulls(freqs, s21, 4.0, 5.0)
    if n_lo:
        deep = min(n_lo, key=lambda p: p[1])
        print('3. deepest null 4.0-5.0GHz  : %.3fGHz (%.1f dB)   [all: %s]'
              % (deep[0], deep[1], ', '.join('%.3f(%.0fdB)' % p for p in n_lo)))
    else:
        print('3. deepest null 4.0-5.0GHz  : NONE below -15dB')

    n_s3 = _nulls(freqs, s21, 5.2, 5.5)
    if n_s3:
        print('4. null reappeared 5.2-5.5? : YES - %s   (v3 had none; S3 recovering)'
              % ', '.join('%.3fGHz(%.1fdB)' % p for p in n_s3))
    else:
        print('4. null reappeared 5.2-5.5? : no')

    print('-' * 70)
    print('   all nulls 3.5-9.0GHz     : %s'
          % ', '.join('%.3f(%.0fdB)' % p for p in _nulls(freqs, s21, 3.5, 9.0)))

    # Decision rule. SIGN CONVENTION, since this is easy to get backwards and
    # I did get it backwards on the first run: these are stopband numbers, so a
    # MORE NEGATIVE dB value is BETTER (deeper rejection). "The hole improved by
    # X dB" therefore means the worst-case S21 in the band went DOWN by X, i.e.
    # improvement = v3_worst - new_worst, positive when the new one is deeper.
    hole_gain = V3_HOLE_WORST - hv
    print('-' * 70)
    print('hole: v3 %+.2fdB -> now %+.2fdB  = %+.2fdB of extra rejection'
          % (V3_HOLE_WORST, hv, hole_gain))
    if hole_gain >= 10.0 and s45 <= -20.0:
        case = ('CASE 1 - the fold works: hole improved %.1fdB AND S21@4.5 still passes at %.2fdB. '
                'Schedule a proper discrete confirmation run.' % (hole_gain, s45))
    elif hole_gain >= 10.0:
        case = ('CASE 2 - partial win: hole improved %.1fdB but S21@4.5 degraded to %.2fdB, past the '
                '-20dB line. Needs a length trim.' % (hole_gain, s45))
    elif abs(hole_gain) <= 3.0:
        case = ('CASE 3 - hole essentially unchanged (%+.1fdB). Separation was not the mechanism, or '
                '4915um is still too close. Fall back to the tee-move option.' % hole_gain)
    elif hole_gain < 0 and s45 > V3_S21_AT_4P5:
        case = ('CASE 4 - worse across the board (hole %+.1fdB, S21@4.5 %+.2fdB vs v3). '
                'Revert to v3 (tag filter_BB_v3).' % (hole_gain, s45 - V3_S21_AT_4P5))
    else:
        case = ('BETWEEN CASES - hole %+.1fdB, S21@4.5 %+.2fdB vs v3. Report both, no clean rule fires.'
                % (hole_gain, s45 - V3_S21_AT_4P5))
    print('DECISION: %s' % case)
    print('=' * 70)

    if bf is not None:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(11, 6))
            m = (bf >= PROBE_START_GHZ) & (bf <= PROBE_STOP_GHZ)
            ax.plot(bf[m], bs[m], lw=1.2, color='#888888',
                    label='v3 (L-stub, S1<->S3 783um)')
            ax.plot(freqs, s21, lw=1.4, color='#1f5fa0',
                    label='v3f_singlefold (S1<->S3 4915um)')
            ax.axvline(4.5, color='#c02020', ls='--', lw=1.0, alpha=0.8)
            ax.annotate('4.5GHz SNAIL', xy=(4.5, -5), color='#c02020', fontsize=9,
                        rotation=90, va='top', ha='right')
            ax.axhline(-20, color='#c02020', ls=':', lw=0.9, alpha=0.6)
            ax.axvspan(4.7, 5.3, color='#f0c040', alpha=0.18, label='the 4.7-5.3GHz hole')
            ax.set_xlabel('frequency (GHz)')
            ax.set_ylabel('S21 (dB)')
            ax.set_title('Rev 18 directional probe: S1 refolded away from S3 (looser mesh than v3)')
            ax.set_xlim(PROBE_START_GHZ, PROBE_STOP_GHZ)
            ax.grid(alpha=0.25)
            ax.legend(loc='lower right', fontsize=9)
            png = os.path.join(out_dir, '%s_overlay.png' % OUT_PREFIX)
            fig.tight_layout()
            fig.savefig(png, dpi=140)
            print('overlay plot -> %s' % png)
        except Exception as exc:
            print('overlay plot failed (%s) - numbers above are unaffected' % exc)
    else:
        print('no %s_S21.csv baseline found - overlay skipped' % BASELINE_PREFIX)


if __name__ == '__main__':
    main()
