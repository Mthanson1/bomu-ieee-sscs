#!/usr/bin/env bash
# LVS driver for the BoMu (sky130A) -- run inside IIC-OSIC-TOOLS.
#
# From the host:
#   docker exec iic-osic-tools_xvnc_uid_1000 bash -lc \
#     'cd /foss/designs/BoMu-tt-sky130a && verify/run_lvs.sh'
#
set -e
# Force sky130A: the IIC-OSIC-TOOLS container defaults PDK=ihp-sg13g2, so a
# ':=' default would NOT override it. This design is sky130A.
export PDK=sky130A
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
NETGEN_SETUP="$PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl"

echo "### 1. Netlist schematic (xschem -> verify/bomu_sch.spice)"
xschem --rcfile env/.xschemrc -q -s -n -x --tcl "set top_subckt 1" \
       -o verify ip/bomu.sch 2>&1 | grep -vi "INFO\]" || true
mv -f verify/bomu.spice verify/bomu_sch.spice
# xschem writes the top wrapper as '**.subckt' (a comment, so ngspice ignores
# it during simulation). netgen wants a real .subckt, so promote it for LVS.
sed -i 's/^\*\*\.subckt/.subckt/; s/^\*\*\.ends/.ends/' verify/bomu_sch.spice

echo "### 2. Extract layout (magic -> verify/bomu_lay.spice)"
magic -dnull -noconsole -rcfile env/.magicrc verify/ext_lvs.tcl 2>&1 \
      | grep -viE "INFO\]|read from|Extracting|Processing" || true

echo "### 3. Compare (netgen LVS)"
netgen -batch lvs \
  "verify/bomu_lay.spice bomu" \
  "verify/bomu_sch.spice bomu" \
  "$NETGEN_SETUP" \
  verify/lvs.report 2>&1 | grep -vi "INFO\]" || true

echo
echo "### LVS verdict:"
grep -E "Circuits match|do not match|uniquely|Netlists" verify/lvs.report | tail -5
echo "Full report -> verify/lvs.report"
