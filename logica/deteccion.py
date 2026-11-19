"""Detección automática de ráfagas, CFO y sincronismo fino (módulo 03).

Cadena por captura:
    1. metrica_schmidl_cox   → M(d): ¿hay una ráfaga que empieza en d?  (insensible a CFO)
    2. detectar_rafagas      → picos de M por encima del umbral, sin duplicados
    3. estimar_cfo           → CFO de cada ráfaga a partir de la fase de P(d)
    4. derotar               → quita el CFO para que la correlación sea coherente
    5. refinar_tiempo        → correlación con la ZC: instante de inicio exacto
"""
import numpy as np


# ---------------------------------------------------------------------------
# metrica_schmidl_cox
# Computacional: z[k] = r[k]·conj(r[k+N]); P(d) = Σ_{k=0}^{L-1} z[d+k] (suma móvil
#   con cumsum, O(n)); R(d) = Σ |r[d+k+N]|²; M(d) = |P|²/R². L = (n_rep-1)·N.
# Matemática/física: si la señal es periódica de periodo N, r[k+N] = r[k]·e^{j2πΔf·N/fs}
#   (el CFO solo rota la fase), luego |P| = L·σ_s² sin importar Δf. M es el coeficiente
#   de correlación al cuadrado entre las dos ventanas (Cauchy-Schwarz: 0 ≤ M ≤ 1): vale
#   ≈1 cuando ambas ventanas caen dentro de la ráfaga y ≈1/L en ruido puro (los términos
#   tienen fase aleatoria y suman como √L en amplitud). No necesita conocer la señal ni
#   el CFO: es un detector no coherente.
def metrica_schmidl_cox(r, n, n_rep):
    r = np.asarray(r, dtype=np.complex128)
    L = (n_rep - 1) * n
    if r.size < n_rep * n + 2:
        return np.zeros(0), np.zeros(0, dtype=complex)
    z = r[:-n] * np.conj(r[n:])
    S = np.concatenate(([0], np.cumsum(z)))
    P = S[L:] - S[:-L]
    e = np.abs(r) ** 2
    Se = np.concatenate(([0], np.cumsum(e)))
    Rw = Se[L:] - Se[:-L]                 # energía de cada ventana de L muestras
    R1, R2 = Rw[:P.size], Rw[n:n + P.size]
    M = np.abs(P) ** 2 / (R1 * R2 + 1e-30)
    return M, P


# ---------------------------------------------------------------------------
# estimar_cfo
# Computacional: Δf = -∠P · fs / (2π·N).
# Matemática/física: con r[k+N] = r[k]·e^{j2πΔf N/fs}, el producto r[k]·r*[k+N]
#   tiene fase -2πΔf·N/fs. Solo es unívoco si |∠P| < π, o sea |Δf| < fs/(2N)
#   (Config.rango_cfo_hz). Dos SDR con osciladores distintos tienen Δf ≈ ppm·fc
#   (≈ ±2 kHz a 915 MHz con 2 ppm).
def estimar_cfo(P_val, n, fs):
    return float(-np.angle(P_val) * fs / (2 * np.pi * n))


# ---------------------------------------------------------------------------
# derotar
# Computacional: multiplica el segmento por exp(-j2π·Δf·k/fs).
# Matemática/física: el CFO es una rampa de fase e^{j2πΔf t}; multiplicar por su
#   conjugada la cancela. Sin esto, una correlación larga (N muestras) se atenúa por
#   un factor sinc(Δf·N/fs) y el timing/canal salen distorsionados.
def derotar(seg, cfo_hz, fs):
    k = np.arange(len(seg))
    return seg * np.exp(-2j * np.pi * cfo_hz * k / fs)


# ---------------------------------------------------------------------------
# detectar_rafagas
# Computacional: busca iterativamente el máximo de M; si supera el umbral lo registra
#   y anula M en ±(duración de la ráfaga) para no contar la misma ráfaga dos veces
#   (no-maximum suppression). Devuelve inicio grueso, valor de M y CFO.
# Matemática/física: el umbral fija el compromiso entre probabilidad de detección
#   y de falsa alarma. En ruido, M ~ 1/L; con SNR por muestra de 0 dB, M ya baja a
#   ≈0.2–0.4, de ahí que el umbral por defecto sea ~0.5.
def detectar_rafagas(r, cfg, umbral=0.5, max_n=500):
    M, P = metrica_schmidl_cox(r, cfg.n_zc, cfg.n_rep)
    if M.size == 0:
        return [], M
    Mw = M.copy()
    out = []
    while len(out) < max_n:
        d = int(np.argmax(Mw))
        if Mw[d] < umbral:
            break
        out.append({'d': d, 'M': float(M[d]), 'cfo_hz': estimar_cfo(P[d], cfg.n_zc, cfg.fs)})
        Mw[max(0, d - cfg.n_rafaga):d + cfg.n_rafaga] = 0
    out.sort(key=lambda b: b['d'])
    return out, M


# ---------------------------------------------------------------------------
# refinar_tiempo
# Computacional: correlación 'valid' entre la ráfaga derotada y UNA ZC en lags
#   −N/4..+N/4 alrededor del inicio grueso; el máximo de |c| da el inicio exacto y
#   su fase da la fase del canal.
# Matemática/física: el pico de la autocorrelación de la ZC es un impulso, por tanto
#   la posición del máximo es el instante de llegada del camino más fuerte con
#   precisión de 1 muestra (1/fs). Como la ráfaga es periódica (N), los picos se
#   repiten cada N: se busca solo en ±N/4 para que sea único.
def refinar_tiempo(x, zc, d, cfo_hz, fs):
    n = zc.size
    q = n // 4
    a = max(0, d - q)
    b = min(x.size, d + n + q)
    seg = derotar(x[a:b], cfo_hz, fs)
    if seg.size < n + 1:
        return None
    c = np.correlate(seg, zc, mode='valid')
    k = int(np.argmax(np.abs(c)))
    return a + k, complex(c[k] / n)
