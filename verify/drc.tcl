# Magic: DRC the BoMu GDS against the sky130A rule deck.
# Run:  magic -dnull -noconsole -rcfile env/.magicrc verify/drc.tcl
# Reads tapeout/bomu.gds fresh (as-shipped geometry) and reports DRC errors.
crashbackups stop
drc on
drc euclidean on
gds read tapeout/bomu.gds
load bomu -dereference
select top cell
drc check
drc catchup
puts "=== DRC error tiles per cell ==="
drc count
set n [drc list count total]
puts "TOTAL DRC ERROR COUNT: $n"
quit -noprompt
