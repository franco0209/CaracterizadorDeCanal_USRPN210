"""Estimación de la respuesta al impulso del canal y multitrayectoria (módulo 06b, 2.5).

Modelo del canal (tiempo discreto):  y[n] = Σ_k h[k]·x[n−k] + w[n]
    h[k]: componente que llega con retardo k/fs. Una reflexión que recorre ΔL metros más
          que el camino directo llega con retardo ΔL/c y menor potencia.
"""
import numpy as np

from . import deteccion
from .parametros import C_LUZ, a_db
from .senal_prueba import zadoff_chu


# ---------------------------------------------------------------------------
# estimar_respuesta_canal
# Computacional: (1) toma la ráfaga ya sincronizada, derota el CFO; (2) descarta la primera
#   copia (contiene el transitorio del silencio previo); (3) promedia coherentemente las
#   n_rep−1 copias restantes (cada copia tiene longitud N); (4) divide en frecuencia:
#   H[k] = Y[k]/X[k]; (5) h = IFFT(H).
# Matemática/física: si la entrada es periódica de periodo N y la respuesta h dura menos
#   de N muestras, la salida en régimen es la convolución CIRCULAR y[n] = (h ⊛ x)[n]; la
#   DFT la diagonaliza: Y[k] = H[k]·X[k]. Como |X[k]| es constante (propiedad de la ZC),
#   la división no amplifica ruido (a diferencia de una señal con ceros espectrales).
#   El promedio de M copias reduce la potencia de ruido de h en 10·log10(M) dB. La
#   resolución de retardos es 1/fs y el span observable N/fs.
def estimar_respuesta_canal(x, inicio, cfo_hz, cfg):
    n = cfg.n_zc
    zc = cfg.amp * zadoff_chu(n, cfg.raiz)
    seg = deteccion.derotar(x[inicio:inicio + cfg.n_rafaga], cfo_hz, cfg.fs)
    copias = seg.reshape(cfg.n_rep, n)[1:]
    y = copias.mean(axis=0)
    return np.fft.ifft(np.fft.fft(y) / np.fft.fft(zc))


# ---------------------------------------------------------------------------
# alinear_camino_principal
# Computacional: rota circularmente h para dejar el máximo en la posición `pre`, de
#   modo que haya una zona anterior (precursor) visible.
# Matemática/física: el instante absoluto de llegada es desconocido (TX y RX no comparten
#   reloj), solo importan los retardos RELATIVOS entre componentes. La rotación circular es
#   legítima porque el canal medido es periódico de periodo N.
def alinear_camino_principal(h, pre=None):
    pre = max(2, len(h) // 12) if pre is None else pre
    k = int(np.argmax(np.abs(h)))
    return np.roll(h, pre - k), pre


# ---------------------------------------------------------------------------
# interpolar_respuesta
# Computacional: multiplica H = FFT(h) por una ventana de Hann (opcional), rellena con
#   ceros el espectro (zero-padding en frecuencia) y vuelve a tiempo con la IFFT, para
#   obtener `factor` puntos por cada muestra original.
# Matemática/física: interpolación band-limited de h(t). Con la banda rectangular el pulso
#   de un solo camino es una sinc con lóbulos laterales de −13 dB que parecerían ecos
#   falsos. La ventana de Hann en frecuencia los baja a ≈ −31 dB a cambio de ensanchar el
#   lóbulo principal ≈1.5× (menor resolución): es el compromiso clásico de los sondeadores
#   de canal. No se añade información nueva, solo se dibuja mejor lo que ya se midió.
def interpolar_respuesta(h, factor=8, ventana=True):
    n = len(h)
    H = np.fft.fftshift(np.fft.fft(h))
    if ventana:
        H = H * np.hanning(n)
    pad = (n * factor - n) // 2
    Hp = np.pad(H, (pad, n * factor - n - pad))
    return np.fft.ifft(np.fft.ifftshift(Hp)) * factor


# ---------------------------------------------------------------------------
# perfil_potencia_retardo
# Computacional: PDP[k] = |h[k]|², y su versión en dB relativa al máximo.
# Matemática/física: perfil de potencia-retardo (power delay profile): potencia media que
#   llega con cada retardo. Es la gráfica clave del punto 2.5: un solo pico (LOS puro) o
#   varios picos (ecos). La potencia total Σ|h|² es la ganancia de potencia del canal.
def perfil_potencia_retardo(h):
    pdp = np.abs(h) ** 2
    return pdp, a_db(pdp / max(pdp.max(), 1e-30))


# ---------------------------------------------------------------------------
# detectar_componentes
# Computacional: encuentra máximos locales del PDP que superen el umbral
#   max(−umbral_rel dB bajo el pico, piso+10 dB) y separados al menos `sep` muestras;
#   devuelve retardo [ns], exceso de camino [m] y potencia relativa [dB].
# Matemática/física: cada máximo es una componente multitrayectoria. Exceso de camino
#   ΔL = c·τ. El piso se estima con la MEDIANA del PDP (la mediana ignora los pocos picos
#   y refleja el nivel de ruido). Dos ecos más cercanos que 1/fs no se pueden separar
#   (resolución).
def detectar_componentes(pdp, fs, pre, umbral_rel_db=25.0, sep=2, max_comp=8):
    piso = float(np.median(pdp))
    thr = max(pdp.max() * 10 ** (-umbral_rel_db / 10), piso * 10)
    cand = [k for k in range(1, len(pdp) - 1)
            if pdp[k] >= pdp[k - 1] and pdp[k] > pdp[k + 1] and pdp[k] >= thr]
    cand.sort(key=lambda k: -pdp[k])
    elegidos = []
    for k in cand:
        if all(abs(k - j) >= sep for j in elegidos):
            elegidos.append(k)
        if len(elegidos) >= max_comp:
            break
    elegidos.sort()
    ref = pdp.max()
    primero = elegidos[0] if elegidos else pre
    return [{'tau_ns': float((k - primero) / fs * 1e9),
             'exceso_m': float((k - primero) / fs * C_LUZ),
             'p_rel_db': float(a_db(pdp[k] / ref))} for k in elegidos]


# ---------------------------------------------------------------------------
# respuesta_en_frecuencia
# Computacional: H(f) = FFT(h) (centrada), en dB relativos a su media, y el rizado
#   pico-a-pico sobre el 80 % central de la banda.
# Matemática/física: la transformada de Fourier de la respuesta al impulso es la respuesta
#   en frecuencia del canal. Con un solo camino |H(f)| es plano; con ecos se suman con
#   fase distinta según f: aparecen NULOS (desvanecimiento selectivo en frecuencia). Un eco
#   de retardo τ produce rizado con periodo 1/τ en frecuencia.
def respuesta_en_frecuencia(h, fs):
    n = len(h)
    H = np.fft.fftshift(np.fft.fft(h))
    db = a_db(np.abs(H) ** 2 / np.mean(np.abs(H) ** 2))
    f = np.fft.fftshift(np.fft.fftfreq(n, 1 / fs))
    lo, hi = int(n * 0.1), int(n * 0.9)
    return f, db, float(np.ptp(db[lo:hi]))


# ---------------------------------------------------------------------------
# parametros_dispersion
# Computacional: (usar el PDP SIN interpolar: una muestra = una componente resoluble)
#   sobre el PDP sin piso de ruido calcula retardo medio τ̄ = Σ τ·P/ΣP, la
#   dispersión RMS στ = √(Σ (τ−τ̄)²·P/ΣP), el factor K del canal (potencia del camino
#   principal / potencia del resto) y el ancho de banda de coherencia B_c ≈ 1/(5·στ).
# Matemática/física: στ resume cuán "esparcido" en el tiempo está el eco. Si el período de
#   símbolo T_s no es mucho mayor que στ aparece interferencia entre símbolos (ISI) y el
#   canal es selectivo en frecuencia: no se arregla subiendo potencia, requiere
#   ecualización/OFDM. B_c es el ancho dentro del cual el canal es ≈ plano en frecuencia.
def parametros_dispersion(pdp, fs, pre):
    piso = float(np.median(pdp))
    P = np.maximum(pdp - piso, 0)
    P[P < P.max() * 1e-3] = 0                       # ignora lo que está 30 dB bajo el pico
    if P.sum() <= 0:
        return {'tau_medio_ns': 0.0, 'tau_rms_ns': 0.0, 'k_db': None, 'bc_mhz': None}
    tau = (np.arange(len(P)) - pre) / fs
    tm = float(np.sum(tau * P) / P.sum())
    rms = float(np.sqrt(np.sum((tau - tm) ** 2 * P) / P.sum()))
    principal = P.max()
    resto = P.sum() - principal
    return {'tau_medio_ns': tm * 1e9, 'tau_rms_ns': rms * 1e9,
            'k_db': float(a_db(principal / resto)) if resto > 0 else None,
            'bc_mhz': float(1 / (5 * rms) / 1e6) if rms > 0 else None,
            'snr_canal_db': float(a_db(P.max() / max(piso, 1e-30)))}
