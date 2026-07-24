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

## 4. Build session results

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

- **EPS_EFF=5.5 is a PLACEHOLDER** - the handoff's own "GATING ITEM": a
  bare-70um-strip-in-bore HFSS extraction (Eddie-side) is needed before
  any stub length here is trustworthy. Every length in this file is a pure
  function of `EPS_EFF` (`stub_quarter_wave_length_um()`), so updating the
  constant recomputes everything automatically.
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
