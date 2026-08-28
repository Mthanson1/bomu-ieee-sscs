# BoMu -- sky130A signoff bundle

Signoff date: 2026-08-25
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
sha256  5b022c43fe23cbf78cfae09917412b6e1e80e3fa6b9697b11edda556e265eccb  bomu.gds
```

## Reproduce (inside IIC-OSIC-TOOLS, PDK=sky130A)

```
verify/write_gds.sh   # layout/bomu.mag -> tapeout/bomu.gds
verify/drc.sh         # Magic + KLayout DRC on tapeout/bomu.gds
verify/run_lvs.sh     # netlist ip/bomu.sch, extract layout, netgen compare
```
