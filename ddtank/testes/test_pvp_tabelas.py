"""Confere a regra do video de calculo (PVP) contra as tabelas EstrAng do proprio jogo.
Ajusta uma fisica simples (distancia = A*F^2*sen(2a) + C*F^3*sen(2a)) nas tabelas de 30 e 50 graus
e testa: (1) as tabelas de 65/70 (so um ponto cada), (2) a regra do video "forca 95: angulo = 90 - distancia"."""
import numpy as np

T30 = [14, 20, 24, 28, 32, 35, 38, 41, 44, 47, 50, 52, 55, 57, 60, 62, 65, 67, 69, 72]
T50 = [14, 20, 24, 28, 32, 35, 39, 42, 44, 48, 50, 53, 55, 58, 60, 63, 65, 68, 70, 72]
PONTOS = [(30, i + 1, f) for i, f in enumerate(T30)] + [(50, i + 1, f) for i, f in enumerate(T50)]
VALIDACAO = [(65, 5, 37), (70, 5, 43)]


def sen2(a):
    return np.sin(np.radians(2 * a))


def ajustar(pontos):
    X = np.array([[f * f * sen2(a), f ** 3 * sen2(a)] for a, d, f in pontos])
    y = np.array([d for a, d, f in pontos])
    return np.linalg.lstsq(X, y, rcond=None)[0]


def main():
    A, C = ajustar(PONTOS)

    def distancia(a, f):
        return A * f * f * sen2(a) + C * f ** 3 * sen2(a)

    erro = max(abs(distancia(a, f) - d) for a, d, f in PONTOS)
    assert erro < 2.0, erro
    for a, d, f in VALIDACAO:
        assert abs(distancia(a, f) - d) < 1.0, (a, d, f)
    for a, d in [(80, 10), (75, 15), (70, 20)]:  # regra do video: forca 95
        assert abs(distancia(a, 95) - d) < 1.0, (a, d)
    for d in (5, 7, 8, 10):  # semi full (video do Strik): angulo = 90 - 2*distancia, forca ~62
        assert abs(distancia(90 - 2 * d, 62) - d) < 1.2, d
    print("tabelas EstrAng x regra do video OK (maior erro nas tabelas: %.2f)" % erro)


if __name__ == "__main__":
    main()
