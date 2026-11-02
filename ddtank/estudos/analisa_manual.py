import json,cv2,numpy as np,sys,os
sys.path.insert(0,'.')
import leitura as L, pvp as P
from navegador import em_1280
D=sys.argv[1]
ev=[json.loads(l) for l in open(D+'eventos.jsonl',encoding='utf-8')]
tiros=[e for e in ev if e['tipo']=='tecla' and e.get('tecla')=='espaco' and e['duracao']>=0.4]
for i,e in enumerate(tiros):
    fr=e['frames']
    a=em_1280(cv2.imread(D+'frames/'+[f for f in fr if 'solta_antes' in f][0]))
    deps=[em_1280(cv2.imread(D+'frames/'+f)) for f in fr if 'solta_depois' in f]
    ang=L.angulo_preciso(a); fo=[round(L.forca(d)) for d in deps]
    larg=P.largura_caixa_minimapa(a)
    pos=P.posicoes_na_tela(a)
    print(f"#{i+1} t={e['t']:.0f}s hold={e['duracao']:.2f}s ang={ang:.0f} forca_depois={fo} caixa_mini={None if larg is None else round(larg)} tela={pos}")
