import json, math
p='src/params.json'
P=json.load(open(p))
L=[]
def E(name, comp, c, r, bone="torso", k=0.03, g="", op="add", mirror=False, axis=None, rot=None):
    d={"name":name,"comp":comp,"type":"ell","c":c,"r":r,"bone":bone,"k":k}
    if g: d["g"]=g
    if op!="add": d["op"]=op
    if mirror: d["mirror"]=True
    if axis: d["axis"]=axis
    if rot: d["rot"]=rot
    L.append(d)
def C(name, comp, a, b, ra, rb, bone="torso", k=0.03, g="", flat=None, mirror=False, op="add"):
    d={"name":name,"comp":comp,"type":"cone","a":a,"b":b,"ra":ra,"rb":rb,"bone":bone,"k":k}
    if g: d["g"]=g
    if flat: d["flat"]=flat
    if mirror: d["mirror"]=True
    if op!="add": d["op"]=op
    L.append(d)
W=lambda x,y,z: {"abs":[x,y,z]}   # punto absoluto (neutro), escalado con el esqueleto
# ---------------- TRONCO
E("ribcage","body",W(0,-0.150,0.525),[0.150,0.270,0.185],g="chest",k=0.05,rot=[-4,0,0])
E("thorax_dorsal","body",W(0,-0.190,0.655),[0.100,0.250,0.070],g="back",k=0.05)
E("withers","body",W(0,-0.345,0.690),[0.075,0.090,0.058],g="back",k=0.04)
E("loin","body",W(0,0.200,0.625),[0.112,0.200,0.088],g="loin",k=0.06)
E("abdomen","body",W(0,0.080,0.500),[0.132,0.240,0.150],g="belly",k=0.06)
E("belly_fold","body",W(0,0.200,0.430),[0.095,0.160,0.065],g="fold",k=0.05)
E("croup","body",W(0,0.450,0.600),[0.130,0.150,0.120],g="croup",k=0.05)
E("glute","body",W(0.075,0.470,0.640),[0.070,0.110,0.075],g="croup",k=0.04,mirror=True)
E("prosternum","body",W(0,-0.460,0.440),[0.090,0.080,0.100],g="chest",k=0.05)
E("neck_base","body",W(0,-0.450,0.580),[0.120,0.100,0.150],g="neck",k=0.05)
C("neck","body",W(0,-0.450,0.600),W(0,-0.625,0.635),0.120,0.090,bone="neck1",k=0.05,g="neck",flat=[0.85,1.0])
E("nape","body",W(0,-0.540,0.680),[0.070,0.120,0.050],bone="neck1",g="neck",k=0.04)
E("throat","body",W(0,-0.600,0.530),[0.070,0.090,0.060],bone="neck2",g="neck",k=0.04)
E("flank_tuck","body",W(0.165,0.190,0.400),[0.050,0.100,0.080],k=0.05,op="sub",mirror=True,g="tuck")
# ---------------- ESCÁPULA / BRAZO
E("scapula","body",{"at":["scap_top_L","shoulder_L",0.40],"off":[0.025,0,0]},[0.040,0.130,0.075],bone="scapula_L",axis=["scap_top_L","shoulder_L"],g="shoulder",k=0.04,mirror=True)
E("deltoid","body",{"lm":"shoulder_L","off":[0.015,-0.010,0.010]},[0.060,0.060,0.070],bone="scapula_L",g="shoulder",k=0.04,mirror=True)
E("triceps","body",{"at":["shoulder_L","elbow_L",0.5],"off":[0.0,0.060,0.010]},[0.060,0.120,0.075],bone="humerus_L",axis=["shoulder_L","olecranon_L"],g="arm",k=0.04,mirror=True)
E("biceps","body",{"at":["shoulder_L","elbow_L",0.5],"off":[0.0,-0.035,0.0]},[0.045,0.100,0.045],bone="humerus_L",axis=["shoulder_L","elbow_L"],g="arm",k=0.03,mirror=True)
# ---------------- MANO
C("forearm","body",{"lm":"elbow_L","off":[0,0.005,0]},{"lm":"carpus_L","off":[0,0,0.010]},0.058,0.037,bone="radius_L",k=0.03,g="forearm",flat=[0.82,1.0],mirror=True)
E("forearm_mass","body",{"at":["elbow_L","carpus_L",0.25],"off":[0.005,-0.010,0]},[0.050,0.080,0.060],bone="radius_L",axis=["elbow_L","carpus_L"],g="forearm",k=0.03,mirror=True)
E("olecranon","body",{"lm":"olecranon_L"},[0.035,0.040,0.035],bone="radius_L",g="forearm",k=0.025,mirror=True)
E("carpus","body",{"lm":"carpus_L"},[0.040,0.042,0.035],bone="radius_L",g="forearm",k=0.02,mirror=True)
E("carpal_pad","body",{"lm":"carpus_L","off":[0,0.035,-0.010]},[0.015,0.012,0.015],bone="radius_L",k=0.01,mirror=True)
C("metacarpus","body",{"lm":"carpus_L"},{"lm":"mcp_L","off":[0,0,0.008]},0.036,0.042,bone="metacarpus_L",k=0.02,g="paw_f",flat=[1.15,0.9],mirror=True)
E("dewclaw","body",{"at":["carpus_L","mcp_L",0.45],"off":[-0.033,-0.005,0]},[0.012,0.014,0.016],bone="metacarpus_L",k=0.008,mirror=True)
E("paw_f","body",{"at":["mcp_L","ftoe_L",0.5],"off":[0,0,0.012]},[0.056,0.052,0.028],bone="fdigits_L",g="paw_f",k=0.02,mirror=True)
for i,(dx,dy) in enumerate([(-0.032,-0.035),(-0.011,-0.048),(0.011,-0.048),(0.032,-0.035)]):
    E("ftoe%d"%(i+2),"body",{"at":["mcp_L","ftoe_L",0.5],"off":[dx,dy,0.004]},[0.019,0.022,0.019],bone="fdigits_L",g="paw_f",k=0.008,mirror=True)
E("fpad","body",{"at":["mcp_L","ftoe_L",0.5],"off":[0,0.014,0.0]},[0.030,0.022,0.014],bone="fdigits_L",k=0.01,mirror=True)
# ---------------- MUSLO / PIERNA / PIE
E("thigh","body",{"at":["hip_L","knee_L",0.45],"off":[0.010,0.020,0]},[0.080,0.160,0.110],bone="femur_L",axis=["hip_L","knee_L"],g="thigh",k=0.05,mirror=True)
E("quadriceps","body",{"at":["hip_L","knee_L",0.60],"off":[0.005,-0.050,0]},[0.060,0.120,0.065],bone="femur_L",axis=["hip_L","knee_L"],g="thigh",k=0.04,mirror=True)
E("hamstrings","body",{"at":["ischium_L","knee_L",0.5],"off":[0.030,0.070,-0.020]},[0.065,0.150,0.075],bone="femur_L",axis=["ischium_L","knee_L"],g="thigh",k=0.04,mirror=True)
E("knee","body",{"lm":"knee_L","off":[0,-0.015,0.005]},[0.050,0.050,0.055],bone="femur_L",g="shank",k=0.03,mirror=True)
E("gastrocnemius","body",{"at":["knee_L","hock_L",0.30],"off":[0,0.045,0]},[0.045,0.085,0.045],bone="tibia_L",axis=["knee_L","hock_L"],g="shank",k=0.03,mirror=True)
C("shin","body",{"lm":"knee_L"},{"lm":"hock_L"},0.048,0.032,bone="tibia_L",k=0.03,g="shank",flat=[0.85,1.0],mirror=True)
C("achilles","body",{"at":["knee_L","hock_L",0.55],"off":[0,0.050,0]},{"lm":"calcaneus_L","off":[0,-0.005,0.010]},0.022,0.018,bone="tibia_L",k=0.02,mirror=True)
E("hock","body",{"lm":"hock_L"},[0.034,0.036,0.034],bone="metatarsus_L",k=0.02,mirror=True)
E("calcaneus","body",{"lm":"calcaneus_L"},[0.024,0.025,0.026],bone="metatarsus_L",k=0.015,mirror=True)
C("metatarsus","body",{"lm":"hock_L"},{"lm":"mtp_L","off":[0,0,0.008]},0.033,0.038,bone="metatarsus_L",k=0.02,g="paw_h",flat=[1.1,0.9],mirror=True)
E("paw_h","body",{"at":["mtp_L","htoe_L",0.5],"off":[0,0,0.012]},[0.050,0.050,0.027],bone="hdigits_L",g="paw_h",k=0.02,mirror=True)
for i,(dx,dy) in enumerate([(-0.028,-0.033),(-0.010,-0.045),(0.010,-0.045),(0.028,-0.033)]):
    E("htoe%d"%(i+2),"body",{"at":["mtp_L","htoe_L",0.5],"off":[dx,dy,0.004]},[0.017,0.020,0.018],bone="hdigits_L",g="paw_h",k=0.008,mirror=True)
E("hpad","body",{"at":["mtp_L","htoe_L",0.5],"off":[0,0.012,0.0]},[0.027,0.020,0.013],bone="hdigits_L",k=0.01,mirror=True)
# ---------------- COLA
E("tail_root","body",{"tail":0,"off":[0,0.005,0.0]},[0.048,0.050,0.048],bone="torso",g="tail",k=0.04)
rads=[0.042,0.039,0.036,0.034,0.032,0.031,0.029]
for i in range(6):
    C("tail%d"%i,"body",{"tail":i},{"tail":i+1},rads[i],rads[i+1],bone="tail%d"%i,k=0.015,g="tail")
# ---------------- CABEZA (coords locales de cabeza: origen en los cóndilos, -Y hacia la nariz)
H=lambda x,y,z: {"hl":[x,y,z]}
E("cranium","head",H(0,-0.055,0.025),[0.082,0.095,0.075],bone="head",g="head",k=0.03)
E("temporal","head",H(0.048,-0.050,0.045),[0.045,0.070,0.048],bone="head",g="head",k=0.03,mirror=True)
E("occipital","head",H(0,0.010,0.030),[0.060,0.040,0.060],bone="head",g="head",k=0.03)
E("forehead","head",H(0,-0.125,0.055),[0.060,0.060,0.045],bone="head",g="head",k=0.03)
E("zygomatic","head",H(0.088,-0.115,0.0),[0.030,0.065,0.032],bone="head",g="head",k=0.025,mirror=True,rot=[0,0,-8])
E("masseter","head",H(0.072,-0.095,-0.045),[0.040,0.055,0.050],bone="head",g="head",k=0.03,mirror=True)
E("jowl","head",H(0.085,-0.070,-0.030),[0.035,0.050,0.050],bone="head",g="head",k=0.03,mirror=True)
E("brow","head",H(0.042,-0.165,0.072),[0.030,0.018,0.016],bone="head",k=0.015,mirror=True)
E("orbit_floor","head",H(0.050,-0.170,0.020),[0.028,0.020,0.015],bone="head",k=0.015,mirror=True)
E("muzzle","head",H(0,-0.225,-0.005),[0.056,0.065,0.048],bone="head",g="muzzle",k=0.035)
C("nasal_bridge","head",H(0,-0.150,0.055),H(0,-0.268,0.022),0.036,0.024,bone="head",k=0.025,g="muzzle")
E("whisker_pad","head",H(0.030,-0.252,-0.025),[0.032,0.030,0.028],bone="head",g="muzzle",k=0.012,mirror=True)
E("upper_lip","head",H(0.045,-0.205,-0.045),[0.032,0.050,0.022],bone="head",g="muzzle",k=0.015,mirror=True)
E("rhinarium","head",H(0,-0.282,0.012),[0.024,0.014,0.017],bone="head",k=0.01)
E("philtrum","head",H(0,-0.292,-0.022),[0.0045,0.030,0.022],bone="head",k=0.006,op="sub")
E("nostril","head",H(0.010,-0.297,0.008),[0.005,0.010,0.004],bone="head",k=0.003,op="sub",mirror=True)
gy=math.radians(22.0)
A=[math.sin(gy),-math.cos(gy),0.035]
E("eye_socket","head",{"hl":[0.042+A[0]*0.010,-0.165+A[1]*0.010,0.045+A[2]*0.010]},[0.022,0.020,0.0155],bone="head",k=0.006,op="sub",mirror=True,rot=[0,0,22])
# ---------------- MANDÍBULA
E("mandible","jaw",H(0,-0.175,-0.078),[0.050,0.080,0.026],bone="jaw",g="jaw",k=0.02)
E("ramus","jaw",H(0.055,-0.105,-0.070),[0.022,0.050,0.030],bone="jaw",g="jaw",k=0.02,mirror=True,rot=[0,0,15])
E("chin","jaw",H(0,-0.238,-0.078),[0.030,0.022,0.028],bone="jaw",g="jaw",k=0.015)
E("lower_lip","jaw",H(0.030,-0.200,-0.058),[0.025,0.050,0.012],bone="jaw",g="jaw",k=0.012,mirror=True)
# ---------------- OREJAS
E("ear_shell","ear_L",{"hl":[0.078,-0.055,0.078],"off":[0.012,0.0,0.020]},[0.032,0.010,0.034],bone="head",k=0.01,rot=[-10,35,30],mirror=True)
E("ear_cup","ear_L",{"hl":[0.078,-0.055,0.078],"off":[0.0178,-0.0061,0.0233]},[0.025,0.007,0.027],bone="head",k=0.004,op="sub",rot=[-10,35,30],mirror=True)
E("ear_root","ear_L",{"hl":[0.078,-0.055,0.078],"off":[0.004,0.0,0.002]},[0.026,0.016,0.022],bone="head",k=0.012,rot=[-10,35,30],mirror=True)
P["sculpt"]={
 "_doc":"Volumenes musculares de la escultura SDF (src/sdf.py). Cada primitiva va unida a un hueso; 'c'/'a'/'b' se dan con landmarks ('lm', 'at' = punto sobre un segmento) o en coords locales de cabeza ('hl'); 'off' en metros; 'k' = radio de mezcla suave; 'g' = grupo de escala que ajusta el optimizador; 'mirror' crea la copia derecha.",
 "groups":{},
 "eye":{"radius":0.0185,"gaze_yaw_deg":22.0,"gaze_pitch_deg":2.0,"inset":0.004},
 "res":{"body":0.008,"head":0.003},
 "prims":L}
json.dump(P,open(p,'w'),indent=1)
print(len(L),"prims")
