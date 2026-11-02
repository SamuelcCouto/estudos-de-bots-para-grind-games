import json, math, collections
import numpy as np
from scipy.optimize import fsolve
R_, W_, G_ = 0.90289815, 6.33592869, -184.11666458
def predict(ang, wind, dx, dy):
    if ang > 90: ang = 180 - ang
    pa = math.atan(dy/dx)*180/math.pi
    xa = math.radians(ang-pa); ya = math.radians(90-ang+pa); pa = math.radians(pa)
    def cp(v0,f,t):
        tmp=f-R_*v0; return (tmp*math.exp(-R_*t)+f*R_*t-tmp)/(R_*R_)
    def sol(F):
        F=float(np.ravel(F)[0])
        vx=math.cos(xa)*F; vy=math.cos(ya)*F
        fx=math.cos(pa)*W_*wind+math.sin(pa)*G_; fy=-math.sin(pa)*W_*wind+math.cos(pa)*G_
        t=fsolve(lambda t1: cp(vy,fy,float(np.ravel(t1)[0])),[2.0])[0]
        return cp(vx,fx,t)-math.hypot(dx,dy)
    return float(fsolve(sol,[100.0])[0])
d=json.load(open('dados/aprendizado.json',encoding='utf-8'))
ts=[t for t in d['tiros'] if t.get('acertou') and t['inst'] in('ULTIMA_LUTA_F1','DEVORADORES','ULTIMA_LUTA_F2')]
print(collections.Counter(t['inst'] for t in ts))
for inst in ('ULTIMA_LUTA_F1','DEVORADORES','ULTIMA_LUTA_F2'):
    xs=[t for t in ts if t['inst']==inst]
    best=None
    for s in np.arange(0.05,0.6,0.01):
        err=[]
        for t in xs:
            dx=abs(t['boss'][0]-t['azul'][0])*s; dy=(t['azul'][1]-t['boss'][1])*s
            if dx<0.5: continue
            try: err.append(abs(predict(t['angulo'],0,dx,dy)-t['forca']))
            except Exception: pass
        if err and (best is None or np.mean(err)<best[0]): best=(np.mean(err),s,len(err),np.median(err))
    print(inst,len(xs),'melhor escala px->tela',best)
