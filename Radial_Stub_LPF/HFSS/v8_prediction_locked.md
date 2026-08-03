# Rev 21 — LOCKED pre-solve prediction: S6 fan terminator

Written **before** the solve. Change under test: S6 gains a 300 µm axial fan
(r_in 49.50 µm, 90°). Drawn centreline **held** at 7379.3227 µm, so the fan is
the only variable.

Baseline for comparison: **`v6_s6move`** — probe mesh, same settings, same
drawn length, no fan. Mesh-matched one-variable diff.

## What the fan is for

Not depth. Q2 found the design's one fragility: storage 1 (5.792 GHz) leans on
S6's zero at 5.900, 108 MHz away, so a 1% S6 length error costs 13.9 dB and
fails the mode. A zero is infinitely deep and narrow; **breadth is the scarce
quantity**, and a fan is the standard way to buy it.

## Predictions

| # | quantity | baseline (v6_s6move) | predicted | reasoning |
|---|---|---|---|---|
| 1 | S6 zero position | 5.900 | **5.75–5.88** | fan end-loading adds electrical length; theory correction says −2.08% → 5.777, but that formula has been percent-level wrong all campaign, so a band not a point |
| 2 | S21 at storage 1 | −28.65 | **better than −30** | zero moves toward the mode |
| 3 | S6 zero width, −3 dB below local baseline | 125 MHz | **wider, ≥ 160 MHz** | the whole point; if it does not widen, the fan is not doing its job |
| 4 | storage 1 worst case under ±1% S6 | −14.65 (FAIL) | **passes, ≤ −20** | combination of centring and broadening |
| 5 | 7.515 GHz S5+S6 zero | 7.515 | **moves** | Q1 showed it needs S6; changing S6's end changes the pair |
| 6 | overall score | 9/9 | **9/9** | no mode should be given up |

> **Correction to row 3, made after committing this file and before the solve
> returned.** It originally read "−30 dB width, 63 MHz". That metric is
> meaningless in this cascade: the composite floor is *already* below −30 dB
> across 5.60–6.10 GHz, so an absolute threshold measures the neighbouring
> stubs, not S6 — the exact effect §2.3 of the master notes warns about, and I
> walked into it. The 63 MHz figure was never measured; it was an estimate
> written from memory. Replaced with the local-baseline convention the fold
> experiment already uses (baseline = mean over ±0.25–0.5 GHz excluding the
> zero), on which the real baseline width is **125 MHz** (90 MHz at −6 dB,
> 55 MHz at −10 dB). The prediction's substance is unchanged — the test is
> still "does it broaden" — but the threshold is now on a metric that can
> actually detect it.

## Falsifiers — what would mean the reasoning is wrong

- **Zero does not move at all.** Then the fan adds no electrical length in this
  groundless geometry, which would contradict the whole fan-correction
  machinery used for S2–S5.
- **Zero moves but does not broaden.** Then the fan is acting purely as a
  length extension, and the fragility is unfixed — the honest response would
  be to revert the fan and instead lengthen S6 by 1.86% to centre the zero,
  which is the simpler change and was already quantified.
- **Zero overshoots below ~5.70.** Then it has moved past storage 1 and the
  mode is exposed on the other side; would need a length trim back up.
- **Any mode drops below −20.** 9/9 is the incumbent; losing a mode to buy
  robustness at storage 1 is a trade, not a win, and must be reported as one.

## Not predicted

Where the 7.515 GHz zero lands. It is a two-body S5+S6 feature whose frequency
is set mainly by S5 (Sec. 3.9), and no measurement so far constrains how it
responds to a change in S6's *termination* as opposed to S6's *length*.
Recording that it is unpredicted rather than guessing.
