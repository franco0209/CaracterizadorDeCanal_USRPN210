"""Potencia recibida por ráfaga, piso de ruido y SNR (módulos 00, 03, 04, 05, 06).

`medir_captura` es el procedimiento completo del punto 2.1d de la práctica: toma las
muestras I/Q crudas y devuelve, para CADA ráfaga detectada, su potencia estimada.
"""
import numpy as np

from . import deteccion
from .parametros import a_db, promedio_db, de_db
from .senal_prueba import zadoff_chu


# ---------------------------------------------------------------------------
# pico_adc
# Computacional: máximo de |I| y |Q| de la captura (escala completa = 1.0).
# Matemática/física: el ADC del SDR cuantiza en ±1 (full scale). Si el pico se acerca
#   a 1 el ADC (o el amplificador de ganancia variable) se satura: la señal se recorta,
#   se generan armónicos y la potencia medida deja de ser proporcional a la recibida.
#   Si el pico es muy pequeño (<0.02) se pierden bits de resolución: el ruido de
#   cuantización domina. Por eso toda serie de medidas se hace con el pico entre ambos.
def pico_adc(x):
    return float(np.max(np.abs(np.r_[x.real, x.imag]))) if x.size else 0.0


# ---------------------------------------------------------------------------
# saturacion_pct
# Computacional: porcentaje de muestras con |I| o |Q| > 0.99.
# Matemática/física: indicador directo de recorte; >0.1 % invalida la medición.
def saturacion_pct(x):
    if not x.size:
        return 0.0
    return float(100 * np.mean(np.abs(np.r_[x.real, x.imag]) > 0.99))


# ---------------------------------------------------------------------------
# potencia_media
# Computacional: media de |x[n]|² sobre las muestras dadas.
# Matemática/física: potencia media discreta P = (1/N)·Σ|x[n]|² (en unidades de
#   "full-scale al cuadrado", dBFS). No es potencia absoluta en dBm: ésta depende de
#   la ganancia del receptor y la calibración (offset constante que no altera el
#   exponente de pérdida n ni las diferencias en dB entre condiciones).
def potencia_media(x):
    x = np.asarray(x)
    return float(np.mean(np.abs(x) ** 2)) if x.size else 0.0


# ---------------------------------------------------------------------------
# piso_ruido
# Computacional: construye una máscara que excluye cada ráfaga con una guarda de
#   2N muestras a cada lado y promedia |x|² del resto (ya sin DC).
# Matemática/física: en los silencios solo hay ruido térmico y del receptor,
#   P_n = k·T·B·F (k Boltzmann, T≈290 K, B≈fs, F figura de ruido). Medirlo en la
#   MISMA captura asegura que cualquier deriva de ganancia afecte igual a señal y
#   ruido. Debe restarse de la potencia de la ráfaga: P_señal = P_total − P_n.
def piso_ruido(x, inicios, largo, guarda):
    mask = np.ones(x.size, dtype=bool)
    for s in inicios:
        mask[max(0, s - guarda):s + largo + guarda] = False
    if mask.sum() < 256:
        return None
    return potencia_media(x[mask])


# ---------------------------------------------------------------------------
# resumen_potencias
# Computacional: agrega una lista de potencias en dBFS: media (pasando por lineal),
#   desviación estándar en dB, mínimo, máximo y cantidad.
# Matemática/física: media en lineal = potencia física media; la desviación en dB
#   mide la dispersión de la medida (inestabilidad del enlace + fading temporal).
def resumen_potencias(p_db):
    p = np.asarray(p_db, dtype=float)
    if p.size == 0:
        return None
    return {'media_db': promedio_db(p), 'std_db': float(np.std(p)),
            'min_db': float(np.min(p)), 'max_db': float(np.max(p)), 'n': int(p.size)}


# ---------------------------------------------------------------------------
# medir_captura
# Computacional: (1) quita el DC; (2) Schmidl-Cox detecta cada ráfaga y estima su CFO;
#   (3) derota y refina el inicio con la ZC; (4) descarta ráfagas cortadas por el
#   borde de la captura; (5) mide P_total por ráfaga y el piso de ruido global;
#   (6) calcula P_señal = P_total − P_ruido y la SNR de cada ráfaga.
# Matemática/física: P_total = P_señal + P_ruido (señal y ruido incorrelados, sus
#   potencias se suman). SNR = P_señal/P_ruido. La potencia en dBFS es la magnitud
#   que se grafica contra distancia: P_rx(d) ∝ P_tx·G_tx·G_rx·(λ/4πd)^n.
#   Si SNR < ~6 dB la resta P_total − P_n es poco fiable (la medida llega al piso).
def medir_captura(x, cfg, umbral=0.5):
    x = np.asarray(x, dtype=np.complex128)
    dc = complex(np.mean(x)) if x.size else 0j
    xs = x - dc
    zc = zadoff_chu(cfg.n_zc, cfg.raiz)
    crudas, M = deteccion.detectar_rafagas(xs, cfg, umbral)
    n, Lb = cfg.n_zc, cfg.n_rafaga

    validas = []
    for b in crudas:
        r = deteccion.refinar_tiempo(xs, zc, b['d'], b['cfo_hz'], cfg.fs)
        if r is None:
            continue
        ini, c = r
        if ini < 0 or ini + Lb > xs.size:      # ráfaga truncada por el borde
            continue
        b = dict(b, inicio=int(ini), fase_deg=float(np.degrees(np.angle(c))))
        validas.append(b)

    p_n = piso_ruido(xs, [b['inicio'] for b in validas], Lb, 2 * n)
    if p_n is None:                              # captura sin silencio utilizable
        p_n = float(np.percentile(np.abs(xs) ** 2, 5)) if xs.size else 1e-12
    p_n = max(p_n, 1e-14)

    rafagas = []
    for b in validas:
        p_tot = potencia_media(xs[b['inicio']:b['inicio'] + Lb])
        p_sig = max(p_tot - p_n, p_n * 1e-3)
        rafagas.append({
            'inicio': b['inicio'], 't_ms': b['inicio'] / cfg.fs * 1e3, 'M': b['M'],
            'cfo_hz': b['cfo_hz'], 'fase_deg': b['fase_deg'],
            'p_tot_dbfs': float(a_db(p_tot)), 'p_dbfs': float(a_db(p_sig)),
            'snr_db': float(a_db(p_sig / p_n)),
        })

    n_esp = max(1, int(x.size // cfg.n_periodo))
    return {
        'rafagas': rafagas, 'n_det': len(rafagas), 'n_esp': n_esp,
        'ruido_dbfs': float(a_db(p_n)), 'pico': pico_adc(x), 'sat_pct': saturacion_pct(x),
        'dc_dbfs': float(a_db(abs(dc) ** 2)), 'M': M, 'umbral': umbral, 'n': int(x.size),
    }
