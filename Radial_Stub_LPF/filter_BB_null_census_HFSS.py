#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 19 B1b - full-range null census, and the S4 deletion test.

TWO QUESTIONS, ONE SCRIPT, DELIBERATELY MESH-MATCHED:

1. Are there really only 5 nulls, or does a stub resonate above 9.0GHz where
   the Rev 18 probe simply never looked? Every "missing notch" in this
   campaign so far has turned out to be a search window that was too narrow,
   so this sweeps 0.5-14GHz before anyone concludes a stub is dead. Cheaper
   than adding a 7th stub to replace one that may already be there.

2. Which null belongs to S4, and is S4 half of a coupled pair? B1 showed S1's
   coupling is small and local, but that does NOT mean nothing is
   hybridising - it only rules S1 out. S3/S4 and S4/S5 are the remaining
   candidates and deleting S4 discriminates between them: whichever
   neighbouring null moves is the partner.

MESH MATCHING IS THE POINT. B1 diffed a 4.7GHz-adapted intact run against a
6.0GHz-adapted deleted run, so the small (<=0.4%) neighbour shifts it reported
sat at the noise floor and could not be trusted. Both designs here are built
at the SAME single-point adaptive frequency (6.0GHz) and the same tolerance,
and the intact run at those settings also becomes a clean re-baseline for B1's
own S1 diff. Nothing in a cross-run comparison here is confounded by mesh.

Deletion is done by filtering the regenerated piece list, never by editing the
STUBS table - removing a table entry would shrink SERIES_SECTIONS and shift
every downstream tee by 2500um. Verified locally for both cases: still 1
merged polygon, 0 holes.

Directional settings (delta_S 0.02, single-point adaptive). Not a scorecard.
"""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filter_BB_firstlight_HFSS as FL  # noqa: E402

SWEEP_START_GHZ = 0.5
SWEEP_STOP_GHZ = 14.0
SWEEP_COUNT = 2701          # 5MHz, matching v3's own density
ADAPTIVE_GHZ = 6.0          # SAME for every run below - see docstring

# (design name, output prefix, label prefix to delete or None)
RUNS = [
    ('v3f_census_intact', 'v3f_census_intact', None),
    ('v3f_census_delS4', 'v3f_census_delS4', '6.1GHz'),
]

STUB_LABELS = ['4.5GHz', '4.7GHz', '5.3GHz', '6.1GHz', '7.0GHz', '8.0GHz']
NULL_FLOOR_DB = -15.0


def nulls(freqs, vals, depth=NULL_FLOOR_DB):
    out = []
    for i in range(1, len(freqs) - 1):
        if vals[i] < vals[i - 1] and vals[i] < vals[i + 1] and vals[i] < depth:
            out.append((float(freqs[i]), float(vals[i])))
    return out


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
    o = np.argsort(np.array(f))
    return np.array(f)[o], np.array(s)[o]


def solve_one(project, out_dir, design_name, prefix, delete_prefix):
    geom = FL._load_geometry()
    if delete_prefix:
        dropped = [p[0] for p in geom['pieces'] if p[0].startswith(delete_prefix)]
        assert dropped, 'nothing matched %s' % delete_prefix
        geom = dict(geom)
        geom['pieces'] = [p for p in geom['pieces'] if not p[0].startswith(delete_prefix)]
        print('  deleted %d piece(s) of %s' % (len(dropped), delete_prefix))

    FL.ADAPTIVE_FREQ_GHZ = ADAPTIVE_GHZ
    specs = [dict(name='Census_Sweep', type='Interpolating',
                  start=SWEEP_START_GHZ, stop=SWEEP_STOP_GHZ, count=SWEEP_COUNT)]
    design, setup, sweeps = FL.build_design(project, design_name, geom, specs,
                                             adaptive='single')
    print('  solving %s (adaptive @ %.1fGHz, delta_S 0.02)...' % (design_name, ADAPTIVE_GHZ))
    setup.analyze()
    rows = FL.export_convergence(design, setup.name, out_dir)
    if rows:
        print('  convergence: %d passes, final delta-S %s' % (len(rows), list(rows[-1].values())[-1]))

    freqs, s21, s11 = FL.pull_sweep(sweeps['Census_Sweep'], out_dir, '_' + prefix)
    path = os.path.join(out_dir, '%s_S21.csv' % prefix)
    with open(path, 'w', newline='') as fh:
        wr = csv.writer(fh)
        wr.writerow(['freq_ghz', 'S21_dB', 'S11_dB'])
        for a, b, c in zip(freqs, s21, s11):
            wr.writerow(['%.6f' % a, '%.6f' % b, '%.6f' % c])
    print('  S21 -> %s' % path)
    return freqs, s21


def main():
    project = FL.connect_project()
    desktop = FL.HFSS.HfssApp().get_app_desktop()
    same = [p for p in desktop.get_projects() if p.name == FL.PROJECT_NAME]
    print('AEDT handles named %r open: %d%s'
          % (FL.PROJECT_NAME, len(same), '  <== MORE THAN ONE' if len(same) > 1 else ''))
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HFSS')

    results = {}
    for design_name, prefix, delete_prefix in RUNS:
        print('--- %s ---' % design_name)
        results[prefix] = solve_one(project, out_dir, design_name, prefix, delete_prefix)

    intact_f, intact_s = results['v3f_census_intact']
    del4_f, del4_s = results['v3f_census_delS4']
    n_intact = nulls(intact_f, intact_s)
    n_del4 = nulls(del4_f, del4_s)

    print('=' * 78)
    print('Rev 19 B1b - full-range null census (%.1f-%.1fGHz), mesh-matched'
          % (SWEEP_START_GHZ, SWEEP_STOP_GHZ))
    print('=' * 78)
    print('Q1: how many nulls does the intact filter actually have?')
    print('  %d nulls below %.0fdB, %d stubs drawn' % (len(n_intact), NULL_FLOOR_DB, len(STUB_LABELS)))
    for f, d in n_intact:
        tag = '   <== ABOVE the Rev 18 probe window, never previously seen' if f > 9.0 else ''
        print('    %7.3f GHz  %7.1f dB%s' % (f, d, tag))
    below9 = [p for p in n_intact if p[0] <= 9.0]
    print('  in 3.5-9.0GHz (the Rev 18 window): %d' % len([p for p in below9 if p[0] >= 3.5]))
    if len(n_intact) >= len(STUB_LABELS):
        print('  READING: enough nulls exist for every stub - nothing is missing, some are')
        print('           merely mis-placed. Repair beats adding a 7th stub.')
    else:
        print('  READING: still fewer nulls than stubs even over the full range - at least')
        print('           one stub genuinely produces no zero.')

    print('-' * 78)
    print('Q2: which null is S4 (6.1GHz), and who is its coupling partner?')
    print('  nulls with S4    : %s' % ', '.join('%.3f' % f for f, _ in n_intact))
    print('  nulls without S4 : %s' % ', '.join('%.3f' % f for f, _ in n_del4))
    print()
    remaining = list(n_del4)
    vanished = []
    print('  %-16s %-16s %-11s %s' % ('with S4', 'without S4', 'shift', 'reading'))
    for f0, d0 in n_intact:
        if remaining:
            j = int(np.argmin([abs(f0 - g[0]) for g in remaining]))
            gf, gd = remaining[j]
            if abs(gf - f0) < 0.45:
                remaining.pop(j)
                shift = gf - f0
                pct = 100 * shift / f0
                note = ('unmoved' if abs(pct) < 0.5 else
                        'shifted %+.1f%% - COUPLED TO S4' % pct)
                print('  %-16s %-16s %+9.3fGHz  %s'
                      % ('%.3f(%.0fdB)' % (f0, d0), '%.3f(%.0fdB)' % (gf, gd), shift, note))
                continue
        vanished.append((f0, d0))
        print('  %-16s %-16s %11s  *** VANISHED - THIS NULL IS S4 ***'
              % ('%.3f(%.0fdB)' % (f0, d0), '(none)', '-'))
    for gf, gd in remaining:
        print('  %-16s %-16s %11s  appeared' % ('(none)', '%.3f(%.0fdB)' % (gf, gd), '-'))

    print('-' * 78)
    if len(vanished) == 1:
        print('  VERDICT: S4 owns the %.3fGHz null (%.0fdB).' % vanished[0])
    elif not vanished:
        print('  VERDICT: no null vanished - S4 produces no zero anywhere in %.1f-%.1fGHz.'
              % (SWEEP_START_GHZ, SWEEP_STOP_GHZ))
        print('           THIS is the dead stub, and repairing it is the cheap fix for the')
        print('           5.5-6.7GHz gap - no 7th stub needed.')
    else:
        print('  VERDICT: AMBIGUOUS - %d vanished' % len(vanished))
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
