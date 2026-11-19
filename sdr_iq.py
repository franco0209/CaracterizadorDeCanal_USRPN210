"""Capa de captura intercambiable. El resto del código no se entera del radio."""
import numpy as np


def capturar_iq(hw, fc, fs, gain, n, opts=None):
    """Devuelve (x, info). x = complex128 normalizado a +-1."""
    opts = opts or {}
    info = {'hw': hw, 'fc': fc, 'fs': fs, 'gain': gain, 'n': n,
            'fs_real': fs, 'overflow': 0}

    if hw == 'usrp':
        import uhd
        addr = opts.get('ip', '192.168.10.2')
        usrp = uhd.usrp.MultiUSRP(f"addr={addr}")
        mcr = opts.get('mcr', 100e6)               # N210: 100 MHz
        dec = int(max(4, min(512, round(mcr / fs))))
        if dec > 128: dec += dec % 2               # pares si > 128
        if dec > 256: dec = (dec // 4) * 4         # múltiplo de 4 si > 256
        usrp.set_rx_rate(mcr / dec, 0)
        usrp.set_rx_freq(uhd.types.TuneRequest(fc), 0)
        usrp.set_rx_gain(gain, 0)
        info['fs_real'] = usrp.get_rx_rate(0)

        # esperar lock del LO
        import time
        t0 = time.time()
        while not usrp.get_rx_sensor("lo_locked", 0).to_bool():
            if time.time() - t0 > 1.0: break
            time.sleep(0.01)

        # descartar arranque, luego capturar
        usrp.recv_num_samps(int(4096), fc, info['fs_real'], [0], gain)
        x = usrp.recv_num_samps(int(n), fc, info['fs_real'], [0], gain)[0]


    elif hw == 'rtl':
        from rtlsdr import RtlSdr
        sdr = RtlSdr()
        sdr.center_freq = fc
        sdr.sample_rate = fs                        # estable hasta 2.4 MSps
        sdr.gain = gain
        x = sdr.read_samples(int(n) + 4096)[4096:]  # boto el arranque, sale sucio
        sdr.close()

    elif hw == 'pluto':
        import adi
        sdr = adi.Pluto(opts.get('uri', 'ip:192.168.2.1'))
        sdr.rx_lo = int(fc)
        sdr.sample_rate = int(fs)
        sdr.gain_control_mode_chan0 = 'manual'
        sdr.rx_hardwaregain_chan0 = gain
        sdr.rx_buffer_size = int(n)
        sdr.rx()                                    # descarto el primer buffer
        x = sdr.rx() / 2**11

    elif hw == 'archivo':
        d = np.fromfile(opts['archivo'], dtype=np.int16, count=2 * int(n))
        x = (d[0::2].astype(np.float64) + 1j * d[1::2]) / 2048.0  # SC16 Q11

    else:
        raise ValueError(f"hw desconocido: {hw}")

    x = np.asarray(x, dtype=np.complex128).ravel()[:int(n)]
    info['n_real'] = x.size
    return x, info
