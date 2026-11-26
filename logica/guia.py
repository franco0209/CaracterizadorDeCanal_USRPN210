"""Modo guiado: qué se ESPERA de cada medida y si el resultado es creíble.

Cada validador devuelve {'estado', 'esperado', 'medido', 'pregunta'}:
    ok          el resultado es compatible con el paso físico pedido
    sospechoso  se aleja de lo esperado: se pregunta al usuario antes de aceptarlo
    invalido    la medida no sirve (sin SNR o saturada): hay que repetir
Las referencias son medidas ya aceptadas de la misma serie (mismos parámetros y fuente).
"""
import numpy as np

# Atenuación orientativa a ~900 MHz: (típico mín, típico máx, aceptado mín, aceptado máx) en dB
MATERIALES = {
    'Madera':  (2, 6, 1.5, 11),
    'Puerta':  (2, 7, 1.5, 13),
    'Vidrio':  (1, 4, 0.5, 10),
    'Persona': (3, 10, 2.0, 18),
    'Pared':   (5, 15, 3.0, 24),
    'Metal':   (10, 30, 7.0, 45),
}
OTRO_MATERIAL = (2, 20, 1.5, 35)

TOL_DIST_DB = 6.0       # desvío admitido frente al modelo log-distancia (sombreado interior)
TOL_REPETIR_DB = 3.0    # misma geometría medida dos veces
VENTANA_FAD = 6         # posiciones seguidas sin cambios => el RX no se está moviendo
RANGO_QUIETO_DB = 0.5


def _res(estado, esperado, medido, pregunta=None):
    return {'estado': estado, 'esperado': esperado, 'medido': medido, 'pregunta': pregunta}


# ---------------------------------------------------------------------------
# calidad
# Computacional: filtro previo a cualquier comparación: SNR y saturación.
# Matemática/física: bajo ~6 dB de SNR se mide ruido; con el ADC recortado la potencia
#   deja de ser proporcional a la recibida. En ambos casos no hay nada que comparar.
def calidad(pt):
    if pt['sat_pct'] >= 0.1:
        return _res('invalido', 'ADC sin saturar', f"{pt['sat_pct']:.2f} % de muestras saturadas",
                    'El receptor está saturado: baja la ganancia o separa más las antenas y repite.')
    if not pt['valido']:
        return _res('invalido', 'SNR ≥ 6 dB', f"SNR {pt['snr_db']:.1f} dB",
                    'La señal está en el piso de ruido. ¿Sigue transmitiendo el TX y están puestas las antenas?')
    return None


# ---------------------------------------------------------------------------
# prediccion_distancia
# Computacional: toma como referencia la medida aceptada más cercana en log(d) y
#   extrapola con el exponente ajustado (si hay ≥3 distancias y es plausible) o con n=2.
# Matemática/física: P(d) = P(d_ref) − 10·n·log10(d/d_ref). Solo se predicen diferencias,
#   así que no hace falta calibrar la potencia absoluta.
def prediccion_distancia(refs, d):
    if not refs:
        return None
    n = 2.0
    ds = [r['d'] for r in refs]
    if len(set(ds)) >= 3:
        m = float(np.polyfit(-10 * np.log10(ds), [r['p_db'] for r in refs], 1)[0])
        if 1.5 <= m <= 4.5:
            n = m
    cerca = min(abs(np.log(d / x)) for x in ds)
    grupo = [r for r in refs if abs(np.log(d / r['d'])) <= cerca + 1e-9]
    d_ref = grupo[0]['d']
    p_ref = float(np.mean([r['p_db'] for r in grupo if r['d'] == d_ref]))
    tol = TOL_REPETIR_DB if abs(d - d_ref) < 1e-9 else TOL_DIST_DB
    return {'p': p_ref - 10 * n * np.log10(d / d_ref), 'tol': tol, 'n': n, 'd_ref': d_ref, 'p_ref': p_ref}


# ---------------------------------------------------------------------------
# validar_distancia
# Computacional: además de la tolerancia, comprueba el SENTIDO del cambio y que no se
#   haya quedado igual tras un salto grande de distancia.
# Matemática/física: duplicar la distancia cuesta ≈6 dB (n=2); si la potencia casi no
#   cambia o sube, lo más probable es que el RX no se haya movido (o haya un eco fuerte).
def validar_distancia(pt, refs, d):
    mal = calidad(pt)
    if mal:
        if refs and pt['sat_pct'] < 0.1 and d > max(r['d'] for r in refs):
            mal['pregunta'] = (f'A {d:g} m la señal cae al piso de ruido: está fuera del alcance del enlace. Comprueba '
                               'las antenas; si están bien, salta este punto o usa una distancia menor.')
        return mal
    medido = f"{pt['p_db']:.1f} dB a {d:g} m"
    pr = prediccion_distancia(refs, d)
    if pr is None:
        return _res('ok', 'primera medida: queda como referencia', medido)
    esperado = f"{pr['p']:.1f} ± {pr['tol']:.0f} dB (desde {pr['p_ref']:.1f} dB a {pr['d_ref']:g} m, n = {pr['n']:.1f})"
    razon = d / pr['d_ref']
    cambio = pt['p_db'] - pr['p_ref']
    pregunta = None
    if razon >= 1.4 and cambio > 3:
        pregunta = f'Alejaste el RX y la potencia SUBIÓ {cambio:.1f} dB. ¿Seguro que está a {d:g} m?'
    elif razon <= 1 / 1.4 and cambio < -3:
        pregunta = f'Acercaste el RX y la potencia BAJÓ {-cambio:.1f} dB. ¿Seguro que está a {d:g} m?'
    elif (razon >= 1.8 or razon <= 1 / 1.8) and abs(cambio) < 1.5:
        pregunta = f'La potencia casi no cambió ({cambio:+.1f} dB). ¿Seguro que moviste el RX a {d:g} m?'
    elif abs(pt['p_db'] - pr['p']) > pr['tol']:
        pregunta = (f"El resultado está a {pt['p_db'] - pr['p']:+.1f} dB de lo esperado. "
                    f'¿Seguro que el RX está a {d:g} m, con las antenas igual que antes y sin nada en medio?')
    return _res('sospechoso' if pregunta else 'ok', esperado, medido, pregunta)


# ---------------------------------------------------------------------------
# validar_obstruccion
# Computacional: atenuación A = P_LOS − P comparada con el rango del material.
# Matemática/física: un obstáculo solo puede restar energía de forma apreciable; si A≈0
#   no está interrumpiendo el camino, y si A es enorme probablemente cambió la geometría.
def validar_obstruccion(pt, refs_los, cond):
    mal = calidad(pt)
    if mal:
        if cond != 'LOS' and refs_los and pt['sat_pct'] < 0.1:
            margen = float(np.mean([r['snr_db'] for r in refs_los])) - pt['snr_db']
            mal['pregunta'] = (f'La señal cayó al piso de ruido (atenuación de unos {margen:.0f} dB o más). Revisa que no '
                               'se soltara una antena. Si todo está bien, el obstáculo bloquea demasiado: acorta la '
                               'distancia de esta fase, vuelve a medir LOS y repite.')
        return mal
    base = float(np.mean([r['p_db'] for r in refs_los])) if refs_los else None
    if cond == 'LOS':
        medido = f"{pt['p_db']:.1f} dB"
        if base is None:
            return _res('ok', 'referencia sin obstáculo', medido)
        dif = pt['p_db'] - base
        esperado = f'{base:.1f} ± {TOL_REPETIR_DB:.0f} dB (igual que el LOS anterior)'
        if abs(dif) > TOL_REPETIR_DB:
            return _res('sospechoso', esperado, medido,
                        f'El LOS cambió {dif:+.1f} dB. ¿Quitaste todo obstáculo y dejaste TX y RX donde estaban?')
        return _res('ok', esperado, medido)
    if base is None:
        return _res('invalido', 'una referencia LOS', 'no hay LOS', 'Primero mide la condición sin obstáculo (LOS).')
    t0, t1, lo, hi = MATERIALES.get(cond, OTRO_MATERIAL)
    a = base - pt['p_db']
    esperado = f'atenuación típica {t0}–{t1} dB (aceptado {lo:g}–{hi:g} dB)'
    medido = f'{a:+.1f} dB de atenuación'
    nombre = cond.lower()
    pregunta = None
    if a < lo:
        pregunta = (f'La señal casi no bajó ({a:+.1f} dB). ¿Seguro que pusiste el obstáculo de {nombre} '
                    'justo entre las dos antenas?')
    elif a > hi:
        pregunta = (f'La señal bajó demasiado para {nombre} ({a:.1f} dB). ¿Moviste el TX o el RX, '
                    'o se soltó una antena?')
    return _res('sospechoso' if pregunta else 'ok', esperado, medido, pregunta)


# ---------------------------------------------------------------------------
# validar_fading
# Computacional: salto enorme respecto a la posición anterior, o `VENTANA_FAD` posiciones
#   seguidas prácticamente idénticas. Una posición ya confirmada reinicia la ventana.
# Matemática/física: a pasos de λ/8 el campo de interferencia varía suavemente pero varía;
#   una serie plana a lo largo de ~0.75 λ indica que el RX no se desplaza.
def validar_fading(pt, previas, paso_cm):
    mal = calidad(pt)
    if mal:
        return mal
    medido = f"{pt['p_db']:.1f} dB"
    previas = sorted((r for r in previas if r['idx'] < pt['idx']), key=lambda r: r['idx'])
    if not previas:
        return _res('ok', 'primera posición: referencia', medido)
    esperado = f'cambios graduales al avanzar {paso_cm:.1f} cm (no totalmente plano)'
    salto = pt['p_db'] - previas[-1]['p_db']
    if previas[-1]['idx'] == pt['idx'] - 1 and abs(salto) > 25:
        return _res('sospechoso', esperado, medido,
                    f'Salto de {salto:+.1f} dB en un solo paso. ¿Moviste solo el RX, sin tocar el TX ni las antenas?')
    ult = previas[-(VENTANA_FAD - 1):]
    if len(ult) == VENTANA_FAD - 1 and not any(r.get('confirmado_por_usuario') for r in ult):
        rango = float(np.ptp([r['p_db'] for r in ult] + [pt['p_db']]))
        if rango < RANGO_QUIETO_DB:
            return _res('sospechoso', esperado, medido,
                        f'Las últimas {VENTANA_FAD} posiciones casi no cambian ({rango:.2f} dB). '
                        f'¿Seguro que estás moviendo el RX {paso_cm:.1f} cm en cada paso?')
    return _res('ok', esperado, medido)


# ---------------------------------------------------------------------------
# validar_canal
# Computacional: en LOS exige un camino dominante; en multitrayectoria exige que la
#   dispersión de retardo o el rizado en frecuencia crezcan respecto a LOS.
# Matemática/física: σ_τ y el rizado de |H(f)| miden cuánta energía llega por ecos.
def validar_canal(pt, los, esc):
    mal = calidad(pt)
    if mal:
        return mal
    tau, riz = pt['disp']['tau_rms_ns'], pt['rizado_db']
    medido = f'σ_τ = {tau:.0f} ns · rizado {riz:.1f} dB'
    if esc == 'los':
        esperado = 'un camino dominante: canal casi plano (rizado < 8 dB)'
        if riz >= 8:
            return _res('sospechoso', esperado, medido,
                        'Se ven ecos fuertes. ¿Seguro que hay línea de vista despejada, sin metal cerca de las antenas?')
        return _res('ok', esperado, medido)
    if los is None:
        return _res('invalido', 'una referencia LOS', 'no hay LOS', 'Primero estima el canal en línea de vista.')
    t0, r0 = los['disp']['tau_rms_ns'], los['rizado_db']
    esperado = f'más dispersión que en LOS (σ_τ > {t0 + 30:.0f} ns o rizado > {r0 + 2:.1f} dB)'
    if tau <= t0 + 30 and riz <= r0 + 2:
        return _res('sospechoso', esperado, medido,
                    'El canal se ve casi igual que en LOS. ¿Seguro que estás en un lugar reflectante (metal, pasillo, '
                    f"esquinas)? Con esta fs, ecos de menos de {pt['resol_ns']:.0f} ns no se separan.")
    return _res('ok', esperado, medido)
