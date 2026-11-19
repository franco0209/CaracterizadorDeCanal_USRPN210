"""Efecto de las obstrucciones a distancia fija (módulo 05, punto 2.3).

Cada registro de entrada es {'cond': nombre, 'p_db': media lineal en dBFS de esa
medición, 'std_db': dispersión entre ráfagas, 'n': nº de ráfagas}. La condición de
referencia (LOS) se llama 'LOS'.
"""
import numpy as np

from .parametros import a_db, de_db


# ---------------------------------------------------------------------------
# agrupar_por_condicion
# Computacional: junta los registros con la misma etiqueta; combina sus potencias
#   promediando en lineal ponderado por el nº de ráfagas y estima el error estándar de la
#   media (SEM = σ/√n) de cada condición.
# Matemática/física: varias repeticiones de la misma condición son muestras de la misma
#   variable aleatoria; la media en lineal es la potencia física media. El SEM indica
#   cuánto confiar en esa media: baja con √n.
def agrupar_por_condicion(registros):
    grupos = {}
    for r in registros:
        grupos.setdefault(r['cond'], []).append(r)
    out = []
    for cond, rs in grupos.items():
        w = np.array([max(1, r['n']) for r in rs], dtype=float)
        p_lin = np.sum(w * de_db(np.array([r['p_db'] for r in rs]))) / w.sum()
        std = float(np.sqrt(np.sum(w * np.array([r['std_db'] for r in rs]) ** 2) / w.sum()))
        n_tot = int(w.sum())
        out.append({'cond': cond, 'p_db': float(a_db(p_lin)), 'std_db': std,
                    'n': n_tot, 'sem_db': std / np.sqrt(n_tot)})
    return out


# ---------------------------------------------------------------------------
# atenuacion_vs_los
# Computacional: A_i = P_LOS − P_i para cada condición, con error combinado
#   sqrt(SEM_LOS² + SEM_i²); agrega la clasificación y la "distancia equivalente".
# Matemática/física: la obstrucción se modela como pérdida adicional L_obs (dB) por
#   sombra (shadowing): P_obs = P_LOS − L_obs. Si el entorno sigue el modelo con exponente
#   n, equivale a alejar el receptor en un factor 10^(L_obs/(10·n)): útil para entender
#   cuánto "cuesta" un muro en términos de alcance.
def atenuacion_vs_los(grupos, ref='LOS', n_ref=2.0):
    base = next((g for g in grupos if g['cond'] == ref), None)
    if base is None:
        return []
    filas = []
    for g in grupos:
        a = base['p_db'] - g['p_db']
        err = float(np.hypot(base['sem_db'], g['sem_db']))
        filas.append({**g, 'atenuacion_db': float(a), 'err_db': err,
                      'clase': 'referencia' if g['cond'] == ref else clasificar_atenuacion(a),
                      'factor_distancia': float(10 ** (a / (10 * n_ref)))})
    return filas


# ---------------------------------------------------------------------------
# clasificar_atenuacion
# Computacional: umbrales sobre la pérdida en dB.
# Matemática/física: referencia orientativa a 900 MHz: persona 3–8 dB, pared de ladrillo
#   5–15 dB, hormigón/metal >15–30 dB. Diferencias <~1–2 dB están dentro del fading y no
#   son significativas.
def clasificar_atenuacion(a_db_):
    if a_db_ < 2:
        return 'despreciable'
    if a_db_ < 6:
        return 'leve'
    if a_db_ < 12:
        return 'moderada'
    if a_db_ < 20:
        return 'fuerte'
    return 'severa'
