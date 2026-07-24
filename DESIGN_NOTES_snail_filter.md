# SNAIL Drive-Line Filter — Design Notes (living document)

Last updated: 2026-07-22. This is the standing record of the physics and the
decisions behind the on-chip filter for the SNAIL pump/drive line. Handoff docs
(Rev 1-11) are deltas; this document is the accumulated state. Add to it as the
design evolves.

---

# PART I — PHYSICS

## 1. The system and what the filter is for

The device is a 3D cQED system: storage and buffer cavity modes coupled through
a SNAIL element for parametric beamsplitter interactions, plus a transmon and
readout. The SNAIL chip (7 mm x 40 mm sapphire, 120 nm Al) carries a drive line
fed by a capacitive pin. Beamsplitter drives span 0.5-3.5 GHz. Modes needing
protection from this port: SNAIL mode ~4.5 GHz, storage 5.5-7 GHz, transmon
~7 GHz. The buffer (~3 GHz) is inside the drive band, is driven through this
port, and is unprotected by design.

The drive port is a fundamental conflict: the same coupling that delivers pump
power lets protected-mode energy escape and generator noise enter. The pin's
coupling strength is pinned from below by drive-delivery requirements, so the
only remaining freedom is FREQUENCY SELECTIVITY — pass the drive band, block
the protected band. That selectivity is the filter. It is a band-block problem
(protect 4.2-8 GHz) even though we approached it for a while as a lowpass.

## 2. How the port causes loss (mechanism, not formula)

A protected mode's evanescent field reaches the pin pad, induces a voltage on
the pin, launches a traveling wave down the coax, and that wave is absorbed by
the first dissipative thing it meets (attenuator, generator back-impedance).
Nothing on the chip dissipates; the port is a doorway, and kappa_port is the
escape rate through it. It factorizes as:

kappa_port(w_m) ~ |mode-pin field overlap|^2 x (pin/pad coupling)^2 x Re[Z_env(w_m)]

Three knob families act on the three factors:
- Pin recess depth in its sub-cutoff side tube: coupling decays exponentially
  with depth (evanescent), kappa as the square. Orders of magnitude of range,
  adjustable at assembly, but BROADBAND — it scales drive delivery and leakage
  together.
- On-chip pad/trace geometry and mode-pin placement: broadband, set at litho.
- The filter: the ONLY frequency-selective knob. In its stopband it presents a
  nearly pure REACTANCE at the pad — the mode's induced currents drive a
  lossless network that reflects energy back instead of conducting it to the
  50-ohm termination. The filter does not absorb the photon; it refuses to
  deliver it to anything that can. Re[Z_env] collapses, kappa_port collapses.
  To leading order the suppression is |S21|^2; rigorously, standing waves
  between filter and pin modify Re[Z_env] locally, so final acceptance uses
  Re[Z(w)] or eigenmode Q_ext from the full model, not the S21 multiplication
  (Yale pump-coupling framework, arXiv:2411.07208).

## 3. The attenuation requirement is derived, not chosen

For each protected mode: coherence target -> kappa_total budget; engineering
discipline allocates a fraction (<=10% standard) to the pump port; the bare
(unfiltered) pin-induced kappa_bare comes from HFSS/pyEPR (eigenmode Q_ext to
the 50-ohm-terminated pin, or Re[Y(w)] extraction); the required filter
attenuation at that mode is:

A(w_m) [dB] >= 10*log10( kappa_bare(w_m) / (f_budget * kappa_target(w_m)) )

Properties worth remembering: the requirement is PER MODE, at each mode's own
frequency; it is the gap between what the pin does and what the budget allows —
not a property of the filter; tightening the budget 10x costs only +10 dB;
a second criterion (thermal-noise injection / dephasing through a lightly
attenuated pump line) can be stricter than the T1 criterion — compute both.
The same arithmetic applied at 8-12 GHz (against whatever modes/harmonics
actually live there) settles whether the stopband-recovery region matters.
STATUS: this table is not yet populated — inherited working target is >=40 dB
across 4.2-8 GHz (open item O5).

## 4. The environment: no on-chip ground plane

The chip is bare metal islands on sapphire inside a superconducting Al bore
(6.985 mm dia); the chip spans the bore; ground reference = bore wall,
~3.5 mm away. Literature name: quasi-stripline / "coaxline" (Axline et al.
2016 — "the enclosure acts as the ground plane"). Consequences, learned in
roughly this order:

- eps_eff drops to ~(1+eps_r)/2 territory (measured: 5.681); lengths grow vs
  any microstrip synthesis.
- SHUNT CAPACITANCE IS SCARCE. Any element whose function is lumped C to
  ground (our radial fans) loses its parallel-plate term and keeps only
  fringing: C grows weakly (~linearly, not quadratically) with size. This is
  the single most consequential fact of the whole design history.
- Line impedance is nearly WIDTH-INDEPENDENT (log dependence on width when the
  ground is mm away): measured |Zpi| = 69.7 ohm at both 70 and 125 um. Any
  design leaning on width-controlled impedance contrast is largely inert here.
- Transmission-line LENGTH still works exactly as always. Interference
  (quarter-wave) phenomena are environment-robust; lumped-C phenomena are not.
  THE DESIGN RULE OF THIS ARCHITECTURE: build from lengths, not from
  capacitances. The decade of Yale-lineage tunnel devices (stripline
  readouts + Purcell filters, meandered "wiggles") independently embodies the
  same rule.
- No ground between structures -> everything couples to everything at mm
  range; parasitic bypass around the filter, not synthesis math, will set the
  realized stopband floor. Fold/meander geometry partially self-shields
  (antiparallel currents cancel far fields).
- The bore is far below waveguide cutoff across the band (TE11 ~25 GHz empty;
  loaded, still >>12 GHz): no propagating tunnel modes in band, exponential
  isolation along the bore, and spurious "box modes" seen in earlier
  oversized-vacuum sims should not exist in the real package.

## 5. Filter topologies traversed, and the physics that killed each

1. TAPPED HAIRPIN BANDPASS (pass 4.5 GHz pump): sound design (coupled lambda/2
   resonators; k_ij/Qe synthesis; reentrance at ~2f0), killed by a
   REQUIREMENTS change — drives became 0.5-3.5 GHz, so bandpass-at-4.5 was the
   wrong function. Retained lesson: coupling-matrix method, and reentrant
   passbands of half-wave structures.
2. RADIAL-STUB (butterfly) LOWPASS LADDER, Chebyshev II / elliptic (L30, L45,
   L60): each shunt branch = stalk (series L) + fan (shunt C), zero at the
   branch's series LC resonance; zero frequency ~ 1/sqrt(LC). Worked on paper
   and in ground-planed models; in the real bore the fans starved (see Sec. 4)
   — realized response ~1.4x high, and closing the gap required ~1.7x linear
   growth, resurrecting electrical-length problems. Also learned here:
   - A stalk+fan branch is a stepped-impedance resonator; overtone/fundamental
     ratio grows with stalk-fan impedance contrast. Observed: P3 pair's first
     overtone as a -3 dB doublet at 10.23 GHz (mirror-symmetric branches =
     degenerate pair, split by mutual coupling).
   - Butterfly pairs read from Nuhertz netlists as duplicated entries; "Total
     Height" = 2x worst branch extent (validated transcription check).
   - Folding stalks (hairpin-style meanders) is benign to first order; costs:
     antiparallel-run mutual inductance reduces net L (~5-15% length penalty),
     parallel-run coupling to main line needs >=500 um clearance.
3. QUARTER-WAVE OPEN-STUB BAND-BLOCK (current design, "filter_BB"): stub
   zeros at f = c/(4*l*sqrt(eps_eff)) are LENGTH-set — immune to C starvation.
   Staggered stubs blanket the protected band with overlapping notches.
   Precedent: Hajr et al., PRX 14, 041049 (multi-stub band-block on a SNAIL
   pump line, 2D). Known intrinsic properties: transmission recovers above the
   highest stub (band-BLOCK, not lowpass); stubs re-null at 3f; notch breadth
   was to be set by stub width (dead — see Sec. 4) and is instead set by fan
   end-terminators (capacitive loading damps/broadens the notch and shortens
   the stub, ~0.6*Rout first-order) and by zero density.

## 6. The pin, the passband, and matching

- Input is Axline-style: pin recessed in a sub-cutoff side tube over an
  on-chip pad. Q_ext set jointly by pad geometry (litho) and pin depth
  (assembly, exponential).
- Capacitive pin transfer tilts ~ w^2: the 0.5 GHz drive arrives ~17 dB weaker
  than 3.5 GHz before the filter — a generator-power budget item, and the
  binding constraint sits at the LOWEST drive frequency.
- The filter was synthesized for 50-ohm terminations it will never see: the
  real source is a reactive weak pin, the real load a SNAIL drive capacitor.
  In-band S11 vs 50 ohm is therefore NOT a figure of merit; the acceptance
  quantities are (a) coax-to-SNAIL transfer across 0.5-3.5 GHz and (b)
  Re[Z]/induced kappa at protected frequencies, both from the full
  pin+filter+chip model. Passband ripple seen against 50-ohm sim ports is
  partly a renormalization artifact (line is ~70 ohm).

## 7. CPW alternative (considered, shelved)

On-chip flanking grounds would restore geometric C and make lumped ladders
work — but in a tunnel the grounds FLOAT: a filter-length ground strip is
itself a lambda/2 resonator at ~4-7 GHz (inside the protection band), slotline
modes need dense airbridges (multi-layer fab), and clamp-region grounding is a
pressure contact at best. No published precedent in this package style.
DECISION: shelved with a defined trigger — revisit (finite-ground CPW, meshed
narrow grounds, bridges, CPW-to-strip transitions) only if the stub design
structurally cannot meet the derived spec. A CPW test structure on a dev chip
is the cheap de-risking path if ever needed.

---

# PART II — DECISIONS, ASSUMPTIONS, CURRENT STATE

## 8. Fixed context (answered/locked)

- Chip 7 x 40 mm, 500 um c-plane sapphire (anisotropic 9.4/9.4/11.6 — use the
  tensor in HFSS; it is a few-% effect on eps_eff), 120 nm Al, single optical
  layer (min feature 70 um lines, 88.39 um fan Rin), metal drawn POSITIVE,
  DXF units um, Heidelberg DWL 66+ constraints (no degenerate vertices, closed
  polylines, capped arc discretization, r_inner >= 5 um fan apex guard).
- masklib conventions: emulate existing hairpin resonator code; KLayout XOR
  flow; self-contained per-filter chip files (parameterized shared module
  deferred by choice).
- Package: superconducting Al, cylindrical bore 6.985 mm dia, chip centered
  (mid-thickness on axis => metal plane +250 um), walls modeled PEC. Chip
  (7.000) vs bore (6.985) differ by 15 um — mounting/pocket geometry NOT
  inferable and still outstanding (O1); placeholder pockets in sims.
  Transverse metal budget: <=6000 um (500 um wall-clearance assumption).
- I/O chain on chip: pin pad (1000x1500 um, 5 mm from input edge, provisional)
  -> taper -> filter -> taper to 200 um line ending 1 mm short of the 5x3 mm
  SNAIL keep-out. Alignment marks/furniture deferred until HFSS convergence.
- Nothing is driven above 4 GHz through this port (lowpass/band-block
  architecture final). Buffer ~3 GHz: driven, exempt from protection.

## 9. Calibration (measured in HFSS, 2026-07-21)

- eps_eff = 5.681 at 6 GHz (70 um: 5.6795; 125 um: 5.6826; <0.1% apart =>
  single global constant justified). Method: wave port on full bore cross
  section, ports-only solve, mode verified visually as strip-hugging.
  APPLIED in filter_BB.py.
- |Zpi| ~ 69.7 ohm, width-independent (consequence: stub-width notch control
  abandoned; collapse all stubs to 70 um — pending edit).
- Frequency SWEEP of the port solve produced garbage (eps_eff ~ 1/f^2
  signature => retrieval evaluated a frozen port solution across the sweep;
  beta ~349 rad/m constant, not even the verified strip mode). STANDING RULE:
  for port-only quantities, use N single-frequency setups, never a sweep.
  Dispersion believed sub-% over 4-8 GHz; three extra single-point solves
  (3/5/8 GHz) are the cheap confirmation if wanted.

## 10. Current design: filter_BB (six-stub band-block)

- Stub zero targets: 4.2, 4.7, 5.3, 6.1, 7.0, 8.0 GHz. Lengths from
  l = c/(4 f sqrt(5.681)): 7.61 / 6.80 / 6.03 / 5.24 / 4.57 / 4.00 mm
  (pre-terminator; fan terminator shortens by ~0.6*Rout).
- All stubs 70 um wide (post-calibration decision); interior stubs carry
  ~300 um fan terminators for notch breadth; band-edge stubs plain.
- The 4.2 GHz stub is the passband-edge hazard (83% of quarter-wave at
  3.5 GHz): escalation if >1-2 dB sag — move its zero to ~4.3-4.35 and let
  the 4.7 stub's skirt cover.
- Folding: Rev 5 machinery (d_perp ~1000 um, run_gap 400 um for 70 um lines,
  alternating sides/fold directions, fans axial at meander ends, envelope
  clearance checks >=500 um, centerline length tracked to the um — a 1%
  length error is a 1% zero error). Transverse extent 4984.6 um vs 6000
  budget. Per-stub dl_um trim parameter for HFSS convergence.
- Series spacing between tees: compact 2.5 mm default (classic lambda/4
  spacing ~5.8 mm gives maximally flat composite rejection but costs ~30 mm;
  per-section lengths are the shaping knob in HFSS).
- Fallback design: converged L60 (elliptic fan ladder) retained; candidate
  dev-chip comparison structure.

## 11. Assumptions and simplifications currently load-bearing

- PEC walls (superconducting Al), PerfectE sheet metal (120 nm Al), kinetic
  inductance folded into empirical length trim, not modeled.
- Chip modeled at bore width, no pockets, for line calibration (fields are
  central — safe THERE; the pocket geometry does matter for the full filter
  model near wide structures and for anything near the clamps).
- Lumped ports for filter shaping; real pin model deferred to the final
  acceptance sim (Rev 7 option-b: coax wave port in sub-cutoff side tube).
- S21^2 multiplier picture for protection while shaping; Re[Z]/Q_ext from the
  full model for acceptance.
- 500 um wall clearance and provisional pin-pad location pending package
  drawing (O1).
- >=40 dB across 4.2-8 GHz as the working target pending the kappa budget
  table (O5).

## 12. Open items

- O1: package pocket/clamp drawing (wall clearance, chip mounting, pin tube
  position + diameter). Leaf-spring end-clamps a la the tunnel-package
  literature are the likely scheme.
- O2: chip vertical centering convention (default: mid-thickness on axis).
- O5: populate the kappa budget table (modes x [w_m, kappa_target, budget
  fraction, kappa_bare, required A]) from the full-system no-filter model;
  overlay on simulated S21 as the acceptance test; includes the 8-12 GHz
  verdict. THIS DEFINES "DONE."
- Width-collapse edit (all stubs 70 um) + DXF regen.
- Full filter_BB-in-bore discrete sweep 0.5-13 GHz; dl_um convergence
  (predicted-vs-realized zero table as the dashboard); check passband sag,
  inter-zero floor, and whether the old 5.9 GHz needle exists in the real
  package.
- Final acceptance sim with real pin + SNAIL-side lumped port: transfer +
  Re[Z(w)].
- Dev-chip decision (filter_BB + L60 on one outline for one-cooldown
  comparison?); measurement plan for a filter test chip (two-pin transmission
  tunnel); alignment marks / mask-flow integration with shared lab flow.
- O6 (Rev 11, CLOSED - elliptical/stadium bore parametric study, verdict
  below): does flattening the package bore restore enough lumped shunt C to
  resurrect the L60 fan-ladder and/or meaningfully shift filter_BB's
  eps_eff? Full 6-point bore_h sweep (6.985mm reference down to 1.0mm,
  major axis fixed) across 3 models (bare-strip eps_eff/Zpi; an UNFOLDED
  real-P4-dimensioned branch pair; an UNFOLDED filter_BB-style stub) -
  scripts, raw CSVs, plots, and full verdict text in Radial_Stub_LPF/HFSS/
  (oval_study.csv, oval_study_verdict.txt, oval_*_vs_gap.png).
  **VERDICT: FAN-LADDER NOT VIABLE.** The unfolded P4 branch's own S21
  null stayed essentially FLAT (11.52-11.78GHz, 2.2% spread) across the
  ENTIRE gap sweep (3242um down to 250um) - no evidence flattening
  meaningfully changes this branch's own resonant behavior, so the oval
  buys the fan-ladder nothing practical; the round-bore stub design
  (filter_BB) stands as the design going forward, unchanged. (The
  branch's own ABSOLUTE null, ~11.6GHz, is far from the real P4 design's
  4.752GHz target for reasons unrelated to gap - ruled out via a widened
  sweep and a halved test-bore width, both leaving the null essentially
  unmoved; most likely the unfolded stalk's own transmission-line
  resonance dominates over fan-capacitance loading in this configuration
  - so only the FLAT TREND, not the absolute value, is being used for
  this verdict.) The stub model (filter_BB-style, unfolded) showed a real
  but modest trend (f_zero 6.52-6.72GHz, 3.0% spread) - too small to
  change the stub-length-budget picture. Model A's own eps_eff trend vs
  gap is UNRESOLVED (6GHz and 9GHz selections disagree substantially away
  from the reference point - a field-plot check found both are wall-
  hugging, not strip-hugging, at small gap, and the plot mechanism isn't
  mode-specific enough to arbitrate) - flagged, not resolved; doesn't
  change the verdict above, which rests on the branch/stub models'
  directly-measured S21 nulls, not on Model A's own contested eps_eff.
  Seam modeling and SNAIL-pad capacitance shifts remain explicitly out of
  scope per the handoff (a mid-plane split-block seam is the presumptive
  mechanical choice if this were ever revisited).

## 13. Useful ideas parked for later

- Extra stub tuned onto any surviving high-side feature (stub 3f re-nulls
  start ~12.6 GHz and help beyond).
- Fan terminator growth as the notch-broadening knob; seventh stub if
  inter-zero floors sag.
- Two-length S21-phase eps_eff cross-check (belt and suspenders on
  calibration).
- CPW fallback recipe (Sec. 7) with its trigger condition.
- Backside patterned ground (Option B of the pivot discussion): physically
  strongest capacitance fix; double-sided fab cost; dormant unless topology
  changes again.
- Machine-readable dims export from layout scripts to drive HFSS parametrics.
- Protection-budget table as the single source of truth once O5 lands;
  record every accepted hole (e.g., 8-12 GHz verdict) there explicitly.
