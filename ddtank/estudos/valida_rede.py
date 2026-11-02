# Compara a fisica exata com as explosoes informadas pelo servidor numa captura de rede (CAPTURAR_REDE.bat).
import sys, math, statistics, xml.etree.ElementTree as ET
sys.path.insert(0, '.')
import rede_ddt as R, fisica_exata as FX
cap = sys.argv[1]
balas = {int(i.get('ID')): FX.Bala(float(i.get('Mass')), float(i.get('Weight')), float(i.get('Wind')), float(i.get('DragIndex')))
         for i in ET.parse('dados/jogo/balllist.xml').getroot().iter('Item')}
f = R.fluxos(R.ler_pcapng(cap))
c = f['servidor'][0]; ini, K, _ = R.recuperar_chave(c); ps = R.pacotes(c, ini, K)
tiros = [R.tiro_do_servidor(p[5], p[3]) for p in ps if p[1] == 91 and p[5] and p[5][0] == 2]

def traj(b, vento, bala, passos):
    """Como o cliente (SimpleBomb): a cada passo lifeTime += 40 ms, calcula a posicao nova e executa as acoes com tempo <= lifeTime;
    CHANGE_SPEED (perk teleguiado) troca a velocidade e zera gravidade e vento (clearWG)."""
    m, arf = bala.mass, FX.MAPA_PADRAO.drag * bala.drag
    fx, fy = vento * bala.wind, FX.MAPA_PADRAO.weight * bala.weight * bala.mass
    x, y, vx, vy = float(b['x']), float(b['y']), float(b['vx']), float(b['vy']); out = [(x, y)]
    trocas = sorted((a['tempo'], a['p']) for a in b['acoes'] if a['tipo'] == 'CHANGE_SPEED')
    vida = 0
    for _ in range(passos):
        vida += 40
        vx += (fx - arf * vx) / m * FX.DT; x += vx * FX.DT; vy += (fy - arf * vy) / m * FX.DT; y += vy * FX.DT; out.append((x, y))
        while trocas and trocas[0][0] <= vida:
            _t, (nvx, nvy, _q, _r) = trocas.pop(0)
            vx, vy, fx, fy = float(nvx), float(nvy), 0.0, 0.0
    return out


def dist_seg(px, py, a, b):
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)

linhas = []
for t in tiros:
    for b in t['bombas']:
        bb = [a for a in b['acoes'] if a['tipo'] == 'BOMB']
        if not bb:
            continue
        a = bb[0]; n = a['tempo'] // 40
        bala = balas.get(b['bala'], FX.BALA_PADRAO)
        tr = traj(b, t['vento'], bala, n + 30)
        ds = [dist_seg(a['p'][0], a['p'][1], tr[i], tr[i + 1]) for i in range(len(tr) - 1)]
        k = min(range(len(ds)), key=ds.__getitem__)
        outras = [x['tipo'] for x in b['acoes'] if x['tipo'] != 'BOMB']
        teleguiado = any(x['tipo'] == 'CHANGE_SPEED' for x in b['acoes'])
        linhas.append(dict(teleguiado=teleguiado, d=ds[min(n, len(ds) - 1)], dmin=ds[k], k_menos_n=k - n, bala=b['bala'], m=(bala.mass, bala.weight, bala.wind, bala.drag),
                           vento=t['vento'], tempo=a['tempo'], outras=outras, atirador=t['atirador']))
print('bombas:', len(linhas))
for nome, sel in (('normais', [l for l in linhas if not l['teleguiado']]), ('teleguiados', [l for l in linhas if l['teleguiado']])):
    if sel:
        print(nome, len(sel), 'distancia ao segmento: mediana', round(statistics.median(l['dmin'] for l in sel), 2), 'max', round(max(l['dmin'] for l in sel), 1),
              '| <=3 px:', sum(l['dmin'] <= 3 for l in sel), '| <=6 px:', sum(l['dmin'] <= 6 for l in sel))
print('distancia minima a trajetoria (px): mediana', round(statistics.median(l['dmin'] for l in linhas), 1),
      '| <=2:', sum(l['dmin'] <= 2 for l in linhas), '| <=6:', sum(l['dmin'] <= 6 for l in linhas), '| >20:', sum(l['dmin'] > 20 for l in linhas))
from collections import Counter
print('k-n (passo mais perto - passo do tempo):', Counter(l['k_menos_n'] for l in linhas).most_common(6))
print('fisica das balas:', Counter(l['m'] for l in linhas).most_common(5))
for l in sorted(linhas, key=lambda l: -l['dmin'])[:10]:
    print(round(l['dmin'], 1), l['bala'], l['m'], 'vento', l['vento'], 'atirador', l['atirador'], l['outras'][:4])
