#!/usr/bin/env python3
"""BoMu diff-pair sizing & design-space sweeps (gm/Id method, sky130A).

    sizing.py worksheet [--spice]
                     Top-down gm/Id sizing worksheet: R_D from BW+C_L, gm from
                     gain, pick gm/Id -> Id -> W from the sky130A grid, then
                     re-check with the real R_D||ro load, swing and headroom.
                     --spice drops W into a generated deck and prints predicted
                     vs. ngspice.  [default]
    sizing.py sweep  Impact of R_D (exact from the grid, no SPICE) and channel
                     length L (SPICE), plus a gate series-R sanity check.  Writes
                     bomu_sweep_rd.png and bomu_sweep_L.png into ../docs/Figures.

The gm/Id grid loader lives in the `extern/sky130A-gmid` git submodule
(imported as the `gmid` package; run `git submodule update --init`).

Run inside IIC-OSIC-TOOLS (numpy; sweep also needs matplotlib + $PDK_ROOT):
  docker run --rm -e PDK=sky130A -e PDK_ROOT=/foss/pdks -v "$DESIGNS":/foss/designs \
    hpretl/iic-osic-tools:latest -s bash -lc \
    'cd /foss/designs/BoMu-tt-sky130a/sim && python3 sizing.py [worksheet|sweep]'
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# The gm/Id grid loader is vendored under extern/sky130A-gmid (git submodule).
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "extern",
                                                 "sky130A-gmid")))


# sub 'worksheet': gm/Id top-down sizing, with optional --spice verify. The flow
# (mirrored from mvm-tia-comp) is: R_D from BW+C_L, gm from the gain target, pick
# gm/Id to get Id, then W = Id/Jd from the grid; step 5 re-checks with the real
# R_D||ro load, swing and saturation.
DESIGN = dict(
    VDD=1.2,
    BW=150e6,        # target -3dB bandwidth [Hz]
    Av0_db=10.0,     # target differential DC gain [dB]
    vod_pp=0.400,    # target differential output swing [V, peak-to-peak]
    C_L=5e-12,       # per-output pad cap [F], FIXED by the TinyTapeout IO, not a knob
    L=0.15,          # channel length [um]
    # free knobs
    gmid=15.0,       # chosen inversion level for the pair [1/V]
    V_S=0.30,        # tail-node DC voltage [V]  (>= 0.2 V sink compliance) -> Vsb
)


def size_pair(grid, Id, gmid, Vsb, Vds):
    """One diff-pair device: W from Jd lookup, plus gm, ro, fT, Cgg."""
    lu = grid.lookup(gmid, Vsb, Vds)
    Jd = lu["jd"]                    # uA/um
    W = Id / (Jd * 1e-6)            # um  (Id in A, Jd*1e-6 in A/um)
    gm = gmid * Id
    ro = lu["gmro"] / gm
    Cgg = gm / (2 * np.pi * lu["ft"])
    return dict(Id=Id, gmid=gmid, Vsb=Vsb, Vds=Vds, Vov=2.0 / gmid,
                Jd=Jd, W=W, gm=gm, ro=ro, gmro=lu["gmro"], ft=lu["ft"], Cgg=Cgg)


def worksheet_run(d=DESIGN):
    from gmid import GmidGrid
    grid = GmidGrid()
    VDD = d["VDD"]

    # targets set R_D, gm, Id
    Av0 = 10.0 ** (d["Av0_db"] / 20.0)             # V/V
    R_D = 1.0 / (2 * np.pi * d["BW"] * d["C_L"])   # ohm  (from BW + fixed C_L)
    gm_req = Av0 / R_D                             # S    (from gain, ideal no-ro)
    Id = gm_req / d["gmid"]                        # A    per branch
    Itail = 2 * Id

    # bias plan: node voltages from the current budget
    V_D = VDD - Id * R_D                            # drain DC
    Vsb = d["V_S"]                                  # bulk at gnd -> Vsb = V_S
    Vds = V_D - d["V_S"]

    m = size_pair(grid, Id, d["gmid"], Vsb, Vds)

    # re-check with the real load R_D||ro
    R_L = R_D * m["ro"] / (R_D + m["ro"])
    Av0_real = m["gm"] * R_L
    Av0_real_db = 20 * np.log10(Av0_real)
    BW_real = 1.0 / (2 * np.pi * R_L * d["C_L"])

    # swing + headroom
    se_peak = d["vod_pp"] / 4.0                     # single-ended peak (diff pp/2, /2)
    V_D_min = V_D - se_peak
    sat_margin = V_D_min - (d["V_S"] + m["Vov"])    # want > 0 for saturation w/ swing
    swing_reserve = Id * R_D - se_peak              # want > 0: enough Ibias for swing
    Ptot = VDD * Itail

    # report
    print(" BoMu diff-pair sizing worksheet  (sky130A, nfet L={:.2f}, gm/Id)".format(d["L"]))
    print(f" targets:  BW={d['BW']/1e6:.0f} MHz   Av0={d['Av0_db']:.1f} dB"
          f"   v_od={d['vod_pp']*1e3:.0f} mVpp   C_L={d['C_L']*1e12:.1f} pF (fixed)")
    print("-" * 68)
    print(f" R_D    = 1/(2pi.BW.C_L)      = {R_D:7.1f} ohm")
    print(f" gm     = Av0/R_D (ideal)     = {gm_req*1e3:7.2f} mS")
    print(f" Id     = gm/(gm/Id)          = {Id*1e6:7.1f} uA   -> I_tail = {Itail*1e6:.1f} uA")
    print(f" nodes:  V_D = {V_D:.3f} V   V_S(tail) = {d['V_S']:.3f} V"
          f"   Vds = {Vds:.3f} V   Vsb = {Vsb:.3f} V")
    print("-" * 68)
    hdr = ("gm/Id", "Vov", "Jd", "W_um", "gm_mS", "ro_ohm", "gm.ro", "fT_GHz")
    print(" {:>5} {:>5} {:>6} {:>7} {:>6} {:>7} {:>6} {:>7}".format(*hdr))
    print(" {:>5.1f} {:>5.3f} {:>6.2f} {:>7.1f} {:>6.2f} {:>7.0f} {:>6.1f} {:>7.1f}"
          .format(m["gmid"], m["Vov"], m["Jd"], m["W"], m["gm"] * 1e3,
                  m["ro"], m["gmro"], m["ft"] / 1e9))
    print("-" * 68)
    print(" With real load R_D||ro (ro included):")
    print(f"   R_L    = R_D||ro           = {R_L:7.1f} ohm")
    print(f"   Av0    = gm.R_L            = {Av0_real:6.2f} V/V ({Av0_real_db:5.2f} dB)"
          f"   [target {d['Av0_db']:.1f} dB]")
    print(f"   f-3dB  = 1/(2pi.R_L.C_L)   = {BW_real/1e6:6.1f} MHz"
          f"                 [target {d['BW']/1e6:.0f} MHz]")
    print(" Swing / headroom:")
    print(f"   single-ended peak          = {se_peak*1e3:5.1f} mV  (v_od/4)")
    print(f"   sat margin V_Dmin-(V_S+Vov)= {sat_margin*1e3:+5.0f} mV  "
          f"({'ok' if sat_margin > 0 else 'LOW'})")
    print(f"   swing reserve Id.R_D-peak  = {swing_reserve*1e3:+5.0f} mV  "
          f"({'ok' if swing_reserve > 0 else 'LOW'})")
    print(f"   P_total = VDD.I_tail       = {Ptot*1e3:.2f} mW")

    return dict(R_D=R_D, gm_req=gm_req, Id=Id, Itail=Itail, m=m,
                V_D=V_D, Vds=Vds, Av0_real_db=Av0_real_db, BW_real=BW_real)


def _spice_deck(d, pred, acfile):
    """Self-contained diff-pair deck: op + differential ac, ideal R_D loads,
    ideal tail sink, W from the sizing.  Mirrors sim/tb_ac.spice."""
    W = pred["m"]["W"]
    R_D = pred["R_D"]
    Id = pred["Id"]
    VSC = d["V_S"] + 0.6            # rough gate CM: V_S + a ~0.6 V Vgs guess
    return f"""* sizing.py worksheet --spice verify (generated, temporary)
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice tt
.subckt bomu vinp vinn voutp voutn vdd vss vtail
XM1 voutn vinp vtail vss sky130_fd_pr__nfet_01v8_lvt L={d['L']} W={W:.4g} nf=8
XM2 voutp vinn vtail vss sky130_fd_pr__nfet_01v8_lvt L={d['L']} W={W:.4g} nf=8
RD1 vdd voutn {R_D:.6g}
RD2 vdd voutp {R_D:.6g}
.ends bomu
Vdd  vdd 0 {d['VDD']}
Vsc  vcm 0 dc {VSC:.4g}
Vdp  gp vcm dc 0 ac  0.5
Vdn  gn vcm dc 0 ac -0.5
Rsp  gp vinp 100
Rsn  gn vinn 100
Xdut vinp vinn voutp voutn vdd 0 vtail bomu
Itail vtail 0 dc {2*Id:.6g}
CLp  voutp 0 {d['C_L']:.6g}
CLn  voutn 0 {d['C_L']:.6g}
.control
op
print i(vdd) v(vtail) v(voutp) v(voutn) @m.xdut.xm1.msky130_fd_pr__nfet_01v8_lvt[gm]
ac dec 100 1k 10G
wrdata {acfile} vdb(voutp,voutn)
.endc
.end
"""


def _fnum(text, name):
    m = re.search(re.escape(name) + r"\s*=?\s*([-+0-9.eE]+)", text)
    return float(m.group(1)) if m else float("nan")


def spice_verify(d, pred):
    if shutil.which("ngspice") is None:
        print("\n[--spice] ngspice not found -- run inside the iic-osic-tools "
              "container (see header).")
        return
    acfile = tempfile.NamedTemporaryFile(suffix="_ac.dat", delete=False).name
    deckfile = tempfile.NamedTemporaryFile(suffix=".spice", delete=False).name
    with open(deckfile, "w") as fh:
        fh.write(_spice_deck(d, pred, acfile))
    try:
        p = subprocess.run(["ngspice", "-b", deckfile], cwd=HERE,
                           capture_output=True, text=True, timeout=300)
        out = p.stdout + p.stderr
        ivdd = abs(_fnum(out, "i(vdd)"))
        vtail = _fnum(out, "v(vtail)")
        gm_sp = _fnum(out, "nfet_01v8_lvt[gm]")
        a = np.loadtxt(acfile)
        f, mag = a[:, 0], a[:, 1]
        gdc = mag[0]
        below = f[mag >= gdc - 3.0]
        f3db = below[-1] if below.size else float("nan")
    finally:
        for f_ in (acfile, deckfile):
            try:
                os.remove(f_)
            except OSError:
                pass

    def row(label, pv, sv, fmt="{:>11.4g}"):
        ps = fmt.format(pv) if pv == pv else "{:>11}".format("n/a")
        ss = fmt.format(sv) if sv == sv else "{:>11}".format("n/a")
        print(f"   {label:<26}{ps}   {ss}")

    print(" SPICE VERIFY  (ngspice, tt corner)       predicted        SPICE")
    print("-" * 68)
    row("I_tail [uA]", pred["Itail"] * 1e6, ivdd * 1e6)
    row("gm per device [mS]", pred["gm_req"] * 1e3, gm_sp * 1e3)
    row("V_tail [V]", d["V_S"], vtail)
    row("Av0 (differential) [dB]", pred["Av0_real_db"], gdc)
    row("f-3dB [MHz]", pred["BW_real"] / 1e6, f3db / 1e6)


def cmd_worksheet(args):
    pred = worksheet_run(DESIGN)
    if args.spice:
        spice_verify(DESIGN, pred)


# sub 'sweep': R_D (grid, exact) plus L (SPICE) plus a gate-R check; writes figures
SW_VDD, SW_CL = 1.2, 5e-12
SW_L0, SW_W0 = 0.15, 68.0
SW_ID0 = 0.9935e-3                 # per-branch; I_tail = 2*ID0
SW_GM0 = 14.90e-3                  # gm at the base point (~const vs R_D and L here)
SW_GMID0 = 15.0
SW_RD0, SW_V_S, SW_VOV = 212.0, 0.30, 0.133
SW_VSC = 0.9
SW_TARGET_AV0_DB, SW_TARGET_BW = 10.0, 150e6
SW_PWR = SW_VDD * 2 * SW_ID0


def _sweep_deck(rd, L, W, itail, rg):
    return f"""* BoMu sweep point (generated, temporary)
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice tt
.subckt bomu vinp vinn voutp voutn vdd vss vtail
XM1 voutn vinp vtail vss sky130_fd_pr__nfet_01v8_lvt L={L:.4g} W={W:.5g} nf=8
XM2 voutp vinn vtail vss sky130_fd_pr__nfet_01v8_lvt L={L:.4g} W={W:.5g} nf=8
RD1 vdd voutn {rd:.6g}
RD2 vdd voutp {rd:.6g}
.ends bomu
Vdd  vdd 0 {SW_VDD}
Vsc  vcm 0 dc {SW_VSC}
Vdp  gp vcm dc 0 ac  0.5
Vdn  gn vcm dc 0 ac -0.5
Rsp  gp vinp {rg:.6g}
Rsn  gn vinn {rg:.6g}
Xdut vinp vinn voutp voutn vdd 0 vtail bomu
Itail vtail 0 dc {itail:.6g}
CLp  voutp 0 {SW_CL:.6g}
CLn  voutn 0 {SW_CL:.6g}
.control
op
print i(vdd) v(vtail) v(voutp)
ac dec 30 1k 5G
let vod_db = db(v(voutp)-v(voutn))
wrdata {{ACFILE}} vod_db
.endc
.end
"""


def _sweep_run_point(rd, L, W, itail, rg=100.0):
    acf = tempfile.NamedTemporaryFile(suffix="_ac.dat", delete=False).name
    dkf = tempfile.NamedTemporaryFile(suffix=".spice", delete=False).name
    with open(dkf, "w") as fh:
        fh.write(_sweep_deck(rd, L, W, itail, rg).replace("{ACFILE}", acf))
    try:
        p = subprocess.run(["ngspice", "-b", dkf], cwd=HERE,
                           capture_output=True, text=True, timeout=300)
        out = p.stdout + p.stderr

        def num(name):
            m = re.search(re.escape(name) + r"\s*=?\s*([-+0-9.eE]+)", out)
            return float(m.group(1)) if m else float("nan")
        ivdd, vd = abs(num("i(vdd)")), num("v(voutp)")
        a = np.loadtxt(acf)
        if a.ndim < 2 or a.shape[0] < 2:
            a0 = f3 = float("nan")
        else:
            f, mag = a[:, 0], a[:, 1]
            a0 = mag[0]
            b = np.where(mag >= a0 - 3.0)[0]
            f3 = f[b[-1]] if b.size else float("nan")
    finally:
        for x in (acf, dkf):
            try:
                os.remove(x)
            except OSError:
                pass
    return dict(a0=a0, f3=f3, pwr=ivdd * SW_VDD, vd=vd)


def cmd_sweep(_args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from gmid import GmidGrid

    fig_dir = os.path.join(HERE, "..", "docs", "Figures")
    os.makedirs(fig_dir, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 150, "font.size": 11,
                         "axes.grid": True, "grid.alpha": 0.3})

    def save(fig, name):
        path = os.path.join(fig_dir, name)
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        print("wrote", os.path.relpath(path, HERE))

    # 1) R_D sweep, exact from the gm/Id grid (no SPICE, iso-power)
    grid = GmidGrid()
    print(" R_D SWEEP  (W=68, I_tail=1.99 mA -> iso-power {:.2f} mW; grid)"
          .format(SW_PWR * 1e3))
    print("   R_D[ohm]  V_D[V]  r_o[ohm]  A_v0[dB]  f-3dB[MHz]  GBW[MHz]  sat")
    rds = np.array([50, 100, 150, 212, 300, 450, 600, 800, 1200])
    rd_a0, rd_bw = [], []
    for rd in rds:
        V_D = SW_VDD - SW_ID0 * rd
        lu = grid.lookup(SW_GMID0, SW_V_S, max(V_D - SW_V_S, 0.05))
        ro = lu["gmro"] / SW_GM0
        R_L = rd * ro / (rd + ro)
        a0 = 20 * np.log10(SW_GM0 * R_L)
        f3 = 1.0 / (2 * np.pi * R_L * SW_CL)
        rd_a0.append(a0)
        rd_bw.append(f3 / 1e6)
        sat = "ok" if (V_D - SW_V_S) > SW_VOV + 0.05 else "TRI"
        print(f"   {rd:7.0f}  {V_D:5.3f}  {ro:7.0f}  {a0:7.2f}  {f3/1e6:9.1f}"
              f"  {(10**(a0/20))*f3/1e6:7.0f}  {sat}")
    rd_a0, rd_bw = np.array(rd_a0), np.array(rd_bw)
    print("   note: gain*BW ~ const (= gm/2piC_L); power is flat (R_D sets no current).")

    # 2) gate series-resistance check (2 SPICE points at the base)
    print(" GATE SERIES RESISTANCE  (base point, SPICE)")
    print("   R_g[ohm]   A_v0[dB]   f-3dB[MHz]")
    for rg in (100.0, 1e4):
        r = _sweep_run_point(SW_RD0, SW_L0, SW_W0, 2 * SW_ID0, rg=rg)
        print(f"   {rg:7.0f}   {r['a0']:7.3f}   {r['f3']/1e6:8.1f}")
    print("   -> 100 ohm changes nothing; even 10 k barely moves the corner")
    print("      (gate pole 1/(2pi Rg Cgg) reaches the 5 pF output pole only ~10 k).")

    # 3) L sweep (SPICE; W scales with L to hold gm/Id~15; R_D=212, iso-power)
    print(" L SWEEP  (W prop. L -> gm/Id~15; R_D=212, iso-power {:.2f} mW)"
          .format(SW_PWR * 1e3))
    print("   L[um]   W[um]   A_v0[dB]  f-3dB[MHz]  P[mW]  V_D[V]")
    Ls = [0.15, 0.25, 0.40, 0.60]
    l_a0, l_bw, l_x = [], [], []
    for L in Ls:
        W = SW_W0 * (L / SW_L0)
        r = _sweep_run_point(SW_RD0, L, W, 2 * SW_ID0)
        l_a0.append(r["a0"])
        l_bw.append(r["f3"] / 1e6)
        l_x.append(L)
        print(f"   {L:5.2f}  {W:6.1f}  {r['a0']:7.2f}  {r['f3']/1e6:9.1f}"
              f"  {r['pwr']*1e3:5.2f}  {r['vd']:5.3f}")
    l_a0, l_bw = np.array(l_a0), np.array(l_bw)

    # figures
    def twin(x, a0, bw, xlabel, title, fname, mark=None):
        fig, ax1 = plt.subplots(figsize=(7, 4.4))
        ax1.plot(x, a0, "o-", color="C0", lw=2, label=r"gain $A_{v0}$")
        ax1.axhline(SW_TARGET_AV0_DB, color="C0", lw=1.0, ls=":")
        ax1.set_xlabel(xlabel)
        ax1.set_ylabel(r"Differential gain $A_{v0}$  [dB]", color="C0")
        ax1.tick_params(axis="y", labelcolor="C0")
        ax2 = ax1.twinx()
        ax2.grid(False)
        ax2.plot(x, bw, "s--", color="C3", lw=2, label=r"BW $f_{-3\mathrm{dB}}$")
        ax2.axhline(SW_TARGET_BW / 1e6, color="C3", lw=1.0, ls=":")
        ax2.set_ylabel(r"Bandwidth $f_{-3\mathrm{dB}}$  [MHz]", color="C3")
        ax2.tick_params(axis="y", labelcolor="C3")
        if mark is not None:
            ax1.axvline(mark, color="0.5", lw=0.9, ls="-.")
        ax1.set_title(title, pad=10)
        save(fig, fname)

    twin(rds, rd_a0, rd_bw, r"Load resistor $R_D$  [$\Omega$]",
         r"$R_D$ sweep: gain$\uparrow$/BW$\downarrow$ along constant gain$\times$BW "
         r"(iso-power)", "bomu_sweep_rd.png", mark=SW_RD0)
    twin(l_x, l_a0, l_bw, r"Channel length $L$  [$\mu$m]",
         r"$L$ sweep: longer $L$ raises $r_o$ -> gain$\to$10 dB (iso-power)",
         "bomu_sweep_L.png", mark=SW_L0)
    print("done")


# dispatch
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p_ws = sub.add_parser("worksheet", help="gm/Id sizing worksheet [default]")
    p_ws.add_argument("--spice", action="store_true",
                      help="also run the ngspice predicted-vs-actual verify")
    sub.add_parser("sweep", help="R_D + L design-space sweeps (writes figures)")
    args = ap.parse_args()
    if args.cmd in (None, "worksheet"):
        if not hasattr(args, "spice"):
            args.spice = False
        cmd_worksheet(args)
    else:
        cmd_sweep(args)


if __name__ == "__main__":
    main()
