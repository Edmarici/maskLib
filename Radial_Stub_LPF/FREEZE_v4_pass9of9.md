# `filter_BB_v4_pass9of9` — frozen passing configuration

The first configuration in this campaign to pass all nine mode-comb rows.
Tagged so it is recoverable without reconstruction; the campaign has more than
once produced a configuration better than the ones that followed.

## What passes

Confirm mesh, δS 0.005, 5 adaptive passes, final δ-S **0.0018621**.
PASS = S21 ≤ −20 dB. Buffer rows scored as the worst value across ±0.15 GHz.

| # | mode | GHz | S21 dB | margin dB |
|---|---|---|---|---|
| 1 | buffer 1 | 4.500 | −27.49 | +7.5 |
| 2 | buffer 2 | 5.000 | −28.82 | +8.8 |
| 3 | storage 1 | 5.792 | −28.23 | +8.2 |
| 4 | storage 2 | 6.160 | −28.79 | +8.8 |
| 5 | storage 3 | 6.528 | −27.06 | +7.1 |
| 6 | storage 4 | 6.897 | −33.36 | +13.4 |
| 7 | storage 5 | 7.265 | −21.38 | **+1.4** |
| 8 | storage 6 | 7.633 | −22.38 | +2.4 |
| 9 | storage 7 | 8.001 | −22.56 | +2.6 |

Drive band 0.5–3.5 GHz: S21 @3.5 GHz = −0.58 dB, ripple 3.39 dB p-p.

## Geometry (the only thing that defines the tag)

`filter_BB.py`'s `STUBS` table. Realized centreline lengths, µm:

| stub | label | f field | realized µm | runs | gap µm | d_perp µm | fold_dir | side |
|---|---|---|---|---|---|---|---|---|
| S1 | 4.5GHz | 4.50 | 8749.7213596 | 2 | 1000 | 1200 | −1 | +1 |
| S2 | 4.7GHz | 4.70 | 9776.0927822 | 3 | 400 | 1000 | +1 | −1 |
| S3 | 5.3GHz | 5.30 | 7395.2928339 | 2 | 400 | 1000 | +1 | +1 |
| S4 | 6.1GHz | 6.10 | 5581.3136360 | 2 | 400 | 1000 | −1 | −1 |
| S5 | 7.0GHz | 7.00 | 4307.8078628 | 2 | 400 | 1000 | +1 | +1 |
| S6 | 6.0GHz | 5.98 | 7379.3226508 | 2 | 400 | 1000 | −1 | −1 |

The `f` field is a **label only** for S6 — it has not resonated at its nominal
target since Rev 19 B2. `realized_length_um` is the number that means
anything. Tees are on a uniform 2500 µm pitch from y=30000 (S1) down to
y=17500 (S6); main line x=3450, width 70 µm.

## Reproducibility — verified, not assumed

`python filter_BB.py` from the tag regenerates:

- `HFSS/filter_BB_dims.json` — **bit-identical** (sha256 e39c567a…)
- `DXF/filter_BB.dxf`, `DXF/filter_BB_CHIP_BB.dxf` — identical except two
  values each, the `$TDCREATE`/`$TDUPDATE` Julian timestamps (8 diff lines
  total per file, all timestamp)
- `DXF/filter_BB_CHIP_BB.gds` — **XOR area 0.000000 µm²** against the frozen
  copy, checked per-layer with klayout (2/0 metal 7786609.467 µm² both sides;
  3/0 and 4/0 empty both sides)

So the byte-level DXF/GDS hashes are *expected* to churn; the geometry is not.
Compare with the XOR, never the hash.

## How to re-solve it

```
cd Radial_Stub_LPF
C:\Users\epm114\.AnE\Scripts\python.exe filter_BB_rev19_confirm_HFSS.py \
    --design <name> --prefix <prefix>
```

Tight mesh is the default (no `--mesh` flag). Settings live in
`filter_BB_rev19_confirm_HFSS.py`: `CONFIRM_MAX_DELTA_S = 0.005`, coarse
interpolating 0.5–14 GHz at 2701 points (5 MHz), discrete window 4.2–8.2 GHz
at 10 MHz, multi-frequency adaptive [3.5, 5.5, 8.0] GHz **attempted** and
expected to fall back to a single point at 3.5 GHz (it has fallen back on
every attempt in this project — the log says which happened, and the fallback
is v3's own adaptive frequency, so the comparison survives either way).

`EXPECT_S6_LEN_UM = 7379.3227` in that driver asserts the dims JSON matches
this tag. If it trips, the geometry is not this configuration.

Probe mesh (`--mesh probe`, ~1 h vs ~7 h) reproduces the scorecard to 0.45–0.61
dB mean. It is **not** adequate for null positions — interpolating sweeps read
them a mean 14 MHz low.

## Frozen artifacts

`HFSS/filter_BB_dims.json`, `DXF/filter_BB.dxf`,
`DXF/filter_BB_CHIP_BB.dxf`, `DXF/filter_BB_CHIP_BB.gds`,
`HFSS/v6_confirm_S21.csv` (tight mesh, 0.5–14 GHz merged),
`HFSS/v6_confirm_comb_scorecard.csv`, `HFSS/v6_s6move_S21.csv` (same geometry
at probe mesh, kept for the mesh-calibration record).

DXF and GDS are normally gitignored in this repo and are force-added at this
tag on explicit instruction, because a frozen fabrication artifact is the
point of the tag.

## Known open items at freeze time

- **storage 5's +1.4 dB is the thinnest margin**, against ~0.6 dB measured
  mesh error. Fabrication/material tolerance not yet folded in.
- **The mechanism setting the ~7.55 GHz null is unidentified.** It requires
  S6's presence (vanishes on deletion) but ignores S6's length (a 14.64%
  change moved it 0.40%). It is currently worth ~1.3 dB each to storage 6 and
  storage 7 — two of the three thinnest margins.
- **8–14 GHz has open transmission windows** near 10.28 and 10.62 GHz at about
  −1 dB. Pre-existing; matters only if pump harmonics up there are a concern.
