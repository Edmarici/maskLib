# SNAIL Drive-Line Filter - Master Design Notes

**Version 2** (supersedes v1). Living document: the standing record of physics,
method, and decisions for the on-chip filter on the SNAIL pump/drive line.
Handoff docs (Rev 1-21) are deltas against this; this is the accumulated state.

New in v2: **Sec. 2** (general design theory for stub band-block filters, from
microwave-engineering first principles) and **Sec. 3** (the as-built filter:
per-stub data, the meander penalty, and the L-geometry correction). Existing
material renumbered; nothing removed.

**v2.1 (Rev 21), in-repo at `Radial_Stub_LPF/notebooks/`.** Corrections and
additions against v2:

- **Sec. 3.2 — S1 was described as an L stub at 7771.41 um. It is not**, and
  has not been since Rev 18; it is a 2-run meander at a 1000 um gap, drawn
  8749.72 um. Stub table replaced with live values from the frozen tag,
  `[Q4]` placeholders filled.
- **Sec. 3.5 marked HISTORICAL** for the same reason.
- **Sec. 3.3** — the buffer rows already *were* worst-case across +/-150 MHz;
  the caveat saying otherwise is removed. Freeze/tag recorded, with the
  XOR-not-hash rule.
- **Sec. 3.7 (new)** — tolerance sensitivity, including the one case that
  fails.
- **Sec. 3.8 (new)** — zero inventory with provenance.
- **Sec. 9** — k_eff reconciled on one definition; the suspected
  length-reference discrepancy does not exist.
- **Sec. 3.1 / 7** — bore corrected 6.985 -> 7.000 mm.
- **Sec. 13 / 15** — a sixth misattribution added, and three withdrawals.

---

# PART I - PHYSICS AND METHOD

## 1. The problem

A 3D cQED device: storage and buffer cavity modes coupled through a SNAIL for
parametric beamsplitter interactions, plus transmon and readout. The SNAIL chip
(7 x 40 mm sapphire, 120 nm Al) carries a drive line fed by a capacitive pin.

**Pass:** beamsplitter drives, 0.5-3.5 GHz.
**Block (>= 20 dB at each):** two buffer modes at ~4.5 and ~5.0 GHz (exact
frequencies pending simulation, treat as +/- 0.15 GHz) and seven storage modes
at 5.792, 6.160, 6.528, 6.897, 7.265, 7.633, 8.001 GHz.

The drive port is an unavoidable conflict: the coupling that delivers pump
power also lets protected-mode energy escape. Pin coupling is pinned from below
by drive-delivery requirements, so **frequency selectivity is the only free
parameter** - that selectivity is the filter.

### 1.1 How the port causes loss

A protected mode's evanescent field reaches the pin pad, induces a voltage on
the pin, launches a wave down the coax, and that wave is absorbed by the first
dissipative element it meets. Nothing on the chip dissipates: the port is a
doorway and kappa_port is the escape rate through it.

  kappa_port(w_m) ~ |mode-pin overlap|^2 x (pin/pad coupling)^2 x Re[Z_env(w_m)]

Three knob families act on the three factors: pin recess depth (exponential in
a sub-cutoff tube, broadband, assembly-adjustable); pad geometry and mode-pin
placement (broadband, litho-fixed); and **the filter - the only
frequency-selective knob.** In its stopband the filter presents a nearly pure
reactance at the pad: the mode's induced currents drive a lossless network that
reflects energy back instead of conducting it to the 50-ohm termination.
Re[Z_env] collapses, kappa_port collapses. The filter does not absorb the
photon; it refuses to deliver it to anything that can.

### 1.2 The attenuation requirement is derived, not chosen

  A(w_m) [dB] >= 10 log10( kappa_bare(w_m) / (f_budget * kappa_target(w_m)) )

Per mode, at its own frequency; it is the gap between what the pin does and
what the coherence budget allows. Tightening the budget fraction 10x costs only
+10 dB. A thermal-noise-injection criterion can be stricter than the T1
criterion - compute both. **Status: the 20 dB working target is still an
assumption (open item O5).** For a published worked example of exactly this
logic, see Hajr et al.: unfiltered Purcell limit ~12 us -> 30 dB of isolation
-> 12 ms limit, against a measured T1 of 38.5 us.

---

## 2. Designing a stub band-block filter (general theory)

Framework and notation follow Pozar, *Microwave Engineering*, Ch. 2 (lines),
Ch. 4 (network parameters), Ch. 8 (filters). This section is written to stand
alone for a reader who knows RF but not filter synthesis.

### 2.1 The mechanism: a length of line that inverts a boundary condition

A lossless transmission line of characteristic impedance Z_s and length l,
terminated in load Z_L, presents at its input

  Z_in = Z_s * (Z_L + j Z_s tan(beta l)) / (Z_s + j Z_L tan(beta l))

with beta = 2*pi/lambda_g. For an OPEN termination (Z_L -> infinity) this
reduces to

  **Z_in = -j Z_s cot(beta l)**        (open-circuited stub)

Two limits matter:

- **beta l = pi/2 (l = lambda_g/4):** cot -> 0, so **Z_in = 0**. The stub is a
  perfect short circuit at its input even though its far end is physically
  open. This is the quarter-wave line acting as an impedance inverter
  (Pozar Sec. 2.4): it maps an open to a short.
- **beta l << pi/2:** cot -> infinity, so Z_in -> infinity. The stub is
  invisible - a small dangling piece of metal the signal ignores.

That pair of limits *is* the filter: the same object is transparent at low
frequency and a dead short at its design frequency.

**Physical picture.** Signal reaching the tap splits; part travels to the open
end, reflects with coefficient +1, and returns. When l = lambda_g/4 the round
trip is lambda_g/2, i.e. 180 degrees, so the returning wave re-enters the main
line in antiphase with the wave still arriving and cancels it. This is
destructive interference of a signal with its own echo - the same principle as
a quarter-wave side branch in an exhaust or duct. Nothing is absorbed; the
energy is **reflected** back toward the source, which is precisely the property
wanted for protecting a coherent mode.

### 2.2 Transmission through a shunt stub

Tap the stub in shunt on a line of characteristic impedance Z_0. The stub's
normalized shunt susceptance is

  **B(f) = (Z_0 / Z_s) * tan(beta l)**

and for a single shunt susceptance on an otherwise matched line,

  **S21 = 2 / (2 + jB)** ,      **|S21|^2 = 4 / (4 + B^2)**

B -> infinity at l = lambda_g/4 gives S21 -> 0: the transmission zero. The
susceptance recurs at odd multiples, so an open stub also blocks at 3f, 5f, ...
and is transparent at even multiples (l = n*lambda_g/2), where it presents an
open at the tap.

**Sign of B matters and is often forgotten.** Below its resonance
(beta l < pi/2) an open stub's tan is positive - capacitive loading; above
resonance, tan flips sign - inductive. A stub therefore contributes with
*opposite sign* on either side of its own null. In a cascade the total loading
is the sum of every stub's susceptance transformed through the connecting
sections, so a stub can help or hurt at frequencies nowhere near its own zero.
(This was measured in the present design: deleting one stub changed eight modes
by -4.6 to +14.4 dB - see Sec. 3.6.)

### 2.3 Notch width, and why cascade notches look narrower than the formula

Expand about resonance: let beta l = pi/2 + delta, so tan(beta l) ~ -1/delta,
and delta = (pi/2)(f - f_0)/f_0. Setting |B| = 2 (the -3 dB point of a lone
stub) gives a full fractional 3-dB width

  Delta_f / f_0 ~ (2/pi) * (Z_0 / Z_s)

For Z_0 = Z_s this is ~0.64 - very broad. **Measured notch widths in a
multi-stub cascade are far narrower than this**, because a notch's apparent
width is measured against the local composite baseline, not against 0 dB. When
neighbouring stubs already hold the baseline at -20 dB, only the last few
hundred MHz around the zero read as "the notch." The design consequence: notch
*depth* is essentially infinite and uninteresting; what sets performance is the
**composite floor between zeros**, i.e. susceptance summation, not the width of
any individual notch.

### 2.4 Design equations used in practice

Guide wavelength and quarter-wave length:

  lambda_g(f) = c / (f * sqrt(eps_eff))
  **l_(lambda/4)(f) = c / (4 f sqrt(eps_eff))**

For this project's measured eps_eff = 5.681, in convenient units:

  **l [um] = 31446 / f [GHz]**

(Check: 4.5 GHz -> 6988 um; 8.0 GHz -> 3931 um.)

Because a physically folded stub does not present its full drawn length
electrically (Sec. 3.4), the drawn length required to place a zero at f is

  **l_drawn = l_(lambda/4)(f) / k_eff**,   k_eff = f_bare / f_measured

where f_bare is the frequency implied by the drawn centreline length and
f_measured is where the zero actually lands. k_eff is a per-geometry constant
measured once (Sec. 3.4) and reused.

### 2.5 Choosing the zero set

Classical band-stop synthesis (Pozar Sec. 8.5; Matthaei, Young & Jones) starts
from a lowpass prototype, converts to stubs, and fixes both stub impedances and
the connecting-line lengths (canonically lambda_g/4 at band centre) to realize
a specified ripple. **This design does not do that** - the zeros are placed
empirically and the connecting sections are compact - so the filter is properly
described as *distributed-element shunt-stub band-block with empirically placed
zeros*, not as a Chebyshev or elliptic band-stop. Say so in any write-up.

Practical placement rules that did emerge from measurement:

1. Adjacent zeros spaced <= ~1.0 GHz keep the intervening floor below -20 dB
   (measured here: 0.625 GHz spacing -> -22 dB; 1.41 GHz -> -17.8 dB).
   **Qualification:** this rule assumes floors are set by null proximity alone.
   Sec. 2.2 shows they are not - susceptance summation can beat the rule in
   either direction, so use it to seed a design, then screen in a circuit
   model.
2. Place for *valley* coverage, not bullseyes, wherever a target frequency is
   uncertain. A zero is infinitely deep but narrow; a valley is broad and is
   what actually carries a mode whose frequency is only known to +/- 150 MHz.
3. The band-block recovers above the highest zero. Out-of-band behaviour must
   be checked explicitly against harmonics and higher modes, not assumed.

### 2.6 Why length-set zeros, not capacitance-set ones

The textbook alternative is a shunt series-LC branch resonating at
1/sqrt(LC) - in distributed form, a narrow high-Z stalk (inductor) terminated
in a broad radial fan (capacitor). That approach was tried first here and
failed: the fan's capacitance depends on its proximity to a ground plane, and
in a groundless bore (Sec. 4) the parallel-plate term vanishes, leaving only
weak fringing. The realized response landed ~1.4x high in frequency.

A quarter-wave zero depends only on a physical length and eps_eff. Neither
evaporates when ground recedes. **This is the central design argument of the
project:** in a groundless enclosure, build from lengths, not capacitances.

---

## 3. The as-built filter

### 3.1 Environment (measured, not assumed)

| quantity | value | method |
|---|---|---|
| eps_eff | **5.681** | wave-port eigenmode on a bare strip in the true bore; 70 um and 125 um strips agreed to <0.1% |
| \|Z_pi\| | **~69.7 ohm** | same extraction; **width-independent** over 70-125 um |
| bore | **7.000 mm** dia, PEC (superconducting Al) | package drawing; 6.985 mm is the superseded figure - the repo has used 7000 um since the width-budget reconciliation (2*(7000/2-500) = 6000 exactly, which the 6985 figure does not give) |
| substrate | 500 um c-plane sapphire, anisotropic (9.4, 9.4, 11.6) | modelled as a tensor - a few-% effect on eps_eff, and eps_eff is the whole design constant |
| TE11 cutoff | ~25 GHz | far sub-cutoff in band: no propagating enclosure modes |
| main line / stub width | 70 um | see below |

**Consequence of width-independence:** with ground millimetres away, Z depends
on strip width only logarithmically, so the Z_0/Z_s ratio in Sec. 2.2 is pinned
near 1 and *width is not available as a design knob* - not for notch breadth,
not for passband loading. Zero density and geometry are the available levers.

**Method note:** port-only solutions must be taken as single-frequency setups.
A swept port solution returned a frozen mode solution (signature: eps_eff ~
1/f^2 across the sweep). See Sec. 16.

### 3.2 Stub set (as-built, passing configuration)

Design targets and geometry. Drawn lengths are centreline including arcs.

Live from `HFSS/filter_BB_dims.json` at tag `filter_BB_v4_pass9of9`. All stubs
are 70 um wide; `d_perp` is the perpendicular standoff from the tap before the
first turn; drawn length is centreline **including arcs**.

| stub | label | zero (GHz) | geometry | drawn (um) | gap | d_perp | tee y | term |
|---|---|---|---|---|---|---|---|---|
| S1 | 4.5GHz | 4.370 | 2-run meander | 8749.7214 | **1000** | **1200** | 30000 | open |
| S2 | 4.7GHz | 4.870 | 3-run meander | 9776.0928 | 400 | 1000 | 27500 | fan 300 |
| S3 | 5.3GHz | 5.470 | 2-run meander | 7395.2928 | 400 | 1000 | 25000 | fan 300 |
| S4 | 6.1GHz | 6.970 | 2-run meander | 5581.3136 | 400 | 1000 | 22500 | fan 300 |
| S5 | 7.0GHz | 8.730 | 2-run meander | 4307.8079 | 400 | 1000 | 20000 | fan 300 |
| S6 | 6.0GHz | 5.900 | 2-run meander | 7379.3227 | 400 | 1000 | 17500 | open |
| ~~S7~~ | — | — | deleted Rev 17 | — | — | — | — | — |

Tees sit on a uniform 2500 um pitch; main line x=3450, 70 um wide. The `label`
column is the piece-name prefix the deletion tests filter on, and for S6 it is
**only** a label — that stub has not resonated near its nominal target since
Rev 19.

> **CORRECTION (was wrong in v2).** S1 is **not** an L stub and its drawn
> length is **8749.72 um, not 7771.41**. The L geometry was Rev 17 (the v3
> configuration) and was **replaced in Rev 18** by a wide-gap 2-run meander -
> 1000 um run gap, 1200 um standoff - precisely because the L's open end came
> to rest 783 um from S3's fan, the tightest pair in the design and the most
> efficient capacitive coupling geometry available (two voltage antinodes
> facing each other). The 7771.41 figure mixes two revisions: it applies
> Rev 20's 70.56 um trim to Rev 17's L-geometry target of 7841.97 um. Sec. 3.5
> is retained as the record of the L experiment, but it describes a geometry
> that is no longer in the filter.

### 3.3 Performance (Rev 20, tight mesh: delta_S 0.0018621, 5 passes)

| mode | f (GHz) | S21 (dB) | margin to 20 dB |
|---|---|---|---|
| buffer 1 | 4.500 | -27.49 | +7.5 |
| buffer 2 | 5.000 | -28.82 | +8.8 |
| storage 1 | 5.792 | -28.23 | +8.2 |
| storage 2 | 6.160 | -28.79 | +8.8 |
| storage 3 | 6.528 | -27.06 | +7.1 |
| storage 4 | 6.897 | -33.36 | +13.4 |
| storage 5 | 7.265 | -21.38 | **+1.4** |
| storage 6 | 7.633 | -22.38 | +2.4 |
| storage 7 | 8.001 | -22.56 | +2.6 |

**9/9 pass.** Drive band unaffected: -0.58 dB at 3.5 GHz, 3.39 dB passband
ripple.

Two of the three caveats v2 carried here are now closed by Rev 21:

- **Buffer modes are already scored across their +/-150 MHz uncertainty**, not
  at nominal. The two buffer rows in the table above *are* worst-case values -
  buffer 1's -27.49 dB is the worst point in [4.35, 4.65] and occurs at 4.580,
  buffer 2's -28.82 dB is the worst in [4.85, 5.15] at 4.920. At the nominal
  frequencies they read -28.08 and -30.11. So the stronger claim holds: the
  filter passes **across** the stated uncertainty.
- **Fabrication tolerance is folded in** - see Sec. 3.7. Global tolerances pass;
  one single-stub case does not.
- Storage 5's +1.4 dB against ~0.6 dB mesh error stands as a caveat.

**Frozen as tag `filter_BB_v4_pass9of9`** with DXF, GDS, dims JSON, sweeps and
scorecard. Rebuild verified from a clean checkout: dims JSON bit-identical,
GDS **XOR area 0.000000 um^2**, DXFs differing only in their `$TDCREATE` /
`$TDUPDATE` timestamps.

> **Compare geometry with an XOR, never with a file hash.** DXF and GDS byte
> hashes churn on every rebuild. A hash mismatch is not a geometry change.

### 3.4 The meander penalty (measured; the project's most transferable result)

**Why folding is necessary.** The transverse budget is set by the bore
(<= 6000 um of metal across the chip), while stub lengths run 4-10 mm. Stubs
must be folded to fit.

**What folding does.** Adjacent runs of a serpentine carry **antiparallel
currents**. Their mutual inductance is negative, so the net inductance per unit
length of the folded section is reduced. Lower L raises the resonance: the stub
behaves as though it were **shorter than drawn**. The effect scales with how
strongly adjacent runs couple, i.e. with fold count and inversely with run gap.

**Measurement** - four geometries at identical drawn length (6987.9 um, bare
quarter-wave 4.500 GHz), each a single stub alone on a matched through-line in
the real bore, so no cascade effect can contribute:

| geometry | measured resonance | k_eff = f_bare/f_meas |
|---|---|---|
| 3 parallel runs, 400 um gap | 6.830 GHz | 0.659 |
| 2 parallel runs, 1000 um gap | 5.680 GHz | 0.792 |
| **single bend (L)** | **5.050 GHz** | **0.891** |

Monotonic in both fold count and gap, exactly as antiparallel cancellation
predicts. Independent corroboration: applying k_eff = 0.659 to S2 (the design's
other 3-run fold, drawn 9776.09 um, a 40% different length) predicts 4.882 GHz
against 4.760 GHz measured - 2.5%, with the residual in the right direction for
its fan end-loading.

**Why this does not appear in the 2D literature.** In grounded microstrip the
field around a trace extends roughly one substrate thickness (500 um here), so
a 400 um run gap is modest coupling and meandering is benign - which is why
published designs meander freely ("wiggles" in the Yale-lineage stripline
devices; meandered stubs in the Berkeley band-block). With ground several
millimetres away the field extends *millimetres*, and the same 400 um gap
produces near-total coupling between runs.

> **Design rule (transferable):** in a groundless enclosure, meander gaps must
> scale with the distance to ground, not with the substrate thickness.

**Consequence for practice:** k_eff is not a hazard, it is a *calibrated design
constant*. Measure it once per fold topology and design with
l_drawn = l_(lambda/4)/k_eff. What derailed this project for several revisions
was not folding but folding *unmeasured* - searching for zeros at unfolded
frequencies while they sat up to 52% higher (Sec. 15).

### 3.5 The L-geometry correction (S1) — HISTORICAL, superseded in Rev 18

> **This describes the Rev 17 (v3) configuration, not the filter as built.**
> S1 is now a 2-run meander at a 1000 um gap (Sec. 3.2). The L was replaced
> because its axial run put S1's open end 783 um from S3's fan. The k_eff
> 0.891 measurement below is a real fold-experiment result and remains the
> best number available for an L, but no stub in the passing configuration
> uses that geometry. Kept because the *mechanism* - orthogonal segments do
> not cancel - is the transferable part, and because a future stub that needs
> k_eff near unity should start here.

**The failure it fixed.** S1 (the longest stub) and the short-lived S7 produced
no identifiable zero in the design band. They were the two longest stubs, at
different positions in the cascade - S1 immediately after the input taper, S7
mid-structure - which ruled out taper proximity, tee geometry and upstream line
uniformity as causes. What they shared was length, hence fold depth: at 3 runs
and 400 um gaps their zeros had moved ~52% above target, outside every search
window in use.

**The fix.** Replace the serpentine with an L: tap, run **perpendicular** to
the main line for a 2500 um standoff, one arc, then run **axially** alongside
the main line for the remaining length.

Why it works: the two segments are **orthogonal**. Antiparallel cancellation
requires parallel conductors carrying opposed currents; a perpendicular segment
and an axial segment have no such adjacency, so the cancellation term is
absent. Measured k_eff rises from 0.659 to **0.891** - the closest to unity of
any geometry tested.

**Cost and constraints.** The axial run is parallel to the *main line*, so it
needs standoff (2500 um used; >= 1500 um is the working minimum), and it
extends the stub's footprint along the chip, which brings the open end - a
voltage antinode - near downstream structures. In the first L implementation
this cut the S1-to-S3 separation from ~2500 um to 783 um, tip-to-fan, which is
the most efficient capacitive coupling geometry available. Subsequent deletion
testing showed S1's actual perturbation of its neighbours is small (<= 1.1% on
the nearest, <= 0.4% elsewhere), so the coupling concern proved smaller than
feared - but the geometry rule stands: **when converting to an L, re-run
all-pairs clearance, not table-adjacent pairs only.**

**Residual.** Even the L geometry is ~10.9% short electrically (k_eff 0.891,
not 1.000). Candidates: coupling of the axial run to the main line, and bend /
tee-junction reference-plane effects. Open-end fringing is *not* a candidate -
it would lower the resonance, not raise it. Currently absorbed empirically into
k_eff; identifying it is an open item.

**Final placement result:** the S1 trim of 70.56 um moved its zero from 4.340
to 4.370 GHz against a 4.375 GHz target - a 5 MHz miss, confirming that length
decisions must be made against the *discrete-sweep* zero position (interpolating
sweeps read zeros ~14 MHz low).

### 3.6 Off-resonance loading is first-order

Deleting one stub (S6) changed eight of the nine mode attenuations, by -4.6 to
+14.4 dB, at frequencies mostly far from its own zero. Mechanism: Sec. 2.2 -
every stub contributes shunt susceptance at every frequency, with sign flipping
across its own resonance, and the cascade sums these through the connecting
sections. A stub can therefore be simultaneously *valuable* (holding up seven
modes) and *misplaced* (hurting the eighth).

Practical consequences:
- The <= 1.0 GHz spacing rule (Sec. 2.5) is a seeding heuristic, not a
  predictor.
- Placement changes should be screened before solving. The ABCD circuit model
  captures susceptance summation natively and is a **ranking** tool, not a
  forward predictor (1/7 within 2% in a locked-prediction test).
  **Qualification added Rev 21:** it was *not* used for the Rev 20 placement
  or the Sec. 3.7 sensitivity, and the reason is not expedience. It produces
  **one pole per stub by construction**, so it cannot represent a cascade in
  which one stub carries two zeros; making it do so would mean hand-inserting
  a pole fitted to the data being predicted, which has no predictive content
  for a *moved* stub. Where a perturbation is global, rescaling the measured
  curve (Sec. 3.7) is strictly better than any model. Reach for the model when
  the question is "rank these placements", not when measured data can answer
  it directly.
- Deleting a stub to "clean up" a flag can cost more elsewhere than it gains.

### 3.7 Tolerance sensitivity, and which margin is actually fragile

Global perturbations are computed by **rescaling the measured response, not by
modelling it**. A uniform change in every length, or in eps_eff, rescales the
whole S21(f) curve in frequency for a non-dispersive TEM structure, so the
perturbed scorecard is the tight-mesh sweep resampled - exact to that
approximation, with no fitting anywhere. (The ABCD model is deliberately not
used here; see Sec. 3.6's qualification below.)

**All lengths +/-0.25% and eps_eff +/-1%: no mode falls below 20 dB.** Worst
margins storage 5 +1.00, storage 6 +2.35, storage 7 +2.43, storage 1 +3.39.

> **Nominal margin does not rank fragility.** Modes sitting *on* a zero have
> large nominal margin but high sensitivity - storage 1 swings 9.5 dB across
> the eps_eff range. Modes sitting *between* zeros have small margin but are
> nearly insensitive - storage 6 moves 0.05 dB. They arrive at similar
> worst-case values from opposite directions. Rank by worst case, not by
> nominal.

> **RESOLVED by the S6 fan (Rev 21) — see Sec. 3.10.** The fragility described
> in the rest of this section was the reason the fan was added, and the fan
> fixes it: storage 1's worst case under a ±1% S6 error goes from −15.66 dB
> (fail) to −26.92 dB (pass), and its swing over that range from 22.6 dB to
> 2.6 dB. The analysis below is kept because it is *why* the fan exists and
> because the mechanism generalizes. **Storage 4 is now the most
> tolerance-sensitive mode** (12.7 dB swing) for exactly the same structural
> reason - it sits 83 MHz from S4's zero at 6.980 - but it carries enough
> nominal depth to absorb it (worst case −27.3 dB).

**The single-stub case is the one that bites.** A 1% length error on **S6
alone** drives storage 1 to **-14.65 dB, failing by 5.35 dB**:

| S6 length error | its zero | storage 1 | margin |
|---|---|---|---|
| +1.0% (longer) | 5.842 | -38.00 | +18.00 |
| nominal | 5.900 | -28.54 | +8.54 |
| -1.0% (shorter) | 5.960 | **-14.65** | **-5.35** |

The cause is specific and fixable: **S6's zero was aimed at 5.792 GHz and
landed at 5.900, 108 MHz high.** Storage 1's comfortable-looking +8.5 dB comes
from a zero sitting *near* it rather than *on* it, and the exposure is
one-sided - S6 too short pushes the zero further away. Centring it (S6
+1.86%, to 7516.92 um) would take the worst case from -5.35 dB to about
+16 dB. **This is the design's single largest robustness lever and it is not
yet applied.**

**Linewidth +/-5 um is negligible, measured rather than assumed:** the
field-plot-verified 6 GHz extraction gives eps_eff 5.6795 / |Z_pi| 69.71 ohm
at 70 um against 5.6826 / 69.70 ohm at 125 um, so a 55 um width change moves
eps_eff <0.1% and Z ~0.01%. A +/-5 um bias is ~1/11 of that. This is the same
width-independence as Sec. 3.1, seen from the tolerance side.

### 3.8 Zero inventory, with provenance

Ten zeros over 0.5-14 GHz in the passing configuration. **How each ownership
was established is recorded, because this campaign's record on untested
assignments is 0 for 4** (Sec. 13).

| GHz | owner | established by |
|---|---|---|
| 4.370 | S1 | **deletion** |
| 4.870 | S2 | assigned, never tested |
| 5.470 | S3 | assigned, never tested |
| 5.900 | S6 | **deletion** |
| 6.970 | S4 | **deletion** |
| 7.550 | **S5 + S6 jointly** | **deletion** — dies if *either* is removed (Sec. 3.9) |
| 8.730 | S5 | **deletion** |
| 9.965 / 11.360 / 12.375 | — | unowned; explicitly *not* S6 |

Five deletion-confirmed (one of them jointly owned), two assigned but
untested (S2, S3), three unowned.

### 3.8.1 The lower band edge sits ~50 MHz below buffer 1's window

Newly quantified in Rev 21, **pre-existing and not caused by any recent
change** - it is present with and without the S6 fan and at both mesh grades.

Going *down* in frequency from buffer 1's scored window, protection collapses
almost immediately:

| GHz | tight mesh (no fan) | probe (fan) |
|---|---|---|
| 4.500 | −28.08 | −29.09 |
| 4.350 (window edge) | −36.55 | −50.91 |
| 4.300 | **−19.58** | −24.63 |
| 4.250 | **−8.07** | −12.46 |
| 4.200 | — | −4.57 |

**The 20 dB line is crossed at ~4.30 GHz at tight mesh, 50 MHz below the
window's low edge**, and by 4.25 GHz there is essentially no protection at
all. This is the band-block's lower edge doing what Sec. 2.5 item 3 says it
must - the response has to recover somewhere below the lowest zero, and the
drive band needs it to recover by 3.5 GHz - but the *proximity* to buffer 1
had never been measured.

**Consequence for Assumption 2 (Sec. 10).** The buffer frequencies are still
pending simulation and carry ±150 MHz. Within that stated window the filter
passes everywhere. But the uncertainty is **asymmetric in consequence**: a
buffer 1 that lands high is harmless (−28.9 dB at 4.65), while one that lands
even slightly below the stated window falls off a cliff. There is effectively
**no guard band on the low side**.

If the buffer-mode simulation returns a value below ~4.4 GHz, this needs
re-opening before anything else in the design does.

### 3.9 A zero can belong to a PAIR of stubs, not to one (Q1, closed)

The 7.515 GHz zero had resisted attribution for two revisions: it vanishes
when S6 is deleted, yet it ignores S6's length (a 14.64% change moved it
0.40%). Rev 21 settled it by deleting S4 and S5 in turn at the frozen
geometry, same mesh:

| owner | intact | delete S4 | delete S5 |
|---|---|---|---|
| S1 | 4.350 | 4.340 | 4.340 |
| S2 | 4.850 | 4.850 | 4.850 |
| S3 | 5.470 | 5.480 | 5.510 |
| S6 | 5.900 | 5.925 | 5.910 |
| S4 | 6.970 | **vanishes** | 7.135 |
| **?** | 7.515 | 7.215 (−4.0%) | **vanishes** |
| S5 | 8.710 | 8.655 | **vanishes** |

> **The 7.515 GHz zero requires BOTH S5 and S6. Deleting either partner
> destroys it; deleting a non-partner (S4) only perturbs it.**

This also explains the behaviour that made it look paradoxical: its frequency
is set mainly by **S5**, which never moved, so it was insensitive to S6's
length while still depending on S6's presence.

**Consequence for the method.** One-stub-per-zero bookkeeping is not merely
imprecise here, it is structurally wrong: with 6 stubs the design has 10
zeros, and at least one of them belongs to no single stub. A deletion test
answers "does this structure participate", not "does this structure own" -
and participation is the question that matters for a design edit.

Two by-products of the same runs:

- **S5's ownership of 8.710 GHz is now deletion-confirmed** (it was
  "assigned, never tested" in Sec. 3.8).
- **S4 is the most load-bearing stub in the design.** Deleting it collapses
  the filter from 9/9 to **2/9**, with seven modes flagging - and its own zero
  is at 6.970, so almost all of that is off-resonance susceptance (Sec. 3.6).
  Deleting S5 costs 7/9, including storage 1 at -3.94 dB, where removing S5
  opens a narrow transmission *peak* right at the mode. **Caveat:** that
  spike is narrow and read from an interpolating sweep, which reconstructs
  sharp features poorly in both directions; the qualitative collapse is
  certain, the exact depth is not.

### 3.10 The S6 fan: trading depth for flatness, measured

**Probe mesh, pending tight-mesh confirmation.** Change: S6 gains a 300 µm
axial fan (r_in 49.50 µm, 90°) with its drawn centreline **held** at
7379.3227 µm, so the fan is the only variable against the `v6_s6move`
baseline.

**It fixes the Sec. 3.7 fragility.** Storage 1 under a ±1% S6 length error:

| | no fan | with fan |
|---|---|---|
| nominal | −28.65 | −28.24 |
| **worst over ±1%** | **−15.66 FAIL** | **−26.92 PASS** |
| swing over that range | 22.62 dB | **2.62 dB** |
| flatness, mode ±100 MHz | 44.07 dB | **4.11 dB** |
| worst nearby transmission peak | −9.35 @ 5.715 (77 MHz away) | −9.93 @ 5.600 (192 MHz away) |

Under the same ±1% test the whole comb goes from **8/9 to 9/9**.

**The mechanism is not the one that was predicted, and the difference is the
point.** The expectation was that the fan would move the zero onto storage 1
and broaden it. What happened instead: **the deep narrow zero dissolved.** The
−102 dB notch at 5.900 GHz is gone, replaced by a broad shallow shelf running
−24 to −30 dB across 5.65–6.10 GHz. Storage 1 is no longer *near* a sharp
feature, which is why it stopped caring where that feature sits.

> **A fan does not just widen a notch here - it can trade the notch for a
> plateau.** Nominal attenuation at that frequency fell ~74 dB. Under a
> mode-comb spec that costs nothing (Sec. 2.5: depth earns no credit, and
> Sec. 2.3 already argued the composite floor is what matters), but it must be
> stated rather than buried: **this change makes the filter deliberately
> shallower and flatter.** On a spec that rewarded depth it would be a
> regression.

Cost, in full: storage 2 −5.11 dB, storage 4 −3.50 dB, storage 3 −2.29 dB, all
from losing that deep zero's help across 6.1–6.9 GHz; buffer 2 gained 4.99 dB.
All modes keep ≥ +2.4 dB, and the weakest margin in the design did not get
weaker. The S5+S6 two-body zero (Sec. 3.9) moved 7.515 → 7.365 GHz, −2.0%.

**Locked prediction scored 2 of 5 testable** (`HFSS/v8_prediction_locked.md`).
Both misses were framing: the zero's landing frequency was predicted (it
dissolved instead), and storage 1 was predicted to improve *nominally* (it
improved in *robustness*, which is what mattered). The width prediction was
not even scorable, because there is no longer a single zero to measure. One
falsifier - "zero overshoots below 5.70" - **fired**, and on its own terms
reads as failure; it is not, because it assumed the zero would survive as a
zero. Logged as a badly-framed falsifier rather than passed over.

---

# PART II - PROJECT STATE

## 4. Environment consequences (summary)

- Shunt capacitance to ground is scarce; lumped-C elements are strongly
  detuned. Lengths are robust. (Sec. 2.6)
- Line impedance is width-independent (~69.7 ohm). (Sec. 3.1)
- Everything couples to everything at mm range: parasitic bypass, not synthesis
  arithmetic, sets the realized floor; and meander runs couple to each other
  (Sec. 3.4) and to the main line.
- The bore is far sub-cutoff in band: strong evanescent isolation along it, and
  no propagating enclosure modes to confuse spectra.

## 5. Topologies traversed, and what ruled each out

1. **Tapped hairpin bandpass** (pass 4.5 GHz pump) - sound design, killed by a
   requirements change (drives became 0.5-3.5 GHz). Retained: coupling-matrix
   method; reentrant passbands of half-wave structures.
2. **Radial-stub lowpass ladders** (Chebyshev II / elliptic; L30/L45/L60) -
   each branch a stalk (series L) + fan (shunt C). Killed by capacitance
   starvation in the bore: realized ~1.4x high, and closing the gap needed
   ~1.7x linear growth which reintroduced electrical-length problems. Retained:
   stalk+fan branches are stepped-impedance resonators whose overtone/
   fundamental ratio grows with impedance contrast (observed as a -3 dB
   doublet at 10.23 GHz); Nuhertz butterfly-pair netlist reading.
3. **Quarter-wave open-stub band-block** (current) - zeros length-set, immune
   to C starvation. Precedent: Hajr et al., PRX 14, 041049 (2D, grounded).
4. **Flattened/oval bore** (considered) - would restore capacitance by bringing
   machined ground close. Measured: branch resonance moved 2.2% across a bore
   sweep from 3.24 mm to 0.25 mm gap. No benefit; closed.
5. **CPW with on-chip grounds** (considered) - restores geometric C, but the
   grounds float in a tunnel: a filter-length ground strip is itself a
   lambda/2 resonator in the protection band, slotline modes need dense
   airbridges (multi-layer fab), and clamp grounding is a pressure contact.
   Shelved with a defined trigger.
6. **Backside ground plane** (considered) - physically strongest fix; costs
   double-sided fabrication on the SNAIL chip. Dormant.

## 6. Pin, passband, and what is actually being measured

Axline-style pin recessed in a sub-cutoff side tube over an on-chip pad; Q_ext
set jointly by pad geometry (litho) and pin depth (assembly, exponential).
Capacitive transfer tilts ~w^2: the 0.5 GHz drive arrives ~17 dB weaker than
3.5 GHz before the filter, so the generator-power constraint binds at the
lowest drive frequency.

**The filter is simulated against 70-ohm lumped ports it will never see.** The
real source is a reactive weak pin, the real load the SNAIL drive capacitance.
In-band S11 against a matched port is therefore *not* a figure of merit. The
acceptance quantities are (a) coax-to-SNAIL transfer across 0.5-3.5 GHz and
(b) Re[Z] / induced kappa at the protected frequencies, both from the full
pin+filter+chip model (Stage A, queued).

## 7. Fixed context

Chip 7 x 40 mm, 500 um c-plane sapphire, 120 nm Al, **single optical layer**
(min feature 70 um), metal drawn positive, DXF in um, Heidelberg DWL 66+ rules
(closed polylines, no degenerate vertices, capped arc discretization, r_inner
>= 5 um). masklib conventions; emulate the hairpin resonator code; KLayout XOR
flow; self-contained per-filter chip files. Package: 7.000 mm bore, chip
centred (mid-thickness on axis), PEC walls; pocket/clamp geometry still
outstanding (O1). I/O chain: pin pad (1000 x 1500 um, 5 mm from input edge,
provisional) -> taper -> filter -> taper -> 200 um line ending 1 mm short of
the 5 x 3 mm SNAIL keep-out.

## 8. Simulation practice

- **Model discipline:** PEC bore, PerfectE metal, lossless sapphire, ports
  renormalized to the measured line impedance. Exactly one dissipative element
  (the terminating port) so that any extracted loss is attributable by
  construction.
- **Adaptive frequency matters.** Stopband-centred adaptation under-resolves the
  largest, lowest-frequency structures. Use multi-frequency adaptive spanning
  the region of interest.
- **Sweep type matters for length decisions.** Interpolating sweeps read zero
  positions ~14 MHz low; use discrete windows when a length is being set.
- **Mesh calibration (measured twice, two geometries):** probe-grade settings
  (delta_S 0.02, ~1 h) agree with tight settings (delta_S 0.005, ~7 h) to
  0.45-0.61 dB mean on mode attenuations. Probe grade is adequate for
  directional decisions; tight grade for scorecards.

## 9. Measured values (running record)

- eps_eff = 5.681; |Z_pi| ~ 69.7 ohm, width-independent (Sec. 3.1).
- **k_eff, reconciled on ONE definition (Rev 21 Q4 - closed).** Definition:
  `k_eff = f_bare / f_zero`, `f_bare = c/(4 L sqrt(eps_eff))`, `L` = drawn
  centreline **including arc length** = `realized_length_um` in the dims JSON.

  | case | L (um) | zero | k_eff | provenance |
  |---|---|---|---|---|
  | 3-run / 400 um | 6987.90 | 6.830 | 0.6589 | isolated |
  | 2-run / 1000 um | 6987.90 | 5.680 | 0.7923 | isolated |
  | L geometry | 6987.90 | 5.050 | 0.8911 | isolated |
  | straight | 6987.90 | 5.450 | 0.8257 | isolated, **wide bore - not comparable** |
  | S6 topology 2-run/400 | 6436.90 | 6.780 | 0.7205 | isolated |
  | S6 in cascade, old L | 6436.90 | 6.640 | 0.7357 | deletion |
  | S6 in cascade, frozen | 7379.32 | 5.900 | 0.7223 | deletion |
  | S1 in cascade, pre-trim | 8820.28 | 4.340 | 0.8215 | deletion |
  | S1 in cascade, frozen | 8749.72 | 4.370 | 0.8224 | deletion |
  | S2 in cascade, frozen | 9776.09 | 4.870 | 0.6605 | **assigned, not tested** |

  **There is no length-reference discrepancy.** Every k_eff quoted anywhere in
  this project recomputes to <0.002 under the definition above. The
  alternative (straight runs only, arcs excluded) would give k_eff > 1 in two
  cases, unphysical under the fold-cancellation reading, so it was never in
  use. The real inconsistency was the **numerator**, twice: S6 was quoted at
  0.6886 against the geometric *mean* of a zero pair (that reading is
  withdrawn - Sec. 15 - so 0.6886 is retired for 0.7357/0.7223), and S2 was
  quoted at 0.664, which corresponds to a 4.845 GHz zero rather than the
  4.760 GHz cited alongside it. **S1 in situ is 0.8215/0.8224, not 0.8243** -
  the older figure came from an interpolating sweep reading the zero at 4.325
  instead of the discrete 4.340.
- **k_eff drifts ~2% between lengths for the same topology** (S6: 0.7357 at
  6436.90 um vs 0.7223 at 7379.32 um), so it transfers but is not a constant.
  Prefer direct 1/length scaling for a length edit (Sec. 8).
- Zero-spacing vs floor: 0.625 GHz -> -22 dB; 1.41 GHz -> -17.8 dB.
- Rev 20 passing scorecard: Sec. 3.3.
- Oval-bore sweep: branch resonance 11.52-11.78 GHz across all gaps (2.2%).
- Isolated folded stub produces ONE zero (6.780 GHz for S6's topology).

## 10. Load-bearing assumptions (things that could still be wrong)

1. 20 dB is the right target (O5 undone).
2. Buffer modes at 4.5/5.0 GHz +/- 0.15. **The +/-0.15 window is now scored
   in full** (Sec. 3.3) - what remains assumed is the centre frequencies
   themselves, which are still pending simulation.
3. Lumped 70-ohm ports stand in for the pin and SNAIL loads.
4. PEC walls; kinetic inductance folded into empirical k_eff, not modelled.
5. Chip modelled at bore width, no pockets (O1 outstanding).
6. k_eff transfers between lengths (validated to 2.5% once on S2; measured to
   drift ~2% for one topology across a 15% length change - Sec. 9). For a
   length *edit*, direct 1/length scaling is the better instrument and has
   been confirmed twice on real solves.
7. **Off-resonance susceptance is first-order** - added v2; null-placement-only
   reasoning is insufficient (Sec. 3.6).
8. Circuit model is a ranking tool, not a forward predictor.

## 11. Open items

- **O5:** populate the kappa budget (modes x [w_m, kappa_target, budget
  fraction, kappa_bare, required A]) and replace the 20 dB assumption. This
  defines "done."
- **O1:** package pocket/clamp drawing; pin tube position and diameter.
- **Q1 (Rev 21, CLOSED):** the 7.515 GHz zero is a **two-body feature of the
  S5-S6 pair** - see Sec. 3.9.
- **Q2 (CLOSED):** see Sec. 3.7. Global tolerances all pass; a 1% error on S6
  alone fails storage 1 by 5.35 dB.
- **Q3 (CLOSED):** buffer worst-cases are -27.49 and -28.82 dB across the full
  +/-150 MHz - both pass. See Sec. 3.3.
- **NEW (Rev 21):** centre S6's zero on storage 1 (+1.86%, 7379.32 ->
  7516.92 um). Largest available robustness gain in the design: converts
  storage 1's worst case from -5.35 dB to about +16 dB. Interacts with the
  fan below - resolve together.
- **NEW (Rev 21, GEOMETRY APPLIED — NOT YET SOLVED):** fan terminator on S6
  (Rout 300 um, r_in 49.50 um, 90 deg, axial), drawn centreline held at
  7379.3227 um, dl_um 2120.8689 -> 2274.6403285714. Rebuild verified: S1-S5
  unchanged to 1e-6 um, merged polygon count 1, **0 holes** (the fan-on-a-
  folded-trace hole risk did not materialize), all stub-to-stub clearances
  unchanged at >= 1200 um, S6's transverse edge moved to x=1532.9 (1583 um of
  bore clearance), transverse budget unchanged at 5227.1/6000 um. The HFSS
  replay picked the fan up through its existing generic path - S6 now yields
  7 pieces including `6.0GHz_fan_taper` and `6.0GHz_fan`, total 55 vs 53.
  **Needs a solve to place the zero.** Rationale:
  to broaden its zero rather than leave it sharp - directly targeting the
  Sec. 3.7 fragility, since a broader zero is less sensitive to where exactly
  it lands. Decision taken: hold the drawn length at 7379.3227 um and fold the
  153.77 um fan correction into dl_um, so the fan is the only variable. Its
  predicted side effect - the added end-loading pulls the zero down ~2.1% from
  5.900 toward ~5.78 - happens to centre it on storage 1 as well, which would
  address both open items in one solve. **Prediction rests on the fan
  correction formula, which is the class of theory correction that has been
  percent-level wrong all campaign; treat as a direction, not a number.**
- Residual 10.9% in the L geometry unexplained (Sec. 3.5).
- Stage A: pin + SNAIL-port model for transfer and Re[Z].
- Dev-chip decision; measurement plan (two-pin transmission tunnel);
  alignment marks and mask-flow integration.
- ~11.8 GHz reentrance logged; out-of-band inventory against harmonics.

## 12. Parked ideas

Seventh stub (retired: 9/9 achieved, and a folded stub gives one zero, not a
designed pair); wider-gap folds as a deliberate k_eff choice; backside ground;
CPW fallback with its trigger; machine-readable dims export driving HFSS
parametrics; section-length (connecting-line) optimization for passband ripple -
the classical knob, still never exercised.

---

# PART III - METHODOLOGY LESSONS

## 13. Attribution: the campaign's recurring failure

Five separate misattributions occurred, all from the same root: **assigning a
zero to a stub by inference rather than by test.** Specifically -

1. A swept port solution returning a frozen mode (eps_eff ~ 1/f^2).
2. A peak-finder accepting a 1.5 dB passband ripple dip as a transmission zero.
3. A double assignment - two labels resolving to the same feature (5.633 GHz).
4. A search window centred on a stub's *target* frequency, for stubs whose
   folds put them up to 52% higher.
5. A "rigid split pair" reading of one stub's two nulls, which a length change
   disproved (14.64% length -> 11.08% and 0.40% shifts).
6. **The evidence FOR that split-pair reading was itself an untested
   inference** - and this is the sharpest instance in the set. S6's zeros at
   its old length were said to "predict" two unexplained census zeros at
   11.110 and 12.535 GHz to 0.23%, which is better agreement than anything
   else in the campaign produced. That assignment was never deletion-tested.
   Across three S6 lengths those zeros moved +2.3% and -1.3% while S6 grew
   1.911x: they were never S6's, and the 0.23% was coincidence. The failure
   mode is worth naming precisely - **a number was believed because it agreed
   closely with a wanted conclusion, and closeness of agreement was treated as
   a substitute for the test.**

Three of these produced confident, plausible, wrong conclusions that survived
multiple revisions. In one case a locked forward prediction scored 4/9 with two
errors that cancelled - without the pre-committed file it would have read as
vindication.

## 14. The rule that survives

> **No zero is attributed to a structure until that structure is deleted and
> the zero is observed to vanish.**

**Amended Rev 21:** deletion establishes *participation*, not sole ownership.
The 7.515 GHz zero dies when either S5 or S6 is removed (Sec. 3.9), so a
single deletion would have "proved" it belonged to whichever stub was tried
first. **Delete every plausible participant, not just one**, and read a
vanishing zero as "this structure participates" rather than "this structure
owns it."

Deletion needs no frequency matching, no search window, no depth threshold, and
no assumption about how far a fold has moved a resonance. It also measures, in
the same solve, that structure's off-resonance contribution to every other
mode. It resolved S1's identity, S6's ownership, and the S7 question after
inference had failed on all three.

Supporting practices: enumerate zeros label-independently before assigning any;
report "NO ZERO FOUND" rather than the shallowest local minimum; lock
predictions to a committed file before solving; and record withdrawals as
withdrawals rather than silently editing them (Sec. 15).

## 15. Withdrawal record

- **"S1 is electrically absent."** Withdrawn. Refuted by deletion (removing S1
  cost 13.6 dB at buffer 1) - S1 owns the 4.325/4.370 GHz zero.
- **"S1-S3 hybridization explains the 5.870 -> 5.480 GHz shift."** Withdrawn as
  unproven: deleting S1 outright moves that zero by <= 0.4%.
- **"S6 produces a rigid split pair."** Withdrawn: a 14.64% length change moved
  the lower zero 11.08% and the upper 0.40%. The upper zero requires S6's
  presence but not its length; its mechanism is unidentified (Q1).
- **"The 4.325 GHz zero protects nothing."** Withdrawn (author: assistant):
  deletion showed it carries buffer mode 1 by 13.6 dB. The proposed retarget
  would have traded a 1.8 dB flag for a 10.6 dB one.
- **"S6's zeros scale together with S6's length, confirmed to 0.23%."**
  Withdrawn (author: assistant). The confirming zeros (11.110 / 12.535 GHz)
  were never deletion-tested and are not S6's - see Sec. 13 item 6. This
  claim was load-bearing for the Rev 20 placement, which still produced 9/9,
  so **a correct outcome does not validate the reasoning that reached it**;
  the locked pre-solve prediction scored 4/9 with two errors that cancelled.
- **"S1 is an L stub, drawn 7771.41 um."** Withdrawn (v2 text, corrected
  Rev 21): S1 has been a 2-run meander at a 1000 um gap since Rev 18, drawn
  8749.72 um. See the correction box in Sec. 3.2.

## 16. Instrumentation notes

- Port-only extractions: single-frequency setups only.
- Stopband dB sign convention: more negative = better. State it in code; a
  sign inversion once produced an inverted verdict.
- Interpolating sweeps: ~14 MHz low on zero position.
- Probe vs tight mesh: 0.45-0.61 dB mean agreement; ~1 h vs ~7 h.
- AEDT hygiene: prune superseded designs; save-and-close between solves; an
  RPC crash mid-post-processing has already cost a full re-solve.

---

# References

- D. M. Pozar, *Microwave Engineering*, 4th ed. (Wiley) - Ch. 2 (transmission
  lines, quarter-wave transformer), Ch. 4 (S/ABCD parameters), Ch. 8 (filters,
  incl. stub band-stop synthesis).
- G. Matthaei, L. Young, E. M. T. Jones, *Microwave Filters, Impedance-Matching
  Networks, and Coupling Structures* (Artech, 1980) - band-stop synthesis.
- O. Naaman, J. Aumentado, "Synthesis of parametrically coupled networks,"
  PRX Quantum 3, 020201 (2022).
- C. Axline et al., APL 109, 042601 (2016) - coaxline architecture; the
  enclosure as ground plane.
- J. Rahamim et al., APL 110, 222602 (2017) - double-sided coaxial package.
- H. Hajr et al., PRX 14, 041049 (2024) - band-block filter on a SNAIL pump
  line; 30 dB isolation; Purcell-limit argument for the requirement.
- Y. Dai et al., arXiv:2411.07208 - pump-coupling optimization; Thevenin
  impedance framework; hairpin + radial-stub filters with backside ground.
- Reed et al., APL 96, 203110 (2010); Bronn et al., IEEE TAS 25, 1 (2015);
  Zhou et al., J. Appl. Phys. 135, 024402 (2024) - Purcell filter lineage.
- Sah et al., arXiv:2402.08906 - on-chip filters for decay-protected qubits.
