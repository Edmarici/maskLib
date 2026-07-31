#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 19 B1 - identify S1 by DELETION, and measure how much it was perturbing
its neighbours.

Attribution has been unresolved since Rev 16: the design has 6 stubs but only
5 nulls, and the frozen S2-S6 nulls demonstrably move when only S1 changes, so
every window/proximity-based matcher has been guessing. Deleting one stub and
seeing which null disappears settles it with no matcher, no search window and
no sign convention to get backwards.

HOW THE DELETION IS DONE (this matters): S1's metal is removed by FILTERING
THE REGENERATED PIECE LIST, not by editing filter_BB.py's STUBS table.
Deleting the table entry would shrink SERIES_SECTIONS and shift every
downstream tee by 2500um - i.e. it would change the entire cascade, which is
the opposite of a controlled deletion. Filtering pieces leaves tee positions,
series-section lengths, fold-direction scheduling and all five other stubs
byte-identical. Verified locally before solving: 48 pieces still merge to 1
polygon with 0 holes.

The residual five nulls are the real second deliverable - their shift versus
the intact probe run is a DIRECT measurement of S1's coupling to each
neighbour, which this campaign has only ever inferred.

Same loose/directional settings as the Rev 18 probe (single-point adaptive,
delta_S 0.02, one interpolating sweep). Not a scorecard.
"""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filter_BB_firstlight_HFSS as FL  # noqa: E402

DESIGN_NAME = 'v3f_delete_S1'
OUT_PREFIX = 'v3f_delete_S1'
INTACT_PREFIX = 'v3f_singlefold'     # the Rev 18 probe, S1 present

DELETE_LABEL_PREFIX = '4.5GHz'       # S1

PROBE_START_GHZ = 3.5
PROBE_STOP_GHZ = 9.0
PROBE_COUNT = 1101
PROBE_ADAPTIVE_GHZ = 6.0             # handoff B1


def _nulls(freqs, vals, lo, hi, depth=-15.0):
    out = []
    for i in range(1, len(freqs) - 1):
        if not (lo <= freqs[i] <= hi):
            continue
        if vals[i] < vals[i - 1] and vals[i] < vals[i + 1] and vals[i] < depth:
            out.append((float(freqs[i]), float(vals[i])))
    return out


def _load(path):
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


def main():
    project = FL.connect_project()
    desktop = FL.HFSS.HfssApp().get_app_desktop()
    same = [p for p in desktop.get_projects() if p.name == FL.PROJECT_NAME]
    print('AEDT handles named %r open: %d%s'
          % (FL.PROJECT_NAME, len(same),
             '  <== MORE THAN ONE' if len(same) > 1 else ''))

    geom = FL._load_geometry()
    n_before = len(geom['pieces'])
    dropped = [p[0] for p in geom['pieces'] if p[0].startswith(DELETE_LABEL_PREFIX)]
    geom = dict(geom)
    geom['pieces'] = [p for p in geom['pieces'] if not p[0].startswith(DELETE_LABEL_PREFIX)]
    print('deleted %d piece(s) belonging to %s: %s'
          % (len(dropped), DELETE_LABEL_PREFIX, ', '.join(dropped)))
    print('pieces %d -> %d (everything else untouched: tees, sections, S2-S6)'
          % (n_before, len(geom['pieces'])))
    assert dropped, 'nothing matched %s - wrong label prefix' % DELETE_LABEL_PREFIX

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HFSS')

    FL.ADAPTIVE_FREQ_GHZ = PROBE_ADAPTIVE_GHZ
    specs = [dict(name='Probe_Sweep', type='Interpolating',
                  start=PROBE_START_GHZ, stop=PROBE_STOP_GHZ, count=PROBE_COUNT)]
    design, setup, sweeps = FL.build_design(project, DESIGN_NAME, geom, specs,
                                             adaptive='single')
    print('solving %s (adaptive @ %.2fGHz, delta_S 0.02)...' % (DESIGN_NAME, PROBE_ADAPTIVE_GHZ))
    setup.analyze()

    rows = FL.export_convergence(design, setup.name, out_dir)
    if rows:
        print('convergence: %d passes, final delta-S %s' % (len(rows), list(rows[-1].values())[-1]))

    freqs, s21, s11 = FL.pull_sweep(sweeps['Probe_Sweep'], out_dir, '_delS1')
    path = os.path.join(out_dir, '%s_S21.csv' % OUT_PREFIX)
    with open(path, 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['freq_ghz', 'S21_dB', 'S11_dB'])
        for a, b, c in zip(freqs, s21, s11):
            wr.writerow(['%.6f' % a, '%.6f' % b, '%.6f' % c])
    print('S21 saved -> %s' % path)

    now = _nulls(freqs, s21, PROBE_START_GHZ, PROBE_STOP_GHZ)
    intact_path = os.path.join(out_dir, '%s_S21.csv' % INTACT_PREFIX)
    print('=' * 78)
    print('Rev 19 B1 - S1 identified by deletion')
    print('=' * 78)
    print('nulls WITHOUT S1 : %s' % ', '.join('%.3f(%.0fdB)' % p for p in now))

    if not os.path.exists(intact_path):
        print('intact trace %s not found - cannot diff' % intact_path)
        return 0

    bf, bs = _load(intact_path)
    before = _nulls(bf, bs, PROBE_START_GHZ, PROBE_STOP_GHZ)
    print('nulls WITH S1    : %s' % ', '.join('%.3f(%.0fdB)' % p for p in before))
    print('-' * 78)

    # greedy nearest-match, intact -> deleted; anything left unmatched vanished
    remaining = list(now)
    print('%-16s %-16s %-10s %s' % ('with S1', 'without S1', 'shift', 'reading'))
    vanished = []
    for f0, d0 in before:
        if remaining:
            j = int(np.argmin([abs(f0 - g[0]) for g in remaining]))
            gf, gd = remaining[j]
            if abs(gf - f0) < 0.45:
                remaining.pop(j)
                shift = gf - f0
                note = ('unmoved' if abs(shift) < 0.02 else
                        'shifted %+.1f%% - S1 was coupling to this one' % (100 * shift / f0))
                print('%-16s %-16s %+8.3fGHz  %s'
                      % ('%.3f(%.0fdB)' % (f0, d0), '%.3f(%.0fdB)' % (gf, gd), shift, note))
                continue
        vanished.append((f0, d0))
        print('%-16s %-16s %10s  *** VANISHED - THIS NULL IS S1 ***'
              % ('%.3f(%.0fdB)' % (f0, d0), '(none)', '-'))
    for gf, gd in remaining:
        print('%-16s %-16s %10s  appeared (not present with S1)'
              % ('(none)', '%.3f(%.0fdB)' % (gf, gd), '-'))

    print('-' * 78)
    if len(vanished) == 1:
        print('VERDICT: S1 owns the %.3fGHz null (%.0fdB).' % vanished[0])
    elif not vanished:
        print('VERDICT: AMBIGUOUS - no null vanished. S1 may not resonate in 3.5-9.0GHz at all,')
        print('         or its null is shallower than the -15dB detection floor.')
    else:
        print('VERDICT: AMBIGUOUS - %d nulls vanished: %s'
              % (len(vanished), ', '.join('%.3f' % f for f, _ in vanished)))
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
