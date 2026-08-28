# Magic: full RC (R+C) parasitic extraction of the BoMu top cell.
# Run:  magic -dnull -noconsole -rcfile env/.magicrc verify/ext_rcx.tcl
# Produces: verify/bomu_rcx.spice  (parasitic caps + wire resistance)
#
# Difference vs ext_pex.tcl (cap-only): this also runs `extresist`, which
# builds the distributed wire-resistance network and splits nodes where R
# matters, then ext2spice folds it in with `extresist on`.
drc off
crashbackups stop
cd layout
load bomu -dereference
select top cell
# full parasitic extraction (caps + coupling)
extract do all
extract do capacitance
extract do coupling
extract unique
extract all
# resistance network on the TOP-CELL interconnect only. `extresist all`
# recurses into the PDK device cells (fets/poly-res) and segfaults magic on
# the resistor's internal net -- their internal R is in the device model
# anyway, so we only want wire R on the bomu routing.
extresist tolerance 10
extresist
# emit hierarchical spice: LVS-style ports, all caps, plus the R network
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist on
ext2spice -o ../verify/bomu_rcx.spice
puts "RCX extraction done -> verify/bomu_rcx.spice"
quit -noprompt
