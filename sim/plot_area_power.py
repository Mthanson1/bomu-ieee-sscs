#!/usr/bin/env python3
# BoMu design-space map: pair gate AREA vs POWER at the tt corner, for the fixed
# 10 dB / 150 MHz / 400 mVpp criteria, marking the adopted W=80 design on the
# gm/Id=15 ray. Model and derivation are in docs/main.tex; this renders the figure.
# Run:  ../.venv-plot/bin/python plot_area_power.py
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "extern", "sky130A-gmid"))
from gmid import GmidGrid

# ---- fixed design context (identical to plot_gain_space.py) --------------
VDD = 1.20
CL = 5e-12
VS = 0.30                      # tail / source-body bias (Vsb)
L = 0.15                       # channel length [um]
BW_T = 150e6
AV0_DB = 10.0
AV0 = 10 ** (AV0_DB / 20.0)
SE_PEAK = 0.100
R_LBW = 1.0 / (2 * np.pi * CL * BW_T)        # 212 ohm

# ---- the adopted, SPICE-verified operating point -------------------------
# tt design point (sec:parasitic): W=80 um, R_D~=243, Itail=2.28 mA,
# 10.1 dB / 168 MHz at tt (real res_high_po loads + mirror, tb_bomu_swing).
TT_W = 80.0
TT_ITAIL = 2.28e-3
TT_P = VDD * TT_ITAIL * 1e3                   # mW
TT_AREA = 2 * TT_W * L                        # pair gate area [um^2]

GMID_HI = 15                   # BoMu's inversion-level choice
grid = GmidGrid()


def solve_point(gmid, P):
    """Max gain at the 150 MHz edge for one (gm/Id, power in mW), with feasibility
    and the matching width/area. Mirrors plot_gain_space.solve_point()."""
    Id = (P * 1e-3) / (2 * VDD)                  # A
    gm = gmid * Id
    drop = AV0 / gmid
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
    W = (Id * 1e6) / jd                          # um  (Id in uA / (uA/um))
    return dict(Av0=Av0, feasible=feasible, W=W, area=2 * W * L)


def min_power_for_target(gmid):
    """Power (mW) where this gm/Id ray crosses the 10 dB target (bisection)."""
    lo, hi = 0.2, 14.0
    if 20 * np.log10(solve_point(gmid, hi)["Av0"]) < AV0_DB:
        return float("nan")
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if 20 * np.log10(solve_point(gmid, mid)["Av0"]) >= AV0_DB:
            hi = mid
        else:
            lo = mid
    return hi


# ---- one ray per gm/Id: area(P), solid where the 10 dB/150 MHz spec is met -----
GMIDS = [10, 12, 15, 18, 20]
Ps_line = np.linspace(0.8, 4.0, 160)              # mW
cmap = plt.cm.viridis(np.linspace(0.12, 0.9, len(GMIDS)))

# the gm/Id=15 minimum point (what BoMu's tt choice sits just above)
p15 = min_power_for_target(GMID_HI)
sp15 = solve_point(GMID_HI, p15)

# ---- figure --------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8.2, 5.3))
front_P, front_A = [], []

for gmid, col in zip(GMIDS, cmap):
    area = np.array([solve_point(gmid, P)["area"] for P in Ps_line])
    ok = np.array([(solve_point(gmid, P)["feasible"] and
                    20 * np.log10(solve_point(gmid, P)["Av0"]) >= AV0_DB)
                   for P in Ps_line])
    lw = 2.8 if gmid == GMID_HI else 1.4
    lab = f"$g_m/I_D$={gmid}" + ("  (BoMu)" if gmid == GMID_HI else "")
    ax.plot(Ps_line, np.where(ok, area, np.nan), "-", color=col, lw=lw,
            label=lab, zorder=3)
    ax.plot(Ps_line, np.where(~ok, area, np.nan), "--", color=col,
            lw=max(lw - 0.8, 0.9), alpha=0.4, zorder=2)
    pmin = min_power_for_target(gmid)
    if np.isfinite(pmin):
        sp = solve_point(gmid, pmin)
        ax.plot(pmin, sp["area"], "o", color=col, ms=6, mec="k", mew=0.5, zorder=4)
        front_P.append(pmin); front_A.append(sp["area"])

# the tt frontier (locus of per-gm/Id minima)
order = np.argsort(front_P)
ax.plot(np.array(front_P)[order], np.array(front_A)[order], ":", color="0.35",
        lw=1.6, zorder=3, label="tt frontier (per-$g_m/I_D$ minima)")

# gm/Id=15 theoretical minimum
ax.plot(p15, sp15["area"], "o", color="green", ms=12, mec="k", mew=0.6, zorder=6,
        label=f"$g_m/I_D$=15 tt min ({p15:.2f} mW, {sp15['area']:.0f} $\\mu$m$^2$)")

# the adopted tt design point (W=80) -- sits just above its gm/Id=15 minimum
ax.plot(TT_P, TT_AREA, "*", color="goldenrod", ms=22, mec="k", mew=0.7, zorder=7,
        label=f"BoMu $W$=80 adopted ({TT_P:.2f} mW, {TT_AREA:.0f} $\\mu$m$^2$)")
ax.annotate("on the $g_m/I_D$=15 ray,\njust above the tt minimum",
            xy=(TT_P, TT_AREA), xytext=(TT_P + 0.08, TT_AREA + 14),
            fontsize=8.2, color="0.25", ha="left", va="bottom",
            arrowprops=dict(arrowstyle="->", color="0.5", lw=0.9))

ax.set_xlabel("Power  $P = V_{DD}\\,I_{tail}$   [mW]")
ax.set_ylabel("Input-pair gate area  $2\\,W L$   [$\\mu$m$^2$]")
ax.set_title("BoMu design space: area vs power, one ray per $g_m/I_D$ "
             "(10 dB / 150 MHz at tt)", fontsize=10.5, pad=8)
ax.set_xlim(1.6, 4.0)
ax.set_ylim(0, 80)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=7.4, ncol=2, loc="upper left", framealpha=0.93)

fig_dir = os.path.join(HERE, "..", "docs", "Figures")
os.makedirs(fig_dir, exist_ok=True)
path = os.path.join(fig_dir, "bomu_area_vs_power.png")
fig.tight_layout()
fig.savefig(path, dpi=150)
plt.close(fig)

# ---- companion: scalar area*power cost vs gm/Id, equal- vs power-weighted ------
# Gotcha: the gm/Id grid is only trustworthy to ~20; beyond that J_D collapses and
# area diverges, so the sweep stays bounded at 20.
W_P, W_A = 0.66, 0.33                      # power : area value ratio (2:1)
gc = np.arange(9.0, 20.01, 0.25)
Pc = np.array([min_power_for_target(g) for g in gc])
Ac = np.array([solve_point(g, p)["area"] if np.isfinite(p) else np.nan
               for g, p in zip(gc, Pc)])
C0 = Pc * Ac                                # equal-weight product
Cw = Pc ** W_P * Ac ** W_A                  # power-weighted product
g0 = gc[int(np.nanargmin(C0))]
gw = gc[int(np.nanargmin(Cw))]
i15 = int(np.argmin(np.abs(gc - GMID_HI)))

fig2, ax2 = plt.subplots(figsize=(7.4, 4.4))
ax2.plot(gc, C0 / np.nanmin(C0), "--", color="0.55", lw=1.8, zorder=2,
         label=f"equal weight $P\\!\\cdot\\!A$  (min at $g_m/I_D$={g0:.0f})")
ax2.plot(gc, Cw / np.nanmin(Cw), "-", color="0.15", lw=2.4, zorder=3,
         label=f"power-weighted $P^{{0.66}}A^{{0.33}}$  (min at $g_m/I_D$={gw:.0f})")
ax2.plot(g0, 1.0, "o", color="0.55", ms=9, mec="k", mew=0.5, zorder=4)
ax2.plot(gw, 1.0, "o", color="green", ms=11, mec="k", mew=0.6, zorder=5)
ax2.plot(GMID_HI, Cw[i15] / np.nanmin(Cw), "*", color="goldenrod", ms=21,
         mec="k", mew=0.7, zorder=6,
         label=f"BoMu $g_m/I_D$=15 ($+{100*(Cw[i15]/np.nanmin(Cw)-1):.0f}\\%$ "
               f"on weighted)")
ax2.annotate("weighting power $2\\times$ area\nshifts optimum $12\\!\\to\\!15$",
             xy=(gw, 1.0), xytext=(16.1, 1.18), fontsize=8.2, color="green",
             ha="left", va="center",
             arrowprops=dict(arrowstyle="->", color="green", lw=1.0, alpha=0.7))
ax2.axhline(1.0, color="0.6", lw=0.8, ls=":")
ax2.set_xlabel("$g_m/I_D$   [1/V]  (inversion level)")
ax2.set_ylabel("normalised cost  $C/C_{\\min}$")
ax2.set_title("Scalar area$\\times$power cost: weighting power $2\\times$ area "
              "lands the optimum at $g_m/I_D$=15", fontsize=10.3, pad=8)
ax2.set_xlim(gc[0], gc[-1])
ax2.set_ylim(0.97, 1.45)
ax2.grid(True, alpha=0.3)
ax2.legend(fontsize=8.2, loc="upper center", framealpha=0.93)
path2 = os.path.join(fig_dir, "bomu_cost_gmid.png")
fig2.tight_layout()
fig2.savefig(path2, dpi=150)
plt.close(fig2)
g_opt, C_opt, C15 = g0, np.nanmin(C0), C0[i15]   # (back-compat for prints)

print(f"R_Lbw (150 MHz load ceiling)   = {R_LBW:.1f} ohm")
print(f"gm/Id=15 tt minimum            = {p15:.2f} mW, {sp15['area']:.1f} um^2 "
      f"(W={sp15['W']:.1f} um)")
print(f"BoMu tt design  (W=80)         = {TT_P:.2f} mW, {TT_AREA:.1f} um^2")
print(f"equal-weight P*A       min at gm/Id={g0:.0f} "
      f"(BoMu 15 is +{100*(C0[i15]/np.nanmin(C0)-1):.0f}%)")
print(f"power-weighted P^.66A^.33 min at gm/Id={gw:.2f} "
      f"(BoMu 15 is +{100*(Cw[i15]/np.nanmin(Cw)-1):.0f}%)")
print("wrote", os.path.relpath(path, HERE))
print("wrote", os.path.relpath(path2, HERE))
