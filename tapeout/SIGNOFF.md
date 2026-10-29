# BoMu -- sky130A signoff bundle

Signoff date: 2026-10-28
Top cell: `bomu`
PDK: sky130A

## Artifacts (this directory)

| file | what |
|------|------|
| `bomu.gds`       | signed-off layout (Magic `gds write` from `layout/bomu.mag`) |
| `bomu_lvs.rpt`   | netgen LVS report -- layout vs `ip/bomu.sch` |
| `bomu_drc.rpt`   | DRC summary -- Magic geometric + KLayout `sky130A_mr.drc` sign-off |
| `bomu_drc.lyrdb` | KLayout DRC results database |

## Verdicts

- **LVS:** `Circuits match uniquely.`
- **DRC (Magic):** 0 errors.
- **DRC (KLayout sky130A_mr, feol+beol+offgrid+floating_met):** CLEAN: 0 violations.

## GDS checksum

```
sha256  ae7d3c812035b1ba8f9560c461c0b1ebbb2fc0ba43d2123ad1f54eaa9a64ffe5  bomu.gds
```

## Reproduce (inside IIC-OSIC-TOOLS, PDK=sky130A)

```
verify/write_gds.sh   # layout/bomu.mag -> tapeout/bomu.gds
verify/drc.sh         # Magic + KLayout DRC on tapeout/bomu.gds
verify/run_lvs.sh     # netlist ip/bomu.sch, extract layout, netgen compare
```
