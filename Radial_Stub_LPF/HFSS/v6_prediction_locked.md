# Rev 20 B3 — LOCKED pre-solve prediction for candidate (a)

Written **before** the geometry change and before the solve (Rev 16 D1
discipline). Candidate (a): lengthen S6 6436.90 → 7379.32 µm so its lower null
moves 6.640 → 5.792 GHz (storage 1), upper null following 7.580 → 6.612 GHz if
the 1.1416 ratio holds.

## Why there is no circuit-model screening here

The handoff asks for ABCD screening "with the pair represented as its measured
two-null structure." `filter_BB_circuit_model.py` produces **one pole per stub
by construction** — each stub enters as an isolated quarter-wave admittance.
Representing the pair would mean hand-inserting a second pole fitted to the
very data being predicted, which has no predictive content for a *moved* stub.

What replaces it is stronger: **direct measurement of both endpoints.** B3
measured every mode with S6 present at its current length; B4 measured every
mode with S6 absent entirely, at identical mesh. Moving S6's upper null away
from 7.58 GHz cannot hurt storage 6/7 by more than deleting S6 does, because
the moved stub still contributes susceptance there. So the S6-absent column is
a **bound**, not a guess.

## Basis (confirm mesh, B3 / B4)

| mode | GHz | S6 present | S6 absent |
|---|---|---|---|
| buffer 1 | 4.500 | −25.44 | −21.43 |
| buffer 2 | 5.000 | −24.54 | −20.85 |
| storage 1 | 5.792 | −15.76 | −20.38 |
| storage 2 | 6.160 | −23.60 | −20.07 |
| storage 3 | 6.528 | −37.10 | −22.73 |
| storage 4 | 6.897 | −40.26 | −29.19 |
| storage 5 | 7.265 | −21.09 | −21.13 |
| storage 6 | 7.633 | −23.76 | −20.09 |
| storage 7 | 8.001 | −23.88 | −19.76 |

## Prediction

Compared against **v5_trim** (probe mesh, trimmed S1) since the S6 move stacks
on the trim — one variable, matched mesh.

| # | mode | v5_trim | predicted | reasoning |
|---|---|---|---|---|
| 1 | buffer 1 | −25.82 | −25 ± 2 | S6 nulls far in both cases; small change |
| 2 | buffer 2 | −23.35 | −25 to −28 | new lower null 0.79 GHz away vs 1.64 now — closer |
| 3 | **storage 1** | **−15.84** | **< −40** | null lands on it |
| 4 | storage 2 | −23.91 | −25 to −30 | now bracketed at 0.37 / 0.45 GHz |
| 5 | storage 3 | −37.79 | < −35 | new upper null only 84 MHz away |
| 6 | storage 4 | −39.43 | −30 to −40 | S4's own 6.890 null covers it; loses S6's 6.640 |
| 7 | storage 5 | −22.03 | ≈ −21 | S6-independent (absent value −21.13 ≈ present −21.09) |
| 8 | storage 6 | −23.84 | −20 to −21 | loses the 7.580 null; floors at the absent −20.09 |
| 9 | **storage 7** | **−23.83** | **≈ −20, AT RISK** | loses 7.580; absent value is −19.76, a flag |

**Headline prediction: storage 1 clears decisively, storage 6 and 7 fall back
toward their S6-absent values, and storage 7 is the single flag risk.**

Expected score **9/9 or 8/9**. If 8/9, the flag has moved from storage 1
(−4.2 dB) to storage 7 (≈−0.2 dB, inside the 0.61 dB mesh error measured in
B1) — a good trade, but a trade, and the honest reading is then that six stubs
cannot span this comb.

## What would falsify the reasoning

- **storage 1 does not go deep.** Then the 1/length scaling of the pair does
  not hold under a 14.6% move, despite holding across the 1.67% move between
  S6's old and new lengths. That would make S6 unplaceable by calculation.
- **storage 6/7 fall *below* their S6-absent values.** The absent column is
  supposed to be a floor; breaching it means the moved stub's susceptance
  actively hurts there, which no measurement so far predicts.
- **any mode outside 5.5–8.0 GHz moves more than ~2 dB.** Would indicate the
  move perturbs the cascade more broadly than a single-stub retune should.
