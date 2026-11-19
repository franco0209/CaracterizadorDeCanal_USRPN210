"""Desvanecimiento a pequeña escala (módulo 06a, punto 2.4).

Con el TX fijo y el RX desplazado fracciones de λ, la potencia oscila decenas de dB
aunque la distancia casi no cambie: es interferencia entre ondas que llegan por
caminos distintos (constructiva ↔ destructiva), no pérdida de propagación.
"""
import numpy as np

from .parametros import de_db, a_db, longitud_onda


# ---------------------------------------------------------------------------
# plan_barrido
# Computacional: devuelve el paso (λ/8 por defecto), el nº de posiciones para cubrir
#   `n_lambda` longitudes de onda y la tabla de posiciones.
# Matemática/física: el campo de interferencia varía con periodo ≈ λ/2 (las fases de dos
#   ondas con ángulos distintos difieren 2π·Δx·(cosθ1−cosθ2)/λ). Muestrear a λ/8 da 4
#   puntos por cada medio periodo (Nyquist espacial holgado) y cubrir ≥ 5λ da suficientes
#   máximos/mínimos para estadística.
def plan_barrido(fc, n_lambda=5, fraccion=8):
    lam = longitud_onda(fc)
    paso = lam / fraccion
    n = int(np.ceil(n_lambda * fraccion)) + 1
    return {'lambda_m': lam, 'paso_m': paso, 'n_pos': n,
            'posiciones_m': (np.arange(n) * paso).tolist()}


# ---------------------------------------------------------------------------
# envolvente_normalizada
# Computacional: r_i = sqrt(P_i)/sqrt(mean(P)) con P en lineal.
# Matemática/física: la amplitud de la señal recibida r = |h|; normalizada a su valor
#   cuadrático medio (RMS) se compara con las distribuciones teóricas, que dependen solo de
#   la relación entre componente directa y dispersa.
def envolvente_normalizada(p_db):
    p = de_db(np.asarray(p_db, dtype=float))
    return np.sqrt(p / np.mean(p))


# ---------------------------------------------------------------------------
# pdf_rayleigh
# Computacional: f(r) = 2r·exp(−r²) (con RMS normalizado a 1).
# Matemática/física: si no hay camino directo (NLOS) y hay muchas componentes de fase
#   aleatoria, I y Q son gaussianas independientes (teorema central del límite) y la
#   envolvente es Rayleigh; la potencia es exponencial. Fades profundos frecuentes:
#   P(P < media−10 dB) ≈ 10 %.
def pdf_rayleigh(r):
    r = np.asarray(r, dtype=float)
    return 2 * r * np.exp(-r ** 2)


# ---------------------------------------------------------------------------
# pdf_rice
# Computacional: f(r) = 2r(1+K)·exp(−K−(1+K)r²)·I0(2r·√(K(1+K))), con I0 = np.i0.
# Matemática/física: con un camino directo dominante (LOS) de potencia K veces la de las
#   componentes dispersas, la envolvente es Rice. K=0 → Rayleigh; K grande → casi
#   constante (poco fading). El factor K es la relación de potencias directa/dispersa.
def pdf_rice(r, K):
    r = np.asarray(r, dtype=float)
    return 2 * r * (1 + K) * np.exp(-K - (1 + K) * r ** 2) * np.i0(2 * r * np.sqrt(K * (1 + K)))


# ---------------------------------------------------------------------------
# estimar_k_rice
# Computacional: método de momentos sobre la potencia: v = var(P)/mean(P)²;
#   K = √(1−v)/(1−√(1−v)) si v<1, y 0 si v ≥ 1.
# Matemática/física: para Rice, la varianza normalizada de la POTENCIA vale
#   v = (1+2K)/(1+K)². Se invierte: con K=0 (Rayleigh) v=1 y con K→∞ v→0. Es un estimador
#   simple; con pocas posiciones (≈40) tiene incertidumbre grande.
def estimar_k_rice(p_db):
    p = de_db(np.asarray(p_db, dtype=float))
    v = np.var(p) / np.mean(p) ** 2
    if v >= 1:
        return 0.0
    s = np.sqrt(1 - v)
    return float(s / (1 - s))


# ---------------------------------------------------------------------------
# estadisticas_fading
# Computacional: calcula σ en dB, rango pico-a-pico, profundidad del fade más profundo
#   respecto a la mediana, % de posiciones a más de 10 dB bajo la mediana, nº de mínimos
#   locales profundos y su separación media (en λ), y el factor K.
# Matemática/física: la mediana es el nivel de referencia local ("potencia media de pequeña
#   escala"). Los mínimos profundos se esperan separados ≈ λ/2 para ondas contrapropagantes.
#   Lo importante para la comparación (2.6): estas variaciones ocurren en cm, mientras que
#   la pérdida de propagación cambia en metros.
def estadisticas_fading(pos_m, p_db, fc):
    pos = np.asarray(pos_m, dtype=float)
    p = np.asarray(p_db, dtype=float)
    lam = longitud_onda(fc)
    med = float(np.median(p))
    rel = p - med
    minimos = [i for i in range(1, p.size - 1)
               if p[i] < p[i - 1] and p[i] < p[i + 1] and rel[i] < -3]
    sep = float(np.mean(np.diff(pos[minimos])) / lam) if len(minimos) > 1 else None
    K = estimar_k_rice(p)
    return {'sigma_db': float(np.std(p)), 'pico_pico_db': float(np.ptp(p)),
            'mediana_db': med, 'fade_max_db': float(-rel.min()),
            'pct_bajo_10db': float(100 * np.mean(rel < -10)),
            'n_minimos': len(minimos), 'sep_minimos_lambda': sep,
            'K': K, 'K_db': float(a_db(K)) if K > 0 else None,
            'tipo': 'Rice (hay componente dominante)' if K > 1 else 'Rayleigh (sin LOS dominante)',
            'lambda_cm': lam * 100, 'span_lambda': float(np.ptp(pos) / lam)}


# ---------------------------------------------------------------------------
# histograma_envolvente
# Computacional: histograma normalizado a densidad de la envolvente y las curvas teóricas
#   Rayleigh y Rice(K estimado) evaluadas en el mismo eje.
# Matemática/física: densidad empírica ≈ pdf si hay suficientes muestras. La comparación
#   visual indica qué modelo describe mejor el canal medido.
def histograma_envolvente(p_db, bins=12):
    r = envolvente_normalizada(p_db)
    dens, edges = np.histogram(r, bins=bins, range=(0, max(2.2, float(r.max()) * 1.05)), density=True)
    c = 0.5 * (edges[1:] + edges[:-1])
    K = estimar_k_rice(p_db)
    rr = np.linspace(0.005, edges[-1], 120)
    return {'centros': c.tolist(), 'densidad': dens.tolist(), 'ancho': float(edges[1] - edges[0]),
            'r': rr.tolist(), 'rayleigh': pdf_rayleigh(rr).tolist(),
            'rice': pdf_rice(rr, K).tolist(), 'K': K}
