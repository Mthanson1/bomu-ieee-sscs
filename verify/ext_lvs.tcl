# Magic: device-only (LVS) extraction of the BoMu top cell.
# Run:  magic -dnull -noconsole -rcfile env/.magicrc verify/ext_lvs.tcl
# Produces: verify/bomu_lay.spice  (no parasitics, for netgen LVS)
drc off
crashbackups stop
# Work where the .mag cells live so subcells resolve.
cd layout
load bomu -dereference
select top cell
extract no all
extract do local
extract unique
extract all
# Device-only netlist: no parasitic R/C.
ext2spice lvs
ext2spice -o ../verify/bomu_lay.spice
puts "LVS extraction done -> verify/bomu_lay.spice"
quit -noprompt
