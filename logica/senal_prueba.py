"""Señal de prueba: secuencia Zadoff-Chu y estructura de la ráfaga (módulo 01).

Una ráfaga = n_rep copias consecutivas de la misma ZC. Se transmite una ráfaga cada
`periodo_ms` y entre ráfagas hay silencio (el receptor mide ahí el piso de ruido).

    |<------------------- periodo ------------------->|
    [ ZC | ZC | ZC | ... | ZC ][ silencio (ruido) ... ]
      └─── n_rep × n_zc ───┘
"""
import numpy as np


# ---------------------------------------------------------------------------
# zadoff_chu
# Computacional: genera x[k] = exp(-jπ·u·k·(k+1)/N), k = 0..N-1 (N impar, gcd(u,N)=1).
# Matemática/física: secuencia CAZAC (Constant Amplitude Zero AutoCorrelation).
#   (1) |x[k]| = 1: envolvente constante → potencia = amplitud² sin picos, ideal para
#       medir potencia y para no saturar el amplificador del SDR.
#   (2) Su autocorrelación periódica es un impulso perfecto: R[m] = N·δ[m mod N].
#       Por eso la correlación con la ZC conocida da directamente la respuesta al
#       impulso del canal (sin "sidelobes" que confundan un eco con ruido).
#   (3) Su espectro tiene módulo constante: al invertir H = Y/X no se amplifica ruido.
def zadoff_chu(n, u):
    k = np.arange(n)
    return np.exp(-1j * np.pi * u * k * (k + 1) / n)


# ---------------------------------------------------------------------------
# construir_rafaga
# Computacional: repite la ZC n_rep veces y la escala por la amplitud `amp`.
# Matemática/física: la repetición hace la señal periódica de periodo N. Eso permite
#   (a) detectar sin conocer la señal comparando una copia con la siguiente
#   (Schmidl-Cox) y que el CFO aparezca como un giro de fase constante entre copias,
#   (b) promediar copias coherentemente: ruido ÷ (n_rep-1) en potencia.
def construir_rafaga(cfg):
    return cfg.amp * np.tile(zadoff_chu(cfg.n_zc, cfg.raiz), cfg.n_rep)


# ---------------------------------------------------------------------------
# construir_periodo
# Computacional: ráfaga + ceros hasta n_periodo; es el buffer que el TX repite en bucle.
# Matemática/física: el ciclo de trabajo (duty = n_rafaga/n_periodo) es pequeño: el
#   transmisor emite poco tiempo, el silencio entre ráfagas es la referencia de ruido
#   térmico del receptor (kTB·F), imprescindible para convertir potencia en SNR.
def construir_periodo(cfg):
    rafaga = construir_rafaga(cfg)
    return np.concatenate([rafaga, np.zeros(cfg.n_periodo - rafaga.size)]).astype(np.complex64)


# ---------------------------------------------------------------------------
# autocorrelacion_periodica_db
# Computacional: R = IFFT(|FFT(x)|²) / N (autocorrelación circular por FFT), en dB.
# Matemática/física: teorema de Wiener-Khinchin: la autocorrelación es la transformada
#   inversa de la densidad espectral. Para una ZC |X[k]|² = N (constante) y por tanto
#   R[m] = N·δ[m]. Numéricamente los lóbulos laterales quedan ~ -300 dB; se recortan a
#   `piso` para graficar.
def autocorrelacion_periodica_db(zc, piso=-80.0):
    n = zc.size
    X = np.fft.fft(zc)
    r = np.fft.ifft(np.abs(X) ** 2) / n
    db = 20 * np.log10(np.abs(r) + 1e-15)
    return np.maximum(db, piso)


# ---------------------------------------------------------------------------
# salida_filtro_adaptado
# Computacional: correlaciona (aperiódicamente) la ráfaga completa con UNA ZC y
#   normaliza por N. Devuelve el módulo y el eje de lags.
# Matemática/física: filtro adaptado h[k] = x*[-k]: maximiza la SNR en el instante
#   de muestreo. Con n_rep copias aparecen n_rep picos separados N muestras, cuya
#   altura sube y baja (rampa triangular) porque cada pico solo suma la parte que se
#   solapa con la ráfaga. El pico central (lag 0) vale N·amp.
def salida_filtro_adaptado(rafaga, zc):
    y = np.correlate(rafaga, zc, mode='full') / zc.size
    lags = np.arange(-(zc.size - 1), rafaga.size)
    return lags, np.abs(y)


# ---------------------------------------------------------------------------
# psd_welch
# Computacional: promedia periodogramas con ventana de Hann sobre bloques de nfft
#   muestras; centra el espectro en 0 Hz y devuelve dB relativos al pico.
# Matemática/física: estima la densidad espectral de potencia S(f). El promedio de
#   bloques reduce la varianza del estimador (≈ 1/nprom). La ventana de Hann reduce la
#   fuga espectral a costa de ensanchar el lóbulo principal.
def psd_welch(x, fs, nfft=1024, nprom_max=64):
    x = np.asarray(x)
    nprom = max(1, min(nprom_max, x.size // nfft))
    w = np.hanning(nfft)
    P = np.zeros(nfft)
    for k in range(nprom):
        seg = x[k * nfft:(k + 1) * nfft]
        if seg.size < nfft:
            seg = np.pad(seg, (0, nfft - seg.size))
        X = np.fft.fftshift(np.fft.fft(seg * w)) / w.sum()
        P += np.abs(X) ** 2
    P /= nprom
    f = np.arange(-nfft // 2, nfft // 2) * fs / nfft
    db = 10 * np.log10(P + 1e-15)
    return f, db
