v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
N 470 1240 490 1240 {lab=#net1}
N 490 1240 490 1260 {lab=#net1}
N 490 1260 510 1260 {lab=#net1}
N 470 1300 490 1300 {lab=#net2}
N 490 1280 490 1300 {lab=#net2}
N 490 1280 510 1280 {lab=#net2}
N 390 1300 410 1300 {lab=#net3}
N 390 1240 410 1240 {lab=#net4}
N 280 1300 280 1320 {lab=#net5}
N 280 1300 330 1300 {lab=#net5}
N 280 1240 330 1240 {lab=#net5}
N 280 1240 280 1300 {lab=#net5}
N 640 1280 700 1280 {lab=voutn}
N 700 1280 720 1280 {lab=voutn}
N 640 1260 700 1260 {lab=voutp}
N 700 1260 720 1260 {lab=voutp}
C {/foss/designs/BoMu-tt-sky130a/ip/bomu.sym} 530 1270 0 0 {name="x1"}
C {vsource.sym} 640 1370 0 0 {name=V1 value=1.2 savecurrent=false}
C {gnd.sym} 640 1400 0 0 {name=l1 lab=0}
C {vdd.sym} 640 1340 0 0 {name=l2 lab=VDD}
C {vdd.sym} 550 1200 0 0 {name=l3 lab=VDD}
C {gnd.sym} 550 1340 0 0 {name=l4 lab=0}
C {res.sym} 440 1240 3 0 {name=R1
value=100
footprint=1206
device=resistor
m=1}
C {res.sym} 440 1300 3 0 {name=R2
value=100
footprint=1206
device=resistor
m=1}
C {vsource.sym} 360 1240 1 0 {name=Vdp value="dc 0 ac 0.5 sin(0 \\\{Va\\\} \\\{F\\\})" savecurrent=false}
C {vsource.sym} 360 1300 1 0 {name=Vdn value="dc 0 ac -0.5 sin(0 \\\{-Va\\\} \\\{F\\\})" savecurrent=false}
C {vsource.sym} 280 1350 0 0 {name=Vcm value=\{VSC\} savecurrent=false}
C {gnd.sym} 280 1380 0 0 {name=l5 lab=0}
C {code_shown.sym} 140 1460 0 0 {name=s1 
only_toplevel=false 
value="
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice tt
.param VSC=1.052
.param Va=23.7m
.param F=1meg
.control
tran 0.5n 3u
let vod = v(voutp)-v(voutn)
meas tran vodmax MAX vod from=1u to=3u
meas tran vodmin MIN vod from=1u to=3u 
let vodpp = vodmax-vodmin
print vodpp
* linearity: harmonic distortion of differential output
fourier 1meg vod
* clipping/compliance sanity: single-ended nodes vs rails
meas tran vopmax MAX v(voutp) from=1u to=3u
meas tran vopmin MIN v(voutp) from=1u to=3u
print vopmax vopmin
* total simulated supply power (averaged over the settled window)
let isup = abs(i(v1))
meas tran iavg AVG isup from=1u to=3u
let pavg_mw = 1.2*iavg*1e3
print iavg pavg_mw
* small-signal differential gain + bandwidth
ac dec 100 1k 10G
let avdb = vdb(voutp,voutn)
meas ac av0_db FIND avdb AT=1k
let gmarg = avdb-(av0_db-3)
meas ac f3db WHEN gmarg=0 FALL=1
print av0_db f3db
.endc"
}
C {lab_pin.sym} 720 1260 0 1 {name=p1 sig_type=std_logic lab=voutp}
C {lab_pin.sym} 720 1280 0 1 {name=p2 sig_type=std_logic lab=voutn}
C {capa.sym} 700 1230 2 0 {name=C1
m=1
value=5p
footprint=1206
device="ceramic capacitor"}
C {capa.sym} 700 1310 0 1 {name=C2
m=1
value=5p
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 700 1340 0 0 {name=l6 lab=0}
C {gnd.sym} 700 1200 2 0 {name=l7 lab=0}
