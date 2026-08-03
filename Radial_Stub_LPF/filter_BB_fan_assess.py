#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 21 - assess the S6 fan against HFSS/v8_prediction_locked.md.

Mesh-matched one-variable diff: v6_s6move (probe mesh, 7379.3227um drawn, NO
fan) against v8_s6fan (same mesh, same drawn length, WITH the 300um fan).

WIDTH METRIC. Absolute-threshold widths are meaningless in this cascade - the
composite floor is already below -30dB across 5.6-6.1GHz, so an absolute
threshold measures the NEIGHBOURING stubs rather than S6 (master notes Sec.
2.3). Width is therefore measured against the LOCAL COMPOSITE BASELINE: the
mean of S21 over +/-0.25..0.5GHz around the zero, excluding the zero itself -
the same convention filter_BB_fold_experiment_HFSS.minus3db_width() uses.

The headline question is not "did the zero move" but "is storage 1 still
protected when S6's length is wrong by 1%". That is the Q2 fragility the fan
was added to fix, and it is checked directly.
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'HFSS')
BASE = os.path.join(OUT, 'v6_s6move_S21.csv')      # no fan
FAN = os.path.join(OUT, 'v8_s6fan_S21.csv')        # with fan

PASS_DB = -20.0
STORAGE1 = 5.792
COMB = [(4.500, 'buffer 1', 0.15), (5.000, 'buffer 2', 0.15),
        (5.792, 'storage 1', None), (6.160, 'storage 2', None),
        (6.528, 'storage 3', None), (6.897, 'storage 4', None),
        (7.265, 'storage 5', None), (7.633, 'storage 6', None),
        (8.001, 'storage 7', None)]


def load(p):
    f, s = [], []
    for r in csv.DictReader(open(p)):
        f.append(float(r['freq_ghz'])); s.append(float(r['S21_dB']))
    return np.array(f), np.array(s)


def find_zero(f, s, lo, hi):
    m = (f >= lo) & (f <= hi)
    i = int(np.argmin(s[m]))
    return float(f[m][i]), float(s[m][i])


def local_width(f, s, f0, drop=3.0):
    bm = (((f >= f0 - 0.5) & (f <= f0 - 0.25)) | ((f >= f0 + 0.25) & (f <= f0 + 0.5)))
    if not bm.any():
        return None, None
    base = float(np.mean(s[bm]))
    th = base - drop
    ci = int(np.argmin(np.abs(f - f0)))
    lo = hi = ci
    while lo > 0 and s[lo] <= th:
        lo -= 1
    while hi < len(f) - 1 and s[hi] <= th:
        hi += 1
    return base, (f[hi] - f[lo]) * 1000.0


def score(f, s):
    out = []
    for f0, lbl, tol in COMB:
        grid = np.arange(f0 - tol, f0 + tol + 1e-9, 0.005) if tol else np.array([f0])
        out.append(float(np.interp(grid, f, s).max()))
    return out


def s6_sensitivity(f, s, f_zero, mode=STORAGE1, d=0.01):
    """S21 at `mode` if S6's length is wrong by +/-d. The zero moves to
    f_zero/(1+d); the local response shifts with it, so the perturbed value at
    `mode` is the measured value at mode - dF."""
    out = {}
    for sign, tag in ((+1, 'longer'), (-1, 'shorter')):
        dF = f_zero / (1 + sign * d) - f_zero
        out[tag] = float(np.interp(mode - dF, f, s))
    return out


def main():
    if not os.path.exists(FAN):
        raise SystemExit('%s not found - the fan solve has not finished' % FAN)
    fb, sb = load(BASE)
    ff, sf = load(FAN)

    z_b, d_b = find_zero(fb, sb, 5.60, 6.10)
    z_f, d_f = find_zero(ff, sf, 5.55, 6.10)
    base_b, w_b = local_width(fb, sb, z_b)
    base_f, w_f = local_width(ff, sf, z_f)

    print('=' * 78)
    print('Rev 21 - S6 FAN, mesh-matched against v6_s6move (same drawn length, no fan)')
    print('=' * 78)
    print('%-34s %14s %14s' % ('', 'NO FAN', 'WITH FAN'))
    print('%-34s %14.3f %14.3f' % ('S6 zero (GHz)', z_b, z_f))
    print('%-34s %14.1f %14.1f' % ('  depth (dB)', d_b, d_f))
    print('%-34s %14.1f %14.1f' % ('  local baseline (dB)', base_b, base_f))
    print('%-34s %14.0f %14.0f' % ('  width, -3dB vs baseline (MHz)', w_b, w_f))
    for drop in (6.0, 10.0):
        _, a = local_width(fb, sb, z_b, drop)
        _, c = local_width(ff, sf, z_f, drop)
        print('%-34s %14.0f %14.0f' % ('  width, -%.0fdB vs baseline (MHz)' % drop, a, c))
    print('%-34s %+14.3f %s' % ('  offset from storage 1 (GHz)', z_b - STORAGE1,
                                '%+14.3f' % (z_f - STORAGE1)))

    print()
    print('MODE-COMB, both probe mesh')
    sb_sc, sf_sc = score(fb, sb), score(ff, sf)
    print('  %-11s %8s %10s %10s %9s  %s' % ('mode', 'GHz', 'no fan', 'with fan', 'change', 'verdict'))
    nfail = 0
    for i, (f0, lbl, _t) in enumerate(COMB):
        v = sf_sc[i]
        ok = v <= PASS_DB
        nfail += (not ok)
        print('  %-11s %8.3f %10.2f %10.2f %+9.2f  %s'
              % (lbl, f0, sb_sc[i], v, v - sb_sc[i], 'PASS' if ok else 'FLAG'))
    print('  ---> %d/9 PASS' % (9 - nfail))

    print()
    print('THE HEADLINE: storage 1 under a +/-1%% S6 length error'.replace('%%', '%'))
    a = s6_sensitivity(fb, sb, z_b)
    b = s6_sensitivity(ff, sf, z_f)
    print('  %-22s %12s %12s' % ('', 'NO FAN', 'WITH FAN'))
    print('  %-22s %12.2f %12.2f' % ('nominal', np.interp(STORAGE1, fb, sb),
                                     np.interp(STORAGE1, ff, sf)))
    for tag in ('longer', 'shorter'):
        print('  %-22s %12.2f %12.2f' % ('S6 1%% %s' % tag, a[tag], b[tag]))
    wa, wb = max(a.values()), max(b.values())
    print('  %-22s %12.2f %12.2f' % ('WORST', wa, wb))
    print('  %-22s %12.2f %12.2f' % ('margin vs -20dB', PASS_DB - wa, PASS_DB - wb))
    print('  -> %s' % ('FRAGILITY FIXED' if wb <= PASS_DB else
                       'STILL FAILS under a 1% S6 error'))

    print()
    print('PREDICTION SCORECARD (HFSS/v8_prediction_locked.md)')
    checks = [
        ('1 zero in 5.75-5.88', 5.75 <= z_f <= 5.88, '%.3f GHz' % z_f),
        ('2 storage 1 better than -30', sf_sc[2] < -30, '%.2f dB' % sf_sc[2]),
        ('3 width >= 160 MHz', w_f >= 160, '%.0f MHz (was %.0f)' % (w_f, w_b)),
        ('4 storage 1 worst <= -20', wb <= PASS_DB, '%.2f dB' % wb),
        ('5 7.515 zero moved', None, 'see null list'),
        ('6 still 9/9', nfail == 0, '%d/9' % (9 - nfail)),
    ]
    hit = 0
    for name, ok, val in checks:
        if ok is None:
            print('  %-30s %-10s %s' % (name, 'n/a', val))
        else:
            hit += ok
            print('  %-30s %-10s %s' % (name, 'HIT' if ok else 'MISS', val))
    print('  -> %d of 5 testable predictions hit' % hit)

    print()
    nl = [(float(ff[i]), float(sf[i])) for i in range(1, len(ff) - 1)
          if sf[i] < sf[i - 1] and sf[i] < sf[i + 1] and sf[i] < -15]
    print('NULLS with the fan (%.1f-%.1fGHz): %s'
          % (ff.min(), ff.max(), ', '.join('%.3f(%.0fdB)' % p for p in nl)))
    nlb = [(float(fb[i]), float(sb[i])) for i in range(1, len(fb) - 1)
           if sb[i] < sb[i - 1] and sb[i] < sb[i + 1] and sb[i] < -15]
    print('NULLS without      : %s' % ', '.join('%.3f(%.0fdB)' % p for p in nlb))
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
