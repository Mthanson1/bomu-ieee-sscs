# BoMu -- Resistively-Loaded NMOS Differential Pair (SKY130A / TinyTapeout)

A single-stage differential amplifier built from a resistively-loaded NMOS
source-coupled pair, designed for the [SKY130A](https://github.com/google/skywater-pdk)
PDK and the open-source [TinyTapeout](https://tinytapeout.com) flow. Devices are
sized by a $g_m/I_D$ methodology and the design is carried all the way through
layout, LVS/DRC sign-off, and parasitic-extracted re-simulation to a signed-off GDS.

The full design writeup is in [`docs/main.pdf`](docs/main.pdf).

## Targets

| Parameter | Target |
|-----------|--------|
| Differential DC gain $A_{v0}$ | 10 dB |
| Small-signal bandwidth $f_{-3\mathrm{dB}}$ | 150 MHz |
| Differential output swing | 400 mV$_{pp}$ |
| Supply $V_{DD}$ / pad load $C_L$ | 1.2 V / 5 pF (fixed) |
| Channel length $L$ | 0.15 µm |

## Key result

The 10 dB / 150 MHz spec sits right on the single-stage gain–bandwidth wall
$g_m/(2\pi C_L)$, so meeting it is a power (transconductance) problem. The signed-off point ($W=320\mu m$, $R_D=193\Omega$) passes **61/63**
PVT corners open-loop and **21/21** under a regulated 1.20 V rail. The block is
laid out **LVS/DRC-clean**, and the parasitic-extracted (RCX) netlist reproduces
the verdict at a uniform ~3.7 % bandwidth / ~0 dB gain penalty. Large-signal THD
is 0.53 % (H3-dominant), offset $\sigma\approx0.88mV$, CMRR $\approx$ 86 dB,
PSRR $\approx$ 70 dB, input-referred noise $\approx$ 47.9 µV$_{rms}$.

## Repository layout

| Path | Contents |
|------|----------|
| `ip/` | xschem schematic (`bomu.sch`), symbol, and swing testbench |
| `sim/` | $g_m/I_D$ sizing, PVT/bias/plot scripts (`sizing.py`, `corners.py`, `bias.py`, `plot_figures.py`) and ngspice decks |
| `layout/` | Magic layout (`bomu.mag`) with edge dummies and guard rings |
| `verify/` | LVS/DRC/PEX/RCX decks, run scripts, and reports |
| `tapeout/` | Signed-off GDS, DRC/LVS reports, and `SIGNOFF.md` |
| `docs/` | LaTeX design writeup, figures, and bibliography |
| `env/` | Tool rc files (`.magicrc`, `.spiceinit`, `.xschemrc`) |
| `extern/sky130A-gmid` | $g_m/I_D$ lookup grid (git submodule) |

## Toolchain

Fully open-source: [xschem](https://xschem.sourceforge.io/),
[ngspice](https://ngspice.sourceforge.io/),
[magic](http://opencircuitdesign.com/magic/), and
[KLayout](https://www.klayout.de/). As bundled in
[IIC-OSIC-TOOLS](https://github.com/iic-jku/IIC-OSIC-TOOLS).

## Getting started

```bash
# Clone with the gm/ID lookup submodule
git clone --recurse-submodules https://github.com/Mthanson1/bomu-ieee-sscs.git

# If you already cloned without --recursive-submodules:
git submodule update --init

# Reproduce the sign-off (inside IIC-OSIC-TOOLS, PDK=sky130A)
verify/write_gds.sh   # layout/bomu.mag -> tapeout/bomu.gds
verify/drc.sh         # Magic + KLayout DRC
verify/run_lvs.sh     # extract layout, netgen compare vs ip/bomu.sch
```

Sizing and PVT scripts run standalone with ngspice, e.g. `python sim/corners.py pex`.

## Status

Signed off on 2026-08-25 (see [`tapeout/SIGNOFF.md`](tapeout/SIGNOFF.md)):
LVS *circuits match uniquely*, DRC clean (Magic + KLayout `sky130A_mr`).
