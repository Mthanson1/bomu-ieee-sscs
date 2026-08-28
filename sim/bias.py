#!/usr/bin/env python3
"""BoMu tail-bias design & verification (one file, several subcommands).

    bias.py size     Size the simple 2-transistor resistor-programmed NMOS tail
                     mirror: find the output width + V_GS that sinks 2.28 mA at
                     the tight ~0.218 V tail node, with a deep-sat droop probe.
    bias.py verify   Integrated check: diff pair + the REAL sized mirror (not an
                     ideal Itail); confirm Vtail/Itail land and the differential
                     gain/BW are untouched.  [default]
    bias.py compare  Overlay the AC response with the ideal tail source vs. the
                     real mirror -> artifacts/tail_compare.png (needs matplotlib).
    bias.py constgm  Proof-of-concept constant-gm (beta-multiplier) tail bias:
                     sweep VDD at a fixed corner to show A0/f3dB/Itail are far
                     flatter than the simple mirror.  (Explored, NOT adopted.)

Run inside IIC-OSIC-TOOLS (ngspice + $PDK_ROOT; compare also needs numpy/mpl):
  docker exec iic-osic-tools_xvnc_uid_1000 bash -lc \
    'export PDK=sky130A; cd /foss/designs/BoMu-tt-sky130a/sim && python3 -u bias.py [sub]'
"""
import argparse
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _val(out, name):
    m = re.search(name + r"\s*=\s*([-+0-9.eE]+)", out)
    return float(m.group(1)) if m else float("nan")


def _ngspice(deck_text, dir=None):
    dkf = tempfile.NamedTemporaryFile(suffix=".spice", delete=False, dir=dir,
                                      mode="w").name
    with open(dkf, "w") as fh:
        fh.write(deck_text)
    try:
        p = subprocess.run(["ngspice", "-b", dkf], cwd=HERE,
                           capture_output=True, text=True, timeout=300)
        return p.stdout + p.stderr
    finally:
        os.remove(dkf)


# sub 'size': mirror output-device sizing (decoupled from Rref)
SIZE_VDD = 1.2
SIZE_ITARGET = 2.2827e-3    # tail current to sink
SIZE_N = 8                  # mirror ratio (Wref = Wout/N)
SIZE_LCH = 0.5             # mirror channel length [um]


def _size_deck(wout, vtail):
    return f"""* tail-mirror device sizing (generated)
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice tt
* gate bias driven directly for sizing; swept below
Vg nref 0 dc 0.9
* output device: drain held at the real tail voltage
Vt vtail 0 dc {vtail:.4g}
XMout vtail nref 0 0 sky130_fd_pr__nfet_01v8 L={SIZE_LCH} W={wout:.5g} nf={SIZE_N}
* deep-sat probe: identical device, drain at 0.6 V (well into saturation)
Vd2 vd2 0 dc 0.6
XMp vd2 nref 0 0 sky130_fd_pr__nfet_01v8 L={SIZE_LCH} W={wout:.5g} nf={SIZE_N}
.control
dc Vg 0.6 1.15 0.002
let iout = -i(Vt)
let iprobe = -i(Vd2)
meas dc vgx   find v(nref)  when iout={SIZE_ITARGET:.6g}
meas dc iprx  find iprobe   when iout={SIZE_ITARGET:.6g}
.endc
.end
"""


def _size_run(wout, vtail):
    out = _ngspice(_size_deck(wout, vtail))
    return _val(out, "vgx"), _val(out, "iprx")


def cmd_size(_args):
    print(f" TAIL MIRROR DEVICE SIZING  (nfet_01v8 std-VT, N={SIZE_N}, "
          f"L={SIZE_LCH}um)")
    print(f" target I_tail = {SIZE_ITARGET*1e3:.4f} mA;  droop = I(0.6V)/I(Vtail)")
    for vtail in (0.30, 0.35):
        print(f"  Vtail = {vtail:.2f} V")
        print("  Wout [um]   Wref [um]   V_GS [V]   droop I(0.6)/I(Vt)   Rref [ohm]")
        for wout in (40, 48, 56, 64, 80, 100):
            vgs, iprobe = _size_run(wout, vtail)
            ratio = iprobe / SIZE_ITARGET if iprobe == iprobe else float("nan")
            iref = SIZE_ITARGET / SIZE_N
            rref = (SIZE_VDD - vgs) / iref if vgs == vgs else float("nan")
            print(f"  {wout:7.0f}   {wout/SIZE_N:8.2f}   {vgs:7.4f}      "
                  f"{ratio:6.3f}            {rref:8.0f}")
    print(" droop near 1.0 => output device in clean saturation at the tail node")
    print(" (good r_out, corner-robust); pick the smallest Wout with droop <~1.03.")


# sub 'verify': diff pair plus the real sized mirror, run together
V_VDD = 1.2
V_CL = 5e-12
V_WP, V_LP, V_RD = 78.0, 0.15, 245.0     # diff pair (pre-layout operating point)
V_VSC = 1.052                            # raised CM to lift Vtail toward 0.35 V
V_WOUT, V_WREF, V_LM, V_N = 80.0, 10.0, 0.5, 8   # tail mirror


def _verify_deck(rref):
    return f"""* BoMu diff pair + real tail mirror (generated)
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice tt
Vdd vdd 0 {V_VDD}
* diff pair
Vsc vcm 0 dc {V_VSC}
Vdp gp vcm dc 0 ac  0.5
Vdn gn vcm dc 0 ac -0.5
Rsp gp vinp 100
Rsn gn vinn 100
XM1 voutn vinp vtail 0 sky130_fd_pr__nfet_01v8_lvt L={V_LP} W={V_WP:.5g} nf=8
XM2 voutp vinn vtail 0 sky130_fd_pr__nfet_01v8_lvt L={V_LP} W={V_WP:.5g} nf=8
RD1 vdd voutn {V_RD:.6g}
RD2 vdd voutp {V_RD:.6g}
CLp voutp 0 {V_CL:.6g}
CLn voutn 0 {V_CL:.6g}
* tail mirror (simple, resistor-programmed)
Rref vdd nref {rref:.6g}
XMref nref nref 0 0 sky130_fd_pr__nfet_01v8 L={V_LM} W={V_WREF:.5g} nf=1
XMout vtail nref 0 0 sky130_fd_pr__nfet_01v8 L={V_LM} W={V_WOUT:.5g} nf={V_N}
.control
op
let itail = -i(Vdd) - (v(vdd)-v(nref))/{rref:.6g}
print v(vtail) v(nref) v(voutn) v(voutp)
ac dec 100 1k 2G
let vod_db = db(v(voutp)-v(voutn))
meas ac a0 find vod_db at=1k
let tg = a0 - 3
meas ac f3 when vod_db=tg fall=1
.endc
.end
"""


def _verify_run(rref):
    out = _ngspice(_verify_deck(rref))
    vt = _val(out, r"v\(vtail\)")
    vout = _val(out, r"v\(voutn\)")
    # tail current = current through the two RD resistors = drop/RD each
    itail = 2 * (V_VDD - vout) / V_RD
    return vt, itail, _val(out, "a0"), _val(out, "f3")


def cmd_verify(_args):
    print(f" BoMu + REAL tail mirror   (Wout={V_WOUT} Wref={V_WREF} L={V_LM} "
          f"N={V_N}, VSC={V_VSC})")
    print("  Rref [ohm]   Vtail [V]   I_tail [mA]   A_v0 [dB]   f3dB [MHz]")
    for rref in (720, 735, 745, 755, 760):
        vt, itail, a0, f3 = _verify_run(rref)
        print(f"  {rref:8.0f}    {vt:7.4f}    {itail*1e3:8.4f}     {a0:7.3f}    "
              f"{f3/1e6:8.1f}")
    print(" pick Rref that lands I_tail ~ 2.283 mA and Vtail ~ 0.35 V;")
    print(" gain/BW should match the ideal-Itail point (10.16 dB / 166 MHz).")


# sub 'compare': overlay the ideal-source and real-mirror AC responses (matplotlib)
CMP_PAIR = """XM1 voutn vinp vtail 0 sky130_fd_pr__nfet_01v8_lvt L=0.15 W=78 nf=8
XM2 voutp vinn vtail 0 sky130_fd_pr__nfet_01v8_lvt L=0.15 W=78 nf=8
RD1 vdd voutn 245
RD2 vdd voutp 245
CLp voutp 0 5p
CLn voutn 0 5p"""

CMP_DRIVE = """Vdd vdd 0 1.2
Vsc vcm 0 dc {vsc}
Vdp gp vcm dc 0 ac  0.5
Vdn gn vcm dc 0 ac -0.5
Rsp gp vinp 100
Rsn gn vinn 100"""

CMP_TAIL = {
    "ideal":  "Itail vtail 0 dc 2.2827m",
    "mirror": ("Rref vdd nbias 745\n"
               "XM4 nbias nbias 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=10 nf=1\n"
               "XM3 vtail nbias 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=80 nf=8"),
}
CMP_VSC = {"ideal": 0.92, "mirror": 1.052}


def _compare_deck(mode, datfile):
    return f"""* tail comparison ({mode})
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice tt
{CMP_DRIVE.format(vsc=CMP_VSC[mode])}
{CMP_PAIR}
{CMP_TAIL[mode]}
.control
ac dec 100 1k 10G
let vod_db = db(v(voutp)-v(voutn))
meas ac a0_db find vod_db at=1k
let targ = a0_db - 3
meas ac f3db when vod_db=targ fall=1
wrdata {datfile} vod_db
print a0_db
print f3db
op
print v(vtail)
.endc
.end
"""


def _compare_run(mode, np):
    dat = tempfile.NamedTemporaryFile(suffix=".dat", delete=False).name
    dkf = tempfile.NamedTemporaryFile(suffix=".spice", delete=False).name
    with open(dkf, "w") as fh:
        fh.write(_compare_deck(mode, dat))
    try:
        p = subprocess.run(["ngspice", "-b", dkf], cwd=HERE,
                           capture_output=True, text=True, timeout=300)
        out = p.stdout + p.stderr
        d = np.loadtxt(dat)
        freq, mag = d[:, 0], d[:, 1]
        return freq, mag, _val(out, "a0_db"), _val(out, "f3db"), \
            _val(out, r"v\(vtail\)")
    finally:
        for f in (dkf, dat):
            os.remove(f)


def cmd_compare(_args):
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    art = os.path.join(HERE, "..", "artifacts")
    os.makedirs(art, exist_ok=True)
    styles = {"ideal":  dict(color="C0", ls="--", lw=2.0),
              "mirror": dict(color="C3", ls="-",  lw=1.6)}
    labels = {"ideal": "ideal tail source", "mirror": "on-chip mirror"}

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    print("  tail         A_v0 [dB]   f3dB [MHz]   Vtail [V]")
    res = {}
    for mode in ("ideal", "mirror"):
        f, mag, a0, f3, vt = _compare_run(mode, np)
        res[mode] = (a0, f3, vt)
        ax.semilogx(f, mag,
                    label=f"{labels[mode]}  ({a0:.2f} dB, {f3/1e6:.1f} MHz)",
                    **styles[mode])
        ax.axvline(f3, color=styles[mode]["color"], ls=":", lw=1.0, alpha=0.7)
        ax.plot(f3, a0 - 3, "o", color=styles[mode]["color"], ms=5)
        print(f"  {labels[mode]:14s}  {a0:6.2f}     {f3/1e6:7.1f}      {vt:5.3f}")

    ax.axhline(10.0, color="gray", ls="-.", lw=0.8)
    ax.text(1.3e3, 10.15, "10 dB spec", color="gray", fontsize=8)
    ax.axvline(150e6, color="gray", ls="-.", lw=0.8)
    ax.text(1.55e8, ax.get_ylim()[0] + 1.0, "150 MHz spec", color="gray",
            fontsize=8, rotation=90, va="bottom")
    ax.set_xlabel("frequency [Hz]")
    ax.set_ylabel(r"$|v_{od}|$  [dB]")
    ax.set_title("BoMu differential AC: ideal tail source vs. on-chip mirror")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="lower left")
    ax.set_xlim(1e3, 1e10)
    fig.tight_layout()
    outpng = os.path.join(art, "tail_compare.png")
    fig.savefig(outpng, dpi=130)
    print(f"wrote {os.path.relpath(outpng, HERE)}")
    da0 = res["mirror"][0] - res["ideal"][0]
    df3 = (res["mirror"][1] - res["ideal"][1]) / 1e6
    print(f"delta (mirror - ideal):  gain {da0:+.3f} dB,  f3dB {df3:+.1f} MHz")


# sub 'constgm': constant-gm (beta-multiplier) tail bias, proof of concept
CG_VSC = 1.052            # input common-mode (unchanged from present design)
# constant-gm reference sizing (starting point)
CG_WN = 10.0              # MN1 width [um]
CG_K = 4.0               # MN2 = K*MN1 -> (1-1/sqrt(K)) = 0.5
CG_WP = 200.0            # PMOS mirror width [um], 1:1; wide so it can source the loop current
CG_LB = 0.5              # tail-device channel length [um]
CG_LMIR = 2.0           # beta-multiplier loop L [um]: LONG -> high ro
CG_WTAIL = 100.0        # tail sink width [um]
CG_NFT = 10             # tail fingers
# diff-pair / load starting point
CG_WD = 200.0
CG_NFD = 20
CG_LRD = 2.2            # res_high_po_5p73 length -> R_D ~ 194 ohm


def _cg_rd_nom(lrd):
    return 70.11 + 56.42 * lrd


DECK_CONSTGM = """* constant-gm BoMu  corner={corner} T={temp} VDD={vdd} Rb={rb}
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice {corner}
.temp {temp}
.subckt bomu vinp vinn voutn voutp vdd vss
* differential pair + resistive load
XM1 voutn vinp vtail vss sky130_fd_pr__nfet_01v8_lvt L=0.15 W={wd} nf={nfd}
XM2 voutp vinn vtail vss sky130_fd_pr__nfet_01v8_lvt L=0.15 W={wd} nf={nfd}
XRD1 voutn vdd vss sky130_fd_pr__res_high_po_5p73 L={lrd} mult=1
XRD2 voutp vdd vss sky130_fd_pr__res_high_po_5p73 L={lrd} mult=1
* constant-gm (beta-multiplier) reference
XMN1 ng  ng  vss vss sky130_fd_pr__nfet_01v8 L={lmir} W={wn} nf=1
XMN2 nd2 ng  nsr vss sky130_fd_pr__nfet_01v8 L={lmir} W={wn2} nf={nfn2}
Rb   nsr vss {rb}
XMP1 ng  nd2 vdd vdd sky130_fd_pr__pfet_01v8 L={lmir} W={wp} nf=20
XMP2 nd2 nd2 vdd vdd sky130_fd_pr__pfet_01v8 L={lmir} W={wp} nf=20
* tail sink shares ng
XMT  vtail ng vss vss sky130_fd_pr__nfet_01v8 L={lb} W={wtail} nf={nft}
.ends
Vdd vdd 0 {vdd}
Vsc vcm 0 dc {vsc}
Vdp gp vcm dc 0 ac  0.5
Vdn gn vcm dc 0 ac -0.5
Rsp gp vinp 100
Rsn gn vinn 100
Xdut vinp vinn voutn voutp vdd 0 bomu
CLp voutp 0 5p
CLn voutn 0 5p
* steer to the active loop solution (startup cell is AC-irrelevant; added later)
.nodeset v(xdut.ng)=0.90 v(xdut.nd2)=0.15 v(xdut.nsr)=0.05 v(xdut.vtail)=0.35
.control
ac dec 100 1k 10G
let vod = v(voutp)-v(voutn)
let vod_db = db(vod)
meas ac a0_db find vod_db at=1k
let targ = a0_db - 3
meas ac f3db when vod_db=targ fall=1
op
let itot = -i(vdd)
let itail = @m.xdut.xmt.msky130_fd_pr__nfet_01v8[id]
print a0_db
print f3db
print v(xdut.vtail)
print v(xdut.ng)
print v(voutp)
print itot
print itail
.endc
.end
"""


def _cg_run(corner, temp, vdd, rb, wd=CG_WD, nfd=CG_NFD, lrd=CG_LRD):
    out = _ngspice(
        DECK_CONSTGM.format(corner=corner, temp=temp, vdd=vdd, rb=rb, vsc=CG_VSC,
                            wd=wd, nfd=nfd, lrd=lrd, wn=CG_WN, wn2=CG_WN * CG_K,
                            nfn2=int(CG_K), wp=CG_WP, lb=CG_LB, lmir=CG_LMIR,
                            wtail=CG_WTAIL, nft=CG_NFT),
        dir=HERE)
    return dict(a0=_val(out, "a0_db"), f3=_val(out, "f3db"),
                vtail=_val(out, "v(xdut.vtail)"), ng=_val(out, "v(xdut.ng)"),
                vout=_val(out, "v(voutp)"), itot=_val(out, "itot"),
                itail=_val(out, "itail"))


def _cg_vdd_sweep(rb, corner="tt", temp=27):
    print(f"\nVDD sweep @ {corner}/{temp}C, Rb={rb}:")
    print(f"  {'VDD':>5s} | {'A0[dB]':>7s} {'f3[MHz]':>8s} {'Itail[mA]':>9s} "
          f"{'Vtail':>6s} {'Vng':>6s} {'Vout':>6s}")
    for vdd in (1.14, 1.20, 1.26):
        r = _cg_run(corner, temp, vdd, rb)
        print(f"  {vdd:5.2f} | {r['a0']:7.2f} {r['f3']/1e6:8.1f} "
              f"{r['itail']*1e3:9.3f} {r['vtail']:6.3f} {r['ng']:6.3f} "
              f"{r['vout']:6.3f}")


def cmd_constgm(_args):
    print("CONSTANT-GM BIAS  proof-of-concept")
    print(f"  ref: WN={CG_WN} K={CG_K} WP={CG_WP} L={CG_LB}  "
          f"tail Wtail={CG_WTAIL} (nf{CG_NFT})")
    print(f"  amp: WD={CG_WD} (nf{CG_NFD})  R_D~{_cg_rd_nom(CG_LRD):.0f} "
          f"(LRD={CG_LRD})\n")
    print("Rb pick @ tt/27/1.20 :")
    print(f"  {'Rb':>6s} | {'A0':>6s} {'f3[MHz]':>8s} {'Itail[mA]':>9s} "
          f"{'Vtail':>6s} {'Vng':>6s} {'Itot[mA]':>8s}")
    best = None
    for rb in (30, 50, 70, 100, 140, 200):
        r = _cg_run("tt", 27, 1.20, rb)
        if best is None or abs(r["itail"] - 2.3e-3) < abs(best[1] - 2.3e-3):
            best = (rb, r["itail"])
        print(f"  {rb:6d} | {r['a0']:6.2f} {r['f3']/1e6:8.1f} "
              f"{r['itail']*1e3:9.3f} {r['vtail']:6.3f} {r['ng']:6.3f} "
              f"{r['itot']*1e3:8.3f}")
    _cg_vdd_sweep(best[0])


# dispatch
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("size", help="mirror output-device sizing")
    sub.add_parser("verify", help="diff pair + real mirror integrated check [default]")
    sub.add_parser("compare", help="ideal vs mirror AC overlay (matplotlib)")
    sub.add_parser("constgm", help="constant-gm bias proof-of-concept")
    args = ap.parse_args()
    {
        None: cmd_verify, "verify": cmd_verify, "size": cmd_size,
        "compare": cmd_compare, "constgm": cmd_constgm,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
