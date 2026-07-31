"""Rev 17 B3 scorecard: v3 (L-stub S1 @4.5GHz, S7 deleted) vs v2+S7 baseline.

Label-independent where possible: nulls are found directly from the merged S21
trace, not read out of the dashboard's stub-assignment.
"""
import csv
import os

HD = r'c:\Users\epm114\Desktop\Masklib\Radial_Stub_LPF\HFSS'


def load_s21(prefix):
    """Return sorted [(f_ghz, s21_db), ...] from the merged S21 csv."""
    path = os.path.join(HD, '%s_S21.csv' % prefix)
    with open(path, newline='') as fh:
        rdr = csv.DictReader(fh)
        cols = rdr.fieldnames
        fcol = next(c for c in cols if c.lower().startswith('f'))
        scol = next(c for c in cols if 's21' in c.lower())
        rows = []
        for r in rdr:
            try:
                rows.append((float(r[fcol]), float(r[scol])))
            except (TypeError, ValueError):
                continue
    rows.sort()
    # de-duplicate identical frequencies (coarse + discrete merged), keep deepest
    out = []
    for f, s in rows:
        if out and abs(out[-1][0] - f) < 1e-9:
            if s < out[-1][1]:
                out[-1] = (f, s)
        else:
            out.append((f, s))
    return out


def local_minima(tr, depth_db, fmin=None, fmax=None):
    """Strict local minima deeper than depth_db, within [fmin, fmax]."""
    res = []
    for i in range(1, len(tr) - 1):
        f, s = tr[i]
        if fmin is not None and f < fmin:
            continue
        if fmax is not None and f > fmax:
            continue
        if s < tr[i - 1][1] and s < tr[i + 1][1] and s < depth_db:
            res.append((f, s))
    return res


def worst_in(tr, fmin, fmax):
    seg = [(f, s) for f, s in tr if fmin <= f <= fmax]
    if not seg:
        return None
    return max(seg, key=lambda p: p[1])


def at_freq(tr, f0):
    return min(tr, key=lambda p: abs(p[0] - f0))


def band_edge(tr, level=-10.0, fmin=0.5, fmax=6.0):
    """Lowest frequency where S21 crosses below `level` and stays below for 200MHz."""
    seg = [(f, s) for f, s in tr if fmin <= f <= fmax]
    for i in range(1, len(seg)):
        if seg[i - 1][1] > level >= seg[i][1]:
            return seg[i][0]
    return None


v3 = load_s21('v3_confirm')
v2 = load_s21('s7v2_confirm')

print('=' * 74)
print('Rev 17 B3 scorecard - v3 (S1=L-stub@4.5GHz, S7 deleted) vs v2+S7')
print('=' * 74)
print('trace points: v3=%d (%.3f-%.3fGHz)  v2+S7=%d (%.3f-%.3fGHz)'
      % (len(v3), v3[0][0], v3[-1][0], len(v2), v2[0][0], v2[-1][0]))

print()
print('--- HEADLINE: S21 at the SNAIL criterion frequency ---')
for nm, tr in (('v3      ', v3), ('v2+S7   ', v2)):
    f, s = at_freq(tr, 4.5)
    print('  %s S21@%.3fGHz = %+8.2f dB' % (nm, f, s))
d = at_freq(v3, 4.5)[1] - at_freq(v2, 4.5)[1]
print('  improvement = %.2f dB   (target <= -20dB: v3 %s, v2+S7 %s)'
      % (-d,
         'PASS' if at_freq(v3, 4.5)[1] <= -20 else 'FAIL',
         'PASS' if at_freq(v2, 4.5)[1] <= -20 else 'FAIL'))

print()
print('--- Label-independent null enumeration (local minima < -15dB, 3-9GHz) ---')
for nm, tr in (('v3', v3), ('v2+S7', v2)):
    nulls = local_minima(tr, -15.0, 3.0, 9.0)
    print('  %-6s %d nulls: %s' % (nm, len(nulls),
          ', '.join('%.3fGHz(%.1fdB)' % (f, s) for f, s in nulls)))

print()
print('--- Stopband floor by sub-window (worst = shallowest S21) ---')
wins = [(4.2, 4.6), (4.6, 5.5), (5.5, 7.0), (7.0, 8.2), (4.2, 8.2)]
print('  %-14s %22s %22s' % ('window', 'v3 worst', 'v2+S7 worst'))
for lo, hi in wins:
    a = worst_in(v3, lo, hi)
    b = worst_in(v2, lo, hi)
    print('  %4.1f-%4.1fGHz   %10.2fdB @ %6.3fGHz %10.2fdB @ %6.3fGHz'
          % (lo, hi, a[1], a[0], b[1], b[0]))

print()
print('--- Passband (0.5-3.5GHz) ---')
spots = [0.5, 1.0, 2.0, 3.0, 3.3, 3.5]
print('  %-8s %10s %10s %8s' % ('f(GHz)', 'v3', 'v2+S7', 'delta'))
va, vb = [], []
for f0 in spots:
    a = at_freq(v3, f0)[1]
    b = at_freq(v2, f0)[1]
    va.append(a)
    vb.append(b)
    print('  %-8.1f %9.2fdB %9.2fdB %+7.2fdB' % (f0, a, b, a - b))
print('  spot-value peak-to-peak ripple: v3 %.2fdB   v2+S7 %.2fdB   (delta %+.2fdB)'
      % (max(va) - min(va), max(vb) - min(vb),
         (max(va) - min(va)) - (max(vb) - min(vb))))
for nm, tr in (('v3', v3), ('v2+S7', v2)):
    seg = [(f, s) for f, s in tr if 0.5 <= f <= 3.5]
    lo = min(seg, key=lambda p: p[1])
    hi = max(seg, key=lambda p: p[1])
    print('  %-6s full-trace 0.5-3.5GHz: best %+.2fdB @ %.3fGHz, worst %+.2fdB @ %.3fGHz, span %.2fdB'
          % (nm, hi[1], hi[0], lo[1], lo[0], hi[1] - lo[1]))

print()
print('--- Band edge (-10dB crossing) - REPORTED, NOT SCORED (Rev 17 D4) ---')
for nm, tr in (('v3', v3), ('v2+S7', v2)):
    be = band_edge(tr)
    print('  %-6s first -10dB crossing: %s'
          % (nm, ('%.3fGHz' % be) if be else 'none in 0.5-6GHz'))

print()
print('--- Out-of-band features 8-14GHz (S21 above -30dB = leakage) ---')
for nm, tr in (('v3', v3), ('v2+S7', v2)):
    seg = [(f, s) for f, s in tr if 8.0 <= f <= 14.0]
    if not seg:
        print('  %-6s no data above 8GHz' % nm)
        continue
    peaks = [seg[i] for i in range(1, len(seg) - 1)
             if seg[i][1] > seg[i - 1][1] and seg[i][1] > seg[i + 1][1]
             and seg[i][1] > -30.0]
    print('  %-6s %d peaks >-30dB: %s' % (nm, len(peaks),
          ', '.join('%.3fGHz(%.1fdB)' % (f, s) for f, s in peaks[:8])))
print('=' * 74)
