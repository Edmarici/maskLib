#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 21 - assess the S6 fan. Compares any two S21 CSVs at matched mesh.

  python filter_BB_fan_assess.py [baseline_prefix] [fanned_prefix]
  defaults: v6_s6move (no fan)  vs  v8_s6fan (fan)

WHY THIS IS WRITTEN ATTRIBUTION-FREE
------------------------------------
An earlier draft of this file located "S6's zero" and measured its width and
displacement. That framing did not survive the solve. The fan did not move a
zero - it DISSOLVED one: the -102dB notch at 5.900GHz is gone, replaced by a
broad -24 to -30dB shelf across 5.65-6.10GHz, and the nulls that remain nearby
cannot be assigned to S6 without new deletion tests. Any metric anchored on
"the zero" is therefore either undefined or silently measures a neighbour.

Everything below is instead computed from the trace itself with no ownership
claim:

  robustness  - shift the whole local trace by +/-1% of the mode frequency and
                take the worst. A 1% stub-length error shifts the response that
                stub controls by ~1% in frequency (1/L scaling, confirmed twice
                on real solves), so this is the right proxy and needs no
                knowledge of which stub owns what.
  flatness    - peak-to-peak swing over the mode +/-100MHz. This is the
                quantity a fan is bought to improve.
  worst peak  - the highest transmission peak near the mode and its distance,
                since that is the feature that bites when anything shifts.

Absolute-threshold notch widths are deliberately NOT used: the composite floor
here is already below -30dB over wide spans, so an absolute threshold measures
the neighbouring stubs rather than the stub of interest (master notes Sec 2.3).
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'HFSS')

PASS_DB = -20.0
LEN_ERR = 0.01          # the single-stub tolerance case from Rev 21 Q2
FLAT_HALFWIDTH = 0.100  # GHz, for the flatness metric

COMB = [(4.500, 'buffer 1', 0.15), (5.000, 'buffer 2', 0.15),
        (5.792, 'storage 1', None), (6.160, 'storage 2', None),
        (6.528, 'storage 3', None), (6.897, 'storage 4', None),
        (7.265, 'storage 5', None), (7.633, 'storage 6', None),
        (8.001, 'storage 7', None)]


def load(prefix):
    p = os.path.join(OUT, '%s_S21.csv' % prefix)
    if not os.path.exists(p):
        raise SystemExit('%s not found' % p)
    f, s = [], []
    for r in csv.DictReader(open(p)):
        f.append(float(r['freq_ghz'])); s.append(float(r['S21_dB']))
    return np.array(f), np.array(s)


def at_mode(f, s, f0, tol, shift=0.0):
    grid = np.arange(f0 - tol, f0 + tol + 1e-9, 0.005) if tol else np.array([f0])
    return float(np.interp(grid - shift, f, s).max())


def worst_over_tolerance(f, s, f0, tol):
    sh = LEN_ERR * f0
    return max(at_mode(f, s, f0, tol, x) for x in (0.0, sh, -sh))


def flatness(f, s, f0):
    m = (f >= f0 - FLAT_HALFWIDTH) & (f <= f0 + FLAT_HALFWIDTH)
    return float(s[m].max() - s[m].min())


def worst_peak_near(f, s, f0, span=0.5):
    m = (f >= f0 - span) & (f <= f0 + span)
    ff, ss = f[m], s[m]
    i = int(np.argmax(ss))
    return float(ss[i]), float(ff[i])


def nulls(f, s, depth=-15.0):
    return [(float(f[i]), float(s[i])) for i in range(1, len(f) - 1)
            if s[i] < s[i - 1] and s[i] < s[i + 1] and s[i] < depth]


def main(argv):
    pa = argv[0] if len(argv) > 0 else 'v6_s6move'
    pb = argv[1] if len(argv) > 1 else 'v8_s6fan'
    fa, sa = load(pa)
    fb, sb = load(pb)

    print('=' * 78)
    print('S6 FAN ASSESSMENT   %s (no fan)  vs  %s (fan)' % (pa, pb))
    print('  both must be the same mesh and the same drawn length - the fan is')
    print('  intended to be the only variable.')
    print('=' * 78)

    print('\nMODE COMB - nominal, and worst under a +/-%.0f%% length error'
          % (100 * LEN_ERR))
    print('  %-11s %8s %9s %9s   %9s %9s   %s'
          % ('mode', 'GHz', 'nom A', 'nom B', 'worst A', 'worst B', 'B verdict'))
    failA = failB = 0
    for f0, lbl, tol in COMB:
        na, nb = at_mode(fa, sa, f0, tol), at_mode(fb, sb, f0, tol)
        wa, wb = worst_over_tolerance(fa, sa, f0, tol), worst_over_tolerance(fb, sb, f0, tol)
        failA += wa > PASS_DB
        failB += wb > PASS_DB
        print('  %-11s %8.3f %9.2f %9.2f   %9.2f %9.2f   %s'
              % (lbl, f0, na, nb, wa, wb, 'PASS' if wb <= PASS_DB else 'FLAG'))
    print('  under tolerance: A %d/9 pass, B %d/9 pass' % (9 - failA, 9 - failB))

    print('\nROBUSTNESS AND FLATNESS, per mode')
    print('  %-11s %11s %11s   %11s %11s'
          % ('mode', 'swing A', 'swing B', 'flatness A', 'flatness B'))
    for f0, lbl, tol in COMB:
        sh = LEN_ERR * f0
        va = [at_mode(fa, sa, f0, tol, x) for x in (0.0, sh, -sh)]
        vb = [at_mode(fb, sb, f0, tol, x) for x in (0.0, sh, -sh)]
        print('  %-11s %11.2f %11.2f   %11.2f %11.2f'
              % (lbl, max(va) - min(va), max(vb) - min(vb),
                 flatness(fa, sa, f0), flatness(fb, sb, f0)))
    print('  swing    = dB spread at the mode as the trace shifts +/-1%')
    print('  flatness = dB peak-to-peak over the mode +/-%.0fMHz'
          % (FLAT_HALFWIDTH * 1000))

    print('\nWORST TRANSMISSION PEAK within 500MHz of each mode')
    print('  %-11s %20s %20s' % ('mode', 'A', 'B'))
    for f0, lbl, _t in COMB:
        pa_db, pa_f = worst_peak_near(fa, sa, f0)
        pb_db, pb_f = worst_peak_near(fb, sb, f0)
        print('  %-11s %9.2fdB @%.3f %9.2fdB @%.3f' % (lbl, pa_db, pa_f, pb_db, pb_f))

    print('\nNULLS (label-independent, no ownership claimed)')
    print('  A: %s' % ', '.join('%.3f(%.0f)' % p for p in nulls(fa, sa)))
    print('  B: %s' % ', '.join('%.3f(%.0f)' % p for p in nulls(fb, sb)))
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
