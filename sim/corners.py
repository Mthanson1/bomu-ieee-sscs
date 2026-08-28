#!/usr/bin/env python3
"""BoMu PVT corner sweeps and sizing search (one file, several subcommands).

    corners.py sch     PVT sweep off the SCHEMATIC netlist (re-netlists
                       ip/bomu.sch so the load + Rref are REAL res_high_po that
                       track the resistor corner ll/hh).  [default]
    corners.py pex [pex|rcx]
                       Same PVT grid off an EXTRACTED netlist (verify/bomu_*.spice)
                       to see the layout-parasitic gain/BW penalty.  Default rcx.
    corners.py search  Staged (R_D -> W -> I_tail) search for a point passing the
                       whole relaxed box (0-70 C, VDD +-5%), parameterized DUT.
    corners.py vdd     Simple-mirror under a REGULATED 1.20 V supply: smallest
                       pair width passing process x temp, then the VDD window.
    corners.py itail   Sweep the tail current (via Rref) at the binding corners
                       to prove current alone cannot clear the GBW wall.
    corners.py mc      Input-referred offset Monte Carlo. sky130 open ngspice has
                       no native statistical mismatch, so mismatch is injected
                       (Pelgrom Vth + W/beta + load-R); see MC_* constants.
    corners.py acq     CMRR, PSRR and input-referred noise at the nominal point
                       (injects one 1-sigma mismatch so the diff CMRR/PSRR are finite).

Specs everywhere: A_v0 >= 10 dB and f_3dB >= 150 MHz.

Run inside IIC-OSIC-TOOLS:
  docker exec iic-osic-tools_xvnc_uid_1000 bash -lc \
    'export PDK=sky130A; cd /foss/designs/BoMu-tt-sky130a/sim && python3 -u corners.py [sub]'
"""
import argparse
import math
import os
import random
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NETDIR = os.path.join(ROOT, "artifacts", "xschem_netlist")
NETLIST = os.path.join(NETDIR, "bomu.spice")

# spec targets
A0_MIN = 10.0       # dB
F3_MIN = 150e6      # Hz
VSC = 1.052         # input common-mode (design point; held fixed across VDD)

# PVT grid. Corner names are sky130 lib sections <fet>[_<rc>]. The two that bind
# are ss_ll (slow FET + low R gives worst gain) and ss_hh (high R gives worst BW).
CORNERS = ["tt", "ss", "ff", "ss_ll", "ss_hh", "ff_ll", "ff_hh"]
TEMPS = [0, 27, 70]                 # deg C (agreed 0-70 box)
VDDS = [1.14, 1.20, 1.26]           # +/-5% around 1.2 V


# shared helpers
def val(out, name):
    m = re.search(re.escape(name) + r"\s*=\s*([-+0-9.eE]+)", out)
    return float(m.group(1)) if m else float("nan")


def ngspice(deck_text):
    """Run one deck through ngspice -b and return its combined output.

    The deck has to sit in sim/ so ngspice picks up sim/.spiceinit
    (ngbehavior=hsa); a deck in /tmp makes the sky130 models parse to all-NaN.
    """
    dk = tempfile.NamedTemporaryFile(suffix=".spice", delete=False, mode="w",
                                     dir=HERE)
    dk.write(deck_text)
    dk.close()
    try:
        p = subprocess.run(["ngspice", "-b", dk.name], cwd=HERE,
                           capture_output=True, text=True, timeout=300)
        return p.stdout + p.stderr
    finally:
        os.remove(dk.name)


def netlist_schematic():
    """Re-netlist ip/bomu.sch -> artifacts/xschem_netlist/bomu.spice and
    promote the top wrapper from '**.subckt' (comment) to a real '.subckt'."""
    os.makedirs(NETDIR, exist_ok=True)
    subprocess.run(
        ["xschem", "--rcfile", "env/.xschemrc", "-q", "-s", "-n", "-x",
         "--tcl", "set top_subckt 1", "-o", "artifacts/xschem_netlist",
         "ip/bomu.sch"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    with open(NETLIST) as fh:
        txt = fh.read()
    if "IS MISSING" in txt:
        raise RuntimeError("xschem netlist failed (symbols missing); check "
                           "env/.xschemrc sources the PDK xschemrc.")
    txt = re.sub(r"^\*\*\.subckt", ".subckt", txt, flags=re.M)
    txt = re.sub(r"^\*\*\.ends", ".ends", txt, flags=re.M)
    with open(NETLIST, "w") as fh:
        fh.write(txt)
    m = re.search(r"^\.subckt bomu (.+)$", txt, flags=re.M)
    return m.group(1).split() if m else []


def _summarize(fails, worst_a0, worst_f3, n):
    print(f"worst gain : {worst_a0[0]:.2f} dB  @ {worst_a0[1]}  "
          f"(spec {A0_MIN:.1f} dB)")
    print(f"worst f3dB : {worst_f3[0]/1e6:.1f} MHz @ {worst_f3[1]}  "
          f"(spec {F3_MIN/1e6:.0f} MHz)")
    if fails:
        print(f"\n{len(fails)} of {n} points FAIL:")
        for tag, a0, f3 in fails:
            print(f"  {tag:22s} A0={a0:.2f}dB f3={f3/1e6:.1f}MHz")
    else:
        print(f"\nALL {n} points PASS both specs.")


# sub 'sch': PVT sweep off the schematic netlist
DECK_SCH = """* BoMu PVT corner: {corner}, T={temp}C, VDD={vdd}
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice {corner}
.include {netlist}
.temp {temp}
.param VDD={vdd}
.param VSC={vsc}
Vdd vdd 0 {{VDD}}
Vsc vcm 0 dc {{VSC}}
Vdp gp vcm dc 0 ac  0.5
Vdn gn vcm dc 0 ac -0.5
Rsp gp vinp 100
Rsn gn vinn 100
* subckt port order: vinp vinn voutp voutn VDD VSS
Xdut vinp vinn voutp voutn vdd 0 bomu
CLp voutp 0 5p
CLn voutn 0 5p
.control
ac dec 100 1k 10G
let vod = v(voutp)-v(voutn)
let vod_db = db(vod)
meas ac a0_db find vod_db at=1k
let targ = a0_db - 3
meas ac f3db when vod_db=targ fall=1
op
let itot = -i(vdd)
print a0_db
print f3db
print v(xdut.vtail)
print v(voutp)
print itot
.endc
.end
"""


def run_sch(corner, temp, vdd):
    out = ngspice(DECK_SCH.format(corner=corner, temp=temp, vdd=vdd, vsc=VSC,
                                  netlist=NETLIST))
    return dict(a0=val(out, "a0_db"), f3=val(out, "f3db"),
                vtail=val(out, "v(xdut.vtail)"),
                vout=val(out, "v(voutp)"), itot=val(out, "itot"))


def cmd_sch(_args):
    ports = netlist_schematic()
    print(f"netlisted .subckt bomu ports: {' '.join(ports)}")
    print(f"specs: A_v0 >= {A0_MIN:.1f} dB  and  f3dB >= {F3_MIN/1e6:.0f} MHz")
    print(f"input common-mode VSC held fixed at {VSC} V across VDD\n")
    hdr = (f"{'corner':7s} {'T[C]':>5s} {'VDD':>5s} | {'A0[dB]':>7s} "
           f"{'f3[MHz]':>8s} {'Vtail':>6s} {'Vout':>6s} {'Itot[mA]':>8s}  verdict")
    print(hdr)
    print("-" * len(hdr))
    fails, worst_a0, worst_f3 = [], (1e9, None), (1e9, None)
    for corner in CORNERS:
        for temp in TEMPS:
            for vdd in VDDS:
                r = run_sch(corner, temp, vdd)
                a0, f3 = r["a0"], r["f3"]
                ok = (a0 >= A0_MIN) and (f3 >= F3_MIN)
                tag = f"{corner}/{temp}C/{vdd}V"
                worst_a0 = min(worst_a0, (a0, tag))
                worst_f3 = min(worst_f3, (f3, tag))
                if not ok:
                    fails.append((tag, a0, f3))
                verdict = "PASS" if ok else "**FAIL**"
                print(f"{corner:7s} {temp:5d} {vdd:5.2f} | {a0:7.2f} "
                      f"{f3/1e6:8.1f} {r['vtail']:6.3f} {r['vout']:6.3f} "
                      f"{r['itot']*1e3:8.3f}  {verdict}")
    print("-" * len(hdr))
    _summarize(fails, worst_a0, worst_f3, len(CORNERS)*len(TEMPS)*len(VDDS))


# sub 'pex': PVT sweep off an extracted (parasitic) netlist
PEX_VARIANTS = {
    "pex": os.path.join(ROOT, "verify", "bomu_pex.spice"),   # cap-only
    "rcx": os.path.join(ROOT, "verify", "bomu_rcx.spice"),   # R + C
}

# The extracted subckt ports are VSS voutn voutp VDD vinp vinn (substrate folds
# into VSS, no separate port), so the DUT instance below is wired to match.
DECK_PEX = """* BoMu POST-LAYOUT ({variant}) corner: {corner}, T={temp}C, VDD={vdd}
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice {corner}
.include {netlist}
.temp {temp}
.param VDD={vdd}
.param VSC={vsc}
Vdd vdd 0 {{VDD}}
Vsc vcm 0 dc {{VSC}}
Vdp gp vcm dc 0 ac  0.5
Vdn gn vcm dc 0 ac -0.5
Rsp gp vinp 100
Rsn gn vinn 100
Xdut 0 voutn voutp vdd vinp vinn bomu
CLp voutp 0 5p
CLn voutn 0 5p
.control
ac dec 30 1k 10G
let vod = v(voutp)-v(voutn)
let vod_db = db(vod)
meas ac a0_db find vod_db at=1k
let targ = a0_db - 3
meas ac f3db when vod_db=targ fall=1
op
let itot = -i(vdd)
print a0_db
print f3db
print v(voutp)
print itot
.endc
.end
"""


def run_pex(variant, netlist, corner, temp, vdd):
    out = ngspice(DECK_PEX.format(variant=variant, corner=corner, temp=temp,
                                  vdd=vdd, vsc=VSC, netlist=netlist))
    return dict(a0=val(out, "a0_db"), f3=val(out, "f3db"),
                vout=val(out, "v(voutp)"), itot=val(out, "itot"))


def cmd_pex(args):
    variant = args.variant
    if variant not in PEX_VARIANTS:
        sys.exit(f"pex variant must be pex|rcx (got {variant!r})")
    netlist = PEX_VARIANTS[variant]
    print(f"POST-LAYOUT corners: variant={variant}  "
          f"netlist={os.path.relpath(netlist, ROOT)}")
    print(f"specs: A_v0 >= {A0_MIN:.1f} dB  and  f3dB >= {F3_MIN/1e6:.0f} MHz")
    print(f"input common-mode VSC held fixed at {VSC} V across VDD\n")
    hdr = (f"{'corner':7s} {'T[C]':>5s} {'VDD':>5s} | {'A0[dB]':>7s} "
           f"{'f3[MHz]':>8s} {'Vout':>6s} {'Itot[mA]':>8s}  verdict")
    print(hdr)
    print("-" * len(hdr))
    fails, worst_a0, worst_f3 = [], (1e9, None), (1e9, None)
    for corner in CORNERS:
        for temp in TEMPS:
            for vdd in VDDS:
                r = run_pex(variant, netlist, corner, temp, vdd)
                a0, f3 = r["a0"], r["f3"]
                ok = (a0 >= A0_MIN) and (f3 >= F3_MIN)
                tag = f"{corner}/{temp}C/{vdd}V"
                worst_a0 = min(worst_a0, (a0, tag))
                worst_f3 = min(worst_f3, (f3, tag))
                if not ok:
                    fails.append((tag, a0, f3))
                verdict = "PASS" if ok else "**FAIL**"
                print(f"{corner:7s} {temp:5d} {vdd:5.2f} | {a0:7.2f} "
                      f"{f3/1e6:8.1f} {r['vout']:6.3f} "
                      f"{r['itot']*1e3:8.3f}  {verdict}")
    print("-" * len(hdr))
    _summarize(fails, worst_a0, worst_f3, len(CORNERS)*len(TEMPS)*len(VDDS))


# sub 'search': staged R_D then W then I_tail sizing search on a parameterized DUT
SEARCH_BW_CORNER = ("ss_hh", 70, 1.14)     # worst BW
SEARCH_GAIN_CORNER = ("ss_ll", 70, 1.14)   # worst gain
BW_AIM = 158e6                             # Hz (>150 with ~5% margin)
GAIN_AIM = 10.30                           # dB (>10 with 0.3 dB margin)
LRD_LIST = [1.4, 1.6, 1.8, 2.0, 2.2, 2.5, 3.1]   # -> R_D below
WD_LIST = [120, 160, 200, 240, 280, 320]         # um total width
STAGE1_WD = 200                            # fixed W for the R_D (BW) sweep
RREF_LADDER = [560, 460, 380]              # raise current if W alone can't hit gain


def rd_nom(lrd):
    """Nominal (tt) R_D of a res_high_po_5p73 of length lrd, per the symbol."""
    return 70.11 + 56.42 * lrd


def nf_of(wd):
    """Keep ~9.75 um finger width (same as the current design)."""
    return max(8, round(wd / 9.75))


DECK_SEARCH = """* sizing search {corner} T={temp} VDD={vdd} WD={wd} LRD={lrd} RREF={rref}
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice {corner}
.temp {temp}
.subckt bomu vinp vinn voutp voutn vdd vss WD=130 NF=13 LRD=2.0 RREF=560
XM1 voutn vinp vtail vss sky130_fd_pr__nfet_01v8_lvt L=0.15 W={{WD}} nf={{NF}}
XM2 voutp vinn vtail vss sky130_fd_pr__nfet_01v8_lvt L=0.15 W={{WD}} nf={{NF}}
XRD1 voutn vdd vss sky130_fd_pr__res_high_po_5p73 L={{LRD}} mult=1
XRD2 voutp vdd vss sky130_fd_pr__res_high_po_5p73 L={{LRD}} mult=1
Rref vdd nbias {{RREF}}
XM4 nbias nbias vss vss sky130_fd_pr__nfet_01v8 L=0.5 W=10 nf=1
XM3 vtail nbias vss vss sky130_fd_pr__nfet_01v8 L=0.5 W=80 nf=8
.ends
Vdd vdd 0 {vdd}
Vsc vcm 0 dc {vsc}
Vdp gp vcm dc 0 ac  0.5
Vdn gn vcm dc 0 ac -0.5
Rsp gp vinp 100
Rsn gn vinn 100
Xdut vinp vinn voutp voutn vdd 0 bomu WD={wd} NF={nf} LRD={lrd} RREF={rref}
CLp voutp 0 5p
CLn voutn 0 5p
.control
ac dec 100 1k 10G
let vod = v(voutp)-v(voutn)
let vod_db = db(vod)
meas ac a0_db find vod_db at=1k
let targ = a0_db - 3
meas ac f3db when vod_db=targ fall=1
op
let itot = -i(vdd)
print a0_db
print f3db
print v(xdut.vtail)
print v(voutp)
print itot
.endc
.end
"""


def run_search(corner, temp, vdd, wd, lrd, rref):
    out = ngspice(DECK_SEARCH.format(corner=corner, temp=temp, vdd=vdd, wd=wd,
                                     nf=nf_of(wd), lrd=lrd, rref=rref, vsc=VSC))
    itot = val(out, "itot")
    return dict(a0=val(out, "a0_db"), f3=val(out, "f3db"),
                vtail=val(out, "v(xdut.vtail)"), vout=val(out, "v(voutp)"),
                itail=itot / 1.125, itot=itot)


def _search_stage1_rd():
    cn, t, v = SEARCH_BW_CORNER
    print(f"STAGE 1  BW -> R_D   (worst-BW corner {cn}/{t}C/{v}V, "
          f"aim f3dB >= {BW_AIM/1e6:.0f} MHz)")
    print(f"  {'LRD':>4s} {'R_D~':>5s} | {'f3[MHz]':>8s} {'A0[dB]':>7s}")
    best = None
    for lrd in LRD_LIST:
        r = run_search(cn, t, v, STAGE1_WD, lrd, RREF_LADDER[0])
        ok = r["f3"] >= BW_AIM
        if ok:
            best = lrd            # ascending lrd -> keep the largest that passes
        print(f"  {lrd:4.1f} {rd_nom(lrd):5.0f} | {r['f3']/1e6:8.1f} "
              f"{r['a0']:7.2f}  {'ok' if ok else '-'}")
    print(f"  -> chosen R_D: LRD={best} (R_D~{rd_nom(best):.0f} ohm)\n")
    return best


def _search_stage2_w(lrd):
    cn, t, v = SEARCH_GAIN_CORNER
    for rref in RREF_LADDER:
        print(f"STAGE 2  gain -> W   (worst-gain corner {cn}/{t}C/{v}V, "
              f"R_ref={rref}, aim A0 >= {GAIN_AIM:.1f} dB)")
        print(f"  {'W':>4s} | {'A0[dB]':>7s} {'f3[MHz]':>8s} "
              f"{'Itail':>6s} {'Vtail':>6s} {'Vout':>6s}")
        pick = None
        for wd in WD_LIST:
            r = run_search(cn, t, v, wd, lrd, rref)
            ok = r["a0"] >= GAIN_AIM
            if ok and pick is None:
                pick = wd         # smallest W that passes
            print(f"  {wd:4d} | {r['a0']:7.2f} {r['f3']/1e6:8.1f} "
                  f"{r['itail']*1e3:6.3f} {r['vtail']:6.3f} {r['vout']:6.3f}"
                  f"  {'ok' if ok else '-'}")
        if pick is not None:
            print(f"  -> chosen W={pick} um at R_ref={rref}\n")
            return pick, rref
        print(f"  W alone insufficient at R_ref={rref}; bumping current...\n")
    return WD_LIST[-1], RREF_LADDER[-1]   # fall back to the strongest tried


def _search_stage3_verify(wd, lrd, rref):
    print(f"STAGE 3  VERIFY full relaxed grid with "
          f"W={wd} um, R_D~{rd_nom(lrd):.0f} ohm (LRD={lrd}), R_ref={rref}")
    hdr = (f"{'corner':7s} {'T':>3s} {'VDD':>5s} | {'A0[dB]':>7s} "
           f"{'f3[MHz]':>8s} {'Vtail':>6s} {'Vout':>6s} {'Itail':>6s}  v")
    print(hdr)
    print("-" * len(hdr))
    fails, wa, wf, pmax = [], (1e9, None), (1e9, None), 0.0
    for cn in CORNERS:
        for t in TEMPS:
            for v in VDDS:
                r = run_search(cn, t, v, wd, lrd, rref)
                ok = (r["a0"] >= A0_MIN) and (r["f3"] >= F3_MIN)
                tag = f"{cn}/{t}C/{v}V"
                wa = min(wa, (r["a0"], tag))
                wf = min(wf, (r["f3"], tag))
                pmax = max(pmax, r["itot"] * v)
                if not ok:
                    fails.append((tag, r["a0"], r["f3"]))
                print(f"{cn:7s} {t:3d} {v:5.2f} | {r['a0']:7.2f} "
                      f"{r['f3']/1e6:8.1f} {r['vtail']:6.3f} {r['vout']:6.3f} "
                      f"{r['itail']*1e3:6.3f}  {'P' if ok else 'F'}")
    print("-" * len(hdr))
    n = len(CORNERS) * len(TEMPS) * len(VDDS)
    print(f"worst gain: {wa[0]:.2f} dB @ {wa[1]}   "
          f"worst f3dB: {wf[0]/1e6:.1f} MHz @ {wf[1]}")
    print(f"max power: {pmax*1e3:.2f} mW")
    if fails:
        print(f"\n{len(fails)}/{n} FAIL:")
        for tag, a0, f3 in fails:
            print(f"  {tag:20s} A0={a0:.2f} f3={f3/1e6:.1f}")
    else:
        print(f"\nALL {n} PASS.  Sizing: W={wd} um (nf~{nf_of(wd)}), "
              f"R_D~{rd_nom(lrd):.0f} ohm (res_high_po_5p73 L={lrd}), "
              f"R_ref={rref} ohm.")


def cmd_search(_args):
    print("BoMu sizing search: box 0-70 C, VDD +-5% (1.14/1.20/1.26)")
    print(f"specs: A0 >= {A0_MIN:.0f} dB, f3dB >= {F3_MIN/1e6:.0f} MHz\n")
    lrd = _search_stage1_rd()
    wd, rref = _search_stage2_w(lrd)
    _search_stage3_verify(wd, lrd, rref)


# sub 'vdd': simple mirror on a regulated 1.20 V supply (reuses run_search)
VDD_LRD = 2.2                     # res_high_po_5p73 length -> R_D ~ 194 ohm
VDD_RREF = 380                    # ideal Rref (from the relaxed-box search)
VNOM = 1.20
VDD_GAIN_CORNER = ("ss_ll", 70)   # worst gain (slow FET + low R + hot)
VDD_BW_CORNER = ("ss_hh", 70)     # worst BW  (high R)


def _vdd_bracket_w():
    print(f"(A1) bracket WD @ VDD={VNOM} (R_D~{rd_nom(VDD_LRD):.0f}, "
          f"Rref={VDD_RREF})")
    print(f"     gain corner {VDD_GAIN_CORNER}, BW corner {VDD_BW_CORNER}")
    print(f"  {'WD':>4s} {'nf':>3s} | {'A0@ssll':>8s} {'f3@sshh':>9s} "
          f"{'Itail':>6s} | verdict")
    ok_w = None
    for wd in (160, 200, 240, 280, 320):
        rg = run_search(VDD_GAIN_CORNER[0], VDD_GAIN_CORNER[1], VNOM, wd,
                        VDD_LRD, VDD_RREF)
        rb = run_search(VDD_BW_CORNER[0], VDD_BW_CORNER[1], VNOM, wd,
                        VDD_LRD, VDD_RREF)
        ok = (rg["a0"] >= A0_MIN) and (rb["f3"] >= F3_MIN)
        if ok and ok_w is None:
            ok_w = wd
        print(f"  {wd:4d} {nf_of(wd):3d} | {rg['a0']:8.2f} "
              f"{rb['f3']/1e6:9.1f} {rg['itail']*1e3:6.3f} | "
              f"{'ok' if ok else '-'}")
    print(f"  -> smallest WD passing both binding corners: {ok_w}\n")
    return ok_w


def _vdd_verify_grid(wd):
    print(f"(A2) VERIFY process x temp @ VDD={VNOM}  WD={wd} (nf{nf_of(wd)}), "
          f"R_D~{rd_nom(VDD_LRD):.0f}, Rref={VDD_RREF}")
    hdr = (f"{'corner':7s} {'T':>3s} | {'A0[dB]':>7s} {'f3[MHz]':>8s} "
           f"{'Vtail':>6s} {'Vout':>6s} {'Itail':>6s}  v")
    print(hdr)
    print("-" * len(hdr))
    fails, wa, wf, pmax = [], (1e9, None), (1e9, None), 0.0
    for cn in CORNERS:
        for t in TEMPS:
            r = run_search(cn, t, VNOM, wd, VDD_LRD, VDD_RREF)
            ok = (r["a0"] >= A0_MIN) and (r["f3"] >= F3_MIN)
            tag = f"{cn}/{t}C"
            wa = min(wa, (r["a0"], tag))
            wf = min(wf, (r["f3"], tag))
            pmax = max(pmax, r["itot"] * VNOM)
            if not ok:
                fails.append((tag, r["a0"], r["f3"]))
            print(f"{cn:7s} {t:3d} | {r['a0']:7.2f} {r['f3']/1e6:8.1f} "
                  f"{r['vtail']:6.3f} {r['vout']:6.3f} {r['itail']*1e3:6.3f}  "
                  f"{'P' if ok else 'F'}")
    print("-" * len(hdr))
    n = len(CORNERS) * len(TEMPS)
    print(f"worst gain {wa[0]:.2f} dB @ {wa[1]}   worst f3 {wf[0]/1e6:.1f} MHz "
          f"@ {wf[1]}   max power {pmax*1e3:.2f} mW")
    print(f"{n - len(fails)}/{n} PASS" + (f"  fails: {fails}" if fails else "")
          + "\n")


def _vdd_swing(wd):
    print(f"(B) VDD swing @ WD={wd}, R_D~{rd_nom(VDD_LRD):.0f}, Rref={VDD_RREF}")
    probes = [("tt", 27), VDD_GAIN_CORNER, VDD_BW_CORNER]
    vdds = [round(1.02 + 0.03 * i, 2) for i in range(13)]   # 1.02 .. 1.38
    for cn, t in probes:
        print(f"  corner {cn}/{t}C:")
        print(f"    {'VDD':>5s} | {'A0[dB]':>7s} {'f3[MHz]':>8s} "
              f"{'Vout':>6s} {'Itail':>6s}  gain/BW")
        lo = hi = None
        for v in vdds:
            r = run_search(cn, t, v, wd, VDD_LRD, VDD_RREF)
            gok = r["a0"] >= A0_MIN
            bok = r["f3"] >= F3_MIN
            if gok and bok:
                lo = v if lo is None else lo
                hi = v
            print(f"    {v:5.2f} | {r['a0']:7.2f} {r['f3']/1e6:8.1f} "
                  f"{r['vout']:6.3f} {r['itail']*1e3:6.3f}  "
                  f"{'G' if gok else '.'}{'B' if bok else '.'}")
        span = f"[{lo:.2f}, {hi:.2f}] V" if lo else "NONE in spec"
        print(f"    -> in-spec VDD window at this corner: {span}\n")


def cmd_vdd(_args):
    print("BoMu simple-mirror under REGULATED supply")
    print(f"specs: A0 >= {A0_MIN:.0f} dB, f3dB >= {F3_MIN/1e6:.0f} MHz\n")
    w = _vdd_bracket_w() or 320
    _vdd_verify_grid(w)
    _vdd_swing(w)


# sub 'itail': tail-current (Rref) sweep at the binding corners
N_MIRROR = 8          # I_tail = N * I_ref ; I_supply = I_tail*(1 + 1/N)
NETLIST_ITAIL = os.path.join(NETDIR, "bomu_itail.spice")
RREFS = [745, 620, 520, 440, 380, 330, 290, 260]   # decreasing -> more current
BOUND = [
    ("tt",    27, 1.20, "nominal"),
    ("ss_ll", 85, 1.14, "worst gain"),
    ("ss_hh", 85, 1.14, "worst BW"),
    ("ff",    85, 1.26, "headroom"),
]


def _make_itail_netlist():
    """Copy the schematic netlist but make R_ref an ideal, instance-settable
    parameter (Rref nbias->VDD), keeping the mirror transistors real."""
    with open(NETLIST) as fh:
        txt = fh.read()
    txt = re.sub(r"^\.subckt bomu (.+)$",
                 r".subckt bomu \1 RREF=745", txt, flags=re.M)
    txt = re.sub(r"^XRref\s+nbias\s+VDD\s+VSS\s+.*$",
                 "Rref nbias VDD {RREF}", txt, flags=re.M)
    with open(NETLIST_ITAIL, "w") as fh:
        fh.write(txt)


DECK_ITAIL = """* BoMu I_tail sweep: {corner}, T={temp}C, VDD={vdd}, RREF={rref}
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice {corner}
.include {netlist}
.temp {temp}
.param VDD={vdd}
.param VSC={vsc}
Vdd vdd 0 {{VDD}}
Vsc vcm 0 dc {{VSC}}
Vdp gp vcm dc 0 ac  0.5
Vdn gn vcm dc 0 ac -0.5
Rsp gp vinp 100
Rsn gn vinn 100
Xdut vinp vinn voutp voutn vdd 0 bomu RREF={rref}
CLp voutp 0 5p
CLn voutn 0 5p
.control
ac dec 100 1k 10G
let vod = v(voutp)-v(voutn)
let vod_db = db(vod)
meas ac a0_db find vod_db at=1k
let targ = a0_db - 3
meas ac f3db when vod_db=targ fall=1
op
let itot = -i(vdd)
print a0_db
print f3db
print v(xdut.vtail)
print v(voutp)
print itot
.endc
.end
"""


def run_itail(corner, temp, vdd, rref):
    out = ngspice(DECK_ITAIL.format(corner=corner, temp=temp, vdd=vdd,
                                    rref=rref, vsc=VSC, netlist=NETLIST_ITAIL))
    itot = val(out, "itot")
    itail = itot / (1 + 1.0 / N_MIRROR)   # strip the reference leg
    return dict(a0=val(out, "a0_db"), f3=val(out, "f3db"),
                vtail=val(out, "v(xdut.vtail)"),
                vout=val(out, "v(voutp)"), itail=itail)


def cmd_itail(_args):
    netlist_schematic()
    _make_itail_netlist()
    print(f"specs: A_v0 >= {A0_MIN:.1f} dB  and  f3dB >= {F3_MIN/1e6:.0f} MHz"
          f"   (mirror N={N_MIRROR}; I_tail = I_supply/(1+1/N))\n")
    passing = {}
    for corner, temp, vdd, why in BOUND:
        tag = f"{corner}/{temp}C/{vdd}V"
        print(f"=== {tag:20s} [{why}] ===")
        print(f"{'RREF':>5s} {'Itail[mA]':>9s} | {'A0[dB]':>7s} "
              f"{'f3[MHz]':>8s} {'Vtail':>6s} {'Vout':>6s}  verdict")
        first_ok = None
        for rref in RREFS:
            r = run_itail(corner, temp, vdd, rref)
            ok = (r["a0"] >= A0_MIN) and (r["f3"] >= F3_MIN)
            if ok and first_ok is None:
                first_ok = (rref, r["itail"])
            v = "PASS" if ok else ("BW" if r["a0"] >= A0_MIN else
                                   ("gain" if r["f3"] >= F3_MIN else "both"))
            print(f"{rref:5d} {r['itail']*1e3:9.3f} | {r['a0']:7.2f} "
                  f"{r['f3']/1e6:8.1f} {r['vtail']:6.3f} {r['vout']:6.3f}  {v}")
        passing[tag] = first_ok
        print()
    print("first R_ref (=> I_tail) that passes both specs, per corner:")
    for tag, fo in passing.items():
        if fo:
            print(f"  {tag:20s} RREF<={fo[0]}  ->  I_tail={fo[1]*1e3:.2f} mA")
        else:
            print(f"  {tag:20s} NO R_ref in sweep passes "
                  f"(binding constraint, likely BW)")


# sub 'mc': input-referred offset Monte Carlo (injected mismatch)
#
# sky130 open ngspice carries mismatch *slopes* but never applies them (no
# agauss/mc_mm_switch term in the models), and the device subckt ignores delvto,
# so there is no native statistical MC. We inject it: a gate-referred Vth offset
# per device (Pelgrom, so that term refers straight to the input) and a load-R
# mismatch (simulated on ideal, alterable loads). beta/W mismatch is a smaller
# second-order term left out of the fast loop. AVT and sigma_R are estimates --
# drop in measured values before trusting the absolute Vos. The whole sweep runs
# in ONE ngspice call (DC-op loop) so the sky130 lib loads once, not per draw.
MC_RUNS = 200
MC_AVT = 4.0            # mV*um, sky130 nfet Vth Pelgrom coefficient (ASSUMPTION)
MC_SIGMA_R = 0.005      # per-resistor fractional load-R mismatch (estimate)
MC_AREA = 320 * 0.15    # pair device gate area um^2 (W_total * L)
MC_RD_L = 2.21          # nominal res_high_po_5p73 length
MC_RD_SLOPE = 56.42     # dR/dL ohm/um for res_high_po_5p73 (see rd_nom)

DECK_MC = """* BoMu offset MC (single ngspice call, DC-op loop): tt, 27C, 1.20V
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice tt
.temp 27
.param VSC={vsc}
Vdd vdd 0 1.20
Vcm vcm 0 dc {vsc}
Vdp g1 vcm dc 0 ac 0.5
Vdn g2 vcm dc 0 ac -0.5
Vos1 g1 gm1 dc 0
Vos2 g2 gm2 dc 0
XM1 voutn gm1 vtail 0 sky130_fd_pr__nfet_01v8_lvt L=0.15 W=320 nf=32
XM2 voutp gm2 vtail 0 sky130_fd_pr__nfet_01v8_lvt L=0.15 W=320 nf=32
RD1 voutn vdd {rnom}
RD2 voutp vdd {rnom}
XRref nbias vdd 0 sky130_fd_pr__res_high_po_2p85 L=1.74 mult=1
XM4 nbias nbias 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=10 nf=1
XM3 vtail nbias 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=80 nf=8
CLp voutp 0 5p
CLn voutn 0 5p
.control
ac dec 10 1k 10G
let gdb = db(v(voutp)-v(voutn))
meas ac a0_db find gdb at=1k
{loop}
.endc
.end
"""


def cmd_mc(args):
    sig_vth = (args.avt * 1e-3) / math.sqrt(MC_AREA)   # V, per device
    r_nom = rd_nom(MC_RD_L)
    random.seed(1234)                                  # reproducible
    # pre-draw mismatch in Python (ngspice has no gauss); one alter/op per draw
    loop = []
    for _ in range(args.runs):
        d1, d2 = random.gauss(0, sig_vth), random.gauss(0, sig_vth)
        rd1 = r_nom * (1 + random.gauss(0, MC_SIGMA_R))
        rd2 = r_nom * (1 + random.gauss(0, MC_SIGMA_R))
        loop += [f"alter Vos1 = {d1:.6e}", f"alter Vos2 = {d2:.6e}",
                 f"alter RD1 = {rd1:.4f}", f"alter RD2 = {rd2:.4f}",
                 "op", "let x = v(voutp)-v(voutn)", "print x"]
    out = ngspice(DECK_MC.format(vsc=VSC, rnom=r_nom, loop="\n".join(loop)))
    a0_db = val(out, "a0_db")
    gain = 10 ** (a0_db / 20.0)
    vod = [float(m) for m in re.findall(r"^x\s*=\s*([-+0-9.eE]+)", out, re.M)]
    vos = [v / gain for v in vod if v == v]            # drop NaN
    print("input-referred offset Monte Carlo (INJECTED mismatch; sky130 open "
          "ngspice has no native statistical MC)")
    print(f"draws={args.runs}  AVT={args.avt} mV.um -> sigma_Vth="
          f"{sig_vth*1e3:.2f} mV/device (gate area {MC_AREA:.1f} um^2); "
          f"R_D mismatch sigma={MC_SIGMA_R*100:.2f}%  (ASSUMPTIONS)")
    n = len(vos)
    if n == 0:
        print("no valid draws -- check the deck")
        return
    mean = sum(vos) / n
    sd = (sum((v - mean) ** 2 for v in vos) / n) ** 0.5
    worst = max(vos, key=abs)
    print(f"gain A0={a0_db:.2f} dB;  {n} valid draws")
    print(f"Vos : mean {mean*1e3:+.3f} mV   sigma {sd*1e3:.3f} mV   "
          f"3sigma {3*sd*1e3:.3f} mV   worst |{abs(worst)*1e3:.3f}| mV")


# sub 'acq': CMRR, PSRR and input-referred noise at the nominal point
#
# A perfectly matched differential output rejects common-mode and supply coupling
# to first order (they appear as common mode and cancel), so nominal CMRR/PSRR of
# the differential path are matching-limited, not tail-limited. We therefore inject
# one representative 1-sigma mismatch (same Pelgrom model as 'mc': dVth on M1 and
# dR_D on RD1) to get finite, physical differential CMRR/PSRR; the common-mode
# gains A_cc / A_sc are finite regardless and are reported too. Noise is the
# input-referred integrated value over 10 Hz-1 GHz.
DECK_ACQ = """* BoMu CMRR/PSRR/noise at tt, 27C, 1.20V (with 1-sigma mismatch)
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice tt
.temp 27
.param VSC={vsc}
Vdd vdd 0 dc 1.20 ac 0
Vcm vcm 0 dc {vsc} ac 0
Vdp g1 vcm dc 0 ac 0
Vdn g2 vcm dc 0 ac 0
Vos1 g1 gm1 dc {d1}
Vos2 g2 gm2 dc 0
XM1 voutn gm1 vtail 0 sky130_fd_pr__nfet_01v8_lvt L=0.15 W=320 nf=32
XM2 voutp gm2 vtail 0 sky130_fd_pr__nfet_01v8_lvt L=0.15 W=320 nf=32
XRD1 voutn vdd 0 sky130_fd_pr__res_high_po_5p73 L={lrd1} mult=1
XRD2 voutp vdd 0 sky130_fd_pr__res_high_po_5p73 L={lrd2} mult=1
XRref nbias vdd 0 sky130_fd_pr__res_high_po_2p85 L=1.74 mult=1
XM4 nbias nbias 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=10 nf=1
XM3 vtail nbias 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=80 nf=8
CLp voutp 0 5p
CLn voutn 0 5p
.control
* differential gain A_dd
alter vdp ac = 0.5
alter vdn ac = -0.5
ac dec 10 1k 10G
let add_v = db(v(voutp)-v(voutn))
meas ac add_db find add_v at=1k
* common-mode in -> differential out (CMRR) and -> common out (A_cc)
alter vdp ac = 0
alter vdn ac = 0
alter vcm ac = 1
ac dec 10 1k 10G
let acd_v = db(v(voutp)-v(voutn))
let acc_v = db(0.5*(v(voutp)+v(voutn)))
meas ac acd_db find acd_v at=1k
meas ac acc_db find acc_v at=1k
* supply in -> differential out (PSRR) and -> common out (A_sc)
alter vcm ac = 0
alter vdd ac = 1
ac dec 10 1k 10G
let apd_v = db(v(voutp)-v(voutn))
let apc_v = db(0.5*(v(voutp)+v(voutn)))
meas ac apd_db find apd_v at=1k
meas ac apc_db find apc_v at=1k
* input-referred noise: single-ended reference, differential output
alter vdd ac = 0
alter vdp ac = 1
noise v(voutp,voutn) vdp dec 10 10 1G
print inoise_total onoise_total
.endc
.end
"""


def cmd_acq(args):
    sig_vth = (MC_AVT * 1e-3) / math.sqrt(MC_AREA)
    r_nom = rd_nom(MC_RD_L)
    lrd1 = MC_RD_L + MC_SIGMA_R * r_nom / MC_RD_SLOPE
    out = ngspice(DECK_ACQ.format(vsc=VSC, d1=sig_vth, lrd1=lrd1, lrd2=MC_RD_L))
    add = val(out, "add_db")
    acd, acc = val(out, "acd_db"), val(out, "acc_db")
    apd, apc = val(out, "apd_db"), val(out, "apc_db")
    inoise = val(out, "inoise_total")
    print("small-signal quality at tt / 1.20 V / 27 C "
          f"(1-sigma mismatch: dVth={sig_vth*1e3:.2f} mV, dR_D={MC_SIGMA_R*100:.1f}%)")
    print(f"  A_dd  differential gain         : {add:7.2f} dB")
    print(f"  CMRR  = A_dd - A_cd (diff)       : {add-acd:7.2f} dB   "
          f"(A_cd={acd:.2f} dB; common-mode gain A_cc={acc:.2f} dB)")
    print(f"  PSRR  = A_dd - A_sd (diff)       : {add-apd:7.2f} dB   "
          f"(A_sd={apd:.2f} dB; supply->CM gain A_sc={apc:.2f} dB)")
    print(f"  input-referred noise (10Hz-1GHz): {inoise*1e6:7.2f} uV,rms")


# dispatch
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("sch", help="PVT sweep off the schematic netlist [default]")
    p_pex = sub.add_parser("pex", help="PVT sweep off an extracted netlist")
    p_pex.add_argument("variant", nargs="?", default="rcx", choices=["pex", "rcx"])
    sub.add_parser("search", help="staged R_D/W/I_tail sizing search")
    sub.add_parser("vdd", help="regulated-supply width bracket + VDD window")
    sub.add_parser("itail", help="tail-current sweep at the binding corners")
    p_mc = sub.add_parser("mc", help="input-referred offset Monte Carlo (injected)")
    p_mc.add_argument("--runs", type=int, default=MC_RUNS)
    p_mc.add_argument("--avt", type=float, default=MC_AVT,
                      help="Vth Pelgrom coefficient [mV.um]")
    sub.add_parser("acq", help="CMRR, PSRR and input-referred noise")
    args = ap.parse_args()
    {
        None: cmd_sch, "sch": cmd_sch, "pex": cmd_pex,
        "search": cmd_search, "vdd": cmd_vdd, "itail": cmd_itail, "mc": cmd_mc,
        "acq": cmd_acq,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
