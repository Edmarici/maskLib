# filter_BB — quarter-wave open-stub band-block filter — design notes

Companion to [`filter_BB.py`](../filter_BB.py). See that file's own module
docstring for the full principle/rationale/decision log - this doc is the
build-session record (what was run, what it showed).

## 1. Why this exists

Rev 8 design pivot (Option A), replacing the L30/L45/L60 lumped-LC ladder
family for the SNAIL protection filter. This session's own L60 Phase 2 real-
package HFSS sim (see `L60_design_notes.md` sec 11) confirmed the ladder
can't reach its intended cutoff inside the real 7.0mm Al cavity: 4.5GHz
attenuation came back at essentially 0dB, because the bore walls are >3mm
away and fan capacitance is fringing-only - no amount of fan-scaling closes
that gap. Open-circuited quarter-wave stubs set their zero by LENGTH and
eps_eff only, not capacitance to ground, so they're immune to the same
starvation. `filter_L30.py`/`filter_L45.py`/`filter_L60.py` are untouched -
L60 stays the fallback/comparison design per the handoff.

## 2. Chip width / package numbers

Confirmed with Eddie: 6.9mm chip width (not the handoff's literal "7x40mm"
line), matching `filter_L60.py`'s own just-revised real chip width for the
same 7.0mm-bore package. Supporting evidence: the handoff's own stated
"<=6000um" width budget only comes out *exact* (2*(7000/2-500)=6000) using
the revised 7.0mm bore, not the stale 6985um figure (which gives 5985) -
the same class of stale-carryover number already found twice in these
handoff docs this session (L60's own 5.5mm/4500um and 6985um figures).

## 3. Geometry decisions (implementing an underspecified handoff)

- **No positive-metal tee primitive exists** anywhere in maskLib (checked
  `microwaveLib.py` directly - only `CPW_tee`, XOR-gap-only). Stubs tee
  off the main line the same hand-built-overlap way `filter_L60.py`'s
  branches already do (`Structure.cloneAlong()` at the main line's current
  point) - just single-sided here (one stub per junction, not a mirrored
  pair).
- **"Reuse the Rev 5 folded-branch generator verbatim"** = `filter_L30.py`'s
  `folded_branch_pair()` exact-length-by-construction solve, not
  `maskLib.microwaveLib.wiggle_calc()`/`CPW_wiggles` (a different, more
  general meander-length solver that also exists in this codebase, checked
  and ruled out - belongs to the CPW/XOR family, not what "Rev 5" means in
  this repo's own terminology).
- **`folded_stub()` is new** (not a copy): combines `folded_branch_pair()`'s
  entrance-turn + n_bends-internal-turns machinery with
  `l_bend_branch_pair()`'s "no exit turn" idea (generalized from l_bend's
  single turn to n_bends turns), single-sided. The missing exit turn is
  deliberate - this handoff wants fan terminators AXIAL (the *opposite* of
  L60's own perpendicular-fan convention, which needed the exit turn
  specifically to rotate back to transverse per Eddie's L60 Rev7
  correction). Turn-arc length: `pi*bend_radius*(n_bends+0.5)` (entrance
  90deg + n_bends*180deg, vs. `folded_branch_pair()`'s `(n_bends+1)` which
  includes the exit turn) - `run_length` solved from this exactly, same
  discipline as the L60 family.
- **`fan_term`'s r_in is derived**, not specified by the handoff, so the
  90deg terminating fan attaches FLUSH to the stub width (`r_in =
  w/(2*sin(45deg))`, no Rev7-style deliberate flare - nothing here asked
  for one). For w=125um this comes out to r_in=88.39um - the same value
  L60's own P2-P5 fans used before Rev7's FAN_ANGLE=115 change, a useful
  cross-check that the derivation is principled.
- **`run_gap = max(4*w, _MIN_RUN_GAP_UM)`** reproduces the handoff's stated
  500um (125um stubs)/400um (70um stubs) exactly from one general rule
  (same self-coupling-margin-floor concept as L60's own `_MIN_RUN_GAP_UM`),
  rather than hardcoding per-stub values.
- **`fold_dir` alternates per SIDE GROUP**: three stubs share side=+1
  (4.2/5.3/7.0GHz), three share side=-1 (4.7/6.1/8.0GHz); within each group
  fold_dir alternates +1,-1,+1 so same-side stubs don't all curl the same
  way.

## 4. Build session results (Rev 8 — FIRST BUILD, superseded)

> **Historical.** The numbers in this section are the original Rev 8 layout at
> `EPS_EFF=5.5` with a 4.2GHz S1 and no HFSS behind them. Every length here
> has since changed. Kept because the *method* notes (exact-length-by-
> construction, the fold_dir bug) still apply. For current numbers see sec 9
> onward.

`filter_BB.py` ran clean on the first real attempt (repo `.venv`) after one
report-only bug fix (see sec 5). Runtime report highlights:

```
Realized transverse bounding box: 4984.6 um (budget 6000.0 um) - UNDER BUDGET
(1015.4um margin - unlike every L60 revision, which stayed over budget)
Realized axial (length) extent: 27500.0 um
```

Per-stub target-vs-realized centerline length (the handoff's own explicit
requirement - "a 1% length error is a 1% zero error"): **all six stubs
matched to 0.0000um** (exact by construction, per `folded_stub()`'s solved
`run_length` - the printed check is a verification of the arithmetic, not
an approximation).

```
4.2GHz: target=7609.24um, realized=7609.24um, open end
4.7GHz: target=6619.74um, realized=6619.74um, fan Rout=300um r_in=88.39um
5.3GHz: target=5849.96um, realized=5849.96um, fan Rout=300um r_in=88.39um
6.1GHz: target=5059.15um, realized=5059.15um, fan Rout=300um r_in=88.39um
7.0GHz: target=4385.54um, realized=4385.54um, fan Rout=300um r_in=88.39um
8.0GHz: target=3994.85um, realized=3994.85um, open end
```

Nearest-neighbor clearances all comfortable (min 1307.7um, 4.7<->5.3GHz -
no `<<CHECK` flags at the 500um threshold).

**One real bug found and fixed during this build** (report-only, not a
geometry bug): the runtime report's `fold_dir` print initially leaked the
LAST value of the build loop's own `fold_dir` variable into a SEPARATE
print loop (Python `for`-loop variables aren't block-scoped), so every
stub printed `fold_dir=+1` regardless of its real value - even though the
actual DRAWN geometry was correct throughout (the real per-stub
`fold_params['fold_dir']` was set correctly before each `folded_stub()`
call). Fixed by carrying `fold_dir` through `stub_report`'s own tuple
instead of relying on the leaked loop variable. Re-run confirmed the
correct per-side alternation (+1,-1,+1 within each side group).

## 5. Build-time / Heidelberg-safety checks

Same klayout `Region` merge + hole-area technique as every L30/L60
revision (`check_L60_rev7_safety.py`'s own pattern, layer (2,0) = BASEMETAL
per `filter_L30.py`'s cross-check precedent), run against the real
exported `DXF/filter_BB_CHIP_BB.gds`:

```
Merged BASEMETAL polygon count: 1
Total holes: 0, largest area 0.0000 um^2
Raw (unmerged) BASEMETAL shape count: 896
RESULT: ALL CHECKS PASSED
```

**The axial-fan-hole risk flagged before building did not materialize**:
`fan_term`'s Rout (300um) is far smaller than L60's own synthesized fans
(1100-2000um), and at this size the fan doesn't reach back over its own
fold's open mouth the way L30/L60's axial-fan dead-ends did (see
`L60_design_notes.md` sec 10.2, CLAUDE.md's own general warning on this
mechanism). Confirmed 0 holes, not just assumed.

Visual check (matplotlib render of the real exported GDS, same technique
as prior L30/L60 sessions): the 4.7GHz stub (fan_term=300) shows a clean
two-U-turn zigzag with the terminal fan pointing AXIALLY (continuing the
last run's own direction, straight past the final bend, not rotated back
toward the main line) - exactly the intended, deliberately-different-from-
L60 orientation. The 8.0GHz stub (fan_term=0) shows a clean single-U-turn
zigzag ending in a plain flat open edge, no artifacts.

## 6. Known open items (carried from the handoff)

- ~~**EPS_EFF=5.5 is a PLACEHOLDER**~~ **RESOLVED.** `filter_BB.py` now
  carries `EPS_EFF = 5.681` from a real extraction (see
  [`extract_epseff.py`](../extract_epseff.py) and
  [`epseff_extraction_status.md`](epseff_extraction_status.md)). Every
  length is still a pure function of the constant, so this recomputed the
  whole table. Caveat that matters downstream: it was extracted from a
  bare through-line, and sec 8 below shows a *folded stub* does not behave
  as if it has that eps_eff - the fold penalty is a separate, larger
  effect that has to be corrected for on top.
- **fan_term's 0.6*Rout length correction is the handoff's own stated
  first-order guess**, not independently verified - "HFSS trims" per the
  handoff, via the per-stub `dl_um` field already present (currently 0 for
  all six).
- **O1 (package pocket drawing)** and **O2 (chip vertical centering)**
  remain open, same as L60's own carried-forward items - not needed for
  this layout-only pass, will matter once a real package HFSS model is
  built for BB (out of scope this session - see `filter_BB.py`'s own
  "SCOPE OF THIS PASS" docstring note).
- **The handoff's full "HFSS plan"** (eps_eff extraction, full package
  sweep, per-stub dl_um walking, L60-in-package comparison) is explicitly
  gated/Eddie-side and not attempted this session - `filter_BB.py`'s
  deliverable this pass is layout + DXF/GDS + safety checks + the target-
  vs-realized length report only, matching the handoff's own framing.
- **O5 (new)**: whether >=40dB across 4.2-8.0GHz is the right target, or
  whether per-mode kappa_ext numbers should size the stub count instead -
  unresolved, Eddie's call.

---

# Part II — HFSS revisions (Rev 12–18)

Everything above is the pre-HFSS layout record. Everything below is measured.

## 7. Line impedance — all three conventions (Rev 15)

Four design decisions rested on a characteristic impedance of which only
`|Z_pi|` had ever been reported. Pulling the other two required deleting and
recreating the ports and re-solving (this AEDT version bakes the impedance
convention in at port-creation time — there is no post-hoc property to query,
confirmed by inspecting the live boundary's property list).

```
Z_pi = 69.71 ohm      <- what the design and the 70-ohm ports use
Z_pv =  0.41 ohm
Z_vi =  5.37 ohm
```

`Z_vi = sqrt(Z_pi * Z_pv)` holds to 4 significant figures, so the three are
self-consistent. The **spread is enormous**, which is the actual finding: on a
chip with no on-chip ground plane the nearest reference conductor is ~3.5mm
away, so any voltage line integral depends strongly on the integration path.
Attributed to that, plausibly but **not proven** — the identity holding does
not by itself validate the physical interpretation.

Practical consequence: `Z_pi` is the only one of the three that means what a
circuit model needs, and it is the one already in use. No design change.

## 8. The fold penalty — measured, and it is large (Rev 17)

> **Read sec 15.2 with this section.** Every `k_eff` below is the *one* null
> each variant shows over the full 0.5–14GHz band — that much is verified, not
> windowed. But Rev 19 found a folded stub can own a null *pair*, which makes
> "the" `k_eff` of a fold ambiguous unless you say whether it means the null
> you can see or the centre of a pair. Do not mix these numbers with sec 15's
> without reading 15.2 first.

**This is the most reusable result in the campaign.** Several stubs had
"missing" notches across Rev 12–16. The cause was not that they failed to
resonate; it was that folding shortens a stub's *effective electrical length*
enough to push its resonance outside the search window that was looking for it.

Measured directly ([`filter_BB_fold_experiment_HFSS.py`](../filter_BB_fold_experiment_HFSS.py)):
one stub alone on a matched through-line, four geometries at an **identical**
6987.90um drawn centerline length, in the **real** 7000um bore.

| geometry | null | k_eff | comparable? |
|---|---|---|---|
| 3 parallel runs, 400um gap | 6.830 GHz | 0.659 | yes |
| 2 parallel runs, 1000um gap | 5.680 GHz | 0.792 | yes |
| **L (single 90deg bend)** | **5.050 GHz** | **0.891** | yes |
| straight, no bend | 5.450 GHz | 0.826 | **NO** — see caveat |

`k_eff` = (bare quarter-wave frequency) / (measured null frequency). 1.0 would
mean the drawn length resonates where lambda/4 theory says. All four are bare
4.500GHz by construction.

**The rule:** in this groundless bore, adjacent antiparallel meander runs
partially cancel. The resonance does **not** disappear at any fold depth
tested — it *shifts up*, monotonically in both fold count and run gap. Fewer
folds and wider gaps are always electrically better; the L geometry is the
best that fits.

Cross-check: applying the 3-run k_eff to S2 (the only other 3-run fold,
9776.09um drawn) predicts 4.882GHz against a measured 4.760GHz — 2.5%.

Three caveats, all load-bearing:

- **V-straight is not comparable.** 6988um of perpendicular reach does not fit
  a 3500um-radius bore at all; it needed a 16mm bore, which changes the
  implied eps_eff to 3.87 vs 5.681. So the cleanest possible control does not
  exist, and the rule rests on the monotonic trend across the three real-bore
  variants instead.
- **Even the L geometry lands 12.2% high.** Its own residual is applied as an
  explicit empirical correction at the call site, not explained. Whether the
  cause is stub-vs-through-line eps_eff, tee loading, or something else is a
  real open question — logged, deliberately not chased.
- **`HFSS/foldexp_results.csv` records V-fold-wide as `NO` notch.** That is the
  windowed search (3.5–5.5GHz) reporting, not physics: the full coarse sweep
  found it cleanly at 5.680GHz. The CSV row is a live example of exactly the
  blind spot this section explains — read it with the log, not alone.

## 9. v3 — the first passing configuration (Rev 17)

Changes from the v2+S7 baseline: **S7 deleted outright** (it produced no notch
while still costing ~2.5mm of line and adding passband shunt susceptance) and
**S1 retargeted 4.2 -> 4.5GHz on the L geometry**, with the measured 1.1222
residual from sec 8 applied as a length correction (7841.97um drawn). S2–S6
frozen byte-identical.

Tagged **`filter_BB_v3`**, solve outputs committed under `HFSS/v3_confirm_*`.

```
                              v3          v2+S7
S21 @ 4.5GHz            -33.56 dB     -10.94 dB     <- headline, target <=-20dB
worst S21 4.7-5.3GHz     -7.39 dB      -5.29 dB     <- "the hole"
worst S21 5.5-7.0GHz    -21.93 dB     -20.42 dB
passband ripple (spots)   2.75 dB       3.19 dB
band edge (-10dB)        3.880 GHz     4.310 GHz    <- reported, NOT scored
```

**S21@4.5GHz improved 22.6dB and passes the SNAIL criterion for the first
time.** That number is a direct trace readout at the criterion frequency — no
labelling, no matcher, no search window — and it is the one result in this
campaign that cannot be reinterpreted.

Everything else is more equivocal and should be read that way:

- The passband improvement is real but small (0.44dB on spot ripple). The
  dominant ~-3.1dB dip near 1.05GHz is present in both and is **not**
  stub-related.
- The band edge moved *down* 430MHz. Deliberately not scored — the criterion
  predates S1's retarget and no longer means what it did.
- 8–14GHz has three features above -30dB, one at **11.925GHz at -1.2dB**, an
  essentially wide-open transmission window. Only matters if pump harmonics up
  there are a concern, but it is worse than v2+S7's equivalent.

## 10. ~~OPEN~~ RESOLVED: the v3 null attribution (see sec 14)

> **Closed by deletion, not by argument.** Both readings below were wrong in
> the same way: each assumed one null per stub. S1 owns 4.325/4.340GHz,
> confirmed by removing it. The full census found 12 nulls for 6 stubs, so the
> "one stub's notch is gone" premise that framed this whole section was itself
> a search-window artifact. Kept for the record — the reasoning is a good
> example of how far a plausible attribution argument can run without being
> true.

Label-independent nulls, 3–9GHz:

```
v3     4.270(-49.6)  4.590(-63.3)  5.870(-62.6)  6.810(-65.6)  8.170(-49.4)   5 nulls
v2+S7  4.760(-29.2)  5.350(-66.2)  5.820(-107.6) 5.840(-126.3) 6.900(-64.9)  8.150(-72.9)
```

S4/S5/S6 moved <=1.3% (expected — frozen geometry). But the low end rearranged
completely, and **one stub's notch is gone**. Two readings fit every number:

1. S1 landed at 4.590 (+2.0%, the L correction working), S2 dragged to 4.270,
   S3 lost.
2. 4.590 = S2 nudged -3.6%, 4.270 = **S3 pulled down 20%**, and S1 still has no
   resonance of its own.

These have opposite implications and **the data in hand cannot separate them.**
The built-in escalation test can't either — it perturbed S3 and searched
[4.505, 6.095]GHz, so it never looked at 4.270.

Resolving it needs one perturbation solve on S1 (+2–3% length) over a window
**wider** than the escalation used: if 4.590 tracks down ~1:1 S1 is real; if
4.270 moves instead, S1 is dead and has taken S3 with it.

This campaign has already had two measurement-attribution failures (a sweep
mode-selection bug and the dashboard peak-finder). Do not close this one by
picking the flattering reading.

## 11. S1 <-> S3 coupling, and the Rev 18 refold

v3's L-stub put S1's open end **783.0um** from S3's fan — the tightest pair in
the design, and **both are voltage antinodes**, the most effective possible
capacitive coupling geometry. Loading an open end pulls its resonance *down*,
which is exactly reading 2 above.

Two things support the coupling being real rather than coincidental:

- Rev 16's Track A perturbation of the *old* S1 produced its largest response
  (r = -0.322) at 5.355GHz — **S3's own notch**. That looked anomalous at the
  time. It wasn't.
- The proximity is a **tip-to-fan** approach with only 258um of y-overlap, not
  a long broadside-coupled run. (Checked explicitly — the broadside guess was
  wrong.)

**Rev 18 response:** S1 refolded as a 2-run / 1000um-gap serpentine (the
measured-best real-bore fold from sec 8, k_eff 0.792, drawn 8820.28um),
`d_perp` 1200um, folded **north — away from S3**.

The handoff specified a *southward* fold turning back before S3's latitude.
**That is geometrically impossible here**: sweeping `d_perp` 600–4200um across
both fold handednesses, no southward configuration satisfies the standoff,
separation, transverse and bore constraints simultaneously — the U-turn apex
cannot clear S3 without pushing the return run through the 6950um bore wall.
Folding north satisfies the same intent far more cheaply, because S1's
southernmost metal becomes its own exit segment at the tee.

| constraint | required | achieved |
|---|---|---|
| southernmost metal | >= 26500 | **29965** |
| S1<->S3 separation | >= 2500 | **4915.1** (v3: 783.0 — 6.3x) |
| transverse total | <= 6000 | **5227.1** |
| runs off main line | >= 1500 | **1665.0** |
| all-pairs clearance | >= 800 | **1165.0** |

Bore clearance 660um; fold apex 1345.6um clear of the y=35000 port plane
(checked explicitly — a +y run is what broke port 1 in Rev 17).

**Cost of folding north:** S1's `run1`/`bend1` now pass **1248um from the
pin-pad launch**, a proximity that did not previously exist. Above the 800um
floor and C4 is satisfied against the main line proper, but it is inside the
range where sec 8 measured real coupling. Better trade than 783um
antinode-to-antinode (a driven port structure is not a resonator, and S1's own
antinode is now >2700um clear of everything) — but it is a new thing to watch,
not free.

### 11.1 Rev 18 probe result — CASE 1, the fold works

[`filter_BB_singlefold_probe_HFSS.py`](../filter_BB_singlefold_probe_HFSS.py),
variant `v3f_singlefold`. **Directional only** — single-point adaptive at
4.7GHz, 4 passes, final delta-S 0.0102, one interpolating sweep 3.5–9.0GHz, no
discrete window. v3's mesh was *tighter* (delta-S 0.0037) and adapted at
3.5GHz. These are not scorecard numbers.

```
                              probe        v3        change
S21 @ 4.5GHz              -23.08 dB   -33.56 dB    +10.49 dB  (worse, still passes)
worst S21 4.7-5.3GHz      -22.23 dB    -7.39 dB    -14.85 dB  (BETTER - hole filled)
worst S21 4.2-4.6GHz      -11.98 dB   -21.64 dB     +9.66 dB  (worse)
worst S21 5.5-7.0GHz      -17.87 dB   -21.93 dB     +4.06 dB  (worse)
worst S21 4.2-8.2GHz      -11.98 dB    -7.39 dB     -4.59 dB  (BETTER)
fraction of 4.2-8.2 <-20dB    91.8%      86.3%
```

**Decision case 1** per the handoff's own rule: the hole improved by >=10dB
*and* S21@4.5GHz still passes at -23.08dB. A proper discrete confirmation run
is the indicated next step.

But read the rest before treating this as a win:

- **The hole moved, it did not simply vanish.** The 4.7–5.3GHz hole filled by
  14.85dB while the 4.2–4.6GHz region got 9.66dB *worse*. The global worst
  across 4.2–8.2GHz improved only 4.59dB, from -7.39 to -11.98dB.
- **Still 5 nulls for 6 stubs.** Every v3 null maps onto a probe null:
  `4.270->4.325, 4.590->4.855, 5.870->5.480, 6.810->6.890, 8.170->8.135`.
  Nothing new appeared and nothing was lost — they **moved**, on frozen S2–S6
  geometry, which is itself more evidence for cascade coupling.
- **A null did appear in 5.2–5.5GHz, but it is NOT evidence of S3
  recovering.** The probe script's own auto-check says "YES — S3 recovering";
  that reading does not survive the mapping above, which makes 5.480 far more
  likely to be v3's 5.870 null moved *down* 6.6%. There is now no null
  anywhere in 5.5–6.5GHz, which is exactly what that mapping predicts.
  **Sec 10's ambiguity is NOT resolved by this run.**
- Two bugs in the probe script's own verdict logic, both mine, both fixed:
  the decision rule had the dB sign backwards (it printed "CASE 4 — worse
  across the board" for what is actually case 1), and check 4's wording
  asserts an attribution the data does not support.

## 12. Process lessons (each cost real time)

- **A windowed notch search reports "no notch" for a notch that exists.** Every
  "missing" stub in Rev 12–16 was this. Always enumerate nulls
  label-independently over the full sweep before concluding anything is absent.
- **The HFSS export replay drifts from the layout script silently.**
  [`verify_filter_BB_hfss_export.py`](../verify_filter_BB_hfss_export.py) is
  the *actual* geometry source for HFSS, and it re-implements
  `filter_BB.py`'s build loop. It has now had to be patched twice for this
  (the Rev 17 L-stub dispatch, and Rev 18's per-stub `d_perp`/`run_gap`, where
  it silently used stale globals — `run_length` 3356.44um replayed against
  2549.58um drawn). **Any change to the build loop needs a matching change
  here**, and the cheap detector is comparing the dims JSON against the
  regenerated pieces. A miss here looks like a physics result, not a bug.
- **Check clearances all-pairs, never table-adjacent-only.** A real 75um
  collision hid in a non-adjacent same-side pair in Rev 13; the S1<->S3
  proximity in sec 11 is another non-adjacent pair.
- **Duplicate same-named AEDT projects can eat a real solve's results.** See
  CLAUDE.md's own extended note — the probe script prints the count of
  same-named open handles for exactly this reason.
- **`Analyze()` returns `None` on success** in this COM binding. Do not read
  the return value as a failure signal; pull the data instead.

# Part III — the mode-comb spec, and attribution by deletion (Rev 19–20)

## 13. The acceptance criterion changed, and the old one is retired

Rev 19 replaced continuous band coverage with a **discrete 9-mode comb**.
Scoring is now a table lookup, not a search:

| # | mode | GHz | tolerance |
|---|---|---|---|
| 1 | buffer 1 | 4.500 | worst across ±0.15 |
| 2 | buffer 2 | 5.000 | worst across ±0.15 |
| 3 | storage 1 | 5.792 | at the mode |
| 4 | storage 2 | 6.160 | at the mode |
| 5 | storage 3 | 6.528 | at the mode |
| 6 | storage 4 | 6.897 | at the mode |
| 7 | storage 5 | 7.265 | at the mode |
| 8 | storage 6 | 7.633 | at the mode |
| 9 | storage 7 | 8.001 | at the mode |

PASS = S21 ≤ −20dB. Above that earns no extra credit and must not be
optimized for. Below it FLAGs with the actual value — a flag is pending the
kappa budget, not a failure. Drive band confirmed still 0.5–3.5GHz.

**"Worst S21 in 4.2–8.0GHz" is retired.** Peaks *between* modes now cost
nothing, so that number does not merely add noise, it actively misleads: v3's
4.910GHz hole reads as a failure under the old criterion and is irrelevant
under the new one. `filter_BB_rev19_confirm_HFSS.py` exists as a separate
driver from `filter_BB_firstlight_HFSS.main()` for exactly this reason.

## 14. Attribution by deletion works. Attribution by inference does not.

**Every k_eff-consistency inference this campaign made was wrong. Every
deletion test was right.** That is not a close call, and it is the single most
useful methodological result here.

The method: rebuild the geometry with one stub's pieces filtered out of
`geom['pieces']` by label prefix, at the **same mesh** as the reference run,
and diff the null lists. Deleting by piece-filter rather than by editing the
`STUBS` table means nothing downstream shifts — series sections, tee
positions and every other stub stay byte-identical.

Confirmed by deletion:

| stub | owns | how it was found |
|---|---|---|
| S1 | 4.325 / 4.340 GHz | deletion |
| S4 | 6.890 GHz | deletion |
| S6 | **6.640 AND 7.580 GHz** | deletion |

Refuted by deletion, having been inferred from k_eff consistency:

- S1 owns 4.855 — no, it owns 4.325.
- S5 owns 6.890 — no, S4 does.
- S6 owns 9.970 — no. 9.970 survived both S6's lengthening *and* S6's
  deletion. This one was doubly wrong and cost two solves: Rev 19 B2 moved S6
  on the strength of it, and B3 confirmed the move had not landed.

**Root cause of all three failures: they assumed one null per stub.** The full
0.5–14GHz census found **12 nulls for 6 stubs**. The earlier "5 nulls for 6
stubs" mystery was a search-window artifact — 3.5–9.0GHz simply could not see
the rest. Once a stub can own two nulls, one-null-per-stub bookkeeping is not
a weak argument, it is an invalid one.

Coupling is measurable the same way: deleting S4 moved the 8.125GHz null to
8.375 (+3.1%) at matched mesh — about 10× the effect deleting S1 has — which
is what makes S4/S5 a better hybridization candidate than the S1/S3 pair
Rev 18 chased.

## 15. A folded stub can own a null PAIR

S6's two nulls are split **±6.84% about a geometric mean of 7.094GHz**, ratio
**1.1416**. Both vanish on deletion; every other null survives within 0.3%.

The pair is S6's own, not a neighbour's. Predicting where it sat at S6's
**old** 3860.9µm length, from the new length's measured k_eff and ratio alone
by pure length scaling:

```
predicted  11.070 / 12.637 GHz   centre 11.8279   (k_eff 0.6886, ratio 1.1416)
observed   11.110 / 12.535 GHz   centre 11.8010   (k_eff 0.6902, ratio 1.1283)
           centre agrees to 0.23%, ratio to 1.17%
```

Those observed values are the v3 census's own 11.110(−102dB) and
12.535(−18dB), which had no owner until this calculation. **A hybridization
with a fixed-frequency neighbour would give a detuning-dependent splitting,
not a ratio preserved to ~1% across a 1.67× frequency move.**

### 15.1 …but no *isolated* fold has ever shown one

Re-reading the Rev 17 fold experiment's own saved full-band sweeps
(`HFSS/foldexp_*_S21.csv` — no new solve), each variant has exactly **one**
resonance over 0.5–14GHz: V-fold-current 6.830, V-fold-wide 5.680, V-L 5.045.
Drop the depth threshold entirely and each trace has four local minima — the
real null plus three shallow features near 1.9, 8.1 and 11.6GHz that sit
within a few hundred MHz of each other across all three variants, i.e. harness
artifacts. Where a 1.1416-ratio partner would sit there is no local minimum at
all, only the skirt of the real null.

**These two facts are not in conflict, though it is easy to write them up as
if they were.** The prediction is that a *wider* gap converges the pair toward
a single null — and V-fold-wide is the wide-gap case (1000µm) showing one
null, which confirms that rather than refuting it. V-fold-current is 3 runs, a
three-line coupled system with three eigenmodes whose coupling to the
through-line differs per mode; its single visible null is not the same
measurement as a two-line split.

**The actual gap in the evidence is narrow: S6's exact topology — two runs at
a 400µm gap — has never been run in isolation.** V-fold-current is 3 runs at
400µm; V-fold-wide is 2 runs at 1000µm. Neither is it. That single missing
point is what `filter_BB_splitpair_gap_HFSS.py` gates on.

### 15.2 What this does to sec 8's k_eff table

Sec 8's numbers stand as measurements — they are genuine single nulls over the
full band, not windowed artifacts. But **`k_eff` is now an ambiguous quantity
for a folded stub unless you say which null it refers to.** Sec 8's values
refer to the one observed null; B4's 0.6886 refers to a pair *centre*. If
V-fold-wide's single null is really an unresolved pair, its 0.792 is a centre
too and the two are comparable — in which case 0.792 (1000µm gap) versus
0.6886 (400µm gap) *is* the gap effect. If it is not, they are different
quantities and must not be put in the same column. This is unresolved.

## 16. Off-resonance susceptance is a first-order effect

Deleting S6 changed **eight** of the nine modes, by −4.6 to +14.4dB, most of
them nowhere near either of S6's own nulls:

```
mode        S6 present   S6 absent   delta
buffer 1      -25.44      -21.43     +4.0
buffer 2      -24.54      -20.85     +3.7
storage 1     -15.76 FLAG -20.38 PASS  -4.6
storage 2     -23.60      -20.07     +3.5
storage 3     -37.10      -22.73    +14.4
storage 4     -40.26      -29.19    +11.1
storage 5     -21.09      -21.13     -0.0
storage 6     -23.76      -20.09     +3.7
storage 7     -23.88      -19.76 FLAG +4.1
```

Both configurations score **8/9**, and neither dominates: S6 present has one
bad flag (−4.24dB) with comfortable margins elsewhere; S6 absent has one
marginal flag (−0.24dB, inside mesh noise) but six modes within 1.5dB of the
line.

A stub loads the line at *every* frequency, and an open stub's susceptance is
capacitive below its resonance and inductive above — so the same stub
contributes with **opposite sign** on either side of its own null. That is why
S6 helps seven modes and hurts one, and why **S6 currently harms the very mode
it was moved to fix.**

**Consequence: the ≤1.0GHz null-spacing rule is not sufficient.** Null
placement sets where attenuation is infinite; susceptance summation sets
everything in between, and the numbers above show that "everything in between"
runs to double-digit dB. Placement candidates should be screened in the ABCD
circuit model, which captures susceptance summation natively even without a
mutual-coupling term. Its failure as a *forward predictor* in Rev 16 does not
disqualify it as a *ranking* tool for this question.

## 17. Process lessons from Rev 19–20

- **Do not change geometry and mesh in the same step.** B3 did (census
  6.0GHz/δS 0.02 → confirm 3.5GHz/δS 0.005) and the null rearrangement above
  6GHz became unattributable. Every later run has been mesh-matched to its own
  comparison, and every one of those produced a clean answer.
- **A deletion run must not print the confirmation run's banner.** The
  `--delete` path initially reported "Rev 19 B3 — confirmation" and ran a
  "DID S6 MOVE?" check that is meaningless when S6 is absent. Shared code
  paths are right; shared *narration* is not.
- **Per-stub overrides must be threaded through the HFSS replay too.** Rev 18
  added `d_perp`/`run_gap` overrides to `filter_BB.py` and
  `verify_filter_BB_hfss_export.py` kept using module globals — HFSS would
  have solved d_perp=1000/r=235 while the mask drew 1200/535. Caught only by
  comparing the dims JSON's `run_length` (2549.58µm) against the replay's
  (3356.44µm). Second occurrence of the same class; see sec 12.
- **The report table is not the geometry.** A separate instance of the same
  bug printed `D_PERP_UM` and a recomputed `run_gap` in the stub table while
  the build used per-stub values, so S1 showed d_perp=1000/run_gap=400
  alongside an impossible bend_radius=535. The internal inconsistency was the
  only tell.
- **Check the all-pairs clearance after any length change.** Lengthening S6 to
  6437µm sent its U-turn to within **88.5µm** of S4's, because both fold the
  same way over an identical x span. `fold_dir=-1` fixed it (88.5 → 2756.8µm).
  Same override, same reason, as S3's Rev 13 fix.
- **Write up the refutation before the confirmation.** An earlier draft of
  `filter_BB_splitpair_gap_HFSS.py` claimed the isolated single-null data
  refuted the split-pair premise. It does not — see sec 15.1 — and the error
  was an argument ("3 runs at 400µm is more coupling than S6") that sounded
  mechanical but ignored that a three-line system is not a two-line one.
  Caught by checking the length-scaling prediction *before* committing the
  claim, not after.
