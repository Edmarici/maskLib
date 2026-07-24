# eps_eff/Z0 HFSS extraction — status report (for next-session handoff)

**Date:** 2026-07-21
**Scripts:** `Radial_Stub_LPF/extract_epseff.py` (build+solve+extract),
`Radial_Stub_LPF/plot_epseff_mode.py` (field-plot mode verification)
**Consumer:** `Radial_Stub_LPF/filter_BB.py` (`EPS_EFF` constant)

## Objective

Replace `filter_BB.py`'s `EPS_EFF=5.5` placeholder with a real value, by
extracting eps_eff(f) and Z0(f) for a bare 70um/125um metal strip on
c-plane sapphire (anisotropic, eps=(9.4,9.4,11.6)) inside the real 7.0mm
package bore, via HFSS wave-port eigenmode analysis (AEDT 2023 R2,
pyaedt). Originally scoped as a full 1-12GHz dispersion sweep plus
Zpi/Zpv/Zvi impedance table.

## What's validated and in use

Single-point solve at 6.0GHz, both widths, mode confirmed as the true
strip-hugging mode (not a bulk cavity mode) by both physical-sanity
filtering across 6 candidate modes AND a visual field plot
(`HFSS/epseff_w70_mode_field.jpg` — E-field clearly concentrated at the
strip, decaying toward the bore wall):

| width | eps_eff @ 6GHz | \|Zpi\| @ 6GHz |
|---|---|---|
| 70um  | 5.6795 | 69.71 ohm |
| 125um | 5.6826 | 69.70 ohm |

The two widths agree to <0.1%, so a single global constant is justified
rather than per-width/per-stub values.

**Already applied:** `filter_BB.py`'s `EPS_EFF` is now `5.681` (the
average). Rebuilt cleanly — stub table regenerated, transverse budget
still comfortable (4984.6um vs 6000um), DXF/GDS exported. Only this one
file changed.

## What's NOT resolved — the real open problem

The 1-12GHz discrete sweep (`hfss.create_linear_step_sweep`, both widths)
produces **non-physical data** and is not trusted or used anywhere:

- eps_eff swings from 277.6 @ 1GHz down to **0.0 @ 12GHz**, with beta
  monotonically decreasing to exactly zero — the signature of a mode
  approaching its own cutoff, not a genuine quasi-TEM strip mode (which
  should propagate at roughly constant eps_eff across this whole range).
- Apparent "dispersion" across 4-8GHz comes out ~130% for both widths —
  physically implausible for a well-behaved line (should be at most a few
  percent).
- The SAME mode label (`P1:1` at 6GHz) gave a different eps_eff in the
  swept run (7.71) than in the earlier single-frequency-only run (5.68)
  for what should be the identical nominal quantity.

**Working theory:** HFSS's per-port mode indexing isn't reliably tracking
the same physical mode across the swept frequency range (confirmed
separately that mode ordering isn't even consistent *between* the two
ports at a single frequency). Not yet root-caused. Field-plot
verification has only been done at 6GHz — spot-checking a few more sweep
frequencies (e.g. 2, 5, 7, 10GHz) to see whether `P1:1` visually swaps to
a different field pattern is the most direct next diagnostic step, but
wasn't run this pass.

## Decision points for next steps

1. **Is single-point eps_eff good enough, or is real dispersion data
   needed?** Current filter_BB.py design uses one constant across all 6
   stubs (4.2-8.0GHz). If genuine dispersion across that band turns out
   to be small (a few %), the single-point value is fine as-is. If it's
   actually significant, the sweep needs to be fixed first — the current
   sweep data cannot be trusted either way.
2. **Worth diagnosing the mode-tracking bug**, or accept the single point
   as final for this design pass? Diagnosis path: field plots at
   additional sweep frequencies, and/or a more robust mode-selection
   method (track continuity of Gamma across frequency instead of trusting
   a fixed mode index).
3. **125um field-plot verification** — only 70um has been visually
   confirmed at 6GHz; 125um relies on the numeric sanity filter only.
   Quick to close if wanted.
4. **Per-stub `dl_um` trimming** (fine length correction from real S11
   zero location, not just eps_eff) — explicitly out of scope this pass,
   still open per the original handoff.
5. **Package/cavity coupling** beyond the bare-strip approximation (walls
   at ~3mm, same simplification `filter_L60.py`'s Phase 1 used) — not
   modeled here either; a possible follow-on if the single-point value
   needs cross-checking against a fuller package sim.

## File locations

- `Radial_Stub_LPF/extract_epseff.py` — the extraction pipeline (geometry,
  material, ports, setup, sweep, mode-sanity filter, CSV export).
- `Radial_Stub_LPF/plot_epseff_mode.py` — field-plot verification (70um
  only so far).
- `Radial_Stub_LPF/HFSS/epseff_w70.csv`, `epseff_w125.csv` — full
  1-12GHz sweep output (NOT trusted, kept for reference/diagnosis only).
- `Radial_Stub_LPF/HFSS/epseff_w70_mode_field.jpg` — mode verification
  field plot.
- `Radial_Stub_LPF/filter_BB.py` — consumer, `EPS_EFF=5.681` now applied.
