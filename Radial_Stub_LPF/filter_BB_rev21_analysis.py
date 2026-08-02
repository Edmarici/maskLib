#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 21 Q2/Q3/Q4 - close-out analysis of the frozen passing configuration.

NO SOLVES. Everything here is computed from artifacts already on disk:
HFSS/v6_confirm_S21.csv (tight mesh, delta_S 0.0018621) and
HFSS/filter_BB_dims.json. Run it against the filter_BB_v4_pass9of9 tag.

WHY THE SENSITIVITY IS NOT DONE IN THE ABCD CIRCUIT MODEL
---------------------------------------------------------
The handoff asks for circuit-model screening. For the two GLOBAL
perturbations there is something strictly better available, and it is not a
shortcut: a uniform change in every length, or in eps_eff, rescales the whole
S21(f) response in frequency for a non-dispersive TEM structure. So the
perturbed scorecard is the MEASURED tight-mesh curve resampled - exact to
that approximation, with no model fitting anywhere. filter_BB_circuit_model.py
did not validate as a forward predictor (Rev 16) and produces one pole per
stub, which cannot represent this cascade's measured null structure.

The two LOCAL perturbations are weaker and are labelled as such in the output.

SIGN CONVENTION, stated once and used throughout
------------------------------------------------
  length L -> L(1+d)     =>  a null at f0 moves to f0/(1+d)
  eps_eff -> eps(1+e)    =>  every null moves to f0/sqrt(1+e)
  a null moving f0 -> f0+dF shifts the local response by +dF, so the
  perturbed response at frequency fm equals the measured response at fm-dF.

An earlier version of the single-stub estimate applied every null's shift to
every mode, which made a 1% error in the 8.730GHz stub appear to cost buffer 1
17dB. It cannot: that null does not control the response at 4.5GHz. Only the
nearest null is applied to each mode now, and the mode-to-null distance is
printed so the reader can judge where the approximation is thin.
"""
import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, 'HFSS')
SWEEP = os.path.join(OUT_DIR, 'v6_confirm_S21.csv')
DIMS = os.path.join(OUT_DIR, 'filter_BB_dims.json')

C_UM_GHZ = 2.998e5
EPS_EFF = 5.681
PASS_DB = -20.0

COMB = [(1, 4.500, 'buffer 1', 0.15), (2, 5.000, 'buffer 2', 0.15),
        (3, 5.792, 'storage 1', None), (4, 6.160, 'storage 2', None),
        (5, 6.528, 'storage 3', None), (6, 6.897, 'storage 4', None),
        (7, 7.265, 'storage 5', None), (8, 7.633, 'storage 6', None),
        (9, 8.001, 'storage 7', None)]

# Passing-configuration nulls over 0.5-14GHz, with ownership and HOW ownership
# was established. "deletion" = a stub was removed and this null vanished.
# "assigned" = never tested; the campaign's record on untested assignments is
# 0 for 4, so these are explicitly not to be relied on (DESIGN_NOTES sec 14).
NULLS = [
    (4.370, 'S1', 'deletion',  'Rev19 B1 removed S1 and 4.325 vanished; tracked the Rev20 trim to 5MHz'),
    (4.870, 'S2', 'assigned',  'never deletion-tested'),
    (5.470, 'S3', 'assigned',  'never deletion-tested'),
    (5.900, 'S6', 'deletion',  'Rev19 B4 removed S6 and this null vanished; moved with S6 length in Rev20 B3'),
    (6.970, 'S4', 'deletion',  'Rev19 B1b census removed S4 and 6.890 vanished'),
    (7.550, '?',  'unknown',   'needs S6 present (vanishes on S6 deletion) but ignores S6 length - Rev21 Q1'),
    (8.730, 'S5', 'assigned',  'never deletion-tested'),
    (9.965, '-',  'unowned',   'survived S6 deletion AND three S6 lengths - explicitly NOT S6'),
    (11.360, '-', 'unowned',   'moved +2.3% while S6 grew 1.911x - not S6'),
    (12.375, '-', 'unowned',   'moved -1.3% while S6 grew 1.911x - not S6'),
]


def load_sweep():
    f, s = [], []
    for r in csv.DictReader(open(SWEEP)):
        f.append(float(r['freq_ghz'])); s.append(float(r['S21_dB']))
    return np.array(f), np.array(s)


def score(f, s, shift_fn):
    """shift_fn(fm) -> dF, the amount the controlling null moves. Perturbed
    response at fm is the measured response at fm - dF."""
    out = []
    for _idx, f0, _lbl, tol in COMB:
        grid = np.arange(f0 - tol, f0 + tol + 1e-9, 0.005) if tol else np.array([f0])
        out.append(float(np.interp(grid - shift_fn(f0), f, s).max()))
    return out


def bare_ghz(length_um):
    return C_UM_GHZ / (4.0 * length_um * math.sqrt(EPS_EFF))


def main():
    f, s = load_sweep()
    print('=' * 78)
    print('Rev 21 close-out analysis - frozen configuration filter_BB_v4_pass9of9')
    print('  source: %s (%d pts, %.2f-%.2f GHz, tight mesh)'
          % (os.path.basename(SWEEP), len(f), f.min(), f.max()))
    print('=' * 78)

    nominal = score(f, s, lambda f0: 0.0)

    # ---------------------------------------------------------------- Q3
    print('\nQ3 - BUFFER MODES ACROSS THEIR STATED +/-0.15GHz UNCERTAINTY')
    print('(no new solve; the scorecard already scores these rows as a worst-case)')
    for f0, lbl, lo, hi in ((4.500, 'buffer 1', 4.35, 4.65), (5.000, 'buffer 2', 4.85, 5.15)):
        m = (f >= lo) & (f <= hi)
        sub_f, sub_s = f[m], s[m]
        i = int(np.argmax(sub_s))
        print('  %-9s [%.2f, %.2f] GHz, %d solved pts: nominal %+.2f, WORST %+.2f @ %.3f GHz -> %s (%+.2f dB)'
              % (lbl, lo, hi, m.sum(), float(np.interp(f0, f, s)), sub_s[i], sub_f[i],
                 'PASS' if sub_s[i] <= PASS_DB else 'FAIL', PASS_DB - sub_s[i]))

    # ---------------------------------------------------------------- Q2
    print('\nQ2 - SENSITIVITY')
    print('\n  (a) GLOBAL perturbations - exact frequency rescale of the measured curve')
    cases = [('all lengths +0.25%', lambda f0: f0 * (1 / 1.0025 - 1)),
             ('all lengths -0.25%', lambda f0: f0 * (1 / 0.9975 - 1)),
             ('eps_eff +1%', lambda f0: f0 * (1 / math.sqrt(1.01) - 1)),
             ('eps_eff -1%', lambda f0: f0 * (1 / math.sqrt(0.99) - 1))]
    hdr = ''.join('%8s' % c[2].replace('storage', 'st').replace('buffer', 'bf') for c in COMB)
    print('      %-20s%s' % ('case', hdr))
    print('      %-20s%s' % ('nominal', ''.join('%8.2f' % v for v in nominal)))
    worst = list(nominal)
    for lbl, fn in cases:
        v = score(f, s, fn)
        worst = [max(a, b) for a, b in zip(worst, v)]
        print('      %-20s%s' % (lbl, ''.join('%8.2f' % x for x in v)))
    print('      %-20s%s' % ('WORST', ''.join('%8.2f' % x for x in worst)))
    print('      %-20s%s' % ('margin', ''.join('%+8.2f' % (PASS_DB - x) for x in worst)))
    bad = [COMB[i][2] for i in range(9) if worst[i] > PASS_DB]
    print('      -> below 20dB under any global perturbation: %s' % (', '.join(bad) if bad else 'NONE'))

    print('\n  (b) SINGLE-STUB 1% length error - nearest-null local shift (approximate)')
    print('      %-11s %7s %8s %9s %9s   %s' % ('mode', 'GHz', 'nominal', 'worst', 'margin', 'nearest null'))
    rows = []
    for i, (_idx, f0, lbl, tol) in enumerate(COMB):
        grid = np.arange(f0 - tol, f0 + tol + 1e-9, 0.005) if tol else np.array([f0])
        nf, owner = min(((n[0], n[1]) for n in NULLS), key=lambda p: abs(p[0] - f0))
        w = max(float(np.interp(grid - (nf / (1 + d) - nf), f, s).max()) for d in (0.01, -0.01))
        rows.append((lbl, nominal[i], w))
        print('      %-11s %7.3f %8.2f %9.2f %+9.2f   %.3f (%s), %.0f MHz away'
              % (lbl, f0, nominal[i], w, PASS_DB - w, nf, owner, abs(nf - f0) * 1000))
    bad2 = [r[0] for r in rows if r[2] > PASS_DB]
    print('      -> below 20dB: %s' % (', '.join(bad2) if bad2 else 'NONE'))

    print('\n  (c) LINEWIDTH +/-5um - from the validated extraction, not modelled')
    print('      epseff_extraction_status.md records the field-plot-verified 6GHz point:')
    print('        w=70um  eps_eff 5.6795  Zpi 69.71 ohm')
    print('        w=125um eps_eff 5.6826  Zpi 69.70 ohm')
    print('      A 55um width change moves eps_eff <0.1% and Zpi ~0.01%. A +/-5um bias')
    print('      is ~1/11 of that, so <0.01% on both - negligible against the +/-1%')
    print('      eps_eff case above, which already passes. Expected physically: with no')
    print('      ground plane the mode is set by the bore, not the strip width.')
    print('      NOTE the same file records that the SWEPT eps_eff(f) data is')
    print('      non-physical and untrusted; only the 6GHz point is in use.')

    # ---------------------------------------------------------------- Q4
    print('\nQ4 - DATA FOR THE NOTE')
    dims = json.load(open(DIMS))
    print('\n  (1) stub table')
    print('      %-7s %-8s %14s %6s %8s %9s %9s %8s' %
          ('stub', 'label', 'realized um', 'runs', 'gap um', 'd_perp um', 'tee y um', 'fold'))
    stub_rows = []
    for i, st in enumerate(dims['stubs'], start=1):
        print('      S%-6d %-8s %14.7f %6d %8.0f %9.0f %9.1f %+8d'
              % (i, st['label'], st['realized_length_um'], st['n_par_runs'],
                 st['run_gap_um'], st['d_perp_um'], st['tee_pos_um'][1], st['fold_dir']))
        stub_rows.append(dict(stub='S%d' % i, label=st['label'],
                              realized_um='%.7f' % st['realized_length_um'],
                              n_par_runs=st['n_par_runs'], run_gap_um='%.0f' % st['run_gap_um'],
                              d_perp_um='%.0f' % st['d_perp_um'],
                              tee_y_um='%.1f' % st['tee_pos_um'][1], fold_dir=st['fold_dir'],
                              side=st['side'], w_um='%.0f' % st['w_um']))

    print('\n  (2) null inventory, 0.5-14GHz, with HOW ownership was established')
    for fz, owner, how, note in NULLS:
        print('      %7.3f GHz  %-3s  %-9s  %s' % (fz, owner, how, note))
    nd = sum(1 for n in NULLS if n[2] == 'deletion')
    print('      -> %d of %d deletion-confirmed; %d assigned but never tested; %d unowned.'
          % (nd, len(NULLS), sum(1 for n in NULLS if n[2] == 'assigned'),
             sum(1 for n in NULLS if n[2] == 'unowned')))

    print('\n  (3) k_eff on ONE definition')
    print('      DEFINITION A (used everywhere, verified below): k_eff = f_bare / f_null,')
    print('      f_bare = c/(4*L*sqrt(eps_eff)) with L = drawn centreline INCLUDING arc')
    print('      length, i.e. d_perp + turn_arc + n*run_length - the quantity')
    print('      folded_stub() solves and dims JSON reports as realized_length_um.')
    keff = [
        ('foldexp 3run/400um', 6987.9007621, 6.830, 'isolated, Rev17 B2'),
        ('foldexp 2run/1000um', 6987.9007621, 5.680, 'isolated, Rev17 B2'),
        ('foldexp L-geometry', 6987.9007621, 5.050, 'isolated, Rev17 B2'),
        ('foldexp straight', 6987.9007621, 5.450, 'isolated, WIDE bore - not comparable'),
        ('S6 topology 2run/400um', 6436.9031508, 6.780, 'isolated, Rev20 B2'),
        ('S6 in cascade, old len', 6436.9031508, 6.640, 'cascade, Rev19 B4'),
        ('S6 in cascade, frozen', 7379.3226508, 5.900, 'cascade, Rev20 confirm'),
        ('S1 in cascade, pre-trim', 8820.2836286, 4.340, 'cascade, Rev19 B3'),
        ('S1 in cascade, frozen', 8749.7213596, 4.370, 'cascade, Rev20 confirm'),
        ('S2 in cascade, frozen', 9776.0927822, 4.870, 'cascade, ASSIGNED not tested'),
    ]
    print('      %-26s %13s %8s %8s   %s' % ('case', 'L um', 'null', 'k_eff', 'provenance'))
    keff_rows = []
    for lbl, L, null, src in keff:
        k = bare_ghz(L) / null
        print('      %-26s %13.4f %8.3f %8.4f   %s' % (lbl, L, null, k, src))
        keff_rows.append(dict(case=lbl, length_um='%.4f' % L, null_ghz='%.3f' % null,
                              k_eff='%.4f' % k, provenance=src))
    print('      RESOLVED: the suspected length-reference discrepancy does NOT exist.')
    print('      Every k_eff quoted in DESIGN_NOTES recomputes to <0.002 under')
    print('      definition A. The alternative (straight runs only, arcs excluded)')
    print('      would give k_eff > 1 for two cases, which is unphysical under the')
    print('      fold-cancellation reading, so it was never in use.')
    print('      The REAL inconsistency is the numerator: S6 was quoted at 0.6886,')
    print('      computed against the geometric MEAN of a null PAIR, while every other')
    print('      entry uses a measured null. That pair reading is withdrawn')
    print('      (sec 18.3), so 0.6886 is retired and replaced by 0.7357 (old length)')
    print('      / 0.7223 (frozen length). A second case: sec 14 quotes S2 at 0.664,')
    print('      which is 4.845GHz not the 4.760GHz the same sentence cites - again a')
    print('      numerator mismatch, not a length one.')

    print('\n  (4) mesh calibration')
    print('      probe (dS 0.02, ~1h) vs tight (dS 0.005, ~7h), measured on TWO geometries:')
    print('        Rev20 B1, pre-move geometry : mean 0.61 dB, worst 2.25 dB')
    print('        Rev20 B3, frozen geometry   : mean 0.45 dB, worst 1.85 dB')
    print('      worst row is buffer 2 both times - it is a worst-across-window row, so')
    print('      it samples wherever the grid lands. Scorecard work can use probe mesh.')
    print('      NULL POSITIONS are the exception: probe reads them a mean 14MHz (worst')
    print('      35MHz) LOW, same direction at all seven nulls, because an Interpolating')
    print('      sweep reconstructs sharp minima poorly. Length decisions need the')
    print('      discrete window.')

    for name, rows_out in (('rev21_stub_table.csv', stub_rows), ('rev21_keff_table.csv', keff_rows)):
        p = os.path.join(OUT_DIR, name)
        with open(p, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
            w.writeheader(); w.writerows(rows_out)
        print('\n  wrote %s' % p)
    p = os.path.join(OUT_DIR, 'rev21_null_inventory.csv')
    with open(p, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['freq_ghz', 'owner', 'how_established', 'note'])
        w.writerows(NULLS)
    print('  wrote %s' % p)
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
