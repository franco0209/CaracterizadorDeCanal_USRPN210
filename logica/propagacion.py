"""Pérdida de propagación y modelo log-distancia (módulo 04, punto 2.2).

Modelo:   P_rx(d) [dB] = P0 − 10·n·log10(d/d0) + X_σ
    P0 : potencia a la distancia de referencia d0 (incluye Ptx, Gtx, Grx, calibración)
    n  : exponente de pérdida (2 espacio libre, 2.7–3.5 urbano, 1.6–1.8 pasillos LOS)
    X_σ: variable gaussiana (dB) con desviación σ: sombreado (shadowing) log-normal
"""
import numpy as np

from .parametros import C_LUZ


# ---------------------------------------------------------------------------
# fspl_db
# Computacional: FSPL = 20·log10(4π·d·f/c).
# Matemática/física: pérdida en espacio libre de Friis. La densidad de potencia de una
#   fuente isótropa cae como 1/(4πd²); la antena receptora isótropa tiene área efectiva
#   λ²/4π, de modo que Pr/Pt = (λ/4πd)². Es la referencia con n = 2: lo que se espera sin
#   obstáculos ni reflexiones. A 915 MHz y 1 m: ≈ 31.7 dB.
def fspl_db(d, fc):
    return 20 * np.log10(4 * np.pi * np.asarray(d, dtype=float) * fc / C_LUZ)


# ---------------------------------------------------------------------------
# modelo_log_distancia
# Computacional: evalúa P0 − 10·n·log10(d/d0).
# Matemática/física: en escala log-log la pérdida es una RECTA de pendiente −10·n dB
#   por década de distancia. n es el parámetro físico que resume el entorno.
def modelo_log_distancia(d, p0, n, d0=1.0):
    return p0 - 10 * n * np.log10(np.asarray(d, dtype=float) / d0)


# ---------------------------------------------------------------------------
# ajustar_log_distancia
# Computacional: regresión lineal por mínimos cuadrados de P_i frente a
#   X_i = −10·log10(d_i/d0): pendiente = n, ordenada = P0. Calcula además σ (desviación
#   residual con n−2 grados de libertad), R², error estándar de n y su IC al 95 %
#   (aprox. ±2·SE).
# Matemática/física: minimiza Σ(P_i − P0 − n·X_i)². Los residuos r_i = P_i − P̂_i
#   estiman el sombreado X_σ; su desviación σ cuantifica cuánto fluctúa la medida respecto
#   al modelo (obstáculos, reflexiones). SE(n) = σ/√Σ(X_i−X̄)²: mide la incertidumbre de n
#   y baja si se miden distancias muy espaciadas en log(d). Nota: con solo 2 distancias
#   la recta pasa por ambos puntos (σ = 0) y no hay estadística.
def ajustar_log_distancia(d, p_db, d0=1.0):
    d = np.asarray(d, dtype=float)
    p = np.asarray(p_db, dtype=float)
    if d.size < 2 or np.ptp(d) == 0:
        raise ValueError('Se necesitan al menos 2 distancias distintas')
    X = -10 * np.log10(d / d0)
    n_est, p0 = np.polyfit(X, p, 1)
    pred = p0 + n_est * X
    res = p - pred
    gl = max(1, d.size - 2)
    sigma = float(np.sqrt(np.sum(res ** 2) / gl)) if d.size > 2 else 0.0
    sxx = float(np.sum((X - X.mean()) ** 2))
    se = sigma / np.sqrt(sxx) if sxx > 0 else float('nan')
    sst = float(np.sum((p - p.mean()) ** 2))
    r2 = 1 - float(np.sum(res ** 2)) / sst if sst > 0 else float('nan')
    return {'n': float(n_est), 'p0': float(p0), 'sigma': sigma, 'r2': r2,
            'se_n': float(se), 'ic95': float(2 * se), 'residuos': res.tolist(),
            'd0': d0, 'gl': int(gl)}


# ---------------------------------------------------------------------------
# curva_modelo
# Computacional: genera puntos del modelo ajustado sobre una malla log-espaciada
#   cubriendo el rango medido (para dibujar la recta).
# Matemática/física: malla geométrica porque la pérdida es lineal en log(d).
def curva_modelo(d, ajuste, npts=60):
    d = np.asarray(d, dtype=float)
    dd = np.geomspace(d.min() * 0.9, d.max() * 1.1, npts)
    return dd, modelo_log_distancia(dd, ajuste['p0'], ajuste['n'], ajuste['d0'])


# ---------------------------------------------------------------------------
# interpretar_exponente
# Computacional: devuelve un texto según el rango de n.
# Matemática/física: valores típicos medidos: ≈2 espacio libre; 1.6–1.8 guía de onda
#   (pasillo LOS); 2.7–3.5 entornos urbanos/interiores con obstáculos; 4–6 interiores muy
#   obstruidos. n>2 implica que las reflexiones destructivas/obstáculos añaden pérdida.
def interpretar_exponente(n):
    if n < 1.5:
        return 'n < 1.5: efecto de guía de onda o mediciones muy cerca (campo cercano / suelo).'
    if n < 2.3:
        return 'n ≈ 2: comportamiento de espacio libre (LOS despejada).'
    if n < 3.0:
        return 'n entre 2.3 y 3: LOS con reflexiones / interior abierto.'
    if n < 4.0:
        return 'n entre 3 y 4: entorno con obstrucciones parciales.'
    return 'n > 4: interior muy obstruido o medidas cerca del piso de ruido.'
