v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
N 360 -620 560 -620 {lab=VDD}
N 460 -640 460 -620 {lab=VDD}
N 360 -620 360 -550 {lab=VDD}
N 560 -620 560 -550 {lab=VDD}
N 360 -490 360 -370 {lab=voutn}
N 560 -490 560 -370 {lab=voutp}
N 360 -430 420 -430 {lab=voutn}
N 560 -430 620 -430 {lab=voutp}
N 360 -310 360 -250 {lab=vtail}
N 560 -310 560 -250 {lab=vtail}
N 360 -250 560 -250 {lab=vtail}
N 300 -340 320 -340 {lab=vinp}
N 500 -340 520 -340 {lab=vinn}
N 360 -340 400 -340 {lab=VSS}
N 560 -340 600 -340 {lab=VSS}
N 325 -520 340 -520 {lab=VSS}
N 525 -520 540 -520 {lab=VSS}
N 480 -250 480 -180 {lab=vtail}
N 480 -150 520 -150 {lab=VSS}
N 165 -240 180 -240 {lab=VSS}
N 200 -290 200 -270 {lab=VDD}
N 200 -210 200 -190 {lab=nbias}
N 270 -150 280 -150 {lab=nbias}
N 270 -190 270 -150 {lab=nbias}
N 200 -190 430 -190 {lab=nbias}
N 320 -190 320 -180 {lab=nbias}
N 430 -190 430 -150 {lab=nbias}
N 430 -150 440 -150 {lab=nbias}
N 320 -120 320 -100 {lab=VSS}
N 320 -100 480 -100 {lab=VSS}
N 480 -120 480 -100 {lab=VSS}
N 520 -150 520 -100 {lab=VSS}
N 480 -100 520 -100 {lab=VSS}
N 320 -150 370 -150 {lab=VSS}
N 370 -150 370 -100 {lab=VSS}
N 180 -565 180 -550 {lab=VSS}
N 180 -490 180 -475 {lab=VSS}
N 145 -520 160 -520 {lab=VSS}
N 760 -565 760 -550 {lab=VSS}
N 760 -490 760 -475 {lab=VSS}
N 725 -520 740 -520 {lab=VSS}
N 920 -330 920 -270 {lab=VSS}
N 880 -300 920 -300 {lab=VSS}
C {sky130_fd_pr/res_high_po_5p73.sym} 360 -520 0 0 {name=RD1
L=3.17
model=res_high_po_5p73
spiceprefix=X
mult=1}
C {sky130_fd_pr/res_high_po_5p73.sym} 560 -520 0 0 {name=RD2
L=3.17
model=res_high_po_5p73
spiceprefix=X
mult=1}
C {sky130_fd_pr/nfet_01v8_lvt.sym} 340 -340 0 0 {name=M1 model=nfet_01v8_lvt W=80 L=0.15 nf=8 mult=1 ad=0 as=0 pd=0 ps=0 nrd=0 nrs=0 sa=0 sb=0 sd=0 spiceprefix=X}
C {sky130_fd_pr/nfet_01v8_lvt.sym} 540 -340 0 0 {name=M2 model=nfet_01v8_lvt W=80 L=0.15 nf=8 mult=1 ad=0 as=0 pd=0 ps=0 nrd=0 nrs=0 sa=0 sb=0 sd=0 spiceprefix=X}
C {devices/ipin.sym} 300 -340 0 0 {name=P_vinp lab=vinp}
C {devices/ipin.sym} 500 -340 0 0 {name=P_vinn lab=vinn}
C {devices/opin.sym} 420 -430 0 0 {name=P_voutn lab=voutn}
C {devices/opin.sym} 620 -430 0 0 {name=P_voutp lab=voutp}
C {devices/iopin.sym} 460 -640 3 0 {name=P_vdd lab=VDD}
C {devices/iopin.sym} 400 -100 1 0 {name=P_vss lab=VSS}
C {devices/lab_pin.sym} 400 -340 0 1 {name=l_m1b lab=VSS}
C {devices/lab_pin.sym} 600 -340 0 1 {name=l_m2b lab=VSS}
C {devices/lab_pin.sym} 325 -520 0 0 {name=l_rw1 lab=VSS}
C {devices/lab_pin.sym} 525 -520 0 0 {name=l_rw2 lab=VSS}
C {devices/lab_pin.sym} 360 -450 0 0 {name=l_von lab=voutn}
C {devices/lab_pin.sym} 560 -450 0 1 {name=l_vop lab=voutp}
C {sky130_fd_pr/res_high_po_2p85.sym} 200 -240 0 0 {name=Rref
L=5.41
model=res_high_po_2p85
spiceprefix=X
mult=1}
C {sky130_fd_pr/nfet_01v8.sym} 460 -150 0 0 {name=M3 model=nfet_01v8 W=80 L=0.5 nf=8 mult=1 ad=0 as=0 pd=0 ps=0 nrd=0 nrs=0 sa=0 sb=0 sd=0 spiceprefix=X}
C {sky130_fd_pr/nfet_01v8.sym} 300 -150 0 0 {name=M4 model=nfet_01v8 W=10 L=0.5 nf=1 mult=1 ad=0 as=0 pd=0 ps=0 nrd=0 nrs=0 sa=0 sb=0 sd=0 spiceprefix=X}
C {devices/lab_pin.sym} 200 -190 0 0 {name=l_nb lab=nbias}
C {devices/lab_pin.sym} 480 -215 0 0 {name=l_tl lab=vtail}
C {devices/lab_pin.sym} 165 -240 0 0 {name=l_rrw lab=VSS}
C {devices/lab_pin.sym} 200 -290 0 0 {name=l_vddr lab=VDD}
C {sky130_fd_pr/res_high_po_5p73.sym} 180 -520 0 0 {name=Rdum1
L=3.17
model=res_high_po_5p73
spiceprefix=X
mult=1}
C {sky130_fd_pr/res_high_po_5p73.sym} 760 -520 0 0 {name=Rdum2
L=3.17
model=res_high_po_5p73
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 180 -565 0 0 {name=l_d1t lab=VSS}
C {devices/lab_pin.sym} 180 -475 0 0 {name=l_d1b lab=VSS}
C {devices/lab_pin.sym} 145 -520 0 0 {name=l_d1w lab=VSS}
C {devices/lab_pin.sym} 760 -565 0 0 {name=l_d2t lab=VSS}
C {devices/lab_pin.sym} 760 -475 0 0 {name=l_d2b lab=VSS}
C {devices/lab_pin.sym} 725 -520 0 0 {name=l_d2w lab=VSS}
C {sky130_fd_pr/nfet_01v8_lvt.sym} 900 -300 0 0 {name=Mdum model=nfet_01v8_lvt W=10 L=0.15 nf=1 mult=4 ad=0 as=0 pd=0 ps=0 nrd=0 nrs=0 sa=0 sb=0 sd=0 spiceprefix=X}
C {devices/lab_pin.sym} 880 -300 0 0 {name=l_dmg lab=VSS}
C {devices/lab_pin.sym} 920 -330 0 0 {name=l_dmd lab=VSS}
