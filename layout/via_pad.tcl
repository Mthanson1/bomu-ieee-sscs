# ============================================================================
# via_pad.tcl -- centered via/pad stack helpers for magic net routing
#
# Usage:
#   source via_pad.tcl          ;# once per Magic session
#   <position the cursor box where you want the pad CENTER>
#   sdpad                       ;# S/D tap:   m1+m2 pad + via1        (no li)
#   platepad                    ;# plate tap: m1+m2+m3 pad + via1 + via2 (into m3 net plate)
#   ringpad                     ;# ring land: li+m1+m2 pad + via1 + mcon
#
# The stack is built concentric on the current box CENTER, so a rough box or a
# single-point box both work. Sizes below match the DRC for SKY130A;
# tweak the config vars if your rules differ.
# ============================================================================

# --== config (microns) ==--
set ::vp(via)     0.26     ;# via cut (via1 / mcon)
set ::vp(encl_m)  0.03     ;# m1/m2 enclosure of via   -> m pad  = via+2*encl_m  = 0.32
set ::vp(encl_li) 0.06     ;# li/m1 overlap            -> li pad = via+2*encl_li = 0.38
set ::vp(iu2um)   0.005    ;# internal units -> microns (magscale 1 2, 200 iu/um)
# --== platepad-specific (via2 into an m3 net plate) ==--
set ::vp(via2)    0.28     ;# via2 cut  (via2 min width 0.28)
set ::vp(pm2)     0.40     ;# m2 pad    (via2 0.28 + 2*0.06 -> 0.06 overlap >= 0.045)
set ::vp(pm3)     0.50     ;# m3 pad    (0.50^2 = 0.25 >= 0.24 um^2 min area)

# --== box center in microns ==--
proc vp_center {} {
    set b [box values]                       ;# {llx lly urx ury ...} in iu
    set cx [expr {([lindex $b 0]+[lindex $b 2])*0.5*$::vp(iu2um)}]
    set cy [expr {([lindex $b 1]+[lindex $b 3])*0.5*$::vp(iu2um)}]
    return [list $cx $cy]
}

# --== paint a square of side $side (um) centered at (cx,cy), on $layers ==--
proc vp_square {cx cy side layers} {
    set h [expr {$side*0.5}]
    box position [expr {$cx-$h}]um [expr {$cy-$h}]um
    box size     ${side}um ${side}um
    foreach L $layers { paint $L }
}

# --== source/drain tap: m1+m2 pad, via1 ==--
proc sdpad {} {
    lassign [vp_center] cx cy
    set pm [expr {$::vp(via)+2*$::vp(encl_m)}]      ;# 0.32
    tech unlock *
    vp_square $cx $cy $pm        {m1 m2}
    vp_square $cx $cy $::vp(via) {via1}
    tech revert
    puts "sdpad  @ ([format %.3f $cx], [format %.3f $cy]) um  via=$::vp(via) pad=$pm"
}

# --== plate tap: m1+m2+m3 pad, stacked via1 + via2 (lands in a metal3 net plate) ==--
#      NB: keep OUT from under a MIM cap -- via2 needs >=0.1um to capm.  If the
#      plate is a MIM bottom plate, tap it in the margin not covered by mimcap
#      and bus over to the sources on m2 (sdpad taps + m2 bus).
proc platepad {} {
    lassign [vp_center] cx cy
    set pm1 [expr {$::vp(via)+2*$::vp(encl_m)}]     ;# 0.32  m1 tap (via1 encl 0.03)
    tech unlock *
    vp_square $cx $cy $pm1        {m1}
    vp_square $cx $cy $::vp(pm2)  {m2}              ;# 0.40  covers via1 + via2
    vp_square $cx $cy $::vp(pm3)  {m3}              ;# 0.50  merges w/ plate; min-area safe
    vp_square $cx $cy $::vp(via)  {via1}            ;# 0.26
    vp_square $cx $cy $::vp(via2) {via2}            ;# 0.28
    tech revert
    puts "platepad @ ([format %.3f $cx], [format %.3f $cy]) um  via1=$::vp(via) via2=$::vp(via2) m2=$::vp(pm2) m3=$::vp(pm3)"
}

# --== m2<->m3 via: m2+m3 pad, via2 only (no li/m1/via1) ==--
proc m2m3pad {} {
    lassign [vp_center] cx cy
    tech unlock *
    vp_square $cx $cy $::vp(pm2)  {m2}              ;# 0.40  covers via2
    vp_square $cx $cy $::vp(pm3)  {m3}              ;# 0.50  min-area safe
    vp_square $cx $cy $::vp(via2) {via2}            ;# 0.28
    tech revert
    puts "m2m3pad @ ([format %.3f $cx], [format %.3f $cy]) um  via2=$::vp(via2) m2=$::vp(pm2) m3=$::vp(pm3)"
}

# --== ring landing: li+m1 (wide) + m2 pad, stacked via1 + mcon ==--
proc ringpad {} {
    lassign [vp_center] cx cy
    set pm  [expr {$::vp(via)+2*$::vp(encl_m)}]     ;# 0.32
    set pli [expr {$::vp(via)+2*$::vp(encl_li)}]    ;# 0.38
    tech unlock *
    vp_square $cx $cy $pli       {li m1}            ;# m1 fully overlaps li
    vp_square $cx $cy $pm        {m2}
    vp_square $cx $cy $::vp(via) {via1 mcon}
    tech revert
    puts "ringpad @ ([format %.3f $cx], [format %.3f $cy]) um  via=$::vp(via) li=$pli m=$pm"
}
