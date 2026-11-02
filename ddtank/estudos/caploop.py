import sys,time,os,datetime,cv2,glob
sys.path.insert(0,'.')
import janela,config
from navegador import em_1280
d=sys.argv[1];h=janela.resolver_janela(config.TITULO_JANELA,config.EXE_JANELA)
fim=time.time()+60*60
while time.time()<fim:
    img=janela.capturar(h,'print')
    if img is not None:
        cv2.imwrite(os.path.join(d,datetime.datetime.now().strftime('%H%M%S_%f')[:9]+'.jpg'),em_1280(img)[60:688,0:1280],[cv2.IMWRITE_JPEG_QUALITY,70])
        fs=sorted(glob.glob(d+'/*.jpg'))
        for f in fs[:-2500]: os.remove(f)
    time.sleep(0.6)
