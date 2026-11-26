"""Práctica 3 - Caracterización del canal inalámbrico con SDR (USRP N210). GUI pywebview.

    python3 app.py            (DEBUG=1 python3 app.py abre el inspector web)

Este archivo solo orquesta: recibe pedidos de la interfaz (web/), maneja el hardware
(radio.py) y llama a la física/matemática que vive en logica/. No contiene algoritmos de
comunicaciones: para estudiarlos, leer logica/ (ver logica/__init__.py).
"""
import base64
import csv
import ipaddress
import json
import os
import shutil
import subprocess
import time
import traceback

import numpy as np
import webview

import radio
from logica import analisis as an
from logica import canal as ca
from logica import desvanecimiento as fd
from logica import enlace as en
from logica import guia as gu
from logica import obstrucciones as ob
from logica import parametros as pa
from logica import potencia as po
from logica import propagacion as pr
from logica import senal_prueba as sp
from logica import simulador as sm

AQUI = os.path.dirname(os.path.abspath(__file__))
MED = os.path.join(AQUI, 'mediciones')
IQ_DIR = os.path.join(MED, 'iq')
EXPORT = os.path.join(AQUI, 'exportados')
RESULTADOS = os.path.join(MED, 'resultados.json')
SNR_MIN_VALIDO = 6.0          # bajo este SNR la medida está en el piso de ruido
INTERP = 8                    # factor de interpolación de la respuesta del canal

DEFAULTS = {
    # --- parámetros globales (regla de oro: constantes durante toda la práctica)
    'fc': 915e6, 'fs': 5e6, 'n_zc': 127, 'raiz': 5, 'n_rep': 8, 'periodo_ms': 20,
    'amp': 0.7, 'gain_tx': 15, 'gain_rx': 20, 'cal_db': 0, 'umbral': 0.5, 'duracion_ms': 100,
    # --- conexión
    'tx_hw': 'ninguno', 'ip_tx': '192.168.10.2', 'rx_hw': 'sim', 'ip_rx': '192.168.10.3',
    'archivo_rx': '',
    # --- canal simulado
    'sim_pref': -35, 'sim_n': 2.7, 'sim_sigma': 3.0, 'sim_ruido': -75, 'sim_cfo': 1500,
    'rx_dist_sim': 1,
    # --- módulos de medida
    'n_caps': 5, 'dist_m': 2, 'obst_cond': 'LOS', 'obst_dist': 4, 'obst_sim_db': 8,
    'fad_dist': 3, 'fad_esc': 'nlos', 'fad_idx': 0, 'fad_nlam': 5, 'fad_frac': 8,
    'canal_esc': 'los', 'canal_dist': 3, 'canal_tab': 'fad',
}


# ------------------------------------------------------------------ utilidades
def _r(v, nd=4):
    return [round(float(a), nd) for a in np.asarray(v).ravel()]


def _num(v):
    """float NaN/inf -> None (JSON)."""
    if v is None:
        return None
    v = float(v)
    return v if np.isfinite(v) else None


def _dec_max(v, n=1500):
    v = np.asarray(v)
    if v.size <= n:
        return v, 1
    b = v.size // n
    return v[:b * n].reshape(n, b).max(axis=1), b


def _cfg(p):
    return pa.Config(p)


def _firma(p):
    """Parámetros que NO deben cambiar dentro de una serie de medidas."""
    return (f"fc={p['fc'] / 1e6:g}M fs={p['fs'] / 1e6:g}M Gtx={p['gain_tx']} Grx={p['gain_rx']} "
            f"amp={p['amp']} ZC={p['n_zc']}/{p['raiz']}x{p['n_rep']} T={p['periodo_ms']}ms")


class Api:
    def __init__(self):
        os.makedirs(IQ_DIR, exist_ok=True)
        os.makedirs(EXPORT, exist_ok=True)
        self._tx = radio.TransmisorUSRP()
        self._rx = radio.ReceptorUSRP()
        self._rng = np.random.default_rng()
        self._ultima = None                      # última captura (módulo 03)
        self._db = self._cargar()

    # ================================================================ persistencia
    def _cargar(self):
        base = {'distancia': [], 'obstruccion': [], 'fading': [], 'canal': {}}
        try:
            with open(RESULTADOS) as f:
                base.update(json.load(f))
        except Exception:
            pass
        return base

    def _guardar(self):
        with open(RESULTADOS, 'w') as f:
            json.dump(self._db, f, indent=1, default=_num)

    def defaults(self):
        return DEFAULTS

    def elegir_archivo(self):
        r = webview.windows[0].create_file_dialog(webview.FileDialog.OPEN)
        return r[0] if r else None

    # ================================================================ 01 señal de prueba
    def info_senal(self, p):
        try:
            cfg = _cfg(p)
            zc = sp.zadoff_chu(cfg.n_zc, cfg.raiz)
            raf = sp.construir_rafaga(cfg)
            per = sp.construir_periodo(cfg)
            tren = np.abs(np.tile(per, 3))
            tren_d, b = _dec_max(tren, 1200)
            lags, mf = sp.salida_filtro_adaptado(raf, zc)
            f, psd = sp.psd_welch(np.tile(per, max(2, 4096 // per.size + 1)), cfg.fs)
            k = np.arange(cfg.n_zc)
            ac = sp.autocorrelacion_periodica_db(zc)
            n_show = min(per.size, 3 * cfg.n_zc)
            return {'ok': True, 'resumen': cfg.resumen(),
                    'zc': {'k': _r(k, 0), 'i': _r(zc.real), 'q': _r(zc.imag),
                           'fase': _r(np.unwrap(np.angle(zc)))},
                    'tren': {'t': _r(np.arange(tren_d.size) * b / cfg.fs * 1e3, 3), 'v': _r(tren_d)},
                    'mf': {'lag': _r(lags, 0), 'db': _r(20 * np.log10(mf / mf.max() + 1e-9), 2)},
                    'acorr': {'lag': _r(np.arange(cfg.n_zc), 0), 'db': _r(ac, 2)},
                    'psd': {'f': _r(f / 1e3, 2), 'db': _r(psd - psd.max(), 2)},
                    'tiempo': {'t': _r(np.arange(n_show) / cfg.fs * 1e6, 3), 'i': _r(per[:n_show].real),
                               'q': _r(per[:n_show].imag)}}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    # ================================================================ adquisición
    def _adquirir(self, p, ctx):
        """Una captura de duracion_ms. En 'sim' el canal depende del contexto físico `ctx`."""
        cfg = _cfg(p)
        n = int(float(p['duracion_ms']) * 1e-3 * cfg.fs)
        hw = p['rx_hw']
        if hw == 'sim':
            pot = sm.potencia_modelo_dbfs(float(ctx.get('d', 3)), float(p['sim_pref']), float(p['sim_n']),
                                          float(ctx.get('sombra', 0)), float(ctx.get('obst', 0)),
                                          float(p['gain_tx']), float(p['gain_rx']))
            x = sm.generar_captura(cfg, n, pot, ctx.get('esc', 'los'), float(ctx.get('pos', 0)),
                                   float(p['sim_ruido']), float(p['sim_cfo']), self._rng)
            return x, {'hw': 'sim', 'overflow': 0}
        if hw == 'archivo':
            ruta = p.get('archivo_rx')
            if not ruta or not os.path.isfile(ruta):
                raise ValueError('Elige un archivo .npy con muestras I/Q')
            x = np.load(ruta).astype(np.complex128).ravel()
            return x, {'hw': 'archivo', 'overflow': 0}
        x, info = radio.capturar(self._rx, 'usrp', float(p['fc']), cfg.fs, float(p['gain_rx']), n,
                                 {'ip': p['ip_rx']})
        return x, info

    def _sombra(self, p, ctx):
        if 'sombra' not in ctx:
            ctx['sombra'] = float(self._rng.normal(0, float(p['sim_sigma'])))
        return ctx

    def _medir_punto(self, p, ctx, n_caps, etiqueta, con_canal=False):
        """n_caps capturas → todas las ráfagas detectadas → potencia agregada del punto."""
        cfg = _cfg(p)
        ctx = self._sombra(p, dict(ctx)) if p['rx_hw'] == 'sim' else dict(ctx)
        pid = f"{etiqueta}_{time.strftime('%H%M%S')}_{int(self._rng.integers(1000, 9999))}"
        ps, snrs, cfos, ruidos, picos, sats, ov = [], [], [], [], [], [], 0
        pdp_sum, raw_sum, n_pdp, h_ref, segs = None, None, 0, None, []
        for k in range(int(n_caps)):
            x, info = self._adquirir(p, ctx)
            ov += info.get('overflow', 0)
            m = po.medir_captura(x, cfg, float(p['umbral']))
            ruidos.append(m['ruido_dbfs']); picos.append(m['pico']); sats.append(m['sat_pct'])
            xs = x - np.mean(x)
            segs += [xs[r['inicio'] - cfg.n_zc:r['inicio'] + cfg.n_rafaga + cfg.n_zc].astype(np.complex64)
                     for r in m['rafagas']
                     if r['inicio'] >= cfg.n_zc and r['inicio'] + cfg.n_rafaga + cfg.n_zc <= xs.size]
            for r in m['rafagas']:
                ps.append(r['p_dbfs']); snrs.append(r['snr_db']); cfos.append(r['cfo_hz'])
                if con_canal:
                    h = ca.estimar_respuesta_canal(xs, r['inicio'], r['cfo_hz'], cfg)
                    h, pre = ca.alinear_camino_principal(h)
                    if h_ref is None:
                        h_ref = h
                    pdp = np.abs(ca.interpolar_respuesta(h, INTERP)) ** 2
                    raw = np.abs(h) ** 2
                    pdp_sum = pdp if pdp_sum is None else pdp_sum + pdp
                    raw_sum = raw if raw_sum is None else raw_sum + raw
                    n_pdp += 1
        if not ps:
            raise ValueError('No se detectó ninguna ráfaga. Revisa TX, ganancias, frecuencia y umbral (módulo 00).')
        # IQ crudo compacto: solo las ráfagas (±N muestras) + el piso de ruido medido
        if segs:
            np.savez(os.path.join(IQ_DIR, f'{pid}.npz'), rafagas=np.array(segs), fs=cfg.fs, fc=float(p['fc']),
                     ruido_dbfs=float(np.mean(ruidos)), n_zc=cfg.n_zc, raiz=cfg.raiz, n_rep=cfg.n_rep)
        res = po.resumen_potencias(ps)
        out = {'id': pid, 'ts': time.strftime('%H:%M:%S'), 'p_db': res['media_db'] + float(p['cal_db']),
               'std_db': res['std_db'], 'n': res['n'], 'snr_db': float(np.mean(snrs)),
               'cfo_hz': float(np.mean(cfos)), 'ruido_dbfs': float(np.mean(ruidos)),
               'pico': float(max(picos)), 'sat_pct': float(max(sats)), 'overflow': ov,
               'valido': bool(np.mean(snrs) >= SNR_MIN_VALIDO and max(sats) < 0.1),
               'firma': _firma(p), 'sombra_sim': ctx.get('sombra'), 'hw': p['rx_hw']}
        if con_canal:
            out['_pdp'] = pdp_sum / n_pdp
            out['_raw'] = raw_sum / n_pdp
            out['_h'] = h_ref
        return out

    # ================================================================ 00 conexión
    def verificar(self, p, modo):
        """modo: 'tx' | 'rx' | 'enlace'"""
        try:
            cfg = _cfg(p)
            pasos = []
            if modo in ('tx', 'enlace'):
                if p['tx_hw'] == 'usrp':
                    pasos += en.evaluar_dispositivo('TX', radio.sonda_dispositivo(p['ip_tx']))
                else:
                    pasos.append({'paso': 'TX en este PC', 'estado': 'warn',
                                  'detalle': 'sin USRP TX local: se asume que otro equipo transmite'})
            if modo in ('rx', 'enlace'):
                if p['rx_hw'] == 'usrp':
                    pasos += en.evaluar_dispositivo('RX', radio.sonda_dispositivo(p['ip_rx']))
                elif p['rx_hw'] == 'sim':
                    pasos.append({'paso': 'RX', 'estado': 'warn', 'detalle': 'fuente SIMULADA (sin hardware)'})
                else:
                    pasos.append({'paso': 'RX', 'estado': 'warn', 'detalle': 'fuente ARCHIVO'})
            res = {'ok': True, 'pasos': pasos}
            hw_ko = any(s['estado'] == 'ko' for s in pasos)
            if modo == 'enlace' and not hw_ko:
                auto = p['tx_hw'] == 'usrp' and not self._tx.estado['activo']
                if auto:
                    self._tx.iniciar(sp.construir_periodo(cfg), float(p['fc']), cfg.fs, float(p['gain_tx']),
                                     p['ip_tx'], 0)
                    time.sleep(1.0)
                try:
                    x, info = self._adquirir(p, {'d': float(p['rx_dist_sim']), 'sombra': 0})
                finally:
                    if auto:
                        self._tx.detener()
                m = po.medir_captura(x, cfg, float(p['umbral']))
                pasos += en.diagnosticar_captura(m, cfg)
                if info.get('overflow'):
                    pasos.append({'paso': 'Overflows RX', 'estado': 'warn',
                                  'detalle': f"{info['overflow']}: baja fs o cierra otros programas"})
                res.update(self._graficas_captura(x, m, cfg))
                rs = m['rafagas']
                res['kpis'] = {'ruido': m['ruido_dbfs'], 'pico': m['pico'], 'sat': m['sat_pct'],
                               'n_det': m['n_det'], 'n_esp': m['n_esp'],
                               'snr': float(np.mean([r['snr_db'] for r in rs])) if rs else None,
                               'cfo': float(np.mean([r['cfo_hz'] for r in rs])) if rs else None,
                               'p': float(np.mean([r['p_dbfs'] for r in rs])) if rs else None}
            res['veredicto'] = en.veredicto(pasos)
            return res
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    def _graficas_captura(self, x, m, cfg):
        env, b = _dec_max(np.abs(x))
        M, bm = _dec_max(m['M'])
        f, psd = sp.psd_welch(x - np.mean(x), cfg.fs)
        return {'env': {'t': _r(np.arange(env.size) * b / cfg.fs * 1e3, 3), 'v': _r(env)},
                'metrica': {'t': _r(np.arange(M.size) * bm / cfg.fs * 1e3, 3), 'v': _r(M), 'umbral': m['umbral']},
                'marcas': _r([r['t_ms'] for r in m['rafagas']], 3),
                'psd': {'f': _r(f / 1e3, 1), 'db': _r(psd, 2)}}

    # ================================================================ 02 transmisor
    def tx_iniciar(self, p):
        try:
            cfg = _cfg(p)
            if p['tx_hw'] != 'usrp':
                return {'ok': False, 'error': 'Selecciona "USRP" como transmisor en el módulo 00.'}
            self._tx.iniciar(sp.construir_periodo(cfg), float(p['fc']), cfg.fs, float(p['gain_tx']),
                             p['ip_tx'], int(p.get('repeticiones', 0)))
            return {'ok': True, 'msg': f'Transmitiendo una ráfaga cada {cfg.periodo_ms:g} ms'}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def tx_detener(self):
        self._tx.detener()
        return self._tx.estado

    def tx_estado(self):
        return self._tx.estado

    # ================================================================ 03 receptor
    def rx_capturar(self, p):
        try:
            cfg = _cfg(p)
            t0 = time.time()
            x, info = self._adquirir(p, {'d': float(p['rx_dist_sim']), 'sombra': 0})
            t1 = time.time()
            m = po.medir_captura(x, cfg, float(p['umbral']))
            self._ultima = (x, m, cfg)
            res = {'ok': True, 't_captura': t1 - t0, 't_proceso': time.time() - t1,
                   'overflow': info.get('overflow', 0), 'ruido_dbfs': m['ruido_dbfs'], 'pico': m['pico'],
                   'sat_pct': m['sat_pct'], 'n_det': m['n_det'], 'n_esp': m['n_esp'],
                   'rafagas': [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}
                               for r in m['rafagas']]}
            res.update(self._graficas_captura(x, m, cfg))
            res['detalle'] = self._detalle(0) if m['rafagas'] else None
            return res
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    def rx_detalle(self, i):
        try:
            return self._detalle(int(i))
        except Exception as e:
            return None

    def _detalle(self, i):
        """Zoom de una ráfaga: I/Q, salida del filtro adaptado y fase tras quitar CFO."""
        from logica import deteccion as de
        x, m, cfg = self._ultima
        r = m['rafagas'][i]
        n, ini = cfg.n_zc, r['inicio']
        a, b = max(0, ini - 2 * n), min(x.size, ini + cfg.n_rafaga + 2 * n)
        xs = (x - np.mean(x))[a:b]
        zc = sp.zadoff_chu(n, cfg.raiz)
        mf = np.abs(np.correlate(xs, zc, mode='valid')) / n
        seg = de.derotar((x - np.mean(x))[ini:ini + cfg.n_rafaga], r['cfo_hz'], cfg.fs)
        c = np.array([np.vdot(zc, seg[k * n:(k + 1) * n]) / n for k in range(cfg.n_rep)])
        t = (np.arange(xs.size) + a - ini) / cfg.fs * 1e6
        return {'idx': i, 't_us': _r(t, 3), 'i': _r(xs.real, 5), 'q': _r(xs.imag, 5),
                't_mf_us': _r((np.arange(mf.size) + a - ini) / cfg.fs * 1e6, 3), 'mf': _r(mf, 5),
                'fase_copias': _r(np.degrees(np.angle(c)), 2), 'amp_copias': _r(np.abs(c), 5),
                'inicio_us': 0, 'fin_us': cfg.n_rafaga / cfg.fs * 1e6}

    # ================================================================ 04 distancia
    def dist_medir(self, p):
        try:
            d = float(p['dist_m'])
            ctx = {'d': d}
            if p.get('sim_olvido') and self._db['distancia']:          # simula no haber movido el RX
                ant = self._db['distancia'][-1]
                ctx = {'d': ant['d'], 'sombra': ant.get('sombra_sim') or 0.0}
            pt = self._medir_punto(p, ctx, p['n_caps'], 'd')
            pt['d'] = d
            self._db['distancia'].append(pt)
            self._guardar()
            return {'ok': True, **self.dist_listar(p)}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    def dist_listar(self, p=None):
        filas = self._db['distancia']
        out = {'filas': filas, 'ajuste': None, 'aviso': None, 'firma_actual': _firma(p) if p else None}
        validas = [r for r in filas if r.get('valido')]
        if len(filas) - len(validas):
            out['aviso'] = (f"{len(filas) - len(validas)} punto(s) excluido(s) del ajuste "
                            f"(SNR < {SNR_MIN_VALIDO:g} dB o saturación).")
        if len({r['d'] for r in validas}) >= 2:
            d = [r['d'] for r in validas]
            P = [r['p_db'] for r in validas]
            aj = pr.ajustar_log_distancia(d, P)
            dd, pp = pr.curva_modelo(d, aj)
            out['ajuste'] = {k: v for k, v in aj.items() if k != 'residuos'}
            out['ajuste']['interpreta'] = pr.interpretar_exponente(aj['n'])
            out['curva'] = {'d': _r(dd, 3), 'p': _r(pp, 2), 'p_fs': _r(pr.modelo_log_distancia(dd, aj['p0'], 2.0), 2)}
            out['d_min'], out['d_max'] = float(min(d)), float(max(d))
            res = {r['id']: x for r, x in zip(validas, aj['residuos'])}
            for r in filas:
                r['residuo_db'] = res.get(r['id'])
        out['firma_ref'] = filas[0]['firma'] if filas else None
        return out

    # ================================================================ 05 obstrucciones
    def obst_medir(self, p):
        try:
            cond = (p['obst_cond'] or 'LOS').strip()
            d = float(p['obst_dist'])
            ctx = {'d': d, 'sombra': float(self._rng.normal(0, 0.7)),
                   'obst': 0.0 if cond.upper() == 'LOS' or p.get('sim_olvido') else float(p['obst_sim_db'])}
            pt = self._medir_punto(p, ctx, p['n_caps'], 'o')
            pt['cond'] = 'LOS' if cond.upper() == 'LOS' else cond
            pt['d'] = d
            self._db['obstruccion'].append(pt)
            self._guardar()
            return {'ok': True, **self.obst_listar(p)}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    def obst_listar(self, p=None):
        filas = self._db['obstruccion']
        grupos = ob.agrupar_por_condicion(filas) if filas else []
        tabla = ob.atenuacion_vs_los(grupos)
        ds = sorted({r['d'] for r in filas})
        return {'firma_actual': _firma(p) if p else None, 'filas': filas, 'grupos': grupos, 'tabla': tabla, 'hay_los': any(g['cond'] == 'LOS' for g in grupos),
                'aviso': ('Las mediciones usan distancias distintas: ' + ', '.join(f'{d:g} m' for d in ds)
                          if len(ds) > 1 else None)}

    # ================================================================ 06a fading
    def fad_plan(self, p):
        pl = fd.plan_barrido(float(p['fc']), float(p['fad_nlam']), float(p['fad_frac']))
        return pl

    def fad_medir(self, p, idx=None):
        try:
            pl = fd.plan_barrido(float(p['fc']), float(p['fad_nlam']), float(p['fad_frac']))
            idx = int(p['fad_idx'] if idx is None else idx)
            pos = idx * pl['paso_m']
            ctx = {'d': float(p['fad_dist']), 'pos': 0.0 if p.get('sim_olvido') else pos,
                   'esc': p['fad_esc'], 'sombra': 0.0}
            pt = self._medir_punto(p, ctx, p['n_caps'], 'f')
            pt['idx'], pt['pos_m'] = idx, pos
            self._db['fading'] = [r for r in self._db['fading'] if r['idx'] != idx] + [pt]
            self._db['fading'].sort(key=lambda r: r['idx'])
            self._guardar()
            return {'ok': True, **self.fad_listar(p)}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    def fad_barrido_sim(self, p):
        try:
            if p['rx_hw'] != 'sim':
                return {'ok': False, 'error': 'El barrido automático solo existe con fuente simulada; con hardware se mueve el RX a mano.'}
            pl = fd.plan_barrido(float(p['fc']), float(p['fad_nlam']), float(p['fad_frac']))
            self._db['fading'] = []
            for i in range(pl['n_pos']):
                self.fad_medir({**p, 'n_caps': 1}, i)
            return {'ok': True, **self.fad_listar(p)}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    def fad_listar(self, p):
        filas = self._db['fading']
        pl = fd.plan_barrido(float(p['fc']), float(p['fad_nlam']), float(p['fad_frac']))
        out = {'filas': filas, 'firma_actual': _firma(p), 'plan': {k: v for k, v in pl.items() if k != 'posiciones_m'},
               'stats': None, 'hist': None}
        if len(filas) >= 8:
            pos = [r['pos_m'] for r in filas]
            P = [r['p_db'] for r in filas]
            out['stats'] = fd.estadisticas_fading(pos, P, float(p['fc']))
            out['hist'] = fd.histograma_envolvente(P)
        return out

    # ================================================================ 06b canal
    def canal_medir(self, p):
        try:
            cfg = _cfg(p)
            esc = p['canal_esc']
            ctx = {'d': float(p['canal_dist']), 'esc': 'los' if p.get('sim_olvido') else esc, 'sombra': 0.0}
            pt = self._medir_punto(p, ctx, p['n_caps'], 'c', con_canal=True)
            pdp, raw, h = pt.pop('_pdp'), pt.pop('_raw'), pt.pop('_h')
            fs_i = cfg.fs * INTERP
            pre_i = max(2, len(h) // 12) * INTERP
            comps = ca.detectar_componentes(pdp, fs_i, pre_i, sep=INTERP)
            disp = ca.parametros_dispersion(raw, cfg.fs, max(2, len(h) // 12))
            f, hdb, rizado = ca.respuesta_en_frecuencia(h, cfg.fs)
            tau = (np.arange(pdp.size) - pre_i) / fs_i * 1e9
            pdp_db = pa.a_db(pdp / pdp.max())
            pt.update({'esc': esc, 'tau_ns': _r(tau, 2), 'pdp_db': _r(pdp_db, 2), 'comps': comps,
                       'disp': disp, 'rizado_db': rizado, 'f_khz': _r(f / 1e3, 1), 'h_db': _r(hdb, 2),
                       'resol_ns': cfg.resol_t_ns})
            self._db['canal'][esc] = pt
            self._guardar()
            return {'ok': True, **self.canal_listar(p)}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    def canal_listar(self, p=None):
        return {'canal': self._db['canal'], 'firma_actual': _firma(p) if p else None}

    # ================================================================ 07 análisis
    def analisis(self, p):
        try:
            dist = obst = fad = canal = None
            d = self.dist_listar(p)
            if d['ajuste']:
                dist = {**d['ajuste'], 'd_min': d['d_min'], 'd_max': d['d_max']}
            o = self.obst_listar(p)
            if o['hay_los'] and len(o['tabla']) > 1:
                obst = [r for r in o['tabla'] if r['cond'] != 'LOS']
            f = self.fad_listar(p)
            if f['stats']:
                fad = f['stats']
            c = self._db['canal'].get('multi') or self._db['canal'].get('los')
            if c:
                canal = {'rizado_db': c['rizado_db'], 'tau_rms_ns': c['disp']['tau_rms_ns'],
                         'bc_mhz': c['disp'].get('bc_mhz') or 0.0, 'n_comp': len(c['comps'])}
            filas = an.comparar_efectos(dist, obst, fad, canal)
            return {'ok': True, 'filas': filas, 'dist': d, 'obst': o, 'fad': f['stats'], 'canal': self._db['canal'],
                    'n': {'distancia': len(self._db['distancia']), 'obstruccion': len(self._db['obstruccion']),
                          'fading': len(self._db['fading']), 'canal': len(self._db['canal'])}}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    # ================================================================ modo guiado
    def guia_red(self, ip):
        """¿Este PC tiene una interfaz en la red del USRP y el equipo responde (ping + UHD)?"""
        try:
            red = ipaddress.ip_network(f'{ip.strip()}/24', strict=False)
            ifs = json.loads(subprocess.run(['ip', '-j', 'addr'], capture_output=True, text=True,
                                            timeout=5).stdout or '[]')
            propia = next((i['ifname'] for i in ifs for a in i.get('addr_info', [])
                           if a.get('family') == 'inet' and ipaddress.ip_address(a['local']) in red), None)
            pasos, comando = [], None
            if propia:
                pasos.append({'paso': 'IP de este PC', 'estado': 'ok', 'detalle': f'{propia} está en {red}'})
            else:
                eth = next((i['ifname'] for i in ifs if i['ifname'].startswith(('en', 'eth'))), '<interfaz>')
                libre = red.network_address + (1 if not ip.strip().endswith('.1') else 10)
                comando = f'sudo ip addr add {libre}/24 dev {eth} && sudo ip link set {eth} up'
                pasos.append({'paso': 'IP de este PC', 'estado': 'warn',
                              'detalle': f'ninguna interfaz está en {red}: ejecuta el comando de abajo'})
            sonda = radio.sonda_dispositivo(ip.strip(), abrir=False)
            pasos += en.evaluar_dispositivo('USRP', sonda)
            return {'ok': True, 'pasos': pasos, 'comando': comando, 'listo': bool(sonda['ping'] and sonda['uhd'])}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def _asegurar_tx(self, p):
        """Con el TX en este PC, lo (re)inicia si no está transmitiendo."""
        if p['tx_hw'] != 'usrp':
            return
        if not self._tx.estado['activo']:
            r = self.tx_iniciar(p)
            if not r['ok']:
                raise RuntimeError(r['error'])
            time.sleep(1.5)
        if self._tx.estado['error'] or not self._tx.estado['activo']:
            raise RuntimeError(f"El transmisor no arrancó: {self._tx.estado['error'] or 'se detuvo'}")

    def guia_tx(self, p):
        try:
            self._asegurar_tx(p)
            return {'ok': True, 'estado': dict(self._tx.estado)}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def guia_enlace(self, p):
        try:
            cfg = _cfg(p)
            self._asegurar_tx(p)
            x, info = self._adquirir(p, {'d': float(p['rx_dist_sim']), 'sombra': 0})
            m = po.medir_captura(x, cfg, float(p['umbral']))
            pasos = en.diagnosticar_captura(m, cfg)
            return {'ok': True, 'pasos': pasos, 'listo': en.veredicto(pasos) != 'ko'}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    def _refs(self, p, filas):
        """Medidas comparables: válidas, misma serie y sin dudas pendientes."""
        return [r for r in filas if r.get('valido') and r.get('firma') == _firma(p) and r.get('hw') == p['rx_hw']
                and (not r.get('dudoso') or r.get('confirmado_por_usuario'))]

    def guia_esperado(self, p, fase):
        """Texto de lo que debería pasar, para mostrarlo antes de medir."""
        try:
            if fase == 'distancia':
                d = float(p['dist_m'])
                pr = gu.prediccion_distancia(self._refs(p, self._db['distancia']), d)
                return (f"Esperado a {d:g} m: {pr['p']:.1f} ± {pr['tol']:.0f} dB" if pr
                        else 'Primera medida: servirá de referencia para las siguientes.')
            if fase == 'obstruccion':
                cond = p['obst_cond']
                los = [r for r in self._refs(p, self._db['obstruccion'])
                       if r['cond'] == 'LOS' and r['d'] == float(p['obst_dist'])]
                if cond == 'LOS':
                    return 'Referencia sin obstáculo: contra ella se comparan los demás.'
                t0, t1 = gu.MATERIALES.get(cond, gu.OTRO_MATERIAL)[:2]
                if not los:
                    return 'Falta la referencia LOS a esta distancia: mídela primero.'
                base = float(np.mean([r['p_db'] for r in los]))
                return f'Esperado con {cond.lower()}: entre {base - t1:.1f} y {base - t0:.1f} dB ({t0}–{t1} dB menos que LOS).'
            if fase == 'fading':
                return 'Esperado: la potencia sube y baja suavemente de una posición a la siguiente.'
            if p['canal_esc'] == 'los':
                return 'Esperado: un pico dominante y |H(f)| casi plano.'
            return 'Esperado: más ecos (mayor dispersión de retardo o rizado) que en línea de vista.'
        except Exception as e:
            return f'No se pudo estimar: {e}'

    def guia_medir(self, p, fase):
        """Mide con el módulo normal y valida el resultado contra lo esperado."""
        try:
            self._asegurar_tx(p)
            medir = {'distancia': self.dist_medir, 'obstruccion': self.obst_medir,
                     'fading': self.fad_medir, 'canal': self.canal_medir}[fase]
            r = medir(p)
            if not r['ok']:
                if fase == 'obstruccion' and p['obst_cond'] != 'LOS' and 'ráfaga' in r['error']:
                    r['error'] += (' Si el TX sigue activo, el obstáculo bloquea toda la señal: acorta la distancia '
                                   'de esta fase, vuelve a medir LOS y repite.')
                return r
            if fase == 'canal':
                ident = p['canal_esc']
                pt = self._db['canal'][ident]
                los = self._db['canal'].get('los')
                if los and (los.get('hw') != p['rx_hw'] or los.get('firma') != _firma(p)
                            or (los.get('dudoso') and not los.get('confirmado_por_usuario'))):
                    los = None
                v = gu.validar_canal(pt, los, ident)
            elif fase == 'fading':
                pt = next(x for x in self._db['fading'] if x['idx'] == int(p['fad_idx']))
                ident = pt['id']
                paso = fd.plan_barrido(float(p['fc']), float(p['fad_nlam']), float(p['fad_frac']))['paso_m']
                v = gu.validar_fading(pt, self._refs(p, self._db['fading']), paso * 100)
            else:
                pt = self._db[fase][-1]
                ident = pt['id']
                refs = [x for x in self._refs(p, self._db[fase]) if x['id'] != ident]
                if fase == 'distancia':
                    v = gu.validar_distancia(pt, refs, pt['d'])
                else:
                    refs = [x for x in refs if x['cond'] == 'LOS' and x['d'] == pt['d']]
                    v = gu.validar_obstruccion(pt, refs, pt['cond'])
            if v['estado'] == 'invalido':
                self.borrar(fase, ident)
                ident = None
            elif v['estado'] == 'sospechoso':
                pt['dudoso'] = v['pregunta']
                self._guardar()
            return {'ok': True, 'id': ident, **v}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'tb': traceback.format_exc()}

    def guia_confirmar(self, fase, ident):
        """El usuario asegura que el montaje era correcto: la medida dudosa se conserva marcada."""
        pt = (self._db['canal'].get(ident) if fase == 'canal'
              else next((r for r in self._db[fase] if r.get('id') == ident), None))
        if pt is None:
            return False
        pt['confirmado_por_usuario'] = True
        self._guardar()
        return True

    def guia_resumen(self):
        return {k: len(v) for k, v in self._db.items()}

    def guia_nueva_practica(self):
        """Archiva los resultados actuales y empieza con la base vacía."""
        try:
            copia = None
            if os.path.isfile(RESULTADOS):
                copia = os.path.join(MED, f"resultados_{time.strftime('%Y%m%d_%H%M%S')}.json")
                shutil.copy2(RESULTADOS, copia)
            self._db = {'distancia': [], 'obstruccion': [], 'fading': [], 'canal': {}}
            self._guardar()
            return {'ok': True, 'copia': copia}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ================================================================ borrar / exportar
    def borrar(self, clave, ident):
        if clave == 'canal':
            self._db['canal'].pop(ident, None)
        else:
            self._db[clave] = [r for r in self._db[clave] if r.get('id') != ident]
        self._guardar()
        return True

    def limpiar(self, clave):
        self._db[clave] = {} if clave == 'canal' else []
        self._guardar()
        return True

    def exportar_csv(self, clave):
        try:
            if clave == 'canal':
                filas = [{'escenario': k, 'tau_rms_ns': v['disp']['tau_rms_ns'], 'tau_medio_ns': v['disp']['tau_medio_ns'],
                          'bc_mhz': v['disp'].get('bc_mhz'), 'rizado_db': v['rizado_db'], 'n_comp': len(v['comps'])}
                         for k, v in self._db['canal'].items()]
            else:
                filas = [{k: v for k, v in r.items() if not isinstance(v, (list, dict))} for r in self._db[clave]]
            if not filas:
                return {'ok': False, 'error': 'No hay datos para exportar'}
            ruta = os.path.join(EXPORT, f'{clave}.csv')
            with open(ruta, 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
                w.writeheader()
                w.writerows(filas)
            return {'ok': True, 'ruta': ruta}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def guardar_png(self, nombre, data_url):
        try:
            seguro = ''.join(c if c.isalnum() or c in '-_' else '_' for c in nombre)[:60] or 'figura'
            ruta = os.path.join(EXPORT, f"{seguro}.png")
            with open(ruta, 'wb') as f:
                f.write(base64.b64decode(data_url.split(',', 1)[1]))
            return {'ok': True, 'ruta': ruta}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def cerrar(self):
        self._tx.detener()
        self._rx.cerrar()


if __name__ == '__main__':
    api = Api()
    win = webview.create_window('Práctica 3 · Canal inalámbrico con SDR', os.path.join(AQUI, 'web', 'index.html'),
                                js_api=api, width=1480, height=920, min_size=(1100, 700),
                                background_color='#0a0f1d')
    win.events.closed += api.cerrar
    webview.start(debug=os.environ.get('DEBUG') == '1', private_mode=False)    # recuerda parámetros y avance guiado
