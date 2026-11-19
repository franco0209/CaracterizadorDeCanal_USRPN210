"""Canal inalámbrico simulado: permite ensayar toda la GUI sin hardware.

Reproduce los cuatro fenómenos de la práctica con modelos de libro:
    pérdida log-distancia + sombreado (distancia) · atenuación fija (obstáculos) ·
    interferencia de ondas planas (fading al mover el RX) · ecos con retardo (multitrayectoria).
"""
import zlib

import numpy as np

from .parametros import longitud_onda
from .senal_prueba import construir_periodo

# Cada eco: (retardo ns, potencia relativa dB, ángulo de llegada °).
ESCENARIOS = {
    'los':   [(0, 0, 20), (80, -18, 110), (250, -24, 250)],
    # retardos cortos y potencias parejas: sin camino dominante → Rayleigh (fading profundo)
    'nlos':  [(0, 0, 20), (15, -1, 75), (30, -2, 130), (45, -1, 190), (60, -3, 250), (90, -4, 310)],
    'multi': [(0, 0, 20), (400, -3, 100), (800, -6, 170), (1300, -9, 230), (1900, -12, 300), (2600, -15, 340)],
}

G_TX_REF, G_RX_REF = 15.0, 20.0     # ganancias a las que corresponde p_ref


# ---------------------------------------------------------------------------
# potencia_modelo_dbfs
# Computacional: P = P_ref − 10·n·log10(d) + sombra − obstáculo + (ΔG_tx + ΔG_rx).
# Matemática/física: modelo log-distancia con d0 = 1 m. `sombra` ~ N(0,σ²) es el
#   shadowing (se sortea UNA vez por posición física, no por ráfaga). Las ganancias del
#   SDR suman 1 dB por dB en el receptor y en el transmisor (hasta saturar).
def potencia_modelo_dbfs(d, p_ref, n_ruta, sombra_db, obst_db, g_tx, g_rx):
    return (p_ref - 10 * n_ruta * np.log10(max(d, 0.05)) + sombra_db - obst_db
            + (g_tx - G_TX_REF) + (g_rx - G_RX_REF))


# ---------------------------------------------------------------------------
# generar_captura
# Computacional: (1) repite el periodo TX con un desfase aleatorio; (2) pasa la señal por
#   H(f) = Σ_k a_k·e^{jφ_k(x)}·e^{−j2πfτ_k} aplicado con FFT (permite retardos
#   fraccionarios); (3) escala a la potencia media objetivo; (4) aplica CFO y fase
#   aleatoria; (5) suma ruido gaussiano complejo; (6) recorta a ±1 como un ADC.
# Matemática/física: canal multitrayectoria de ondas planas: la k-ésima onda llega por el
#   ángulo θ_k, y al desplazar el RX x metros su fase cambia 2π·x·cosθ_k/λ: al sumarse con
#   las demás aparece la interferencia que ve el receptor (fading espacial). Las potencias
#   a_k² se normalizan a 1 para que la potencia MEDIA coincida con la del modelo de
#   propagación. El CFO es una rampa de fase e^{j2πΔf t}.
def generar_captura(cfg, n, p_dbfs, escenario, pos_m, ruido_dbfs, cfo_hz, rng):
    per = construir_periodo(cfg)
    off = int(rng.integers(0, per.size))
    tx = np.tile(per, n // per.size + 2)[off:off + n].astype(np.complex128)

    taps = ESCENARIOS[escenario]
    pw = 10 ** (np.array([t[1] for t in taps]) / 10)
    pw /= pw.sum()
    fases = np.random.RandomState(zlib.crc32(escenario.encode())).uniform(0, 2 * np.pi, len(taps))
    f = np.fft.fftfreq(n, 1 / cfg.fs)
    lam = longitud_onda(cfg.fc)
    H = np.zeros(n, dtype=complex)
    for (tau, _, ang), a, ph in zip(taps, pw, fases):
        fase = ph + 2 * np.pi * pos_m * np.cos(np.radians(ang)) / lam
        H += np.sqrt(a) * np.exp(1j * fase) * np.exp(-2j * np.pi * f * tau * 1e-9)
    y = np.fft.ifft(np.fft.fft(tx) * H) * (10 ** (p_dbfs / 20) / cfg.amp)

    t = np.arange(n) / cfg.fs
    y *= np.exp(1j * (2 * np.pi * cfo_hz * t + rng.uniform(0, 2 * np.pi)))
    sig = np.sqrt(10 ** (ruido_dbfs / 10) / 2)
    y += sig * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    y = np.clip(y.real, -1, 1) + 1j * np.clip(y.imag, -1, 1)
    return y
