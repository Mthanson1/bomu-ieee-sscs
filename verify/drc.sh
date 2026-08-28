#!/usr/bin/env bash
# DRC driver for the BoMu (sky130A) -- run inside IIC-OSIC-TOOLS.
# Runs both checkers on the tapeout GDS:
#   1. Magic  (verify/drc.tcl)           -> quick geometric DRC
#   2. KLayout sky130A_mr.drc sign-off   -> verify/bomu_drc.lyrdb
#
# From the host:
#   docker exec iic-osic-tools_xvnc_uid_1000 bash -lc \
#     'cd /foss/designs/BoMu-tt-sky130a && verify/drc.sh'
#
set -e
# Force sky130A: the container defaults PDK=ihp-sg13g2, which a ':=' default
# would NOT override. This design is sky130A.
export PDK=sky130A
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
GDS="tapeout/bomu.gds"
TOP="bomu"
RDB="$ROOT/verify/bomu_drc.lyrdb"

[ -s "$GDS" ] || { echo "ERROR: $GDS not found -- run verify/write_gds.sh first" >&2; exit 1; }

echo "### 1. Magic DRC (magic -> stdout)"
magic -dnull -noconsole -rcfile env/.magicrc verify/drc.tcl 2>&1 \
  | grep -iE "Total DRC errors|TOTAL DRC ERROR COUNT" || true

echo
echo "### 2. KLayout sign-off DRC (sky130A_mr.drc -> verify/bomu_drc.lyrdb)"
# Report path must be absolute: the deck resolves a relative path against the
# GDS directory (tapeout/), which would fail to write.
klayout -b -r "$PDK_ROOT/sky130A/libs.tech/klayout/drc/sky130A_mr.drc" \
  -rd input="$GDS" -rd top_cell="$TOP" -rd report="$RDB" \
  -rd feol=true -rd beol=true -rd offgrid=true -rd floating_met=true \
  2>&1 | grep -iE "^ERROR|Exception" | grep -viE "error_|_error" || true

echo
echo "### KLayout DRC verdict:"
if [ -s "$RDB" ]; then
  python3 - "$RDB" <<'PY'
import sys, xml.etree.ElementTree as ET
from collections import Counter
root = ET.parse(sys.argv[1]).getroot()
c = Counter(i.findtext("category").strip("'") for i in root.iter("item"))
total = sum(c.values())
if total == 0:
    print("CLEAN -- 0 violations")
else:
    print(f"{total} violation(s) across {len(c)} rule(s):")
    for rule, n in c.most_common():
        print(f"  {n:5d}  {rule}")
print("Report -> verify/bomu_drc.lyrdb")
PY
else
  echo "ERROR: KLayout report $RDB was not produced" >&2
  exit 1
fi
