# L45 radial-stub lowpass filter — design notes

Companion to [`filter_L45.py`](../filter_L45.py). This records *why* the
mask geometry looks the way it does, not just what it looks like — see
[`L30_design_notes.md`](L30_design_notes.md) for the 8th-order sibling
(same methodology, different synthesized numbers; the two files are kept
separate rather than sharing a "methodology" doc, to match the `.py` files'
own "two self-contained files, no shared module yet" convention this
session). Sections 1-7 below mirror L30's reasoning exactly (same
derivations, same repo conventions) — only the numeric results in §8 differ
in any meaningful way; read `L30_design_notes.md` first if this is your
first pass through either file.

## 1. Provenance

All dimensions below are transcribed **verbatim** from a Nuhertz Filter
Solutions synthesis: 12th order Chebyshev-II distributed lowpass, fc=3.500
GHz, stopband from 3.935 GHz (ratio 1.124), 45 dB equiripple floor, same
microstrip/alumina model as L30 (εr=9.80, h=500um, t=300nm, main line
Zo=84.29Ω / 125um). Zero-crossing frequencies are carried through the code
as comments only — they document *why* each branch exists, they are not
used in the geometry. Nuhertz source/netlist files have not been provided
directly; transcribed from screenshots (item V1/V2, §9).

L45's zero set (4.411, 5.086, 6.909, 11.6, 19.6 GHz) covers the high side
(storage 5.5-7GHz, transmon ~7GHz, plus 2nd-harmonic-adjacent cleanup at
11.6/19.6GHz) considerably better than L30's — this was the deciding factor
in Rev 4 of the handoff doc resolving the old "does L45 need an extra
high-side stub" question in L45's favor (it doesn't).

## 2. Topology

Same as L30: a constant-125um/84.29Ω main line with shunt butterfly branch
pairs at each section boundary, six pairs here instead of four (12th order
vs 8th). P1 before S1, P2 between S1/S2, ..., P6 between S5/S6.

## 3. Positive-metal-draw convention

Identical to L30 — see [`L30_design_notes.md` §3](L30_design_notes.md#3-positive-metal-draw-convention-why-this-differs-from-the-rest-of-the-repo).
No ground plane, no XOR, `Strip_straight`/`Strip_taper`/`CurveRect` as the
drawing primitives, same `SNAIL/SNAIL.py`/`FlagPads` precedent.

## 4. Radial fan geometry derivation

Identical derivation and formulas as L30 — see
[`L30_design_notes.md` §4](L30_design_notes.md#4-radial-fan-geometry-derivation):

```
rotation = S + fan_angle/2 - 90
insert   = tip + (attach_width/2) * (cos(S+90), sin(S+90))
```

valid when `attach_width == 2 * r_in * sin(fan_angle/2)`, which holds for
every row of L45's table too (same `r_in` values, 88.39/176.8um, as L30 —
only the fan `r_out` and stalk lengths differ between the two filters).
Independently confirmed in this filter's own rendered DXF: all 428
BASEMETAL shapes in `filter_L45.dxf` merge into a **single connected
polygon**.

### `attach_width` vs `stalk_width`

Same resolution as L30: numerically identical per row here, geometrically
distinct concepts (stalk cross-section vs. fan inner-arc chord); both kept
in the table with a runtime consistency assert.

## 5. Tilt / butterfly geometry

Identical mechanism to L30 (`cloneAlong(vector=(0,0),
newDirection=sign*(90+TILT_DEG))` off the main line's current `Structure`,
main line at `direction=-90`, both branch directions lean toward +y / the
input). `TILT_DEG = 55`, same top-of-file constant convention as L30 — kept
separately in each file (not shared) so an HFSS-driven change to one filter
doesn't silently affect the other.

## 6. T-junction strategy

Identical to L30 — main line drawn unbroken, stalks start at the junction
point and overlap the main line polygon, fuse with no boolean op. Confirmed
via the same `klayout.db.Region.merge()` connectivity check on this
filter's own DXF.

## 7. Bounding-box / clearance methodology

Identical to L30 — see
[`L30_design_notes.md` §7](L30_design_notes.md#7-bounding-boxclearance-methodology).
Same vertex-to-vertex nearest-distance approximation for clearance, same
"actual rendered `CurveRect` polygon, not hand-approximated" approach for
the fan's contribution to the bounding box.

## 8. Results (as-built, from the actual rendered `filter_L45.dxf`)

Usable chip: 6800 x 39800um, main line centered at x=3400.

| Pair | Realized transverse width | Notes |
|---|---|---|
| P1 | 884.5 um | |
| P2 | 2613.0 um | |
| P3 | 5588.5 um | |
| P4 | **6440.4 um** | tightest pair in either filter — only 59.6um under budget |
| P5 | 4152.5 um | |
| P6 | 1710.8 um | |

**Overall realized transverse bounding box: 6440.4 um** (budget 6500um,
**only 59.6um margin**) — confirmed both by the script's own printed report
and by directly measuring the rendered DXF's BASEMETAL layer bbox in
KLayout (6440.377um, matching to floating-point noise). **This is the
single tightest number across both filters** — any future dimension
change, rounding difference, or centering shift should re-check this first.

Per-pair nearest-neighbor clearance: P1↔P2 **221.1um** (flagged), **P2↔P3
127.6um (flagged — tightest clearance in either filter)**, P3↔P4 1794.6um,
P4↔P5 1031.7um, P5↔P6 983.2um.

DXF validation performed this session (via `klayout.db`):
- 428 BASEMETAL shapes, **0 degenerate (<3-vertex) polygons**.
- All 428 shapes merge into **exactly 1 connected polygon**.

## 9. Open verification items (carried from the handoff doc)

Same three items as L30 (§9 there) apply here identically:
- **V1**: butterfly-at-one-junction interpretation, unverified against the
  original Nuhertz 3D layout.
- **V2**: P1's stalk Zo (66.55Ω/250um) taken as given, not re-derived.
- **V3**: programmatic DXF checks (connectivity, degenerate-geometry) done
  this session; human KLayout visual pass and converter acceptance on real
  hardware still open — **especially important here given how tight P4's
  width margin and P2↔P3's clearance are** (§8).

## 10. HFSS-pending caveats

Every electrical dimension in `filter_L45.py` is a **PLACEHOLDER** pending
HFSS re-extraction in the real (bare-sapphire, tunnel-grounded) environment
— same caveat as L30 and as `Hairpin_Filter.py`/`SNAIL_Pump_Filter.py`.
Given how little margin P4 and P2↔P3 already have at the as-synthesized
dimensions (§8), **this filter is the more exposed of the two to HFSS-driven
growth**: the handoff doc's own worked example says +30% growth would push
a 55°-tilt L45 over budget, requiring escalation to 60° tilt (recovers to
~6.2mm per the handoff doc's estimate) or the reserve stalk-L-bend option.
Neither escalation is implemented in `filter_L45.py` yet — `TILT_DEG` is a
single top-of-file constant specifically so this is a one-line change when
HFSS numbers land.

## 11. Known risks carried into implementation

1. **P4 realized transverse width (6440.4um) is only 59.6um under the
   6500um budget** — the tightest number in either filter. Treat any
   further dimension change as needing an immediate re-check here, not an
   optional one.
2. **P2↔P3 nearest-vertex clearance (127.6um) is the tightest clearance in
   either filter** — a specific, high-priority visual check in KLayout
   before this filter goes anywhere near fab.
3. Same pin-pad-placement and SNAIL-keep-out-orientation provisional
   assumptions as L30 (§11 there) apply here identically — both are
   placeholder/marker geometry, not exposed to real risk, but should be
   confirmed against the eventual package drawing.
4. S6 (33.83um) is the shortest main-line segment across both filters —
   still well above the DWL degenerate-length threshold, and branch tilt
   always leans backward (toward input) so P6's own branch can't reach
   forward into it; confirmed fine on first render this session.
5. Given how tight this filter already is at as-synthesized dimensions,
   **L45 is the more likely of the two to need the 60° tilt escalation (or
   the reserve L-bend stalk option) once real HFSS-driven dimensions
   arrive** — worth deciding this question before L30, if only one gets
   HFSS time first.
