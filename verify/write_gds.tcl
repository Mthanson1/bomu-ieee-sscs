# Magic: write the BoMu top cell to GDS for tapeout.
# Run:  magic -dnull -noconsole -rcfile env/.magicrc verify/write_gds.tcl
# Produces: tapeout/bomu.gds
drc off
crashbackups stop
# Work where the .mag cells live so subcells resolve.
cd layout
load bomu -dereference
select top cell
# Flatten nothing: keep hierarchy, write the sky130 GDS layer map from the tech.
gds write ../tapeout/bomu.gds
puts "GDS written -> tapeout/bomu.gds"
quit -noprompt
