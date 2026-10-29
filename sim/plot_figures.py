#!/usr/bin/env python3
"""Generate the BoMu diff-pair result figures for docs/ from the ngspice
artifacts (and the gm/Id grid).  Writes PNGs into ../docs/Figures.  Run inside
the IIC-OSIC-TOOLS container (numpy + matplotlib):

    export DESIGNS=$HOME/ASIC/projects
    docker run --rm -v "$DESIGNS":/foss/designs hpretl/iic-osic-tools:latest \
        -s bash -lc 'cd /foss/designs/BoMu-tt-sky130a/sim && python3 plot_figures.py'

Regenerate the AC data first with `ngspice -b tb_ac.spice` if the design changed.
Mirrors mvm-tia-comp/sim/plot_figures.py.
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "..", "artifacts")
FIG = os.path.join(HERE, "..", "docs", "Figures")
os.makedirs(FIG, exist_ok=True)

# design constants (kept in sync with sizing.py DESIGN)
VDD = 1.2
C_L = 5e-12
R_D = 1.0 / (2 * np.pi * 150e6 * C_L)   # 212 ohm, pinned by BW + fixed pad cap
GM_REQ = 3.16227766 / R_D               # 14.9 mS, from the 10 dB gain target
V_S = 0.30                              # tail-node DC (>= 0.2 V compliance)
TARGET_AV0_DB = 10.0
TARGET_BW = 150e6

plt.rcParams.update({
    "figure.dpi": 150,
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
})


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    print("wrote", os.path.relpath(path, HERE))


def f3db(f, mag):
    """Last frequency still within 3 dB of the DC value (matches ngspice
    `meas ... fall=1` and the sizing.py convention)."""
    b = np.where(mag >= mag[0] - 3.0)[0]
    return f[b[-1]] if b.size else None


# differential AC frequency response
# artifacts/bomu_ac.dat: (freq, vod_db)  from tb_ac.spice `wrdata ... vod_db`
ac_path = os.path.join(ART, "bomu_ac.dat")
if os.path.exists(ac_path):
    d = np.loadtxt(ac_path)
    f, mag = d[:, 0], d[:, 1]
    a0, fbw = mag[0], f3db(f, mag)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.semilogx(f, mag, color="C0", lw=2.0, label="SPICE (tt, sized $W$)")
    # DC gain and -3 dB corner
    ax.axhline(a0, color="0.6", lw=0.8, ls=":")
    ax.axhline(a0 - 3, color="0.6", lw=0.8, ls=":")
    if fbw is not None:
        ax.axvline(fbw, color="C0", lw=0.9, ls="--")
        ax.annotate(f"$f_{{-3\\mathrm{{dB}}}}$ = {fbw/1e6:.0f} MHz",
                    xy=(fbw, a0 - 3), xytext=(fbw / 20, a0 - 9), fontsize=9,
                    color="C0", arrowprops=dict(arrowstyle="->", color="C0"))
    ax.text(f[0] * 1.5, a0 + 0.3, f"$A_{{v0}}$ = {a0:.2f} dB", fontsize=9,
            color="0.2", va="bottom")
    # targets for contrast (unmet single-stage; see the trade-off figure)
    ax.axhline(TARGET_AV0_DB, color="C3", lw=1.2, ls="--",
               label=f"target $A_{{v0}}$ = {TARGET_AV0_DB:.0f} dB")
    ax.axvline(TARGET_BW, color="C2", lw=1.2, ls="--",
               label=f"target $f_{{-3\\mathrm{{dB}}}}$ = {TARGET_BW/1e6:.0f} MHz")

    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel(r"Differential gain $|v_{od}/v_{id}|$  [dB]")
    ax.set_ylim(a0 - 25, TARGET_AV0_DB + 4)
    ax.set_title("BoMu differential AC response (SKY130A, tt corner)")
    ax.legend(loc="lower left", fontsize=9)
    save(fig, "bomu_ac_response.png")
else:
    print(f"[skip] {os.path.relpath(ac_path, HERE)} not found "
          "(run `ngspice -b tb_ac.spice` first)")


# gain / bandwidth vs gm/Id: the r_o-limited trade-off.
# Hold gm at the 10 dB value (gm = A_v0/R_D) and sweep gm/Id: weaker inversion
# raises r_o so R_D||r_o approaches R_D, and gain climbs toward 10 dB while BW
# settles toward 150 MHz, at the cost of a much wider, slower device. This plots
# that trade.
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "extern", "sky130A-gmid")))
try:
    from gmid import GmidGrid
    grid = GmidGrid()
except Exception as e:                                   # grid submodule absent
    print(f"[skip] gm/Id trade-off figure: {e}")
    grid = None

if grid is not None:
    gmid = np.linspace(8.0, 26.0, 60)
    av0_db, bw_mhz, w_um = [], [], []
    for g in gmid:
        Id = GM_REQ / g
        V_D = VDD - Id * R_D
        lu = grid.lookup(g, V_S, V_D - V_S)          # (gm/Id, Vsb, Vds)
        ro = lu["gmro"] / GM_REQ
        R_L = R_D * ro / (R_D + ro)
        av0_db.append(20 * np.log10(GM_REQ * R_L))
        bw_mhz.append(1.0 / (2 * np.pi * R_L * C_L) / 1e6)
        w_um.append(Id / (lu["jd"] * 1e-6))
    av0_db, bw_mhz, w_um = map(np.array, (av0_db, bw_mhz, w_um))

    fig, ax1 = plt.subplots(figsize=(7, 4.4))
    l1, = ax1.plot(gmid, av0_db, color="C0", lw=2.0, label=r"gain $A_{v0}$")
    ax1.axhline(TARGET_AV0_DB, color="C0", lw=1.0, ls=":")
    ax1.text(gmid[-1], TARGET_AV0_DB + 0.05, "10 dB target", ha="right",
             va="bottom", fontsize=8, color="C0")
    ax1.set_xlabel(r"Inversion level  $g_m/I_D$  [V$^{-1}$]")
    ax1.set_ylabel(r"Differential gain $A_{v0}$  [dB]", color="C0")
    ax1.tick_params(axis="y", labelcolor="C0")
    ax1.set_ylim(7.5, 10.6)                       # show the 8.3 dB plateau AND target

    ax2 = ax1.twinx()
    ax2.grid(False)
    l2, = ax2.plot(gmid, bw_mhz, color="C3", lw=2.0, label=r"bandwidth $f_{-3\mathrm{dB}}$")
    ax2.axhline(TARGET_BW / 1e6, color="C3", lw=1.0, ls=":")
    ax2.set_ylabel(r"Bandwidth $f_{-3\mathrm{dB}}$  [MHz]", color="C3")
    ax2.tick_params(axis="y", labelcolor="C3")
    ax2.set_ylim(145, 200)                        # show the 150 MHz target line

    # mark the first-cut operating point (gm/Id = 15)
    i15 = int(np.argmin(np.abs(gmid - 15.0)))
    ax1.plot(15.0, av0_db[i15], "o", color="C0", ms=6)
    ax2.plot(15.0, bw_mhz[i15], "o", color="C3", ms=6)
    ax1.annotate(f"$g_m/I_D$=15:  {av0_db[i15]:.1f} dB, {bw_mhz[i15]:.0f} MHz, "
                 f"$W$={w_um[i15]:.0f} $\\mu$m",
                 xy=(15.0, av0_db[i15]), xytext=(0.30, 0.30),
                 textcoords="axes fraction", fontsize=8.5, color="0.2",
                 arrowprops=dict(arrowstyle="->", color="0.4"))
    # gain never reaches 10 dB: the r_o cap
    ax1.annotate(r"gain plateaus $\approx$ 8.3 dB (never reaches 10 dB): $r_o$ cap",
                 xy=(0.5, 0.62), xycoords="axes fraction", ha="center",
                 fontsize=8.5, color="C0")

    ax1.set_title(r"Single-stage $r_o$ limit: gain & BW vs $g_m/I_D$  "
                  r"($R_D{=}212\,\Omega$ fixed)", pad=10)
    ax1.legend([l1, l2], [l1.get_label(), l2.get_label()],
               loc="center right", fontsize=9)
    save(fig, "bomu_gain_bw_tradeoff.png")

# gain-vs-power and area-vs-power design-space maps. Each is its own runnable
# script; run here so they regenerate with the rest of the figures.
import runpy
runpy.run_path(os.path.join(HERE, "plot_gain_space.py"), run_name="__main__")
runpy.run_path(os.path.join(HERE, "plot_area_power.py"), run_name="__main__")

print("done")
