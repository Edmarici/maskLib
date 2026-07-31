#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 19 B3 - confirmation solve for the retargeted geometry (S6 8.0 -> 5.98GHz).

A DEDICATED DRIVER rather than filter_BB_firstlight_HFSS.main(), on purpose:
that function still computes and prints the criteria Rev 19 retired - worst
S21 across 4.2-8.0GHz, the inter-zero valley table, and the Rev 12/13
verdicts. Under a mode-comb spec, peaks BETWEEN modes cost nothing, so those
numbers are not merely redundant, they actively mislead (v3's 4.910GHz hole
read as a failure under the old criterion and is irrelevant under the new
one). This reports only what the Rev 19 handoff asks for.

MESH IS MATCHED TO v3, which is the whole point of a confirmation run:
multi-frequency adaptive at 3.5/5.5/8.0GHz, delta_S 0.005. Every Rev 18/19
directional run so far used a single adaptive point at delta_S 0.02, so none
of them could be compared to v3 on absolute dB. If the multi-frequency setup
fails (it has fallen back on every previous attempt in this project), the
fallback is a single point at 3.5GHz - which is still v3's own adaptive
frequency, so the comparison survives either way. The log says which happened.

Deliverables, per the handoff: the 9-row comb scorecard (the headline),
label-independent null enumeration, S21 at 3.5GHz for drive-band delivery
(unreported since Rev 17), passband ripple, and anything above -30dB in
8-14GHz.
"""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filter_BB_firstlight_HFSS as FL  # noqa: E402
from filter_BB_comb_score import COMB, PASS_DB  # noqa: E402

DESIGN_NAME = 'Rev19_B3_Confirm'
OUT_PREFIX = 'v4_comb'

COARSE_START_GHZ = 0.5
COARSE_STOP_GHZ = 14.0
COARSE_COUNT = 2701          # 5MHz
DISCRETE_START_GHZ = 4.2
DISCRETE_STOP_GHZ = 8.2
DISCRETE_STEP_GHZ = 0.01     # 10MHz, real solved points across the comb
DISCRETE_COUNT = int(round((DISCRETE_STOP_GHZ - DISCRETE_START_GHZ) / DISCRETE_STEP_GHZ)) + 1

CONFIRM_MAX_DELTA_S = 0.005  # v3 reached 0.0037; this is the matched setting

PASSBAND_SPOTS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.3, 3.5]
EXPECT_S6_LEN_UM = 6436.9032


def nulls(f, s, lo, hi, depth=-15.0):
    return [(float(f[i]), float(s[i])) for i in range(1, len(f) - 1)
            if lo <= f[i] <= hi and s[i] < s[i - 1] and s[i] < s[i + 1] and s[i] < depth]


def main():
    project = FL.connect_project()
    desktop = FL.HFSS.HfssApp().get_app_desktop()
    same = [p for p in desktop.get_projects() if p.name == FL.PROJECT_NAME]
    print('AEDT handles named %r open: %d%s'
          % (FL.PROJECT_NAME, len(same), '  <== MORE THAN ONE' if len(same) > 1 else ''))

    geom = FL._load_geometry()
    dims = FL._load_dims()
    s6 = dims['stubs'][-1]
    print('S6 under test: label %s, target %.2fGHz, realized %.4fum, fold_dir %+d'
          % (s6['label'], s6['f_target_ghz'], s6['realized_length_um'], s6['fold_dir']))
    assert abs(s6['realized_length_um'] - EXPECT_S6_LEN_UM) < 1e-3, (
        'S6 realized %.4fum != Rev 19 target %.4fum - stale dims JSON, re-run filter_BB.py'
        % (s6['realized_length_um'], EXPECT_S6_LEN_UM))

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HFSS')
    FL.MAX_DELTA_S = CONFIRM_MAX_DELTA_S
    specs = [
        dict(name='Coarse_Sweep', type='Interpolating',
             start=COARSE_START_GHZ, stop=COARSE_STOP_GHZ, count=COARSE_COUNT),
        dict(name='Discrete_Window', type='Discrete',
             start=DISCRETE_START_GHZ, stop=DISCRETE_STOP_GHZ, count=DISCRETE_COUNT),
    ]
    design, setup, sweeps = FL.build_design(project, DESIGN_NAME, geom, specs, adaptive='multi')
    print('solving %s (delta_S %.4f, multi-freq %s attempted)...'
          % (DESIGN_NAME, CONFIRM_MAX_DELTA_S, FL.MULTI_FREQ_ADAPTIVE_GHZ))
    setup.analyze()

    rows = FL.export_convergence(design, setup.name, out_dir)
    conv = 'unavailable'
    if rows:
        conv = '%d passes, final delta-S %s' % (len(rows), list(rows[-1].values())[-1])
    print('convergence: %s' % conv)

    fc, s21c, s11c = FL.pull_sweep(sweeps['Coarse_Sweep'], out_dir, '_coarse19')
    fd, s21d, s11d = FL.pull_sweep(sweeps['Discrete_Window'], out_dir, '_disc19')
    window = (DISCRETE_START_GHZ, DISCRETE_STOP_GHZ)
    f, s21 = FL.merge_sweep_data(fc, s21c, fd, s21d, window)
    _, s11 = FL.merge_sweep_data(fc, s11c, fd, s11d, window)
    order = np.argsort(f)
    f, s21, s11 = f[order], s21[order], s11[order]

    path = os.path.join(out_dir, '%s_S21.csv' % OUT_PREFIX)
    with open(path, 'w', newline='') as fh:
        wr = csv.writer(fh)
        wr.writerow(['freq_ghz', 'S21_dB', 'S11_dB'])
        for a, b, c in zip(f, s21, s11):
            wr.writerow(['%.6f' % a, '%.6f' % b, '%.6f' % c])
    print('merged S21 -> %s' % path)

    def at(x):
        return float(s21[int(np.argmin(np.abs(f - x)))])

    print('=' * 78)
    print('Rev 19 B3 - confirmation, S6 retargeted 8.0 -> 5.98GHz')
    print('  mesh: delta_S %.4f (v3: 0.0037).  convergence: %s' % (CONFIRM_MAX_DELTA_S, conv))
    print('=' * 78)
    print('MODE-COMB SCORECARD  (PASS = S21 <= %.0fdB; buffer rows = worst across +/-0.15GHz)' % PASS_DB)
    npass = 0
    scorecard = []
    for idx, f0, label, tol in COMB:
        if tol:
            m = (f >= f0 - tol) & (f <= f0 + tol)
            val = float(s21[m].max())
            where = float(f[m][int(np.argmax(s21[m]))])
        else:
            val = at(f0)
            where = f0
        ok = val <= PASS_DB
        npass += ok
        print('  %d  %-11s %6.3f GHz  %+8.2f dB  %-4s  margin %+6.1f dB%s'
              % (idx, label, f0, val, 'PASS' if ok else 'FLAG', PASS_DB - val,
                 '  (worst @%.3f)' % where if tol else ''))
        scorecard.append(dict(index=idx, mode=label, freq_ghz='%.3f' % f0,
                              s21_db='%.2f' % val, verdict='PASS' if ok else 'FLAG',
                              margin_db='%.2f' % (PASS_DB - val)))
    print('  ---> %d/9 PASS' % npass)

    sc_path = os.path.join(out_dir, '%s_comb_scorecard.csv' % OUT_PREFIX)
    with open(sc_path, 'w', newline='') as fh:
        wr = csv.DictWriter(fh, fieldnames=list(scorecard[0].keys()))
        wr.writeheader()
        wr.writerows(scorecard)
    print('  scorecard -> %s' % sc_path)

    print('-' * 78)
    alln = nulls(f, s21, 0.5, 14.0)
    print('NULLS (label-independent, <-15dB, 0.5-14GHz): %d' % len(alln))
    print('  %s' % ', '.join('%.3f(%.0fdB)' % p for p in alln))
    print('  in the comb range 4.2-8.2GHz: %s'
          % ', '.join('%.3f' % p[0] for p in alln if 4.2 <= p[0] <= 8.2))
    print('  DID S6 MOVE? expected a new null near 5.98GHz, and 9.970GHz to vanish:')
    near = [p for p in alln if 5.7 <= p[0] <= 6.3]
    old = [p for p in alln if 9.7 <= p[0] <= 10.2]
    print('    near 5.98 : %s' % (', '.join('%.3f(%.0fdB)' % p for p in near) if near else 'NONE'))
    print('    near 9.97 : %s' % (', '.join('%.3f(%.0fdB)' % p for p in old) if old else 'gone'))
    if near and not old:
        print('    -> CONFIRMED: S6 owned 9.970GHz and has moved as designed.')
    elif near and old:
        print('    -> PARTIAL: a null appeared near 5.98 but 9.97 survives - 9.97 was NOT S6.')
    else:
        print('    -> NOT CONFIRMED: no null near 5.98. The inferred S6 assignment was wrong.')

    print('-' * 78)
    print('DRIVE BAND (0.5-3.5GHz confirmed still the passband this revision):')
    for x in PASSBAND_SPOTS:
        print('  %.1f GHz : %+7.2f dB' % (x, at(x)))
    seg = s21[(f >= 0.5) & (f <= 3.5)]
    print('  S21 @ 3.5GHz = %+.2f dB   (delivery at the top of the drive band)' % at(3.5))
    print('  passband ripple 0.5-3.5GHz: %.2f dB peak-to-peak (best %+.2f, worst %+.2f)'
          % (seg.max() - seg.min(), seg.max(), seg.min()))

    print('-' * 78)
    m = (f >= 8.0) & (f <= 14.0)
    ff, ss = f[m], s21[m]
    pk = [(ff[i], ss[i]) for i in range(1, len(ff) - 1)
          if ss[i] > ss[i - 1] and ss[i] > ss[i + 1] and ss[i] > -30.0]
    print('8-14GHz features above -30dB: %d' % len(pk))
    print('  %s' % (', '.join('%.2f(%.0fdB)' % p for p in pk) if pk else 'none'))
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
