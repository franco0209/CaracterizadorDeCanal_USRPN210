"""Manejo del USRP N210 (hardware): TX continuo en un hilo, RX persistente y sonda
de conexión. Es la única capa que habla con UHD; la física está en logica/.
"""
import subprocess
import threading
import time
import numpy as np

import sdr_iq
from logica.parametros import tasa_valida as _tasa_valida


def sonda_dispositivo(ip, abrir=True):
    """Comprueba un N210: ping, descubrimiento UHD y apertura (lee reloj/LO)."""
    r = {'ping': False, 'uhd': False, 'uhd_info': '', 'abre': None, 'detalle': ''}
    try:
        r['ping'] = subprocess.run(['ping', '-c', '1', '-W', '1', ip], capture_output=True,
                                   timeout=4).returncode == 0
    except Exception:
        pass
    try:
        import uhd
        hallados = uhd.find(f'addr={ip}')
        r['uhd'] = len(hallados) > 0
        if hallados:
            r['uhd_info'] = ' · '.join(f'{k}={v}' for k, v in dict(hallados[0].to_dict()).items()
                                       if k in ('type', 'product', 'serial', 'name') and v)
    except Exception as e:
        r['uhd_info'] = f'{type(e).__name__}: {e}'
    if abrir and r['uhd']:
        try:
            import uhd
            u = uhd.usrp.MultiUSRP(f'addr={ip}')
            r['abre'] = True
            r['detalle'] = f"{u.get_mboard_name()} · MCR {u.get_master_clock_rate() / 1e6:.0f} MHz"
        except Exception as e:
            r['abre'] = False
            r['detalle'] = f'{type(e).__name__}: {e}'
    return r


class TransmisorUSRP:
    """Repite una ráfaga I/Q en bucle hasta que se pida parar."""

    def __init__(self):
        self.hilo = None
        self.parar = threading.Event()
        self.estado = {'activo': False, 'enviadas': 0, 'rafagas': 0, 'error': None,
                       'underflows': 0, 'fs_real': None}

    def iniciar(self, x, fc, fs, gain, ip, repeticiones=0):
        if self.hilo and self.hilo.is_alive():
            raise RuntimeError('El transmisor ya está activo')
        self.parar.clear()
        self.estado.update({'activo': True, 'enviadas': 0, 'rafagas': 0, 'error': None,
                            'underflows': 0})
        self.hilo = threading.Thread(target=self._bucle, daemon=True,
                                     args=(np.asarray(x, np.complex64), fc, fs, gain, ip, repeticiones))
        self.hilo.start()

    def detener(self):
        self.parar.set()
        if self.hilo:
            self.hilo.join(timeout=3)
        self.estado['activo'] = False

    def _bucle(self, x, fc, fs, gain, ip, repeticiones):
        try:
            import uhd
            usrp = uhd.usrp.MultiUSRP(f"addr={ip}")
            usrp.set_tx_rate(_tasa_valida(fs), 0)
            usrp.set_tx_freq(uhd.types.TuneRequest(fc), 0)
            usrp.set_tx_gain(gain, 0)
            self.estado['fs_real'] = usrp.get_tx_rate(0)
            t0 = time.time()
            while not usrp.get_tx_sensor("lo_locked", 0).to_bool():
                if time.time() - t0 > 1.0: break
                time.sleep(0.01)

            st = uhd.usrp.StreamArgs("fc32", "sc16")
            st.channels = [0]
            tx = usrp.get_tx_stream(st)
            md = uhd.types.TXMetadata()
            nmax = tx.get_max_num_samps()
            buf = x.reshape(1, -1)
            k = 0
            while not self.parar.is_set() and (repeticiones <= 0 or k < repeticiones):
                for i in range(0, x.size, nmax):
                    if self.parar.is_set():
                        break
                    md.start_of_burst = (k == 0 and i == 0)
                    md.end_of_burst = False
                    self.estado['enviadas'] += tx.send(buf[:, i:i + nmax], md)
                k += 1
                self.estado['rafagas'] = k
            md.start_of_burst, md.end_of_burst = False, True
            tx.send(np.zeros((1, 0), np.complex64), md)
        except Exception as e:  # al UI le llega el texto del error
            self.estado['error'] = f'{type(e).__name__}: {e}'
        finally:
            self.estado['activo'] = False


class ReceptorUSRP:
    """Mantiene abierto el USRP entre capturas: crear MultiUSRP tarda segundos."""

    def __init__(self):
        self.usrp = self.rx = None
        self.cfg = None
        self.lock = threading.Lock()

    def _abrir(self, fc, fs, gain, ip):
        import uhd
        clave = (ip, fs)
        if self.usrp is None or self.cfg[0] != clave:
            self.usrp = uhd.usrp.MultiUSRP(f"addr={ip}")
            self.usrp.set_rx_rate(_tasa_valida(fs), 0)
            st = uhd.usrp.StreamArgs("fc32", "sc16")
            st.channels = [0]
            self.rx = self.usrp.get_rx_stream(st)
            self.cfg = (clave, None, None)
        if self.cfg[1:] != (fc, gain):
            self.usrp.set_rx_freq(uhd.types.TuneRequest(fc), 0)
            self.usrp.set_rx_gain(gain, 0)
            t0 = time.time()
            while not self.usrp.get_rx_sensor("lo_locked", 0).to_bool():
                if time.time() - t0 > 1.0: break
                time.sleep(0.01)
            self.cfg = (clave, fc, gain)

    def capturar(self, fc, fs, gain, n, ip):
        import uhd
        with self.lock:
            self._abrir(fc, fs, gain, ip)
            n_desc = 8192                                   # arranque sucio
            cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
            cmd.num_samps = int(n) + n_desc
            cmd.stream_now = True
            self.rx.issue_stream_cmd(cmd)
            nmax = self.rx.get_max_num_samps()
            buf = np.zeros((1, nmax), np.complex64)
            out = np.zeros(int(n) + n_desc, np.complex64)
            md = uhd.types.RXMetadata()
            k, overflow = 0, 0
            while k < out.size:
                r = self.rx.recv(buf, md, 1.0)
                if md.error_code == uhd.types.RXMetadataErrorCode.overflow:
                    overflow += 1
                    continue
                if md.error_code != uhd.types.RXMetadataErrorCode.none:
                    if md.error_code == uhd.types.RXMetadataErrorCode.timeout:
                        break
                    raise RuntimeError(f'Error RX: {md.strerror()}')
                m = min(r, out.size - k)
                out[k:k + m] = buf[0, :m]
                k += m
            x = out[n_desc:k].astype(np.complex128)
            return x, {'hw': 'usrp', 'fc': fc, 'fs': fs, 'gain': gain, 'n': n,
                       'fs_real': self.usrp.get_rx_rate(0), 'overflow': overflow, 'n_real': x.size}

    def cerrar(self):
        self.usrp = self.rx = None


def capturar(receptor, hw, fc, fs, gain, n, opts):
    if hw == 'usrp':
        return receptor.capturar(fc, fs, gain, n, opts.get('ip', '192.168.10.2'))
    return sdr_iq.capturar_iq(hw, fc, fs, gain, n, opts)
