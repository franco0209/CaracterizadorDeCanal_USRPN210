"""Análisis comparativo final (módulo 07, punto 2.6).

Responde: ¿cuánto pesa cada fenómeno?, ¿en qué escala ocurre?, ¿se arregla con potencia
o requiere procesamiento de señal?
"""
import numpy as np


COMPENSACION = {
    'distancia': ('Hardware', 'Subir potencia TX, ganancia RX o usar antenas directivas: la señal solo pierde energía y conserva su forma.'),
    'obstruccion': ('Hardware', 'Reubicar o subir ganancia/potencia: es una pérdida adicional de energía; la forma de la señal se mantiene.'),
    'fading': ('Parcial / DSP', 'Subir potencia solo da margen de fade (decenas de dB, ineficiente). Se mitiga con diversidad de antenas, codificación y entrelazado.'),
    'multitrayectoria': ('DSP', 'Más potencia solo amplifica también los ecos (ISI). Requiere ecualización, OFDM o receptor RAKE.'),
}


# ---------------------------------------------------------------------------
# comparar_efectos
# Computacional: arma una fila por fenómeno con su magnitud en dB, su escala espacial y
#   la forma de compensarlo. Usa lo medido en los módulos 04–06; las filas sin datos
#   se marcan como pendientes.
# Matemática/física: magnitudes comparables en dB:
#   · distancia   : 10·n·log10(d_max/d_min) (pérdida entre extremos medidos, escala m)
#   · obstrucción : máxima atenuación frente a LOS (escala: la que ocupa el obstáculo)
#   · fading      : pico-a-pico de la potencia al mover el RX (escala: cm, ~λ/2)
#   · multitrayec.: rizado en frecuencia del canal |H(f)|; su origen es dispersión de
#                   retardo στ (selectividad), no pérdida de energía.
def comparar_efectos(dist=None, obst=None, fad=None, canal=None):
    filas = []

    def fila(clave, nombre, escala, mag, detalle):
        tipo, como = COMPENSACION[clave]
        filas.append({'clave': clave, 'efecto': nombre, 'escala': escala, 'mag_db': mag,
                      'detalle': detalle, 'tipo': tipo, 'como': como})

    if dist:
        fila('distancia', 'Distancia (pérdida de propagación)', 'metros',
             float(10 * dist['n'] * np.log10(dist['d_max'] / dist['d_min'])),
             f"n = {dist['n']:.2f}, σ = {dist['sigma']:.1f} dB, de {dist['d_min']:g} a {dist['d_max']:g} m")
    else:
        fila('distancia', 'Distancia (pérdida de propagación)', 'metros', None, 'sin datos (módulo 04)')
    if obst:
        peor = max(obst, key=lambda r: r['atenuacion_db'])
        fila('obstruccion', 'Obstrucciones (sombra)', 'tamaño del obstáculo', float(peor['atenuacion_db']),
             f"peor caso: {peor['cond']} ({peor['atenuacion_db']:.1f} dB)")
    else:
        fila('obstruccion', 'Obstrucciones (sombra)', 'tamaño del obstáculo', None, 'sin datos (módulo 05)')
    if fad:
        fila('fading', 'Desvanecimiento a pequeña escala', f"≈ λ/2 = {fad['lambda_cm'] / 2:.1f} cm",
             float(fad['pico_pico_db']),
             f"σ = {fad['sigma_db']:.1f} dB, fade máx = {fad['fade_max_db']:.1f} dB, K = {fad['K']:.1f} ({fad['tipo']})")
    else:
        fila('fading', 'Desvanecimiento a pequeña escala', '≈ λ/2', None, 'sin datos (módulo 06a)')
    if canal:
        fila('multitrayectoria', 'Multitrayectoria (selectividad)', 'ns (retardo de ecos)',
             float(canal['rizado_db']),
             f"στ = {canal['tau_rms_ns']:.0f} ns, B_c ≈ {canal['bc_mhz']:.2f} MHz, {canal['n_comp']} componentes")
    else:
        fila('multitrayectoria', 'Multitrayectoria (selectividad)', 'ns', None, 'sin datos (módulo 06b)')
    return filas
