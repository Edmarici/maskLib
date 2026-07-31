#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 19 B0 - score a solved S21 trace against the mode-comb acceptance spec.

The acceptance criterion changed in Rev 19 from continuous band coverage
("worst S21 in 4.2-8.0GHz") to a 9-row table lookup at discrete mode
frequencies. Peaks BETWEEN modes now cost nothing - which is why v3's
4.910GHz hole, the thing Rev 18 was built to fix, may not have mattered.

PASS = at least 20dB of attenuation at the mode (S21 <= -20dB). Above that
earns no extra credit and must not be optimized for. Below it is FLAGGED with
the actual value, not failed - acceptability there depends on the O5 kappa_ext
budget, which is not settled.

The two buffer modes are PENDING SIM and carry +/-0.15GHz of uncertainty, so
for those the reported number is the WORST S21 across the whole window, not
the value at the nominal centre. A narrow 60dB null centred on 4.5GHz that
degrades to -12dB at 4.65GHz is not protection.

Local only - reads committed CSVs, no Ansys.
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, 'HFSS')

PASS_DB = -20.0
BUFFER_TOL_GHZ = 0.15

# (index, freq_ghz, label, tolerance_ghz or None for a fixed mode)
COMB = [
    (1, 4.500, 'buffer 1', BUFFER_TOL_GHZ),
    (2, 5.000, 'buffer 2', BUFFER_TOL_GHZ),
    (3, 5.792, 'storage 1', None),
    (4, 6.160, 'storage 2', None),
    (5, 6.528, 'storage 3', None),
    (6, 6.897, 'storage 4', None),
    (7, 7.265, 'storage 5', None),
    (8, 7.633, 'storage 6', None),
    (9, 8.001, 'storage 7', None),
]

GEOMETRIES = [
    ('probe', 'v3f_singlefold_S21.csv', 'Rev 18 single fold, adaptive 4.7GHz delta-S 0.0102'),
    ('v3', 'v3_confirm_S21.csv', 'Rev 17 L-stub, adaptive 3.5GHz delta-S 0.0037'),
]


def load(path):
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


def score_one(freqs, s21, f0, tol):
    """Returns (reported_db, where_ghz, covered). For a toleranced mode the
    reported value is the WORST across the window - robustness, not depth."""
    if tol is None:
        i = int(np.argmin(np.abs(freqs - f0)))
        if abs(freqs[i] - f0) > 0.02:
            return None, None, False
        return float(s21[i]), float(freqs[i]), True
    m = (freqs >= f0 - tol) & (freqs <= f0 + tol)
    if not m.any():
        return None, None, False
    sub_f, sub_s = freqs[m], s21[m]
    # window must actually be covered by the trace, not clipped at an edge
    covered = (freqs.min() <= f0 - tol + 1e-9) and (freqs.max() >= f0 + tol - 1e-9)
    j = int(np.argmax(sub_s))
    return float(sub_s[j]), float(sub_f[j]), covered


def main():
    traces = {}
    for name, fn, note in GEOMETRIES:
        path = os.path.join(OUT_DIR, fn)
        if not os.path.exists(path):
            print('MISSING: %s (%s) - skipped' % (fn, name))
            continue
        traces[name] = load(path) + (note,)

    if not traces:
        print('no traces found')
        return 1

    names = [n for n, _, _ in GEOMETRIES if n in traces]

    print('=' * 96)
    print('Rev 19 B0 - mode-comb scorecard   (PASS = S21 <= %.0fdB at the mode)' % PASS_DB)
    for n in names:
        print('  %-6s %s' % (n, traces[n][2]))
    print('  NOTE: the two geometries were solved at DIFFERENT mesh settings, so cross-geometry')
    print('        deltas below are indicative only - B3 re-solves at matched mesh.')
    print('  NOTE: buffer rows report the WORST S21 across +/-%.2fGHz, not the value at centre.' % BUFFER_TOL_GHZ)
    print('=' * 96)

    hdr = '%-3s %-11s %-10s' % ('#', 'mode', 'freq(GHz)')
    for n in names:
        hdr += ' | %-28s' % ('%s: S21 / verdict / margin' % n)
    print(hdr)
    print('-' * 96)

    rows = []
    tally = {n: {'pass': 0, 'flag': 0, 'na': 0} for n in names}
    for idx, f0, label, tol in COMB:
        line = '%-3d %-11s %-10.3f' % (idx, label, f0)
        row = {'index': idx, 'mode': label, 'freq_ghz': '%.3f' % f0,
               'tolerance_ghz': ('%.2f' % tol) if tol else ''}
        for n in names:
            freqs, s21, _ = traces[n]
            val, where, covered = score_one(freqs, s21, f0, tol)
            if val is None or not covered:
                line += ' | %-28s' % 'n/a (outside sweep)'
                row['%s_s21_db' % n] = ''
                row['%s_verdict' % n] = 'NO DATA'
                row['%s_margin_db' % n] = ''
                tally[n]['na'] += 1
                continue
            verdict = 'PASS' if val <= PASS_DB else 'FLAG'
            margin = PASS_DB - val          # positive = better than the 20dB line
            tally[n]['pass' if verdict == 'PASS' else 'flag'] += 1
            suffix = ' @%.3f' % where if tol else ''
            line += ' | %8.2fdB %-4s %+7.1fdB%s' % (val, verdict, margin, suffix)
            row['%s_s21_db' % n] = '%.2f' % val
            row['%s_verdict' % n] = verdict
            row['%s_margin_db' % n] = '%.2f' % margin
            row['%s_worst_at_ghz' % n] = '%.3f' % where
        print(line)
        rows.append(row)

    print('-' * 96)
    for n in names:
        t = tally[n]
        print('  %-6s  PASS %d/9   FLAG %d/9   no-data %d' % (n, t['pass'], t['flag'], t['na']))

    # who is ahead, and where each one fails
    print('-' * 96)
    for n in names:
        flags = [(r['mode'], r['freq_ghz'], r['%s_s21_db' % n])
                 for r in rows if r.get('%s_verdict' % n) == 'FLAG']
        if flags:
            print('  %-6s flags at: %s' % (n, ', '.join('%s %sGHz (%sdB)' % f for f in flags)))
        else:
            print('  %-6s flags at: none - passes every mode' % n)

    out_path = os.path.join(OUT_DIR, 'comb_scorecard.csv')
    fieldnames = ['index', 'mode', 'freq_ghz', 'tolerance_ghz']
    for n in names:
        fieldnames += ['%s_s21_db' % n, '%s_verdict' % n, '%s_margin_db' % n, '%s_worst_at_ghz' % n]
    with open(out_path, 'w', newline='') as fh:
        wr = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction='ignore')
        wr.writeheader()
        wr.writerows(rows)
    print('-' * 96)
    print('scorecard -> %s' % out_path)
    print('=' * 96)
    return 0


if __name__ == '__main__':
    sys.exit(main())
