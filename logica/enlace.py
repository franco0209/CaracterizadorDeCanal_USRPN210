"""Verificación de la conexión (módulo 00): convierte mediciones en un diagnóstico.

Cada paso del diagnóstico es {'paso', 'estado': ok|warn|ko, 'detalle'}.
"""
import numpy as np


def _p(paso, estado, detalle):
    return {'paso': paso, 'estado': estado, 'detalle': detalle}


# ---------------------------------------------------------------------------
# evaluar_dispositivo
# Computacional: traduce el resultado de sondear un USRP (ping, descubrimiento UHD,
#   apertura) en pasos de checklist.
# Matemática/física: no hay física aquí, es capa de enlace de datos: el N210 se maneja por
#   Gigabit Ethernet (UDP) con IP fija 192.168.10.2; sin ping o sin descubrimiento UHD
#   no hay muestras I/Q posibles.
def evaluar_dispositivo(nombre, s):
    out = [_p(f'{nombre}: red (ping)', 'ok' if s.get('ping') else 'ko',
              'responde' if s.get('ping') else 'sin respuesta: revisa cable, IP del PC (192.168.10.x) y alimentación')]
    out.append(_p(f'{nombre}: descubrimiento UHD', 'ok' if s.get('uhd') else 'ko',
                  s.get('uhd_info') or 'uhd_find_devices no lo ve'))
    if s.get('abre') is not None:
        out.append(_p(f'{nombre}: apertura / reloj', 'ok' if s['abre'] else 'ko',
                      s.get('detalle') or ''))
    return out


# ---------------------------------------------------------------------------
# diagnosticar_captura
# Computacional: aplica umbrales a lo medido en una captura: nivel ADC, piso de ruido,
#   tasa de detección, SNR, CFO, estabilidad y coincidencia del periodo con el configurado.
# Matemática/física:
#   · ADC: pico≈1 o %sat>0.1 ⇒ recorte (no lineal). Pico<0.02 ⇒ señal baja (poca resolución).
#   · SNR ≥ 15 dB ⇒ la resta P_total−P_ruido es fiable; 6–15 dB ⇒ válida pero sensible;
#     <6 dB ⇒ medida en el piso de ruido (se estaría midiendo ruido).
#   · CFO debe quedar bajo fs/(2N) (rango unívoco del estimador); fuera de él, el
#     sincronismo falla aunque haya señal.
#   · Estabilidad: si P fluctúa >3 dB entre ráfagas el enlace no es estático (movimiento,
#     interferencia) y los promedios pierden sentido.
def diagnosticar_captura(med, cfg):
    d = []
    pico, sat = med['pico'], med['sat_pct']
    if sat > 0.1:
        d.append(_p('Nivel ADC', 'ko', f'saturado ({sat:.2f} % de muestras): baja la ganancia RX o TX'))
    elif pico > 0.9:
        d.append(_p('Nivel ADC', 'warn', f'pico {pico:.2f}: muy cerca de saturar'))
    elif pico < 0.02:
        d.append(_p('Nivel ADC', 'warn', f'pico {pico:.3f}: señal baja, usas pocos bits del ADC (sube la ganancia RX si el SNR es bajo)'))
    else:
        d.append(_p('Nivel ADC', 'ok', f'pico {pico:.2f}, saturación {sat:.2f} %'))

    d.append(_p('Piso de ruido', 'warn' if med['ruido_dbfs'] > -50 else 'ok',
                f"{med['ruido_dbfs']:.1f} dBFS" + (' (alto: interferencia o ganancia excesiva)' if med['ruido_dbfs'] > -50 else '')))
    if med['dc_dbfs'] > med['ruido_dbfs'] + 10:
        d.append(_p('Offset DC', 'warn', f"{med['dc_dbfs']:.1f} dBFS: portadora residual del LO; se resta automáticamente"))

    rafs = med['rafagas']
    if not rafs:
        d.append(_p('Detección de ráfagas', 'ko', 'no se detectó ninguna: revisa que ambos equipos usen los mismos parámetros'))
        return d
    tasa = med['n_det'] / med['n_esp']
    d.append(_p('Detección de ráfagas', 'ok' if tasa >= 0.8 else 'warn',
                f"{med['n_det']} detectadas de ≈{med['n_esp']} esperadas ({100 * min(tasa, 1):.0f} %)"))

    snr = float(np.mean([r['snr_db'] for r in rafs]))
    d.append(_p('SNR por ráfaga', 'ok' if snr >= 15 else 'warn' if snr >= 6 else 'ko',
                f'{snr:.1f} dB' + ('' if snr >= 15 else ' — medida cercana al piso de ruido')))

    cfo = float(np.mean([r['cfo_hz'] for r in rafs]))
    lim = cfg.rango_cfo_hz
    d.append(_p('Offset de frecuencia (CFO)', 'ok' if abs(cfo) < 0.7 * lim else 'warn',
                f'{cfo:+.0f} Hz (rango unívoco ±{lim:.0f} Hz)'))

    std = float(np.std([r['p_dbfs'] for r in rafs])) if len(rafs) > 1 else 0.0
    d.append(_p('Estabilidad del enlace', 'ok' if std < 1 else 'warn' if std < 3 else 'ko',
                f'σ = {std:.2f} dB entre ráfagas'))

    if len(rafs) >= 3:
        dt = float(np.median(np.diff([r['t_ms'] for r in rafs])))
        ok = abs(dt - cfg.periodo_ms) / cfg.periodo_ms < 0.05
        d.append(_p('Parámetros TX = RX', 'ok' if ok else 'warn',
                    f'periodo medido {dt:.2f} ms vs configurado {cfg.periodo_ms:.2f} ms'
                    + ('' if ok else ' — ¿el TX usa otro periodo?')))
    return d


# ---------------------------------------------------------------------------
# veredicto
# Computacional: resume la lista en 'ko' si algún paso falla, 'warn' si hay avisos, si no 'ok'.
# Matemática/física: criterio de "listo para medir": todos los pasos ok.
def veredicto(pasos):
    estados = [p['estado'] for p in pasos]
    return 'ko' if 'ko' in estados else 'warn' if 'warn' in estados else 'ok'
