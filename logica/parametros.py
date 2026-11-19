"""Parámetros del sistema y utilidades de unidades.

Todo el resto de `logica/` parte de la clase Config: ella fija la señal de prueba
y de ella se derivan resolución temporal, rango de CFO, ganancia de procesado, etc.
"""
import math

import numpy as np

C_LUZ = 299_792_458.0      # velocidad de la luz [m/s]
MCR_N210 = 100e6           # reloj maestro del USRP N210 [Hz]


# ---------------------------------------------------------------------------
# tasa_valida
# Computacional: el N210 solo entrega fs = MCR/D con D entero (4..512; par si D>128,
#   múltiplo de 4 si D>256). Calcula el D permitido más cercano al fs pedido.
# Matemática/física: el DDC (conversor digital descendente) del FPGA reduce el
#   muestreo del ADC (100 MS/s) por un factor entero D mediante filtros CIC+halfband.
#   Un fs que no sea MCR/D exacto no existe en hardware; fs_real = MCR/D.
def tasa_valida(fs, mcr=MCR_N210):
    dec = int(max(4, min(512, round(mcr / fs))))
    if dec > 128:
        dec += dec % 2
    if dec > 256:
        dec = (dec // 4) * 4
    return mcr / dec


# ---------------------------------------------------------------------------
# a_db
# Computacional: convierte potencia lineal (array o escalar) a dB; evita log(0)
#   imponiendo un piso de 1e-20.
# Matemática/física: P_dB = 10·log10(P). Se usa dB porque la pérdida de propagación
#   es multiplicativa (distancia^-n) y en dB pasa a ser aditiva y lineal en log(d).
def a_db(p_lineal):
    return 10.0 * np.log10(np.maximum(np.asarray(p_lineal, dtype=float), 1e-20))


# ---------------------------------------------------------------------------
# de_db
# Computacional: inversa de a_db.
# Matemática/física: P = 10^(P_dB/10). Necesario antes de promediar potencias.
def de_db(db):
    return 10.0 ** (np.asarray(db, dtype=float) / 10.0)


# ---------------------------------------------------------------------------
# promedio_db
# Computacional: promedia una lista de potencias dadas en dB pasando por lineal.
# Matemática/física: la potencia media física es la media ARITMÉTICA de las
#   potencias lineales (energía/tiempo). Promediar directamente los dB da la media
#   geométrica, que subestima la potencia cuando hay fluctuaciones (fading).
def promedio_db(p_db):
    p = np.asarray(p_db, dtype=float)
    if p.size == 0:
        return float('nan')
    return float(a_db(np.mean(de_db(p))))


# ---------------------------------------------------------------------------
# longitud_onda
# Computacional: λ = c / fc.
# Matemática/física: λ fija la escala del desvanecimiento a pequeña escala: los
#   máximos y mínimos de la interferencia se repiten cada ~λ/2 de desplazamiento
#   (a 915 MHz: λ ≈ 32.8 cm).
def longitud_onda(fc):
    return C_LUZ / fc


# ---------------------------------------------------------------------------
# Config
# Computacional: contenedor de los parámetros COMUNES de la práctica. Se construye
#   desde el diccionario `p` que llega de la interfaz. Valida la coherencia.
# Matemática/física: la señal de prueba es una secuencia Zadoff-Chu de longitud
#   n_zc repetida n_rep veces (una ráfaga) y seguida de silencio hasta completar el
#   periodo. Estas magnitudes derivadas son las que se justifican en el informe.
class Config:
    def __init__(self, p):
        self.fc = float(p['fc'])
        self.fs = float(p['fs'])
        self.n_zc = int(p['n_zc'])
        self.raiz = int(p['raiz'])
        self.n_rep = int(p['n_rep'])
        self.periodo_ms = float(p['periodo_ms'])
        self.amp = float(p['amp'])
        if self.n_zc < 7 or self.n_zc % 2 == 0:
            raise ValueError('La longitud Zadoff-Chu debe ser impar y ≥ 7')
        if math.gcd(self.raiz, self.n_zc) != 1:
            raise ValueError(f'La raíz {self.raiz} debe ser coprima con N={self.n_zc}')
        if self.n_rep < 3:
            raise ValueError('Se necesitan al menos 3 repeticiones (detección + CFO + canal)')
        if self.n_periodo < 2 * self.n_rafaga:
            raise ValueError('El periodo debe ser ≥ 2 veces la duración de la ráfaga')
        if not 0 < self.amp <= 1:
            raise ValueError('La amplitud debe estar en (0, 1]')

    # muestras de una ráfaga (n_rep periodos de la ZC)
    @property
    def n_rafaga(self):
        return self.n_zc * self.n_rep

    # muestras entre el inicio de dos ráfagas consecutivas (ráfaga + silencio)
    @property
    def n_periodo(self):
        return int(round(self.periodo_ms * 1e-3 * self.fs))

    @property
    def lam(self):
        return longitud_onda(self.fc)

    # Matemática/física: una ZC muestreada a fs ocupa ≈ fs de ancho de banda y la
    #   salida del filtro adaptado tiene ancho ≈ 1/fs: ésa es la resolución de retardos.
    @property
    def resol_t_ns(self):
        return 1e9 / self.fs

    # Dos ecos separados menos que c/fs se funden en una sola componente.
    @property
    def resol_d_m(self):
        return C_LUZ / self.fs

    # Matemática/física: al correlacionar con la ZC conocida, la energía de N·R
    #   muestras se concentra en un pico: la SNR mejora 10·log10(N·R) dB.
    @property
    def ganancia_proc_db(self):
        return 10 * math.log10(self.n_rafaga)

    # Matemática/física: el estimador de CFO usa el desfase entre dos periodos
    #   separados N muestras; es unívoco solo si |Δf|·N/fs < 1/2.
    @property
    def rango_cfo_hz(self):
        return self.fs / (2 * self.n_zc)

    def resumen(self):
        return {
            'fc': self.fc, 'fs': self.fs, 'fs_real': tasa_valida(self.fs),
            'n_zc': self.n_zc, 'n_rep': self.n_rep, 'n_rafaga': self.n_rafaga,
            'n_periodo': self.n_periodo, 't_rafaga_us': self.n_rafaga / self.fs * 1e6,
            'duty_pct': 100 * self.n_rafaga / self.n_periodo,
            'lambda_cm': self.lam * 100, 'resol_t_ns': self.resol_t_ns,
            'resol_d_m': self.resol_d_m, 'gp_db': self.ganancia_proc_db,
            'rango_cfo_hz': self.rango_cfo_hz,
            'span_canal_us': self.n_zc / self.fs * 1e6,
        }
