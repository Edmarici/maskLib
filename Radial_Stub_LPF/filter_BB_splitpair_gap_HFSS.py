#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rev 20 B2 - characterize the SPLIT PAIR against run gap.

WHY THIS EXISTS
---------------
Rev 19 B4 deleted S6 from the full filter at matched mesh and found it owned
TWO nulls, not one: 6.640 and 7.580GHz, a pair split +/-6.84% about a
geometric mean of 7.094GHz (ratio 1.1416). A fold's parallel runs are a
coupled-line pair and support an even and an odd mode; the earlier fold
experiment measured a single number per geometry because it only ever looked
in a 3.5-5.5GHz window, so it could not have seen a pair.

That makes the split ratio a DESIGN PARAMETER, not a defect: a folded stub is
a two-notch element whose span should scale with the coupling between its
runs, hence with their gap. If that is true and measurable, one folded stub
can bridge a coverage gap that no single-null stub can. The two remaining
gaps in the mode comb are 1.5 and 1.8GHz wide and the current pair spans
0.94GHz, so this is the number the seventh-stub decision turns on.

METHOD
------
One stub alone on a matched through-line in the REAL 7000um bore - the same
harness as the Rev 17 fold experiment, imported rather than re-implemented
(DESIGN_NOTES sec 12: a re-derived build loop drifts silently). Total drawn
centerline length is FIXED at S6's own realized 6436.9032um so every variant
ties directly to the B4 measurement. n_par_runs and d_perp are fixed at S6's
values too. Only run_gap varies.

GAPS
----
  G-400  : S6's ACTUAL gap. The handoff proposed 1000/1500, but 400 is the
           only point in the sweep that can be checked against an independent
           measurement - B4's in-cascade k_eff 0.6886 and ratio 1.1416. It
           anchors the trend and validates the harness at the same time. If
           G-400 disagrees with B4, the isolated harness does not represent
           the stub in the cascade and the other two points cannot be trusted
           either - that is worth knowing before reading any trend.
  G-1000 : the handoff's first point; also nominally the earlier fold
           experiment's V-fold-wide geometry, whose 0.792 k_eff was extracted
           assuming a single null. Expect disagreement, and report it.
  G-1500 : the handoff's second point.

WINDOW
------
The pair sits near 7GHz for this length, NOT in the fold experiment's own
3.5-5.5GHz discrete window - which is exactly why the split was invisible for
three revisions. Discrete window here is 5.0-9.5GHz at 10MHz, over a 0.5-14GHz
coarse sweep at 5MHz, so a pair that spreads or converges with gap stays
inside the window either way.
"""
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filter_BB_fold_experiment_HFSS as FE  # noqa: E402

# S6's realized drawn length and fold geometry, from HFSS/filter_BB_dims.json.
S6_LENGTH_UM = 6436.903150752643
S6_D_PERP_UM = 1000.0
S6_N_PAR_RUNS = 2
S6_RUN_GAP_UM = 400.0

# Rev 19 B4's in-cascade measurement of this exact geometry, for the G-400
# cross-check.
B4_LOWER_GHZ = 6.640
B4_UPPER_GHZ = 7.580

GAPS_UM = [400.0, 1000.0, 1500.0]

COARSE_START_GHZ = 0.5
COARSE_STOP_GHZ = 14.0
COARSE_COUNT = 2701          # 5MHz
DISCRETE_START_GHZ = 5.0
DISCRETE_STOP_GHZ = 9.5
DISCRETE_STEP_GHZ = 0.01     # 10MHz
DISCRETE_COUNT = int(round((DISCRETE_STOP_GHZ - DISCRETE_START_GHZ) / DISCRETE_STEP_GHZ)) + 1
ADAPTIVE_FREQ_GHZ = 7.0      # the pair's own region, not the bare quarter-wave point

EPS_EFF = 5.681
C_UM_GHZ = 2.998e5

NULL_DEPTH_DB = -15.0


def bare_quarter_wave_ghz(length_um):
    return C_UM_GHZ / (4.0 * length_um * math.sqrt(EPS_EFF))


def nulls(f, s, depth=NULL_DEPTH_DB):
    return [(float(f[i]), float(s[i])) for i in range(1, len(f) - 1)
            if s[i] < s[i - 1] and s[i] < s[i + 1] and s[i] < depth]


def main():
    os.makedirs(FE.OUT_DIR, exist_ok=True)

    # Override the fold experiment's module-level sweep/mesh settings. Its
    # build_design() reads these at call time, so this is the whole config.
    FE.COARSE_START_GHZ, FE.COARSE_STOP_GHZ, FE.COARSE_COUNT = (
        COARSE_START_GHZ, COARSE_STOP_GHZ, COARSE_COUNT)
    FE.DISCRETE_START_GHZ, FE.DISCRETE_STOP_GHZ, FE.DISCRETE_COUNT = (
        DISCRETE_START_GHZ, DISCRETE_STOP_GHZ, DISCRETE_COUNT)
    FE.ADAPTIVE_FREQ_GHZ = ADAPTIVE_FREQ_GHZ

    project = FE.connect_project()
    desktop = FE.HFSS.HfssApp().get_app_desktop()
    same = [p for p in desktop.get_projects() if p.name == FE.PROJECT_NAME]
    print('AEDT handles named %r open: %d%s'
          % (FE.PROJECT_NAME, len(same), '  <== MORE THAN ONE' if len(same) > 1 else ''))

    f_bare = bare_quarter_wave_ghz(S6_LENGTH_UM)
    print('=' * 78)
    print('Rev 20 B2 - split-pair vs run gap, single stub in the real 7000um bore')
    print('  fixed length %.4fum (S6\'s own), n_par_runs %d, d_perp %.0fum'
          % (S6_LENGTH_UM, S6_N_PAR_RUNS, S6_D_PERP_UM))
    print('  bare quarter-wave of that length: %.4f GHz' % f_bare)
    print('  adaptive @%.1fGHz, delta_S 0.02, discrete %.1f-%.1fGHz @%.0fMHz'
          % (ADAPTIVE_FREQ_GHZ, DISCRETE_START_GHZ, DISCRETE_STOP_GHZ,
             DISCRETE_STEP_GHZ * 1000))
    print('=' * 78)

    rows = []
    for gap in GAPS_UM:
        name = 'G-%d' % int(gap)
        spec = FE.fold_spec(name, S6_LENGTH_UM, S6_D_PERP_UM, S6_N_PAR_RUNS, gap)
        assert abs(spec['total_check'] - S6_LENGTH_UM) < 1e-6, \
            '%s total %.6f != %.6f' % (name, spec['total_check'], S6_LENGTH_UM)
        print('--- %s ---' % name)
        print('  bend_radius %.1fum, run_length %.2fum, transverse reach %.1fum'
              % (spec['bend_radius'], spec['run_length'], spec['transverse_reach']))
        if spec['run_length'] < 2.0 * spec['bend_radius']:
            print('  CONFOUND: run_length %.0fum is under 2x bend_radius %.0fum. At fixed'
                  % (spec['run_length'], spec['bend_radius']))
            print('  total length, widening the gap converts straight run into U-turn arc'
                  ' - so this')
            print('  point varies SHAPE as well as coupling and is not a clean coupling'
                  ' datum.')

        design_name = 'Split_G%d' % int(gap)
        design, setup, coarse, discrete = FE.build_design(project, design_name, spec)
        setup.analyze()

        f_c, v_c = FE._pull(coarse, '%s_coarse' % design_name)
        f_d, v_d = FE._pull(discrete, '%s_discrete' % design_name)
        with open(os.path.join(FE.OUT_DIR, 'splitpair_%s_S21.csv' % design_name),
                  'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['freq_GHz', 'S21_dB', 'sweep'])
            w.writerows([(a, b, 'coarse') for a, b in zip(f_c, v_c)])
            w.writerows([(a, b, 'discrete') for a, b in zip(f_d, v_d)])

        all_c = nulls(np.asarray(f_c), np.asarray(v_c))
        in_win = nulls(np.asarray(f_d), np.asarray(v_d))
        print('  nulls, full 0.5-14GHz coarse   : %s'
              % ', '.join('%.3f(%.0fdB)' % n for n in all_c))
        print('  nulls, %.1f-%.1fGHz discrete    : %s'
              % (DISCRETE_START_GHZ, DISCRETE_STOP_GHZ,
                 ', '.join('%.3f(%.0fdB)' % n for n in in_win)))

        row = dict(variant=name, gap_um='%.0f' % gap,
                   bend_radius_um='%.1f' % spec['bend_radius'],
                   run_length_um='%.2f' % spec['run_length'],
                   n_nulls_in_window=len(in_win))
        if len(in_win) >= 2:
            # the two DEEPEST nulls in the window are the pair; report if the
            # window held more than two, because that would mean the
            # two-mode reading is incomplete.
            pair = sorted(sorted(in_win, key=lambda n: n[1])[:2])
            (lo, lo_db), (hi, hi_db) = pair
            centre = math.sqrt(lo * hi)
            ratio = hi / lo
            span = hi - lo
            k_eff = f_bare / centre
            half_split_pct = 100.0 * (hi - lo) / (hi + lo)
            print('  PAIR: %.3f (%.1fdB) and %.3f (%.1fdB)' % (lo, lo_db, hi, hi_db))
            print('        centre (geometric mean) %.4f GHz, span %.4f GHz'
                  % (centre, span))
            print('        ratio %.4f  (+/-%.2f%% about centre)' % (ratio, half_split_pct))
            print('        k_eff to centre = %.4f / %.4f = %.4f'
                  % (f_bare, centre, k_eff))
            print('        implied span at a 6.0GHz centre: %.3f GHz' % (6.0 * (ratio - 1) / math.sqrt(ratio)))
            print('        implied span at a 7.0GHz centre: %.3f GHz' % (7.0 * (ratio - 1) / math.sqrt(ratio)))
            if len(in_win) > 2:
                print('        NOTE: %d nulls in the window, not 2 - the pair above is the '
                      'two deepest. Read the full list before trusting it.' % len(in_win))
            row.update(lower_ghz='%.3f' % lo, lower_db='%.1f' % lo_db,
                       upper_ghz='%.3f' % hi, upper_db='%.1f' % hi_db,
                       centre_ghz='%.4f' % centre, span_ghz='%.4f' % span,
                       ratio='%.4f' % ratio, half_split_pct='%.2f' % half_split_pct,
                       k_eff='%.4f' % k_eff)
        else:
            print('  NO PAIR FOUND in the window (%d null(s)). Do not infer a trend '
                  'from this point.' % len(in_win))
            row.update(lower_ghz='', lower_db='', upper_ghz='', upper_db='',
                       centre_ghz='', span_ghz='', ratio='', half_split_pct='', k_eff='')

        if abs(gap - S6_RUN_GAP_UM) < 1e-6 and row.get('ratio'):
            b4_centre = math.sqrt(B4_LOWER_GHZ * B4_UPPER_GHZ)
            b4_ratio = B4_UPPER_GHZ / B4_LOWER_GHZ
            b4_keff = f_bare / b4_centre
            print('  CROSS-CHECK vs Rev 19 B4 (same geometry, measured in the cascade):')
            print('    B4       : %.3f / %.3f, centre %.4f, ratio %.4f, k_eff %.4f'
                  % (B4_LOWER_GHZ, B4_UPPER_GHZ, b4_centre, b4_ratio, b4_keff))
            print('    isolated : %s / %s, centre %s, ratio %s, k_eff %s'
                  % (row['lower_ghz'], row['upper_ghz'], row['centre_ghz'],
                     row['ratio'], row['k_eff']))
            d_centre = 100.0 * (float(row['centre_ghz']) - b4_centre) / b4_centre
            d_ratio = 100.0 * (float(row['ratio']) - b4_ratio) / b4_ratio
            print('    centre differs %+.2f%%, ratio differs %+.2f%%' % (d_centre, d_ratio))
            print('    -> %s' % ('harness represents the cascade well'
                                 if abs(d_centre) < 3.0 and abs(d_ratio) < 5.0 else
                                 'HARNESS DISAGREES WITH THE CASCADE - the isolated numbers '
                                 'below carry cascade loading as an unmodelled error'))
        rows.append(row)

    out = os.path.join(FE.OUT_DIR, 'splitpair_gap_sweep.csv')
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('=' * 78)
    print('SUMMARY  (fixed length %.1fum, %d runs, d_perp %.0fum)'
          % (S6_LENGTH_UM, S6_N_PAR_RUNS, S6_D_PERP_UM))
    print('  gap_um   lower    upper    centre   ratio    k_eff    span@7GHz')
    for r in rows:
        if r.get('ratio'):
            ratio = float(r['ratio'])
            print('  %-8s %-8s %-8s %-8s %-8s %-8s %.3f GHz'
                  % (r['gap_um'], r['lower_ghz'], r['upper_ghz'], r['centre_ghz'],
                     r['ratio'], r['k_eff'], 7.0 * (ratio - 1) / math.sqrt(ratio)))
        else:
            print('  %-8s no pair found' % r['gap_um'])
    print('  -> %s' % out)
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
