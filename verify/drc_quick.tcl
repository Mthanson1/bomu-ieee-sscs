drc euclidean on
crashbackups stop
cd /foss/designs/BoMu-tt-sky130a/layout
load bomu
select top cell
drc check
drc catchup
set c [drc list count total]
puts "DRC_TOTAL_VIOLATIONS = $c"
quit -noprompt
