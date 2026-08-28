# Magic: PARASITIC (RC) extraction of the BoMu top cell.
# Run:  magic -dnull -noconsole -rcfile env/.magicrc verify/ext_pex.tcl
# Produces: verify/bomu_pex.spice  (with parasitic caps, for post-layout sim)
#
# Unlike ext_lvs.tcl (which calls `ext2spice lvs` and strips all parasitics),
# this pass keeps parasitic capacitance.  cthresh 0 = include EVERY parasitic
# cap (coupling + substrate); rthresh 0 would add wire R but is left at the lvs
# default here -- cap-only PEX is the standard first pass and captures the
# dominant effect (node caps loading the high-impedance internal nodes).
drc off
crashbackups stop
cd layout
load bomu -dereference
select top cell
# Enable full parasitic extraction (caps + coupling). NOTE: ext_lvs.tcl does
# `extract no all` which DISABLES capacitance -- do the opposite here.
extract do all
extract do capacitance
extract do coupling
extract unique
extract all
# Start from the LVS-style subckt formatting (hierarchical, named ports)...
ext2spice lvs
# ...then re-enable parasitic capacitance (lvs sets cthresh to infinite).
ext2spice cthresh 0
ext2spice -o ../verify/bomu_pex.spice
puts "PEX extraction done -> verify/bomu_pex.spice"
quit -noprompt
