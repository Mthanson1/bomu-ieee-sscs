#!/usr/bin/env python3
# BoMu design-space map: small-signal gain vs power at the 150 MHz BW limit, one
# line per gm/Id, marking the adopted W=80 design. Model and derivation are in the
# write-up (docs/main.tex); this script only renders the figure.
# Run:  ../.venv-plot/bin/python plot_gain_space.py
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "extern", "sky130A-gmid"))
from gmid import GmidGrid

# ---- fixed design context -------------------------------------------------
VDD = 1.20
CL = 5e-12
VS = 0.30                      # tail / source-body bias (Vsb)
BW_T = 150e6                   # hard bandwidth target
AV0_DB = 10.0                  # hard gain target
AV0 = 10 ** (AV0_DB / 20.0)
SE_PEAK = 0.100               # single-ended output swing peak (v_od/4)
R_LBW = 1.0 / (2 * np.pi * CL * BW_T)        # 212 ohm: max load for 150 MHz

# ---- adopted W=80 design point, SPICE-measured at tt (sec:parasitic) ------
# Itail = 2.28 mA -> P = VDD*Itail = 2.74 mW (pair); measured A_v0 = 10.1 dB,
# f_3dB = 168 MHz (real res_high_po loads + mirror, tb_bomu_swing / tb_ac).
ADO_P = VDD * 2.28e-3 * 1e3   # mW
ADO_GAIN_TT = 10.1

GMIDS = [8, 10, 12, 15, 20, 25, 30]
GMID_HI = 15                   # BoMu's inversion-level choice (highlighted)
grid = GmidGrid()


def solve_point(gmid, P, derate=1.0):
    """Max gain at the 150 MHz edge for one (gm/Id, power in mW), with feasibility.
    derate scales gm (1.0 = tt; <1 = worst corner)."""
    Id = (P * 1e-3) / (2 * VDD)
    gm = gmid * Id * derate
    drop = AV0 / gmid                        # seed Id*R_D
    gmro = jd = R_D = float("nan")
    for _ in range(5):
        Vds = max(VDD - drop - VS, 0.05)
        lu = grid.lookup(gmid, VS, Vds)
        gmro, jd = lu["gmro"], lu["jd"]
        ro = gmro / gm
        R_L = min(R_LBW, ro)
        if ro > R_L:
            R_D = R_L * ro / (ro - R_L)
            drop = Id * R_D
        else:
            R_D = float("inf")
            drop = Id * R_L
    R_L = min(R_LBW, gmro / gm)
    Av0 = gm * R_L
    Vov = 2.0 / gmid
    V_D = VDD - drop
    feasible = (drop > SE_PEAK) and ((V_D - SE_PEAK) > (VS + Vov)) and V_D > 0
    return Av0, feasible


def gain_db_curve(gmid, Ps, derate=1.0):
    g = np.array([solve_point(gmid, P, derate)[0] for P in Ps])
    feas = np.array([solve_point(gmid, P, derate)[1] for P in Ps])
    return 20 * np.log10(g), feas


def min_power_for_target(gmid, derate=1.0):
    """Power where this gm/Id ray crosses the 10 dB target (bisection)."""
    lo, hi = 0.2, 12.0                        # mW
    if gain_db_curve_scalar(gmid, hi, derate) < AV0_DB:
        return float("nan")
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if gain_db_curve_scalar(gmid, mid, derate) >= AV0_DB:
            hi = mid
        else:
            lo = mid
    return hi


def gain_db_curve_scalar(gmid, P, derate=1.0):
    return 20 * np.log10(solve_point(gmid, P, derate)[0])


# ---- figure ---------------------------------------------------------------
Ps = np.linspace(0.6, 9.0, 220)              # mW
fig, ax = plt.subplots(figsize=(8.0, 5.2))
cmap = plt.cm.viridis(np.linspace(0.12, 0.9, len(GMIDS)))

for gmid, col in zip(GMIDS, cmap):
    gdb, feas = gain_db_curve(gmid, Ps)
    lw = 2.8 if gmid == GMID_HI else 1.3
    lab = (f"$g_m/I_D$={gmid}" + ("  (BoMu)" if gmid == GMID_HI else ""))
    # solid where feasible (swing+headroom), faint dashed where not
    gf = np.where(feas, gdb, np.nan)
    gx = np.where(~feas, gdb, np.nan)
    ax.plot(Ps, gf, "-", color=col, lw=lw, label=lab, zorder=3)
    ax.plot(Ps, gx, "--", color=col, lw=max(lw - 1.2, 0.8), alpha=0.35, zorder=2)

# 10 dB hard target
ax.axhline(AV0_DB, color="k", lw=1.4, ls=":")
ax.text(Ps[-1], AV0_DB + 0.15, " 10 dB gain target", ha="right", va="bottom",
        fontsize=9)

# minimum-power crossing on BoMu's gm/Id=15 ray
p_tt = min_power_for_target(GMID_HI)              # tt minimum (gm/Id=15)
ax.plot(p_tt, AV0_DB, "o", color="green", ms=11, mec="k", mew=0.6, zorder=6,
        label=f"$g_m/I_D$=15 tt minimum ({p_tt:.1f} mW)")

# adopted W=80 design, SPICE-measured at tt -- sits just above the gm/Id=15 min
ax.plot(ADO_P, ADO_GAIN_TT, "*", color="goldenrod", ms=20, mec="k", mew=0.7,
        zorder=7,
        label=f"BoMu $W$=80 adopted ({ADO_P:.2f} mW, {ADO_GAIN_TT:.1f} dB)")

ax.set_xlabel("Power  $P = V_{DD}\\,I_{tail} = 2 V_{DD} I_D$   [mW]")
ax.set_ylabel("Small-signal gain  $A_{v0}$   [dB]  (at the 150 MHz BW edge)")
ax.set_title("BoMu design space: gain vs power at fixed 150 MHz, one line per "
             "$g_m/I_D$", fontsize=10.5, pad=8)
ax.set_xlim(Ps[0], Ps[-1])
ax.set_ylim(6, 16)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=7.4, ncol=2, loc="lower right", framealpha=0.92)

fig_dir = os.path.join(HERE, "..", "docs", "Figures")
os.makedirs(fig_dir, exist_ok=True)
path = os.path.join(fig_dir, "bomu_gain_vs_power.png")
fig.tight_layout()
fig.savefig(path, dpi=150)
plt.close(fig)

print(f"R_Lbw (150 MHz load ceiling)      = {R_LBW:.1f} ohm")
print(f"gm/Id=15 tt minimum power         = {p_tt:.2f} mW")
print(f"BoMu W=80 adopted                 = {ADO_P:.2f} mW  (tt {ADO_GAIN_TT} dB)")
print("wrote", os.path.relpath(path, HERE))
